"""Every figure and table in the paper, from the files in results/.

    python exhibits/make.py                 # writes exhibits/out/

Nothing here computes a policy value. The script reads what the evaluator wrote, reshapes it, and
draws it, so every number in a figure or table can be found in a results file and traced to the
command that wrote it (results/README.md). Figures are written as PDF for the manuscript and PNG
for reading; tables as Markdown, LaTeX and CSV.

The main-text exhibits are the ones PLAN.md Section 7 names: the cap's marginal value across the
sweep (the primary result), the state rule's margin over the best schedule within and across
configurations (the primary transfer), the table of policy values with break-evens, and the best
cross-configuration schedule against each configuration's own. Anything not in the registration
says so in its title and its caption.
"""
from __future__ import annotations

import argparse
import os
from typing import Dict, List

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                              # noqa: E402
from matplotlib.ticker import FuncFormatter, LogLocator      # noqa: E402

# ----------------------------------------------------------------------------- names and order

ORDER = ("gpt-5_4runs", "gpt_5.2_4runs", "claude-sonnet-4_4runs", "claude-sonnet-4.5_4runs",
         "gemini-3-pro-preview_4runs", "kimi-k2_4runs", "qwen3-coder-480b-a35b-instruct-4runs")
NAME = {"gpt-5_4runs": "GPT-5", "gpt_5.2_4runs": "GPT-5.2",
        "claude-sonnet-4_4runs": "Sonnet 4", "claude-sonnet-4.5_4runs": "Sonnet 4.5",
        "gemini-3-pro-preview_4runs": "Gemini 3 Pro", "kimi-k2_4runs": "Kimi K2",
        # Qwen's dollar figures rest on an imputed price and are marked so wherever they appear
        "qwen3-coder-480b-a35b-instruct-4runs": "Qwen3 Coder\u2020"}
IMPUTED = "\u2020 Qwen3 Coder's dollar figures rest on an imputed price (PLAN.md Section 10)."
REGIMES = (("automated", 0.0), ("human 0.1", 0.1), ("human 0.3", 0.3), ("human 0.5", 0.5))
REGIME_LABEL = {"automated": "automated verifier", "human 0.1": "review at 0.1 H",
                "human 0.3": "review at 0.3 H", "human 0.5": "review at 0.5 H"}
TABLE_RATES = (25.0, 100.0, 300.0)

# ----------------------------------------------------------------------------- style

INK, INK_2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS, SURFACE = "#e1e0d9", "#c3c2b7", "#ffffff"
# review price is an ordered magnitude, so it takes one hue stepped light to dark (blue 300, 450,
# 550, 700), validated as an ordinal ramp; darker is dearer review
REGIME_COLOR = {"automated": "#6da7ec", "human 0.1": "#2a78d6", "human 0.3": "#1c5cab",
                "human 0.5": "#0d366b"}
SERIES_1, SERIES_2 = "#2a78d6", "#eb6834"      # categorical slots 1 and 2, validated all-pairs


def _style():
    plt.rcParams.update({
        "font.family": "sans-serif", "font.size": 8.5, "axes.titlesize": 9,
        "axes.labelsize": 8.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5, "axes.edgecolor": AXIS, "axes.linewidth": 0.6,
        "axes.labelcolor": INK_2, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6, "text.color": INK,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "lines.linewidth": 1.5, "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
        "legend.frameon": False, "pdf.fonttype": 42,
    })


BARE = False     # --bare: the manuscript's figures, whose titles and notes are in its captions


def _save(fig, out: str, name: str) -> List[str]:
    if BARE:
        if fig._suptitle is not None:
            fig._suptitle.set_visible(False)
        for t in fig.texts:
            t.set_visible(False)
    paths = []
    for ext in ("pdf", "png"):
        p = os.path.join(out, f"{name}.{ext}")
        # no creation date in the PDF, so that an unchanged figure is an unchanged file
        fig.savefig(p, dpi=200, bbox_inches="tight",
                    metadata={"CreationDate": None} if ext == "pdf" else None)
        paths.append(p)
    plt.close(fig)
    return paths


MULTIPLE_TICKS = (1, 3, 10, 30, 100, 300)
RATE_TICKS = (5, 10, 25, 50, 100, 300)


def _log_x(ax, label: str = "", ticks=MULTIPLE_TICKS):
    ax.set_xscale("log")
    ax.set_xticks(list(ticks))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}"))
    ax.xaxis.set_minor_locator(LogLocator(base=10, subs="auto", numticks=40))
    ax.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: ""))
    if label:
        ax.set_xlabel(label)


def _pct(ax):
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}%" if v else "0"))


def _zero(ax):
    ax.axhline(0.0, color=AXIS, linewidth=0.9, zorder=1)


# ----------------------------------------------------------------------------- loading

def load(results: str) -> Dict[str, pd.DataFrame]:
    got = {}
    for name in ("ladder", "breakeven", "cascade", "outcome_correlation", "sensitivity_ladder",
                 "sensitivity_breakeven", "sensitivity_cascade", "sensitivity_two_stage",
                 "comparators", "oracle", "difficulty", "distribution", "spread", "diagnostics",
                 "tail_composition"):
        p = os.path.join(results, f"{name}.csv")
        if os.path.exists(p):
            got[name] = pd.read_csv(p)
    if "ladder" not in got:
        raise FileNotFoundError(f"{results}/ladder.csv: run python -m restart.ladder first")
    return got


def order_of(configs) -> List[str]:
    """The paper's order for the configurations it knows, then any others, by name."""
    present = list(dict.fromkeys(configs))
    return [c for c in ORDER if c in present] + sorted(c for c in present if c not in ORDER)


def label_of(config: str) -> str:
    return NAME.get(config, config)


def _sweep(d: pd.DataFrame, config: str, regime: str) -> pd.DataFrame:
    """Both axes of the sweep for one configuration and regime, in order of the outside option."""
    here = d[(d.config == config) & (d.regime_name == regime)]
    return here.sort_values("multiple").drop_duplicates("multiple")


def agent_pays_above(d: pd.DataFrame, config: str, regime: str) -> float:
    """Exploratory, not registered: the outside option, in multiples of the median attempt cost,
    above which retrying without a cap (step ii) first costs less than sending every task straight
    to the outside option. Log-interpolated between points of the sweep; NaN if it never does."""
    s = _sweep(d, config, regime)
    x, y = s.multiple.values, (s.value_ii - s.value_escalate).values
    for i in range(len(x) - 1):
        if y[i] > 0 >= y[i + 1]:
            t = y[i] / (y[i] - y[i + 1])
            return float(np.exp(np.log(x[i]) + t * (np.log(x[i + 1]) - np.log(x[i]))))
    return float("nan") if y[0] > 0 else float(x[0])


