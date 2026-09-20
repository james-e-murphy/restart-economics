"""A synthetic OpenHands archive with the schema observed in the real release, small enough to
build in memory. Two runs, four instances, chosen to exercise every branch of the terminal-state
classifier and the cost reconstruction."""
import io, json, tarfile
import pytest

MODEL = "gpt-5-2025-08-07"
CONFIG = f"{MODEL}_maxiter_100_N_v0.62.0-no-hint"

def _usage(prompt, completion, cached):
    return dict(model=MODEL, prompt_tokens=prompt, completion_tokens=completion,
                cache_read_tokens=cached, cache_write_tokens=0, context_window=272000,
                per_turn_token=prompt + completion, response_id="x")

def _cost(prompt, completion, cached, ts):
    uncached = prompt - cached
    return dict(model=MODEL, cost=uncached*1.25e-6 + cached*0.125e-6 + completion*10e-6, timestamp=ts)

def _act(action, thought="", **args):
    return dict(source="agent", action=action, args=dict(thought=thought, **args), message="m")


def _obs(kind="run"):
    return dict(source="environment", observation=kind, content="output", extras={})


USER = dict(source="user", action="message", args=dict(content="Fix the issue."))


def _exec(iid, calls, error=None, difficulty="<15 min fix", n_calls=None, history=()):
    usages, costs, lats = [], [], []
    for k, (p, c, cch) in enumerate(calls):
        usages.append(_usage(p, c, cch)); costs.append(_cost(p, c, cch, 1000.0 + 10*k))
        lats.append(dict(model=MODEL, latency=1.0, response_id="x"))
    if n_calls is not None:                      # pad to simulate an iteration-limit run
        while len(usages) < n_calls:
            usages.append(_usage(100, 10, 0)); costs.append(_cost(100, 10, 0, 1000.0 + 10*len(usages)))
            lats.append(dict(model=MODEL, latency=1.0, response_id="x"))
    return dict(instance_id=iid, error=error,
                instance=dict(repo="r/x", difficulty=difficulty),
                metrics=dict(accumulated_cost=sum(c["cost"] for c in costs), max_budget_per_task=None,
                             token_usages=usages, costs=costs, response_latencies=lats, condenser=[]),
                history=list(history), test_result=dict(git_patch=""))

RUNS = {
    1: dict(
        lines=[
            _exec("a__1", [(7009, 215, 5632), (74466, 2069, 73216)],                # resolved
                  history=[USER, _act("run", "look", command="ls"), _obs(), _act("run", command="cat x.py"), _obs(),
                           _act("edit", path="x.py", new_str="A"), _obs("edit"), _act("finish", "done")]),
            _exec("b__2", [(500, 50, 0), (600, 60, 400)],                           # unresolved
                  history=[USER, _act("run", command="pytest"), _obs(), _act("finish", "gave up")]),
            _exec("c__3", [(300, 20, 0)], error="STATUS$ERROR_LLM_CONTENT_POLICY_VIOLATION"),
            _exec("d__4", [(300, 20, 0)], n_calls=100,
                  error="RuntimeError: Agent reached maximum iteration. Current iteration: 100",
                  history=[USER, _act("run", command="ls"), _obs(), _act("change_agent_state")]),
        ],
        # d__4 hit the iteration limit, but the harness evaluated its diff and it passed;
        # b__2's patch did not apply, which the report lists as an evaluation error
        report=dict(resolved_ids=["a__1", "d__4"], unresolved_ids=[], empty_patch_ids=["c__3"],
                    error_ids=["b__2"]),
        # a__1: the harness crashed on a first try of two calls and re-ran the instance; the logs
        # are written out of time order. b__2: one of its two calls has no log.
        completion_logs={"a__1": [(1000.5, _cost(7009, 215, 5632, 0)["cost"]), (900.25, 0.01),
                                  (1001.5, _cost(74466, 2069, 73216, 0)["cost"]), (901.25, 0.02), (899.5, None)],
                         "b__2": [(1000.5, _cost(500, 50, 0, 0)["cost"])]},
        eval_files={"a__1": {"report.json": "{}", "run_instance.log": "APPLY_PATCH_PASS\nok"},
                    "b__2": {"patch.diff": "x", "run_instance.log":
                             "Failed to apply patch with git apply, trying with patch command...\nAPPLY_PATCH_FAIL"}},
    ),
    2: dict(
        lines=[
            # a__1 agrees with run 1 for two actions, worded differently, then edits differently
            _exec("a__1", [(500, 50, 0)],
                  history=[USER, _act("run", "list files", command="ls"), _obs(), _act("run", "read", command="cat x.py"),
                           _obs(), _act("edit", path="x.py", new_str="B"), _obs("edit"), _act("finish", "ok")]),
            # b__2 repeats run 1 exactly
            _exec("b__2", [(500, 50, 0)],
                  history=[USER, _act("run", "again", command="pytest"), _obs(), _act("finish", "gave up again")]),
            _exec("c__3", [(300, 20, 0)], history=[USER, _act("run", command="ls")]),
            _exec("d__4", [], error="STATUS$ERROR_LLM_SERVICE_UNAVAILABLE"),         # zero calls
        ],
        # c__3 ran normally, its patch applied, and the tests timed out: no verdict
        report=dict(resolved_ids=["a__1", "b__2"], unresolved_ids=[], empty_patch_ids=["d__4"],
                    error_ids=["c__3"]),
        eval_files={"a__1": {"report.json": "{}"},
                    "c__3": {"eval.sh": "x", "test_output.txt": "collected 12 items",
                             "run_instance.log": "APPLY_PATCH_PASS\nTest process timed out"}},
    ),
}

METADATA = dict(agent_class="CodeActAgent", max_iterations=100, git_commit="974bcdfd",
                start_time="2025-12-31 04:28:19",
                llm_config=dict(model=MODEL, temperature=0.0, seed=None, caching_prompt=True,
                                num_retries=5, for_routing=False, correct_num=5, api_key="sk-not-a-real-key",
                                base_url=None, reasoning_effort="high", max_output_tokens=None,
                                aws_secret_access_key=None),
                condenser_config=dict(type="noop"))

@pytest.fixture
def synthetic_archive(tmp_path):
    path = tmp_path / "synthetic_4runs.tar.gz"
    with tarfile.open(path, "w:gz") as tf:
        for run, spec in RUNS.items():
            base = f"synthetic_4runs/{CONFIG}-run_{run}"
            files = {
                "output.jsonl": "\n".join(json.dumps(l) for l in spec["lines"]).encode(),
                "metadata.json": json.dumps(METADATA).encode(),
                "report.json": json.dumps(dict(total_instances=4, **spec["report"])).encode(),
            }
            # per-call completion logs, a second record of the calls, named by timestamp
            for iid, logs in spec.get("completion_logs", {}).items():
                for ts, c in logs:
                    files[f"llm_completions/{iid}/{MODEL}-{ts}.json"] = json.dumps(
                        dict(messages=[{"role": "user", "content": "x"}],
                             response={"usage": {"completion_tokens_details": {"reasoning_tokens": 10}}},
                             timestamp=ts, cost=c)).encode()
            # per-instance evaluation folders; their report.json is not the run report
            for iid, ef in spec["eval_files"].items():
                for fn, text in ef.items():
                    files[f"eval_outputs/{iid}/{fn}"] = text.encode()
            for name, data in files.items():
                ti = tarfile.TarInfo(f"{base}/{name}"); ti.size = len(data)
                tf.addfile(ti, io.BytesIO(data))
    return path

@pytest.fixture
def config_name():
    return CONFIG
