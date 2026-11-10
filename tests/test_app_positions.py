"""Positions tab: controllers on synthetic data and the HTTP endpoints. All the figures are invented."""

from datetime import date
from types import SimpleNamespace

import pytest
from dash import dcc, no_update

from tape_dashboard.app import ids
from tape_dashboard.app.leg_form import LegFormIds, leg_fields
from tape_dashboard.app.state import AppState
from tape_dashboard.app.tabs.operations import view as ops_view
from tape_dashboard.app.tabs.positions import callbacks as cb
from tape_dashboard.app.tabs.positions import forms, view
from tape_dashboard.app.tabs.positions.rows import EXPIRED, ORPHAN
from tape_dashboard.app.warnings import collect
from tape_dashboard.charts import figures
from tape_dashboard.positions.store import Leg
from tape_dashboard.rules import classification as c

OPENED = "2026-10-01"
EXP = "2026-12-18"
SINGLE = "20261013-AAA-10:00:00.000-AUTO"       # AAA call bought: net, bull
VERTICAL = "20261013-BBB-11:00:00.100-MLET"
HALF_KNOWN = "20261013-BBB-14:30:00.000-MLET"   # one leg without a clear side
LEG = ("call", "buy", 100, EXP, 2, 2.5, None, None)
EMPTY = (None,) * 8


def rows(*legs):
    return [*legs, *[EMPTY] * (forms.LEG_SLOTS - len(legs))]


def fields(opened=OPENED, symbol="xyz", commissions=4, notes="note", operations=None):
    return opened, symbol, commissions, notes, operations


def leg(side="buy", strike=100.0, entry=2.0, exp=EXP, closed=None, price=None, quantity=1):
    return Leg("XYZ", "call", strike, exp, side, quantity, entry, closed, price)


def closed_leg(**kw):
    return leg(closed="2026-10-11", price=3.0, **kw)


def field(result, name):
    return result[[n for n, _ in cb.FORM_FIELDS].index(name)]


def close_field(result, name):
    return result[[n for n, _ in cb.CLOSE_FIELDS].index(name)]


def save_form(app, editing=None, selected=None, form=None, legs=None, version=0):
    return cb.form_action(app.tape_state, forms.FORM_SAVE, selected, None, editing or {"id": None}, version,
                          form or fields(), legs or rows(LEG))


def open_form(app, trigger, selected=None, prefill=None):
    return cb.form_action(app.tape_state, trigger, selected, prefill, None, 0, fields(), rows())


def only(app):
    (position,) = app.tape_state.positions.all()
    return position


# --- lists ---------------------------------------------------------------------------------

def test_open_and_closed_positions_go_to_their_list(app):
    store = app.tape_state.positions
    store.create(OPENED, [leg()], 1.0)
    store.create(OPENED, [closed_leg()], 10.0)
    open_rows, history = cb.list_content(app.tape_state)
    assert [(r["symbol"], r["status"], r["commissions"], r["flags"], r["linked"]) for r in open_rows] == \
        [("XYZ", "open", 1.0, "", "")]
    (row,) = history
    assert (row["closed"], row["days"], row["pnl"], row["pnl_pct"]) == ("2026-10-11", 10, 90.0, 45.0)
    assert row["legs"] == "buy 1 100C 2026-12-18 @ 2"
    assert (row["structure"], row["direction"], row["premium_m"], row["linked"]) == ("", "", None, "")


def test_a_partly_closed_position_stays_open(app):
    app.tape_state.positions.create(OPENED, [closed_leg(), leg("sell", 110.0)])
    open_rows, history = cb.list_content(app.tape_state)
    assert [r["status"] for r in open_rows] == ["partially closed"] and history == []


def test_one_link_shows_its_structure_and_direction(app):
    state = app.tape_state
    state.positions.create(OPENED, [leg()], operation_ids=[SINGLE])
    state.positions.create(OPENED, [closed_leg()], operation_ids=[SINGLE])
    (open_row,), (row,) = cb.list_content(state)
    assert open_row["linked"] == "single-leg call · bull" and SINGLE in open_row["notes"]
    assert (row["structure"], row["direction"], row["premium_m"]) == ("single-leg call", c.BULL, 0.702)
    assert row["aggressiveness"] is not None
    state.store.set_direction(SINGLE, c.BEAR)
    assert cb.list_content(state)[1][0]["direction"] == c.BEAR


