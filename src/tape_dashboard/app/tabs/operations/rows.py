"""Grid rows, the catalogue of columns a layout can show (decision 0035), and leg details for the operations tab."""

from ....data.loading import build_contract_symbol
from ....rules.classification import DESTINATIONS, PENDING
from ....rules.sides import leg_side

EDITED, ANOMALOUS, NOTE = "✎", "⚠", "ⓘ"


def _blank_to_none(value):
    return None if value == "" else value


def _contract_volume(op, volume_of):
    """
    Volume of the operation's contracts on the session they traded, added up
    across legs. None if any leg is missing from level 1 (a manual leg, for
    one): a partial sum would understate it.
    """
    if volume_of is None:
        return None
    volumes = [volume_of(leg["contract_symbol"]) for leg in op.legs]
    return None if not volumes or None in volumes else sum(volumes)


def operation_row(item, volume_of=None):
    """One grid row from a ClassifiedOperation; `volume_of(contract)` gives a contract's volume on its trade date."""
    op, c = item.operation, item.classification
    s = op.summary
    notes = list(c.warnings) + list(item.problems)
    if c.anomalous_size_ratio:
        notes.append(f"anomalous size ratio: largest leg {c.size_ratio:.1f}× the smallest")
    flags = (EDITED if item.edited else "") + (ANOMALOUS if c.anomalous_size_ratio else "") + \
            (NOTE if c.warnings or item.problems else "")
    volume = _contract_volume(op, volume_of)
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
        "trades": s["n_trades"],
        "size": s["size_total"],
        "duration_s": s["duracion_s"],
        "contract_volume": volume,
        "volume_share": round(s["size_total"] / volume * 100, 1) if volume else None,
        "edited": item.edited,
        "anomalous_ratio": c.anomalous_size_ratio,
        "flags": flags,
        "notes": " · ".join(notes),
        "script_direction": s["direccion"],
    }


def operation_rows(items, dataset=None):
    """Rows for the grid; with the dataset, each operation's contract volume comes from its capture's level 1."""
    def volume_of(item):
        capture = dataset.captures.get(item.operation.capture_date) if dataset is not None else None
        return capture.contract_volume if capture is not None else None
    return [operation_row(item, volume_of(item)) for item in items]


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


def number_format(decimals):
    return {"function": f"params.value == null ? '' : d3.format(',.{decimals}f')(params.value)"}


# Direction is pinned because it opens the pop-up: it has to be visible however narrow the list is.
COLUMN_DEFS = [
    {"field": "symbol", "headerName": "Symbol", "pinned": "left", "minWidth": 90},
    {"field": "direction", "headerName": "Direction ✎", "pinned": "left", "cellClass": "cell-editable",
     "headerTooltip": "Click a cell to correct the direction or the operation type, or to edit a manual leg",
     "valueFormatter": {"function": "params.value || '—'"},
     "cellClassRules": {"dir-bull": "params.value === 'bull'", "dir-bear": "params.value === 'bear'"}},
    {"field": "flags", "headerName": "Flags", "tooltipField": "notes", "minWidth": 80},
    {"field": "capture", "headerName": "Capture", "minWidth": 110},
    {"field": "trade_date", "headerName": "Trade date", "minWidth": 110},
    {"field": "structure", "headerName": "Structure", "minWidth": 150},
    {"field": "strike", "headerName": "Strike"},
    {"field": "expiration", "headerName": "Expiration", "minWidth": 120},
    {"field": "premium_m", "headerName": "Premium (M)", "filter": "agNumberColumnFilter",
     "type": "rightAligned", "valueFormatter": number_format(3), "sort": "desc"},
    {"field": "net_price", "headerName": "Net price", "filter": "agNumberColumnFilter",
     "type": "rightAligned", "valueFormatter": number_format(2)},
    {"field": "aggressiveness", "headerName": "Aggr.", "filter": "agNumberColumnFilter",
     "type": "rightAligned", "valueFormatter": number_format(2)},
    {"field": "destination", "headerName": "Destination", "minWidth": 140},
    {"field": "wall", "headerName": "Wall"},
    {"field": "conditions", "headerName": "Conditions", "minWidth": 110},
    {"field": "start", "headerName": "Start", "minWidth": 110},
    {"field": "end", "headerName": "End", "minWidth": 110},
    {"field": "legs", "headerName": "Legs", "filter": "agNumberColumnFilter", "type": "rightAligned", "hide": True},
    {"field": "trades", "headerName": "Trades", "filter": "agNumberColumnFilter", "type": "rightAligned",
     "hide": True},
    {"field": "size", "headerName": "Size", "headerTooltip": "Contracts in the operation, all legs together",
     "filter": "agNumberColumnFilter", "type": "rightAligned", "valueFormatter": number_format(0), "hide": True},
    {"field": "duration_s", "headerName": "Duration (s)", "filter": "agNumberColumnFilter", "type": "rightAligned",
     "valueFormatter": number_format(1), "hide": True},
    {"field": "contract_volume", "headerName": "Contract volume",
     "headerTooltip": "Volume of the contract on the trade date; added up across legs",
     "filter": "agNumberColumnFilter", "type": "rightAligned", "valueFormatter": number_format(0), "hide": True},
    {"field": "volume_share", "headerName": "Share of volume (%)", "headerTooltip": "Size ÷ contract volume",
     "filter": "agNumberColumnFilter", "type": "rightAligned", "valueFormatter": number_format(1), "hide": True},
    {"field": "id", "headerName": "ID", "hide": True, "minWidth": 260},
    {"field": "script_direction", "headerName": "Script direction", "hide": True},
]

