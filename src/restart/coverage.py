"""Does the registered interval on the primary result cover what it claims to? (PLAN.md Section 8)

The cap's marginal value is a comparison between two families chosen from data, so what the
cross-fitted margin estimates is the population value of the policies the procedure chooses from a
training set, not the value of the best policy in the population. This builds a synthetic
population with a known answer and checks both halves of the inference against it:

    target     choose on many independent 400-task samples, score each choice on the whole
               population, and average: the value of the procedure, which the margin estimates
    point      the cross-fitted margin on a 500-task sample, which should be unbiased for it
    interval   the full-pipeline percentile bootstrap, which should cover it at its nominal rate

The population has what makes the real pools hard: tasks that differ in difficulty and share it
across their draws, attempts whose chance of resolving falls with their length, calls that grow
dearer as context accumulates, and an outside option drawn from the benchmark's four difficulty
buckets in roughly their proportions. The oracle, the best policy in the population, is printed
beside the target so that the cost of choosing from data can be read off.

    python -m restart.coverage              # about five minutes
"""
from __future__ import annotations

from typing import Sequence, Tuple

import numpy as np

from . import evaluate as ev
from . import inference as inf
from . import ladder as ld
from . import policies as po

SETTINGS: Tuple[Tuple[float, float], ...] = ((1.0, 0.0), (5.0, 0.0), (50.0, 0.0), (20.0, 0.5))
BUCKETS = np.array([3.9, 30.0, 120.0, 480.0])
SHARES = np.array([0.39, 0.52, 0.08, 0.01])


def population(n: int = 12000, seed: int = inf.SEED) -> ev.Pool:
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    cost, out, res, minutes = [], [], [], []
    for _ in tasks:
        skill = rng.normal(0, 1.2)
        rows, wins = [], []
        for _ in range(4):
            calls = int(np.clip(rng.gamma(2.0, 18.0) * np.exp(-0.2 * skill), 3, 99))
            wins.append(bool(rng.random() < 1 / (1 + np.exp(-(skill + 1.2 - calls / 25.0)))))
            rows.append(((0.01 + 0.0004 * np.arange(calls)).tolist(), [300.0] * calls))
        cost.append([c for c, _ in rows])
        out.append([o for _, o in rows])
        res.append(wins)
        minutes.append(rng.choice(BUCKETS, p=SHARES))
    return ev.build("population", 100, tasks, ("1", "2", "3", "4"), cost, out, res,
                    candidate=[[True] * 4 for _ in tasks], usable=[[True] * 4 for _ in tasks],
                    minutes=minutes)


def study(pool: ev.Pool, multiple: float, fraction: float, datasets: int = 120,
          replicates: int = 200, sample: int = 500, train: int = 400, truth_draws: int = 400,
          seed: int = inf.SEED) -> dict:
    rng = np.random.default_rng([seed, int(multiple * 100), int(fraction * 100)])
    ks = tuple(range(1, po.MAX_ATTEMPTS + 1))
    rate = ev.rate_for_multiple(pool, multiple)
    h = ev.outside_option(pool, rate)
    v = ev.verification(h, fraction)
    retry = ld._family(pool, [po.retry(pool.config, k) for k in ks], h, v, 0.0, None)
    capped = ld._family(pool, po.constant_family(pool.config, pool.grid, ks), h, v, 0.0, None)
    whole_r, whole_c = retry.values.mean(axis=1), capped.values.mean(axis=1)
    n = pool.n_tasks

    chosen = []
    for _ in range(truth_draws):
        s = rng.choice(n, train, replace=False)
        chosen.append(whole_r[np.argmin(retry.values[:, s].mean(1))]
                      - whole_c[np.argmin(capped.values[:, s].mean(1))])
    target = float(np.mean(chosen))

    def on(family, s):
        return inf.Family(values=family.values[:, s], used=np.ones((family.values.shape[0], len(s)),
                          bool), labels=family.labels)

    cover, error, shift, width = [], [], [], []
    for d in range(datasets):
        s = rng.choice(n, sample, replace=False)
        r, c = on(retry, s), on(capped, s)
        point = inf.margin(r, c)
        b = inf.bootstrap(sample, lambda idx: inf.margin(r, c, idx), replicates=replicates, seed=d)
        cover.append(b["low"] <= target <= b["high"])
        error.append(point - target)
        shift.append(b["mean"] - point)
        width.append(b["high"] - b["low"])
    return dict(multiple=multiple, fraction=fraction, rate=rate, target=target,
                oracle=float(whole_r.min() - whole_c.min()),
                bias=float(np.mean(error)), bias_se=float(np.std(error) / np.sqrt(datasets)),
                shift=float(np.mean(shift)), width=float(np.mean(width)),
                coverage=float(np.mean(cover)), datasets=datasets, replicates=replicates)


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tasks", type=int, default=12000)
    ap.add_argument("--datasets", type=int, default=120)
    ap.add_argument("--replicates", type=int, default=200)
    a = ap.parse_args(argv)
    pool = population(a.tasks)
    print(f"population of {pool.n_tasks} tasks: median attempt ${ev.median_attempt_cost(pool):.3f},"
          f" resolve rate {pool.resolved.mean():.2f}")
    for multiple, fraction in SETTINGS:
        got = study(pool, multiple, fraction, a.datasets, a.replicates)
        print(f"  {multiple:5.1f}x median attempt cost, review {fraction}:"
              f"  target {got['target']:+.3f} (oracle {got['oracle']:+.3f})"
              f"  point - target {got['bias']:+.3f} (se {got['bias_se']:.3f})"
              f"  replicate mean - point {got['shift']:+.3f}"
              f"  width {got['width']:.3f}"
              f"  covers {got['coverage']:.0%} of {got['datasets']}")


if __name__ == "__main__":
    _main()