def test_several_links_stay_short_in_the_lists(app):
    state = app.tape_state
    state.positions.create(OPENED, [closed_leg()], operation_ids=[SINGLE, VERTICAL])
    (row,) = cb.list_content(state)[1]
    assert row["linked"] == "2 operations"
    assert SINGLE in row["notes"] and VERTICAL in row["notes"]
    assert row["structure"] == "single-leg call, debit vertical" and row["direction"] == "bull"
    single, vertical = state.classified(SINGLE).operation, state.classified(VERTICAL).operation
    assert row["premium_m"] == round((single.premium + vertical.premium) / 1_000_000, 3)
    weights = [(o.premium, o.summary["agresividad_pond"]) for o in (single, vertical)]
    assert row["aggressiveness"] == round(sum(p * a for p, a in weights) / sum(p for p, _ in weights), 2)


def test_a_link_to_a_missing_operation_is_shown_and_kept(app):
    state = app.tape_state
    state.positions.create(OPENED, [leg()], operation_ids=["GONE"])
    state.positions.create(OPENED, [closed_leg()], operation_ids=[SINGLE, "GONE"])
    open_rows, history = cb.list_content(state)
    assert ORPHAN in open_rows[0]["flags"] and open_rows[0]["linked"] == "missing operation"
    assert history[0]["flags"] == ORPHAN and history[0]["structure"] == "single-leg call"
    assert sum("operation GONE, which no longer exists" in n.text for n in collect(state)) == 2
    assert [p.operation_ids for p in state.positions.all()] == [(SINGLE, "GONE"), ("GONE",)]


def test_expired_open_legs_are_flagged_but_not_closed(synthetic_settings):
    state = AppState(synthetic_settings, today=lambda: date(2026, 10, 15))
    state.positions.create(OPENED, [leg(exp="2026-10-10")])
    (row,) = cb.list_content(state)[0]
    assert EXPIRED in row["flags"] and row["status"] == "open"
    assert any("past their expiration" in n.text for n in collect(state))
    assert not only(SimpleNamespace(tape_state=state)).legs[0].closed


# --- history view and chart -----------------------------------------------------------------------

def test_the_chart_follows_the_rows_left_by_the_filters():
    all_rows = [{"closed": "2026-10-01", "pnl": 100.0}, {"closed": "2026-10-05", "pnl": -40.0}]
    fig, line = cb.history_view(all_rows[:1], all_rows)
    assert list(fig.data[0].y) == [100.0] and line == "1 closed positions, total P&L +100.00"
    fig, line = cb.history_view(None, all_rows)
    assert list(fig.data[0].x) == ["2026-10-01", "2026-10-05"] and list(fig.data[0].y) == [100.0, 60.0]


def test_the_chart_without_closed_positions():
    fig, line = cb.history_view([], [])
    assert not fig.data and "No closed positions" in fig.layout.annotations[0].text
    assert line == "0 closed positions, total P&L +0.00"


def test_cumulative_figure():
    fig = figures.cumulative_pnl_figure([("2026-10-01", 100.0), ("2026-10-05", 60.0)])
    assert fig.data[0].line.shape == "hv" and fig.data[0].showlegend is False
    assert fig.layout.xaxis.type == "date" and fig.layout.yaxis.rangemode == "tozero"
    assert fig.layout.xaxis.range is None


def test_a_single_closing_date_keeps_a_readable_axis():
    fig = figures.cumulative_pnl_figure([("2026-10-01", 100.0)])
    assert list(fig.layout.xaxis.range) == ["2026-09-28", "2026-10-04"]
    assert fig.layout.xaxis.tickformat == "%Y-%m-%d"


# --- reading the forms ------------------------------------------------------------------------------

def test_parse_a_position():
    parsed, errors = forms.parse_position(*fields(operations=[SINGLE, VERTICAL, SINGLE]), rows(LEG))
    assert errors == []
    assert (parsed.opened_on, parsed.commissions, parsed.notes) == (OPENED, 4.0, "note")
    assert parsed.operation_ids == (SINGLE, VERTICAL)
    (only_leg,) = parsed.legs
    assert (only_leg.symbol, only_leg.side, only_leg.strike, only_leg.quantity) == ("XYZ", "buy", 100.0, 2)
    assert not only_leg.closed


