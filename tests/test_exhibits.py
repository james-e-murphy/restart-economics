"""The exhibits script, run end to end on results the evaluator wrote for synthetic pools.

The script computes no policy value, so the test is that it reads every results file the runners
write, in the columns they write, and produces every figure and table; and that the one quantity it
does derive, the exploratory point where retrying first beats escalating, is right.
"""
import csv
import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

matplotlib = pytest.importorskip("matplotlib")

from restart import breakeven as be          # noqa: E402
from restart import cascade as cs            # noqa: E402
from restart import evaluate as ev           # noqa: E402
from restart import ladder as ld             # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MAKE = os.path.join(HERE, os.pardir, "exhibits", "make.py")


def _module():
    spec = importlib.util.spec_from_file_location("exhibits_make", MAKE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pools(n=40, names=("m1", "m2"), seed=5):
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    skill = rng.normal(0, 1, n)
    out = {}
    for j, name in enumerate(names):
        cost, outs, wins = [], [], []
        for i in range(n):
            row_c, row_o, row_w = [], [], []
            for _ in range(4):
                calls = int(np.clip(rng.gamma(2.0, 8.0), 3, 99))
                row_w.append(bool(rng.random() < 1 / (1 + np.exp(-(skill[i] + 1 - calls / 10)))))
                row_c.append([0.04 * (1 + j)] * calls)
                row_o.append([50.0] * calls)
            cost.append(row_c), outs.append(row_o), wins.append(row_w)
        out[name] = ev.build(name, 100, tasks, ("1", "2", "3", "4"), cost, outs, wins,
                             candidate=[[True] * 4] * n, usable=[[True] * 4] * n,
                             minutes=[30.0] * n)
    return out


def _write(rows, path, fields=None):
    fields = fields or list(rows[0])
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    root = tmp_path_factory.mktemp("results")
    pools = _pools()
    rows, crossings = [], []
    for name, pool in pools.items():
        other = [c for c in pools if c != name]
        source = {c: ev.reindex(pools[c], pool.tasks) for c in other}
        rows += ld.ladder(pool, rates=(5.0, 25.0, 100.0, 300.0), multiples=(0.5, 2.0, 20.0),
                          replicates=10, fitted_replicates=4, fitted_rates=(25.0, 100.0, 300.0),
                          transfer=(source, other))
    ld.write(rows, str(root / "ladder.csv"))
    with open(root / "ladder.csv", newline="") as fh:
        ladder_rows = list(csv.DictReader(fh))
    for pool in pools.values():
        crossings += be.rows_for(pool, ladder_rows=ladder_rows, scan=8)
    be.write(crossings, str(root / "breakeven.csv"))
    aligned = ev.align(pools)
    cells = []
    for regime, fraction in ld.REGIMES:
        for rate in (5.0, 25.0, 100.0):
            row = cs.cell(aligned, rate, fraction, replicates=0)
            row["regime_name"] = regime
            cells.append(row)
    _write(cells, str(root / "cascade.csv"))
    names, corr, _ = cs.outcome_correlation(aligned)
    with open(root / "outcome_correlation.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["configuration"] + list(names))
        for c, r in zip(names, corr):
            w.writerow([c] + list(r))
    return root


def test_every_exhibit_is_written_from_the_results_files(results, tmp_path):
    make = _module()
    out = tmp_path / "out"
    make.main(["--results", str(results), "--out", str(out)])
    for stem in ("fig1_cap_margin", "fig2_transfer", "figA2_transfer_review_05", "fig3_cascade",
                 "fig4_break_even_in_attempts", "figA1_outcome_correlation"):
        for ext in ("pdf", "png"):
            assert (out / f"{stem}.{ext}").stat().st_size > 0, stem
    for stem in ("table1_ladder", "table2_breakeven", "table3_transfer"):
        for ext in ("csv", "md", "tex"):
            assert (out / f"{stem}.{ext}").stat().st_size > 0, stem
    t1 = pd.read_csv(out / "table1_ladder.csv")
    assert set(t1.configuration) == {"m1", "m2"}
    assert len(t1) == 2 * 2 * 3                 # regimes x configurations x rates


def test_the_point_where_retrying_first_beats_escalating(results):
    make = _module()
    d = pd.read_csv(results / "ladder.csv")
    for config in ("m1", "m2"):
        above = make.agent_pays_above(d, config, "automated")
        s = make._sweep(d, config, "automated")
        if np.isfinite(above):
            below = s[s.multiple < above * 0.98]
            beyond = s[s.multiple > above * 1.02]
            # below it, retrying without a cap costs more than escalating; just past it, less
            assert (below.value_ii > below.value_escalate).all()
            assert beyond.empty or beyond.iloc[0].value_ii <= beyond.iloc[0].value_escalate
