"""Grid rows, column definitions and leg details for the operations tab."""

from ....data.loading import build_contract_symbol
from ....rules.classification import DESTINATIONS, PENDING
from ....rules.sides import leg_side

EDITED, ANOMALOUS, NOTE = "✎", "⚠", "ⓘ"


def _blank_to_none(value):
    return None if value == "" else value


def operation_row(item):
    """One grid row from a ClassifiedOperation."""
    op, c = item.operation, item.classification
    s = op.summary
    notes = list(c.warnings) + list(item.problems)
    if c.anomalous_size_ratio:
        notes.append(f"anomalous size ratio: largest leg {c.size_ratio:.1f}× the smallest")
    flags = (EDITED if item.edited else "") + (ANOMALOUS if c.anomalous_size_ratio else "") + \
            (NOTE if c.warnings or item.problems else "")
    return {
        "id": op.id,
        "capture": op.capture_date.isoformat(),
        "trade_date": ", ".join(d.isoformat() for d in op.trade_dates),
        "symbol": op.symbol,
        "structure": c.structure,
        "strike": s["strike"],
        "expiration": s["fecha_expiracion"],
        "premium_m": round(op.premium / 1_000_000, 3),
        "net_price": _blank_to_none(c.net_price),
        "aggressiveness": _blank_to_none(s["agresividad_pond"]),
        "direction": c.direction or "",
        "destination": c.destination,
        "wall": c.wall or "",
        "conditions": s["trade_conditions"],
        "start": s["hora_inicio"],
        "end": s["hora_fin"],
        "legs": len(op.legs),
        "edited": item.edited,
        "anomalous_ratio": c.anomalous_size_ratio,
        "flags": flags,
        "notes": " · ".join(notes),
        "script_direction": s["direccion"],
    }


def operation_rows(items):
    return [operation_row(item) for item in items]


def destination_counts(items):
    """Number of operations per destination, in the classification's order (pending ones are not listed)."""
    counts = {d: 0 for d in DESTINATIONS if d != PENDING}
    for item in items:
        counts[item.classification.destination] = counts.get(item.classification.destination, 0) + 1
    return counts


def leg_rows(item):
    """Detail of each leg: measured side and the side the classification used."""
    op, c = item.operation, item.classification
    manual = {build_contract_symbol(op.symbol, leg.exp_date, leg.strike, leg.option_type)
              for leg in item.manual_legs}
    rows = []
    for i, leg in enumerate(op.legs):
        rows.append({
            "contract": leg["contract_symbol"],
            "size": leg["size"],
            "premium_m": round(leg["premium"] / 1_000_000, 3),
            "price": round(leg["precio_medio"], 4),
            "aggressiveness": None if leg["agr"] is None else round(leg["agr"], 2),
            "measured_side": leg_side(leg["agr"]) or "undetermined",
            "side_used": (c.sides[i] if i < len(c.sides) else None) or "—",
            "manual": leg["contract_symbol"] in manual,
        })
    return rows


def _number(decimals):
    return {"function": f"params.value == null ? '' : d3.format(',.{decimals}f')(params.value)"}


COLUMN_DEFS = [
    {"field": "capture", "headerName": "Capture", "minWidth": 110},
    {"field": "trade_date", "headerName": "Trade date", "minWidth": 110},
    {"field": "symbol", "headerName": "Symbol", "pinned": "left", "minWidth": 90},
    {"field": "structure", "headerName": "Structure", "minWidth": 150},
    {"field": "strike", "headerName": "Strike"},
    {"field": "expiration", "headerName": "Expiration", "minWidth": 120},
    {"field": "premium_m", "headerName": "Premium (M)", "filter": "agNumberColumnFilter",
     "type": "rightAligned", "valueFormatter": _number(3), "sort": "desc"},
    {"field": "net_price", "headerName": "Net price", "filter": "agNumberColumnFilter",
     "type": "rightAligned", "valueFormatter": _number(2)},
    {"field": "aggressiveness", "headerName": "Aggr.", "filter": "agNumberColumnFilter",
     "type": "rightAligned", "valueFormatter": _number(2)},
    {"field": "direction", "headerName": "Direction ✎", "cellClass": "cell-editable",
     "headerTooltip": "Click a cell to correct the direction or the operation type",
     "cellClassRules": {"dir-bull": "params.value === 'bull'", "dir-bear": "params.value === 'bear'"}},
    {"field": "destination", "headerName": "Destination", "minWidth": 140},
    {"field": "wall", "headerName": "Wall"},
    {"field": "conditions", "headerName": "Conditions", "minWidth": 110},
    {"field": "start", "headerName": "Start", "minWidth": 110},
    {"field": "end", "headerName": "End", "minWidth": 110},
    {"field": "flags", "headerName": "Flags", "tooltipField": "notes", "minWidth": 80},
    {"field": "id", "headerName": "ID", "hide": True, "minWidth": 260},
    {"field": "script_direction", "headerName": "Script direction", "hide": True},
]

# columns hidden by default that the user can show
OPTIONAL_COLUMNS = (("id", "ID"), ("script_direction", "Script direction"))


def column_defs(visible_optional=()):
    defs = []
    for col in COLUMN_DEFS:
        col = dict(col)
        if col["field"] in dict(OPTIONAL_COLUMNS):
            col["hide"] = col["field"] not in visible_optional
        defs.append(col)
    return defs


ROW_CLASS_RULES = {
    "row-undetermined": "['undetermined', 'undetermined multi-leg'].includes(params.data.destination)",
    "row-edited": "params.data.edited",
}
