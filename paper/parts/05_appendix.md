# Appendix A. The Registered Sensitivities

Each sensitivity changes one input and reruns the ladder, the break-even and the cascade with every choice redone. The cap's margin keeps its 1,000-replicate interval under every sensitivity; the fitted steps are scored as point estimates. The nine are:

- **False accepts at \(\phi = 0.34\) and \(\phi = 0.50\).** That share of accepted patches is charged the outside option later, and every policy is re-selected with the charge in its objective (Section 3.5).
- **A common 100-call horizon.** Every configuration is cut at 100 calls, with cutoffs up to 95, and an attempt still running at 100 is scored as a failure.
- **All tasks.** Every task with a usable draw is scored, each policy on the tasks that can fill it, rather than only the tasks with four usable draws. The two sides of a margin can then rest on different tasks.
- **Refusals excluded, evaluations without a verdict counted as failures, and re-runs dropped.** The three changes to the attempt pool of Section 4.2.
- **The lowest third-party price for Qwen3 Coder**, $0.22 per million input tokens and $1.80 per million output tokens. Every configuration is rescored, since Qwen's attempts are among those the others' transfer rules are fitted on.
- **The bucket-specific correction to the annotated times.** Kwa et al. (2025, Table 8) timed seven baseline runs on six tasks: four tasks from the shortest bucket took a geometric mean of 32.9 minutes rather than 3.9, and two from the 1 to 4 hour bucket averaged 131.6 minutes rather than 120. The correction factor is interpolated in the logarithm of annotated minutes for the 15 minute to 1 hour bucket, giving 75.1 minutes, and the factor measured at 1 to 4 hours is held above 4 hours, giving 526.4.

Table A1 gives the break-even under each, Table A2 the primary margins, and Table A3 the two-stage bootstrap. Section 7.6 summarizes them.

One check that the plan did not register runs beside the nine and is marked as such in the tables: every configuration scored on the 275 tasks with four usable draws in all seven, the cascade's tasks, so that a median across configurations summarizes one task set rather than seven. The primary ladder scores each configuration on its own tasks with four usable draws, 405 to 500 of them. On the common tasks the automated break-evens run from 2.0 to 5.2 median attempts, a median of 2.3 against the primary's 2.5, and the cap's margin at $100 an hour is −$0.73 to −$0.00, a median of −$0.41 against −$0.24, with every interval straddling zero. Under review at 0.5 the cap still saves for six configurations at every wage, from $0.50 to $3.98 per task at $100; for GPT-5 it turns to a cost of $0.09 to $0.61 per task from $75 an hour up, with an interval that straddles zero by several dollars either side. The transfer's median margin is $0.18 at $100 against $0.12. The common tasks are the ones every configuration completed four times, which leaves out the tasks on which the three configurations that suffered outages lost draws, so they are not a random subset; the check is that the medians quoted in the text do not depend on which task set they summarize.

{{table tableA1_sensitivity_breakeven
**Table A1. The break-even under each sensitivity.** The median and, in brackets, the range across configurations of the first rate at which the cap's margin changes sign, among the configurations whose margin changes sign in the sweep, in dollars an hour and in multiples of the median attempt cost. A crossing is supported when the interval excludes zero on both sides of it. Every crossing is in `results/sensitivity_breakeven.csv`. \* Not registered: a check added after the results were in.
}}

{{table tableA2_sensitivity_margins
**Table A2. The primary margins under each sensitivity.** Medians across configurations, dollars per task; positive is what the richer policy saves. Cap: step ii minus step iii, with an automated verifier (A) and under review at 0.5 of the outside option (R), at $25, $100 and $300 an hour. Transfer: step iii-b minus the state rule fitted on the other configurations, automated verifier. Switching: the best single configuration minus the cascade, automated verifier. \* Not registered: a check added after the results were in.
}}

