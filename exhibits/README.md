# Exhibits

One script regenerates every figure and table in the paper from the files in `results/`:

    python exhibits/make.py          # writes exhibits/out/; needs matplotlib

It computes no policy value. It reads what the evaluator wrote, reshapes it and draws it, so every
number in an exhibit can be found in a results file and traced to the command that wrote that file
(`results/README.md`). Figures are written as PDF for the manuscript and PNG for reading, tables as
Markdown, LaTeX and CSV. With `--bare` the figures are drawn without their titles and notes,
which the manuscript carries in its captions; the paper's build uses that (`paper/README.md`).

## Main text, as PLAN.md Section 7 names them

| file | what it shows |
|---|---|
| `fig1_cap_margin` | the primary result: the cap's marginal value given retry, step ii minus step iii, across the sweep in every regime, per configuration and as the median |
| `fig_ladder` | the ladder drawn: steps i to iv and the transferred rule, each as a share of one attempt's cost, per configuration and as the median, at $25, $100 and $300 an hour, automated verifier and review at 0.5 H; the table of policy values in a picture |
| `fig2_transfer` | the primary transfer: the state rule's margin over the best schedule, fitted on the other six configurations and on the configuration itself, automated verifier |
| `fig3_cascade` | the best cross-configuration schedule against each configuration's own, and against the best single configuration chosen from the same data |
| `table1_ladder` | policy value by configuration for steps i to iii-b at $25, $100 and $300 an hour, with the cap's margin, its interval, what the folds chose and the first break-even |
| `table2_breakeven` | the break-even, the summary statistic of the primary result, per configuration and regime, in dollars an hour and in multiples of the median attempt cost |
| `table3_transfer` | the primary transfer with its intervals, and how far the transferred rule sits from retrying without any cap |

## Appendix

| file | what it shows |
|---|---|
| `figA1_transfer_review_05` | the transfer figure under review at 0.5 H, where the rule does stop attempts |
| `figA2_outcome_correlation` | the seven-by-seven correlation of outcomes, the portfolio predictor of whether a cascade pays |
| `tableA1_sensitivity_breakeven` | the break-even under each registered sensitivity beside the primary: per regime, how many configurations cross in the sweep, and the first crossing's median and range |
| `tableA2_sensitivity_margins` | the primary margins under each registered sensitivity, as medians across configurations: the cap's saving in both headline regimes, the primary transfer, and switching |
| `tableA3_two_stage` | the two-stage bootstrap interval beside the primary task-level one, for the cap's saving and the primary transfer |
| `tableA4_comparators` | the dollar cutoff, the threshold comparator, the universal schedule and the first-look rule, automated verifier, with intervals |
| `tableA5_oracle` | the sample oracle benchmark against the best cascade and single configuration |
| `tableA6_difficulty` | the cap's saving by difficulty bucket, every policy choosing within the bucket |
| `tableA7_distribution` | the median and 95th percentile of cost per task, and the median-cost version of the primary comparison |
| `tableA8_spread` | the spread across configurations against the spread across policies |
| `tableA9_diagnostics` | within-task share of log-spend variance, mixed outcomes, attempts past their outside option |
| `figA3_tail_composition` | what a cutoff at each decision point would cut from attempts that go on to resolve, with where the annotated outside option falls on the grid |

Each appendix exhibit is written when `results/` holds the file its command writes, and skipped
otherwise.

## Not registered

Everything below is marked as exploratory in its title or caption, and computed after the
registered results were in.

- `fig4_break_even_in_attempts`, and the column of Table 2 marked with an asterisk: the first
  break-even re-expressed in full attempts, tokens plus review, `M / (1 + f M)`.
- The dotted line in Figure 1, and the last column of Table 2: the outside option above which
  retrying without a cap first costs less than escalating every task.
- `value_escalate` wherever it appears: every task sent straight to the outside option.

Qwen3 Coder's dollar figures rest on an imputed price and carry a dagger wherever they appear.
