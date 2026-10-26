"""
Reglas de clasificación: una prueba por cada fila de la tabla de la
especificación, más los casos que la tabla no cubría (decisiones 0016-0022)
y las correcciones manuales.
"""

import pytest

from fake_operations import leg, op
from tape_dashboard.rules import classification as c
from tape_dashboard.rules.classification import Override, classify
from tape_dashboard.rules.sides import BUY, SELL

NEAR, FAR = "2026-11-20", "2027-01-15"
M = 1_000_000


# --- Single-leg -------------------------------------------------------------

@pytest.mark.parametrize("option_type, direction, signed", [("call", c.BULL, 1), ("put", c.BEAR, -1)])
def test_single_leg_bought_goes_to_net(option_type, direction, signed):
    r = classify(op(leg(option_type, 100, NEAR, 2 * M, 0.9)))
    assert (r.destination, r.direction, r.premium) == (c.NET, direction, signed * 2 * M)
    assert (r.strike, r.expiration) == (100.0, NEAR)


@pytest.mark.parametrize("option_type, wall, direction", [
    ("put", c.SUPPORT, c.BULL), ("call", c.RESISTANCE, c.BEAR)])
def test_single_leg_sold_goes_to_walls(option_type, wall, direction):
    r = classify(op(leg(option_type, 100, NEAR, 2 * M, -1.0)))
    assert (r.destination, r.wall, r.direction, r.premium) == (c.WALLS, wall, direction, 2 * M)
    assert r.strike == 100.0


@pytest.mark.parametrize("agr", [0.1, -0.2, None, 0.25000000000000333])
def test_single_leg_without_clear_side_is_undetermined(agr):
    r = classify(op(leg("call", 100, NEAR, 2 * M, agr)))
    assert (r.destination, r.direction, r.premium) == (c.UNDETERMINED_SINGLE, c.UNDETERMINED, 2 * M)
    assert (r.strike, r.expiration) == (100.0, NEAR)


# --- Verticales y diagonales --------------------------------------------------

def test_debit_vertical_example_from_the_specification():
    # bear put: 10 M en la put 100 comprada y 5 M en la put 90 vendida:
    # strike 100, −5 M (bajista)
    r = classify(op(leg("put", 100, NEAR, 10 * M, 0.8), leg("put", 90, NEAR, 5 * M, -0.8)))
    assert (r.destination, r.structure, r.direction) == (c.NET, "debit vertical", c.BEAR)
    assert (r.strike, r.expiration, r.premium) == (100.0, NEAR, -5 * M)


def test_debit_call_vertical_is_bullish():
    r = classify(op(leg("call", 110, NEAR, 1 * M, -0.9), leg("call", 100, NEAR, 3 * M, 0.9)))
    assert (r.destination, r.direction, r.strike, r.premium) == (c.NET, c.BULL, 100.0, 2 * M)
    assert r.sides == (SELL, BUY)


@pytest.mark.parametrize("option_type, sold_strike, bought_strike, wall, direction", [
    ("put", 100, 90, c.SUPPORT, c.BULL),        # bull put spread
    ("call", 100, 110, c.RESISTANCE, c.BEAR),   # bear call spread
])
def test_credit_vertical_goes_to_walls_at_the_sold_strike(option_type, sold_strike, bought_strike, wall, direction):
    r = classify(op(leg(option_type, sold_strike, NEAR, 6 * M, -0.9),
                    leg(option_type, bought_strike, NEAR, 2 * M, 0.9)))
    assert (r.destination, r.structure, r.wall, r.direction) == (c.WALLS, "credit vertical", wall, direction)
    assert (r.strike, r.premium) == (float(sold_strike), 4 * M)


def test_debit_diagonal_goes_to_net_with_the_nearest_expiration():
    r = classify(op(leg("put", 140, NEAR, 1.7 * M, 0.9), leg("put", 145, FAR, 0.1 * M, -0.9)))
    assert (r.destination, r.structure, r.direction) == (c.NET, "debit diagonal", c.BEAR)
    assert (r.strike, r.expiration, r.premium) == (140.0, NEAR, pytest.approx(-1.6 * M))


def test_credit_diagonal_takes_the_direction_of_the_dominant_leg():
    # call lejana 125 comprada (1 M) y call cercana 130 vendida (1,5 M):
    # neto en el strike comprado, expiración cercana, bajista por 0,5 M
    r = classify(op(leg("call", 125, FAR, 1.0 * M, 0.9), leg("call", 130, NEAR, 1.5 * M, -0.9)))
    assert (r.destination, r.structure, r.direction) == (c.NET, "credit diagonal", c.BEAR)
    assert (r.strike, r.expiration, r.premium) == (125.0, NEAR, pytest.approx(-0.5 * M))


def test_net_price_uses_the_sides():
    r = classify(op(leg("call", 100, NEAR, 3 * M, 0.9, price=6.0), leg("call", 110, NEAR, 1 * M, -0.9, price=2.0)))
    assert r.net_price == 4.0


# --- Indeterminadas multi-leg --------------------------------------------------

def test_multi_leg_with_an_undetermined_leg():
    r = classify(op(leg("call", 100, NEAR, 3 * M, 0.9), leg("call", 110, NEAR, 1 * M, 0.1)))
    assert (r.destination, r.direction, r.premium) == (c.UNDETERMINED_MULTI, c.UNDETERMINED, 4 * M)
    assert r.net_price == ""


@pytest.mark.parametrize("agr", [0.9, -0.9])
def test_two_legs_on_the_same_side_are_undetermined(agr):
    r = classify(op(leg("call", 100, NEAR, 3 * M, agr), leg("call", 110, NEAR, 1 * M, agr)))
    assert (r.destination, r.reason) == (c.UNDETERMINED_MULTI, "both legs on the same side")


