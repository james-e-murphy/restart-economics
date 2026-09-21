"""The policy classes of PLAN.md Section 6, as data. Nothing here computes a cost.

A policy is a sequence of **slots**, one per attempt it is allowed. A slot names the configuration
the attempt runs under and the cutoff at which that attempt is stopped, counted in LLM calls, or
``None`` for the configuration's own stop: the agent finishing, its loop detector, or its iteration
maximum. The ladder of Section 6 is five ways of filling that sequence, and the evaluator treats
them all alike.

    i      one attempt, no cutoff                     single(config)
    ii     K attempts, no cutoff                      retry(config, k)
    iii    K attempts at a constant cutoff            constant(config, t, k)
    iii-b  K attempts under a schedule                schedule(config, (t1, ..., tK))
    v      a schedule that may change configuration   cascade(((m1, t1), ...))

Step iv, the state rule, is not a fixed cutoff: it decides at each decision point from the running
attempt's state. It is built on the same slots and lives in its own module, because it needs
fitted models and the evaluator to compute its restart values.

Decision points are common to every policy, so a cutoff that is not one of them is refused rather
than quietly rounded: extra opportunities may not masquerade as the value of richer state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence, Tuple

FINE = tuple(range(5, 101, 5))          # every fifth call to 100
COARSE = tuple(range(125, 500, 25))     # then every twenty-fifth to 475

MAX_ATTEMPTS = 4                        # four logged runs per task is the horizon


def decision_points(cap: int) -> Tuple[int, ...]:
    """The decision points below a configuration's own iteration cap: 19 for a cap of 100, 35 for
    a cap of 500. A cutoff at the cap is no cutoff, and is written as ``None``."""
    return tuple(t for t in FINE + COARSE if t < cap)


def common_horizon(points: Sequence[int], horizon: int = 100) -> Tuple[int, ...]:
    """The sensitivity grid: the same points up to a horizon common to every configuration.

    The horizon is itself a decision point and is the baseline of that sensitivity: an attempt
    still running there is stopped and scored as a failure, which is what makes a configuration
    capped at 500 comparable with one capped at 100. Under this grid no slot runs to the
    configuration's own stop, so ``None`` is not used.
    """
    return tuple(t for t in points if t < horizon) + (horizon,)


@dataclass(frozen=True)
class Slot:
    """One attempt: which configuration runs it, and where it is stopped."""
    config: str
    cutoff: Optional[int] = None

    def __post_init__(self):
        if self.cutoff is not None and self.cutoff <= 0:
            raise ValueError("a cutoff is a positive number of calls, or None for no cutoff")


@dataclass(frozen=True)
class Policy:
    slots: Tuple[Slot, ...]
    label: str = field(default="", compare=False)

    def __post_init__(self):
        if not 1 <= len(self.slots) <= MAX_ATTEMPTS:
            raise ValueError(f"a policy has 1 to {MAX_ATTEMPTS} attempts, not {len(self.slots)}")

    @property
    def k(self) -> int:
        """The attempt budget."""
        return len(self.slots)

    @property
    def configs(self) -> Tuple[str, ...]:
        """The configurations the policy draws on, in first-use order."""
        return tuple(dict.fromkeys(s.config for s in self.slots))

    @property
    def cutoffs(self) -> Tuple[Optional[int], ...]:
        return tuple(s.cutoff for s in self.slots)


def single(config: str) -> Policy:
    """Step i: one attempt, run to the harness's own stop, then the outside option."""
    return Policy((Slot(config),), "i: one attempt")


def retry(config: str, k: int) -> Policy:
    """Step ii: K attempts, none of them cut off."""
    return Policy(tuple(Slot(config) for _ in range(k)), f"ii: {k} attempts, no cutoff")


def constant(config: str, cutoff: Optional[int], k: int) -> Policy:
    """Step iii: K attempts, each stopped at the same cutoff."""
    return Policy(tuple(Slot(config, cutoff) for _ in range(k)),
                  f"iii: {k} attempts at {cutoff if cutoff is not None else 'no'} cutoff")


def schedule(config: str, cutoffs: Sequence[Optional[int]]) -> Policy:
    """Step iii-b: K attempts under a schedule, the cap varying by attempt but not by state."""
    return Policy(tuple(Slot(config, t) for t in cutoffs), f"iii-b: schedule {tuple(cutoffs)}")


def cascade(pairs: Sequence[Tuple[str, Optional[int]]]) -> Policy:
    """Step v: a schedule over (configuration, cutoff) pairs. Step iii-b is the case where every
    slot names the same configuration, which is why retry and reroute are one decision."""
    return Policy(tuple(Slot(m, t) for m, t in pairs), f"v: cascade {tuple(pairs)}")


def constant_family(config: str, points: Sequence[int],
                    ks: Sequence[int] = (1, 2, 3, 4)) -> Tuple[Policy, ...]:
    """Every constant-cutoff policy on this grid, including the no-cutoff member of each *K*, which
    is what step iii is selected over. Step ii is the no-cutoff member; step i is *K* = 1."""
    out = []
    for k in ks:
        for t in tuple(points) + (None,):
            out.append(constant(config, t, k))
    return tuple(out)
