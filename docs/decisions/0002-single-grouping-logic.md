# 0002. A single grouping logic

- **Date:** 2026-10-15 (specification)
- **Status:** accepted

## Context

If the dashboard grouped trades with its own code, sooner or later it would drift from the script the capture pipeline uses, and the dashboard's operations would no longer be the same as level 3's.

## Decision

The dashboard imports the functions of `nivel3_agrupar.py` and does not reimplement them. To make that possible, the script is refactored (without changing its output) to expose the per-leg calculation, the operation ID and the separation between grouping and threshold filter.

## Rejected alternatives

- **Reimplementing the grouping in the dashboard**: two logics to maintain in parallel.
- **Running the script as a process and reading its CSV**: no access to per-leg detail, and no way to apply edits before the filter.

## Consequences

- Any change to the grouping affects the pipeline and the dashboard at the same time.
- The refactor requires a byte-for-byte regression test (see [0006](0006-frozen-oracle-and-synthetic-data.md)).
