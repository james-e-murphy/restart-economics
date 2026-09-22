"""The fitted steps' intervals at the primary's replicate count (PLAN.md Section 5).

The ladder gives steps iii-b, iv and the transfer their intervals from 100 replicates, because a
replicate refits the schedule search and the state rule's two models inside every fold, which is
far dearer than re-scoring a fixed policy. The plan asks for 1,000 replicates where the cost can
be borne, and reads the primary transfer's resolution off these intervals, so this recomputes the
three intervals at any count: in the automated regime at $25, $100 and $300 an hour, on the same
task resamples as the ladder (the first 100 of 1,000 are the ladder's 100, since the resamples
are drawn in order from one seed), with every replicate fitting each family once and reading all
three margins from the fits. Point estimates are recomputed and must equal the ladder's; a
difference is a bug. The intervals are written into results/ladder.csv in place, and the count
into its ``fitted_replicates`` column, so that every exhibit reads them from where it always has.

    python -m restart.fitted --derived data/derived --replicates 1000
"""
from __future__ import annotations

import csv
import os
import time
from typing import Dict, List, Optional, Sequence

import numpy as np

from . import evaluate as ev
from . import inference as inf
from . import ladder as ld
from . import policies as po
from . import schedules as sc
from . import state as st

REPLICATES = inf.REPLICATES
MARGINS = ("schedule_margin", "state_margin", "transfer_margin")


def refine(pool: ev.Pool, source: Dict[str, ev.Pool], others: Sequence[str],
           rates: Sequence[float] = ld.FITTED_RATES, replicates: int = REPLICATES,
           seed: int = inf.SEED, phi: float = 0.0, log=None) -> List[dict]:
    """One configuration: the three fitted margins and their intervals at each rate, automated
    verifier, on the four-draw tasks, from one bootstrap that fits every family once per
    replicate."""
    mask = ev.full_draw_tasks({pool.config: pool})
    label = inf.folds(pool.n_tasks)
    tab = sc.table(pool)
    ks = tuple(range(1, po.MAX_ATTEMPTS + 1))
    size = 5 * (replicates + 1) + 8
    cache: dict = {}
    moved_cache: dict = {}
    rows = []
    for rate in rates:
        t0 = time.time()
        outside = ev.outside_option(pool, rate)
        verify = ev.verification(outside, 0.0)
        capped = ld._family(pool, po.constant_family(pool.config, pool.grid, ks),
                            outside, verify, phi, mask)
        sched = sc.family(pool, outside, verify, phi, ks, tab=tab, mask=mask,
                          start=sc.constant_start(capped, tab, ks))
        rule = st.family(pool, outside, verify, phi, ks, mask=mask, cache=cache, cache_size=size)
        moved = st.family(pool, outside, verify, phi, ks, source=source, source_configs=others,
                          mask=mask, cache=moved_cache, cache_size=size)
        point = {k: inf.cross_fit(f, label, mask).value
                 for k, f in (("iii", capped), ("iiib", sched), ("iv", rule), ("iv_transfer", moved))}

        def statistic(idx):
            v = {k: inf.cross_fitted_value(f, idx, mask)
                 for k, f in (("iii", capped), ("iiib", sched), ("iv", rule),
                              ("iv_transfer", moved))}
            return (v["iii"] - v["iiib"], v["iiib"] - v["iv"], v["iiib"] - v["iv_transfer"])

        bands = inf.bootstrap_many(pool.n_tasks, statistic, replicates=replicates, seed=seed)
        row = dict(config=pool.config, regime_name="automated", axis="rate", rate=float(rate),
                   value_iii=point["iii"], value_iiib=point["iiib"], value_iv=point["iv"],
                   value_iv_transfer=point["iv_transfer"],
                   schedule_margin=point["iii"] - point["iiib"],
                   state_margin=point["iiib"] - point["iv"],
                   transfer_margin=point["iiib"] - point["iv_transfer"],
                   fitted_replicates=min(b["replicates"] for b in bands),
                   dropped=max(b["dropped"] for b in bands))
        for name, b in zip(MARGINS, bands):
            row[f"{name}_low"], row[f"{name}_high"] = b["low"], b["high"]
        rows.append(row)
        if log:
            log(f"  ${rate:4.0f}/h  " + "  ".join(
                f"{n.split('_')[0]} {row[n]:+.3f} [{row[n + '_low']:+.2f}, {row[n + '_high']:+.2f}]"
                for n in MARGINS) + f"  ({row['fitted_replicates']} replicates, "
                f"{time.time() - t0:.0f} s)")
    return rows


def merge(ladder_rows: List[dict], refined: Sequence[dict], tolerance: float = 1e-6) -> int:
    """Write the refined intervals into the ladder's rows, in place, after checking that the
    point estimates agree; returns how many rows changed."""
    by = {(r["config"], r["regime_name"], r["axis"], float(r["rate"])): r for r in refined}
    changed = 0
    for row in ladder_rows:
        key = (row["config"], row["regime_name"], row["axis"], float(row["rate"]))
        new = by.get(key)
        if new is None:
            continue
        for k in ("value_iiib", "value_iv", "value_iv_transfer"):
            if abs(float(row[k]) - new[k]) > tolerance:
                raise AssertionError(f"{key}: {k} {row[k]} in the ladder, {new[k]} refitted")
        for name in MARGINS:
            row[f"{name}_low"], row[f"{name}_high"] = new[f"{name}_low"], new[f"{name}_high"]
        row["fitted_replicates"] = new["fitted_replicates"]
        changed += 1
    return changed


def read(path: str) -> List[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derived", default="data/derived")
    ap.add_argument("--notes", default="configurations_notes.json")
    ap.add_argument("--ladder", default="results/ladder.csv", help="the file to refine in place")
    ap.add_argument("--replicates", type=int, default=REPLICATES)
    ap.add_argument("--rates", nargs="*", type=float, default=list(ld.FITTED_RATES))
    ap.add_argument("--only", nargs="*", help="configuration folder names")
    a = ap.parse_args(argv)
    say = (lambda line: print(line, flush=True))
    ladder_rows = read(a.ladder)
    pools = {os.path.basename(f.rstrip("/")): ev.load(f)
             for f in ld.configurations(a.derived, a.notes)}
    refined: List[dict] = []
    started = time.time()
    names = [n for n in pools if not a.only or n in a.only]
    for i, name in enumerate(names):
        pool = pools[name]
        others = [c for c in pools if c != name]
        source = {c: ev.reindex(pools[c], pool.tasks) for c in others}
        say(f"{name}: {a.replicates} replicates of the fitted steps, automated verifier")
        refined += refine(pool, source, others, a.rates, a.replicates, log=say)
        changed = merge(ladder_rows, refined)
        ld.write(ladder_rows, a.ladder)
        elapsed = time.time() - started
        say(f"  {changed} rows of {a.ladder} carry the refined intervals; {elapsed / 60:.0f} min so"
            f" far, about {elapsed / (i + 1) * (len(names) - i - 1) / 60:.0f} min to go")


if __name__ == "__main__":
    _main()
