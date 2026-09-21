"""Cross-fitting and the bootstrap: choosing a policy without scoring it on the tasks that chose it.

Replay is exact, so the evaluator's arithmetic needs no inference. What needs inference is the
choice: a cutoff, an attempt budget, a schedule, a state rule or a cascade picked from data on 500
tasks will look better on those tasks than it is. PLAN.md Section 5 handles that in two parts,
both here.

**Cross-fitting.** One outer split of the tasks into five task-grouped folds. For each fold, every
quantity chosen from data is chosen on the other four and scored once on that fold, so no task
contributes to both the choice and the score. The held-out scores are what every comparison uses.

**A full-pipeline bootstrap.** Resample tasks with replacement, redo the split, the selection and
the fitting inside the replicate, and score again on that replicate's held-out tasks. Selection
variation then enters the interval instead of being conditioned away. Intervals are 95 percent
percentile intervals from 1,000 replicates, or from a smaller count, which is reported.

A policy family enters as a ``Family``: either fixed policies, whose per-task values do not depend
on which tasks were used to choose them, or a fitted rule, which is refitted on each training set.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

import numpy as np

FOLDS = 5
SEED = 20260920                 # the split is fixed once, before any policy is scored
REPLICATES = 1000
LEVEL = 0.95


def folds(n_tasks: int, k: int = FOLDS, seed: int = SEED) -> np.ndarray:
    """A fold label per task. Tasks are the clusters: a task's draws never straddle folds."""
    rng = np.random.default_rng(seed)
    label = np.arange(n_tasks) % k
    rng.shuffle(label)
    return label


@dataclass(frozen=True)
class Family:
    """A set of candidate policies and their per-task values.

    ``values`` is [policy, task] and ``used`` is [policy, task]: a task a policy cannot fill is not
    scored for it. ``fit`` is present when the family is refitted on each training set; it takes a
    boolean training mask and returns the same pair, or that pair and a set of labels, which is how
    a family whose candidates are themselves searched for reports what each training set chose.
    ``labels`` names the candidates.
    """
    values: np.ndarray
    used: np.ndarray
    labels: Tuple[str, ...]
    fit: Optional[Callable[[np.ndarray], Tuple[np.ndarray, ...]]] = None

    @staticmethod
    def of(results: Sequence) -> "Family":
        """From evaluator results, one per candidate policy."""
        values = np.vstack([r.per_task for r in results])
        used = np.vstack([r.used for r in results])
        labels = tuple(r.policy.label or str(r.policy.cutoffs) for r in results)
        return Family(values=np.nan_to_num(values, nan=0.0), used=used, labels=labels)

    def refit(self, train: np.ndarray) -> "Family":
        if self.fit is None:
            return self
        got = self.fit(train)
        values, used = got[0], got[1]
        labels = tuple(got[2]) if len(got) > 2 else self.labels
        return Family(values=np.nan_to_num(values, nan=0.0), used=used, labels=labels)


def _mean(values: np.ndarray, used: np.ndarray, where: np.ndarray) -> np.ndarray:
    """Each candidate's mean value over the tasks in ``where`` that it can fill."""
    keep = used & where
    n = keep.sum(axis=1)
    total = (values * keep).sum(axis=1)
    return np.where(n > 0, total / np.maximum(n, 1), np.inf)


def means(family: Family, where: Optional[np.ndarray] = None) -> np.ndarray:
    """Each candidate's mean value over the tasks in ``where`` it can fill; infinite where none."""
    n_tasks = family.values.shape[1]
    here = np.ones(n_tasks, bool) if where is None else np.asarray(where, bool)
    return _mean(family.values, family.used, here)


@dataclass(frozen=True)
class CrossFitted:
    per_task: np.ndarray        # [task] the value of the policy chosen without this task
    scored: np.ndarray          # [task] bool
    chosen: Tuple[int, ...]     # the candidate each fold chose
    labels: Tuple[str, ...]
    picked: Tuple[str, ...] = ()    # what each fold chose, named as that fold's fit named it

    @property
    def value(self) -> float:
        return float(self.per_task[self.scored].mean()) if self.scored.any() else float("nan")

    @property
    def n_tasks(self) -> int:
        return int(self.scored.sum())

    @property
    def choices(self) -> Tuple[str, ...]:
        return self.picked or tuple(self.labels[i] for i in self.chosen)


def cross_fit(family: Family, label: np.ndarray, restrict: Optional[np.ndarray] = None,
              k: int = FOLDS) -> CrossFitted:
    """Choose on the training folds, score once on the held-out fold, for every fold."""
    n_tasks = family.values.shape[1]
    eligible = np.ones(n_tasks, bool) if restrict is None else np.asarray(restrict, bool)
    per_task = np.zeros(n_tasks)
    scored = np.zeros(n_tasks, bool)
    chosen, picked = [], []
    for f in range(k):
        test = (label == f) & eligible
        train = (label != f) & eligible
        fitted = family.refit(train)
        pick = int(np.argmin(_mean(fitted.values, fitted.used, train)))
        chosen.append(pick)
        picked.append(fitted.labels[pick] if pick < len(fitted.labels) else str(pick))
        here = test & fitted.used[pick]
        per_task[here] = fitted.values[pick][here]
        scored |= here
    return CrossFitted(per_task=per_task, scored=scored, chosen=tuple(chosen),
                       labels=family.labels, picked=tuple(picked))


