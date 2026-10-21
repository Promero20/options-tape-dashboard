"""
Lectura y normalización de los CSV de nivel 1 y nivel 2.

Los ficheros se abren solo para lectura. Las columnas se renombran a su
nombre canónico (ver schemas.py) y los valores se normalizan, con una
excepción: las columnas del nivel 2 que consume el script de nivel 3 se le
pasan con su valor original, para que la reconstrucción sea idéntica a la del
pipeline.
"""

import collections
import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from . import schemas
from .issues import INFO, WARNING, Issue


class SchemaError(Exception):
    """El fichero no tiene las columnas obligatorias de su nivel."""

    def __init__(self, path, missing, available):
        self.file = Path(path).name
        self.missing = list(missing)
        self.available = list(available)
        super().__init__(
            f"{self.file}: faltan columnas obligatorias: {', '.join(self.missing)}. "
            f"Columnas del fichero: {', '.join(self.available) or '(ninguna)'}")


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _header_issues(path, match):
    """Avisos sobre el encabezado: variante nueva, columnas que faltan o sobran."""
    issues = []
    if match.variant is None:
        detail = []
        if match.missing_optional:
            detail.append(f"faltan columnas opcionales: {', '.join(match.missing_optional)}")
        if match.unknown:
            detail.append(f"columnas desconocidas (no se cargan): {', '.join(match.unknown)}")
        issues.append(Issue(WARNING, Path(path).name,
                            "variante de encabezado nueva" + (f"; {'; '.join(detail)}" if detail else "")))
    return issues


def _match_or_fail(schema, path, fieldnames):
    match = schemas.match_header(schema, fieldnames)
    if not match.usable:
        raise SchemaError(path, match.missing_required, fieldnames)
    return match


class _Parser:
    """Convierte valores y cuenta los que no se pueden interpretar, por columna."""

    def __init__(self):
        self.failures = collections.Counter()

    def __call__(self, column, value, convert):
        if value is None or value.strip() == "":
            return None
        try:
            return convert(value.strip())
        except ValueError:
            self.failures[column] += 1
            return None

    def issues(self, path):
        return [Issue(WARNING, Path(path).name, f"{n} valores no interpretables en '{col}'")
                for col, n in sorted(self.failures.items())]


def _iso_date(value):
    return date.fromisoformat(value).isoformat()


def _option_type(value):
    v = value.lower()
    if v not in ("call", "put"):
        raise ValueError(value)
    return v


def _boolean(value):
    v = value.lower()
    if v not in ("true", "false"):
        raise ValueError(value)
    return v == "true"


def _integer(value):
    return int(float(value))


def _last_trade_date(value):
    """
    Fecha del último trade. Ha llegado como epoch en segundos, como
    'YYYY-MM-DD HH:MM:SS', como 'YYYY-MM-DD' o como 'MM/DD/YY'. Solo se
    conserva la fecha: la hora no es comparable entre formatos y el dashboard
    no la usa. El epoch se interpreta en UTC, que coincide con la fecha de
    Nueva York en horario de mercado.
    """
    if value.isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc).date().isoformat()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(value)


def _volume_dates(value):
    """`fecha_volumen`: una o varias fechas separadas por ';', en cualquier orden."""
    return sorted(_iso_date(d.strip()) for d in value.split(";") if d.strip())


def build_contract_symbol(symbol, exp_date, strike, option_type):
    """Formato del contrato: 'AAPL|20261120|250.00C'."""
    return f"{symbol}|{exp_date.replace('-', '')}|{strike:.2f}{'C' if option_type == 'call' else 'P'}"


# --- Nivel 1 -----------------------------------------------------------------

LEVEL1_FLOATS = ("price", "strike", "moneyness", "bid", "ask", "vol_oi", "iv", "delta", "mid",
                 "premium_estimado", "ratio_reconciliacion")
LEVEL1_INTEGERS = ("volume", "open_interest", "oi_chg", "dte", "volumen_en_fecha")


@dataclass
class Level1Data:
    path: Path
    variant: str | None
    rows: list[dict]
    prices: dict[str, float]          # precio del subyacente por símbolo
    contract_rebuilt: bool            # el fichero no traía columna de contrato
    issues: list[Issue] = field(default_factory=list)


