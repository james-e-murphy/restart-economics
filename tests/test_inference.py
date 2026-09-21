"""Cross-fitting and the bootstrap, against cases whose answers are known.

Two of the three checks PLAN.md Section 8 asks of the dry run live here: that cross-fitting
removes in-sample optimism, and that the bootstrap covers at about its nominal rate for a ratio
estimand under heavy-tailed spend. The third, that the enumerator recovers a known optimum, is in
test_evaluate.py.
"""
import numpy as np
import pytest

from restart import inference as inf


def _family(values, used=None, labels=None):
    values = np.asarray(values, float)
    used = np.ones_like(values, bool) if used is None else np.asarray(used, bool)
    labels = labels or tuple(f"p{i}" for i in range(values.shape[0]))
    return inf.Family(values=values, used=used, labels=tuple(labels))


def test_the_split_is_a_partition_and_is_fixed():
    label = inf.folds(500)
    assert label.shape == (500,) and set(np.unique(label)) == set(range(5))
    assert np.bincount(label).tolist() == [100] * 5
    assert (inf.folds(500) == label).all()          # the split is settled once, by seed


def test_the_best_candidate_is_chosen_in_every_fold_and_scored_out_of_sample():
    rng = np.random.default_rng(0)
    n = 200
    good = 5.0 + rng.normal(0, 0.1, n)
    bad = 9.0 + rng.normal(0, 0.1, n)
    fam = _family([good, bad], labels=("good", "bad"))
    got = inf.cross_fit(fam, inf.folds(n))
    assert got.choices == ("good",) * 5
    assert got.n_tasks == n
    assert got.value == pytest.approx(good.mean())


def test_a_task_a_policy_cannot_fill_is_not_scored_for_it():
    n = 50
    values = np.vstack([np.full(n, 3.0), np.full(n, 1.0)])
    used = np.ones((2, n), bool)
    used[1, :10] = False                              # the cheaper candidate needs four draws
    got = inf.cross_fit(_family(values, used), inf.folds(n))
    assert got.n_tasks == n - 10 and not got.scored[:10].any()
    assert got.value == pytest.approx(1.0)
    restricted = inf.cross_fit(_family(values, used), inf.folds(n),
                               restrict=np.arange(n) >= 10)
    assert restricted.n_tasks == n - 10


def test_cross_fitting_removes_the_optimism_of_choosing_and_scoring_on_one_sample():
    """Forty candidates that are all the same policy in disguise: their true value is identical,
    so any gap between the best in-sample mean and the truth is selection, not value."""
    rng = np.random.default_rng(3)
    n, m, truth = 300, 40, 10.0
    fam = _family(truth + rng.normal(0, 1.0, (m, n)))
    optimistic, _ = inf.in_sample(fam)
    honest = inf.cross_fit(fam, inf.folds(n)).value
    assert optimistic < truth - 0.02                   # the winner's curse, in dollars
    assert abs(honest - truth) < 0.15
    assert honest > optimistic


def test_the_bootstrap_covers_at_about_its_nominal_rate_for_a_ratio_under_heavy_tails():
    rng = np.random.default_rng(11)
    n, sims, reps = 300, 200, 200
    mu, sigma = 0.0, 1.5
    truth = 1.0                                        # both arms are the same lognormal
    covered = 0
    for s in range(sims):
        spend = rng.lognormal(mu, sigma, (2, n))
        def ratio(idx, spend=spend):
            return spend[0][idx].mean() / spend[1][idx].mean()
        got = inf.bootstrap(n, ratio, replicates=reps, seed=s)
        covered += got["low"] <= truth <= got["high"]
    rate = covered / sims
    assert 0.85 <= rate <= 0.99, f"coverage {rate:.3f}"


def test_the_bootstrap_carries_selection_variation_and_reports_what_it_dropped():
    rng = np.random.default_rng(5)
    n, m = 200, 30
    fam = _family(10.0 + rng.normal(0, 1.0, (m, n)))
    point = inf.cross_fitted_value(fam)
    got = inf.bootstrap(n, lambda idx: inf.cross_fitted_value(fam, idx), replicates=150, seed=1)
    assert got["replicates"] == 150 and got["dropped"] == 0
    assert got["low"] < point < got["high"]
    assert got["high"] - got["low"] > 0.05             # selection and sampling both move it

    empty = inf.bootstrap(n, lambda idx: float("nan"), replicates=10, seed=1)
    assert empty["dropped"] == 10 and empty["replicates"] == 0


