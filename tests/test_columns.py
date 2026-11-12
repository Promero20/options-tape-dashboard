"""Columns of the operations list: catalogue, saved layout, preferences file and the pop-up (decision 0035)."""

import json
from datetime import date

import pytest
from dash import no_update

from tape_dashboard.app.preferences import Preferences
from tape_dashboard.app.state import AppState
from tape_dashboard.app.tabs.operations import callbacks as cb
from tape_dashboard.app.tabs.operations import view
from tape_dashboard.app.tabs.operations.rows import (COLUMN_DEFS, COLUMN_GROUPS, column_defs, factory_layout,
                                                     layout_from_state, operation_rows, visible_by_group,
                                                     with_visibility)
from tape_dashboard.app.warnings import collect
from tape_dashboard.data.dataset import load_dataset
from tape_dashboard.edits.apply import apply_edits
from tape_dashboard.edits.store import Edits, ManualLeg
from tape_dashboard.rules.classification import Override

D13 = date(2026, 10, 13)
SINGLE = "20261013-AAA-10:00:00.000-AUTO"       # one leg, 1,400 contracts
VERTICAL = "20261013-BBB-11:00:00.100-MLET"     # two legs, 4,500 contracts
INCOMPLETE = "20261013-BBB-13:00:00.000-MLAT"


def fields(defs):
    return [d["field"] for d in defs]


def hidden(defs):
    return {d["field"] for d in defs if d.get("hide")}


# --- catalogue and layouts -----------------------------------------------------------------------

def test_every_column_but_symbol_is_in_one_group():
    grouped = [field for _, group in COLUMN_GROUPS for field in group]
    assert sorted(grouped) == sorted(f for f in fields(COLUMN_DEFS) if f != "symbol")
    assert len(grouped) == len(set(grouped))


def test_a_layout_sets_order_visibility_and_widths():
    layout = [{"colId": "premium_m", "hide": False, "width": 130}, {"colId": "symbol", "hide": False},
              {"colId": "structure", "hide": True}, {"colId": "capture", "hide": False}]
    defs = column_defs(layout)
    assert fields(defs)[:4] == ["symbol", "premium_m", "structure", "capture"]
    assert defs[1]["width"] == 130 and "structure" in hidden(defs) and "capture" not in hidden(defs)


def test_columns_a_layout_does_not_know_are_appended_hidden_and_unknown_ones_ignored():
    defs = column_defs([{"colId": "capture", "hide": False}, {"colId": "open_interest", "hide": False}, 7])
    assert "open_interest" not in fields(defs)
    assert sorted(fields(defs)) == sorted(fields(COLUMN_DEFS))
    assert hidden(defs) == set(fields(COLUMN_DEFS)) - {"symbol", "capture"}


def test_symbol_is_always_first_and_shown():
    defs = column_defs([{"colId": "capture", "hide": False}, {"colId": "symbol", "hide": True}])
    assert defs[0]["field"] == "symbol" and not defs[0].get("hide")


def test_the_grid_state_is_reduced_to_a_layout():
    state = [{"colId": "capture", "hide": False, "width": 111.6, "sort": None, "pinned": None},
             {"colId": "ag-Grid-SelectionColumn", "hide": False}, {"colId": "capture", "hide": True},
             {"colId": "symbol", "hide": False, "width": 0}]
    assert layout_from_state(state) == [{"colId": "capture", "hide": False, "width": 111},
                                        {"colId": "symbol", "hide": False}]
    assert layout_from_state(None) == []


def test_visibility_and_ticks():
    layout = with_visibility(factory_layout(), {"capture", "contract_volume", "id"})
    shown = {e["colId"] for e in layout if not e["hide"]}
    assert shown == {"symbol", "capture", "contract_volume", "id"}
    assert visible_by_group(layout) == [["capture"], ["contract_volume"], ["id"]]


# --- new row fields ---------------------------------------------------------------------------------

