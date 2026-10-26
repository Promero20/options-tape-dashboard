"""Indicadores de calidad del nivel 2 e informe por consola."""

import hashlib
from pathlib import Path

import pytest

from helpers import NEW_SCRIPT
from synthetic import scenario, write_capture, write_level1, write_level2
from tape_dashboard import report
from tape_dashboard.data.dataset import load_dataset
from tape_dashboard.data.files import DeclaredHash, declared_hash
from tape_dashboard.data.loading import load_level2
from tape_dashboard.data.quality import level2_quality


@pytest.mark.parametrize("variant", ["N2-A", "N2-E"])
def test_quality_indicators(variant, tmp_path):
    trades = scenario()
    path = tmp_path / "n2.csv"
    write_level2(path, trades, variant)
    q = level2_quality(load_level2(path))
    assert q.trades == len(trades)          # sin la fila vacía ni el pie de página
    assert q.crossed_quotes == 1
    assert q.cancellations == 2
    assert q.identical_rows == 1
    assert q.size_ten == 2
    assert q.without_aggressiveness == 1


def test_report_renders_every_section(tmp_path):
    folder = tmp_path / "datos"
    folder.mkdir()
    write_capture(folder, "20261013", scenario())
    write_level1(folder / "nivel1_candidatos_20261016.csv", scenario())
    write_level2(folder / "nivel2_trades_20261016.csv", [])

    text = report.render(load_dataset(folder))

    assert "Captures: 2, rebuildable: 1" in text
    assert "Pipeline script: not found in the data folder" in text
    assert "2026-10-13  N1-E    N2-E    —" in text
    assert "Level-2 quality" in text
    assert "nivel2_trades_20261016.csv: level 2 has no trades" in text


def test_report_fails_cleanly_without_data_folder(tmp_path, capsys):
    assert report.main(["--data-dir", str(tmp_path / "no-existe")]) == 1
    assert "The data folder does not exist" in capsys.readouterr().err


def test_declared_hash_is_found_anywhere_in_the_file(tmp_path):
    canonical = hashlib.sha256(NEW_SCRIPT.read_bytes()).hexdigest()
    path = tmp_path / "instructions.md"
    assert declared_hash(path) == DeclaredHash(path, False, False)
    path.write_text(f"Expected hash:\n\n| 2026-10-21 | {canonical.upper()} |\n", encoding="utf-8")
    assert declared_hash(path) == DeclaredHash(path, True, True)
    path.write_text(f"| 2026-10-21 | {canonical[:-1]}0 |\n", encoding="utf-8")
    assert declared_hash(path) == DeclaredHash(path, True, False)


@pytest.mark.parametrize("declared, line", [
    (None, None),
    (DeclaredHash(Path("x/instructions.md"), True, True), "Declared script hash: matches (instructions.md)"),
    (DeclaredHash(Path("x/instructions.md"), True, False), "Declared script hash: DOES NOT MATCH"),
    (DeclaredHash(Path("x/instructions.md"), False, False), "Declared script hash: file not found"),
])
def test_report_shows_the_declared_hash_when_configured(declared, line, tmp_path):
    folder = tmp_path / "datos"
    folder.mkdir()
    write_capture(folder, "20261013", scenario())
    text = report.render(load_dataset(folder), declared=declared)
    if line is None:
        assert "Declared script hash" not in text
    else:
        assert line in text
