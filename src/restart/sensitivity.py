"""The registered sensitivities, in one command (PLAN.md Sections 3, 5 and 10).

Each sensitivity changes one input and reruns, under it, the pipeline that produced the primary
results: the ladder with its transfer step, the break-even, and the cascade, every selection redone
on the training folds. None is a rescaling of a stored result. Policies are re-selected under the
changed input, so a price change refits the cutoffs rather than repricing the ones chosen at list
price (Section 4), and a changed outside option re-selects every budget and cutoff.

    phi 0.34, phi 0.50     a share of test-passing attempts are false accepts, and pay the outside
                           option later (Sections 3 and 10)
    common horizon 100     every configuration capped at 100 calls, an attempt still running there
                           stopped and scored as a failure (Section 10, stopping rules)
    all tasks              every task with a usable draw, not only those with four (Section 10,
                           unequal usable draws)
    refusals excluded      provider refusals leave the attempt pool (Section 10, the attempt pool)
    no verdict unresolved  an evaluation that returned no verdict is a failure, not an exclusion
    re-runs dropped        executions the harness re-ran after a crash leave the pool
    Qwen lowest price      Qwen3 Coder at the lowest third-party price for its weights (Section 10,
                           price schedules); every configuration is rescored, because Qwen's
                           attempts are among the rows the others' transfer rules are fitted on
    METR minutes           the outside option under the bucket-specific correction (Section 3)

One check that the plan did not register runs beside them, and is marked as such wherever it
appears:

    common tasks           every configuration scored on the 275 tasks with four usable draws in
                           all seven, the cascade's tasks, so that a median across configurations
                           summarizes one task set rather than seven

The ladder is scored on both axes of the sweep. The fitted steps (iii-b, iv and the transfer) are
scored on the dollar axis, as point estimates; the multiples axis carries steps i to iii, which is
what the break-even's resolution reads. The cap's margin carries its full-pipeline bootstrap
interval in every row, at the primary's 1,000 replicates.

The interval sensitivity of Section 5 is here too: the two-stage bootstrap, which resamples each
task's attempts as well as the tasks, for the cap's margin at every point of the sweep and for the
primary transfer where the ladder gives it an interval. It draws the same tasks in every replicate
as the primary interval does, from the same seed, and resamples each drawn task's usable draws with
replacement on top, so that the two intervals differ only by the second stage. A
draw drawn twice is replayed as two attempts, which is what the second stage means: the logged
draws treated as a sample of the configuration's behaviour on that task, as if more than four had
been run. For a mean over tasks, resampling at both stages counts the within-task variation twice,
once through the tasks and again through their draws, and the two-stage interval is the wider for
it. Policy value is not such a mean. A retry draws a task's attempts without replacement, so a
replicate whose task holds one draw twice prices a retry that can meet the same attempt again, and
the value of retrying, and of capping the retries, moves with it: the two-stage replicates need not
be centred where the one-stage replicates are. Both centres are written beside the intervals, so
that a shift of the interval can be told from a widening of it; neither is corrected.

Both bootstraps of the cap's margin take a faster route than the ladder's, to the same numbers.
Steps i to iii are fixed policies whose value per task is linear in the outside option and the
verification cost: what the attempts spend, what they submit for review, what they resolve and
whether all of them fail depend on neither, and a mean over tasks is then linear in the rate. So
the four coefficients are read once per replicate, summed once per fold, and every point of the
sweep is priced from the sums. That is the evaluator's arithmetic rearranged, not approximated:
the tests hold it to the evaluator on every policy and to the ladder's own interval, and every
run checks it against the ladder's point estimate on every row.

    python -m restart.sensitivity --derived data/derived
"""
from __future__ import annotations

import csv
import itertools
import os
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import breakeven as be
from . import cascade as cs
from . import evaluate as ev
from . import inference as inf
from . import ladder as ld
from . import policies as po
from . import pricing
from . import schedules as sc

REPLICATES = inf.REPLICATES                 # the cap margin's interval under each sensitivity
TWO_STAGE_REPLICATES = inf.REPLICATES       # the primary interval's count, so the two compare
TRANSFER_REPLICATES = ld.FITTED_REPLICATES  # likewise for the primary transfer
STEPS = ("iii-b", "iv", "transfer")
KS = tuple(range(1, po.MAX_ATTEMPTS + 1))
PARTS = ("ladder", "cascade", "two-stage")


# ----------------------------------------------------------------------------- the variants

