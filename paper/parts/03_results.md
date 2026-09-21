
# 7. Results

All values are expected cost per incoming task in dollars, chosen on training folds and scored on held-out folds. Margins are written so that a positive number is what the richer policy saves. Intervals are 95 percent bootstrap intervals that repeat the choice inside every replicate.

## 7.1 Retrying

With an automated verifier, retrying pays at every wage from $50 an hour up. At $100 an hour, letting the folds choose up to four attempts lowers expected cost by 13.2 to 19.6 percent against a single attempt for six configurations, and at $300 an hour by 16.4 to 21.0 percent. The folds choose four attempts at both wages. GPT-5.2 gains least, 4.3 percent at $100 and 8.0 percent at $300, and at $25 an hour retrying it does not pay at all. At $25 the other six gain 1.5 to 13.8 percent, most of them with two attempts. Where the outside option is worth five median attempts or fewer, no configuration retries.

Review changes this. When each patch submitted costs a review of 0.3 or 0.5 of the outside option, no configuration retries at any wage: every fold chooses one attempt. At 0.1 of the outside option, retrying pays in 8 of the 63 configuration and wage cells. A second attempt is only worth its review when the first failed, and after a failure the chance that the next attempt succeeds is not high enough to cover a review priced at a large share of what the engineer would charge to fix the task.

## 7.2 The cap given retry

The primary result is the marginal value of a constant cutoff given retry, step ii minus step iii. The plan registered an expectation, set from the magnitudes the audit established and not from any policy result: that with an automated verifier the cap would not pay at any wage an enterprise would recognize, because the outside option exceeds attempt cost by two orders of magnitude, and that under human review it would pay, because a discarded attempt saves a review. Figure 1 shows the margin across the sweep in every regime, and Tables 3 and 4 give its values and its break-evens.

![Figure 1](figures/fig1_cap_margin.pdf)

> **Figure 1. The cap's marginal value given retry.** Step ii minus step iii across the sweep, for each configuration and as the median across them, as a share of what retrying without a cap costs. The horizontal axis is the outside option in multiples of the configuration's median attempt cost. Bands are 95 percent intervals from 1,000 bootstrap replicates for the automated verifier and for review at 0.5 of the outside option. The dotted line, an exploratory addition, marks the outside option above which retrying without a cap first costs less than escalating every task. † Qwen3 Coder's price is imputed.

**With an automated verifier the cap stops paying at two to four attempts' worth of outside option.** For every configuration the margin is positive at the bottom of the sweep and crosses zero between 2.14 and 3.83 times the median attempt cost, which is between $1.74 and $7.08 an hour (Table 4). The saving is resolved only below about one to two median attempt costs, between $1.16 and $5.00 an hour. Above the crossing the margin is small and mostly negative: at $100 an hour it runs from −0.74 to +0.01 dollars per task, a median of −0.24 (Table 3). Its interval covers zero at every point of the sweep above the crossings, in every configuration. In none of the 532 cells of the primary sweep, and none of the cells of the nine sensitivities in Section 7.6, is the cap resolved as a cost. Some configurations cross zero more than once, GPT-5.2 four times, and none of these crossings has both of its sides resolved.

{{ladder
**Table 3. Policy value across the sweep.** Expected cost per incoming task in dollars, each step chosen on training folds and scored on held-out folds. Cap's saving is step ii minus step iii with its 95 percent interval from 1,000 replicates. Step iii chose: the distinct choices made across the five folds, attempts × cutoff in calls. Under review at 0.5 of the outside option every fold chooses one attempt, so step ii is step i. \* Exploratory, not registered: every task sent to the outside option without running the agent. † Imputed price.
}}

What the folds choose explains the size of the margin. With an automated verifier at $100 an hour, step iii keeps four attempts, except in some folds for GPT-5.2, and caps each at 80 to 275 calls, or in at least one of GPT-5's folds not at all. The cap therefore stops only attempts that have already run long, some of which would have succeeded. Each success cut off costs the outside option, about $50 on average at this wage, against the few dollars of tokens the cap saves on the attempts it stops. The cap is chosen on the training folds because it helps there by a little, and out of sample that little does not survive.

Table: **Table 4. The break-even of the cap's marginal value.** For each configuration and regime, the first rate at which the margin changes sign, in multiples of the median attempt cost with dollars an hour in parentheses, and the largest multiple at which the cap's saving is resolved. None: the margin does not change sign in the sweep; under review at 0.5 the cap saves across the whole sweep in point estimate. Every crossing found is in `results/breakeven.csv`; none has both of its sides resolved. † Imputed price.

