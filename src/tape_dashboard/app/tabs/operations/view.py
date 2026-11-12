"""Layout of the operations tab: the list on the left; charts and the selected operation on the right."""

import dash_ag_grid as dag
from dash import dcc, html

from ....charts.aggregate import EXPIRATION, STRIKE
from ....charts.figures import empty_figure
from ....config import web_url
from ...leg_form import LegFormIds, leg_fields, preview_area
from .ranges import MONTH, PRESETS, TODAY
from .rows import COLUMN_GROUPS, ROW_CLASS_RULES, column_defs, column_label

RANGE, DATES, RANGE_NOTE = "ops-range", "ops-dates", "ops-range-note"
GRID, SUMMARY = "ops-grid", "ops-summary"
COLUMNS_BUTTON, COLUMNS_MODAL, COLUMNS_MESSAGE = "ops-columns-button", "ops-columns-modal", "ops-columns-message"
COLUMNS_ALL, COLUMNS_NONE, COLUMNS_SAVE = "ops-columns-all", "ops-columns-none", "ops-columns-save"
COLUMNS_RESTORE, COLUMNS_FACTORY, COLUMNS_CLOSE = "ops-columns-restore", "ops-columns-factory", "ops-columns-close"
COLUMN_GROUP_IDS = tuple(f"ops-columns-{name.lower()}" for name, _ in COLUMN_GROUPS)
DETAIL, EDIT, ACTIONS, NEW_POSITION = "ops-detail", "ops-edit", "ops-actions", "ops-new-position"
GEX_REFERENCE = "ops-gex-reference"
MODAL, MODAL_TITLE, MODAL_INFO, MODAL_LEGS = "ops-modal", "ops-modal-title", "ops-modal-info", "ops-modal-legs"
DIRECTION_BOX, DIRECTION_INPUT = "ops-direction-box", "ops-direction"
STRATEGY_BOX, STRATEGY_INPUT = "ops-strategy-box", "ops-strategy"
READ_ONLY_TEXT = "ops-read-only"
SAVE, CLEAR, CLOSE = "ops-save", "ops-clear", "ops-close"
MANUAL_LEG_BOX, DELETE_LEG, MODAL_MESSAGE = "ops-manual-leg-box", "ops-delete-leg", "ops-modal-message"
LEG = LegFormIds.with_prefix("ops")
EDITING = "ops-editing"
SYMBOL = "ops-symbol"
CHART_RANGE, CHART_DATES, CHART_NOTE = "ops-chart-range", "ops-chart-dates", "ops-chart-note"
AXIS, NET_GRAPH, NET_TOTALS = "ops-net-axis", "ops-net-graph", "ops-net-totals"
WALL_EXPIRATIONS, SHOW_ITM, WALLS_GRAPH = "ops-wall-expirations", "ops-show-itm", "ops-walls-graph"
ITM = "itm"

NO_SYMBOL = "Select an operation in the list or pick an underlying."
GRAPH_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

HIDDEN, SHOWN, SHOWN_INLINE = {"display": "none"}, {"display": "block"}, {"display": "inline-block"}


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
    return [html.H4("Selected operation"), html.P("Select an operation in the list to see its legs.",
                                                  className="muted")]


def range_selector(radio_id, dates_id, value):
    return [
        dcc.RadioItems(id=radio_id, options=[{"label": label, "value": v} for v, label in PRESETS],
                       value=value, inline=True, className="choices"),
        dcc.DatePickerRange(id=dates_id, display_format="YYYY-MM-DD", disabled=True, clearable=True,
                            first_day_of_week=1),
    ]


def charts_panel():
    """Net directional and walls charts of one underlying, with their own date range (decision 0029)."""
    return html.Div(className="panel charts", children=[
        html.Div(className="toolbar", children=[
            html.H4("Underlying charts"),
            dcc.Dropdown(id=SYMBOL, options=[], placeholder="Underlying", clearable=False,
                         className="symbol-picker"),
        ]),
        html.Div(className="toolbar", children=range_selector(CHART_RANGE, CHART_DATES, MONTH)),
        html.Div(id=CHART_NOTE, className="range-note"),
        dcc.Tabs(value="net", className="inner-tabs", children=[
            dcc.Tab(label="Net directional", value="net", children=[
                dcc.RadioItems(id=AXIS, value=EXPIRATION, inline=True, className="choices axis",
                               options=[{"label": "By expiration", "value": EXPIRATION},
                                        {"label": "By strike", "value": STRIKE}]),
                dcc.Graph(id=NET_GRAPH, figure=empty_figure(NO_SYMBOL), config=GRAPH_CONFIG),
                html.Div(id=NET_TOTALS, className="summary"),
            ]),
            dcc.Tab(label="Walls", value="walls", children=[
                html.Div(className="toolbar", children=[
                    dcc.Dropdown(id=WALL_EXPIRATIONS, options=[], value=[], multi=True,
                                 placeholder="All expirations", className="expiration-picker"),
                    dcc.Checklist(id=SHOW_ITM, options=[{"label": "Show ITM walls", "value": ITM}],
                                  value=[ITM], inline=True, className="choices"),
                ]),
                dcc.Graph(id=WALLS_GRAPH, figure=empty_figure(NO_SYMBOL), config=GRAPH_CONFIG),
            ]),
        ]),
    ])


