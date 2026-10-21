"""Lado de una pata (compra o venta) a partir de su agresividad."""

from pipeline import nivel3_agrupar as n3

BUY = "compra"
SELL = "venta"

# La agresividad se calcula con coma flotante: un trade a un cuarto del
# half-spread puede salir como 0.2499999999999989 o como 0.25000000000000333.
# La tolerancia hace que la frontera sea siempre indeterminada.
_TOLERANCE = 1e-9


def leg_side(aggressiveness):
    """
    Compra si la agresividad es > +0,25; venta si es < −0,25; None
    (indeterminado) entre ambas, en la frontera o sin dato. El umbral es
    ZONA_MUERTA del script de nivel 3.
    """
    if aggressiveness is None or abs(aggressiveness) <= n3.ZONA_MUERTA + _TOLERANCE:
        return None
    return BUY if aggressiveness > 0 else SELL


def option_type(leg):
    """'call' o 'put', sea cual sea la capitalización del fichero."""
    return "call" if leg["type"].lower().startswith("c") else "put"
