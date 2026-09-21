"""The receding-horizon restart rule: its two fits, its stopping rule, and what it learns.

The world here has attempts of random length whose chance of resolving falls as they run on. A
rule that reads the execution's state should learn to stop the long ones, and should land near the
best constant cutoff, which the enumerator finds on its own.
"""
import numpy as np
import pytest

from restart import evaluate as ev
from restart import inference as inf
from restart import policies as po
from restart import state as st

RATE, H, PER_CALL = 100.0, 100.0, 0.1


def _world(n=400, seed=7):
    """Attempts run for a random number of calls, and the shorter ones resolve more often, so a
    rule that reads how long an attempt has been running and how much it has written has something
    to learn. Spend per call rises as context grows, as it does in the real configurations."""
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    cost, out, resolved = [], [], []
    for _ in tasks:
        row, wins = [], []
        for _ in range(4):
            calls = int(np.clip(rng.gamma(2.0, 12.0), 3, 99))
            wins.append(bool(rng.random() < 1 / (1 + np.exp((calls - 25) / 8.0))))
            row.append(([PER_CALL * (1 + 0.005 * i) for i in range(calls)],
                        list(np.maximum(rng.normal(10, 2, calls), 1.0))))
        cost.append([c for c, _ in row])
        out.append([o for _, o in row])
        resolved.append(wins)
    return ev.build("m", 100, tasks, ("1", "2", "3", "4"), cost, out, resolved,
                    candidate=[[True] * 4 for _ in tasks], usable=[[True] * 4 for _ in tasks],
                    minutes=[60.0] * n)


def _rates(pool):
    h = ev.outside_option(pool, RATE)
    return h, np.zeros(pool.n_tasks)


def test_the_logistic_fit_recovers_coefficients_it_was_given():
    rng = np.random.default_rng(0)
    n = 4000
    x = np.column_stack([np.ones(n), rng.normal(size=(n, 3))])
    beta = np.array([-0.5, 1.2, -0.8, 0.3])
    with np.errstate(all="ignore"):
        y = (rng.random(n) < 1 / (1 + np.exp(-x @ beta))).astype(float)
    got, note = st._logistic(x, y, np.ones(n) / n)
    assert note == ""
    assert got == pytest.approx(beta, abs=0.12)


def test_the_spend_fit_recovers_a_log_linear_mean():
    rng = np.random.default_rng(1)
    n = 4000
    x = np.column_stack([np.ones(n), rng.normal(size=(n, 3))])
    beta = np.array([0.7, 0.4, -0.2, 0.1])
    with np.errstate(all="ignore"):
        mu = np.exp(x @ beta)
    y = rng.gamma(shape=2.0, scale=mu / 2.0)          # overdispersed, positive, continuous
    got, note = st._quasi_poisson(x, y, np.ones(n) / n)
    assert got == pytest.approx(beta, abs=0.1)


def test_a_separated_logistic_is_bounded_rather_than_left_to_run_away():
    n = 400
    x = np.column_stack([np.ones(n), np.linspace(-1, 1, n)])
    y = (x[:, 1] > 0).astype(float)                   # perfectly separated
    got, note = st._logistic(x, y, np.ones(n) / n)
    assert np.all(np.isfinite(got)) and np.max(np.abs(got)) < st.SEPARATED
    assert (x[:300] @ got)[0] < 0 < (x @ got)[-1]     # it still orders the two sides
    # without any ridge the coefficients run away, and the fit is redone with one
    unpenalized, trouble = st._logistic(x, y, np.ones(n) / n, ridge=0.0)
    assert "ridge" in trouble and np.all(np.isfinite(unpenalized))


def test_the_state_is_the_one_the_plan_names():
    pool = _world(n=20)
    x = st.design(pool)
    assert x.shape[-1] == 4 and len(st.FEATURES) == 4
    j = pool.grid.index(20)
    assert x[0, 0, j, 1] == pytest.approx(np.log(20))
    assert x[0, 0, j, 2] == pytest.approx(np.log1p(pool.out_grid[0, 0, j]))
    assert x[0, 0, j, 3] == pytest.approx(np.log1p(pool.out_recent[0, 0, j]))


