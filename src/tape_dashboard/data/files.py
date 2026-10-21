"""Descubrimiento de los ficheros del pipeline, agrupados por fecha de captura."""

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from pipeline import nivel3_agrupar

from .issues import WARNING, Issue

PATTERNS = {
    "level1": re.compile(r"nivel1_candidatos_(\d{8})\.csv"),
    "level2": re.compile(r"nivel2_trades_(\d{8})\.csv"),
    "level3": re.compile(r"nivel3_operaciones_(\d{8})\.csv"),
}

SCRIPT_NAME = "nivel3_agrupar.py"
CANONICAL_SCRIPT = Path(nivel3_agrupar.__file__).resolve()


@dataclass
class CaptureFiles:
    date: date
    level1: Path | None = None
    level2: Path | None = None
    level3: Path | None = None


def discover(data_dir):
    """
    Devuelve ({fecha de captura: CaptureFiles}, avisos). Un CSV cuyo nombre no
    sigue ningún patrón conocido se reporta, no se ignora.
    """
    captures, issues = {}, []
    for path in sorted(Path(data_dir).glob("*.csv")):
        for level, pattern in PATTERNS.items():
            m = pattern.fullmatch(path.name)
            if m:
                try:
                    day = datetime.strptime(m.group(1), "%Y%m%d").date()
                except ValueError:
                    issues.append(Issue(WARNING, path.name, "fecha no válida en el nombre"))
                    break
                setattr(captures.setdefault(day, CaptureFiles(day)), level, path)
                break
        else:
            issues.append(Issue(WARNING, path.name, "CSV no reconocido: no se carga"))
    return dict(sorted(captures.items())), issues


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class ScriptStatus:
    found: bool
    matches: bool
    deployed_sha256: str | None
    canonical_sha256: str


def script_status(data_dir):
    """Compara la copia del script en la carpeta de datos con la canónica del repo."""
    canonical = _sha256(CANONICAL_SCRIPT)
    deployed_path = Path(data_dir) / SCRIPT_NAME
    if not deployed_path.is_file():
        return ScriptStatus(False, False, None, canonical)
    deployed = _sha256(deployed_path)
    return ScriptStatus(True, deployed == canonical, deployed, canonical)
