"""Layout of the incomplete-legs tab: pending operations of one capture on the left, the form on the right."""

import dash_ag_grid as dag
from dash import dcc, html

from ...leg_form import LegFormIds, leg_fields
from .rows import COLUMN_DEFS

DAY, DAY_NOTE, GRID, SUMMARY = "inc-day", "inc-day-note", "inc-grid", "inc-summary"
FORM_TITLE, KNOWN_LEG, FORM, SAVE, MESSAGE = "inc-form-title", "inc-known-leg", "inc-form", "inc-save", "inc-message"
SELECTED = "inc-selected"
LEG = LegFormIds.with_prefix("inc")

HIDDEN, SHOWN = {"display": "none"}, {"display": "block"}
FORM_TITLE_TEXT = "Missing leg"
NO_SELECTION = "Select an operation in the list to complete it."


def layout(day_options=(), day=None):
    return html.Div(className="ops-tab", children=[
        html.Div(className="panel", children=[
            html.Div(className="toolbar", children=[
                html.Label("Capture", htmlFor=DAY),
                dcc.Dropdown(id=DAY, options=list(day_options), value=day, clearable=False, className="day-picker"),
            ]),
            html.Div(id=DAY_NOTE, className="range-note"),
            dag.AgGrid(
                id=GRID,
                columnDefs=COLUMN_DEFS,
                rowData=[],
                getRowId="params.data.id",
                defaultColDef={"sortable": True, "filter": True, "floatingFilter": True, "resizable": True},
                columnSize="autoSize",
                dashGridOptions={
                    "rowSelection": {"mode": "singleRow", "checkboxes": False, "enableClickSelection": True},
                    "tooltipShowDelay": 300,
                    "enableCellTextSelection": True,
                },
                className="ops-grid",
            ),
            html.Div(id=SUMMARY, className="summary"),
        ]),
        html.Div(className="ops-side", children=[
            html.Div(className="panel", children=[
                html.H4(FORM_TITLE_TEXT, id=FORM_TITLE),
                html.P(NO_SELECTION, id=KNOWN_LEG, className="muted"),
                html.Div(id=FORM, style=HIDDEN, children=[
                    leg_fields(LEG),
                    html.Div(className="modal-buttons",
                             children=[html.Button("Save", id=SAVE, className="btn primary")]),
                ]),
                html.Div(id=MESSAGE, className="form-message"),
            ]),
        ]),
        dcc.Store(id=SELECTED),
    ])
