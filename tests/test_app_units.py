"""Pure pieces of the application: ranges, grid rows, editing rules and warnings."""

import shutil
from datetime import date

import pytest

from helpers import NEW_SCRIPT
from tape_dashboard.app.state import AppState
from tape_dashboard.app.tabs.operations import editing
from tape_dashboard.app.tabs.operations.ranges import CUSTOM, MONTH, TODAY, WEEK, resolve_range
from tape_dashboard.app.tabs.operations.rows import (ANOMALOUS, EDITED, column_defs, destination_counts,
                                                     leg_rows, operation_row)
from tape_dashboard.app.warnings import collect
from tape_dashboard.config import Settings
from tape_dashboard.data.dataset import load_dataset
from tape_dashboard.edits.apply import apply_edits
from tape_dashboard.edits.store import EditStore, Edits, ManualLeg
from tape_dashboard.rules import classification as c
from tape_dashboard.rules.classification import Override

D13, D15 = date(2026, 10, 13), date(2026, 10, 15)
SINGLE = "20261013-AAA-10:00:00.000-AUTO"
VERTICAL = "20261013-BBB-11:00:00.100-MLET"
BUTTERFLY = "20261013-CCC-15:00:00.000-MLET"
WITH_STOCK = "20261013-CCC-10:30:00.000-TLET"
INCOMPLETE = "20261013-BBB-13:00:00.000-MLAT"


@pytest.fixture
def dataset(synthetic_folder):
    return load_dataset(synthetic_folder)


def classified(dataset, op_id, edits=Edits.empty()):
    op = next(o for o in dataset.captures[D13].operations if o.id == op_id)
    return apply_edits([op], edits)[0]


# --- ranges ---------------------------------------------------------------------

def test_today_is_todays_capture(dataset):
    r = resolve_range(dataset, TODAY, D15)
    assert (r.start, r.end, r.note) == (D15, D15, "")


def test_today_falls_back_to_the_latest_capture_with_a_note(dataset):
    r = resolve_range(dataset, TODAY, date(2026, 10, 14))
    assert (r.start, r.end) == (D13, D13)
    assert "No capture for today (2026-10-14)" in r.note


def test_today_without_captures(dataset):
    r = resolve_range(dataset, TODAY, date(2026, 10, 1))
    assert r.empty and r.note


@pytest.mark.parametrize("preset, start", [(WEEK, date(2026, 10, 9)), (MONTH, date(2026, 9, 16))])
def test_week_and_month_are_calendar_days_up_to_today(dataset, preset, start):
    r = resolve_range(dataset, preset, D15)
    assert (r.start, r.end) == (start, D15)


def test_custom_range_accepts_either_order_and_needs_both_dates(dataset):
    r = resolve_range(dataset, CUSTOM, D15, "2026-10-15", "2026-10-13T00:00:00")
    assert (r.start, r.end) == (D13, D15)
    assert resolve_range(dataset, CUSTOM, D15, "2026-10-13", None).empty


def test_unknown_preset_is_an_error(dataset):
    with pytest.raises(ValueError):
        resolve_range(dataset, "yesterday", D15)


# --- rows --------------------------------------------------------------------------

def test_operation_row(dataset):
    row = operation_row(classified(dataset, SINGLE))
    assert (row["id"], row["capture"], row["symbol"]) == (SINGLE, "2026-10-13", "AAA")
    assert (row["destination"], row["direction"], row["structure"]) == (c.NET, c.BULL, "single-leg call")
    assert row["premium_m"] == 0.702
    assert row["flags"] == "" and not row["edited"]
    assert row["script_direction"] == "bull"


def test_flags_for_edited_and_anomalous_operations(dataset):
    edited = classified(dataset, SINGLE, Edits({SINGLE: Override(direction=c.BEAR)}, {}))
    row = operation_row(edited)
    assert EDITED in row["flags"] and row["edited"]
    assert (row["destination"], row["wall"]) == (c.WALLS, c.RESISTANCE)

    butterfly = classified(dataset, BUTTERFLY)
    assert ANOMALOUS not in operation_row(butterfly)["flags"]   # 1000/2000/1000: ratio 2


def test_destination_counts_skip_pending(dataset):
    items = apply_edits(dataset.captures[D13].operations, Edits.empty())
    counts = destination_counts([i for i in items if i.classification.destination != c.PENDING])
    assert c.PENDING not in counts
    assert counts[c.NET] >= 1 and counts[c.DISCARDED] >= 1


