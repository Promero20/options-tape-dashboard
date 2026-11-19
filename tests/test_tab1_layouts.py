"""The two layouts of the operations tab and the switch between them (decision 0038)."""

import json
from dataclasses import replace

import pytest

from tape_dashboard.app.preferences import HORIZONTAL, VERTICAL, Preferences
from tape_dashboard.app.state import AppState
from tape_dashboard.app.tabs.operations import view


def _find(component, component_id=None, class_name=None):
    if component_id is not None and getattr(component, "id", None) == component_id:
        return component
    if class_name is not None and class_name in (getattr(component, "className", None) or "").split():
        return component
    children = getattr(component, "children", None)
    for child in children if isinstance(children, (list, tuple)) else [children]:
        if hasattr(child, "to_plotly_json"):
            found = _find(child, component_id, class_name)
            if found is not None:
                return found
    return None


# --- the preference --------------------------------------------------------------------------------

def test_the_vertical_layout_is_the_default(tmp_path):
    assert Preferences(tmp_path / "preferences.json").operations_view() == VERTICAL


def test_the_layout_chosen_is_kept_with_the_other_preferences(tmp_path):
    path = tmp_path / "preferences.json"
    preferences = Preferences(path)
    preferences.save_operations_columns([{"colId": "capture", "hide": False}])
    preferences.save_operations_view(HORIZONTAL)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "operations_columns": [{"colId": "capture", "hide": False}], "operations_view": HORIZONTAL}
    assert Preferences(path).operations_view() == HORIZONTAL
    assert Preferences(path).operations_columns() == [{"colId": "capture", "hide": False}]


def test_an_unknown_layout_in_the_file_opens_the_default_one(tmp_path):
    path = tmp_path / "preferences.json"
    path.write_text(json.dumps({"operations_view": "diagonal"}), encoding="utf-8")
    assert Preferences(path).operations_view() == VERTICAL and Preferences(path).problem() is None


def test_an_unknown_layout_is_not_saved(tmp_path):
    with pytest.raises(ValueError):
        Preferences(tmp_path / "preferences.json").save_operations_view("diagonal")
    assert not (tmp_path / "preferences.json").exists()


# --- the page ---------------------------------------------------------------------------------------

def test_the_tab_opens_with_the_layout_chosen_last(app):
    page = view.layout(app.tape_state)
    assert (_find(page, view.TAB).className, _find(page, view.VIEW).data) == ("ops-tab view-vertical", VERTICAL)
    app.tape_state.preferences.save_operations_view(HORIZONTAL)
    page = view.layout(app.tape_state)
    assert (_find(page, view.TAB).className, _find(page, view.VIEW).data) == ("ops-tab view-horizontal", HORIZONTAL)


def test_the_three_panels_are_placed_by_the_layout(app):
    tab = _find(view.layout(app.tape_state), view.TAB)
    panels = [c.className for c in tab.children if "panel" in (getattr(c, "className", "") or "").split()]
    assert panels == ["panel ops-list", "panel charts", "panel detail-panel"]
    assert _find(tab, view.VIEW_BUTTON).title.startswith("Switch between")
    # the graphs follow the size of their box
    assert _find(tab, view.NET_GRAPH).responsive is True and _find(tab, view.WALLS_GRAPH).responsive is True


def test_the_gex_button_is_in_the_header_of_the_charts(synthetic_settings):
    state = AppState(replace(synthetic_settings, gex_reference_url="https://example.com/gex"))
    charts = _find(view.layout(state), class_name="charts")
    header = charts.children[0]
    assert _find(header, view.GEX_REFERENCE) is not None and _find(header, view.SYMBOL) is not None


def test_switching_is_remembered_for_the_next_visit(app):
    app.tape_callbacks["remember_view"](HORIZONTAL)
    assert app.tape_state.preferences.operations_view() == HORIZONTAL

    def props_of(node, component_id):
        if isinstance(node, dict):
            if node.get("props", {}).get("id") == component_id:
                return node["props"]
            return next((p for v in node.values() if (p := props_of(v, component_id))), None)
        if isinstance(node, list):
            return next((p for v in node if (p := props_of(v, component_id))), None)
        return None

    served = app.server.test_client().get("/_dash-layout").get_json()
    assert props_of(served, view.TAB)["className"] == "ops-tab view-horizontal"


def test_the_switch_runs_in_the_browser_with_a_view_transition(app):
    client = app.server.test_client()
    switch = [c for c in client.get("/_dash-dependencies").get_json()
              if (c.get("clientside_function") or {}).get("function_name") == "toggle_view"]
    assert len(switch) == 1
    assert switch[0]["clientside_function"]["namespace"] == "operations"
    assert switch[0]["output"] == f"..{view.VIEW}.data...{view.TAB}.className.."
    script = client.get("/assets/operations.js")
    assert script.status_code == 200
    text = script.get_data(as_text=True)
    assert "toggle_view" in text and "startViewTransition" in text and "prefers-reduced-motion" in text
