"""Replay: what a policy would have cost on the attempts as they were logged.

Every policy in the class stops at or before the point where the harness stopped, so its outcome
on a logged attempt is that attempt truncated (PLAN.md Section 5). Nothing is imputed and nothing
is modelled: an attempt cut off at call *t* costs what its first *t* calls cost, is discarded
unverified, and resolves nothing; an attempt that reaches its own stop costs what it cost, is
verified if it produced a patch to check, and resolves if the benchmark's tests accepted it.

For a task the value of a policy is the average over the orderings of that task's usable draws,
which is what exchangeability licenses: *K* attempts are an ordered *K*-subset of the four logged
runs, every subset as likely as any other. Across configurations the draws are independent, so a
cascade averages over the product of each configuration's orderings. A task contributes only when
it has enough usable draws to fill the policy, and the count of contributing tasks is returned
beside the value.

The tables this reads carry physical quantities only. Dollars enter here, through
``restart.pricing``, and the outside option enters through a rate, so a price change or a rate
change refits policies rather than rescaling a stored total.
"""
from __future__ import annotations

import csv
import dataclasses
import glob
import itertools
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import pricing
from .extract import reclassify
from .policies import Policy, decision_points

# SWE-bench Verified's annotation of engineer time to fix, at the geometric means of METR's
# Table 8, in minutes. The bucket strings are the release's own.
MINUTES = {"<15 min fix": 3.9, "15 min - 1 hour": 30.0, "1-4 hours": 120.0, ">4 hours": 480.0}

# The prespecified sensitivity to the annotation's optimism (PLAN.md Section 3): METR baselined
# four tasks from the shortest bucket at a geometric mean of 32.9 minutes and two from the 1-to-4
# hour bucket at 131.6. The plan fixes those two buckets at the measured means and interpolates the
# other two. The interpolation is of the correction factor, measured over annotated minutes, in
# logarithms on both axes, between the two measured buckets; above the last one, where there is
# nothing to interpolate toward, the factor is held where it was measured rather than extrapolated.
METR_MEASURED = {"<15 min fix": 32.9, "1-4 hours": 131.6}


def metr_minutes() -> Dict[str, float]:
    """The outside option's minutes under the bucket-specific METR correction."""
    lo, hi = "<15 min fix", "1-4 hours"
    f_lo = np.log(METR_MEASURED[lo] / MINUTES[lo])
    f_hi = np.log(METR_MEASURED[hi] / MINUTES[hi])
    x_lo, x_hi = np.log(MINUTES[lo]), np.log(MINUTES[hi])
    out = {}
    for bucket, m in MINUTES.items():
        if bucket in METR_MEASURED:
            out[bucket] = METR_MEASURED[bucket]
            continue
        x = np.log(m)
        t = min(max((x - x_lo) / (x_hi - x_lo), 0.0), 1.0)
        out[bucket] = float(m * np.exp(f_lo + t * (f_hi - f_lo)))
    return out

WINDOW = 5      # the recent-rate window, one decision point wide in the fine part of the grid


@dataclass(frozen=True)
class Pool:
    """One configuration's attempts, indexed [task, draw], with everything a policy needs.

    ``grid`` holds the decision points. For each of them the pool carries what an attempt stopped
    there would have cost, whether it is still running, and the state variables the rule of
    Section 6 reads. ``_end`` arrays are the attempt run to its own stop.
    """
    config: str
    cap: int
    tasks: Tuple[str, ...]
    runs: Tuple[str, ...]
    grid: Tuple[int, ...]
    usable: np.ndarray          # [task, draw] bool: in the attempt pool
    calls: np.ndarray           # [task, draw] int: calls the attempt made
    resolved: np.ndarray        # [task, draw] bool: the evaluation accepted its patch
    candidate: np.ndarray       # [task, draw] bool: it ended with a patch to verify
    cost_end: np.ndarray        # [task, draw] dollars, whole attempt
    out_end: np.ndarray         # [task, draw] output tokens, whole attempt
    cost_grid: np.ndarray       # [task, draw, point] dollars to that point
    out_grid: np.ndarray        # [task, draw, point] cumulative output tokens
    out_recent: np.ndarray      # [task, draw, point] output tokens over the last five calls
    cost_rate: np.ndarray       # [task, draw, point] dollars per call over the last five calls
    alive: np.ndarray           # [task, draw, point] bool: still running at that point
    minutes: np.ndarray         # [task] annotated engineer minutes

    @property
    def n_tasks(self) -> int:
        return len(self.tasks)

    @property
    def n_draws(self) -> int:
        return len(self.runs)

    def point(self, cutoff: int) -> int:
        """The index of a cutoff on the grid. A cutoff that is not a decision point is refused."""
        try:
            return self.grid.index(cutoff)
        except ValueError:
            raise ValueError(f"{cutoff} is not a decision point of {self.config}") from None


