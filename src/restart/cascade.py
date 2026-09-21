"""Step v: a schedule over (configuration, cutoff) pairs, chosen on the training folds.

After a failed attempt an operator chooses what to try next, and trying the same configuration
again is one of the choices, so retry and reroute are one decision (PLAN.md Section 6). A cascade
is therefore a schedule whose every attempt also names a configuration, and step iii-b is the case
where every attempt names the same one.

    best single   for each training set, every configuration's searched schedule at every K,
                  and the cheapest of them: the best one configuration an operator could have
                  picked from the same data, which is what switching has to beat
    cascade       coordinate ascent over (configuration, cutoff) pairs, attempt by attempt, from
                  that best single-configuration schedule; a move is taken only when it pays on
                  the same training tasks, so on them the cascade is never worse than it

Replay is the evaluator's: for a task, the average over every combination of draws the policy can
use, the orderings of each configuration's own draws taken together, which requires exchangeable
draws within a configuration and independent draws between them (Section 4). The search scores a
slot's candidates by the same factorization ``restart.schedules`` uses, generalized to draws from
several configurations; the tests hold it against the evaluator replaying each candidate in full.

Comparisons rest on the tasks with four usable draws in every configuration (Section 10), so the
cascade, the best single configuration and each configuration's own schedule are scored on the
same tasks. The diagnostics the plan puts beside the cascade are here too: the seven-by-seven
correlation of outcomes across configurations, the algorithm-portfolio predictor of whether a
cascade pays, and in the appendix each configuration's leave-one-out essentialness to the best
cascade.

    python -m restart.cascade --derived data/derived
"""
from __future__ import annotations

import csv
import itertools
import os
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from . import evaluate as ev
from . import inference as inf
from . import ladder as ld
from . import policies as po
from . import schedules as sc

PASSES = sc.PASSES
MEMO = 5 * (ld.FITTED_REPLICATES + 1) + 8


# ----------------------------------------------------------------------------- one rate, one regime

@dataclass
class Bank:
    """Every configuration's candidate cutoffs at one rate and regime, on common tasks."""
    names: Tuple[str, ...]
    pools: Dict[str, ev.Pool]
    tabs: Dict[str, sc.Table]
    charge: Dict[str, np.ndarray]           # [candidate, task, draw]
    survive: Dict[str, np.ndarray]
    constants: Dict[str, inf.Family]        # step iii's family, per configuration
    outside: np.ndarray
    verify: np.ndarray
    phi: float
    mask: np.ndarray

    @property
    def n_tasks(self) -> int:
        return len(self.outside)


def bank(pools: Dict[str, ev.Pool], rate: float, fraction: float, phi: float = 0.0,
         mask: Optional[np.ndarray] = None,
         tabs: Optional[Dict[str, sc.Table]] = None) -> Bank:
    names = tuple(pools)
    first = pools[names[0]]
    for c in names[1:]:
        if pools[c].tasks != first.tasks:
            raise ValueError("a cascade needs its pools aligned on the same tasks; use ev.align")
        if not np.array_equal(pools[c].minutes, first.minutes):
            raise ValueError(f"{c} and {names[0]} annotate the same tasks differently")
    outside = ev.outside_option(first, rate)
    verify = ev.verification(outside, fraction)
    mask = ev.full_draw_tasks(pools, names) if mask is None else np.asarray(mask, bool)
    tabs = tabs or {c: sc.table(pools[c]) for c in names}
    charge, survive, constants = {}, {}, {}
    ks = tuple(range(1, po.MAX_ATTEMPTS + 1))
    for c in names:
        charge[c], survive[c] = sc.charges(tabs[c], outside, verify, phi)
        constants[c] = ld._family(pools[c], po.constant_family(c, pools[c].grid, ks),
                                  outside, verify, phi, mask)
    return Bank(names, pools, tabs, charge, survive, constants, outside, verify, phi, mask)


# ----------------------------------------------------------------------------- the search

