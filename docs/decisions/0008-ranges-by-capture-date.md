# 0008. Range selectors use the capture date

- **Date:** 2026-10-16
- **Status:** accepted (amends an assumption of the specification)

## Context

The specification assumed the selectors filter by operation date, that is, when the trade happened. But the change in open interest is published with a delay: a day's capture contains trades from 1 to 4 business days earlier. With that criterion, the "today" selector would always be empty.

## Decision

All range selectors (today, last week, last month, custom), in tabs 1 and 2 and in the charts, filter by **capture date**. "Today" is today's capture; if there is none yet (weekend, holiday, or the pipeline has not run yet), the latest capture is shown with a visible warning. The operation date is still shown as a column.

"Last week" and "last month" are the captures of the last 7 and 30 calendar days, today included (made explicit in phase 3).

## Rejected alternatives

- **"Today" by capture and the rest by operation date**: two different criteria on the same screen.

## Consequences

- Each operation belongs to one capture.
- In multi-day ranges the same operation can appear in two captures (see [0010](0010-operation-in-several-captures.md)).
