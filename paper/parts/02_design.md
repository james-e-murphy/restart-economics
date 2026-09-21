
# 3. The Decision and the Estimand

## 3.1 The operator's problem

A task arrives. The operator may run the agent on it up to \(K \le 4\) times, each run a fresh attempt that starts from the task and not from the previous attempt's state. Each attempt runs under a configuration, a model under a harness, and may be stopped at a cutoff, counted in model calls, before the harness would stop it. An attempt that reaches its own end and produces a patch is verified. If the patch resolves the task the operator stops. If every allowed attempt fails, the operator pays for the task to be resolved another way: the outside option.

## 3.2 Policy value

For task \(i\) and a policy with \(K\) attempts, let \(C_{ij}\) be what attempt \(j\) spends up to its stop, \(D_{ij}\) indicate that it ends with a patch to verify, and \(S_{ij}\) indicate that it resolves. The cost of the task is

\[ L_i = \sum_{j=1}^{K} \Big(\prod_{l<j} (1 - S_{il})\Big)\big(C_{ij} + v_i D_{ij} + \phi H_i S_{ij}\big) + \Big(\prod_{j=1}^{K} (1 - S_{ij})\Big) H_i , \]

where \(H_i\) is the outside option, \(v_i\) the cost of verifying a patch and \(\phi\) the share of accepted patches that are false accepts, zero in the primary analysis. The value of the policy is the mean of \(L_i\) over incoming tasks, in expectation over which of the task's runs the attempts draw. Every task is resolved, either by an attempt or by the outside option, so the value is also the cost per resolved task, and the share of tasks the agent resolves without the outside option is reported beside it rather than traded against it.

Three properties are deliberate. The estimand is finite: with at most four attempts it needs no model of what a fifth would do, and a task that no attempt resolves costs its attempts plus the outside option rather than an undefined ratio of cost to success probability. Abandonment is never free, because a task given up on is paid for at the outside option. And the outside option is external and task-specific, set by the benchmark's own annotation rather than by the agent's behavior.

## 3.3 The outside option

SWE-bench Verified annotates each task with the time an engineer with a few hours of familiarity with the codebase would need to fix it, in four buckets: under 15 minutes, 15 minutes to an hour, 1 to 4 hours, and over 4 hours (Chowdhury et al. 2024). Following Kwa et al. (2025), the buckets are converted to 3.9, 30, 120 and 480 minutes, and \(H_i\) is that time at a fully loaded engineer wage. The wage is swept from $5 to $300 an hour. The lower end is far below any human wage on purpose: it stands for a cheap automated fallback, a deferral, or a task that may simply be dropped.

The tasks are mostly short. On the tasks scored here the mean annotated time is about 30 minutes, so at $100 an hour the mean outside option is about $50, against a median attempt cost of $0.34 to $1.66 depending on the configuration. Because attempt costs differ fivefold across configurations, the sweep is also run in units of attempt cost: at a multiple \(M\), the wage is set so that the mean outside option equals \(M\) times the configuration's median attempt cost. A break-even in these units compares across configurations; the same break-even in dollars does not.

## 3.4 The verifier

Every result is reported under two verifier regimes. With an automated verifier, the benchmark's own tests, \(v_i\) is taken as zero. With a human reviewer, \(v_i = f H_i\) for \(f\) of 0.1, 0.3 and 0.5: review costs a share of what it would cost the reviewer to fix the task, so it costs more on the tasks whose escalation costs more. Under review a cap earns a second credit, because an attempt cut off before it produces a patch saves a review as well as tokens.

## 3.5 What resolution means

