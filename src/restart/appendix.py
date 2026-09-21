"""The appendix displays of PLAN.md Section 7 that re-read the ladder rather than add a policy.

    difficulty     the cap's marginal value by difficulty bucket, every policy choosing within the
                   bucket: ex-ante task information admitted to all of them at once. The two
                   longest buckets are shown together, because the longest holds about five tasks,
                   too few for a training fold to choose a policy on.
    distribution   the median and 95th percentile of cost per incoming task under the policies
                   steps i to iii-b choose on mean cost, because a cap is partly insurance and the
                   mean alone undervalues it; and the median-cost version of the primary
                   comparison, steps ii and iii each chosen and scored on median cost.
    spread         on the cascade's common tasks, how far apart the configurations are against how
                   far apart the policies within a configuration are: whether choosing the
                   configuration or the policy moves cost more.

A quantile of cost per incoming task is taken over tasks and, within a task, over the orderings
of its draws that the policy can use, each task weighing the same: the distribution of what the
next task will cost. It is the lower quantile, the smallest cost at which the cumulative weight
reaches the level, so it is always a cost some task and ordering actually incurs.

    python -m restart.appendix --derived data/derived
"""
from __future__ import annotations

import csv
import os
import re
from typing import Dict, List, Sequence

import numpy as np

from . import evaluate as ev
from . import inference as inf
from . import ladder as ld
from . import policies as po
from . import schedules as sc
from . import sensitivity as se

KS = tuple(range(1, po.MAX_ATTEMPTS + 1))
BUCKETS = (("under 15 minutes", (ev.MINUTES["<15 min fix"],)),
           ("15 minutes to 1 hour", (ev.MINUTES["15 min - 1 hour"],)),
           ("1 hour or more", (ev.MINUTES["1-4 hours"], ev.MINUTES[">4 hours"])))


# ----------------------------------------------------------------------------- quantiles

def weights(valid: np.ndarray, tasks: np.ndarray) -> np.ndarray:
    """[combination, task]: each scored task weighs the same, split over its usable combinations."""
    here = valid & np.asarray(tasks, bool)[None, :]
    n = here.sum(axis=0)
    w = np.where(here, 1.0 / np.maximum(n, 1)[None, :], 0.0)
    total = w.sum()
    return w / total if total > 0 else w


def quantile(cost: np.ndarray, w: np.ndarray, q: float) -> float:
    keep = w > 0
    x, wt = cost[keep], w[keep]
    if not x.size:
        return float("nan")
    order = np.argsort(x, kind="mergesort")
    cum = np.cumsum(wt[order])
    cum /= cum[-1]
    return float(x[order][min(np.searchsorted(cum, q - 1e-12), len(x) - 1)])


def _policy(pool: ev.Pool, label: str) -> po.Policy:
    """The fixed policy a fold chose, read back from its label."""
    body = label.split(": ", 1)[-1]
    m = re.match(r"(\d+) attempts on schedule (.+)$", body)
    if m:
        cuts = [None if c == "none" else int(c) for c in m.group(2).split(",")]
        return po.schedule(pool.config, cuts)
    m = re.match(r"(\d+) attempts at (\S+) cutoff$", body)
    if m:
        return po.constant(pool.config, None if m.group(2) == "no" else int(m.group(2)),
                           int(m.group(1)))
    m = re.match(r"(\d+) attempts, no cutoff$", body)
    if m:
        return po.retry(pool.config, int(m.group(1)))
    if body == "one attempt":
        return po.single(pool.config)
    raise ValueError(f"not a fixed policy: {label!r}")


def held_out(pool: ev.Pool, got: inf.CrossFitted, label: np.ndarray, mask: np.ndarray,
             outside: np.ndarray, verify: np.ndarray, phi: float, k: int = inf.FOLDS):
    """The costs each fold's chosen policy incurs on that fold's held-out tasks, pooled over the
    folds: (cost, weight), both [combination, task], weights summing to one."""
    costs, ws = [], []
    for f, name in enumerate(got.choices):
        policy = _policy(pool, name)
        cost, valid = ev.replay({pool.config: pool}, policy, outside, verify, phi)
        test = (label == f) & mask & got.scored
        costs.append(cost)
        ws.append(weights(valid, test) * test.sum())
    width = max(c.shape[0] for c in costs)
    cost = np.vstack([np.pad(c, ((0, width - c.shape[0]), (0, 0))) for c in costs])
    w = np.vstack([np.pad(x, ((0, width - x.shape[0]), (0, 0))) for x in ws])
    return cost, w / w.sum()


