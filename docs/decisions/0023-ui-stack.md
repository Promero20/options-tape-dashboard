# 0023. Interface stack: Dash, dash-ag-grid and Plotly, local only

- **Date:** 2026-10-21
- **Status:** accepted

## Context

The backend has to be Python, because the dashboard imports the level-3 script. The interface needs a sortable and filterable table where clicking a cell opens a pop-up (direction or operation type), panels linked to the selected row, diverging bar charts, and forms for manual legs and positions.

Three options were considered: Dash with dash-ag-grid and Plotly; Streamlit; and a FastAPI backend with a JavaScript single-page app.

## Decision

- **Dash + dash-ag-grid + Plotly.** AG Grid gives per-column sorting and filtering, cell-click events and per-row styling (undetermined, edited, anomalous ratio); Plotly draws the diverging bars; everything stays in Python.
- **Bound to 127.0.0.1 only.** The dashboard has no authentication and it edits data (manual edits and, later, positions). Making it reachable from other devices is **not** just a configuration change: it will require adding authentication, or restricting access to the home network, and revisiting where the edits file lives ([0019](0019-edits-store.md)).
- **Callbacks organised per tab from the start**: each tab has its own module with its layout and callbacks, and the business logic stays in `tape_dashboard.data`, `tape_dashboard.rules` and `tape_dashboard.edits`, so callbacks remain thin and the logic is tested without the interface.

## Rejected alternatives

- **Streamlit**: quickest to start, but it has no cell click (only row selection), and its rerun-everything model makes linked state (selection → chart → pop-up) awkward.
- **FastAPI + a JavaScript SPA**: the most control and the best prepared for remote access, but two languages, a build toolchain and two or three times the code for a single user.

## Consequences

- Dash, dash-ag-grid and Plotly become runtime dependencies from phase 3.
- Access from other devices, if it is ever needed, gets its own decision.
