"""Pricing: a pure function from physical quantities and a dated schedule to dollars.

Kept separate from extraction so that a price change refits policies rather than rescaling a
stored total.

The rule. Each configuration is priced at its model developer's published list price in force
on the run's first day, applied to the token classes that developer bills: uncached input, cache
reads, cache writes and output (reasoning tokens are billed within output), with any
long-context tier. Qwen3 Coder ran on a self-hosted server, has no run date and no bill; it is
priced at the developer's price for the model's hosted API when the model was released, with the
lowest third-party price for the same weights as a sensitivity.

Logged cost is not the price. It establishes what the logged token counts include (whether the
prompt count contains cache reads and cache writes), and it validates the schedule on every call
where the harness computed cost correctly. Where the harness did not, a harness-accounting
variant of the published schedule (``HARNESS``) reproduces the logged cost on every call, which
locates the deviation in the harness's arithmetic rather than in the prices or the token counts.

Prices are written in dollars per million tokens.
"""
from __future__ import annotations

M = 1e-6


def _rates(input, cached, output, cache_write=0.0):
    return dict(input=input * M, cached=cached * M, cache_write=cache_write * M, output=output * M)


# Keyed by archive name, as the per-archive folders under data/derived are named. ``tiers`` is a
# list of (largest prompt, in total input tokens, that the tier covers; rates), the last with None.
# ``prompt_includes`` names the cache classes the logged prompt count contains.
SCHEDULES = {
    "gpt-5_4runs": dict(
        model="gpt-5-2025-08-07", endpoint="OpenAI API", date="2025-12-31",
        prompt_includes=("read",),
        tiers=[(None, _rates(1.25, 0.125, 10.0))],
        source="OpenAI's published price for gpt-5-2025-08-07, as Bai et al. state it (Appendix B.2). "
               "Reproduces logged cost on every call."),
    "gpt_5.2_4runs": dict(
        model="gpt-5.2", endpoint="OpenRouter (openai/gpt-5.2)", date="2026-01-21",
        prompt_includes=("read",),
        tiers=[(None, _rates(1.75, 0.175, 14.0))],
        source="OpenAI's model page for gpt-5.2 (snapshot gpt-5.2-2025-12-11) and OpenRouter's listing, both "
               "$1.75/$0.175/$14, read 19 Sep 2026; LiteLLM's price table at the run date (commit 9e1275b76c, "
               "20 Jan 2026) lists the same for openrouter/openai/gpt-5.2. No long-context tier."),
    "gemini-3-pro-preview_4runs": dict(
        model="gemini-3-pro-preview", endpoint="OpenRouter (google/gemini-3-pro-preview)", date="2026-01-18",
        prompt_includes=("read",),
        tiers=[(200_000, _rates(2.0, 0.20, 12.0)), (None, _rates(4.0, 0.40, 18.0))],
        source="Google's launch post, 18 Nov 2025: $2 input and $12 output per million for prompts of 200k tokens "
               "or less. LiteLLM's price table at the run date (commit ce1a2c3209, 17 Jan 2026) lists the full "
               "schedule, cache reads $0.20 and $0.40 and the over-200k tier $4/$18, for gemini-3-pro-preview and "
               "openrouter/google/gemini-3-pro-preview. The model was shut down on 9 Mar 2026; the Gemini API "
               "pricing page now lists its successor, 3.1 Pro Preview, at the identical schedule (19 Sep 2026). "
               "Implicit caching has no write charge."),
    "kimi-k2_4runs": dict(
        model="kimi-k2-0905", endpoint="OpenRouter (moonshotai/kimi-k2-0905)", date="2026-01-04",
        prompt_includes=("read",),
        tiers=[(None, _rates(0.60, 0.15, 2.50))],
        source="Moonshot's price for kimi-k2-0905-preview: cache miss $0.60, cache hit $0.15, output $2.50, "
               "262,144-token context, as quoted from Moonshot's pricing page in LiteLLM issue #17417 "
               "(3 Dec 2025); LiteLLM's price table at the run date (commit 9b1c5f7e36, 4 Jan 2026) lists the "
               "same; OpenRouter lists $0.60/$2.50 for the model (19 Sep 2026). No long-context tier."),
    "qwen3-coder-480b-a35b-instruct-4runs": dict(
        model="Qwen3-Coder-480B-A35B-Instruct-FP8", endpoint="self-hosted OpenAI-compatible server",
        date="2025-07-22",
        prompt_includes=("read",),
        tiers=[(32_000, _rates(1.0, 0.40, 5.0)), (128_000, _rates(1.8, 0.72, 9.0)),
               (256_000, _rates(3.0, 1.20, 15.0)), (None, _rates(6.0, 2.40, 60.0))],
        source="Imputed: no bill exists and the run date is not logged. Alibaba Cloud Model Studio's standard "
               "price for qwen3-coder-plus, the hosted API the Qwen3-Coder release post (22 Jul 2025) points to, "
               "tiered by input tokens, as stated against a discount that ran 24 Jul to 23 Aug 2025 on Alibaba's "
               "page 'Limited-time discount for Qwen3-Coder-Plus'. Tier bounds read as thousands of tokens."),
    "claude-sonnet-4_4runs": dict(
        model="claude-sonnet-4-20250514", endpoint="All Hands LLM proxy (evaluation)", date="2025-06-02",
        prompt_includes=("read",),
        tiers=[(None, _rates(3.0, 0.30, 15.0, cache_write=3.75))],
        source="Anthropic's published price: cache reads at a tenth of input, five-minute cache writes at 1.25 "
               "times input, as Bai et al. state for writes. The logged prompt count includes cache reads but "
               "not cache writes. Reproduces logged cost on every call."),
    "claude-sonnet-4.5_4runs": dict(
        model="claude-sonnet-4-5-20250929", endpoint="Anthropic API", date="2025-12-19",
        prompt_includes=("read", "write"),
        tiers=[(None, _rates(3.0, 0.30, 15.0, cache_write=3.75))],
        source="Anthropic's published price, as for Sonnet 4; the long-context premium applies only with the "
               "1M-context beta and no call exceeds 200k tokens. The logged prompt count includes cache reads "
               "and writes. Reproduces logged cost on every call."),
    # excluded (condition 2); priced only to document its harness's accounting
    "claude-sonnet-3.7_4runs": dict(
        model="claude-3-7-sonnet-20250219", endpoint="All Hands LLM proxy (app)", date="2025-04-08",
        prompt_includes=("read", "write"),
        tiers=[(None, _rates(3.0, 0.30, 15.0, cache_write=3.75))],
        source="Anthropic's published price. Excluded configuration."),
}


