"""Build ``configurations.csv``, the one-row-per-configuration record the audit protocol asks for.

Numeric fields come from each archive's extraction (``data/derived/<archive>/audit_*.json`` and
its tables); facts that no table holds, such as what an endpoint was, which temperature was
actually applied, and whether and why a configuration is excluded, come from the hand-kept
``configurations_notes.json``. An archive that could not be extracted still gets a row, from its
notes and its verified checksum.

    python -m restart.audit                       # writes configurations.csv and prints a summary
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import statistics
import sys

FIELDS = [
    "config_id", "archive", "sha256", "model_string", "endpoint", "agent_class", "harness_version",
    "git_commit", "run_date_start", "run_date_end", "max_iterations", "budget_cap_usd",
    "loop_detector_fired", "temperature_configured", "temperature_applied", "reasoning_effort",
    "n_tasks", "n_executions", "n_usable", "n_resolved", "n_finished_unresolved", "n_empty",
    "n_apply_failed", "n_eval_error", "n_iteration_limit", "n_loop_detector", "n_budget_cap",
    "n_provider_refusal", "n_infrastructure", "n_other_error", "usable_draws_per_task",
    "median_divergence_action", "tasks_diverging_at_first_action", "n_tasks_identical_pair",
    "calls_per_action", "calls_total", "logged_spend_usd", "harness_reruns", "discarded_try_spend_usd",
    "rerun_first_prompt_ratio",
    "final_try_log_mismatches", "reasoning_tokens_reported", "reasoning_share_of_output",
    "resolved_needing_over_100_calls", "prefix_fields_missing", "schedule_date", "mini_sufficient",
    "excluded", "exclusion_condition", "note",
]
PREFIX_REQUIRED = ("prompt_tokens", "completion_tokens", "cache_read_tokens", "cost_logged", "elapsed_s")


def _sums(path: str) -> dict:
    out = {}
    if os.path.exists(path):
        for line in open(path):
            if line.strip() and not line.startswith("#") and len(line.split()) == 2:
                sha, name = line.split()
                out[name] = sha
    return out


def _prefix_scan(prefix_csv: str, rerun: set) -> tuple[str, float | str]:
    """Required per-call fields empty on more than one percent of calls; and the median first
    prompt of executions the harness re-ran over that of all others, which is near one when a
    re-run starts fresh and well above one when it carries the crashed try's context forward."""
    n, empty = 0, dict.fromkeys(PREFIX_REQUIRED, 0)
    first = {True: [], False: []}
    with open(prefix_csv, newline="") as fh:
        for r in csv.DictReader(fh):
            n += 1
            for k in PREFIX_REQUIRED:
                if r.get(k) in (None, ""):
                    empty[k] += 1
            if r["call"] == "1" and r.get("prompt_tokens") not in (None, ""):
                first[(r["run"], r["instance_id"]) in rerun].append(int(r["prompt_tokens"]))
    bad = [f"{k} {100 * v / n:.0f}%" for k, v in empty.items() if n and v / n > 0.01]
    ratio = (round(statistics.median(first[True]) / statistics.median(first[False]), 3)
             if first[True] and first[False] and statistics.median(first[False]) else "")
    return "; ".join(bad) or "none", ratio


