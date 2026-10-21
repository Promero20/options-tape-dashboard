# 0019. Manual edits are stored in a local SQLite file

- **Date:** 2026-10-19
- **Status:** accepted

## Context

Manual edits (corrections of direction or operation type, and added legs) go in the dashboard's own files ([0003](0003-edits-in-own-files.md)). Positions will come later, with several legs, links to operations, and their import from tastytrade.

## Decision

A single SQLite file, `ediciones.sqlite`, in the user-data folder (configurable and outside git), using the standard library's `sqlite3`. The schema is in the [data contract](../data-contract.md#manual-edits).

The report opens the file read-only and does not create it if it does not exist. Edits are applied on an in-memory snapshot, with pure functions that are tested without a database.

## Rejected alternatives

- **JSON**: easier to read by hand, but with no integrity constraints or atomic writes, and a worse fit for the relational positions of phase 6.

## Consequences

- Inspecting or backing up the edits means copying a single file.
- If the dashboard is ever used from several devices, where that file lives will need revisiting.
