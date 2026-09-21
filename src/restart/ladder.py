"""The ladder of PLAN.md Section 7 across the rate sweep and both verifier regimes.

Each configuration is scored on one number, expected cost per incoming task, under:

    i      one attempt, no cutoff, then the outside option
    ii     K attempts, no cutoff                   (K chosen on the training folds)
    iii    K attempts at a constant cutoff         (K and the cutoff chosen on the training folds)
    iii-b  K attempts under a schedule of cutoffs  (searched on the training folds)
    iv     K attempts under the state rule         (its models fitted on the training folds)
    iv-t   the same rule, its two models fitted on the other configurations (the transfer)

The primary result is the cap's marginal value given retry, step ii minus step iii, written here
so that a positive number is what the cap saves. It is reported per configuration and per regime
across the sweep, with a 95 percent interval from the full-pipeline bootstrap, which redoes the
selection inside every replicate. Beside it sit the value of retry, step i minus step ii, the
value of letting the cap vary by attempt, step iii minus step iii-b, and the value of reading the
execution's state, step iii-b minus step iv. Every step is scored on the same tasks: those with
four usable draws, since comparisons across attempt budgets rest on that subset.

The sweep runs on both axes of Section 7: dollars an hour, and multiples of the configuration's
own median attempt cost, which is the same outside option expressed in units that are comparable
across configurations whose attempts differ manyfold in cost. Every row carries both.

The primary transfer (Section 7) is the rule's margin over the best schedule when its two models
are fitted on the other six configurations, with the held-out fold's tasks excluded from them too
(Section 5), and its restart values and attempt budget taken from the target's own training folds.

Steps iii-b, iv and iv-t are refitted inside each bootstrap replicate, which costs a few hundred
times what resampling a fixed family costs, so their intervals are computed on a stated subset of
the sweep and at a replicate count that is recorded in the row. The rule's models do not depend
on the rate, so within a configuration they are fitted once per training set and reused across
the sweep, replicate by replicate. Step v, the cascade, is in its own module.

One column is not in the registration and is labelled so wherever it appears: ``value_escalate``,
the cost of sending every task straight to the outside option without running the agent. The
registered ladder has no policy that declines to run the agent, so where escalation is cheap the
constant-cutoff family stands in for one by stopping every attempt at the first decision point;
this reference line shows where that is happening.
"""
from __future__ import annotations

import csv
import glob
import os
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from . import audit
from . import evaluate as ev
from . import inference as inf
from . import policies as po
from . import pricing
from . import schedules as sc
from . import state as st

RATES = (5.0, 10.0, 25.0, 50.0, 75.0, 100.0, 150.0, 200.0, 300.0)   # dollars an hour
MULTIPLES = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0, 200.0, 500.0)   # of median attempt cost
REGIMES = (("automated", 0.0), ("human 0.1", 0.1), ("human 0.3", 0.3), ("human 0.5", 0.5))

# Steps iii-b and iv are refitted inside every replicate, so their intervals are computed where
# the plan reads them: the automated-verifier regime, at three rates spanning the sweep, at a
# replicate count each row records. The point estimates are computed at every point of the sweep.
FITTED_REGIMES = ("automated",)
FITTED_RATES = (25.0, 100.0, 300.0)
FITTED_REPLICATES = 100

# the state rule's fitted models, kept per training set: five folds, and five per bootstrap
# replicate, which recur at every rate because every rung resamples from the same seed
CACHE = 5 * (FITTED_REPLICATES + 1) * 4


def _family(pool: ev.Pool, policies, outside, verify, phi, mask) -> inf.Family:
    return inf.Family.of([ev.value({pool.config: pool}, p, outside, verify, phi, mask)
                          for p in policies])


