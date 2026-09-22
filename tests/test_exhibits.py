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
from restart import sensitivity as se        # noqa: E402
from restart import appendix as ap           # noqa: E402
from restart import comparators as cp        # noqa: E402
from restart import diagnostics as dg        # noqa: E402
from restart import oracle as orc            # noqa: E402

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
    _sensitivities(pools, root)
    _appendix(pools, root)
    return root


def _appendix(pools, root):
    """What the appendix runners write, on the same pools."""
    rates = (25.0, 100.0, 300.0)
    rows, diff, dist, diag, tails = [], [], [], [], []
    for pool in pools.values():
        rows += cp.rows_for(pool, rates=rates, multiples=(), replicates=2)
        diff += ap.difficulty_rows(pool, rates=(100.0,), replicates=10)
        dist += ap.distribution_rows(pool, rates=(100.0,))
        diag.append(dg.summary(pool))
        tails += dg.tail(pool)
    cp.write(rows, str(root / "comparators.csv"))
    ap.write(diff, str(root / "difficulty.csv"), ap.DIFFICULTY_FIELDS)
    ap.write(dist, str(root / "distribution.csv"), ap.DISTRIBUTION_FIELDS)
    ap.write(ap.spread_rows(pools, rates=rates), str(root / "spread.csv"),
             ap.spread_fields(tuple(pools)))
    orc.write(orc.rows_for(pools, rates=rates), str(root / "oracle.csv"))
    dg.write(diag, str(root / "diagnostics.csv"), dg.SUMMARY_FIELDS)
    dg.write(tails, str(root / "tail_composition.csv"), dg.TAIL_FIELDS)


def _sensitivities(pools, root):
    """What ``restart.sensitivity`` writes, for two of its variants, on the same pools."""
    rows, found, casc = [], [], []
    for key in ("phi-0.50", "all-tasks"):
        v = se.BY_KEY[key]
        r, c = se.ladder_rows(v, pools, replicates=8, steps=("iii-b", "transfer"),
                              rates=(5.0, 25.0, 100.0, 300.0), multiples=(0.5, 2.0, 20.0), scan=6)
        rows += r
        found += c
        k, names = se.cascade_rows(v, pools, rates=(25.0, 100.0))
        casc += k
    se.write(rows, str(root / "sensitivity_ladder.csv"), se.LADDER_FIELDS)
    se.write(found, str(root / "sensitivity_breakeven.csv"), se.BREAKEVEN_FIELDS)
    se.write(casc, str(root / "sensitivity_cascade.csv"), ("variant",) + cs.fields(names))
    two = []
    for name, pool in pools.items():
        two += se.cap_intervals(pool, 6, rates=(25.0, 100.0, 300.0), multiples=())
        others = [c for c in pools if c != name]
        source = {c: ev.reindex(pools[c], pool.tasks) for c in others}
        two += se.two_stage_transfer(pool, source, others, 2, rates=(25.0, 100.0, 300.0))
    se.write(two, str(root / "sensitivity_two_stage.csv"), se.TWO_STAGE_FIELDS)


def test_every_exhibit_is_written_from_the_results_files(results, tmp_path):
    make = _module()
    out = tmp_path / "out"
    make.main(["--results", str(results), "--out", str(out)])
    for stem in ("fig1_ladder", "fig2_cap_margin", "fig3_transfer", "figA1_transfer_review_05",
                 "fig4_cascade", "fig5_break_even_in_attempts", "figA2_outcome_correlation",
                 "figA3_tail_composition"):
        for ext in ("pdf", "png"):
            assert (out / f"{stem}.{ext}").stat().st_size > 0, stem
    for stem in ("table1_ladder", "table2_breakeven", "table3_transfer",
                 "tableA1_sensitivity_breakeven", "tableA2_sensitivity_margins",
                 "tableA3_two_stage", "tableA4_comparators", "tableA5_oracle",
                 "tableA6_difficulty", "tableA7_distribution", "tableA8_spread",
                 "tableA9_diagnostics"):
        for ext in ("csv", "md", "tex"):
            assert (out / f"{stem}.{ext}").stat().st_size > 0, stem
    t1 = pd.read_csv(out / "table1_ladder.csv")
    assert set(t1.configuration) == {"m1", "m2"}
    assert len(t1) == 2 * 2 * 3                 # regimes x configurations x rates
    a1 = pd.read_csv(out / "tableA1_sensitivity_breakeven.csv")
    assert list(dict.fromkeys(a1.sensitivity)) == ["primary", "phi 0.50", "all tasks"]
    assert len(a1) == 3 * 4                     # the primary and two variants, by regime
    a2 = pd.read_csv(out / "tableA2_sensitivity_margins.csv")
    assert list(a2.sensitivity) == ["primary", "phi 0.50", "all tasks"]
    a3 = pd.read_csv(out / "tableA3_two_stage.csv")
    assert set(a3.margin) == {"cap, automated verifier", "cap, review at 0.5 H",
                              "transfer, automated verifier"}
    assert a3["two-stage [95%]"].str.startswith("[").all()
    bare = tmp_path / "bare"
    make.main(["--results", str(results), "--out", str(bare), "--bare"])
    assert (bare / "fig2_cap_margin.pdf").stat().st_size > 0
    make.BARE = False
    a6 = pd.read_csv(out / "tableA6_difficulty.csv", dtype=str)
    assert list(a6.columns) == ["regime", "configuration", "under 15 min", "15 min to 1 h",
                                "1 to 4 h", "over 4 h", "1 h or more", "all, within",
                                "all, blind"]
    assert len(a6) == 2 * 2                     # regimes x configurations
    # a bucket too small to choose on shows its count of tasks, in parentheses
    cells = a6[["under 15 min", "15 min to 1 h", "1 to 4 h", "over 4 h", "1 h or more"]]
    assert cells.fillna("").apply(lambda c: c.str.match(r"^(\(\d+\)|-?[\d,]+\.\d\d\*?)?$")).all().all()


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


def test_the_facts_sheet_is_written_from_the_same_files(results, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "facts", os.path.join(os.path.dirname(MAKE), os.pardir, "paper", "facts.py"))
    facts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(facts)
    out = tmp_path / "facts.md"
    facts.main(["--results", str(results), "--out", str(out)])
    text = out.read_text()
    for title in ("## Configurations", "## Comparators", "## Sample oracle", "## Difficulty at $100",
                  "## Distribution of cost at $100", "## Spread", "## Diagnostics"):
        assert title in text, title