@dataclass(frozen=True)
class Variant:
    """One registered sensitivity: what it changes, and where the plan registers it."""
    key: str                                    # what --variants takes
    name: str                                   # what the results files carry
    what: str
    where: str
    load: Tuple[Tuple[str, object], ...] = ()   # keyword arguments to the loader
    phi: float = 0.0
    horizon: Optional[int] = None
    all_tasks: bool = False
    qwen_price: bool = False
    metr: bool = False
    common_tasks: bool = False
    registered: bool = True                     # False: a check added after the results were in

    def load_kwargs(self) -> dict:
        kw = dict(self.load)
        if self.qwen_price:
            kw["schedules"] = {**pricing.SCHEDULES, **pricing.SENSITIVITY}
        if self.metr:
            kw["annotation_minutes"] = ev.metr_minutes()
        return kw

    @property
    def load_key(self) -> tuple:
        return (self.load, self.qwen_price, self.metr)


PRIMARY = Variant("primary", "primary", "the primary specification, for checking the runner",
                  "Sections 5 to 7")

# ordered so that the variants read from the same loaded tables are adjacent
VARIANTS = (
    Variant("phi-0.34", "phi 0.34",
            "34 percent of test-passing attempts are false accepts and pay the outside option later",
            "Sections 3 and 10", phi=0.34),
    Variant("phi-0.50", "phi 0.50",
            "half of test-passing attempts are false accepts and pay the outside option later",
            "Sections 3 and 10", phi=0.50),
    Variant("horizon", "common horizon 100",
            "every configuration capped at 100 calls; an attempt running there is a failure",
            "Section 10, stopping rules and the iteration cap", horizon=100),
    Variant("all-tasks", "all tasks",
            "every task with a usable draw, each policy scored on the tasks that can fill it",
            "Section 10, unequal usable draws", all_tasks=True),
    Variant("refusals", "refusals excluded", "provider refusals leave the attempt pool",
            "Section 10, the attempt pool", load=(("retain_refusals", False),)),
    Variant("no-verdict", "no verdict unresolved",
            "an evaluation that returned no verdict counts as a failure",
            "Section 10, the attempt pool", load=(("no_verdict_unresolved", True),)),
    Variant("reruns", "re-runs dropped", "executions the harness re-ran after a crash are dropped",
            "Section 10, the attempt pool", load=(("drop_reruns", True),)),
    Variant("qwen-price", "Qwen lowest price",
            "Qwen3 Coder at the lowest third-party price for the same weights",
            "Section 10, price schedules", qwen_price=True),
    Variant("metr", "METR minutes",
            "the outside option under the bucket-specific METR correction",
            "Section 3", metr=True),
)
# not registered: added after the registered results were in, reported as a check and marked so
CHECKS = (
    Variant("common", "common tasks",
            "every configuration scored on the tasks with four usable draws in all seven",
            "not registered", common_tasks=True, registered=False),
)
BY_KEY = {v.key: v for v in (PRIMARY,) + VARIANTS + CHECKS}


def load_pools(variant: Variant, folders: Sequence[str],
               cache: Optional[dict] = None) -> Dict[str, ev.Pool]:
    """Every included configuration's pool under the variant. ``cache`` keeps the last tables
    read, so the variants that change nothing about loading share one read."""
    if cache is not None and cache.get("key") == variant.load_key:
        pools = cache["pools"]
    else:
        kw = variant.load_kwargs()
        pools = {os.path.basename(f.rstrip("/")): ev.load(f, **kw) for f in folders}
        if cache is not None:
            cache.clear()
            cache.update(key=variant.load_key, pools=pools)
    if variant.horizon:
        pools = {c: ev.truncate(p, variant.horizon) for c, p in pools.items()}
    return pools


def basis(variant: Variant, pool: ev.Pool,
          pools: Optional[Dict[str, ev.Pool]] = None) -> np.ndarray:
    """The tasks scored: those with four usable draws, or under the all-tasks sensitivity every
    task with one, each policy then scored on the tasks that can fill it; under the common-tasks
    check, those with four usable draws in every configuration of ``pools``."""
    if variant.all_tasks:
        return pool.usable.any(axis=1)
    keep = ev.full_draw_tasks({pool.config: pool})
    if variant.common_tasks and pools:
        for c, other in pools.items():
            if c != pool.config:
                keep &= ev.full_draw_tasks({c: ev.reindex(other, pool.tasks)})
    return keep


def common_basis(variant: Variant, pools: Dict[str, ev.Pool]) -> np.ndarray:
    """The same, for pools aligned on common tasks, as the cascade reads them."""
    if variant.all_tasks:
        keep = np.zeros(next(iter(pools.values())).n_tasks, bool)
        for p in pools.values():
            keep |= p.usable.any(axis=1)
        return keep
    return ev.full_draw_tasks(pools, tuple(pools))


