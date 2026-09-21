"""The sample oracle benchmark (PLAN.md Section 7, appendix).

For each task, the cheapest policy in the schedule class the cascades are drawn from, one to four
attempts each naming a configuration and a cutoff, evaluated on that task's own draws, and the
mean of those minima over tasks. It bounds the evaluated class: no policy chosen without knowing
the task can do better on these draws. It is not a population ceiling, because taking a minimum
over seven configurations on four draws per task picks up the draws that happened to go well, a
winner's-curse bias downward. The gap between the best cross-fitted cascade and this benchmark is
therefore an upper estimate of what knowing the task in advance would be worth.

The minimum is exact, not searched. Three facts make it small enough to compute.

1. Within a configuration and a task, a cutoff matters only through which of the task's draws it
   lets finish and resolve. Among cutoffs that resolve the same draws the smallest spends least
   and verifies least, so it is the only one worth trying. A cutoff that resolves none of the
   draws only adds cost, since the policy never learns which draw it used, so it is worth
   trying only as the one attempt a policy must make before escalating, which is the cheapest
   plan when success is unlikely and review is dear. That leaves one candidate per set of draws
   a cutoff can resolve, and beside the recursion one attempt at the cheapest cutoff that
   resolves nothing, then the outside option.
2. A configuration's draws are used in random order without replacement, and those of different
   configurations independently, so given that every attempt so far failed, what the next attempt
   costs and the chance it fails depend only on which cutoffs each configuration has used, not
   their order. That is the state.
3. The value of continuing from a state does not depend on how it was reached, so the minimum
   over schedules is a recursion over states: stop and pay the outside option (after at least one
   attempt), or add one more attempt from some configuration at one of its candidates.

A fixed schedule is open-loop, but the only thing it could observe is whether an attempt resolved,
and it stops when one does, so the recursion's minimum is attained by a fixed schedule. The tests
hold the recursion to a brute-force search over every schedule on small cases.

    python -m restart.oracle --derived data/derived
"""
from __future__ import annotations

import csv
import itertools
import os
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import cascade as cs
from . import evaluate as ev
from . import ladder as ld
from . import policies as po
from . import schedules as sc

MAX = po.MAX_ATTEMPTS


def candidates(tab: sc.Table, task: int) -> List[int]:
    """The cutoffs worth trying on one task: for each set of draws a cutoff can resolve, the
    smallest cutoff that resolves exactly that set, the empty set left out."""
    seen: Dict[Tuple[bool, ...], int] = {}
    for c in range(len(tab.cutoffs)):          # the table runs from the smallest cutoff up
        key = tuple(bool(x) for x in tab.resolves[c, task])
        if any(key) and key not in seen:
            seen[key] = c
    return sorted(seen.values())


class Config:
    """One configuration on one task: what each candidate cutoff does to each draw, and the
    chances and expected costs the recursion reads, computed once per used-cutoff multiset."""

    def __init__(self, tab: sc.Table, task: int, cands: Sequence[int]):
        self.cands = tuple(cands)
        self.cost = tab.cost[list(cands), task]            # [candidate, draw]
        self.res = tab.resolves[list(cands), task].astype(float)
        self.chk = tab.checks[list(cands), task].astype(float)
        n_d = tab.cost.shape[2]
        self.perms = np.asarray(list(itertools.permutations(range(n_d))), int)
        self.n_d = n_d
        self._fail: Dict[Tuple[int, ...], np.ndarray] = {}

    def failed(self, used: Tuple[int, ...]) -> np.ndarray:
        """[ordering]: whether every used draw failed, used cutoffs assigned to the first draws."""
        if used not in self._fail:
            out = np.ones(len(self.perms))
            for i, c in enumerate(used):
                out = out * (1.0 - self.res[c, self.perms[:, i]])
            self._fail[used] = out
        return self._fail[used]

    def step(self, used: Tuple[int, ...], c: int):
        """Given that every used draw failed: the next attempt's expected spend, verifications
        and resolutions, and the chance it fails too. None where the given cannot happen."""
        before = self.failed(used)
        p = before.mean()
        if p <= 0:
            return None
        nxt = self.perms[:, len(used)]
        spend = (before * self.cost[c, nxt]).mean() / p
        checks = (before * self.chk[c, nxt]).mean() / p
        wins = (before * self.res[c, nxt]).mean() / p
        return spend, checks, wins, 1.0 - wins


def task_minimum(configs: Sequence[Config], outside: np.ndarray, verify: np.ndarray,
                 phi: float = 0.0) -> np.ndarray:
    """The minimum over schedules of one to four attempts, at many rates at once: ``outside`` and
    ``verify`` are this task's outside option and verification cost at each point."""
    memo: Dict[Tuple[Tuple[int, ...], ...], np.ndarray] = {}

    def value(state: Tuple[Tuple[int, ...], ...]) -> np.ndarray:
        if state in memo:
            return memo[state]
        made = sum(len(s) for s in state)
        best = outside.copy() if made else np.full(len(outside), np.inf)
        if made < MAX:
            for m, cfg in enumerate(configs):
                if len(state[m]) >= cfg.n_d:
                    continue
                for c in range(len(cfg.cands)):
                    got = cfg.step(state[m], c)
                    if got is None:
                        continue
                    spend, checks, wins, again = got
                    here = spend + verify * checks + phi * outside * wins
                    if again > 0:
                        nxt = list(state)
                        nxt[m] = tuple(sorted(state[m] + (c,)))
                        here = here + again * value(tuple(nxt))
                    best = np.minimum(best, here)
        memo[state] = best
        return best

    return value(tuple(() for _ in configs))


