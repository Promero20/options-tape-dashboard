"""
Validación de la reconstrucción contra el nivel 3 que guardó el pipeline.

El nivel 3 guardado no es fuente de datos (decisión 0001): solo sirve para
comprobar que la reconstrucción coincide con lo que generó el pipeline. Varios
días los generaron versiones anteriores del script, así que la comparación
distingue estos casos.
"""

import csv
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pipeline import nivel3_agrupar as n3

from . import schemas
from .loading import read_csv
from .reconstruction import reconstruct_capture

IDENTICAL = "identical"                    # byte a byte
PREVIOUS_VERSION = "previous version"     # idéntico al script previo, que no quitaba cancelaciones
LABEL_ONLY = "equivalent"                 # solo cambia la etiqueta single_leg antigua
OLD_FORMAT = "old format"                 # versión anterior del script con otras columnas
DIFFERENT = "different"                   # mismo formato, contenido distinto: revisar
NO_LEVEL3 = "no level 3"
LEVEL3_WITHOUT_LEVEL2 = "level 3 without level 2"
NOT_RECONSTRUCTED = "not rebuilt"         # hay nivel 3 pero el día no se pudo reconstruir


@dataclass(frozen=True)
class Validation:
    status: str
    detail: str = ""
    variant: str | None = None


def _reconstructed_csv(capture, folder):
    Path(folder).mkdir(parents=True, exist_ok=True)
    path = Path(folder) / "nivel3.csv"
    all_ops = [op.summary for op in capture.operations]
    passing = [op.summary for op in capture.operations if op.passes_threshold]
    n3.escribir_operaciones(path, all_ops, passing)
    return path


def _old_label(row):
    """Las versiones anteriores escribían 'single_leg' sin el tipo."""
    if row["estructura"].startswith("single_leg_"):
        return dict(row, estructura="single_leg")
    return row


def validate_capture(capture):
    stored = capture.files.level3
    if stored is None:
        return Validation(NO_LEVEL3)
    fieldnames, stored_rows = read_csv(stored)
    variant = schemas.match_header(schemas.LEVEL3, fieldnames).variant
    if not capture.usable:
        level2_empty = capture.files.level2 is None or (
            capture.level2 is not None and not capture.level2.rows)
        if level2_empty:
            return Validation(LEVEL3_WITHOUT_LEVEL2, f"{len(stored_rows)} stored operations", variant)
        return Validation(NOT_RECONSTRUCTED, f"{len(stored_rows)} stored operations", variant)

    # La reconstrucción actual y, si la captura tiene cancelaciones, la del
    # script anterior al 19/10/2026, que las agrupaba como trades.
    versions = [capture]
    if capture.cancellations:
        versions.append(reconstruct_capture(capture.files, remove_cancellations=False))
    stored_bytes = stored.read_bytes()
    rebuilt_rows = []
    with tempfile.TemporaryDirectory() as folder:
        for i, version in enumerate(versions):
            rebuilt = _reconstructed_csv(version, Path(folder) / str(i))
            if rebuilt.read_bytes() == stored_bytes:
                if version is capture:
                    return Validation(IDENTICAL, f"{len(stored_rows)} operations", variant)
                return Validation(PREVIOUS_VERSION, f"{len(stored_rows)} operations; produced before "
                                                    f"cancellations were dropped", variant)
            with open(rebuilt, encoding="utf-8", newline="") as f:
                rebuilt_rows.append(list(csv.DictReader(f)))

    if tuple(fieldnames) != schemas.LEVEL3_CURRENT:
        return Validation(OLD_FORMAT, f"{len(stored_rows)} stored operations, "
                                      f"{len(rebuilt_rows[0])} rebuilt", variant)
    for rows in rebuilt_rows:
        if [_old_label(r) for r in rows] == stored_rows:
            return Validation(LABEL_ONLY, f"{len(stored_rows)} operations; only "
                                          f"'single_leg' → 'single_leg_call/put' differs", variant)
    rebuilt_rows = rebuilt_rows[0]
    differing = sum(1 for a, b in zip(rebuilt_rows, stored_rows) if _old_label(a) != _old_label(b))
    differing += abs(len(rebuilt_rows) - len(stored_rows))
    return Validation(DIFFERENT, f"{differing} different rows ({len(stored_rows)} stored, "
                                 f"{len(rebuilt_rows)} rebuilt)", variant)
