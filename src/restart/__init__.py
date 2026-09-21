"""Restart economics: policy evaluation for agent executions.

Module map, in dependency order:

    acquire    list the dataset on Hugging Face, stream each archive through the extractor,
               verify its checksum against the one Hugging Face records
    extract    read the raw trajectory archives into an execution table and a prefix table,
               carrying physical quantities only, plus the archive checksum
    audit      builds configurations.csv from the extraction audits and the hand-kept notes
    pricing    a pure function from physical quantities and a dated schedule to dollars,
               kept separate from everything else so a price change never touches a policy
    policies   the policy classes as data: single attempt, retry without cutoff, constant cutoff,
               attempt-indexed schedule, cross-configuration schedule
    evaluate   the enumerating evaluator: policy value by replay over attempt orderings
    state      the receding-horizon restart rule and the two models it reads the state with
    inference  outer task folds, cross-fitting, the full-pipeline bootstrap
    ladder     the ladder of steps i to iii across the rate sweep and both verifier regimes

Every module is implemented. acquire, extract, audit and pricing are tested against a synthetic
archive with the schema of the real release; policies, evaluate, state, inference and ladder
against costs worked out by hand and a synthetic dry run whose answers are known. The plan is
frozen and registered, so quantities indexed by a cutoff, an attempt budget, an outside-option rate
or a verification cost may now be computed; see README working rule 1. Steps iii-b and v, the
schedule search and the cascade, are the remaining policy classes.
"""

__version__ = "0.1.0.dev0"