# ----------------------------------------------------------------------------- distribution

def median_choice(pool: ev.Pool, policies: Sequence[po.Policy], outside: np.ndarray,
                  verify: np.ndarray, phi: float, label: np.ndarray, mask: np.ndarray,
                  k: int = inf.FOLDS) -> float:
    """A family chosen on the training folds by median cost and scored by the median of the
    held-out costs, the folds pooled: the median-cost version of cross-fitting."""
    replays = [ev.replay({pool.config: pool}, p, outside, verify, phi) for p in policies]
    costs, ws = [], []
    for f in range(k):
        train = (label != f) & mask
        test = (label == f) & mask
        medians = [quantile(c, weights(v, train), 0.5) for c, v in replays]
        pick = int(np.nanargmin(medians))
        c, v = replays[pick]
        costs.append(c)
        ws.append(weights(v, test) * (v & test[None, :]).any(axis=0).sum())
    width = max(c.shape[0] for c in costs)
    cost = np.vstack([np.pad(c, ((0, width - c.shape[0]), (0, 0))) for c in costs])
    w = np.vstack([np.pad(x, ((0, width - x.shape[0]), (0, 0))) for x in ws])
    return quantile(cost, w / w.sum(), 0.5)


STEPS = ("i", "ii", "iii", "iiib")


def distribution_cell(pool: ev.Pool, rate: float, fraction: float, phi: float,
                      mask: np.ndarray, label: np.ndarray, tab: sc.Table) -> dict:
    outside = ev.outside_option(pool, rate)
    verify = ev.verification(outside, fraction)
    single = [po.single(pool.config)]
    retry = [po.retry(pool.config, k) for k in KS]
    constant = list(po.constant_family(pool.config, pool.grid, KS))
    fams = dict(i=ld._family(pool, single, outside, verify, phi, mask),
                ii=ld._family(pool, retry, outside, verify, phi, mask),
                iii=ld._family(pool, constant, outside, verify, phi, mask))
    fams["iiib"] = sc.family(pool, outside, verify, phi, KS, tab=tab, mask=mask,
                             start=sc.constant_start(fams["iii"], tab, KS))
    row = dict(config=pool.config, rate=rate, regime=fraction, phi=phi,
               multiple=ev.multiple_for_rate(pool, rate, mask))
    for step, fam in fams.items():
        got = inf.cross_fit(fam, label, mask)
        cost, w = held_out(pool, got, label, mask, outside, verify, phi)
        row[f"mean_{step}"] = float((cost * w).sum())
        row[f"value_{step}"] = got.value
        row[f"median_{step}"] = quantile(cost, w, 0.5)
        row[f"p95_{step}"] = quantile(cost, w, 0.95)
    row["tasks"] = int(inf.cross_fit(fams["i"], label, mask).n_tasks)
    row["cap_margin_p95"] = row["p95_ii"] - row["p95_iii"]
    row["median_ii_by_median"] = median_choice(pool, retry, outside, verify, phi, label, mask)
    row["median_iii_by_median"] = median_choice(pool, constant, outside, verify, phi, label, mask)
    row["cap_margin_median"] = row["median_ii_by_median"] - row["median_iii_by_median"]
    return row


DISTRIBUTION_FIELDS = (("config", "regime_name", "regime", "rate", "multiple", "phi", "tasks")
                       + tuple(f"{x}_{s}" for x in ("value", "median", "p95") for s in STEPS)
                       + ("cap_margin_p95", "median_ii_by_median", "median_iii_by_median",
                          "cap_margin_median"))


