"""The break-even rate: locating the sign change in the cap's marginal value."""
import csv

import numpy as np
import pytest

from restart import breakeven as be
from restart import evaluate as ev
from restart import ladder as ld


def _world(n=80, seed=4, per_call=0.1):
    """Long attempts are likelier to fail, so a cap saves money while the outside option is cheap
    and costs money once a lost success is dear."""
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    cost, out, resolved = [], [], []
    for _ in tasks:
        row, wins = [], []
        for _ in range(4):
            calls = int(np.clip(rng.gamma(2.0, 10.0), 3, 99))
            wins.append(bool(rng.random() < 1 / (1 + np.exp((calls - 20) / 6.0))))
            row.append(([per_call] * calls, [10.0] * calls))
        cost.append([c for c, _ in row])
        out.append([o for _, o in row])
        resolved.append(wins)
    return ev.build("m", 100, tasks, ("1", "2", "3", "4"), cost, out, resolved,
                    candidate=[[True] * 4 for _ in tasks], usable=[[True] * 4 for _ in tasks],
                    minutes=[60.0] * n)


def test_the_crossing_is_where_the_margin_changes_sign():
    pool = _world()
    got = be.crossings(pool, fraction=0.0, scan=12)
    # the world is built so the cap saves while escalation is cheap and costs once it is dear
    assert got["sign_low"] == 1 and got["sign_high"] == -1
    assert got["crossings"]
    first = got["crossings"][0]
    brackets = [(float(got["grid"][i]), float(got["grid"][i + 1]))
                for i in range(len(got["grid"]) - 1)
                if be._sign(got["values"][i]) != be._sign(got["values"][i + 1])]
    assert any(lo <= first["rate"] <= hi for lo, hi in brackets)
    assert first["multiple"] == pytest.approx(ev.multiple_for_rate(pool, first["rate"]), rel=1e-9)
    assert "below this rate" in be.direction(first["below"], first["above"])


def test_the_edge_of_a_plateau_at_zero_is_a_crossing():
    # where no fold chooses a cap that binds, the margin is exactly zero, and the rate at which
    # that stops being true is a break-even like any other
    values = [0.4, 0.0, 0.0, -0.3]
    signs = [be._sign(v) for v in values]
    assert [signs[i] != signs[i + 1] for i in range(3)] == [True, False, True]


def test_the_crossing_is_reported_in_both_units():
    pool = _world()
    rows = be.rows_for(pool, regimes=(("automated", 0.0),))
    assert len(rows) >= 1
    row = rows[0]
    if row["crossing"]:
        # the multiple is the mean outside option at the break-even, in attempts
        outside = ev.outside_option(pool, row["rate"])
        mask = ev.full_draw_tasks({pool.config: pool})
        assert (outside[mask].mean() / row["median_attempt_cost"]
                == pytest.approx(row["multiple"], rel=1e-9))
        assert "the cap " in row["direction"] and "above it" in row["direction"]


def test_a_margin_that_never_changes_sign_is_reported_as_such():
    # every attempt resolves at its tenth call, so no cutoff below ten can pay at any rate and the
    # capped family never improves on the uncapped one: the margin is zero across the sweep
    n = 40
    tasks = tuple(f"t{i}" for i in range(n))
    cost = [[[0.1] * 10 for _ in range(4)] for _ in tasks]
    out = [[[10.0] * 10 for _ in range(4)] for _ in tasks]
    pool = ev.build("m", 100, tasks, ("1", "2", "3", "4"), cost, out,
                    resolved=[[True] * 4 for _ in tasks],
                    candidate=[[True] * 4 for _ in tasks],
                    usable=[[True] * 4 for _ in tasks], minutes=[60.0] * n)
    rows = be.rows_for(pool, regimes=(("automated", 0.0),))
    assert len(rows) == 1 and rows[0]["crossing"] == 0
    assert rows[0]["rate"] == "" and rows[0]["direction"] == be.NEVER[0]


