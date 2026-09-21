"""The comparators the plan registers beside the ladder (PLAN.md Sections 4, 6 and 7).

Each is a policy family of its own, chosen on the training folds and scored on the held-out folds
like every rung of the ladder, on the same tasks and against the same outside option. They are
reported in full and not argued from.

    dollar cutoff      K attempts, each stopped at the first decision point at which its spend
                       exceeds a dollar cutoff, over 40 cutoffs spaced evenly in logarithm between
                       the 5th percentile of spend at call 5 and the largest attempt spend on the
                       training folds (Sections 4 and 6). It is the sensitivity of the primary result
                       to denominating the cap in dollars rather than calls, fitted separately and
                       never chosen between: its margin is step ii minus it.
    threshold          the low-complexity comparator to the state rule (Section 6): stop at decision
                       point t when spend per call over the last five calls exceeds a + b t, with a
                       at the 5th to 95th percentiles of that spend rate over running attempts on
                       the training folds, in steps of five, and b at eleven values that move the
                       threshold at the last decision point from a quarter of a to four times a,
                       evenly in logarithm; K chosen alongside. Its margin is it minus step iv: if
                       the plug-in rule cannot beat it, the regressions are adding nothing.
    universal          the universal restart schedule, whose cutoffs run in the sequence 1, 1, 2, 1
                       of a unit (Section 7, appendix). Its classical guarantee assumes unbounded
                       restarts of a procedure that eventually succeeds, and is not claimed to carry
                       over. The plan does not fix the unit, and a unit of one call would stop every
                       attempt at once, so the unit is chosen on the training folds from the
                       decision points whose double is also a decision point, or at or past the
                       configuration's own stop, with K chosen alongside. Its margin is it minus
                       step iii-b, the searched schedule it is a special case of.
    first look         the state rule allowed to act only at the first decision point (Section 7,
                       appendix), with the same two models; its margin is step iii-b minus it, read
                       beside step iii-b minus the unrestricted rule. If it were large it would
                       recommend one early look and a fixed rule thereafter.

The dollar cutoff and the threshold stop every attempt by the same rule, so a policy's value on a
task is a symmetric function of that task's draws, and it is computed in closed form: attempts are
the task's usable draws taken in random order without replacement, a draw is attempted when every
draw before it failed, and the chance of that depends on the draw only through whether it fails
itself. The tests hold the closed form to the evaluator's enumeration of orderings. Both families
are refitted on each training set, since their grids are set there, and the fit does not depend on
the rate, so it is kept per training set and read at every rate.

Intervals are the full-pipeline bootstrap, every family refitted inside every replicate, at the
count and the rates of the ladder's own fitted steps: the automated verifier at $25, $100 and
$300, 100 replicates.

    python -m restart.comparators --derived data/derived
"""
from __future__ import annotations

import csv
import math
import os
from collections import OrderedDict
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import evaluate as ev
from . import inference as inf
from . import ladder as ld
from . import policies as po
from . import schedules as sc
from . import state as st

KS = tuple(range(1, po.MAX_ATTEMPTS + 1))
DOLLAR_CUTOFFS = 40
THRESHOLD_A = tuple(range(5, 100, 5))                 # percentiles of the spend rate
THRESHOLD_M = tuple(np.geomspace(0.25, 4.0, 11))      # threshold at the last point, over a
LUBY = (1, 1, 2, 1)                                   # the universal sequence's first four terms
REPLICATES = ld.FITTED_REPLICATES
FITTED_RATES = ld.FITTED_RATES


# ----------------------------------------------------------------------------- the closed form

def _comb(n: int) -> np.ndarray:
    """C(a, b) at [a + 1, b] for a from -1 to n, zero where b > a."""
    table = np.zeros((n + 2, n + 1))
    for a in range(n + 1):
        for b in range(a + 1):
            table[a + 1, b] = math.comb(a, b)
    return table


