# 0027. The editing pop-up uses plain Dash components and local CSS

- **Date:** 2026-10-26
- **Status:** accepted

## Context

Tab 1 needs one pop-up to correct an operation: a radio group or a drop-down, a table of legs and three buttons. The phase 3 plan used `dash-bootstrap-components` for it. That package needs the Bootstrap stylesheet, which is usually linked from a CDN or copied into the repository.

## Decision

The pop-up is an `html.Div` overlay shown and hidden by a callback through its `style`, with its look in `src/tape_dashboard/app/assets/style.css`. The interface has no dependencies beyond Dash and dash-ag-grid, and loads nothing from third-party servers: it works offline.

## Rejected alternatives

- **`dash-bootstrap-components`**: one more dependency and a whole stylesheet for a single component, plus either an external request or a vendored copy of Bootstrap.
- **`dcc.ConfirmDialog`**: it only shows text, with no inputs.

## Consequences

- The forms of phases 5 and 6 (manual legs, positions) will reuse the same pattern. If they grow complex enough to need a component library, that gets its own decision.