def _share(x, base):
    return 100.0 * np.asarray(x, float) / np.asarray(base, float)


# ----------------------------------------------------------------------------- figure 1

def fig_cap_margin(d: pd.DataFrame, out: str):
    """The primary result: the cap's marginal value given retry across the sweep, per configuration
    and as the median across them, in every regime. The saving is shown as a share of what retrying
    without a cap costs, so that configurations whose attempts differ manyfold in cost sit on one
    scale; the dollar values and their intervals are in Table 1 and results/ladder.csv."""
    order = order_of(d.config)
    fig, axes = plt.subplots(2, 4, figsize=(9.6, 4.9), sharex=True, sharey=True)
    panels = (order + ["median"])[:8]
    grid = np.geomspace(0.5, 500, 40)
    for ax, config in zip(axes.flat, panels):
        for regime, _ in REGIMES:
            color = REGIME_COLOR[regime]
            if config == "median":
                ys = []
                for c in order:
                    s = _sweep(d, c, regime)
                    ys.append(np.interp(np.log(grid), np.log(s.multiple),
                                        _share(s.cap_margin, s.value_ii)))
                ax.plot(grid, np.median(ys, axis=0), color=color, label=REGIME_LABEL[regime])
                continue
            s = _sweep(d, config, regime)
            if regime in ("automated", "human 0.5"):
                ax.fill_between(s.multiple, _share(s.cap_margin_low, s.value_ii),
                                _share(s.cap_margin_high, s.value_ii), color=color, alpha=0.12,
                                linewidth=0, zorder=2)
            ax.plot(s.multiple, _share(s.cap_margin, s.value_ii), color=color, zorder=3,
                    label=REGIME_LABEL[regime])
        if config != "median":
            above = agent_pays_above(d, config, "automated")
            if np.isfinite(above):
                ax.axvline(above, color=MUTED, linestyle=":", linewidth=1.1, zorder=1,
                           label="retrying without a cap first beats escalating (automated)*")
        _zero(ax)
        ax.set_title("median of the configurations" if config == "median" else label_of(config),
                     loc="left", color=INK)
        _pct(ax)
    for ax in axes.flat:
        _log_x(ax)
    fig.supxlabel("outside option, multiples of median attempt cost", fontsize=8.5, color=INK_2,
                  y=0.07)
    fig.supylabel("cap's saving, % of retry's cost", fontsize=8.5, color=INK_2, x=0.005)
    axes[0, 0].set_ylim(-20, 75)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=5, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("The cap's marginal value given retry (step ii minus step iii)", x=0.01,
                 ha="left", fontsize=10, color=INK)
    fig.text(0.01, -0.09, "Positive: the cap saves. Bands: 95% intervals from the full-pipeline "
             "bootstrap (1,000 replicates) for the automated verifier and review at 0.5 H, scaled by "
             "the point value of step ii. * Exploratory, not registered: to the left of the dotted "
             "line, escalating every task without running the agent is cheaper than retrying "
             "without a cap. " + IMPUTED, fontsize=7, color=INK_2, ha="left", wrap=True)
    fig.tight_layout(rect=(0.01, 0.08, 1, 0.97))
    return _save(fig, out, "fig1_cap_margin")


# ----------------------------------------------------------------------------- figure 2

def fig_transfer(d: pd.DataFrame, out: str, regime: str = "automated", name: str = "fig2_transfer"):
    """The primary transfer: the state rule's margin over the best schedule, its models fitted on
    the other six configurations, beside the same rule fitted on the configuration itself and
    beside the margin of not capping at all. Where the three lines coincide, the rule is not
    stopping attempts: its margin over the schedule is the schedule's own cost of selection."""
    order = order_of(d.config)
    fig, axes = plt.subplots(2, 4, figsize=(9.6, 4.9), sharex=True, sharey=True)
    panels = (order + ["median"])[:8]
    grid = np.geomspace(0.5, 500, 40)
    for ax, config in zip(axes.flat, panels):
        if config == "median":
            for col, color, style, lab in (("transfer_margin", SERIES_1, "-", "rule fitted elsewhere"),
                                           ("state_margin", SERIES_2, "--", "rule fitted here")):
                ys = []
                for c in order:
                    s = _sweep(d, c, regime)
                    ys.append(np.interp(np.log(grid), np.log(s.multiple),
                                        _share(s[col], s.value_ii)))
                ax.plot(grid, np.median(ys, axis=0), color=color, linestyle=style, label=lab)
        else:
            s = _sweep(d, config, regime)
            nocap = _share(s.value_iiib - s.value_ii, s.value_ii)
            ax.plot(s.multiple, nocap, color=MUTED, linestyle=":", linewidth=1.3, zorder=2,
                    label="no cap at all (step ii)")
            ax.plot(s.multiple, _share(s.state_margin, s.value_ii), color=SERIES_2,
                    linestyle="--", zorder=3, label="rule fitted here")
            ax.plot(s.multiple, _share(s.transfer_margin, s.value_ii), color=SERIES_1, zorder=4,
                    label="rule fitted elsewhere")
            ci = s[s.transfer_margin_low.notna()]
            if len(ci):
                lo = _share(ci.transfer_margin - ci.transfer_margin_low, ci.value_ii)
                hi = _share(ci.transfer_margin_high - ci.transfer_margin, ci.value_ii)
                ax.errorbar(ci.multiple, _share(ci.transfer_margin, ci.value_ii), yerr=[lo, hi],
                            fmt="o", color=SERIES_1, markersize=4, elinewidth=1.0, capsize=0,
                            zorder=5)
        _zero(ax)
        ax.set_title("median of the configurations" if config == "median" else label_of(config),
                     loc="left", color=INK)
        _pct(ax)
    for ax in axes.flat:
        _log_x(ax)
    fig.supxlabel("outside option, multiples of median attempt cost", fontsize=8.5, color=INK_2,
                  y=0.07)
    fig.supylabel("saving over the best schedule, % of retry's cost", fontsize=8.5,
                  color=INK_2, x=0.005)
    axes[0, 0].set_ylim(-10, 10)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.03))
    what = "primary transfer" if regime == "automated" else "not the registered regime"
    fig.suptitle(f"The state rule against the best schedule, {REGIME_LABEL[regime]} ({what})",
                 x=0.01, ha="left", fontsize=10, color=INK)
    if regime == "automated":
        note = ("Points: 95% intervals for the transferred rule at $25, $100 and $300 an hour "
                "(100 replicates, refitting inside each), scaled by the point value of step ii. "
                "Below about two attempts the dotted line leaves the frame: there, not capping at "
                "all costs far more than the schedule. ")
    else:
        note = ("No intervals are computed in this regime. Where the dotted line leaves the "
                "frame, not capping at all costs far more than the schedule. ")
    fig.text(0.01, -0.09, "Positive: the rule is cheaper than step iii-b. " + note + IMPUTED,
             fontsize=7, color=INK_2, ha="left", wrap=True)
    fig.tight_layout(rect=(0.01, 0.08, 1, 0.97))
    return _save(fig, out, name)