def build(config: str, cap: int, tasks: Sequence[str], runs: Sequence[str],
          call_cost, call_out, resolved, candidate, usable, minutes,
          grid: Optional[Sequence[int]] = None) -> Pool:
    """Assemble a pool from per-call costs and output tokens, ``[task][draw]`` nested sequences,
    with ``None`` where a run has no record of a task."""
    points = tuple(grid) if grid is not None else decision_points(cap)
    g = np.asarray(points)
    n_t, n_d, n_g = len(tasks), len(runs), len(points)
    calls = np.zeros((n_t, n_d), int)
    cost_end = np.zeros((n_t, n_d))
    out_end = np.zeros((n_t, n_d))
    cost_grid = np.zeros((n_t, n_d, n_g))
    out_grid = np.zeros((n_t, n_d, n_g))
    out_recent = np.zeros((n_t, n_d, n_g))
    cost_rate = np.zeros((n_t, n_d, n_g))
    alive = np.zeros((n_t, n_d, n_g), bool)
    for i in range(n_t):
        for d in range(n_d):
            per_call = call_cost[i][d]
            if per_call is None:
                continue
            cc = np.concatenate(([0.0], np.cumsum(np.asarray(per_call, float))))
            oo = np.concatenate(([0.0], np.cumsum(np.asarray(call_out[i][d], float))))
            t_end = len(per_call)
            calls[i, d] = t_end
            cost_end[i, d], out_end[i, d] = cc[t_end], oo[t_end]
            reached = np.minimum(g, t_end)
            back = np.maximum(reached - WINDOW, 0)
            cost_grid[i, d] = cc[reached]
            out_grid[i, d] = oo[reached]
            span = np.maximum(reached - back, 1)
            cost_rate[i, d] = (cc[reached] - cc[back]) / span     # spend per call, not per window
            out_recent[i, d] = oo[reached] - oo[back]
            alive[i, d] = g < t_end
    return Pool(config=config, cap=cap, tasks=tuple(tasks), runs=tuple(runs), grid=points,
                usable=np.asarray(usable, bool), calls=calls,
                resolved=np.asarray(resolved, bool), candidate=np.asarray(candidate, bool),
                cost_end=cost_end, out_end=out_end, cost_grid=cost_grid, out_grid=out_grid,
                out_recent=out_recent, cost_rate=cost_rate, alive=alive,
                minutes=np.asarray(minutes, float))