# ----------------------------------------------------------------------------- the ladder

def ladder_rows(variant: Variant, pools: Dict[str, ev.Pool], replicates: int = REPLICATES,
                steps: Sequence[str] = STEPS, rates: Sequence[float] = ld.RATES,
                multiples: Sequence[float] = ld.MULTIPLES, regimes=ld.REGIMES,
                scan: int = be.SCAN, only: Optional[Sequence[str]] = None, log=None):
    """The ladder and the break-even for every configuration under the variant.

    Every point estimate is the ladder's own. The cap margin's interval is the full-pipeline
    bootstrap the ladder runs, at the primary's replicate count, computed by the fast path of
    ``cap_intervals``, which is checked against the ladder's point estimate in every row."""
    rows, crossings = [], []
    for name, pool in pools.items():
        if only and name not in only:
            continue
        others = [c for c in pools if c != name]
        source = {c: ev.reindex(pools[c], pool.tasks) for c in others}
        mask = basis(variant, pool, pools)
        got = ld.ladder(pool, rates=rates, multiples=(), regimes=regimes, phi=variant.phi,
                        replicates=0, steps=steps, fitted_replicates=0,
                        transfer=(source, others), mask=mask)
        got += ld.ladder(pool, rates=(), multiples=multiples, regimes=regimes, phi=variant.phi,
                         replicates=0, steps=(), fitted_replicates=0, mask=mask)
        bands = cap_intervals(pool, replicates, phi=variant.phi, mask=mask, regimes=regimes,
                              rates=rates, multiples=multiples, stage_two=False)
        slow = attach(got, bands, pool, variant.phi, mask, replicates)
        if slow and log:
            log(f"  {name}: {slow} rows' intervals recomputed by the ladder's own bootstrap,"
                " where the fast path did not reproduce the point estimate")
        found = be.rows_for(pool, regimes=regimes, phi=variant.phi, ladder_rows=got, scan=scan,
                            mask=mask)
        for r in got + found:
            r["variant"] = variant.name
        rows += got
        crossings += found
        if log:
            log(_summary(name, got, found, regimes))
    return rows, crossings


def attach(rows: Sequence[dict], bands: Sequence[dict], pool: ev.Pool, phi: float,
           mask: np.ndarray, replicates: int) -> int:
    """Put each interval on its ladder row.

    The fast path is the ladder's arithmetic rearranged, so run on the sample itself it must
    reproduce the ladder's point estimate, and every row is checked. Where it does not, which a
    near-tie between two candidates on the training folds, broken one way by one rounding and the
    other way by the other, could cause, and so could a matrix library returning wrong products,
    the row's interval is computed by the ladder's own bootstrap instead. Returns how many rows
    that was."""
    at = {(b["regime_name"], b["axis"], b["rate"]): b for b in bands}
    slow = 0
    for r in rows:
        b = at[(r["regime_name"], r["axis"], r["rate"])]
        if np.isclose(b["fast_estimate"], r["cap_margin"], rtol=1e-9, atol=1e-9):
            r.update(cap_margin_low=b["one_stage_low"], cap_margin_high=b["one_stage_high"],
                     replicates=b["one_stage_replicates"], dropped=b["one_stage_dropped"])
            continue
        again = ld.rung(pool, r["rate"], r["regime"], phi, replicates, mask, steps=())
        r.update(cap_margin_low=again["cap_margin_low"], cap_margin_high=again["cap_margin_high"],
                 replicates=again["replicates"], dropped=again["dropped"])
        slow += 1
    return slow


def _summary(config: str, rows: Sequence[dict], found: Sequence[dict], regimes) -> str:
    """One line per configuration: its break-evens in multiples of the median attempt cost, a star
    where both sides are resolved, and the two primary margins at $100 an hour."""
    parts = []
    for name, _ in regimes:
        here = [r for r in found if r["regime_name"] == name]
        if not here:
            continue
        if here[0]["crossing"] == 0:
            sign = {1: "saves", -1: "costs", 0: "zero"}[here[0]["sign_at_scan_low"]]
            parts.append(f"{name} none ({sign})")
        else:
            parts.append(f"{name} " + ",".join(
                f"{r['multiple']:.1f}x" + ("*" if r["supported"] is True else "") for r in here))
    at = {(r["regime_name"], r["rate"]): r for r in rows if r["axis"] == "rate"}
    tail = ""
    row = at.get((regimes[0][0], 100.0))
    if row is not None:
        tail = f"  | ${100:.0f}/h cap {row['cap_margin']:+.3f}"
        if isinstance(row["transfer_margin"], float):
            tail += f" transfer {row['transfer_margin']:+.3f}"
    return f"  {cs._short_name(config):24s} " + "; ".join(parts) + tail


