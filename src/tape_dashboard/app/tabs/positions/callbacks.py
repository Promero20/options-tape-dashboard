"""
Callbacks of the positions tab. As in the other tabs, each callback wraps a
controller that takes the application state and plain values, so the tests
call the controllers without a browser.
"""

from dash import Input, Output, State, ctx, html, no_update

from ....charts.aggregate import for_symbol
from ....charts.figures import cumulative_pnl_figure
from ....edits.apply import classified_operations
from ....positions import pnl
from ....rules.sides import option_type as leg_type
from ... import ids
from ...leg_form import errors_block
from ..operations import view as operations_view
from . import forms, view
from .rows import history_row, leg_text, legs_text, open_row, symbol_of

M = 1_000_000


# --- lists, detail and chart ---------------------------------------------------

def list_content(state):
    """Rows of the open positions and of the history."""
    today, open_rows, history = state.today(), [], []
    for position in state.positions.all():
        item = state.classified(position.operation_id) if position.operation_id else None
        if pnl.is_closed(position):
            history.append(history_row(position, item))
        else:
            open_rows.append(open_row(position, item, today))
    return open_rows, history


def history_view(virtual_rows, rows):
    """The chart and the line under the history, for the rows left by the grid's filters (decision 0032)."""
    shown = virtual_rows if virtual_rows is not None else (rows or [])
    total = sum(row["pnl"] for row in shown)
    return (cumulative_pnl_figure(pnl.cumulative([(row["closed"], row["pnl"]) for row in shown])),
            f"{len(shown)} closed positions, total P&L {total:+,.2f}")


def _position(state, selected):
    return state.positions.get(selected["id"]) if selected else None


def _legs_table(position):
    header = ["Leg", "Exit date", "Exit price", "P&L ($)"]
    body = []
    for leg in position.legs:
        result = pnl.leg_pnl(leg)
        body.append(html.Tr([html.Td(leg_text(leg)), html.Td(leg.exit_date or "—"),
                             html.Td("—" if leg.exit_price is None else f"{leg.exit_price:g}"),
                             html.Td("—" if result is None else f"{result:+,.2f}")]))
    return html.Table(className="legs", children=[html.Thead(html.Tr([html.Th(h) for h in header])), html.Tbody(body)])


def detail_content(state, selected):
    """The panel of the selected position and whether its buttons show."""
    position = _position(state, selected)
    if position is None:
        return view.empty_detail(), view.HIDDEN
    facts = [f"Opened {position.opened_on} · {pnl.status(position)} · commissions {position.commissions:,.2f}"]
    if pnl.is_closed(position):
        percentage = pnl.pnl_pct(position)
        facts.append(f"Closed {pnl.closing_date(position)} after {pnl.days_held(position)} days · "
                     f"P&L {pnl.net_pnl(position):+,.2f}" + ("" if percentage is None else f" ({percentage:+.1f}%)"))
    if position.operation_id:
        item = state.classified(position.operation_id)
        facts.append(f"Linked to {position.operation_id} ({item.classification.structure}, "
                     f"{item.classification.direction or '—'})" if item else
                     f"Linked to {position.operation_id}, which no longer exists")
    if position.notes:
        facts.append(position.notes)
    return [html.H4(f"{symbol_of(position)} · position {position.id}"), html.Ul([html.Li(f) for f in facts]),
            _legs_table(position)], view.SHOWN_INLINE


def selection_action(state, trigger, open_cell, history_cell, selected, version):
    """A click in either list selects that position; confirming the dialog deletes the selected one."""
    cell = {view.OPEN_GRID: open_cell, view.HISTORY_GRID: history_cell}.get(trigger)
    if cell and cell.get("rowId"):
        return {"id": int(cell["rowId"])}, no_update
    if trigger == view.CONFIRM and selected:
        state.positions.delete(selected["id"])
        return None, (version or 0) + 1
    return no_update, no_update


