"""
Callbacks of the operations tab. Each callback is a thin wrapper around a
controller function that takes the application state and plain values, so
the controllers can be tested without a browser.
"""

from dash import Input, Output, State, ctx, html, no_update

from ....edits.apply import classified_operations
from ....rules.classification import NET
from ... import ids
from ... import manual_legs as ml
from ...leg_form import errors_block, preview_block
from . import editing
from . import view
from .ranges import CUSTOM, resolve_range
from .rows import column_defs, destination_counts, leg_rows, operation_rows


# --- controllers --------------------------------------------------------------

def grid_content(state, preset, start, end):
    """Rows for the grid, the note above it and the summary below it."""
    r = resolve_range(state.dataset, preset, state.today(), start, end)
    if r.empty:
        return [], r.note, ""
    items = classified_operations(state.dataset, state.edits(), r.start, r.end)
    period = r.start.isoformat() if r.start == r.end else f"{r.start.isoformat()} → {r.end.isoformat()}"
    counts = ", ".join(f"{dest} {n}" for dest, n in destination_counts(items).items())
    summary = f"{len(items)} operations above the threshold ({period}): {counts}"
    note = r.note or ("" if items else "No operations in this range.")
    return operation_rows(items), note, summary


def detail_content(state, operation_id):
    """Panel with the selected operation and its legs."""
    item = state.classified(operation_id) if operation_id else None
    if item is None:
        return view.empty_detail()
    op, c = item.operation, item.classification
    premium = f"{c.premium / 1_000_000:+.3f}M" if c.destination == NET else f"{c.premium / 1_000_000:.3f}M"
    facts = [
        f"Captured {op.capture_date.isoformat()}, traded {', '.join(d.isoformat() for d in op.trade_dates)}",
        f"{c.structure} → {c.destination}" + (f" ({c.wall})" if c.wall else ""),
        f"Direction: {c.direction or '—'}" + (" (corrected by hand)" if item.override else ""),
        f"Strike {c.strike:g}, expiration {c.expiration}, premium {premium}" if c.strike is not None
        else f"Gross premium {op.premium / 1_000_000:.3f}M",
    ]
    notes = list(c.warnings) + list(item.problems)
    return [
        html.H4(f"{op.symbol} · {op.id}"),
        html.Ul([html.Li(f) for f in facts]),
        html.Ul([html.Li(n) for n in notes], className="notes") if notes else None,
        view.legs_table(leg_rows(item)),
    ]


# Order of the modal outputs, by name; every controller result follows it.
MODAL_FIELDS = [
    ("style", (view.MODAL, "style")), ("editing", (view.EDITING, "data")),
    ("title", (view.MODAL_TITLE, "children")), ("info", (view.MODAL_INFO, "children")),
    ("direction_box", (view.DIRECTION_BOX, "style")), ("direction_options", (view.DIRECTION_INPUT, "options")),
    ("direction", (view.DIRECTION_INPUT, "value")),
    ("strategy_box", (view.STRATEGY_BOX, "style")), ("strategy_options", (view.STRATEGY_INPUT, "options")),
    ("strategy", (view.STRATEGY_INPUT, "value")),
    ("leg_box", (view.MANUAL_LEG_BOX, "style")),
    *zip(("option_type", "strike", "exp_date", "price", "size"), view.LEG.leg_values),
    ("delete_button", (view.DELETE_LEG, "style")),
    ("read_only", (view.READ_ONLY_TEXT, "children")), ("legs", (view.MODAL_LEGS, "children")),
    ("message", (view.MODAL_MESSAGE, "children")), ("version", (ids.EDITS_VERSION, "data")),
]
MODAL_OUTPUTS = [output for _, output in MODAL_FIELDS]
UNCHANGED = tuple(no_update for _ in MODAL_OUTPUTS)


def _modal(**values):
    return tuple(values.get(name, no_update) for name, _ in MODAL_FIELDS)


def _closed(version):
    return _modal(style=view.HIDDEN, editing=None, version=version)


def open_editor(state, operation_id):
    item = state.classified(operation_id)
    if item is None:
        return UNCHANGED
    editor = editing.editor_for(item)
    c = item.classification
    info = [html.Div(f"ID {item.operation.id}"),
            html.Div(f"Now: {c.direction or '—'} → {c.destination}"
                     + (" (corrected by hand)" if item.override else ""))]
    info += [html.Div(w, className="warning-text") for w in c.warnings]
    options = [{"label": label, "value": value} for value, label in editor.options]
    is_direction = editor.kind == editing.DIRECTION
    has_type = editor.kind in (editing.STRATEGY, editing.MANUAL_LEG)
    has_leg = editor.kind == editing.MANUAL_LEG
    editing_data = {"id": item.operation.id, "kind": editor.kind}
    values = dict(
        style=view.SHOWN, title=f"{item.operation.symbol} · {c.structure}", info=info,
        direction_box=view.SHOWN if is_direction else view.HIDDEN, direction_options=options if is_direction else [],
        direction=editor.current if is_direction else None,
        strategy_box=view.SHOWN if has_type else view.HIDDEN, strategy_options=options if has_type else [],
        strategy=editor.current if has_type else None,
        leg_box=view.SHOWN if has_leg else view.HIDDEN, delete_button=view.SHOWN_INLINE if has_leg else view.HIDDEN,
        read_only=editor.reason, legs=view.legs_table(leg_rows(item)), message="",
    )
    if has_leg:
        leg = editor.manual_leg
        editing_data["leg_id"] = leg.id
        values.update(option_type=leg.option_type, strike=leg.strike, exp_date=leg.exp_date, price=leg.price,
                      size=leg.size)
    return _modal(editing=editing_data, **values)


