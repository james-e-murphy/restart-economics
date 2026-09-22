"""The appendix runners end to end: each reads the included configurations, as the ladder's does,
and writes the file results/README.md says it writes, in the columns it names."""
import csv
import os
from unittest import mock

import numpy as np
import pytest

from restart import appendix as ap
from restart import comparators as cp
from restart import diagnostics as dg
from restart import evaluate as ev
from restart import fitted as ft
from restart import ladder as ld
from restart import oracle as orc


def _pools(names=("a", "b", "c"), n=30):
    rng = np.random.default_rng(12)
    tasks = tuple(f"t{i}" for i in range(n))
    minutes = rng.choice([3.9, 30.0, 120.0], n)
    skill = rng.normal(0, 1, n)
    out = {}
    for j, name in enumerate(names):
        cost, toks, wins = [], [], []
        for i in range(n):
            rc, ro, rw = [], [], []
            for _ in range(4):
                calls = int(np.clip(rng.lognormal(3.0, 0.6), 3, 99))
                rw.append(bool(rng.random() < 1 / (1 + np.exp(-(skill[i] + 0.5 - calls / 20)))))
                rc.append(list(rng.gamma(2.0, 0.01 * (1 + j), calls)))
                ro.append([20.0] * calls)
            cost.append(rc), toks.append(ro), wins.append(rw)
        out[name] = ev.build(name, 100, tasks, ("1", "2", "3", "4"), cost, toks, wins,
                             candidate=[[True] * 4] * n, usable=[[True] * 4] * n,
                             minutes=minutes)
    return out


@pytest.fixture
def patched(tmp_path):
    pools = _pools()
    folders = [str(tmp_path / c) + "/" for c in pools]
    with mock.patch.object(ld, "configurations",
                           lambda derived, notes, only=None: [f for f in folders
                                                              if not only or
                                                              os.path.basename(f[:-1]) in only]), \
            mock.patch.object(ev, "load", lambda f, **kw: pools[os.path.basename(f.rstrip("/"))]):
        yield tmp_path


def _read(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def test_the_comparators_runner(patched):
    out = patched / "comparators.csv"
    cp._main(["--out", str(out), "--rates", "25", "100", "--multiples", "2", "--replicates", "2"])
    rows = _read(out)
    assert len(rows) == 3 * 4 * 3 and set(rows[0]) == set(cp.FIELDS)
    assert {r["fitted_replicates"] for r in rows if r["regime_name"] == "automated"
            and r["axis"] == "rate" and float(r["rate"]) == 100.0} == {"2"}


def test_the_oracle_runner(patched):
    out = patched / "oracle.csv"
    orc._main(["--out", str(out), "--rates", "25", "100"])
    rows = _read(out)
    assert len(rows) == 4 * 2 and set(rows[0]) == set(orc.FIELDS)
    for r in rows:
        assert float(r["value_oracle"]) <= float(r["value_cascade"]) + 1e-9
        assert float(r["oracle_gap"]) >= -1e-9


def test_the_appendix_runner(patched):
    ap._main(["--out-dir", str(patched), "--rates", "25", "100", "--replicates", "5"])
    diff = _read(patched / "difficulty.csv")
    dist = _read(patched / "distribution.csv")
    spread = _read(patched / "spread.csv")
    assert set(diff[0]) == set(ap.DIFFICULTY_FIELDS) and set(dist[0]) == set(ap.DISTRIBUTION_FIELDS)
    assert len(dist) == 3 * 4 * 2 and len(spread) == 4 * 2
    assert {"all, chosen within bucket", "all, chosen blind"} <= {r["bucket"] for r in diff}


def test_the_diagnostics_runner(patched):
    dg._main(["--out-dir", str(patched)])
    assert len(_read(patched / "diagnostics.csv")) == 3
    tails = _read(patched / "tail_composition.csv")
    assert len(tails) == 3 * 19 and set(tails[0]) == set(dg.TAIL_FIELDS)


def test_the_fitted_runner_refines_the_ladder_in_place(patched):
    out = patched / "ladder.csv"
    ld._main(["--out", str(out), "--replicates", "0", "--fitted-replicates", "3", "--only", "a"])
    before = _read(out)
    ft._main(["--ladder", str(out), "--replicates", "5", "--rates", "100", "--only", "a"])
    after = _read(out)
    assert len(after) == len(before) and set(after[0]) == set(ld.FIELDS)
    refined = [r for r in after if r["regime_name"] == "automated" and r["axis"] == "rate"
               and float(r["rate"]) == 100.0]
    assert {r["fitted_replicates"] for r in refined} == {"5"}
    untouched = [r for r in after if not (r["regime_name"] == "automated" and r["axis"] == "rate"
                                          and float(r["rate"]) == 100.0)]
    assert all(r["fitted_replicates"] in ("0", "3") for r in untouched)
    for b, a in zip(before, after):
        assert b["value_iv_transfer"] == a["value_iv_transfer"]

