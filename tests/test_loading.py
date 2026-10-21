"""Lectura y normalización de cada variante de nivel 1 y nivel 2."""

import csv

import pytest

from synthetic import (CONDITION_TEXT, LEVEL1_VARIANTS, LEVEL2_VARIANTS, PRICES, level1_rows,
                       scenario, write_level1, write_level2)
from tape_dashboard.data import schemas
from tape_dashboard.data.issues import WARNING
from tape_dashboard.data.loading import SchemaError, build_contract_symbol, load_level1, load_level2


def warnings(data):
    return [i.message for i in data.issues if i.severity == WARNING]


# --- Nivel 1 -----------------------------------------------------------------

@pytest.mark.parametrize("variant", LEVEL1_VARIANTS)
def test_level1_variants_normalise_to_the_same_rows(variant, tmp_path):
    trades = scenario()
    path = tmp_path / "n1.csv"
    write_level1(path, trades, variant)

    data = load_level1(path)

    assert data.variant == variant
    assert data.contract_rebuilt is (variant == "N1-B")
    assert [r["contract_symbol"] for r in data.rows] == [r["contract_symbol"] for r in level1_rows(trades)]
    assert data.prices == PRICES
    first = data.rows[0]
    assert first["type"] in ("call", "put")
    assert first["open_interest"] == 5000
    assert first["last_trade"] == (None if variant == "N1-D" else "2026-10-12")
    assert warnings(data) == []


def test_level1_reconciliation_fields(tmp_path):
    path = tmp_path / "n1.csv"
    write_level1(path, scenario())
    rows = {r["contract_symbol"]: r for r in load_level1(path).rows}

    selected = rows["BBB|20261218|100.00C"]
    assert selected["fecha_volumen"] == ["2026-10-13"]
    assert (selected["reconciliacion_fallida"], selected["reconciliacion_ambigua"]) == (False, False)

    not_selected = rows["AAA|20261218|40.00C"]
    assert not_selected["fecha_volumen"] == []
    assert not_selected["reconciliacion_fallida"] is None

    # varias fechas separadas por ';' y desordenadas
    assert rows["AAA|20261218|45.00C"]["fecha_volumen"] == ["2026-10-12", "2026-10-13"]


def test_rebuilt_contract_matches_the_contract_format():
    assert build_contract_symbol("AAPL", "2026-11-20", 250.0, "call") == "AAPL|20261120|250.00C"
    assert build_contract_symbol("BRK.B", "2027-01-15", 7.5, "put") == "BRK.B|20270115|7.50P"


def test_level1_without_a_required_column_is_reported(tmp_path):
    path = tmp_path / "n1.csv"
    header = [c for c in schemas.LEVEL1.variants["N1-E"] if c != "price"]
    write_level1(path, scenario(), header=header)
    with pytest.raises(SchemaError) as error:
        load_level1(path)
    assert error.value.file == "n1.csv"
    assert error.value.missing == ["price"]
    assert "price" in str(error.value)


def test_level1_new_variant_is_loaded_with_a_warning(tmp_path):
    path = tmp_path / "n1.csv"
    write_level1(path, scenario(), header=list(schemas.LEVEL1.variants["N1-E"]) + ["columna_nueva"])
    data = load_level1(path)
    assert data.variant is None
    assert data.rows
    assert any("variante de encabezado nueva" in w and "columna_nueva" in w for w in warnings(data))


def test_unparseable_values_are_counted_not_hidden(tmp_path):
    path = tmp_path / "n1.csv"
    write_level1(path, scenario())
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header, rows = reader.fieldnames, list(reader)
    rows[0]["iv"] = rows[1]["iv"] = "n/a"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)

    data = load_level1(path)
    assert data.rows[0]["iv"] is None
    assert "2 valores no interpretables en 'iv'" in warnings(data)


# --- Nivel 2 -----------------------------------------------------------------

@pytest.mark.parametrize("variant", LEVEL2_VARIANTS)
def test_level2_variants_load_with_canonical_names(variant, tmp_path):
    trades = scenario()
    path = tmp_path / "n2.csv"
    write_level2(path, trades, variant)

    data = load_level2(path)

    assert data.variant == variant
    required = [c.name for c in schemas.LEVEL2.columns if c.required]
    assert set(required) <= set(data.fieldnames)
    real = [r for r in data.rows if r["Time"]]
    assert len(real) == len(trades)
    assert {r["Trade Condition"] for r in real} <= set(CONDITION_TEXT)
    assert {r["fecha_consultada"] for r in real} == {"2026-10-13", "2026-10-14"}
    assert "I" in {r["Exchange"] for r in real}          # 'I\r' recortado
    assert warnings(data) == []


def test_level2_without_a_required_column_is_reported(tmp_path):
    path = tmp_path / "n2.csv"
    write_level2(path, scenario(), header=[c for c in schemas.LEVEL2.variants["N2-E"] if c != "agresividad"])
    with pytest.raises(SchemaError) as error:
        load_level2(path)
    assert error.value.missing == ["agresividad"]