# ----------------------------------------------------------------------------- the cascade

def cascade_rows(variant: Variant, pools: Dict[str, ev.Pool], rates: Sequence[float] = ld.RATES,
                 regimes=ld.REGIMES, log=None) -> Tuple[List[dict], Tuple[str, ...]]:
    """Step v under the variant, as point estimates, on the configurations' common tasks."""
    if len(pools) < 2:
        return [], tuple(pools)
    aligned = ev.align(pools)
    names = tuple(aligned)
    mask = common_basis(variant, aligned)
    tabs = {c: sc.table(aligned[c]) for c in names}
    rows = []
    for name, fraction in regimes:
        for rate in rates:
            row = cs.cell(aligned, rate, fraction, variant.phi, mask, tabs, replicates=0)
            row.update(variant=variant.name, regime_name=name)
            rows.append(row)
            if log:
                log(f"  {name:10s} ${rate:4.0f}/h  best single {row['value_best_single']:8.2f}"
                    f"  cascade {row['value_cascade']:8.2f}  switch {row['switch_margin']:+7.3f}"
                    f"  on {row['tasks']} tasks")
    return rows, names


# ----------------------------------------------------------------------------- fixed policies

@dataclass(frozen=True)
class Fixed:
    """Steps i, ii and iii on one pool, as the per-task coefficients their value is linear in.

    For a policy of fixed cutoffs the value of a task is

        spend + v x checks + phi H x resolves + H x fails

    where ``spend`` is what its attempts are expected to cost, ``checks`` how many of them are
    expected to be submitted for verification, ``resolves`` the chance one resolves (each accepted
    resolution pays phi H under the false-accept sensitivity) and ``fails`` the chance none does.
    None of the four depends on the rate or the regime, so one computation prices the whole sweep.
    Rows are in ``policies.constant_family`` order: every cutoff on the grid and then no cutoff,
    for each attempt budget in turn.
    """
    spend: np.ndarray
    checks: np.ndarray
    resolves: np.ndarray
    fails: np.ndarray
    used: np.ndarray
    labels: Tuple[str, ...]
    size: int
    ks: Tuple[int, ...]

    def values(self, outside: np.ndarray, verify: np.ndarray, phi: float = 0.0) -> np.ndarray:
        return (self.spend + verify * self.checks + phi * outside * self.resolves
                + outside * self.fails)

    @property
    def retry_rows(self) -> List[int]:
        """Step ii's candidates: the no-cutoff member of each attempt budget."""
        return [i * self.size + self.size - 1 for i in range(len(self.ks))]

    def families(self, outside: np.ndarray, verify: np.ndarray, phi: float = 0.0):
        """Steps i, ii and iii's families, as ``ladder.rung`` builds them from the evaluator."""
        v = self.values(outside, verify, phi)
        none = self.retry_rows

        def fam(rows):
            return inf.Family(values=v[rows], used=self.used[rows],
                              labels=tuple(self.labels[i] for i in rows))
        return fam([none[self.ks.index(1)]]), fam(none), fam(list(range(v.shape[0])))

    def take(self, idx: np.ndarray) -> "Fixed":
        """The coefficients on a resample of the tasks, as the one-stage bootstrap sees them."""
        return Fixed(spend=self.spend[:, idx], checks=self.checks[:, idx],
                     resolves=self.resolves[:, idx], fails=self.fails[:, idx],
                     used=self.used[:, idx], labels=self.labels, size=self.size, ks=self.ks)


