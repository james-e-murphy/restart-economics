import csv, json
from restart.extract import extract, classify, reclassify, EXCLUDED_STATES
from restart.pricing import validate, price_call

def _read(p):
    with open(p) as fh:
        return list(csv.DictReader(fh))

def test_streams_archive_and_writes_tables(synthetic_archive, config_name, tmp_path):
    out = tmp_path / "derived"
    summary = extract(str(synthetic_archive), str(out))
    assert config_name in summary
    ex = _read(out / f"executions_{config_name}.csv")
    px = _read(out / f"prefix_{config_name}.csv")
    assert len(ex) == 8                                   # 2 runs x 4 instances
    assert {r["run"] for r in ex} == {"1", "2"}
    assert summary[config_name]["archive_sha256"]         # checksum recorded
    # prefix rows: one per call, none for the zero-call execution
    calls_by_exec = {(r["run"], r["instance_id"]): int(r["n_calls"]) for r in ex}
    assert sum(calls_by_exec.values()) == len(px)
    assert calls_by_exec[("2", "d__4")] == 0

def test_terminal_state_precedence(synthetic_archive, config_name, tmp_path):
    out = tmp_path / "derived"; extract(str(synthetic_archive), str(out))
    ex = {(r["run"], r["instance_id"]): r for r in _read(out / f"executions_{config_name}.csv")}
    assert ex[("1", "a__1")]["terminal_state"] == "resolved"        and ex[("1", "a__1")]["resolved"] == "True"
    assert ex[("2", "b__2")]["terminal_state"] == "resolved"
    # a patch that did not apply is the agent's invalid output: retained, unresolved
    assert ex[("1", "b__2")]["terminal_state"] == "apply_failed"     and ex[("1", "b__2")]["usable"] == "True"
    assert ex[("1", "b__2")]["resolved"] == "False"
    # a refusal is the provider's response to the attempt: retained, scored by the report
    assert ex[("1", "c__3")]["terminal_state"] == "provider_refusal" and ex[("1", "c__3")]["usable"] == "True"
    assert ex[("1", "d__4")]["terminal_state"] == "iteration_limit"  and ex[("1", "d__4")]["usable"] == "True"
    assert ex[("1", "d__4")]["hit_limit"] == "True"
    # the harness evaluates the diff at its own limit, so a limit-hit attempt keeps the report's verdict
    assert ex[("1", "d__4")]["resolved"] == "True"
    # an evaluation that returned no verdict leaves the outcome unobserved: excluded
    assert ex[("2", "c__3")]["terminal_state"] == "eval_error"       and ex[("2", "c__3")]["usable"] == "False"
    assert ex[("2", "c__3")]["verdict"] == "no_verdict" and "timed out" in ex[("2", "c__3")]["eval_log_tail"]
    assert ex[("2", "d__4")]["terminal_state"] == "infrastructure"   and ex[("2", "d__4")]["usable"] == "False"
    # a refusal is excluded even if the report happened to list the instance as resolved
    # a refusal is a stop scored by the report, like the harness's own; the refusal pattern wins
    # over the infrastructure pattern its string also matches
    assert classify("STATUS$ERROR_LLM_CONTENT_POLICY_VIOLATION", "resolved", 3, 100) == \
        ("provider_refusal", True, False, True)
    # the prespecified sensitivity excludes refusals
    assert classify("STATUS$ERROR_LLM_CONTENT_POLICY_VIOLATION", "resolved", 3, 100, retain_refusals=False)[3] is False
    # an outage is excluded under either rule
    assert classify("STATUS$ERROR_LLM_SERVICE_UNAVAILABLE", "resolved", 3, 100)[0] in EXCLUDED_STATES
    assert classify("STATUS$ERROR_LLM_SERVICE_UNAVAILABLE", "resolved", 3, 100)[3] is False
    # a router relaying an upstream failure is infrastructure; a runtime error caused by the
    # model's own malformed tool call is not, and is scored by the report
    assert classify("BadRequestError: litellm.BadRequestError: OpenrouterException - Provider returned error",
                    "resolved", 3, 500)[:1] == ("infrastructure",)
    assert classify("RequestHTTPError: Server error '500 Internal Server Error' for url 'http://localhost:1/execute_action' "
                    "Details: [Errno 36] File name too long: '/workspace/x.py</parameter", "resolved", 3, 500) == \
        ("other_error", True, False, True)
    # every stored row reclassifies to itself, so a rule can be re-applied without the archive
    for r in ex.values():
        s, res, hit, use = reclassify(r)
        assert (s, str(res), str(hit), str(use)) == (r["terminal_state"], r["resolved"], r["hit_limit"], r["usable"])

