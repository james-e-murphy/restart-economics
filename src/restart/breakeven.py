"""The break-even rate: the summary statistic of the primary result (PLAN.md Section 7).

The primary result is the cap's marginal value given retry, step ii minus step iii, as a function
of the outside-option rate. Its summary statistic is the rate at which that value changes sign,
one per configuration per regime, in dollars an hour and in multiples of the configuration's
median attempt cost.

Uniqueness is not assumed. Under automated verification a higher rate makes each lost success
dearer, but under human review the cap also saves the review of every attempt it discards, and the
policy is re-selected at every rate, so the margin need not cross zero once or at all. The sweep is
therefore scanned on a logarithmic grid wide enough to hold both axes of Section 7, every bracket
where the sign changes is bisected, and all of the crossings are reported. Where the sign never
changes, the row records that and states which side of the sweep the break-even lies on.

Bisection locates the crossing of the point estimate. Its uncertainty is read from the sweep the
ladder has already run: the band of rates over which the bootstrap interval on the margin covers
zero is the range of rates at which the sign is not resolved, and is carried beside the crossing.
"""
from __future__ import annotations

import csv
import os
from typing import Callable, Dict, List, Optional, Sequence

import numpy as np

from . import evaluate as ev
from . import ladder as ld
from . import schedules as sc

SCAN = 24               # points on the logarithmic scan of the rate
TOLERANCE = 0.02        # a crossing is located to this relative width in the rate
ZERO = 1e-9             # dollars per task: below this a margin has no sign


def cap_margin(pool: ev.Pool, rate: float, fraction: float, phi: float = 0.0,
               mask: Optional[np.ndarray] = None, tab: Optional[sc.Table] = None) -> float:
    """The primary result at one rate: what the cap saves given retry, cross-fitted, no interval."""
    row = ld.rung(pool, rate, fraction, phi, replicates=0, mask=mask, tab=tab, steps=())
    return row["cap_margin"]


def _sign(x: float) -> int:
    return 0 if not np.isfinite(x) or abs(x) < ZERO else (1 if x > 0 else -1)


def bisect(f: Callable[[float], float], lo: float, hi: float,
           tolerance: float = TOLERANCE) -> float:
    """The rate between ``lo`` and ``hi`` at which the sign changes, to a relative width.

    The scan is logarithmic because the sweep is: the interesting rates run from a few dollars an
    hour to a few hundred, and a crossing at $7 deserves the same resolution as one at $250.
    """
    f_lo = f(lo)
    while hi / lo > 1.0 + tolerance:
        mid = float(np.sqrt(lo * hi))
        f_mid = f(mid)
        if _sign(f_mid) == _sign(f_lo) or _sign(f_mid) == 0:
            lo, f_lo = mid, f_mid
        else:
            hi = mid
    return float(np.sqrt(lo * hi))


def crossings(pool: ev.Pool, fraction: float, phi: float = 0.0,
              mask: Optional[np.ndarray] = None, scan: int = SCAN,
              tolerance: float = TOLERANCE, rates: Optional[Sequence[float]] = None,
              log=None) -> dict:
    """Scan the rate axis for one configuration in one regime and locate every sign change."""
    mask = ev.full_draw_tasks({pool.config: pool}) if mask is None else mask
    tab = sc.table(pool)
    lo = min(min(ld.RATES), ev.rate_for_multiple(pool, min(ld.MULTIPLES), mask))
    hi = max(max(ld.RATES), ev.rate_for_multiple(pool, max(ld.MULTIPLES), mask))
    grid = np.asarray(rates, float) if rates is not None else np.geomspace(lo, hi, scan)

    seen: Dict[float, float] = {}

    def f(rate: float) -> float:
        rate = float(rate)
        if rate not in seen:
            seen[rate] = cap_margin(pool, rate, fraction, phi, mask, tab)
            if log:
                log(f"    ${rate:9.2f}/h  {ev.multiple_for_rate(pool, rate, mask):8.2f}x"
                    f"  cap ${seen[rate]:8.3f}")
        return seen[rate]

    values = [f(r) for r in grid]
    found = []
    for i in range(len(grid) - 1):
        a, b = _sign(values[i]), _sign(values[i + 1])
        # a margin of exactly zero is its own sign, not a missing one: it is what the comparison
        # returns over the range of rates where no fold chooses a cap that binds, and the edges of
        # that range are the rates at which a cap starts and stops being worth choosing
        if a != b:
            rate = bisect(f, float(grid[i]), float(grid[i + 1]), tolerance)
            found.append(dict(rate=rate, multiple=ev.multiple_for_rate(pool, rate, mask),
                              below=a, above=b))
    return dict(config=pool.config, regime=fraction, phi=phi, grid=grid, values=values,
                crossings=found, scan_low=float(grid[0]), scan_high=float(grid[-1]),
                sign_low=_sign(values[0]), sign_high=_sign(values[-1]),
                median_attempt_cost=ev.median_attempt_cost(pool, mask),
                evaluations=len(seen))


def band(rows: Sequence[dict], config: str, regime: float):
    """From the ladder's sweep: the rates at which the interval on the margin still covers zero."""
    here = [r for r in rows
            if r.get("config") == config and float(r.get("regime", -1)) == regime
            and r.get("cap_margin_low") not in (None, "")]
    covers = [float(r["rate"]) for r in here
              if float(r["cap_margin_low"]) <= 0.0 <= float(r["cap_margin_high"])]
    return (min(covers), max(covers)) if covers else (None, None)


