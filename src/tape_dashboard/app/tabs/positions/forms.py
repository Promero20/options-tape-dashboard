"""The two pop-ups of tab 3, creating or editing a position and closing its legs, and how their values are read."""

from dataclasses import dataclass

from dash import dcc, html

from ....positions.store import Leg, check
from ....rules.sides import BUY, SELL
from ...manual_legs import CALL, PUT, iso_date_or_none, number_or_none

HIDDEN, SHOWN = {"display": "none"}, {"display": "block"}
ROW_SHOWN = {"display": "grid"}
LEG_SLOTS = 4

FORM, FORM_TITLE, FORM_SAVE, FORM_CANCEL, FORM_MESSAGE, EDITING = (
    "pos-form", "pos-form-title", "pos-form-save", "pos-form-cancel", "pos-form-message", "pos-editing")
OPENED, SYMBOL, COMMISSIONS, NOTES, OPERATION = (
    "pos-opened", "pos-symbol", "pos-commissions", "pos-notes", "pos-operation")
CLOSE_FORM, CLOSE_TITLE, CLOSE_SAVE, CLOSE_CANCEL, CLOSE_MESSAGE, CLOSING = (
    "pos-close-form", "pos-close-title", "pos-close-save", "pos-close-cancel", "pos-close-message", "pos-closing")

# name and property of the fields of a leg row, in the order parse_position reads them
LEG_FIELDS = (("option_type", "value"), ("side", "value"), ("strike", "value"), ("exp_date", "date"),
              ("quantity", "value"), ("entry_price", "value"))
POSITION_FIELDS = (("opened", (OPENED, "date")), ("symbol", (SYMBOL, "value")), ("commissions", (COMMISSIONS, "value")),
                   ("notes", (NOTES, "value")), ("operation", (OPERATION, "value")))


def leg_id(slot, field):
    return f"pos-leg-{slot}-{field.replace('_', '-')}"


def close_id(slot, field):
    return f"pos-close-{slot}-{field}"


def _leg_row(slot):
    number = {"type": "number", "min": 0, "step": "any"}
    return html.Div(className="pos-leg-row", children=[
        dcc.Dropdown(id=leg_id(slot, "option_type"), placeholder="Type",
                     options=[{"label": "Call", "value": CALL}, {"label": "Put", "value": PUT}]),
        dcc.Dropdown(id=leg_id(slot, "side"), placeholder="Side",
                     options=[{"label": "Buy", "value": BUY}, {"label": "Sell", "value": SELL}]),
        dcc.Input(id=leg_id(slot, "strike"), placeholder="Strike", **number),
        dcc.DatePickerSingle(id=leg_id(slot, "exp_date"), display_format="YYYY-MM-DD", first_day_of_week=1,
                             placeholder="Expiration"),
        dcc.Input(id=leg_id(slot, "quantity"), placeholder="Quantity", **{**number, "min": 1, "step": 1}),
        dcc.Input(id=leg_id(slot, "entry_price"), placeholder="Entry price", **number),
    ])


def _modal(element_id, *children):
    return html.Div(id=element_id, className="modal-backdrop", style=HIDDEN,
                    children=html.Div(className="modal-box", children=list(children)))


def position_form():
    return _modal(
        FORM,
        html.H3(id=FORM_TITLE),
        html.Div(className="pos-fields", children=[
            html.Div([html.Label("Opened", htmlFor=OPENED),
                      dcc.DatePickerSingle(id=OPENED, display_format="YYYY-MM-DD", first_day_of_week=1)]),
            html.Div([html.Label("Underlying", htmlFor=SYMBOL), dcc.Input(id=SYMBOL, type="text", debounce=True)]),
            html.Div([html.Label("Commissions (total)", htmlFor=COMMISSIONS),
                      dcc.Input(id=COMMISSIONS, type="number", min=0, step="any")]),
        ]),
        html.Label("Linked operation (optional)", htmlFor=OPERATION),
        dcc.Dropdown(id=OPERATION, options=[], placeholder="Choose the operation this position mimics"),
        html.Label("Legs"),
        html.Div(className="pos-leg-row pos-leg-head", children=[
            html.Span("Type"), html.Span("Side"), html.Span("Strike"), html.Span("Expiration"), html.Span("Quantity"),
            html.Span("Entry price")]),
        *[_leg_row(slot) for slot in range(LEG_SLOTS)],
        html.Label("Notes", htmlFor=NOTES),
        dcc.Textarea(id=NOTES, style={"width": "100%"}),
        html.Div(id=FORM_MESSAGE, className="form-message"),
        html.Div(className="modal-buttons", children=[
            html.Button("Save", id=FORM_SAVE, className="btn primary"),
            html.Button("Cancel", id=FORM_CANCEL, className="btn"),
        ]),
    )


