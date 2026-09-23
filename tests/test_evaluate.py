"""The evaluator, checked to the cent against costs worked out by hand.

The four cases PLAN.md Section 8 names are built here as a pool: a task no draw resolves, a task
every draw resolves, a task one of four draws resolves, and a task with a run that stopped at the
harness's iteration limit. Their policy costs are written out in the assertions, enumerated by
hand rather than by the code under test.
"""
import numpy as np
import pytest

from restart import evaluate as ev
from restart import policies as po

RATE = 100.0            # dollars per hour; every task here is annotated at one hour
H = 100.0               # so the outside option is $100 a task
PER_CALL = 0.1


def _attempt(calls):
    return [PER_CALL] * calls, [10] * calls     # cost per call, output tokens per call


def _pool(config="m", cap=100, candidate=True, grid=None):
    """Four tasks: none resolved, all resolved, one of four resolved, and one with a run that ran
    to a 100-call limit. Every attempt ends with a patch to verify."""
    calls = {
        "none":  [10, 10, 10, 10],
        "all":   [2, 2, 2, 2],
        "one":   [5, 10, 10, 10],
        "limit": [100, 10, 10, 10],
    }
    resolved = {
        "none":  [False] * 4,
        "all":   [True] * 4,
        "one":   [True, False, False, False],
        "limit": [False] * 4,
    }
    tasks = tuple(calls)
    cost, out = [], []
    for t in tasks:
        row = [_attempt(c) for c in calls[t]]
        cost.append([c for c, _ in row])
        out.append([o for _, o in row])
    return ev.build(config, cap, tasks, ("1", "2", "3", "4"), cost, out,
                    resolved=[resolved[t] for t in tasks],
                    candidate=[[candidate] * 4 for _ in tasks],
                    usable=[[True] * 4 for _ in tasks],
                    minutes=[60.0] * len(tasks), grid=grid)


def _value(pool, policy, verify=0.0):
    h = ev.outside_option(pool, RATE)
    return ev.value({pool.config: pool}, policy, h, np.full(pool.n_tasks, verify))


def test_the_grid_is_the_plans_grid():
    assert po.decision_points(100) == tuple(range(5, 100, 5))
    assert len(po.decision_points(100)) == 19
    assert len(po.decision_points(500)) == 35
    assert po.decision_points(500)[-1] == 475
    with pytest.raises(ValueError):
        _pool().point(7)


def test_one_attempt_no_cutoff():
    got = _value(_pool(), po.single("m"))
    # none: 1.00 spent, then the outside option. all: 0.20 and done. one: a quarter of the draws
    # resolve at 0.50, the rest spend 1.00 and escalate. limit: the long run costs 10.00.
    by_task = dict(zip(got.tasks, got.per_task))
    assert by_task["none"] == pytest.approx(1.0 + H)
    assert by_task["all"] == pytest.approx(0.2)
    assert by_task["one"] == pytest.approx((0.5 + 3 * (1.0 + H)) / 4)
    assert by_task["limit"] == pytest.approx((10.0 + 3 * 1.0) / 4 + H)
    assert got.n_tasks == 4


def test_two_attempts_no_cutoff_enumerated_by_hand():
    got = _value(_pool(), po.retry("m", 2))
    by_task = dict(zip(got.tasks, got.per_task))
    assert by_task["none"] == pytest.approx(2.0 + H)
    assert by_task["all"] == pytest.approx(0.2)
    # twelve ordered pairs: the resolving draw first in three, second in three, absent in six
    assert by_task["one"] == pytest.approx((3 * 0.5 + 3 * 1.5 + 6 * (2.0 + H)) / 12)
    # every pair fails; each draw leads three of the twelve pairs
    assert by_task["limit"] == pytest.approx(2 * 3 * (10.0 + 1.0 + 1.0 + 1.0) / 12 + H)
    assert got.value == pytest.approx(np.mean([by_task[t] for t in got.tasks]))
    assert (got.orderings == 12).all()