def test_empty_commissions_are_one_dollar_per_contract_up_to_ten_per_leg():
    legs = rows(("call", "buy", 100, EXP, 3, 2.5, None, None), ("call", "sell", 110, EXP, 25, 1.0, None, None))
    parsed, _ = forms.parse_position(*fields(commissions=None), legs)
    assert parsed.commissions == 13.0
    parsed, _ = forms.parse_position(*fields(commissions=0), legs)
    assert parsed.commissions == 0.0                           # a value typed in is kept, even 0


def test_the_commissions_hint():
    assert forms.automatic_commissions_hint([3, 25, None, ""]) == "Automatic: 13.00"
    assert forms.automatic_commissions_hint([None] * 4) == "Automatic"


def test_a_row_can_be_left_empty_between_legs():
    parsed, errors = forms.parse_position(*fields(), [LEG, EMPTY, LEG, EMPTY])
    assert errors == [] and len(parsed.legs) == 2


def test_closes_are_read_from_the_form():
    closed = ("call", "buy", 100, EXP, 2, 2.5, "2026-10-11", 3)
    parsed, _ = forms.parse_position(*fields(), rows(closed, ("call", "sell", 110, EXP, 2, 1.0, "2026-10-11", None)))
    first, second = parsed.legs
    assert (first.exit_date, first.exit_price) == ("2026-10-11", 3.0)
    assert (second.exit_date, second.exit_price) == (None, None)    # no price: the leg is open


def test_form_errors():
    cases = [
        (fields(opened=None), rows(LEG), "opening date"),
        (fields(symbol=" "), rows(LEG), "underlying"),
        (fields(), rows(("call", None, 100, EXP, 2, 2.5, None, None)), "Leg 1: fill in every field"),
        (fields(), rows(), "at least one leg"),
        (fields(), rows(("call", "buy", 100, "2026-09-01", 2, 2.5, None, None)), "expires before"),
        (fields(), rows(("call", "buy", 100, EXP, 1.5, 2.5, None, None)), "quantity"),
        (fields(), rows(("call", "buy", 100, EXP, 2, 2.5, None, 3)), "Leg 1: pick the closing date"),
        (fields(), rows(("call", "buy", 100, EXP, 2, 2.5, "2026-09-01", 3)), "closes before"),
        (fields(commissions="abc"), rows(LEG), "commissions"),
    ]
    for form, legs, message in cases:
        parsed, errors = forms.parse_position(*form, legs)
        assert parsed is None and any(message in e for e in errors), message


def test_parse_exits():
    assert forms.parse_exits([1, 2], [("2026-10-05", 3), ("2026-10-05", None)]) == \
        ({1: ("2026-10-05", 3.0), 2: None}, [])
    exits, errors = forms.parse_exits([1], [(None, 3)])
    assert exits is None and "closing date" in errors[0]


# --- the position form -----------------------------------------------------------------------------

def test_new_form_starts_empty_with_todays_date(app):
    result = open_form(app, view.NEW)
    assert field(result, "style") == forms.SHOWN and field(result, "opened") == "2026-10-15"
    assert field(result, "editing") == {"id": None} and field(result, "symbol") is None
    assert field(result, "leg0_strike") is None and field(result, "version") is no_update
    assert field(result, "legs_class") == forms.LEGS_CLASS and field(result, "operations") == []


def test_saving_a_new_position(app):
    result = save_form(app, form=fields(operations=[SINGLE]), version=2)
    assert field(result, "style") == forms.HIDDEN and field(result, "version") == 3
    position = only(app)
    assert (position.operation_ids, position.commissions, position.legs[0].symbol) == ((SINGLE,), 4.0, "XYZ")


def test_an_invalid_form_stays_open_and_writes_nothing(app):
    result = save_form(app, form=fields(symbol=""))
    assert "underlying" in str(field(result, "message"))
    assert field(result, "style") is no_update and field(result, "version") is no_update
    assert app.tape_state.positions.all() == []


