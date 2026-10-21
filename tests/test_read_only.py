"""
La carpeta de datos del pipeline es de solo lectura (especificación):
procesar todos sus días no debe crear, modificar ni borrar nada en ella,
tampoco un __pycache__.
"""

import pytest

from helpers import days_with_level2, snapshot
from pipeline import nivel3_agrupar as n3


@pytest.mark.real_data
def test_processing_every_day_leaves_data_folder_untouched(data_dir, tmp_path):
    before = snapshot(data_dir)
    for day in days_with_level2():
        n3.main(str(data_dir / f"nivel2_trades_{day}.csv"),
                str(data_dir / f"nivel1_candidatos_{day}.csv"),
                str(tmp_path / f"nivel3_operaciones_{day}.csv"))
    assert snapshot(data_dir) == before
    assert not list(data_dir.rglob("__pycache__"))
