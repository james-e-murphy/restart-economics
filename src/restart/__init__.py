"""Restart economics: policy evaluation for agent executions.

Module map, in dependency order:

    acquire      list the dataset on Hugging Face, stream each archive through the extractor,
                 verify its checksum against the one Hugging Face records
    extract      read the raw trajectory archives into an execution table and a prefix table,
                 carrying physical quantities only, plus the archive checksum
    audit        builds configurations.csv from the extraction audits and the hand-kept notes
    pricing      a pure function from physical quantities and a dated schedule to dollars,
                 kept separate from everything else so a price change never touches a policy
    policies     the policy classes as data: single attempt, retry without cutoff, constant cutoff,
                 attempt-indexed schedule, cross-configuration schedule
    evaluate     the enumerating evaluator: policy value by replay over attempt orderings
    inference    outer task folds, cross-fitting, the full-pipeline bootstrap
    schedules    step iii-b, the schedule of cutoffs searched on the training folds
    state        the receding-horizon restart rule and the two models it reads the state with
    ladder       steps i to iv and the transfer across the rate sweep and every verifier regime
    breakeven    the rates at which the cap's marginal value changes sign
    cascade      step v, switching configurations, and the outcome correlation
    sensitivity  the registered sensitivities and the two-stage bootstrap
    comparators  the dollar cutoff, the threshold comparator, the universal schedule, first look
    oracle       the sample oracle benchmark
    appendix     the difficulty display, the distribution of cost per task, the spread
    diagnostics  the within-task variance share, mixed outcomes and tail composition
    coverage     the synthetic check that the primary interval covers at its nominal rate
    dynamic      the synthetic check of the state rule against the exact dynamic program

acquire, extract, audit and pricing are tested against a synthetic archive with the schema of the
real release; everything else against costs worked out by hand, brute-force searches on small
cases, and synthetic populations whose answers are known.
"""

__version__ = "0.1.0.dev0"
