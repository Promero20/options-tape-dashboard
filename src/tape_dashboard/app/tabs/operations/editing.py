"""What can be corrected on an operation, and how a correction is saved (decisions 0020 and 0021)."""

from dataclasses import dataclass

from ....rules import strategies
from ....rules.classification import BEAR, BULL, UNDETERMINED

DIRECTION, STRATEGY, READ_ONLY = "direction", "strategy", "read-only"
DIRECTION_OPTIONS = ((BULL, "Bull"), (BEAR, "Bear"), (UNDETERMINED, "Undetermined"))


@dataclass(frozen=True)
class Editor:
    kind: str
    options: tuple = ()          # (value, label) pairs
    current: str | None = None   # value of the current correction, if any
    reason: str = ""             # why it cannot be edited (read-only)


def editor_for(item):
    """
    Single-legs are corrected with a direction; two-leg operations with an
    operation type from the catalogue; anything else is read-only.
    """
    op, override = item.operation, item.override
    if op.summary["stock_option"]:
        return Editor(READ_ONLY, reason="Operations with stock are always discarded (decision 0016).")
    if op.summary["patas_incompletas"]:
        return Editor(READ_ONLY, reason="Complete the missing leg first (tab 2).")
    if len(op.legs) == 1:
        return Editor(DIRECTION, DIRECTION_OPTIONS, override.direction if override else None)
    if len(op.legs) == 2:
        options = tuple((s.key, s.label) for s in strategies.options_for(op.legs))
        return Editor(STRATEGY, options, override.strategy if override else None)
    return Editor(READ_ONLY, reason="Operations with three or more legs are always discarded.")


def save(store, operation_id, kind, value):
    """Stores a correction; an empty value removes it."""
    if not value:
        store.clear_override(operation_id)
    elif kind == DIRECTION:
        store.set_direction(operation_id, value)
    elif kind == STRATEGY:
        store.set_strategy(operation_id, value)
    else:
        raise ValueError(f"operation {operation_id} cannot be corrected")
