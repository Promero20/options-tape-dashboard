"""
Datos sintéticos de nivel 1 y nivel 2 para los tests.

Son inventados y se escriben en el directorio temporal de cada test: el
repositorio no versiona ningún CSV. El escenario cubre los casos que importan
al script de nivel 3 (cruces multi-leg, troceado, calendar, patas
incompletas, operaciones con acciones, spread cero, colisión de milisegundo
con distinta Trade Condition, umbrales en sus límites...) y las rarezas de
calidad vistas en los datos reales. Se puede escribir con cualquiera de las
variantes de esquema conocidas (las de tape_dashboard.data.schemas).
"""

import csv
import random
from datetime import datetime, timezone

from tape_dashboard.data import schemas

TRADE_DATE = "2026-10-13"

CONDITION_TEXT = {
    "AUTO": "AUTO - (I) Transaction was executed electronically.",
    "ISOI": "ISOI - (S) Intermarket Sweep Order.",
    "SLAN": "SLAN - (a) Single Leg Auction Non ISO.",
    "MLET": "MLET - (f) Multi Leg auto-electronic trade.",
    "MLAT": "MLAT - (g) Multi Leg Auction.",
    "TLET": "TLET - (n) Stock Options auto-electronic trade.",
    "CANC": "CANC - (C) Transaction cancelled.",
}

# Precio del subyacente en el nivel 1. DDD no aparece: el script conserva sus
# operaciones aunque no pueda aplicar el umbral.
PRICES = {
    "AAA": 30.0,     # tramo de $500.000
    "BBB": 100.0,    # tramo de $1.000.000
    "CCC": 300.0,    # tramo de $3.000.000
    "EEE": 0.5,      # < $1: el script le aplica $3.000.000
    "FFF": 50.0,     # límite exacto: tramo de $1.000.000
    "GGG": 200.0,    # límite exacto: tramo de $3.000.000
    "HHH": 49.99,    # justo por debajo de $50: tramo de $500.000
}


def trade(symbol, exp_date, strike, option_type, time, price, size, bid, ask, condition,
          date=TRADE_DATE, exchange="CBOE"):
    """Una fila de Time & Sales con los nombres de columna canónicos del nivel 2."""
    mid = (bid + ask) / 2
    half_spread = (ask - bid) / 2
    aggressiveness = "" if half_spread == 0 else repr((price - mid) / half_spread)
    letter = "C" if option_type == "call" else "P"
    return {
        "symbol": symbol,
        "contract_symbol": f"{symbol}|{exp_date.replace('-', '')}|{strike:.2f}{letter}",
        "exp_date": exp_date,
        "strike": f"{strike:.2f}",
        "type": option_type,
        "fecha_consultada": date,
        "Time": f"{date} {time}",
        "Trade": repr(price),
        "Trade Size": str(size),
        "Exchange": exchange,
        "Bid": repr(bid),
        "Bid Size": "10",
        "Bid Exchange": "NASD",
        "Ask": repr(ask),
        "Ask Size": "10",
        "Ask Exchange": "NYSE",
        "Trade Condition": condition,
        "Trade Condition Full": CONDITION_TEXT[condition],
        "Premium": repr(round(price * size * 100, 2)),
        "mid": repr(mid),
        "half_spread": repr(half_spread),
        "agresividad": aggressiveness,
        "spread_cero": str(half_spread == 0),
        "es_cancelacion": str(condition == "CANC"),
    }


