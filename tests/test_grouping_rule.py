"""
The grouping rule of 16/11/2026 (decision 0036), on invented trades: bursts,
relevant chunks, chaining by side, the 50 ms cross only for multi-leg
conditions, and unique IDs.
"""

import csv
import importlib.util

import pytest

from helpers import PREVIOUS_SCRIPT
from pipeline import nivel3_agrupar as n3
from synthetic import scenario, trade, write_level1
from tape_dashboard.rules import classification as cl
from tape_dashboard.rules.sides import BUY, SELL, leg_side

EXP = "2026-11-20"
PRICES = {"AAA": 30.0}               # $1-50 bracket: threshold $500,000


def at(time, side="buy", size=1000, price=5.0, condition="AUTO", strike=30, option_type="call", symbol="AAA"):
    """One trade at the ask (buy), at the bid (sell) or at the mid (undetermined)."""
    bid, ask = {"buy": (price - 0.1, price), "sell": (price, price + 0.1), "mid": (price - 0.1, price + 0.1)}[side]
    return trade(symbol, EXP, strike, option_type, time, price, size, bid, ask, condition)


def group(trades, prices=PRICES, estimates=None):
    rows = n3.preparar_filas([dict(t) for t in trades], list(trades[0]))
    groups = n3.agrupar(rows, prices, estimates or {})
    return rows, groups


def sizes(groups):
    return sorted(len(g) for g in groups.values())


# --- the side of a trade ------------------------------------------------------------------------

@pytest.mark.parametrize("aggressiveness, side", [
    (0.25, None), (-0.25, None), (0.25 + 5e-10, None), (0.2499999999999989, None), (0.25000000000000333, None),
    (0.2500001, n3.COMPRA), (-0.2500001, n3.VENTA), (None, None), (0.0, None),
])
def test_the_boundary_is_undetermined(aggressiveness, side):
    assert n3.lado(aggressiveness) == side
    assert leg_side(aggressiveness) == {n3.COMPRA: BUY, n3.VENTA: SELL}.get(side)


def test_direction_and_net_price_use_the_same_boundary():
    assert n3.direccion("Call", 0.25) == "indeterminado" and n3.direccion("Call", 0.3) == "bull"
    legs = [{"agr": 0.25, "precio_medio": 2.0}, {"agr": -0.9, "precio_medio": 1.0}]
    assert n3.precio_neto_operacion(legs, False) == ("", "no_calculable_direccion_ambigua")


# --- bursts and chunks ------------------------------------------------------------------------------

def test_a_sweep_in_milliseconds_is_one_operation_and_one_chunk():
    sweep = [at(f"10:00:00.{ms:03d}", size=100) for ms in range(0, 15)]       # 15 trades in 14 ms
    rows, groups = group(sweep)
    (only,) = groups.values()
    assert len(only) == 15 and n3.resumen(only)["n_trozos"] == 1


def test_a_burst_allows_one_second_between_trades():
    trades = [at("10:00:00.000"), at("10:00:01.000"), at("10:00:02.500")]
    rows, groups = group(trades, prices={})               # no price: every chunk is relevant and chains
    (only,) = groups.values()
    assert n3.resumen(only)["n_trozos"] == 2


def test_a_block_trade_keeps_its_operation_and_id():
    block = [at("10:00:00.000", size=2000)]                # $1,000,000 over the $500,000 threshold
    rows, groups = group(block)
    (only,) = groups.values()
    assert n3.ids_operaciones(groups) == {next(iter(groups)): "20261013-AAA-10:00:00.000-AUTO"}
    summary = n3.resumen(only)
    assert (summary["lado"], summary["n_trozos"], summary["lado_de_trozo_menor"]) == ("compra", 1, False)

    previous = _module(PREVIOUS_SCRIPT)
    old_rows = previous.preparar_filas([dict(t) for t in block], list(block[0]))
    (old,) = previous.agrupar(old_rows).values()
    assert {k: v for k, v in summary.items() if k in previous.resumen(old)} == previous.resumen(old)


def test_a_small_chunk_stays_alone_and_never_chains():
    trades = [at("10:00:00.000", size=1000),               # $500,000: relevant
              at("10:00:30.000", size=10),                 # $5,000: not relevant
              at("10:01:00.000", size=1000)]               # relevant, 60 s after the first
    rows, groups = group(trades)
    assert sizes(groups) == [1, 2]


def test_a_relevant_chunk_on_the_other_side_opens_a_new_operation():
    rows, groups = group([at("10:00:00.000"), at("10:00:30.000", side="sell"), at("10:01:00.000")])
    assert sizes(groups) == [1, 1, 1]              # buy, sell, then a buy that cannot join the closed one