def test_verification_is_charged_only_on_attempts_that_reach_their_own_stop():
    v = 10.0
    got = _value(_pool(), po.retry("m", 2), verify=v)
    by_task = dict(zip(got.tasks, got.per_task))
    assert by_task["none"] == pytest.approx(2.0 + 2 * v + H)
    assert by_task["all"] == pytest.approx(0.2 + v)
    assert by_task["one"] == pytest.approx(
        (3 * (0.5 + v) + 3 * (1.0 + v + 0.5 + v) + 6 * (2.0 + 2 * v + H)) / 12)
    # a cutoff discards the attempt unverified, so no verification is charged at all
    cut = _value(_pool(), po.constant("m", 5, 2), verify=v)
    assert dict(zip(cut.tasks, cut.per_task))["none"] == pytest.approx(2 * 5 * PER_CALL + H)


def test_a_cutoff_truncates_and_resolves_nothing():
    got = _value(_pool(), po.constant("m", 5, 2))
    by_task = dict(zip(got.tasks, got.per_task))
    # every "none" draw is ten calls long, so both attempts stop at five calls
    assert by_task["none"] == pytest.approx(2 * 0.5 + H)
    # "all" finishes in two calls, before the cutoff, so the cutoff changes nothing
    assert by_task["all"] == pytest.approx(0.2)
    # "one" resolves in exactly five calls, so at a cutoff of five it has already reached its own
    # stop and still resolves: the cutoff stops attempts that are running after five calls
    assert by_task["one"] == pytest.approx((3 * 0.5 + 3 * 1.0 + 6 * (2 * 0.5 + H)) / 12)
    # the limit run is cut from 100 calls to 5
    assert by_task["limit"] == pytest.approx(2 * 0.5 + H)


def test_a_cutoff_at_or_above_every_attempt_is_no_cutoff():
    pool = _pool(cap=500)
    late = po.constant("m", 125, 2)
    assert (_value(pool, late).per_task ==
            pytest.approx(_value(pool, po.retry("m", 2)).per_task))


def test_a_task_that_cannot_fill_the_policy_is_left_out_and_counted():
    pool = _pool()
    usable = pool.usable.copy()
    usable[pool.tasks.index("one"), 1:] = False          # one usable draw left
    thin = ev.build(pool.config, pool.cap, pool.tasks, pool.runs,
                    [[[PER_CALL] * int(c) for c in row] for row in pool.calls],
                    [[[10] * int(c) for c in row] for row in pool.calls],
                    pool.resolved, pool.candidate, usable, pool.minutes)
    two = _value(thin, po.retry("m", 2))
    assert two.n_tasks == 3 and not two.used[thin.tasks.index("one")]
    one = _value(thin, po.single("m"))
    assert one.n_tasks == 4 and one.orderings[thin.tasks.index("one")] == 1
    assert dict(zip(one.tasks, one.per_task))["one"] == pytest.approx(0.5)


def test_a_cascade_averages_over_both_configurations_draws():
    first = _pool("x")
    second = _pool("y")
    pools = {"x": first, "y": second}
    policy = po.cascade((("x", None), ("y", None)))
    h = ev.outside_option(first, RATE)
    got = ev.value(pools, policy, h, np.zeros(first.n_tasks))
    by_task = dict(zip(got.tasks, got.per_task))
    # the second slot's draw is chosen independently of the first's, so the sixteen combinations
    # are equally likely: x's draw resolves "one" a quarter of the time, and when it does not,
    # y's draw resolves it a quarter of the time
    assert by_task["one"] == pytest.approx(
        np.mean([0.5 if a == 0 else 1.0 + (0.5 if b == 0 else 1.0 + H)
                 for a in range(4) for b in range(4)]))
    assert (got.orderings == 16).all()


def test_the_loader_prices_the_synthetic_archive(synthetic_archive, tmp_path):
    from restart.extract import extract
    out = tmp_path / "derived"
    extract(str(synthetic_archive), str(out))
    pool = ev.load(str(out), key="gpt-5_4runs")
    assert pool.n_draws == 2 and pool.n_tasks == 4
    assert pool.usable.sum() == 6                     # the census of the extraction tests
    assert pool.cap == 100 and pool.grid == tuple(range(5, 100, 5))
    ran = pool.calls > 0
    assert (pool.cost_end[ran] > 0).all()
    # cumulative cost at a point past the attempt's own stop is the whole attempt
    for i in range(pool.n_tasks):
        for d in range(pool.n_draws):
            if pool.calls[i, d]:
                past = [j for j, t in enumerate(pool.grid) if t >= pool.calls[i, d]]
                if past:
                    assert pool.cost_grid[i, d, past[0]] == pytest.approx(pool.cost_end[i, d])
                    assert not pool.alive[i, d, past[0]]
    assert set(np.unique(pool.minutes)) <= set(ev.MINUTES.values())


