"""Tab 3: real positions. Content arrives in phase 6."""

from dash import html

TITLE = "Positions"


def layout(state):
    return html.Div(className="panel placeholder", children=[
        html.H4(TITLE),
        html.P("Open positions linked to the operation they mimic, their history and the cumulative P&L. "
               "Coming in phase 6.", className="muted"),
    ])


def register(app, state):
    return {}
