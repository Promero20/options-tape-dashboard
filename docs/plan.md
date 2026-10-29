# Phased plan

Each phase ends with the tests passing, the documentation up to date and a commit. Decisions taken along the way go to the [decision log](decisions/README.md).

| Phase | Content | Status |
|---|---|---|
| 0 | Scaffolding and refactor of `nivel3_agrupar.py` with a regression test | **done** |
| 1 | Data layer: schemas, normalisation and operation reconstruction | **done** |
| 2 | Classification, operation-type catalogue and manual edits (pure logic) | **done** |
| 3 | Application and tab 1: list | **done** |
| 4 | Tab 1: net directional and walls charts | **done** |
| 5 | Tab 2: incomplete legs | **done** |
| 6 | Tab 3: positions | pending |
| 7 | SPY GEX (new input file and panel) | pending |
| 8 | Visual polish: readability and look of the whole interface | pending |

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

## Phase 3: application and tab 1 (list)

- Interface, stored values and new code in English ([0025](decisions/0025-interface-and-new-code-in-english.md)).
- Dash application with the three tabs, local only, with callbacks organised per tab ([0023](decisions/0023-ui-stack.md)). Tabs 2 and 3 are placeholders.
- Tab 1: range selector by capture date, list with sorting and filters on every column, pop-up to correct the direction or the operation type, detail of the selected operation, and a Reload button.
- Warnings banner: schemas, days that cannot be rebuilt, orphan edits, outdated script, and the optional declared-hash check ([0026](decisions/0026-declared-script-hash-check.md)).
- Pop-up without extra dependencies ([0027](decisions/0027-editing-pop-up-without-extra-dependencies.md)).

**Done when:** the interface's pure functions (ranges, rows, editing, warnings) and its controllers are tested on synthetic data; the app builds, serves its layout and answers its callbacks over HTTP; the list builds for the whole real period; and the server starts on 127.0.0.1 with the real data. ✔

## Phase 4: net directional and walls charts

- Chart data as pure functions (`tape_dashboard.charts.aggregate`) and Plotly figures (`charts.figures`), with the reference price from the dataset.
- Chart panel in tab 1: underlying from the selected row or a drop-down, one date range for both charts (last month by default), net chart by expiration or strike, walls chart with an expiration filter ([0029](decisions/0029-chart-panel-controls.md)).
- In-the-money walls marked and optionally hidden ([0028](decisions/0028-in-the-money-walls.md)).

**Done when:** the aggregation, the figures and the panel's controllers are tested on synthetic data; every dollar of every real underlying lands in exactly one place of the charts; a correction moves premium between charts; and the charts are served over HTTP with the real data. ✔

## Phase 5: tab 2, incomplete legs

- Shared logic for the manual leg (`app/manual_legs.py`) and its fields (`app/leg_form.py`): validation, the completed operation rebuilt with the script, the operation types that fit, a preview, and saving only when everything is valid.
- Tab 2: day selector by capture, the pending operations above the threshold, and a form that starts from the known leg ([0013](decisions/0013-tab-2-scope.md), [0030](decisions/0030-manual-legs.md)).
- Tab 1's pop-up edits or deletes the manual leg of a completed operation; deleting it sends the operation back to tab 2.

**Done when:** the manual-leg logic, tab 2's controllers and the pop-up are tested on synthetic data; every real pending operation can be completed in the form; and a real operation is completed, shown in tab 1, and sent back to tab 2 over HTTP. ✔

## Phases 6 to 8

- **6**: positions, history and P&L, with a model ready for a future read-only import from tastytrade.
- **7**: SPY GEX file and its panel.
- **8**: visual polish, once everything works: readability, layout and look of every tab. Until then, styling stays minimal.