The two-stage bootstrap resamples each task's usable draws as well as the tasks, on the same task resamples as the primary interval, so the two differ only by the second stage. For a mean over tasks the second stage would count within-task variation twice and widen the interval. Policy value is not such a mean: a retry draws a task's attempts without replacement, so a replicate that holds one draw twice prices a retry that can meet the same attempt again. The two bootstraps therefore need not be centered alike, and Table A3 gives each one's mean beside its interval. For the cap's margin the two intervals have about the same width, a median ratio of 1.02 over the 532 cells of the sweep, and the same center at the median, though in individual cells the centers differ by as much as $2. For the transfer the two-stage intervals, from 100 replicates, are narrower than the task-level ones from 1,000 in 20 of the 21 cells; GPT-5's margin stays distinct from zero at $100 and $300 an hour and Sonnet 4's at $300 does not.

{{table tableA3_two_stage
**Table A3. The two-stage bootstrap.** For the cap's margin in both regimes and the primary transfer at the three wages with fitted intervals: the point estimate, the task-level interval and the two-stage interval, each with the mean of its replicates for the cap; for the transfer the task-level mean is not recorded. The transfer's task-level interval is the one in Table 6, from 1,000 replicates; its two-stage interval is from 100. † Imputed price.
}}

# Appendix B. Comparators and the Sample Oracle

The plan registers four comparators beside the ladder, each a family chosen on the training folds and scored on the held-out folds, and reports them in full without arguing from them.

- **The dollar cutoff.** A sensitivity family in the plan, fitted separately from the cap in calls: \(K\) attempts, each stopped at the first decision point at which its spend exceeds a cutoff in dollars, over 40 cutoffs spaced evenly in logarithm between the 5th percentile of spend at call 5 and the largest attempt spend on the training folds. It asks whether the primary result depends on stating the cap in calls.
- **The threshold comparator.** An empirical welfare maximization family (Kitagawa and Tetenov 2018): stop at decision point \(t\) when spend per call over the last five calls exceeds \(a + bt\), with \(a\) at the 5th to 95th percentiles of that rate over running attempts on the training folds and \(b\) moving the threshold at the last decision point from a quarter of \(a\) to four times \(a\). If the state rule cannot beat it, the regressions add nothing.
- **The universal schedule.** Cutoffs in the sequence 1, 1, 2, 1 of a unit (Luby, Sinclair and Zuckerman 1993), the first four terms of the universal sequence. The plan does not fix the unit, and a unit of one call would stop every attempt at once, so the unit is chosen on the training folds among the decision points whose double is also a decision point or reaches the configuration's cap. Its classical guarantee assumes unbounded restarts of a procedure that eventually succeeds and is not claimed to carry over.
- **The first look.** The state rule allowed to act only at the first decision point, which if nearly as good as the full rule would recommend one early look and a fixed rule thereafter.

{{table tableA4_comparators
**Table A4. The registered comparators, automated verifier.** Dollars per task; positive is what the richer or registered policy saves. Cap in calls: step ii minus step iii. Cap in dollars: step ii minus the dollar cutoff. Rule over threshold: the threshold comparator minus the state rule. Searched over universal: the universal schedule minus step iii-b. First look: step iii-b minus the first-look rule, beside the same margin for the unrestricted rule. Intervals from 100 replicates with every family refitted inside each. † Imputed price.
}}

With an automated verifier at $100 an hour, the cap stated in dollars behaves as the cap in calls does: its margin runs from −0.58 to +0.18 per task and every interval includes zero. Under review at 0.5, at the same wage, it saves $1.40 to $4.88, more than the cap in calls for six of the seven configurations. At $100 an hour with an automated verifier the state rule beats the threshold comparator for all seven, by $0.25 to $1.17, distinct from zero for Gemini alone (at $300 it is distinct from zero for two, and loses for Qwen3 Coder); since the rule does not stop attempts there, this says that the threshold family, chosen from data, costs more than not capping at all. Under review at 0.5 at $100 an hour the threshold comparator does better than the rule for six of the seven. At $100 an hour the universal schedule costs less than the searched schedule in point estimate for five of the seven with an automated verifier, by up to $0.39, and every interval includes zero, which is the searched schedule's cost of being chosen from data again. With an automated verifier at $100 and $300 an hour the first-look rule is the full rule, since neither stops attempts. Under review at 0.5 at $100 an hour, restricting the rule to the first decision point costs $0.69 to $4.50 more for four configurations and changes the other three by at most three cents, so one early look does not stand in for the full rule where the rule acts at all.