def test_a_margin_is_positive_when_the_richer_family_is_cheaper():
    n = 200
    baseline = _family([np.full(n, 8.0)], labels=("baseline",))
    richer = _family([np.full(n, 8.0), np.full(n, 6.0)], labels=("same", "cheaper"))
    assert inf.margin(baseline, richer) == pytest.approx(2.0)
    assert inf.margin(richer, baseline) == pytest.approx(-2.0)


def test_a_fitted_family_is_refitted_on_each_training_set_and_on_each_resample():
    """A rule fitted on the training tasks: here it reads their mean, which is what a real state
    rule's restart values do. The point is that it never sees the tasks it is scored on."""
    n = 120
    truth = np.linspace(1.0, 5.0, n)
    seen = []

    def fit(train):
        seen.append(int(train.sum()))
        level = truth[train].mean() + 1.0          # a rule that is worse than the truth by a dollar
        return np.vstack([np.full(n, level), truth]), np.ones((2, n), bool)

    fam = inf.Family(values=np.zeros((2, n)), used=np.ones((2, n), bool),
                     labels=("fitted", "truth"), fit=fit)
    got = inf.cross_fit(fam, inf.folds(n))
    assert len(seen) == 5 and all(s == n - n // 5 for s in seen)
    assert got.choices == ("truth",) * 5               # the fitted rule loses to the truth

    seen.clear()
    idx = np.arange(n)[::-1]                           # a resample that reorders the tasks
    inf.cross_fit(inf.resampled(fam, idx), inf.folds(n))
    assert len(seen) == 5 and all(s == n - n // 5 for s in seen)


# ----------------------------------------------------------------------------- the replicate's split

def test_every_copy_of_a_resampled_task_lands_in_the_same_fold():
    rng = np.random.default_rng(1)
    for _ in range(20):
        idx = rng.integers(0, 300, 300)
        label = inf.replicate_folds(idx)
        for t in np.unique(idx):
            assert len(set(label[idx == t])) == 1
        assert set(label) == set(range(inf.FOLDS))
    # the split is a function of the resample, so both families of a margin are split alike
    idx = rng.integers(0, 300, 300)
    assert (inf.replicate_folds(idx) == inf.replicate_folds(idx.copy())).all()
    assert not (inf.replicate_folds(idx) == inf.replicate_folds(rng.integers(0, 300, 300))).all()


def test_a_replicate_does_not_score_a_choice_on_the_task_that_made_it():
    """Sixty candidates of pure noise, each truly worth 1.0. Selecting among them in sample finds
    one that looks far cheaper; cross-fitting should not, and neither should a replicate of it.
    Splitting a replicate by position instead of by task is shown to fail the same check, so the
    test has the power to see the leak it guards against."""
    rng = np.random.default_rng(2)
    tasks, cands = 200, 60
    values = 1.0 + rng.normal(0, 1, (cands, tasks))
    fam = inf.Family(values=values, used=np.ones_like(values, bool),
                     labels=tuple(str(i) for i in range(cands)))
    idxs = [rng.integers(0, tasks, tasks) for _ in range(150)]
    grouped = np.mean([inf.cross_fitted_value(fam, idx) for idx in idxs])
    by_position = np.mean([inf.cross_fit(inf.resampled(fam, idx), inf.folds(tasks)).value
                           for idx in idxs])
    assert abs(grouped - 1.0) < 0.05
    assert by_position < 0.95


def test_the_coverage_study_runs_and_its_point_estimate_is_centred_on_its_target():
    from restart import coverage
    pool = coverage.population(n=1500, seed=5)
    got = coverage.study(pool, 5.0, 0.0, datasets=12, replicates=40, sample=300, train=240,
                         truth_draws=60)
    assert 0.0 <= got["coverage"] <= 1.0 and got["width"] > 0
    assert abs(got["bias"]) < 4 * got["bias_se"] + 0.05
