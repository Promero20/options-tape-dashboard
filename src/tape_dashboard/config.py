"""
Configuración: dónde están los datos del pipeline y los datos del usuario.

Cada ruta se toma, por orden de prioridad, de:

1. una variable de entorno (TAPE_DATA_DIR, TAPE_USER_DATA_DIR);
2. el fichero config.toml de la raíz del repositorio (ver config.example.toml);
3. el valor por defecto: ../tape_data y ./user_data.

Optionally, `[pipeline] expected_hash_file` (or TAPE_EXPECTED_HASH_FILE) names a
file in which the capture pipeline declares the SHA-256 it expects for the
level-3 script; the dashboard warns if it is not the canonical one.

Las rutas relativas de config.toml se resuelven respecto a la raíz del repo.
"""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = REPO_ROOT / "config.toml"


@dataclass(frozen=True)
class Settings:
    data_dir: Path        # carpeta de datos del pipeline: solo lectura
    user_data_dir: Path   # ediciones manuales y posiciones: fuera de git
    expected_hash_file: Path | None = None   # where the pipeline declares the script's hash


def load_settings(config_file=CONFIG_FILE, environ=None):
    environ = os.environ if environ is None else environ
    config = {}
    if config_file is not None and Path(config_file).is_file():
        with open(config_file, "rb") as f:
            toml = tomllib.load(f)
        config = {**toml.get("paths", {}), **toml.get("pipeline", {})}

    def resolve(env_var, key, default):
        if environ.get(env_var):
            return Path(environ[env_var]).expanduser().resolve()
        if config.get(key):
            return (REPO_ROOT / Path(config[key]).expanduser()).resolve()
        return default.resolve() if default is not None else None

    return Settings(
        data_dir=resolve("TAPE_DATA_DIR", "data_dir", REPO_ROOT.parent / "tape_data"),
        user_data_dir=resolve("TAPE_USER_DATA_DIR", "user_data_dir", REPO_ROOT / "user_data"),
        expected_hash_file=resolve("TAPE_EXPECTED_HASH_FILE", "expected_hash_file", None),
    )