An attempt resolves when the benchmark's tests accept its patch. That is benchmark resolution, not a correct and mergeable fix. Maintainers reviewing agent pull requests that SWE-bench Verified scores as correct would not merge roughly half of them (Whitfill et al. 2026), and on a different benchmark, whose synthesized tasks state constraints drawn from real code review, about a third of test-passing repairs violate them (He et al. 2026). The registered sensitivity treats a share \(\phi\) of accepted patches as false accepts whose outside option is paid later, at \(\phi = 0.34\) and \(\phi = 0.50\), the two ends of the range these sources imply, and re-selects every policy with that charge in its objective. A single \(\phi\) assumes the false-accept share does not depend on the policy, which may fail if patches produced after a cutoff-driven retry are more superficial than those from uninterrupted runs. The assumption is stated, not tested.

# 4. Data

## 4.1 The release and the configurations

The data are the trajectories released with Bai et al. (2026): four OpenHands runs on all 500 SWE-bench Verified tasks for each of eight models, in nine archives; one run of one configuration lacks one task. The paper treats each archive as a configuration rather than a model, since a run is a model under a harness version, at a date, through an endpoint, under a price schedule. An audit completed before the plan was frozen established what each archive was, and admitted seven. Two were excluded. In the Claude Sonnet 3.7 archive, the harness replaced every attempt that reached its 100-call limit with a fresh one and kept only the later try, so the recorded attempts are a sample from which long attempts were removed. The second Sonnet 4.5 archive runs a different agent under a different harness, with a critic that allows up to three attempts per task and keeps the one it accepts.

All seven included configurations run the same agent, CodeActAgent (Wang et al. 2024), under OpenHands (Wang et al. 2025). Table 1 describes them. Harness versions differ, and are reported with every result. GPT-5 stops at 100 iterations and the other six at 500, and the cap is treated as an attribute of the configuration: each is evaluated within its own cap, and a common 100-call horizon is a sensitivity. The audit found one model call per agent iteration and no history condensation in any configuration, so cutoffs are stated in calls.

Table: **Table 1. The seven configurations.** Usable attempts are those in the attempt pool (Section 4.2); the resolved share is among them. Tasks with four usable draws are the tasks on which every comparison across attempt budgets is scored. The median attempt is the median cost of a usable attempt run to its own end, on those tasks, at list price. † Qwen3 Coder's price is imputed.

| Configuration | Harness, run dates | Cap | Usable attempts | Resolved | Tasks with four draws | Median attempt |
|---|---|---|---|---|---|---|
| GPT-5 | 0.62.0, Dec 2025 to Jan 2026 | 100 | 1,995 | 59.8% | 496 | $0.34 |
| GPT-5.2 | 0.62.0, Jan 2026 | 500 | 1,891 | 65.9% | 405 | $0.56 |
| Claude Sonnet 4 | 0.40.0, Jun 2025 | 500 | 1,998 | 68.7% | 498 | $1.04 |
| Claude Sonnet 4.5 | 0.62.0, Dec 2025 | 500 | 2,000 | 64.1% | 500 | $1.66 |
| Gemini 3 Pro Preview | 0.62.0, Jan 2026 | 500 | 1,893 | 61.3% | 410 | $0.82 |
| Kimi K2 | 1.1.0, Jan 2026 | 500 | 1,904 | 56.7% | 412 | $0.70 |
| Qwen3 Coder 480B† | 0.48.0, Jul 2025 | 500 | 2,000 | 66.1% | 500 | $1.09 |

## 4.2 The attempt pool

How an attempt stopped and whether it resolved are recorded separately, because the harness evaluates whatever patch exists when it stops, including at its own limit. An attempt enters the pool when it is a draw from the configuration's behavior and its outcome was observed. Infrastructure failures (outages, rate limits, relayed provider errors and the harness's eight-hour timeout) and evaluations that returned no verdict are excluded. Finishes, empty patches, patches that did not apply, stops at the iteration limit or by the harness's loop detector, provider refusals and errors caused by the model's own output are retained and scored by the benchmark's report. The pool holds 13,681 of the 13,999 executions. Three prespecified sensitivities change these rules: excluding refusals, which occur only for GPT-5; counting evaluations without a verdict as failures; and dropping executions the harness re-ran after a crash, which every configuration has, from 12 for GPT-5 to 108 for GPT-5.2.