def test_the_band_is_the_rates_where_the_interval_still_covers_zero():
    rows = [dict(config="m", regime=0.0, rate=10.0, cap_margin_low=0.2, cap_margin_high=0.5),
            dict(config="m", regime=0.0, rate=50.0, cap_margin_low=-0.1, cap_margin_high=0.3),
            dict(config="m", regime=0.0, rate=100.0, cap_margin_low=-0.4, cap_margin_high=0.1),
            dict(config="m", regime=0.0, rate=300.0, cap_margin_low=-0.9, cap_margin_high=-0.2),
            dict(config="m", regime=0.5, rate=50.0, cap_margin_low=0.1, cap_margin_high=0.4)]
    assert be.band(rows, "m", 0.0) == (50.0, 100.0)
    assert be.band(rows, "m", 0.5) == (None, None)
    assert be.band(rows, "other", 0.0) == (None, None)


def test_bisection_finds_the_crossing_of_a_known_function():
    calls = []

    def f(rate):
        calls.append(rate)
        return 1.0 - rate / 37.0

    got = be.bisect(f, 1.0, 1000.0, tolerance=0.001)
    assert got == pytest.approx(37.0, rel=0.01)
    assert len(calls) < 30


def test_the_rows_write_one_line_per_crossing(tmp_path):
    pool = _world(n=50)
    rows = be.rows_for(pool, regimes=(("automated", 0.0), ("human 0.5", 0.5)))
    path = be.write(rows, str(tmp_path / "results" / "breakeven.csv"))
    with open(path, newline="") as fh:
        back = list(csv.DictReader(fh))
    assert len(back) == len(rows) and set(back[0]) == set(be.FIELDS)
    assert {r["regime_name"] for r in back} == {"automated", "human 0.5"}


def test_the_scan_spans_both_axes_of_the_sweep():
    pool = _world(n=40)
    got = be.crossings(pool, fraction=0.0, scan=6)
    mask = ev.full_draw_tasks({pool.config: pool})
    assert got["scan_low"] <= min(min(ld.RATES),
                                  ev.rate_for_multiple(pool, min(ld.MULTIPLES), mask)) + 1e-9
    assert got["scan_high"] >= max(max(ld.RATES),
                                   ev.rate_for_multiple(pool, max(ld.MULTIPLES), mask)) - 1e-9


def test_a_crossing_is_supported_only_when_the_sweep_resolves_both_sides():
    rows = [dict(config="m", regime=0.0, rate=r, cap_margin=c, cap_margin_low=lo,
                 cap_margin_high=hi)
            for r, c, lo, hi in ((5.0, 0.5, 0.3, 0.7),      # resolved positive
                                 (20.0, -0.01, -0.2, 0.1),  # unresolved, just below zero
                                 (40.0, 0.01, -0.1, 0.2),   # unresolved, just above zero
                                 (100.0, -0.6, -0.9, -0.3)  # resolved negative
                                 )]
    # a sweep that crosses at 10, wobbles back at 30, and crosses again at 60
    bounds = [1.0, 10.0, 30.0, 60.0, 300.0]
    signs = [1, -1, 1, -1]
    assert be.resolved(rows, "m", 0.0, bounds, signs) == [True, False, False, True]


def test_the_rows_say_which_crossings_the_bootstrap_supports():
    pool = _world()
    ladder_rows = ld.ladder(pool, rates=(1.0, 2.0, 5.0, 50.0, 300.0), multiples=(),
                            regimes=(("automated", 0.0),), replicates=40, steps=(),
                            fitted_replicates=0)
    rows = be.rows_for(pool, regimes=(("automated", 0.0),), ladder_rows=ladder_rows)
    for r in rows:
        if r["crossing"]:
            assert r["supported"] in (True, False)
            assert r["supported"] == (r["resolved_below"] and r["resolved_above"])
