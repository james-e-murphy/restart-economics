"""Step iv: the receding-horizon restart rule of PLAN.md Section 6.

At each decision point the rule compares committing the running attempt to termination against
restarting now. Committing costs its fitted remaining spend, plus verification, plus the value of
restarting weighted by the fitted probability that it does not resolve; restarting costs the value
of starting afresh with the attempts that remain. Subtracting the common term, the rule stops when

    fitted remaining spend + v  >  fitted resolution probability x (V - phi H)

where *V* is the value of restarting with the attempts that remain and *H* is the population mean
outside option at the rate being evaluated. It is named a receding-horizon rule and not the value
function: the commit-to-termination cost ignores the option to stop later, which biases it toward
restarting, while its restart values, computed by replaying the rule itself on the training folds
and averaged over tasks rather than conditioned on the task at hand, pull both ways.

Two models are fitted on every usable attempt still running at a decision point, pooled across
decision points and attempts, on three state variables: the log of the decision point, the log of
one plus cumulative output tokens, and the log of one plus output tokens over the last five calls.

    resolution   logistic, for the probability the attempt resolves if run to its end
    spend        log-link quasi-Poisson, for remaining spend in multiples of the attempt's own
                 spend per call over the last five calls, so the target carries no currency and
                 the prediction converts to dollars at that rate

That is eight coefficients per configuration, none of them specific to a decision point. Fitted on
the configuration's own training folds it is the within-configuration rule; fitted on the other six
configurations, each weighted equally, it is the transfer rule, and in both the restart values and
the attempt budget come from the target configuration's own training folds.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

import numpy as np

from . import evaluate as ev
from . import inference as inf
from .policies import MAX_ATTEMPTS, Policy, Slot

FEATURES = ("intercept", "log calls", "log output tokens", "log recent output tokens")

def _quiet(fn):
    """Some BLAS builds raise divide-by-zero and overflow flags on ordinary matrix products. The
    fits clip their own arguments and check what they produce, so the flags are noise."""
    @functools.wraps(fn)
    def wrapped(*args, **kwargs):
        with np.errstate(all="ignore"):
            return fn(*args, **kwargs)
    return wrapped
RIDGE = 1e-6            # keeps the Newton step solvable; raised on separation
SEPARATED = 1e3         # a coefficient this large is separation, not signal


@dataclass(frozen=True)
class Models:
    """The eight coefficients, and any fallback the fit needed.

    ``center`` and ``scale`` standardize the three state variables at the values the training rows
    had. They are not fitted to the outcome; they only condition the fit, which matters because the
    state variables are close to collinear by construction: output tokens accumulate with calls.
    A transferred rule carries its source's standardization with it.
    """
    resolve: np.ndarray
    spend: np.ndarray
    center: np.ndarray
    scale: np.ndarray
    notes: Tuple[str, ...] = ()
    rows: int = 0


def design(pool: ev.Pool) -> np.ndarray:
    """[task, draw, point, 4]: the state a running attempt shows at each decision point."""
    calls = np.asarray(pool.grid, float)
    log_calls = np.broadcast_to(np.log(calls), pool.out_grid.shape)
    return np.stack([np.ones_like(pool.out_grid), log_calls,
                     np.log1p(pool.out_grid), np.log1p(pool.out_recent)], axis=-1)


def _rows(pool: ev.Pool, train: np.ndarray):
    """The fitting rows: attempts in the pool, on training tasks, still running at the point."""
    here = pool.alive & (pool.usable & np.asarray(train, bool)[:, None])[:, :, None]
    x = design(pool)[here]
    resolved = np.broadcast_to(pool.resolved[:, :, None], pool.alive.shape)[here]
    remaining = (pool.cost_end[:, :, None] - pool.cost_grid)[here]
    rate = np.maximum(pool.cost_rate[here], 1e-12)
    return x, resolved.astype(float), np.maximum(remaining, 0.0) / rate


def fit(pools, train, configs: Optional[Sequence[str]] = None) -> Models:
    """Fit both models. ``pools`` is one pool or several; with several, each contributes the same
    total weight, so a configuration whose attempts run longer does not dominate the fit."""
    if isinstance(pools, ev.Pool):
        pools = {pools.config: pools}
    configs = tuple(configs or pools)
    xs, ys, zs, ws = [], [], [], []
    for c in configs:
        x, y, z = _rows(pools[c], train)
        if not len(x):
            continue
        xs.append(x), ys.append(y), zs.append(z)
        ws.append(np.full(len(x), 1.0 / len(x)))        # equal total weight per configuration
    if not xs:
        raise ValueError("no attempts were running at any decision point on the training tasks")
    x = np.concatenate(xs)
    y = np.concatenate(ys)
    z = np.concatenate(zs)
    w = np.concatenate(ws)
    center = np.average(x[:, 1:], axis=0, weights=w)
    scale = np.sqrt(np.average((x[:, 1:] - center) ** 2, axis=0, weights=w))
    scale = np.where(scale > 1e-12, scale, 1.0)
    xs_ = np.column_stack([x[:, 0], (x[:, 1:] - center) / scale])
    resolve, note_r = _logistic(xs_, y, w)
    spend, note_s = _quasi_poisson(xs_, z, w)
    notes = tuple(n for n in (note_r, note_s) if n)
    return Models(resolve=resolve, spend=spend, center=center, scale=scale,
                  notes=notes, rows=len(x))


def predict(pool: ev.Pool, models: Models) -> Tuple[np.ndarray, np.ndarray]:
    """(probability of resolving, remaining spend in dollars) at every decision point."""
    x = design(pool)
    x = np.concatenate([x[..., :1], (x[..., 1:] - models.center) / models.scale], axis=-1)
    with np.errstate(all="ignore"):
        q = 1.0 / (1.0 + np.exp(-np.clip(x @ models.resolve, -30, 30)))
        s = np.exp(np.clip(x @ models.spend, -30, 30)) * pool.cost_rate
    return q, s


def stop_index(pool: ev.Pool, models: Models, verify: float, continuation: float,
               prediction: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> np.ndarray:
    """[task, draw]: the first decision point at which the rule stops a running attempt, or -1 if
    it never does, in which case the attempt runs to its own stop.

    ``prediction`` is what the two models say at every decision point. It depends on the models and
    the pool and not on the rate, the regime or the attempt budget, so the caller computes it once
    and the recursion over attempts reuses it.
    """
    q, s = predict(pool, models) if prediction is None else prediction
    stop = pool.alive & (s + verify > q * continuation)
    first = np.argmax(stop, axis=2)
    return np.where(stop.any(axis=2), first, -1)


def restart_values(pool: ev.Pool, models: Models, k: int, outside: np.ndarray,
                   verify: np.ndarray, phi: float, train: np.ndarray,
                   prediction: Optional[Tuple[np.ndarray, np.ndarray]] = None):
    """Backward over attempts on the training tasks: the value of restarting with *j* to *K*
    attempts left, and the slot each of them replays. ``V[K+1]`` is the population mean outside
    option, which is what the rule falls back to when the last attempt is stopped."""
    train = np.asarray(train, bool)
    h_bar = float(outside[train].mean())
    v_bar = float(verify[train].mean())
    values = {k + 1: h_bar}
    slots = {}
    prediction = predict(pool, models) if prediction is None else prediction
    for j in range(k, 0, -1):
        stop = stop_index(pool, models, v_bar, values[j + 1] - phi * h_bar, prediction)
        slots[j] = ev.stopped_slot(pool, stop)
        policy = Policy(tuple(Slot(pool.config) for _ in range(k - j + 1)))
        got = ev.value({pool.config: pool}, policy, outside, verify, phi, mask=train,
                       arrays=[slots[i] for i in range(j, k + 1)])
        values[j] = got.value if np.isfinite(got.value) else h_bar
    return values, slots


def rule_result(pool: ev.Pool, models: Models, k: int, outside: np.ndarray, verify: np.ndarray,
                phi: float, train: np.ndarray, mask: Optional[np.ndarray] = None,
                prediction: Optional[Tuple[np.ndarray, np.ndarray]] = None) -> ev.Result:
    """The rule's value on every task, with its restart values set on the training tasks."""
    _, slots = restart_values(pool, models, k, outside, verify, phi, train, prediction)
    policy = Policy(tuple(Slot(pool.config) for _ in range(k)), f"iv: state rule, {k} attempts")
    return ev.value({pool.config: pool}, policy, outside, verify, phi, mask=mask,
                    arrays=[slots[j] for j in range(1, k + 1)])