def in_sample(family: Family, restrict: Optional[np.ndarray] = None) -> Tuple[float, int]:
    """The best candidate's own mean, the optimistic number cross-fitting is there to avoid."""
    n_tasks = family.values.shape[1]
    where = np.ones(n_tasks, bool) if restrict is None else np.asarray(restrict, bool)
    means = _mean(family.values, family.used, where)
    pick = int(np.argmin(means))
    return float(means[pick]), pick


# ----------------------------------------------------------------------------- the bootstrap

def bootstrap(n_tasks: int, statistic: Callable[[np.ndarray], float],
              replicates: int = REPLICATES, seed: int = SEED,
              level: float = LEVEL) -> dict:
    """Resample tasks with replacement and recompute the statistic inside each replicate.

    ``statistic`` takes the resampled task indices and returns one number, redoing whatever
    selection and fitting the estimate involves. Replicates that cannot be computed, because a
    resample leaves a fold unable to fill the policy, are dropped and counted rather than filled in.
    """
    rng = np.random.default_rng(seed)
    draws = []
    failures = 0
    for _ in range(replicates):
        idx = rng.integers(0, n_tasks, n_tasks)
        try:
            got = float(statistic(idx))
        except Exception:                      # a replicate that cannot be scored is not an answer
            failures += 1
            continue
        if np.isfinite(got):
            draws.append(got)
        else:
            failures += 1
    draws = np.asarray(draws)
    lo, hi = (1 - level) / 2 * 100, (1 + level) / 2 * 100
    return dict(replicates=len(draws), dropped=failures, level=level,
                low=float(np.percentile(draws, lo)) if draws.size else float("nan"),
                high=float(np.percentile(draws, hi)) if draws.size else float("nan"),
                mean=float(draws.mean()) if draws.size else float("nan"),
                draws=draws)


def resampled(family: Family, idx: np.ndarray) -> Family:
    """The family as seen on a bootstrap resample of the tasks."""
    return Family(values=family.values[:, idx], used=family.used[:, idx], labels=family.labels,
                  fit=None if family.fit is None
                  else (lambda train, f=family, i=idx: _refit_resampled(f, i, train)))


def _refit_resampled(family: Family, idx: np.ndarray, train: np.ndarray):
    """Refit on the original tasks a resample's training mask selects, then read them off in the
    resample's order, so that a task drawn twice trains once and scores twice."""
    original = np.zeros(family.values.shape[1], bool)
    original[idx[train]] = True
    got = family.fit(original)
    return (got[0][:, idx], got[1][:, idx]) + tuple(got[2:])


def replicate_folds(idx: np.ndarray, k: int = FOLDS, seed: int = SEED) -> np.ndarray:
    """The fold split redone inside a bootstrap replicate, one label per resampled position.

    Tasks are the clusters, in a replicate as on the original sample, so every copy of a task
    drawn more than once goes to the same fold. Assigning folds by position instead would put the
    copies of most repeated tasks on both sides of the split, letting the replicate score a choice
    on a task that made it, and pulling every interval toward the in-sample answer. The split is a
    function of the resample alone, so the two families of a margin, scored on the same resample,
    are split alike.
    """
    idx = np.asarray(idx, int)
    unique, inverse = np.unique(idx, return_inverse=True)
    digest = hashlib.sha256(idx.tobytes()).digest()
    rng = np.random.default_rng([seed, int.from_bytes(digest[:8], "little")])
    label = np.arange(len(unique)) % k
    rng.shuffle(label)
    return label[inverse]


def cross_fitted_value(family: Family, idx: Optional[np.ndarray] = None,
                       restrict: Optional[np.ndarray] = None, k: int = FOLDS,
                       seed: int = SEED) -> float:
    """The cross-fitted value of a family, on the tasks or on a resample of them. This is the
    statistic the bootstrap resamples, and the point estimate when ``idx`` is None."""
    if idx is None:
        n = family.values.shape[1]
        return cross_fit(family, folds(n, k, seed), restrict, k).value
    here = resampled(family, idx)
    keep = None if restrict is None else np.asarray(restrict, bool)[idx]
    return cross_fit(here, replicate_folds(idx, k, seed), keep, k).value


def margin(baseline: Family, richer: Family, idx: Optional[np.ndarray] = None,
           restrict: Optional[np.ndarray] = None, k: int = FOLDS, seed: int = SEED) -> float:
    """What the richer family saves per task: the cross-fitted value of ``baseline`` minus that of
    ``richer``, both chosen and scored on the same tasks. Positive means the richer family is
    cheaper; negative means the extra freedom cost more than it saved out of sample."""
    return (cross_fitted_value(baseline, idx, restrict, k, seed)
            - cross_fitted_value(richer, idx, restrict, k, seed))