def _variant(key, note, **changes):
    s = dict(SCHEDULES[key], source=note)
    s.update(changes)
    return s


# The published schedule as the harness applied it, where that differs: each reproduces the
# logged cost on every call. Not used for pricing.
HARNESS = {
    "gpt_5.2_4runs": _variant(
        "gpt_5.2_4runs", "Cache reads charged at the input price.",
        tiers=[(None, _rates(1.75, 1.75, 14.0))]),
    "gemini-3-pro-preview_4runs": _variant(
        "gemini-3-pro-preview_4runs", "Cache reads charged at the input price; the over-200k tier not applied.",
        tiers=[(None, _rates(2.0, 2.0, 12.0))]),
    "claude-sonnet-3.7_4runs": _variant(
        "claude-sonnet-3.7_4runs", "The prompt count read as excluding cache writes, which it includes, so "
        "written tokens are charged once as input and again as cache writes.",
        prompt_includes=("read",)),
}

# Prespecified sensitivity for the imputed schedule.
SENSITIVITY = {
    "qwen3-coder-480b-a35b-instruct-4runs": _variant(
        "qwen3-coder-480b-a35b-instruct-4runs",
        "The lowest price OpenRouter lists for the same open weights, Google Vertex, $0.22 input and $1.80 "
        "output, with no cache price listed, so cache reads at the input price (19 Sep 2026).",
        tiers=[(None, _rates(0.22, 0.22, 1.80))]),
}

_BY_MODEL = {s["model"]: s for k, s in SCHEDULES.items() if k != "claude-sonnet-3.7_4runs"}


def _schedule(key, schedules=None):
    if isinstance(key, dict):
        return key
    table = schedules or SCHEDULES
    return table[key] if key in table else _BY_MODEL[key]


def _split(s, prompt_tokens, cache_read_tokens, cache_write_tokens):
    """(uncached input, total input) for one call under the schedule's reading of the prompt count."""
    inc = s["prompt_includes"]
    p, cr, cw = prompt_tokens or 0, cache_read_tokens or 0, cache_write_tokens or 0
    uncached = p - (cr if "read" in inc else 0) - (cw if "write" in inc else 0)
    total = p + (0 if "read" in inc else cr) + (0 if "write" in inc else cw)
    return uncached, total


def rates_for(s, total_input):
    for bound, r in s["tiers"]:
        if bound is None or total_input <= bound:
            return r
    raise ValueError("no tier covers this prompt")


