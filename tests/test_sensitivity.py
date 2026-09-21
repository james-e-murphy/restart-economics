"""The sensitivity runner: each variant changes what it says, the fast path of the bootstrap is the
evaluator's arithmetic, and the two-stage bootstrap resamples what it says it resamples."""
import csv
import dataclasses
import os
from unittest import mock

import numpy as np
import pytest

from restart import evaluate as ev
from restart import inference as inf
from restart import ladder as ld
from restart import policies as po
from restart import pricing
from restart import sensitivity as se


def _pool(n=80, seed=3, name="m", cap=100, knock=True, minutes=None):
    """Attempts of varying length and outcome, with a few draws outside the pool."""
    rng = np.random.default_rng(seed)
    tasks = tuple(f"t{i}" for i in range(n))
    skill = rng.normal(0, 1, n)
    cost, out, wins = [], [], []
    for i in range(n):
        rc, ro, rw = [], [], []
        for _ in range(4):
            calls = int(np.clip(rng.lognormal(3.0, 0.7), 3, cap))
            rw.append(bool(rng.random() < 1 / (1 + np.exp(-(skill[i] + 1 - calls / 15)))))
            rc.append(list(rng.gamma(2.0, 0.01, calls)))
            ro.append(list(rng.gamma(2.0, 50.0, calls)))
        cost.append(rc), out.append(ro), wins.append(rw)
    usable = np.ones((n, 4), bool)
    if knock:
        usable[:4, 3] = False
        usable[4:6, 2:] = False
    if minutes is None:
        minutes = np.random.default_rng(seed + 1).choice([3.9, 30.0, 120.0], n)
    return ev.build(name, cap, tasks, ("1", "2", "3", "4"), cost, out, wins,
                    candidate=[[True] * 4] * n, usable=usable, minutes=minutes)


def _pools(names=("a", "b", "c"), n=40):
    minutes = np.random.default_rng(99).choice([3.9, 30.0, 120.0], n)
    return {c: _pool(n=n, seed=10 + j, name=c, minutes=minutes) for j, c in enumerate(names)}


# ----------------------------------------------------------------------------- the fast path

@pytest.mark.parametrize("rate,fraction,phi", [(5.0, 0.0, 0.0), (100.0, 0.3, 0.5), (40.0, 0.5, 0.34)])
def test_the_coefficients_price_every_fixed_policy_as_the_evaluator_does(rate, fraction, phi):
    pool = _pool()
    fx = se.fixed(pool)
    h = ev.outside_option(pool, rate)
    v = ev.verification(h, fraction)
    policies = po.constant_family(pool.config, pool.grid)
    fam = ld._family(pool, policies, h, v, phi, None)
    assert fx.labels == fam.labels
    assert np.array_equal(fx.used, fam.used)
    assert np.allclose(np.where(fam.used, fx.values(h, v, phi), 0), fam.values, atol=1e-10)


def test_the_fast_cross_fit_is_the_cross_fit_at_every_point_of_the_sweep():
    pool = _pool()
    fx = se.fixed(pool)
    mask = ev.full_draw_tasks({pool.config: pool})
    hours = pool.minutes / 60.0
    rates = np.array([2.0, 5.0, 25.0, 100.0, 300.0] * 2)
    fractions = np.array([0.0] * 5 + [0.5] * 5)
    rng = np.random.default_rng(0)
    for _ in range(5):
        idx = rng.integers(0, pool.n_tasks, pool.n_tasks)
        label = inf.replicate_folds(idx)
        here = fx.take(idx)
        fast = se.cap_margins(here, hours[idx], label, mask[idx], rates, fractions, 0.34)
        for j, (rate, f) in enumerate(zip(rates, fractions)):
            h = ev.outside_option(pool, rate)[idx]
            assert fast[j] == pytest.approx(se.cap_margin(here, h, f * h, 0.34, label, mask[idx]),
                                            abs=1e-10)