def _combos(assignment: Sequence[str], width: int) -> np.ndarray:
    """[combination, slot]: the draw each slot takes, over every combination the policy can use.
    Each configuration's draws are taken in every ordering, without replacement, and the
    configurations' orderings are crossed, which is the evaluator's enumeration."""
    order = tuple(dict.fromkeys(assignment))
    counts = {c: sum(1 for a in assignment if a == c) for c in order}
    rows = []
    for combo in itertools.product(*(itertools.permutations(range(width), counts[c])
                                     for c in order)):
        chosen = {c: list(d) for c, d in zip(order, combo)}
        cursor = dict.fromkeys(order, 0)
        row = []
        for a in assignment:
            row.append(chosen[a][cursor[a]])
            cursor[a] += 1
        rows.append(row)
    return np.asarray(rows, int)


def search(b: Bank, train: np.ndarray, k: int, start: Sequence[Tuple[str, int]],
           names: Optional[Sequence[str]] = None, passes: int = PASSES):
    """Coordinate ascent over (configuration, cutoff) pairs, scored on the training tasks.

    ``start`` is one (configuration, candidate index) per attempt. ``names`` restricts the
    configurations a slot may move to, which is how leave-one-out is run. Returns the schedule and
    its mean cost per training task, the number the evaluator returns for the same policy.
    """
    names = tuple(names or b.names)
    idx = np.flatnonzero(np.asarray(train, bool) & b.mask)
    if idx.size == 0:
        raise ValueError("the cascade search needs training tasks")
    width = b.pools[names[0]].n_draws
    u = {c: b.charge[c][:, idx, :] for c in b.names}
    w = {c: b.survive[c][:, idx, :] for c in b.names}
    ok = {c: b.pools[c].usable[idx] for c in b.names}          # [task, draw]
    h = b.outside[idx]
    n_t = idx.size
    combos_at: Dict[Tuple[str, ...], np.ndarray] = {}

    def combos(assignment):
        key = tuple(assignment)
        if key not in combos_at:
            combos_at[key] = _combos(key, width)
        return combos_at[key]

    def slot_values(sched, j, config):
        """The whole policy's mean value for every cutoff of ``config`` in slot *j*.

        A task is scored over the combinations of its draws that are all usable, and only if it
        has one, which is the evaluator's rule; on tasks with every draw usable in every
        configuration, the basis the comparisons rest on, every combination qualifies."""
        assignment = [c for c, _ in sched]
        assignment[j] = config
        draws = combos(assignment)                              # [combination, slot]
        m = len(draws)
        valid = np.ones((m, n_t))
        for l, c in enumerate(assignment):
            valid = valid * ok[c][:, draws[:, l]].T
        count = valid.sum(axis=0)
        scored = count > 0
        if not scored.any():
            return np.full(u[config].shape[0], np.inf)
        per = np.where(scored, 1.0 / np.maximum(count, 1), 0.0)   # per-task mean over combinations
        views_u = [None] * k
        views_w = [None] * k
        for l, (c, t) in enumerate(sched):
            if l != j:
                views_u[l] = u[c][t][:, draws[:, l]].T          # [combination, task]
                views_w[l] = w[c][t][:, draws[:, l]].T
        running = valid.copy()
        prefix = np.zeros((m, n_t))
        for l in range(j):
            prefix += running * views_u[l]
            running = running * views_w[l]
        tail = np.broadcast_to(h, (m, n_t)).copy()
        for l in range(k - 1, j, -1):
            tail = views_u[l] + views_w[l] * tail
        g = np.zeros((width, n_t))
        f = np.zeros((width, n_t))
        for d in range(width):
            here = draws[:, j] == d
            if here.any():
                g[d] = running[here].sum(axis=0)
                f[d] = (running[here] * tail[here]).sum(axis=0)
        base = prefix.sum(axis=0) * per                          # the same for every cutoff
        per_task = ((u[config] * (g * per).T).sum(axis=2) + (w[config] * (f * per).T).sum(axis=2)
                    + base)
        return per_task[:, scored].mean(axis=1)

    sched = [tuple(s) for s in start]
    if len(sched) != k:
        raise ValueError("the starting cascade has one (configuration, cutoff) per attempt")
    for _ in range(max(passes, 1)):
        moved = False
        for j in range(k):
            current = slot_values(sched, j, sched[j][0])[sched[j][1]]
            best, pick = current, sched[j]
            for c in names:
                values = slot_values(sched, j, c)
                t = int(np.argmin(values))
                if values[t] < best - 1e-12:
                    best, pick = float(values[t]), (c, t)
            if pick != sched[j]:
                sched[j], moved = pick, True
        if not moved:
            break
    value = float(slot_values(sched, 0, sched[0][0])[sched[0][1]])
    return tuple(sched), value


