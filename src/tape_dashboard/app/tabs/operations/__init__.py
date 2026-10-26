"""Tab 1: detected operations, with the underlying charts."""

from . import callbacks, chart_callbacks
from .view import layout

TITLE = "Operations"


def register(app, state):
    return {**callbacks.register(app, state), **chart_callbacks.register(app, state)}


__all__ = ["TITLE", "layout", "register"]
