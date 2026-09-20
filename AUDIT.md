# Data audit protocol

For *Restart Economics for AI Agents*. Runs against the nine-archive release accompanying Bai et al. before the analysis plan in PLAN.md is frozen and before any policy result is computed. Its purpose is to establish the facts about how the trajectories were generated on which the paper's claims depend: whether the four runs per task are exchangeable draws, what each configuration actually was, which executions belong in the attempt pool, and whether each archive is usable at all. The inclusion decision is made from technical criteria fixed in advance, before any result exists. Every item produces a written record whether it passes or fails. The audit's outputs are the inputs to plan freeze; the plan does not change for any other reason.

---

## 0. Rules

**Sequence.** Acquire → extract → audit items 1 to 9 → exclusion decision → regression oracles → freeze record. No step is skipped, no step is reordered, and the exclusion decision is made before the oracles are run so that a configuration cannot be dropped because its numbers look wrong.

**What the audit may compute.** Anything needed to establish integrity and comparability: counts, terminal states, resolve rates, cost and token totals, iteration and call counts, divergence points, field presence. **What it may not compute:** any quantity indexed by a cutoff, an attempt budget *K*, an outside-option rate, or a verification cost *v*. That is the line between an audit output and a policy result. If a check seems to need a policy quantity, the check is wrong.

**Recording.** Two artifacts. `audit_record.md`, one section per item, written as the item is done, including failures and surprises. `configurations.csv`, one row per archive, with the fields listed in Section 11, built by `python -m restart.audit` from the extraction and from `configurations_notes.json`, which holds only what no table can: what each endpoint was, the applied temperature, and each exclusion and its reason. Both are frozen with the plan and shipped with the paper.

**Provenance.** Nothing is modified in the archives. All derived tables carry the archive checksum they were built from.

---

## 1. Acquisition

Download all fourteen files from `loong0814/openhands_trajectories` on Hugging Face. Five configurations have `_mini` archives; download those first and inspect one before pulling the full archives, but the decision to include a configuration is not contingent on the download's convenience.

| Archive | Size | Mini |
|---|---|---|
| claude-sonnet-3.7_4runs | 3.4 GB | 65.2 MB |
| claude-sonnet-4_4runs | 4.48 GB | 80.3 MB |
| claude-sonnet-4.5_4runs | 6.44 GB | 98.3 MB |
| claude-sonnet-4.5_new_v2_4runs | 2.46 GB | none |
| gpt-5_4runs | 2.51 GB | 78.5 MB |
| gpt_5.2_4runs | 2.91 GB | none |
| gemini-3-pro-preview_4runs | 4.67 GB | none |
| kimi-k2_4runs | 10 GB | none |
| qwen3-coder-480b-a35b-instruct-4runs | 4.6 GB | 83.9 MB |

Sizes as read from the dataset page on 14 September 2026; verify before scripting.

The first full archive is stored and inspected by hand (manifest, file layout, one execution record read in full) so that the extractor is written against the real schema. Once the extractor reproduces the published resolve counts for that archive, every archive is acquired by `restart.acquire`, which reads Hugging Face's own listing of the dataset (saved as `archives/hf_tree.json`), so no file name is typed by hand, and takes every full archive. An archive already on disk is extracted from there; any other is streamed from Hugging Face through the extractor, with a temporary copy written and hashed on the way and deleted once the extraction succeeds and the hash matches, so no archive is kept unless something fails. The extractor reads only what it needs from the stream (three files per run, each instance's evaluation log, and the cost field of each per-call completion log). Each archive's tables and extraction log go to their own folder, `data/derived/<archive>/`.

```bash
python -m restart.acquire --local ~/Downloads/archives --out data/derived
```

Every archive's SHA-256 is compared with the one Hugging Face records for the file, which is the LFS object id and is the SHA-256 of the content, and `archives/SHA256SUMS` is written from the verified values. A download that fails, a tar read failure, or a checksum that differs is an integrity failure, recorded before anything else is done with that archive; the temporary copy is then kept, so the extraction can be rerun locally.

---

## 2. Extraction

Run the reduction in `src/restart/extract.py` against the first stored archive, then against every archive that passes item 1 below.

