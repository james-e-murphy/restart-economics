"""Extract execution and prefix tables from an OpenHands SWE-bench evaluation archive.

Reads, per run directory, exactly three files: ``output.jsonl`` (one line per instance:
metrics with per-call token usage and cost, history, error, the dataset row), ``report.json``
(the SWE-bench evaluation report with resolved / unresolved / empty-patch ids), and
``metadata.json`` (the run configuration). From each instance's evaluation folder,
``eval_outputs/<instance_id>/``, it records which files exist and reads the evaluation log and
test output, so that an instance the report lists as an evaluation error can be classified as
a patch that did not apply or a verifier failure. From the per-call completion logs,
``llm_completions/<instance_id>/*.json``, it reads each log's timestamp, ``cost`` and reported
reasoning tokens: a second
record of the calls, which confirms the run's metrics call by call and reveals tries the harness
ran and discarded after a crash, whose calls the metrics omit. Everything else is skipped unread.

Outputs, per configuration (a run directory name with its run index removed):

    executions_<config>.csv   one row per instance x run
    prefix_<config>.csv       one row per instance x run x call
    actions_<config>.csv      one row per instance x run: the agent's actions in order, as short
                              signatures of action type and defining arguments (no text)
    audit_<config>.json       the census AUDIT.md asks for: terminal states, error strings,
                              stopping rules, sampling settings, usable draws per task

Physical quantities only. The provider's logged per-call cost is carried as ``cost_logged``
because it is an observation and the validation target for ``restart.pricing``; no
reconstructed dollars are written here.

Usage:
    python -m restart.extract ARCHIVE.tar.gz --out data/derived/
    python -m restart.extract EXTRACTED_DIR  --out data/derived/
    curl -sL URL | python -m restart.extract - --out data/derived/     # streamed, never stored
    python -m restart.extract --reclassify --out data/derived/           # re-apply rules, no archive
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import glob
import hashlib
import io
import json
import os
import re
import sys
import tarfile
from typing import Iterator

# ----------------------------------------------------------------------------- terminal states

# Error-string patterns for provider-side stops, checked in order; the first match wins (a refusal
# string also contains ERROR_LLM_, so the refusal pattern must come first).
PROVIDER_ERRORS = (
    ("provider_refusal", re.compile(r"CONTENT_POLICY", re.I)),
    # a request the provider failed to serve, including an upstream error relayed by a router
    # with no further detail, is not the configuration's response to the attempt
    ("infrastructure",   re.compile(r"SERVICE_UNAVAILABLE|RATE_LIMIT|ERROR_LLM_|Timeout after|"
                                    r"Connection|APIError|InternalServerError|Provider returned error", re.I)),
)
RETAINED = (
    ("iteration_limit", re.compile(r"maximum iteration", re.I)),
    ("loop_detector",   re.compile(r"stuck in a loop", re.I)),
)
# Stop states excluded from the attempt pool under the primary rule: an outage is not the
# provider's response to the attempt. A refusal is, and is retained; excluding refusals too is
# the prespecified sensitivity (retain_refusals=False).
EXCLUDED_STATES = {"infrastructure"}
# Rows the audit lists individually: every stop other than an ordinary finish or a provider error.
NOT_NOTABLE = ("resolved", "unresolved", "empty_patch", "provider_refusal", "infrastructure")
# The evaluation log's marker that the agent's patch did not apply. An evaluation that fails
# for any other reason leaves the outcome unobserved.
APPLY_FAILED = re.compile(r"APPLY_PATCH_FAIL|Patch Apply Failed", re.I)
VERDICT_STATE = {"resolved": "resolved", "unresolved": "unresolved", "empty_patch": "empty_patch",
                 "apply_failed": "apply_failed", "no_verdict": "eval_error", "none": "unknown"}


def report_class(instance_id: str, report: dict) -> str:
    """Which list of the run report an instance appears in."""
    for k in ("resolved", "empty_patch", "error", "unresolved"):
        if instance_id in report.get(k, ()):
            return k
    return "none"


def verdict(report_cls: str, apply_failed: bool) -> str:
    """The evaluation outcome. An instance in the report's error list resolved nothing; whether
    that is the agent's doing depends on the evaluation log: a patch that did not apply is the
    agent's invalid output, anything else is a verifier failure with no verdict."""
    if report_cls == "error":
        return "apply_failed" if apply_failed else "no_verdict"
    return report_cls