def test_the_dry_run_recovers_a_known_optimal_cutoff_and_budget():
    """A world with a known answer: an attempt either resolves at its tenth call or runs to the
    harness's cap of 100 and fails. The cheapest policy is therefore to cap every attempt at ten
    calls and to use all four attempts, and its value is known in closed form."""
    rng, p, n = np.random.default_rng(7), 0.35, 300
    tasks = tuple(f"t{i}" for i in range(n))
    cost, out, resolved = [], [], []
    for _ in tasks:
        wins = rng.random(4) < p
        row = [_attempt(10 if w else 100) for w in wins]
        cost.append([c for c, _ in row])
        out.append([o for _, o in row])
        resolved.append(list(wins))
    pool = ev.build("m", 100, tasks, ("1", "2", "3", "4"), cost, out, resolved,
                    candidate=[[True] * 4 for _ in tasks], usable=[[True] * 4 for _ in tasks],
                    minutes=[60.0] * n)

    family = po.constant_family("m", pool.grid)
    scored = [_value(pool, policy) for policy in family]
    best = min(scored, key=lambda r: r.value)
    assert best.policy.k == 4 and best.policy.cutoffs[0] == 10

    # closed form: every attempt costs 1.00 at a cutoff of ten, and the task escalates only when
    # all four attempts fail
    analytic = sum((1 - p) ** j for j in range(4)) * 1.0 + (1 - p) ** 4 * H
    se = float(np.std(best.per_task[best.used], ddof=1) / np.sqrt(best.n_tasks))
    assert abs(best.value - analytic) < 3 * se

    at_ten = {r.policy.k: r.value for r in scored if r.policy.cutoffs[0] == 10}
    assert at_ten[4] < at_ten[3] < at_ten[2] < at_ten[1]         # retrying pays at this rate
    no_cutoff = {r.policy.k: r.value for r in scored if r.policy.cutoffs[0] is None}
    assert at_ten[4] < no_cutoff[4]                              # and the cap pays on top of it


def test_a_schedule_varies_the_cutoff_by_attempt():
    got = _value(_pool(), po.schedule("m", (5, None)))
    by_task = dict(zip(got.tasks, got.per_task))
    # the resolving draw of "one" ends at exactly five calls, so it survives the first slot's
    # cutoff; the others are cut there and only resolve nothing, while the second slot runs on
    assert by_task["one"] == pytest.approx(
        np.mean([0.5 if a == 0 else 0.5 + (0.5 if b == 0 else 1.0 + H)
                 for a in range(4) for b in range(4) if a != b]))
    assert by_task["none"] == pytest.approx(0.5 + 1.0 + H)


def test_a_cascade_can_fill_several_slots_from_one_configuration():
    pools = {"x": _pool("x"), "y": _pool("y")}
    policy = po.cascade((("x", None), ("y", None), ("x", None)))
    h = ev.outside_option(pools["x"], RATE)
    got = ev.value(pools, policy, h, np.zeros(pools["x"].n_tasks))
    by_task = dict(zip(got.tasks, got.per_task))
    assert (got.orderings == 48).all()          # ordered pairs of x draws times one y draw
    assert by_task["none"] == pytest.approx(3.0 + H)
    assert by_task["one"] == pytest.approx(np.mean(
        [0.5 if a1 == 0 else 1.0 + (0.5 if b == 0 else 1.0 + (0.5 if a2 == 0 else 1.0 + H))
         for a1 in range(4) for a2 in range(4) if a1 != a2 for b in range(4)]))