def symmetric(cost: np.ndarray, resolves: np.ndarray, checks: np.ndarray, usable: np.ndarray,
              ks: Sequence[int] = KS):
    """Coefficients of K attempts under one stopping rule, per candidate rule and task.

    ``cost``, ``resolves`` and ``checks`` are [candidate, task, draw]: what each draw does when
    stopped by that candidate. With n usable draws of which f fail, taken in random order without
    replacement, the draw in position j + 1 is attempted when the j before it all failed, which
    for a failing draw has chance C(f - 1, j) / C(n - 1, j) and for a resolving one C(f, j) /
    C(n - 1, j); every K attempts fail with chance C(f, K) / C(n, K). Returns spend, checks,
    resolves, fails and used, each [candidate x K, task], candidates within each K in turn."""
    usable = np.asarray(usable, bool)
    n_d = usable.shape[1]
    table = _comb(n_d)
    ok = np.asarray(resolves, bool) & usable[None]
    bad = ~np.asarray(resolves, bool) & usable[None]
    n = usable.sum(axis=1)[None, :]                        # [1, task]
    f = bad.sum(axis=2)                                    # [candidate, task]
    spend_f, spend_s = (cost * bad).sum(axis=2), (cost * ok).sum(axis=2)
    check_f, check_s = (checks * bad).sum(axis=2), (checks * ok).sum(axis=2)
    wins = n - f
    out = {key: [] for key in ("spend", "checks", "resolves", "fails", "used")}
    n_safe = np.maximum(n, 1)
    for k in ks:
        valid = np.broadcast_to(n >= k, f.shape)
        w_fail = np.zeros(f.shape)
        w_succ = np.zeros(f.shape)
        for j in range(k):
            den = table[np.clip(n - 1, -1, n_d) + 1, j]
            den = np.where(den > 0, den, 1.0)
            w_fail += table[f, j] / den                    # C(f - 1, j): row f is a = f - 1
            w_succ += table[f + 1, j] / den
        w_fail, w_succ = w_fail / n_safe, w_succ / n_safe
        all_fail = table[f + 1, k] / np.where(table[n + 1, k] > 0, table[n + 1, k], 1.0)
        zero = np.zeros(f.shape)
        out["spend"].append(np.where(valid, w_fail * spend_f + w_succ * spend_s, zero))
        out["checks"].append(np.where(valid, w_fail * check_f + w_succ * check_s, zero))
        out["resolves"].append(np.where(valid, w_succ * wins, zero))
        out["fails"].append(np.where(valid, all_fail, zero))
        out["used"].append(valid.copy())
    return {key: np.vstack(v) for key, v in out.items()}


def stopped(pool: ev.Pool, stop: np.ndarray):
    """[candidate, task, draw] slot arrays for candidates that stop attempts at a decision point
    index each, -1 where the attempt runs to its own stop; ``evaluate.stopped_slot``, stacked."""
    stop = np.asarray(stop, int)
    j = np.clip(stop, 0, len(pool.grid) - 1)
    t, d = np.indices(stop.shape[1:])
    cut = (stop >= 0) & pool.alive[t[None], d[None], j]
    cost = np.where(cut, pool.cost_grid[t[None], d[None], j], pool.cost_end[None])
    return cost, pool.resolved[None] & ~cut, pool.candidate[None] & ~cut


def _first(over: np.ndarray) -> np.ndarray:
    """The first decision point where ``over`` holds, -1 where it never does; last axis."""
    return np.where(over.any(axis=-1), over.argmax(axis=-1), -1)


# ----------------------------------------------------------------------------- the two refitted families

def dollar_cutoffs(pool: ev.Pool, train: np.ndarray, count: int = DOLLAR_CUTOFFS) -> np.ndarray:
    """Section 6: log-spaced between the 5th percentile of spend at call 5 and the largest attempt
    spend, both over usable attempts on the training tasks."""
    keep = pool.usable & np.asarray(train, bool)[:, None]
    first = pool.grid.index(5) if 5 in pool.grid else 0
    lo = float(np.percentile(pool.cost_grid[:, :, first][keep], 5))
    hi = float(pool.cost_end[keep].max())
    return np.geomspace(max(lo, 1e-12), max(hi, lo * (1 + 1e-9), 1e-12), count)


