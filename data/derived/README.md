# Derived tables

Written by `python -m restart.acquire`, one folder per archive, `data/derived/<archive>/`, holding that archive's tables and its extraction log. Physical quantities only, no trajectory text, no dollars.

    executions_<config>.csv    one row per task x run: identifiers, iteration count, LLM calls,
                               tokens by class, elapsed time, terminal state (how the attempt
                               stopped), verdict and resolve flag (what the evaluation found),
                               usable flag, source archive checksum, and every input the
                               classifier used: the error string, the run report list the
                               instance appears in, which evaluation files exist, and for
                               evaluation errors the tail of the evaluation log; and from the per-call
                               completion logs, their count and cost, the logs and cost of
                               any earlier tries the harness discarded, and whether the final
                               try's logs cost exactly what the run's metrics record
    prefix_<config>.csv        one row per task x run x iteration: cumulative and incremental
                               physical quantities, condensation indicator where available,
                               source archive checksum

No reconstructed dollars are stored here. Pricing is applied at analysis time by `restart.pricing`
under a dated schedule, so that a price change refits policies rather than rescaling a stored
total. The provider's *logged* per-call cost is carried as `cost_logged` because it is an
observation and the validation target for the pricing function: every schedule is compared with it
on every call, and where they differ the difference is located (`restart.pricing`, audit item 9).

    actions_<config>.csv       one row per task x run: the agent's actions in order, each as an
                               8-character signature of its type and defining arguments; no
                               text. The input to the replicate-divergence diagnostic
    audit_<config>.json        the census AUDIT.md asks for, written by the same pass

Whether these tables may be published depends on the upstream release's license; see
LICENSE-NOTE.md. Until that is settled the directory holds this note only.
