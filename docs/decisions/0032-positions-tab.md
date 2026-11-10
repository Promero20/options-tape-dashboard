# 0032. Positions tab: link to the operation, form limits, and a chart that follows the filters

- **Date:** 2026-11-09
- **Status:** accepted (completes the specification); amended by [0033](0033-positions-links-commissions-and-closes.md)

## Context

The specification has the linked operation "chosen from the tab 1 list" and asks for the history to be filterable by the source operation's data, so as to measure which signals work. It says nothing about how a position is started from an operation, how many legs the form holds, or what happens to a position whose option has expired.

## Decision

- **Linking**: a "New position" button next to Edit, in the panel of the operation selected in tab 1, opens tab 3 with the form linked to it and with each leg's type, strike, expiration and side. The side is copied only if the classification knows it. Quantity and price are left empty, because the user's are not the operation's. The form also has a drop-down with the operations of that underlying, from every capture, to set or change the link.
- **A form of up to four legs and one underlying per position**, which covers an iron condor. The model keeps the underlying per leg, as the specification says, so that an import is not limited by the form.
- **The chart and the total follow the history's filters.** Filtering by structure or direction shows the cumulative P&L of those positions alone.
- **Open legs past their expiration are only flagged**, in the list and in the warnings banner. They are never closed automatically: an in-the-money option does not expire at 0, so the closing price is the user's to enter.
- **A link to an operation that no longer exists is shown as an orphan** and kept ([decision 0003](0003-edits-in-own-files.md)).
- **Deleting a position** asks for confirmation. The specification does not list it, but a position entered by mistake has to be removable.
- **Form fields have no timed delay.** With one, a Save pressed right after typing read the previous value, and a closing price could be lost without warning. Only the underlying field waits until the user leaves it, because it triggers a search.

## Rejected alternatives

- **Only the drop-down**: every leg would be typed by hand, although the operation already has them.
- **Prefilling quantity and price**: a position mimics an operation at a far smaller size and at another price.
- **Closing expired legs at 0 automatically**: right for an option that expires worthless, wrong and silent for one that does not.

## Consequences

- A position with more than four legs cannot be entered by hand. If an import ever brings one, the form will have to grow first.