def label(b: Bank, sched: Sequence[Tuple[str, int]]) -> str:
    parts = []
    for c, t in sched:
        cut = b.tabs[c].cutoffs[t]
        parts.append(f"{c}@{'none' if cut is None else cut}")
    return f"v: cascade {', '.join(parts)}"


def replay(b: Bank, sched: Sequence[Tuple[str, int]]) -> ev.Result:
    """The evaluator's value of a cascade on every task."""
    policy = po.cascade([(c, b.tabs[c].cutoffs[t]) for c, t in sched])
    return ev.value(b.pools, policy, b.outside, b.verify, b.phi, mask=b.mask,
                    arrays=[b.tabs[c].arrays(t) for c, t in sched])


# ----------------------------------------------------------------------------- the two families

class Searches:
    """Each configuration's searched schedule at each K on a training set, computed once and
    shared by the two families that start from it. Bounded, because a bootstrap draws a new
    training set in every replicate."""

    def __init__(self, b: Bank, ks: Sequence[int], size: int = MEMO):
        self.b, self.ks, self.size, self.memo = b, tuple(ks), size, {}

    def __call__(self, train: np.ndarray) -> Dict[Tuple[str, int], Tuple[tuple, float]]:
        key = np.packbits(np.asarray(train, bool)).tobytes()
        if key in self.memo:
            return self.memo[key]
        b, got = self.b, {}
        for c in b.names:
            start = sc.constant_start(b.constants[c], b.tabs[c], self.ks)(train & b.mask)
            for k in self.ks:
                sched, value = sc.search(b.pools[c], b.tabs[c], b.charge[c], b.survive[c],
                                         b.outside, train & b.mask, k, start[k])
                got[(c, k)] = (sched, value)
        if len(self.memo) < self.size:
            self.memo[key] = got
        return got


def single_family(b: Bank, searches: Searches) -> inf.Family:
    """Every configuration's own schedule at every K, so that cross-fitting chooses the
    configuration as well as the schedule: the best single configuration picked from data."""
    cells = [(c, k) for c in b.names for k in searches.ks]

    def fit_on(train):
        got = searches(train)
        rows, used, labels = [], [], []
        for c, k in cells:
            sched = got[(c, k)][0]
            res = replay(b, [(c, t) for t in sched])
            rows.append(res.per_task)
            used.append(res.used)
            labels.append(f"single {c}: " + sc.label(c, [b.tabs[c].cutoffs[t] for t in sched]))
        return np.vstack(rows), np.vstack(used), tuple(labels)

    return inf.Family(values=np.zeros((len(cells), b.n_tasks)),
                      used=np.ones((len(cells), b.n_tasks), bool),
                      labels=tuple(f"single {c}, {k} attempts" for c, k in cells), fit=fit_on)


def cascade_family(b: Bank, searches: Searches, names: Optional[Sequence[str]] = None,
                   passes: int = PASSES) -> inf.Family:
    """One searched cascade per K, each started from the best single-configuration schedule at
    that K on the same training tasks. ``names`` restricts the configurations it may use."""
    names = tuple(names or b.names)
    ks = searches.ks

    def fit_on(train):
        got = searches(train)
        rows, used, labels = [], [], []
        for k in ks:
            c0 = min(names, key=lambda c: got[(c, k)][1])
            start = [(c0, t) for t in got[(c0, k)][0]]
            sched, _ = search(b, train, k, start, names, passes)
            res = replay(b, sched)
            rows.append(res.per_task)
            used.append(res.used)
            labels.append(label(b, sched))
        return np.vstack(rows), np.vstack(used), tuple(labels)

    return inf.Family(values=np.zeros((len(ks), b.n_tasks)),
                      used=np.ones((len(ks), b.n_tasks), bool),
                      labels=tuple(f"v: cascade, {k} attempts" for k in ks), fit=fit_on)