def distribution_rows(pool: ev.Pool, rates: Sequence[float] = ld.RATES, regimes=ld.REGIMES,
                      phi: float = 0.0) -> List[dict]:
    mask = ev.full_draw_tasks({pool.config: pool})
    label = inf.folds(pool.n_tasks)
    tab = sc.table(pool)
    rows = []
    for name, fraction in regimes:
        for rate in rates:
            row = distribution_cell(pool, rate, fraction, phi, mask, label, tab)
            row["regime_name"] = name
            # the pooled held-out mean is the cross-fitted value; a difference is a bug
            for s in STEPS:
                if not np.isclose(row[f"mean_{s}"], row[f"value_{s}"], rtol=1e-9, atol=1e-9):
                    raise AssertionError(f"{pool.config} {name} ${rate}: step {s} held-out mean "
                                         f"{row[f'mean_{s}']} against {row[f'value_{s}']}")
            rows.append(row)
    return rows


# ----------------------------------------------------------------------------- difficulty

def bucket_masks(pool: ev.Pool) -> Dict[str, np.ndarray]:
    return {name: np.isin(pool.minutes, minutes) for name, minutes in BUCKETS}


DIFFICULTY_FIELDS = ("config", "bucket", "regime_name", "regime", "rate", "multiple", "tasks",
                     "value_ii", "value_iii", "cap_margin", "cap_margin_low", "cap_margin_high",
                     "replicates", "choice_ii", "choice_iii")


def difficulty_rows(pool: ev.Pool, rates: Sequence[float] = ld.RATES, regimes=ld.REGIMES,
                    replicates: int = inf.REPLICATES, phi: float = 0.0) -> List[dict]:
    """The cap's margin within each bucket, every policy choosing within it, with its interval;
    then every bucket's choices pooled, the value of admitting the bucket to every policy, beside
    the primary's blind choice. ``multiple`` is on the configuration's whole scored set, so that
    rows compare across buckets."""
    full = ev.full_draw_tasks({pool.config: pool})
    rows = []
    pooled: Dict[tuple, dict] = {}
    for bucket, inside in bucket_masks(pool).items():
        mask = full & inside
        if mask.sum() < inf.FOLDS * 2:
            continue
        bands = {(b["regime_name"], b["rate"]): b
                 for b in se.cap_intervals(pool, replicates, phi=phi, mask=mask, regimes=regimes,
                                           rates=rates, multiples=(), stage_two=False)}
        for name, fraction in regimes:
            for rate in rates:
                r = ld.rung(pool, rate, fraction, phi, replicates=0, mask=mask, steps=())
                b = bands[(name, rate)]
                rows.append(dict(config=pool.config, bucket=bucket, regime_name=name,
                                 regime=fraction, rate=rate,
                                 multiple=ev.multiple_for_rate(pool, rate, full),
                                 tasks=r["tasks"], value_ii=r["value_ii"],
                                 value_iii=r["value_iii"], cap_margin=r["cap_margin"],
                                 cap_margin_low=b["one_stage_low"],
                                 cap_margin_high=b["one_stage_high"],
                                 replicates=b["one_stage_replicates"],
                                 choice_ii=r["choice_ii"], choice_iii=r["choice_iii"]))
                acc = pooled.setdefault((name, fraction, rate), dict(n=0, ii=0.0, iii=0.0))
                acc["n"] += r["tasks"]
                acc["ii"] += r["tasks"] * r["value_ii"]
                acc["iii"] += r["tasks"] * r["value_iii"]
    for (name, fraction, rate), acc in pooled.items():
        blind = ld.rung(pool, rate, fraction, phi, replicates=0, mask=full, steps=())
        for bucket, ii, iii, n in (("all, chosen within bucket", acc["ii"] / acc["n"],
                                    acc["iii"] / acc["n"], acc["n"]),
                                   ("all, chosen blind", blind["value_ii"], blind["value_iii"],
                                    blind["tasks"])):
            rows.append(dict(config=pool.config, bucket=bucket, regime_name=name,
                             regime=fraction, rate=rate,
                             multiple=ev.multiple_for_rate(pool, rate, full), tasks=n,
                             value_ii=ii, value_iii=iii, cap_margin=ii - iii))
    return rows


# ----------------------------------------------------------------------------- spread

