# Phased plan

Each phase ends with the tests passing, the documentation up to date and a commit. Decisions taken along the way go to the [decision log](decisions/README.md).

| Phase | Content | Status |
|---|---|---|
| 0 | Scaffolding and refactor of `nivel3_agrupar.py` with a regression test | **done** |
| 1 | Data layer: schemas, normalisation and operation reconstruction | **done** |
| 2 | Classification, operation-type catalogue and manual edits (pure logic) | **done** |
| 3 | Application and tab 1: list | pending |
| 4 | Tab 1: net directional and walls charts | pending |
| 5 | Tab 2: incomplete legs | pending |
| 6 | Tab 3: positions | pending |
| 7 | SPY GEX (new input file and panel) | pending |

Phase 2 comes before the interface because the direction pop-up, the charts and tab 2 all need it. It is also the business logic with the most risk, and it is easier to test without a UI.

## Phase 0: scaffolding and regression-tested refactor

- Repository: `.gitignore` (no data under version control), `.gitattributes`, `pyproject.toml`, README and decision log.
- `pipeline/nivel3_agrupar.py` refactored: per-leg calculation, operation ID and threshold separated from grouping, with the output unchanged ([details](level3-script.md)).
- Frozen copy of the previous version in `tests/legacy/` as the oracle.

**Done when:** the new script's output is byte-for-byte identical to the frozen copy's for every real day with level 2 and for the synthetic scenario in every schema variant; it matches the stored level-3 files produced by that version; and the data folder is left untouched. ✔

## Phase 1: data layer and reconstruction

- Configurable data path (environment variable, configuration file, or `../tape_data` by default).
- Canonical schema for each CSV, with aliases and a registry of the known variants. A file missing required columns is reported with its name and the missing columns; a new but resolvable header is loaded with a warning.
- Value normalisation: types, dates, booleans and rebuilt contract.
- Per-capture reconstruction with the script's functions, de-duplicating IDs across captures.
- Validation against the stored level 3.
- Command-line report (`python -m tape_dashboard.report`).
- Documentation: data contract, data quality and architecture.

**Done when:** the report on the real data is correct and the tests for per-variant normalisation, invalid headers, de-duplication and ID uniqueness pass. ✔

## Phase 2: classification, catalogue and edits

- A single destination per operation, following the specification's rules and using per-leg detail.
- Operation-type catalogue (bull call, bear put, straddle…) that sets each leg's side ([0011](decisions/0011-manual-leg-operation-type.md)).
- Local store for manual edits (directions, manual legs, chosen types), with orphan detection.
- Anomalous size ratio flag ([0012](decisions/0012-flag-anomalous-size-ratios.md)).

**Done when:** there are tests for every rule in the specification, every catalogue type, the real cases the rules did not cover, and premium conservation. ✔

It also includes the script change that drops cancellations ([0015](decisions/0015-drop-cancellations.md)).

## Phases 3 to 7

- **3**: application with the three tabs, in Dash, local only and with callbacks organised per tab ([0023](decisions/0023-ui-stack.md)); list with sorting and filters, range selector by capture date, direction pop-up, warnings (schemas, orphan edits, outdated pipeline script).
- **4**: net directional and walls charts.
- **5**: tab 2, with a day selector, the list of incomplete operations above the threshold and a form with the operation type.
- **6**: positions, history and P&L, with a model ready for a future read-only import from tastytrade.
- **7**: SPY GEX file and its panel.
