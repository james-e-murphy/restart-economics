"""The appendix displays and the diagnostics: quantiles are of the distribution the plan names,
the difficulty display chooses within each bucket, and the diagnostics are the shares they say."""
import dataclasses

import numpy as np
import pytest

from restart import appendix as ap
from restart import diagnostics as dg
from restart import evaluate as ev
from restart import inference as inf
from restart import ladder as ld
from restart import policies as po
from restart import schedules as sc


def _pool(n=60, seed=6, name="m", minutes=None):
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    skill = rng.normal(0, 1, n)
    cost, out, wins = [], [], []
    for i in range(n):
        rc, ro, rw = [], [], []
        for _ in range(4):
            calls = int(np.clip(rng.lognormal(3.0, 0.7), 3, 99))
            rw.append(bool(rng.random() < 1 / (1 + np.exp(-(skill[i] + 1 - calls / 15)))))
            rc.append(list(rng.gamma(2.0, 0.01, calls)))
            ro.append([30.0] * calls)
        cost.append(rc), out.append(ro), wins.append(rw)
    if minutes is None:
        minutes = np.random.default_rng(seed + 1).choice([3.9, 30.0, 120.0, 480.0], n,
                                                         p=[0.4, 0.45, 0.1, 0.05])
    return ev.build(name, 100, tasks, ("1", "2", "3", "4"), cost, out, wins,
                    candidate=[[True] * 4] * n, usable=[[True] * 4] * n, minutes=minutes)


def test_the_quantile_is_the_lower_quantile_of_tasks_weighted_alike():
    cost = np.array([[1.0, 10.0], [3.0, 10.0], [np.nan, 20.0]])
    valid = np.array([[True, True], [True, True], [False, True]])
    w = ap.weights(valid, np.array([True, True]))
    assert w.sum() == pytest.approx(1.0)
    assert w[:, 0].sum() == pytest.approx(0.5) and w[2, 1] == pytest.approx(1 / 6)
    assert ap.quantile(np.nan_to_num(cost), w, 0.25) == 1.0
    assert ap.quantile(np.nan_to_num(cost), w, 0.5) == 3.0
    assert ap.quantile(np.nan_to_num(cost), w, 0.95) == 20.0


def test_a_chosen_label_reads_back_as_the_policy_it_names():
    pool = _pool()
    for p in (po.single("m"), po.retry("m", 3), po.constant("m", 25, 2), po.constant("m", None, 4)):
        assert ap._policy(pool, p.label).cutoffs == p.cutoffs
    assert ap._policy(pool, sc.label("m", [5, None, 10])).cutoffs == (5, None, 10)


def test_the_held_out_distribution_has_the_cross_fitted_value_as_its_mean():
    pool = _pool()
    rows = ap.distribution_rows(pool, rates=(10.0, 100.0),
                                regimes=(("automated", 0.0), ("human 0.5", 0.5)))
    assert len(rows) == 4
    for r in rows:
        for s in ap.STEPS:
            assert r[f"median_{s}"] <= r[f"p95_{s}"]
        assert np.isfinite(r["cap_margin_median"])


def test_the_median_version_scores_every_held_out_task_once():
    """With one candidate every fold chooses it, and the held-out tasks pooled over the folds are
    all the tasks, so the cross-fitted median is that policy's median over all of them."""
    pool = _pool(n=80)
    mask = ev.full_draw_tasks({"m": pool})
    outside = ev.outside_option(pool, 100.0)
    verify = ev.verification(outside, 0.0)
    policy = po.retry("m", 2)
    got = ap.median_choice(pool, [policy], outside, verify, 0.0, inf.folds(80), mask)
    cost, valid = ev.replay({"m": pool}, policy, outside, verify)
    assert got == pytest.approx(ap.quantile(cost, ap.weights(valid, mask), 0.5))
    retry = [po.retry("m", k) for k in (1, 2, 3, 4)]
    assert np.isfinite(ap.median_choice(pool, retry, outside, verify, 0.0, inf.folds(80), mask))


def test_the_difficulty_display_chooses_within_each_bucket():
    pool = _pool(n=120)
    rows = ap.difficulty_rows(pool, rates=(50.0,), regimes=(("automated", 0.0),), replicates=20)
    buckets = [r["bucket"] for r in rows]
    assert buckets[:3] == ["under 15 minutes", "15 minutes to 1 hour", "1 hour or more"]
    assert buckets[3:] == ["all, chosen within bucket", "all, chosen blind"]
    full = ev.full_draw_tasks({"m": pool})
    long = full & np.isin(pool.minutes, (120.0, 480.0))
    ref = ld.rung(pool, 50.0, 0.0, replicates=0, mask=long, steps=())
    got = rows[2]
    assert got["tasks"] == ref["tasks"] == long.sum()
    assert got["cap_margin"] == pytest.approx(ref["cap_margin"])
    assert got["cap_margin_low"] <= got["cap_margin_high"]
    pooled = rows[3]
    assert pooled["tasks"] == sum(r["tasks"] for r in rows[:3])


def test_the_spread_sets_configurations_against_policies_on_common_tasks():
    minutes = np.random.default_rng(1).choice([3.9, 30.0], 50)
    pools = {c: _pool(n=50, seed=s, name=c, minutes=minutes) for c, s in (("a", 1), ("b", 2))}
    rows = ap.spread_rows(pools, rates=(25.0,), regimes=(("automated", 0.0),))
    r = rows[0]
    assert r["across_best"] == pytest.approx(abs(r["best_a"] - r["best_b"]))
    assert r["within_max"] == pytest.approx(max(r["within_a"], r["within_b"]))
    assert r["cheapest"] in ("a", "b") and r["cheapest"] != r["dearest"]


def test_the_within_task_share_is_zero_when_a_task_s_draws_cost_alike_and_one_when_tasks_do():
    pool = _pool()
    first = np.repeat(pool.cost_end[:, :1], 4, axis=1)
    alike = dataclasses.replace(pool, cost_end=first)
    assert dg.summary(alike)["within_task_share"] == pytest.approx(0.0, abs=1e-12)
    across = dataclasses.replace(pool, cost_end=np.tile(pool.cost_end[:1, :], (pool.n_tasks, 1)))
    assert dg.summary(across)["within_task_share"] == pytest.approx(1.0)


def test_the_diagnostic_shares_add_up():
    pool = _pool()
    s = dg.summary(pool)
    assert s["mixed_share"] + s["all_fail_share"] + s["all_resolve_share"] == pytest.approx(1.0)
    rows = dg.tail(pool)
    assert [r["cutoff"] for r in rows] == list(pool.grid)
    beyond = [r["spend_beyond"] for r in rows]
    assert all(a >= b for a, b in zip(beyond, beyond[1:]))
    running = [r["running"] for r in rows]
    assert all(a >= b for a, b in zip(running, running[1:]))
    # by hand at the first decision point
    end, at = pool.cost_end, pool.cost_grid[:, :, 0]
    past = np.maximum(end - at, 0)
    assert rows[0]["resolving_beyond"] == pytest.approx(past[pool.resolved].sum() / past.sum())