def classify(error: str | None, verdict_: str, n_calls: int,
             max_iterations: int | None, retain_refusals: bool = True) -> tuple[str, bool, bool, bool]:
    """Return (terminal_state, resolved, hit_limit, usable).

    The terminal state records how the attempt stopped; ``resolved`` records the evaluation
    verdict. They are separate because the harness evaluates whatever diff exists when it stops,
    including at its own iteration limit or loop detector, so a harness-stopped attempt can
    still resolve.

    An attempt is usable when it is a draw from the configuration's behaviour and its outcome
    was observed. An infrastructure error (outage, rate limit, runtime timeout) is not a draw. A
    provider refusal is the provider's response to the attempt's content: the operator pays for
    it and the harness scores what the attempt produced, so it is retained as a stop like the
    harness's own, scored by the report. An evaluation that returned no verdict, or an instance
    absent from the report, is a draw whose outcome is unobserved. Empty patches and patches
    that did not apply are observed failures.

    ``retain_refusals=False`` excludes refusals as well: the prespecified sensitivity.
    """
    e = error or ""
    resolved = verdict_ == "resolved"
    observed = verdict_ not in ("no_verdict", "none")
    hit_limit = bool(RETAINED[0][1].search(e)) or (
        max_iterations is not None and n_calls >= max_iterations)
    for name, pat in PROVIDER_ERRORS:
        if pat.search(e):
            if name == "provider_refusal" and retain_refusals:
                return name, resolved, hit_limit, observed
            return name, False, hit_limit, False
    for name, pat in RETAINED:
        if pat.search(e):
            return name, resolved, hit_limit, observed
    if e:
        return "other_error", resolved, hit_limit, observed
    if hit_limit:
        return "iteration_limit", resolved, hit_limit, observed
    return VERDICT_STATE[verdict_], resolved, hit_limit, observed


def reclassify(row: dict, retain_refusals: bool = True) -> tuple[str, bool, bool, bool]:
    """Recompute the classification from an execution-table row alone, so that a rule can be
    changed and re-applied without the archive, which for streamed configurations is not kept."""
    mi = row.get("max_iterations")
    af = row.get("eval_apply_failed")
    v = verdict(row["report_class"], af in (True, "True"))
    return classify(row.get("error") or None, v, int(row["n_calls"]),
                    int(mi) if mi not in (None, "") else None, retain_refusals)


# ----------------------------------------------------------------------------- archive reading

RUN_DIR_RE = re.compile(r"^(?P<config>.+?)-run_(?P<run>\d+)$")
WANTED = ("output.jsonl", "report.json", "metadata.json")


class _HashingReader:
    """Wraps a binary stream and hashes every byte pulled through it, so a streamed archive
    that is never stored still gets the same SHA-256 that ``shasum -a 256`` would give the file."""

    def __init__(self, fh):
        self._fh = fh
        self._h = hashlib.sha256()

    def read(self, n: int = -1) -> bytes:
        b = self._fh.read(n)
        self._h.update(b)
        return b

    def drain(self) -> str:
        """Consume whatever tarfile left after the end-of-archive marker and return the digest."""
        for chunk in iter(lambda: self._fh.read(1 << 20), b""):
            self._h.update(chunk)
        return self._h.hexdigest()


def _is_run_file(parent: str, fn: str) -> bool:
    """A wanted file sitting directly in a run directory. The evaluation logs nest a
    per-instance ``report.json`` under each instance id; those are not the run report."""
    return fn in WANTED and RUN_DIR_RE.match(parent) is not None


# Per-instance evaluation files, ``<run_dir>/eval_outputs/<instance_id>/<file>``: which exist is
# recorded for every instance; these two are also read, for the apply-failure marker and a tail.
EVAL_TAILS = {"run_instance.log": 2000, "test_output.txt": 600}


def _eval_evidence(holder: dict, run_dir: str, iid: str, fn: str, read) -> None:
    ev = holder["eval"].setdefault((run_dir, iid), dict(files=set(), apply_failed=False))
    ev["files"].add(fn)
    if fn in EVAL_TAILS:
        text = read().decode("utf-8", "replace")
        if fn == "run_instance.log" and APPLY_FAILED.search(text):
            ev["apply_failed"] = True
        ev[fn] = text[-EVAL_TAILS[fn]:]


_COST_NUM = re.compile(rb'\s*:\s*(-?[0-9][0-9.eE+-]*|null)')


def _completion_cost(b: bytes) -> float | None:
    """The top-level ``cost`` of one per-call completion log, which OpenHands writes as the last
    key. Read from the end of the file rather than by parsing the whole message history."""
    i = b.rfind(b'"cost"')
    if i < 0:
        return None
    m = _COST_NUM.match(b, i + len(b'"cost"'))
    if not m or m.group(1) == b"null":
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


