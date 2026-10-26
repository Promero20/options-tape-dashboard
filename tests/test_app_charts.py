"""Underlying charts in the operations tab: controllers on synthetic data and the HTTP endpoints."""

from dash import no_update

from tape_dashboard.app import ids
from tape_dashboard.app.tabs.operations import callbacks as cb
from tape_dashboard.app.tabs.operations import chart_callbacks as charts
from tape_dashboard.app.tabs.operations import editing, view
from tape_dashboard.charts.aggregate import EXPIRATION, STRIKE
from tape_dashboard.rules import classification as c

SINGLE = "20261013-AAA-10:00:00.000-AUTO"     # AAA call bought: net, 2026-11-20, strike 30
NOV = "2026-11-20"


def traces(fig):
    return {t.name: t for t in fig.data}


def net(app, symbol="AAA", preset="month", start=None, end=None, axis=EXPIRATION):
    return charts.net_chart(app.tape_state, symbol, preset, start, end, axis)


def walls(app, symbol="AAA", expirations=(), show_itm=(view.ITM,)):
    return charts.walls_chart(app.tape_state, symbol, "month", None, None, list(expirations), list(show_itm))


def test_selecting_a_row_sets_the_underlying():
    assert charts.symbol_from_selection([{"symbol": "BBB", "id": "x"}]) == "BBB"
    assert charts.symbol_from_selection([]) is no_update and charts.symbol_from_selection(None) is no_update


def test_underlying_options(app):
    options = charts.symbol_options(app.tape_state, "month", None, None, None)
    values = [o["value"] for o in options]
    assert values == sorted(values) and {"AAA", "BBB", "CCC"} <= set(values)
    assert "AAA (3)" in [o["label"] for o in options]
    with_current = charts.symbol_options(app.tape_state, "month", None, None, "ZZZ")
    assert {"label": "ZZZ (0)", "value": "ZZZ"} in with_current


def test_net_chart_of_an_underlying(app):
    fig, line, note = net(app)
    bull = traces(fig)["Bull"]
    assert list(bull.x) == [NOV] and list(bull.customdata) == [2]       # two bought calls, two captures
    assert line.startswith("AAA, 2026-09-16 → 2026-10-15. Undetermined multi-leg: 0.000M (0)")
    assert note == ""

    by_strike, _, _ = net(app, axis=STRIKE)
    assert list(traces(by_strike)["Bull"].x) == [30.0]
    assert [s.x0 for s in by_strike.layout.shapes] == [30.0]           # the price of the latest capture


def test_net_chart_totals_and_undetermined(app):
    fig, line, _ = net(app, symbol="BBB")
    assert "Undetermined" in traces(fig)
    assert "Undetermined multi-leg: " in line and "(1)" in line and "Discarded: " in line


def test_charts_without_an_underlying_or_a_range(app):
    fig, line, note = net(app, symbol=None)
    assert not fig.data and fig.layout.annotations[0].text == view.NO_SYMBOL and line == ""
    fig, _, note = net(app, preset="custom")
    assert note == "Pick a start and an end date." and not fig.data
    assert not walls(app, symbol=None).data


def test_walls_chart(app):
    fig = walls(app)
    support = traces(fig)["Support"]
    assert list(support.y) == [25.0] and list(support.x) == [0.6]
    assert [s.y0 for s in fig.layout.shapes] == [30.0]
    assert charts.wall_expiration_options(app.tape_state, "AAA", "month", None, None) == \
        [{"label": NOV, "value": NOV}]
    assert traces(walls(app, expirations=["2030-01-18"]))["Support"]    # a stale filter is ignored


def test_a_correction_moves_premium_from_net_to_walls(app):
    state = app.tape_state
    cb.modal_action(state, view.SAVE, None, {"id": SINGLE, "kind": editing.DIRECTION}, c.BEAR, None, 0)

    fig, _, _ = net(app)
    assert list(traces(fig)["Bull"].customdata) == [1]
    resistance = traces(walls(app))["Resistance"]
    assert list(resistance.y) == [30.0] and list(resistance.x) == [0.702]


def test_chart_callbacks_are_registered(app):
    callbacks = app.tape_callbacks
    assert callbacks["toggle_chart_dates"]("custom") is False
    assert callbacks["reset_wall_expirations"]("AAA", "month", None, None) == []
    fig, _, _ = callbacks["refresh_net"]("AAA", "month", None, None, EXPIRATION, 0, 0)
    assert traces(fig)["Bull"]


def test_the_net_chart_is_served_over_http(app):
    client = app.server.test_client()
    outputs = [d["output"] for d in client.get("/_dash-dependencies").get_json()]
    assert any(f"{view.WALLS_GRAPH}.figure" in o for o in outputs)
    dep = next(o for o in outputs if f"{view.NET_GRAPH}.figure" in o)

    response = client.post("/_dash-update-component", json={
        "output": dep,
        "outputs": [{"id": view.NET_GRAPH, "property": "figure"}, {"id": view.NET_TOTALS, "property": "children"},
                    {"id": view.CHART_NOTE, "property": "children"}],
        "inputs": [{"id": view.SYMBOL, "property": "value", "value": "AAA"},
                   {"id": view.CHART_RANGE, "property": "value", "value": "month"},
                   {"id": view.CHART_DATES, "property": "start_date", "value": None},
                   {"id": view.CHART_DATES, "property": "end_date", "value": None},
                   {"id": view.AXIS, "property": "value", "value": EXPIRATION},
                   {"id": ids.DATA_VERSION, "property": "data", "value": 0},
                   {"id": ids.EDITS_VERSION, "property": "data", "value": 0}],
        "changedPropIds": [f"{view.SYMBOL}.value"], "state": [],
    })
    assert response.status_code == 200
    figure = response.get_json()["response"][view.NET_GRAPH]["figure"]
    assert [t["name"] for t in figure["data"]] == ["Bull", "Bear", "Net"]