def spread_rows(pools: Dict[str, ev.Pool], rates: Sequence[float] = ld.RATES,
                regimes=ld.REGIMES, phi: float = 0.0) -> List[dict]:
    """On the cascade's common tasks: the range across configurations of their best policy's
    value and of their one-attempt value, against the range across the policies within each
    configuration, steps i to iii-b."""
    aligned = ev.align(pools)
    names = tuple(aligned)
    mask = ev.full_draw_tasks(aligned, names)
    tabs = {c: sc.table(aligned[c]) for c in names}
    rows = []
    for name, fraction in regimes:
        for rate in rates:
            values = {}
            for c in names:
                r = ld.rung(aligned[c], rate, fraction, phi, replicates=0, mask=mask,
                            tab=tabs[c], steps=("iii-b",))
                values[c] = [r["value_i"], r["value_ii"], r["value_iii"], r["value_iiib"]]
            best = {c: min(v) for c, v in values.items()}
            one = {c: v[0] for c, v in values.items()}
            within = {c: max(v) - min(v) for c, v in values.items()}
            row = dict(regime_name=name, regime=fraction, rate=rate, phi=phi,
                       tasks=int(mask.sum()),
                       across_best=max(best.values()) - min(best.values()),
                       across_one=max(one.values()) - min(one.values()),
                       within_median=float(np.median(list(within.values()))),
                       within_max=max(within.values()),
                       cheapest=min(best, key=best.get), dearest=max(best, key=best.get))
            row.update({f"best_{c}": best[c] for c in names})
            row.update({f"within_{c}": within[c] for c in names})
            rows.append(row)
    return rows


def spread_fields(names: Sequence[str]):
    return (("regime_name", "regime", "rate", "phi", "tasks", "across_best", "across_one",
             "within_median", "within_max", "cheapest", "dearest")
            + tuple(f"best_{c}" for c in names) + tuple(f"within_{c}" for c in names))


# ----------------------------------------------------------------------------- output

def write(rows: Sequence[dict], path: str, fields: Sequence[str]) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields))
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})
    return path


PARTS = ("difficulty", "distribution", "spread")


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derived", default="data/derived")
    ap.add_argument("--notes", default="configurations_notes.json")
    ap.add_argument("--out-dir", default="results")
    ap.add_argument("--parts", nargs="*", default=list(PARTS), choices=PARTS)
    ap.add_argument("--replicates", type=int, default=inf.REPLICATES)
    ap.add_argument("--rates", nargs="*", type=float, default=list(ld.RATES))
    a = ap.parse_args(argv)
    pools = {os.path.basename(f.rstrip("/")): ev.load(f)
             for f in ld.configurations(a.derived, a.notes)}
    out = lambda part: os.path.join(a.out_dir, f"{part}.csv")          # noqa: E731
    if "difficulty" in a.parts:
        rows = []
        for name, pool in pools.items():
            rows += difficulty_rows(pool, a.rates, replicates=a.replicates)
            write(rows, out("difficulty"), DIFFICULTY_FIELDS)
            here = [r for r in rows if r["config"] == name and r["rate"] == 100.0
                    and r["regime_name"] in ("automated", "human 0.5")]
            print(f"{name}: cap's saving at $100/h by bucket  " + "  ".join(
                f"{r['regime_name']} {r['bucket']} {r['cap_margin']:+.3f}" for r in here),
                flush=True)
    if "distribution" in a.parts:
        rows = []
        for name, pool in pools.items():
            rows += distribution_rows(pool, a.rates)
            write(rows, out("distribution"), DISTRIBUTION_FIELDS)
            here = [r for r in rows if r["config"] == name and r["rate"] == 100.0]
            print(f"{name}: at $100/h, p95 of ii and iii, and the median-cost cap margin  " +
                  "  ".join(f"{r['regime_name']} {r['p95_ii']:.2f}/{r['p95_iii']:.2f}"
                            f" {r['cap_margin_median']:+.3f}" for r in here), flush=True)
    if "spread" in a.parts and len(pools) > 1:
        rows = spread_rows(pools, a.rates)
        write(rows, out("spread"), spread_fields(tuple(pools)))
        for r in rows:
            if r["rate"] in (25.0, 100.0, 300.0):
                print(f"  {r['regime_name']:10s} ${r['rate']:4.0f}/h  across configurations"
                      f" {r['across_best']:7.2f}  within, median {r['within_median']:7.2f}"
                      f"  max {r['within_max']:7.2f}", flush=True)


if __name__ == "__main__":
    _main()
