"""The state rule against the exact dynamic program, on synthetic attempts (PLAN.md Section 8).

The rule of Section 6 is a receding-horizon approximation: it compares committing the running
attempt to termination against restarting now, which ignores the option to stop later and so
overstates the cost of continuing, a bias toward restarting; and its restart values are its own
replayed costs, which overstate the cost of restarting relative to the optimal policy, a bias the
other way. Which way the two net out is not asserted. It is measured here, where the optimum can
be computed exactly: a population of attempts whose law is known and whose state is the rule's.

Each attempt is of one of two kinds it does not reveal. A good attempt resolves when it finishes,
a bad one seldom does; a bad attempt runs longer and writes more. Calls come in intervals of five,
one decision point apart, and in each interval an attempt writes a high or a low volume of output
and pays for it, then finishes with a probability that depends on its kind; at the cap the harness
stops it. The rule's three state variables, the decision point, the cumulative output and the
output over the last five calls, then determine how many high intervals the attempt has had, and
with the decision point that count is a sufficient statistic for its kind. So the optimum over the
rule's own state and actions is a backward induction over (attempt, decision point, count), with
the belief about the attempt's kind updated by Bayes' rule, and its value is exact.

Tasks are alike here, so the restart values' other weakness, being averages over tasks rather than
conditional on the task at hand, does not arise; with tasks that differ, the optimum over the same
state is no longer a backward induction, and nothing is claimed for that case.

For each setting the log gives the exact optimum, the optimum's own policy replayed by the
evaluator on a simulated sample (a check that the two agree), and on the same held-out sample the
state rule fitted on a separate training sample, the best constant cutoff, and retrying without a
cap; then the share of attempts each policy stops before their end and where.

    python -m restart.dynamic
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import evaluate as ev
from . import inference as inf
from . import policies as po
from . import state as st

STEP = 5                      # calls per interval, one decision point apart
CAP = 100
SEED = 20260921


@dataclass(frozen=True)
class Model:
    """The law of one attempt. Index 0 is a good attempt, 1 a bad one."""
    good: float = 0.5                         # the chance an attempt is good
    high: Tuple[float, float] = (0.3, 0.6)    # chance of a high-output interval
    finish: Tuple[float, float] = (0.12, 0.04)  # chance of finishing at an interval's end
    resolve: Tuple[float, float] = (0.9, 0.05)  # chance a finished attempt resolves
    at_cap: Tuple[float, float] = (0.3, 0.02)   # chance an attempt stopped at the cap resolves
    cost: Tuple[float, float] = (0.05, 0.12)    # dollars for a low and a high interval
    tokens: Tuple[float, float] = (400.0, 1600.0)   # output tokens in a low and a high interval
    cap: int = CAP

    @property
    def points(self) -> Tuple[int, ...]:
        return po.decision_points(self.cap)

    @property
    def prior(self) -> np.ndarray:
        return np.array([self.good, 1.0 - self.good])


# ----------------------------------------------------------------------------- the exact optimum

def belief(model: Model, i: int, k: int) -> np.ndarray:
    """P(kind | alive at decision point i, k high intervals among the i + 1 so far)."""
    n = i + 1
    high = np.asarray(model.high)
    fin = np.asarray(model.finish)
    like = model.prior * high ** k * (1 - high) ** (n - k) * (1 - fin) ** n
    return like / like.sum()


def solve(model: Model, outside: float, verify: float, k_max: int = po.MAX_ATTEMPTS,
          fixed: Optional[Tuple[Dict[int, np.ndarray], int]] = None):
    """Backward induction. Returns the value of the problem, the value of starting each attempt,
    for each attempt a table stop[i, k], whether to stop an attempt alive at decision point i with
    k high intervals, and the attempt budget. Starting another attempt is optional after the
    first, which is choosing the budget, since a policy only ever starts one after every earlier
    one failed. ``fixed`` supplies the tables and the budget instead of optimizing them, which
    evaluates that policy exactly."""
    if fixed is not None:
        k_max = fixed[1]
    points = model.points
    n_i = len(points)
    high, fin = np.asarray(model.high), np.asarray(model.finish)
    res, cap_res = np.asarray(model.resolve), np.asarray(model.at_cap)
    c_low, c_high = model.cost
    start = {k_max + 1: outside}
    stop_tables: Dict[int, np.ndarray] = {}
    for j in range(k_max, 0, -1):
        after = start[j + 1]
        w = np.zeros((n_i, n_i + 1))
        stop = np.zeros((n_i, n_i + 1), bool)
        for i in range(n_i - 1, -1, -1):
            for k in range(i + 2):
                q = belief(model, i, k)
                cont = 0.0
                for s, (p_s, c_s) in enumerate(((1 - high, c_low), (high, c_high))):
                    ps = q * p_s                                 # [kind]
                    if i == n_i - 1:                             # the next interval ends at the cap
                        cont += (ps * (c_s + verify + (1 - cap_res) * after)).sum()
                    else:
                        cont += (ps * (c_s + fin * (verify + (1 - res) * after))).sum()
                        alive = (ps * (1 - fin)).sum()
                        cont += alive * w[i + 1, k + s]
                if fixed is None:
                    stop[i, k] = after < cont
                else:
                    stop[i, k] = bool(fixed[0][j][i, k])
                w[i, k] = after if stop[i, k] else cont
        fresh = 0.0
        for s, (p_s, c_s) in enumerate(((1 - high, c_low), (high, c_high))):
            ps = model.prior * p_s
            fresh += (ps * (c_s + fin * (verify + (1 - res) * after))).sum()
            fresh += (ps * (1 - fin)).sum() * w[0, s]
        start[j] = fresh if (j == 1 or fixed is not None) else min(outside, fresh)
        stop_tables[j] = stop
    budget = next((j - 1 for j in range(2, k_max + 1) if start[j] >= outside), k_max)
    return start[1], start, stop_tables, budget


def evaluate(model: Model, tables: Dict[int, np.ndarray], budget: int, outside: float,
             verify: float) -> float:
    """The exact value of a given policy: stop tables for attempts 1 to ``budget``."""
    return solve(model, outside, verify, fixed=(tables, budget))[0]


# ----------------------------------------------------------------------------- simulated attempts

def simulate(model: Model, tasks: int, draws: int = 4, seed: int = SEED) -> ev.Pool:
    """A pool of attempts drawn from the model, every task alike, in the evaluator's format."""
    rng = np.random.default_rng(seed)
    points = model.points
    cost, out, wins = [], [], []
    for _ in range(tasks):
        rc, ro, rw = [], [], []
        for _ in range(draws):
            kind = 0 if rng.random() < model.good else 1
            calls_c, calls_o = [], []
            n = 0
            resolved = False
            while True:
                s = int(rng.random() < model.high[kind])
                calls_c += [model.cost[s] / STEP] * STEP
                calls_o += [model.tokens[s] / STEP] * STEP
                n += STEP
                if n >= model.cap:
                    resolved = rng.random() < model.at_cap[kind]
                    break
                if rng.random() < model.finish[kind]:
                    resolved = rng.random() < model.resolve[kind]
                    break
            rc.append(calls_c), ro.append(calls_o), rw.append(bool(resolved))
        cost.append(rc), out.append(ro), wins.append(rw)
    names = tuple(f"t{i}" for i in range(tasks))
    return ev.build("synthetic", model.cap, names, tuple(str(d + 1) for d in range(draws)),
                    cost, out, wins, candidate=[[True] * draws] * tasks,
                    usable=[[True] * draws] * tasks, minutes=[60.0] * tasks, grid=points)