_LOG_TS = re.compile(r"-(\d+(?:\.\d+)?)\.json$")


_INT_AFTER = re.compile(rb'\s*:\s*(\d+|null)')


def _reasoning_tokens(b: bytes) -> int | None:
    """Reasoning tokens as the provider reports them in the logged response's usage, or None
    where the provider does not report them."""
    i = b.rfind(b'"reasoning_tokens"')
    if i < 0:
        return None
    m = _INT_AFTER.match(b, i + len(b'"reasoning_tokens"'))
    return int(m.group(1)) if m and m.group(1) != b"null" else None


def _completion_log(holder: dict, run_dir: str, iid: str, fn: str, read) -> None:
    """Record one completion log's timestamp (from its file name), cost, and reasoning tokens."""
    logs = holder["completions"].setdefault((run_dir, iid), [])
    m = _LOG_TS.search(fn)
    b = read()
    logs.append((float(m.group(1)) if m else None, len(logs), _completion_cost(b), _reasoning_tokens(b)))


def _split_logs(logs: list, n_calls: int, metric_cost: float | None) -> dict:
    """Split an execution's completion logs into the final try, which the run's metrics describe,
    and any earlier tries the harness ran and discarded after a crash. The final try is the last
    ``n_calls`` logs in time order; it is confirmed when their costs sum to the metrics' cost."""
    logs = sorted(logs, key=lambda x: (x[0] is None, x[0] or 0.0, x[1]))
    n = len(logs)
    final, prior = (logs[-n_calls:], logs[:-n_calls]) if 0 < n_calls <= n else ((logs, []) if n < n_calls else ([], logs))
    known = lambda xs: all(x[2] is not None for x in xs)      # a log can lack its cost field
    fsum = sum(x[2] or 0.0 for x in final)
    reasoning = [x[3] for x in final if x[3] is not None]
    return dict(
        n_completion_logs=n,
        completion_logs_missing_cost=sum(x[2] is None for x in logs),
        completion_cost_logged=round(sum(x[2] or 0.0 for x in logs), 10) if (n and known(logs)) else None,
        prior_try_logs=len(prior),
        prior_try_cost_logged=round(sum(x[2] or 0.0 for x in prior), 10) if known(prior) else None,
        # judged on the final try's own logs, so a missing cost among discarded tries does not
        # count against it; None where the final try's logs themselves lack a cost
        final_try_matches_metrics=(None if n == 0 or not known(final) else
                                   n >= n_calls and abs(fsum - (metric_cost or 0.0)) <= 1e-6),
        final_try_logs_reporting_reasoning=len(reasoning),
        final_try_reasoning_tokens=sum(reasoning) if reasoning else None,
    )


def _slurp(p: str) -> bytes:
    with open(p, "rb") as fh:
        return fh.read()


def _iter_archive(path: str, holder: dict) -> Iterator[tuple[str, str, bytes]]:
    """Yield (run_dir, filename, bytes) for the three wanted files, from a tar.gz stream on
    stdin, a tar.gz file, or an already-extracted directory. Evaluation evidence is collected
    into ``holder["eval"]`` on the way past. On return, ``holder["sha256"]`` holds the archive
    digest (None for a directory) and ``holder["nested_ignored"]`` counts same-named files
    found outside run directories."""
    holder["sha256"] = None
    holder["nested_ignored"] = 0
    holder["top_dirs"] = collections.Counter()
    holder["eval"] = {}
    holder["completions"] = {}
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            parent = os.path.basename(root)
            up = os.path.dirname(root)
            for fn in files:
                if _is_run_file(parent, fn):
                    with open(os.path.join(root, fn), "rb") as fh:
                        yield parent, fn, fh.read()
                    continue
                if (os.path.basename(up) == "llm_completions" and fn.endswith(".json")
                        and RUN_DIR_RE.match(os.path.basename(os.path.dirname(up)))):
                    _completion_log(holder, os.path.basename(os.path.dirname(up)), parent, fn,
                                    lambda p=os.path.join(root, fn): _slurp(p))
                    continue
                if os.path.basename(up) == "eval_outputs" and RUN_DIR_RE.match(os.path.basename(os.path.dirname(up))):
                    _eval_evidence(holder, os.path.basename(os.path.dirname(up)), parent, fn,
                                   lambda p=os.path.join(root, fn): _slurp(p))
                if fn in WANTED:
                    holder["nested_ignored"] += 1
        return
    raw = sys.stdin.buffer if path == "-" else open(path, "rb")
    reader = _HashingReader(raw)
    try:
        with tarfile.open(fileobj=reader, mode="r|gz") as tf:
            for m in tf:
                if not m.isfile():
                    continue
                parts = m.name.split("/")
                if len(parts) >= 3:
                    holder["top_dirs"][parts[1]] += 1
                if len(parts) < 2:
                    continue
                if _is_run_file(parts[-2], parts[-1]):
                    fh = tf.extractfile(m)
                    if fh is not None:
                        yield parts[-2], parts[-1], fh.read()
                    continue
                if (len(parts) >= 4 and parts[-3] == "llm_completions" and parts[-1].endswith(".json")
                        and RUN_DIR_RE.match(parts[-4])):
                    _completion_log(holder, parts[-4], parts[-2], parts[-1],
                                    lambda m=m: (tf.extractfile(m) or io.BytesIO()).read())
                    continue
                if len(parts) >= 4 and parts[-3] == "eval_outputs" and RUN_DIR_RE.match(parts[-4]):
                    _eval_evidence(holder, parts[-4], parts[-2], parts[-1],
                                   lambda m=m: (tf.extractfile(m) or io.BytesIO()).read())
                if parts[-1] in WANTED:
                    holder["nested_ignored"] += 1
        holder["sha256"] = reader.drain()
    finally:
        if raw is not sys.stdin.buffer:
            raw.close()