def dollar_fit(pool: ev.Pool, train: np.ndarray, ks: Sequence[int] = KS):
    cuts = dollar_cutoffs(pool, train)
    over = pool.alive[None] & (pool.cost_grid[None] > cuts[:, None, None, None])
    got = symmetric(*stopped(pool, _first(over)), pool.usable, ks)
    got["labels"] = tuple(f"dollar: {k} attempts at ${c:.4g}" for k in ks for c in cuts)
    return got


def threshold_grid(pool: ev.Pool, train: np.ndarray) -> List[Tuple[float, float]]:
    """(a, b) pairs: a at percentiles of spend per call over the last five calls, over running
    attempts at decision points on the training tasks; b moving the threshold at the last
    decision point from a/4 to 4a."""
    here = pool.alive & (pool.usable & np.asarray(train, bool)[:, None])[:, :, None]
    rates = pool.cost_rate[here]
    last = float(pool.grid[-1])
    out = []
    for a in np.percentile(rates, THRESHOLD_A):
        for m in THRESHOLD_M:
            out.append((float(a), float((m - 1.0) * a / last)))
    return out


def threshold_fit(pool: ev.Pool, train: np.ndarray, ks: Sequence[int] = KS):
    pairs = threshold_grid(pool, train)
    a = np.array([p[0] for p in pairs])[:, None]
    b = np.array([p[1] for p in pairs])[:, None]
    line = a + b * np.asarray(pool.grid, float)[None, :]            # [candidate, point]
    over = pool.alive[None] & (pool.cost_rate[None] > line[:, None, None, :])
    got = symmetric(*stopped(pool, _first(over)), pool.usable, ks)
    got["labels"] = tuple(f"threshold: {k} attempts, a {x:.4g} b {y:+.3g}"
                          for k in ks for x, y in pairs)
    return got


class Lru:
    """A small cache of fits by training set: a replicate reads each of its five training sets at
    every rate before moving on, so a handful of entries is enough and memory stays bounded."""

    def __init__(self, size: int = 8):
        self.size, self.store = size, OrderedDict()

    def get(self, key, make: Callable[[], dict]) -> dict:
        if key in self.store:
            self.store.move_to_end(key)
            return self.store[key]
        got = make()
        self.store[key] = got
        if len(self.store) > self.size:
            self.store.popitem(last=False)
        return got


def refitted(pool: ev.Pool, fit: Callable, outside: np.ndarray, verify: np.ndarray,
             phi: float, cache: Lru, size: int, mask: Optional[np.ndarray] = None) -> inf.Family:
    """A family refitted on each training set, read at one rate from fits kept per training set."""
    keep = np.ones(pool.n_tasks, bool) if mask is None else np.asarray(mask, bool)

    def fit_on(train):
        train = np.asarray(train, bool)
        got = cache.get(np.packbits(train).tobytes(), lambda: fit(pool, train))
        values = (got["spend"] + verify * got["checks"] + phi * outside * got["resolves"]
                  + outside * got["fails"])
        return values, got["used"] & keep[None], got["labels"]

    return inf.Family(values=np.zeros((size, pool.n_tasks)),
                      used=np.ones((size, pool.n_tasks), bool),
                      labels=tuple(str(i) for i in range(size)), fit=fit_on)


# ----------------------------------------------------------------------------- the two fixed ones

def luby_units(pool: ev.Pool) -> List[int]:
    """Units whose multiples in the schedule are decision points or at or past the stop."""
    grid = set(pool.grid)
    return [u for u in pool.grid if all(m * u in grid or m * u >= pool.cap for m in set(LUBY))]


def universal_policies(pool: ev.Pool, ks: Sequence[int] = KS):
    out = []
    for k in ks:
        for u in luby_units(pool):
            cuts = [m * u if m * u < pool.cap else None for m in LUBY[:k]]
            out.append(po.Policy(tuple(po.Slot(pool.config, c) for c in cuts),
                                 f"universal: {k} attempts, unit {u}"))
    return out


def first_point(pool: ev.Pool) -> np.ndarray:
    allowed = np.zeros(len(pool.grid), bool)
    allowed[0] = True
    return allowed


# ----------------------------------------------------------------------------- one rate

FAMILIES = ("ii", "iii", "iiib", "iv", "iv_first", "dollar", "threshold", "universal")


