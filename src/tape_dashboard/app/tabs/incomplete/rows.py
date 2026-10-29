"""Rows and columns of the incomplete-legs list (tab 2)."""

from ....rules.sides import leg_side
from ..operations.rows import number_format

M = 1_000_000


def pending_row(item):
    """One row per operation with a missing leg: the known leg is what the user has to go on."""
    op, s = item.operation, item.operation.summary
    known = op.legs[0]
    return {
        "id": op.id,
        "symbol": op.symbol,
        "contract": known["contract_symbol"],
        "conditions": s["trade_conditions"],
        "size": s["size_total"],
        "premium_m": round(op.premium / M, 3),
        "aggressiveness": None if known["agr"] is None else round(known["agr"], 2),
        "measured_side": leg_side(known["agr"]) or "undetermined",
        "price": op.price,
        "start": s["hora_inicio"],
        "end": s["hora_fin"],
        "trade_date": ", ".join(d.isoformat() for d in op.trade_dates),
        "flags": "ⓘ" if item.problems else "",
        "notes": " · ".join(item.problems),
    }


COLUMN_DEFS = [
    {"field": "symbol", "headerName": "Symbol", "pinned": "left", "minWidth": 90},
    {"field": "contract", "headerName": "Known leg", "minWidth": 170},
    {"field": "conditions", "headerName": "Conditions", "minWidth": 110},
    {"field": "size", "headerName": "Size", "filter": "agNumberColumnFilter", "type": "rightAligned",
     "valueFormatter": number_format(0)},
    {"field": "premium_m", "headerName": "Premium (M)", "filter": "agNumberColumnFilter",
     "type": "rightAligned", "valueFormatter": number_format(3), "sort": "desc"},
    {"field": "aggressiveness", "headerName": "Aggr.", "filter": "agNumberColumnFilter",
     "type": "rightAligned", "valueFormatter": number_format(2)},
    {"field": "measured_side", "headerName": "Measured side"},
    {"field": "price", "headerName": "Underlying", "filter": "agNumberColumnFilter", "type": "rightAligned",
     "valueFormatter": number_format(2)},
    {"field": "start", "headerName": "Start", "minWidth": 110},
    {"field": "end", "headerName": "End", "minWidth": 110},
    {"field": "trade_date", "headerName": "Trade date", "minWidth": 110},
    {"field": "flags", "headerName": "Flags", "tooltipField": "notes", "minWidth": 80},
]


def known_leg_text(op):
    known = op.legs[0]
    aggr = "no aggressiveness" if known["agr"] is None else f"aggressiveness {known['agr']:+.2f}"
    side = leg_side(known["agr"]) or "undetermined"
    price = f", underlying {op.price:g}" if op.price is not None else ""
    return (f"Known leg: {known['contract_symbol']}, {known['size']:,} at {known['precio_medio']:.2f} "
            f"({known['premium'] / M:.3f}M), {aggr} ({side}); {op.summary['trade_conditions']}{price}.")