Excluding attempts leaves some tasks with fewer than four usable draws, mostly in the three configurations that suffered outages. Comparisons across attempt budgets are therefore scored on the tasks with four usable draws in every configuration involved, which is each configuration's own subset for the ladder (Table 1) and 275 tasks common to all seven for the cascades. Scoring every policy on every task that can fill it is a registered sensitivity.

## 4.3 Prices

Cost is reconstructed from token counts under each model developer's published list price on the run's first day, applied call by call over the token classes the developer bills. The logged cost is not the price. For GPT-5 and both Sonnet configurations the published schedule reproduces the logged cost of every call. For GPT-5.2 and Gemini the harness charged cached input at the full input price, and ignored Gemini's long-context tier; for Kimi the logged cost follows no fixed schedule, consistent with a router sending calls to providers at different prices. At the published schedules the six configurations that log cost spent $12,692, against $23,543 logged. Qwen3 Coder was self-hosted and logs no cost, so its schedule is imputed at the developer's hosted price at release, tiered by prompt length, and its dollar figures carry a dagger throughout. The lowest third-party price for the same weights, $0.22 per million input tokens and $1.80 per million output tokens, is a registered sensitivity.

# 5. Identification and Estimation

## 5.1 Replay

Every policy in the class stops an attempt at or before the point where the harness stopped it. The outcome of any such policy on a logged attempt is therefore a deterministic function of the log: the attempt's prefix up to the cutoff. An attempt cut off at call \(t\) costs what its first \(t\) calls cost, is discarded unverified, and resolves nothing. An attempt that reaches its own end costs what it cost, is verified if it produced a patch, and resolves if the tests accepted it. Nothing is imputed and nothing about the agent is modeled, so no ignorability assumption is needed. The harness's own stops are not censoring: continuing past them is outside the policy class, not unidentified within it.

One consequence is a direction, not a bias to be corrected. The harness submits whatever patch is in the workspace when it stops at its limit, and some such patches pass; a policy's cut-off attempt is discarded instead, because the workspace at an earlier call cannot be recovered. With an automated verifier, submitting would weakly dominate discarding, so the measured value of a cutoff is conservative. With a human verifier and a low-yield partial patch, discarding can be cheaper. The two are not ordered in general, and no bound is claimed.

## 5.2 Enumeration

A task's four runs are treated as exchangeable: any ordering of them is as likely as any other. A policy of \(K\) attempts is then evaluated exactly by averaging its cost over every ordered selection of \(K\) of the task's usable draws: 24 orderings for four attempts from one configuration, and for a cascade the product of each configuration's orderings, since separate runs of different configurations are independent. Exchangeability does not require the runs to be independent of one another. A configuration that sometimes repeats a trajectory, as Gemini does on four tasks, is priced as behaving that way, which is what a retry of it would meet. With the policy fixed out of sample, the mean of this estimator over tasks is unbiased for the policy's value on a workload drawn like SWE-bench Verified. Nothing is claimed about any single task's conditional expected cost.

## 5.3 Cross-fitting and the full-pipeline bootstrap

Every quantity chosen from data (the attempt budget, the cutoff, the schedule, the state rule, the cascade) is chosen on four of five task-grouped folds and scored once on the fifth. The split is fixed before any policy is scored. Cross-fitting removes the optimism of scoring a choice on the tasks that made it but does not carry the variability of the choice into an interval, so intervals come from a bootstrap that resamples tasks and repeats the split, the choice and the scoring inside every replicate. Copies of a task drawn more than once in a replicate are kept in the same fold, so that a replicate never scores a choice on a task that made it. Intervals are 95 percent percentile intervals from 1,000 replicates for the primary result, and from 100 replicates for the fitted steps, whose models and choices are refitted inside each replicate, which is far more expensive; those are computed with an automated verifier at $25, $100 and $300 an hour. No significance test is run. A margin is called positive or negative only when its interval excludes zero.