```bash
python -m restart.extract ~/Downloads/archives/gpt-5_4runs.tar.gz --out data/derived/gpt-5_4runs/
```

When a rule is changed after extraction, it is re-applied to the stored tables without the archives: `python -m restart.extract --reclassify --out data/derived/`.

Each provider field mapping added while generalizing the extractor is recorded. The extraction produces, per configuration: an execution table (one row per task × run), a prefix table (one row per LLM call), and an audit census. None carries trajectory text.

**Expected OpenHands output fields, to confirm on first contact:** per instance, `instance_id`; `metadata` with `agent_class`, `model_name`, `max_iterations`, `llm_config` (including `temperature`), a version or git commit, and a start time; `metrics` with accumulated cost and per-call token usage; `test_result` with the resolve report; an `error` string when the run terminated abnormally; and `history`, the event list, from which the terminal action and the iteration count are read.

---

## 3. The nine audit items

Each item lists what to check, how, the criterion, what to record, and what a failure means. "Exclude" means the configuration fails one of the four exclusion conditions of Section 10. "Handle" means the configuration stays in and the plan records a rule for it.

### Item 1. Telemetry sufficiency

**Check.** Whether the archive carries, per LLM call: input tokens, output tokens, cache classes where the provider has them, cost or the inputs to compute it, and the call's position in the trajectory.

**How.** Field presence on a sample of 20 executions per configuration, then a full scan for missing values.

**Criterion.** Every field the physical data layer requires is present or reconstructible for at least 99 percent of calls; any missing field is named.

**Record.** Field map per configuration; missing-field rate; whether `_mini` suffices or the full archive was needed.

**On failure.** Exclusion condition 4 if a required field is absent and not reconstructible. A field present in the full archive but not the mini is not a failure; it means the full archive is used.

### Item 2. Harness version and date

**Check.** OpenHands version or commit, agent class, and run date range per configuration.

**How.** From `metadata` and from the execution-ID string, which in this release encodes model snapshot, iteration maximum, harness version and run index.

**Criterion.** Record only. A version difference is a covariate, not an exclusion reason. A different *agent class* is exclusion condition 1.

**Record.** Version, commit if present, agent class, earliest and latest run timestamps.

### Item 3. The Sonnet 4.5 duplicate

**Check.** What distinguishes `claude-sonnet-4.5_4runs` from `claude-sonnet-4.5_new_v2_4runs`: model snapshot string, harness version, date, iteration maximum, and whether the same tasks are covered.

**How.** Items 2 and 7 run on both; a diff of the metadata.

**Criterion.** If they differ in harness version or model snapshot, they are two configurations and both are eligible; the paper reports both and designates one as the Sonnet 4.5 row in the primary tables by a rule fixed here: the later run date, on the grounds that a re-run supersedes. If they are the same configuration re-run, one is chosen by the same rule and the other is held as a replication check, not pooled.

**Record.** The diff and the choice, with the reason.

### Item 4. Replicate construction

**Check.** How the four runs per task were produced: separately launched, fresh container per run, no shared workspace, no shared cache that could carry state between runs of the same task.

**How.** From `metadata` and the launch structure visible in the archive layout; from the description in Bai et al.; and from item 8's divergence diagnostic.

**Criterion.** Runs share no seeded environment state and are exchangeable: nothing but chance distinguishes one run of a task from another. This is what licenses enumerating attempt orderings. Crossing one configuration's runs with another's in the cascade estimator additionally requires independence between configurations, which separate runs provide. A configuration that repeats a trajectory is recorded as behaving that way; repetition is not a failure of this criterion, because a retry of that configuration would meet it too.

**Record.** The evidence for independence; anything that argues against it.

**On failure.** Handle: if runs are not exchangeable, for instance if later runs of a task systematically differ from earlier ones, the enumeration is not unbiased and the cascade estimator is not licensed; PLAN.md would have to be revised, which is the one outcome of this audit that reopens the design. Everything in item 8 is designed to detect this early.

### Item 5. Terminal-state classification

**Check.** Every execution assigned to exactly one terminal state.

