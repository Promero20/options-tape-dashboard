"""
No regresión de nivel3_agrupar.py.

La salida del script (pipeline/) se compara byte a byte con la de la versión
congelada del 01/10/2026 (tests/legacy/). El único cambio de salida
deliberado desde entonces es quitar las cancelaciones junto con el trade que
anulan (decisión 0015). Por eso el oráculo es la versión congelada ejecutada
sobre el mismo nivel 2 sin esas filas: si no hay cancelaciones, es el mismo
fichero. Se comprueba con los datos reales de cada día con nivel 2 y con el
escenario sintético en cada variante de esquema.
"""

import csv

import pytest

from helpers import LEGACY_SCRIPT, NEW_SCRIPT, days_with_level2, run_script
from synthetic import LEVEL2_VARIANTS, scenario, write_level1, write_level2

CANCEL_CONDITIONS = {"CANC", "CNCL", "CNCO", "CNOL"}

# Días cuyo nivel3 guardado lo generó la versión del 01/10 y que no tienen
# cancelaciones: el script actual debe reproducirlo byte a byte. Los
# anteriores salieron de versiones más antiguas (ver docs/data-quality.md).
DAYS_WITH_CURRENT_LEVEL3 = ["20261006", "20261013", "20261015"]


def without_cancellations(level2, output):
    """
    Copia del nivel 2 sin las cancelaciones ni los trades que anulan. Es una
    implementación independiente de la del script, a partir del CSV crudo,
    para no comprobar el script consigo mismo. Devuelve cuántas
    cancelaciones había.
    """
    with open(level2, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header, rows = reader.fieldnames, list(reader)
    api = "tradeTime" in header
    time, price, size = ("tradeTime", "lastPrice", "tradeSize") if api else ("Time", "Trade", "Trade Size")
    condition = "tradeConditionCode" if api else "Trade Condition"

    cancels = sorted((r for r in rows if r[condition] in CANCEL_CONDITIONS), key=lambda r: r[time])
    removed = {id(c) for c in cancels}
    for c in cancels:
        candidates = [r for r in rows
                      if id(r) not in removed and r[time]
                      and r["contract_symbol"] == c["contract_symbol"]
                      and float(r[size]) == float(c[size]) and float(r[price]) == float(c[price])
                      and r[time] <= c[time]]
        if candidates:
            removed.add(id(max(candidates, key=lambda r: r[time])))

    with open(output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(r for r in rows if id(r) not in removed)
    return len(cancels)


def assert_same_as_legacy(level2, level1, tmp_path):
    filtered = tmp_path / "nivel2_sin_cancelaciones.csv"
    n_cancels = without_cancellations(level2, filtered)
    legacy_output, new_output = tmp_path / "legacy.csv", tmp_path / "new.csv"
    # El legacy necesita el modo UTF-8 para escribir '→' en Windows (en el
    # Linux del pipeline es el comportamiento por defecto).
    legacy = run_script(LEGACY_SCRIPT, filtered, level1, legacy_output, utf8_mode=True)
    assert legacy.returncode == 0, legacy.stderr.decode()
    # El nuevo se ejecuta sin forzarlo: debe funcionar con la codificación
    # por defecto del sistema, también en Windows.
    new = run_script(NEW_SCRIPT, level2, level1, new_output, utf8_mode=False)
    assert new.returncode == 0, new.stderr.decode()

    assert new_output.read_bytes() == legacy_output.read_bytes()
    legacy_lines, new_lines = legacy.stdout.splitlines(), new.stdout.splitlines()
    assert new_lines[0] == legacy_lines[0]
    if n_cancels:
        assert new_lines[1].startswith(f"{n_cancels} cancelaciones quitadas".encode())
    else:
        assert new.stdout == legacy.stdout
    return new_output


@pytest.mark.parametrize("variant", LEVEL2_VARIANTS)
def test_no_regression_synthetic(variant, tmp_path):
    trades = scenario()
    level2 = tmp_path / "nivel2_trades_20261013.csv"
    level1 = tmp_path / "nivel1_candidatos_20261013.csv"
    write_level2(level2, trades, variant)
    write_level1(level1, trades)

    output = assert_same_as_legacy(level2, level1, tmp_path)
    # el calendar del escenario obliga a escribir '→'
    assert "→" in output.read_text(encoding="utf-8")


def test_without_cancellations_the_output_is_untouched(tmp_path):
    trades = [t for t in scenario() if t["Trade Condition"] not in CANCEL_CONDITIONS]
    level2, level1 = tmp_path / "n2.csv", tmp_path / "n1.csv"
    write_level2(level2, trades)
    write_level1(level1, trades)
    legacy = run_script(LEGACY_SCRIPT, level2, level1, tmp_path / "legacy.csv", utf8_mode=True)
    new = run_script(NEW_SCRIPT, level2, level1, tmp_path / "new.csv", utf8_mode=False)
    assert new.stdout == legacy.stdout
    assert (tmp_path / "new.csv").read_bytes() == (tmp_path / "legacy.csv").read_bytes()


@pytest.mark.real_data
@pytest.mark.parametrize("day", days_with_level2())
def test_no_regression_real_data(day, data_dir, tmp_path):
    assert_same_as_legacy(
        data_dir / f"nivel2_trades_{day}.csv", data_dir / f"nivel1_candidatos_{day}.csv", tmp_path)


@pytest.mark.real_data
@pytest.mark.parametrize("day", DAYS_WITH_CURRENT_LEVEL3)
def test_matches_stored_level3(day, data_dir, tmp_path):
    stored = data_dir / f"nivel3_operaciones_{day}.csv"
    if not stored.exists():
        pytest.skip(f"no existe {stored.name}")
    output = tmp_path / "new.csv"
    r = run_script(NEW_SCRIPT, data_dir / f"nivel2_trades_{day}.csv",
                   data_dir / f"nivel1_candidatos_{day}.csv", output, utf8_mode=False)
    assert r.returncode == 0, r.stderr.decode()
    assert output.read_bytes() == stored.read_bytes()