@pytest.fixture
def dataset(synthetic_folder):
    return load_dataset(synthetic_folder)


def rows_by_id(dataset, edits=Edits.empty()):
    return {r["id"]: r for r in operation_rows(apply_edits(dataset.captures[D13].operations, edits), dataset)}


def test_size_trades_duration_and_volume(dataset):
    rows = rows_by_id(dataset)
    single, vertical = rows[SINGLE], rows[VERTICAL]
    assert (single["legs"], single["trades"], single["size"]) == (1, 3, 1400)
    assert single["duration_s"] == 150.0
    assert (single["contract_volume"], single["volume_share"]) == (1000, 140.0)    # invented level-1 volume
    assert (vertical["legs"], vertical["size"], vertical["contract_volume"]) == (2, 4500, 2000)  # added up


def test_a_manual_leg_leaves_the_volume_empty(dataset):
    edits = Edits({INCOMPLETE: Override(strategy="bull_call")},
                  {INCOMPLETE: [ManualLeg(1, INCOMPLETE, "call", 130.0, "2026-12-18", 1.5, 3000)]})
    row = rows_by_id(dataset, edits)[INCOMPLETE]
    assert row["legs"] == 2 and row["contract_volume"] is None and row["volume_share"] is None


def test_without_the_dataset_there_is_no_volume(dataset):
    (row, *_) = operation_rows(apply_edits(dataset.captures[D13].operations, Edits.empty()))
    assert row["contract_volume"] is None


# --- preferences file ---------------------------------------------------------------------------------

def test_no_file_means_factory_columns(tmp_path):
    preferences = Preferences(tmp_path / "preferences.json")
    assert preferences.operations_columns() is None and preferences.problem() is None


def test_saving_writes_the_file_atomically_and_keeps_other_settings(tmp_path):
    path = tmp_path / "user" / "preferences.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"something_else": 1}), encoding="utf-8")
    layout = [{"colId": "symbol", "hide": False}, {"colId": "capture", "hide": True}]
    Preferences(path).save_operations_columns(layout)
    assert json.loads(path.read_text(encoding="utf-8")) == {"something_else": 1, "operations_columns": layout}
    assert Preferences(path).operations_columns() == layout
    assert [p.name for p in path.parent.iterdir()] == ["preferences.json"]           # no temporary file left


@pytest.mark.parametrize("content, message", [
    ("{not json", "cannot be read"),
    ("[1, 2]", "is not a JSON object"),
    ('{"operations_columns": "all of them"}', "is not valid"),
])
def test_an_unreadable_file_gives_factory_columns_and_a_warning(tmp_path, content, message):
    path = tmp_path / "preferences.json"
    path.write_text(content, encoding="utf-8")
    preferences = Preferences(path)
    assert preferences.operations_columns() is None and message in preferences.problem()
    assert path.read_text(encoding="utf-8") == content                               # left as it is


