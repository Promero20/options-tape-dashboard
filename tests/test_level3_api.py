"""Funciones que el refactor de nivel3_agrupar.py expone al dashboard."""

import pytest

from pipeline import nivel3_agrupar as n3
from synthetic import scenario, write_level1, write_level2
from tape_dashboard.data.schemas import LEVEL2


@pytest.fixture
def groups():
    rows = n3.preparar_filas([dict(r) for r in scenario()], LEVEL2.variants["N2-E"])
    return n3.agrupar(rows)


def by_id(groups):
    return {n3.id_operacion(g): g for g in groups.values()}


# --- ID de operación -------------------------------------------------------

def test_ids_are_unique_even_when_the_millisecond_matches(groups):
    ids = [n3.id_operacion(g) for g in groups.values()]
    assert len(ids) == len(set(ids))
    # mismo contrato y milisegundo, distinta Trade Condition: dos operaciones
    assert "20261013-AAA-10:00:00.000-AUTO" in ids
    assert "20261013-AAA-10:00:00.000-ISOI" in ids


def test_id_uses_date_and_time_of_first_trade(groups):
    ops = by_id(groups)
    assert len(ops["20261013-BBB-11:00:00.100-MLET"]) == 3   # vertical + troceado
    assert "20261014-CCC-09:31:00.000-AUTO" in ops            # otro día de trade


# --- Cálculo por pata ------------------------------------------------------

def test_legs_of_a_vertical(groups):
    legs = n3.patas_de(by_id(groups)["20261013-BBB-11:00:00.100-MLET"])
    assert [p["contract_symbol"] for p in legs] == ["BBB|20261218|100.00C", "BBB|20261218|110.00C"]
    bought, sold = legs
    assert (bought["n_trades"], bought["size"], bought["premium"]) == (2, 2500, 1_500_000.0)
    assert bought["agr"] == pytest.approx(1.0)
    assert bought["precio_medio"] == pytest.approx(6.0)
    assert sold["agr"] == pytest.approx(-1.0)


def test_leg_without_aggressiveness():
    rows = [{"type": "put", "strike": "90.00", "exp_date": "2026-12-18",
             "size": 1000, "premium": 1_000_000.0, "agr": None, "Trade": "10.0"}]
    leg = n3.resumen_pata("BBB|20261218|90.00P", rows)
    assert leg["agr"] is None
    assert leg["precio_medio"] == pytest.approx(10.0)


def test_summary_is_consistent_with_its_legs(groups):
    for g in groups.values():
        legs = n3.patas_de(g)
        op = n3.resumen(g)
        assert op["n_patas"] == len(legs)
        assert op["premium_total"] == round(sum(p["premium"] for p in legs), 2)
        assert op["size_total"] == sum(p["size"] for p in legs)


def test_summary_of_vertical_calendar_and_incomplete(groups):
    ops = by_id(groups)
    vertical = n3.resumen(ops["20261013-BBB-11:00:00.100-MLET"])
    assert (vertical["estructura"], vertical["strike"]) == ("vertical", "100-110")
    assert (vertical["precio_neto"], vertical["precio_neto_metodo"]) == (4.0, "multi_leg_combinado")

    calendar = n3.resumen(ops["20261013-BBB-12:00:00.000-MLET"])
    assert calendar["estructura"] == "calendar/diagonal"
    assert calendar["fecha_expiracion"] == "2026-11-20→2027-01-15"

    incomplete = n3.resumen(ops["20261013-BBB-13:00:00.000-MLAT"])
    assert incomplete["patas_incompletas"] is True
    assert incomplete["precio_neto_metodo"] == "no_calculable_patas_incompletas"

    with_stock = n3.resumen(ops["20261013-CCC-10:30:00.000-TLET"])
    assert with_stock["stock_option"] is True and with_stock["patas_incompletas"] is True


def test_zero_spread_is_undetermined(groups):
    op = n3.resumen(by_id(groups)["20261013-BBB-14:00:00.000-AUTO"])
    assert (op["agresividad_pond"], op["direccion"]) == ("", "indeterminado")


# --- Umbral separado de la agrupación --------------------------------------

@pytest.mark.parametrize("premium, price, passes", [
    (499_999.99, 30, False), (500_000, 30, True), (500_000, 49.99, True),
    (999_999, 50, False), (1_000_000, 50, True),            # $50 ya es el tramo de 1 M
    (2_999_999, 200, False), (3_000_000, 200, True),        # $200 ya es el tramo de 3 M
    (2_000_000, 0.5, False),                                # < $1: el script aplica 3 M
    (1, None, True),                                        # sin precio no se descarta
])
def test_threshold(premium, price, passes):
    assert n3.pasa_umbral(premium, price) is passes