def price_call(key, prompt_tokens: int, completion_tokens: int,
               cache_read_tokens: int = 0, cache_write_tokens: int = 0,
               schedules: dict | None = None) -> float:
    """Dollars for one call. ``key`` is an archive name, a model string, or a schedule itself."""
    s = _schedule(key, schedules)
    uncached, total = _split(s, prompt_tokens, cache_read_tokens, cache_write_tokens)
    r = rates_for(s, total)
    return (uncached * r["input"] + (cache_read_tokens or 0) * r["cached"]
            + (cache_write_tokens or 0) * r["cache_write"] + (completion_tokens or 0) * r["output"])


def _int(v):
    return int(v) if v not in (None, "") else 0


def validate(prefix_rows, key, tol: float = 1e-7, schedules: dict | None = None) -> dict:
    """Price every call and compare with cost_logged where it exists. Returns a summary; raises
    nothing. ``negative_uncached`` counts calls whose uncached input comes out negative, which
    means the schedule's reading of the prompt count is wrong for this configuration."""
    s = _schedule(key, schedules)
    n = bad = neg = priced = 0
    worst = logged = recon = recon_all = 0.0
    ratios, tiers = [], [0] * len(s["tiers"])
    for r in prefix_rows:
        p, c = _int(r.get("prompt_tokens")), _int(r.get("completion_tokens"))
        cr, cw = _int(r.get("cache_read_tokens")), _int(r.get("cache_write_tokens"))
        uncached, total = _split(s, p, cr, cw)
        neg += uncached < 0
        tiers[[i for i, (b, _) in enumerate(s["tiers"]) if b is None or total <= b][0]] += 1
        calc = price_call(s, p, c, cr, cw)
        priced += 1
        recon_all += calc
        if r.get("cost_logged") in (None, ""):
            continue
        got = float(r["cost_logged"])
        diff = abs(calc - got)
        n += 1
        worst = max(worst, diff)
        bad += diff > tol
        logged += got
        recon += calc
        if calc > 0:
            ratios.append(got / calc)
    ratios.sort()
    q = (lambda f: round(ratios[min(len(ratios) - 1, int(f * len(ratios)))], 4)) if ratios else (lambda f: None)
    return dict(key=key if isinstance(key, str) else s.get("model"), calls_priced=priced, calls_checked=n,
                mismatches=bad, worst_abs_diff=worst, tol=tol, negative_uncached=neg, calls_per_tier=tiers,
                logged_usd=round(logged, 4), schedule_usd_on_checked=round(recon, 4),
                schedule_usd=round(recon_all, 4),
                ratio_p05=q(0.05), ratio_median=q(0.5), ratio_p95=q(0.95))


# ----------------------------------------------------------------------------- implied prices

LONG_CONTEXT = 200_000      # prompt size above which several providers charge a higher tier


def _classes(r: dict, prompt_includes_cache: bool) -> tuple[float, float, float, float]:
    """(uncached input, cache read, cache write, output) tokens for one call. Providers differ on
    whether the reported prompt count includes the cached and cache-written tokens."""
    p = int(r.get("prompt_tokens") or 0)
    cr = int(r.get("cache_read_tokens") or 0)
    cw = int(r.get("cache_write_tokens") or 0)
    c = int(r.get("completion_tokens") or 0)
    return (p - cr - cw if prompt_includes_cache else p), cr, cw, c


def _nnls(X, y):
    """Least squares with non-negative coefficients, exact for a handful of columns: the best
    unconstrained fit over every subset of columns whose coefficients all come out non-negative."""
    import itertools
    import numpy as np
    best, k = None, X.shape[1]
    for m in range(1, k + 1):
        for cols in itertools.combinations(range(k), m):
            with np.errstate(all="ignore"):     # spurious BLAS flags on some platforms
                b, *_ = np.linalg.lstsq(X[:, cols], y, rcond=None)
                if (b < 0).any():
                    continue
                full = np.zeros(k)
                full[list(cols)] = b
                sse = float(((X @ full - y) ** 2).sum())
            if best is None or sse < best[1]:
                best = (full, sse)
    return best[0] if best else np.zeros(k)


