"""
The manual-leg fields, shared by tab 2's form and tab 1's pop-up. Each place
passes its own ID prefix, so both can be on the page at the same time.
"""

from dataclasses import dataclass

from dash import dcc, html

from .manual_legs import CALL, PUT

DEBOUNCE_SECONDS = 0.6


@dataclass(frozen=True)
class LegFormIds:
    option_type: str
    strike: str
    exp_date: str
    price: str
    size: str
    strategy: str
    preview: str

    @classmethod
    def with_prefix(cls, prefix):
        names = ("type", "strike", "expiration", "price", "size", "strategy", "preview")
        return cls(*(f"{prefix}-leg-{name}" for name in names))

    @property
    def leg_values(self):
        """(component id, property) of the five leg fields, in parse_leg's order."""
        return [(self.option_type, "value"), (self.strike, "value"), (self.exp_date, "date"),
                (self.price, "value"), (self.size, "value")]


def preview_area(ids):
    return html.Div(id=ids.preview, className="preview")


def leg_fields(ids, with_strategy=True, with_preview=True):
    children = [
        html.Label("Type", htmlFor=ids.option_type),
        dcc.RadioItems(id=ids.option_type, options=[{"label": "Call", "value": CALL}, {"label": "Put", "value": PUT}],
                       inline=True, className="choices"),
        html.Div(className="leg-grid", children=[
            html.Div([html.Label("Strike", htmlFor=ids.strike),
                      dcc.Input(id=ids.strike, type="number", min=0, step="any", debounce=DEBOUNCE_SECONDS)]),
            html.Div([html.Label("Expiration", htmlFor=ids.exp_date),
                      dcc.DatePickerSingle(id=ids.exp_date, display_format="YYYY-MM-DD", first_day_of_week=1)]),
            html.Div([html.Label("Price", htmlFor=ids.price),
                      dcc.Input(id=ids.price, type="number", min=0, step="any", debounce=DEBOUNCE_SECONDS)]),
            html.Div([html.Label("Size (contracts)", htmlFor=ids.size),
                      dcc.Input(id=ids.size, type="number", min=1, step=1, debounce=DEBOUNCE_SECONDS)]),
        ]),
    ]
    if with_strategy:
        children += [
            html.Label("Operation type", htmlFor=ids.strategy),
            dcc.Dropdown(id=ids.strategy, options=[], placeholder="Choose the operation type"),
        ]
    if with_preview:
        children.append(preview_area(ids))
    return html.Div(className="leg-form", children=children)


def errors_block(errors):
    return html.Ul([html.Li(e) for e in errors], className="form-errors")


def preview_block(form_state):
    """What the preview area shows for a manual_legs.FormState: what is wrong, or the result and its warnings."""
    if form_state.errors:
        return errors_block(form_state.errors)
    parts = [html.P(["Result: ", html.Strong(form_state.text)])] if form_state.text else []
    if form_state.warnings:
        parts.append(html.Ul([html.Li(w) for w in form_state.warnings], className="notes"))
    return parts
