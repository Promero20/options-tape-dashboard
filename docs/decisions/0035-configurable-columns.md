# 0035. Configurable columns in the operations list, saved in the user-data folder

- **Date:** 2026-11-12
- **Status:** accepted

## Context

The operations list had sixteen fixed columns and two optional ones. The user wants a cleaner list with only the columns they care about, in their order, saved as a base layout, and to add data the list did not show, such as the contract's volume.

Some data about a contract is a snapshot of the capture and loses meaning as time passes: open interest and its change, vol/OI, implied volatility, delta, moneyness, days to expiration, the quote and the underlying's price. Level 1 also has the contract's volume on the session it traded (`volumen_en_fecha`), which does not change. In the real data, its date is the operation's trade date for every leg of every listed operation, and an operation never exceeds it.

## Decision

- **A "✎ Columns" button** at the top right of the list opens a pop-up with every available column, grouped (operation, volume, technical), with All and None. Ticking or unticking applies at once. Symbol is always shown and first.
- **The order is changed by dragging the column headers**, as the grid already allows.
- **"Save as default"** keeps the list as it is (shown columns, order and widths) in `preferences.json` in the user-data folder, outside git. The list opens with it from then on. **"Restore default"** brings it back, and **"Factory columns"** returns to the original list without saving. Changes that are not saved last until the page is reloaded.
- **New columns**, hidden in the factory layout: legs, trades, size (contracts in the operation), duration, **contract volume** (volume of each leg's contract on the trade date, added up across legs) and **share of volume** (size ÷ contract volume).
- **Snapshot data is left out for now.**
- **An operation completed by hand has no contract volume**: its manual leg is not in level 1, and a partial sum would understate it.
- **The preferences file is written atomically.** If it cannot be read, factory columns are used and the banner says so; the file is not touched until a new layout is saved, and then a copy of it is kept as `preferences.json.unreadable`.

## Rejected alternatives

- **Arrows in the pop-up to set the order**: more clicks than dragging a header, and they do not keep widths.
- **Saving every change automatically**: there would be no base layout to come back to.
- **Browser storage**: lost with another browser or when its data is cleared.
- **The contract's `volume` from level 1**: it is the day volume at capture time, not the volume of the session the operation traded.

## Consequences

- A column added to the catalogue later appears hidden in a saved layout until it is ticked.
- The same approach can serve the lists of tabs 2 and 3 if they ever need it.
