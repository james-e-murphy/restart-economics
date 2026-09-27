# Licensing, to settle before the repository is made public

Two questions, both open until checked:

1. **Code and text.** MIT for `src/` and `tests/`, in `LICENSE`. CC BY 4.0 for PLAN.md, AUDIT.md and
   audit_record.md: that is the license the OSF registration of 20 September 2026 was submitted under,
   and it covers the copies of those files attached there, so it stands. Settled 27 September 2026:
   the manuscript and its sources in `paper/` are all rights reserved, matching the author's other
   working papers; the manuscript was never part of the registration, so nothing already granted
   changes.

2. **Derived tables.** `data/derived/` holds execution and prefix tables computed from the Bai et al.
   release. Confirm that release's license permits redistributing derived tables before publishing
   them. If it does not, the repository ships the extraction code and the archive checksums, and a
   reader reproduces the tables locally; the paper says so. This is checked as part of audit item 6,
   not after the fact.

   Audit item 6 found no license in Hugging Face's metadata for the release (19 September 2026), so
   the tables are not committed (`.gitignore`). Before the repository is made public, read the
   dataset card itself for any license or terms, and ask the authors if none is stated.

SWE-bench Verified task metadata, including the human time-to-fix annotations used for the outside
option, comes from the SWE-bench release and carries its own terms.
