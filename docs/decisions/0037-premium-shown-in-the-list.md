# 0037. The list shows the premium of the charts

- **Date:** 2026-11-19
- **Status:** accepted

## Context

The operations list showed each operation's gross premium: the sum of the premium of every leg. The charts use the classification's premium ([business rules](../business-rules.md#rules-in-order-of-precedence)): for a debit vertical, bought − sold; for a credit vertical, sold − bought. For a bull call spread with 1.5M bought and 0.4M sold, the list said 1.9M and the chart 1.1M.

## Decision

- **The Premium (M) column shows the classification's premium, without its sign**: net for verticals and diagonals, the total for single-legs, and gross for undetermined multi-legs and discarded operations. It is the same amount as in the charts and in the selected operation's panel. The Direction column gives the sign, and sorting by premium keeps the largest operations first, bullish or bearish.
- **A new optional column, Gross premium (M)**, hidden by default, keeps the sum of every leg. The threshold applies to it, so a spread can be listed with a net premium below its bracket's threshold.
- A manual correction changes the classification, and so the premium shown.

## Rejected alternatives

- **The signed premium, as on the net chart**: sorting by premium would send bearish operations to the bottom, and walls are positive on their chart anyway.
- **Dropping the gross premium**: without it, a listed spread below the threshold would look like an error.

## Consequences

- The default order of the list changes: spreads move down.
- Saved column layouts keep working: the column keeps its identifier.
- The positions tab still shows the gross premium of the operations linked to a position.