Figure A1 draws the state rule against the best schedule across the sweep under review at 0.5, the regime in which the rule stops attempts: fitted on the configuration itself it gains for three configurations at some points of the sweep, and fitted on the other six it gains in 3 of the sweep's 133 cells and loses by more than a cent in 97.

![Figure A1](figures/figA1_transfer_review_05.pdf)

> **Figure A1. The state rule against the best schedule under review at 0.5 of the outside option.** As Figure 3, not the registered regime for the transfer and without intervals: the rule fitted on the other six configurations (solid), on the configuration itself (dashed), and not capping at all (dotted), as a share of what retrying without a cap costs. Where the dotted line leaves the frame, not capping costs far more than the schedule. † Imputed price.

**Leave-one-out essentialness.** Removing one configuration from the cascade's choices and rechoosing shows which the cascade relies on. With an automated verifier, removing GPT-5.2 raises the cascade's cost by $1.48 per task at $100 an hour and $2.19 at $300, and removing Sonnet 4 by $0.96 and $2.05; at $25 GPT-5 and Sonnet 4 matter most, at $0.41 and $0.31. Removing Sonnet 4.5 or Gemini lowers the cascade's cost at $100, by $0.06 and $0.15, because the cascade chosen with them does worse out of sample. Under review at 0.5, only removing GPT-5.2 raises the cost by more than a cent, by $1.12 per task at $100 and $2.70 at $300.

**The sample oracle.** For each of the 275 common tasks, the oracle is the cheapest schedule of one to four (configuration, cutoff) attempts on that task's own draws, and its value is the average over tasks. No policy in the class the cascades are drawn from can beat it on these draws, but as an estimate of any population quantity it is biased downward, since it takes a minimum over seven configurations on four draws per task, so its gap to the best cross-fitted cascade is an upper estimate of what knowing the task in advance would be worth, not a value of information. The minimum is found exactly by a recursion that the tests hold to a brute-force search over every schedule.

{{table tableA5_oracle
**Table A5. The sample oracle.** On the 275 common tasks, dollars per task: the oracle, the best cross-fitted cascade and single configuration on the same tasks, and the gap as a share of the cascade's cost. \* Exploratory, not registered: every task sent to the outside option. † Imputed price.
}}

With an automated verifier at $100 an hour the oracle costs $14.07 per task against $19.94 for the best cross-fitted cascade, a gap of $5.87, or 29 percent of the cascade's cost; across the three wages the gap is 27 to 33 percent, and under review at 0.5 at $100 it is 31 percent. Across the regimes and the three wages the gap is 27 to 37 percent of what the best cascade costs. Knowing each task in advance could be worth that much, far more than the cap, the schedule or the state rule is worth on these logs, although the gap is an upper estimate.

# Appendix C. Difficulty, the Distribution of Cost, and the Spread

**Difficulty.** In the primary ladder no policy observes a task's annotation. Here the annotation is admitted to every policy at once: each is chosen within a difficulty bucket, and the cap's margin is reported per bucket with its interval. The longest bucket holds a handful of tasks, too few for a training fold to choose on, so it is shown by its count and also pooled with the 1 to 4 hour bucket. Pooling the choices made within the buckets and comparing them with the primary's blind choice gives what admitting the annotation is worth.

