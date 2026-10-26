"""Callbacks of the application, called as plain functions and through Dash's HTTP endpoints."""

import subprocess
import sys

from dash import html

from helpers import REPO_ROOT
from tape_dashboard import __main__ as entry
from tape_dashboard.app import ids
from tape_dashboard.app.tabs.operations import callbacks as cb
from tape_dashboard.app.tabs.operations import editing
from tape_dashboard.app.tabs.operations import view
from tape_dashboard.rules import classification as c

SINGLE = "20261013-AAA-10:00:00.000-AUTO"
VERTICAL = "20261013-BBB-11:00:00.100-MLET"
BUTTERFLY = "20261013-CCC-15:00:00.000-MLET"
INCOMPLETE = "20261013-BBB-13:00:00.000-MLAT"


def rows_of(app, start="2026-10-13", end="2026-10-13"):
    rows, _, _ = cb.grid_content(app.tape_state, "custom", start, end)
    return {row["id"]: row for row in rows}


def click(app, op_id, column="direction"):
    return cb.modal_action(app.tape_state, view.GRID, {"colId": column, "rowId": op_id}, None, None, None, 0)


def output(result, component, prop):
    return result[cb.MODAL_OUTPUTS.index((component, prop))]


# --- grid ------------------------------------------------------------------------

def test_today_shows_todays_capture(app):
    rows, note, summary = cb.grid_content(app.tape_state, "today", None, None)
    assert rows and {r["capture"] for r in rows} == {"2026-10-15"}
    assert note == ""
    assert summary.startswith(f"{len(rows)} operations above the threshold (2026-10-15)")


def test_pending_operations_are_not_listed(app):
    rows = rows_of(app)
    assert INCOMPLETE not in rows
    assert rows[SINGLE]["destination"] == c.NET


def test_multi_day_range_counts_repeated_operations_once(app):
    rows, _, _ = cb.grid_content(app.tape_state, "custom", "2026-10-13", "2026-10-15")
    assert [r["id"] for r in rows].count(VERTICAL) == 1
    assert next(r for r in rows if r["id"] == VERTICAL)["capture"] == "2026-10-15"


# --- editing modal -------------------------------------------------------------------

def test_clicking_another_column_does_nothing(app):
    assert click(app, SINGLE, column="symbol") == cb.UNCHANGED


def test_open_editor_for_a_single_leg(app):
    result = click(app, SINGLE)
    assert output(result, view.MODAL, "style") == view.SHOWN
    assert output(result, view.EDITING, "data") == {"id": SINGLE, "kind": editing.DIRECTION}
    assert output(result, view.DIRECTION_BOX, "style") == view.SHOWN
    assert [o["value"] for o in output(result, view.DIRECTION_INPUT, "options")] == [c.BULL, c.BEAR, c.UNDETERMINED]
    assert output(result, view.STRATEGY_BOX, "style") == view.HIDDEN


def test_open_editor_for_two_legs_and_read_only(app):
    result = click(app, VERTICAL)
    assert output(result, view.EDITING, "data")["kind"] == editing.STRATEGY
    assert "bear_call" in [o["value"] for o in output(result, view.STRATEGY_INPUT, "options")]
    read_only = click(app, BUTTERFLY)
    assert output(read_only, view.EDITING, "data")["kind"] == editing.READ_ONLY
    assert output(read_only, view.READ_ONLY_TEXT, "children")


def test_saving_a_direction_moves_the_operation(app):
    state = app.tape_state
    result = cb.modal_action(state, view.SAVE, None, {"id": SINGLE, "kind": editing.DIRECTION}, c.BEAR, None, 3)
    assert output(result, view.MODAL, "style") == view.HIDDEN
    assert output(result, ids.EDITS_VERSION, "data") == 4
    row = rows_of(app)[SINGLE]
    assert (row["destination"], row["direction"], row["edited"]) == (c.WALLS, c.BEAR, True)

    cb.modal_action(state, view.CLEAR, None, {"id": SINGLE, "kind": editing.DIRECTION}, None, None, 4)
    assert rows_of(app)[SINGLE]["destination"] == c.NET
    assert state.edits().overrides == {}


def test_saving_an_operation_type(app):
    cb.modal_action(app.tape_state, view.SAVE, None, {"id": VERTICAL, "kind": editing.STRATEGY}, None, "bear_call", 0)
    row = rows_of(app, "2026-10-15", "2026-10-15")[VERTICAL]
    assert (row["structure"], row["destination"], row["wall"]) == ("credit vertical", c.WALLS, c.RESISTANCE)


def test_close_and_read_only_never_write(app):
    state = app.tape_state
    closed = cb.modal_action(state, view.CLOSE, None, {"id": SINGLE, "kind": editing.DIRECTION}, c.BEAR, None, 1)
    assert output(closed, view.MODAL, "style") == view.HIDDEN
    cb.modal_action(state, view.SAVE, None, {"id": BUTTERFLY, "kind": editing.READ_ONLY}, None, None, 1)
    assert state.edits().overrides == {}


# --- detail panel, page callbacks ---------------------------------------------------------

def test_detail_panel(app):
    panel = cb.detail_content(app.tape_state, VERTICAL)
    assert panel[0].children == f"BBB · {VERTICAL}"
    assert any(isinstance(part, html.Table) for part in panel)
    assert repr(cb.detail_content(app.tape_state, None)) == repr(view.empty_detail())
    assert repr(cb.detail_content(app.tape_state, "20261013-ZZZ-10:00:00.000-AUTO")) == repr(view.empty_detail())


def test_page_callbacks(app):
    callbacks = app.tape_callbacks
    assert callbacks["reload_data"](1, 2) == 3
    banner, info = callbacks["refresh_header"](3, 0)
    assert "2 captures (latest 2026-10-15)" in info
    assert banner is not None
    assert callbacks["toggle_dates"]("custom") is False and callbacks["toggle_dates"]("today") is True


# --- HTTP ------------------------------------------------------------------------------------

def test_layout_and_callbacks_are_served(app):
    client = app.server.test_client()
    assert client.get("/").status_code == 200
    assert client.get("/_dash-layout").status_code == 200
    outputs = {d["output"] for d in client.get("/_dash-dependencies").get_json()}
    assert any("ops-grid.rowData" in o for o in outputs)

    dep = next(o for o in outputs if "ops-grid.rowData" in o)
    response = client.post("/_dash-update-component", json={
        "output": dep,
        "outputs": [{"id": "ops-grid", "property": "rowData"}, {"id": "ops-range-note", "property": "children"},
                    {"id": "ops-summary", "property": "children"}],
        "inputs": [{"id": "ops-range", "property": "value", "value": "custom"},
                   {"id": "ops-dates", "property": "start_date", "value": "2026-10-13"},
                   {"id": "ops-dates", "property": "end_date", "value": "2026-10-13"},
                   {"id": ids.DATA_VERSION, "property": "data", "value": 0},
                   {"id": ids.EDITS_VERSION, "property": "data", "value": 0}],
        "changedPropIds": ["ops-range.value"], "state": [],
    })
    assert response.status_code == 200
    assert len(response.get_json()["response"]["ops-grid"]["rowData"]) == len(rows_of(app))


def test_the_app_only_listens_on_localhost():
    assert entry.HOST == "127.0.0.1"
    result = subprocess.run([sys.executable, "-m", "tape_dashboard", "--help"], cwd=REPO_ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert "--port" in result.stdout and "--host" not in result.stdout
