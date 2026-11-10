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


def link_text(operation_id, item):
    """One linked operation, as the detail panel and the tooltips show it."""
    if item is None:
        return f"{operation_id}, which no longer exists"
    c = item.classification
    return f"{operation_id} ({c.structure}, {c.direction or '—'}, {item.operation.premium / M:.3f}M)"


def links_summary(links):
    """
    The Linked column, short on purpose (decision 0033): the operation's
    structure and direction if there is one, or how many there are. The
    tooltip lists them all.
    """
    if not links:
        return ""
    if len(links) == 1:
        operation_id, item = links[0]
        c = item.classification if item else None
        return f"{c.structure} · {c.direction or '—'}" if c else "missing operation"
    return f"{len(links)} operations"


def source_data(links):
    """The data of the linked operations to filter the history by: structures and directions, total premium,
    and the premium-weighted aggressiveness."""
    found = [item for _, item in links if item is not None]
    structures = ", ".join(dict.fromkeys(item.classification.structure for item in found))
    directions = ", ".join(dict.fromkeys(item.classification.direction or "—" for item in found))
    weighted = [(item.operation.premium, item.operation.summary["agresividad_pond"]) for item in found
                if item.operation.summary["agresividad_pond"] not in (None, "")]
    weight = sum(premium for premium, _ in weighted)
    return {
        "structure": structures,
        "direction": directions,
        "premium_m": round(sum(item.operation.premium for item in found) / M, 3) if found else None,
        "aggressiveness": round(sum(p * a for p, a in weighted) / weight, 2) if weight else None,
    }


def _notes(links, expired):
    notes = [f"{len(expired)} open leg(s) past their expiration"] if expired else []
    notes += [link_text(operation_id, item) for operation_id, item in links]
    return " · ".join(notes)


def _flags(links, expired):
    return (EXPIRED if expired else "") + (ORPHAN if any(item is None for _, item in links) else "")


def open_row(position, links, today):
    """`links` pairs each linked operation ID with that operation, edits applied, or None if it is gone."""
    expired = pnl.expired_legs(position, today)
    return {
        "id": str(position.id),
        "symbol": symbol_of(position),
        "legs": legs_text(position),
        "opened": position.opened_on,
        "status": pnl.status(position),
        "commissions": position.commissions,
        "linked": links_summary(links),
        "flags": _flags(links, expired),
        "notes": _notes(links, expired),
    }


def history_row(position, links):
    """A closed position and the data of the operations it mimics, to filter by."""
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
        "linked": links_summary(links),
        **source_data(links),
        "flags": _flags(links, ()),
        "notes": _notes(links, ()),
    }


_NUMBER = {"filter": "agNumberColumnFilter", "type": "rightAligned"}
_RESULT_CLASSES = {"dir-bull": "params.value > 0", "dir-bear": "params.value < 0"}

OPEN_COLUMNS = [
    {"field": "symbol", "headerName": "Symbol", "pinned": "left", "minWidth": 90},
    {"field": "flags", "headerName": "Flags", "tooltipField": "notes", "minWidth": 80},
    {"field": "status", "headerName": "Status", "minWidth": 120},
    {"field": "linked", "headerName": "Linked", "tooltipField": "notes", "minWidth": 170},
    {"field": "opened", "headerName": "Opened", "minWidth": 110, "sort": "desc"},
    {"field": "legs", "headerName": "Legs", "minWidth": 240},
    {"field": "commissions", "headerName": "Commissions", **_NUMBER, "valueFormatter": number_format(2)},
]

HISTORY_COLUMNS = [
    {"field": "symbol", "headerName": "Symbol", "pinned": "left", "minWidth": 90},
    {"field": "pnl", "headerName": "P&L ($)", "pinned": "left", **_NUMBER, "valueFormatter": number_format(2),
     "cellClassRules": _RESULT_CLASSES},
    {"field": "pnl_pct", "headerName": "P&L (%)", **_NUMBER, "valueFormatter": number_format(1),
     "cellClassRules": _RESULT_CLASSES},
    {"field": "flags", "headerName": "Flags", "tooltipField": "notes", "minWidth": 80},
    {"field": "linked", "headerName": "Linked", "tooltipField": "notes", "minWidth": 170},
    {"field": "structure", "headerName": "Structure", "minWidth": 150},
    {"field": "direction", "headerName": "Direction"},
    {"field": "closed", "headerName": "Closed", "minWidth": 110, "sort": "desc"},
    {"field": "opened", "headerName": "Opened", "minWidth": 110},
    {"field": "days", "headerName": "Days", **_NUMBER},
    {"field": "premium_m", "headerName": "Premium (M)", **_NUMBER, "valueFormatter": number_format(3)},
    {"field": "aggressiveness", "headerName": "Aggr.", **_NUMBER, "valueFormatter": number_format(2)},
    {"field": "legs", "headerName": "Legs", "minWidth": 240},
    {"field": "commissions", "headerName": "Commissions", **_NUMBER, "valueFormatter": number_format(2)},
]