def test_an_undetermined_chunk_joins_and_the_side_comes_from_the_first_chunk_with_one():
    trades = [at("10:00:00.000", side="mid", size=3000),   # the largest chunk, undetermined
              at("10:00:30.000", side="buy", size=1000)]
    rows, groups = group(trades)
    (only,) = groups.values()
    summary = n3.resumen(only)
    assert (summary["lado"], summary["n_trozos"], summary["lado_de_trozo_menor"]) == ("compra", 2, True)
    assert summary["direccion"] == "bull"
    assert summary["premium_trozo_mayor"] == 1_500_000


def test_chaining_counts_120_seconds_from_the_last_trade():
    trades = [at("10:00:00.000"), at("10:02:00.000"), at("10:04:00.001")]
    rows, groups = group(trades)
    assert sizes(groups) == [1, 2]


@pytest.mark.parametrize("price, estimate, minimum", [
    (30.0, None, 50_000), (30.0, 0.0, 50_000), (30.0, 1_000_000, 100_000), (30.0, 10_000_000, 500_000),
    (None, 1_000_000, None),
])
def test_how_much_a_relevant_chunk_needs(price, estimate, minimum):
    assert n3.umbral_trozo(price, estimate) == minimum


def test_the_estimated_premium_sets_what_is_relevant():
    trades = [at("10:00:00.000", size=200), at("10:01:00.000", size=200)]      # $100,000 each
    contract = "AAA|20261120|30.00C"
    assert sizes(group(trades)[1]) == [2]                                      # 10 % of the threshold: $50,000
    assert sizes(group(trades, estimates={contract: 2_000_000})[1]) == [1, 1]  # 10 % of the estimate: $200,000
    assert sizes(group(trades, estimates={contract: 500_000})[1]) == [2]       # 10 % of the estimate: $50,000


# --- the 50 ms cross and multi-leg conditions --------------------------------------------------------

def test_the_50_ms_cross_only_joins_multi_leg_conditions():
    auto = [at("10:00:00.000", strike=30), at("10:00:00.020", strike=35, side="sell")]
    assert sizes(group(auto)[1]) == [1, 1]
    multi = [at("10:00:00.000", strike=30, condition="MLET"), at("10:00:00.020", strike=35, condition="MLET")]
    (spread,) = group(multi)[1].values()
    assert len(spread) == 2 and n3.resumen(spread)["n_trozos"] == ""


def test_multi_leg_conditions_keep_the_120_s_window():
    trades = [at("10:00:00.000", condition="MLET"), at("10:01:59.000", condition="MLET", side="sell")]
    assert sizes(group(trades)[1]) == [2]


# --- IDs ---------------------------------------------------------------------------------------------

def test_colliding_ids_keep_the_largest_and_add_contract_and_side_to_the_rest():
    trades = [at("10:00:00.000", size=2000), at("10:00:00.000", side="sell", size=500),
              at("10:00:00.000", strike=35, size=300)]
    rows, groups = group(trades)
    ids = sorted(n3.ids_operaciones(groups).values())
    assert ids == ["20261013-AAA-10:00:00.000-AUTO", "20261013-AAA-10:00:00.000-AUTO-20261120-30C-venta",
                   "20261013-AAA-10:00:00.000-AUTO-20261120-35C-compra"]


# --- the whole scenario --------------------------------------------------------------------------------

def test_no_trade_disappears_and_ids_are_unique():
    trades = [t for t in scenario() if t["Trade Condition"] != "CANC"]
    rows, groups = group(trades, prices={"AAA": 30.0, "BBB": 100.0, "CCC": 300.0})
    assert sum(len(g) for g in groups.values()) == len(rows)
    assert sum(r["premium"] for g in groups.values() for r in g) == pytest.approx(sum(r["premium"] for r in rows))
    ids = n3.ids_operaciones(groups)
    assert len(set(ids.values())) == len(groups)


def test_level1_without_a_contract_column_is_rebuilt(tmp_path):
    path = tmp_path / "nivel1.csv"
    write_level1(path, scenario(), variant="N1-B")
    with open(path, encoding="utf-8") as f:
        assert "contract_symbol" not in next(csv.reader(f))
    prices, estimates = n3.cargar_nivel1(path)
    assert prices["AAA"] == 30.0 and estimates["AAA|20261120|30.00C"] == 1_000_000.0


# --- the dashboard uses the operation's side -------------------------------------------------------------

def test_the_classification_uses_the_operation_side():
    leg = {"contract_symbol": "AAA|20261120|30.00C", "type": "call", "strike": "30.00", "exp_date": EXP,
           "n_trades": 2, "size": 1000, "premium": 1_000_000.0, "agr": 0.1, "precio_medio": 10.0}
    operation = type("Op", (), {})()
    operation.legs = [leg]
    operation.summary = {"premium_total": 1_000_000.0, "stock_option": False, "patas_incompletas": False,
                         "lado": "venta"}
    assert cl.classify(operation).destination == cl.WALLS            # a sold call, although agr is 0.1
    operation.summary["lado"] = ""                                   # multi-leg: the leg's aggressiveness
    assert cl.classify(operation).destination == cl.UNDETERMINED_SINGLE


def _module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