def rung(pool: ev.Pool, rate: float, fraction: float, phi: float = 0.0,
         replicates: int = inf.REPLICATES, mask: Optional[np.ndarray] = None,
         seed: int = inf.SEED, tab: Optional[sc.Table] = None,
         fitted_replicates: int = 0, steps: Sequence[str] = ("iii-b", "iv", "transfer"),
         transfer: Optional[Tuple[Dict[str, ev.Pool], Sequence[str]]] = None,
         state_cache: Optional[dict] = None, transfer_cache: Optional[dict] = None,
         label: Optional[np.ndarray] = None) -> dict:
    """One configuration at one rate in one regime: the ladder and the comparisons between rungs.

    ``transfer`` is the other configurations' pools, indexed by this configuration's tasks, and
    their names; without it the transfer step is skipped. ``label`` replaces the fold split, which
    the two-stage bootstrap needs when the pool is itself a resample."""
    outside = ev.outside_option(pool, rate)
    verify = ev.verification(outside, fraction)
    if mask is None:
        mask = ev.full_draw_tasks({pool.config: pool})
    label = inf.folds(pool.n_tasks) if label is None else np.asarray(label)
    tab = tab if tab is not None else sc.table(pool)
    ks = tuple(range(1, po.MAX_ATTEMPTS + 1))

    one = _family(pool, [po.single(pool.config)], outside, verify, phi, mask)
    retry = _family(pool, [po.retry(pool.config, k) for k in ks], outside, verify, phi, mask)
    capped = _family(pool, po.constant_family(pool.config, pool.grid, ks),
                     outside, verify, phi, mask)

    scored = {"i": inf.cross_fit(one, label, mask),
              "ii": inf.cross_fit(retry, label, mask),
              "iii": inf.cross_fit(capped, label, mask)}
    # in sample the capped family cannot lose: it contains the uncapped policies. A negative
    # figure here would be a bug, not a finding; a negative cross-fitted margin is the finding.
    floor = inf.in_sample(retry, mask)[0] - inf.in_sample(capped, mask)[0]
    interval = inf.bootstrap(pool.n_tasks,
                             lambda idx: inf.margin(retry, capped, idx, mask),
                             replicates=replicates, seed=seed)
    row = dict(
        config=pool.config, rate=rate, regime=fraction, phi=phi,
        multiple=ev.multiple_for_rate(pool, rate, mask),
        tasks=scored["i"].n_tasks,
        value_i=scored["i"].value, value_ii=scored["ii"].value, value_iii=scored["iii"].value,
        value_iiib="", value_iv="", value_iv_transfer="",
        # not registered: every task straight to the outside option, the agent never run
        value_escalate=float(outside[scored["i"].scored].mean()),
        retry_value=scored["i"].value - scored["ii"].value,
        cap_margin=scored["ii"].value - scored["iii"].value,
        cap_margin_in_sample=floor,
        cap_margin_low=interval["low"], cap_margin_high=interval["high"],
        schedule_margin="", schedule_margin_low="", schedule_margin_high="",
        state_margin="", state_margin_low="", state_margin_high="",
        transfer_margin="", transfer_margin_low="", transfer_margin_high="",
        replicates=interval["replicates"], dropped=interval["dropped"],
        fitted_replicates=0,
        choice_ii="|".join(sorted(set(scored["ii"].choices))),
        choice_iii="|".join(sorted(set(scored["iii"].choices))),
        choice_iiib="", choice_iv="", choice_iv_transfer="", state_notes="",
        transfer_notes="",
        median_attempt_cost=ev.median_attempt_cost(pool, mask),
    )

    if "iii-b" in steps:
        sched = sc.family(pool, outside, verify, phi, ks, tab=tab, mask=mask,
                          start=sc.constant_start(capped, tab, ks))
        got = inf.cross_fit(sched, label, mask)
        row.update(value_iiib=got.value, schedule_margin=scored["iii"].value - got.value,
                   choice_iiib="|".join(sorted(set(got.choices))))
        if fitted_replicates:
            band = inf.bootstrap(pool.n_tasks,
                                 lambda idx: inf.margin(capped, sched, idx, mask),
                                 replicates=fitted_replicates, seed=seed)
            row.update(schedule_margin_low=band["low"], schedule_margin_high=band["high"],
                       fitted_replicates=band["replicates"])

    if "iv" in steps:
        notes: list = []
        rule = st.family(pool, outside, verify, phi, ks, mask=mask, notes=notes,
                         cache=state_cache, cache_size=CACHE)
        got = inf.cross_fit(rule, label, mask)
        row.update(value_iv=got.value, choice_iv="|".join(sorted(set(got.choices))),
                   state_notes="; ".join(sorted(set(notes))))
        if row["value_iiib"] != "":
            row["state_margin"] = row["value_iiib"] - got.value
        if fitted_replicates and "iii-b" in steps:
            band = inf.bootstrap(pool.n_tasks,
                                 lambda idx: inf.margin(sched, rule, idx, mask),
                                 replicates=fitted_replicates, seed=seed)
            row.update(state_margin_low=band["low"], state_margin_high=band["high"],
                       fitted_replicates=band["replicates"])

    if "transfer" in steps and transfer is not None and transfer[1]:
        source, names = transfer
        notes = []
        moved = st.family(pool, outside, verify, phi, ks, source=source, source_configs=names,
                          mask=mask, notes=notes, cache=transfer_cache, cache_size=CACHE)
        got = inf.cross_fit(moved, label, mask)
        row.update(value_iv_transfer=got.value,
                   choice_iv_transfer="|".join(sorted(set(got.choices))),
                   transfer_notes="; ".join(sorted(set(notes))))
        if row["value_iiib"] != "":
            row["transfer_margin"] = row["value_iiib"] - got.value
        if fitted_replicates and "iii-b" in steps:
            band = inf.bootstrap(pool.n_tasks,
                                 lambda idx: inf.margin(sched, moved, idx, mask),
                                 replicates=fitted_replicates, seed=seed)
            row.update(transfer_margin_low=band["low"], transfer_margin_high=band["high"],
                       fitted_replicates=band["replicates"])
    return row


