"""Incomplete-legs tab: controllers on synthetic data and the HTTP endpoints."""

from datetime import date

from dash import no_update

from tape_dashboard.app import ids
from tape_dashboard.app.state import AppState
from tape_dashboard.app.tabs.incomplete import callbacks as cb
from tape_dashboard.app.tabs.incomplete import view
from tape_dashboard.app.tabs.operations import callbacks as ops
from tape_dashboard.app.tabs.operations.rows import EDITED
from tape_dashboard.rules import classification as c

INCOMPLETE = "20261013-BBB-13:00:00.000-MLAT"     # in the captures of 13/10 and 15/10
DEC = "2026-12-18"
VALUES = ("call", 130, DEC, 1.5, 3000)


def field(result, name):
    return result[[n for n, _ in cb.FORM_FIELDS].index(name)]


def save(app, values=VALUES, strategy="bull_call", version=0):
    return cb.form_action(app.tape_state, view.SAVE, None, values, strategy, {"id": INCOMPLETE}, version)


def pending_ids(app, day):
    rows, _ = cb.pending_content(app.tape_state, day)
    return [r["id"] for r in rows]


# --- day selector and list ----------------------------------------------------------------

def test_days_latest_first_with_their_pending_count(app):
    assert cb.day_options(app.tape_state) == [{"label": "2026-10-15 (1)", "value": "2026-10-15"},
                                              {"label": "2026-10-13 (1)", "value": "2026-10-13"}]
    assert cb.default_day(app.tape_state) == "2026-10-15"
    assert cb.day_note(app.tape_state, "2026-10-15") == ""


def test_without_a_capture_today_the_latest_one_is_shown_with_a_note(synthetic_settings):
    state = AppState(synthetic_settings, today=lambda: date(2026, 10, 20))
    assert cb.default_day(state) == "2026-10-15"
    assert cb.day_note(state, "2026-10-15").startswith("No capture for today (2026-10-20)")
    assert cb.day_note(state, "2026-10-13") == ""


def test_pending_rows(app):
    rows, line = cb.pending_content(app.tape_state, "2026-10-13")
    (row,) = rows
    assert (row["id"], row["contract"], row["size"], row["premium_m"]) == (INCOMPLETE, "BBB|20261218|120.00C",
                                                                         3000, 1.2)
    assert (row["measured_side"], row["price"], row["flags"]) == ("undetermined", 100.0, "")
    assert line == "1 operations with a missing leg above the threshold (2026-10-13)"
    assert cb.pending_content(app.tape_state, None) == ([], "")


# --- the form ---------------------------------------------------------------------------------

def test_selecting_a_row_opens_the_form_with_the_known_leg(app):
    result = cb.form_action(app.tape_state, view.GRID, [{"id": INCOMPLETE}], (None,) * 5, None, None, 0)
    assert field(result, "style") == view.SHOWN and "BBB" in field(result, "title")
    assert field(result, "known").startswith("Known leg: BBB|20261218|120.00C, 3,000 at 4.00 (1.200M)")
    assert [field(result, n) for n in ("option_type", "strike", "exp_date", "price", "size")] == \
        ["call", None, DEC, None, 3000]
    assert field(result, "selected") == {"id": INCOMPLETE} and field(result, "version") is no_update


def test_types_and_preview_follow_the_fields(app):
    options, preview = cb.form_feedback(app.tape_state, {"id": INCOMPLETE}, VALUES, None)
    assert [o["value"] for o in options] == ["bull_call", "bear_call", "unknown"]
    assert "Choose the operation type" in str(preview)
    _, preview = cb.form_feedback(app.tape_state, {"id": INCOMPLETE}, VALUES, "bull_call")
    assert "debit vertical → net, bull, strike 120" in str(preview)
    options, preview = cb.form_feedback(app.tape_state, {"id": INCOMPLETE}, ("call", None, DEC, 1.5, 3000), None)
    assert options == [] and "strike" in str(preview)
    assert cb.form_feedback(app.tape_state, None, VALUES, None) == ([], None)


def test_saving_moves_the_operation_to_tab_1(app):
    result = save(app, version=2)
    assert field(result, "message") == f"Saved: BBB {INCOMPLETE} is now in the Operations tab (net, bull)."
    assert field(result, "version") == 3 and field(result, "style") == view.HIDDEN
    assert pending_ids(app, "2026-10-13") == [] and pending_ids(app, "2026-10-15") == []

    rows, _, _ = ops.grid_content(app.tape_state, "custom", "2026-10-13", "2026-10-15")
    row = next(r for r in rows if r["id"] == INCOMPLETE)
    assert (row["destination"], row["direction"], row["structure"]) == (c.NET, c.BULL, "debit vertical")
    assert EDITED in row["flags"]


def test_a_rejected_save_explains_why_and_writes_nothing(app):
    result = save(app, strategy=None)
    assert "Choose the operation type" in str(field(result, "message"))
    assert field(result, "version") is no_update and field(result, "style") is no_update
    result = save(app, values=("call", 120, DEC, 1.5, 3000))
    assert "same contract" in str(field(result, "message"))
    edits = app.tape_state.edits()
    assert edits.manual_legs == {} and edits.overrides == {}


def test_the_message_survives_the_list_refresh(app):
    save(app)
    result = cb.form_action(app.tape_state, view.GRID, [], (None,) * 5, None, None, 1)
    assert field(result, "style") == view.HIDDEN and field(result, "message") is no_update


# --- wiring and HTTP ------------------------------------------------------------------------------

def test_incomplete_callbacks_are_registered(app):
    callbacks = app.tape_callbacks
    rows, _ = callbacks["refresh_pending"]("2026-10-13", 0, 0)
    assert [r["id"] for r in rows] == [INCOMPLETE]
    assert callbacks["refresh_days"](0, 0)[0]["value"] == "2026-10-15"


