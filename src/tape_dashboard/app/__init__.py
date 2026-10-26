"""The Dash application (decision 0023: Dash + dash-ag-grid, local only, callbacks organised per tab)."""

from datetime import date
from pathlib import Path

from dash import Dash

from ..config import load_settings
from . import layout
from .state import AppState
from .tabs import TABS

ASSETS = Path(__file__).resolve().parent / "assets"


def create_app(settings=None, today=date.today):
    """
    Builds the application. `today` is injectable so tests can pin the date
    that the "Today" range resolves to.
    """
    state = AppState(settings or load_settings(), today)
    app = Dash(__name__, title="Tape Reading Dashboard", assets_folder=str(ASSETS))
    app.layout = lambda: layout.page(state)
    callbacks = layout.register(app, state)
    for tab in TABS:
        callbacks.update(tab.register(app, state))
    app.tape_state = state
    app.tape_callbacks = callbacks
    return app
