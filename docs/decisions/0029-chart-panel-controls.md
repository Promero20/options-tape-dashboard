# 0029. Chart panel: one shared date range, last month by default, and an underlying selector

- **Date:** 2026-10-26
- **Status:** accepted (amends the specification)

## Context

The specification gives each of the two charts its own date-range selector, independent of the list, and sets the underlying from the row selected in the list. Two things weigh on that: the two charts are two views of the same flow, and in the real data the median underlying has two operations in the whole period, so a single capture usually draws one bar.

## Decision

- **One date-range selector for both charts**, independent of the list, with the same presets (today, last week, last month, custom; [decision 0008](0008-ranges-by-capture-date.md)). Switching between the net and walls tabs keeps the period.
- **Last month by default.** The list still starts at today.
- **The underlying** is set by selecting a row in the list, as the specification says, and can also be picked from a drop-down with the underlyings that have operations in the chart range, each with its count.
- **The reference price** is the underlying's price in the latest capture up to the end of the chart range whose level 1 includes it, and is shown with its date. Level 1 lists an underlying only on days it has candidates, so the price can be a few days old.
- The charts use the same operations as the list: above the threshold, with manual edits applied, each operation once and without pending ones ([business rules](../business-rules.md#6-charts)). They refresh after Reload and after a correction is saved.

## Rejected alternatives

- **One selector per chart**, as the specification says: more controls, and two views of the same flow that could silently show different periods.
- **Today by default**: most underlyings would show a single bar.
- **Row selection only**: to see an underlying that is not in the list's range, the user would have to change the list first.

## Consequences

- The chart range and the list range are independent: the list can show today while the charts show the month.