{{table tableA6_difficulty
**Table A6. The cap's margin by difficulty.** Dollars per task at $100 an hour, every policy chosen within the bucket. \* The 95 percent interval from 1,000 replicates excludes zero; every interval is in `results/difficulty.csv`. Over 4 hours: too few tasks for a training fold to choose on, with their count in parentheses; the two longest buckets are also shown together. All, within: the choices made under 15 minutes, from 15 minutes to 1 hour and at 1 hour or more, pooled. All, blind: the primary. Tasks per bucket: 158 to 194, 210 to 261, 30 to 42, 2 to 3 and 32 to 45. † Imputed price.
}}

With an automated verifier, admitting the annotation changes little. At $100 an hour the cap's margin within the two short buckets stays within about half a dollar of zero, and pooled over the buckets the cheaper of steps ii and iii costs at most $0.41 per task less than when chosen blind, and for Gemini $0.03 more. Within the tasks annotated at an hour or more, the cap chosen within the bucket costs $4.78 to $9.03 per task for four configurations, the cost of choosing among caps on 32 to 45 tasks, though no interval excludes zero. The only cells in the paper where the interval puts the cap wholly on the cost side are here: in GPT-5's 1 to 4 hour bucket, 42 tasks, the cap costs about a cent per task with an automated verifier at every wage from $25 an hour, and more at three wages under review at 0.1.

Under review at 0.5 the long tasks are where the cap pays. At $100 an hour it saves $38.6 to $62.8 per task within the tasks annotated at an hour or more, distinct from zero for two configurations, and $26.0 to $44.1 within the 1 to 4 hour bucket, distinct from zero for three. Pooled over the buckets its saving is $2.81 to $5.68 per task against $0.75 to $3.56 when chosen blind, and admitting the annotation lowers the cost of the cheaper of steps ii and iii by $1.67 to $3.52 per task, 3 to 7 percent. Under review, what the cap saves is concentrated on the tasks that are most expensive to escalate.

**The distribution of cost.** A cap is partly insurance, and the mean alone undervalues it. The distribution of cost per incoming task is taken over tasks and, within a task, over the orderings of its draws the policy can use, each task weighing the same, and its quantiles are lower quantiles, so each is a cost some task and ordering actually incurs. The median-cost version of the primary comparison chooses steps ii and iii on the training folds by median cost and scores them by the median of the held-out costs.

{{table tableA7_distribution
**Table A7. The distribution of cost per task at $100 an hour.** Under steps ii and iii as chosen on mean cost: the mean, median and 95th percentile of cost per incoming task, and the cap's margin at the 95th percentile; and the median-cost version of the primary comparison. † Imputed price.
}}

With an automated verifier at $100 an hour, the 95th percentile of cost per task is about $200 for six configurations, the outside option of a task annotated at 1 to 4 hours, and about $65 for Sonnet 4.5, and the cap moves it by between $2.06 down and $1.52 up. Under review at 0.5 the cap lowers the 95th percentile by about $100 for every configuration, from about $300 to about $200: in the tail, a long task that would have been attempted, reviewed at half its outside option and then escalated is escalated without the review. As insurance, then, the cap pays only where review is dear. It is not free insurance: for four configurations the cap chosen on mean cost also raises the median cost per task under review, from about $26 to about $50, because it escalates the typical task, one annotated at 30 minutes whose outside option is $50, rather than attempting it and reviewing the patch. The median-cost version of the primary comparison is within about a cent of zero in every regime, since the median task is resolved cheaply whether or not the attempts are capped.

**The spread.** On the 275 common tasks, the range of policy value across the configurations, each at its best policy or at a single attempt, against the range across steps i to iii-b within a configuration: whether choosing the configuration or the policy moves cost more.

{{table tableA8_spread
**Table A8. Choosing the configuration against choosing the policy.** On the 275 common tasks, dollars per task: the range across configurations, holding each at its best policy and at one attempt, and the median and largest range across steps i to iii-b within a configuration. † Imputed price.
}}

