# 0020. Multi-legs are corrected by picking the operation type

- **Date:** 2026-10-19
- **Status:** accepted (extends 0011 to tab 1)

## Context

In many multi-legs the aggressiveness does not tell which leg was bought: a leg falls in the dead zone, both legs come out on the same side (the real data has "buy-buy" and "sell-sell" verticals and diagonals), or the grouping is questionable. In a multi-leg, correcting only "bull/bear", as the specification says for single-legs, is not enough to know each leg's side or the destination.

## Decision

- In tab 1, a multi-leg is corrected with the same **operation type selector** as in tab 2 ([0011](0011-manual-leg-operation-type.md)): bull call, bear put, straddle, "don't know"… The type sets each leg's side.
- Until it is corrected, a vertical or diagonal with an undetermined leg, or with **both legs on the same side**, goes to **undetermined multi-leg**.
- Single-legs are still corrected with bull, bear or undetermined.

## Rejected alternatives

- **Only bull/bear for multi-legs**: the destination would be approximate.
- **Multi-legs not editable**: questionable groupings would have no fix.

## Consequences

The rules and the catalogue are in the [business rules](../business-rules.md#manual-corrections).
