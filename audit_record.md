# Audit record

What the audit protocol in AUDIT.md found, item by item, for the nine archives of `loong0814/openhands_trajectories`, 16 to 19 September 2026. Per-archive figures are in `configurations.csv`, which `python -m restart.audit` builds from the extraction; this record states what was checked, what was found, and the rule adopted. Items still open are marked as such.

The nine archives, by the name used below:

| Name | Archive | Configuration |
|---|---|---|
| Sonnet 3.7 | `claude-sonnet-3.7_4runs` | `claude-3-7-sonnet-20250219_maxiter_100_N_v0.31.0-no-hint-juan-inst-t1` |
| Sonnet 4 | `claude-sonnet-4_4runs` | `claude-sonnet-4-20250514_maxiter_500_N_v0.40.0-no-hint-main-06-02-2025-t1-rerank` |
| Sonnet 4.5 | `claude-sonnet-4.5_4runs` | `claude-sonnet-4-5-20250929_maxiter_500_N_v0.62.0-no-hint` |
| Sonnet 4.5 SDK | `claude-sonnet-4.5_new_v2_4runs` | `claude-sonnet-4-5-20250929_sdk_bde715c_maxiter_100` |
| GPT-5 | `gpt-5_4runs` | `gpt-5-2025-08-07_maxiter_100_N_v0.62.0-no-hint` |
| GPT-5.2 | `gpt_5.2_4runs` | `gpt-5.2_maxiter_500_N_v0.62.0-no-hint` |
| Gemini 3 Pro | `gemini-3-pro-preview_4runs` | `gemini-3-pro-preview_maxiter_500_N_v0.62.0-no-hint` |
| Kimi K2 | `kimi-k2_4runs` | `kimi-k2-0905_maxiter_500_N_v1.1.0-no-hint` |
| Qwen3 Coder | `qwen3-coder-480b-a35b-instruct-4runs` | `Qwen3-Coder-480B-A35B-Instruct-FP8_maxiter_500_N_v0.48.0-no-hint-main-2025-07-07-ctx256k` |

Run-name suffixes such as `juan-inst`, `rerank` and `ctx256k` are not explained in any archive's metadata. They are recorded as labels. Nothing in the data shows a run that is not a single trajectory, apart from what item 5 records.

---

## Acquisition

The first archive, GPT-5, was downloaded, listed, and read by hand. The extractor was written against it and reproduced its published resolve counts. The other eight were then acquired with `restart.acquire`, which takes the file list from Hugging Face's own listing of the dataset (`archives/hf_tree.json`). All nine were on disk by then, so all were extracted from local copies.

The `_mini` archives hold one completion-log file per instance and none of the three files a run's record lives in. They establish nothing and were not used.

## Extraction

Eight archives extracted; the Sonnet 4.5 SDK archive did not. Its runs sit in a different layout (`<config>_run1`, not `<config>-run_1`, under `princeton-nlp__SWE-bench_Verified-test/`) with a different record schema. Its settings were read directly from its run-1 metadata and output (item 3). Because it is excluded, no extractor was written for it.

The extractor reads three files per run. It also reads each instance's evaluation folder, to classify evaluation errors, and the timestamp and cost of every per-call completion log, as a second record of the calls. Every input to the terminal-state classifier is stored in the execution table, so a changed rule is re-applied to all configurations without the archives (`python -m restart.extract --reclassify`). Three such changes were made during the audit: the classification of evaluation errors, of provider refusals, and of relayed provider errors (item 5).

---

## Item 1. Telemetry sufficiency

The run record of every extracted configuration carries, per call, token counts by class, the call's position and the harness's logged cost. The exception is Qwen3 Coder, which logs no cost because it ran on a self-hosted server; its cost is reconstructed from tokens (item 9). The full scan of required fields on every call is in `configurations.csv` (`prefix_fields_missing`).

The per-call completion logs give an independent check. For every execution that has them, the logs of the final try are compared with the run's recorded calls and cost. In every extracted configuration, every execution with logs matches exactly: the final try's logs cost what the run records, call for call. In Sonnet 4.5, six executions include a log with no cost field; the comparison is made on the final try's own logs, and those six match too. The full scan finds no required field missing on more than one percent of calls, except Qwen3 Coder's cost and call times, which it does not log.

Criterion met for every extracted configuration. The full archive was needed in every case.

