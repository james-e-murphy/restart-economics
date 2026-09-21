"""The ladder runner: the steps, the comparisons between them, and what it writes."""
import csv
import json
import os
from unittest import mock

import numpy as np
import pytest

from restart import audit
from restart import evaluate as ev
from restart import ladder as ld
from restart import pricing
from restart import state as st

PER_CALL = 0.1


def _world(n=120, seed=4):
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    cost, out, resolved = [], [], []
    for _ in tasks:
        row, wins = [], []
        for _ in range(4):
            calls = int(np.clip(rng.gamma(2.0, 10.0), 3, 99))
            wins.append(bool(rng.random() < 1 / (1 + np.exp((calls - 20) / 6.0))))
            row.append(([PER_CALL] * calls, [10.0] * calls))
        cost.append([c for c, _ in row])
        out.append([o for _, o in row])
        resolved.append(wins)
    return ev.build("m", 100, tasks, ("1", "2", "3", "4"), cost, out, resolved,
                    candidate=[[True] * 4 for _ in tasks], usable=[[True] * 4 for _ in tasks],
                    minutes=[60.0] * n)


def test_a_rung_scores_the_three_steps_on_the_same_tasks():
    pool = _world()
    got = ld.rung(pool, rate=100.0, fraction=0.0, replicates=40, steps=())
    assert got["tasks"] == pool.n_tasks
    # retrying pays when the outside option is a hundred dollars and an attempt costs a few
    assert got["value_ii"] < got["value_i"] and got["retry_value"] > 0
    # the cap can only help, since no cutoff is a member of the capped family
    assert got["cap_margin"] > -1.0
    assert got["cap_margin_low"] <= got["cap_margin"] <= got["cap_margin_high"]
    assert got["replicates"] == 40 and got["dropped"] == 0
    assert "attempts" in got["choice_ii"] and "cutoff" in got["choice_iii"]


def test_the_cap_is_worth_less_when_escalation_is_dear_than_when_it_is_cheap():
    pool = _world()
    cheap = ld.rung(pool, rate=5.0, fraction=0.0, replicates=30, steps=())
    dear = ld.rung(pool, rate=300.0, fraction=0.0, replicates=30, steps=())
    assert cheap["cap_margin"] >= dear["cap_margin"]
    # a cut-off attempt saves a review too, so the cap is worth more under human verification
    human = ld.rung(pool, rate=100.0, fraction=0.5, replicates=30, steps=())
    automated = ld.rung(pool, rate=100.0, fraction=0.0, replicates=30, steps=())
    assert human["cap_margin"] >= automated["cap_margin"]


def test_the_false_accept_sensitivity_raises_every_value():
    pool = _world()
    plain = ld.rung(pool, rate=100.0, fraction=0.0, replicates=20, steps=())
    with_phi = ld.rung(pool, rate=100.0, fraction=0.0, phi=0.5, replicates=20, steps=())
    assert with_phi["value_i"] > plain["value_i"]
    assert with_phi["value_ii"] > plain["value_ii"]


def test_a_rung_carries_the_searched_schedule_and_the_state_rule():
    pool = _world(n=80)
    got = ld.rung(pool, rate=100.0, fraction=0.0, replicates=10, fitted_replicates=8)
    # the schedule class contains the constant cutoffs, so on the folds that chose it the schedule
    # cannot be worse; out of sample the extra freedom may cost, which is what the margin reports
    assert isinstance(got["value_iiib"], float) and isinstance(got["value_iv"], float)
    assert got["schedule_margin"] == pytest.approx(got["value_iii"] - got["value_iiib"])
    assert got["state_margin"] == pytest.approx(got["value_iiib"] - got["value_iv"])
    assert got["schedule_margin_low"] <= got["schedule_margin_high"]
    assert got["state_margin_low"] <= got["state_margin_high"]
    assert got["fitted_replicates"] == 8
    assert "schedule" in got["choice_iiib"] and "state rule" in got["choice_iv"]


def test_the_ladder_writes_one_row_per_point_and_regime(tmp_path):
    pool = _world(n=60)
    rows = ld.ladder(pool, rates=(10.0, 100.0), multiples=(1.0, 50.0),
                     regimes=(("automated", 0.0), ("human 0.3", 0.3)),
                     replicates=10, steps=(), fitted_replicates=0)
    assert len(rows) == 8
    path = ld.write(rows, str(tmp_path / "results" / "ladder.csv"))
    with open(path, newline="") as fh:
        back = list(csv.DictReader(fh))
    assert len(back) == 8 and set(back[0]) == set(ld.FIELDS)
    assert {r["regime_name"] for r in back} == {"automated", "human 0.3"}
    assert {r["axis"] for r in back} == {"rate", "multiple"}


def test_the_second_axis_is_the_outside_option_in_units_of_an_attempt():
    pool = _world(n=60)
    mask = ev.full_draw_tasks({pool.config: pool})
    for m in (0.5, 10.0, 500.0):
        rate = ev.rate_for_multiple(pool, m, mask)
        assert ev.multiple_for_rate(pool, rate, mask) == pytest.approx(m)
    rows = ld.ladder(pool, rates=(), multiples=(20.0,), regimes=(("automated", 0.0),),
                     replicates=5, steps=(), fitted_replicates=0)
    assert rows[0]["multiple"] == pytest.approx(20.0)
    # the mean outside option at that rate is twenty times what an attempt costs at the median
    outside = ev.outside_option(pool, rows[0]["rate"])
    assert outside[mask].mean() == pytest.approx(20.0 * rows[0]["median_attempt_cost"])


