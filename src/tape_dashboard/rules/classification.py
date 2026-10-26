"""
Clasificación de cada operación en un único destino (decisión 0004).

Reglas de la especificación, completadas con las decisiones 0016 a 0022.
Precedencia:

1. Con acciones (condiciones TLxx/TxSL) → descartada, aunque tenga patas
   incompletas: la pata que falta es la acción.
2. Patas incompletas → pendiente (pestaña 2).
3. Tres patas o más → descartada.
4. Una pata: comprada → neto direccional; vendida → paredes; sin lado
   claro → indeterminada, en su strike y expiración.
5. Dos patas:
   - call + put (straddle, strangle, sintético, risk reversal o con
     distinta expiración) y calendar puro → descartada, sea cual sea el lado;
   - alguna pata sin lado claro, o las dos del mismo lado → indeterminada
     multi-leg;
   - vertical de débito → neto direccional; de crédito → paredes;
   - diagonal → neto direccional, también si es de crédito.

El lado de cada pata sale de su agresividad, salvo que el usuario haya
fijado la dirección (single-leg) o el tipo de operación (multi-leg).
"""

from dataclasses import dataclass, field

from pipeline import nivel3_agrupar as n3

from . import strategies
from .sides import BUY, SELL, leg_side, option_type

# Destinos
NET = "net"
WALLS = "walls"
UNDETERMINED_SINGLE = "undetermined"
UNDETERMINED_MULTI = "undetermined multi-leg"
DISCARDED = "discarded"
PENDING = "pending"
DESTINATIONS = (NET, WALLS, UNDETERMINED_SINGLE, UNDETERMINED_MULTI, DISCARDED, PENDING)

# Direcciones y paredes
BULL, BEAR, UNDETERMINED = "bull", "bear", "undetermined"
SUPPORT, RESISTANCE = "support", "resistance"

# Ratio entre la pata más grande y la más pequeña a partir del cual una
# multi-leg se marca para revisión (decisión 0012).
SIZE_RATIO_FLAG = 10


@dataclass(frozen=True)
class Override:
    """Corrección manual: dirección (single-leg) o tipo de operación (multi-leg)."""
    direction: str | None = None
    strategy: str | None = None


@dataclass(frozen=True)
class Classification:
    destination: str
    structure: str                  # estructura reconocida, en palabras
    reason: str                     # por qué va a este destino
    direction: str | None           # bull / bear / indeterminado; None si descartada o pendiente
    strike: float | None = None
    expiration: str | None = None
    # neto: con signo (bull +, bear −); paredes: positivo; resto: premium bruto
    premium: float = 0.0
    wall: str | None = None         # soporte / resistencia
    sides: tuple = ()               # lado de cada pata, en el orden de operation.legs
    manual: bool = False            # los lados vienen de una corrección del usuario
    net_price: float | str = ""     # precio neto con esos lados ('' si no se puede calcular)
    size_ratio: float | None = None
    warnings: tuple = field(default_factory=tuple)

    @property
    def anomalous_size_ratio(self):
        return self.size_ratio is not None and self.size_ratio >= SIZE_RATIO_FLAG


def _gross(operation):
    return operation.summary["premium_total"]


def _size_ratio(legs):
    if len(legs) < 2:
        return None
    sizes = [l["size"] for l in legs]
    return max(sizes) / min(sizes)


def _net_price(legs, sides):
    signed = [dict(l, agr=None if s is None else (1.0 if s == BUY else -1.0)) for l, s in zip(legs, sides)]
    price, _ = n3.precio_neto_operacion(signed, False)
    return price


def _measured_sides(legs):
    return tuple(leg_side(l["agr"]) for l in legs)


def _direction_of(leg, side):
    """Sesgo de una pata: comprar call o vender put es alcista."""
    return BULL if (option_type(leg) == "call") == (side == BUY) else BEAR


def _signed(direction, amount):
    return amount if direction == BULL else -amount


def _single_leg(operation, leg, side, base):
    structure = f"single-leg {option_type(leg)}"
    common = dict(base, structure=structure, strike=float(leg["strike"]), expiration=leg["exp_date"])
    gross = _gross(operation)
    if side is None:
        return Classification(UNDETERMINED_SINGLE, reason="undetermined side", direction=UNDETERMINED,
                              premium=gross, **common)
    direction = _direction_of(leg, side)
    if side == BUY:
        return Classification(NET, reason="bought leg", direction=direction,
                              premium=_signed(direction, gross), **common)
    wall = SUPPORT if option_type(leg) == "put" else RESISTANCE
    return Classification(WALLS, reason="sold leg", direction=direction, premium=gross,
                          wall=wall, **common)


_COMBO_STRUCTURES = {
    strategies.COMBO_SAME_STRIKE: ("straddle", "synthetic"),
    strategies.COMBO_DIFF_STRIKE: ("strangle", "risk reversal"),
    strategies.COMBO_DIFF_EXP: ("call + put with different expirations",) * 2,
}


