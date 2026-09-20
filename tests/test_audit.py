"""configurations.csv is built from the extraction audits and the hand-kept notes, with a row
for an archive that could not be extracted."""
import csv, json
from restart.extract import extract
from restart.audit import build, FIELDS


def test_builds_one_row_per_archive(synthetic_archive, tmp_path):
    derived = tmp_path / "derived"
    extract(str(synthetic_archive), str(derived / "synthetic_4runs"))
    notes = {"synthetic_4runs.tar.gz": dict(endpoint="OpenAI API", temperature_applied="default",
                                            mini_sufficient="no", excluded=False, exclusion_condition=""),
             "other_4runs.tar.gz": dict(config_id="other_sdk", max_iterations=100, excluded=True,
                                        exclusion_condition="1: a different agent")}
    (tmp_path / "notes.json").write_text(json.dumps(notes))
    (tmp_path / "SUMS").write_text("# c\nabc  other_4runs.tar.gz\n")
    rows = build(str(derived), str(tmp_path / "notes.json"), str(tmp_path / "SUMS"), str(tmp_path / "c.csv"))
    got = {r["archive"]: r for r in csv.DictReader(open(tmp_path / "c.csv"))}
    assert list(csv.reader(open(tmp_path / "c.csv")))[0] == FIELDS
    s = got["synthetic_4runs.tar.gz"]
    assert s["n_executions"] == "8" and s["n_usable"] == "6" and s["n_resolved"] == "4"
    assert s["endpoint"] == "OpenAI API" and s["max_iterations"] == "100" and s["n_provider_refusal"] == "1"
    assert s["harness_reruns"] == "1" and s["tasks_diverging_at_first_action"] == "2"
    assert s["sha256"] and s["excluded"] == "False"
    assert float(s["rerun_first_prompt_ratio"]) > 0 and s["prefix_fields_missing"] == "none"
    o = got["other_4runs.tar.gz"]
    assert o["excluded"] == "True" and o["sha256"] == "abc" and o["n_usable"] == "" and o["config_id"] == "other_sdk"
    assert len(rows) == 2