## Item 2. Harness version and date

| Name | OpenHands | Agent | First and last call (UTC) |
|---|---|---|---|
| Sonnet 3.7 | 0.31.0 | CodeActAgent | 2025-04-08 22:08 to 2025-04-09 21:55 |
| Sonnet 4 | 0.40.0 | CodeActAgent | 2025-06-02 18:44 to 2025-06-03 09:10 |
| Qwen3 Coder | 0.48.0 | CodeActAgent | not logged; its run name carries the date 7 July 2025 |
| Sonnet 4.5 | 0.62.0 | CodeActAgent | 2025-12-19 22:16 to 2025-12-23 18:52 |
| GPT-5 | 0.62.0 (974bcdfd) | CodeActAgent | 2025-12-31 04:29 to 2026-01-01 19:33 |
| Kimi K2 | 1.1.0 | CodeActAgent | 2026-01-04 05:24 to 2026-01-05 13:13 |
| Gemini 3 Pro | 0.62.0 | CodeActAgent | 2026-01-18 04:49 to 2026-01-19 04:12 |
| GPT-5.2 | 0.62.0 | CodeActAgent | 2026-01-21 01:53 to 2026-01-26 20:49 |
| Sonnet 4.5 SDK | SDK bde715c | SDK agent with critic | not extracted |

The harness versions span 0.31.0 to 1.1.0, a covariate reported with every table. Kimi's 1.1.0 runs the same CodeActAgent and writes the same record format as the 0.x versions. Kimi's runs 1 to 3 ran concurrently, in separate sandboxes.

## Item 3. The Sonnet 4.5 duplicate

The two Sonnet 4.5 archives are not a re-run of one configuration.

**Sonnet 4.5** is CodeActAgent under OpenHands 0.62.0, cap 500, temperature 0.

**Sonnet 4.5 SDK** is a different agent and harness: OpenHands' software-agent SDK at commit bde715c, cap 100, reasoning effort high. It also runs a critic (`AgentFinishedCritic`, mode `finish_and_message`) that allows up to three attempts per task and keeps the one it accepts. In run 1, 494 records are present; 487 are first attempts, 2 second, and 5 third.

Under item 3's rule the two are different configurations. The SDK archive is excluded under condition 1 (a different agent). Its critic loop is also a termination rule of its own. **Sonnet 4.5** is therefore the Sonnet 4.5 configuration, and the later-date tie-break is not needed.

## Item 4. Replicate construction

Each run was launched separately, as item 2's call windows show. No task in any configuration has four identical runs, and item 8 gives the divergence evidence.

The criterion, as revised before any result, is exchangeability, not independence: nothing but chance distinguishes one run of a task from another. That is what enumerating attempt orderings needs. A configuration that repeats a trajectory, as Gemini sometimes does, is recorded as behaving that way. Crossing configurations in the cascade estimator needs independence between configurations, which separate runs provide.

Harness re-runs are recorded under item 5. Whether a re-run's final try started fresh is checked per configuration by its first prompt, which should be the ordinary size, not one carrying the crashed try's context. In every configuration it does: the median first prompt of re-run executions is between 0.99 and 1.03 times that of all others (`rerun_first_prompt_ratio`).

## Item 5. Terminal-state classification

How an attempt stopped and whether it resolved are recorded separately, because the harness evaluates whatever diff exists when it stops. An attempt enters the pool when it is a draw from the configuration's behaviour and its outcome was observed.

| Name | Resolved | Unresolved | Empty | Did not apply | No verdict | Iteration limit | Loop detector | Refusal | Infrastructure | Other | Usable | Resolved, usable |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Sonnet 4 | 1,373 | 621 | 0 | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 1,998 | 1,373 |
| Sonnet 4.5 | 1,282 | 705 | 8 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 2,000 | 1,282 |
| GPT-5 | 1,174 | 691 | 24 | 2 | 2 | 10 | 1 | 93 | 3 | 0 | 1,995 | 1,194 |
| GPT-5.2 | 1,246 | 630 | 11 | 4 | 5 | 0 | 0 | 0 | 104 | 0 | 1,891 | 1,246 |
| Gemini 3 Pro | 1,132 | 557 | 9 | 5 | 4 | 0 | 190 | 0 | 103 | 0 | 1,893 | 1,161 |
| Kimi K2 | 1,077 | 807 | 3 | 6 | 3 | 5 | 4 | 0 | 93 | 2 | 1,904 | 1,080 |
| Qwen3 Coder | 1,322 | 672 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 2,000 | 1,322 |
| *Sonnet 3.7 (excluded)* | 1,192 | 768 | 0 | 5 | 4 | 31 | 0 | 0 | 0 | 0 | 1,996 | 1,201 |