| Configuration | Automated | Review 0.1 | Review 0.3 | Review 0.5 |
|---|---|---|---|---|
| GPT-5 | 2.54 ($1.74); resolved to 2.0 | 3.18 ($2.18); 2.0 | 6.86 ($4.71); 2.0 | none; 20.0 |
| GPT-5.2 | 2.89 ($3.36); 1.0 | 5.79 ($6.73); 2.0 | none; 2.0 | none; 8.6 |
| Sonnet 4 | 2.18 ($4.51); 1.0 | 2.68 ($5.54); 2.0 | 4.98 ($10.29); 2.4 | none; 5.0 |
| Sonnet 4.5 | 2.14 ($7.08); 1.5 | 2.68 ($8.87); 2.0 | 5.47 ($18.11); 3.0 | none; 10.0 |
| Gemini 3 Pro | 2.35 ($3.90); 2.0 | 2.95 ($4.88); 2.0 | 6.13 ($10.16); 3.0 | none; 10.0 |
| Kimi K2 | 3.83 ($5.30); 2.0 | 5.90 ($8.16); 2.0 | 10.76 ($14.88); 5.0 | none; 20.0 |
| Qwen3 Coder† | 2.73 ($5.91); 2.0 | 3.42 ($7.40); 2.3 | 10.56 ($22.82); 4.6 | none; 23.1 |

**Under review at half the outside option the cap saves, in point estimate at every wage, but the saving is resolved only at the lower wages.** With review at half the outside option, the margin is positive across the whole sweep for all seven configurations, from $0.75 to $3.56 per task at $100 an hour, but its interval excludes zero only up to between 5 and 23 median attempt costs, between $10 and $50 an hour. At review of 0.3, six configurations cross from saving to costing between 5.0 and 10.8 median attempt costs, and at 0.1 the crossings sit between 2.7 and 5.9, close to the automated ones. As with the automated verifier, the cost side of every crossing is unresolved. The registered expectation holds in point estimate at a review share of 0.5: opposite answers in the two regimes from one policy class, with the review side resolved only at the lowest wages, up to $10 to $50 an hour. At review shares of 0.1 and 0.3 the answer is the automated one with a later break-even.

What the cap does under review is mostly not to run the agent. At $5 and $10 an hour, every fold under review at 0.5 chooses one attempt cut at 5 calls, which spends a few cents, submits nothing for review, and hands the task to the outside option. At higher wages most folds cut a single attempt at 20 to 90 calls, so that the long attempts, which are the least likely to succeed, are never reviewed; a few still cut at 5 calls, and at the top of the sweep some of GPT-5's and Kimi K2's folds keep two to four capped attempts. An exploratory comparison that the plan did not register makes the point sharper. Across the wage sweep under review at 0.5, the best capped policy costs between 3.7 percent less and 3.5 percent more than sending every task to the outside option without running the agent, and a single attempt without a cap costs a median of 6 percent more than escalating everything. At a review price of half the outside option, the agent on this benchmark is worth about nothing, and the cap's registered saving is the saving of submitting less for review.

## 7.3 Schedules

Letting the cap vary by attempt adds nothing measurable. With an automated verifier the schedule's margin over the constant cutoff at $100 an hour runs from −0.10 to +0.19 dollars per task, a median of zero, and at $300 from −0.08 to +0.60; its interval includes zero for every configuration at every rate at which it is computed. Under review at 0.5 the margin is zero at all three wages for every configuration, since the folds choose few attempts and cut them alike; at 0.1, where the folds retry, it runs from −0.64 to +0.31 at $300 in point estimate. The search starts from the best constant cutoff and moves only when a move pays on the training folds, so on those folds the schedule is never worse; the moves it finds do not carry to held-out tasks.

## 7.4 Execution state and the primary transfer

The primary transfer is the state rule's margin over the best schedule, step iii-b minus the rule, with its two models fitted on the other six configurations. Table 5 and Figure 2 give it with an automated verifier.

![Figure 2](figures/fig2_transfer.pdf)

> **Figure 2. The state rule against the best schedule, automated verifier.** Step iii-b minus the state rule, as a share of what retrying without a cap costs, for the rule fitted on the other six configurations (solid) and on the configuration itself (dashed), and for not capping at all (dotted). Points are 95 percent intervals for the transferred rule at $25, $100 and $300 an hour, from 100 replicates that refit every model. Where the lines coincide the rule is not stopping attempts. † Imputed price.