_SECRET_KEY = re.compile(r"(api_?key|secret|password|credential|token$|aws_access|aws_session)", re.I)
_SECRET_VAL = re.compile(r"(sk-[A-Za-z0-9_\-]{12,}|sk_[A-Za-z0-9_\-]{12,}|AKIA[0-9A-Z]{12,}|"
                         r"gh[po]_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|xox[bp]-[A-Za-z0-9\-]{10,})")


def _redact(obj):
    """Anything that could be a credential replaced, so that what is written can be kept in a
    public repository: values under keys that name a secret, and strings shaped like a key."""
    if isinstance(obj, dict):
        return {k: ("<redacted>" if _SECRET_KEY.search(str(k)) and v not in (None, "", False)
                    else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    if isinstance(obj, str) and _SECRET_VAL.search(obj):
        return _SECRET_VAL.sub("<redacted>", obj)
    return obj


def _utc(t: float) -> str:
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _version_from(run_dir: str) -> str | None:
    m = re.search(r"_v(\d+\.\d+\.\d+)", run_dir)
    return m.group(1) if m else None


# ----------------------------------------------------------------------------- action sequences

# Arguments that make two agent actions the same action. The model's free-text reasoning
# ("thought") and bookkeeping fields are left out, so that two runs that do the same thing for
# differently worded reasons count as agreeing.
SIG_KEYS = ("command", "path", "code", "old_str", "new_str", "file_text", "insert_line",
            "view_range", "url", "content", "start", "end")
CONTENT_FREE = {"finish", "think", "message"}
NOT_AGENT_STEPS = {"change_agent_state", "recall", "system", "condensation", "condensation_request"}


def agent_actions(history) -> list[str]:
    """The agent's actions in order, each as an 8-character signature of the action type and
    the arguments that define it. Observations, user and system events are skipped."""
    sigs = []
    for ev in history or ():
        if not isinstance(ev, dict) or ev.get("source") != "agent" or "action" not in ev:
            continue
        a = ev.get("action")
        if a in NOT_AGENT_STEPS:
            continue
        args = ev.get("args") or {}
        core = {} if a in CONTENT_FREE else {k: args[k] for k in SIG_KEYS if k in args}
        sigs.append(hashlib.sha1(json.dumps([a, core], sort_keys=True, default=str).encode()).hexdigest()[:8])
    return sigs


def divergence(seqs: list[list[str]]) -> int | None:
    """First position at which the runs' action sequences are not all equal; a run that has
    already ended differs from one that continues. None when every sequence is identical."""
    if len(seqs) < 2 or all(s == seqs[0] for s in seqs):
        return None
    i = 0
    while True:
        heads = {s[i] if i < len(s) else None for s in seqs}
        if len(heads) > 1:
            return i
        i += 1


# ----------------------------------------------------------------------------- per-run reduction

def reduce_run(run_dir: str, files: dict[str, bytes], sha: str | None = None):
    """Turn one run's three files into execution rows, prefix rows, a census, and config metadata.
    ``sha`` is stamped on execution rows; the driver fills it in after the archive is fully read."""
    m = RUN_DIR_RE.match(run_dir)
    if not m:
        raise ValueError(f"run directory does not end in -run_N: {run_dir}")
    config, run = m.group("config"), int(m.group("run"))

    meta = json.loads(files["metadata.json"])
    rep = json.loads(files["report.json"])
    report = {
        "resolved": set(rep.get("resolved_ids", [])),
        "unresolved": set(rep.get("unresolved_ids", [])),
        "empty_patch": set(rep.get("empty_patch_ids", [])),
        "error": set(rep.get("error_ids", [])),
    }
    llm = meta.get("llm_config") or {}
    max_iter = meta.get("max_iterations")
    cond = (meta.get("condenser_config") or {}).get("type")

    execs, prefix = [], []
    census = dict(errors=collections.Counter(), budget_caps=set(), calls=[], n=0,
                  actions=collections.Counter(), metadata=_redact(meta),
                  report_lists={k: len(v) for k, v in sorted(rep.items())
                                if k.endswith("_ids") and isinstance(v, list)})

    for line in io.BytesIO(files["output.jsonl"]):
        if not line.strip():
            continue
        d = json.loads(line)
        iid = d["instance_id"]
        metrics = d.get("metrics") or {}
        usages = metrics.get("token_usages") or []
        costs = metrics.get("costs") or []
        lats = metrics.get("response_latencies") or []
        inst = d.get("instance") or {}
        error = d.get("error")
        n_calls = len(usages)
        history = d.get("history") or []
        sigs = agent_actions(history)
        for ev in history:
            if isinstance(ev, dict) and ev.get("source") == "agent" and "action" in ev:
                census["actions"][str(ev.get("action"))] += 1

        census["errors"][str(error)[:80] if error else "None"] += 1
        census["budget_caps"].add(str(metrics.get("max_budget_per_task")))
        census["calls"].append(n_calls)
        census["n"] += 1

        cum = dict(prompt=0, completion=0, cache_read=0, cache_write=0, cost=0.0)
        t0 = costs[0]["timestamp"] if costs else None
        for k, u in enumerate(usages, start=1):
            c_k = costs[k - 1] if k - 1 < len(costs) else {}
            cost_k, ts_k = c_k.get("cost"), c_k.get("timestamp")
            lat_k = lats[k - 1].get("latency") if k - 1 < len(lats) else None
            cum["prompt"] += u.get("prompt_tokens") or 0
            cum["completion"] += u.get("completion_tokens") or 0
            cum["cache_read"] += u.get("cache_read_tokens") or 0
            cum["cache_write"] += u.get("cache_write_tokens") or 0
            if cost_k is not None:
                cum["cost"] += cost_k
            prefix.append(dict(
                config=config, run=run, instance_id=iid, call=k,
                prompt_tokens=u.get("prompt_tokens"), completion_tokens=u.get("completion_tokens"),
                cache_read_tokens=u.get("cache_read_tokens"), cache_write_tokens=u.get("cache_write_tokens"),
                cost_logged=cost_k, latency_s=lat_k,
                elapsed_s=(ts_k - t0) if (ts_k is not None and t0 is not None) else None,
                cum_prompt=cum["prompt"], cum_completion=cum["completion"],
                cum_cache_read=cum["cache_read"], cum_cache_write=cum["cache_write"],
                cum_cost_logged=round(cum["cost"], 10),
                frac_of_limit=(k / max_iter) if max_iter else None,
            ))

        execs.append(dict(
            config=config, run=run, instance_id=iid, archive_sha256=sha,
            repo=inst.get("repo"), difficulty=inst.get("difficulty"),
            model=llm.get("model"), harness_version=_version_from(run_dir),
            git_commit=meta.get("git_commit"), start_time=meta.get("start_time"),
            max_iterations=max_iter, budget_cap=metrics.get("max_budget_per_task"),
            temperature=llm.get("temperature"), condenser=cond,
            # classification is completed by the driver once the evaluation evidence, which
            # streams past after this file, has been read
            n_calls=n_calls, terminal_state=None, usable=None, resolved=None, hit_limit=None,
            error=(str(error)[:2000] if error else None),     # classified on this stored value
            prompt_tokens=cum["prompt"], completion_tokens=cum["completion"],
            cache_read_tokens=cum["cache_read"], cache_write_tokens=cum["cache_write"],
            accumulated_cost_logged=metrics.get("accumulated_cost"),
            sum_call_cost_logged=round(cum["cost"], 10) if costs else None,
            elapsed_s=(costs[-1]["timestamp"] - t0) if len(costs) > 1 else None,
            first_call_ts=t0, last_call_ts=(costs[-1].get("timestamp") if costs else None),
            report_class=report_class(iid, report), verdict=None,
            eval_files="", eval_apply_failed=False, eval_log_tail="", test_output_tail="",
            n_completion_logs=0, completion_logs_missing_cost=0, completion_cost_logged=None, prior_try_logs=0,
            prior_try_cost_logged=None, final_try_matches_metrics=None,
            final_try_logs_reporting_reasoning=0, final_try_reasoning_tokens=None,
            n_history_events=len(history), n_agent_actions=len(sigs),
            _run_dir=run_dir, _sigs=sigs,
        ))

    cfgmeta = dict(
        model=llm.get("model"), temperature=llm.get("temperature"), seed=llm.get("seed"),
        max_iterations=max_iter, condenser=cond, git_commit=meta.get("git_commit"),
        start_time=meta.get("start_time"), agent_class=meta.get("agent_class"),
        caching_prompt=llm.get("caching_prompt"), num_retries=llm.get("num_retries"),
        # endpoint and the settings that decide what was billed and how it was sampled; a
        # configured value is not necessarily an applied one (a provider may reject it and the
        # client drop it), which the audit records per configuration from provider documentation
        base_url=llm.get("base_url"), custom_llm_provider=llm.get("custom_llm_provider"),
        api_version=llm.get("api_version"), reasoning_effort=llm.get("reasoning_effort"),
        top_p=llm.get("top_p"), max_output_tokens=llm.get("max_output_tokens"),
        drop_params=llm.get("drop_params"), native_tool_calling=llm.get("native_tool_calling"),
        nonstandard_llm_fields=sorted(k for k in llm if k in ("for_routing", "correct_num")),
    )
    return config, run, execs, prefix, census, cfgmeta


# ----------------------------------------------------------------------------- driver

def extract(path: str, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    holder: dict = {}
    pending: dict[str, dict[str, bytes]] = collections.defaultdict(dict)
    per_config: dict[str, dict] = {}

    def flush(run_dir: str):
        config, run, execs, prefix, census, cfgmeta = reduce_run(run_dir, pending.pop(run_dir))
        acc = per_config.setdefault(config, dict(execs=[], prefix=[], runs={}, meta=cfgmeta))
        acc["execs"].extend(execs)
        acc["prefix"].extend(prefix)
        calls = census["calls"]
        ts = [t for e in execs for t in (e["first_call_ts"], e["last_call_ts"]) if t is not None]
        acc["runs"][run] = dict(
            first_call_utc=_utc(min(ts)) if ts else None, last_call_utc=_utc(max(ts)) if ts else None,
            n=census["n"], terminal=None,
            errors=dict(census["errors"].most_common(20)),
            budget_caps=sorted(census["budget_caps"]),
            calls=dict(min=min(calls), median=sorted(calls)[len(calls) // 2], max=max(calls)) if calls else None,
            report_lists=census["report_lists"],
            agent_action_types=dict(census["actions"].most_common()),
            metadata=census["metadata"],
        )

    for run_dir, fn, data in _iter_archive(path, holder):
        pending[run_dir][fn] = data
        if all(w in pending[run_dir] for w in WANTED):
            flush(run_dir)
    for run_dir in list(pending):
        missing = [w for w in WANTED if w not in pending[run_dir]]
        print(f"WARNING: {run_dir} missing {missing}; run skipped", file=sys.stderr)
        pending.pop(run_dir)
    sha = holder.get("sha256")          # known only once the whole archive has streamed past
    if holder.get("nested_ignored"):
        print(f"note: ignored {holder['nested_ignored']} files named {'/'.join(WANTED)} outside run "
              f"directories (per-instance evaluation logs)", file=sys.stderr)
    if not per_config:
        seen = ", ".join(f"{d} ({n})" for d, n in holder.get("top_dirs", collections.Counter()).most_common(12))
        print("WARNING: no run directories matching '<config>-run_<N>' were found; second-level "
              f"folders seen: {seen or 'none'}", file=sys.stderr)

    summary = {}
    for config, acc in per_config.items():
        for e in acc["execs"]:
            e["archive_sha256"] = sha
            rd = e.pop("_run_dir")
            e.update(_split_logs(holder["completions"].get((rd, e["instance_id"]), []),
                                 e["n_calls"], e["sum_call_cost_logged"]))
            ev = holder["eval"].get((rd, e["instance_id"]), {})
            e["eval_files"] = ",".join(sorted(ev.get("files", ())))
            e["eval_apply_failed"] = bool(ev.get("apply_failed"))
            if e["report_class"] in ("error", "none"):        # the rows whose verdict needs a reader
                e["eval_log_tail"] = ev.get("run_instance.log", "")
                e["test_output_tail"] = ev.get("test_output.txt", "")
        _classify_all(acc["execs"])
        for e in acc["execs"]:                          # error strings and log tails are free text
            for k in ("error", "eval_log_tail", "test_output_tail"):
                e[k] = _redact(e[k])
        sigs = {(e["run"], e["instance_id"]): e.pop("_sigs") for e in acc["execs"]}
        _write_csv(os.path.join(out_dir, f"actions_{config}.csv"),
                   [dict(run=r, instance_id=i, n_actions=len(v), signatures=" ".join(v))
                    for (r, i), v in sorted(sigs.items(), key=lambda kv: (kv[0][1], kv[0][0]))])
        _write_csv(os.path.join(out_dir, f"executions_{config}.csv"), acc["execs"])
        _write_csv(os.path.join(out_dir, f"prefix_{config}.csv"), acc["prefix"])
        runs = {str(k): v for k, v in sorted(acc["runs"].items())}
        audit = dict(
            config=config, archive_sha256=sha, source=path, **acc["meta"],
            n_runs=len(runs), n_executions=len(acc["execs"]),
            n_tasks=len({e["instance_id"] for e in acc["execs"]}),
            **_census(acc["execs"], runs),
            replicate_divergence=_divergence_census(sigs),
            actions_vs_calls=dict(
                total_agent_actions=sum(e["n_agent_actions"] for e in acc["execs"]),
                total_calls=sum(e["n_calls"] for e in acc["execs"]),
                executions_more_actions_than_calls=sum(e["n_agent_actions"] > e["n_calls"] for e in acc["execs"]),
                executions_with_calls_but_no_history=sum(e["n_calls"] > 0 and e["n_history_events"] == 0 for e in acc["execs"]),
            ),
            completion_logs=dict(
                executions_with_logs=sum(e["n_completion_logs"] > 0 for e in acc["execs"]),
                total_logs=sum(e["n_completion_logs"] for e in acc["execs"]),
                total_metric_calls=sum(e["n_calls"] for e in acc["execs"]),
                executions_fewer_logs_than_calls=sum(e["n_completion_logs"] < e["n_calls"] for e in acc["execs"]),
                executions_more_logs_than_calls=sum(e["n_completion_logs"] > e["n_calls"] for e in acc["execs"]),
                final_try_logs_reporting_reasoning=sum(e["final_try_logs_reporting_reasoning"] for e in acc["execs"]),
                final_try_reasoning_tokens=sum(e["final_try_reasoning_tokens"] or 0 for e in acc["execs"]),
                final_try_completion_tokens=sum(e["completion_tokens"] for e in acc["execs"]),
                executions_rerun_by_harness=sum(e["prior_try_logs"] > 0 for e in acc["execs"]),
                prior_try_logs=sum(e["prior_try_logs"] for e in acc["execs"]),
                prior_try_spend_logged=round(sum(e["prior_try_cost_logged"] or 0.0 for e in acc["execs"]), 4),
                final_try_mismatches=[dict(run=e["run"], instance_id=e["instance_id"], n_calls=e["n_calls"],
                                           n_logs=e["n_completion_logs"])
                                      for e in acc["execs"] if e["final_try_matches_metrics"] is False],
                final_try_cost_unreadable=sum(e["final_try_matches_metrics"] is None and e["n_completion_logs"] > 0
                                              for e in acc["execs"]),
                logs_missing_cost=sum(e["completion_logs_missing_cost"] for e in acc["execs"]),
            ),
            runs=runs,
        )
        audit = _redact(audit)
        with open(os.path.join(out_dir, f"audit_{config}.json"), "w") as fh:
            json.dump(audit, fh, indent=2, default=str)
        summary[config] = audit
        _print_summary(audit)
    return summary


def _divergence_census(sigs: dict) -> dict:
    """Audit item 8: per task, the first action at which its runs differ, over all runs of the
    task whatever their outcome, since the question is whether the runs are independent draws."""
    by_task = collections.defaultdict(list)
    for (run, iid), v in sigs.items():
        by_task[iid].append(v)
    firsts, identical_all, identical_pair = [], 0, 0
    for seqs in by_task.values():
        d = divergence(seqs)
        if d is None:
            identical_all += bool(seqs and seqs[0])          # runs with no actions are not "identical"
        else:
            firsts.append(d)
        if any(seqs[i] == seqs[j] and seqs[i] for i in range(len(seqs)) for j in range(i + 1, len(seqs))):
            identical_pair += 1
    firsts.sort()
    q = (lambda f: firsts[min(len(firsts) - 1, int(f * len(firsts)))]) if firsts else (lambda f: None)
    return dict(n_tasks=len(by_task), tasks_all_runs_identical=identical_all,
                tasks_with_an_identical_pair=identical_pair,
                first_divergence_quartiles=[q(0.25), q(0.5), q(0.75)],
                tasks_diverging_at_first_action=sum(f == 0 for f in firsts))


def _classify_all(execs: list[dict]) -> None:
    """Apply the current rules to every row, in place, from the row's stored inputs alone."""
    for e in execs:
        e["verdict"] = verdict(e["report_class"], e["eval_apply_failed"] in (True, "True"))
        state, resolved, hit_limit, usable = reclassify(e)
        e.update(terminal_state=state, resolved=resolved, hit_limit=hit_limit, usable=usable)


def _census(execs: list[dict], runs: dict) -> dict:
    """The audit fields that depend on classification. Fills each run's terminal-state counts."""
    by_run = collections.defaultdict(collections.Counter)
    notable = []
    for e in execs:
        by_run[str(e["run"])][e["terminal_state"]] += 1
        if e["terminal_state"] not in NOT_NOTABLE:
            n = dict(run=int(e["run"]), instance_id=e["instance_id"], state=e["terminal_state"],
                     verdict=e["verdict"], resolved=e["resolved"], usable=e["usable"], n_calls=int(e["n_calls"]),
                     error=(e["error"][:80] if e["error"] else None))
            if e["report_class"] in ("error", "none"):
                n.update(eval_files=e["eval_files"], eval_log_tail=(e["eval_log_tail"] or "")[-600:],
                         test_output_tail=(e["test_output_tail"] or "")[-300:])
            notable.append(n)
    for run, counts in by_run.items():
        runs[run]["terminal"] = dict(counts)
    tasks = {e["instance_id"] for e in execs}
    usable_by_task = collections.Counter(e["instance_id"] for e in execs if e["usable"])
    draws = collections.Counter(usable_by_task.get(t, 0) for t in tasks)
    return dict(
        n_usable=sum(bool(e["usable"]) for e in execs),
        n_resolved_usable=sum(bool(e["resolved"]) for e in execs if e["usable"]),
        resolved_by_terminal_state=dict(collections.Counter(
            e["terminal_state"] for e in execs if e["usable"] and e["resolved"])),
        usable_draws_per_task={str(k): v for k, v in sorted(draws.items(), reverse=True)},
        terminal_states=dict(sum(by_run.values(), collections.Counter())),
        notable_executions=sorted(notable, key=lambda r: (r["state"], r["instance_id"], r["run"])),
    )


def _print_summary(audit: dict) -> None:
    print(f"{audit['config']}: {audit['n_executions']} executions, {audit['n_usable']} usable, "
          f"{audit['n_resolved_usable']} resolved among usable {audit['resolved_by_terminal_state']}; "
          f"usable draws per task {audit['usable_draws_per_task']}; terminal {audit['terminal_states']}")
    if "replicate_divergence" in audit:
        print(f"  replicate divergence {audit['replicate_divergence']}; actions vs calls {audit['actions_vs_calls']}")


def reclassify_dir(out_dir: str) -> dict:
    """Re-apply the current rules to every configuration already extracted under ``out_dir``,
    including per-archive subfolders, rewriting the execution tables and the classification
    fields of each audit file. No archive is read: every input to the classifier is stored in
    the execution table."""
    summary = {}
    for path in sorted(glob.glob(os.path.join(out_dir, "**", "executions_*.csv"), recursive=True)):
        config = os.path.basename(path)[len("executions_"):-len(".csv")]
        with open(path, newline="") as fh:
            execs = list(csv.DictReader(fh))
        _classify_all(execs)
        _write_csv(path, execs)
        apath = os.path.join(os.path.dirname(path), f"audit_{config}.json")
        with open(apath) as fh:
            audit = json.load(fh)
        audit.update(_census(execs, audit["runs"]))
        with open(apath, "w") as fh:
            json.dump(audit, fh, indent=2, default=str)
        summary[config] = audit
        _print_summary(audit)
    return summary


def _write_csv(path: str, rows: list[dict]):
    if not rows:
        return
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", nargs="?", help="archive .tar.gz, an extracted directory, or - for a tar.gz stream on stdin")
    ap.add_argument("--out", default="data/derived", help="output directory")
    ap.add_argument("--reclassify", action="store_true",
                    help="re-apply the current rules to the tables already in --out; reads no archive")
    a = ap.parse_args(argv)
    if a.reclassify:
        reclassify_dir(a.out)
    elif a.path:
        extract(a.path, a.out)
    else:
        ap.error("give an archive path, or --reclassify")


if __name__ == "__main__":
    main()