def test_the_edit_form_of_an_open_position_has_no_closing_fields(app):
    new = app.tape_state.positions.create(OPENED, [leg(), leg("sell", 110.0)], 3.0, "old", [SINGLE])
    result = open_form(app, view.EDIT, {"id": new})
    assert field(result, "editing") == {"id": new} and field(result, "symbol") == "XYZ"
    assert (field(result, "leg0_strike"), field(result, "leg1_side")) == (100.0, "sell")
    assert field(result, "leg2_strike") is None and field(result, "legs_class") == forms.LEGS_CLASS
    assert field(result, "operations") == [SINGLE] and field(result, "commissions") == 3.0
    assert SINGLE in [o["value"] for o in field(result, "operation_options")]


def test_a_closed_position_is_edited_with_its_closes(app):
    store = app.tape_state.positions
    new = store.create(OPENED, [closed_leg(), closed_leg(side="sell", strike=110.0)])
    result = open_form(app, view.EDIT, {"id": new})
    assert field(result, "legs_class") == forms.LEGS_WITH_EXITS_CLASS
    assert (field(result, "leg0_exit_date"), field(result, "leg1_exit_price")) == ("2026-10-11", 3.0)

    edited = rows(("call", "buy", 100, EXP, 1, 2.0, "2026-10-12", 3.5),
                  ("call", "sell", 110, EXP, 1, 2.0, "2026-10-11", 3.0))
    save_form(app, editing={"id": new}, selected={"id": new}, legs=edited)
    first, second = only(app).legs
    assert (first.exit_date, first.exit_price, second.exit_price) == ("2026-10-12", 3.5, 3.0)
    assert cb.list_content(app.tape_state)[1][0]["closed"] == "2026-10-12"


def test_emptying_an_exit_price_in_the_edit_form_reopens_the_leg(app):
    new = app.tape_state.positions.create(OPENED, [closed_leg()])
    reopened = rows(("call", "buy", 100, EXP, 1, 2.0, "2026-10-11", None))
    save_form(app, editing={"id": new}, selected={"id": new}, legs=reopened)
    assert not only(app).legs[0].closed


def test_default_commissions_show_empty_when_editing(app):
    store = app.tape_state.positions
    automatic = store.create(OPENED, [leg(quantity=3)], 3.0)
    typed = store.create(OPENED, [leg(quantity=3)], 4.5)
    assert field(open_form(app, view.EDIT, {"id": automatic}), "commissions") is None
    assert field(open_form(app, view.EDIT, {"id": typed}), "commissions") == 4.5


def test_edit_without_a_selection_does_nothing(app):
    assert all(value is no_update for value in open_form(app, view.EDIT))


def test_cancelling_the_form(app):
    result = cb.form_action(app.tape_state, forms.FORM_CANCEL, None, None, {"id": None}, 0, fields(), rows())
    assert field(result, "style") == forms.HIDDEN and app.tape_state.positions.all() == []


# --- closing --------------------------------------------------------------------------------------

def opened_close(app, position_id):
    return cb.close_action(app.tape_state, view.CLOSE, {"id": position_id}, None, 0, [])


def test_the_closing_form_has_a_row_per_leg_and_todays_date(app):
    new = app.tape_state.positions.create(OPENED, [closed_leg(), leg("sell", 110.0)])
    result = opened_close(app, new)
    assert close_field(result, "style") == forms.SHOWN
    assert (close_field(result, "row0"), close_field(result, "row2")) == (forms.ROW_SHOWN, forms.HIDDEN)
    assert (close_field(result, "date0"), close_field(result, "price0")) == ("2026-10-11", 3.0)
    assert (close_field(result, "date1"), close_field(result, "price1")) == ("2026-10-15", None)
    assert close_field(result, "label1").startswith("sell 1 110C")


def test_closing_leg_by_leg_and_reopening(app):
    state = app.tape_state
    new = state.positions.create(OPENED, [leg(), leg("sell", 110.0)])
    closing = close_field(opened_close(app, new), "closing")

    result = cb.close_action(state, forms.CLOSE_SAVE, {"id": new}, closing, 7,
                             [("2026-10-05", 3.0), ("2026-10-05", None)])
    assert close_field(result, "style") == forms.HIDDEN and close_field(result, "version") == 8
    assert [r["status"] for r in cb.list_content(state)[0]] == ["partially closed"]

    cb.close_action(state, forms.CLOSE_SAVE, {"id": new}, closing, 8, [("2026-10-05", 3.0), ("2026-10-09", 0.5)])
    (row,) = cb.list_content(state)[1]
    assert (row["closed"], row["pnl"]) == ("2026-10-09", 250.0)         # +100 on the call, +150 on the short

    cb.close_action(state, forms.CLOSE_SAVE, {"id": new}, closing, 9, [("2026-10-05", None), ("2026-10-09", 0.5)])
    assert [r["status"] for r in cb.list_content(state)[0]] == ["partially closed"] and cb.list_content(state)[1] == []


