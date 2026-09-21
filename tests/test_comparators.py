"""The appendix comparators: the closed form is the evaluator's enumeration, each family stops
attempts where the plan says it does, and the families are scored as the ladder scores its own."""
import itertools

import numpy as np
import pytest

from restart import comparators as cp
from restart import evaluate as ev
from restart import inference as inf
from restart import ladder as ld
from restart import policies as po
from restart import schedules as sc
from restart import sensitivity as se
from restart import state as st


def _pool(n=60, seed=2, cap=500, knock=True):
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    skill = rng.normal(0, 1, n)
    cost, out, wins = [], [], []
    for i in range(n):
        rc, ro, rw = [], [], []
        for _ in range(4):
            calls = int(np.clip(rng.lognormal(3.3, 0.8), 3, cap))
            rw.append(bool(rng.random() < 1 / (1 + np.exp(-(skill[i] + 1 - calls / 30)))))
            rc.append(list(rng.gamma(2.0, 0.01, calls)))
            ro.append(list(rng.gamma(2.0, 50.0, calls)))
        cost.append(rc), out.append(ro), wins.append(rw)
    usable = np.ones((n, 4), bool)
    if knock:
        usable[:3, 3] = False
        usable[3:5, 1:] = False
    return ev.build("m", cap, tasks, ("1", "2", "3", "4"), cost, out, wins,
                    candidate=[[True] * 4] * n, usable=usable,
                    minutes=np.random.default_rng(seed + 1).choice([3.9, 30.0, 120.0], n))


def test_the_closed_form_is_the_enumeration_of_orderings():
    pool = _pool()
    tab = sc.table(pool)
    fx = se.fixed(pool, tab)
    got = cp.symmetric(tab.cost, tab.resolves, tab.checks.astype(float), pool.usable)
    assert np.array_equal(got["used"], fx.used)
    for key in ("spend", "checks", "resolves", "fails"):
        assert np.allclose(np.where(fx.used, got[key], 0), np.where(fx.used, getattr(fx, key), 0),
                           atol=1e-12), key


def test_a_dollar_cutoff_stops_an_attempt_where_its_spend_first_passes_the_cutoff():
    pool = _pool(knock=False)
    train = np.arange(pool.n_tasks) % 5 != 0
    cuts = cp.dollar_cutoffs(pool, train)
    keep = pool.usable & train[:, None]
    assert len(cuts) == 40
    assert cuts[0] == pytest.approx(np.percentile(pool.cost_grid[:, :, 0][keep], 5))
    assert cuts[-1] == pytest.approx(pool.cost_end[keep].max())
    assert np.allclose(np.diff(np.log(cuts)), np.log(cuts[1] / cuts[0]))
    c = cuts[20]
    cost, res, chk = cp.stopped(pool, cp._first(pool.alive[None]
                                                & (pool.cost_grid[None] > c)))
    for i, d in itertools.product(range(pool.n_tasks), range(4)):
        over = [j for j in range(len(pool.grid)) if pool.alive[i, d, j]
                and pool.cost_grid[i, d, j] > c]
        if over:
            assert cost[0, i, d] == pool.cost_grid[i, d, over[0]] and not res[0, i, d]
        else:
            assert cost[0, i, d] == pool.cost_end[i, d] and res[0, i, d] == pool.resolved[i, d]
    # the largest cutoff never binds on a training attempt
    top = cp.stopped(pool, cp._first(pool.alive[None] & (pool.cost_grid[None] > cuts[-1])))
    assert np.array_equal(top[1][0][keep], pool.resolved[keep])


def test_the_threshold_grid_is_the_registered_one():
    pool = _pool()
    train = np.ones(pool.n_tasks, bool)
    pairs = cp.threshold_grid(pool, train)
    assert len(pairs) == 19 * 11
    last = pool.grid[-1]
    for a in sorted({p[0] for p in pairs}):
        ends = sorted((p[0] + p[1] * last) / a for p in pairs if p[0] == a)
        assert ends[0] == pytest.approx(0.25) and ends[-1] == pytest.approx(4.0)
        assert np.allclose(np.diff(np.log(ends)), np.log(4.0 / 0.25) / 10)
    running = pool.cost_rate[pool.alive & pool.usable[:, :, None]]
    assert pairs[0][0] == pytest.approx(np.percentile(running, 5))