def families(pool: ev.Pool, rate: float, fraction: float, phi: float, mask: np.ndarray,
             tab: sc.Table, caches: dict) -> Dict[str, inf.Family]:
    """Every family at one rate, the ladder's own steps built as ``ladder.rung`` builds them."""
    outside = ev.outside_option(pool, rate)
    verify = ev.verification(outside, fraction)
    retry = ld._family(pool, [po.retry(pool.config, k) for k in KS], outside, verify, phi, mask)
    capped = ld._family(pool, po.constant_family(pool.config, pool.grid, KS),
                        outside, verify, phi, mask)
    return dict(
        ii=retry, iii=capped,
        iiib=sc.family(pool, outside, verify, phi, KS, tab=tab, mask=mask,
                       start=sc.constant_start(capped, tab, KS)),
        iv=st.family(pool, outside, verify, phi, KS, mask=mask, notes=caches["notes"],
                     cache=caches["state"], cache_size=10 ** 6),
        iv_first=st.family(pool, outside, verify, phi, KS, mask=mask, notes=caches["notes"],
                           cache=caches["state"], cache_size=10 ** 6,
                           allowed=first_point(pool)),
        dollar=refitted(pool, dollar_fit, outside, verify, phi, caches["dollar"],
                        DOLLAR_CUTOFFS * len(KS), mask),
        threshold=refitted(pool, threshold_fit, outside, verify, phi, caches["threshold"],
                           len(THRESHOLD_A) * len(THRESHOLD_M) * len(KS), mask),
        universal=ld._family(pool, universal_policies(pool), outside, verify, phi, mask),
    )


# margins, each written so that a positive number is what the richer or registered policy saves
MARGINS = {
    "dollar_cap_margin": ("ii", "dollar"),          # the primary result, cap in dollars
    "dollar_vs_calls": ("iii", "dollar"),           # descriptive: the two denominations
    "rule_vs_threshold": ("threshold", "iv"),       # what the regressions add
    "threshold_vs_schedule": ("iiib", "threshold"),
    "schedule_vs_universal": ("universal", "iiib"),
    "universal_vs_retry": ("ii", "universal"),
    "state_margin": ("iiib", "iv"),
    "first_look_margin": ("iiib", "iv_first"),
}
INTERVALS = ("dollar_cap_margin", "rule_vs_threshold", "schedule_vs_universal",
             "first_look_margin")


def caches() -> dict:
    return dict(state={}, dollar=Lru(8), threshold=Lru(8), notes=[])


def cell(pool: ev.Pool, rate: float, fraction: float, phi: float, mask: np.ndarray,
         label: np.ndarray, tab: sc.Table, store: dict) -> dict:
    """Every comparator's cross-fitted value at one rate and regime, and the margins."""
    fams = families(pool, rate, fraction, phi, mask, tab, store)
    got = {name: inf.cross_fit(f, label, mask) for name, f in fams.items()}
    row = dict(config=pool.config, rate=rate, regime=fraction, phi=phi,
               multiple=ev.multiple_for_rate(pool, rate, mask), tasks=got["ii"].n_tasks)
    for name in FAMILIES:
        row[f"value_{name}"] = got[name].value
    for name, (base, richer) in MARGINS.items():
        row[name] = got[base].value - got[richer].value
    for name in ("dollar", "threshold", "universal", "iv_first"):
        row[f"choice_{name}"] = "|".join(sorted(set(got[name].choices)))
    return row


def intervals(pool: ev.Pool, phi: float, mask: np.ndarray, tab: sc.Table,
              rates: Sequence[float] = FITTED_RATES, fraction: float = 0.0,
              replicates: int = REPLICATES, seed: int = inf.SEED) -> Dict[float, dict]:
    """The full-pipeline bootstrap of the registered margins at a few rates, every family
    refitted inside every replicate and read at every rate from the same fits."""
    store = caches()
    fams = {r: families(pool, r, fraction, phi, mask, tab, store) for r in rates}
    names = sorted({n for m in INTERVALS for n in MARGINS[m]})

    def statistic(idx):
        out = []
        for r in rates:
            v = {n: inf.cross_fitted_value(fams[r][n], idx, mask) for n in names}
            out += [v[MARGINS[m][0]] - v[MARGINS[m][1]] for m in INTERVALS]
        return out

    bands = inf.bootstrap_many(pool.n_tasks, statistic, replicates=replicates, seed=seed)
    got = {}
    for i, r in enumerate(rates):
        got[r] = {}
        for j, m in enumerate(INTERVALS):
            b = bands[i * len(INTERVALS) + j]
            got[r].update({f"{m}_low": b["low"], f"{m}_high": b["high"]})
        got[r]["fitted_replicates"] = min(bands[i * len(INTERVALS) + j]["replicates"]
                                          for j in range(len(INTERVALS)))
    return got