def test_an_excluded_configuration_is_not_scored(tmp_path):
    notes = tmp_path / "configurations_notes.json"
    notes.write_text(json.dumps({"kept_4runs.tar.gz": {"excluded": False},
                                 "dropped_4runs.tar.gz": {"excluded": True,
                                                          "exclusion_condition": "2: selected"}}))
    assert audit.excluded(str(notes)) == {"dropped_4runs"}
    derived = tmp_path / "derived"
    for name in ("kept_4runs", "dropped_4runs"):
        (derived / name).mkdir(parents=True)
        (derived / name / "prefix_x.csv").write_text("run,instance_id\n")
    # the runner reads the audit's own record, so nothing excluded can reach a results table
    with mock.patch.dict(pricing.SCHEDULES, {"kept_4runs": {}, "dropped_4runs": {}}, clear=False):
        got = ld.configurations(str(derived), str(notes))
    assert [os.path.basename(f.rstrip("/")) for f in got] == ["kept_4runs"]


def test_the_runner_refuses_to_guess_when_the_exclusion_record_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        ld.configurations(str(tmp_path), str(tmp_path / "nothing.json"))


# ----------------------------------------------------------------------------- transfer, escalation

def _configs(n=60, names=("a", "b", "c"), seed=8, missing=None):
    """Several configurations on the same tasks, sharing each task's difficulty, so that what one
    configuration's attempts show about their chances says something about another's."""
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    skill = rng.normal(0, 1, n)
    pools = {}
    for j, name in enumerate(names):
        cost, out, resolved = [], [], []
        for i in range(n):
            row, wins = [], []
            for _ in range(4):
                calls = int(np.clip(rng.gamma(2.0, 10.0) * np.exp(-0.3 * skill[i]), 3, 99))
                wins.append(bool(rng.random() < 1 / (1 + np.exp(-(skill[i] + 1 - calls / 12)))))
                row.append(([0.05 * (1 + j)] * calls, [20.0 * (1 + j)] * calls))
            cost.append([c for c, _ in row])
            out.append([o for _, o in row])
            resolved.append(wins)
        keep = [t for t in tasks if not (missing and name in missing and t in missing[name])]
        at = [tasks.index(t) for t in keep]
        pools[name] = ev.build(name, 100, tuple(keep), ("1", "2", "3", "4"),
                               [cost[i] for i in at], [out[i] for i in at],
                               [resolved[i] for i in at],
                               candidate=[[True] * 4 for _ in at], usable=[[True] * 4 for _ in at],
                               minutes=[60.0] * len(at))
    return pools


def test_escalating_every_task_costs_the_mean_outside_option_on_the_scored_tasks():
    pool = _world(n=60)
    got = ld.rung(pool, rate=40.0, fraction=0.3, replicates=5, steps=())
    mask = ev.full_draw_tasks({pool.config: pool})
    assert got["value_escalate"] == pytest.approx(ev.outside_option(pool, 40.0)[mask].mean())


def test_the_transfer_rule_is_scored_beside_the_within_configuration_rule():
    pools = _configs()
    target, others = "a", ["b", "c"]
    source = {c: ev.reindex(pools[c], pools[target].tasks) for c in others}
    got = ld.rung(pools[target], rate=100.0, fraction=0.0, replicates=5, fitted_replicates=6,
                  transfer=(source, others), transfer_cache={}, state_cache={})
    assert isinstance(got["value_iv_transfer"], float)
    assert got["transfer_margin"] == pytest.approx(got["value_iiib"] - got["value_iv_transfer"])
    assert got["transfer_margin_low"] <= got["transfer_margin_high"]
    assert "state rule" in got["choice_iv_transfer"]


def test_the_transfer_holds_out_the_fold_s_tasks_from_the_other_configurations_too():
    """PLAN.md Section 5: for a target fold, the models are fitted on the other configurations
    with that fold's tasks excluded. Fitting on the source pools under the training mask must be
    the same as fitting on source pools from which the held-out tasks have been removed."""
    pools = _configs()
    others = ["b", "c"]
    source = {c: ev.reindex(pools[c], pools["a"].tasks) for c in others}
    train = np.arange(pools["a"].n_tasks) % 5 != 2
    masked = st.fit(source, train, others)
    kept = [t for t, k in zip(pools["a"].tasks, train) if k]
    removed = {c: ev.reindex(pools[c], kept) for c in others}
    direct = st.fit(removed, np.ones(len(kept), bool), others)
    assert np.allclose(masked.resolve, direct.resolve) and np.allclose(masked.spend, direct.spend)


def test_a_task_another_configuration_never_ran_contributes_nothing_to_the_transfer():
    pools = _configs(missing={"b": {"t0", "t1", "t2"}})
    padded = ev.reindex(pools["b"], pools["a"].tasks)
    assert padded.tasks == pools["a"].tasks
    assert not padded.usable[:3].any() and padded.usable[3:].all()
    rows_all = st._rows(padded, np.ones(padded.n_tasks, bool))[0]
    rows_ran = st._rows(pools["b"], np.ones(pools["b"].n_tasks, bool))[0]
    assert len(rows_all) == len(rows_ran)


def test_the_rule_s_models_are_fitted_once_per_training_set_across_the_sweep():
    pools = _configs(n=50)
    others = ["b", "c"]
    source = {c: ev.reindex(pools[c], pools["a"].tasks) for c in others}
    calls = []
    real = st.fit

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    reps = 4
    with mock.patch.object(st, "fit", counting):
        ld.ladder(pools["a"], rates=(25.0, 100.0), multiples=(), regimes=(("automated", 0.0),),
                  replicates=3, fitted_replicates=reps, fitted_rates=(25.0, 100.0),
                  transfer=(source, others))
    # within and transfer: five folds on the sample and five in each replicate, once each,
    # however many rates reuse them
    assert len(calls) <= 2 * 5 * (reps + 1)
