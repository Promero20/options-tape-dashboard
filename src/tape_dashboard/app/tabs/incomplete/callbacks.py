"""
Callbacks of the incomplete-legs tab. As in tab 1, each callback wraps a
controller that takes the application state and plain values, so the tests
call the controllers without a browser.
"""

from datetime import date

from dash import Input, Output, State, ctx, no_update

from ....edits.apply import pending_operations
from ....rules.classification import NET, WALLS
from ... import ids
from ... import manual_legs as ml
from ...leg_form import errors_block, preview_block
from . import view
from .rows import known_leg_text, pending_row


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


# --- controllers --------------------------------------------------------------

def day_options(state):
    """Usable captures, latest first, each with its number of pending operations."""
    dataset, edits = state.dataset, state.edits()
    return [{"label": f"{d.isoformat()} ({len(pending_operations(dataset, edits, d))})", "value": d.isoformat()}
            for d in sorted(dataset.usable_dates, reverse=True)]


def default_day(state):
    """Today's capture or, if there is none yet, the latest one (decision 0013)."""
    day, _ = state.dataset.resolve_today(state.today())
    return day.isoformat() if day else None


def day_note(state, value):
    today = state.today()
    day, is_today = state.dataset.resolve_today(today)
    if day is None:
        return "There are no captures yet."
    if not is_today and value == day.isoformat():
        return f"No capture for today ({today.isoformat()}); showing the latest one ({day.isoformat()})."
    return ""


def pending_content(state, value):
    """Rows of the list and the line under it."""
    day = _day(value)
    if day is None:
        return [], ""
    rows = [pending_row(item) for item in pending_operations(state.dataset, state.edits(), day)]
    return rows, f"{len(rows)} operations with a missing leg above the threshold ({day.isoformat()})"


FORM_FIELDS = [
    ("title", (view.FORM_TITLE, "children")), ("known", (view.KNOWN_LEG, "children")),
    ("style", (view.FORM, "style")),
    *zip(("option_type", "strike", "exp_date", "price", "size"), view.LEG.leg_values),
    ("strategy", (view.LEG.strategy, "value")), ("selected", (view.SELECTED, "data")),
    ("message", (view.MESSAGE, "children")), ("version", (ids.EDITS_VERSION, "data")),
]
FORM_OUTPUTS = [output for _, output in FORM_FIELDS]


def _outputs(**values):
    return tuple(values.get(name, no_update) for name, _ in FORM_FIELDS)


def _closed(**extra):
    return _outputs(title=view.FORM_TITLE_TEXT, known=view.NO_SELECTION, style=view.HIDDEN, selected=None,
                    **extra)


def open_form(state, operation_id):
    """The form for one pending operation, with the known leg's type, expiration and size."""
    op = state.operation(operation_id) if operation_id else None
    if op is None:
        return _closed()
    problems = state.classified(op.id).problems
    message = errors_block([f"A manual leg saved earlier could not be applied ({p}); saving replaces it."
                            for p in problems]) if problems else ""
    return _outputs(title=f"Missing leg: {op.symbol} · {op.id}", known=known_leg_text(op), style=view.SHOWN,
                    strategy=None, selected={"id": op.id}, message=message, **ml.prefill(op))


def _where(classification):
    if classification.destination == NET:
        return f"net, {classification.direction}"
    if classification.destination == WALLS:
        return f"walls, {classification.wall}"
    return classification.destination


def form_action(state, trigger, selected_rows, values, strategy, selected, version):
    """Selecting a row opens the form; Save stores the leg and its type, or shows what is wrong."""
    if trigger == view.GRID:
        # after a save the row leaves the list and the selection empties: the message stays
        return open_form(state, selected_rows[0]["id"]) if selected_rows else _closed()
    if trigger != view.SAVE or not selected:
        return _outputs()
    op = state.operation(selected["id"])
    if op is None:
        return _outputs(message=errors_block(["The operation no longer exists: reload the data."]))
    leg, errors = ml.parse_leg(*values)
    # a pending operation only has a stored leg if that leg could not be applied: it is replaced
    stored = state.edits().manual_legs.get(op.id)
    if not errors:
        try:
            ml.save(state.store, op, leg, strategy, leg_id=stored[0].id if stored else None)
        except ValueError as error:
            errors = [str(error)]
    if errors:
        return _outputs(message=errors_block(errors))
    saved = state.classified(op.id)
    return _closed(message=f"Saved: {op.symbol} {op.id} is now in the Operations tab "
                           f"({_where(saved.classification)}).", version=(version or 0) + 1)


def form_feedback(state, selected, values, strategy):
    """Operation types that fit the legs as they are being typed, and the preview."""
    op = state.operation(selected["id"]) if selected else None
    if op is None:
        return [], None
    form = ml.form_state(op, values, strategy)
    return [{"label": label, "value": key} for key, label in form.options], preview_block(form)


# --- wiring -------------------------------------------------------------------

def register(app, state):
    versions = [Input(ids.DATA_VERSION, "data"), Input(ids.EDITS_VERSION, "data")]
    leg_inputs = [Input(component, prop) for component, prop in view.LEG.leg_values]
    leg_states = [State(component, prop) for component, prop in view.LEG.leg_values]

    @app.callback(Output(view.DAY, "options"), *versions, prevent_initial_call=True)
    def refresh_days(_data_version, _edits_version):
        return day_options(state)

    @app.callback(Output(view.DAY_NOTE, "children"), Input(view.DAY, "value"), Input(ids.DATA_VERSION, "data"))
    def refresh_note(day, _data_version):
        return day_note(state, day)

    @app.callback(Output(view.GRID, "rowData"), Output(view.SUMMARY, "children"), Input(view.DAY, "value"),
                  *versions)
    def refresh_pending(day, _data_version, _edits_version):
        return pending_content(state, day)

    @app.callback(
        [Output(c, p, allow_duplicate=True) if c == ids.EDITS_VERSION else Output(c, p) for c, p in FORM_OUTPUTS],
        Input(view.GRID, "selectedRows"), Input(view.SAVE, "n_clicks"),
        *leg_states, State(view.LEG.strategy, "value"), State(view.SELECTED, "data"),
        State(ids.EDITS_VERSION, "data"),
        prevent_initial_call=True,
    )
    def handle_form(selected_rows, _save, option_type, strike, exp_date, price, size, strategy, selected, version):
        return form_action(state, ctx.triggered_id, selected_rows, (option_type, strike, exp_date, price, size),
                           strategy, selected, version)

    @app.callback(Output(view.LEG.strategy, "options"), Output(view.LEG.preview, "children"),
                  Input(view.SELECTED, "data"), *leg_inputs, Input(view.LEG.strategy, "value"))
    def refresh_feedback(selected, option_type, strike, exp_date, price, size, strategy):
        return form_feedback(state, selected, (option_type, strike, exp_date, price, size), strategy)

    return {"refresh_days": refresh_days, "refresh_note": refresh_note, "refresh_pending": refresh_pending,
            "handle_form": handle_form, "refresh_feedback": refresh_feedback}