def test_usable_draws_census(synthetic_archive, config_name, tmp_path):
    out = tmp_path / "derived"; extract(str(synthetic_archive), str(out))
    audit = json.load(open(out / f"audit_{config_name}.json"))
    # a__1, b__2: usable in both runs; c__3: refused in run 1 (retained), no verdict in run 2;
    # d__4: crashed in run 2
    assert audit["usable_draws_per_task"] == {"2": 2, "1": 2}
    assert audit["n_executions"] == 8 and audit["n_usable"] == 6
    assert audit["temperature"] == 0.0 and audit["condenser"] == "noop" and audit["max_iterations"] == 100
    assert audit["nonstandard_llm_fields"] == ["correct_num", "for_routing"]
    assert audit["runs"]["1"]["budget_caps"] == ["None"]

def test_cost_reconstructs_exactly(synthetic_archive, config_name, tmp_path):
    out = tmp_path / "derived"; extract(str(synthetic_archive), str(out))
    px = _read(out / f"prefix_{config_name}.csv")
    v = validate(px, "gpt-5-2025-08-07")
    assert v["mismatches"] == 0 and v["calls_checked"] > 0
    # the two real calls observed in the audit, to the cent
    assert abs(price_call("gpt-5-2025-08-07", 74466, 2069, 73216) - 0.0314045) < 1e-9
    assert abs(price_call("gpt-5-2025-08-07", 7009, 215, 5632) - 0.00457525) < 1e-9

def test_cumulative_columns_are_consistent(synthetic_archive, config_name, tmp_path):
    out = tmp_path / "derived"; extract(str(synthetic_archive), str(out))
    px = _read(out / f"prefix_{config_name}.csv"); ex = _read(out / f"executions_{config_name}.csv")
    last = {}
    for r in px: last[(r["run"], r["instance_id"])] = r
    for e in ex:
        k = (e["run"], e["instance_id"])
        if k in last:
            assert int(last[k]["cum_prompt"]) == int(e["prompt_tokens"])
            assert abs(float(last[k]["cum_cost_logged"]) - float(e["sum_call_cost_logged"])) < 1e-9
            assert int(last[k]["call"]) == int(e["n_calls"])

def test_streamed_hash_matches_file_hash(synthetic_archive, config_name, tmp_path, monkeypatch):
    """A streamed archive (stdin) must record the same SHA-256 as the stored file, so the
    eight archives that are streamed and never stored still carry file-level provenance."""
    import hashlib, io, sys
    file_sha = hashlib.sha256(synthetic_archive.read_bytes()).hexdigest()
    s1 = extract(str(synthetic_archive), str(tmp_path / "from_file"))
    assert s1[config_name]["archive_sha256"] == file_sha
    class _Stdin:                                          # minimal stand-in for sys.stdin
        buffer = io.BytesIO(synthetic_archive.read_bytes())
    monkeypatch.setattr(sys, "stdin", _Stdin)
    s2 = extract("-", str(tmp_path / "from_stdin"))
    assert s2[config_name]["archive_sha256"] == file_sha
    ex = _read(tmp_path / "from_stdin" / f"executions_{config_name}.csv")
    assert {r["archive_sha256"] for r in ex} == {file_sha}   # stamped on every row

def test_nested_reports_ignored_and_outcomes_censused(synthetic_archive, config_name, tmp_path, capsys):
    """Per-instance evaluation reports share the run report's file name; they must not be read as
    runs. The audit separates how attempts stopped from whether they resolved."""
    audit = extract(str(synthetic_archive), str(tmp_path / "d"))[config_name]
    err = capsys.readouterr().err
    assert "WARNING" not in err and "ignored 2 files" in err
    assert audit["n_runs"] == 2
    assert audit["resolved_by_terminal_state"] == {"resolved": 3, "iteration_limit": 1}
    assert audit["n_resolved_usable"] == 4
    notable = {(r["run"], r["instance_id"]): r for r in audit["notable_executions"]}
    assert set(notable) == {(1, "d__4"), (1, "b__2"), (2, "c__3")}
    assert notable[(1, "d__4")]["state"] == "iteration_limit" and notable[(1, "d__4")]["resolved"] is True
    assert notable[(2, "c__3")]["eval_files"] == "eval.sh,run_instance.log,test_output.txt"
    assert notable[(1, "b__2")]["verdict"] == "apply_failed"
    assert audit["runs"]["2"]["report_lists"]["error_ids"] == 1
    assert audit["runs"]["2"]["terminal"]["eval_error"] == 1

