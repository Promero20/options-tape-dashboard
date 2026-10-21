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
COMBO_SAME_STRIKE = "call+put mismo strike"
COMBO_DIFF_STRIKE = "call+put strikes distintos"
COMBO_DIFF_EXP = "call+put expiración distinta"


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


UNKNOWN = "no_lo_se"

STRATEGIES = (
    Strategy("bull_call", "Bull call spread (débito: compra el strike bajo)", VERTICAL, calls_only=True),
    Strategy("bear_call", "Bear call spread (crédito: vende el strike bajo)", VERTICAL, calls_only=True),
    Strategy("bear_put", "Bear put spread (débito: compra el strike alto)", VERTICAL, puts_only=True),
    Strategy("bull_put", "Bull put spread (crédito: vende el strike alto)", VERTICAL, puts_only=True),
    Strategy("diagonal_compra_cercana", "Diagonal: compra el vencimiento cercano", DIAGONAL),
    Strategy("diagonal_compra_lejana", "Diagonal: compra el vencimiento lejano", DIAGONAL),
    Strategy("calendar_largo", "Calendar largo (compra el vencimiento lejano)", CALENDAR),
    Strategy("calendar_corto", "Calendar corto (vende el vencimiento lejano)", CALENDAR),
    Strategy("straddle_comprado", "Straddle comprado", COMBO_SAME_STRIKE),
    Strategy("straddle_vendido", "Straddle vendido", COMBO_SAME_STRIKE),
    Strategy("sintetico_largo", "Sintético largo (compra call, vende put)", COMBO_SAME_STRIKE),
    Strategy("sintetico_corto", "Sintético corto (vende call, compra put)", COMBO_SAME_STRIKE),
    Strategy("strangle_comprado", "Strangle comprado", COMBO_DIFF_STRIKE),
    Strategy("strangle_vendido", "Strangle vendido", COMBO_DIFF_STRIKE),
    Strategy("risk_reversal_alcista", "Risk reversal alcista (compra call, vende put)", COMBO_DIFF_STRIKE),
    Strategy("risk_reversal_bajista", "Risk reversal bajista (compra put, vende call)", COMBO_DIFF_STRIKE),
    Strategy("compra_call_vende_put", "Compra la call y vende la put", COMBO_DIFF_EXP),
    Strategy("compra_put_vende_call", "Compra la put y vende la call", COMBO_DIFF_EXP),
    Strategy("compra_ambas", "Compra las dos patas", COMBO_DIFF_EXP),
    Strategy("vende_ambas", "Vende las dos patas", COMBO_DIFF_EXP),
    Strategy(UNKNOWN, "No lo sé", None),
)

_SIDES = {
    "bull_call": lambda legs: _by(legs, _strike, BUY, SELL),
    "bear_call": lambda legs: _by(legs, _strike, SELL, BUY),
    "bear_put": lambda legs: _by(legs, _strike, SELL, BUY),
    "bull_put": lambda legs: _by(legs, _strike, BUY, SELL),
    "diagonal_compra_cercana": lambda legs: _by(legs, _exp, BUY, SELL),
    "diagonal_compra_lejana": lambda legs: _by(legs, _exp, SELL, BUY),
    "calendar_largo": lambda legs: _by(legs, _exp, SELL, BUY),
    "calendar_corto": lambda legs: _by(legs, _exp, BUY, SELL),
    "straddle_comprado": lambda legs: (BUY, BUY),
    "straddle_vendido": lambda legs: (SELL, SELL),
    "sintetico_largo": lambda legs: _by_type(legs, BUY, SELL),
    "sintetico_corto": lambda legs: _by_type(legs, SELL, BUY),
    "strangle_comprado": lambda legs: (BUY, BUY),
    "strangle_vendido": lambda legs: (SELL, SELL),
    "risk_reversal_alcista": lambda legs: _by_type(legs, BUY, SELL),
    "risk_reversal_bajista": lambda legs: _by_type(legs, SELL, BUY),
    "compra_call_vende_put": lambda legs: _by_type(legs, BUY, SELL),
    "compra_put_vende_call": lambda legs: _by_type(legs, SELL, BUY),
    "compra_ambas": lambda legs: (BUY, BUY),
    "vende_ambas": lambda legs: (SELL, SELL),
    UNKNOWN: lambda legs: (None, None),
}

BY_KEY = {s.key: s for s in STRATEGIES}


def options_for(legs):
    """Tipos de operación que encajan con las patas, en el orden del catálogo."""
    return [s for s in STRATEGIES if s.applies_to(legs)]