def load(folder: str, key: Optional[str] = None, schedules: Optional[dict] = None,
         retain_refusals: bool = True, no_verdict_unresolved: bool = False,
         drop_reruns: bool = False, grid: Optional[Sequence[int]] = None,
         cap: Optional[int] = None,
         annotation_minutes: Optional[Dict[str, float]] = None) -> Pool:
    """Read one configuration's derived tables and price every call.

    ``key`` selects the price schedule and defaults to the folder's name, which is the archive's.
    The three flags are the prespecified sensitivities of PLAN.md Section 10: excluding provider
    refusals, counting an evaluation that returned no verdict as unresolved rather than dropping
    it, and dropping executions the harness re-ran after a crash.
    """
    folder = folder.rstrip("/")
    key = key or os.path.basename(folder)
    ex_file = _one(folder, "executions_*.csv")
    px_file = _one(folder, "prefix_*.csv")
    with open(ex_file, newline="") as fh:
        execs = list(csv.DictReader(fh))
    tasks = tuple(sorted({r["instance_id"] for r in execs}))
    runs = tuple(sorted({r["run"] for r in execs}))
    t_at = {t: i for i, t in enumerate(tasks)}
    r_at = {r: i for i, r in enumerate(runs)}
    n_t, n_d = len(tasks), len(runs)

    usable = np.zeros((n_t, n_d), bool)
    resolved = np.zeros((n_t, n_d), bool)
    candidate = np.zeros((n_t, n_d), bool)
    logged_calls = np.zeros((n_t, n_d), int)
    minutes = np.full(n_t, np.nan)
    caps = set()
    table = MINUTES if annotation_minutes is None else annotation_minutes
    for r in execs:
        i, d = t_at[r["instance_id"]], r_at[r["run"]]
        state, res, _limit, use = reclassify(r, retain_refusals=retain_refusals)
        # the sensitivity is a change to the verdict, not to the exclusion rules: an attempt that
        # was excluded because its provider failed, or refused and refusals are excluded, stays out
        if (no_verdict_unresolved and r["verdict"] == "no_verdict"
                and state not in ("infrastructure", "provider_refusal")):
            use, res = True, False
        if drop_reruns and int(r.get("prior_try_logs") or 0) > 0:
            use = False
        usable[i, d], resolved[i, d] = use, bool(res)
        candidate[i, d] = r["verdict"] != "empty_patch"
        logged_calls[i, d] = _int(r["n_calls"])
        minutes[i] = _minutes(r["difficulty"], minutes[i], r["instance_id"], table)
        if r.get("max_iterations"):
            caps.add(int(r["max_iterations"]))
    if np.isnan(minutes).any():
        raise ValueError(f"{key}: no difficulty annotation for "
                         f"{[tasks[i] for i in np.flatnonzero(np.isnan(minutes))][:3]}")
    if cap is None:
        if len(caps) != 1:
            raise ValueError(f"{key}: expected one iteration cap, found {sorted(caps)}; "
                             "pass cap= to state it")
        cap = caps.pop()

    call_cost: List[List[Optional[list]]] = [[None] * n_d for _ in range(n_t)]
    call_out: List[List[Optional[list]]] = [[None] * n_d for _ in range(n_t)]
    with open(px_file, newline="") as fh:
        for row in csv.DictReader(fh):
            i, d = t_at[row["instance_id"]], r_at[row["run"]]
            if call_cost[i][d] is None:
                call_cost[i][d], call_out[i][d] = [], []
            p, c = _int(row["prompt_tokens"]), _int(row["completion_tokens"])
            cr, cw = _int(row["cache_read_tokens"]), _int(row["cache_write_tokens"])
            call_cost[i][d].append(pricing.price_call(key, p, c, cr, cw, schedules))
            call_out[i][d].append(c)

    # every usable attempt must be present call for call in the prefix table, or it would enter
    # the pool as a free attempt that cost nothing and stopped immediately
    priced = np.array([[len(call_cost[i][d] or ()) for d in range(n_d)] for i in range(n_t)])
    wrong = np.flatnonzero((priced != logged_calls) & usable)
    if wrong.size:
        i, d = divmod(int(wrong[0]), n_d)
        raise ValueError(f"{key}: {wrong.size} usable attempts are not priced call for call, "
                         f"first {tasks[i]} run {runs[d]}: {priced[i, d]} of {logged_calls[i, d]}")
    return build(key, cap, tasks, runs, call_cost, call_out,
                 resolved, candidate, usable, minutes, grid=grid)


def _minutes(annotation: str, seen: float, task: str,
             table: Optional[Dict[str, float]] = None) -> float:
    """The outside option's engineer minutes, from the benchmark's own difficulty bucket. Every
    run of a task carries the same annotation, and a disagreement is a join error."""
    if annotation in (None, ""):
        return seen
    try:
        value = (MINUTES if table is None else table)[annotation]
    except KeyError:
        raise ValueError(f"unknown difficulty annotation {annotation!r} on {task}") from None
    if not np.isnan(seen) and seen != value:
        raise ValueError(f"{task} is annotated both {seen} and {value} minutes")
    return value