ALWAYS_SHOWN = "symbol"

# how the columns pop-up groups them; every column but Symbol is in one group
COLUMN_GROUPS = (
    ("Operation", ("direction", "flags", "capture", "trade_date", "structure", "strike", "expiration", "premium_m",
                   "net_price", "aggressiveness", "destination", "wall", "conditions", "start", "end", "legs",
                   "trades", "size", "duration_s")),
    ("Volume", ("contract_volume", "volume_share")),
    ("Technical", ("id", "script_direction")),
)


def column_label(field):
    header = next(col["headerName"] for col in COLUMN_DEFS if col["field"] == field)
    return header.replace(" ✎", "")


def factory_layout():
    return [{"colId": col["field"], "hide": col.get("hide", False)} for col in COLUMN_DEFS]


def _width(value):
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 else None


def layout_from_state(column_state):
    """The grid's columnState reduced to what a layout keeps: known columns in order, visibility and width."""
    known, layout = {col["field"] for col in COLUMN_DEFS}, []
    for entry in column_state or []:
        col_id = entry.get("colId") if isinstance(entry, dict) else None
        if col_id in known and col_id not in {e["colId"] for e in layout}:
            layout.append({"colId": col_id, "hide": bool(entry.get("hide"))}
                          | ({"width": _width(entry.get("width"))} if _width(entry.get("width")) else {}))
    return layout


def column_defs(layout=None):
    """
    Column definitions in a layout's order, visibility and widths, or the
    factory ones without a layout. Unknown columns are ignored, columns the
    layout does not know (added later) go at the end, hidden, and Symbol is
    always the first and always shown.
    """
    if not layout:
        return [dict(col) for col in COLUMN_DEFS]
    by_field, defs = {col["field"]: col for col in COLUMN_DEFS}, []
    for entry in layout:
        col = by_field.get(entry.get("colId")) if isinstance(entry, dict) else None
        if col is None or any(d["field"] == col["field"] for d in defs):
            continue
        defs.append(dict(col, hide=bool(entry.get("hide")))
                    | ({"width": _width(entry.get("width"))} if _width(entry.get("width")) else {}))
    placed = {d["field"] for d in defs}
    defs += [dict(col, hide=True) for col in COLUMN_DEFS if col["field"] not in placed]
    symbol = next(d for d in defs if d["field"] == ALWAYS_SHOWN)
    return [dict(symbol, hide=False)] + [d for d in defs if d is not symbol]


def with_visibility(layout, visible):
    """The layout with only the `visible` columns shown; Symbol is always shown."""
    return [dict(e, hide=e["colId"] != ALWAYS_SHOWN and e["colId"] not in visible) for e in layout]


def visible_by_group(layout):
    """The pop-up's ticks: the visible columns of each group."""
    shown = {e["colId"] for e in layout if not e.get("hide")}
    return [[field for field in fields if field in shown] for _, fields in COLUMN_GROUPS]


ROW_CLASS_RULES = {
    "row-undetermined": "['undetermined', 'undetermined multi-leg'].includes(params.data.destination)",
    "row-edited": "params.data.edited",
}