# ----------------------------------------------------------------------------- the ladder

LADDER_STEPS = (("value_i", "i"), ("value_ii", "ii"), ("value_iii", "iii"), ("value_iiib", "iii-b"),
                ("value_iv", "iv"), ("value_iv_transfer", "iv-t"))


def fig_ladder(d: pd.DataFrame, out: str, regimes=("automated", "human 0.5")):
    """The ladder drawn: each step's policy value as a share of one attempt's (step i), for every
    configuration and their median, at the three table rates, in the two headline regimes. Step
    iv is the state rule fitted on the configuration itself and iv-t the rule fitted on the other
    six. Each step is chosen on training folds and scored on held-out ones, so a line can rise."""
    rate = d[(d.axis == "rate") & (d.rate.isin(TABLE_RATES))]
    order = order_of(rate.config)
    cols = [c for c, _ in LADDER_STEPS if c in rate]
    x = np.arange(len(cols))
    fig, axes = plt.subplots(len(regimes), len(TABLE_RATES), figsize=(7.6, 2.3 * len(regimes)),
                             sharex=True, sharey="row", squeeze=False)
    for i, regime in enumerate(regimes):
        for j, r in enumerate(TABLE_RATES):
            ax = axes[i, j]
            here = rate[(rate.regime_name == regime) & (rate.rate == r)].set_index("config")
            shares = np.array([_share(here.loc[c, cols].values.astype(float), here.loc[c, "value_i"])
                               for c in order if c in here.index])
            ax.axhline(100.0, color=AXIS, linewidth=0.9, zorder=1)
            for k, row in enumerate(shares):
                ax.plot(x, row, color=MUTED, linewidth=0.8, alpha=0.55, marker="o",
                        markersize=2.5, zorder=2, label="each configuration" if k == 0 else None)
            med = np.median(shares, axis=0)
            ax.plot(x, med, color=SERIES_1, linewidth=2.0, marker="o", markersize=5,
                    markeredgecolor=SURFACE, markeredgewidth=1.0, zorder=3,
                    label="median of the configurations")
            ax.annotate(f"{med[-1]:.0f}%", (x[-1], med[-1]), xytext=(5, 0),
                        textcoords="offset points", va="center", fontsize=7, color=INK_2)
            if i == 0:
                ax.set_title(f"${r:.0f} an hour", loc="left", color=INK)
            ax.set_xticks(x)
            ax.set_xticklabels([lab for c, lab in LADDER_STEPS if c in cols])
            ax.set_xlim(-0.3, len(cols) - 0.5)
            ax.grid(axis="x", visible=False)
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
        axes[i, 0].set_ylabel(f"{REGIME_LABEL[regime]}\ncost, % of one attempt", fontsize=8)
    fig.supxlabel("step of the ladder", fontsize=8.5, color=INK_2, y=0.07)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("The policy ladder: expected cost at each step as a share of one attempt",
                 x=0.01, ha="left", fontsize=10, color=INK)
    fig.text(0.01, -0.05, "Below 100%: cheaper than a single attempt followed by the outside "
             "option. iv: the state rule fitted on the configuration itself; iv-t: fitted on the "
             "other six. Every step is chosen on training folds and scored on held-out folds. "
             + IMPUTED, fontsize=7, color=INK_2, ha="left", wrap=True)
    fig.tight_layout(rect=(0.0, 0.07, 1, 0.97))
    return _save(fig, out, "fig_ladder")


# ----------------------------------------------------------------------------- figure 3