def test_the_fast_interval_is_the_ladder_s_interval():
    pool = _pool()
    got = se.cap_intervals(pool, replicates=40, rates=(5.0, 60.0), multiples=(),
                           regimes=(("automated", 0.0), ("human 0.5", 0.5)), stage_two=False)
    for row in got:
        ref = ld.rung(pool, row["rate"], row["regime"], replicates=40, steps=())
        assert row["estimate"] == pytest.approx(ref["cap_margin"], abs=1e-10)
        assert row["one_stage_low"] == pytest.approx(ref["cap_margin_low"], abs=1e-10)
        assert row["one_stage_high"] == pytest.approx(ref["cap_margin_high"], abs=1e-10)
        assert row["one_stage_replicates"] == ref["replicates"] == 40
        assert row["two_stage_low"] == ""


def test_a_second_stage_that_keeps_every_draw_is_the_first_stage():
    pool = _pool()
    fx = se.fixed(pool)
    idx = np.random.default_rng(4).integers(0, pool.n_tasks, pool.n_tasks)
    same = ev.resample(pool, idx, np.tile(np.arange(4), (pool.n_tasks, 1)))
    again = se.fixed(same)
    for name in ("spend", "checks", "resolves", "fails", "used"):
        assert np.array_equal(getattr(again, name), getattr(fx.take(idx), name)), name


def test_where_a_task_s_draws_are_alike_the_second_stage_changes_nothing():
    """Resampling draws that are copies of one another returns the same task, so on such a pool
    the two-stage interval is the one-stage interval exactly."""
    pool = _pool(knock=False)
    first = lambda x: np.repeat(x[:, :1], 4, axis=1)            # noqa: E731
    alike = dataclasses.replace(
        pool, calls=first(pool.calls), resolved=first(pool.resolved),
        candidate=first(pool.candidate), cost_end=first(pool.cost_end),
        out_end=first(pool.out_end), cost_grid=first(pool.cost_grid),
        out_grid=first(pool.out_grid), out_recent=first(pool.out_recent),
        cost_rate=first(pool.cost_rate), alive=first(pool.alive))
    got = se.cap_intervals(alike, replicates=30, rates=(10.0, 100.0), multiples=(),
                           regimes=(("automated", 0.0),))
    for row in got:
        assert row["two_stage_low"] == pytest.approx(row["one_stage_low"], abs=1e-10)
        assert row["two_stage_high"] == pytest.approx(row["one_stage_high"], abs=1e-10)
        assert row["two_stage_mean"] == pytest.approx(row["one_stage_mean"], abs=1e-10)


def test_the_second_stage_draws_only_usable_draws_and_keeps_their_number():
    pool = _pool()
    rng = np.random.default_rng(1)
    for _ in range(20):
        idx = rng.integers(0, pool.n_tasks, pool.n_tasks)
        draws = se.redraw(pool.usable[idx], rng)
        again = ev.resample(pool, idx, draws)
        assert np.array_equal(again.usable.sum(axis=1), pool.usable[idx].sum(axis=1))
        assert np.array_equal(ev.full_draw_tasks({"m": again}),
                              ev.full_draw_tasks({"m": pool})[idx])
    # and it does resample: a task drawn with every draw usable does not always keep all four
    draws = se.redraw(np.ones((200, 4), bool), np.random.default_rng(2))
    assert (np.sort(draws, axis=1) != np.arange(4)).any(axis=1).mean() > 0.5


def test_the_two_stage_interval_is_computed_where_the_one_stage_one_is():
    pool = _pool()
    got = se.cap_intervals(pool, replicates=25, rates=(5.0, 100.0), multiples=(1.0,),
                           regimes=(("automated", 0.0),))
    assert [r["axis"] for r in got] == ["rate", "rate", "multiple"]
    for row in got:
        assert row["two_stage_low"] <= row["two_stage_mean"] <= row["two_stage_high"]
        assert row["one_stage_low"] <= row["one_stage_mean"] <= row["one_stage_high"]
        assert row["replicates"] + row["dropped"] == 25