def modal():
    return html.Div(id=MODAL, className="modal-backdrop", style=HIDDEN, children=html.Div(className="modal-box", children=[
        html.H3(id=MODAL_TITLE),
        html.Div(id=MODAL_INFO, className="modal-info"),
        html.Div(id=DIRECTION_BOX, style=HIDDEN, children=[
            html.Label("Direction", htmlFor=DIRECTION_INPUT),
            dcc.RadioItems(id=DIRECTION_INPUT, options=[], inline=True, className="choices"),
        ]),
        html.Div(id=MANUAL_LEG_BOX, style=HIDDEN, children=[
            html.H4("Manual leg"),
            leg_fields(LEG, with_strategy=False, with_preview=False),
        ]),
        html.Div(id=STRATEGY_BOX, style=HIDDEN, children=[
            html.Label("Operation type", htmlFor=STRATEGY_INPUT),
            dcc.Dropdown(id=STRATEGY_INPUT, options=[], clearable=True, placeholder="Choose the operation type"),
        ]),
        preview_area(LEG),
        html.P(id=READ_ONLY_TEXT, className="read-only"),
        html.Div(id=MODAL_LEGS),
        html.Div(id=MODAL_MESSAGE),
        html.Div(className="modal-buttons", children=[
            html.Button("Save", id=SAVE, className="btn primary"),
            html.Button("Clear correction", id=CLEAR, className="btn"),
            html.Button("Delete manual leg", id=DELETE_LEG, className="btn", style=HIDDEN),
            html.Button("Close", id=CLOSE, className="btn"),
        ]),
    ]))


def gex_reference_link(url):
    """The button to the optional external GEX reference page, or nothing without a valid address (decision 0034)."""
    url = web_url(url)
    if url is None:
        return []
    return [html.A("GEX SPX", id=GEX_REFERENCE, href=url, target="_blank", rel="noopener noreferrer",
                   className="btn gex-reference")]


def columns_modal():
    """Which columns the list shows; the order is changed by dragging the headers (decision 0035)."""
    groups = [html.Div(className="column-group", children=[
        html.Label(name, htmlFor=group_id),
        dcc.Checklist(id=group_id, options=[{"label": column_label(field), "value": field} for field in fields],
                      value=[], inline=True, className="choices column-choices"),
    ]) for (name, fields), group_id in zip(COLUMN_GROUPS, COLUMN_GROUP_IDS)]
    return html.Div(id=COLUMNS_MODAL, className="modal-backdrop", style=HIDDEN, children=html.Div(
        className="modal-box", children=[
            html.H3("Columns"),
            html.P("Symbol is always shown. Drag a column header in the list to change the order. Changes apply at "
                   "once; Save as default keeps the list as it is for the next time.", className="muted"),
            html.Div(className="toolbar", children=[html.Button("All", id=COLUMNS_ALL, className="btn"),
                                                    html.Button("None", id=COLUMNS_NONE, className="btn")]),
            *groups,
            html.Div(id=COLUMNS_MESSAGE, className="form-message"),
            html.Div(className="modal-buttons", children=[
                html.Button("Save as default", id=COLUMNS_SAVE, className="btn primary"),
                html.Button("Restore default", id=COLUMNS_RESTORE, className="btn"),
                html.Button("Factory columns", id=COLUMNS_FACTORY, className="btn"),
                html.Button("Close", id=COLUMNS_CLOSE, className="btn"),
            ]),
        ]))


def layout(state):
    saved = state.preferences.operations_columns()
    return html.Div(className="ops-tab", children=[
        html.Div(className="panel ops-list", children=[
            html.Div(className="toolbar", children=[
                *range_selector(RANGE, DATES, TODAY),
                html.Button("✎ Columns", id=COLUMNS_BUTTON, className="btn columns-button",
                            title="Choose the columns of the list"),
            ]),
            html.Div(id=RANGE_NOTE, className="range-note"),
            dag.AgGrid(
                id=GRID,
                columnDefs=column_defs(saved),
                rowData=[],
                getRowId="params.data.id",
                defaultColDef={"sortable": True, "filter": True, "floatingFilter": True, "resizable": True},
                rowClassRules=ROW_CLASS_RULES,
                columnSize=None if saved else "autoSize",       # a saved layout keeps its own widths
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
            charts_panel(),
            html.Div(className="panel detail-panel", children=[
                html.Div(id=ACTIONS, className="detail-actions", style=HIDDEN, children=[
                    html.Button("New position", id=NEW_POSITION, className="btn"),
                    html.Button("Edit", id=EDIT, className="btn"),
                ]),
                html.Div(id=DETAIL, children=empty_detail()),
            ]),
            *gex_reference_link(state.settings.gex_reference_url),
        ]),
        modal(),
        columns_modal(),
        dcc.Store(id=EDITING),
    ])