def _short(choices: str) -> str:
    """The cutoffs and budgets the folds chose, without the prose of the labels."""
    out = []
    for c in choices.split("|"):
        c = c.split(": ", 1)[-1]
        out.append(c.replace(" attempts on schedule ", "x@").replace(" attempts at ", "x@")
                   .replace(" attempts", "x").replace(" cutoff", "")
                   .replace("state rule, ", "").replace("no cutoff", "none"))
    return ",".join(out)


def _points(pool: ev.Pool, rates: Sequence[float], multiples: Sequence[float],
            mask: np.ndarray):
    """The sweep: every rate on the dollar axis, then the rate each multiple of the median attempt
    cost implies. A row's axis says which grid put it there; both units are recorded either way."""
    got = [("rate", float(r)) for r in rates]
    got += [("multiple", ev.rate_for_multiple(pool, float(m), mask)) for m in multiples]
    return got


def ladder(pool: ev.Pool, rates: Sequence[float] = RATES,
           multiples: Sequence[float] = MULTIPLES, regimes=REGIMES, phi: float = 0.0,
           replicates: int = inf.REPLICATES, seed: int = inf.SEED, log=None,
           steps: Sequence[str] = ("iii-b", "iv", "transfer"),
           fitted_replicates: int = FITTED_REPLICATES,
           fitted_regimes: Sequence[str] = FITTED_REGIMES,
           fitted_rates: Sequence[float] = FITTED_RATES,
           transfer: Optional[Tuple[Dict[str, ev.Pool], Sequence[str]]] = None,
           mask: Optional[np.ndarray] = None):
    """Every point of the sweep by every regime, for one configuration. ``mask`` replaces the tasks
    scored, the four-draw subset by default; the all-tasks sensitivity passes every task with a
    usable draw, and each policy is then scored on the tasks that can fill it."""
    mask = ev.full_draw_tasks({pool.config: pool}) if mask is None else np.asarray(mask, bool)
    tab = sc.table(pool)
    cache: dict = {}
    moved: dict = {}
    rows = []
    for name, fraction in regimes:
        for axis, rate in _points(pool, rates, multiples, mask):
            wanted = name in fitted_regimes and axis == "rate" and rate in tuple(fitted_rates)
            row = rung(pool, rate, fraction, phi, replicates, mask, seed, tab,
                       fitted_replicates=fitted_replicates if wanted else 0, steps=steps,
                       transfer=transfer, state_cache=cache, transfer_cache=moved)
            row["regime_name"], row["axis"] = name, axis
            rows.append(row)
            if log:
                log(_line(row))
    return rows


def _num(x, width=9, places=2):
    return f"{x:{width}.{places}f}" if isinstance(x, float) else " " * (width - 1) + "-"