def operation_options(state, symbol, current):
    """Operations of that underlying in tab 1's list, latest first, plus the current link if it is not there."""
    symbol = (symbol or "").strip().upper()
    dates = state.dataset.usable_dates
    items = for_symbol(classified_operations(state.dataset, state.edits(), min(dates), max(dates)), symbol) \
        if symbol and dates else []
    options = []
    for item in sorted(items, key=lambda i: i.operation.id, reverse=True):
        op, c = item.operation, item.classification
        options.append({"label": f"{op.capture_date.isoformat()} · {op.summary['hora_inicio']} · {c.structure} · "
                                 f"{c.direction or '—'} · {op.premium / M:.3f}M", "value": op.id})
    if current and current not in {o["value"] for o in options}:
        options.insert(0, {"label": f"{current} (not listed for this underlying)", "value": current})
    return options


def prefill_from_operation(state, operation_id, nonce):
    """
    What the form starts with when a position is opened from an operation:
    the link and each leg's contract and side. Quantity and price are left
    empty, because the user's are not the operation's.
    """
    item = state.classified(operation_id) if operation_id else None
    if item is None:
        return None
    op, sides = item.operation, item.classification.sides
    legs = [{"option_type": leg_type(leg), "side": sides[i] if i < len(sides) else None,
             "strike": float(leg["strike"]), "exp_date": leg["exp_date"]}
            for i, leg in enumerate(op.legs[:forms.LEG_SLOTS])]
    note = (f"This operation has {len(op.legs)} legs: only the first {forms.LEG_SLOTS} were copied."
            if len(op.legs) > forms.LEG_SLOTS else "")
    return {"symbol": op.symbol, "operation_id": op.id, "legs": legs, "note": note, "nonce": nonce}


# --- the position form ----------------------------------------------------------

FORM_FIELDS = [
    ("style", (forms.FORM, "style")), ("title", (forms.FORM_TITLE, "children")),
    *forms.POSITION_FIELDS,
    *[(f"leg{slot}_{name}", (forms.leg_id(slot, name), prop)) for slot in range(forms.LEG_SLOTS)
      for name, prop in forms.LEG_FIELDS],
    ("message", (forms.FORM_MESSAGE, "children")), ("editing", (forms.EDITING, "data")),
    ("version", (ids.POSITIONS_VERSION, "data")),
]
FORM_OUTPUTS = [output for _, output in FORM_FIELDS]
LEG_NAMES = [name for name, _ in forms.LEG_FIELDS]


def _form(**values):
    return tuple(values.get(name, no_update) for name, _ in FORM_FIELDS)


def _open_form(title, editing, opened, symbol=None, commissions=None, notes=None, operation=None, legs=(), message=""):
    values = {}
    for slot in range(forms.LEG_SLOTS):
        leg = legs[slot] if slot < len(legs) else {}
        values.update({f"leg{slot}_{name}": leg.get(name) for name in LEG_NAMES})
    return _form(style=forms.SHOWN, title=title, editing=editing, opened=opened, symbol=symbol, commissions=commissions,
                 notes=notes, operation=operation, message=message, **values)


def _closed_form(**extra):
    return _form(style=forms.HIDDEN, editing=None, **extra)


def _edit_form(position):
    legs = [{name: getattr(leg, name) for name in LEG_NAMES} for leg in position.legs]
    return _open_form(f"Edit {symbol_of(position)} · position {position.id}", {"id": position.id}, position.opened_on,
                      symbol_of(position), position.commissions, position.notes, position.operation_id, legs)


def form_action(state, trigger, selected, prefill, editing, version, fields, rows):
    """Opens the form (new, edit or from an operation), cancels it, or saves it if it is valid."""
    today = state.today().isoformat()
    if trigger == view.NEW:
        return _open_form("New position", {"id": None}, today)
    if trigger == view.EDIT:
        position = _position(state, selected)
        return _edit_form(position) if position else _form()
    if trigger == view.PREFILL and prefill:
        note = html.P(prefill["note"], className="muted") if prefill.get("note") else ""
        return _open_form("New position", {"id": None}, today, prefill["symbol"], operation=prefill["operation_id"],
                          legs=prefill["legs"], message=note)
    if trigger == forms.FORM_CANCEL:
        return _closed_form()
    if trigger != forms.FORM_SAVE or not editing:
        return _form()
    position_id = editing.get("id")
    current = state.positions.get(position_id) if position_id else None
    parsed, errors = forms.parse_position(*fields, rows, current)
    if errors:
        return _form(message=errors_block(errors))
    values = (parsed.opened_on, parsed.legs, parsed.commissions, parsed.notes, parsed.operation_id)
    if current:
        state.positions.update(position_id, *values)
    else:
        state.positions.create(*values)
    return _closed_form(version=(version or 0) + 1)


