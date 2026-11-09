"""Tab 3: real positions, linked to the operation they mimic (decisions 0031 and 0032)."""

from . import callbacks, view

TITLE = "Positions"


def layout(state):
    return view.layout()


def register(app, state):
    return callbacks.register(app, state)


__all__ = ["TITLE", "layout", "register"]