def _line(row: dict) -> str:
    unit = (f"${row['rate']:6.0f}/h" if row["axis"] == "rate"
            else f"{row['multiple']:7.1f}x ")
    out = (f"  {row['regime_name']:10s} {unit}  i {_num(row['value_i'])}"
           f"  ii {_num(row['value_ii'])}  iii {_num(row['value_iii'])}"
           f"  iii-b {_num(row['value_iiib'])}  iv {_num(row['value_iv'])}"
           f"  iv-t {_num(row['value_iv_transfer'])}  esc {_num(row['value_escalate'])}"
           f"  | cap {_num(row['cap_margin'], 7)}"
           f" [{_num(row['cap_margin_low'], 7)},{_num(row['cap_margin_high'], 7)}]"
           f"  sched {_num(row['schedule_margin'], 6)}  state {_num(row['state_margin'], 6)}"
           f"  transfer {_num(row['transfer_margin'], 6)}")
    if row["transfer_margin_low"] != "":
        out += (f" [{_num(row['transfer_margin_low'], 6)},"
                f"{_num(row['transfer_margin_high'], 6)}]")
    if row["axis"] == "rate":
        out += f"  | iii {_short(row['choice_iii'])}"
        if row["choice_iiib"]:
            out += f"  iii-b {_short(row['choice_iiib'])}"
    return out


FIELDS = ("config", "regime_name", "regime", "axis", "rate", "multiple", "phi", "tasks",
          "value_i", "value_ii", "value_iii", "value_iiib", "value_iv", "value_iv_transfer",
          "value_escalate", "retry_value", "cap_margin", "cap_margin_low", "cap_margin_high",
          "cap_margin_in_sample", "schedule_margin", "schedule_margin_low",
          "schedule_margin_high", "state_margin", "state_margin_low", "state_margin_high",
          "transfer_margin", "transfer_margin_low", "transfer_margin_high",
          "replicates", "dropped", "fitted_replicates", "choice_ii", "choice_iii",
          "choice_iiib", "choice_iv", "choice_iv_transfer", "state_notes", "transfer_notes",
          "median_attempt_cost")


def write(rows, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r[k] for k in FIELDS})
    return path


def configurations(derived: str, notes: str, only: Optional[Sequence[str]] = None):
    """The extraction folders to score: priced, extracted, and not excluded by the audit."""
    out = []
    kept_out = audit.excluded(notes)
    for folder in sorted(glob.glob(os.path.join(derived, "*/"))):
        name = os.path.basename(folder.rstrip("/"))
        if name not in pricing.SCHEDULES or (only and name not in only):
            continue
        if not glob.glob(os.path.join(folder, "prefix_*.csv")):
            continue
        if name in kept_out:
            print(f"{name}: excluded by the audit, not scored", flush=True)
            continue
        out.append(folder)
    return out


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--derived", default="data/derived", help="folder of per-archive folders")
    ap.add_argument("--notes", default="configurations_notes.json", help="the exclusion record")
    ap.add_argument("--out", default="results/ladder.csv")
    ap.add_argument("--replicates", type=int, default=inf.REPLICATES)
    ap.add_argument("--fitted-replicates", type=int, default=FITTED_REPLICATES,
                    help="replicates for the intervals on steps iii-b and iv; 0 for none")
    ap.add_argument("--phi", type=float, default=0.0)
    ap.add_argument("--steps", nargs="*", default=["iii-b", "iv", "transfer"],
                    help="which of the fitted steps to score")
    ap.add_argument("--only", nargs="*", help="configuration folder names")
    a = ap.parse_args(argv)
    # every included configuration is loaded before any is scored, because the transfer fits a
    # configuration's rule on all the others
    pools = {}
    for folder in configurations(a.derived, a.notes):
        name = os.path.basename(folder.rstrip("/"))
        pools[name] = ev.load(folder)
    rows = []
    for name, pool in pools.items():
        if a.only and name not in a.only:
            continue
        others = [c for c in pools if c != name]
        source = {c: ev.reindex(pools[c], pool.tasks) for c in others}
        print(f"{name}: {pool.n_tasks} tasks, {int(pool.usable.sum())} usable attempts;"
              f" transfer from {len(others)} configurations", flush=True)
        rows += ladder(pool, phi=a.phi, replicates=a.replicates, steps=a.steps,
                       fitted_replicates=a.fitted_replicates, transfer=(source, others),
                       log=lambda line: print(line, flush=True))
    print(f"\n{len(rows)} rows -> {write(rows, a.out)}")

if __name__ == "__main__":
    _main()