def test_an_invalid_close_explains_why_and_writes_nothing(app):
    new = app.tape_state.positions.create(OPENED, [leg()])
    closing = close_field(opened_close(app, new), "closing")
    result = cb.close_action(app.tape_state, forms.CLOSE_SAVE, {"id": new}, closing, 0, [("2026-09-01", 3.0)])
    assert "closes before" in str(close_field(result, "message")) and close_field(result, "version") is no_update
    assert not only(app).legs[0].closed


# --- selection, detail, deletion -------------------------------------------------------------------

def test_a_click_in_either_list_selects_the_position(app):
    state = app.tape_state
    assert cb.selection_action(state, view.OPEN_GRID, {"rowId": "3"}, None, None, 0) == ({"id": 3}, no_update)
    assert cb.selection_action(state, view.HISTORY_GRID, None, {"rowId": "4"}, {"id": 3}, 0) == ({"id": 4}, no_update)


def test_confirming_the_dialog_deletes_the_selected_position(app):
    state = app.tape_state
    new = state.positions.create(OPENED, [leg()])
    assert cb.selection_action(state, view.CONFIRM, None, None, {"id": new}, 2) == (None, 3)
    assert state.positions.all() == []
    assert cb.selection_action(state, view.CONFIRM, None, None, None, 2) == (no_update, no_update)


def test_the_detail_panel_lists_every_link(app):
    state = app.tape_state
    assert cb.detail_content(state, None)[1] == view.HIDDEN
    new = state.positions.create(OPENED, [closed_leg()], 10.0, "my note", [SINGLE, "GONE"])
    panel, actions = cb.detail_content(state, {"id": new})
    assert actions == view.SHOWN_INLINE and panel[0].children == f"XYZ · position {new}"
    text = str(panel[1])
    assert "P&L +90.00 (+45.0%)" in text and "my note" in text
    assert f"Linked to {SINGLE} (single-leg call, bull, 0.702M)" in text
    assert "Linked to GONE, which no longer exists" in text
    assert cb.detail_content(state, {"id": 999})[1] == view.HIDDEN


def test_operations_offered_for_an_underlying(app):
    state = app.tape_state
    options = cb.operation_options(state, " aaa", None)
    assert SINGLE in [o["value"] for o in options] and all("BBB" not in o["value"] for o in options)
    label = next(o["label"] for o in options if o["value"] == SINGLE)
    assert label == "10-13 10:00 · single-leg call · bull · 0.70M"
    assert cb.operation_options(state, "", None) == []
    assert cb.operation_options(state, "ZZZ", None) == []
    kept = cb.operation_options(state, "AAA", ["GONE", SINGLE])
    assert kept[0] == {"label": "GONE (not listed for this underlying)", "value": "GONE"}
    assert [o["value"] for o in kept].count(SINGLE) == 1


# --- New position from an operation ----------------------------------------------------------------

def test_a_position_can_start_from_an_operation(app):
    prefill = cb.prefill_from_operation(app.tape_state, VERTICAL, 1)
    assert (prefill["symbol"], prefill["operation_ids"], prefill["note"]) == ("BBB", [VERTICAL], "")
    assert sorted((l["strike"], l["side"], l["option_type"], l["exp_date"]) for l in prefill["legs"]) == \
        [(100.0, "buy", "call", EXP), (110.0, "sell", "call", EXP)]
    assert all("quantity" not in l and "entry_price" not in l for l in prefill["legs"])


def test_prefill_sends_the_link_together_with_its_option(app):
    # tab 3 may never have been shown: an option that arrived later would drop the link
    prefill = cb.prefill_from_operation(app.tape_state, VERTICAL, 1)
    result = open_form(app, view.PREFILL, prefill=prefill)
    assert field(result, "style") == forms.SHOWN and field(result, "symbol") == "BBB"
    assert field(result, "operations") == [VERTICAL]
    assert VERTICAL in [o["value"] for o in field(result, "operation_options")]
    assert field(result, "leg0_strike") in (100.0, 110.0) and field(result, "leg0_quantity") is None