def fig_cascade(c: pd.DataFrame, out: str):
    """The best cross-configuration schedule against each configuration's own optimum, in every
    regime, as a share of what escalating every task would cost. The best single configuration
    chosen from the same training folds is the comparison switching has to beat."""
    fig, axes = plt.subplots(1, 4, figsize=(9.6, 2.9), sharey=True)
    order = order_of(k[len("own_"):] for k in c.columns if k.startswith("own_"))
    for ax, (regime, _) in zip(axes, REGIMES):
        s = c[c.regime_name == regime].sort_values("rate")
        esc = s.value_escalate.values
        for i, config in enumerate(order):
            ax.plot(s.rate, s[f"own_{config}"] / esc, color=MUTED, linewidth=0.9, zorder=2,
                    label="each configuration's own schedule" if i == 0 else None)
        ax.plot(s.rate, s.value_best_single / esc, color=SERIES_2, zorder=3,
                label="best single configuration, chosen from data")
        ax.plot(s.rate, s.value_cascade / esc, color=SERIES_1, zorder=4, label="cascade")
        ax.axhline(1.0, color=AXIS, linewidth=0.9, zorder=1)
        ax.set_title(REGIME_LABEL[regime], loc="left", color=INK)
        _log_x(ax, "outside option, $ an hour", RATE_TICKS)
        ax.set_xlim(4, 350)
    axes[0].set_ylabel("cost, share of escalating every task")
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.09))
    n = int(c.tasks.iloc[0])
    fig.suptitle("Switching configurations: the cascade against each configuration's own schedule",
                 x=0.01, ha="left", fontsize=10, color=INK)
    fig.text(0.01, -0.2, f"On the {n} tasks with four usable draws in all seven configurations. "
             "Below 100%: cheaper than sending every task straight to the outside option (a "
             "reference line that is not in the registration). " + IMPUTED,
             fontsize=7, color=INK_2, ha="left", wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    return _save(fig, out, "fig3_cascade")


# ----------------------------------------------------------------------------- figure 4 (exploratory)

def attempt_units(b: pd.DataFrame) -> pd.DataFrame:
    """The first break-even re-expressed in full attempts, tokens plus review: the mean outside
    option H over the median token cost m plus the review f H. With H = M m this is M / (1 + f M),
    which under review can never exceed 1 / f. Not registered; computed after the results."""
    first = b[b.crossing == 1].copy()
    first["full_attempts"] = first.multiple / (1.0 + first.regime * first.multiple)
    return first


def fig_attempt_units(b: pd.DataFrame, out: str):
    first = attempt_units(b)
    order = order_of(b.config)
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    ys = {c: i for i, c in enumerate(reversed(order))}
    for regime, f in REGIMES[:3]:
        here = first[first.regime_name == regime]
        ax.scatter(here.full_attempts, [ys[c] for c in here.config], s=30,
                   color=REGIME_COLOR[regime], edgecolor=SURFACE, linewidth=1.2, zorder=3,
                   label=REGIME_LABEL[regime])
    for f in (0.5, 0.3):
        ax.axvline(1 / f, color=REGIME_COLOR[f"human {f}"], linewidth=0.9, linestyle="--",
                   zorder=2)
        ax.text(1 / f, len(order) - 0.35, f" ceiling at {f} H " if f == 0.5 else
                f" ceiling at {f} H ", color=INK_2, fontsize=7, va="bottom",
                ha="left" if f == 0.5 else "right")
    ax.set_yticks(list(ys.values()))
    ax.set_yticklabels([label_of(c) for c in ys])
    ax.set_xlim(1.6, 4.2)
    ax.set_ylim(-0.6, len(order) + 0.2)
    ax.set_xlabel("first break-even: outside option in full attempts (tokens + review)")
    ax.grid(axis="y", visible=False)
    ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5))
    ax.set_title("Exploratory, not registered: the break-even in units of a full attempt",
                 loc="left", color=INK, fontsize=9)
    fig.text(0.01, -0.07, "Under review at 0.5 H no configuration crosses: an attempt then costs at "
             "least half the outside option, so the outside option is at most two attempts, below "
             "every configuration's threshold. GPT-5.2 at 0.3 H crosses nowhere for the same reason.",
             fontsize=7, color=INK_2, ha="left", wrap=True)
    fig.tight_layout()
    return _save(fig, out, "fig4_break_even_in_attempts")


# ----------------------------------------------------------------------------- appendix figure

def fig_correlation(r: pd.DataFrame, out: str, n_tasks: int):
    order = order_of(r.configuration)
    r = r.set_index("configuration").loc[order, order]
    fig, ax = plt.subplots(figsize=(4.6, 3.9))
    im = ax.imshow(r.values, cmap=matplotlib.colors.LinearSegmentedColormap.from_list(
        "blue", ["#cde2fb", "#6da7ec", "#2a78d6", "#184f95", "#0d366b"]), vmin=0.5, vmax=1.0)
    for i in range(len(order)):
        for j in range(len(order)):
            v = r.values[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7,
                    color=SURFACE if v > 0.78 else INK)
    names = [label_of(c) for c in order]
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(names, rotation=40, ha="right")
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels(names)
    ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.03)
    cb.outline.set_visible(False)
    cb.ax.tick_params(labelsize=7, color=MUTED)
    ax.set_title(f"Outcome correlation across {n_tasks} tasks", loc="left", color=INK)
    fig.tight_layout()
    return _save(fig, out, "figA2_outcome_correlation")


# ----------------------------------------------------------------------------- tables

def _fmt(x, places=2):
    return "" if pd.isna(x) else f"{x:,.{places}f}"


def _interval(v, lo, hi):
    if pd.isna(lo):
        return _fmt(v)
    return f"{v:,.2f} [{lo:,.2f}, {hi:,.2f}]"


def _band(lo, hi) -> str:
    lo, hi = pd.to_numeric(lo, errors="coerce"), pd.to_numeric(hi, errors="coerce")
    return "" if pd.isna(lo) or pd.isna(hi) else f"[{lo:,.2f}, {hi:,.2f}]"


def _choice(s: str) -> str:
    """What the folds chose for step iii, written short: 4x@175 is four attempts at 175 calls."""
    if pd.isna(s):
        return ""
    out = []
    for c in str(s).split("|"):
        c = c.split(": ", 1)[-1]
        out.append(c.replace(" attempts at ", "x@").replace(" cutoff", "").replace("no", "none"))
    return ", ".join(sorted(set(out)))


def table_ladder(d: pd.DataFrame, b: pd.DataFrame, out: str) -> List[str]:
    """Table 1: policy value by configuration for steps i to iii-b, in the automated regime and
    under review at 0.5 H, at three rates, with the cap's margin and its interval, what the folds
    chose, and the first break-even. The full sweep is results/ladder.csv."""
    rows = []
    for regime in ("automated", "human 0.5"):
        for config in order_of(d.config):
            be = b[(b.config == config) & (b.regime_name == regime) & (b.crossing <= 1)].iloc[0]
            first = ("none in sweep" if be.crossing == 0 else
                     f"${be.rate:,.2f}/h = {be.multiple:.2f}x")
            for rate in TABLE_RATES:
                r = d[(d.config == config) & (d.regime_name == regime) & (d.axis == "rate")
                      & (d.rate == rate)].iloc[0]
                rows.append({
                    "regime": REGIME_LABEL[regime], "configuration": label_of(config),
                    "$/h": f"{rate:.0f}", "x attempt": f"{r.multiple:.0f}",
                    "i": _fmt(r.value_i), "ii": _fmt(r.value_ii), "iii": _fmt(r.value_iii),
                    "iii-b": _fmt(r.value_iiib),
                    "cap's saving [95%]": _interval(r.cap_margin, r.cap_margin_low,
                                                    r.cap_margin_high),
                    "iii chose": _choice(r.choice_iii),
                    "escalate all*": _fmt(r.value_escalate),
                    "first break-even": first if rate == TABLE_RATES[0] else "",
                })
    t = pd.DataFrame(rows)
    return _write_table(t, out, "table1_ladder",
                        caption="Policy value, expected cost per incoming task in dollars, "
                        "chosen on training folds and scored on held-out folds. Cap's saving is "
                        "step ii minus step iii. * Not registered: every task sent straight to the "
                        "outside option. " + IMPUTED)