The first ten count columns are terminal states. "Resolved, usable" includes attempts stopped by the harness whose diff the report accepted: 2 at the iteration limit for GPT-5, 18 GPT-5 refusals, 29 Gemini and 1 Kimi loop-detector stops, 2 Kimi errors, and 9 Sonnet 3.7 limit stops. Sonnet 4 has 1,999 executions: `sympy__sympy-13031` is missing from one run. No execution in any configuration is left unclassified.

The rules adopted:

- **Infrastructure errors are excluded.** These are outages (`SERVICE_UNAVAILABLE`), rate limits, the harness's eight-hour timeout, and an upstream error OpenRouter relayed without detail ("Provider returned error": 16 Gemini attempts, 2 of which had resolved). None of these is the configuration's response to the attempt.
- **Provider refusals are retained**, as a stop scored by the report. A refusal is the provider's response to the attempt's content; the operator pays for the attempt, and the harness scores what it produced. 18 of GPT-5's 93 refusals had already produced a passing patch. Only GPT-5 has refusals. Excluding them is the prespecified sensitivity.
- **Evaluation errors are split by the evaluation log.**
  - A patch that did not apply is an observed failure, and is retained: GPT-5's `psf__requests-1142`, runs 2 and 3.
  - An evaluation that returned no verdict is excluded, with counting it unresolved as a sensitivity: GPT-5's `scikit-learn-14710`, runs 2 and 3, whose test suite timed out after an hour.
  - A timeout could be the patch's own doing; the logs cannot say, which is what the sensitivity covers.
- **Errors caused by the model's own output are retained.** Kimi's two "other" errors are the sandbox rejecting a file path containing tool-call markup (`proper_test_case.py</parameter…`), which the model's malformed call produced. Both were scored resolved.
- **Harness re-runs.** When the harness crashed on an instance it re-ran it and kept only the final try. The discarded tries appear only in the completion logs, as the earlier logs in time.
  - **Included configurations:** every discarded try ended before the cap, so they are crashes, bar one Sonnet 4 try that reached exactly 500. Re-run executions, and the discarded tries' spend where cost is logged: GPT-5 12 ($7), Sonnet 4.5 26 ($26), Gemini 22 ($106), Kimi 38 ($54), Sonnet 4 86 ($90), Qwen3 Coder 101 (not logged), GPT-5.2 108 ($160). The final try is used; the discarded tries have no verdict and stay out of the pool. Dropping re-run executions is a sensitivity.
  - **Sonnet 3.7 is different.** At least 140 of its re-runs replaced one or more tries that ran to the 100-call cap: 96 with one such try, 41 with two, and 3 with three. The discarded tries cost $649, against $1,728 recorded. The gap between a discarded try and its replacement ran from 1 minute to 2 hours (median 18 minutes). That harness treated reaching the cap as an error and restarted the task, which is a termination rule of its own (condition 2; see the exclusion decision below).

## Item 6. Checksums

The SHA-256 of all nine archives matches the value Hugging Face records for each file (its LFS object id), and all nine are in `archives/SHA256SUMS`, including the Sonnet 4.5 SDK archive, which could not be extracted.

Hugging Face's metadata for the release records no license. The derived tables are therefore not committed: the repository holds the extraction code and the checksums, and the tables are rebuilt locally by `restart.acquire` (LICENSE-NOTE.md).

## Item 7. The harness's own stopping rules

- **Iteration maximum.** 100 for GPT-5 and Sonnet 3.7, 500 for the other six extracted configurations, 100 for the Sonnet 4.5 SDK.
- **Budget cap.** None, in any configuration.
- **Loop detector.** Active throughout. It fired in Gemini (190 attempts), Kimi (4) and GPT-5 (1).
- **Iteration limit.** GPT-5 reached it 10 times, Kimi 5 and Sonnet 3.7 31. Kimi's five report iteration 500 with fewer than 500 calls recorded. GPT-5's `sphinx-doc__sphinx-11445`, run 1, reached 100 calls with no limit error, and is counted at the limit by call count.

