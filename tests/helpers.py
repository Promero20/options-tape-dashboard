"""Rutas y utilidades compartidas por los tests."""

import csv
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

from tape_dashboard.config import load_settings

REPO_ROOT = Path(__file__).resolve().parent.parent
NEW_SCRIPT = REPO_ROOT / "pipeline" / "nivel3_agrupar.py"
LEGACY_SCRIPT = REPO_ROOT / "tests" / "legacy" / "nivel3_agrupar_20261001.py"


def data_dir():
    """Carpeta de datos según la configuración del dashboard, o None si no existe."""
    path = load_settings().data_dir
    return path if path.is_dir() else None


def _has_trades(path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        return next(reader, None) is not None


def days_with_level2():
    """Fechas de captura (YYYYMMDD) con nivel 2 no vacío y nivel 1 disponible."""
    folder = data_dir()
    if folder is None:
        return []
    days = []
    for path in sorted(folder.glob("nivel2_trades_*.csv")):
        m = re.fullmatch(r"nivel2_trades_(\d{8})\.csv", path.name)
        if m and (folder / f"nivel1_candidatos_{m.group(1)}.csv").exists() and _has_trades(path):
            days.append(m.group(1))
    return days


def run_script(script, level2, level1, output, utf8_mode):
    """
    Ejecuta un script de nivel 3 por línea de comandos, como lo hace el pipeline,
    y devuelve el proceso terminado. Con utf8_mode=True se fuerza el modo
    UTF-8 de Python, que reproduce el entorno Linux del pipeline; el script
    legacy lo necesita en Windows para poder escribir el carácter '→'.
    """
    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)
    if utf8_mode:
        env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, "-B", str(script), str(level2), str(level1), str(output)],
        capture_output=True, env=env, check=False,
    )


def snapshot(folder):
    """Estado de una carpeta (tamaño, fecha de modificación y hash de cada fichero)."""
    state = {}
    for path in sorted(Path(folder).rglob("*")):
        key = path.relative_to(folder).as_posix()
        if path.is_file():
            st = path.stat()
            state[key] = (st.st_size, st.st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
        else:
            state[key] = "dir"
    return state