def table_breakeven(d: pd.DataFrame, b: pd.DataFrame, out: str) -> List[str]:
    """Table 2: the summary statistic of the primary result, per configuration and regime: the
    first break-even in both units, how many crossings the scan found and how many the bootstrap
    supports, and the highest rate at which the cap's saving is resolved."""
    rows = []
    for regime, f in REGIMES:
        for config in order_of(d.config):
            here = b[(b.config == config) & (b.regime_name == regime)]
            first = here[here.crossing <= 1].iloc[0]
            lad = d[(d.config == config) & (d.regime_name == regime)]
            resolved = lad[lad.cap_margin_low > 0]
            supported = int((here.supported.astype(str) == "True").sum())
            units = (first.multiple / (1 + f * first.multiple)) if first.crossing else np.nan
            rows.append({
                "regime": REGIME_LABEL[regime], "configuration": label_of(config),
                "first break-even, $/h": _fmt(first.rate) if first.crossing else "none",
                "x median attempt": _fmt(first.multiple) if first.crossing else "",
                "crossings (supported)": f"{int(first.crossings)} ({supported})",
                "saving resolved up to, $/h": _fmt(resolved.rate.max()) if len(resolved) else "",
                "in full attempts*": _fmt(units),
                "retry beats escalating above*": (lambda v: "never in sweep" if np.isnan(v)
                                                  else _fmt(v))(agent_pays_above(d, config, regime)),
            })
    t = pd.DataFrame(rows)
    return _write_table(t, out, "table2_breakeven",
                        caption="The rate at which the cap's marginal value changes sign. Every "
                        "crossing is reported in results/breakeven.csv; one is supported when the "
                        "bootstrap resolves the sign on both sides of it. * Exploratory, not "
                        "registered: the break-even over the full cost of an attempt, tokens plus "
                        "review, M / (1 + f M); and the multiple of the median attempt cost above which retrying without "
                        "a cap first costs less than escalating every task. " + IMPUTED)


def table_transfer(d: pd.DataFrame, out: str) -> List[str]:
    """Table 3: the primary transfer at the three rates with intervals, and how far the transferred
    rule sits from not capping at all."""
    rows = []
    for config in order_of(d.config):
        for rate in TABLE_RATES:
            r = d[(d.config == config) & (d.regime_name == "automated") & (d.axis == "rate")
                  & (d.rate == rate)].iloc[0]
            rows.append({
                "configuration": label_of(config), "$/h": f"{rate:.0f}",
                "iii-b": _fmt(r.value_iiib), "iv, fitted here": _fmt(r.value_iv),
                "iv, fitted elsewhere": _fmt(r.value_iv_transfer), "ii": _fmt(r.value_ii),
                "transfer margin [95%]": _interval(r.transfer_margin, r.transfer_margin_low,
                                                   r.transfer_margin_high),
                "elsewhere minus ii": _fmt(r.value_iv_transfer - r.value_ii),
            })
    for rate in TABLE_RATES:
        here = d[(d.regime_name == "automated") & (d.axis == "rate") & (d.rate == rate)]
        rows.append({"configuration": "median", "$/h": f"{rate:.0f}",
                     "transfer margin [95%]": _fmt(here.transfer_margin.median()),
                     "elsewhere minus ii": _fmt((here.value_iv_transfer - here.value_ii).median())})
    t = pd.DataFrame(rows).fillna("")
    return _write_table(t, out, "table3_transfer",
                        caption="The primary transfer, automated verifier: step iii-b minus the "
                        "state rule with its models fitted on the other six configurations. The "
                        "last column is how far that rule sits from retrying without any cap. "
                        + IMPUTED)


# ----------------------------------------------------------------------------- appendix: sensitivities

PRIMARY = "primary"


def _with_primary(primary: pd.DataFrame, variants: pd.DataFrame) -> pd.DataFrame:
    """The primary rows labelled as a variant, then every sensitivity's, in the order run."""
    variants = variants[variants.variant != PRIMARY]        # the runner's check of itself
    return pd.concat([primary.assign(variant=PRIMARY), variants], ignore_index=True, sort=False)


def _median_range(x: pd.Series, places: int = 2) -> str:
    x = pd.to_numeric(x, errors="coerce").dropna()
    if x.empty:
        return ""
    if len(x) == 1:
        return _fmt(x.iloc[0], places)
    return f"{x.median():,.{places}f} [{x.min():,.{places}f}, {x.max():,.{places}f}]"


def table_sensitivity_breakeven(b: pd.DataFrame, sb: pd.DataFrame, out: str) -> List[str]:
    """Appendix: the summary statistic of the primary result under each registered sensitivity.
    Per regime, how many configurations' margins change sign in the sweep, and the first
    break-even's median and range across them, in dollars an hour and in multiples of the median
    attempt cost."""
    both = _with_primary(b, sb)
    rows = []
    for variant in dict.fromkeys(both.variant):
        for regime, _ in REGIMES:
            here = both[(both.variant == variant) & (both.regime_name == regime)]
            first = here[here.crossing <= 1].drop_duplicates("config")
            crossed = first[first.crossing == 1]
            supported = here[here.supported.astype(str) == "True"].config.nunique()
            rows.append({
                "sensitivity": variant, "regime": REGIME_LABEL[regime],
                "cross in sweep": f"{len(crossed)} of {len(first)}",
                "with a supported crossing": str(supported),
                "first break-even, $/h": _median_range(crossed.rate),
                "x median attempt": _median_range(crossed.multiple),
            })
    t = pd.DataFrame(rows)
    return _write_table(t, out, "tableA1_sensitivity_breakeven",
                        caption="The break-even of the cap's marginal value under each registered "
                        "sensitivity: median [range] of the first crossing across the "
                        "configurations whose margin changes sign in the sweep. Every crossing is "
                        "in results/breakeven.csv and results/sensitivity_breakeven.csv. " + IMPUTED)


