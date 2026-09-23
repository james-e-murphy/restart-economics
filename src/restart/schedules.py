"""Step iii-b: *K* attempts under a schedule of cutoffs, chosen on the training folds.

A schedule is one cutoff per attempt, (*t₁*, …, *t_K*), each of them a decision point or the
configuration's own stop. The class contains the constant cutoffs of step iii, so the schedule is
searched from the best constant one and only ever moved when the move pays on the same training
tasks: on the folds that choose it, step iii-b is therefore never worse than step iii, and the
whole of its margin is the value of letting the cap vary by attempt. The search is coordinate
ascent, one attempt at a time until a full pass changes nothing. It is not guaranteed to find the
best schedule in the class; where it stops short it understates step iii-b, which is conservative
for the primary transfer, whose baseline this is.

The search is exact arithmetic on the replayed pool, not an approximation of it. Sweeping one
attempt's cutoff would otherwise mean replaying the whole schedule once per candidate, so the
replay is factored instead: with the other attempts held fixed, what the policy costs is the spend
before this attempt, plus what this attempt costs, plus what the rest costs weighted by the chance
this attempt leaves the task unresolved. Only the last two terms move with the candidate, and both
are linear in the candidate's own arrays, so every candidate is scored in one product. The
factorization is checked against the evaluator itself in the tests.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

import numpy as np

from . import evaluate as ev
from . import inference as inf
from . import policies as po

PASSES = 6          # a pass that changes nothing ends the search; this only bounds it


@dataclass(frozen=True)
class Table:
    """Every candidate cutoff's slot arrays, stacked: [candidate, task, draw].

    The candidates are the configuration's decision points and its own stop, written ``None``.
    Nothing here depends on a rate, a regime or an attempt budget, so one table serves the whole
    sweep for a configuration.
    """
    cutoffs: Tuple[Optional[int], ...]
    cost: np.ndarray
    resolves: np.ndarray
    checks: np.ndarray

    def arrays(self, index: int):
        return self.cost[index], self.resolves[index], self.checks[index]


def table(pool: ev.Pool, points: Optional[Sequence[int]] = None) -> Table:
    """The slot arrays of every candidate cutoff for one configuration."""
    cutoffs = tuple(points if points is not None else pool.grid) + (None,)
    got = [ev.slot_arrays(pool, t) for t in cutoffs]
    return Table(cutoffs=cutoffs,
                 cost=np.stack([g[0] for g in got]),
                 resolves=np.stack([g[1] for g in got]),
                 checks=np.stack([g[2] for g in got]))


def charges(tab: Table, outside: np.ndarray, verify: np.ndarray, phi: float = 0.0):
    """What an attempt run in a slot charges the policy, and what it leaves for the next slot.

    ``charge`` is the attempt's own spend plus verification where it produced something to check
    plus, under the false-accept sensitivity, the share of the outside option an accepted attempt
    does not in fact avoid. ``survive`` is one where the attempt does not resolve, which is the
    weight everything after it carries.
    """
    charge = (tab.cost + verify[None, :, None] * tab.checks
              + phi * outside[None, :, None] * tab.resolves)
    return charge, 1.0 - tab.resolves


def _slot_views(x: np.ndarray, sched: Sequence[int], perms: np.ndarray):
    """[slot][ordering, task] from [candidate, task, draw]: what each slot's attempt does under
    each ordering of the draws."""
    return [x[c][:, perms[:, j]].T for j, c in enumerate(sched)]


def search(pool: ev.Pool, tab: Table, charge: np.ndarray, survive: np.ndarray,
           outside: np.ndarray, train: np.ndarray, k: int,
           start: Optional[Sequence[int]] = None, passes: int = PASSES):
    """Coordinate ascent over the schedule, scored on the training tasks.

    Returns the candidate index of each attempt and the mean cost per training task, which is the
    same number the evaluator returns for the policy those indices name.
    """
    idx = np.flatnonzero(np.asarray(train, bool))
    if idx.size == 0:
        raise ValueError("the schedule search needs training tasks")
    u_all, w_all = charge[:, idx, :], survive[:, idx, :]
    usable, h = pool.usable[idx], np.asarray(outside, float)[idx]
    n_c, n_t, n_d = u_all.shape
    if k > n_d:
        raise ValueError(f"{k} attempts from {n_d} draws")

    perms = np.asarray(list(itertools.permutations(range(n_d), k)), int)   # [ordering, slot]
    valid = usable[:, perms].all(axis=2).T.astype(float)                  # [ordering, task]
    n = valid.sum(axis=0)
    if not np.any(n > 0):
        raise ValueError("no training task has enough usable draws to fill the schedule")
    weight = np.where(n > 0, 1.0 / np.maximum(n, 1), 0.0) / max(int((n > 0).sum()), 1)

    sched = list(start if start is not None else [n_c - 1] * k)
    if len(sched) != k:
        raise ValueError("the starting schedule has one cutoff per attempt")

    def prepare(current):
        """Each slot's arrays under the current schedule, and what follows each slot per unit of
        unresolved task left to it. The suffix of a slot depends only on the slots after it, so a
        forward sweep may change a slot without invalidating the suffixes it has yet to use."""
        u = _slot_views(u_all, current, perms)
        w = _slot_views(w_all, current, perms)
        suffix, tail = [None] * k, np.broadcast_to(h, u[0].shape).copy()
        for j in range(k - 1, -1, -1):
            suffix[j] = tail
            if j:
                tail = u[j] + w[j] * tail
        return u, w, suffix

    def candidates(running, suffix_j, j):
        """Every candidate's value in slot *j*, the rest of the schedule held fixed. At the first
        slot nothing has been spent yet, so this is the whole policy's value per task."""
        g = np.zeros((n_d, n_t))
        f = np.zeros((n_d, n_t))
        for d in range(n_d):
            here = perms[:, j] == d
            if here.any():
                g[d] = (running[here] * weight).sum(axis=0)
                f[d] = (running[here] * suffix_j[here] * weight).sum(axis=0)
        return (u_all * g.T).sum(axis=(1, 2)) + (w_all * f.T).sum(axis=(1, 2))

    for _ in range(max(passes, 1)):
        u, w, suffix = prepare(sched)
        moved, running = False, valid
        for j in range(k):
            value = candidates(running, suffix[j], j)
            pick = int(np.argmin(value))
            if value[pick] < value[sched[j]] - 1e-12:
                sched[j], moved = pick, True
                u[j] = u_all[pick][:, perms[:, j]].T
                w[j] = w_all[pick][:, perms[:, j]].T
            running = running * w[j]
        if not moved:
            break
    _, _, suffix = prepare(sched)
    best = float(candidates(valid, suffix[0], 0)[sched[0]])
    return tuple(sched), best


