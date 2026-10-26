"""Tab 2: incomplete legs. Content arrives in phase 5."""

from dash import html

TITLE = "Incomplete legs"


def layout(state):
    return html.Div(className="panel placeholder", children=[
        html.H4(TITLE),
        html.P("Multi-leg operations above the threshold that are missing a leg, with a form to complete "
               "them by picking the operation type. Coming in phase 5.", className="muted"),
    ])


def register(app, state):
    return {}