def test_the_transfer_s_two_stage_interval():
    pools = _pools()
    target, others = "a", ["b", "c"]
    source = {c: ev.reindex(pools[c], pools[target].tasks) for c in others}
    got = se.two_stage_transfer(pools[target], source, others, replicates=4, rates=(25.0, 100.0))
    ref = ld.rung(pools[target], 100.0, 0.0, replicates=0, steps=("iii-b", "transfer"),
                  transfer=(source, others))
    assert [r["rate"] for r in got] == [25.0, 100.0]
    assert got[1]["estimate"] == pytest.approx(ref["transfer_margin"])
    for row in got:
        assert row["margin"] == "transfer" and row["replicates"] + row["dropped"] == 4
        assert row["two_stage_low"] <= row["two_stage_high"]


# ----------------------------------------------------------------------------- the variants

def test_every_registered_sensitivity_is_a_variant():
    names = {v.name for v in se.VARIANTS}
    assert names == {"phi 0.34", "phi 0.50", "common horizon 100", "all tasks",
                     "refusals excluded", "no verdict unresolved", "re-runs dropped",
                     "Qwen lowest price", "METR minutes"}
    assert len({v.key for v in se.VARIANTS}) == len(se.VARIANTS)


def test_each_variant_asks_the_loader_for_what_it_changes(tmp_path):
    seen = []

    def fake_load(folder, **kw):
        seen.append((os.path.basename(folder.rstrip("/")), kw))
        return _pool(n=20, cap=500, name=os.path.basename(folder.rstrip("/")))

    folders = [str(tmp_path / "x_4runs") + "/"]
    with mock.patch.object(ev, "load", fake_load):
        for v in se.VARIANTS:
            seen.clear()
            pools = se.load_pools(v, folders)
            kw = seen[0][1]
            assert kw.get("retain_refusals", True) is (v.key != "refusals")
            assert kw.get("no_verdict_unresolved", False) is (v.key == "no-verdict")
            assert kw.get("drop_reruns", False) is (v.key == "reruns")
            if v.key == "qwen-price":
                q = "qwen3-coder-480b-a35b-instruct-4runs"
                assert kw["schedules"][q] == pricing.SENSITIVITY[q]
            else:
                assert "schedules" not in kw
            if v.key == "metr":
                assert kw["annotation_minutes"] == ev.metr_minutes()
            else:
                assert "annotation_minutes" not in kw
            pool = pools["x_4runs"]
            assert (pool.cap == 100) is (v.key == "horizon")


def test_variants_that_read_the_same_tables_read_them_once(tmp_path):
    calls = []

    def fake_load(folder, **kw):
        calls.append(kw)
        return _pool(n=20, cap=500)

    cache = {}
    with mock.patch.object(ev, "load", fake_load):
        for key in ("phi-0.34", "phi-0.50", "horizon", "all-tasks", "refusals"):
            se.load_pools(se.BY_KEY[key], [str(tmp_path / "x")], cache)
    assert len(calls) == 2


def test_the_all_tasks_basis_scores_tasks_the_primary_leaves_out():
    pool = _pool()
    primary, every = se.basis(se.PRIMARY, pool), se.basis(se.BY_KEY["all-tasks"], pool)
    assert primary.sum() == pool.n_tasks - 6 and every.all()
    rows_p, _ = se.ladder_rows(se.PRIMARY, {"m": pool}, replicates=10, steps=(),
                               rates=(100.0,), multiples=(), scan=4)
    rows_a, _ = se.ladder_rows(se.BY_KEY["all-tasks"], {"m": pool}, replicates=10, steps=(),
                               rates=(100.0,), multiples=(), scan=4)
    first = lambda rows: [r for r in rows if r["regime_name"] == "automated"][0]  # noqa: E731
    assert first(rows_a)["tasks"] > first(rows_p)["tasks"]


