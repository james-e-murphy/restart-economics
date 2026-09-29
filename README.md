# Restart Economics for AI Agents

Cutoffs, retries, and cost per resolved task. Working paper and companion code.

This repository is the paper's reproducibility record. It holds the frozen analysis plan, the data
audit record, the code that rebuilds the derived tables, the policy evaluator, the results it
wrote, and the script that regenerates every exhibit from them. It does not hold the raw trajectory archives, which are a
third-party release, or the tables derived from them; it records the archives' checksums.

## What the paper does

Repeated agent executions on the same task vary enormously in cost, by up to thirty times in
reported token counts. An operator therefore runs a policy, not a single attempt: cap the attempt,
retry, escalate. The paper measures what a resolved task costs under such policies, using four
logged runs on 500 SWE-bench Verified tasks for each of seven configurations, and asks in order
whether retrying pays, whether a cap improves the retries, whether varying the cap by attempt
improves it further, whether observing execution state beats a fixed schedule, and whether switching
models improves it again.

**Policy value**, the single quantity every policy is scored on, is expected cost per incoming task:
agent spend, plus verification cost on attempts that produce something to check, plus a task-specific
outside option paid when the allowed attempts are exhausted. Because the outside option resolves the
task for certain, every task resolves, so this is also cost per resolved task and a policy cannot look
cheap by abandoning hard tasks. PLAN.md states the estimand, the policy classes, the identification
argument, and every prespecified comparison.

## Layout

    PLAN.md              the pre-analysis plan, frozen at the plan-frozen tag when the audit
                         closed, and registered on OSF
    AUDIT.md             the data audit protocol, then the record as it is completed
    audit_record.md      what the audit found, item by item
    configurations.csv   one row per archive, built by python -m restart.audit
    configurations_notes.json  the facts no table holds: endpoints, applied temperature, exclusions
    archives/SHA256SUMS  checksums of the raw archives; archives themselves are not committed
    src/restart/         extraction, cost reconstruction, policies, evaluator, bootstrap,
                         the schedule search, the state rule, the ladder, the break-even,
                         the cascade, the registered sensitivities, the appendix comparators,
                         the oracle, the diagnostics, and the coverage check of the intervals
    tests/               hand-walked edge cases and the synthetic dry run
    data/derived/        execution and prefix tables, rebuilt locally and not committed
    results/             policy values, margins, break-evens and cascades, each file written by
                         one command listed in results/README.md
    exhibits/            make.py, which regenerates every figure and table from results/
    paper/               the manuscript's parts, its assembly and facts sheet, and the build
    LICENSE              the MIT license, for src/ and tests/; see License below for the rest

## Working rules

1. **The plan precedes the results.** PLAN.md and AUDIT.md were written before any archive was
   opened. The plan is frozen at the `plan-frozen` tag when the audit closes, before any policy
   result is computed. Nothing in `exhibits/` is committed before that tag, and the commit history
   is the record that the plan came before the results.
2. **Raw archives are never committed.** They are large, third-party, and under their own license.
   The repository holds `archives/SHA256SUMS`. The derived tables are rebuilt from the archives by
   `restart.acquire`, and every table records the checksum of the archive it came from. The release
   records no license, so the tables are not committed either. The SWE-bench Verified task
   metadata, including the time-to-fix annotations used for the outside option, carries its own
   terms.
3. **The evaluator is verified before it is trusted.** The synthetic dry run and the hand-walked edge
   cases in `tests/` run in CI. Against real data, the extraction is reconciled with what Bai et al.
   state in numbers and with an earlier extraction of the GPT-5 archive, and every price schedule is
   checked call by call against the harness's logged cost, with any difference located.
4. **Deviations are recorded, not absorbed.** After the `plan-frozen` tag, any departure from PLAN.md
   is a deviation with its own entry in AUDIT.md, not an amendment to the plan.

## Reproducing

    pip install -e ".[dev]"                   # Python 3.9 or later
    pytest                                    # edge cases and the synthetic dry run
    python -m restart.acquire --out data/derived/   # lists, streams, verifies and extracts every archive
    python -m restart.pricing --validate data/derived/   # prices every call, compares with logged cost
    python -m restart.evaluate --check data/derived      # loads and prices each attempt pool
    python -m restart.ladder --derived data/derived      # steps i to iv and the transfer, the sweep
    python -m restart.fitted --derived data/derived      # the fitted steps' intervals at 1,000 replicates
    python -m restart.breakeven --derived data/derived   # the break-even of the primary result
    python -m restart.cascade --derived data/derived     # step v and the outcome correlation
    python -m restart.sensitivity --derived data/derived # every registered sensitivity
    python -m restart.comparators --derived data/derived # dollar cutoffs, threshold, universal, first look
    python -m restart.oracle --derived data/derived      # the sample oracle benchmark
    python -m restart.appendix --derived data/derived    # difficulty, cost distribution, spread
    python -m restart.diagnostics --derived data/derived # variance share, mixed outcomes, tail
    python -m restart.coverage                           # the interval's coverage, on synthetic data
    python -m restart.dynamic                            # the state rule against the exact optimum, synthetic
    python exhibits/make.py                              # every figure and table, from results/
    python paper/facts.py                                # every number the manuscript quotes
    bash paper/build/build.sh                            # the manuscript and its PDF (paper/README.md)

## Data

Trajectories are from the release accompanying Bai et al., *How Do AI Agents Spend Your Money?*
(arXiv 2604.22750), `loong0814/openhands_trajectories` on Hugging Face: four OpenHands
runs on 500 SWE-bench Verified tasks per configuration, in nine archives, of which the audit admits seven.
The paper treats these as *configurations* rather than models, because a run is a model under a harness version
at a date through an endpoint under a price schedule. AUDIT.md establishes what each one was.

## Preregistration

The frozen plan is registered on OSF Registries:
[osf.io/pdmw9](https://osf.io/pdmw9/), registered 20 September 2026, Secondary Data Preregistration
template. It carries PLAN.md, AUDIT.md, `audit_record.md` and this repository at the `plan-frozen`
tag, commit `d270cb8`, whose archive has SHA-256
`8032446f282aa57e1cffa889312a55dd79b65120389dde62eff684f3839a42d8`. The registration's own answers
record what was known about the data before the freeze, and what was not.

## Status

The audit is complete and PLAN.md Section 10 records what it found, including the state rule's class
and φ. The plan is frozen at the `plan-frozen` tag and registered. The primary results, the
cascade, the registered sensitivities, the appendix and the exhibits are computed from it by the
commands above. Version 0.1 of the paper, 28 September 2026, is built from the `v0.1` tag and posted
at [jamesemurphy.com/ai-economics/restart-economics](https://jamesemurphy.com/ai-economics/restart-economics/).

## License

The code in `src/` and `tests/` is under the MIT license, in `LICENSE`. PLAN.md, AUDIT.md and
`audit_record.md` are under CC BY 4.0, the license they were registered under on OSF. The manuscript
and its sources in `paper/` are copyright 2026 James E. Murphy, all rights reserved.