def test_pieces_are_equivalent_to_main(tmp_path):
    trades = scenario()
    level2, level1 = tmp_path / "n2.csv", tmp_path / "n1.csv"
    write_level2(level2, trades)
    write_level1(level1, trades)

    rows, all_ops, ops, discarded, cancellations = n3.main(str(level2), str(level1), str(tmp_path / "n3.csv"))

    rows_2, cancellations_2 = n3.quitar_cancelaciones(n3.cargar(str(level2)))
    assert len(rows_2) == len(rows) and len(cancellations_2) == len(cancellations) == 2
    all_ops_2 = n3.resumir_todas(n3.agrupar(rows_2))
    ops_2, discarded_2 = n3.filtrar_por_umbral(all_ops_2, n3.cargar_precios(str(level1)))
    assert (all_ops_2, ops_2, discarded_2) == (all_ops, ops, discarded)
    assert len(ops) + discarded == len(all_ops)
    assert any(o["symbol"] == "DDD" for o in ops)   # sin precio: se conserva


# --- Cancelaciones ---------------------------------------------------------

def test_cancellation_removes_the_trade_it_cancels():
    rows = n3.preparar_filas([dict(r) for r in scenario()], LEVEL2.variants["N2-E"])
    kept, pairs = n3.quitar_cancelaciones(rows)

    assert len(pairs) == 2
    (matched_cancel, cancelled), (unmatched_cancel, nothing) = pairs
    # anula el trade anterior del mismo contrato, precio y tamaño
    assert (cancelled["Time"], cancelled["size"], cancelled["Trade Condition"]) ==         ("2026-10-13 11:00:00.000", 10, "AUTO")
    # sin trade que cuadre: la cancelación se quita igualmente
    assert unmatched_cancel["size"] == 13 and nothing is None
    assert len(kept) == len(rows) - 3
    assert not any(r["Trade Condition"] == "CANC" for r in kept)


def test_cancellation_picks_the_latest_matching_trade_before_it():
    def row(time, condition, size=10, price="1.0"):
        return {"contract_symbol": "X|20261120|10.00C", "Trade Condition": condition, "size": size,
                "Trade": price, "t": __import__("datetime").datetime.fromisoformat(f"2026-10-13 {time}")}
    earlier, latest, after = row("10:00:00", "AUTO"), row("10:05:00", "AUTO"), row("10:20:00", "AUTO")
    other_size, cancel = row("10:06:00", "AUTO", size=11), row("10:10:00", "CANC")
    kept, pairs = n3.quitar_cancelaciones([earlier, latest, other_size, cancel, after])
    assert pairs == [(cancel, latest)]
    assert kept == [earlier, other_size, after]


def test_no_cancellations_leaves_rows_untouched():
    rows = [dict(r) for r in scenario() if r["Trade Condition"] != "CANC"]
    rows = n3.preparar_filas(rows, LEVEL2.variants["N2-E"])
    kept, pairs = n3.quitar_cancelaciones(rows)
    assert kept is rows and pairs == []


# --- Carga -----------------------------------------------------------------

def test_load_skips_footer_and_rows_without_time(tmp_path):
    trades = scenario()
    level2 = tmp_path / "n2.csv"
    write_level2(level2, trades, variant="N2-A")
    assert len(n3.cargar(str(level2))) == len(trades)


def test_load_api_variant_uses_condition_code(tmp_path):
    level2 = tmp_path / "n2.csv"
    write_level2(level2, scenario(), variant="N2-B")
    conditions = {r["Trade Condition"] for r in n3.cargar(str(level2))}
    # tradeConditionCode (código corto), no tradeCondition (texto largo)
    assert conditions <= {"AUTO", "ISOI", "SLAN", "MLET", "MLAT", "TLET", "CANC"}


def test_level2_without_trades_gives_clear_error(tmp_path):
    level2, level1 = tmp_path / "n2.csv", tmp_path / "n1.csv"
    write_level2(level2, [])
    write_level1(level1, [])
    with pytest.raises(ValueError, match="no tiene ningún trade"):
        n3.main(str(level2), str(level1), str(tmp_path / "n3.csv"))
    assert not (tmp_path / "n3.csv").exists()


def test_level2_without_header_gives_clear_error(tmp_path):
    level2 = tmp_path / "n2.csv"
    level2.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="no tiene las columnas esperadas"):
        n3.cargar(str(level2))
