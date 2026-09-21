"""The sample oracle: the recursion's minimum is the minimum over every schedule in the class,
found by brute force on a small grid, and it sits below every policy chosen from the class."""
import itertools

import numpy as np
import pytest

from restart import cascade as cs
from restart import evaluate as ev
from restart import oracle as orc
from restart import policies as po
from restart import schedules as sc

GRID = (5, 10)


def _pools(n=6, names=("a", "b"), seed=4, cap=20, fail_task=None):
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    minutes = rng.choice([3.9, 30.0], n)
    out = {}
    for j, name in enumerate(names):
        cost, toks, wins = [], [], []
        for i in range(n):
            rc, ro, rw = [], [], []
            for _ in range(4):
                calls = int(rng.integers(3, cap))
                rw.append(bool(rng.random() < 0.45) and i != fail_task)
                rc.append(list(rng.gamma(2.0, 0.02 * (1 + j), calls)))
                ro.append([10.0] * calls)
            cost.append(rc), toks.append(ro), wins.append(rw)
        out[name] = ev.build(name, cap, tasks, ("1", "2", "3", "4"), cost, toks, wins,
                             candidate=[[True] * 4] * n, usable=[[True] * 4] * n,
                             minutes=minutes, grid=GRID)
    return out


def _brute(pools, rate, fraction, phi=0.0):
    """Every schedule of one to four attempts over (configuration, cutoff), each replayed by the
    evaluator, and the least of them per task."""
    names = tuple(pools)
    first = pools[names[0]]
    outside = ev.outside_option(first, rate)
    verify = ev.verification(outside, fraction)
    slots = [(c, t) for c in names for t in GRID + (None,)]
    best = np.full(first.n_tasks, np.inf)
    for k in range(1, 5):
        for pairs in itertools.product(slots, repeat=k):
            got = ev.value(pools, po.cascade(pairs), outside, verify, phi)
            best = np.minimum(best, got.per_task)
    return best


@pytest.mark.parametrize("rate,fraction,phi", [(5.0, 0.0, 0.0), (100.0, 0.0, 0.0),
                                               (60.0, 0.5, 0.0), (60.0, 0.1, 0.4)])
def test_the_recursion_finds_the_minimum_over_every_schedule(rate, fraction, phi):
    pools = _pools(fail_task=2)
    _, per_task = orc.oracle(pools, [rate], [fraction], phi)
    assert np.allclose(per_task[:, 0], _brute(pools, rate, fraction, phi))


def test_the_benchmark_bounds_every_policy_chosen_from_the_class():
    pools = _pools(n=30, names=("a", "b", "c"), seed=9)
    mask = ev.full_draw_tasks(pools)
    means, per_task = orc.oracle(pools, [5.0, 100.0], [0.0, 0.5])
    for (rate, fraction), best in zip([(5.0, 0.0), (100.0, 0.5)], means):
        got = cs.cell(pools, rate, fraction, 0.0, mask, replicates=0)
        assert best <= got["value_cascade"] + 1e-12
        assert best <= got["value_best_single"] + 1e-12
        assert best <= got["value_escalate"] + ev.median_attempt_cost(pools["a"]) * 10


def test_a_cutoff_is_a_candidate_only_as_the_smallest_that_resolves_its_draws():
    pools = _pools()
    tab = sc.table(pools["a"])
    for i in range(pools["a"].n_tasks):
        cands = orc.candidates(tab, i)
        sets = [tuple(tab.resolves[c, i]) for c in cands]
        assert len(set(sets)) == len(sets) and all(any(s) for s in sets)
        for c in range(len(tab.cutoffs)):
            key = tuple(tab.resolves[c, i])
            if any(key):
                assert min(x for x in cands if tuple(tab.resolves[x, i]) == key) <= c


def test_a_task_no_configuration_resolves_costs_one_cheapest_attempt_and_the_outside_option():
    pools = _pools(fail_task=2)
    _, per_task = orc.oracle(pools, [40.0], [0.3])
    tabs = [sc.table(p) for p in pools.values()]
    h = ev.outside_option(pools["a"], 40.0)[2]
    cheapest = min(float((t.cost[:, 2] + 0.3 * h * t.checks[:, 2]).mean(axis=1).min())
                   for t in tabs)
    assert per_task[2, 0] == pytest.approx(cheapest + h)
