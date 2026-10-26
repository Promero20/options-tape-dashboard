"""
Catálogo de tipos de operación para operaciones de dos patas (decisión 0011).

Cuando el lado de las patas no se puede deducir de la agresividad (pata
manual, lado indeterminado, agrupación dudosa), el usuario elige el tipo de
operación. Cada tipo fija el lado de cada pata, y la clasificación hace el
resto. Solo se ofrecen los tipos compatibles con la geometría de las patas
(tipos de opción, expiraciones y strikes).
"""

from dataclasses import dataclass

from .sides import BUY, SELL, option_type

# Geometrías de dos patas
VERTICAL = "vertical"               # mismo tipo y expiración, strikes distintos
DIAGONAL = "diagonal"               # mismo tipo, expiración y strike distintos
CALENDAR = "calendar"               # mismo tipo y strike, expiración distinta
COMBO_SAME_STRIKE = "call+put same strike"
COMBO_DIFF_STRIKE = "call+put different strikes"
COMBO_DIFF_EXP = "call+put different expirations"


def geometry(legs):
    """Geometría de una operación de dos patas, o None si no tiene dos."""
    if len(legs) != 2:
        return None
    a, b = legs
    same_type = option_type(a) == option_type(b)
    same_exp = a["exp_date"] == b["exp_date"]
    same_strike = float(a["strike"]) == float(b["strike"])
    if same_type:
        if same_exp:
            return VERTICAL
        return CALENDAR if same_strike else DIAGONAL
    if not same_exp:
        return COMBO_DIFF_EXP
    return COMBO_SAME_STRIKE if same_strike else COMBO_DIFF_STRIKE


def _by(legs, key, first_side, second_side):
    """Asigna first_side a la pata con menor `key` y second_side a la otra."""
    low = min(range(2), key=lambda i: key(legs[i]))
    sides = [second_side, second_side]
    sides[low] = first_side
    return tuple(sides)


def _strike(leg):
    return float(leg["strike"])


def _exp(leg):
    return leg["exp_date"]


def _by_type(legs, call_side, put_side):
    return tuple(call_side if option_type(l) == "call" else put_side for l in legs)


@dataclass(frozen=True)
class Strategy:
    key: str
    label: str
    geometry: str | None        # None: aplicable a cualquier operación de dos patas
    calls_only: bool = False
    puts_only: bool = False

    def applies_to(self, legs):
        g = geometry(legs)
        if g is None or (self.geometry is not None and self.geometry != g):
            return False
        types = {option_type(l) for l in legs}
        if self.calls_only and types != {"call"}:
            return False
        if self.puts_only and types != {"put"}:
            return False
        return True

    def sides(self, legs):
        """Lado de cada pata, en el orden de `legs`."""
        return _SIDES[self.key](legs)


UNKNOWN = "unknown"

STRATEGIES = (
    Strategy("bull_call", "Bull call spread (debit: buys the low strike)", VERTICAL, calls_only=True),
    Strategy("bear_call", "Bear call spread (credit: sells the low strike)", VERTICAL, calls_only=True),
    Strategy("bear_put", "Bear put spread (debit: buys the high strike)", VERTICAL, puts_only=True),
    Strategy("bull_put", "Bull put spread (credit: sells the high strike)", VERTICAL, puts_only=True),
    Strategy("diagonal_buy_near", "Diagonal: buys the near expiration", DIAGONAL),
    Strategy("diagonal_buy_far", "Diagonal: buys the far expiration", DIAGONAL),
    Strategy("long_calendar", "Long calendar (buys the far expiration)", CALENDAR),
    Strategy("short_calendar", "Short calendar (sells the far expiration)", CALENDAR),
    Strategy("long_straddle", "Long straddle", COMBO_SAME_STRIKE),
    Strategy("short_straddle", "Short straddle", COMBO_SAME_STRIKE),
    Strategy("long_synthetic", "Long synthetic (buys the call, sells the put)", COMBO_SAME_STRIKE),
    Strategy("short_synthetic", "Short synthetic (sells the call, buys the put)", COMBO_SAME_STRIKE),
    Strategy("long_strangle", "Long strangle", COMBO_DIFF_STRIKE),
    Strategy("short_strangle", "Short strangle", COMBO_DIFF_STRIKE),
    Strategy("bullish_risk_reversal", "Bullish risk reversal (buys the call, sells the put)", COMBO_DIFF_STRIKE),
    Strategy("bearish_risk_reversal", "Bearish risk reversal (buys the put, sells the call)", COMBO_DIFF_STRIKE),
    Strategy("buy_call_sell_put", "Buys the call and sells the put", COMBO_DIFF_EXP),
    Strategy("buy_put_sell_call", "Buys the put and sells the call", COMBO_DIFF_EXP),
    Strategy("buy_both", "Buys both legs", COMBO_DIFF_EXP),
    Strategy("sell_both", "Sells both legs", COMBO_DIFF_EXP),
    Strategy(UNKNOWN, "Don't know", None),
)

_SIDES = {
    "bull_call": lambda legs: _by(legs, _strike, BUY, SELL),
    "bear_call": lambda legs: _by(legs, _strike, SELL, BUY),
    "bear_put": lambda legs: _by(legs, _strike, SELL, BUY),
    "bull_put": lambda legs: _by(legs, _strike, BUY, SELL),
    "diagonal_buy_near": lambda legs: _by(legs, _exp, BUY, SELL),
    "diagonal_buy_far": lambda legs: _by(legs, _exp, SELL, BUY),
    "long_calendar": lambda legs: _by(legs, _exp, SELL, BUY),
    "short_calendar": lambda legs: _by(legs, _exp, BUY, SELL),
    "long_straddle": lambda legs: (BUY, BUY),
    "short_straddle": lambda legs: (SELL, SELL),
    "long_synthetic": lambda legs: _by_type(legs, BUY, SELL),
    "short_synthetic": lambda legs: _by_type(legs, SELL, BUY),
    "long_strangle": lambda legs: (BUY, BUY),
    "short_strangle": lambda legs: (SELL, SELL),
    "bullish_risk_reversal": lambda legs: _by_type(legs, BUY, SELL),
    "bearish_risk_reversal": lambda legs: _by_type(legs, SELL, BUY),
    "buy_call_sell_put": lambda legs: _by_type(legs, BUY, SELL),
    "buy_put_sell_call": lambda legs: _by_type(legs, SELL, BUY),
    "buy_both": lambda legs: (BUY, BUY),
    "sell_both": lambda legs: (SELL, SELL),
    UNKNOWN: lambda legs: (None, None),
}

BY_KEY = {s.key: s for s in STRATEGIES}


def options_for(legs):
    """Tipos de operación que encajan con las patas, en el orden del catálogo."""
    return [s for s in STRATEGIES if s.applies_to(legs)]
