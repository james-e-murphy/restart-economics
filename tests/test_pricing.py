"""The price schedules: tiers, the reading of the prompt count, and the harness-accounting variants."""
import random

import pytest

from restart.pricing import HARNESS, SCHEDULES, SENSITIVITY, price_call, validate, _main


def _rows(key, n=300, seed=0, schedules=None, cw_share=0.0, max_prompt=150_000):
    """Calls whose logged cost is generated from a schedule, with OpenAI-style prompt counts."""
    rnd, rows = random.Random(seed), []
    for _ in range(n):
        p = rnd.randint(2_000, max_prompt); cr = rnd.randint(0, int(p * 0.9)); cw = int((p - cr) * cw_share)
        c = rnd.randint(20, 4_000)
        rows.append(dict(prompt_tokens=str(p), completion_tokens=str(c), cache_read_tokens=str(cr),
                         cache_write_tokens=str(cw), cost_logged=repr(price_call(key, p, c, cr, cw, schedules))))
    return rows


def test_every_schedule_is_dated_sourced_and_complete():
    for table in (SCHEDULES, HARNESS, SENSITIVITY):
        for key, s in table.items():
            assert s["date"] and s["source"] and s["model"], key
            assert s["tiers"][-1][0] is None, key
            bounds = [b for b, _ in s["tiers"][:-1]]
            assert bounds == sorted(bounds), key
            assert set(s["prompt_includes"]) <= {"read", "write"}, key
    assert set(HARNESS) <= set(SCHEDULES) and set(SENSITIVITY) <= set(SCHEDULES)


def test_real_calls_to_the_cent():
    # two GPT-5 calls observed in the audit, by archive name and by model string
    assert abs(price_call("gpt-5_4runs", 74466, 2069, 73216) - 0.0314045) < 1e-12
    assert abs(price_call("gpt-5-2025-08-07", 7009, 215, 5632) - 0.00457525) < 1e-12


def test_long_context_tier_is_set_by_total_input():
    g = "gemini-3-pro-preview_4runs"
    assert abs(price_call(g, 200_000, 1_000, 150_000) - (50_000 * 2e-6 + 150_000 * 0.2e-6 + 1_000 * 12e-6)) < 1e-12
    assert abs(price_call(g, 200_001, 1_000, 150_000) - (50_001 * 4e-6 + 150_000 * 0.4e-6 + 1_000 * 18e-6)) < 1e-12
    q = "qwen3-coder-480b-a35b-instruct-4runs"
    assert abs(price_call(q, 32_000, 100) - (32_000 * 1e-6 + 100 * 5e-6)) < 1e-12
    assert abs(price_call(q, 32_001, 100, 30_000) - (2_001 * 1.8e-6 + 30_000 * 0.72e-6 + 100 * 9e-6)) < 1e-12
    assert abs(price_call(q, 130_000, 100) - (130_000 * 3e-6 + 100 * 15e-6)) < 1e-12
    rows = [dict(prompt_tokens=str(t), completion_tokens="1", cache_read_tokens="0", cache_write_tokens="0")
            for t in (10, 32_000, 32_001, 128_000, 200_000, 256_001)]
    assert validate(rows, q)["calls_per_tier"] == [2, 2, 1, 1]
    assert validate(rows, g)["calls_per_tier"] == [5, 1]


def test_the_reading_of_the_prompt_count():
    # Sonnet 4 logs a prompt count without cache writes: the same call priced under Sonnet 4.5's
    # reading comes out with negative uncached input, which validate flags
    row = dict(prompt_tokens="30000", completion_tokens="500", cache_read_tokens="29000", cache_write_tokens="4000")
    assert abs(price_call("claude-sonnet-4_4runs", 30000, 500, 29000, 4000)
               - (1000 * 3e-6 + 29000 * 0.3e-6 + 4000 * 3.75e-6 + 500 * 15e-6)) < 1e-12
    assert validate([row], "claude-sonnet-4_4runs")["negative_uncached"] == 0
    assert validate([row], "claude-sonnet-4.5_4runs")["negative_uncached"] == 1


@pytest.mark.parametrize("key", sorted(HARNESS))
def test_harness_variant_reproduces_its_own_cost_and_differs_from_the_published(key):
    rows = _rows(key, schedules=HARNESS, cw_share=0.2 if key.startswith("claude") else 0.0,
                 max_prompt=260_000 if key.startswith("gemini") else 150_000)
    h = validate(rows, key, schedules=HARNESS)
    assert h["mismatches"] == 0 and h["calls_checked"] == len(rows)
    p = validate(rows, key)
    assert p["mismatches"] > 0.9 * len(rows) and p["logged_usd"] > p["schedule_usd_on_checked"]


def test_sonnet_37_harness_charges_writes_twice():
    k = "claude-sonnet-3.7_4runs"
    got = price_call(k, 50_000, 800, 40_000, 6_000, HARNESS)
    published = price_call(k, 50_000, 800, 40_000, 6_000)
    assert abs(got - published - 6_000 * 3e-6) < 1e-12


def test_the_published_schedule_reproduces_the_configurations_that_computed_cost_correctly():
    for key in ("gpt-5_4runs", "claude-sonnet-4_4runs", "claude-sonnet-4.5_4runs"):
        v = validate(_rows(key, cw_share=0.1 if key.startswith("claude") else 0.0), key)
        assert v["mismatches"] == 0 and v["ratio_median"] == 1.0, key


def test_qwen_sensitivity_is_lower_and_no_cost_is_checked():
    k = "qwen3-coder-480b-a35b-instruct-4runs"
    rows = [dict(prompt_tokens="60000", completion_tokens="300", cache_read_tokens="58000",
                 cache_write_tokens="0", cost_logged="")]
    a, b = validate(rows, k), validate(rows, k, schedules=SENSITIVITY)
    assert a["calls_checked"] == 0 and a["calls_priced"] == 1 and a["ratio_median"] is None
    assert 0 < b["schedule_usd"] < a["schedule_usd"]


def test_validate_command_runs(tmp_path, capsys):
    d = tmp_path / "gpt-5_4runs"; d.mkdir()
    rows = _rows("gpt-5_4runs", n=5)
    with open(d / "prefix_x.csv", "w") as fh:
        fh.write(",".join(rows[0]) + "\n" + "\n".join(",".join(r.values()) for r in rows) + "\n")
    _main(["--validate", str(tmp_path)])
    out = capsys.readouterr().out
    assert "gpt-5_4runs" in out and "0 differ" in out
