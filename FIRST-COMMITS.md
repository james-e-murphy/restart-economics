# Initializing the repository

Run these from the project folder when the audit closes. The first commit holds the plan with the
audit's findings, the protocol, the audit record, the code and the checksums, and it is tagged
`plan-frozen` before any policy result exists.

    git init -b main
    git add -A --dry-run          # check the list: no .tar.gz, nothing under data/derived/<archive>/
    git add -A
    git commit -m "Audit closed; plan frozen with audit findings recorded"
    git tag plan-frozen

    git remote add origin git@github.com:<you>/restart-economics.git
    git push -u origin main --tags

Keep the repository **private** until the paper is posted, then make it public with the history
intact. The history is the record that the plan came before the results, and is worth more
unrewritten.

## After the freeze

Nothing in `exhibits/` is committed before the `plan-frozen` tag. After it, a departure from
PLAN.md is a deviation with an entry in AUDIT.md, committed on its own with a message naming it,
not an edit to the plan.

## What never enters the repository

The raw `.tar.gz` archives, the derived tables under `data/derived/<archive>/` (the release records
no license; see LICENSE-NOTE.md), extraction intermediates, and anything containing trajectory
text. `.gitignore` covers these paths; check the dry run before the first commit anyway, since a
large file committed once stays in the history for good.
