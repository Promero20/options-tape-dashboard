"""
Callbacks of the operations tab. Each callback is a thin wrapper around a
controller function that takes the application state and plain values, so
the controllers can be tested without a browser.
"""

from dash import Input, Output, State, ctx, html, no_update

from ....edits.apply import classified_operations
from ....rules.classification import NET
from ... import ids
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


# Order of the modal outputs; every controller result follows it.
MODAL_OUTPUTS = [
    (view.MODAL, "style"), (view.EDITING, "data"), (view.MODAL_TITLE, "children"), (view.MODAL_INFO, "children"),
    (view.DIRECTION_BOX, "style"), (view.DIRECTION_INPUT, "options"), (view.DIRECTION_INPUT, "value"),
    (view.STRATEGY_BOX, "style"), (view.STRATEGY_INPUT, "options"), (view.STRATEGY_INPUT, "value"),
    (view.READ_ONLY_TEXT, "children"), (view.MODAL_LEGS, "children"), (ids.EDITS_VERSION, "data"),
]
UNCHANGED = tuple(no_update for _ in MODAL_OUTPUTS)


def _closed(version):
    return (view.HIDDEN, None) + (no_update,) * (len(MODAL_OUTPUTS) - 3) + (version,)


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
    is_direction, is_strategy = editor.kind == editing.DIRECTION, editor.kind == editing.STRATEGY
    return (
        view.SHOWN, {"id": item.operation.id, "kind": editor.kind},
        f"{item.operation.symbol} · {c.structure}", info,
        view.SHOWN if is_direction else view.HIDDEN, options if is_direction else [],
        editor.current if is_direction else None,
        view.SHOWN if is_strategy else view.HIDDEN, options if is_strategy else [],
        editor.current if is_strategy else None,
        editor.reason, view.legs_table(leg_rows(item)), no_update,
    )


def modal_action(state, trigger, cell, editing_data, direction, strategy, version):
    """Opens the editor on a click in the Direction column; saves, clears or closes it."""
    version = version or 0
    if trigger == view.GRID:
        if not cell or cell.get("colId") != "direction" or not cell.get("rowId"):
            return UNCHANGED
        return open_editor(state, cell["rowId"])
    if not editing_data:
        return _closed(no_update)
    kind = editing_data["kind"]
    if trigger == view.CLOSE or kind == editing.READ_ONLY:
        return _closed(no_update)
    if trigger == view.SAVE:
        value = direction if kind == editing.DIRECTION else strategy
        editing.save(state.store, editing_data["id"], kind, value)
    elif trigger == view.CLEAR:
        editing.save(state.store, editing_data["id"], kind, None)
    else:
        return UNCHANGED
    return _closed(version + 1)


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
        Input(view.CLOSE, "n_clicks"),
        State(view.EDITING, "data"), State(view.DIRECTION_INPUT, "value"), State(view.STRATEGY_INPUT, "value"),
        State(ids.EDITS_VERSION, "data"),
        prevent_initial_call=True,
    )
    def handle_modal(cell, _save, _clear, _close, editing_data, direction, strategy, version):
        return modal_action(state, ctx.triggered_id, cell, editing_data, direction, strategy, version)

    return {"toggle_dates": toggle_dates, "show_columns": show_columns, "refresh_grid": refresh_grid,
            "show_detail": show_detail, "handle_modal": handle_modal}