With an automated verifier at $100 an hour, the range across configurations at their best policies is $4.94 per task, against a median range across policies within a configuration of $3.83 and a largest of $4.44. At the three wages of Table A8 the choice of configuration mostly moves cost more than the choice of policy, by nine times or more the median range within a configuration under review at 0.1 and 0.3, where the configurations seldom retry. The exceptions are the top of the automated sweep, where retrying makes the two about equal ($13.72 across against a median of $14.22 within at $300), and review at 0.5 at $25 an hour, where whether to run the agent at all is the larger choice.

# Appendix D. Diagnostics

The share of the variance in log spend that is within task, and the share of tasks with mixed outcomes across their four runs, motivate restarts but do not bound their value, which depends jointly on the cost and success distributions, their dependence, the outside option, \(K\) and the cutoff.

{{table tableA9_diagnostics
**Table A9. Within-task variation.** Per configuration, on its tasks with four usable draws: the share of the variance in log spend that is within task, the shares of tasks with mixed outcomes, with all four draws failing and with all four resolving, the median attempt cost, and the share of attempts whose spend passes their own task's outside option at $25 an hour. † Imputed price.
}}

The four runs of a task differ widely in what they cost, and 24 to 64 percent of the variance of log spend is within task, the most for GPT-5. They differ much less in whether they succeed. Only 11 to 25 percent of tasks have mixed outcomes across their four runs, while 22 to 31 percent fail on every run and 44 to 61 percent resolve on every run. All of the value of retrying comes from the mixed tasks; on the tasks where every run fails, a retry adds an attempt that cannot succeed, which is cheap when an attempt costs a dollar and the outside option fifty. Long attempts are not hopeless. In the six configurations capped at 500 calls, an attempt still running at 100 calls goes on to resolve 33 to 55 percent of the time, against 58 to 69 percent at the start (Figure A3), which is why a cap cuts successes as well as spend. The share of attempts whose spend passes their own task's outside option at $25 an hour runs from 0.05 percent of GPT-5's to 14.5 percent of Sonnet 4.5's, whose attempts cost most.

Whether switching after a failure can pay depends on how often the configurations fail together. Their outcomes are highly correlated (Figure A2): across the 275 common tasks the share of a configuration's draws that resolve is correlated with another's at 0.62 to 0.90.

![Figure A2](figures/figA2_outcome_correlation.pdf)

> **Figure A2. Outcome correlation across configurations.** The correlation, across the 275 common tasks, of the share of each configuration's draws that resolve. It is the portfolio predictor of whether switching after a failure can pay. † Imputed price.

{{figure figA3_tail_composition
**Figure A3. Tail composition.** For each cutoff on the decision grid: the share of attempts still running (dotted); of the spend incurred beyond the cutoff, the share by attempts that go on to resolve (solid), which is what a cutoff there would cut from successes; the chance that an attempt still running there resolves (dashed); and the share of running attempts whose spend has already passed their own task's outside option at $25 an hour (dash-dot), which marks where on the grid a cutoff at the annotated engineer time would fall. The last three are drawn while at least 1 percent of attempts are still running. † Imputed price.
}}

# Appendix E. Verification

**Coverage of the primary interval.** A synthetic population of 12,000 tasks has what makes the real pools hard: tasks that differ in difficulty and share it across their draws, attempts whose chance of resolving falls with their length, calls that grow dearer as context accumulates, and an outside option drawn from the benchmark's four buckets in about their proportions. Its median attempt costs $0.45 and its attempts resolve 48 percent of the time. What the cross-fitted cap margin estimates is the population value of the policies the procedure chooses from a training set, the target, which is computed by choosing on many independent samples and scoring each choice on the whole population. Table E1 gives, at four settings, the target, the best policy in the population, the bias of the point estimate on samples of 500 tasks, and how often the registered interval covers the target over 120 samples.

Table: **Table E1. Coverage of the registered interval on a synthetic population.** The cap's margin in dollars per task. Target: the population value of the procedure's choice. Best: the margin of the best policies in the population. Bias: the mean point estimate minus the target, with its standard error.