def _save_manual_leg(state, editing_data, leg_values, strategy):
    """Saves the edited manual leg and its type; returns what is wrong, if anything."""
    op = state.operation(editing_data["id"])
    if op is None:
        return ["The operation no longer exists: reload the data."]
    leg, errors = ml.parse_leg(*leg_values)
    if errors:
        return errors
    try:
        ml.save(state.store, op, leg, strategy, leg_id=editing_data["leg_id"])
    except ValueError as error:
        return [str(error)]
    return []


def modal_action(state, trigger, cell, editing_data, direction, strategy, version, leg_values=(None,) * 5):
    """
    Opens the editor on a click in the Direction column; saves, clears or
    closes it. For an operation completed by hand it also saves or deletes
    the manual leg (decision 0030).
    """
    version = version or 0
    if trigger == view.GRID:
        if not cell or cell.get("colId") != "direction" or not cell.get("rowId"):
            return UNCHANGED
        return open_editor(state, cell["rowId"])
    if not editing_data:
        return _closed(no_update)
    kind, operation_id = editing_data["kind"], editing_data["id"]
    if trigger == view.CLOSE or kind == editing.READ_ONLY:
        return _closed(no_update)
    if trigger == view.SAVE and kind == editing.MANUAL_LEG:
        errors = _save_manual_leg(state, editing_data, leg_values, strategy)
        if errors:
            return _modal(message=errors_block(errors))
    elif trigger == view.SAVE:
        editing.save(state.store, operation_id, kind, direction if kind == editing.DIRECTION else strategy)
    elif trigger == view.CLEAR:
        editing.save(state.store, operation_id, kind, None)
    elif trigger == view.DELETE_LEG and kind == editing.MANUAL_LEG:
        ml.delete(state.store, operation_id, editing_data["leg_id"])
    else:
        return UNCHANGED
    return _closed(version + 1)


def leg_feedback(state, editing_data, leg_values, strategy):
    """
    While a manual leg is edited in the pop-up: the operation types that fit
    and the preview. For any other operation the preview is emptied.
    """
    if not editing_data or editing_data.get("kind") != editing.MANUAL_LEG:
        return no_update, None
    op = state.operation(editing_data["id"])
    if op is None:
        return no_update, None
    form = ml.form_state(op, leg_values, strategy)
    return [{"label": label, "value": key} for key, label in form.options], preview_block(form)


# --- wiring -------------------------------------------------------------------

def register(app, state):
    @app.callback(Output(view.DATES, "disabled"), Input(view.RANGE, "value"))
    def toggle_dates(preset):
        return preset != CUSTOM

    @app.callback(Output(view.GRID, "columnDefs"), Input(view.COLUMNS, "value"))
    def show_columns(visible):
        return column_defs(visible or ())

    @app.callback(
        Output(view.GRID, "rowData"), Output(view.RANGE_NOTE, "children"), Output(view.SUMMARY, "children"),
        Input(view.RANGE, "value"), Input(view.DATES, "start_date"), Input(view.DATES, "end_date"),
        Input(ids.DATA_VERSION, "data"), Input(ids.EDITS_VERSION, "data"),
    )
    def refresh_grid(preset, start, end, _data_version, _edits_version):
        return grid_content(state, preset, start, end)

    @app.callback(Output(view.DETAIL, "children"),
                  Input(view.GRID, "selectedRows"), Input(ids.EDITS_VERSION, "data"))
    def show_detail(selected, _edits_version):
        return detail_content(state, selected[0]["id"] if selected else None)

    @app.callback(
        [Output(component, prop) for component, prop in MODAL_OUTPUTS],
        Input(view.GRID, "cellClicked"), Input(view.SAVE, "n_clicks"), Input(view.CLEAR, "n_clicks"),
        Input(view.DELETE_LEG, "n_clicks"), Input(view.CLOSE, "n_clicks"),
        State(view.EDITING, "data"), State(view.DIRECTION_INPUT, "value"), State(view.STRATEGY_INPUT, "value"),
        State(ids.EDITS_VERSION, "data"), *[State(c, p) for c, p in view.LEG.leg_values],
        prevent_initial_call=True,
    )
    def handle_modal(cell, _save, _clear, _delete, _close, editing_data, direction, strategy, version,
                     option_type, strike, exp_date, price, size):
        return modal_action(state, ctx.triggered_id, cell, editing_data, direction, strategy, version,
                            (option_type, strike, exp_date, price, size))

    @app.callback(
        Output(view.STRATEGY_INPUT, "options", allow_duplicate=True), Output(view.LEG.preview, "children"),
        Input(view.EDITING, "data"), *[Input(c, p) for c, p in view.LEG.leg_values],
        Input(view.STRATEGY_INPUT, "value"),
        prevent_initial_call=True,
    )
    def refresh_leg_feedback(editing_data, option_type, strike, exp_date, price, size, strategy):
        return leg_feedback(state, editing_data, (option_type, strike, exp_date, price, size), strategy)

    return {"toggle_dates": toggle_dates, "show_columns": show_columns, "refresh_grid": refresh_grid,
            "show_detail": show_detail, "handle_modal": handle_modal, "refresh_leg_feedback": refresh_leg_feedback}