def test_completion_logs_are_a_second_record(synthetic_archive, config_name, tmp_path):
    """Completion logs are split by timestamp into the final try, which must cost exactly what the
    run's metrics record, and earlier tries the harness discarded after a crash."""
    audit = extract(str(synthetic_archive), str(tmp_path / "d"))[config_name]
    ex = {(r["run"], r["instance_id"]): r for r in _read(tmp_path / "d" / f"executions_{config_name}.csv")}
    a = ex[("1", "a__1")]
    # three logs from a crashed first try, one of them without a cost field
    assert a["n_completion_logs"] == "5" and a["prior_try_logs"] == "3" and a["completion_logs_missing_cost"] == "1"
    assert a["prior_try_cost_logged"] == "" and a["completion_cost_logged"] == ""
    assert a["final_try_matches_metrics"] == "True"          # judged on the final try's own logs
    assert ex[("1", "b__2")]["final_try_matches_metrics"] == "False"      # a call with no log
    assert ex[("2", "a__1")]["n_completion_logs"] == "0" and ex[("2", "a__1")]["final_try_matches_metrics"] == ""
    cl = audit["completion_logs"]
    assert cl["executions_with_logs"] == 2 and cl["total_logs"] == 6
    assert cl["executions_rerun_by_harness"] == 1 and cl["prior_try_logs"] == 3 and cl["logs_missing_cost"] == 1
    assert [(m["run"], m["instance_id"]) for m in cl["final_try_mismatches"]] == [(1, "b__2")]


def test_reclassify_from_stored_tables(synthetic_archive, config_name, tmp_path, monkeypatch):
    """Re-applying the rules to the stored tables, without the archive, reproduces a fresh
    extraction exactly; and a changed rule takes effect through the same path."""
    import restart.extract as X
    out = tmp_path / "d"
    fresh = extract(str(synthetic_archive), str(out))[config_name]
    before = (out / f"executions_{config_name}.csv").read_text()
    rows = _read(out / f"executions_{config_name}.csv")                # scramble the classification
    for r in rows:
        r.update(terminal_state="x", usable="False", resolved="False", hit_limit="False", verdict="x")
    X._write_csv(str(out / f"executions_{config_name}.csv"), rows)
    again = X.reclassify_dir(str(out))[config_name]
    assert (out / f"executions_{config_name}.csv").read_text() == before
    for k in ("n_usable", "n_resolved_usable", "resolved_by_terminal_state", "usable_draws_per_task",
              "terminal_states", "notable_executions", "runs", "completion_logs", "archive_sha256"):
        assert json.loads(json.dumps(again[k], default=str)) == json.loads(json.dumps(fresh[k], default=str)), k
    # the sensitivity rule, applied the same way
    orig = X.reclassify
    monkeypatch.setattr(X, "reclassify", lambda row: orig(row, retain_refusals=False))
    sens = X.reclassify_dir(str(out))[config_name]
    assert sens["n_usable"] == 5 and sens["usable_draws_per_task"] == {"2": 2, "1": 1, "0": 1}

def test_directory_input_matches_archive(synthetic_archive, config_name, tmp_path):
    """An extracted directory yields the same tables as the archive it came from."""
    import tarfile
    with tarfile.open(synthetic_archive) as tf:
        tf.extractall(tmp_path / "x")
    extract(str(synthetic_archive), str(tmp_path / "f"))
    extract(str(tmp_path / "x" / "synthetic_4runs"), str(tmp_path / "d"))
    key = lambda r: (r["run"], r["instance_id"])
    a = sorted(_read(tmp_path / "f" / f"executions_{config_name}.csv"), key=key)
    b = sorted(_read(tmp_path / "d" / f"executions_{config_name}.csv"), key=key)
    assert [(key(x), k) for x, y in zip(a, b) for k in x if k != "archive_sha256" and x[k] != y[k]] == []

