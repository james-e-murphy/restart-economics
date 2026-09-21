"""The exact dynamic program the state rule is measured against: it is the optimum over its own
state and actions, its policy replays to its value, and the rule is scored beside it."""
import numpy as np
import pytest

from restart import dynamic as dy


MODEL = dy.Model()


def test_the_belief_is_a_distribution_that_high_output_moves_toward_a_bad_attempt():
    for i in (0, 5, 18):
        qs = [dy.belief(MODEL, i, k) for k in range(i + 2)]
        assert all(q.sum() == pytest.approx(1.0) for q in qs)
        good = [q[0] for q in qs]
        assert all(a >= b for a, b in zip(good, good[1:]))
    # with output that says nothing, surviving longer without finishing is itself evidence of a
    # bad attempt, since bad attempts finish less often
    silent = dy.Model(high=(0.5, 0.5))
    good = [dy.belief(silent, i, 0)[0] for i in range(19)]
    assert all(a > b for a, b in zip(good, good[1:]))


def test_evaluating_the_optimum_s_own_policy_returns_its_value():
    best, _, tables, budget = dy.solve(MODEL, 5.0, 1.0)
    assert dy.evaluate(MODEL, tables, budget, 5.0, 1.0) == pytest.approx(best)


@pytest.mark.parametrize("outside,verify", [(1.0, 0.0), (5.0, 0.0), (20.0, 10.0)])
def test_no_other_policy_on_the_same_state_does_better(outside, verify):
    best, _, tables, budget = dy.solve(MODEL, outside, verify)
    rng = np.random.default_rng(0)
    n_i = len(MODEL.points)
    for _ in range(25):
        k = int(rng.integers(1, 5))
        other = {j: rng.random((n_i, n_i + 1)) < 0.3 for j in range(1, k + 1)}
        assert best <= dy.evaluate(MODEL, other, k, outside, verify) + 1e-12
    for cut in range(n_i):
        for k in range(1, 5):
            const = {j: np.broadcast_to((np.arange(n_i) >= cut)[:, None], (n_i, n_i + 1))
                     for j in range(1, k + 1)}
            assert best <= dy.evaluate(MODEL, const, k, outside, verify) + 1e-12


def test_the_optimum_s_policy_replayed_on_simulated_attempts_costs_what_it_should():
    pool = dy.simulate(MODEL, 6000, seed=5)
    train = np.arange(pool.n_tasks) < 1000
    got = dy.compare(MODEL, 5.0, 0.0, pool, train)
    assert got["optimum_replayed"] == pytest.approx(got["optimum"], rel=0.04)
    # the optimum is the best policy on this state, so the rule and the constant cutoff can only
    # match it up to sampling noise
    assert got["rule"] >= got["optimum"] * 0.96
    assert got["constant"] >= got["optimum"] * 0.96


def test_the_count_of_high_intervals_is_read_back_from_cumulative_output():
    pool = dy.simulate(MODEL, 50, seed=9)
    k = dy.highs(MODEL, pool)
    i = np.arange(len(MODEL.points))[None, None, :]
    alive = pool.alive
    assert (k[alive] >= 0).all() and (k[alive] <= np.broadcast_to(i + 1, k.shape)[alive]).all()
    # a high interval costs more, so spend is a function of the count and the point
    n = (np.asarray(MODEL.points) // dy.STEP)[None, None, :]
    spend = MODEL.cost[0] * (n - k) + MODEL.cost[1] * k
    assert np.allclose(spend[alive], pool.cost_grid[alive])


def test_the_study_writes_its_log(tmp_path):
    rows = dy.study(multiples=(5.0,), fractions=(0.0,), train_tasks=300, test_tasks=600,
                    log=lambda line: None)
    assert len(rows) == len(dy.SETTINGS)
    for r in rows:
        assert r["optimum_stops"] >= 0 and r["rule_stops"] >= 0
