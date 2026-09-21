"""The diagnostics PLAN.md Section 7 puts beside the results they explain.

Per configuration, on the tasks with four usable draws:

    within_task_share   the share of the variance of log spend, over attempts, that lies within
                        tasks rather than between them: how much of what an attempt costs is the
                        draw and not the task
    mixed_share         the share of tasks whose four draws neither all resolve nor all fail,
                        beside the shares that do each

Both motivate restarts and neither bounds their value, which depends jointly on the cost and
success distributions, their dependence, the outside option, verification, K and the cutoff.

Tail composition, per configuration and decision point t, over usable attempts:

    running             the share still running at t
    spend_beyond        the share of all spend incurred after t
    resolving_beyond    of the spend incurred after t, the share by attempts that ultimately
                        resolve: what a cutoff at t would cut from successes
    resolve_if_running  the chance an attempt still running at t resolves
    over_outside_25, over_outside_100   the share of attempts still running at t whose spend has
                        already passed their own task's outside option at $25 and $100 an hour,
                        which marks where on the grid a cutoff at the annotated engineer time
                        would fall

The outcome correlation across configurations is written by ``restart.cascade``.

    python -m restart.diagnostics --derived data/derived
"""
from __future__ import annotations

import csv
import os
from typing import List, Sequence

import numpy as np

from . import evaluate as ev
from . import ladder as ld

MARK_RATES = (25.0, 100.0)


def summary(pool: ev.Pool) -> dict:
    mask = ev.full_draw_tasks({pool.config: pool})
    use = pool.usable & mask[:, None]
    y = np.log(np.maximum(pool.cost_end[mask], 1e-12))             # [task, 4]
    between = y.mean(axis=1, keepdims=True)
    total = ((y - y.mean()) ** 2).sum()
    within = ((y - between) ** 2).sum()
    wins = (pool.resolved & use)[mask].sum(axis=1)
    n = int(mask.sum())
    row = dict(config=pool.config, tasks=n, attempts=int(use.sum()),
               within_task_share=float(within / total) if total > 0 else float("nan"),
               mixed_share=float(((wins > 0) & (wins < 4)).mean()),
               all_fail_share=float((wins == 0).mean()), all_resolve_share=float((wins == 4).mean()),
               resolve_rate=float((pool.resolved & use).sum() / use.sum()),
               median_attempt_cost=ev.median_attempt_cost(pool, mask),
               mean_outside_hours=ev.mean_outside_hours(pool, mask))
    for rate in MARK_RATES:
        h = ev.outside_option(pool, rate)[:, None]
        row[f"over_outside_{rate:.0f}"] = float((pool.cost_end > h)[use].mean())
    return row


def tail(pool: ev.Pool) -> List[dict]:
    mask = ev.full_draw_tasks({pool.config: pool})
    use = pool.usable & mask[:, None]
    end = pool.cost_end[use]
    won = pool.resolved[use]
    total = end.sum()
    rows = []
    for j, t in enumerate(pool.grid):
        at = pool.cost_grid[:, :, j][use]
        alive = pool.alive[:, :, j][use]
        beyond = np.maximum(end - at, 0.0)
        row = dict(config=pool.config, cutoff=t, running=float(alive.mean()),
                   spend_beyond=float(beyond.sum() / total),
                   resolving_beyond=float(beyond[won].sum() / beyond.sum())
                   if beyond.sum() > 0 else float("nan"),
                   resolve_if_running=float(won[alive].mean()) if alive.any() else float("nan"))
        for rate in MARK_RATES:
            h = np.broadcast_to(ev.outside_option(pool, rate)[:, None], use.shape)[use]
            row[f"over_outside_{rate:.0f}"] = (float((at[alive] > h[alive]).mean())
                                               if alive.any() else float("nan"))
        rows.append(row)
    return rows


SUMMARY_FIELDS = ("config", "tasks", "attempts", "within_task_share", "mixed_share",
                  "all_fail_share", "all_resolve_share", "resolve_rate", "median_attempt_cost",
                  "mean_outside_hours") + tuple(f"over_outside_{r:.0f}" for r in MARK_RATES)
TAIL_FIELDS = ("config", "cutoff", "running", "spend_beyond", "resolving_beyond",
               "resolve_if_running") + tuple(f"over_outside_{r:.0f}" for r in MARK_RATES)


def write(rows: Sequence[dict], path: str, fields: Sequence[str]) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return path


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derived", default="data/derived")
    ap.add_argument("--notes", default="configurations_notes.json")
    ap.add_argument("--out-dir", default="results")
    a = ap.parse_args(argv)
    rows, tails = [], []
    for folder in ld.configurations(a.derived, a.notes):
        pool = ev.load(folder)
        r = summary(pool)
        rows.append(r)
        tails += tail(pool)
        print(f"{pool.config}: within-task share of log-spend variance {r['within_task_share']:.2f},"
              f" mixed outcomes {r['mixed_share']:.2f} (all fail {r['all_fail_share']:.2f},"
              f" all resolve {r['all_resolve_share']:.2f}), attempts past their outside option"
              f" at $25/h {r['over_outside_25']:.4f}", flush=True)
    print(write(rows, os.path.join(a.out_dir, "diagnostics.csv"), SUMMARY_FIELDS))
    print(write(tails, os.path.join(a.out_dir, "tail_composition.csv"), TAIL_FIELDS))


if __name__ == "__main__":
    _main()
