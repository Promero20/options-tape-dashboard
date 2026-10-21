"""
El repositorio no versiona datos: ni CSV, ni bases de
datos de ediciones o posiciones, ni credenciales. Comprueba lo que git tiene
en seguimiento o preparado para commit.
"""

import subprocess
import tomllib

import pytest

from helpers import REPO_ROOT

FORBIDDEN_EXTENSIONS = (".csv", ".sqlite", ".sqlite3", ".db", ".env", ".pem", ".key")


def test_no_data_tracked_by_git():
    try:
        r = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True)
    except FileNotFoundError:
        pytest.skip("git no está instalado")
    if r.returncode != 0:
        pytest.skip("no es un repositorio git")
    forbidden = [f for f in r.stdout.splitlines()
                 if f.lower().endswith(FORBIDDEN_EXTENSIONS) or f.startswith("datos_usuario/")]
    assert forbidden == []


def test_every_package_is_declared_in_pyproject():
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        declared = set(tomllib.load(f)["tool"]["setuptools"]["packages"])
    src = REPO_ROOT / "src"
    found = {".".join(p.relative_to(src).parent.parts) for p in src.rglob("__init__.py")}
    assert declared == found | {"pipeline"}
