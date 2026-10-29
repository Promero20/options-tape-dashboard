"""
The manual leg that completes an operation with incomplete legs: entered in
tab 2, edited or deleted from tab 1's pop-up (decisions 0011 and 0030).

Pure logic, no Dash: reading the form, building the completed operation with
the level-3 script, the operation types that fit, a preview of the result,
and saving. Nothing is written unless the whole edit is valid.
"""

from dataclasses import dataclass
from datetime import date

from ..data.loading import build_contract_symbol
from ..edits.apply import with_manual_legs
from ..edits.store import ManualLeg
from ..rules import strategies
from ..rules.classification import NET, WALLS, Override, classify
from ..rules.sides import option_type as leg_type

CALL, PUT = "call", "put"
M = 1_000_000


@dataclass(frozen=True)
class LegInput:
    option_type: str
    strike: float
    exp_date: str
    price: float
    size: int


def _number(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_date(value):
    try:
        return date.fromisoformat(str(value)[:10]).isoformat() if value else None
    except ValueError:
        return None


def parse_leg(option_type, strike, exp_date, price, size):
    """The form's values as a LegInput and an empty list, or None and the errors."""
    strike, price, size, exp_date = _number(strike), _number(price), _number(size), _iso_date(exp_date)
    errors = []
    if option_type not in (CALL, PUT):
        errors.append("Choose call or put.")
    if strike is None or strike <= 0:
        errors.append("The strike must be a number above 0.")
    if exp_date is None:
        errors.append("Pick the expiration date.")
    if price is None or price < 0:
        errors.append("The price must be a number, 0 or more.")
    if size is None or size <= 0 or size != int(size):
        errors.append("The size must be a whole number of contracts above 0.")
    if errors:
        return None, errors
    return LegInput(option_type, strike, exp_date, price, int(size)), []


def prefill(operation):
    """Type, expiration and size of the known leg; strike and price are left to the user (decision 0030)."""
    known = operation.legs[0]
    return {"option_type": leg_type(known), "strike": None, "exp_date": known["exp_date"],
            "price": None, "size": known["size"]}


def from_manual_leg(leg):
    return LegInput(leg.option_type, leg.strike, leg.exp_date, leg.price, leg.size)


def candidate(operation, leg):
    """
    The operation, as rebuilt and without edits, completed with this leg and
    recomputed by the script: (operation, None) or (None, error).
    """
    contract = build_contract_symbol(operation.symbol, leg.exp_date, leg.strike, leg.option_type)
    if any(known["contract_symbol"] == contract for known in operation.legs):
        return None, f"The manual leg is the same contract as the known leg ({contract})."
    manual = ManualLeg(0, operation.id, leg.option_type, leg.strike, leg.exp_date, leg.price, leg.size)
    return with_manual_legs(operation, [manual]), None


def type_options(completed):
    """(key, label) of the operation types that fit the completed operation's legs, "Don't know" last."""
    return [(s.key, s.label) for s in strategies.options_for(completed.legs)]


def preview(completed, strategy):
    """What the operation becomes with that type: a one-line summary and the classification's warnings."""
    c = classify(completed, Override(strategy=strategy) if strategy else None)
    if c.destination == NET:
        text = (f"{c.structure} → net, {c.direction}, strike {c.strike:g}, {c.expiration}, "
                f"{c.premium / M:+.3f}M")
    elif c.destination == WALLS:
        text = f"{c.structure} → walls, {c.wall} at {c.strike:g}, {c.expiration}, {c.premium / M:.3f}M"
    else:
        text = f"{c.structure} → {c.destination}, gross premium {c.premium / M:.3f}M"
    return text, list(c.warnings)


@dataclass(frozen=True)
class FormState:
    """What the form shows while it is being filled in."""
    options: list            # (key, label) of the operation types that fit
    text: str | None = None  # the preview, once a type is chosen
    warnings: list = ()
    errors: list = ()


def form_state(operation, values, strategy):
    """Operation types and preview for the form's current values (option_type, strike, exp_date, price, size)."""
    leg, errors = parse_leg(*values)
    if errors:
        return FormState([], errors=errors)
    completed, error = candidate(operation, leg)
    if error:
        return FormState([], errors=[error])
    options = type_options(completed)
    if strategy not in dict(options):
        return FormState(options, warnings=["Choose the operation type to see the result."])
    text, warnings = preview(completed, strategy)
    return FormState(options, text, warnings)


def check(operation, leg, strategy):
    """Every reason not to save this leg with this type; empty if it can be saved."""
    completed, error = candidate(operation, leg)
    if error:
        return [error]
    if not strategy:
        return ["Choose the operation type (\"Don't know\" is an option)."]
    if strategy not in dict(type_options(completed)):
        return ["The operation type does not fit these legs: choose it again."]
    return []


def save(store, operation, leg, strategy, leg_id=None):
    """
    Adds the manual leg (or updates leg `leg_id`) and sets the operation type.
    Raises ValueError, without writing anything, if the edit is not valid or
    if the operation already has a manual leg and none is being updated.
    """
    problems = check(operation, leg, strategy)
    if leg_id is None and store.snapshot().manual_legs.get(operation.id):
        problems.append("This operation already has a manual leg: edit it from the Operations tab.")
    if problems:
        raise ValueError(" ".join(problems))
    values = (leg.option_type, leg.strike, leg.exp_date, leg.price, leg.size)
    if leg_id is None:
        store.add_manual_leg(operation.id, *values)
    else:
        store.update_manual_leg(leg_id, *values)
    store.set_strategy(operation.id, strategy)


def delete(store, operation_id, leg_id):
    """Deletes the manual leg and the operation type chosen with it: the operation is pending again."""
    store.delete_manual_leg(leg_id)
    store.clear_override(operation_id)
