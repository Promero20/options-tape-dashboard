# 0031. Positions: their own file, closes per leg, and P&L on the net premium

- **Date:** 2026-11-09
- **Status:** accepted (completes the specification); amended by [0033](0033-positions-links-commissions-and-closes.md)

## Context

Tab 3 records the user's real positions, entered by hand for now, and the specification asks for a model that a later read-only import can feed without redoing the tab. It asks for P&L in $ and %, but not for the base of the percentage, and it lists "closing date and price per leg" without saying whether legs can close on different days or how commissions count.

## Decision

- **Own SQLite file**, `positions.sqlite`, in the user-data folder, separate from `edits.sqlite`. They are different kinds of data, and an import must not touch the manual edits. Every write is one transaction and validates first.
- **Ready for an import**: each position has a `source` (`manual` for now) and an optional `external_id`, unique per source, so an imported position can be recognised instead of duplicated. The tab only reads from the store.
- **Each leg closes whole, with its own date and price**, and legs can close on different days. A position moves to the history once all its legs are closed, and its closing date is that of the last leg. To close part of a leg, the leg is split in two when the position is entered or edited.
- **P&L of a leg**: (exit − entry) × quantity × 100, with the sign reversed if it was sold. Standard option contracts only.
- **Commissions** are one total per position, opening and closing included, and the P&L is net of them.
- **P&L in %**: net P&L over the absolute net premium at the opening, that is, the debit paid or the credit received. If that premium is 0, no percentage is shown.
- **Days in the position** are calendar days from the opening to the last close.

## Rejected alternatives

- **The same file as the manual edits**: nothing relates them, and a failed import would put the edits at risk.
- **Closes with their own quantity**: closer to real fills, but more form and code for a case that splitting the leg already covers. An import may bring it back.
- **One closing date per position**: it cannot represent legging out.
- **Percentage on the gross premium of all legs**: it is never 0, but it understates spreads: a spread opened with legs of 5.00 and 3.00 that gains 1.00 would show +12.5% instead of +50%.

## Consequences

- Open positions have no P&L: there are no live prices, and level 1 only covers each day's candidate contracts.