def highs(model: Model, pool: ev.Pool) -> np.ndarray:
    """[task, draw, point]: high intervals so far, read back from cumulative output."""
    lo, hi = model.tokens
    n = (np.asarray(model.points) // STEP)[None, None, :]
    return np.rint((pool.out_grid - lo * n) / (hi - lo)).astype(int)


# ----------------------------------------------------------------------------- the comparison

def compare(model: Model, multiple: float, fraction: float, pool: ev.Pool,
            train: np.ndarray) -> dict:
    """At an outside option of ``multiple`` median attempt costs and review at ``fraction`` of it:
    the exact optimum, and every policy chosen on the training tasks and scored on the rest."""
    test = ~train
    outside = multiple * ev.median_attempt_cost(pool, train)
    verify = fraction * outside
    best, start, tables, budget = solve(model, outside, verify)
    h = np.full(pool.n_tasks, outside)
    v = np.full(pool.n_tasks, verify)
    ks = tuple(range(1, po.MAX_ATTEMPTS + 1))
    row = dict(multiple=multiple, fraction=fraction, outside=outside, optimum=best,
               optimum_budget=budget)

    # the optimum's own policy replayed by the evaluator on the held-out tasks
    k = highs(model, pool)
    i = np.broadcast_to(np.arange(len(model.points))[None, None, :], k.shape)
    firsts = {}
    for j in range(1, budget + 1):
        table = tables[j]
        want = pool.alive & table[i, np.clip(k, 0, table.shape[1] - 1)]
        firsts[j] = np.where(want.any(axis=2), want.argmax(axis=2), -1)
    policy = po.Policy(tuple(po.Slot(pool.config) for _ in range(budget)))
    got = ev.value({pool.config: pool}, policy, h, v,
                   arrays=[ev.stopped_slot(pool, firsts[j]) for j in range(1, budget + 1)])
    row["optimum_replayed"] = float(got.per_task[test].mean())

    # the state rule: models, restart values and budget from the training tasks
    models = st.fit(pool, train)
    results = [st.rule_result(pool, models, kk, h, v, 0.0, train) for kk in ks]
    pick = int(np.argmin([r.per_task[train].mean() for r in results]))
    k_rule = ks[pick]
    row.update(rule=float(results[pick].per_task[test].mean()), rule_budget=k_rule)
    values, _ = st.restart_values(pool, models, k_rule, h, v, 0.0, train)

    # the best constant cutoff, and retrying without one, chosen on training and scored on test
    fam = inf.Family.of([ev.value({pool.config: pool}, p, h, v)
                         for p in po.constant_family(pool.config, pool.grid, ks)])
    per_k = len(pool.grid) + 1
    best_c = int(np.argmin(fam.values[:, train].mean(axis=1)))
    retry = [n * per_k + per_k - 1 for n in range(len(ks))]
    best_r = retry[int(np.argmin(fam.values[retry][:, train].mean(axis=1)))]
    row.update(constant=float(fam.values[best_c, test].mean()), constant_choice=fam.labels[best_c],
               retry=float(fam.values[best_r, test].mean()))

    # how each stops a first attempt: the share stopped before its own end, and where
    rule_first = st.stop_index(pool, models, verify, values[2])
    for name, first in (("optimum", firsts[1]), ("rule", rule_first)):
        cut = (first >= 0)[test]
        row[f"{name}_stops"] = float(cut.mean())
        at = np.asarray(model.points)[first[test][cut]]
        row[f"{name}_stop_at"] = float(at.mean()) if at.size else float("nan")
    return row


SETTINGS = (
    ("signals weakly informative", Model()),
    ("signals strongly informative", replace(Model(), high=(0.2, 0.8))),
)
MULTIPLES = (2.0, 10.0, 50.0)
FRACTIONS = (0.0, 0.5)


def study(settings=SETTINGS, multiples=MULTIPLES, fractions=FRACTIONS, train_tasks: int = 2000,
          test_tasks: int = 8000, seed: int = SEED, log=print) -> List[dict]:
    rows = []
    for name, model in settings:
        pool = simulate(model, train_tasks + test_tasks, seed=seed)
        train = np.arange(pool.n_tasks) < train_tasks
        log(f"{name}: good {model.good}, high-output chance {model.high}, finishing chance "
            f"{model.finish}, resolving {model.resolve}")
        for f in fractions:
            for m in multiples:
                r = compare(model, m, f, pool, train)
                r["setting"] = name
                rows.append(r)
                log(f"  {m:5.1f}x median attempt, review {f}: optimum {r['optimum']:.4f}"
                    f" (replayed {r['optimum_replayed']:.4f}, K {r['optimum_budget']})"
                    f"  rule {r['rule']:.4f} (K {r['rule_budget']})"
                    f"  rule above optimum {r['rule'] - r['optimum']:+.4f}"
                    f" ({(r['rule'] - r['optimum']) / r['optimum']:+.1%})"
                    f"  constant {r['constant']:.4f}  retry {r['retry']:.4f}"
                    f"  | first attempts stopped: optimum {r['optimum_stops']:.0%}"
                    f" at {r['optimum_stop_at']:.0f} calls, rule {r['rule_stops']:.0%}"
                    f" at {r['rule_stop_at']:.0f}")
    return rows


def _main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="results/dynamic_program.log")
    a = ap.parse_args(argv)
    lines: List[str] = []

    def log(line):
        print(line, flush=True)
        lines.append(line)

    study(log=log)
    with open(a.out, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"-> {a.out}")


if __name__ == "__main__":
    _main()