def test_the_stopping_rule_turns_on_the_value_of_restarting():
    pool = _world()
    train = np.ones(pool.n_tasks, bool)
    models = st.fit(pool, train)
    q, s = st.predict(pool, models)
    assert q.shape == pool.alive.shape and (s >= 0).all()
    # nothing to gain from continuing: the rule stops every running attempt at the first point
    never = st.stop_index(pool, models, verify=0.0, continuation=0.0)
    assert (never[pool.alive[:, :, 0]] == 0).all()
    # a boundless value of restarting: the rule never stops anything
    always = st.stop_index(pool, models, verify=0.0, continuation=1e12)
    assert (always == -1).all()


def test_restart_values_are_built_backward_and_end_at_the_outside_option():
    pool = _world(n=200)
    outside, verify = _rates(pool)
    train = np.ones(pool.n_tasks, bool)
    models = st.fit(pool, train)
    values, slots = st.restart_values(pool, models, 3, outside, verify, 0.0, train)
    assert values[4] == pytest.approx(H)
    assert set(slots) == {1, 2, 3}
    # more attempts left is worth at least as much as fewer, and all beat the outside option
    assert values[1] <= values[2] <= values[3] <= values[4]


def test_the_rule_stops_the_long_attempts_and_lands_near_the_best_constant_cutoff():
    pool = _world()
    outside, verify = _rates(pool)
    train = np.ones(pool.n_tasks, bool)
    models = st.fit(pool, train)
    rule = st.rule_result(pool, models, 4, outside, verify, 0.0, train)

    scored = [ev.value({"m": pool}, p, outside, verify) for p in po.constant_family("m", pool.grid)]
    best = min(scored, key=lambda r: r.value)
    no_cutoff = min((r for r in scored if r.policy.cutoffs[0] is None), key=lambda r: r.value)
    assert rule.value < no_cutoff.value                    # reading the state beats not capping
    assert rule.value < best.value * 1.2                   # and lands near the best fixed cap


def test_the_rule_cross_fits_as_a_family_and_is_refitted_on_each_training_set():
    pool = _world(n=200)
    outside, verify = _rates(pool)
    fam = st.family(pool, outside, verify)
    got = inf.cross_fit(fam, inf.folds(pool.n_tasks))
    assert got.n_tasks == pool.n_tasks
    assert all("state rule" in c for c in got.choices)
    assert np.isfinite(got.value)
    # the fitted family sees only its training tasks: refitting on half the tasks gives a
    # different rule from refitting on all of them
    half = np.zeros(pool.n_tasks, bool)
    half[: pool.n_tasks // 2] = True
    assert not np.allclose(st.fit(pool, half).resolve, st.fit(pool, np.ones_like(half)).resolve)


def test_transfer_fits_the_models_elsewhere_and_keeps_the_targets_own_restart_values():
    target = _world(n=150, seed=1)
    elsewhere = _world(n=150, seed=2)
    other = ev.build("other", elsewhere.cap, target.tasks, elsewhere.runs,
                     [[[PER_CALL] * int(c) for c in row] for row in elsewhere.calls],
                     [[[10.0] * int(c) for c in row] for row in elsewhere.calls],
                     elsewhere.resolved, elsewhere.candidate, elsewhere.usable, elsewhere.minutes)
    outside, verify = _rates(target)
    fam = st.family(target, outside, verify, source={"other": other}, source_configs=("other",))
    got = inf.cross_fit(fam, inf.folds(target.n_tasks))
    assert np.isfinite(got.value)
    train = np.ones(target.n_tasks, bool)
    assert not np.allclose(st.fit(other, train).resolve, st.fit(target, train).resolve)
