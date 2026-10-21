# 0007. The operation ID includes the Trade Condition

- **Date:** 2026-10-16
- **Status:** accepted (amends the specification)

## Context

The specification proposed `YYYYMMDD-SYMBOL-HH:MM:SS.mmm` (date and time of the first trade). In the real data that format is not unique: different groups start on the same contract and millisecond with different Trade Conditions (e.g. AUTO and ISOI). It happens on almost every captured day, sometimes on operations above the threshold. Manual edits would point to the wrong operation.

## Decision

`YYYYMMDD-SYMBOL-HH:MM:SS.mmm-TC`, where `TC` is the operation's Trade Condition. It is computed by `id_operacion()` in `pipeline/nivel3_agrupar.py`.

It is unique within a capture by construction: both grouping mechanisms only join trades with the same condition, so all the rows of an operation share it, and two groups with the same underlying, millisecond and condition would already have been merged.

## Rejected alternatives

- **A numeric suffix on collisions (`-2`, `-3`)**: it depends on the reading order and is not stable.
- **Adding the first trade's contract**: it does not solve the real case, because the collisions are on the same contract.

## Consequences

- The ID changes if the grouping logic changes; those edits would become orphans (see [0003](0003-edits-in-own-files.md)).
- The same operation captured on two days has the same ID in both (see [0010](0010-operation-in-several-captures.md)).
