"""Lado de una pata (compra o venta) a partir de su agresividad."""

from pipeline import nivel3_agrupar as n3

BUY = "buy"
SELL = "sell"

_FROM_SCRIPT = {n3.COMPRA: BUY, n3.VENTA: SELL}


def leg_side(aggressiveness):
    """
    Buy if the aggressiveness is > +0.25, sell if it is < −0.25, None
    (undetermined) in between, at the boundary or without data. It is the
    level-3 script's lado(), with its ZONA_MUERTA and TOLERANCIA_ZONA_MUERTA:
    one boundary for the whole project (decisions 0017 and 0036).
    """
    return _FROM_SCRIPT.get(n3.lado(aggressiveness))


def operation_side(script_side):
    """The script's side of an operation ('compra', 'venta', 'indeterminado') as buy, sell or None."""
    return _FROM_SCRIPT.get(script_side)


def option_type(leg):
    """'call' o 'put', sea cual sea la capitalización del fichero."""
    return "call" if leg["type"].lower().startswith("c") else "put"
