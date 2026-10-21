"""
Reconstrucción de las operaciones de una captura a partir de su nivel 2.

Toda la lógica de agrupación, resumen, ID y umbral es la del script de nivel
3 (pipeline/nivel3_agrupar.py): aquí solo se encadenan sus funciones. Se
conservan todas las operaciones, también las que no superan el umbral,
porque las ediciones manuales se aplican antes de filtrar.
"""

from dataclasses import dataclass, field
from datetime import date

from pipeline import nivel3_agrupar as n3

from .files import CaptureFiles
from .issues import ERROR, INFO, WARNING, Issue
from .loading import Level1Data, Level2Data, SchemaError, load_level1, load_level2


@dataclass
class Operation:
    id: str
    capture_date: date
    summary: dict            # resumen() del script; premium_total en dólares
    legs: list[dict]         # patas_de() del script, de mayor a menor premium
    trades: list[dict]       # filas de trade del grupo
    price: float | None      # precio del subyacente en el nivel 1 de la captura
    passes_threshold: bool

    @property
    def symbol(self):
        return self.summary["symbol"]

    @property
    def premium(self):
        return self.summary["premium_total"]

    @property
    def trade_dates(self):
        return sorted({r["t"].date() for r in self.trades})


@dataclass
class Capture:
    date: date
    files: CaptureFiles
    level1: Level1Data | None = None
    level2: Level2Data | None = None
    n_trades: int = 0
    operations: list[Operation] = field(default_factory=list)   # orden de resumir_todas()
    cancellations: list[tuple] = field(default_factory=list)    # (cancelación, trade anulado o None)
    issues: list[Issue] = field(default_factory=list)
    usable: bool = False

    @property
    def passing(self):
        return [op for op in self.operations if op.passes_threshold]


def _load(loader, path, capture):
    try:
        data = loader(path)
    except SchemaError as e:
        capture.issues.append(Issue(ERROR, e.file, str(e).split(": ", 1)[1]))
        return None
    capture.issues.extend(data.issues)
    return data


def reconstruct_capture(files, remove_cancellations=True):
    """
    Operaciones de una captura. Con remove_cancellations=False se reproduce la
    versión del script anterior al 19/10/2026, que agrupaba las cancelaciones
    como trades; solo sirve para validar niveles 3 antiguos.
    """
    capture = Capture(files.date, files)
    day = files.date.isoformat()

    if files.level1 is not None:
        capture.level1 = _load(load_level1, files.level1, capture)
    if files.level2 is not None:
        capture.level2 = _load(load_level2, files.level2, capture)

    if files.level2 is None:
        capture.issues.append(Issue(INFO, None, f"captura {day}: sin nivel 2"))
        return capture
    if capture.level2 is None:
        return capture   # el error de esquema ya está reportado
    if not capture.level2.rows:
        capture.issues.append(Issue(WARNING, files.level2.name,
                                    "nivel 2 sin trades: el día no se puede reconstruir"))
        return capture
    if capture.level1 is None:
        capture.issues.append(Issue(ERROR, files.level2.name,
                                    "falta un nivel 1 utilizable del mismo día: sin precio no se "
                                    "puede aplicar el umbral"))
        return capture

    rows = n3.preparar_filas(capture.level2.rows, capture.level2.fieldnames)
    if remove_cancellations:
        rows, capture.cancellations = n3.quitar_cancelaciones(rows)
        if capture.cancellations:
            unmatched = sum(1 for _, cancelled in capture.cancellations if cancelled is None)
            capture.issues.append(Issue(INFO, files.level2.name,
                                        f"{len(capture.cancellations)} cancelaciones quitadas junto con "
                                        f"el trade que anulan"))
            if unmatched:
                capture.issues.append(Issue(WARNING, files.level2.name,
                                            f"{unmatched} cancelaciones sin trade anulado localizado "
                                            f"(se quitan igualmente)"))
    capture.n_trades = len(rows)
    if not rows:
        capture.issues.append(Issue(WARNING, files.level2.name,
                                    "nivel 2 sin trades válidos (solo pies de página o filas sin hora)"))
        return capture

    prices = capture.level1.prices
    operations = []
    for group in n3.agrupar(rows).values():
        summary = n3.resumen(group)
        price = prices.get(summary["symbol"])
        operations.append(Operation(
            id=n3.id_operacion(group),
            capture_date=files.date,
            summary=summary,
            legs=n3.patas_de(group),
            trades=group,
            price=price,
            passes_threshold=n3.pasa_umbral(summary["premium_total"], price),
        ))
    # mismo orden que resumir_todas(): premium descendente, orden estable
    operations.sort(key=lambda op: -op.premium)
    capture.operations = operations
    capture.usable = True

    without_price = sorted({op.symbol for op in operations if op.price is None})
    if without_price:
        capture.issues.append(Issue(WARNING, files.level1.name,
                                    f"símbolos del nivel 2 sin precio en el nivel 1 (sus operaciones "
                                    f"no se filtran por umbral): {', '.join(without_price)}"))
    ids = [op.id for op in operations]
    if len(ids) != len(set(ids)):
        capture.issues.append(Issue(ERROR, files.level2.name, "IDs de operación repetidos"))
    return capture