def fixed(pool: ev.Pool, tab: Optional[sc.Table] = None, ks: Sequence[int] = KS) -> Fixed:
    """The coefficients of every constant-cutoff policy, by the evaluator's enumeration: for each
    task, the mean over the orderings of its usable draws that fill the policy.

    The orderings of the largest budget are enumerated once. A budget of *k* reads their first *k*
    slots, and since every ordering of *k* draws begins the same number of the longer orderings,
    the mean over the longer ones, taken where their first *k* draws are usable, is the mean over
    the orderings of *k*."""
    tab = tab if tab is not None else sc.table(pool)
    if tab.cutoffs != tuple(pool.grid) + (None,):
        raise ValueError("the candidate table is not on the pool's own grid")
    ks = tuple(ks)
    n_c, n_t, n_d = tab.cost.shape
    perms = np.asarray(list(itertools.permutations(range(n_d), max(ks))), int)  # [ordering, slot]
    s = tab.cost[:, :, perms]                                   # [candidate, task, ordering, slot]
    r = tab.resolves[:, :, perms].astype(float)
    c = tab.checks[:, :, perms].astype(float)
    left = np.cumprod(1.0 - r, axis=3)                          # unresolved after each slot
    run = np.concatenate([np.ones_like(left[..., :1]), left[..., :-1]], axis=3)
    spent = np.cumsum(run * s, axis=3)
    checked = np.cumsum(run * c, axis=3)
    accepted = np.cumsum(run * r, axis=3)
    ok = pool.usable[:, perms]                                  # [task, ordering, slot]
    spend, checks, resolves, fails, used = [], [], [], [], []
    for k in ks:
        valid = ok[:, :, :k].all(axis=2)                        # [task, ordering]
        n = valid.sum(axis=1)
        weight = valid / np.maximum(n, 1)[:, None]
        spend.append(np.einsum("cto,to->ct", spent[..., k - 1], weight))
        checks.append(np.einsum("cto,to->ct", checked[..., k - 1], weight))
        resolves.append(np.einsum("cto,to->ct", accepted[..., k - 1], weight))
        fails.append(np.einsum("cto,to->ct", left[..., k - 1], weight))
        used.append(np.broadcast_to(n > 0, (n_c, n_t)))
    labels = tuple(p.label for p in po.constant_family(pool.config, pool.grid, ks))
    return Fixed(spend=np.vstack(spend), checks=np.vstack(checks),
                 resolves=np.vstack(resolves), fails=np.vstack(fails),
                 used=np.vstack(used), labels=labels, size=n_c, ks=ks)


def cap_margin(fx: Fixed, outside: np.ndarray, verify: np.ndarray, phi: float,
               label: np.ndarray, mask: np.ndarray) -> float:
    """The primary result from the coefficients: step ii minus step iii, cross-fitted by
    ``inference.cross_fit``. This is the reference the fast path below is held to."""
    _, retry, capped = fx.families(outside, verify, phi)
    return (inf.cross_fit(retry, label, mask).value
            - inf.cross_fit(capped, label, mask).value)


def _cross_fitted(fx: Fixed, rows: Sequence[int], hours: np.ndarray, label: np.ndarray,
                  eligible: np.ndarray, rates: np.ndarray, fractions: np.ndarray,
                  phi: float, k: int = inf.FOLDS) -> np.ndarray:
    """``inference.cross_fit`` of a fixed family at many points of the sweep at once.

    A candidate's mean over a set of tasks is linear in the rate too, the outside option being
    the task's hours times the rate, so the training and held-out sums of the four coefficients
    are taken once per fold and every point of the sweep is priced from them: the same choice on
    the training folds, the same score on the held-out fold, one number per point."""
    used = fx.used[rows]
    parts = np.stack([fx.spend[rows], fx.checks[rows] * hours, fx.resolves[rows] * hours,
                      fx.fails[rows] * hours]) * used               # [4, candidate, task]
    sides = np.zeros((len(hours), 2 * k))
    for f in range(k):
        sides[:, f] = (label != f) & eligible
        sides[:, k + f] = (label == f) & eligible
    # Apple's Accelerate library sets floating-point flags on ordinary matrix products, so the
    # products are taken quietly and their result is checked instead; a product that is not finite
    # makes every point of this replicate unscorable, which the caller counts as dropped
    with np.errstate(all="ignore"):
        sums = parts @ sides                                        # [4, candidate, 2k]
        counts = used.astype(float) @ sides                         # [candidate, 2k]
    if not (np.isfinite(sums).all() and np.isfinite(counts).all()):
        return np.full(len(np.atleast_1d(rates)), np.nan)
    rates = np.asarray(rates, float)[:, None, None]
    slope = (np.asarray(fractions, float)[:, None, None] * sums[1] + phi * sums[2] + sums[3])
    total = sums[0] + rates * slope                                 # [point, candidate, 2k]
    with np.errstate(invalid="ignore", divide="ignore"):
        means = np.where(counts[:, :k] > 0, total[:, :, :k] / counts[:, :k], np.inf)
    pick = np.argmin(means, axis=1)                                 # [point, fold]
    points = np.arange(total.shape[0])[:, None]
    folds = np.arange(k)[None, :]
    scored = total[points, pick, k + folds].sum(axis=1)
    n = counts[pick, k + folds].sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(n > 0, scored / np.maximum(n, 1), np.nan)


def cap_margins(fx: Fixed, hours: np.ndarray, label: np.ndarray, eligible: np.ndarray,
                rates: Sequence[float], fractions: Sequence[float], phi: float) -> np.ndarray:
    """The cap's margin at many points of the sweep, by the fast path."""
    every = list(range(fx.spend.shape[0]))
    return (_cross_fitted(fx, fx.retry_rows, hours, label, eligible, rates, fractions, phi)
            - _cross_fitted(fx, every, hours, label, eligible, rates, fractions, phi))


