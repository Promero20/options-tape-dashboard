# 0003. Manual edits in the dashboard's own files

- **Date:** 2026-10-15 (specification)
- **Status:** accepted

## Context

The user corrects directions, adds missing legs and records positions. The pipeline's CSV files are the original source and must not be modified.

## Decision

Every manual edit is stored in the dashboard's own files, outside the pipeline's data folder and outside git, and is applied on top of the data at load time. Each edit points to an operation ID. If that ID stops existing (for example, because the grouping logic changed), the edit is shown as an **orphan** for review; it is never silently deleted.

## Rejected alternatives

- **Writing the edits into the pipeline's CSV files**: it mixes captured data with the user's decisions and breaks the read-only rule.

## Consequences

- The operation ID has to be stable and unique (see [0007](0007-operation-id-format.md)).
- The format of the edits store is defined in phase 2 ([0019](0019-edits-store.md)).