def scenario():
    """Lista de trades (dicts con columnas canónicas) del escenario completo."""
    t = []
    # AAA ($30): call comprada troceada (3 trades a menos de 120 s entre sí) ...
    t += [trade("AAA", "2026-11-20", 30, "call", "10:00:00.000", 5.0, 500, 4.9, 5.0, "AUTO"),
          trade("AAA", "2026-11-20", 30, "call", "10:01:00.000", 5.0, 500, 4.9, 5.0, "AUTO"),
          trade("AAA", "2026-11-20", 30, "call", "10:02:30.000", 5.05, 400, 4.9, 5.0, "AUTO")]
    # ... el mismo contrato 7,5 min después: operación aparte, bajo el umbral
    t += [trade("AAA", "2026-11-20", 30, "call", "10:10:00.000", 5.0, 100, 4.9, 5.0, "AUTO")]
    # ... y en el mismo milisegundo que el primero, pero con otra condición:
    # grupo distinto que solo se distingue en el ID por la Trade Condition
    t += [trade("AAA", "2026-11-20", 30, "call", "10:00:00.000", 4.9, 20, 4.9, 5.0, "ISOI")]
    # put vendida; su exchange trae un salto de línea, como en algunas capturas
    t += [trade("AAA", "2026-11-20", 25, "put", "11:30:00.500", 3.0, 2000, 3.0, 3.2, "SLAN",
                exchange="I\r")]
    # print multi-leg suelto en el mismo milisegundo que la vertical de BBB:
    # no se une a ella porque es otro subyacente
    t += [trade("AAA", "2026-11-20", 35, "call", "11:00:00.100", 1.0, 50, 0.95, 1.05, "MLET")]

    # BBB ($100): vertical de débito (cruce A) + un troceado de la pata
    # comprada (B) que el union-find une a la misma operación
    t += [trade("BBB", "2026-12-18", 100, "call", "11:00:00.100", 6.0, 2000, 5.8, 6.0, "MLET"),
          trade("BBB", "2026-12-18", 110, "call", "11:00:00.120", 2.0, 2000, 2.0, 2.2, "MLET"),
          trade("BBB", "2026-12-18", 100, "call", "11:01:00.000", 6.0, 500, 5.8, 6.0, "MLET")]
    # calendar: dos expiraciones, la salida lleva el carácter '→'
    t += [trade("BBB", "2026-11-20", 105, "call", "12:00:00.000", 3.0, 1500, 3.0, 3.1, "MLET"),
          trade("BBB", "2027-01-15", 105, "call", "12:00:00.000", 7.0, 1500, 6.9, 7.0, "MLET")]
    # multi-leg declarado con una sola pata capturada: patas incompletas
    t += [trade("BBB", "2026-12-18", 120, "call", "13:00:00.000", 4.0, 3000, 3.9, 4.1, "MLAT")]
    # spread cero (agresividad vacía) y premium exactamente en el umbral
    t += [trade("BBB", "2026-12-18", 90, "put", "14:00:00.000", 10.0, 1000, 10.0, 10.0, "AUTO")]
    # dos patas, una en la zona muerta: precio neto no calculable
    t += [trade("BBB", "2026-12-18", 95, "put", "14:30:00.000", 5.0, 2000, 4.9, 5.1, "MLET"),
          trade("BBB", "2026-12-18", 85, "put", "14:30:00.000", 2.0, 2000, 2.0, 2.1, "MLET")]

    # CCC ($300): opción + acciones (TLET), una sola pata de opción
    t += [trade("CCC", "2026-12-18", 300, "call", "10:30:00.000", 5.0, 10000, 4.9, 5.1, "TLET")]
    # tres patas (butterfly), cada una a 10 ms de la anterior
    t += [trade("CCC", "2026-11-20", 290, "call", "15:00:00.000", 15.0, 1000, 14.8, 15.0, "MLET"),
          trade("CCC", "2026-11-20", 300, "call", "15:00:00.010", 9.0, 2000, 9.0, 9.2, "MLET"),
          trade("CCC", "2026-11-20", 310, "call", "15:00:00.020", 5.0, 1000, 4.9, 5.0, "MLET")]
    # straddle comprado bajo el umbral de su tramo
    t += [trade("CCC", "2026-11-20", 300, "call", "15:30:00.000", 9.0, 1000, 8.9, 9.0, "MLET"),
          trade("CCC", "2026-11-20", 300, "put", "15:30:00.000", 8.0, 1000, 7.9, 8.0, "MLET")]
    # risk reversal: call comprada + put vendida
    t += [trade("CCC", "2026-11-20", 320, "call", "15:45:00.000", 4.0, 5000, 3.9, 4.0, "MLET"),
          trade("CCC", "2026-11-20", 280, "put", "15:45:00.000", 3.5, 5000, 3.5, 3.6, "MLET")]
    # otro día de trade dentro de la misma captura
    t += [trade("CCC", "2026-12-18", 300, "call", "09:31:00.000", 5.0, 7000, 4.9, 5.0, "AUTO",
                date="2026-10-14")]

    # sin precio en el nivel 1
    t += [trade("DDD", "2026-11-20", 50, "call", "10:00:00.000", 1.0, 100, 0.9, 1.0, "AUTO")]
    # umbrales en los límites del tramo
    t += [trade("EEE", "2026-11-20", 1, "call", "10:00:00.000", 1.5, 5000, 1.4, 1.5, "AUTO"),
          trade("FFF", "2026-11-20", 50, "call", "10:00:00.000", 3.0, 3000, 2.9, 3.0, "AUTO"),
          trade("GGG", "2026-11-20", 200, "call", "10:00:00.000", 5.0, 5000, 4.9, 5.0, "AUTO"),
          trade("HHH", "2026-11-20", 50, "call", "10:00:00.000", 3.0, 2000, 2.9, 3.0, "AUTO")]

    # rarezas de calidad: cotización cruzada (bid > ask) que luego se cancela,
    # una cancelación sin trade anulado localizable y una fila repetida
    t += [trade("HHH", "2026-11-20", 55, "call", "11:00:00.000", 1.0, 10, 1.05, 1.0, "AUTO"),
          trade("HHH", "2026-11-20", 55, "call", "11:30:00.000", 1.0, 10, 0.95, 1.05, "CANC"),
          trade("HHH", "2026-11-20", 55, "call", "13:00:00.000", 1.0, 13, 0.95, 1.05, "CANC")]
    duplicated = trade("HHH", "2026-11-20", 55, "call", "12:00:00.000", 1.0, 12, 0.95, 1.05, "AUTO")
    t += [duplicated, dict(duplicated)]

    # el tape suele llegar en orden descendente; aquí se baraja con
    # semilla fija para no depender del orden de entrada
    random.Random(20261016).shuffle(t)
    return t


# --- Nivel 2 -----------------------------------------------------------------

