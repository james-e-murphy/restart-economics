"""Step v: the cascade search, the two families it is compared through, and the diagnostics."""
import numpy as np
import pytest

from restart import cascade as cs
from restart import evaluate as ev
from restart import inference as inf

CAP = 25            # decision points 5, 10, 15, 20 and the configuration's own stop


def _pools(n=40, names=("a", "b", "c"), seed=3, shared=0.5, cost=(0.1, 0.2, 0.05)):
    """Configurations on the same tasks. ``shared`` sets how much of a task's difficulty is common
    to all of them: at one their failures coincide, at zero they are independent."""
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    common = rng.normal(0, 1, n)
    out = {}
    for j, name in enumerate(names):
        own = rng.normal(0, 1, n)
        skill = shared * common + (1 - shared) * own
        per_call, calls_, outs, wins = [], [], [], []
        for i in range(n):
            row_c, row_o, row_w = [], [], []
            for _ in range(4):
                calls = int(np.clip(rng.gamma(2.0, 5.0), 2, CAP))
                row_w.append(bool(rng.random() < 1 / (1 + np.exp(-(skill[i] + 0.5 - calls / 8)))))
                row_c.append([cost[j % len(cost)]] * calls)
                row_o.append([10.0] * calls)
            per_call.append(row_c), outs.append(row_o), wins.append(row_w)
        out[name] = ev.build(name, CAP, tasks, ("1", "2", "3", "4"), per_call, outs, wins,
                             candidate=[[True] * 4] * n, usable=[[True] * 4] * n,
                             minutes=[30.0] * n)
    return out


def _brute(b, train, k, start, passes=8):
    """The same ascent, every (configuration, cutoff) in every slot replayed by the evaluator."""
    here = np.asarray(train, bool) & b.mask

    def value(sched):
        res = cs.replay(b, sched)
        return float(res.per_task[here].mean())

    sched = list(start)
    for _ in range(passes):
        moved = False
        for j in range(k):
            best, pick = value(sched), sched[j]
            for c in b.names:
                trials = []
                for t in range(len(b.tabs[c].cutoffs)):
                    trial = list(sched)
                    trial[j] = (c, t)
                    trials.append(value(trial))
                t = int(np.argmin(trials))
                if trials[t] < best - 1e-12:
                    best, pick = trials[t], (c, t)
            if pick != sched[j]:
                sched[j], moved = pick, True
        if not moved:
            break
    return tuple(sched), value(sched)


@pytest.mark.parametrize("k", [1, 2, 3, 4])
def test_the_cascade_search_finds_what_replaying_every_candidate_finds(k):
    pools = _pools()
    b = cs.bank(pools, rate=40.0, fraction=0.0)
    train = np.arange(b.n_tasks) % 5 != 1
    start = [("a", len(b.tabs["a"].cutoffs) - 1)] * k
    fast, fast_value = cs.search(b, train, k, start)
    slow, slow_value = _brute(b, train, k, start)
    assert fast == slow
    assert fast_value == pytest.approx(slow_value, rel=1e-12)


def test_the_value_the_search_reports_is_the_value_the_evaluator_replays():
    pools = _pools(seed=9)
    for fraction, phi in ((0.0, 0.0), (0.5, 0.0), (0.3, 0.34)):
        b = cs.bank(pools, rate=80.0, fraction=fraction, phi=phi)
        train = np.arange(b.n_tasks) % 3 != 0
        sched, value = cs.search(b, train, 4, [("b", 0), ("a", 2), ("c", 4), ("b", 1)])
        replayed = cs.replay(b, sched).per_task[train & b.mask].mean()
        assert value == pytest.approx(replayed, rel=1e-12)


def test_on_its_training_tasks_the_cascade_never_loses_to_the_best_single_configuration():
    pools = _pools(n=50, seed=4)
    b = cs.bank(pools, rate=60.0, fraction=0.0)
    s = cs.Searches(b, (1, 2, 3, 4))
    train = np.arange(b.n_tasks) % 5 != 3
    single = cs.single_family(b, s).refit(train)
    casc = cs.cascade_family(b, s).refit(train)
    assert inf.means(casc, train & b.mask).min() <= inf.means(single, train & b.mask).min() + 1e-12


def test_switching_pays_when_failures_are_independent_and_not_when_they_coincide():
    rows = {}
    for shared in (0.0, 1.0):
        pools = _pools(n=80, seed=12, shared=shared, cost=(0.1, 0.1, 0.1))
        b = cs.bank(pools, rate=100.0, fraction=0.0)
        s = cs.Searches(b, (1, 2, 3, 4))
        train = np.ones(b.n_tasks, bool)
        single = inf.means(cs.single_family(b, s).refit(train), b.mask).min()
        casc = inf.means(cs.cascade_family(b, s).refit(train), b.mask).min()
        rows[shared] = single - casc
    assert rows[0.0] > rows[1.0] >= -1e-12


def test_the_cascade_can_be_kept_off_a_configuration():
    pools = _pools(seed=6)
    b = cs.bank(pools, rate=50.0, fraction=0.0)
    s = cs.Searches(b, (1, 2, 3, 4))
    fam = cs.cascade_family(b, s, names=("b", "c")).refit(np.ones(b.n_tasks, bool))
    assert all("a@" not in lab for lab in fam.labels)


def test_outcome_correlation_is_one_for_a_configuration_with_itself():
    pools = _pools(n=60, seed=2)
    names, corr, n = cs.outcome_correlation(pools)
    assert names == ("a", "b", "c") and n == 60
    assert np.allclose(np.diag(corr), 1.0) and np.allclose(corr, corr.T)


def test_a_cell_reports_the_cascade_beside_every_configuration_s_own_schedule():
    pools = _pools(n=50, seed=8)
    row = cs.cell(pools, rate=60.0, fraction=0.0, replicates=4, essential=True)
    assert row["switch_margin"] == pytest.approx(row["value_best_single"] - row["value_cascade"])
    assert row["replicates"] == 4 and row["switch_margin_low"] <= row["switch_margin_high"]
    for c in ("a", "b", "c"):
        assert np.isfinite(row[f"own_{c}"])
        assert row[f"essential_{c}"] == pytest.approx(row[f"without_{c}"] - row["value_cascade"])
    assert set(row["configurations_used"].split("|")) <= {"a", "b", "c"}


def test_pools_on_different_tasks_are_refused_until_aligned():
    pools = _pools(n=30)
    short = ev.restrict(pools["b"], np.arange(20))
    with pytest.raises(ValueError):
        cs.bank({"a": pools["a"], "b": short}, rate=50.0, fraction=0.0)
    aligned = ev.align({"a": pools["a"], "b": short})
    assert cs.bank(aligned, rate=50.0, fraction=0.0).n_tasks == 20