def table_sensitivity_margins(d: pd.DataFrame, sd: pd.DataFrame, c: pd.DataFrame,
                              sc_: pd.DataFrame, out: str) -> List[str]:
    """Appendix: the primary margins under each registered sensitivity, as medians across the
    configurations: the cap's saving in both headline regimes, the primary transfer, and the value
    of switching configurations."""
    both = _with_primary(d[d.axis == "rate"], sd[sd.axis == "rate"])
    casc = _with_primary(c, sc_) if c is not None and sc_ is not None else None
    rows = []
    for variant in dict.fromkeys(both.variant):
        here = both[both.variant == variant]
        row = {"sensitivity": variant}
        for regime, short in (("automated", "A"), ("human 0.5", "R")):
            for rate in TABLE_RATES:
                x = here[(here.regime_name == regime) & (here.rate == rate)].cap_margin
                row[f"cap {short} ${rate:.0f}"] = _fmt(x.median())
        for rate in TABLE_RATES:
            x = here[(here.regime_name == "automated") & (here.rate == rate)].transfer_margin
            row[f"transfer ${rate:.0f}"] = _fmt(pd.to_numeric(x, errors="coerce").median())
        if casc is not None:
            k = casc[(casc.variant == variant) & (casc.regime_name == "automated")
                     & (casc.rate == 100.0)]
            row["switching $100"] = _fmt(k.switch_margin.iloc[0]) if len(k) else ""
        rows.append(row)
    t = pd.DataFrame(rows)
    return _write_table(t, out, "tableA2_sensitivity_margins",
                        caption="The primary margins under each registered sensitivity, medians "
                        "across configurations, in dollars per task; positive is what the richer "
                        "policy saves. Cap: step ii minus step iii, with an automated verifier (A) "
                        "and under review at 0.5 H (R). Transfer: step iii-b minus the "
                        "state rule fitted on the other configurations, automated verifier. "
                        "Switching: the best single configuration minus the cascade, automated "
                        "verifier. " + IMPUTED)


def table_two_stage(two: pd.DataFrame, d: pd.DataFrame, out: str) -> List[str]:
    """Appendix: the one-stage and two-stage intervals side by side, for the cap's margin in the
    two headline regimes and for the primary transfer, at the three table rates."""
    rows = []
    cap = two[(two.margin == "cap") & (two.axis == "rate")]
    for regime in ("automated", "human 0.5"):
        for config in order_of(cap.config):
            for rate in TABLE_RATES:
                r = cap[(cap.config == config) & (cap.regime_name == regime) & (cap.rate == rate)]
                if not len(r):
                    continue
                r = r.iloc[0]
                rows.append({"margin": f"cap, {REGIME_LABEL[regime]}",
                             "configuration": label_of(config), "$/h": f"{rate:.0f}",
                             "estimate": _fmt(r.estimate),
                             "one-stage [95%]": _band(r.one_stage_low, r.one_stage_high),
                             "one-stage mean": _fmt(r.one_stage_mean),
                             "two-stage [95%]": _band(r.two_stage_low, r.two_stage_high),
                             "two-stage mean": _fmt(r.two_stage_mean)})
    moved = two[two.margin == "transfer"]
    for config in order_of(moved.config):
        for rate in TABLE_RATES:
            r = moved[(moved.config == config) & (moved.rate == rate)]
            if not len(r):
                continue
            r = r.iloc[0]
            lad = d[(d.config == config) & (d.regime_name == "automated") & (d.axis == "rate")
                    & (d.rate == rate)]
            lo, hi = ((lad.transfer_margin_low.iloc[0], lad.transfer_margin_high.iloc[0])
                      if len(lad) else (np.nan, np.nan))
            rows.append({"margin": "transfer, automated verifier",
                         "configuration": label_of(config), "$/h": f"{rate:.0f}",
                         "estimate": _fmt(r.estimate),
                         "one-stage [95%]": _band(lo, hi), "one-stage mean": "",
                         "two-stage [95%]": _band(r.two_stage_low, r.two_stage_high),
                         "two-stage mean": _fmt(r.two_stage_mean)})
    t = pd.DataFrame(rows)
    return _write_table(t, out, "tableA3_two_stage",
                        caption="The two-stage bootstrap, which resamples each task's attempts as "
                        "well as the tasks, beside the primary task-level interval, on the same "
                        "task resamples, with the mean of each bootstrap's replicates: a draw "
                        "resampled twice is an attempt a retry can meet twice, so the two need "
                        "not be centred alike. The transfer's one-stage interval is the one in "
                        "results/ladder.csv. " + IMPUTED)


# ----------------------------------------------------------------------------- appendix: comparators

def _ci(r, key) -> str:
    lo, hi = r.get(f"{key}_low"), r.get(f"{key}_high")
    return _interval(r[key], lo, hi) if lo is not None else _fmt(r[key])


def table_comparators(cmp: pd.DataFrame, out: str) -> List[str]:
    """Appendix: the registered comparators at the three table rates, automated verifier, with the
    intervals the ladder's fitted steps also carry, and the medians across configurations."""
    rows = []
    here = cmp[(cmp.regime_name == "automated") & (cmp.axis == "rate")]
    for config in order_of(here.config):
        for rate in TABLE_RATES:
            r = here[(here.config == config) & (here.rate == rate)]
            if not len(r):
                continue
            r = r.iloc[0]
            rows.append({
                "configuration": label_of(config), "$/h": f"{rate:.0f}",
                "cap in calls": _fmt(r.value_ii - r.value_iii),
                "cap in dollars [95%]": _ci(r, "dollar_cap_margin"),
                "rule over threshold [95%]": _ci(r, "rule_vs_threshold"),
                "searched over universal [95%]": _ci(r, "schedule_vs_universal"),
                "first look [95%]": _ci(r, "first_look_margin"),
                "rule, any point": _fmt(r.state_margin),
            })
    for rate in TABLE_RATES:
        r = here[here.rate == rate]
        rows.append({"configuration": "median", "$/h": f"{rate:.0f}",
                     "cap in calls": _fmt((r.value_ii - r.value_iii).median()),
                     "cap in dollars [95%]": _fmt(r.dollar_cap_margin.median()),
                     "rule over threshold [95%]": _fmt(r.rule_vs_threshold.median()),
                     "searched over universal [95%]": _fmt(r.schedule_vs_universal.median()),
                     "first look [95%]": _fmt(r.first_look_margin.median()),
                     "rule, any point": _fmt(r.state_margin.median())})
    t = pd.DataFrame(rows).fillna("")
    return _write_table(t, out, "tableA4_comparators",
                        caption="The registered comparators, automated verifier, dollars per task; "
                        "positive is what the richer or registered policy saves. Cap in calls: step "
                        "ii minus step iii. Cap in dollars: step ii minus K attempts at a dollar "
                        "cutoff, the prespecified sensitivity family. Rule over threshold: the "
                        "two-parameter threshold comparator minus the state rule. Searched over "
                        "universal: the universal restart schedule minus step iii-b. First look: step "
                        "iii-b minus the state rule allowed to act only at the first decision point, "
                        "beside the same margin for the unrestricted rule. Intervals: 100 replicates, "
                        "every family refitted inside each. " + IMPUTED)