def own_schedule(b: Bank, searches: Searches, config: str) -> inf.Family:
    """One configuration's step iii-b on the cascade's common tasks, for the figure that sets the
    best cascade against each configuration's own optimum."""
    ks = searches.ks

    def fit_on(train):
        got = searches(train)
        rows, used, labels = [], [], []
        for k in ks:
            sched = got[(config, k)][0]
            res = replay(b, [(config, t) for t in sched])
            rows.append(res.per_task)
            used.append(res.used)
            labels.append(sc.label(config, [b.tabs[config].cutoffs[t] for t in sched]))
        return np.vstack(rows), np.vstack(used), tuple(labels)

    return inf.Family(values=np.zeros((len(ks), b.n_tasks)),
                      used=np.ones((len(ks), b.n_tasks), bool),
                      labels=tuple(f"{config}, {k} attempts" for k in ks), fit=fit_on)


# ----------------------------------------------------------------------------- diagnostics

def outcome_correlation(pools: Dict[str, ev.Pool], mask: Optional[np.ndarray] = None):
    """Across tasks, the correlation of each pair of configurations' resolve rates: the share of a
    task's usable draws that resolved. Weakly correlated failures are what make a portfolio pay."""
    names = tuple(pools)
    mask = ev.full_draw_tasks(pools, names) if mask is None else np.asarray(mask, bool)
    rates = []
    for c in names:
        p = pools[c]
        n = np.maximum(p.usable.sum(axis=1), 1)
        rates.append(((p.resolved & p.usable).sum(axis=1) / n)[mask])
    return names, np.corrcoef(np.vstack(rates)), int(mask.sum())


# ----------------------------------------------------------------------------- the runner

def cell(pools: Dict[str, ev.Pool], rate: float, fraction: float, phi: float = 0.0,
         mask: Optional[np.ndarray] = None, tabs=None, replicates: int = 0,
         seed: int = inf.SEED, essential: bool = False) -> dict:
    b = bank(pools, rate, fraction, phi, mask, tabs)
    label_ = inf.folds(b.n_tasks)
    searches = Searches(b, tuple(range(1, po.MAX_ATTEMPTS + 1)))
    single = single_family(b, searches)
    casc = cascade_family(b, searches)
    got_single = inf.cross_fit(single, label_, b.mask)
    got_casc = inf.cross_fit(casc, label_, b.mask)
    row = dict(rate=rate, regime=fraction, phi=phi, tasks=got_casc.n_tasks,
               value_escalate=float(b.outside[b.mask].mean()),
               value_best_single=got_single.value, value_cascade=got_casc.value,
               switch_margin=got_single.value - got_casc.value,
               switch_margin_low="", switch_margin_high="", replicates=0,
               choice_best_single="|".join(sorted(set(got_single.choices))),
               choice_cascade="|".join(sorted(set(got_casc.choices))),
               configurations_used="|".join(sorted({part.split("@")[0].split(" ")[-1]
                                                    for ch in got_casc.choices
                                                    for part in ch.split(": ", 1)[-1]
                                                    .replace("cascade ", "").split(", ")})))
    for c in b.names:
        row[f"own_{c}"] = inf.cross_fit(own_schedule(b, searches, c), label_, b.mask).value
    if replicates:
        band = inf.bootstrap(b.n_tasks, lambda idx: inf.margin(single, casc, idx, b.mask),
                             replicates=replicates, seed=seed)
        row.update(switch_margin_low=band["low"], switch_margin_high=band["high"],
                   replicates=band["replicates"])
    if essential:
        for c in b.names:
            rest = [x for x in b.names if x != c]
            without = inf.cross_fit(cascade_family(b, searches, rest), label_, b.mask).value
            row[f"without_{c}"] = without
            row[f"essential_{c}"] = without - got_casc.value
    return row