# --- the closing form ------------------------------------------------------------

CLOSE_FIELDS = [
    ("style", (forms.CLOSE_FORM, "style")), ("title", (forms.CLOSE_TITLE, "children")),
    *[(f"{field}{slot}", (forms.close_id(slot, field), prop)) for slot in range(forms.LEG_SLOTS)
      for field, prop in (("row", "style"), ("label", "children"), ("date", "date"), ("price", "value"))],
    ("message", (forms.CLOSE_MESSAGE, "children")), ("closing", (forms.CLOSING, "data")),
    ("version", (ids.POSITIONS_VERSION, "data")),
]
CLOSE_OUTPUTS = [output for _, output in CLOSE_FIELDS]


def _close(**values):
    return tuple(values.get(name, no_update) for name, _ in CLOSE_FIELDS)


def _open_close_form(position, today):
    """A row per leg; a leg still open starts with today's date, so usually only the price is typed."""
    values = {}
    for slot in range(forms.LEG_SLOTS):
        leg = position.legs[slot] if slot < len(position.legs) else None
        values.update({
            f"row{slot}": forms.ROW_SHOWN if leg else forms.HIDDEN,
            f"label{slot}": leg_text(leg) if leg else "",
            f"date{slot}": (leg.exit_date or today) if leg else None,
            f"price{slot}": leg.exit_price if leg else None,
        })
    return _close(style=forms.SHOWN, title=f"Close {symbol_of(position)} · position {position.id}", message="",
                  closing={"id": position.id, "legs": [leg.id for leg in position.legs]}, **values)


def close_action(state, trigger, selected, closing, version, rows):
    """Opens the closing form, cancels it, or stores the exits if they are valid."""
    if trigger == view.CLOSE:
        position = _position(state, selected)
        return _open_close_form(position, state.today().isoformat()) if position else _close()
    if trigger == forms.CLOSE_CANCEL:
        return _close(style=forms.HIDDEN, closing=None)
    if trigger != forms.CLOSE_SAVE or not closing:
        return _close()
    exits, errors = forms.parse_exits(closing["legs"], rows)
    if not errors:
        try:
            state.positions.set_exits(closing["id"], exits)
        except (KeyError, ValueError) as error:
            errors = [str(error)]
    if errors:
        return _close(message=errors_block(errors))
    return _close(style=forms.HIDDEN, closing=None, version=(version or 0) + 1)


# --- wiring -------------------------------------------------------------------

def _rows_of(values, size):
    return [tuple(values[i:i + size]) for i in range(0, len(values), size)]


def _with_shared_version(outputs):
    return [Output(c, p, allow_duplicate=True) if c == ids.POSITIONS_VERSION else Output(c, p) for c, p in outputs]


