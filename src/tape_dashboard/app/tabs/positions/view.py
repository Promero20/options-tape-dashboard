"""Layout of the positions tab: open positions and history on the left; selected position and P&L on the right."""

import dash_ag_grid as dag
from dash import dcc, html

from ....charts.figures import empty_figure
from . import forms
from .rows import HISTORY_COLUMNS, OPEN_COLUMNS

OPEN_GRID, HISTORY_GRID, HISTORY_SUMMARY, NEW = "pos-open-grid", "pos-history-grid", "pos-history-summary", "pos-new"
DETAIL, ACTIONS, EDIT, CLOSE, DELETE = "pos-detail", "pos-actions", "pos-edit", "pos-close", "pos-delete"
CHART, SELECTED, PREFILL, CONFIRM = "pos-chart", "pos-selected", "pos-prefill", "pos-confirm-delete"

HIDDEN, SHOWN_INLINE = {"display": "none"}, {"display": "inline-block"}
NO_SELECTION = "Select a position in either list to see its legs."


def _grid(grid_id, columns):
    return dag.AgGrid(
        id=grid_id,
        columnDefs=columns,
        rowData=[],
        getRowId="params.data.id",
        defaultColDef={"sortable": True, "filter": True, "floatingFilter": True, "resizable": True},
        columnSize="autoSize",
        dashGridOptions={
            "rowSelection": {"mode": "singleRow", "checkboxes": False, "enableClickSelection": True},
            "tooltipShowDelay": 300,
            "enableCellTextSelection": True,
        },
        className="pos-grid",
    )


def empty_detail():
    return [html.H4("Selected position"), html.P(NO_SELECTION, className="muted")]


def layout():
    return html.Div(className="ops-tab", children=[
        html.Div(className="positions-left", children=[
            html.Div(className="panel", children=[
                html.Div(className="toolbar", children=[
                    html.H4("Open positions"),
                    html.Button("New position", id=NEW, className="btn primary"),
                ]),
                _grid(OPEN_GRID, OPEN_COLUMNS),
            ]),
            html.Div(className="panel", children=[
                html.H4("History"),
                _grid(HISTORY_GRID, HISTORY_COLUMNS),
                html.Div(id=HISTORY_SUMMARY, className="summary"),
            ]),
        ]),
        html.Div(className="ops-side", children=[
            html.Div(className="panel detail-panel", children=[
                html.Div(id=ACTIONS, className="detail-actions", style=HIDDEN, children=[
                    html.Button("Edit", id=EDIT, className="btn"),
                    html.Button("Close", id=CLOSE, className="btn"),
                    html.Button("Delete", id=DELETE, className="btn"),
                ]),
                html.Div(id=DETAIL, children=empty_detail()),
            ]),
            html.Div(className="panel", children=[
                html.H4("Cumulative P&L"),
                dcc.Graph(id=CHART, figure=empty_figure("No closed positions to show."),
                          config={"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}),
            ]),
        ]),
        forms.position_form(),
        forms.close_form(),
        dcc.ConfirmDialog(id=CONFIRM, message="Delete this position and its legs? This cannot be undone."),
        dcc.Store(id=SELECTED),
        dcc.Store(id=PREFILL),
        dcc.Store(id=forms.EDITING),
        dcc.Store(id=forms.CLOSING),
    ])