def implied_prices(prefix_rows) -> dict:
    """The per-token prices that best reproduce the logged per-call cost, in dollars per million
    tokens, under both readings of the prompt count, for calls at or under the long-context
    threshold and above it. An exact fit (every call within a thousandth of its cost) means the
    harness priced calls with a fixed schedule in these token classes; the fitted prices can then
    be compared with the provider's published schedule."""
    import numpy as np
    rows = [r for r in prefix_rows if r.get("cost_logged") not in (None, "")]
    out = dict(calls=len(rows), calls_with_zero_cost=sum(float(r["cost_logged"]) == 0 for r in rows))
    if not rows or out["calls_with_zero_cost"] == len(rows):
        return out
    y_all = np.array([float(r["cost_logged"]) for r in rows])
    long_ = np.array([int(r.get("prompt_tokens") or 0) > LONG_CONTEXT for r in rows])
    out["calls_over_200k"] = int(long_.sum())
    for incl in (True, False):
        X_all = np.array([_classes(r, incl) for r in rows], dtype=float)
        key = "prompt_includes_cache" if incl else "prompt_excludes_cache"
        res = dict(negative_uncached_calls=int((X_all[:, 0] < 0).sum()))
        for name, mask in (("under_200k", ~long_), ("over_200k", long_)):
            if mask.sum() < 20:
                continue
            X, y = X_all[mask], y_all[mask]
            b = _nnls(X, y)
            with np.errstate(all="ignore"):
                fit = X @ b
            exact = np.abs(fit - y) <= np.maximum(1e-7, 1e-3 * np.abs(y))
            ss = float(((y - y.mean()) ** 2).sum())
            res[name] = dict(
                usd_per_million=dict(zip(("input", "cache_read", "cache_write", "output"),
                                         [round(float(v) * 1e6, 4) for v in b])),
                r2=round(1 - float(((fit - y) ** 2).sum()) / ss, 6) if ss else None,
                exact_share=round(float(exact.mean()), 4), calls=int(mask.sum()))
        out[key] = res
    return out


def _rows(folder):
    import csv
    import glob
    import os
    f = glob.glob(os.path.join(folder, "prefix_*.csv"))
    if not f:
        return None
    with open(f[0], newline="") as fh:
        return list(csv.DictReader(fh))


def _print_implied(name, rows):
    r = implied_prices(rows)
    if "prompt_includes_cache" not in r:
        print(f"{name}: {r['calls']} calls, all with zero or no logged cost")
        return
    print(f"{name}: {r['calls']} calls, {r['calls_over_200k']} with prompts over 200k tokens")
    for key in ("prompt_includes_cache", "prompt_excludes_cache"):
        res = r[key]
        for bucket in ("under_200k", "over_200k"):
            if bucket in res:
                b = res[bucket]
                u = b["usd_per_million"]
                print(f"  {key:22s} {bucket:10s} $/M input {u['input']:8.4f}  cache read {u['cache_read']:7.4f}"
                      f"  cache write {u['cache_write']:7.4f}  output {u['output']:8.4f} | exact {b['exact_share']:.4f}"
                      f"  r2 {b['r2']} | {b['calls']} calls | negative uncached {res['negative_uncached_calls']}")


def _print_validation(name, rows):
    if name not in SCHEDULES:
        print(f"{name}: no schedule")
        return
    print(f"{name}  (priced at {SCHEDULES[name]['date']})")
    for label, table in (("published", SCHEDULES), ("harness", HARNESS), ("sensitivity", SENSITIVITY)):
        if name not in table:
            continue
        v = validate(rows, name, schedules=table)
        line = (f"  {label:11s} {v['calls_priced']:>7,} calls  schedule ${v['schedule_usd']:>10,.2f}"
                f"  negative uncached {v['negative_uncached']}")
        if len(v["calls_per_tier"]) > 1:
            line += f"  calls per tier {v['calls_per_tier']}"
        if v["calls_checked"]:
            line += (f" | {v['calls_checked']:,} with logged cost ${v['logged_usd']:,.2f} against"
                     f" ${v['schedule_usd_on_checked']:,.2f}, {v['mismatches']:,} differ (worst ${v['worst_abs_diff']:.6f})"
                     f"; logged/schedule per call p5 {v['ratio_p05']} median {v['ratio_median']} p95 {v['ratio_p95']}")
        print(line)


def _main(argv=None):
    import argparse
    import glob
    import os
    ap = argparse.ArgumentParser(description="Validate each configuration's schedule against logged cost, "
                                             "or fit the prices its logged cost implies.")
    ap.add_argument("--validate", metavar="DIR", help="folder of per-archive extraction folders")
    ap.add_argument("--implied", metavar="DIR", help="folder of per-archive extraction folders")
    a = ap.parse_args(argv)
    if not (a.validate or a.implied):
        ap.error("give --validate or --implied")
    for d in sorted(glob.glob(os.path.join(a.validate or a.implied, "*/"))):
        rows = _rows(d)
        if rows is None:
            continue
        name = os.path.basename(d.rstrip("/"))
        (_print_validation if a.validate else _print_implied)(name, rows)


if __name__ == "__main__":
    _main()
