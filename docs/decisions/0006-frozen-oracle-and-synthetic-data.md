# 0006. Regression testing with a frozen copy of the script and synthetic data

- **Date:** 2026-10-16
- **Status:** accepted

## Context

The script's refactor must not change its output (specification). It needs something to compare against:

- The original in the data folder will be replaced as soon as the new version is deployed.
- The stored level-3 CSV files do not work for every day: several were produced by earlier versions of the script.
- Real data cannot be committed, and on GitHub there is no data to test with.

## Decision

- **Oracle**: a frozen copy of the 01/10/2026 version in `tests/legacy/`, protected by a SHA-256 test and excluded from git's line-ending conversion. It is not a second logic: only the tests use it. When the repository was published, one comment in that copy (about where the column names come from) was generalised; before pinning its new hash, its output (CSV and console) was checked to be identical to the original's on the 14 real captures and the 5 synthetic variants.
- **Real data**: the test runs the legacy and the new script on every day with level 2 and requires the CSV and the console message to be byte-for-byte identical. It is skipped if the data folder is not found.
- **Synthetic data**: a scenario generated in code (no CSV is committed) that covers the script's cases and the known schema variants. It always runs, on GitHub too.

## Rejected alternatives

- **Stored "golden" outputs**: derived from real data, so they cannot be committed, and if they are lost the oracle is lost.
- **Comparing only with the stored level-3 files**: only those produced by the current version match.

## Consequences

- The dashboard always uses the real data; synthetic data only exists inside the tests.
- If the script's output is changed on purpose, the test has to prove that this is the only change. For cancellations ([0015](0015-drop-cancellations.md)) this was done by transforming the oracle's input, without freezing a new version.