def table_oracle(o: pd.DataFrame, out: str) -> List[str]:
    rows = []
    for regime, _ in REGIMES:
        for rate in TABLE_RATES:
            r = o[(o.regime_name == regime) & (o.rate == rate)]
            if not len(r):
                continue
            r = r.iloc[0]
            rows.append({"regime": REGIME_LABEL[regime], "$/h": f"{rate:.0f}",
                         "sample oracle": _fmt(r.value_oracle), "cascade": _fmt(r.value_cascade),
                         "best single": _fmt(r.value_best_single),
                         "escalate all*": _fmt(r.value_escalate),
                         "cascade minus oracle": _fmt(r.oracle_gap),
                         "share of the cascade": f"{r.oracle_gap / r.value_cascade:.0%}"})
    t = pd.DataFrame(rows)
    n = int(o.tasks.iloc[0])
    return _write_table(t, out, "tableA5_oracle",
                        caption=f"The sample oracle on the cascade's {n} common tasks: for each task "
                        "the cheapest schedule of one to four (configuration, cutoff) attempts on "
                        "that task's own draws, averaged. It bounds the class but is biased "
                        "downward by taking a minimum over configurations on four draws, so the gap "
                        "is an upper estimate of the value of knowing the task in advance. * Not "
                        "registered: every task sent straight to the outside option. " + IMPUTED)


DIFFICULTY_COLUMNS = (("under 15 minutes", "under 15 min"), ("15 minutes to 1 hour", "15 min to 1 h"),
                      ("1 to 4 hours", "1 to 4 h"), ("over 4 hours", "over 4 h"),
                      ("1 hour or more", "1 h or more"), ("all, chosen within bucket", "all, within"),
                      ("all, chosen blind", "all, blind"))


def table_difficulty(dd: pd.DataFrame, out: str) -> List[str]:
    """One row per configuration and regime, one column per bucket: the cap's saving at $100 an
    hour, starred where its interval excludes zero. The intervals themselves are in
    results/difficulty.csv; a bucket too small to choose on shows its count of tasks."""
    rows = []
    for regime in ("automated", "human 0.5"):
        for config in order_of(dd.config):
            here = dd[(dd.config == config) & (dd.regime_name == regime) & (dd.rate == 100.0)]
            row = {"regime": REGIME_LABEL[regime], "configuration": label_of(config)}
            for bucket, short in DIFFICULTY_COLUMNS:
                r = here[here.bucket == bucket]
                if not len(r):
                    row[short] = ""
                    continue
                r = r.iloc[0]
                if pd.isna(r.cap_margin):
                    row[short] = f"({int(r.tasks)})"
                    continue
                lo, hi = r.get("cap_margin_low"), r.get("cap_margin_high")
                star = "*" if (pd.notna(lo) and (lo > 0 or hi < 0)) else ""
                row[short] = f"{r.cap_margin:,.2f}{star}"
            rows.append(row)
    t = pd.DataFrame(rows)
    return _write_table(t, out, "tableA6_difficulty",
                        caption="The cap's marginal value by the benchmark's difficulty annotation, "
                        "every policy chosen within the bucket, dollars per task at $100 an hour. "
                        "* The 95 percent interval from 1,000 replicates excludes zero; every "
                        "interval is in results/difficulty.csv. Over 4 hours: too few tasks for a "
                        "training fold to choose on, with their count in parentheses; the two "
                        "longest buckets are also shown together. 'All, within' pools the choices "
                        "made under 15 minutes, from 15 minutes to 1 hour and at 1 hour or more; "
                        "'all, blind' is the primary. " + IMPUTED)


def table_distribution(ds: pd.DataFrame, out: str) -> List[str]:
    rows = []
    for regime in ("automated", "human 0.5"):
        for config in order_of(ds.config):
            r = ds[(ds.config == config) & (ds.regime_name == regime) & (ds.rate == 100.0)]
            if not len(r):
                continue
            r = r.iloc[0]
            rows.append({"regime": REGIME_LABEL[regime], "configuration": label_of(config),
                         "ii mean": _fmt(r.value_ii), "ii median": _fmt(r.median_ii),
                         "ii p95": _fmt(r.p95_ii), "iii mean": _fmt(r.value_iii),
                         "iii median": _fmt(r.median_iii), "iii p95": _fmt(r.p95_iii),
                         "cap's saving at p95": _fmt(r.cap_margin_p95),
                         "median version": _fmt(r.cap_margin_median)})
    t = pd.DataFrame(rows)
    return _write_table(t, out, "tableA7_distribution",
                        caption="Cost per incoming task at $100 an hour under steps ii and iii as "
                        "chosen on mean cost: its mean, median and 95th percentile over tasks and "
                        "the orderings of their draws. The median version is the primary comparison "
                        "with both families chosen and scored on median cost. " + IMPUTED)


def table_spread(sp: pd.DataFrame, out: str) -> List[str]:
    rows = []
    for regime, _ in REGIMES:
        for rate in TABLE_RATES:
            r = sp[(sp.regime_name == regime) & (sp.rate == rate)]
            if not len(r):
                continue
            r = r.iloc[0]
            rows.append({"regime": REGIME_LABEL[regime], "$/h": f"{rate:.0f}",
                         "across configurations, best policy": _fmt(r.across_best),
                         "across configurations, one attempt": _fmt(r.across_one),
                         "within a configuration, median": _fmt(r.within_median),
                         "within a configuration, largest": _fmt(r.within_max),
                         "cheapest": label_of(r.cheapest), "dearest": label_of(r.dearest)})
    t = pd.DataFrame(rows)
    n = int(sp.tasks.iloc[0])
    return _write_table(t, out, "tableA8_spread",
                        caption=f"On the cascade's {n} common tasks, dollars per task: the range of "
                        "policy value across the seven configurations, holding the policy at each "
                        "one's best or at a single attempt, against the range across steps i to "
                        "iii-b within a configuration. " + IMPUTED)


