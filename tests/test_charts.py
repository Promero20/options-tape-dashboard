"""Chart data (charts.aggregate), the reference price and the Plotly figures (charts.figures)."""

from datetime import date
from types import SimpleNamespace

import pytest

from synthetic import scenario, write_level1, write_level2
from tape_dashboard.charts import aggregate as agg
from tape_dashboard.charts import figures
from tape_dashboard.data.dataset import load_dataset
from tape_dashboard.edits.apply import classified_operations
from tape_dashboard.edits.store import Edits
from tape_dashboard.rules import classification as c
from tape_dashboard.rules.classification import Classification

M = 1_000_000
NOV, DEC = "2026-11-20", "2026-12-18"


def item(destination, premium, strike=100.0, expiration=NOV, direction=None, wall=None, price=100.0,
         symbol="XYZ"):
    """A classified operation with only what the charts read."""
    classification = Classification(destination, structure="test", reason="test", direction=direction,
                                    strike=strike, expiration=expiration, premium=premium, wall=wall)
    return SimpleNamespace(operation=SimpleNamespace(symbol=symbol, price=price), classification=classification)


def bull(premium, **kw):
    return item(c.NET, premium, direction=c.BULL, **kw)


def bear(premium, **kw):
    return item(c.NET, -premium, direction=c.BEAR, **kw)


def wall(kind, premium, strike, **kw):
    return item(c.WALLS, premium, strike=strike, wall=kind,
                direction=c.BULL if kind == c.SUPPORT else c.BEAR, **kw)


MIXED = [
    bull(2 * M, strike=110.0), bear(1 * M, strike=90.0),
    item(c.UNDETERMINED_SINGLE, 0.5 * M, expiration=DEC, direction=c.UNDETERMINED),
    bull(1 * M, expiration=DEC, strike=110.0),
    wall(c.SUPPORT, 3 * M, 95.0), wall(c.SUPPORT, 1 * M, 95.0, expiration=DEC), wall(c.RESISTANCE, 2 * M, 90.0),
    item(c.UNDETERMINED_MULTI, 4 * M, strike=None, expiration=None, direction=c.UNDETERMINED),
    item(c.DISCARDED, 5 * M, strike=None, expiration=None), item(c.DISCARDED, 1 * M, strike=None, expiration=None),
]


# --- aggregate ------------------------------------------------------------------------

def test_net_buckets_by_expiration():
    nov, dec = agg.net_buckets(MIXED, agg.EXPIRATION)
    assert (nov.key, nov.bull, nov.bear, nov.net, nov.undetermined) == (NOV, 2 * M, 1 * M, 1 * M, 0.0)
    assert (nov.n_bull, nov.n_bear, nov.n_undetermined) == (1, 1, 0)
    assert (dec.key, dec.bull, dec.undetermined, dec.n_undetermined) == (DEC, 1 * M, 0.5 * M, 1)


def test_net_buckets_by_strike_are_sorted_numerically():
    buckets = agg.net_buckets(MIXED, agg.STRIKE)
    assert [b.key for b in buckets] == [90.0, 100.0, 110.0]
    assert [(b.bull, b.bear, b.undetermined) for b in buckets] == [(0, 1 * M, 0), (0, 0, 0.5 * M), (3 * M, 0, 0)]


def test_unknown_axis_is_an_error():
    with pytest.raises(ValueError):
        agg.net_buckets(MIXED, "trade date")


def test_side_totals_are_gross_premium():
    assert agg.side_totals(MIXED) == agg.Totals(4 * M, 1, 6 * M, 2)


@pytest.mark.parametrize("kind, strike, price, itm", [
    (c.SUPPORT, 110.0, 100.0, True), (c.SUPPORT, 90.0, 100.0, False),
    (c.RESISTANCE, 90.0, 100.0, True), (c.RESISTANCE, 110.0, 100.0, False),
    (c.SUPPORT, 100.0, 100.0, False), (c.RESISTANCE, 100.0, 100.0, False),
    (c.RESISTANCE, 90.0, None, False),
])
def test_itm_walls(kind, strike, price, itm):
    assert agg.is_itm(wall(kind, M, strike, price=price)) is itm


def test_only_walls_can_be_itm():
    assert agg.is_itm(bull(M, strike=50.0)) is False


def test_wall_levels_group_by_strike_kind_and_itm():
    levels = agg.wall_levels(MIXED)
    assert levels == [agg.WallLevel(90.0, c.RESISTANCE, True, 2 * M, 1),
                      agg.WallLevel(95.0, c.SUPPORT, False, 4 * M, 2)]
    assert agg.wall_levels(MIXED, [DEC]) == [agg.WallLevel(95.0, c.SUPPORT, False, 1 * M, 1)]
    assert agg.wall_expirations(MIXED) == [NOV, DEC]


def test_symbols():
    items = [bull(M, symbol="BBB"), bull(M, symbol="AAA"), bear(M, symbol="BBB")]
    assert agg.symbol_counts(items) == [("AAA", 1), ("BBB", 2)]
    assert len(agg.for_symbol(items, "BBB")) == 2