The protocol assumed a cap of 100 for every configuration and made any other value an exclusion. That premise was wrong, and the rule was revised before any result: the cap is a configuration attribute. Each configuration is evaluated within its own cap, with a common 100-call horizon as a sensitivity. Between 2 and 21 percent of the resolved attempts of the 500-cap configurations need more than 100 calls: Sonnet 4.5 21%, Gemini 17%, Kimi 14%, Sonnet 4 10%, Qwen 7%, GPT-5.2 2%.

## Item 8. Source of replicate variation

| Name | Temperature configured | Applied | Median first divergence (action) | Tasks diverging at the first action | Tasks with identical runs |
|---|---|---|---|---|---|
| GPT-5 | 0.0 | model default | 0 | 326 | 0 |
| GPT-5.2 | 0.0 | model default | 0 | 473 | 0 |
| Sonnet 4 | 1.0 | 1.0 | 1 | 204 | 0 |
| Qwen3 Coder | 1.0 | 1.0 | 1 | 172 | 0 |
| Sonnet 4.5 | 0.0 | 0.0 | 1 | 48 | 0 |
| Kimi K2 | 0.0 | 0.0 | 2 | 108 | 0 |
| Gemini 3 Pro | 0.0 | 0.0 | 2 | 141 | 4 |
| *Sonnet 3.7 (excluded)* | 1.0 | 1.0 | 0 | 477 | 0 |

The applied temperature was established from provider documentation, not from the configuration:
- **GPT-5** accepts only its default temperature, and the client, with `drop_params` set, drops the parameter.
- **GPT-5.2** accepts a temperature only with reasoning off, and reasoning was on.
- **Sonnet 4** runs at 1 because extended thinking requires it.

No seed is set anywhere. Actions are compared by type and defining arguments, not by the model's wording. The divergence pattern broadly agrees with the applied temperatures:
- GPT-5 and GPT-5.2 part at the first action (index 0 in the table).
- Sonnet 4 and Qwen, at temperature 1, part at the second, with a third or more of tasks parting at the first.
- Of the configurations at temperature 0, Sonnet 4.5 parts at the second action, with a tenth of tasks parting at the first. Kimi and Gemini part at the third, though a fifth to over a quarter of their tasks part at the first.

Gemini alone repeats itself. On four tasks two or three runs take the same 41 to 99 actions: `scikit-learn-25931` and `matplotlib-26208` in three runs each, `django-14007` and `django-11477` in two. This is recorded as behaviour (item 4).

## Item 9. Cost reconstruction inputs

Each configuration is priced at its model developer's published list price on the run's first day, over the token classes the developer bills, with any long-context tier. The logged cost is not taken as the price. It shows what the logged prompt count includes, and where the harness computed cost correctly the schedule reproduces it on every call. The schedules, their sources and the variants below are in `src/restart/pricing.py`; `python -m restart.pricing --validate data/derived` prices every call and compares it with the logged cost.

| Name | Endpoint | Priced at | Input | Cache read | Cache write | Output | Prompt count includes | Logged cost against the schedule |
|---|---|---|---|---|---|---|---|---|
| GPT-5 | OpenAI API | 2025-12-31 | 1.25 | 0.125 | none | 10 | cache reads | reproduced on every call |
| GPT-5.2 | OpenRouter | 2026-01-21 | 1.75 | 0.175 | none | 14 | cache reads | cache reads charged at the input price |
| Gemini 3 Pro | OpenRouter | 2026-01-18 | 2 / 4 | 0.20 / 0.40 | none | 12 / 18 | cache reads | cache reads at the input price; no tier |
| Kimi K2 | OpenRouter | 2026-01-04 | 0.60 | 0.15 | none | 2.50 | cache reads | follows no fixed schedule |
| Sonnet 4 | All Hands evaluation proxy | 2025-06-02 | 3 | 0.30 | 3.75 | 15 | cache reads, not writes | reproduced on every call |
| Sonnet 4.5 | Anthropic API | 2025-12-19 | 3 | 0.30 | 3.75 | 15 | cache reads and writes | reproduced on every call |
| Qwen3 Coder | self-hosted | 2025-07-22 (release) | 1 / 1.8 / 3 | 0.40 / 0.72 / 1.20 | none | 5 / 9 / 15 | cache reads | none logged; imputed |
| *Sonnet 3.7 (excluded)* | All Hands app proxy | 2025-04-08 | 3 | 0.30 | 3.75 | 15 | cache reads and writes | cache writes charged twice |