def test_saving_over_an_unreadable_file_keeps_a_copy(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text("{not json", encoding="utf-8")
    Preferences(path).save_operations_columns([{"colId": "symbol", "hide": False}])
    assert (tmp_path / "preferences.json.unreadable").read_text(encoding="utf-8") == "{not json"
    assert Preferences(path).problem() is None


def test_the_banner_reports_an_unreadable_file(synthetic_settings):
    synthetic_settings.user_data_dir.mkdir(parents=True, exist_ok=True)
    (synthetic_settings.user_data_dir / "preferences.json").write_text("{not json", encoding="utf-8")
    assert any("preferences.json cannot be read" in n.text for n in collect(AppState(synthetic_settings)))


# --- the pop-up --------------------------------------------------------------------------------------

def field_of(result, name):
    return result[[n for n, _ in cb.COLUMNS_FIELDS].index(name)]


def act(app, trigger, groups=(None, None, None), column_state=None):
    return cb.columns_action(app.tape_state, trigger, list(groups), column_state)


def dragged_state():
    """A grid whose user dragged Capture to the front and widened it."""
    order = ["capture"] + [f for f in fields(COLUMN_DEFS) if f != "capture"]
    factory = {e["colId"]: e["hide"] for e in factory_layout()}
    return [{"colId": f, "hide": factory[f], "width": 150 if f == "capture" else 100} for f in order]


def test_opening_ticks_the_visible_columns(app):
    result = act(app, view.COLUMNS_BUTTON)
    assert field_of(result, "style") == view.SHOWN
    operation, volume, technical = (field_of(result, f"group{i}") for i in range(3))
    assert "premium_m" in operation and "legs" not in operation and volume == [] and technical == []


def test_ticking_applies_at_once_and_keeps_the_dragged_order(app):
    result = act(app, view.COLUMN_GROUP_IDS[1], groups=(["capture", "premium_m"], ["contract_volume"], []),
                 column_state=dragged_state())
    defs = field_of(result, "defs")
    assert fields(defs)[:2] == ["symbol", "capture"] and defs[1]["width"] == 150
    assert set(fields(defs)) - hidden(defs) == {"symbol", "capture", "premium_m", "contract_volume"}
    assert field_of(result, "group0") is no_update                 # the boxes are already as the user left them


def test_all_and_none(app):
    everything = field_of(act(app, view.COLUMNS_ALL, column_state=dragged_state()), "defs")
    assert hidden(everything) == set()
    nothing = act(app, view.COLUMNS_NONE, column_state=dragged_state())
    assert set(fields(field_of(nothing, "defs"))) - hidden(field_of(nothing, "defs")) == {"symbol"}
    assert [field_of(nothing, f"group{i}") for i in range(3)] == [[], [], []]


def test_save_restore_and_factory(app):
    state = with_visibility(layout_from_state(dragged_state()), {"capture", "contract_volume"})
    saved = act(app, view.COLUMNS_SAVE, column_state=state)
    assert field_of(saved, "message") == f"Saved as default: 3 of {len(COLUMN_DEFS)} columns shown."
    assert app.tape_state.preferences.operations_columns()[0]["colId"] == "capture"

    factory = act(app, view.COLUMNS_FACTORY, column_state=state)
    assert fields(field_of(factory, "defs")) == fields(COLUMN_DEFS) and field_of(factory, "size") == "autoSize"

    restored = act(app, view.COLUMNS_RESTORE)
    defs = field_of(restored, "defs")
    assert fields(defs)[:2] == ["symbol", "capture"] and defs[1]["width"] == 150
    assert set(fields(defs)) - hidden(defs) == {"symbol", "capture", "contract_volume"}
    assert field_of(restored, "size") is None and field_of(restored, "group1") == ["contract_volume"]


def test_restore_without_a_saved_default(app):
    result = act(app, view.COLUMNS_RESTORE)
    assert "no saved default yet" in field_of(result, "message")
    assert fields(field_of(result, "defs")) == fields(COLUMN_DEFS)


def test_closing(app):
    assert field_of(act(app, view.COLUMNS_CLOSE), "style") == view.HIDDEN


def test_the_page_opens_with_the_saved_layout(app):
    app.tape_state.preferences.save_operations_columns([{"colId": "capture", "hide": False, "width": 150}])
    grid = _find(view.layout(app.tape_state), view.GRID)
    assert fields(grid.columnDefs)[:2] == ["symbol", "capture"] and grid.columnSize is None
    assert hidden(grid.columnDefs) == set(fields(COLUMN_DEFS)) - {"symbol", "capture"}


def test_without_a_saved_layout_the_page_opens_with_factory_columns(app):
    grid = _find(view.layout(app.tape_state), view.GRID)
    assert fields(grid.columnDefs) == fields(COLUMN_DEFS) and grid.columnSize == "autoSize"


def _find(component, component_id):
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    for child in children if isinstance(children, (list, tuple)) else [children]:
        if hasattr(child, "to_plotly_json"):
            found = _find(child, component_id)
            if found is not None:
                return found
    return None