def resolved(rows: Sequence[dict], config: str, regime: float, bounds: Sequence[float],
             signs: Sequence[int]) -> List[bool]:
    """For each stretch of the sweep between crossings, whether the ladder resolves its sign.

    A stretch where the margin is positive is resolved if at some point of the ladder inside it
    the bootstrap interval lies wholly above zero, and likewise below; a stretch at exactly zero
    is resolved if the ladder finds the margin exactly zero there. A crossing with both of its
    sides resolved is a sign change the data support. One with an unresolved side is the margin
    moving within its own noise, which the plan still requires to be reported, and this is how
    the two are told apart.
    """
    here = [r for r in rows
            if r.get("config") == config and float(r.get("regime", -1)) == regime
            and r.get("cap_margin_low") not in (None, "")]
    out = []
    for i, s in enumerate(signs):
        lo, hi = bounds[i], bounds[i + 1]
        inside = [r for r in here if lo < float(r["rate"]) < hi]
        if s > 0:
            out.append(any(float(r["cap_margin_low"]) > 0 for r in inside))
        elif s < 0:
            out.append(any(float(r["cap_margin_high"]) < 0 for r in inside))
        else:
            out.append(any(abs(float(r["cap_margin"])) < ZERO for r in inside))
    return out


SIDE = {1: "the cap saves", 0: "the cap adds nothing", -1: "the cap costs"}
NEVER = {1: "the cap saves across the whole sweep; any break-even is outside it",
         -1: "the cap costs across the whole sweep; any break-even is outside it",
         0: "the cap adds nothing across the whole sweep"}


def direction(below: int, above: int) -> str:
    return f"{SIDE[below]} below this rate, {SIDE[above]} above it"

FIELDS = ("config", "regime_name", "regime", "phi", "crossings", "crossing", "rate", "multiple",
          "direction", "resolved_below", "resolved_above", "supported",
          "sign_at_scan_low", "sign_at_scan_high", "scan_low_rate", "scan_high_rate",
          "band_low_rate", "band_high_rate", "median_attempt_cost", "evaluations")


def rows_for(pool: ev.Pool, regimes=ld.REGIMES, phi: float = 0.0,
             ladder_rows: Sequence[dict] = (), log=None) -> List[dict]:
    """One row per crossing, or one row saying there is none, for each regime."""
    mask = ev.full_draw_tasks({pool.config: pool})
    out = []
    for name, fraction in regimes:
        if log:
            log(f"  {name}")
        got = crossings(pool, fraction, phi, mask, log=log)
        low, high = band(ladder_rows, pool.config, fraction)
        found = got["crossings"]
        bounds = [got["scan_low"] * (1 - 1e-9)] + [c["rate"] for c in found] + \
                 [got["scan_high"] * (1 + 1e-9)]
        signs = [found[0]["below"] if found else got["sign_low"]] + [c["above"] for c in found]
        sides = resolved(ladder_rows, pool.config, fraction, bounds, signs) if ladder_rows else \
            [""] * len(signs)
        common = dict(config=pool.config, regime_name=name, regime=fraction, phi=phi,
                      crossings=len(found),
                      sign_at_scan_low=got["sign_low"], sign_at_scan_high=got["sign_high"],
                      scan_low_rate=got["scan_low"], scan_high_rate=got["scan_high"],
                      band_low_rate="" if low is None else low,
                      band_high_rate="" if high is None else high,
                      median_attempt_cost=got["median_attempt_cost"],
                      evaluations=got["evaluations"])
        if not found:
            out.append(dict(common, crossing=0, rate="", multiple="",
                            direction=NEVER[got["sign_low"]], resolved_below=sides[0],
                            resolved_above="", supported=""))
            if log:
                log(f"    no crossing: {NEVER[got['sign_low']]}"
                    + ("" if sides[0] == "" else f" (resolved: {sides[0]})"))
            continue
        for i, c in enumerate(found, 1):
            below, above = sides[i - 1], sides[i]
            supported = "" if "" in (below, above) else bool(below and above)
            out.append(dict(common, crossing=i, rate=c["rate"], multiple=c["multiple"],
                            direction=direction(c["below"], c["above"]),
                            resolved_below=below, resolved_above=above, supported=supported))
            if log:
                log(f"    crossing {i}: ${c['rate']:.2f}/h = {c['multiple']:.2f}x median attempt"
                    f" cost, {direction(c['below'], c['above'])}"
                    + ("" if supported == "" else
                       ("  [supported]" if supported else "  [within noise]")))
    return out


def write(rows, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in FIELDS})
    return path


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derived", default="data/derived")
    ap.add_argument("--notes", default="configurations_notes.json")
    ap.add_argument("--ladder", default="results/ladder.csv",
                    help="the sweep, for the band of rates where the interval covers zero")
    ap.add_argument("--out", default="results/breakeven.csv")
    ap.add_argument("--phi", type=float, default=0.0)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    ladder_rows = []
    if a.ladder and os.path.exists(a.ladder):
        with open(a.ladder, newline="") as fh:
            ladder_rows = list(csv.DictReader(fh))
    rows = []
    for folder in ld.configurations(a.derived, a.notes, a.only):
        pool = ev.load(folder)
        print(f"{os.path.basename(folder.rstrip('/'))}: {pool.n_tasks} tasks", flush=True)
        rows += rows_for(pool, phi=a.phi, ladder_rows=ladder_rows,
                         log=None if a.quiet else (lambda line: print(line, flush=True)))
    print(f"\n{len(rows)} rows -> {write(rows, a.out)}")


if __name__ == "__main__":
    _main()
