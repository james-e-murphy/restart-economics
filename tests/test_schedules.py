"""Step iii-b: the schedule search.

The search scores a candidate cutoff by a factorization of the replay rather than by replaying the
whole schedule, so the tests hold it against the evaluator itself: the same schedules, the same
values, the same choices.
"""
import numpy as np
import pytest

from restart import evaluate as ev
from restart import inference as inf
from restart import policies as po
from restart import schedules as sc

POINTS = (5, 10, 20, 40)


def _world(n=40, seed=11, draws=4, usable=None):
    """Attempts whose chance of resolving falls with their length, so a cutoff has something to do
    and the best cutoff is not at either end of the grid."""
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    cost, out, resolved, cand = [], [], [], []
    for _ in tasks:
        row, wins = [], []
        for _ in range(draws):
            calls = int(np.clip(rng.gamma(2.0, 9.0), 2, 60))
            wins.append(bool(rng.random() < 1 / (1 + np.exp((calls - 18) / 5.0))))
            row.append(([0.05 + 0.01 * rng.random()] * calls, [10.0] * calls))
        cost.append([c for c, _ in row])
        out.append([o for _, o in row])
        resolved.append(wins)
        cand.append([True] * draws)
    return ev.build("m", 100, tasks, tuple(str(i) for i in range(draws)), cost, out, resolved,
                    candidate=cand,
                    usable=[[True] * draws for _ in tasks] if usable is None else usable,
                    minutes=[60.0] * n)


def _setting(pool, rate=60.0, fraction=0.0, phi=0.0, points=POINTS):
    outside = ev.outside_option(pool, rate)
    verify = ev.verification(outside, fraction)
    tab = sc.table(pool, points)
    charge, survive = sc.charges(tab, outside, verify, phi)
    return outside, verify, tab, charge, survive


def _replay(pool, tab, sched, outside, verify, phi, train):
    """What the evaluator says the schedule costs on the training tasks."""
    got = ev.value({pool.config: pool},
                   po.schedule(pool.config, [tab.cutoffs[c] for c in sched]),
                   outside, verify, phi, mask=train, arrays=[tab.arrays(c) for c in sched])
    return got.value


def _brute(pool, tab, outside, verify, phi, train, k, start, passes=8):
    """The same coordinate ascent, every candidate replayed in full by the evaluator."""
    sched = list(start)
    for _ in range(passes):
        moved = False
        for j in range(k):
            trials = []
            for c in range(len(tab.cutoffs)):
                trial = list(sched)
                trial[j] = c
                trials.append(_replay(pool, tab, trial, outside, verify, phi, train))
            pick = int(np.argmin(trials))
            if trials[pick] < trials[sched[j]] - 1e-12:
                sched[j], moved = pick, True
        if not moved:
            break
    return tuple(sched), _replay(pool, tab, sched, outside, verify, phi, train)


@pytest.mark.parametrize("k", [1, 2, 3, 4])
def test_the_search_finds_what_replaying_every_candidate_finds(k):
    pool = _world()
    outside, verify, tab, charge, survive = _setting(pool)
    train = np.ones(pool.n_tasks, bool)
    start = [len(tab.cutoffs) - 1] * k
    fast, value = sc.search(pool, tab, charge, survive, outside, train, k, start)
    slow, slow_value = _brute(pool, tab, outside, verify, 0.0, train, k, start)
    assert fast == slow
    assert value == pytest.approx(slow_value, rel=1e-12)


def test_the_value_the_search_reports_is_the_value_the_evaluator_replays():
    pool = _world(seed=3)
    for fraction, phi, rate in ((0.0, 0.0, 30.0), (0.5, 0.0, 120.0), (0.3, 0.34, 80.0)):
        outside, verify, tab, charge, survive = _setting(pool, rate, fraction, phi)
        train = np.arange(pool.n_tasks) % 3 != 0
        sched, value = sc.search(pool, tab, charge, survive, outside, train, 3)
        assert value == pytest.approx(
            _replay(pool, tab, sched, outside, verify, phi, train), rel=1e-12)


def test_tasks_without_enough_usable_draws_are_left_out_of_the_search():
    n = 40
    usable = [[True] * 4 for _ in range(n)]
    for i in range(0, n, 5):                       # every fifth task keeps two draws
        usable[i][2] = usable[i][3] = False
    pool = _world(n=n, seed=7, usable=usable)
    outside, verify, tab, charge, survive = _setting(pool)
    train = np.ones(n, bool)
    sched, value = sc.search(pool, tab, charge, survive, outside, train, 3)
    # the evaluator scores a task only when it can fill the policy; the search must agree, both on
    # which tasks those are and on the weight each gets
    assert value == pytest.approx(_replay(pool, tab, sched, outside, verify, 0.0, train), rel=1e-12)


def test_the_search_never_returns_a_schedule_worse_than_the_one_it_started_from():
    pool = _world(seed=5)
    outside, verify, tab, charge, survive = _setting(pool)
    train = np.arange(pool.n_tasks) % 4 != 1
    for start_cut in range(len(tab.cutoffs)):
        start = [start_cut] * 3
        sched, value = sc.search(pool, tab, charge, survive, outside, train, 3, start)
        assert value <= _replay(pool, tab, start, outside, verify, 0.0, train) + 1e-12


def test_the_schedule_family_beats_the_best_constant_cutoff_on_its_own_training_tasks():
    pool = _world(n=60, seed=9)
    outside, verify, tab, charge, survive = _setting(pool)
    ks = (1, 2, 3, 4)
    constants = inf.Family.of([ev.value({pool.config: pool}, p, outside, verify)
                               for p in po.constant_family(pool.config, POINTS, ks)])
    fam = sc.family(pool, outside, verify, ks=ks, tab=tab,
                    start=sc.constant_start(constants, tab, ks))
    train = np.arange(pool.n_tasks) % 5 != 0
    fitted = fam.refit(train)
    best_schedule = inf.means(fitted, train).min()
    best_constant = inf.means(constants, train).min()
    assert best_schedule <= best_constant + 1e-12
    assert all(lab.startswith("iii-b:") for lab in fitted.labels)


def test_cross_fitting_the_schedule_family_records_what_each_fold_chose():
    pool = _world(n=60, seed=13)
    outside, verify, tab, charge, survive = _setting(pool)
    fam = sc.family(pool, outside, verify, tab=tab)
    got = inf.cross_fit(fam, inf.folds(pool.n_tasks))
    assert got.n_tasks == pool.n_tasks
    assert len(got.choices) == inf.FOLDS
    assert all("schedule" in c for c in got.choices)


def test_the_bootstrap_refits_the_search_inside_the_replicate():
    pool = _world(n=40, seed=17)
    outside, verify, tab, charge, survive = _setting(pool)
    fam = sc.family(pool, outside, verify, tab=tab, ks=(2,))
    got = inf.bootstrap(pool.n_tasks, lambda idx: inf.cross_fitted_value(fam, idx), replicates=8)
    assert got["replicates"] + got["dropped"] == 8
    assert np.isfinite(got["low"]) and got["low"] <= got["high"]