| Terminal state | Evidence |
|---|---|
| Resolved | Instance in the run report's `resolved_ids`; attempt stopped on its own |
| Unresolved | Instance in `unresolved_ids`; attempt stopped on its own |
| Empty patch | Instance in `empty_patch_ids` |
| Patch did not apply | Instance in `error_ids`, and its evaluation log in `eval_outputs/<instance>/run_instance.log` records the apply failure |
| Evaluation error | Instance in `error_ids` with no apply failure in its log: the evaluation harness returned no verdict |
| Unknown | Instance absent from every list of the run report |
| Iteration limit | `error` names the iteration maximum, or the call count equals it |
| Loop detector | `error` names the stuck-in-loop condition |
| Budget cap | `error` names the budget; or accumulated cost at the cap with no finish |
| Provider refusal | `error` names a content-policy refusal |
| Infrastructure error | Any other provider or runtime `error`: service unavailability, rate limits, connection failures, timeouts |

**How.** A classifier over `error`, the run report's id lists, and, for instances in `error_ids`, the evaluation log, applied to every execution, with the ten most common `error` strings per configuration read by a person and mapped by hand. Only the report at the top of each run directory is read as the report; the per-instance folders under `eval_outputs/` are read as evidence. Every input to the classifier is stored in the execution table, so a rule can be re-applied to a streamed configuration without its archive.

**Criterion.** Every execution classified; no residual "unknown" above 0.5 percent per configuration.

**Record.** Count by terminal state per configuration, and resolved attempts by terminal state. **Rule fixed here:** the terminal state records how an attempt stopped; whether it resolved is read from the run report for every retained attempt, including attempts stopped by the harness, because the harness evaluates whatever diff exists when it stops. An attempt enters the pool when it is a draw from the configuration's behaviour and its outcome was observed. Infrastructure errors (outages, rate limits, runtime timeouts) are excluded: they are not the configuration's response to the attempt. Provider refusals are retained as a stop like the harness's own and scored by the run report: a refusal is the provider's response to the attempt's content, the operator pays for the attempt, and the harness scores whatever it produced. Excluding refusals as well is reported as a sensitivity. Iteration-limit, loop-detector and budget-cap terminations are retained at the harness's own stopping rule and reported as their own categories. Empty patches and patches that did not apply are retained as unresolved: the agent's output was absent or invalid. An evaluation error with no apply failure, and an instance absent from the report, are excluded: the attempt ran, but the verifier returned no verdict, and counting a missing verdict as a failure would charge the agent for the verifier. Counting them as unresolved instead is reported as a sensitivity. When the harness crashed on an instance and re-ran it, the run's record keeps only the final try; earlier tries survive only as per-call completion logs. The final try is identified as the last logs in time whose costs sum to the run's recorded cost, and is used. Earlier tries have no verdict and stay out of the pool, like other infrastructure failures; their count and spend are reported per configuration, and dropping re-run executions altogether is reported as a sensitivity.

### Item 6. Checksums

**Check.** SHA-256 of every archive, recorded in `SHA256SUMS` and in `audit_record.md`.

**Criterion.** Record only.

### Item 7. The harness's own stopping rules

**Check.** For each configuration: whether the stuck-in-loop detector was active; whether a per-task budget cap was configured and at what value; the iteration maximum.

**How.** `metadata` (`max_iterations`, `max_budget_per_task` if present), the `llm_config`, and the terminal-state counts from item 5, which show whether either rule ever fired.

**Criterion.** Record. The iteration maximum is a configuration attribute, not an exclusion: each configuration is evaluated within its own cap, with a common 100-call horizon as a sensitivity (PLAN Section 10). Loop detector and budget cap are record-and-handle. A termination rule other than these is exclusion condition 2.

**Record.** The three settings; the number of executions each rule terminated; for a budget cap, the cost distribution of terminated runs.

**On finding a binding cap.** Handle: if any configuration's runs were terminated by a budget cap, every cutoff analysis for that configuration is conditioned on it and the configuration is flagged in every table, because a cost cutoff measured on top of an existing cost cutoff is a different quantity. If the cap bound on some configurations and not others, the cross-configuration comparison in Q1 is reported with and without the affected configurations.

### Item 8. Source of replicate variation

