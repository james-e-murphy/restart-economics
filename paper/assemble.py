"""Assemble the manuscript from its parts and the exhibits.

    python paper/assemble.py --exhibits paper/build/figures

The parts in paper/parts/ are the source. A block

    {{table NAME
    caption
    }}

becomes that exhibit's table from exhibits/make.py, under its caption; {{figure NAME ...}} becomes
the figure; and {{ladder ...}} becomes Table 3, set from table1_ladder.csv in two panels. When an
exhibit has not been written yet, because its results file does not exist, the block becomes a
note saying so, and the build reports it. Negative numbers in the exhibits are set with a minus
sign rather than a hyphen. Nothing here computes a number.
"""
from __future__ import annotations

import argparse
import csv
import glob
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "Restart_Economics_Manuscript_v0_1_2026_09_21.md"
BLOCK = re.compile(r"\{\{(table|figure|ladder|transfer)( [A-Za-z0-9_]+)?\n(.*?)\n\}\}", re.S)
ORDER = ("gpt-5_4runs", "gpt_5.2_4runs", "claude-sonnet-4_4runs", "claude-sonnet-4.5_4runs",
         "gemini-3-pro-preview_4runs", "kimi-k2_4runs", "qwen3-coder-480b-a35b-instruct-4runs")
LABEL = {"gpt-5_4runs": "GPT-5", "gpt_5.2_4runs": "GPT-5.2", "claude-sonnet-4_4runs": "Sonnet 4",
         "claude-sonnet-4.5_4runs": "Sonnet 4.5", "gemini-3-pro-preview_4runs": "Gemini 3 Pro",
         "kimi-k2_4runs": "Kimi K2", "qwen3-coder-480b-a35b-instruct-4runs": "Qwen3 Coder\u2020"}
MINUS = re.compile(r"(?<![\w.])-(?=\d)")


def minus(s: str) -> str:
    return MINUS.sub("−", s)


def collapse(rows):
    """Leave a label blank where it repeats the row above, in the first two columns, the
    second only while the first repeats too, so that a long table reads in groups."""
    out, prev = [], None
    for r in rows:
        shown = list(r)
        if prev is not None and r[0] == prev[0]:
            shown[0] = ""
            if len(r) > 1 and r[1] == prev[1] and not re.fullmatch(r"[\d.$\u2212-]+", r[1]):
                shown[1] = ""
        out.append(shown)
        prev = r
    return out


def exhibit_table(path: str) -> str:
    """The pipe table from an exhibit's markdown, without the caption that follows it, with
    repeated labels collapsed."""
    lines = [l for l in open(path).read().splitlines() if l.startswith("|")]
    head, rule, body = lines[0], lines[1], lines[2:]
    rows = collapse([[c.strip() for c in l.strip().strip("|").split("|")] for l in body])
    return minus("\n".join([head, rule] + ["| " + " | ".join(r) + " |" for r in rows]))


def choices(s: str) -> str:
    """The folds' distinct choices for step iii, grouped by budget: '4x@80, 4x@85, 4x@none'
    becomes '4×80/85/none'."""
    groups = {}
    for item in (x.strip() for x in s.split(",") if x.strip()):
        k, _, cut = item.partition("x@")
        groups.setdefault(k, []).append(cut)
    return ", ".join(f"{k}×{'/'.join(v)}" for k, v in groups.items())


def ladder(path: str) -> str:
    """Table 3: steps i to iii-b with the cap's saving and the folds' choices, in two panels,
    set so that no cell wraps (a nowrap div, which blocks.lua sets at natural widths)."""
    rows = list(csv.DictReader(open(path)))
    head = ("| Configuration | $/h | i | ii | iii | iii-b | Cap's saving [95%] | Step iii chose "
            "| Escalate all\\* |\n|:---|---:|---:|---:|---:|---:|---:|:---|---:|")
    out, regime, config = [head], None, None
    for r in rows:
        if r["regime"] != regime:
            regime = r["regime"]
            label = regime[0].upper() + regime[1:]
            out.append(f"| **{label}** | | | | | | | | |")
            config = None
        name = r["configuration"] if r["configuration"] != config else ""
        config = r["configuration"]
        chose = choices(r["iii chose"])
        saving = r["cap's saving [95%]"]
        out.append(f"| {name} | {r['$/h']} | {r['i']} | {r['ii']} | {r['iii']} | {r['iii-b']} "
                   f"| {saving} | {chose} | {r['escalate all*']} |")
    return minus("\n".join(out))


