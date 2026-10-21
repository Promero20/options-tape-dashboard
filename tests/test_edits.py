"""Almacén de ediciones, patas manuales, aplicación sobre los datos y ediciones huérfanas."""

from datetime import date

import pytest

from synthetic import scenario, trade, write_capture
from tape_dashboard.data.dataset import load_dataset
from tape_dashboard.edits.apply import (apply_edits, classified_operations, orphans, pending_operations,
                                        with_manual_legs)
from tape_dashboard.edits.store import EditStore, Edits, ManualLeg, read_edits
from tape_dashboard.rules import classification as c
from tape_dashboard.rules.classification import DESTINATIONS, Override

D13 = date(2026, 10, 13)
INCOMPLETE = "20261013-BBB-13:00:00.000-MLAT"     # call 120 MLAT, una sola pata
WITH_STOCK = "20261013-CCC-10:30:00.000-TLET"     # opción + acciones, incompleta
SINGLE = "20261013-AAA-10:00:00.000-AUTO"         # call comprada troceada


@pytest.fixture
def store(tmp_path):
    return EditStore(tmp_path / "usuario" / "ediciones.sqlite")


@pytest.fixture
def dataset(tmp_path):
    folder = tmp_path / "datos"
    folder.mkdir()
    write_capture(folder, "20261013", scenario())
    return load_dataset(folder)


def operation(dataset, op_id):
    return next(op for op in dataset.captures[D13].operations if op.id == op_id)


# --- Almacén --------------------------------------------------------------------

def test_overrides_round_trip(store):
    store.set_direction("A", c.BULL)
    store.set_strategy("B", "bull_call")
    store.set_strategy("A", "no_lo_se")          # sustituye a la dirección
    store.set_direction("C", c.BEAR)
    store.clear_override("C")
    assert store.snapshot().overrides == {"A": Override(strategy="no_lo_se"),
                                          "B": Override(strategy="bull_call")}


def test_manual_legs_round_trip(store):
    first = store.add_manual_leg("A", "call", 130, "2026-12-18", 1.5, 3000)
    second = store.add_manual_leg("A", "put", 90, "2026-12-18", 2.0, 100)
    store.update_manual_leg(first, "call", 125, "2026-12-18", 1.8, 3000)
    store.delete_manual_leg(second)
    assert store.snapshot().manual_legs == {"A": [ManualLeg(first, "A", "call", 125.0, "2026-12-18", 1.8, 3000)]}


@pytest.mark.parametrize("call", [
    lambda s: s.set_direction("A", "alcista"),
    lambda s: s.set_strategy("A", "iron_condor"),
    lambda s: s.add_manual_leg("A", "Call", 100, "2026-12-18", 1, 10),
    lambda s: s.add_manual_leg("A", "call", 100, "18/12/2026", 1, 10),
    lambda s: s.add_manual_leg("A", "call", 100, "2026-12-18", 1, 0),
    lambda s: s.add_manual_leg("A", "call", -5, "2026-12-18", 1, 10),
])
def test_invalid_edits_are_rejected(store, call):
    with pytest.raises(ValueError):
        call(store)


def test_reading_edits_never_creates_the_file(tmp_path, store):
    missing = tmp_path / "no-existe" / "ediciones.sqlite"
    assert read_edits(missing) == Edits.empty()
    assert not missing.parent.exists()
    store.set_direction("A", c.BULL)
    assert read_edits(store.path).overrides == {"A": Override(direction=c.BULL)}


# --- Patas manuales ----------------------------------------------------------------

def test_manual_leg_completes_the_operation_with_the_script(dataset):
    op = operation(dataset, INCOMPLETE)
    leg = ManualLeg(1, op.id, "call", 130.0, "2026-12-18", 1.5, 3000)
    completed = with_manual_legs(op, [leg])

    assert completed.id == op.id
    assert completed.summary["n_patas"] == 2
    assert completed.summary["patas_incompletas"] is False
    assert completed.summary["estructura"] == "vertical"
    assert completed.premium == op.premium + 450_000
    # la pata manual no tiene agresividad: la media es la de la pata real
    assert completed.summary["agresividad_pond"] == op.summary["agresividad_pond"]
    assert op.summary["n_patas"] == 1          # la operación original no cambia

    r = c.classify(completed, Override(strategy="bull_call"))
    assert (r.destination, r.direction, r.strike) == (c.NET, c.BULL, 120.0)
    assert r.premium == pytest.approx(1_200_000 - 450_000)