def test_leg_rows_mark_manual_legs_and_sides(dataset):
    edits = Edits({INCOMPLETE: Override(strategy="bull_call")},
                  {INCOMPLETE: [ManualLeg(1, INCOMPLETE, "call", 130.0, "2026-12-18", 1.5, 3000)]})
    rows = leg_rows(classified(dataset, INCOMPLETE, edits))
    assert [(r["manual"], r["side_used"]) for r in rows] == [(False, "buy"), (True, "sell")]
    assert rows[1]["aggressiveness"] is None and rows[1]["measured_side"] == "undetermined"


def test_optional_columns_are_hidden_until_requested():
    hidden = {col["field"]: col.get("hide", False) for col in column_defs()}
    assert hidden["id"] and hidden["script_direction"] and not hidden["symbol"]
    shown = {col["field"]: col.get("hide", False) for col in column_defs(["id"])}
    assert not shown["id"] and shown["script_direction"]


# --- editing -------------------------------------------------------------------------

def test_single_leg_is_corrected_with_a_direction(dataset):
    editor = editing.editor_for(classified(dataset, SINGLE))
    assert editor.kind == editing.DIRECTION
    assert [value for value, _ in editor.options] == [c.BULL, c.BEAR, c.UNDETERMINED]


def test_two_legs_are_corrected_with_an_operation_type(dataset):
    editor = editing.editor_for(classified(dataset, VERTICAL, Edits({VERTICAL: Override(strategy="bear_call")}, {})))
    assert editor.kind == editing.STRATEGY
    assert [value for value, _ in editor.options] == ["bull_call", "bear_call", "unknown"]
    assert editor.current == "bear_call"


@pytest.mark.parametrize("op_id", [BUTTERFLY, WITH_STOCK])
def test_three_legs_and_stock_are_read_only(dataset, op_id):
    editor = editing.editor_for(classified(dataset, op_id))
    assert editor.kind == editing.READ_ONLY and editor.reason


def test_save_and_clear(tmp_path):
    store = EditStore(tmp_path / "edits.sqlite")
    editing.save(store, "A", editing.DIRECTION, c.BEAR)
    editing.save(store, "B", editing.STRATEGY, "bull_call")
    editing.save(store, "B", editing.STRATEGY, None)
    assert store.snapshot().overrides == {"A": Override(direction=c.BEAR)}
    with pytest.raises(ValueError):
        editing.save(store, "C", editing.READ_ONLY, "bull")


# --- warnings ------------------------------------------------------------------------

def notices(settings):
    return [(n.level, n.text) for n in collect(AppState(settings))]


def test_missing_data_folder_is_an_error(tmp_path):
    found = notices(Settings(data_dir=tmp_path / "nope", user_data_dir=tmp_path / "user"))
    assert found[0][0] == "error" and "does not exist" in found[0][1]


def test_dataset_issues_are_shown(synthetic_settings):
    texts = [text for _, text in notices(synthetic_settings)]
    assert any("nivel2_trades_20261016.csv: level 2 has no trades" in t for t in texts)
    assert any("level-3 script is not in the data folder" in t for t in texts)


def test_deployed_script_is_compared_with_the_canonical_one(synthetic_settings):
    script = synthetic_settings.data_dir / "nivel3_agrupar.py"
    script.write_text("# another version\n", encoding="utf-8")
    assert any("differs from pipeline/nivel3_agrupar.py" in t for _, t in notices(synthetic_settings))
    shutil.copyfile(NEW_SCRIPT, script)
    assert not any("level-3 script" in t for _, t in notices(synthetic_settings))


def test_declared_hash(synthetic_settings, tmp_path):
    import hashlib
    canonical = hashlib.sha256(NEW_SCRIPT.read_bytes()).hexdigest()
    declaration = tmp_path / "instructions.md"
    settings = Settings(synthetic_settings.data_dir, synthetic_settings.user_data_dir, declaration)

    assert any("declared script hash was not found" in t for _, t in notices(settings))
    declaration.write_text(f"| current | `{'0' * 64}` |\n", encoding="utf-8")
    assert any("does not match" in t for _, t in notices(settings))
    declaration.write_text(f"| current | `{canonical.upper()}` |\n", encoding="utf-8")
    assert not any("declared" in t for _, t in notices(settings))


def test_orphan_edits_are_shown(synthetic_settings):
    EditStore(synthetic_settings.user_data_dir / "edits.sqlite").set_direction(
        "20261013-ZZZ-10:00:00.000-AUTO", c.BULL)
    assert any(t.startswith("Orphan correction on 20261013-ZZZ") for _, t in notices(synthetic_settings))