def load_level1(path):
    fieldnames, raw_rows = read_csv(path)
    match = _match_or_fail(schemas.LEVEL1, path, fieldnames)
    issues = _header_issues(path, match)
    parse = _Parser()
    m = match.mapping
    rows, prices = [], {}
    for raw in raw_rows:
        get = lambda col: raw.get(m[col]) if col in m else None
        row = {"symbol": get("symbol").strip()}
        for col in LEVEL1_FLOATS:
            row[col] = parse(col, get(col), float)
        for col in LEVEL1_INTEGERS:
            row[col] = parse(col, get(col), _integer)
        row["type"] = parse("type", get("type"), _option_type)
        row["exp_date"] = parse("exp_date", get("exp_date"), _iso_date)
        row["fecha_volumen"] = parse("fecha_volumen", get("fecha_volumen"), _volume_dates) or []
        row["reconciliacion_fallida"] = parse("reconciliacion_fallida", get("reconciliacion_fallida"), _boolean)
        row["reconciliacion_ambigua"] = parse("reconciliacion_ambigua", get("reconciliacion_ambigua"), _boolean)
        row["last_trade"] = parse("last_trade", get("last_trade"), _last_trade_date)

        contract = (get("contract_symbol") or "").strip()
        if not contract and None not in (row["exp_date"], row["strike"], row["type"]):
            contract = build_contract_symbol(row["symbol"], row["exp_date"], row["strike"], row["type"])
        row["contract_symbol"] = contract or None

        if row["price"] is not None:
            # como el script: el primer precio de cada símbolo
            prices.setdefault(row["symbol"], row["price"])
        rows.append(row)

    rebuilt = "contract_symbol" not in m
    if rebuilt:
        issues.append(Issue(INFO, Path(path).name, "sin columna de contrato: se reconstruye"))
    return Level1Data(Path(path), match.variant, rows, prices, rebuilt, issues + parse.issues(path))


# --- Nivel 2 -----------------------------------------------------------------

EXCHANGE_COLUMNS = ("Exchange", "Bid Exchange", "Ask Exchange")


@dataclass
class Level2Data:
    path: Path
    variant: str | None
    fieldnames: list[str]   # nombres canónicos presentes, en el orden del esquema
    rows: list[dict]        # una fila por trade, con nombres canónicos
    issues: list[Issue] = field(default_factory=list)


def _consultation_date(value):
    """`fecha_consultada` aparece como 'YYYY-MM-DD' o como 'MM/DD/YYYY'."""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            pass
    raise ValueError(value)


def load_level2(path):
    fieldnames, raw_rows = read_csv(path)
    match = _match_or_fail(schemas.LEVEL2, path, fieldnames)
    issues = _header_issues(path, match)
    canonical = [c.name for c in schemas.LEVEL2.columns if c.name in match.mapping]
    parse = _Parser()
    reformatted_dates = trimmed_exchanges = 0

    rows = []
    for raw in raw_rows:
        row = {name: raw[match.mapping[name]] for name in canonical}
        # Columnas que no consume el script: se normalizan aquí.
        if row.get("fecha_consultada"):
            iso = parse("fecha_consultada", row["fecha_consultada"], _consultation_date)
            if iso is not None and iso != row["fecha_consultada"]:
                reformatted_dates += 1
            row["fecha_consultada"] = iso
        for col in EXCHANGE_COLUMNS:
            if col in row and row[col] != row[col].strip():
                row[col] = row[col].strip()
                trimmed_exchanges += 1
        rows.append(row)

    name = Path(path).name
    if reformatted_dates:
        issues.append(Issue(INFO, name, f"fecha_consultada en formato MM/DD/YYYY: "
                                        f"{reformatted_dates} filas normalizadas a ISO"))
    if trimmed_exchanges:
        issues.append(Issue(INFO, name, f"{trimmed_exchanges} códigos de exchange con espacios o "
                                        f"saltos de línea: recortados"))
    return Level2Data(Path(path), match.variant, canonical, rows, issues + parse.issues(path))
