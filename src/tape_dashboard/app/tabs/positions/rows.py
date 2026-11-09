"""Rows and columns of the open positions and the history (tab 3)."""

from ....positions import pnl
from ..operations.rows import number_format

M = 1_000_000
EXPIRED, ORPHAN = "⌛", "⚠"


def symbol_of(position):
    return ", ".join(dict.fromkeys(leg.symbol for leg in position.legs))


def leg_text(leg):
    return f"{leg.side} {leg.quantity} {leg.strike:g}{leg.option_type[0].upper()} {leg.exp_date} @ {leg.entry_price:g}"


def legs_text(position):
    return " / ".join(leg_text(leg) for leg in position.legs)


def _is_orphan(position, item):
    return position.operation_id is not None and item is None


def open_row(position, item, today):
    """`item` is the linked operation with its edits applied, or None."""
    expired = pnl.expired_legs(position, today)
    notes = [f"{len(expired)} open leg(s) past their expiration"] if expired else []
    if _is_orphan(position, item):
        notes.append("the linked operation no longer exists")
    return {
        "id": str(position.id),
        "symbol": symbol_of(position),
        "legs": legs_text(position),
        "opened": position.opened_on,
        "status": pnl.status(position),
        "commissions": position.commissions,
        "operation": position.operation_id or "",
        "flags": (EXPIRED if expired else "") + (ORPHAN if _is_orphan(position, item) else ""),
        "notes": " · ".join(notes),
    }


def history_row(position, item):
    """A closed position and, if it is linked, the data of the operation it mimics, to filter by."""
    c = item.classification if item else None
    aggressiveness = item.operation.summary["agresividad_pond"] if item else None
    percentage = pnl.pnl_pct(position)
    return {
        "id": str(position.id),
        "symbol": symbol_of(position),
        "legs": legs_text(position),
        "opened": position.opened_on,
        "closed": pnl.closing_date(position),
        "days": pnl.days_held(position),
        "pnl": round(pnl.net_pnl(position), 2),
        "pnl_pct": None if percentage is None else round(percentage, 2),
        "commissions": position.commissions,
        "structure": c.structure if c else "",
        "direction": (c.direction or "") if c else "",
        "premium_m": round(item.operation.premium / M, 3) if item else None,
        "aggressiveness": None if aggressiveness in (None, "") else aggressiveness,
        "operation": position.operation_id or "",
        "flags": ORPHAN if _is_orphan(position, item) else "",
        "notes": "the linked operation no longer exists" if _is_orphan(position, item) else "",
    }


_NUMBER = {"filter": "agNumberColumnFilter", "type": "rightAligned"}
_RESULT_CLASSES = {"dir-bull": "params.value > 0", "dir-bear": "params.value < 0"}

OPEN_COLUMNS = [
    {"field": "symbol", "headerName": "Symbol", "pinned": "left", "minWidth": 90},
    {"field": "flags", "headerName": "Flags", "tooltipField": "notes", "minWidth": 80},
    {"field": "status", "headerName": "Status", "minWidth": 120},
    {"field": "opened", "headerName": "Opened", "minWidth": 110, "sort": "desc"},
    {"field": "legs", "headerName": "Legs", "minWidth": 240},
    {"field": "commissions", "headerName": "Commissions", **_NUMBER, "valueFormatter": number_format(2)},
    {"field": "operation", "headerName": "Linked operation", "minWidth": 240},
]

HISTORY_COLUMNS = [
    {"field": "symbol", "headerName": "Symbol", "pinned": "left", "minWidth": 90},
    {"field": "pnl", "headerName": "P&L ($)", "pinned": "left", **_NUMBER, "valueFormatter": number_format(2),
     "cellClassRules": _RESULT_CLASSES},
    {"field": "pnl_pct", "headerName": "P&L (%)", **_NUMBER, "valueFormatter": number_format(1),
     "cellClassRules": _RESULT_CLASSES},
    {"field": "flags", "headerName": "Flags", "tooltipField": "notes", "minWidth": 80},
    {"field": "closed", "headerName": "Closed", "minWidth": 110, "sort": "desc"},
    {"field": "opened", "headerName": "Opened", "minWidth": 110},
    {"field": "days", "headerName": "Days", **_NUMBER},
    {"field": "structure", "headerName": "Structure", "minWidth": 150},
    {"field": "direction", "headerName": "Direction"},
    {"field": "premium_m", "headerName": "Premium (M)", **_NUMBER, "valueFormatter": number_format(3)},
    {"field": "aggressiveness", "headerName": "Aggr.", **_NUMBER, "valueFormatter": number_format(2)},
    {"field": "legs", "headerName": "Legs", "minWidth": 240},
    {"field": "commissions", "headerName": "Commissions", **_NUMBER, "valueFormatter": number_format(2)},
    {"field": "operation", "headerName": "Linked operation", "minWidth": 240},
]