Table: **Table 5. The primary transfer.** Step iii-b minus the state rule fitted on the other six configurations, automated verifier, dollars per task, with 95 percent intervals from 100 replicates that refit the rule's models and the schedule inside each. The last two columns, at $100 an hour, give the same margin for the rule fitted on the configuration itself, and how far the transferred rule sits from retrying without a cap. † Imputed price.

| Configuration | $25 | $100 | $300 | Within, $100 | Transferred minus ii |
|---|---|---|---|---|---|
| GPT-5 | 0.09 [−0.005, 0.25] | 0.38 [0.07, 1.61] | 1.13 [0.22, 4.82] | 0.38 | 0.000 |
| GPT-5.2 | 0.01 [−0.05, 0.11] | −0.01 [−0.05, 0.45] | −0.02 [−0.10, 1.52] | −0.01 | 0.000 |
| Sonnet 4 | 0.00 [−0.11, 0.07] | 0.11 [−0.003, 0.32] | 0.08 [0.01, 0.73] | 0.11 | 0.000 |
| Sonnet 4.5 | 0.00 [−0.11, 0.15] | 0.05 [−0.02, 0.66] | 0.15 [−0.02, 2.49] | 0.05 | 0.000 |
| Gemini 3 Pro | 0.00 [−0.09, 0.08] | 0.12 [−0.04, 0.60] | 0.36 [−0.03, 2.68] | 0.12 | 0.000 |
| Kimi K2 | 0.03 [−0.11, 0.14] | 0.45 [−0.27, 1.39] | 1.44 [−0.11, 4.32] | 0.45 | 0.000 |
| Qwen3 Coder† | 0.06 [−0.09, 0.53] | 0.74 [−0.26, 1.74] | 1.74 [−0.23, 4.76] | 0.74 | 0.000 |

At the three wages with intervals, the transferred rule never loses to the schedule by more than two cents, and its margin is resolved in three cells: GPT-5 at $100 and $300 an hour, and Sonnet 4 at $300. The median margin is $0.01, $0.12 and $0.36 per task at the three wages. The last column says why. At $100 and $300 the transferred rule costs exactly what retrying without a cap costs, to three decimals, for every configuration: it does not stop attempts. Its margin over the schedule is therefore step ii minus step iii-b, the cost the schedule pays out of sample for having been chosen from data. The rule fitted on the configuration itself behaves the same way with an automated verifier. With the outside option worth tens of dollars and an attempt costing one, the fitted chance of success would have to fall to a few percent before stopping paid, and the models rarely predict that.

Under review the rule does stop attempts, and there the two fits part (Figure A2). Fitted on the configuration itself, the rule beats the best schedule at $100 an hour for GPT-5.2, by $1.01, and Kimi K2, by $1.20, and loses for the other five, by $0.33 to $2.87. Fitted on the other six configurations, it loses for all seven, by $0.75 to $3.33. What an execution's state says about its chances carries across configurations only as far as saying that it will probably finish, which with an automated verifier is all the rule needs to know. When the decision turns on which attempts to submit for an expensive review, the models fitted elsewhere do not carry what is needed.

Synthetic attempts whose optimal restart policy can be computed exactly show which way the rule errs (Appendix E). Where the rule's own state determines the attempt's prospects, the optimum stops 29 to 65 percent of first attempts with an automated verifier, at 8 to 42 calls on average, while the fitted rule stops 42 to 78 percent at 5 to 10 calls. The rule costs 7 to 32 percent more than the optimum with an automated verifier, and under review at 0.5 it costs 7 to 14 percent more at the two higher outside options and the same at the lowest, where both escalate almost at once; and in three of the six automated settings it costs more than the best constant cutoff. The bias toward restarting that the commit-to-termination approximation introduces outweighs the opposite pull of its restart values.

## 7.5 Switching configurations

After a failed attempt an operator can retry the same configuration or switch to another. Figure 3 and Table 6 compare the best cascade with the best single configuration chosen from the same training folds, on the 275 tasks with four usable draws in all seven configurations.

![Figure 3](figures/fig3_cascade.pdf)

> **Figure 3. Switching configurations.** The best cascade (blue), the best single configuration chosen from the same training folds (orange) and each configuration's own schedule (grey), as a share of the cost of escalating every task, on the 275 tasks with four usable draws in all seven configurations. Escalating every task is an exploratory reference. † Imputed price.

Table: **Table 6. Switching configurations.** Dollars per task on the 275 common tasks. Switching saves: the best single configuration chosen on the training folds minus the cascade, with a 95 percent interval from 100 replicates where computed. Best own in hindsight: the cheapest configuration's own schedule, cross-fitted, and which configuration that is. Escalate all: every task sent to the outside option without running the agent, an exploratory reference not in the registration. † Imputed price.