| Outside option | Verifier | Target | Best | Bias (s.e.) | Mean width | Covers |
|---|---|---|---|---|---|---|
| 1 median attempt | automated | +0.464 | +0.464 | +0.003 (0.003) | 0.111 | 93% |
| 5 median attempts | automated | +0.374 | +0.386 | −0.006 (0.008) | 0.417 | 98% |
| 50 median attempts | automated | −0.029 | +0.043 | +0.015 (0.022) | 1.022 | 98% |
| 20 median attempts | review at 0.5 | +1.527 | +1.612 | −0.020 (0.031) | 1.435 | 99% |

The point estimate is no more than one standard error from the target at every setting, and the interval covers at 93 to 99 percent. At 50 median attempts the target is negative while the best policy's margin is positive: the cost of choosing a cap from data exceeds what the best cap would save, which is the pattern the real data show above the break-even.

**The state rule against the exact optimum.** Where an attempt's prospects are fully described by the rule's own state, the optimal restart policy can be computed by backward induction. The synthetic attempts are of two kinds that they do not reveal: a good attempt almost always resolves when it finishes, a bad one seldom does and runs longer and writes more. In each interval of five calls an attempt writes a high or low volume of output, pays for it and finishes with a chance that depends on its kind, so the rule's three state variables determine how many high-output intervals the attempt has had, a sufficient statistic for its kind. Tasks are alike, so the restart values' other weakness, being averages over tasks, does not arise. The rule is fitted on 2,000 simulated tasks and every policy is scored on another 8,000. Table E2 gives the result for signals of two strengths.

Table: **Table E2. The state rule against the exact optimum on synthetic attempts.** Dollars per task. Signals weak: a good attempt has a high-output interval with probability 0.3 and a bad one 0.6; strong: 0.2 and 0.8. Stopped: the share of first attempts each policy stops before their end, and the mean call at which it does.

| Signals | Outside option | Verifier | Optimum | Rule | Rule above optimum | Best constant cutoff | No cap | Stopped: optimum | Stopped: rule |
|---|---|---|---|---|---|---|---|---|---|
| weak | 2 | automated | 1.220 | 1.302 | 6.8% | 1.511 | 1.771 | 65% at 12 | 78% at 10 |
| weak | 10 | automated | 2.150 | 2.842 | 32.2% | 2.636 | 2.636 | 42% at 29 | 65% at 8 |
| weak | 50 | automated | 5.420 | 6.198 | 14.3% | 5.642 | 5.642 | 29% at 42 | 42% at 5 |
| weak | 2 | review at 0.5 | 1.579 | 1.579 | 0.0% | 1.579 | 2.531 | 92% at 5 | 92% at 5 |
| weak | 10 | review at 0.5 | 6.514 | 6.967 | 7.0% | 7.458 | 8.984 | 67% at 14 | 81% at 10 |
| weak | 50 | review at 0.5 | 28.954 | 32.692 | 12.9% | 33.158 | 41.248 | 57% at 23 | 81% at 10 |
| strong | 2 | automated | 0.952 | 1.068 | 12.2% | 1.483 | 1.819 | 57% at 8 | 72% at 8 |
| strong | 10 | automated | 1.751 | 2.236 | 27.7% | 2.762 | 2.762 | 47% at 15 | 63% at 7 |
| strong | 50 | automated | 5.034 | 6.079 | 20.7% | 5.689 | 5.689 | 42% at 23 | 52% at 7 |
| strong | 2 | review at 0.5 | 1.543 | 1.544 | 0.1% | 1.544 | 2.559 | 92% at 5 | 92% at 5 |
| strong | 10 | review at 0.5 | 5.717 | 6.335 | 10.8% | 7.301 | 8.842 | 60% at 12 | 76% at 10 |
| strong | 50 | review at 0.5 | 25.694 | 29.337 | 14.2% | 32.406 | 40.257 | 60% at 12 | 76% at 10 |