def _two_legs(operation, legs, sides, base):
    gross = _gross(operation)
    g = strategies.geometry(legs)

    if g in _COMBO_STRUCTURES:
        same_side, opposite = _COMBO_STRUCTURES[g]
        if None in sides:
            structure = same_side if same_side == opposite else f"{same_side} or {opposite}"
        else:
            structure = same_side if sides[0] == sides[1] else opposite
        reason = ("risk reversals and synthetics are discarded until it is decided whether they go to net"
                  if structure in ("synthetic", "risk reversal") else "structure that is discarded")
        return Classification(DISCARDED, structure=structure, reason=reason, direction=None,
                              premium=gross, **base)
    if g == strategies.CALENDAR:
        return Classification(DISCARDED, structure="calendar", reason="structure that is discarded",
                              direction=None, premium=gross, **base)

    structure = "vertical" if g == strategies.VERTICAL else "diagonal"
    if None in sides:
        return Classification(UNDETERMINED_MULTI, structure=structure, reason="a leg without a clear side",
                              direction=UNDETERMINED, premium=gross, **base)
    if sides[0] == sides[1]:
        return Classification(UNDETERMINED_MULTI, structure=structure,
                              reason="both legs on the same side", direction=UNDETERMINED,
                              premium=gross, **base)

    bought, sold = (legs[0], legs[1]) if sides[0] == BUY else (legs[1], legs[0])
    debit = bought["premium"] - sold["premium"]

    if g == strategies.VERTICAL:
        if debit > 0:
            direction = _direction_of(bought, BUY)
            return Classification(NET, structure="debit vertical", reason="the bought leg is larger",
                                  direction=direction, strike=float(bought["strike"]),
                                  expiration=bought["exp_date"], premium=_signed(direction, debit), **base)
        if debit < 0:
            direction = _direction_of(sold, SELL)
            wall = SUPPORT if option_type(sold) == "put" else RESISTANCE
            return Classification(WALLS, structure="credit vertical", reason="the sold leg is larger",
                                  direction=direction, strike=float(sold["strike"]),
                                  expiration=sold["exp_date"], premium=-debit, wall=wall, **base)
        return Classification(UNDETERMINED_MULTI, structure="vertical", reason="debit and credit are equal",
                              direction=UNDETERMINED, premium=gross, **base)

    # Diagonal: siempre al neto. La dirección es la de la pata con más premium
    # (la del script); el importe, |comprada − vendida| (decisión 0018).
    dominant, dominant_side = (bought, BUY) if debit >= 0 else (sold, SELL)
    direction = _direction_of(dominant, dominant_side)
    kind = "debit" if debit >= 0 else "credit"
    return Classification(NET, structure=f"{kind} diagonal", reason="diagonals go to net",
                          direction=direction, strike=float(bought["strike"]),
                          expiration=min(bought["exp_date"], sold["exp_date"]),
                          premium=_signed(direction, abs(debit)), **base)


def _override_sides(legs, override, measured):
    """Lados que fija una corrección, o (None, aviso) si no encaja con las patas."""
    if len(legs) == 1:
        if override.direction is None:
            return None, "operation-type correction on a single-leg: ignored"
        if override.direction == UNDETERMINED:
            return (None,), None
        wants_call_bought = override.direction == BULL
        bought = (option_type(legs[0]) == "call") == wants_call_bought
        return (BUY if bought else SELL,), None
    strategy = strategies.BY_KEY.get(override.strategy) if override.strategy else None
    if strategy is None or not strategy.applies_to(legs):
        return None, f"the chosen operation type ({override.strategy or override.direction}) " \
                     f"no longer fits the legs: ignored"
    return strategy.sides(legs), None


def _contradictions(legs, measured, chosen):
    notes = []
    for leg, m, c in zip(legs, measured, chosen):
        if m is not None and c is not None and m != c:
            notes.append(f"{leg['contract_symbol']}: aggressiveness ({leg['agr']:+.2f}) says {m}, "
                         f"the correction says {c}")
    return notes


def classify(operation, override=None):
    """Destino, dirección, strike, expiración y premium de una operación."""
    legs = operation.legs
    summary = operation.summary
    base = dict(size_ratio=_size_ratio(legs))
    gross = _gross(operation)

    if summary["stock_option"]:
        return Classification(DISCARDED, structure="with stock", reason="includes a stock leg",
                              direction=None, premium=gross, **base)
    if summary["patas_incompletas"]:
        return Classification(PENDING, structure="incomplete legs",
                              reason="multi-leg with a single captured leg", direction=None,
                              premium=gross, **base)
    if len(legs) >= 3:
        return Classification(DISCARDED, structure=f"{len(legs)} legs", reason="three legs or more",
                              direction=None, premium=gross, **base)

    measured = _measured_sides(legs)
    sides, manual, warnings = measured, False, []
    if override is not None and (override.direction or override.strategy):
        chosen, problem = _override_sides(legs, override, measured)
        if problem:
            warnings.append(problem)
        else:
            sides, manual = chosen, True
            warnings += _contradictions(legs, measured, chosen)

    base.update(sides=sides, manual=manual, net_price=_net_price(legs, sides), warnings=tuple(warnings))
    if len(legs) == 1:
        return _single_leg(operation, legs[0], sides[0], base)
    return _two_legs(operation, legs, sides, base)