def register(app, state):
    versions = [Input(ids.DATA_VERSION, "data"), Input(ids.EDITS_VERSION, "data"), Input(ids.POSITIONS_VERSION, "data")]

    @app.callback(Output(view.OPEN_GRID, "rowData"), Output(view.HISTORY_GRID, "rowData"), *versions)
    def refresh_lists(_data_version, _edits_version, _positions_version):
        return list_content(state)

    @app.callback(Output(view.CHART, "figure"), Output(view.HISTORY_SUMMARY, "children"),
                  Input(view.HISTORY_GRID, "virtualRowData"), Input(view.HISTORY_GRID, "rowData"))
    def refresh_history_view(virtual_rows, rows):
        return history_view(virtual_rows, rows)

    @app.callback(Output(view.DETAIL, "children"), Output(view.ACTIONS, "style"),
                  Input(view.SELECTED, "data"), *versions)
    def refresh_detail(selected, _data_version, _edits_version, _positions_version):
        return detail_content(state, selected)

    @app.callback(Output(view.CONFIRM, "displayed"), Input(view.DELETE, "n_clicks"), prevent_initial_call=True)
    def ask_to_delete(_clicks):
        return True

    @app.callback(Output(view.SELECTED, "data"), Output(ids.POSITIONS_VERSION, "data", allow_duplicate=True),
                  Input(view.OPEN_GRID, "cellClicked"), Input(view.HISTORY_GRID, "cellClicked"),
                  Input(view.CONFIRM, "submit_n_clicks"), State(view.SELECTED, "data"),
                  State(ids.POSITIONS_VERSION, "data"), prevent_initial_call=True)
    def handle_selection(open_cell, history_cell, _confirm, selected, version):
        return selection_action(state, ctx.triggered_id, open_cell, history_cell, selected, version)

    @app.callback(Output(forms.OPERATION, "options"), Input(forms.SYMBOL, "value"), Input(forms.OPERATION, "value"))
    def refresh_operations(symbol, current):
        return operation_options(state, symbol, current)

    @app.callback(Output(view.PREFILL, "data"), Output(ids.TABS, "value"),
                  Input(operations_view.NEW_POSITION, "n_clicks"), State(operations_view.GRID, "selectedRows"),
                  prevent_initial_call=True)
    def new_from_operation(clicks, selected):
        prefill = prefill_from_operation(state, selected[0]["id"] if selected else None, clicks)
        return prefill, "positions" if prefill else no_update

    position_states = [State(c, p) for _, (c, p) in forms.POSITION_FIELDS]
    leg_states = [State(forms.leg_id(slot, name), prop) for slot in range(forms.LEG_SLOTS)
                  for name, prop in forms.LEG_FIELDS]

    @app.callback(
        _with_shared_version(FORM_OUTPUTS),
        Input(view.NEW, "n_clicks"), Input(view.EDIT, "n_clicks"), Input(view.PREFILL, "data"),
        Input(forms.FORM_SAVE, "n_clicks"), Input(forms.FORM_CANCEL, "n_clicks"),
        State(view.SELECTED, "data"), State(forms.EDITING, "data"), State(ids.POSITIONS_VERSION, "data"),
        *position_states, *leg_states,
        prevent_initial_call=True,
    )
    def handle_form(_new, _edit, prefill, _save, _cancel, selected, editing, version, *values):
        fields, legs = values[:len(position_states)], values[len(position_states):]
        return form_action(state, ctx.triggered_id, selected, prefill, editing, version, fields,
                           _rows_of(legs, len(forms.LEG_FIELDS)))

    close_states = [State(forms.close_id(slot, field), prop) for slot in range(forms.LEG_SLOTS)
                    for field, prop in (("date", "date"), ("price", "value"))]

    @app.callback(
        _with_shared_version(CLOSE_OUTPUTS),
        Input(view.CLOSE, "n_clicks"), Input(forms.CLOSE_SAVE, "n_clicks"), Input(forms.CLOSE_CANCEL, "n_clicks"),
        State(view.SELECTED, "data"), State(forms.CLOSING, "data"), State(ids.POSITIONS_VERSION, "data"),
        *close_states,
        prevent_initial_call=True,
    )
    def handle_close(_close_click, _save, _cancel, selected, closing, version, *values):
        return close_action(state, ctx.triggered_id, selected, closing, version, _rows_of(values, 2))

    return {"refresh_lists": refresh_lists, "refresh_history_view": refresh_history_view,
            "refresh_detail": refresh_detail, "ask_to_delete": ask_to_delete, "handle_selection": handle_selection,
            "refresh_operations": refresh_operations, "new_from_operation": new_from_operation,
            "handle_form": handle_form, "handle_close": handle_close}
