"""Tab 2: operations with a missing leg, completed by hand (decisions 0011, 0013 and 0030)."""

from . import callbacks, view

TITLE = "Incomplete legs"


def layout(state):
    return view.layout(callbacks.day_options(state), callbacks.default_day(state))


def register(app, state):
    return callbacks.register(app, state)


__all__ = ["TITLE", "layout", "register"]
