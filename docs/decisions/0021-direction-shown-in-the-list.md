# 0021. The list shows the classification's direction

- **Date:** 2026-10-19
- **Status:** accepted

## Context

The script computes `direccion` from the leg with the most premium only. Sometimes that does not match the destination: a multi-leg with an undetermined leg can come out as "bull" and still go to undetermined.

## Decision

The list's "direction" column is the one that results from the classification, consistent with the destination, and it is the one the user edits. The script's `direccion` is kept as a secondary column.

## Rejected alternatives

- **Showing the script's**: the destination would not match the direction on screen.

## Consequences

The two columns can differ. The difference is informative, not an error.