def test_weighting_is_uniform_over_the_ordered_subsets_of_usable_draws():
    pool = _pool()
    usable = pool.usable.copy()
    usable[pool.tasks.index("one"), 3] = False              # three usable draws left
    thin = ev.build(pool.config, pool.cap, pool.tasks, pool.runs,
                    [[[PER_CALL] * int(c) for c in row] for row in pool.calls],
                    [[[10] * int(c) for c in row] for row in pool.calls],
                    pool.resolved, pool.candidate, usable, pool.minutes)
    got = _value(thin, po.retry("m", 2))
    i = thin.tasks.index("one")
    assert got.orderings[i] == 6
    assert got.per_task[i] == pytest.approx(np.mean(
        [0.5 if a == 0 else 1.0 + (0.5 if b == 0 else 1.0 + H)
         for a in range(3) for b in range(3) if a != b]))


def test_an_attempt_with_no_patch_is_not_verified():
    got = _value(_pool(candidate=False), po.single("m"), verify=10.0)
    assert dict(zip(got.tasks, got.per_task))["none"] == pytest.approx(1.0 + H)


def test_the_common_horizon_stops_attempts_at_the_horizon():
    grid = po.common_horizon(po.decision_points(500))
    assert grid[-1] == 100 and len(grid) == 20
    pool = _pool(cap=500, grid=grid)
    got = _value(pool, po.constant("m", 100, 1))
    # the hundred-call run reaches its own stop exactly at the horizon and still fails; the
    # others are shorter, so nothing is truncated here and the task escalates either way
    assert dict(zip(got.tasks, got.per_task))["limit"] == pytest.approx((10.0 + 3 * 1.0) / 4 + H)


def test_the_state_variables_are_the_ones_the_plan_names():
    pool = _pool()
    i, five, ten = pool.tasks.index("none"), pool.grid.index(5), pool.grid.index(10)
    assert pool.out_grid[i, 0, five] == pytest.approx(50)        # ten output tokens a call
    assert pool.out_recent[i, 0, five] == pytest.approx(50)      # the whole run so far
    assert pool.out_recent[i, 0, ten] == pytest.approx(50)       # calls six to ten
    assert pool.cost_rate[i, 0, ten] == pytest.approx(PER_CALL)  # dollars per call, not per window
    short = pool.tasks.index("all")                             # a two-call attempt
    assert pool.out_recent[short, 0, five] == pytest.approx(20)
    assert pool.cost_rate[short, 0, five] == pytest.approx(PER_CALL)


def test_a_false_accept_pays_the_outside_option_later():
    phi = 0.34
    pool = _pool()
    h = ev.outside_option(pool, RATE)
    got = ev.value({"m": pool}, po.single("m"), h, np.zeros(pool.n_tasks), phi=phi)
    by_task = dict(zip(got.tasks, got.per_task))
    assert by_task["all"] == pytest.approx(0.2 + phi * H)
    assert by_task["none"] == pytest.approx(1.0 + H)            # nothing was accepted
    assert by_task["one"] == pytest.approx((0.5 + phi * H + 3 * (1.0 + H)) / 4)


def test_comparisons_across_budgets_can_be_held_to_the_same_tasks():
    pool = _pool()
    usable = pool.usable.copy()
    usable[pool.tasks.index("one"), 2:] = False
    thin = ev.build(pool.config, pool.cap, pool.tasks, pool.runs,
                    [[[PER_CALL] * int(c) for c in row] for row in pool.calls],
                    [[[10] * int(c) for c in row] for row in pool.calls],
                    pool.resolved, pool.candidate, usable, pool.minutes)
    pools = {"m": thin}
    keep = ev.full_draw_tasks(pools)
    assert keep.sum() == 3 and not keep[thin.tasks.index("one")]
    h = ev.outside_option(thin, RATE)
    one = ev.value(pools, po.single("m"), h, np.zeros(thin.n_tasks), mask=keep)
    four = ev.value(pools, po.retry("m", 4), h, np.zeros(thin.n_tasks), mask=keep)
    assert one.n_tasks == four.n_tasks == 3
    assert (one.used == four.used).all()


def test_the_loader_carries_the_prespecified_sensitivities(synthetic_archive, tmp_path):
    import csv
    from restart.extract import extract
    out = tmp_path / "derived"
    extract(str(synthetic_archive), str(out))
    base = ev.load(str(out), key="gpt-5_4runs")
    assert base.usable.sum() == 6
    assert ev.load(str(out), key="gpt-5_4runs", retain_refusals=False).usable.sum() == 5
    assert ev.load(str(out), key="gpt-5_4runs", no_verdict_unresolved=True).usable.sum() == 7
    rows = list(csv.DictReader(open(next((out).glob("executions_*.csv")))))
    rerun = sum(1 for r in rows if int(r["prior_try_logs"] or 0) > 0
                and r["usable"] == "True")
    assert ev.load(str(out), key="gpt-5_4runs", drop_reruns=True).usable.sum() == 6 - rerun