def rows_for(pool: ev.Pool, phi: float = 0.0, rates: Sequence[float] = ld.RATES,
             multiples: Sequence[float] = ld.MULTIPLES, regimes=ld.REGIMES,
             replicates: int = REPLICATES, fitted_rates: Sequence[float] = FITTED_RATES,
             mask: Optional[np.ndarray] = None, log=None) -> List[dict]:
    mask = ev.full_draw_tasks({pool.config: pool}) if mask is None else np.asarray(mask, bool)
    tab = sc.table(pool)
    label = inf.folds(pool.n_tasks)
    store = caches()
    rows = []
    for name, fraction in regimes:
        for axis, rate in ld._points(pool, rates, multiples, mask):
            row = cell(pool, rate, fraction, phi, mask, label, tab, store)
            row.update(regime_name=name, axis=axis, fitted_replicates=0)
            rows.append(row)
    if replicates and fitted_rates:
        wanted = [r for r in fitted_rates if r in tuple(rates)]
        bands = intervals(pool, phi, mask, tab, wanted, 0.0, replicates)
        for row in rows:
            if row["regime_name"] == "automated" and row["axis"] == "rate" \
                    and row["rate"] in bands:
                row.update(bands[row["rate"]])
    for row in rows:
        row["state_notes"] = "; ".join(sorted(set(store["notes"])))
    if log:
        for row in rows:
            if row["axis"] == "rate" and row["rate"] == 100.0:
                log(_line(row))
    return rows


def _line(row: dict) -> str:
    def f(key):
        x = row.get(key, "")
        return f"{x:+8.3f}" if isinstance(x, float) else "       -"

    def band(key):
        lo = row.get(f"{key}_low", "")
        return f" [{lo:+.2f},{row[f'{key}_high']:+.2f}]" if isinstance(lo, float) else ""
    return (f"  {row['regime_name']:10s} ${row['rate']:4.0f}/h  dollar cap {f('dollar_cap_margin')}"
            f"{band('dollar_cap_margin')}  rule vs threshold {f('rule_vs_threshold')}"
            f"{band('rule_vs_threshold')}  schedule vs universal {f('schedule_vs_universal')}"
            f"{band('schedule_vs_universal')}  first look {f('first_look_margin')}"
            f"{band('first_look_margin')} (state {f('state_margin')})")


FIELDS = (("config", "regime_name", "regime", "axis", "rate", "multiple", "phi", "tasks")
          + tuple(f"value_{n}" for n in FAMILIES) + tuple(MARGINS)
          + tuple(f"{m}_{s}" for m in INTERVALS for s in ("low", "high"))
          + ("fitted_replicates", "choice_dollar", "choice_threshold", "choice_universal",
             "choice_iv_first", "state_notes"))


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
    ap.add_argument("--out", default="results/comparators.csv")
    ap.add_argument("--replicates", type=int, default=REPLICATES)
    ap.add_argument("--rates", nargs="*", type=float, default=list(ld.RATES))
    ap.add_argument("--multiples", nargs="*", type=float, default=list(ld.MULTIPLES))
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args(argv)
    rows = []
    for folder in ld.configurations(a.derived, a.notes, a.only):
        pool = ev.load(folder)
        print(f"{os.path.basename(folder.rstrip('/'))}: {pool.n_tasks} tasks", flush=True)
        rows += rows_for(pool, rates=a.rates, multiples=a.multiples, replicates=a.replicates,
                         log=lambda line: print(line, flush=True))
        write(rows, a.out)
    print(f"\n{len(rows)} rows -> {a.out}")


if __name__ == "__main__":
    _main()
