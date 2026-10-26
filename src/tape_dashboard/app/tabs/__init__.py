"""The dashboard's tabs. Each one exposes TITLE, layout(state) and register(app, state)."""

from . import incomplete, operations, positions

TABS = (operations, incomplete, positions)