def _one(folder: str, pattern: str) -> str:
    found = glob.glob(os.path.join(folder, pattern))
    if len(found) != 1:
        raise FileNotFoundError(f"expected one {pattern} in {folder}, found {len(found)}")
    return found[0]


def _int(v) -> int:
    return int(v) if v not in (None, "") else 0


# ----------------------------------------------------------------------------- one slot

def slot_arrays(pool: Pool, cutoff: Optional[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """What one attempt costs, resolves and verifies in a slot with this cutoff, [task, draw].

    An attempt that is still running at the cutoff is stopped there: it costs what it had spent,
    resolves nothing, and is discarded without verification. An attempt that had already reached
    its own stop is unaffected by the cutoff.
    """
    if cutoff is None:
        return pool.cost_end, pool.resolved, pool.candidate
    j = pool.point(cutoff)
    reached_own_stop = ~pool.alive[:, :, j]
    return (pool.cost_grid[:, :, j],
            pool.resolved & reached_own_stop,
            pool.candidate & reached_own_stop)


# ----------------------------------------------------------------------------- policy value

@dataclass(frozen=True)
class Result:
    policy: Policy
    tasks: Tuple[str, ...]
    per_task: np.ndarray        # [task] dollars; nan where the task cannot fill the policy
    used: np.ndarray            # [task] bool
    orderings: np.ndarray       # [task] how many orderings the average ran over

    @property
    def value(self) -> float:
        """Expected cost per incoming task, over the tasks that can fill the policy."""
        return float(self.per_task[self.used].mean()) if self.used.any() else float("nan")

    @property
    def n_tasks(self) -> int:
        return int(self.used.sum())

    def __repr__(self) -> str:
        return (f"Result({self.policy.label or self.policy.cutoffs}, "
                f"${self.value:,.4f} per task over {self.n_tasks} tasks)")


def outside_option(pool: Pool, rate_per_hour: float) -> np.ndarray:
    """*H_i*: the annotated engineer time at a stated fully loaded rate."""
    return pool.minutes / 60.0 * rate_per_hour


def verification(outside: np.ndarray, fraction: float = 0.0, flat: float = 0.0) -> np.ndarray:
    """*v*: near zero with an automated verifier, a fraction of the outside option with a human
    one, which makes review cost more on the tasks whose escalation costs more. Verification is
    charged only on attempts that end with something to check."""
    return fraction * outside + flat


def median_attempt_cost(pool: Pool, mask: Optional[np.ndarray] = None) -> float:
    """The median cost of a usable attempt run to its own stop, over the tasks scored.

    This is the unit of the sweep's second axis. It is taken over the same tasks the policies are
    scored on, so that a break-even expressed in multiples of it refers to the attempts that
    produced the break-even.
    """
    keep = pool.usable if mask is None else pool.usable & np.asarray(mask, bool)[:, None]
    return float(np.median(pool.cost_end[keep]))


def mean_outside_hours(pool: Pool, mask: Optional[np.ndarray] = None) -> float:
    """The mean annotated engineer time, in hours, over the tasks scored."""
    minutes = pool.minutes if mask is None else pool.minutes[np.asarray(mask, bool)]
    return float(minutes.mean()) / 60.0


def rate_for_multiple(pool: Pool, multiple: float, mask: Optional[np.ndarray] = None) -> float:
    """The rate at which the mean outside option is ``multiple`` times the median attempt cost.

    The sweep's second axis (PLAN.md Section 7) scales the outside option in units of what an
    attempt costs, so that break-evens are comparable across configurations whose attempts differ
    manyfold in cost. It is a reparametrization of the rate and not a second regime: the shape of
    the outside option across tasks, which the difficulty annotation sets, is unchanged, and only
    its level moves.
    """
    return multiple * median_attempt_cost(pool, mask) / mean_outside_hours(pool, mask)


def multiple_for_rate(pool: Pool, rate: float, mask: Optional[np.ndarray] = None) -> float:
    """The inverse: what a rate in dollars an hour is, in multiples of the median attempt cost."""
    return rate * mean_outside_hours(pool, mask) / median_attempt_cost(pool, mask)


def restrict(pool: Pool, keep: np.ndarray) -> Pool:
    """The pool on a subset of its tasks, in its own order."""
    keep = np.asarray(keep)
    idx = np.flatnonzero(keep) if keep.dtype == bool else keep.astype(int)
    return dataclasses.replace(
        pool, tasks=tuple(pool.tasks[i] for i in idx),
        usable=pool.usable[idx], calls=pool.calls[idx], resolved=pool.resolved[idx],
        candidate=pool.candidate[idx], cost_end=pool.cost_end[idx], out_end=pool.out_end[idx],
        cost_grid=pool.cost_grid[idx], out_grid=pool.out_grid[idx],
        out_recent=pool.out_recent[idx], cost_rate=pool.cost_rate[idx], alive=pool.alive[idx],
        minutes=pool.minutes[idx])


def truncate(pool: Pool, horizon: int = 100) -> Pool:
    """The common-horizon sensitivity (PLAN.md Section 10): every configuration at cutoffs up to
    ``horizon`` calls, and any attempt still running there stopped and scored as a failure.

    The attempt then costs what it had spent by the horizon, resolves nothing and produces nothing
    to verify. An attempt that reached its own stop at or before the horizon is unchanged. The
    decision points are those below the horizon, and the configuration's own stop becomes the
    horizon, so a policy with no cutoff runs every attempt at most that far.
    """
    if horizon >= pool.cap:
        return pool
    if horizon not in pool.grid:
        raise ValueError(f"the horizon {horizon} is not a decision point of {pool.config}")
    j = pool.grid.index(horizon)
    running = pool.alive[:, :, j]
    keep = [i for i, t in enumerate(pool.grid) if t < horizon]
    return dataclasses.replace(
        pool, cap=horizon, grid=tuple(pool.grid[i] for i in keep),
        calls=np.minimum(pool.calls, horizon),
        resolved=pool.resolved & ~running, candidate=pool.candidate & ~running,
        cost_end=np.where(running, pool.cost_grid[:, :, j], pool.cost_end),
        out_end=np.where(running, pool.out_grid[:, :, j], pool.out_end),
        cost_grid=pool.cost_grid[:, :, keep], out_grid=pool.out_grid[:, :, keep],
        out_recent=pool.out_recent[:, :, keep], cost_rate=pool.cost_rate[:, :, keep],
        alive=pool.alive[:, :, keep])


def resample(pool: Pool, idx: np.ndarray, draws: np.ndarray) -> Pool:
    """The two-stage bootstrap's resample: tasks ``idx``, and within each the draws ``draws``,
    [task, draw] indices into that task's own draws, drawn with replacement. A task drawn twice
    keeps its name, so the fold split can keep its copies together."""
    idx = np.asarray(idx, int)
    draws = np.asarray(draws, int)
    rows = idx[:, None]

    def pick(x):
        return x[rows, draws]

    return dataclasses.replace(
        pool, tasks=tuple(pool.tasks[i] for i in idx), usable=pick(pool.usable),
        calls=pick(pool.calls), resolved=pick(pool.resolved), candidate=pick(pool.candidate),
        cost_end=pick(pool.cost_end), out_end=pick(pool.out_end), cost_grid=pick(pool.cost_grid),
        out_grid=pick(pool.out_grid), out_recent=pick(pool.out_recent),
        cost_rate=pick(pool.cost_rate), alive=pick(pool.alive), minutes=pool.minutes[idx])


def reindex(pool: Pool, tasks: Sequence[str]) -> Pool:
    """The pool on this list of tasks, in this order.

    A task the configuration never ran enters with no usable draws, so it fills no policy and
    contributes no fitting rows: nothing is imputed into a configuration that never ran a task.
    Its other fields are the gathered placeholder and are not read anywhere ``usable`` is false.
    """
    at = {t: i for i, t in enumerate(pool.tasks)}
    idx = np.array([at.get(t, 0) for t in tasks], int)
    have = np.array([t in at for t in tasks], bool)
    got = restrict(pool, idx)
    return dataclasses.replace(got, tasks=tuple(tasks), usable=got.usable & have[:, None])


def align(pools: Dict[str, Pool]) -> Dict[str, Pool]:
    """Every pool on the tasks all of them have, in one order.

    A cascade reads one task's draws from several configurations, so the pools must be indexed
    alike. Dropping to the common tasks is the only alignment a cascade uses; the transfer design,
    which needs the other configurations indexed by the target's tasks and not by the intersection,
    uses ``reindex`` instead.
    """
    common = set.intersection(*(set(p.tasks) for p in pools.values())) if pools else set()
    order = sorted(common)
    return {c: reindex(p, order) for c, p in pools.items()}


def full_draw_tasks(pools: Dict[str, Pool], configs: Optional[Sequence[str]] = None,
                    draws: int = 4) -> np.ndarray:
    """The tasks with at least this many usable draws in every configuration named. Comparisons
    across attempt budgets rest on this subset (PLAN.md Section 10); the all-tasks version, which
    is what ``value`` returns without a mask, is the sensitivity."""
    configs = tuple(configs or pools)
    keep = np.ones(pools[configs[0]].n_tasks, bool)
    for c in configs:
        keep &= pools[c].usable.sum(axis=1) >= draws
    return keep


def value(pools: Dict[str, Pool], policy: Policy, outside: np.ndarray, verify: np.ndarray,
          phi: float = 0.0, mask: Optional[np.ndarray] = None,
          arrays: Optional[Sequence[Tuple[np.ndarray, np.ndarray, np.ndarray]]] = None) -> Result:
    """The policy's expected cost per task, by enumeration over orderings of the logged draws.

    ``phi`` is the false-accept sensitivity: a fraction of test-passing attempts are not target
    resolutions, so the outside option is paid later, which adds phi times it to the cost of an
    attempt the policy accepts. ``mask`` restricts the tasks scored, for comparisons that must run
    on the same tasks at every attempt budget.

    ``arrays`` supplies each slot's (cost, resolves, verifies) directly, which is how a rule that
    stops attempt by attempt rather than at a fixed cutoff is replayed: the enumeration over
    orderings is the same whatever decided the stop.
    """
    tasks = _aligned(pools, policy.configs)
    n_t = len(tasks)
    outside = np.asarray(outside, float)
    verify = np.asarray(verify, float)
    if outside.shape != (n_t,) or verify.shape != (n_t,):
        raise ValueError("the outside option and verification cost are one value per task")

    slots = policy.slots
    if arrays is None:
        arrays = [slot_arrays(pools[s.config], s.cutoff) for s in slots]
    elif len(arrays) != len(slots):
        raise ValueError("one set of arrays per slot")
    orderings_per_config = {}
    for config in policy.configs:
        width = pools[config].n_draws
        filled = sum(1 for s in slots if s.config == config)
        if filled > width:
            raise ValueError(f"{policy.label or 'policy'} asks {config} for {filled} of {width} draws")
        orderings_per_config[config] = list(itertools.permutations(range(width), filled))

    # the orderings are enumerated as an array rather than a loop: every combination of draws is
    # a row, and the replay runs over slots with the combinations carried along, which is the same
    # arithmetic an order of magnitude faster, and the searches ahead run it many thousands of times
    combos = []
    for combo in itertools.product(*(orderings_per_config[c] for c in policy.configs)):
        chosen = {c: list(draws) for c, draws in zip(policy.configs, combo)}
        cursor = {c: 0 for c in policy.configs}
        row = []
        for s in slots:
            row.append(chosen[s.config][cursor[s.config]])
            cursor[s.config] += 1
        combos.append(row)
    draws = np.asarray(combos, int)                       # [combination, slot]

    valid = np.ones((len(combos), n_t), bool)
    for j, s in enumerate(slots):
        valid &= pools[s.config].usable[:, draws[:, j]].T
    running = np.ones((len(combos), n_t), bool)
    cost = np.zeros((len(combos), n_t))
    for j, (spend, resolves, checks) in enumerate(arrays):
        d = draws[:, j]
        cost += running * (spend[:, d].T + verify * checks[:, d].T
                           + phi * outside * resolves[:, d].T)
        running &= ~resolves[:, d].T
    cost += running * outside

    counted = valid.sum(axis=0)
    total = np.where(valid, cost, 0.0).sum(axis=0)
    used = counted > 0
    if mask is not None:
        used &= np.asarray(mask, bool)
    per_task = np.where(counted > 0, total / np.maximum(counted, 1), np.nan)
    return Result(policy=policy, tasks=tasks, per_task=per_task, used=used, orderings=counted)


def stopped_slot(pool: Pool, stop: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A slot whose stop is decided per attempt: ``stop`` holds the index of the decision point at
    which the attempt is stopped, or -1 for an attempt the rule never stopped, which then runs to
    its own end. An attempt stopped while it was still running is discarded unverified."""
    stop = np.asarray(stop, int)
    j = np.clip(stop, 0, max(len(pool.grid) - 1, 0))
    rows, cols = np.indices(stop.shape)
    still_running = (stop >= 0) & pool.alive[rows, cols, j]
    cost = np.where(still_running, pool.cost_grid[rows, cols, j], pool.cost_end)
    return (cost,
            pool.resolved & ~still_running,
            pool.candidate & ~still_running)


def evaluate(pools: Dict[str, Pool], policy: Policy, rate_per_hour: float,
             verify_fraction: float = 0.0, verify_flat: float = 0.0, phi: float = 0.0,
             mask: Optional[np.ndarray] = None) -> Result:
    """``value`` with the outside option and verification cost built from a rate and a regime."""
    first = pools[policy.configs[0]]
    h = outside_option(first, rate_per_hour)
    return value(pools, policy, h, verification(h, verify_fraction, verify_flat), phi, mask)


def _aligned(pools: Dict[str, Pool], configs: Sequence[str]) -> Tuple[str, ...]:
    """Cascades read one task's draws from several configurations, so the pools must be indexed
    by the same tasks in the same order."""
    missing = [c for c in configs if c not in pools]
    if missing:
        raise KeyError(f"no pool for {missing}")
    tasks = pools[configs[0]].tasks
    for c in configs[1:]:
        if pools[c].tasks != tasks:
            raise ValueError(f"{c} and {configs[0]} are indexed by different tasks")
    return tasks


def _main(argv=None):
    """``python -m restart.evaluate --check data/derived`` loads every configuration's tables and
    prices them, and reports what the pools hold. It computes nothing indexed by a cutoff, an
    attempt budget, a rate or a verification cost."""
    import argparse
    ap = argparse.ArgumentParser(description="Load and price each configuration's attempt pool.")
    ap.add_argument("--check", metavar="DIR", required=True,
                    help="folder of per-archive extraction folders")
    a = ap.parse_args(argv)
    for folder in sorted(glob.glob(os.path.join(a.check, "*/"))):
        name = os.path.basename(folder.rstrip("/"))
        if name not in pricing.SCHEDULES or not glob.glob(os.path.join(folder, "prefix_*.csv")):
            continue
        pool = load(folder)
        spend = pool.cost_end[pool.usable]
        print(f"{name}: {pool.n_tasks} tasks x {pool.n_draws} draws, {int(pool.usable.sum())} usable"
              f" | cap {pool.cap}, {len(pool.grid)} decision points"
              f" | attempt ${spend.mean():.4f} mean, ${np.median(spend):.4f} median,"
              f" ${spend.sum():,.2f} total"
              f" | outside option {pool.minutes.mean():.1f} min mean")


if __name__ == "__main__":
    _main()