The optimum's own policy, replayed by the evaluator on the held-out tasks, reproduces its computed value to within 1 percent in every setting, which checks the evaluator against an independent calculation. The rule stops more first attempts than the optimum in every setting where the two differ, and at the same call or earlier: the commit-to-termination approximation's bias toward restarting outweighs the opposite pull of its restart values. With an automated verifier it costs 7 to 32 percent more than the optimum, and in three of the six automated settings more than the best constant cutoff. Under review it still beats the best constant cutoff at the two higher outside options, where stopping early is valuable enough that reading the state pays despite the bias.

**Other checks.** Hand-worked cases check policy cost to the cent for a task whose four draws all fail, one where all resolve, one where one resolves, and one with an attempt stopped at the harness's limit; the schedule and cascade searches and the oracle's recursion are checked against brute-force searches on small cases; and the faster route by which the sensitivities' intervals are computed is checked against the ladder's estimate on every row. Against the release, the extraction reproduces what Bai et al. (2026) state in numbers: Sonnet 4.5 and Kimi K2 consume 3.14 and 2.19 million more tokens per execution than GPT-5, against their statement of over 1.5 million, and their GPT-5 price schedule is the one validated here. The code's tests run on every change.

# Appendix F. The Plan and the Choices It Left Open

The analysis plan was frozen at the `plan-frozen` tag of the repository after the data audit and registered on OSF Registries (osf.io/pdmw9) on 20 September 2026 under the Secondary Data Preregistration template, both before any policy was evaluated. Everything the audit found that the plan had not anticipated was recorded in the plan before the freeze: the configurations admitted and excluded, the attempt pool, each configuration's own iteration cap, the unequal numbers of usable draws, the price schedules, the state rule's class, and the value of \(\phi\). The paper departs from the frozen plan in four places, each a matter of what is reported rather than of what is computed, and each is stated here so that the plan and the paper can be read against each other.

- **Intervals for the fitted steps.** The plan asks for a 95 percent interval on every quantity chosen from data and allows a reduced replicate count where refitting inside every replicate is too expensive. Steps iii-b, iv and iv-t carry intervals only at $25, $100 and $300 an hour with an automated verifier, where the plan reads the primary transfer; elsewhere they are point estimates, which the plan did not provide for. The cap's margin and the value of retry carry their intervals at every point of the sweep in every regime.
- **The cascades' tasks.** The plan says that cascades enumerate all available draw combinations and are unbiased at any count, and also that comparisons across attempt budgets rest on the tasks with four usable draws in every configuration involved. The second rule is applied: step v, the leave-one-out, the sample oracle and the spread are scored on the 275 tasks that all seven configurations cover with four draws. Those tasks are not a random subset of the 500 (Appendix A).
- **Where the diagnostics and the flags sit.** The plan places the diagnostics beside the results they explain and the configuration's cap and harness version in every table; the diagnostics are in Appendix D, cross-referenced from Section 8.1, and the cap and harness version are in Table 1.
- **Two summaries given in prose or in the results files rather than as exhibits.** The rates at which the chosen attempt budget and cutoff change over the sweep are described in Sections 7.1 and 7.2 and recorded in the `choice_*` columns of `results/ladder.csv`; the 95th percentile of cost is given for steps ii and iii (Table A7) rather than for every step, with the rest in `results/distribution.csv`.

Where the plan left a detail open, the choice made is stated here.

