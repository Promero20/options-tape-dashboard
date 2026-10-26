"""Layout of the operations tab: list on the left, underlying panel and SPY GEX on the right."""

import dash_ag_grid as dag
from dash import dcc, html

from .ranges import PRESETS, TODAY
from .rows import OPTIONAL_COLUMNS, ROW_CLASS_RULES, column_defs

RANGE, DATES, RANGE_NOTE = "ops-range", "ops-dates", "ops-range-note"
COLUMNS, GRID, SUMMARY = "ops-columns", "ops-grid", "ops-summary"
DETAIL = "ops-detail"
MODAL, MODAL_TITLE, MODAL_INFO, MODAL_LEGS = "ops-modal", "ops-modal-title", "ops-modal-info", "ops-modal-legs"
DIRECTION_BOX, DIRECTION_INPUT = "ops-direction-box", "ops-direction"
STRATEGY_BOX, STRATEGY_INPUT = "ops-strategy-box", "ops-strategy"
READ_ONLY_TEXT = "ops-read-only"
SAVE, CLEAR, CLOSE = "ops-save", "ops-clear", "ops-close"
EDITING = "ops-editing"

HIDDEN, SHOWN = {"display": "none"}, {"display": "block"}


def legs_table(rows):
    header = ["Contract", "Size", "Premium (M)", "Price", "Aggr.", "Measured side", "Side used"]
    body = []
    for r in rows:
        contract = r["contract"] + (" (manual)" if r["manual"] else "")
        aggr = "" if r["aggressiveness"] is None else f"{r['aggressiveness']:+.2f}"
        body.append(html.Tr([html.Td(contract), html.Td(f"{r['size']:,}"), html.Td(f"{r['premium_m']:.3f}"),
                             html.Td(f"{r['price']:g}"), html.Td(aggr), html.Td(r["measured_side"]),
                             html.Td(r["side_used"])]))
    return html.Table(className="legs", children=[html.Thead(html.Tr([html.Th(h) for h in header])),
                                                   html.Tbody(body)])


def empty_detail():
    return [html.H4("Underlying"), html.P("Select an operation in the list to see its legs.", className="muted")]


def modal():
    return html.Div(id=MODAL, className="modal-backdrop", style=HIDDEN, children=html.Div(className="modal-box", children=[
        html.H3(id=MODAL_TITLE),
        html.Div(id=MODAL_INFO, className="modal-info"),
        html.Div(id=DIRECTION_BOX, style=HIDDEN, children=[
            html.Label("Direction", htmlFor=DIRECTION_INPUT),
            dcc.RadioItems(id=DIRECTION_INPUT, options=[], inline=True, className="choices"),
        ]),
        html.Div(id=STRATEGY_BOX, style=HIDDEN, children=[
            html.Label("Operation type", htmlFor=STRATEGY_INPUT),
            dcc.Dropdown(id=STRATEGY_INPUT, options=[], clearable=True, placeholder="Choose the operation type"),
        ]),
        html.P(id=READ_ONLY_TEXT, className="read-only"),
        html.Div(id=MODAL_LEGS),
        html.Div(className="modal-buttons", children=[
            html.Button("Save", id=SAVE, className="btn primary"),
            html.Button("Clear correction", id=CLEAR, className="btn"),
            html.Button("Close", id=CLOSE, className="btn"),
        ]),
    ]))


def layout(state):
    return html.Div(className="ops-tab", children=[
        html.Div(className="panel ops-list", children=[
            html.Div(className="toolbar", children=[
                dcc.RadioItems(id=RANGE, options=[{"label": label, "value": value} for value, label in PRESETS],
                               value=TODAY, inline=True, className="choices"),
                dcc.DatePickerRange(id=DATES, display_format="YYYY-MM-DD", disabled=True, clearable=True,
                                    first_day_of_week=1),
                dcc.Checklist(id=COLUMNS, options=[{"label": label, "value": field}
                                                   for field, label in OPTIONAL_COLUMNS],
                              value=[], inline=True, className="choices optional-columns"),
            ]),
            html.Div(id=RANGE_NOTE, className="range-note"),
            dag.AgGrid(
                id=GRID,
                columnDefs=column_defs(),
                rowData=[],
                getRowId="params.data.id",
                defaultColDef={"sortable": True, "filter": True, "floatingFilter": True, "resizable": True},
                rowClassRules=ROW_CLASS_RULES,
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
            html.Div(id=DETAIL, className="panel", children=empty_detail()),
            html.Div(className="panel placeholder", children=[
                html.H4("SPY GEX"),
                html.P("Market context from the daily SPY GEX file: regime, gamma flip and main strikes. "
                       "Coming in phase 7.", className="muted"),
            ]),
        ]),
        modal(),
        dcc.Store(id=EDITING),
    ])