def test_the_primary_variant_reproduces_the_ladder():
    pool = _pool()
    rows, found = se.ladder_rows(se.PRIMARY, {"m": pool}, replicates=30, steps=("iii-b",),
                                 rates=(10.0, 100.0), multiples=(2.0,),
                                 regimes=(("automated", 0.0), ("human 0.5", 0.5)), scan=6)
    ref = ld.ladder(pool, rates=(10.0, 100.0), multiples=(), steps=("iii-b",), replicates=30,
                    fitted_replicates=0, regimes=(("automated", 0.0), ("human 0.5", 0.5)))
    at = {(r["regime_name"], r["rate"]): r for r in rows if r["axis"] == "rate"}
    for r in ref:
        got = at[(r["regime_name"], r["rate"])]
        for key in ("value_i", "value_ii", "value_iii", "value_iiib", "cap_margin",
                    "cap_margin_low", "cap_margin_high", "replicates"):
            assert got[key] == pytest.approx(r[key], abs=1e-10), key
        assert got["variant"] == "primary"
    assert {r["regime_name"] for r in found} == {"automated", "human 0.5"}


def test_a_row_the_fast_path_does_not_reproduce_takes_the_ladder_s_bootstrap():
    pool = _pool()
    mask = ev.full_draw_tasks({pool.config: pool})
    rows = ld.ladder(pool, rates=(50.0,), multiples=(), regimes=(("automated", 0.0),),
                     replicates=0, steps=(), fitted_replicates=0)
    bands = se.cap_intervals(pool, 20, rates=(50.0,), multiples=(),
                             regimes=(("automated", 0.0),), stage_two=False)
    bands[0]["estimate"] += 1.0
    assert se.attach(rows, bands, pool, 0.0, mask, 20) == 1
    ref = ld.rung(pool, 50.0, 0.0, replicates=20, steps=())
    assert rows[0]["cap_margin_low"] == pytest.approx(ref["cap_margin_low"])


# ----------------------------------------------------------------------------- the runner

def test_the_runner_writes_every_file_it_is_asked_for(tmp_path):
    pools = _pools()

    def fake_load(folder, **kw):
        return pools[os.path.basename(folder.rstrip("/"))]

    folders = [str(tmp_path / c) + "/" for c in pools]
    with mock.patch.object(ld, "configurations", lambda derived, notes, only=None: folders), \
            mock.patch.object(ev, "load", fake_load):
        se._main(["--variants", "phi-0.50", "all-tasks", "--out-dir", str(tmp_path / "out"),
                  "--replicates", "6", "--two-stage-replicates", "5",
                  "--transfer-replicates", "2", "--rates", "25", "100", "--multiples", "2",
                  "--scan", "4", "--steps", "iii-b", "transfer"])
    out = tmp_path / "out"
    with open(out / "sensitivity_ladder.csv", newline="") as fh:
        ladder = list(csv.DictReader(fh))
    assert {r["variant"] for r in ladder} == {"phi 0.50", "all tasks"}
    assert set(ladder[0]) == set(se.LADDER_FIELDS)
    # three configurations, four regimes, two rates and one multiple, under two variants
    assert len(ladder) == 2 * 3 * 4 * 3
    assert {r["phi"] for r in ladder if r["variant"] == "phi 0.50"} == {"0.5"}
    with open(out / "sensitivity_breakeven.csv", newline="") as fh:
        assert {r["variant"] for r in csv.DictReader(fh)} == {"phi 0.50", "all tasks"}
    with open(out / "sensitivity_cascade.csv", newline="") as fh:
        cascade = list(csv.DictReader(fh))
    assert len(cascade) == 2 * 4 * 2
    with open(out / "sensitivity_two_stage.csv", newline="") as fh:
        two = list(csv.DictReader(fh))
    assert {r["margin"] for r in two} == {"cap", "transfer"}
    assert len([r for r in two if r["margin"] == "cap"]) == 3 * 4 * 3
    assert len([r for r in two if r["margin"] == "transfer"]) == 3 * 2