def escalate_after_one(tabs: Sequence[sc.Table], task: int, outside: np.ndarray,
                       verify: np.ndarray) -> np.ndarray:
    """One attempt at the cheapest cutoff that resolves none of the task's draws, then the
    outside option; infinite where every cutoff of every configuration resolves some draw."""
    best = np.full(len(outside), np.inf)
    for tab in tabs:
        none = ~tab.resolves[:, task].any(axis=1)
        if not none.any():
            continue
        spend = tab.cost[none, task].mean(axis=1)[:, None]         # [cutoff, 1]
        checks = tab.checks[none, task].mean(axis=1)[:, None]
        best = np.minimum(best, (spend + checks * verify[None, :]).min(axis=0))
    return best + outside


def oracle(pools: Dict[str, ev.Pool], rates: Sequence[float], fractions: Sequence[float],
           phi: float = 0.0, mask: Optional[np.ndarray] = None,
           tabs: Optional[Dict[str, sc.Table]] = None, log=None) -> Tuple[np.ndarray, np.ndarray]:
    """[point]: the benchmark's mean over the tasks in ``mask`` at each (rate, fraction), and
    [task, point]: each task's minimum."""
    names = tuple(pools)
    first = pools[names[0]]
    mask = ev.full_draw_tasks(pools, names) if mask is None else np.asarray(mask, bool)
    tabs = tabs or {c: sc.table(pools[c]) for c in names}
    rates = np.asarray(rates, float)
    fractions = np.asarray(fractions, float)
    hours = first.minutes / 60.0
    per_task = np.full((first.n_tasks, len(rates)), np.nan)
    for n, i in enumerate(np.flatnonzero(mask)):
        outside = rates * hours[i]
        verify = fractions * outside
        configs = []
        for c in names:
            cands = candidates(tabs[c], i)
            if cands:
                configs.append(Config(tabs[c], i, cands))
        floor = escalate_after_one([tabs[c] for c in names], i, outside, verify)
        per_task[i] = (np.minimum(task_minimum(configs, outside, verify, phi), floor)
                       if configs else floor)
        if log and (n + 1) % 50 == 0:
            log(f"    {n + 1} of {int(mask.sum())} tasks")
    return per_task[mask].mean(axis=0), per_task


FIELDS = ("regime_name", "regime", "rate", "phi", "tasks", "value_oracle", "value_cascade",
          "value_best_single", "value_escalate", "oracle_gap", "oracle_gap_single")


def rows_for(pools: Dict[str, ev.Pool], rates: Sequence[float] = ld.RATES, regimes=ld.REGIMES,
             phi: float = 0.0, log=None) -> List[dict]:
    """The benchmark beside the best cross-fitted cascade and single configuration, on the
    cascade's own tasks, at every rate and regime."""
    aligned = ev.align(pools)
    names = tuple(aligned)
    mask = ev.full_draw_tasks(aligned, names)
    tabs = {c: sc.table(aligned[c]) for c in names}
    points = [(name, f, r) for name, f in regimes for r in rates]
    means, _ = oracle(aligned, [p[2] for p in points], [p[1] for p in points], phi, mask, tabs,
                      log=log)
    rows = []
    for (name, f, r), best in zip(points, means):
        got = cs.cell(aligned, r, f, phi, mask, tabs, replicates=0)
        rows.append(dict(regime_name=name, regime=f, rate=r, phi=phi, tasks=int(mask.sum()),
                         value_oracle=float(best), value_cascade=got["value_cascade"],
                         value_best_single=got["value_best_single"],
                         value_escalate=got["value_escalate"],
                         oracle_gap=got["value_cascade"] - float(best),
                         oracle_gap_single=got["value_best_single"] - float(best)))
        if log:
            log(f"  {name:10s} ${r:4.0f}/h  oracle {best:8.2f}  cascade {got['value_cascade']:8.2f}"
                f"  best single {got['value_best_single']:8.2f}"
                f"  gap {got['value_cascade'] - best:7.2f}")
    return rows


def write(rows: Sequence[dict], path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(FIELDS))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    return path


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derived", default="data/derived")
    ap.add_argument("--notes", default="configurations_notes.json")
    ap.add_argument("--out", default="results/oracle.csv")
    ap.add_argument("--rates", nargs="*", type=float, default=list(ld.RATES))
    a = ap.parse_args(argv)
    pools = {os.path.basename(f.rstrip("/")): ev.load(f)
             for f in ld.configurations(a.derived, a.notes)}
    rows = rows_for(pools, rates=a.rates, log=lambda line: print(line, flush=True))
    print(f"\n{len(rows)} rows -> {write(rows, a.out)}")


if __name__ == "__main__":
    _main()