# ----------------------------------------------------------------------------- the two-stage bootstrap

def redraw(usable: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """[task, draw]: the second stage. Each task's usable draws are resampled with replacement
    from among themselves, and a draw outside the pool stays where it is, so a task keeps the
    number of usable draws it had and the tasks scored are the tasks the first stage drew."""
    usable = np.asarray(usable, bool)
    n_t, n_d = usable.shape
    out = np.tile(np.arange(n_d), (n_t, 1))
    full = usable.all(axis=1)
    out[full] = rng.integers(0, n_d, (int(full.sum()), n_d))
    for i in np.flatnonzero(~full & usable.any(axis=1)):
        have = np.flatnonzero(usable[i])
        out[i, have] = rng.choice(have, have.size, replace=True)
    return out


def _centre(draws: Sequence[float]) -> float:
    d = np.asarray(draws, float)
    d = d[np.isfinite(d)]
    return float(d.mean()) if d.size else float("nan")


def _interval(draws: Sequence[float], level: float = inf.LEVEL) -> Tuple[float, float]:
    d = np.asarray(draws, float)
    d = d[np.isfinite(d)]
    if not d.size:
        return float("nan"), float("nan")
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    return float(np.percentile(d, lo)), float(np.percentile(d, hi))


def cap_intervals(pool: ev.Pool, replicates: int = TWO_STAGE_REPLICATES, seed: int = inf.SEED,
                  phi: float = 0.0, mask: Optional[np.ndarray] = None, regimes=ld.REGIMES,
                  rates: Sequence[float] = ld.RATES, multiples: Sequence[float] = ld.MULTIPLES,
                  stage_two: bool = True) -> List[dict]:
    """The cap's margin at every point of the sweep, with its one-stage interval and, if
    ``stage_two``, its two-stage interval.

    The first stage is the primary interval's own: the same generator, seed and draws of task
    indices as ``inference.bootstrap``, and the fold split redone by task inside the replicate, so
    the one-stage interval here is the one ``ladder.rung`` computes, by a faster route. The second
    stage resamples the draws within each task the first stage drew."""
    mask = ev.full_draw_tasks({pool.config: pool}) if mask is None else np.asarray(mask, bool)
    n = pool.n_tasks
    fx = fixed(pool)
    hours = pool.minutes / 60.0
    cells = [(name, fraction, axis, rate) for name, fraction in regimes
             for axis, rate in ld._points(pool, rates, multiples, mask)]
    at = np.array([c[3] for c in cells], float)
    frac = np.array([c[1] for c in cells], float)
    label = inf.folds(n)
    estimate = [cap_margin(fx, ev.outside_option(pool, rate),
                           ev.verification(ev.outside_option(pool, rate), fraction), phi,
                           label, mask) for _, fraction, _, rate in cells]
    # the fast route on the sample itself, which every run holds to the ladder's point estimate
    fast = cap_margins(fx, hours, label, mask, at, frac, phi)
    one, two = [], []
    first = np.random.default_rng(seed)
    second = np.random.default_rng([seed, 2])
    for _ in range(replicates):
        idx = first.integers(0, n, n)
        folds = inf.replicate_folds(idx)
        keep = mask[idx]
        one.append(cap_margins(fx.take(idx), hours[idx], folds, keep, at, frac, phi))
        if stage_two:
            again = ev.resample(pool, idx, redraw(pool.usable[idx], second))
            two.append(cap_margins(fixed(again), hours[idx], folds, keep, at, frac, phi))
    one = np.asarray(one, float).reshape(-1, len(cells))
    two = np.asarray(two, float).reshape(-1, len(cells))
    out = []
    for j, (name, fraction, axis, rate) in enumerate(cells):
        lo1, hi1 = _interval(one[:, j])
        row = dict(config=pool.config, margin="cap", regime_name=name, regime=fraction,
                   axis=axis, rate=rate, multiple=ev.multiple_for_rate(pool, rate, mask),
                   phi=phi, estimate=estimate[j], fast_estimate=float(fast[j]),
                   one_stage_low=lo1, one_stage_high=hi1,
                   one_stage_mean=_centre(one[:, j]),
                   one_stage_replicates=int(np.isfinite(one[:, j]).sum()),
                   one_stage_dropped=int((~np.isfinite(one[:, j])).sum()),
                   two_stage_low="", two_stage_high="", two_stage_mean="", replicates="",
                   dropped="")
        if stage_two:
            lo2, hi2 = _interval(two[:, j])
            row.update(two_stage_low=lo2, two_stage_high=hi2, two_stage_mean=_centre(two[:, j]),
                       replicates=int(np.isfinite(two[:, j]).sum()),
                       dropped=int((~np.isfinite(two[:, j])).sum()))
        out.append(row)
    return out


def two_stage_transfer(pool: ev.Pool, source: Dict[str, ev.Pool], names: Sequence[str],
                       replicates: int = TRANSFER_REPLICATES, seed: int = inf.SEED,
                       phi: float = 0.0, mask: Optional[np.ndarray] = None,
                       rates: Sequence[float] = ld.FITTED_RATES, fraction: float = 0.0,
                       regime_name: str = "automated") -> List[dict]:
    """The primary transfer's two-stage interval, at the rates where the ladder gives its one-stage
    interval, which is at this count and draws the same tasks in every replicate.

    Every configuration's draws are resampled within the tasks drawn, the target's and each
    source's independently, since separate runs are independent draws. Unlike the one-stage
    bootstrap, where a task drawn twice is one task and trains once, a task drawn twice here carries
    two different resamples of its draws, and both train. The rule's models are refitted in every
    replicate and shared across its rates, as they are on the sample."""
    mask = ev.full_draw_tasks({pool.config: pool}) if mask is None else np.asarray(mask, bool)
    n = pool.n_tasks
    names = tuple(names)
    tab = sc.table(pool)
    cache: dict = {}
    estimate = {}
    for rate in rates:
        row = ld.rung(pool, rate, fraction, phi, replicates=0, mask=mask, tab=tab,
                      steps=("iii-b", "transfer"), transfer=(source, names),
                      transfer_cache=cache)
        estimate[rate] = row["transfer_margin"]
    draws_at: Dict[float, list] = {r: [] for r in rates}
    dropped = dict.fromkeys(rates, 0)
    first = np.random.default_rng(seed)
    second = np.random.default_rng([seed, 3])
    for _ in range(replicates):
        idx = first.integers(0, n, n)
        folds = inf.replicate_folds(idx)
        target = ev.resample(pool, idx, redraw(pool.usable[idx], second))
        others = {c: ev.resample(source[c], idx, redraw(source[c].usable[idx], second))
                  for c in names}
        tab_r = sc.table(target)
        fits: dict = {}                    # never shared across replicates: the pools differ
        for rate in rates:
            try:
                row = ld.rung(target, rate, fraction, phi, replicates=0, mask=mask[idx],
                              tab=tab_r, steps=("iii-b", "transfer"), transfer=(others, names),
                              transfer_cache=fits, label=folds)
                got = float(row["transfer_margin"])
            except Exception:
                got = float("nan")
            if np.isfinite(got):
                draws_at[rate].append(got)
            else:
                dropped[rate] += 1
    out = []
    for rate in rates:
        lo, hi = _interval(draws_at[rate])
        out.append(dict(config=pool.config, margin="transfer", regime_name=regime_name,
                        regime=fraction, axis="rate", rate=rate,
                        multiple=ev.multiple_for_rate(pool, rate, mask), phi=phi,
                        estimate=estimate[rate], one_stage_low="", one_stage_high="",
                        one_stage_mean="", two_stage_low=lo, two_stage_high=hi,
                        two_stage_mean=_centre(draws_at[rate]), one_stage_replicates="",
                        replicates=len(draws_at[rate]), dropped=dropped[rate]))
    return out


# ----------------------------------------------------------------------------- output

LADDER_FIELDS = ("variant",) + ld.FIELDS
BREAKEVEN_FIELDS = ("variant",) + be.FIELDS
TWO_STAGE_FIELDS = ("config", "margin", "regime_name", "regime", "axis", "rate", "multiple",
                    "phi", "estimate", "one_stage_low", "one_stage_high", "one_stage_mean",
                    "two_stage_low", "two_stage_high", "two_stage_mean", "one_stage_replicates",
                    "replicates", "dropped")


def _read(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def write(rows: Sequence[dict], path: str, fields: Sequence[str]) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
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
    ap.add_argument("--variants", nargs="*", default=[v.key for v in VARIANTS + CHECKS],
                    choices=sorted(BY_KEY),
                    help="which sensitivities; the nine registered and the common-tasks check "
                         "by default")
    ap.add_argument("--append", action="store_true",
                    help="keep the other variants' rows in the results files and replace only "
                         "those of the variants run")
    ap.add_argument("--parts", nargs="*", default=list(PARTS), choices=PARTS)
    ap.add_argument("--replicates", type=int, default=REPLICATES,
                    help="replicates for the cap margin's interval under each sensitivity")
    ap.add_argument("--two-stage-replicates", type=int, default=TWO_STAGE_REPLICATES)
    ap.add_argument("--transfer-replicates", type=int, default=TRANSFER_REPLICATES)
    ap.add_argument("--steps", nargs="*", default=list(STEPS))
    ap.add_argument("--rates", nargs="*", type=float, default=list(ld.RATES))
    ap.add_argument("--multiples", nargs="*", type=float, default=list(ld.MULTIPLES))
    ap.add_argument("--scan", type=int, default=be.SCAN)
    ap.add_argument("--only", nargs="*", help="configuration folder names to score")
    a = ap.parse_args(argv)
    say = (lambda line: print(line, flush=True))

    folders = ld.configurations(a.derived, a.notes)
    out = {part: os.path.join(a.out_dir, f"sensitivity_{part}.csv")
           for part in ("ladder", "breakeven", "cascade", "two_stage")}
    ladder_all, crossings_all, cascade_all = [], [], []
    cascade_names: Tuple[str, ...] = ()
    if a.append:
        running = {BY_KEY[k].name for k in a.variants}
        ladder_all, crossings_all, cascade_all = (
            [r for r in _read(out[part]) if r["variant"] not in running]
            for part in ("ladder", "breakeven", "cascade"))
        if cascade_all:
            cascade_names = tuple(k[len("own_"):] for k in cascade_all[0] if k.startswith("own_"))
    cache: dict = {}
    written = []
    started = time.time()
    for key in a.variants:
        v = BY_KEY[key]
        t0 = time.time()
        pools = load_pools(v, folders, cache)
        say(f"\n{v.name}: {v.what} ({v.where})")
        if "ladder" in a.parts:
            say("  break-even in multiples of the median attempt cost, * where both sides are"
                " resolved; the primary margins at $100 an hour")
            rows, found = ladder_rows(v, pools, a.replicates, a.steps, a.rates, a.multiples,
                                      scan=a.scan, only=a.only, log=say)
            ladder_all += rows
            crossings_all += found
            written += [write(ladder_all, out["ladder"], LADDER_FIELDS),
                        write(crossings_all, out["breakeven"], BREAKEVEN_FIELDS)]
        if "cascade" in a.parts:
            rows, cascade_names = cascade_rows(v, pools, a.rates, log=say)
            cascade_all += rows
            if rows:
                written.append(write(cascade_all, out["cascade"],
                                     ("variant",) + cs.fields(cascade_names)))
        say(f"  {time.time() - t0:.0f} s")

    if "two-stage" in a.parts:
        say(f"\ntwo-stage bootstrap: the cap's margin at {a.two_stage_replicates} replicates,"
            f" the primary transfer at {a.transfer_replicates}")
        pools = load_pools(PRIMARY, folders, cache)
        rows = []
        for name, pool in pools.items():
            if a.only and name not in a.only:
                continue
            t0 = time.time()
            got = cap_intervals(pool, a.two_stage_replicates, rates=a.rates,
                                multiples=a.multiples)
            off = sum(not np.isclose(g["fast_estimate"], g["estimate"], rtol=1e-9, atol=1e-9)
                      for g in got)
            if off:
                say(f"  {name}: at {off} points the fast route does not reproduce the point"
                    " estimate; read those rows' intervals with that in mind")
            rows += got
            others = [c for c in pools if c != name]
            if others and a.transfer_replicates:
                source = {c: ev.reindex(pools[c], pool.tasks) for c in others}
                rows += two_stage_transfer(pool, source, others, a.transfer_replicates,
                                           rates=[r for r in ld.FITTED_RATES if r in a.rates])
            written.append(write(rows, out["two_stage"], TWO_STAGE_FIELDS))
            here = [r for r in rows if r["config"] == name and r["axis"] == "rate"
                    and r["rate"] == 100.0 and r["regime_name"] in ("automated", "human 0.5")]
            say(f"  {cs._short_name(name):24s} " + "  ".join(
                f"{r['margin']} {r['regime_name']}: "
                + (f"one [{_f(r['one_stage_low'])}, {_f(r['one_stage_high'])}] "
                   if r["one_stage_low"] != "" else "")
                + f"two [{_f(r['two_stage_low'])}, {_f(r['two_stage_high'])}]" for r in here)
                + f"  ({time.time() - t0:.0f} s)")
    say(f"\ndone in {(time.time() - started) / 60:.0f} min -> "
        + ", ".join(dict.fromkeys(written)))


def _f(x) -> str:
    return f"{x:.2f}" if isinstance(x, float) else "-"


if __name__ == "__main__":
    _main()