**Check.** Sampling settings per configuration, and how early the four runs of a task diverge.

**How.** `llm_config.temperature` and any seed from `metadata`. For the divergence diagnostic, per task and configuration, over all tasks and every run whatever its outcome: the first agent action at which the four runs' action sequences differ, read from `history`. An action is compared by its type and the arguments that define it (the command run, the file and text edited); the model's free-text reasoning is left out, so runs that do the same thing for differently worded reasons agree. The sequences are stored as short signatures in `actions_<config>.csv`, so the diagnostic can be recomputed under another definition without the archive.

**Criterion.** Record. The applied temperature is recorded, not only the configured one: a provider may accept only its default and the client drop the parameter, which is established from provider documentation for each configuration. If the applied temperature is zero, variation is serving-side nondeterminism and the paper says so; otherwise it is sampling. If the median divergence iteration is late, or if any task's four runs are identical, item 4's independence claim is in question.

**Record.** Temperature and seed; the distribution of divergence iteration per configuration; the count of tasks with any two identical runs.

### Item 9. Cost reconstruction inputs

**Check.** Whether logged usage includes reasoning tokens for configurations that bill them as hidden output; which endpoint served each model; which cache classes the logged prompt count includes; the price schedule, with cache classes and any long-context tier, at the run date.

**How.** Compare logged output tokens against any provider-reported total; read the endpoint from `llm_config` or the model string. The schedule is the model developer's published list price in force on the run's first day, taken from the developer's pricing pages or, where a page has since changed, from dated sources that quote it. What the logged prompt count includes is read from the logged cost: fit the per-token prices that reproduce it under each reading (`python -m restart.pricing --implied`), then price every call under the schedule and compare (`--validate`). Where the harness computed cost differently from the schedule, a variant of the schedule that reproduces the logged cost on every call is recorded, to show where the difference lies.

**Criterion.** Every configuration has a complete schedule at a stated date, with cache classes and tiers handled; on every call where cost is logged, either the schedule reproduces it or a stated variant does, or the logged cost is shown to follow no fixed schedule; reasoning-token treatment stated per configuration.

Revised before any result. The protocol priced the endpoint. A router's per-call price can depend on which provider served the call, so the developer's price is used throughout; for configurations served by the developer the two are the same. A self-hosted configuration has no endpoint price and may have no run date. It is priced at the developer's price for the model's hosted API when the model was released, with the lowest third-party price for the same weights as a prespecified sensitivity, and its dollar figures are marked as imputed.

**Record.** Endpoint, schedule, source, date, what the prompt count includes, the result of the call-by-call comparison, reasoning-token treatment.

**On failure.** Handle: if reasoning tokens are unlogged for a configuration, its dollar costs are a lower bound and are marked; its iteration-denominated results are unaffected, which is one reason iterations are the primary cutoff unit.

### Item 10, from the cutoff unit. Iteration-to-call mapping

**Check.** Per configuration, calls per iteration: the condenser's summarization calls and any logged retries.

**How.** From the prefix table: distribution of LLM calls per iteration; identification of condenser events if the history marks them.

**Criterion.** Record. The decision grid is in iterations regardless; this item establishes what "iteration" contains so that the prefix table indexes correctly. With one call per iteration and no condensation in any configuration, the grid is stated in calls, which is what the prefix table indexes.

**Record.** Mean and maximum calls per iteration; whether condenser events are identifiable; whether retries appear in the log.

---

## 10. Exclusion decision

Made after items 1 to 9, before the regression oracles, from these four conditions only:

| Condition | Source item | Meaning |
|---|---|---|
| 1. Different agent or scaffold | 2 | Not the same procedure; a version difference alone does not qualify |
| 2. Different termination rule | 7 | Attempts ended, or replaced, by a rule other than the agent's finish, the loop detector, a budget cap, or the iteration maximum, so that the recorded attempts are not the configuration's attempts as they ran; a different iteration maximum alone does not qualify |
| 3. Outcome labels absent or off-semantics | 5 | No resolve flag, or a flag not on the benchmark's resolve criterion |
| 4. Required telemetry missing and not reconstructible | 1 | A field the physical layer needs is absent |