def test_a_refitted_family_is_the_evaluator_s_value_of_the_policies_it_names():
    pool = _pool()
    train = np.arange(pool.n_tasks) % 5 != 1
    got = cp.threshold_fit(pool, train)
    outside = ev.outside_option(pool, 80.0)
    verify = ev.verification(outside, 0.3)
    fam = cp.refitted(pool, cp.threshold_fit, outside, verify, 0.2, cp.Lru(), got["spend"].shape[0])
    values, used, labels = fam.fit(train)
    pairs = cp.threshold_grid(pool, train)
    for row in (0, 57, len(pairs) * 3 + 100):
        k, cand = divmod(row, len(pairs))
        a, b = pairs[cand]
        line = a + b * np.asarray(pool.grid, float)
        stop = cp._first(pool.alive & (pool.cost_rate > line[None, None, :]))
        slot = ev.stopped_slot(pool, stop)
        policy = po.Policy(tuple(po.Slot("m") for _ in range(k + 1)))
        ref = ev.value({"m": pool}, policy, outside, verify, 0.2, arrays=[slot] * (k + 1))
        assert np.array_equal(used[row], ref.used)
        assert np.allclose(values[row][ref.used], ref.per_task[ref.used])
        assert labels[row].startswith(f"threshold: {k + 1} attempts")


def test_the_universal_schedule_runs_one_one_two_one_in_units_on_the_grid():
    pool = _pool(cap=500)
    units = cp.luby_units(pool)
    assert 5 in units and 75 in units and 250 in units and 55 not in units
    for p in cp.universal_policies(pool):
        cuts = p.cutoffs
        u = cuts[0]
        want = [m * u if m * u < pool.cap else None for m in cp.LUBY[:len(cuts)]]
        assert list(cuts) == want
        assert all(c is None or c in pool.grid for c in cuts)
    small = _pool(cap=100)
    assert all(u < 100 for u in cp.luby_units(small))


def test_the_first_look_rule_acts_only_at_the_first_decision_point():
    pool = _pool()
    models = st.fit(pool, np.ones(pool.n_tasks, bool))
    stop = st.stop_index(pool, models, 0.0, 1e-9, allowed=cp.first_point(pool))
    assert set(np.unique(stop)) <= {-1, 0}
    free = st.stop_index(pool, models, 0.0, 1e-9)
    assert (free >= 0).sum() >= (stop >= 0).sum()


def test_a_cell_scores_the_ladder_s_steps_as_the_ladder_does():
    pool = _pool()
    mask = ev.full_draw_tasks({"m": pool})
    got = cp.cell(pool, 100.0, 0.0, 0.0, mask, inf.folds(pool.n_tasks), sc.table(pool),
                  cp.caches())
    ref = ld.rung(pool, 100.0, 0.0, replicates=0, steps=("iii-b", "iv"))
    for key in ("value_ii", "value_iii", "value_iiib", "value_iv"):
        assert got[key] == pytest.approx(ref[key]), key
    assert got["dollar_cap_margin"] == pytest.approx(got["value_ii"] - got["value_dollar"])
    assert got["rule_vs_threshold"] == pytest.approx(got["value_threshold"] - got["value_iv"])
    assert "dollar" in got["choice_dollar"] and "universal" in got["choice_universal"]


def test_the_rows_carry_intervals_where_the_ladder_s_fitted_steps_do(tmp_path):
    pool = _pool(n=40)
    rows = cp.rows_for(pool, rates=(25.0, 100.0), multiples=(2.0,),
                       regimes=(("automated", 0.0), ("human 0.5", 0.5)), replicates=3,
                       fitted_rates=(100.0,))
    assert len(rows) == 2 * 3
    fitted = [r for r in rows if r.get("fitted_replicates")]
    assert [(r["regime_name"], r["rate"]) for r in fitted] == [("automated", 100.0)]
    for m in cp.INTERVALS:
        assert fitted[0][f"{m}_low"] <= fitted[0][f"{m}_high"]
    path = cp.write(rows, str(tmp_path / "comparators.csv"))
    assert open(path).readline().strip().split(",") == list(cp.FIELDS)