def test_manual_leg_follows_the_capitalisation_of_the_file(tmp_path):
    # capturas antiguas escriben 'Call'; si la pata manual dijera 'call', el
    # script vería dos tipos distintos y la tomaría por un straddle
    folder = tmp_path / "datos"
    folder.mkdir()
    write_capture(folder, "20261013", [dict(t, type=t["type"].capitalize()) for t in scenario()])
    op = operation(load_dataset(folder), INCOMPLETE)
    completed = with_manual_legs(op, [ManualLeg(1, op.id, "call", 130.0, "2026-12-18", 1.5, 3000)])
    assert completed.summary["estructura"] == "vertical"


def test_manual_leg_repeating_a_contract_is_reported_not_applied(dataset):
    op = operation(dataset, INCOMPLETE)
    edits = Edits({}, {op.id: [ManualLeg(1, op.id, "call", 120.0, "2026-12-18", 1.5, 3000)]})
    [result] = apply_edits([op], edits)
    assert result.operation is op and result.manual_legs == ()
    assert "repite el contrato" in result.problems[0]


# --- Pestañas ------------------------------------------------------------------------

def test_tab2_lists_incomplete_operations_above_the_threshold(dataset):
    pending = {x.operation.id for x in pending_operations(dataset, Edits.empty(), D13)}
    assert INCOMPLETE in pending
    assert WITH_STOCK not in pending                 # con acciones: descartada (decisión 0016)
    assert all(x.operation.passes_threshold for x in pending_operations(dataset, Edits.empty(), D13))


def test_completed_operation_moves_from_tab2_to_tab1(dataset):
    edits = Edits({INCOMPLETE: Override(strategy="bull_call")},
                  {INCOMPLETE: [ManualLeg(1, INCOMPLETE, "call", 130.0, "2026-12-18", 1.5, 3000)]})
    assert INCOMPLETE not in {x.operation.id for x in pending_operations(dataset, edits, D13)}
    tab1 = {x.operation.id: x for x in classified_operations(dataset, edits, D13, D13)}
    assert tab1[INCOMPLETE].classification.destination == c.NET
    assert tab1[INCOMPLETE].edited

    # al borrar la pata, vuelve a la pestaña 2
    edits_without_leg = Edits(edits.overrides, {})
    assert INCOMPLETE in {x.operation.id for x in pending_operations(dataset, edits_without_leg, D13)}


def test_tab1_excludes_pending_and_below_threshold(dataset):
    tab1 = classified_operations(dataset, Edits.empty(), D13, D13)
    assert tab1
    assert all(x.operation.passes_threshold for x in tab1)
    assert all(x.classification.destination != c.PENDING for x in tab1)


def test_direction_override_changes_the_destination(dataset):
    edits = Edits({SINGLE: Override(direction=c.BEAR)}, {})   # bear sobre una call: vendida
    tab1 = {x.operation.id: x for x in classified_operations(dataset, edits, D13, D13)}
    assert tab1[SINGLE].classification.destination == c.WALLS
    assert tab1[SINGLE].classification.wall == c.RESISTANCE


def test_every_operation_goes_to_exactly_one_destination(dataset):
    classified = apply_edits(dataset.captures[D13].operations, Edits.empty())
    by_destination = {d: 0.0 for d in DESTINATIONS}
    for x in classified:
        by_destination[x.classification.destination] += x.operation.premium
    total = sum(op.premium for op in dataset.captures[D13].operations)
    assert sum(by_destination.values()) == pytest.approx(total)


# --- Huérfanas -------------------------------------------------------------------------

def test_edits_for_missing_operations_are_orphans_and_kept(dataset, store):
    store.set_direction(SINGLE, c.BEAR)
    store.set_direction("20261013-ZZZ-10:00:00.000-AUTO", c.BULL)
    store.add_manual_leg("20261013-ZZZ-11:00:00.000-MLET", "put", 50, "2026-12-18", 2, 100)
    found = orphans(dataset, store.snapshot())
    assert [(o.kind, o.operation_id) for o in found] == [
        ("corrección", "20261013-ZZZ-10:00:00.000-AUTO"),
        ("pata manual", "20261013-ZZZ-11:00:00.000-MLET"),
    ]
    assert len(store.snapshot().overrides) == 2     # nada se borra