Dollars per million tokens. Gemini's two values are for prompts up to 200k tokens and above; 62 of its calls are above. Qwen's three are for prompts up to 32k, 128k and 256k tokens, holding 80,289, 57,661 and 381 of its calls; none exceeds 256k, where a fourth tier would apply. Every tier is set by the call's total input, cached tokens included.

Sources. GPT-5: OpenAI's price for `gpt-5-2025-08-07`, as Bai et al. state it. GPT-5.2: OpenAI's model page and OpenRouter's listing, which agree. Gemini: Google's launch post of 18 November 2025 for the price up to 200k tokens. The model was shut down on 9 March 2026, and the pricing page now lists its successor at the same schedule. Kimi: Moonshot's price for `kimi-k2-0905-preview`, as quoted from its pricing page on 3 December 2025 (LiteLLM issue 17417). Anthropic: the published price, with five-minute cache writes at 1.25 times input. For GPT-5.2, Gemini and Kimi, LiteLLM's price table, which the harness computes cost with, lists exactly these schedules at commits dated the day before each run. The pricing pages as archived at the run dates could not be reached from the audit environment. The sources above are dated or agree with the harness's table at the run date.

**Reproduced.** GPT-5 (72,187 calls), Sonnet 4 (139,138) and Sonnet 4.5 (177,257): the published schedule reproduces the logged cost on every call. The two Anthropic configurations log the prompt count differently. Sonnet 4's excludes cache writes, and read as including them, 139,097 of its calls would have negative uncached input. Sonnet 4.5's includes them. The reading is set per configuration.

**Harness accounting.** In GPT-5.2 (91,826 calls) and Gemini (143,815), the logged cost is the published input and output price with cache reads charged as uncached input. For Gemini the over-200k tier is also not applied, on 62 calls. A variant of each schedule with those changes reproduces every call. LiteLLM's price table at the run dates lists the discounted cache price and the tier, so the difference lies in how cost was computed from the usage, not in the prices used. Both configurations are priced at the published schedule. Their logged cost is 3.4 and 4.3 times what that schedule charges.

**Kimi.** The logged cost follows no fixed schedule. Moonshot's price reproduces 62,620 of the 152,054 calls exactly (41 percent). The rest are charged between two-thirds of it and three times it (the 5th and 95th percentiles of the per-call ratio), and the total is 19 percent above it. That is consistent with a router sending some calls to providers at Moonshot's price and others to providers that charge differently. Kimi is priced at Moonshot's price.

**Qwen3 Coder, imputed.** It ran on a self-hosted server and logs no cost and no call times, so there is no bill and no run date. It is priced at release, 22 July 2025, at the developer's standard price for the model's hosted API, `qwen3-coder-plus`, which is the API the release post names. That price is tiered by prompt length, with cache hits at 40 percent of input. Alibaba cut cache hits to 10 percent of input for a month from 24 July 2025, and its notice of that discount is the source for the standard price, which is the one used. The prompt count is read as including cache reads, as OpenAI-compatible servers report it, and under that reading no call has negative uncached input. The prespecified sensitivity is the lowest price OpenRouter lists for the same weights: Google Vertex at $0.22 input and $1.80 output, with no cache price, so cache reads at the input price. Its 138,331 calls cost $3,044 under the schedule and $1,027 under the sensitivity.

**Sonnet 3.7, excluded.** Its prompt count includes cache writes, and its harness also charged them as cache writes, so written tokens were charged once at the input price and again at the write price. A variant that reads the prompt count as excluding writes reproduces all 88,439 calls. It is recorded because the $649 and $1,728 in item 5 are logged cost; at the published schedule the recorded attempts cost $1,475.

Spend over all calls, logged and at the schedule:

