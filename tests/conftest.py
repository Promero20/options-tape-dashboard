"""
Fixtures comunes de los tests.

Los tests con datos reales leen la carpeta de datos y se omiten si no
existe (por ejemplo, en GitHub). Esa carpeta es de solo lectura: los tests
solo escriben en directorios temporales.
"""

from datetime import date

import pytest

from helpers import data_dir as find_data_dir
from synthetic import scenario, trade, write_capture, write_level1, write_level2
from tape_dashboard.config import Settings


@pytest.fixture(scope="session")
def data_dir():
    path = find_data_dir()
    if path is None:
        pytest.skip("no hay carpeta de datos (ver TAPE_DATA_DIR o config.toml)")
    return path


@pytest.fixture
def synthetic_folder(tmp_path):
    """
    Synthetic data folder with three captures: 13/10 (the full scenario),
    15/10 (BBB's trades again plus a new AAA trade) and 16/10 (empty level 2).
    """
    folder = tmp_path / "data"
    folder.mkdir()
    trades = scenario()
    write_capture(folder, "20261013", trades)
    again = [t for t in trades if t["symbol"] == "BBB"] + [
        trade("AAA", "2026-11-20", 30, "call", "10:00:00.000", 5.0, 2000, 4.9, 5.0, "AUTO", date="2026-10-14")]
    write_capture(folder, "20261015", again, level1_variant="N1-B", level2_variant="N2-B")
    write_level1(folder / "nivel1_candidatos_20261016.csv", trades)
    write_level2(folder / "nivel2_trades_20261016.csv", [])
    return folder


@pytest.fixture
def synthetic_settings(synthetic_folder, tmp_path):
    return Settings(data_dir=synthetic_folder, user_data_dir=tmp_path / "user")


@pytest.fixture
def app(synthetic_settings):
    from tape_dashboard.app import create_app
    return create_app(synthetic_settings, today=lambda: date(2026, 10, 15))