def test_a_leg_without_a_clear_side_is_left_for_the_user(app):
    prefill = cb.prefill_from_operation(app.tape_state, HALF_KNOWN, 1)
    assert None in [l["side"] for l in prefill["legs"]]


def test_more_legs_than_the_form_holds_are_announced(app, monkeypatch):
    legs = [{"type": "call", "strike": f"{100 + i}.00", "exp_date": EXP} for i in range(5)]
    item = SimpleNamespace(operation=SimpleNamespace(symbol="XYZ", id="X", legs=legs),
                           classification=SimpleNamespace(sides=()))
    monkeypatch.setattr(app.tape_state, "classified", lambda operation_id: item)
    prefill = cb.prefill_from_operation(app.tape_state, "X", 1)
    assert len(prefill["legs"]) == 4 and "only the first 4" in prefill["note"]
    assert prefill["legs"][0]["side"] is None


def test_prefill_needs_an_operation(app):
    assert cb.prefill_from_operation(app.tape_state, None, 1) is None
    assert cb.prefill_from_operation(app.tape_state, "GONE", 1) is None
    assert app.tape_callbacks["new_from_operation"](1, None) == (None, no_update)


def test_the_button_goes_to_the_positions_tab(app):
    prefill, tab = app.tape_callbacks["new_from_operation"](2, [{"id": VERTICAL}])
    assert tab == "positions" and prefill["nonce"] == 2


def test_tab_1_shows_its_actions_only_with_a_selection(app):
    show_detail = app.tape_callbacks["show_detail"]
    assert show_detail([], 0)[1] == ops_view.HIDDEN
    assert show_detail([{"id": VERTICAL}], 0)[1] == ops_view.SHOWN_INLINE


# --- wiring and HTTP -------------------------------------------------------------------------------

def test_the_lists_are_served_over_http(app):
    app.tape_state.positions.create(OPENED, [leg()])
    client = app.server.test_client()
    outputs = [d["output"] for d in client.get("/_dash-dependencies").get_json()]
    assert any(f"{ids.POSITIONS_VERSION}.data@" in o and forms.FORM_TITLE in o for o in outputs)
    dep = next(o for o in outputs if f"{view.OPEN_GRID}.rowData" in o)
    response = client.post("/_dash-update-component", json={
        "output": dep,
        "outputs": [{"id": view.OPEN_GRID, "property": "rowData"}, {"id": view.HISTORY_GRID, "property": "rowData"}],
        "inputs": [{"id": ids.DATA_VERSION, "property": "data", "value": 0},
                   {"id": ids.EDITS_VERSION, "property": "data", "value": 0},
                   {"id": ids.POSITIONS_VERSION, "property": "data", "value": 0}],
        "changedPropIds": [f"{ids.POSITIONS_VERSION}.data"], "state": [],
    })
    assert response.status_code == 200
    body = response.get_json()["response"]
    assert [r["symbol"] for r in body[view.OPEN_GRID]["rowData"]] == ["XYZ"]
    assert body[view.HISTORY_GRID]["rowData"] == []


def test_the_commissions_hint_is_wired(app):
    assert app.tape_callbacks["refresh_commissions_hint"](2, None, 30, None) == "Automatic: 12.00"


def _inputs(component):
    """Every text or number field in a tree of Dash components."""
    children = getattr(component, "children", None)
    children = children if isinstance(children, (list, tuple)) else [children]
    found = [component] if isinstance(component, dcc.Input) else []
    for child in children:
        if hasattr(child, "to_plotly_json"):
            found += _inputs(child)
    return found


@pytest.mark.parametrize("build", [forms.position_form, forms.close_form,
                                   lambda: leg_fields(LegFormIds.with_prefix("test"))])
def test_a_timed_delay_cannot_lose_what_was_just_typed(build):
    # Save reads the fields' last value: with a delay in seconds, a quick click saves an older one
    inputs = _inputs(build())
    assert inputs and all(getattr(i, "debounce", None) in (None, False, True) for i in inputs)
