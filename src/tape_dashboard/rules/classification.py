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
NET = "neto"
WALLS = "paredes"
UNDETERMINED_SINGLE = "indeterminada"
UNDETERMINED_MULTI = "indeterminada multi-leg"
DISCARDED = "descartada"
PENDING = "pendiente"
DESTINATIONS = (NET, WALLS, UNDETERMINED_SINGLE, UNDETERMINED_MULTI, DISCARDED, PENDING)

# Direcciones y paredes
BULL, BEAR, UNDETERMINED = "bull", "bear", "indeterminado"
SUPPORT, RESISTANCE = "soporte", "resistencia"

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
        return Classification(UNDETERMINED_SINGLE, reason="lado indeterminado", direction=UNDETERMINED,
                              premium=gross, **common)
    direction = _direction_of(leg, side)
    if side == BUY:
        return Classification(NET, reason="pata comprada", direction=direction,
                              premium=_signed(direction, gross), **common)
    wall = SUPPORT if option_type(leg) == "put" else RESISTANCE
    return Classification(WALLS, reason="pata vendida", direction=direction, premium=gross,
                          wall=wall, **common)


_COMBO_STRUCTURES = {
    strategies.COMBO_SAME_STRIKE: ("straddle", "sintético"),
    strategies.COMBO_DIFF_STRIKE: ("strangle", "risk reversal"),
    strategies.COMBO_DIFF_EXP: ("call + put con distinta expiración",) * 2,
}


def _two_legs(operation, legs, sides, base):
    gross = _gross(operation)
    g = strategies.geometry(legs)

    if g in _COMBO_STRUCTURES:
        same_side, opposite = _COMBO_STRUCTURES[g]
        if None in sides:
            structure = same_side if same_side == opposite else f"{same_side} o {opposite}"
        else:
            structure = same_side if sides[0] == sides[1] else opposite
        reason = ("risk reversal y sintéticos se descartan hasta decidir si van al neto"
                  if structure in ("sintético", "risk reversal") else "estructura que se descarta")
        return Classification(DISCARDED, structure=structure, reason=reason, direction=None,
                              premium=gross, **base)
    if g == strategies.CALENDAR:
        return Classification(DISCARDED, structure="calendar", reason="estructura que se descarta",
                              direction=None, premium=gross, **base)

    structure = "vertical" if g == strategies.VERTICAL else "diagonal"
    if None in sides:
        return Classification(UNDETERMINED_MULTI, structure=structure, reason="alguna pata sin lado claro",
                              direction=UNDETERMINED, premium=gross, **base)
    if sides[0] == sides[1]:
        return Classification(UNDETERMINED_MULTI, structure=structure,
                              reason="las dos patas del mismo lado", direction=UNDETERMINED,
                              premium=gross, **base)

    bought, sold = (legs[0], legs[1]) if sides[0] == BUY else (legs[1], legs[0])
    debit = bought["premium"] - sold["premium"]

    if g == strategies.VERTICAL:
        if debit > 0:
            direction = _direction_of(bought, BUY)
            return Classification(NET, structure="vertical de débito", reason="la pata comprada pesa más",
                                  direction=direction, strike=float(bought["strike"]),
                                  expiration=bought["exp_date"], premium=_signed(direction, debit), **base)
        if debit < 0:
            direction = _direction_of(sold, SELL)
            wall = SUPPORT if option_type(sold) == "put" else RESISTANCE
            return Classification(WALLS, structure="vertical de crédito", reason="la pata vendida pesa más",
                                  direction=direction, strike=float(sold["strike"]),
                                  expiration=sold["exp_date"], premium=-debit, wall=wall, **base)
        return Classification(UNDETERMINED_MULTI, structure="vertical", reason="débito y crédito iguales",
                              direction=UNDETERMINED, premium=gross, **base)

    # Diagonal: siempre al neto. La dirección es la de la pata con más premium
    # (la del script); el importe, |comprada − vendida| (decisión 0018).
    dominant, dominant_side = (bought, BUY) if debit >= 0 else (sold, SELL)
    direction = _direction_of(dominant, dominant_side)
    kind = "débito" if debit >= 0 else "crédito"
    return Classification(NET, structure=f"diagonal de {kind}", reason="las diagonales van al neto",
                          direction=direction, strike=float(bought["strike"]),
                          expiration=min(bought["exp_date"], sold["exp_date"]),
                          premium=_signed(direction, abs(debit)), **base)


def _override_sides(legs, override, measured):
    """Lados que fija una corrección, o (None, aviso) si no encaja con las patas."""
    if len(legs) == 1:
        if override.direction is None:
            return None, "corrección de tipo de operación en una single-leg: se ignora"
        if override.direction == UNDETERMINED:
            return (None,), None
        wants_call_bought = override.direction == BULL
        bought = (option_type(legs[0]) == "call") == wants_call_bought
        return (BUY if bought else SELL,), None
    strategy = strategies.BY_KEY.get(override.strategy) if override.strategy else None
    if strategy is None or not strategy.applies_to(legs):
        return None, f"el tipo de operación elegido ({override.strategy or override.direction}) " \
                     f"no encaja con las patas actuales: se ignora"
    return strategy.sides(legs), None


def _contradictions(legs, measured, chosen):
    notes = []
    for leg, m, c in zip(legs, measured, chosen):
        if m is not None and c is not None and m != c:
            notes.append(f"{leg['contract_symbol']}: la agresividad ({leg['agr']:+.2f}) indica {m}, "
                         f"la corrección dice {c}")
    return notes


def classify(operation, override=None):
    """Destino, dirección, strike, expiración y premium de una operación."""
    legs = operation.legs
    summary = operation.summary
    base = dict(size_ratio=_size_ratio(legs))
    gross = _gross(operation)

    if summary["stock_option"]:
        return Classification(DISCARDED, structure="con acciones", reason="incluye una pata de acciones",
                              direction=None, premium=gross, **base)
    if summary["patas_incompletas"]:
        return Classification(PENDING, structure="patas incompletas",
                              reason="multi-leg con una sola pata capturada", direction=None,
                              premium=gross, **base)
    if len(legs) >= 3:
        return Classification(DISCARDED, structure=f"{len(legs)} patas", reason="tres patas o más",
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