LEVEL2_VARIANTS = tuple(schemas.LEVEL2.variants)

# variante N2-B: nombres de columna alternativos
API_NAMES = {
    "Time": "tradeTime", "Trade": "lastPrice", "Trade Size": "tradeSize",
    "Exchange": "lastExchange", "Bid": "bidPrice", "Bid Size": "bidSize",
    "Bid Exchange": "bidExchange", "Ask": "askPrice", "Ask Size": "askSize",
    "Ask Exchange": "askExchange", "Trade Condition Full": "tradeCondition",
    "Trade Condition": "tradeConditionCode", "Premium": "premium",
}


def _us_date(iso):
    return datetime.strptime(iso, "%Y-%m-%d").strftime("%m/%d/%Y")


def write_level2(path, trades, variant="N2-E", header=None):
    """
    Escribe el nivel 2 con el encabezado de una variante conocida (o con uno
    arbitrario, para probar variantes nuevas). Las variantes con
    `es_metadata_footer` llevan además una fila sin hora y el pie de página de
    una descarga.
    """
    header = list(header or schemas.LEVEL2.variants[variant])
    rename = API_NAMES if variant == "N2-B" else {}
    rows = []
    for r in trades:
        row = {rename.get(k, k): v for k, v in r.items()}
        if variant == "N2-D":
            row["fecha_consultada"] = _us_date(r["fecha_consultada"])
        rows.append(row)
    if "es_metadata_footer" in header:
        for row in rows:
            row["es_metadata_footer"] = "False"
        rows.append(dict(dict.fromkeys(header, ""), es_metadata_footer="False"))
        rows.append(dict(dict.fromkeys(header, ""),
                         symbol="Exported on 10-13-2026",
                         es_metadata_footer="True"))
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# --- Nivel 1 -----------------------------------------------------------------

LEVEL1_VARIANTS = tuple(schemas.LEVEL1.variants)
LAST_TRADE = datetime(2026, 10, 12, 15, 59, 0)


def _last_trade(variant):
    if variant == "N1-A":
        return str(int(LAST_TRADE.replace(tzinfo=timezone.utc).timestamp()))
    if variant == "N1-C":
        return LAST_TRADE.strftime("%m/%d/%y")
    return LAST_TRADE.strftime("%Y-%m-%d %H:%M:%S")


def level1_rows(trades, prices=PRICES):
    """
    Filas canónicas del nivel 1: una por contrato del escenario con precio
    conocido (seleccionado y reconciliado), más un candidato no seleccionado y
    uno con el volumen repartido en dos fechas.
    """
    seen, rows = set(), []
    for r in sorted(trades, key=lambda r: r["contract_symbol"]):
        if r["symbol"] not in prices or r["contract_symbol"] in seen:
            continue
        seen.add(r["contract_symbol"])
        rows.append({
            "symbol": r["symbol"], "contract_symbol": r["contract_symbol"],
            "price": repr(prices[r["symbol"]]), "exp_date": r["exp_date"],
            "type": r["type"].capitalize(), "strike": str(float(r["strike"])),
            "moneyness": "-0.05", "bid": r["Bid"], "ask": r["Ask"], "volume": "1000",
            "open_interest": "5000", "oi_chg": "1000", "vol_oi": "0.2", "iv": "0.5",
            "delta": "0.5", "mid": r["mid"], "premium_estimado": "1000000.0", "dte": "30",
            "fecha_volumen": r["fecha_consultada"], "volumen_en_fecha": "1000",
            "ratio_reconciliacion": "1.0", "reconciliacion_fallida": "False",
            "reconciliacion_ambigua": "False",
        })
    if not rows:
        return rows
    rows.append(dict(rows[0], contract_symbol="AAA|20261218|40.00C", exp_date="2026-12-18",
                     type="Call", strike="40.0", fecha_volumen="", volumen_en_fecha="",
                     ratio_reconciliacion="", reconciliacion_fallida="", reconciliacion_ambigua=""))
    rows.append(dict(rows[0], contract_symbol="AAA|20261218|45.00C", exp_date="2026-12-18",
                     type="Call", strike="45.0", fecha_volumen="2026-10-13;2026-10-12"))
    return rows


def write_level1(path, trades, variant="N1-E", prices=PRICES, header=None):
    header = list(header or schemas.LEVEL1.variants[variant])
    rows = []
    for r in level1_rows(trades, prices):
        row = dict(r)
        if "option_symbol" in header:
            row["option_symbol"] = row.pop("contract_symbol")
        if "open_int" in header:
            row["open_int"] = row.pop("open_interest")
        if "last_trade_ts" in header:
            row["last_trade_ts"] = _last_trade(variant)
        else:
            row["last_trade"] = _last_trade(variant)
        rows.append(row)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_capture(folder, day, trades, level1_variant="N1-E", level2_variant="N2-E"):
    """Escribe el nivel 1 y el nivel 2 de una captura con los nombres de fichero del pipeline."""
    write_level1(folder / f"nivel1_candidatos_{day}.csv", trades, level1_variant)
    write_level2(folder / f"nivel2_trades_{day}.csv", trades, level2_variant)
