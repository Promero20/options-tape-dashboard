# 0001. Operations are rebuilt from level 2

- **Date:** 2026-10-15 (specification)
- **Status:** accepted

## Context

Every day the capture pipeline leaves a `nivel3_operaciones_YYYYMMDD.csv` with the operations already grouped, but that file has changed format with each version of the script: the oldest ones have no strike, no expiration and no threshold filter. Besides, it has no per-leg detail, which the dashboard needs in order to classify.

## Decision

The dashboard rebuilds the operations from `nivel2_trades_*.csv` (plus the level-1 price), with the same code that produces level 3. The level-3 CSV is only used to check that the reconstruction matches.

## Rejected alternatives

- **Reading level 3 as it is**: it means supporting every historical format, and it gives no per-leg detail.

## Consequences

- Every day ends up in the current format and with per-leg detail.
- A day without level 2 cannot be rebuilt (see [0009](0009-discard-2026-09-22.md)).
