"""Page layout: header, warnings banner and tabs, plus the callbacks that belong to the page."""

from dash import Input, Output, State, dcc, html

from . import ids
from .tabs import TABS
from .warnings import collect


def header_info(state):
    dataset = state.dataset
    dates = dataset.usable_dates
    latest = f"latest {dates[-1].isoformat()}" if dates else "none usable"
    return f"Data folder: {state.settings.data_dir} · {len(dates)} captures ({latest})"


def notices_banner(state):
    notices = collect(state)
    if not notices:
        return None
    errors = sum(1 for n in notices if n.level == "error")
    title = f"{len(notices)} warnings" + (f", {errors} errors" if errors else "")
    return html.Details(className="notices", open=bool(errors), children=[
        html.Summary(title),
        html.Ul([html.Li(n.text, className=f"notice-{n.level}") for n in notices]),
    ])


def page(state):
    return html.Div(className="page", children=[
        html.Header(className="header", children=[
            html.H1("Tape Reading Dashboard"),
            html.Span(header_info(state), id=ids.HEADER_INFO, className="muted"),
            html.Button("Reload data", id=ids.RELOAD, className="btn"),
        ]),
        html.Div(notices_banner(state), id=ids.NOTICES),
        dcc.Tabs(id=ids.TABS, className="tabs", children=[
            dcc.Tab(label=tab.TITLE, value=tab.__name__.rsplit(".", 1)[-1], children=tab.layout(state))
            for tab in TABS
        ]),
        dcc.Store(id=ids.DATA_VERSION, data=0),
        dcc.Store(id=ids.EDITS_VERSION, data=0),
    ])


def register(app, state):
    @app.callback(Output(ids.DATA_VERSION, "data"), Input(ids.RELOAD, "n_clicks"),
                  State(ids.DATA_VERSION, "data"), prevent_initial_call=True)
    def reload_data(_clicks, version):
        state.reload()
        return (version or 0) + 1

    @app.callback(Output(ids.NOTICES, "children"), Output(ids.HEADER_INFO, "children"),
                  Input(ids.DATA_VERSION, "data"), Input(ids.EDITS_VERSION, "data"),
                  prevent_initial_call=True)
    def refresh_header(_data_version, _edits_version):
        return notices_banner(state), header_info(state)

    return {"reload_data": reload_data, "refresh_header": refresh_header}
