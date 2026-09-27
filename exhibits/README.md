# Exhibits

One script regenerates every figure and table in the paper from the files in `results/`:

    python exhibits/make.py          # writes exhibits/out/; needs matplotlib

It computes no policy value. It reads what the evaluator wrote, reshapes it and draws it, so every
number in an exhibit can be found in a results file and traced to the command that wrote that file
(`results/README.md`). Figures are written as PDF for the manuscript and PNG for reading, tables as
Markdown, LaTeX and CSV. With `--bare` the figures are drawn without their titles and notes,
which the manuscript carries in its captions; the paper's build uses that (`paper/README.md`).

## Main text, as PLAN.md Section 7 names them

| file | in the paper | what it shows |
|---|---|---|
| `fig1_ladder` | Figure 1 | the ladder drawn: steps i to iv and the transferred rule, each as a share of one attempt's cost, per configuration and as the median, at $25, $100 and $300 an hour, automated verifier and review at 0.5 H; the primary result and the primary transfer are two of its steps |
| `fig2_cap_margin` | Figure 2 | the primary result: the cap's marginal value given retry, step ii minus step iii, across the sweep in every regime, per configuration and as the median |
| `fig3_transfer` | Figure 3 | the primary transfer: the state rule's margin over the best schedule, fitted on the other six configurations and on the configuration itself, automated verifier |
| `fig4_cascade` | Figure 4 | the best cross-configuration schedule against each configuration's own, and against the best single configuration chosen from the same data |
| `table_retry` | Table 3 | the value of retry, step i minus step ii, with its interval, and the share of tasks one attempt and the chosen budget resolve |
| `table2_breakeven` | Table 4, condensed | the break-even, the summary statistic of the primary result, per configuration and regime, in dollars an hour and in multiples of the median attempt cost |
| `table1_ladder` | Table 5 | policy value by configuration for steps i to iii-b at $25, $100 and $300 an hour, with the cap's margin, its interval, what the folds chose, the share each step resolves and the first break-even |
| `table3_transfer` | Table 6 | the primary transfer with its intervals, and how far the transferred rule sits from retrying without any cap; the paper sets its table from `results/ladder.csv` directly |

Tables 1, 2 and 7 are written in the manuscript's text: the configurations, the policies, and switching.

## Appendix

| file | in the paper | what it shows |
|---|---|---|
| `figA1_transfer_review_05` | Figure A1 | the transfer figure under review at 0.5 H, where the rule does stop attempts |
| `figA2_outcome_correlation` | Figure A2 | the seven-by-seven correlation of outcomes, the portfolio predictor of whether a cascade pays |
| `figA3_tail_composition` | Figure A3 | what a cutoff at each decision point would cut from attempts that go on to resolve, with where the annotated outside option falls on the grid |
| `tableA1_sensitivity_breakeven` | Table A1 | the break-even under each registered sensitivity beside the primary: per regime, how many configurations cross in the sweep, and the first crossing's median and range |
| `tableA2_sensitivity_margins` | Table A2 | the primary margins under each registered sensitivity, as medians across configurations: the cap's saving in both headline regimes, the primary transfer, and switching |
| `tableA3_two_stage` | Table A3 | the two-stage bootstrap interval beside the primary task-level one, for the cap's saving and the primary transfer |
| `tableA4_comparators` | Table A4 | the dollar cutoff, the threshold comparator, the universal schedule and the first-look rule, automated verifier, with intervals |
| `tableA5_oracle` | Table A5 | the sample oracle benchmark against the best cascade and single configuration |
| `tableA6_difficulty` | Table A6 | the cap's saving by difficulty bucket, every policy choosing within the bucket |
| `tableA7_distribution` | Table A7 | the median and 95th percentile of cost per task, and the median-cost version of the primary comparison |
| `tableA8_spread` | Table A8 | the spread across configurations against the spread across policies |
| `tableA9_diagnostics` | Table A9 | within-task share of log-spend variance, mixed outcomes, attempts past their outside option |
| `tableA10_ladder_review` | Table A10 | `table1_ladder` under review at 0.1 and 0.3 H |
| `tableA11_crossings` | Table A11 | every crossing of the cap's margin over the sweep, with the sign on each side and where the interval is clear of zero |

Each appendix exhibit is written when `results/` holds the file its command writes, and skipped
otherwise.

## Not registered

Everything below is marked as exploratory in its title or caption, and computed after the
registered results were in.

- `fig5_break_even_in_attempts` (the paper's Figure 5), and the column of `table2_breakeven` headed
  "in full attempts\*": the first break-even re-expressed in full attempts, tokens plus review,
  `M / (1 + f M)`.
- The dotted line in `fig2_cap_margin`, and the last column of `table2_breakeven`: the outside
  option above which retrying without a cap first costs less than escalating every task.
- `value_escalate` wherever it appears: every task sent straight to the outside option.

Qwen3 Coder's dollar figures rest on an imputed price and carry a dagger wherever they appear.
