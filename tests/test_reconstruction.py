"""Reconstrucción de operaciones por captura y consultas por rango de fechas de captura."""

from datetime import date

import pytest

from helpers import NEW_SCRIPT, run_script
from pipeline import nivel3_agrupar as n3
from synthetic import LEVEL2_VARIANTS, scenario, trade, write_capture, write_level1, write_level2
from tape_dashboard.data.dataset import load_dataset
from tape_dashboard.data.files import discover
from tape_dashboard.data.issues import ERROR, WARNING
from tape_dashboard.data.reconstruction import reconstruct_capture

D13, D14, D15, D16 = (date(2026, 10, d) for d in (13, 14, 15, 16))


def capture_for(folder, day):
    return reconstruct_capture(discover(folder)[0][day])


def messages(issues, severity):
    return [f"{i.file}: {i.message}" for i in issues if i.severity == severity]


@pytest.fixture
def folder(tmp_path):
    path = tmp_path / "datos"
    path.mkdir()
    return path


# --- Una captura -----------------------------------------------------------

@pytest.mark.parametrize("variant", LEVEL2_VARIANTS)
def test_reconstruction_is_identical_to_the_script(variant, folder, tmp_path):
    write_capture(folder, "20261013", scenario(), level2_variant=variant)
    capture = capture_for(folder, D13)
    assert capture.usable

    cli = run_script(NEW_SCRIPT, folder / "nivel2_trades_20261013.csv",
                     folder / "nivel1_candidatos_20261013.csv", tmp_path / "cli.csv", utf8_mode=False)
    assert cli.returncode == 0, cli.stderr.decode()
    n3.escribir_operaciones(tmp_path / "rebuilt.csv", [op.summary for op in capture.operations],
                            [op.summary for op in capture.passing])
    assert (tmp_path / "rebuilt.csv").read_bytes() == (tmp_path / "cli.csv").read_bytes()


def test_operations_keep_everything_and_flag_the_threshold(folder):
    write_capture(folder, "20261013", scenario())
    capture = capture_for(folder, D13)
    ops = {op.id: op for op in capture.operations}

    assert len(ops) == len(capture.operations)
    premiums = [op.premium for op in capture.operations]
    assert premiums == sorted(premiums, reverse=True)
    assert ops["20261013-AAA-10:00:00.000-AUTO"].passes_threshold
    assert not ops["20261013-AAA-10:10:00.000-AUTO"].passes_threshold
    assert len(ops["20261013-BBB-11:00:00.100-MLET"].legs) == 2
    assert ops["20261014-CCC-09:31:00.000-AUTO"].trade_dates == [D14]
    without_price = ops["20261013-DDD-10:00:00.000-AUTO"]
    assert without_price.price is None and without_price.passes_threshold
    assert any("DDD" in m for m in messages(capture.issues, WARNING))


def test_level2_without_trades_is_not_usable(folder):
    write_level1(folder / "nivel1_candidatos_20261013.csv", scenario())
    write_level2(folder / "nivel2_trades_20261013.csv", [])
    capture = capture_for(folder, D13)
    assert not capture.usable
    assert any("sin trades" in m for m in messages(capture.issues, WARNING))


def test_level2_without_level1_is_an_error(folder):
    write_level2(folder / "nivel2_trades_20261013.csv", scenario())
    capture = capture_for(folder, D13)
    assert not capture.usable
    assert any("nivel 1" in m for m in messages(capture.issues, ERROR))


def test_schema_error_names_the_file_and_the_missing_columns(folder):
    write_level1(folder / "nivel1_candidatos_20261013.csv", scenario())
    header = [c for c in __import__("tape_dashboard.data.schemas", fromlist=["LEVEL2"]).LEVEL2.variants["N2-E"]
              if c != "Premium"]
    write_level2(folder / "nivel2_trades_20261013.csv", scenario(), header=header)
    capture = capture_for(folder, D13)
    assert not capture.usable
    errors = messages(capture.issues, ERROR)
    assert any(m.startswith("nivel2_trades_20261013.csv:") and "Premium" in m for m in errors)


def test_unrecognised_csv_is_reported(folder):
    (folder / "candidatos_pata_faltante_20261013.csv").write_text("a,b\n", encoding="utf-8")
    _, issues = discover(folder)
    assert messages(issues, WARNING) == ["candidatos_pata_faltante_20261013.csv: CSV no reconocido: no se carga"]


# --- Varias capturas -------------------------------------------------------

@pytest.fixture
def dataset(folder):
    trades = scenario()
    write_capture(folder, "20261013", trades)
    # la captura del 15 vuelve a traer los contratos de BBB del 13 (mismos
    # trades, mismos IDs), con otras variantes de esquema, y un trade nuevo
    again = [t for t in trades if t["symbol"] == "BBB"] + [
        trade("AAA", "2026-11-20", 30, "call", "10:00:00.000", 5.0, 2000, 4.9, 5.0, "AUTO", date="2026-10-14")]
    write_capture(folder, "20261015", again, level1_variant="N1-B", level2_variant="N2-B")
    # el 16 hay nivel 1 pero el nivel 2 llegó vacío
    write_level1(folder / "nivel1_candidatos_20261016.csv", trades)
    write_level2(folder / "nivel2_trades_20261016.csv", [])
    return load_dataset(folder)


def test_repeated_operation_counts_once_in_a_range(dataset):
    vertical = "20261013-BBB-11:00:00.100-MLET"
    assert dataset.repeated_ids()[vertical] == [D13, D15]

    both = dataset.operations(D13, D16)
    assert [op.id for op in both].count(vertical) == 1
    assert next(op for op in both if op.id == vertical).capture_date == D15

    first_only = dataset.operations(D13, D13)
    assert next(op for op in first_only if op.id == vertical).capture_date == D13


def test_range_returns_passing_operations_by_premium(dataset):
    passing = dataset.operations(D13, D15)
    assert all(op.passes_threshold for op in passing)
    assert [op.premium for op in passing] == sorted((op.premium for op in passing), reverse=True)
    everything = dataset.operations(D13, D15, passing_only=False)
    assert len(everything) > len(passing)


def test_today_is_the_capture_of_today_or_the_latest_one(dataset):
    assert dataset.usable_dates == [D13, D15]
    assert dataset.resolve_today(D15) == (D15, True)
    assert dataset.resolve_today(D14) == (D13, False)        # sin captura ese día
    assert dataset.resolve_today(D16) == (D15, False)        # captura sin trades
    assert dataset.resolve_today(date(2026, 10, 1)) == (None, False)
