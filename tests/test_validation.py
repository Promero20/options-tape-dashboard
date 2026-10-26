"""Comparación de la reconstrucción con el nivel 3 guardado por el pipeline."""

import csv
import io
from datetime import date

import pytest

from helpers import LEGACY_SCRIPT, NEW_SCRIPT, run_script
from synthetic import scenario, trade, write_capture, write_level1, write_level2
from tape_dashboard.data import schemas, validation
from tape_dashboard.data.files import discover
from tape_dashboard.data.reconstruction import reconstruct_capture

DAY = date(2026, 10, 13)


@pytest.fixture
def folder(tmp_path):
    path = tmp_path / "datos"
    path.mkdir()
    write_capture(path, "20261013", scenario())
    return path


@pytest.fixture
def script_output(folder, tmp_path):
    r = run_script(NEW_SCRIPT, folder / "nivel2_trades_20261013.csv",
                   folder / "nivel1_candidatos_20261013.csv", tmp_path / "cli.csv", utf8_mode=False)
    assert r.returncode == 0, r.stderr.decode()
    return (tmp_path / "cli.csv").read_bytes()


def validate(folder):
    return validation.validate_capture(reconstruct_capture(discover(folder)[0][DAY]))


def store(folder, content):
    (folder / "nivel3_operaciones_20261013.csv").write_bytes(content)


def test_identical(folder, script_output):
    store(folder, script_output)
    result = validate(folder)
    assert (result.status, result.variant) == (validation.IDENTICAL, "N3-C")


def test_level3_generated_before_removing_cancellations(folder, tmp_path):
    # un trade grande cancelado: el script anterior contaba dos operaciones
    # por encima del umbral que no llegaron a ejecutarse
    big = [trade("AAA", "2026-11-20", 30, "call", "14:00:00.000", 5.0, 3000, 4.9, 5.0, "AUTO"),
           trade("AAA", "2026-11-20", 30, "call", "14:30:00.000", 5.0, 3000, 4.9, 5.0, "CANC")]
    write_capture(folder, "20261013", scenario() + big)
    r = run_script(LEGACY_SCRIPT, folder / "nivel2_trades_20261013.csv",
                   folder / "nivel1_candidatos_20261013.csv", tmp_path / "legacy.csv", utf8_mode=True)
    assert r.returncode == 0, r.stderr.decode()
    store(folder, (tmp_path / "legacy.csv").read_bytes())
    assert validate(folder).status == validation.PREVIOUS_VERSION


def test_old_single_leg_label_is_equivalent(folder, script_output):
    store(folder, script_output.replace(b"single_leg_call", b"single_leg").replace(b"single_leg_put", b"single_leg"))
    assert validate(folder).status == validation.LABEL_ONLY


def test_old_format(folder):
    header = ",".join(schemas.LEVEL3.variants["N3-B"])
    store(folder, (header + "\r\n" + ",".join(["x"] * 18) + "\r\n").encode())
    result = validate(folder)
    assert (result.status, result.variant) == (validation.OLD_FORMAT, "N3-B")


def test_different_content(folder, script_output):
    rows = list(csv.DictReader(io.StringIO(script_output.decode("utf-8"))))
    rows[0]["n_trades"] = "999"
    out = io.StringIO(newline="")
    writer = csv.DictWriter(out, fieldnames=schemas.LEVEL3_CURRENT)
    writer.writeheader()
    writer.writerows(rows)
    store(folder, out.getvalue().encode("utf-8"))
    result = validate(folder)
    assert result.status == validation.DIFFERENT
    assert result.detail.startswith("1 different rows")


def test_without_level3(folder):
    assert validate(folder).status == validation.NO_LEVEL3


def test_level3_without_level2(folder, script_output):
    store(folder, script_output)
    write_level2(folder / "nivel2_trades_20261013.csv", [])
    assert validate(folder).status == validation.LEVEL3_WITHOUT_LEVEL2