def test_action_sequences_and_replicate_divergence(synthetic_archive, config_name, tmp_path):
    """Audit item 8. Actions are compared by type and defining arguments, not by the model's
    wording; the census finds where each task's runs first part ways and which runs repeat."""
    from restart.extract import agent_actions, divergence
    audit = extract(str(synthetic_archive), str(tmp_path / "d"))[config_name]
    acts = {(r["run"], r["instance_id"]): r["signatures"].split() for r in _read(tmp_path / "d" / f"actions_{config_name}.csv")}
    assert len(acts[("1", "a__1")]) == 4 and acts[("1", "a__1")][:2] == acts[("2", "a__1")][:2]
    assert acts[("1", "a__1")][2] != acts[("2", "a__1")][2]
    assert acts[("1", "b__2")] == acts[("2", "b__2")]                 # the thought differs, the actions do not
    assert acts[("1", "d__4")] and len(acts[("1", "d__4")]) == 1     # state changes are not agent steps
    assert divergence([acts[("1", "a__1")], acts[("2", "a__1")]]) == 2
    assert divergence([[], ["x"]]) == 0 and divergence([["x"], ["x"]]) is None
    rd = audit["replicate_divergence"]
    assert rd["n_tasks"] == 4 and rd["tasks_all_runs_identical"] == 1 and rd["tasks_with_an_identical_pair"] == 1
    assert rd["tasks_diverging_at_first_action"] == 2                  # c__3 and d__4: one run has no actions
    assert audit["runs"]["1"]["agent_action_types"]["run"] == 4
    assert agent_actions([{"source": "environment", "observation": "run"}]) == []

def test_configuration_kept_without_credentials(synthetic_archive, config_name, tmp_path):
    """Each run's metadata is kept for audit items 2, 7 and 9 with credentials removed, and the
    provider's reported reasoning tokens are read from the final try's completion logs."""
    audit = extract(str(synthetic_archive), str(tmp_path / "d"))[config_name]
    llm = audit["runs"]["1"]["metadata"]["llm_config"]
    assert llm["api_key"] == "<redacted>" and llm["aws_secret_access_key"] is None
    assert "sk-not-a-real-key" not in json.dumps(audit)
    from restart.extract import _redact
    assert _redact("Error: Incorrect API key provided: sk-proj-abcdef1234567890 xyz") == \
        "Error: Incorrect API key provided: <redacted> xyz"
    assert _redact({"max_output_tokens": 5, "prompt_tokens": 7}) == {"max_output_tokens": 5, "prompt_tokens": 7}
    assert audit["reasoning_effort"] == "high" and audit["temperature"] == 0.0
    ex = {(r["run"], r["instance_id"]): r for r in _read(tmp_path / "d" / f"executions_{config_name}.csv")}
    a = ex[("1", "a__1")]
    assert a["final_try_logs_reporting_reasoning"] == "2" and a["final_try_reasoning_tokens"] == "20"
    assert ex[("2", "a__1")]["final_try_reasoning_tokens"] == ""

def test_implied_prices_recover_a_known_schedule():
    """Costs generated from a known tiered schedule, with the prompt count including cached and
    cache-written tokens, are fitted back exactly under that reading and not under the other."""
    import random
    from restart.pricing import implied_prices
    rnd, rows = random.Random(1), []
    for _ in range(400):
        p = rnd.randint(5_000, 400_000); cr = rnd.randint(0, p // 2); cw = rnd.randint(0, (p - cr) // 4)
        c = rnd.randint(50, 5_000)
        inp, out_ = (3e-6, 15e-6) if p <= 200_000 else (6e-6, 22.5e-6)
        cost = (p - cr - cw) * inp + cr * inp / 10 + cw * inp * 1.25 + c * out_
        rows.append(dict(prompt_tokens=p, cache_read_tokens=cr, cache_write_tokens=cw, completion_tokens=c, cost_logged=cost))
    got = implied_prices(rows)
    lo = got["prompt_includes_cache"]["under_200k"]
    assert lo["exact_share"] == 1.0 and lo["usd_per_million"] == dict(input=3.0, cache_read=0.3, cache_write=3.75, output=15.0)
    hi = got["prompt_includes_cache"]["over_200k"]
    assert hi["usd_per_million"]["input"] == 6.0 and hi["usd_per_million"]["output"] == 22.5
    assert got["prompt_excludes_cache"]["under_200k"]["exact_share"] < 1.0
    assert implied_prices([dict(prompt_tokens=5, completion_tokens=1, cost_logged=0.0)])["calls_with_zero_cost"] == 1
