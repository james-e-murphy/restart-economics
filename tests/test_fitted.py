"""The refinement of the fitted steps' intervals reproduces the ladder's own intervals at the
same replicate count, from the same resamples, and writes them back into the ladder's rows."""
import numpy as np
import pytest

from restart import evaluate as ev
from restart import fitted as ft
from restart import ladder as ld


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


def test_the_refinement_reproduces_the_ladders_intervals_and_merges_them():
    pools = _pools()
    pool, other = pools["m1"], ["m2"]
    source = {"m2": ev.reindex(pools["m2"], pool.tasks)}
    rates = (25.0, 100.0)
    rows = ld.ladder(pool, rates=rates, multiples=(), regimes=(("automated", 0.0),),
                     replicates=0, fitted_replicates=4, fitted_rates=rates,
                     transfer=(source, other))
    refined = ft.refine(pool, source, other, rates=rates, replicates=4)
    assert len(refined) == 2
    for r, f in zip(rows, refined):
        for k in ("value_iiib", "value_iv", "value_iv_transfer"):
            assert r[k] == pytest.approx(f[k])
        for name in ft.MARGINS:
            assert r[name] == pytest.approx(f[name])
            assert r[f"{name}_low"] == pytest.approx(f[f"{name}_low"])
            assert r[f"{name}_high"] == pytest.approx(f[f"{name}_high"])
    # a refinement at more replicates nests the ladder's: same first resamples, new count
    more = ft.refine(pool, source, other, rates=(25.0,), replicates=8)
    assert more[0]["fitted_replicates"] == 8
    stale = [dict(r, transfer_margin_low="", transfer_margin_high="", fitted_replicates=0)
             for r in rows]
    assert ft.merge(stale, more) == 1
    assert stale[0]["fitted_replicates"] == 8
    assert stale[0]["transfer_margin_low"] == pytest.approx(more[0]["transfer_margin_low"])
    assert stale[1]["fitted_replicates"] == 0
    # a point estimate that disagrees is a bug, not something to overwrite
    wrong = [dict(r, value_iv=float(r["value_iv"]) + 1.0) for r in rows]
    with pytest.raises(AssertionError):
        ft.merge(wrong, refined)
