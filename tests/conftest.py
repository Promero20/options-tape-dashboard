"""
Fixtures comunes de los tests.

Los tests con datos reales leen la carpeta de datos y se omiten si no
existe (por ejemplo, en GitHub). Esa carpeta es de solo lectura: los tests
solo escriben en directorios temporales.
"""

import pytest

from helpers import data_dir as find_data_dir


@pytest.fixture(scope="session")
def data_dir():
    path = find_data_dir()
    if path is None:
        pytest.skip("no hay carpeta de datos (ver TAPE_DATA_DIR o config.toml)")
    return path