def family(pool: ev.Pool, outside: np.ndarray, verify: np.ndarray, phi: float = 0.0,
           ks: Sequence[int] = tuple(range(1, MAX_ATTEMPTS + 1)),
           source: Optional[Dict[str, ev.Pool]] = None,
           source_configs: Optional[Sequence[str]] = None,
           mask: Optional[np.ndarray] = None,
           notes: Optional[list] = None,
           cache: Optional[dict] = None, cache_size: int = 16) -> inf.Family:
    """The state rule as a family to cross-fit: one candidate per attempt budget, refitted on each
    training set. ``source`` fits the two models on other configurations instead of this one, which
    is the transfer design; the restart values and the budget still come from this configuration's
    training tasks. ``notes`` collects what each fit had to fall back to, which belongs beside the
    number the fit produced.

    Neither model depends on the rate or the regime, so a ``cache`` keyed by the training set is
    shared across the sweep and the models are fitted once per fold, as the registration states.
    It is bounded, because a bootstrap draws a new training set in every replicate, and a hit is
    an exact match on the training mask.
    """
    ks = tuple(ks)
    labels = tuple(f"iv: state rule, {k} attempts" for k in ks)

    def models_for(train: np.ndarray) -> Models:
        if cache is None:
            return fit(source or pool, train, source_configs)
        key = np.packbits(np.asarray(train, bool)).tobytes()
        if key not in cache:
            got = fit(source or pool, train, source_configs)
            if len(cache) >= cache_size:
                return got
            cache[key] = got
        return cache[key]

    def fit_on(train: np.ndarray):
        models = models_for(train)
        if notes is not None:
            notes.extend(models.notes)
        prediction = predict(pool, models)
        results = [rule_result(pool, models, k, outside, verify, phi, train, mask, prediction)
                   for k in ks]
        return (np.vstack([r.per_task for r in results]),
                np.vstack([r.used for r in results]))

    return inf.Family(values=np.zeros((len(ks), pool.n_tasks)),
                      used=np.ones((len(ks), pool.n_tasks), bool), labels=labels, fit=fit_on)


