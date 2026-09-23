# Draft deviation records, for review before anything is written into AUDIT.md

README.md rule 4: after the `plan-frozen` tag, any departure from PLAN.md is a deviation with its
own entry in AUDIT.md. AUDIT.md has no such section yet. A fresh read of the manuscript against
PLAN.md on 23 September 2026 found the departures below, all in what is reported rather than in
what is computed. Each is stated in Appendix F of the manuscript in the same terms. Two further
omissions found by the same read, the agent-resolved share (PLAN.md Section 3) and the interval
on the value of retry (Section 5), were not departures to record but gaps to close, and are closed
in the results and in Tables 3 and 4.

Proposed heading in AUDIT.md: `## 15. Deviations from the frozen plan`, after the freeze record.

---

### Deviation 1. Intervals for the fitted steps at three rates only

**Plan.** Section 5: "Where refitting inside every replicate is too expensive, the replicate count
is reduced and the intervals are stated as conditional on the fitted selection procedure rather
than claimed to include it. Intervals are 95 percent percentile intervals from 1,000 replicates,
or from the reduced count, which is then reported."

**Done.** Steps iii-b, iv and iv-t carry intervals at $25, $100 and $300 an hour with an
automated verifier, from 1,000 replicates (`restart.fitted`). At every other point of the sweep
and in every review regime they are point estimates. The plan provided for a reduced count, not
for no interval.

**Why.** A replicate refits the schedule search and the state rule's two models inside every
fold; at 532 cells that is far beyond what the ladder run could bear. The three rates are where
the plan reads the primary transfer.

**Effect on the paper.** Every claim about steps iii-b, iv and iv-t is made at those three rates
or in point estimate and says so (Sections 7.3, 7.4, Appendix F). The primary result and the
value of retry are unaffected: both carry intervals at every cell.

### Deviation 2. Cascades scored on the 275 tasks common to all seven configurations

**Plan.** Section 10: "Cascades enumerate all available cross-configuration draw combinations,
which requires one draw per configuration and is unbiased at any count." Same section:
"comparisons across K rest on the subset with four usable draws for every configuration
involved."

**Done.** Step v, the leave-one-out, the sample oracle and the spread are scored on the 275 tasks
with four usable draws in every configuration (`restart.cascade`, `restart.oracle`).

**Why.** The two sentences pull apart when a cascade is compared with single-configuration
policies at several attempt budgets; the four-draw rule was applied so that every policy in the
comparison is scored on the same tasks.

**Effect on the paper.** Table 7 and Section 7.5 state the task count. Appendix A's common-tasks
check shows the ladder on the same 275 tasks and notes they are not a random subset of the 500.

### Deviation 3. Diagnostics in an appendix; cap and harness version in Table 1 only

**Plan.** Section 7: "Diagnostics, presented beside the result they explain." Section 10: the
no-cutoff baseline at the harness's own cap is "flagged in every table" and the harness version
is "a covariate reported with every table."

**Done.** The diagnostics are Appendix D, cross-referenced from Section 8.1. The cap and the
harness version are in Table 1 and stated once in Section 4.1; the other tables do not repeat
them.

**Why.** Presentation. The diagnostics run to two tables and a figure.

**Effect on the paper.** None on any number.

### Deviation 4. Two summaries given in prose or in the results files rather than as exhibits

**Plan.** Section 7, main-text exhibits: the policy-value table "with break-even rates and the
breakpoints where the optimal K and cutoff change." Section 7, appendix: "The 95th percentile of
cost per task under each policy."

**Done.** The rates at which the chosen budget and cutoff change are described in Sections 7.1
and 7.2 and recorded per sweep point in the `choice_*` columns of `results/ladder.csv`. The 95th
percentile is tabulated for steps ii and iii (Table A7); steps i and iii-b are in
`results/distribution.csv`.

**Why.** Space in the main text; the table of policy values already fills a page.

**Effect on the paper.** None on any number.

---

Not recorded as deviations, because the paper now does what the plan asks:

- The share of tasks resolved without the outside option (Section 3) is reported beside every
  value (Tables 3, 4 and A10; `share_*` columns of `results/ladder.csv`).
- The value of retry carries a 95 percent interval from the same bootstrap and the same task
  resamples as the cap's margin (Table 3; `retry_value_low`, `retry_value_high`).
- Every crossing of the cap's margin is listed (Table A11).
- The ladder under review at 0.1 and 0.3 is tabulated (Table A10).
- The task count for every attempt budget is in `tasks_with_draws` in `results/ladder.csv`.
- The best cap chosen with hindsight (`cap_margin_in_sample`) is labelled as unregistered
  wherever it appears and listed in Appendix F.
