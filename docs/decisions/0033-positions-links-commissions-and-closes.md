# 0033. Positions: several linked operations, automatic commissions, and closes edited from Edit

- **Date:** 2026-11-10
- **Status:** accepted (amends 0031 and 0032)

## Context

After using tab 3, the user asked for four changes. A position can mimic more than one operation, but without overloading the form or the lists. Commissions follow the broker's schedule: $1 per contract to open, at most $10 per leg. A closed position has to be editable from Edit, closes included. And it was unclear whether prices are entered per share or per contract.

Testing in a real browser also showed that a link set from tab 1 was lost when tab 3 had not been shown yet: the drop-down got its value before its options and dropped it.

## Decision

- **Several linked operations per position**, in a `position_links` table. The form uses a multiple drop-down with short labels (date, time, structure, direction and premium). The lists show one short column: the structure and direction for one link, "N operations" for several, with every link in the tooltip. The selected position's panel lists them all with their IDs.
- **To filter the history**, a position with several links shows their structures and directions without repeats, their total premium, and their aggressiveness weighted by premium.
- **Files with the previous format** are migrated when opened: the single link moves to the new table in one transaction, and a copy of the file is kept next to it as `positions.before-links.sqlite`.
- **Automatic commissions**: if the field is left empty, $1 per contract to open, at most $10 per leg, nothing to close. The field shows that amount as it is filled in, and a value typed in is kept, 0 included. When editing, a position whose commissions match the rule shows the field empty, so a change of quantity updates them.
- **Edit opens every field of a closed or partly closed position**, closing date and exit price per leg included. As in the closing form, a leg without an exit price is open.
- **Prices are per share, as quoted**: 6.00 means $600 per contract. The forms say so.
- **The form receives its drop-down's options together with its value**, so a link is never dropped for not being among the options yet.

## Rejected alternatives

- **A list of links in the table, one per line**: the row height and the number of columns would grow with every link.
- **Commissions always computed and not editable**: the broker's statements can include other small fees, and a split leg (to close part of it) would be charged the cap twice.
- **Editing closes only from Close**: the user expected Edit to open everything.

## Consequences

- A leg split in two so that part of it can be closed is charged the $10 cap per piece; the field can be corrected by hand.
- The data contract has a new table, and `positions.operation_id` no longer exists.