# ----------------------------------------------------------------------------- the two fits

@_quiet
def _logistic(x: np.ndarray, y: np.ndarray, w: np.ndarray, ridge: Optional[float] = None):
    """Weighted logistic regression by Newton steps. A fit that separates or does not converge is
    refitted with a ridge, and if that fails too the rule falls back to the pooled rate, which is
    the chain the registration states. The ridge is scaled by the weight total, so it does not
    depend on how many rows the fit happens to have."""
    ridge = RIDGE * w.sum() if ridge is None else ridge
    b, note = _newton_logistic(x, y, w, ridge)
    if b is None or note or np.max(np.abs(b)) > SEPARATED:
        again, trouble = _newton_logistic(x, y, w, ridge=1e-2 * w.sum())
        if again is not None and np.all(np.isfinite(again)):
            return again, "logistic separated or did not converge; refitted with a ridge"
        rate = float(np.average(y, weights=w))
        b = np.zeros(x.shape[1])
        b[0] = np.log(max(rate, 1e-6) / max(1 - rate, 1e-6))
        return b, "logistic did not converge; fell back to the pooled rate"
    return b, note


@_quiet
def _newton_logistic(x, y, w, ridge, iters: int = 60):
    b = np.zeros(x.shape[1])
    eye = np.eye(x.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-np.clip(x @ b, -30, 30)))
        grad = x.T @ (w * (y - p)) - ridge * b
        hess = x.T @ (x * (w * p * (1 - p))[:, None]) + ridge * eye
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            return None, "logistic step was singular"
        b = b + step
        if not np.all(np.isfinite(b)):
            return None, "logistic diverged"
        if np.max(np.abs(step)) < 1e-9:
            return b, ""
    return b, "logistic reached its iteration limit"


@_quiet
def _quasi_poisson(x: np.ndarray, y: np.ndarray, w: np.ndarray, iters: int = 60):
    """Weighted quasi-Poisson with a log link, consistent for the conditional mean of a positive
    continuous outcome. On failure the same log-linear mean is fitted by Gauss-Newton least
    squares, and failing that the rule falls back to the pooled mean, as the registration states."""
    b = np.zeros(x.shape[1])
    b[0] = np.log(max(np.average(y, weights=w), 1e-9))
    eye = np.eye(x.shape[1])
    for _ in range(iters):
        mu = np.exp(np.clip(x @ b, -30, 30))
        grad = x.T @ (w * (y - mu))
        hess = x.T @ (x * (w * mu)[:, None]) + RIDGE * w.sum() * eye
        try:
            step = np.linalg.solve(hess, grad)
        except np.linalg.LinAlgError:
            break
        step = np.clip(step, -5, 5)
        b = b + step
        if not np.all(np.isfinite(b)):
            break
        if np.max(np.abs(step)) < 1e-9:
            return b, ""
    b_nls, ok = _gauss_newton(x, y, w, iters)
    if ok:
        return b_nls, "quasi-Poisson did not converge; fitted by nonlinear least squares"
    pooled = np.zeros(x.shape[1])
    pooled[0] = np.log(max(np.average(y, weights=w), 1e-9))
    return pooled, "quasi-Poisson and least squares both failed; fell back to the pooled mean"


@_quiet
def _gauss_newton(x, y, w, iters: int = 60):
    b = np.zeros(x.shape[1])
    b[0] = np.log(max(np.average(y, weights=w), 1e-9))
    eye = np.eye(x.shape[1])
    for _ in range(iters):
        mu = np.exp(np.clip(x @ b, -30, 30))
        j = x * mu[:, None]
        grad = j.T @ (w * (y - mu))
        hess = j.T @ (j * w[:, None]) + RIDGE * w.sum() * eye
        try:
            step = np.clip(np.linalg.solve(hess, grad), -5, 5)
        except np.linalg.LinAlgError:
            return b, False
        b = b + step
        if not np.all(np.isfinite(b)):
            return b, False
        if np.max(np.abs(step)) < 1e-9:
            return b, True
    return b, False