- **Sign.** The plan defines the cap's marginal value as step iii minus step ii in cost. The paper reports the same quantity with the opposite sign, step ii minus step iii, so that a positive margin is a saving throughout.
- **The annotation correction above 4 hours.** The plan interpolates the correction for the buckets without measured baselines. Above 4 hours there is nothing to interpolate toward, and the factor measured at 1 to 4 hours is held (Appendix A).
- **The universal schedule's unit** is chosen on the training folds, since the plan does not fix it (Appendix B).
- **The difficulty display** shows all four buckets, with the smallest shown by its count only and pooled with the next, and the pooled choices are those made under 15 minutes, from 15 minutes to 1 hour and at 1 hour or more (Appendix C).
- **Quantiles and the median version** are defined as in Appendix C.
- **The two-stage bootstrap** uses the same task resamples as the primary and reports both centers without correcting either (Appendix A).
- **Break-evens** are located by a scan in the logarithm of the rate refined by bisection. Table 4 gives the first crossing per configuration and regime, and every crossing the scan found is in Table A11, as the plan requires.
- **The tail composition** marks the annotated outside option on the decision grid by the share of running attempts whose spend has already passed it at $25 an hour, since the outside option differs by task.
- **The first figure.** The plan asks that the abstract and the first figure be built from the primary result and the primary transfer. Figure 1 draws the whole ladder from the registered values of Table 5, each step as a share of step i, and the primary result and the primary transfer are two of its steps; Figures 2 and 3 then give each its own figure. It adds a display, not a quantity.
- **Replicates for the fitted steps.** The plan allows fewer than 1,000 replicates where refitting inside every replicate is too expensive, and asks that the count be reported. The fitted steps' intervals at $25, $100 and $300 an hour with an automated verifier come from 1,000 replicates, each refitting every model and choice, computed first at 100 and then extended to 1,000 on the same task resamples, which changed no conclusion; the comparators' intervals (Appendix B), the cascade's switching margin and the two-stage transfer are from 100. The value of retry's interval comes from the same bootstrap and the same resamples as the cap's margin.
- **The common-tasks check** in Appendix A was added after the registered results were in, and is marked as unregistered where it appears.
- **The best cap chosen with hindsight** (Sections 7.2 and 8.1, `cap_margin_in_sample` in `results/ladder.csv`), the in-sample margin of the capped family over the uncapped one, is not in the plan, whose only hindsight quantity is the per-task sample oracle of Appendix B. It is reported as an unregistered check on the size of the gain any cap could find.

Several exhibits were added after the registered results were in, and each is marked as exploratory where it appears: escalating every task without running the agent as a reference line (Tables 5, 7, A5 and A10, Figure 4) and the comparisons of the best capped policy with it under review (the abstract, Sections 1, 7.2, 8.3 and 10); the outside option at which retrying first beats escalating (Figure 2 and Section 8.2); the best cap chosen with hindsight, above; and the break-even in full attempts (Figure 5). The argument that the break-even in multiples does not depend on the level of token prices (Section 8.1) is arithmetic on the estimand rather than a result.

# Appendix G. The Ladder under Review at 0.1 and 0.3, and Every Crossing

The plan reports every result under an automated verifier and under review at 0.1, 0.3 and 0.5 of the outside option. The text and the main exhibits read the automated verifier and review at 0.5, the two regimes that bracket the answer; Tables 4, 7, A1, A5 and A8 carry all four. Table A10 gives the ladder of Table 5 under review at 0.1 and 0.3, and Table A11 lists every crossing of the cap's margin the scan found, where Table 4 gives only the first. Every number here is in `results/ladder.csv` and `results/breakeven.csv`.

{{ladder tableA10_ladder_review
**Table A10. Policy value under review at 0.1 and 0.3 of the outside option.** As Table 5, with each patch submitted charged a review of 0.1 (top) or 0.3 (bottom) of its task's outside option. Resolves: the share of tasks steps i, ii, iii and iii-b resolve without the outside option, in percent. \* Exploratory, not registered: every task to the outside option. † Imputed price.
}}

{{table tableA11_crossings
**Table A11. Every crossing of the cap's marginal value.** For each configuration and regime, each rate at which the margin changes sign over the sweep, in dollars an hour and in multiples of the median attempt cost, with the sign on either side and whether the bootstrap interval is clear of zero below it, above it, on both sides or on neither. Under review at 0.5 the margin does not change sign. † Imputed price.
}}