# ----------------------------------------------------------------------------- sensitivities

def test_the_common_horizon_stops_every_attempt_still_running_at_it_as_a_failure():
    tasks = ("a", "b")
    # a resolves at call 60; b resolves at call 180, past the horizon
    cost = [[[0.01] * 60], [[0.01] * 180]]
    out = [[[5.0] * 60], [[5.0] * 180]]
    pool = ev.build("m", 500, tasks, ("1",), cost, out, resolved=[[True], [True]],
                    candidate=[[True], [True]], usable=[[True], [True]], minutes=[30.0, 30.0])
    short = ev.truncate(pool, 100)
    assert short.cap == 100 and max(short.grid) == 95
    assert short.resolved.tolist() == [[True], [False]]
    assert short.candidate.tolist() == [[True], [False]]
    assert short.cost_end[0, 0] == pytest.approx(0.60)       # unchanged: it stopped at 60
    assert short.cost_end[1, 0] == pytest.approx(1.00)       # what it had spent by call 100
    assert short.calls.tolist() == [[60], [100]]
    # a configuration already capped at the horizon is left as it is
    assert ev.truncate(short, 100) is short


def test_the_two_stage_resample_draws_attempts_within_the_tasks_it_draws():
    pool = _pool()
    idx = np.array([1, 1, 0])
    draws = np.array([[0, 0, 1, 2], [3, 3, 3, 3], [2, 1, 0, 0]])
    got = ev.resample(pool, idx, draws)
    assert got.tasks == (pool.tasks[1], pool.tasks[1], pool.tasks[0])
    for r, (i, row) in enumerate(zip(idx, draws)):
        for c, d in enumerate(row):
            assert got.cost_end[r, c] == pool.cost_end[i, d]
            assert got.resolved[r, c] == pool.resolved[i, d]
            assert (got.cost_grid[r, c] == pool.cost_grid[i, d]).all()


def test_the_metr_correction_keeps_the_measured_buckets_and_interpolates_between_them():
    m = ev.metr_minutes()
    assert m["<15 min fix"] == 32.9 and m["1-4 hours"] == 131.6
    # between the two measured buckets the factor falls from about 8.4 to about 1.1
    factor = m["15 min - 1 hour"] / ev.MINUTES["15 min - 1 hour"]
    assert 131.6 / 120.0 < factor < 32.9 / 3.9
    # above the last measured bucket it is held, not extrapolated
    assert m[">4 hours"] / 480.0 == pytest.approx(131.6 / 120.0)


def test_the_share_the_policy_resolves_itself_is_enumerated_beside_its_cost():
    """PLAN.md Section 3: beside the value, the share of tasks resolved without the outside
    option. One attempt resolves 'one' a quarter of the time; two attempts, in six of twelve
    ordered pairs; a cutoff below the resolving draw's length resolves nothing."""
    one = _value(_pool(), po.single("m"))
    by = dict(zip(one.tasks, one.resolved))
    assert by["none"] == 0.0 and by["all"] == 1.0 and by["limit"] == 0.0
    assert by["one"] == pytest.approx(0.25)
    assert one.share == pytest.approx((0 + 1 + 0.25 + 0) / 4)
    two = _value(_pool(), po.retry("m", 2))
    assert dict(zip(two.tasks, two.resolved))["one"] == pytest.approx(6 / 12)
    assert two.share >= one.share
    # at a cutoff of five the resolving draw has reached its own stop and still counts, and a
    # cutoff can never resolve more than no cutoff
    cut = _value(_pool(), po.constant("m", 5, 2))
    assert dict(zip(cut.tasks, cut.resolved))["one"] == pytest.approx(6 / 12)
    assert cut.share <= two.share
    # a task that cannot fill the policy has no share, as it has no cost
    assert np.isnan(one.resolved).sum() == np.isnan(one.per_task).sum()