def label(config: str, cutoffs: Sequence[Optional[int]]) -> str:
    written = ",".join("none" if t is None else str(t) for t in cutoffs)
    return f"iii-b: {len(tuple(cutoffs))} attempts on schedule {written}"


def constant_start(constants: inf.Family, tab: Table,
                   ks: Sequence[int]) -> Callable[[np.ndarray], dict]:
    """Start the search where step iii ended: the best constant cutoff on the same training tasks.

    ``constants`` is step iii's family, built by ``policies.constant_family`` in its own order,
    every cutoff on the grid and then the configuration's own stop, for each *K* in turn. Because
    the search only moves a cutoff when the move pays on these same tasks, the schedule a fold
    chooses is never worse there than the constant cutoff that fold would have chosen.
    """
    size = len(tab.cutoffs)
    ks = tuple(ks)
    if constants.values.shape[0] != size * len(ks):
        raise ValueError("the constant family and the candidate table are on different grids")

    def start(train: np.ndarray) -> dict:
        m = inf.means(constants, train)
        return {k: [int(np.argmin(m[i * size:(i + 1) * size]))] * k for i, k in enumerate(ks)}
    return start


def family(pool: ev.Pool, outside: np.ndarray, verify: np.ndarray, phi: float = 0.0,
           ks: Sequence[int] = tuple(range(1, po.MAX_ATTEMPTS + 1)),
           tab: Optional[Table] = None, passes: int = PASSES,
           start: Optional[Callable[[np.ndarray], dict]] = None,
           mask: Optional[np.ndarray] = None) -> inf.Family:
    """Step iii-b as a family to cross-fit: one searched schedule per attempt budget, the search
    redone on each training set. ``start`` supplies the starting schedules, normally step iii's
    best constant cutoff on the same training tasks; without it the search starts from no cutoff.
    """
    ks = tuple(ks)
    tab = tab if tab is not None else table(pool)
    outside = np.asarray(outside, float)
    verify = np.asarray(verify, float)
    charge, survive = charges(tab, outside, verify, phi)

    def fit_on(train: np.ndarray):
        starts = start(train) if start is not None else {}
        rows, used, labels, shares = [], [], [], []
        for k in ks:
            sched, _ = search(pool, tab, charge, survive, outside, train, k,
                              starts.get(k), passes)
            cutoffs = [tab.cutoffs[c] for c in sched]
            got = ev.value({pool.config: pool}, po.schedule(pool.config, cutoffs),
                           outside, verify, phi, mask=mask,
                           arrays=[tab.arrays(c) for c in sched])
            rows.append(got.per_task)
            used.append(got.used)
            labels.append(label(pool.config, cutoffs))
            shares.append(got.resolved)
        return np.vstack(rows), np.vstack(used), tuple(labels), np.vstack(shares)

    return inf.Family(values=np.zeros((len(ks), pool.n_tasks)),
                      used=np.ones((len(ks), pool.n_tasks), bool),
                      labels=tuple(f"iii-b: {k} attempts on a schedule" for k in ks),
                      fit=fit_on)
