# 0024. Documentation in English; the pipeline's names stay in Spanish

- **Date:** 2026-10-21
- **Status:** accepted

## Context

The documentation was first written in Spanish. The repository is going to be published as part of a portfolio, for an audience that may not read Spanish. At the same time, several names come from outside the dashboard: the files and CSV columns the pipeline produces, and the level-3 script it runs.

## Decision

- **In English**: the README, the specification, everything under `docs/` (including this log) and, from now on, commit messages.
- **In Spanish, for good**:
  - The level-3 script's identifiers and console messages (`pipeline/nivel3_agrupar.py`). The pipeline runs it and checks its hash; renaming them would change the hash and the script's interface, and the frozen copy used as the regression oracle would no longer match it ([0005](0005-canonical-script-copy.md), [0006](0006-frozen-oracle-and-synthetic-data.md)).
  - File names and CSV column names (`nivel2_trades_*.csv`, `agresividad`, `premium_total_M`…): they are produced outside this repository, and the [data contract](../data-contract.md) documents them as they are.
- **Still in Spanish for now**: code comments, docstrings, test texts and the text shown by the report and the interface, as well as the values stored in the edits file (e.g. `indeterminado`). Whether to translate them is a separate, pending decision.

## Rejected alternatives

- **Keeping everything in Spanish**: it limits who can read the project.
- **Translating everything, including the pipeline's names**: it would break the contract with the pipeline and the regression oracle.

## Consequences

The documentation and the code mix languages until the pending decision is taken; the README says so.
