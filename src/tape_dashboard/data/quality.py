"""
Indicadores de calidad del nivel 2. Son informativos: no cambian la
agrupación ni la clasificación (ver docs/data-quality.md).
"""

import collections
from dataclasses import dataclass

CANCEL_CONDITIONS = {"CANC", "CNCL", "CNCO", "CNOL"}


@dataclass(frozen=True)
class Level2Quality:
    trades: int
    crossed_quotes: int       # bid > ask: el signo de la agresividad sale invertido
    cancellations: int        # condición de cancelación; el script las agrupa como trades
    identical_rows: int       # filas repetidas exactamente (sin ID de trade, no se distinguen)
    size_ten: int             # tamaño 10: los trades llegan filtrados con >= 10
    without_aggressiveness: int


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def level2_quality(level2):
    rows = [r for r in level2.rows if r.get("Time") and r.get("es_metadata_footer") != "True"]
    fields = level2.fieldnames
    crossed = sum(1 for r in rows
                  if None not in (_float(r["Bid"]), _float(r["Ask"])) and _float(r["Bid"]) > _float(r["Ask"]))
    cancellations = sum(1 for r in rows
                        if r["Trade Condition"] in CANCEL_CONDITIONS or r.get("es_cancelacion") == "True")
    counts = collections.Counter(tuple(r[f] for f in fields) for r in rows)
    identical = sum(n - 1 for n in counts.values() if n > 1)
    size_ten = sum(1 for r in rows if _float(r["Trade Size"]) == 10)
    without_agr = sum(1 for r in rows if not r["agresividad"])
    return Level2Quality(len(rows), crossed, cancellations, identical, size_ten, without_agr)