def _cells(line: str):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def widths(text: str) -> str:
    """Give every pipe table relative column widths from its content. A wide pipe table is set
    at the full text width with its columns in proportion to the dashes under the header, so
    equal dashes give a label column the same room as a column of short numbers. Each column
    gets the length of its longest cell, counting only the longest word of a header, since a
    header can wrap, within bounds that keep a short column legible and a long one from taking
    the table."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) - 1:
        if lines[i].startswith("|") and re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", lines[i + 1]):
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                j += 1
            head = _cells(lines[i])
            body = [_cells(l) for l in lines[i + 2:j]]
            n = len(head)
            w = [max([max((len(x) for x in h.split()), default=1)] +
                     [len(r[k]) for r in body if k < len(r)]) for k, h in enumerate(head)]
            w = [min(max(x, 4), 36) for x in w]
            rule = _cells(lines[i + 1])
            lines[i + 1] = "|" + "|".join(
                (":" if c.startswith(":") else "") + "-" * x + (":" if c.endswith(":") else "")
                for c, x in zip(rule, w)) + "|"
            assert all(len(r) == n for r in body), f"ragged table at: {lines[i]}"
            i = j
        else:
            i += 1
    return "\n".join(lines)


def _band(v, lo, hi) -> str:
    """An estimate with its interval, the endpoint nearest zero to three places when two would
    round it to zero."""
    def end(x):
        return f"{x:.3f}" if 0 < abs(x) < 0.005 else f"{x:.2f}"
    return f"{v:.2f} [{end(lo)}, {end(hi)}]"


def transfer(path: str) -> str:
    """Table 5, from results/ladder.csv: the primary transfer with its intervals at the three
    fitted rates, the within-configuration rule's margin at $100, and how far the transferred rule
    sits from retrying without a cap."""
    rows = [r for r in csv.DictReader(open(path))
            if r["regime_name"] == "automated" and r["axis"] == "rate"
            and r["transfer_margin_low"] != ""]
    by = {(r["config"], float(r["rate"])): r for r in rows}
    configs = [c for c in ORDER if any(k[0] == c for k in by)]
    head = ("| Configuration | $25 | $100 | $300 | Within, $100 | Transferred minus ii |\n"
            "|:---|---:|---:|---:|---:|---:|")
    out = [head]
    for c in configs:
        cells = []
        for rate in (25.0, 100.0, 300.0):
            r = by[(c, rate)]
            cells.append(_band(float(r["transfer_margin"]), float(r["transfer_margin_low"]),
                               float(r["transfer_margin_high"])))
        r = by[(c, 100.0)]
        cells.append(f"{float(r['state_margin']):.2f}")
        cells.append(f"{float(r['value_iv_transfer']) - float(r['value_ii']):.3f}")
        out.append(f"| {LABEL.get(c, c)} | " + " | ".join(cells) + " |")
    counts = {r["fitted_replicates"] for r in rows}
    assert len(counts) == 1, f"mixed replicate counts in the fitted intervals: {counts}"
    return minus("\n".join(out))


def render(text: str, exhibits: str, missing: list, results: str = "") -> str:
    def one(m):
        kind, name, caption = m.group(1), (m.group(2) or "").strip(), m.group(3).strip()
        if kind == "ladder":
            path = os.path.join(exhibits, "table1_ladder.csv")
            if not os.path.exists(path):
                missing.append("table1_ladder")
                return f"> Pending: {caption}"
            return f"::: nowrap\n\nTable: {caption}\n\n{ladder(path)}\n\n:::"
        if kind == "transfer":
            path = os.path.join(results, "ladder.csv")
            if not os.path.exists(path):
                missing.append("ladder")
                return f"> Pending: {caption}"
            return f"Table: {caption}\n\n{transfer(path)}"
        if kind == "table":
            path = os.path.join(exhibits, f"{name}.md")
            if not os.path.exists(path):
                missing.append(name)
                return (f"> Pending the final appendix run, which writes this table from the "
                        f"results. {caption}")
            return f"Table: {caption}\n\n{exhibit_table(path)}"
        path = os.path.join(exhibits, f"{name}.pdf")
        label = re.match(r"\*\*(Figure [A-Z]?\d+)\.", caption)
        if not os.path.exists(path):
            missing.append(name)
            return (f"> Pending the final appendix run, which draws this figure from the "
                    f"results. {caption}")
        return f"![{label.group(1)}](figures/{name}.pdf)\n\n> {caption}"
    return BLOCK.sub(one, text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exhibits", default=os.path.join(HERE, "build", "figures"))
    ap.add_argument("--results", default=os.path.join(HERE, os.pardir, "results"))
    ap.add_argument("--out", default=os.path.join(HERE, NAME))
    a = ap.parse_args(argv)
    parts = sorted(glob.glob(os.path.join(HERE, "parts", "*.md")))
    text = "\n\n".join(open(p).read().strip("\n") for p in parts) + "\n"
    missing: list = []
    text = widths(render(text, a.exhibits, missing, a.results))
    left = re.findall(r"\{\{\w+", text)
    assert not left, f"unrendered blocks: {left}"
    with open(a.out, "w") as fh:
        fh.write(text)
    print(f"wrote {a.out}")
    for name in missing:
        print(f"  pending: {name}")


if __name__ == "__main__":
    main()