A synthetic population with a known answer checks the interval before it is trusted. At four settings of the outside option and the verifier, the registered interval covers the population value of the policy its procedure chooses in 93 to 99 percent of 120 samples of 500 tasks (Appendix E).

## 5.4 The transfer test

The primary transfer fits the state rule's models on the other six configurations and scores it on the target. For the target's fold \(f\), the models are fitted on the other configurations with fold \(f\)'s tasks excluded from them too, so that the rule never sees a held-out task through another configuration. The claim this licenses is configuration-level generality within SWE-bench Verified under this harness, with each configuration held out in turn, not generality across domains.

# 6. Policies

All policies are schedules of attempts over (configuration, cutoff) pairs, evaluated on the same terms with the same outside option and the same verifier. Table 2 lists the ladder.

Table: **Table 2. The policy ladder.** Each step is chosen on training folds from its class, the attempt budget \(K \le 4\) included.

| Step | Policy | What it measures |
|---|---|---|
| i | One attempt, no cutoff, then the outside option | Baseline |
| ii | \(K\) attempts, no cutoff | The value of retrying |
| iii | \(K\) attempts at a constant cutoff | The value of a cap, given retry |
| iii-b | \(K\) attempts under a schedule of cutoffs | The value of varying the cap by attempt |
| iv | A state-aware restart rule | The value of observing the execution |
| v | A schedule over (configuration, cutoff) pairs | The value of switching configurations |

**Decision points.** Every policy acts at the same points: every fifth call from 5 to 100, then every twenty-fifth from 125 to 475, below the configuration's own cap. That is 19 points for GPT-5 and 35 for the others. A constant cutoff stops at one of them regardless of state; a schedule may use a different one for each attempt. Extra opportunities to stop are not allowed to pass for the value of richer state.

**Schedules.** Step iii-b is searched by coordinate ascent, one attempt at a time, starting from the best constant cutoff on the same training tasks, and a move is kept only when it lowers cost on those tasks. On the folds that choose it, the schedule is therefore never worse than the constant cutoff, and its whole margin out of sample is the value of letting the cap vary by attempt, net of the cost of choosing it. The search is exact arithmetic on the replayed pool, checked against the evaluator.

**The state-aware rule.** Step iv is a receding-horizon restart rule. At each decision point it compares the expected cost of committing the running attempt to its end against restarting now, and stops the attempt when

\[ s + v > q\,(V_{j+1} - \phi \bar H), \]

where \(q\) is the fitted probability that the attempt resolves if run to its end, \(s\) its fitted remaining spend, \(v\) the verification cost at the mean outside option \(\bar H\), and \(V_{j+1}\) the value of starting afresh with the attempts that remain. Two models supply \(q\) and \(s\): a logistic regression and a log-link quasi-Poisson regression, each on three state variables (the log of the call count, of one plus cumulative output tokens, and of one plus output tokens over the last five calls), pooled across decision points. That is eight coefficients per configuration. The restart values \(V_j\) are the rule's own replayed costs on the training folds, computed backward over attempts, and \(K\) is chosen as for every policy. Committing to termination ignores the option to stop later and so biases the rule toward restarting, while restart values that are averages over tasks, and that replay a rule which is not optimal, can pull either way. The net direction is measured on synthetic data where the optimum is computable (Appendix E), not asserted.

The same rule serves within and across configurations; the two differ only in where the two models are fitted. For the transfer, the other six configurations' rows are pooled with equal weight per configuration, and in both cases the restart values and \(K\) come from the target configuration's own training folds, so the transfer tests whether reading an execution's state carries across configurations, not whether a configuration's success rate does. Elapsed time was registered as a state variable and dropped because Qwen logs no call times.

**Cascades.** Step v lets each attempt name a configuration as well as a cutoff. Retrying the same configuration is one of the choices, so retry and reroute are one decision. For each training set the search starts from the best single configuration's schedule, the best one configuration an operator could have picked from the same data, and moves one (configuration, cutoff) pair at a time. Switching's margin is measured against that best single configuration, chosen on the same folds.
