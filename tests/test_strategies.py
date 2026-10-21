"""Catálogo de tipos de operación: geometría, tipos ofrecidos y lado de cada pata."""

import pytest

from fake_operations import leg
from tape_dashboard.rules import strategies as s
from tape_dashboard.rules.sides import BUY, SELL, leg_side

NEAR, FAR = "2026-11-20", "2027-01-15"


@pytest.mark.parametrize("legs, geometry", [
    ([leg("call", 100, NEAR, 1, 1), leg("call", 110, NEAR, 1, 1)], s.VERTICAL),
    ([leg("put", 100, NEAR, 1, 1), leg("put", 100, FAR, 1, 1)], s.CALENDAR),
    ([leg("put", 100, NEAR, 1, 1), leg("put", 90, FAR, 1, 1)], s.DIAGONAL),
    ([leg("call", 100, NEAR, 1, 1), leg("put", 100, NEAR, 1, 1)], s.COMBO_SAME_STRIKE),
    ([leg("call", 110, NEAR, 1, 1), leg("put", 90, NEAR, 1, 1)], s.COMBO_DIFF_STRIKE),
    ([leg("call", 110, NEAR, 1, 1), leg("put", 90, FAR, 1, 1)], s.COMBO_DIFF_EXP),
    ([leg("call", 110, NEAR, 1, 1)], None),
])
def test_geometry(legs, geometry):
    assert s.geometry(legs) == geometry


def test_only_compatible_types_are_offered():
    calls = [leg("call", 100, NEAR, 1, 1), leg("call", 110, NEAR, 1, 1)]
    puts = [leg("put", 100, NEAR, 1, 1), leg("put", 110, NEAR, 1, 1)]
    assert [x.key for x in s.options_for(calls)] == ["bull_call", "bear_call", s.UNKNOWN]
    assert [x.key for x in s.options_for(puts)] == ["bear_put", "bull_put", s.UNKNOWN]
    assert s.options_for([leg("call", 100, NEAR, 1, 1)]) == []


@pytest.mark.parametrize("key, legs, expected", [
    # verticales: el lado depende del strike
    ("bull_call", [leg("call", 110, NEAR, 1, 1), leg("call", 100, NEAR, 1, 1)], (SELL, BUY)),
    ("bear_call", [leg("call", 110, NEAR, 1, 1), leg("call", 100, NEAR, 1, 1)], (BUY, SELL)),
    ("bear_put", [leg("put", 90, NEAR, 1, 1), leg("put", 100, NEAR, 1, 1)], (SELL, BUY)),
    ("bull_put", [leg("put", 90, NEAR, 1, 1), leg("put", 100, NEAR, 1, 1)], (BUY, SELL)),
    # diagonales y calendars: depende de la expiración
    ("diagonal_compra_cercana", [leg("call", 110, FAR, 1, 1), leg("call", 100, NEAR, 1, 1)], (SELL, BUY)),
    ("diagonal_compra_lejana", [leg("call", 110, FAR, 1, 1), leg("call", 100, NEAR, 1, 1)], (BUY, SELL)),
    ("calendar_largo", [leg("call", 100, NEAR, 1, 1), leg("call", 100, FAR, 1, 1)], (SELL, BUY)),
    ("calendar_corto", [leg("call", 100, NEAR, 1, 1), leg("call", 100, FAR, 1, 1)], (BUY, SELL)),
    # call + put: depende del tipo
    ("sintetico_largo", [leg("put", 100, NEAR, 1, 1), leg("call", 100, NEAR, 1, 1)], (SELL, BUY)),
    ("risk_reversal_bajista", [leg("put", 90, NEAR, 1, 1), leg("call", 110, NEAR, 1, 1)], (BUY, SELL)),
    ("straddle_vendido", [leg("put", 100, NEAR, 1, 1), leg("call", 100, NEAR, 1, 1)], (SELL, SELL)),
    (s.UNKNOWN, [leg("put", 100, NEAR, 1, 1), leg("call", 100, NEAR, 1, 1)], (None, None)),
])
def test_sides_follow_the_legs_not_their_order(key, legs, expected):
    strategy = s.BY_KEY[key]
    assert strategy.applies_to(legs)
    assert strategy.sides(legs) == expected


def test_every_strategy_has_a_side_rule():
    assert set(s.BY_KEY) == set(s._SIDES)


@pytest.mark.parametrize("agr, side", [
    (0.8, BUY), (-1.0, SELL), (0.1, None), (None, None),
    # en la frontera es indeterminado, también con el ruido de coma flotante
    (0.25, None), (0.25000000000000333, None), (-0.25000000000000555, None),
    (0.2500001, BUY), (-0.26, SELL),
])
def test_leg_side(agr, side):
    assert leg_side(agr) == side