def table_diagnostics(dg_: pd.DataFrame, out: str) -> List[str]:
    rows = []
    for config in order_of(dg_.config):
        r = dg_[dg_.config == config].iloc[0]
        rows.append({"configuration": label_of(config), "tasks": int(r.tasks),
                     "within-task share of log-spend variance": f"{r.within_task_share:.0%}",
                     "mixed outcomes": f"{r.mixed_share:.0%}",
                     "all four fail": f"{r.all_fail_share:.0%}",
                     "all four resolve": f"{r.all_resolve_share:.0%}",
                     "median attempt, $": _fmt(r.median_attempt_cost, 3),
                     "attempts past their outside option at $25/h": f"{r.over_outside_25:.2%}"})
    t = pd.DataFrame(rows)
    return _write_table(t, out, "tableA9_diagnostics",
                        caption="Per configuration, on its tasks with four usable draws. Both shares "
                        "motivate restarts and neither bounds their value. " + IMPUTED)


TAIL_FLOOR = 0.01


def fig_tail(tc: pd.DataFrame, out: str):
    """Tail composition: for each cutoff, the share of the spend beyond it incurred by attempts that
    go on to resolve, and the chance an attempt still running there resolves."""
    order = order_of(tc.config)
    fig, axes = plt.subplots(2, 4, figsize=(9.6, 4.6), sharex=True, sharey=True)
    for ax, config in zip(axes.flat, order):
        s = tc[tc.config == config].sort_values("cutoff").copy()
        # a share of what a handful of attempts do is noise: draw the ratios only while at least
        # TAIL_FLOOR of attempts are still running
        thin = s.running < TAIL_FLOOR
        for col in ("resolving_beyond", "resolve_if_running", "over_outside_25"):
            if col in s:
                s.loc[thin, col] = np.nan
        ax.plot(s.cutoff, s.running, color=MUTED, linestyle=":", linewidth=1.2, zorder=2,
                label="still running")
        ax.plot(s.cutoff, s.resolving_beyond, color=SERIES_1, zorder=3,
                label="share of spend beyond it by attempts that resolve")
        ax.plot(s.cutoff, s.resolve_if_running, color=SERIES_2, linestyle="--", zorder=4,
                label="chance a running attempt resolves")
        if "over_outside_25" in s:
            ax.plot(s.cutoff, s.over_outside_25, color=INK_2, linestyle="-.", linewidth=1.0,
                    zorder=3, label="running attempts past their outside option at $25/h")
        ax.set_title(label_of(config), loc="left", color=INK)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0%}"))
    for ax in axes.flat[len(order):]:
        ax.axis("off")
    for ax in axes.flat[:len(order)]:
        _log_x(ax, ticks=(5, 10, 25, 50, 100, 250))
    fig.supxlabel("cutoff, calls", fontsize=8.5, color=INK_2, y=0.07)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.06))
    fig.suptitle("Tail composition: what a cutoff at each point would cut", x=0.01, ha="left",
                 fontsize=10, color=INK)
    fig.tight_layout(rect=(0.01, 0.08, 1, 0.97))
    return _save(fig, out, "figA3_tail_composition")


def _write_table(t: pd.DataFrame, out: str, name: str, caption: str) -> List[str]:
    paths = []
    p = os.path.join(out, f"{name}.csv")
    t.to_csv(p, index=False)
    paths.append(p)
    p = os.path.join(out, f"{name}.md")
    with open(p, "w") as fh:
        fh.write(_markdown(t) + f"\n\n{caption}\n")
    paths.append(p)
    p = os.path.join(out, f"{name}.tex")
    with open(p, "w") as fh:
        fh.write(_latex(t, caption, name))
    paths.append(p)
    return paths


def _markdown(t: pd.DataFrame) -> str:
    cols = list(t.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in t.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines)


def _latex(t: pd.DataFrame, caption: str, label: str) -> str:
    esc = lambda s: (str(s).replace("\\", "\\textbackslash{}").replace("&", "\\&")
                     .replace("%", "\\%").replace("$", "\\$").replace("#", "\\#")
                     .replace("_", "\\_").replace("\u2020", "$^\\dagger$"))
    cols = list(t.columns)
    body = ["\\begin{table}[t]", "\\centering", "\\small",
            f"\\caption{{{esc(caption)}}}", f"\\label{{tab:{label}}}",
            "\\begin{tabular}{" + "l" * 2 + "r" * (len(cols) - 2) + "}", "\\toprule",
            " & ".join(esc(c) for c in cols) + " \\\\", "\\midrule"]
    last = None
    for _, r in t.iterrows():
        first = r[cols[0]]
        if last is not None and first != last:
            body.append("\\midrule")
        last = first
        body.append(" & ".join(esc(r[c]) for c in cols) + " \\\\")
    body += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(body)


# ----------------------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", default=os.path.join("exhibits", "out"))
    ap.add_argument("--bare", action="store_true",
                    help="figures without their titles and notes, for the manuscript, which "
                         "carries them in its captions")
    a = ap.parse_args(argv)
    global BARE
    BARE = a.bare
    os.makedirs(a.out, exist_ok=True)
    _style()
    got = load(a.results)
    d = got["ladder"]
    written = []
    written += fig_cap_margin(d, a.out)
    written += fig_ladder(d, a.out)
    written += fig_transfer(d, a.out)
    written += fig_transfer(d, a.out, regime="human 0.5", name="figA1_transfer_review_05")
    if "breakeven" in got:
        written += table_ladder(d, got["breakeven"], a.out)
        written += table_breakeven(d, got["breakeven"], a.out)
        written += fig_attempt_units(got["breakeven"], a.out)
    written += table_transfer(d, a.out)
    if "cascade" in got:
        written += fig_cascade(got["cascade"], a.out)
        if "outcome_correlation" in got:
            written += fig_correlation(got["outcome_correlation"], a.out,
                                       int(got["cascade"].tasks.iloc[0]))
    if "sensitivity_breakeven" in got and "breakeven" in got:
        written += table_sensitivity_breakeven(got["breakeven"], got["sensitivity_breakeven"],
                                               a.out)
    if "sensitivity_ladder" in got:
        written += table_sensitivity_margins(d, got["sensitivity_ladder"], got.get("cascade"),
                                             got.get("sensitivity_cascade"), a.out)
    if "sensitivity_two_stage" in got:
        written += table_two_stage(got["sensitivity_two_stage"], d, a.out)
    for name, draw in (("comparators", table_comparators), ("oracle", table_oracle),
                       ("difficulty", table_difficulty), ("distribution", table_distribution),
                       ("spread", table_spread), ("diagnostics", table_diagnostics),
                       ("tail_composition", fig_tail)):
        if name in got:
            written += draw(got[name], a.out)
    for p in written:
        print(p)


if __name__ == "__main__":
    main()