def close_form():
    rows = [html.Div(id=close_id(slot, "row"), className="pos-close-row", style=HIDDEN, children=[
        html.Span(id=close_id(slot, "label")),
        dcc.DatePickerSingle(id=close_id(slot, "date"), display_format="YYYY-MM-DD", first_day_of_week=1),
        dcc.Input(id=close_id(slot, "price"), type="number", min=0, step="any", placeholder="Exit price"),
    ]) for slot in range(LEG_SLOTS)]
    return _modal(
        CLOSE_FORM,
        html.H3(id=CLOSE_TITLE),
        html.P("Enter the exit price of the legs you closed. A leg without a price stays open; emptying the price of "
               "a closed leg reopens it.", className="muted"),
        *rows,
        html.Div(id=CLOSE_MESSAGE, className="form-message"),
        html.Div(className="modal-buttons", children=[
            html.Button("Save", id=CLOSE_SAVE, className="btn primary"),
            html.Button("Cancel", id=CLOSE_CANCEL, className="btn"),
        ]),
    )


@dataclass(frozen=True)
class PositionInput:
    opened_on: str
    legs: tuple
    commissions: float
    notes: str
    operation_id: str | None


def _is_blank(value):
    return value is None or value == ""


def _parse_leg(symbol, row, number, current):
    """A Leg, or None for an empty row, and what is wrong with it. An edited leg keeps its close."""
    if all(_is_blank(value) for value in row):
        return None, []
    option_type, side, strike, exp_date, quantity, entry_price = row
    strike, quantity, entry_price = number_or_none(strike), number_or_none(quantity), number_or_none(entry_price)
    exp_date = iso_date_or_none(exp_date)
    if None in (option_type, side, strike, exp_date, quantity, entry_price):
        return None, [f"Leg {number}: fill in every field, or leave the whole row empty."]
    exit_date, exit_price = (current.exit_date, current.exit_price) if current else (None, None)
    return Leg(symbol, option_type, strike, exp_date, side, quantity, entry_price, exit_date, exit_price), []


def parse_position(opened, symbol, commissions, notes, operation, rows, current=None):
    """The form's values as a PositionInput and an empty list, or None and what is wrong."""
    errors, legs = [], []
    opened_on = iso_date_or_none(opened)
    symbol = (symbol or "").strip().upper()
    fee = 0.0 if _is_blank(commissions) else number_or_none(commissions)
    if opened_on is None:
        errors.append("Pick the opening date.")
    if not symbol:
        errors.append("Enter the underlying.")
    if fee is None:
        errors.append("The commissions must be a number.")
    existing = current.legs if current else ()
    for slot, row in enumerate(rows):
        leg, problems = _parse_leg(symbol, row, slot + 1, existing[slot] if slot < len(existing) else None)
        errors += problems
        if leg is not None:
            legs.append(leg)
    if errors:
        return None, errors
    errors = check(opened_on, legs, fee)
    if errors:
        return None, errors
    return PositionInput(opened_on, tuple(legs), fee, notes or "", operation or None), []


def parse_exits(leg_ids, rows):
    """{leg id: (date, price), or None if it has no price} from the closing form, and what is wrong."""
    exits, errors = {}, []
    for number, (leg_id_, (exit_date, price)) in enumerate(zip(leg_ids, rows), 1):
        if _is_blank(price):
            exits[leg_id_] = None
            continue
        parsed_date, parsed_price = iso_date_or_none(exit_date), number_or_none(price)
        if parsed_date is None:
            errors.append(f"Leg {number}: pick the closing date.")
        if parsed_price is None:
            errors.append(f"Leg {number}: the price must be a number.")
        exits[leg_id_] = (parsed_date, parsed_price)
    return (None, errors) if errors else (exits, [])