| Regime | $/h | Best single | Cascade | Switching saves | Best own in hindsight | Escalate all |
|---|---|---|---|---|---|---|
| Automated | 25 | 6.42 | 5.98 | 0.44 [−0.27, 1.36] | 6.42 (GPT-5) | 12.51 |
| Automated | 100 | 21.97 | 19.94 | 2.03 [−2.22, 5.59] | 20.99 (Sonnet 4) | 50.05 |
| Automated | 300 | 61.36 | 56.01 | 5.35 [−8.30, 17.95] | 58.56 (Sonnet 4) | 150.16 |
| Review 0.1 | 100 | 30.29 | 28.35 | 1.95 | 29.56 (GPT-5.2) | 50.05 |
| Review 0.3 | 100 | 39.19 | 39.19 | 0.00 | 39.19 (GPT-5.2) | 50.05 |
| Review 0.5 | 100 | 48.84 | 48.84 | 0.00 | 48.84 (GPT-5.2) | 50.05 |

With an automated verifier, switching lowers cost by 6.8 percent at $25 an hour, 9.2 percent at $100 and 8.7 percent at $300 in point estimate, but every interval includes zero. Against the configuration that proves cheapest in hindsight, Sonnet 4 at $100 and $300, the cascade is 5 percent cheaper at $100 and 4 percent at $300; against the best configuration an operator could have picked from the same data, it is 9 percent cheaper. The cascades the folds build rely mainly on two configurations: removing GPT-5.2 raises the cascade's cost at $100 by $1.48 and removing Sonnet 4 by $0.96, while removing any of the other five changes it by less than $0.16. Under review at 0.3 and 0.5 at $100 an hour the best policy is a single configuration, GPT-5.2, with one capped attempt, and switching adds nothing, while at the highest wages under review the cascade chosen from data costs slightly more than the best single configuration; at 0.1 switching saves 6 to 9 percent in point estimate at $100 to $300.

Switching pays only where failures do not coincide, and here they mostly do. Across the 275 common tasks, the share of a configuration's draws that resolve is correlated with another configuration's at 0.62 to 0.90, a median of 0.81 (Figure A1). The two configurations that stand apart are Sonnet 4 and Qwen3 Coder, the two run under the oldest harness versions, which correlate with the other five at 0.62 to 0.74 and with each other at 0.85.

## 7.6 Sensitivities

Nine registered sensitivities change one input each and rerun the ladder, the break-even and the cascade with every choice redone (Appendix A); the cap stated in dollars rather than calls, which the plan also registers as a sensitivity, is reported with the comparators (Appendix B). None changes the pattern of the primary result, although individual cells move. With an automated verifier the first break-even stays between 1.8 and 8.8 median attempt costs under every sensitivity, and its median across configurations between 2.1 and 5.0. False accepts raise it most, to a median of 3.8 at \(\phi = 0.34\) and 5.0 at \(\phi = 0.50\), because a success cut off by the cap then costs less: part of its value was never real. No cell of any sweep, under any sensitivity, resolves the cap as a cost. The only crossings with both sides resolved come under the common 100-call horizon, two with an automated verifier and two under review at 0.1, and each runs from saving to exactly zero, where no fold chooses a cap that binds.

Under review at 0.5 the cap still saves across the whole sweep for every configuration under the false-accept and price sensitivities, and when refusals are excluded or evaluations without a verdict are counted as failures. False accepts raise that saving from a median of $1.85 per task at $100 an hour to $10.20 at \(\phi = 0.34\) and $13.69 at \(\phi = 0.50\), since every patch the cap keeps from review now also carries part of an outside option that will be paid later. Under the other four, the saving turns high in the sweep for one to three configurations: between 11.6 and 49 median attempt costs under the bucket-specific correction to the annotated times, which raises the shortest tasks' outside option about eightfold; at 41 and 58 under the common horizon; at 46 and 136 when every task that can fill a policy is scored; and at 272 when re-runs are dropped. As everywhere else, the costing side is unresolved.

Switching keeps its sign: with an automated verifier at $100 an hour it saves between $1.00 and $5.48 per task under every sensitivity, most under the annotation correction and the common horizon. The two-stage bootstrap, which resamples each task's attempts as well as the tasks, gives intervals for the cap's margin of about the same width as the task-level bootstrap, a median ratio of 1.02, and centred in the same place at the median, though individual cells shift. GPT-5's transfer margin stays resolved at $100 and $300 an hour under it; Sonnet 4's at $300 does not.
