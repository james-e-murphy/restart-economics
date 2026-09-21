"""Every number the manuscript quotes, computed from results/ and written to facts.md.

    python paper/facts.py [--results results] [--out paper/facts.md]

The manuscript is written from this sheet, so a number in the text can be traced to a line here
and from there to the results file and the command that wrote it (results/README.md). Nothing
here is estimated: it selects, rounds and summarizes what the evaluator wrote.
"""
from __future__ import annotations

import argparse
import importlib.util
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("make", os.path.join(HERE, os.pardir, "exhibits",
                                                                    "make.py"))
mk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mk)

RATES = (25.0, 100.0, 300.0)


def _read(results, name):
    p = os.path.join(results, f"{name}.csv")
    return pd.read_csv(p) if os.path.exists(p) else None


def _range(x, places=2, unit=""):
    x = pd.to_numeric(pd.Series(x), errors="coerce").dropna()
    if x.empty:
        return "n/a"
    return f"{x.min():.{places}f}{unit} to {x.max():.{places}f}{unit} (median {x.median():.{places}f}{unit})"


def _md(t: pd.DataFrame) -> str:
    return mk._markdown(t.fillna(""))


def sections(results: str):
    d, b, c = _read(results, "ladder"), _read(results, "breakeven"), _read(results, "cascade")
    corr = _read(results, "outcome_correlation")
    sl, sb, sc_, two = (_read(results, n) for n in ("sensitivity_ladder", "sensitivity_breakeven",
                                                     "sensitivity_cascade", "sensitivity_two_stage"))
    out = []
    order = mk.order_of(d.config)
    rate = d[d.axis == "rate"]

    # --- data
    first = rate.groupby("config").first()
    rows = [{"configuration": mk.label_of(k), "tasks with four usable draws": int(first.loc[k, "tasks"]),
             "median attempt, $": f"{first.loc[k, 'median_attempt_cost']:.3f}",
             "$ an hour at 1x": f"{first.loc[k, 'rate'] / first.loc[k, 'multiple']:.2f}"}
            for k in order]
    out.append(("Configurations", _md(pd.DataFrame(rows)),
                "`$ an hour at 1x` is the rate at which the mean outside option equals one median "
                "attempt; a break-even of M times is M times that rate."))

    # --- retry
    rows = []
    for k in order:
        for r in RATES:
            x = rate[(rate.config == k) & (rate.regime_name == "automated") & (rate.rate == r)].iloc[0]
            rows.append({"configuration": mk.label_of(k), "$/h": int(r), "i": round(x.value_i, 2),
                         "ii": round(x.value_ii, 2), "saving": round(x.retry_value, 2),
                         "saving %": f"{100 * x.retry_value / x.value_i:.1f}",
                         "K chosen": mk._choice(x.choice_ii).replace("attempts, none", "")})
    out.append(("Retry, automated verifier", _md(pd.DataFrame(rows)), ""))
    steps = [c for c in ("value_i", "value_ii", "value_iii", "value_iiib", "value_iv",
                         "value_iv_transfer") if c in rate]
    rows = []
    for regime in ("automated", "human 0.5"):
        for r in RATES:
            x = rate[(rate.regime_name == regime) & (rate.rate == r)]
            med = (x[steps].div(x.value_i, axis=0) * 100).median()
            rows.append({"regime": regime, "$/h": int(r),
                         **{c.replace("value_", ""): round(float(med[c]), 1) for c in steps}})
    out.append(("The ladder in Figure 2: median across configurations, % of step i",
                _md(pd.DataFrame(rows)), ""))
    rv = rate[(rate.regime_name != "automated")]
    retry_any = rv.groupby("regime_name").retry_value.apply(lambda s: int((s > 1e-9).sum()))
    out.append(("Retry under review: rows where retrying saves anything",
                retry_any.to_string(), "Rows are configurations x rates on the dollar axis."))

    # --- the cap: break-evens
    rows = []
    for regime, f in mk.REGIMES:
        for k in order:
            here = b[(b.config == k) & (b.regime_name == regime)]
            fr = here[here.crossing <= 1].iloc[0]
            lad = d[(d.config == k) & (d.regime_name == regime)]
            res = lad[lad.cap_margin_low > 0]
            cost = lad[lad.cap_margin_high < 0]
            rows.append({"regime": regime, "configuration": mk.label_of(k),
                         "first crossing $/h": "" if fr.crossing == 0 else round(fr.rate, 2),
                         "x median attempt": "" if fr.crossing == 0 else round(fr.multiple, 2),
                         "crossings": int(fr.crossings),
                         "supported": int((here.supported.astype(str) == "True").sum()),
                         "saving resolved up to $/h": round(res.rate.max(), 2) if len(res) else "",
                         "saving resolved up to x": round(res.multiple.max(), 2) if len(res) else "",
                         "rows resolved as a cost": len(cost),
                         "retry beats escalating above x*": round(mk.agent_pays_above(d, k, regime), 2)})
    t = pd.DataFrame(rows)
    out.append(("The cap given retry: break-evens and resolution", _md(t),
                "* exploratory, not registered."))
    auto = t[t.regime == "automated"]
    out.append(("Automated first break-evens",
                f"$/h {_range(auto['first crossing $/h'])}; multiples {_range(auto['x median attempt'])}",
                ""))
    rows = []
    for regime in ("automated", "human 0.5"):
        for k in order:
            for r in RATES:
                x = rate[(rate.config == k) & (rate.regime_name == regime) & (rate.rate == r)].iloc[0]
                rows.append({"regime": regime, "configuration": mk.label_of(k), "$/h": int(r),
                             "multiple": round(x.multiple, 1),
                             "cap margin": round(x.cap_margin, 3),
                             "low": round(x.cap_margin_low, 3), "high": round(x.cap_margin_high, 3),
                             "iii chose": mk._choice(x.choice_iii),
                             "iii minus escalate*": round(x.value_iii - x.value_escalate, 2),
                             "escalate*": round(x.value_escalate, 2)})
    out.append(("The cap's margin at the table rates", _md(pd.DataFrame(rows)),
                "* exploratory: every task sent straight to the outside option."))
    h = rate[rate.regime_name == "human 0.5"]
    out.append(("Review at 0.5 H: best capped policy against escalating everything*",
                f"value_iii / value_escalate {_range(h.value_iii / h.value_escalate, 3)}; "
                f"value_ii / value_escalate {_range(h.value_ii / h.value_escalate, 3)}", ""))

    # --- schedules, state, transfer
    rows = []
    for regime in ("automated", "human 0.5"):
        for r in RATES:
            x = rate[(rate.regime_name == regime) & (rate.rate == r)]
            rows.append({"regime": regime, "$/h": int(r),
                         "schedule margin": _range(x.schedule_margin, 3),
                         "state margin": _range(x.state_margin, 3),
                         "transfer margin": _range(x.transfer_margin, 3),
                         "iv-t minus ii": _range(x.value_iv_transfer - x.value_ii, 3)})
    out.append(("Schedules, the state rule and the transfer", _md(pd.DataFrame(rows)), ""))
    rows = []
    for k in order:
        for r in RATES:
            x = rate[(rate.config == k) & (rate.regime_name == "automated") & (rate.rate == r)].iloc[0]
            rows.append({"configuration": mk.label_of(k), "$/h": int(r),
                         "transfer": round(x.transfer_margin, 3),
                         "low": round(x.transfer_margin_low, 3), "high": round(x.transfer_margin_high, 3),
                         "state": round(x.state_margin, 3),
                         "state low": round(x.state_margin_low, 3), "state high": round(x.state_margin_high, 3),
                         "schedule": round(x.schedule_margin, 3),
                         "sched low": round(x.schedule_margin_low, 3), "sched high": round(x.schedule_margin_high, 3)})
    out.append(("Fitted margins with intervals, automated verifier", _md(pd.DataFrame(rows)), ""))

    # --- cascade
    own = [x for x in c.columns if x.startswith("own_")]
    c = c.assign(best_own=c[own].min(axis=1),
                 best_own_name=c[own].idxmin(axis=1).str.replace("own_", "").map(mk.label_of))
    t = c[["regime_name", "rate", "tasks", "value_escalate", "value_best_single", "value_cascade",
           "switch_margin", "switch_margin_low", "switch_margin_high", "best_own", "best_own_name"]]
    t = t.assign(**{"switch %": (100 * c.switch_margin / c.value_best_single).round(1)})
    out.append(("Switching configurations", _md(t.round(3)), ""))
    o = c[c.rate.isin(RATES)][["regime_name", "rate"] + own]
    o = o.assign(spread=o[own].max(axis=1) - o[own].min(axis=1))
    o.columns = ["regime", "rate"] + [mk.label_of(x[len("own_"):]) for x in own] + ["spread"]
    out.append(("Each configuration's own schedule on the common tasks", _md(o.round(2)),
                "Cross-fitted, on the cascade's common tasks; spread is the dearest minus the "
                "cheapest."))
    ld_rate = rate[rate.rate.isin(RATES)]
    span = ld_rate.assign(span=ld_rate.value_i - ld_rate[["value_ii", "value_iii",
                                                          "value_iiib"]].min(axis=1))
    rows = [{"regime": g, "$/h": int(r), "i minus the best of ii to iii-b":
             _range(span[(span.regime_name == g) & (span.rate == r)].span)}
            for g in ("automated", "human 0.5") for r in RATES]
    out.append(("The ladder's span within a configuration, own tasks", _md(pd.DataFrame(rows)),
                ""))
    ess = [x for x in c.columns if x.startswith("essential_")]
    if ess:
        e = c[c[ess[0]].notna()][["regime_name", "rate"] + ess]
        e.columns = ["regime", "rate"] + [mk.label_of(x[len("essential_"):]) for x in ess]
        out.append(("Leave-one-out essentialness", _md(e.round(3)), ""))
    m = corr.set_index("configuration").values
    off = m[~np.eye(len(m), dtype=bool)]
    out.append(("Outcome correlation", f"off-diagonal {_range(off)}", ""))

    # --- sensitivities
    if sb is not None:
        rows = []
        both = pd.concat([b.assign(variant="primary"), sb[sb.variant != "primary"]])
        for v in dict.fromkeys(both.variant):
            for regime, _ in mk.REGIMES:
                here = both[(both.variant == v) & (both.regime_name == regime)]
                first = here[here.crossing <= 1].drop_duplicates("config")
                cr = first[first.crossing == 1]
                rows.append({"variant": v, "regime": regime, "cross": f"{len(cr)} of {len(first)}",
                             "first crossing x": _range(cr.multiple),
                             "supported": int(here[here.supported.astype(str) == "True"].config.nunique())})
        out.append(("Break-evens under each sensitivity", _md(pd.DataFrame(rows)), ""))
        allrows = pd.concat([d.assign(variant="primary"), sl])
        cost = allrows[allrows.cap_margin_high < 0]
        out.append(("Cells of any sweep where the cap is resolved as a cost", str(len(cost)), ""))
        rows = []
        for v in dict.fromkeys(allrows.variant):
            x = allrows[(allrows.variant == v) & (allrows.axis == "rate") & (allrows.rate == 100.0)]
            a, h5 = x[x.regime_name == "automated"], x[x.regime_name == "human 0.5"]
            rows.append({"variant": v, "cap, automated $100": _range(a.cap_margin, 3),
                         "cap, review 0.5 $100": _range(h5.cap_margin, 3),
                         "transfer, automated $100": _range(a.transfer_margin, 3)})
        out.append(("Margins at $100 under each sensitivity", _md(pd.DataFrame(rows)), ""))
        key = ["config", "regime_name", "axis", "rate"]
        prim = d[(d.axis == "rate") & (d.rate == 100.0) & (d.regime_name == "automated")]
        hor = sl[(sl.variant == "common horizon 100") & (sl.axis == "rate") & (sl.rate == 100.0)
                 & (sl.regime_name == "automated")]
        if len(hor):
            j = prim[key + ["value_ii"]].merge(hor[key + ["value_ii"]], on=key,
                                                suffixes=("", "_horizon"))
            j = j.assign(configuration=j.config.map(mk.label_of),
                         added=j.value_ii_horizon - j.value_ii)
            out.append(("Common 100-call horizon: what retrying costs at $100, automated",
                        _md(j[["configuration", "value_ii", "value_ii_horizon", "added"]].round(2)),
                        "added is the common horizon minus the primary, own tasks."))
    if sc_ is not None:
        both = pd.concat([c.assign(variant="primary"), sc_])
        x = both[(both.regime_name == "automated") & (both.rate == 100.0)]
        out.append(("Switching at $100, automated, under each sensitivity",
                    _md(x[["variant", "tasks", "value_best_single", "value_cascade",
                           "switch_margin"]].round(3)), ""))
    if two is not None:
        cap = two[(two.margin == "cap")]
        w1 = cap.one_stage_high - cap.one_stage_low
        w2 = cap.two_stage_high - cap.two_stage_low
        shift = (cap.two_stage_mean - cap.one_stage_mean)
        out.append(("Two-stage bootstrap",
                    f"cap cells {len(cap)}; width ratio two/one {_range(w2 / w1.replace(0, np.nan), 2)}; "
                    f"cells where two-stage excludes zero but one-stage does not: "
                    f"{int(((cap.two_stage_low > 0) | (cap.two_stage_high < 0)).sum() - ((cap.one_stage_low > 0) | (cap.one_stage_high < 0)).sum())} net; "
                    f"centre shift {_range(shift, 3)}", ""))
        tr = two[two.margin == "transfer"]
        out.append(("Two-stage transfer", _md(tr[["config", "rate", "estimate", "two_stage_low",
                                                   "two_stage_high"]].round(3)), ""))
    return out


