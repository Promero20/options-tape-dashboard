"""Indicadores de calidad del nivel 2 e informe por consola."""

import pytest

from synthetic import scenario, write_capture, write_level1, write_level2
from tape_dashboard import report
from tape_dashboard.data.dataset import load_dataset
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

    assert "Capturas: 2, reconstruibles: 1" in text
    assert "Script del pipeline: no está en la carpeta de datos" in text
    assert "2026-10-13  N1-E    N2-E    —" in text
    assert "Calidad del nivel 2" in text
    assert "nivel2_trades_20261016.csv: nivel 2 sin trades" in text


def test_report_fails_cleanly_without_data_folder(tmp_path, capsys):
    assert report.main(["--data-dir", str(tmp_path / "no-existe")]) == 1
    assert "No existe la carpeta de datos" in capsys.readouterr().err
