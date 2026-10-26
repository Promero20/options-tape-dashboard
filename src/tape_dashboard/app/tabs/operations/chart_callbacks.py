"""
Callbacks of the underlying charts in the operations tab. As in callbacks.py,
each one wraps a controller that takes the application state and plain
values, so the tests call the controllers without a browser.
"""

from dash import Input, Output, no_update

from ....charts import aggregate as agg
from ....charts.figures import empty_figure, net_figure, walls_figure
from ....edits.apply import classified_operations
from ... import ids
from . import view
from .ranges import CUSTOM, resolve_range

M = 1_000_000


# --- controllers --------------------------------------------------------------

def chart_operations(state, preset, start, end):
    """The range the charts cover and its operations: the same set as the list (business rules, section 6)."""
    capture_range = resolve_range(state.dataset, preset, state.today(), start, end)
    if capture_range.empty:
        return capture_range, []
    return capture_range, classified_operations(state.dataset, state.edits(), capture_range.start,
                                                capture_range.end)


def _period(capture_range):
    if capture_range.start == capture_range.end:
        return capture_range.start.isoformat()
    return f"{capture_range.start.isoformat()} → {capture_range.end.isoformat()}"


def symbol_from_selection(selected_rows):
    """Selecting a row in the list sets the underlying; clearing the selection keeps it."""
    return selected_rows[0]["symbol"] if selected_rows else no_update


def symbol_options(state, preset, start, end, current):
    """Underlyings with operations in the chart range, plus the current one if it has none."""
    _, items = chart_operations(state, preset, start, end)
    counts = dict(agg.symbol_counts(items))
    if current and current not in counts:
        counts[current] = 0
    return [{"label": f"{symbol} ({n})", "value": symbol} for symbol, n in sorted(counts.items())]


def _price(state, symbol, capture_range):
    found = state.dataset.price_on_or_before(symbol, capture_range.end)
    return (found[1], found[0].isoformat()) if found else (None, None)


def net_chart(state, symbol, preset, start, end, axis):
    """Net directional figure, the line with the separate totals, and the range note."""
    capture_range, items = chart_operations(state, preset, start, end)
    if capture_range.empty:
        return empty_figure(capture_range.note), "", capture_range.note
    if not symbol:
        return empty_figure(view.NO_SYMBOL), "", capture_range.note
    mine = agg.for_symbol(items, symbol)
    price, _ = _price(state, symbol, capture_range)
    totals = agg.side_totals(mine)
    line = (f"{symbol}, {_period(capture_range)}. "
            f"Undetermined multi-leg: {totals.undetermined_multi / M:.3f}M ({totals.n_undetermined_multi}) · "
            f"Discarded: {totals.discarded / M:.3f}M ({totals.n_discarded})")
    return net_figure(agg.net_buckets(mine, axis), axis, price), line, capture_range.note


def wall_expiration_options(state, symbol, preset, start, end):
    _, items = chart_operations(state, preset, start, end)
    mine = agg.for_symbol(items, symbol) if symbol else []
    return [{"label": e, "value": e} for e in agg.wall_expirations(mine)]


def walls_chart(state, symbol, preset, start, end, expirations, show_itm):
    """Walls figure. Expirations that no longer have walls are ignored; none selected means all."""
    capture_range, items = chart_operations(state, preset, start, end)
    if capture_range.empty:
        return empty_figure(capture_range.note)
    if not symbol:
        return empty_figure(view.NO_SYMBOL)
    mine = agg.for_symbol(items, symbol)
    available = set(agg.wall_expirations(mine))
    chosen = [e for e in expirations or () if e in available]
    price, price_date = _price(state, symbol, capture_range)
    return walls_figure(agg.wall_levels(mine, chosen), price, price_date, show_itm=bool(show_itm))


# --- wiring -------------------------------------------------------------------

def register(app, state):
    chart_range = [Input(view.CHART_RANGE, "value"), Input(view.CHART_DATES, "start_date"),
                   Input(view.CHART_DATES, "end_date")]
    versions = [Input(ids.DATA_VERSION, "data"), Input(ids.EDITS_VERSION, "data")]

    @app.callback(Output(view.CHART_DATES, "disabled"), Input(view.CHART_RANGE, "value"))
    def toggle_chart_dates(preset):
        return preset != CUSTOM

    @app.callback(Output(view.SYMBOL, "value"), Input(view.GRID, "selectedRows"), prevent_initial_call=True)
    def select_symbol(selected):
        return symbol_from_selection(selected)

    @app.callback(Output(view.SYMBOL, "options"), *chart_range, *versions, Input(view.SYMBOL, "value"))
    def refresh_symbols(preset, start, end, _data_version, _edits_version, current):
        return symbol_options(state, preset, start, end, current)

    @app.callback(Output(view.NET_GRAPH, "figure"), Output(view.NET_TOTALS, "children"),
                  Output(view.CHART_NOTE, "children"),
                  Input(view.SYMBOL, "value"), *chart_range, Input(view.AXIS, "value"), *versions)
    def refresh_net(symbol, preset, start, end, axis, _data_version, _edits_version):
        return net_chart(state, symbol, preset, start, end, axis)

    @app.callback(Output(view.WALL_EXPIRATIONS, "options"), Input(view.SYMBOL, "value"), *chart_range, *versions)
    def refresh_wall_expirations(symbol, preset, start, end, _data_version, _edits_version):
        return wall_expiration_options(state, symbol, preset, start, end)

    @app.callback(Output(view.WALL_EXPIRATIONS, "value"), Input(view.SYMBOL, "value"), *chart_range,
                  prevent_initial_call=True)
    def reset_wall_expirations(_symbol, _preset, _start, _end):
        return []

    @app.callback(Output(view.WALLS_GRAPH, "figure"), Input(view.SYMBOL, "value"), *chart_range,
                  Input(view.WALL_EXPIRATIONS, "value"), Input(view.SHOW_ITM, "value"), *versions)
    def refresh_walls(symbol, preset, start, end, expirations, show_itm, _data_version, _edits_version):
        return walls_chart(state, symbol, preset, start, end, expirations, show_itm)

    return {"toggle_chart_dates": toggle_chart_dates, "select_symbol": select_symbol,
            "refresh_symbols": refresh_symbols, "refresh_net": refresh_net,
            "refresh_wall_expirations": refresh_wall_expirations,
            "reset_wall_expirations": reset_wall_expirations, "refresh_walls": refresh_walls}
