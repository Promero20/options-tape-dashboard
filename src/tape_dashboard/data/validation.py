"""
Validación de la reconstrucción contra el nivel 3 que guardó el pipeline.

El nivel 3 guardado no es fuente de datos (decisión 0001): solo sirve para
comprobar que la reconstrucción coincide con lo que generó el pipeline. Varios
días los generaron versiones anteriores del script, así que la comparación
distingue estos casos.

The earlier versions are reproduced with their frozen copies in tests/legacy,
run from the command line as the pipeline ran them: the script before the
grouping rule of 16/11/2026 (decision 0036) and the one before cancellations
were dropped (decision 0015). Without those copies, the comparison stops at the
current reconstruction: a stored file with the previous header is then "not
checked" instead of "different".
"""

import csv
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pipeline import nivel3_agrupar as n3

from ..config import REPO_ROOT
from . import schemas
from .loading import read_csv

IDENTICAL = "identical"                    # byte a byte
PREVIOUS_RULE = "previous grouping rule"  # identical to the script before decision 0036
PREVIOUS_VERSION = "previous version"     # idéntico al script previo, que no quitaba cancelaciones
LABEL_ONLY = "equivalent"                 # solo cambia la etiqueta single_leg antigua
OLD_FORMAT = "old format"                 # versión anterior del script con otras columnas
DIFFERENT = "different"                   # mismo formato, contenido distinto: revisar
NO_LEVEL3 = "no level 3"
LEVEL3_WITHOUT_LEVEL2 = "level 3 without level 2"
NOT_RECONSTRUCTED = "not rebuilt"         # hay nivel 3 pero el día no se pudo reconstruir
NOT_CHECKED = "not checked"               # previous header, but an earlier script could not be run

LEGACY_DIR = REPO_ROOT / "tests" / "legacy"
# (frozen script, status if the stored file matches it, detail)
EARLIER_SCRIPTS = (
    (LEGACY_DIR / "nivel3_agrupar_20261021.py", PREVIOUS_RULE, "produced by the grouping rule before 16/11/2026"),
    (LEGACY_DIR / "nivel3_agrupar_20261001.py", PREVIOUS_VERSION, "produced before cancellations were dropped"),
)


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


def _earlier_csv(script, files, folder):
    """Output of a frozen earlier script on the capture's files, or None if it is missing or fails."""
    if not script.is_file():
        return None
    output = Path(folder) / f"{script.stem}.csv"
    # UTF-8 mode: the earlier scripts write '→' without naming the encoding (as on the pipeline's Linux)
    result = subprocess.run([sys.executable, "-X", "utf8", str(script), str(files.level2), str(files.level1),
                             str(output)], capture_output=True)
    return output if result.returncode == 0 and output.is_file() else None


def _rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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

    stored_bytes = stored.read_bytes()
    candidates = []        # rows of every version, to compare when no file is identical
    not_run = []           # earlier scripts that are missing or failed
    with tempfile.TemporaryDirectory() as folder:
        rebuilt = _reconstructed_csv(capture, Path(folder) / "current")
        if rebuilt.read_bytes() == stored_bytes:
            return Validation(IDENTICAL, f"{len(stored_rows)} operations", variant)
        candidates.append(_rows(rebuilt))
        for script, status, detail in EARLIER_SCRIPTS:
            earlier = _earlier_csv(script, capture.files, folder)
            if earlier is None:
                not_run.append(script.name)
                continue
            if earlier.read_bytes() == stored_bytes:
                return Validation(status, f"{len(stored_rows)} operations; {detail}", variant)
            candidates.append(_rows(earlier))

    if tuple(fieldnames) not in (schemas.LEVEL3_CURRENT, schemas.LEVEL3_PREVIOUS):
        return Validation(OLD_FORMAT, f"{len(stored_rows)} stored operations, "
                                      f"{len(candidates[0])} rebuilt", variant)
    same_columns = [rows for rows in candidates if not rows or tuple(rows[0]) == tuple(fieldnames)]
    for rows in same_columns:
        if [_old_label(r) for r in rows] == stored_rows:
            return Validation(LABEL_ONLY, f"{len(stored_rows)} operations; only "
                                          f"'single_leg' → 'single_leg_call/put' differs", variant)
    if not_run and tuple(fieldnames) == schemas.LEVEL3_PREVIOUS:
        return Validation(NOT_CHECKED, f"{len(stored_rows)} stored operations; could not run "
                                       f"{', '.join(not_run)}", variant)
    rebuilt_rows = same_columns[0] if same_columns else candidates[0]
    differing = sum(1 for a, b in zip(rebuilt_rows, stored_rows) if _old_label(a) != _old_label(b))
    differing += abs(len(rebuilt_rows) - len(stored_rows))
    return Validation(DIFFERENT, f"{differing} different rows ({len(stored_rows)} stored, "
                                 f"{len(rebuilt_rows)} rebuilt)", variant)
