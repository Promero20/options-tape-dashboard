# 0012. Multi-legs with an anomalous size ratio are flagged

- **Date:** 2026-10-16
- **Status:** accepted

## Context

The 50 ms cross with the same Trade Condition, combined with union-find, can join prints that only coincide by chance. In the real data there are "diagonals" with one leg of thousands of contracts and another of a few dozen: they are unlikely to be a single order.

## Decision

The grouping is not changed (single grouping logic). The list visually flags multi-leg operations whose largest leg has **10 times or more** the contracts of the smallest, so the user can review them and, if needed, correct their type.

The cutoff comes from the data: multi-legs above the threshold have ratios from 1 to 5.9 (real ratio spreads rarely go beyond 1:3), and then jump to 11.9, 21.9, 30 and up to more than 300.

## Rejected alternatives

- **Splitting those groups automatically**: it would be a second grouping logic.

## Consequences

It is a visual aid; it does not change the classification on its own. In the captures analysed, 9 operations above the threshold are flagged.