def charted(items):
    """Every dollar the charts show for these operations, wherever it lands."""
    buckets = agg.net_buckets(items, agg.EXPIRATION)
    totals = agg.side_totals(items)
    return (sum(b.net + b.undetermined for b in buckets) + sum(l.premium for l in agg.wall_levels(items))
            + totals.undetermined_multi + totals.discarded)


def test_every_dollar_lands_in_one_place(synthetic_folder):
    dataset = load_dataset(synthetic_folder)
    items = classified_operations(dataset, Edits.empty(), date(2026, 10, 13), date(2026, 10, 15))
    for symbol, _ in agg.symbol_counts(items):
        mine = agg.for_symbol(items, symbol)
        assert charted(mine) == pytest.approx(sum(i.classification.premium for i in mine))


def test_an_operation_in_two_captures_counts_once(synthetic_folder):
    dataset = load_dataset(synthetic_folder)
    items = agg.for_symbol(classified_operations(dataset, Edits.empty(), date(2026, 10, 13),
                                                 date(2026, 10, 15)), "BBB")
    (dec,) = [b for b in agg.net_buckets(items, agg.EXPIRATION) if b.key == DEC]
    assert (dec.n_bull, dec.n_undetermined) == (1, 1)


# --- reference price --------------------------------------------------------------------------

def test_reference_price_is_the_latest_capture_up_to_the_day(tmp_path):
    trades = scenario()
    for day, aaa in (("20261013", 30.0), ("20261015", 33.0)):
        write_level1(tmp_path / f"nivel1_candidatos_{day}.csv", trades, prices={"AAA": aaa, "BBB": 100.0})
        write_level2(tmp_path / f"nivel2_trades_{day}.csv", trades)
    dataset = load_dataset(tmp_path)

    assert dataset.price_on_or_before("AAA", date(2026, 10, 14)) == (date(2026, 10, 13), 30.0)
    assert dataset.price_on_or_before("AAA", date(2026, 10, 31)) == (date(2026, 10, 15), 33.0)
    assert dataset.price_on_or_before("CCC", date(2026, 10, 31)) is None
    assert dataset.price_on_or_before("AAA", date(2026, 10, 12)) is None


# --- figures ---------------------------------------------------------------------------------------

def test_net_figure_by_expiration():
    fig = figures.net_figure(agg.net_buckets(MIXED, agg.EXPIRATION), agg.EXPIRATION)
    traces = {t.name: t for t in fig.data}
    assert list(traces) == ["Bull", "Bear", "Net", "Undetermined"]
    assert list(traces["Bull"].y) == [2.0, 1.0] and list(traces["Bear"].y) == [-1.0, 0.0]
    assert list(traces["Net"].y) == [1.0, 1.0]
    assert list(traces["Undetermined"].x) == [DEC] and list(traces["Undetermined"].y) == [0.5]
    assert fig.layout.barmode == "relative"
    assert fig.layout.xaxis.type == "category" and list(fig.layout.xaxis.categoryarray) == [NOV, DEC]


def test_net_figure_by_strike_marks_the_price():
    fig = figures.net_figure(agg.net_buckets(MIXED, agg.STRIKE), agg.STRIKE, price=104.5)
    assert fig.layout.xaxis.type == "linear"
    assert [s.x0 for s in fig.layout.shapes] == [104.5]
    traces = {t.name: t for t in fig.data}
    assert list(traces["Undetermined"].x) == [100.0]
    assert list(traces["Net"].x) == [90.0, 110.0]       # no net marker where there is only undetermined


def test_net_figure_without_data():
    fig = figures.net_figure([], agg.EXPIRATION)
    assert not fig.data and "No net directional" in fig.layout.annotations[0].text
    with pytest.raises(ValueError):
        figures.net_figure([], "trade date")


def test_walls_figure():
    fig = figures.walls_figure(agg.wall_levels(MIXED), price=100.0, price_date="2026-10-15")
    traces = {t.name: t for t in fig.data}
    assert list(traces) == ["Support", "Resistance ITM"]
    assert traces["Support"].orientation == "h" and list(traces["Support"].y) == [95.0]
    assert list(traces["Support"].x) == [4.0]
    assert fig.layout.barmode == "stack"
    (line,) = fig.layout.shapes
    assert line.y0 == 100.0
    assert any("Price 100 (2026-10-15)" in a.text for a in fig.layout.annotations)


def test_itm_walls_can_be_hidden():
    fig = figures.walls_figure(agg.wall_levels(MIXED), price=100.0, show_itm=False)
    assert [t.name for t in fig.data] == ["Support"]
    only_itm = [l for l in agg.wall_levels(MIXED) if l.itm]
    empty = figures.walls_figure(only_itm, price=100.0, show_itm=False)
    assert not empty.data and "ITM walls are hidden" in empty.layout.annotations[0].text


def test_a_lone_bar_far_from_the_price_stays_visible():
    fig = figures.walls_figure([agg.WallLevel(50.0, c.SUPPORT, False, M, 1)], price=150.0)
    assert fig.data[0].width >= 0.025 * 100