def test_equal_debit_and_credit_is_undetermined():
    r = classify(op(leg("call", 100, NEAR, 2 * M, 0.9), leg("call", 110, NEAR, 2 * M, -0.9)))
    assert r.destination == c.UNDETERMINED_MULTI


# --- Descartadas y pendientes -------------------------------------------------

@pytest.mark.parametrize("legs, structure", [
    ([leg("call", 100, NEAR, 1 * M, 0.9), leg("call", 100, FAR, 2 * M, -0.9)], "calendar"),
    ([leg("call", 100, NEAR, 1 * M, 0.9), leg("put", 100, NEAR, 2 * M, 0.9)], "straddle"),
    ([leg("call", 110, NEAR, 1 * M, -0.9), leg("put", 90, NEAR, 2 * M, -0.9)], "strangle"),
    ([leg("call", 110, NEAR, 1 * M, 0.9), leg("put", 90, NEAR, 2 * M, -0.9)], "risk reversal"),
    ([leg("call", 100, NEAR, 1 * M, 0.9), leg("put", 100, NEAR, 2 * M, -0.9)], "synthetic"),
    ([leg("call", 110, NEAR, 1 * M, 0.9), leg("put", 90, FAR, 2 * M, -0.9)], "call + put with different expirations"),
    # se descarta aunque algún lado sea indeterminado
    ([leg("call", 100, NEAR, 1 * M, 0.1), leg("put", 100, NEAR, 2 * M, 0.9)], "straddle or synthetic"),
    ([leg("call", 100, NEAR, 1 * M, 0.9), leg("call", 105, NEAR, 2 * M, -0.9),
      leg("call", 110, NEAR, 1 * M, 0.9)], "3 legs"),
])
def test_discarded_structures(legs, structure):
    r = classify(op(*legs))
    assert (r.destination, r.structure, r.direction) == (c.DISCARDED, structure, None)
    assert r.premium == sum(l["premium"] for l in legs)


def test_stock_option_is_discarded_even_if_incomplete():
    r = classify(op(leg("call", 100, NEAR, 5 * M, 0.9), stock_option=True, incomplete=True))
    assert (r.destination, r.structure) == (c.DISCARDED, "with stock")


def test_incomplete_legs_are_pending():
    r = classify(op(leg("call", 100, NEAR, 5 * M, 0.9), incomplete=True))
    assert (r.destination, r.direction, r.premium) == (c.PENDING, None, 5 * M)


# --- Correcciones manuales ------------------------------------------------------

@pytest.mark.parametrize("option_type, direction, destination, wall", [
    ("call", c.BULL, c.NET, None),            # bull sobre una call: comprada
    ("call", c.BEAR, c.WALLS, c.RESISTANCE),  # bear sobre una call: vendida
    ("put", c.BULL, c.WALLS, c.SUPPORT),      # bull sobre una put: vendida
    ("put", c.BEAR, c.NET, None),             # bear sobre una put: comprada
    ("put", c.UNDETERMINED, c.UNDETERMINED_SINGLE, None),
])
def test_single_leg_direction_override(option_type, direction, destination, wall):
    r = classify(op(leg(option_type, 100, NEAR, 2 * M, 0.0)), Override(direction=direction))
    assert (r.destination, r.direction, r.wall, r.manual) == (destination, direction, wall, True)


def test_strategy_override_fixes_the_sides():
    same_side = op(leg("call", 100, NEAR, 3 * M, 0.9), leg("call", 110, NEAR, 1 * M, 0.9))
    r = classify(same_side, Override(strategy="bull_call"))
    assert (r.destination, r.direction, r.premium, r.manual) == (c.NET, c.BULL, 2 * M, True)
    assert r.sides == (BUY, SELL)
    # la pata de 110 se midió como comprada: se avisa, no se bloquea
    assert len(r.warnings) == 1 and "110.00C" in r.warnings[0]


def test_unknown_strategy_keeps_it_undetermined():
    r = classify(op(leg("call", 100, NEAR, 3 * M, 0.9), leg("call", 110, NEAR, 1 * M, -0.9)),
                 Override(strategy="unknown"))
    assert (r.destination, r.manual) == (c.UNDETERMINED_MULTI, True)


def test_override_that_no_longer_fits_is_ignored_with_a_warning():
    r = classify(op(leg("call", 100, NEAR, 3 * M, 0.9), leg("call", 110, NEAR, 1 * M, -0.9)),
                 Override(strategy="bull_put"))
    assert (r.destination, r.manual) == (c.NET, False)
    assert "no longer fits" in r.warnings[0]


def test_override_does_not_complete_pending_operations():
    r = classify(op(leg("call", 100, NEAR, 5 * M, 0.9), incomplete=True), Override(direction=c.BULL))
    assert r.destination == c.PENDING


# --- Ratio de tamaños -----------------------------------------------------------

def test_anomalous_size_ratio_is_flagged():
    flagged = classify(op(leg("call", 100, NEAR, 3 * M, 0.9, size=3000), leg("call", 110, NEAR, 1, -0.9, size=30)))
    normal = classify(op(leg("call", 100, NEAR, 3 * M, 0.9, size=1000), leg("call", 110, NEAR, 1, -0.9, size=500)))
    assert flagged.anomalous_size_ratio and flagged.size_ratio == 100
    assert not normal.anomalous_size_ratio
    assert classify(op(leg("call", 100, NEAR, 3 * M, 0.9))).size_ratio is None