Nine archives. The decision is recorded as a table: configuration, each condition pass or fail, in or out. A configuration that is in stays in.

---

## 11. `configurations.csv` fields

`config_id`, `archive`, `sha256`, `model_string`, `endpoint`, `agent_class`, `harness_version`, `run_date_start`, `run_date_end`, `max_iterations`, `budget_cap_usd`, `loop_detector_active`, `temperature`, `n_tasks`, `n_executions`, `n_resolved`, `n_finished_unresolved`, `n_iteration_limit`, `n_loop_detector`, `n_budget_cap`, `n_infrastructure`, `n_empty`, `median_divergence_iter`, `n_identical_pairs`, `calls_per_iter_mean`, `reasoning_tokens_logged`, `schedule_date`, `mini_sufficient`, `excluded`, `exclusion_condition`.

---

## 12. Regression oracles

Run after the exclusion decision. These are integrity checks and audit outputs; they are not policy results.

**Oracle A, the GPT-5 archive against a previously validated extraction.** An earlier extraction of this archive by the author yields 1,998 executions, of which 1,869 have an outcome label and no harness-limit termination, 1,175 of those resolved, at a mean cost of $0.4278 per execution. The new extraction must reproduce these counts from the same archive. A mismatch is a bug in the extraction and stops the audit until resolved. This is an internal integrity check, not a published result.

Revised after the oracle was run, and recorded as such. The earlier extraction classified how attempts finished from the inference logs, which this extraction does not read. Its resolved count and mean cost therefore rest on a classification the two do not share, and a difference in them is not by itself a bug. The check is the count that does not depend on classification, which must match. Differences in the rest are recorded with their source. No policy result depends on the oracle.

**Oracle B, against Bai et al.** Their paper reports its per-model results as charts, with no table of resolve rates or token consumption, so the oracle is what it states in numbers: that Kimi-K2 and Claude Sonnet 4.5 each consume, on average, over 1.5 million more tokens per task than GPT-5 (Section 4); and its GPT-5 price schedule (Appendix B.2: $1.25, $0.125 and $10 per million input, cached-input and output tokens), which must equal the schedule validated here, together with its statement that Claude cache writes are priced at the five-minute rate. A failure of either is investigated before anything else. Revised before the oracle was run, on finding that the per-configuration figures the original wording assumed are not published.

**Oracle C, the fixed-cap replay.** Constant-cutoff policy values computed for the GPT-5 configuration in earlier work are reproduced by the new evaluator once it exists. This oracle runs at the start of the analysis phase, not in the audit, because it involves a cutoff.

---

## 13. Freeze record

The audit closes by writing the following into Section 10 of PLAN.md, after which the plan is frozen and tagged:

- The configuration list with inclusions and exclusions, and the Sonnet 4.5 designation.
- The pricing rule and each configuration's schedule and date.
- The terminal-state rule as fixed in item 5.
- The harness stopping rules per configuration and any budget-cap conditioning.
- The iteration-to-call mapping.
- The source of replicate variation and the divergence summary.
- The reasoning-token treatment per configuration.
- Whether `_mini` sufficed, per configuration.

Anything the audit found that the plan did not anticipate is recorded under a heading of its own, with the handling rule adopted. That heading is expected to be non-empty.

---

## 14. Working protocol for stepping through

Each item is done in one sitting and its record written before the next begins. Where the archives are held locally, the following are enough to upload for each step, and none contains trajectory text:

- **Acquisition:** `SHA256SUMS` and the nine manifest files.
- **Extraction:** the extraction script's log, the per-configuration execution table (one row per execution, tens of kilobytes), and the first 200 rows of one prefix table.
- **Items 1, 2, 7, 9:** the `metadata` block of three executions per configuration, one from each of three different tasks.
- **Items 5 and 7:** the terminal-state counts and the twenty most common `error` strings per configuration with their counts.
- **Item 8:** the divergence-iteration distribution per configuration and the temperature field.
- **Item 3:** the metadata diff of the two Sonnet 4.5 archives.

If the extraction script fails on a `_mini` archive, upload the traceback and one representative JSON file from that archive, and the script is adapted before the audit proceeds.
