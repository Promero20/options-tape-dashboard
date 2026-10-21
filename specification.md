# Dashboard Tape Reading — Specification

Oct 15, 2026 · @Pablo Romero

> Decisions taken after this specification are recorded in [docs/decisiones/](docs/decisiones/README.md); where they differ, they take precedence.

## Context

The dashboard is a local application that reads the daily CSV files produced by an options-flow capture pipeline and shows them in three tabs: detected operations, operations to complete, and real positions.

The capture pipeline lives outside this repository. It delivers three levels of files:

1. **Level 1 — candidates.** Full table of the day's contracts with an increase in open interest. It computes `premium_estimado = mid × oi_chg × 100`, takes the top N (N=25 today) and filters them by the premium threshold for the underlying's price. For the selected contracts it identifies the actual date of the volume (`fecha_volumen`). File: `nivel1_candidatos_YYYYMMDD.csv`.
2. **Level 2 — trades.** Time & Sales of each reconciled candidate on its `fecha_volumen` (only trades of size ≥ 10), with `agresividad = (trade − mid) / half_spread`. File: `nivel2_trades_YYYYMMDD.csv`.
3. **Level 3 — operations.** The `nivel3_agrupar.py` script groups trades into operations (simultaneous legs with the same Trade Condition, and a contract's order split into several prints), infers structure and direction, and drops those below the threshold. File: `nivel3_operaciones_YYYYMMDD.csv`.

Premium threshold by underlying price bracket, used throughout the project:

| Underlying price | Premium threshold |
| --- | --- |
| $1 – $50 | ≥ $500,000 |
| $50 – $200 | ≥ $1,000,000 |
| > $200 | ≥ $3,000,000 |

All files live in a configurable data folder. The dashboard only reads that folder; it never writes to it.

## Data layer

Operations are rebuilt from level 2 rather than read from the level-3 CSV: that way there is a single grouping logic, per-leg detail is available, and every day ends up in the current format.

### Input files

| File | Use in the dashboard |
| --- | --- |
| `nivel1_candidatos_YYYYMMDD.csv` | Underlying price (threshold bracket, reference price in charts) |
| `nivel2_trades_YYYYMMDD.csv` | Source of the operations: grouped with the code in `nivel3_agrupar.py` |
| `nivel3_operaciones_YYYYMMDD.csv` | Not used as a source; only to check that the reconstruction matches |
| `gex_spy_YYYYMMDD.csv` (new) | SPY GEX at capture time (see *Changes outside the dashboard*) |

### Schema normalisation

Historical CSV files do not share a schema. The data layer maps every variant to a canonical schema before anything else. Known variants:

- Level 1: contract in `contract_symbol` or `option_symbol`, or missing (rebuilt as `SYMBOL|YYYYMMDD|STRIKE.00C/P`); `open_int` or `open_interest`; `last_trade`, `last_trade_ts` or missing; `fecha_volumen` sometimes as text with several dates.
- Level 2: alternative names (`tradeTime`, `lastPrice`, `tradeSize`, `tradeConditionCode`, `premium`…) instead of the canonical ones (`Time`, `Trade`, `Trade Size`, `Trade Condition`, `Premium`); optional `Trade Condition Full` and `es_metadata_footer`; footer rows to drop.

A file that matches no known variant is reported on screen with its name and the missing columns; it is never silently ignored.

### Days without recoverable data

- `nivel2_trades_20260922.csv` is empty (0 rows): 22/09 is discarded.
- 25/08 and 09/09 have an old-format level 3, but their level 2 is complete: they are rebuilt without problems.

### Operation ID

Each operation gets a stable ID: `YYYYMMDD-SYMBOL-HH:MM:SS.mmm` (date and time of the group's first trade). Manual edits and links to positions point to this ID.

### Manual edits

Everything the user enters is stored in the dashboard's own files, separate from the pipeline's, and applied on top of the data at load time:

- Legs added by hand (tab 2).
- Directions assigned or corrected by hand (tab 1).
- Real positions and their link to operations (tab 3).

If an edit points to an ID that no longer exists (for example, because the grouping logic changed), the dashboard shows it as an orphan for review; it never deletes it.

## Classification rules

Each operation goes to exactly one of four destinations: the net directional chart, the walls chart, the undetermined total or the discarded total. That way no premium is counted twice.

A leg is **bought** if its aggressiveness is > +0.25 and **sold** if it is < −0.25. Between those values its side is undetermined.

| Structure | Condition | Destination | Strike | Expiration | Premium |
| --- | --- | --- | --- | --- | --- |
| Single-leg call or put | Bought | Net directional (call = bull, put = bear) | The contract's | The contract's | Total premium |
| Single-leg call or put | Sold | Walls (put = support, call = resistance) | The contract's | The contract's | Total premium |
| Single-leg | Undetermined side | Undetermined, at its strike and expiration | The contract's | The contract's | Total premium |
| Debit vertical | Bought-leg premium > sold-leg premium | Net directional | Bought leg | Shared | Bought leg − sold leg |
| Credit vertical | Sold-leg premium > bought-leg premium | Walls | Sold leg | Shared | Sold leg − bought leg |
| Diagonal | Both legs with a clear side | Net directional | Bought leg | The nearest | Bought leg − sold leg |
| Multi-leg with any undetermined leg | — | Undetermined, as a separate total | — | — | Gross premium |
| Pure calendar, straddle, strangle, risk reversal, condor, 3+ legs | — | Discarded | — | — | Gross premium |
| With stock (`TLET`, `TLAT`, `TLCT`, `TLFT`, `TASL`, `TESL`, `TFSL`) | — | Discarded | — | — | Gross premium |
| Incomplete legs not yet completed | — | Discarded (pending) until completed in tab 2 | — | — | Gross premium |

Debit vertical example: a bear put with 10M on the bought 100 put and 5M on the sold 90 put. It is placed at strike 100 with −5M (bearish).

### Direction assigned by hand

Assigning or correcting an operation's direction changes its destination according to these same rules. In a single-leg, the direction implies the side: bull on a call means bought (goes to net), and bull on a put means sold (goes to walls).

### Wall direction

A sold put or a bull put spread forms a support wall, below the price. A sold call or a bear call spread forms a resistance wall, above it.

## Tab 1 — Operations

Three panels, following the original sketch: the operations list on the left, the underlying's chart top right and the SPY GEX bottom right.

### Panel 1 — Operations list

- Rebuilt level-3 operations, including those completed by hand in tab 2. It excludes those with pending incomplete legs.
- Range selector: today, last week, last month and custom range.
- Columns: those of `nivel3_operaciones` (symbol, structure, strike, expiration, operation date, premium in millions, `precio_neto`, aggressiveness, direction, trade conditions, start and end time).
- Sortable and filterable by column.
- Clicking the direction cell opens a pop-up to assign or correct the direction (bull, bear or undetermined). Undetermined ones are highlighted for review. A direction edited by hand is visually marked.
- Selecting a row sets the underlying for panel 2.

### Panel 2 — Underlying charts

Two charts of the selected underlying, switchable with inner tabs. Each has its own date-range selector, independent of the list.

**Net directional**

- Diverging bars: bull premium upwards, bear premium downwards, and a marker with the net (bull − bear) on each bar.
- Selectable X axis: by expiration date or by strike (one or the other, not both).
- Accumulated undetermined premium, with its own marker on each bar (undetermined single-legs).
- Separate indicators, as totals: undetermined multi-legs and discarded combinations (accumulated gross premium).

**Walls**

- Net premium by sold strike: support (sold puts, bull put spreads) below the price and resistance (sold calls, bear call spreads) above it.
- Current underlying price marked as a reference.
- Filter by expiration date.

### Panel 3 — SPY GEX

General market context, independent of the selected operation. Data from the latest `gex_spy_YYYYMMDD.csv`, with its capture time visible.

- Regime: positive or negative gamma.
- Gamma flip level versus the current SPY price.
- Main strikes by absolute GEX.

## Tab 2 — Incomplete legs

This is where multi-leg operations missing a leg are completed by hand; on saving, the operation moves to tab 1.

### Panel 1 — List

- Operations with `patas_incompletas = True` that have not been completed yet.
- Same range selector as tab 1.
- Columns: symbol, contract of the known leg, Trade Condition, size, premium, start and end time, operation date.

### Panel 2 — Missing-leg form

Selecting an operation opens a form with the underlying already filled in. Minimum fields:

- Type (call or put), strike and expiration date.
- Execution price.
- Size (contracts).
- Side: bought or sold.

On saving:

1. The leg is added to the operation (stored in the manual-edits file).
2. The operation is recomputed with the same logic as the others: structure, `precio_neto`, direction and premium.
3. It disappears from this tab and appears in tab 1, classified according to the classification rules.

A leg added by hand can be edited or deleted later; deleting it sends the operation back to this tab.

## Tab 3 — Positions

A record of the user's real positions, linked to the operation they mimic, to measure which signals work and not just the overall P&L.

### Panel 1 — Open positions

- Manual creation, editing and closing of positions.
- A position can have several legs. Fields per leg: contract (underlying, type, strike, expiration), side (buy or sell), quantity and entry price.
- Fields per position: opening date, commissions, notes and linked operation (operation ID, optional, chosen from the tab 1 list).

### Panel 2 — History

- Closed positions: closing date and price per leg, P&L in $ and %, days in the position.
- For linked positions, the data of the source operation (structure, direction, premium, aggressiveness), so the history can be filtered by them.

### Panel 3 — History chart

- Cumulative P&L over time.
- More views when needed; the user will add them later.

### Import from tastytrade

Later phase. Manual entry first; the positions data model must allow replacing it later with an automatic import from the tastytrade API without redoing the tab. API availability and terms will be checked when that phase arrives.

## Changes outside the dashboard

Two changes are needed in the capture pipeline; neither alters what it delivers today.

### 1. `nivel3_agrupar.py`: expose legs and ID without changing its output

The dashboard imports the script's functions instead of reimplementing them. To do so:

- Extract the per-leg calculation (contract, type, strike, expiration, size, premium, aggressiveness, average price) into its own function that `resumen()` keeps using.
- Add a function that returns the operation ID (`YYYYMMDD-SYMBOL-HH:MM:SS.mmm`).
- Separate grouping from the threshold filter, so the dashboard can group and apply manual edits before filtering.
- Regression test: the `nivel3_operaciones_YYYYMMDD.csv` produced by the refactored script must be byte-for-byte identical to the current script's, for every day with level 2 available.

### 2. New file with the SPY GEX

The capture pipeline will have to produce a new file, independent of levels 1-3:

- One capture per day, at the same time as the rest of the data.
- Output: `gex_spy_YYYYMMDD.csv` in the data folder, with capture time, SPY price and GEX by strike.
- If the source does not provide the gamma flip or the regime directly, they are computed from the GEX by strike.

## Documentation

The project is documented as it is built, not at the end: each phase delivers its code together with the matching documentation.

- **README**: what the project does, a screenshot of each tab, how to install and run it, and the repository structure.
- **Data contract**: canonical schema of each input CSV (columns, types, meaning) and of the manual-edits files. It is the project's entry point: "it takes CSV files with this schema".
- **Business rules**: thresholds, aggressiveness, trade grouping and the classification rules of this specification, with examples.
- **Architecture**: data layer, operation reconstruction, manual edits and views, with a diagram.
- **Decision log**: one short entry per relevant decision (what was decided, why, rejected alternatives). The decisions in this specification are the first entries.
- **Tests**: schema normalisation, classification rules and the level-3 script regression.

Publishing aspects (sample data, what is not published) will be handled later.

## Open points and assumptions

Assumptions apply as stated unless corrected; open points are decided before the phase that needs them.

### Assumptions

- The net and walls charts share panel 2 through inner tabs, because the sketch has three panels.
- Multi-legs with an undetermined side go into a separate total, not spread by strike.
- Diagonals always go to net directional, even credit ones.
- The date used by the range selectors is the operation date (when it traded), not the file's capture date.

### Open points

- **Risk reversal.** The script groups it with straddles and strangles, so today it is discarded, although it does have a single direction (bought call + sold put = bull). Should it be separated and sent to net?
- **Stack.** Not decided. Constraint: the dashboard imports Python code (`nivel3_agrupar.py`), so the backend must be Python. Options will be proposed in the plan.
- **Local-only or accessible from other devices.** Not decided; it affects the stack and where manual edits are stored.