def _resolved(lo, hi):
    lo, hi = pd.to_numeric(lo, errors="coerce"), pd.to_numeric(hi, errors="coerce")
    return int(((lo > 0) | (hi < 0)).sum())


def appendix_sections(results: str):
    """The appendix files: comparators, oracle, difficulty, distribution, spread, diagnostics."""
    out = []
    cmp_ = _read(results, "comparators")
    if cmp_ is not None:
        rows = []
        for regime in ("automated", "human 0.5"):
            for rate in RATES:
                x = cmp_[(cmp_.axis == "rate") & (cmp_.regime_name == regime) & (cmp_.rate == rate)]
                row = {"regime": regime, "$/h": int(rate),
                       "cap in calls": _range(x.value_ii - x.value_iii, 3)}
                for m in ("dollar_cap_margin", "rule_vs_threshold", "schedule_vs_universal",
                          "first_look_margin", "state_margin"):
                    row[m] = _range(x[m], 3)
                    if f"{m}_low" in x and x[f"{m}_low"].notna().any():
                        row[m] += f"; resolved {_resolved(x[m + '_low'], x[m + '_high'])} of {len(x)}"
                rows.append(row)
        out.append(("Comparators", _md(pd.DataFrame(rows)), ""))
        x = cmp_[(cmp_.axis == "rate") & (cmp_.regime_name == "human 0.5") & (cmp_.rate == 100.0)]
        n = int((x.dollar_cap_margin > x.value_ii - x.value_iii).sum())
        out.append(("Review 0.5 at $100: the dollar cap saves more than the cap in calls",
                    f"{n} of {len(x)} configurations", ""))
    orc = _read(results, "oracle")
    if orc is not None:
        t = orc[orc.rate.isin(RATES)].assign(share=lambda z: (100 * z.oracle_gap
                                                              / z.value_cascade).round(1))
        out.append(("Sample oracle", _md(t[["regime_name", "rate", "tasks", "value_oracle",
                                            "value_cascade", "value_best_single", "oracle_gap",
                                            "share"]].round(2)), "share: gap as % of the cascade."))
    dd = _read(results, "difficulty")
    if dd is not None:
        rows = []
        for regime in ("automated", "human 0.5"):
            for bucket in dict.fromkeys(dd.bucket):
                x = dd[(dd.regime_name == regime) & (dd.rate == 100.0) & (dd.bucket == bucket)]
                rows.append({"regime": regime, "bucket": bucket,
                             "tasks": _range(x.tasks, 0),
                             "cap margin": _range(x.cap_margin, 3),
                             "resolved": (f"{_resolved(x.cap_margin_low, x.cap_margin_high)} of "
                                          f"{int(x.cap_margin_low.notna().sum())}"),
                             "value ii": _range(x.value_ii, 2), "value iii": _range(x.value_iii, 2)})
        out.append(("Difficulty at $100", _md(pd.DataFrame(rows)), ""))
        rows = []
        for regime in ("automated", "human 0.5"):
            for config in mk.order_of(dd.config):
                x = dd[(dd.regime_name == regime) & (dd.rate == 100.0) & (dd.config == config)]
                w = x[x.bucket == "all, chosen within bucket"]
                b = x[x.bucket == "all, chosen blind"]
                if len(w) and len(b):
                    rows.append({"regime": regime, "configuration": mk.label_of(config),
                                 "best of ii, iii within": round(float(w[["value_ii", "value_iii"]].min(axis=1).iloc[0]), 3),
                                 "best of ii, iii blind": round(float(b[["value_ii", "value_iii"]].min(axis=1).iloc[0]), 3),
                                 "cap within": round(float(w.cap_margin.iloc[0]), 3),
                                 "cap blind": round(float(b.cap_margin.iloc[0]), 3)})
        out.append(("Admitting the annotation, $100", _md(pd.DataFrame(rows)), ""))
    ds = _read(results, "distribution")
    if ds is not None:
        rows = []
        for regime in dict.fromkeys(ds.regime_name):
            x = ds[(ds.regime_name == regime) & (ds.rate == 100.0)]
            rows.append({"regime": regime, "p95 ii": _range(x.p95_ii), "p95 iii": _range(x.p95_iii),
                         "cap at p95": _range(x.cap_margin_p95),
                         "median ii": _range(x.median_ii), "median iii": _range(x.median_iii),
                         "median version": _range(x.cap_margin_median, 3)})
        out.append(("Distribution of cost at $100", _md(pd.DataFrame(rows)), ""))
    sp = _read(results, "spread")
    if sp is not None:
        out.append(("Spread", _md(sp[["regime_name", "rate", "tasks", "across_best", "across_one",
                                      "within_median", "within_max", "cheapest",
                                      "dearest"]].round(2)), ""))
    dg_ = _read(results, "diagnostics")
    if dg_ is not None:
        rows = [{"quantity": c, "range": _range(dg_[c], 3)}
                for c in ("within_task_share", "mixed_share", "all_fail_share",
                          "all_resolve_share", "resolve_rate", "over_outside_25",
                          "over_outside_100") if c in dg_]
        out.append(("Diagnostics", _md(pd.DataFrame(rows)), ""))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", default=os.path.join(HERE, os.pardir, "results"))
    ap.add_argument("--out", default=os.path.join(HERE, "facts.md"))
    a = ap.parse_args(argv)
    lines = ["# Facts the manuscript quotes", "",
             "Written by `paper/facts.py` from `results/`. Do not edit by hand.", ""]
    for title, body, note in sections(a.results) + appendix_sections(a.results):
        lines += [f"## {title}", "", body, ""]
        if note:
            lines += [note, ""]
    with open(a.out, "w") as fh:
        fh.write("\n".join(lines))
    print(a.out)


if __name__ == "__main__":
    main()