def test_the_pending_list_is_served_over_http(app):
    client = app.server.test_client()
    outputs = [d["output"] for d in client.get("/_dash-dependencies").get_json()]
    assert any(f"{ids.EDITS_VERSION}.data@" in o and view.FORM_TITLE in o for o in outputs)
    dep = next(o for o in outputs if f"{view.GRID}.rowData" in o)
    response = client.post("/_dash-update-component", json={
        "output": dep,
        "outputs": [{"id": view.GRID, "property": "rowData"}, {"id": view.SUMMARY, "property": "children"}],
        "inputs": [{"id": view.DAY, "property": "value", "value": "2026-10-13"},
                   {"id": ids.DATA_VERSION, "property": "data", "value": 0},
                   {"id": ids.EDITS_VERSION, "property": "data", "value": 0}],
        "changedPropIds": [f"{view.DAY}.value"], "state": [],
    })
    assert response.status_code == 200
    assert [r["id"] for r in response.get_json()["response"][view.GRID]["rowData"]] == [INCOMPLETE]


def test_a_stored_leg_that_no_longer_applies_can_be_replaced(app):
    # a leg repeating the known contract cannot be applied: the operation stays pending, with a note
    app.tape_state.store.add_manual_leg(INCOMPLETE, "call", 120, DEC, 1.5, 3000)
    (row,) = cb.pending_content(app.tape_state, "2026-10-13")[0]
    assert row["flags"] == "ⓘ" and "repeats the operation's contract" in row["notes"]
    opened = cb.form_action(app.tape_state, view.GRID, [{"id": INCOMPLETE}], (None,) * 5, None, None, 0)
    assert "saving replaces it" in str(field(opened, "message"))

    save(app)
    (manual,) = app.tape_state.edits().manual_legs[INCOMPLETE]
    assert manual.strike == 130.0 and pending_ids(app, "2026-10-13") == []


# --- editing a completed operation from tab 1's pop-up (decision 0030) -----------------------------

def modal(app, trigger, editing_data=None, strategy=None, leg_values=(None,) * 5, cell=None):
    return ops.modal_action(app.tape_state, trigger, cell, editing_data, None, strategy, 5, leg_values)


def opened(app):
    return modal(app, ops.view.GRID, cell={"colId": "direction", "rowId": INCOMPLETE})


def modal_field(result, name):
    return result[[n for n, _ in ops.MODAL_FIELDS].index(name)]


def test_the_pop_up_of_a_completed_operation_shows_its_manual_leg(app):
    save(app)
    result = opened(app)
    editing_data = modal_field(result, "editing")
    assert editing_data["kind"] == "manual-leg" and editing_data["leg_id"]
    assert modal_field(result, "leg_box") == ops.view.SHOWN
    assert modal_field(result, "delete_button") == ops.view.SHOWN_INLINE
    assert [modal_field(result, n) for n in ("option_type", "strike", "exp_date", "price", "size")] == \
        ["call", 130.0, DEC, 1.5, 3000]
    assert modal_field(result, "strategy") == "bull_call"


def test_other_operations_keep_their_pop_up(app):
    result = modal(app, ops.view.GRID, cell={"colId": "direction", "rowId": "20261013-AAA-10:00:00.000-AUTO"})
    assert modal_field(result, "editing")["kind"] == "direction"
    assert modal_field(result, "leg_box") == ops.view.HIDDEN
    assert modal_field(result, "delete_button") == ops.view.HIDDEN
    assert ops.leg_feedback(app.tape_state, modal_field(result, "editing"), VALUES, None) == (no_update, None)


def test_editing_the_manual_leg_and_its_type(app):
    save(app)
    editing_data = modal_field(opened(app), "editing")
    risk_reversal = ("put", 100, DEC, 2.0, 3000)
    options, preview = ops.leg_feedback(app.tape_state, editing_data, risk_reversal, "bullish_risk_reversal")
    assert "bullish_risk_reversal" in [o["value"] for o in options] and "risk reversal" in str(preview)

    result = modal(app, ops.view.SAVE, editing_data, "bullish_risk_reversal", risk_reversal)
    assert modal_field(result, "style") == ops.view.HIDDEN and modal_field(result, "version") == 6
    item = app.tape_state.classified(INCOMPLETE)
    assert (item.classification.structure, item.classification.destination) == ("risk reversal", c.DISCARDED)


def test_an_invalid_edit_keeps_the_pop_up_open(app):
    save(app)
    editing_data = modal_field(opened(app), "editing")
    result = modal(app, ops.view.SAVE, editing_data, "long_straddle", VALUES)
    assert "does not fit" in str(modal_field(result, "message"))
    assert modal_field(result, "style") is no_update and modal_field(result, "version") is no_update


def test_clearing_the_type_keeps_the_leg(app):
    save(app)
    modal(app, ops.view.CLEAR, modal_field(opened(app), "editing"))
    edits = app.tape_state.edits()
    assert INCOMPLETE in edits.manual_legs and INCOMPLETE not in edits.overrides
    assert app.tape_state.classified(INCOMPLETE).classification.destination == c.UNDETERMINED_MULTI


def test_deleting_the_manual_leg_sends_the_operation_back_to_tab_2(app):
    save(app)
    result = modal(app, ops.view.DELETE_LEG, modal_field(opened(app), "editing"))
    assert modal_field(result, "version") == 6
    edits = app.tape_state.edits()
    assert edits.manual_legs == {} and edits.overrides == {}
    assert pending_ids(app, "2026-10-13") == [INCOMPLETE]
    rows, _, _ = ops.grid_content(app.tape_state, "custom", "2026-10-13", "2026-10-15")
    assert INCOMPLETE not in [r["id"] for r in rows]
