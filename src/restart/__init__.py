"""Restart economics: policy evaluation for agent executions.

Module map, in dependency order:

    acquire    list the dataset on Hugging Face, stream each archive through the extractor,
               verify its checksum against the one Hugging Face records
    extract    read the raw trajectory archives into an execution table and a prefix table,
               carrying physical quantities only, plus the archive checksum
    audit      builds configurations.csv from the extraction audits and the hand-kept notes
    pricing    a pure function from physical quantities and a dated schedule to dollars,
               kept separate from everything else so a price change never touches a policy
    policies   the policy classes: single attempt, retry without cutoff, constant cutoff,
               attempt-indexed schedule, cross-model schedule, receding-horizon state rule,
               two-parameter threshold comparator
    evaluate   the enumerating evaluator: policy value by replay over attempt orderings
    inference  outer task folds, full-pipeline bootstrap, transfer cells

acquire, extract, audit and pricing are implemented and tested against a synthetic archive with the schema
of the real release. policies, evaluate and inference are stubs until the plan is
frozen. Nothing here computes a quantity indexed by a cutoff, an attempt budget, an
outside-option rate, or a verification cost until then; see README working rule 1.
"""

__version__ = "0.1.0.dev0"