def fields(names: Sequence[str]) -> Tuple[str, ...]:
    """The columns of a cascade results file, for configurations ``names``."""
    return (("regime_name", "regime", "rate", "phi", "tasks", "value_escalate",
             "value_best_single", "value_cascade", "switch_margin", "switch_margin_low",
             "switch_margin_high", "replicates", "choice_best_single", "choice_cascade",
             "configurations_used")
            + tuple(f"own_{c}" for c in names) + tuple(f"without_{c}" for c in names)
            + tuple(f"essential_{c}" for c in names))


def _short_name(c: str) -> str:
    return (c.replace("_4runs", "").replace("-4runs", "").replace("-instruct", "")
            .replace("claude-", "").replace("-preview", ""))


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derived", default="data/derived")
    ap.add_argument("--notes", default="configurations_notes.json")
    ap.add_argument("--out", default="results/cascade.csv")
    ap.add_argument("--correlation", default="results/outcome_correlation.csv")
    ap.add_argument("--replicates", type=int, default=ld.FITTED_REPLICATES,
                    help="bootstrap replicates for the switching margin, at the fitted rates")
    ap.add_argument("--phi", type=float, default=0.0)
    a = ap.parse_args(argv)

    raw = {os.path.basename(f.rstrip("/")): ev.load(f)
           for f in ld.configurations(a.derived, a.notes)}
    if len(raw) < 2:
        print(f"{len(raw)} configurations found; a cascade needs at least two")
        return
    pools = ev.align(raw)
    mask = ev.full_draw_tasks(pools, tuple(pools))
    print(f"{len(pools)} configurations aligned on {len(next(iter(pools.values())).tasks)} tasks;"
          f" {int(mask.sum())} have four usable draws in every one", flush=True)

    names, corr, n = outcome_correlation(pools, mask)
    os.makedirs(os.path.dirname(a.correlation) or ".", exist_ok=True)
    with open(a.correlation, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["configuration"] + list(names))
        for c, r in zip(names, corr):
            w.writerow([c] + [f"{x:.4f}" for x in r])
    print(f"outcome correlation across {n} tasks -> {a.correlation}")
    off = corr[~np.eye(len(names), dtype=bool)]
    print(f"  off-diagonal: median {np.median(off):.2f}, range {off.min():.2f} to {off.max():.2f}")

    tabs = {c: sc.table(pools[c]) for c in pools}
    rows = []
    for name, fraction in ld.REGIMES:
        for rate in ld.RATES:
            fitted = name in ld.FITTED_REGIMES and rate in ld.FITTED_RATES
            essential = rate in ld.FITTED_RATES and name in ("automated", "human 0.5")
            row = cell(pools, rate, fraction, a.phi, mask, tabs,
                       replicates=a.replicates if fitted else 0, essential=essential)
            row["regime_name"] = name
            rows.append(row)
            band = (f" [{row['switch_margin_low']:6.2f},{row['switch_margin_high']:6.2f}]"
                    if row["replicates"] else "")
            own = min((row[f"own_{c}"], c) for c in names)
            print(f"  {name:10s} ${rate:4.0f}/h  best single {row['value_best_single']:8.2f}"
                  f"  cascade {row['value_cascade']:8.2f}  switch {row['switch_margin']:6.2f}{band}"
                  f"  | best own {_short_name(own[1])} {own[0]:8.2f}"
                  f"  esc {row['value_escalate']:8.2f}"
                  f"  | uses {','.join(_short_name(c) for c in row['configurations_used'].split('|'))}",
                  flush=True)
            if essential:
                print("      essential: " + "  ".join(
                    f"{_short_name(c)} {row[f'essential_{c}']:+.2f}" for c in names), flush=True)

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="") as fh:
        columns = fields(names)
        w = csv.DictWriter(fh, fieldnames=columns)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in columns})
    print(f"\n{len(rows)} rows -> {a.out}")


if __name__ == "__main__":
    _main()