| Name | Calls | Logged | At the schedule | Logged ÷ schedule |
|---|---|---|---|---|
| GPT-5 | 72,187 | $829.91 | $829.91 | 1.00 |
| Sonnet 4 | 139,138 | $2,566.41 | $2,566.41 | 1.00 |
| Sonnet 4.5 | 177,257 | $3,680.92 | $3,680.92 | 1.00 |
| GPT-5.2 | 91,826 | $5,072.48 | $1,511.31 | 3.36 |
| Gemini 3 Pro | 143,815 | $8,970.20 | $2,067.08 | 4.34 |
| Kimi K2 | 152,054 | $2,423.38 | $2,036.57 | 1.19 |
| Qwen3 Coder | 138,331 | none | $3,044.38, imputed ($1,027.20 under the sensitivity) | |
| *Sonnet 3.7 (excluded)* | 88,439 | $1,728.21 | $1,475.00 | 1.17 |

**Reasoning tokens** are billed as output by every developer here, and wherever reported they sit within the logged output count: 77 percent of output for GPT-5, 63 for GPT-5.2 and 12 for Gemini. Kimi reports the field at zero. The Anthropic configurations do not report thinking separately, but their output count includes it: Sonnet 4 ran with extended thinking, and its logged cost is reproduced from that count. Qwen3 Coder's instruct model does not think. No configuration's cost is therefore a lower bound.

## Item 10. Iteration-to-call mapping

One LLM call per agent step, and no history condensation in any configuration. Where a model issues parallel tool calls, one call yields several actions: GPT-5.2 in 449 executions, Gemini in 51, Sonnet 4 in 15. Retries of a failed API request are not logged as calls. Crashed tries the harness re-ran appear only in the completion logs (item 5). The decision grid is in calls.

---

## Exclusion decision

Made after items 1 to 8 and 10, from the four conditions only. Item 9 bears on no condition, since cost is reconstructible from tokens wherever it is not logged.

| Name | 1. Same agent | 2. Termination rule | 3. Outcome labels | 4. Telemetry | Decision |
|---|---|---|---|---|---|
| Sonnet 4 | pass | pass | pass | pass | in |
| Sonnet 4.5 | pass | pass | pass | pass | in |
| GPT-5 | pass | pass | pass | pass | in |
| GPT-5.2 | pass | pass | pass | pass | in |
| Gemini 3 Pro | pass | pass | pass | pass | in |
| Kimi K2 | pass | pass | pass | pass | in |
| Qwen3 Coder | pass | pass | pass | pass (cost from tokens) | in |
| Sonnet 3.7 | pass | **fail**: attempts reaching the cap were replaced by fresh ones | pass | pass | **out** |
| Sonnet 4.5 SDK | **fail**: a different agent and harness | **fail**: a critic retries up to three times | not assessed | not assessed | **out** |

Seven configurations are included: 13,999 executions, of which 13,681 are in the attempt pool, and $23,543 of logged spend across the six that log cost, which is $12,692 at the published schedules (item 9). Sonnet 4 has one execution with a discarded try at its 500-call cap. A single instance does not make its recorded attempts a filtered sample, so it is recorded here and falls under the sensitivity that drops re-run executions.

## Regression oracles

**Oracle A**, GPT-5 against an earlier extraction. That extraction built its rows from the per-call completion logs and classified how attempts finished from the inference logs; this one reads the run record. The count that does not depend on classification reproduces exactly: 1,998 executions have completion logs. The earlier extraction's partition, 1,869 executions with an outcome and no harness stop, matches this extraction's clean stops in size (1,869). The two differ by one resolved execution (1,175 against 1,174) and in mean cost ($0.4278 against $0.4249 from the completion logs, $0.4226 from the run record), because the finish classification comes from a different source. Resolving that execution by execution would mean re-reading the inference logs. Since nothing in this study depends on the earlier figures, the difference is recorded here, not pursued.

**Oracle B**, against what Bai et al. state in numbers: **passed**. Token consumption: mean tokens per execution, prompt plus output, are 0.99 million for GPT-5, 4.13 million for Sonnet 4.5 and 3.18 million for Kimi. Sonnet 4.5 and Kimi therefore consume 3.14 and 2.19 million more than GPT-5, over the 1.5 million stated. Counting cache tokens separately gives 6.34 and 3.32 million more. Price schedule: the GPT-5 schedule is Appendix B.2's $1.25, $0.125 and $10, and it reproduces every call. Claude cache writes are priced at the five-minute rate, $3.75: that is the rate that reproduces every Sonnet 4 and Sonnet 4.5 call.

**Oracle C**, the fixed-cap replay: runs at the start of the analysis phase.