def _row(archive_dir: str, notes: dict, sums: dict) -> dict:
    archive = os.path.basename(archive_dir.rstrip("/")) + ".tar.gz"
    note = notes.get(archive, {})
    row = dict.fromkeys(FIELDS, "")
    row.update(archive=archive, sha256=sums.get(archive, ""),
               **{k: note.get(k, "") for k in ("endpoint", "temperature_applied", "schedule_date",
                                               "mini_sufficient", "excluded", "exclusion_condition", "note")})
    audits = glob.glob(os.path.join(archive_dir, "audit_*.json"))
    if not audits:
        row.update(config_id=note.get("config_id", ""), model_string=note.get("model_string", ""),
                   agent_class=note.get("agent_class", ""), harness_version=note.get("harness_version", ""),
                   max_iterations=note.get("max_iterations", ""))
        return row
    a = json.load(open(audits[0]))
    ex = list(csv.DictReader(open(glob.glob(os.path.join(archive_dir, "executions_*.csv"))[0], newline="")))
    t = a["terminal_states"]
    runs = a["runs"].values()
    firsts = [r["first_call_utc"] for r in runs if r.get("first_call_utc")]
    lasts = [r["last_call_utc"] for r in runs if r.get("last_call_utc")]
    starts = [str((r.get("metadata") or {}).get("start_time")) for r in runs if (r.get("metadata") or {}).get("start_time")]
    cl, av = a["completion_logs"], a.get("actions_vs_calls", {})
    rd = a.get("replicate_divergence", {})
    cap = a.get("max_iterations")
    resolved = [r for r in ex if r["resolved"] == "True" and r["usable"] == "True"]
    m = re.search(r"_v(\d+\.\d+\.\d+)", a["config"])
    row.update(
        config_id=a["config"], sha256=row["sha256"] or a.get("archive_sha256") or "",
        model_string=a.get("model"), agent_class=a.get("agent_class"),
        harness_version=m.group(1) if m else "", git_commit=(a.get("git_commit") or "")[:12],
        run_date_start=min(firsts) if firsts else (min(starts) + " (run start)" if starts else ""),
        run_date_end=max(lasts) if lasts else "",
        max_iterations=cap,
        budget_cap_usd=";".join(sorted({c for r in runs for c in r.get("budget_caps", [])})) or "None",
        loop_detector_fired=t.get("loop_detector", 0),
        temperature_configured=a.get("temperature"), reasoning_effort=a.get("reasoning_effort"),
        n_tasks=a["n_tasks"], n_executions=a["n_executions"], n_usable=a["n_usable"],
        n_resolved=a["n_resolved_usable"], n_finished_unresolved=t.get("unresolved", 0),
        n_empty=t.get("empty_patch", 0), n_apply_failed=t.get("apply_failed", 0),
        n_eval_error=t.get("eval_error", 0), n_iteration_limit=t.get("iteration_limit", 0),
        n_loop_detector=t.get("loop_detector", 0), n_budget_cap=t.get("budget_cap", 0),
        n_provider_refusal=t.get("provider_refusal", 0), n_infrastructure=t.get("infrastructure", 0),
        n_other_error=t.get("other_error", 0),
        usable_draws_per_task=json.dumps(a["usable_draws_per_task"]),
        median_divergence_action=(rd.get("first_divergence_quartiles") or [None, None])[1],
        tasks_diverging_at_first_action=rd.get("tasks_diverging_at_first_action"),
        n_tasks_identical_pair=rd.get("tasks_with_an_identical_pair"),
        calls_per_action=round(av["total_calls"] / av["total_agent_actions"], 4) if av.get("total_agent_actions") else "",
        calls_total=av.get("total_calls", sum(int(r["n_calls"]) for r in ex)),
        logged_spend_usd=round(sum(float(r["sum_call_cost_logged"] or 0) for r in ex), 2),
        harness_reruns=cl.get("executions_rerun_by_harness"),
        discarded_try_spend_usd=cl.get("prior_try_spend_logged"),
        final_try_log_mismatches=len(cl.get("final_try_mismatches", [])),
        reasoning_tokens_reported=cl.get("final_try_logs_reporting_reasoning", 0) > 0,
        reasoning_share_of_output=(round(cl["final_try_reasoning_tokens"] / cl["final_try_completion_tokens"], 3)
                                   if cl.get("final_try_completion_tokens") else ""),
        resolved_needing_over_100_calls=sum(int(r["n_calls"]) > 100 for r in resolved),
    )
    rerun = {(r["run"], r["instance_id"]) for r in ex if int(r["prior_try_logs"] or 0) > 0}
    row["prefix_fields_missing"], row["rerun_first_prompt_ratio"] = _prefix_scan(
        glob.glob(os.path.join(archive_dir, "prefix_*.csv"))[0], rerun)
    return row


def build(derived: str = "data/derived", notes_path: str = "configurations_notes.json",
          sums_path: str = "archives/SHA256SUMS", out: str = "configurations.csv") -> list[dict]:
    notes = json.load(open(notes_path)) if os.path.exists(notes_path) else {}
    sums = _sums(sums_path)
    dirs = sorted(d for d in glob.glob(os.path.join(derived, "*/")) if os.path.isdir(d))
    known = {os.path.basename(d.rstrip("/")) + ".tar.gz" for d in dirs}
    rows = [_row(d, notes, sums) for d in dirs]
    for archive in sorted(set(notes) - known):          # noted but never extracted
        rows.append(_row(os.path.join(derived, archive[: -len(".tar.gz")]), notes, sums))
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--derived", default="data/derived")
    ap.add_argument("--notes", default="configurations_notes.json")
    ap.add_argument("--sums", default="archives/SHA256SUMS")
    ap.add_argument("--out", default="configurations.csv")
    a = ap.parse_args(argv)
    rows = build(a.derived, a.notes, a.sums, a.out)
    for r in rows:
        status = f"EXCLUDED ({r['exclusion_condition']})" if str(r["excluded"]).lower() == "true" else "included"
        print(f"{r['archive']}: {status} | cap {r['max_iterations']} | usable {r['n_usable']} of {r['n_executions']}"
              f" | resolved {r['n_resolved']} | spend ${r['logged_spend_usd']} | re-runs {r['harness_reruns']}"
              f" (${r['discarded_try_spend_usd']}, first-prompt ratio {r['rerun_first_prompt_ratio']})"
              f" | final-try mismatches {r['final_try_log_mismatches']}"
              f" | fields missing: {r['prefix_fields_missing']} | sha256 {'recorded' if r['sha256'] else 'MISSING'}")
    inc = [r for r in rows if str(r["excluded"]).lower() != "true" and r["n_usable"] != ""]
    if inc:
        print(f"\n{len(inc)} configurations included, {sum(int(r['n_executions']) for r in inc)} executions, "
              f"{sum(int(r['n_usable']) for r in inc)} usable; median divergence at action "
              f"{statistics.median(int(r['median_divergence_action']) for r in inc)}")
    print(f"wrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
