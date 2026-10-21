"""
Esquema canónico de cada CSV de entrada y variantes de encabezado conocidas.

Los CSV históricos no comparten esquema: cambian nombres de columna (p. ej.
`open_int`/`open_interest`, o `tradeTime`/`Time` en el nivel 2)
y su orden. Cada columna canónica declara los nombres alternativos que
acepta. Al leer un fichero:

- si falta una columna obligatoria, el fichero no se puede usar y se reporta
  con su nombre y las columnas que faltan;
- si el encabezado no coincide con ninguna variante conocida pero tiene las
  obligatorias, se usa y se avisa de que es una variante nueva.

El contrato completo (tipos y significado) está en docs/contrato-datos.md.
"""

from dataclasses import dataclass, field

from pipeline import nivel3_agrupar as n3


@dataclass(frozen=True)
class Column:
    name: str
    aliases: tuple[str, ...] = ()
    required: bool = False


@dataclass(frozen=True)
class Schema:
    level: str
    columns: tuple[Column, ...]
    variants: dict[str, tuple[str, ...]] = field(default_factory=dict)

    def column(self, name):
        return next(c for c in self.columns if c.name == name)


@dataclass
class HeaderMatch:
    mapping: dict[str, str]     # nombre canónico -> nombre en el fichero
    missing_required: list[str]
    missing_optional: list[str]
    unknown: list[str]          # columnas del fichero que el esquema no conoce
    variant: str | None         # variante conocida, o None si es nueva

    @property
    def usable(self):
        return not self.missing_required


def match_header(schema, fieldnames):
    fieldnames = list(fieldnames or [])
    mapping, missing_required, missing_optional = {}, [], []
    for col in schema.columns:
        actual = next((n for n in (col.name, *col.aliases) if n in fieldnames), None)
        if actual is not None:
            mapping[col.name] = actual
        elif col.required:
            missing_required.append(col.name)
        else:
            missing_optional.append(col.name)
    used = set(mapping.values())
    unknown = [n for n in fieldnames if n not in used]
    variant = next((v for v, header in schema.variants.items() if list(header) == fieldnames), None)
    return HeaderMatch(mapping, missing_required, missing_optional, unknown, variant)


def _script_aliases(name):
    """Alias que acepta el propio script de nivel 3 para una columna: una sola fuente."""
    return tuple(a for a in n3.ALIASES_COLUMNA[name] if a != name)


# --- Nivel 1: candidatos -----------------------------------------------------

_LEVEL1_BASE = (
    "symbol", "price", "exp_date", "type", "strike", "moneyness", "bid", "ask",
    "volume", "open_int", "oi_chg", "vol_oi", "iv", "delta",
)
_LEVEL1_TAIL = (
    "mid", "premium_estimado", "dte", "fecha_volumen", "volumen_en_fecha",
    "ratio_reconciliacion", "reconciliacion_fallida", "reconciliacion_ambigua",
)

LEVEL1 = Schema(
    level="nivel1",
    columns=(
        Column("symbol", required=True),
        # el contrato falta en algunas capturas: se reconstruye
        Column("contract_symbol", aliases=("option_symbol",)),
        Column("price", required=True),
        Column("exp_date", required=True),
        Column("type", required=True),
        Column("strike", required=True),
        Column("moneyness"),
        Column("bid"),
        Column("ask"),
        Column("volume"),
        Column("open_interest", aliases=("open_int",)),
        Column("oi_chg"),
        Column("vol_oi"),
        Column("iv"),
        Column("delta"),
        Column("last_trade", aliases=("last_trade_ts",)),
        Column("mid"),
        Column("premium_estimado"),
        Column("dte"),
        Column("fecha_volumen"),
        Column("volumen_en_fecha"),
        Column("ratio_reconciliacion"),
        Column("reconciliacion_fallida"),
        Column("reconciliacion_ambigua"),
    ),
    variants={
        "N1-A": ("symbol", "contract_symbol", "price", "exp_date", "type", "strike", "moneyness",
                 "bid", "ask", "volume", "open_int", "oi_chg", "vol_oi", "iv", "delta",
                 "last_trade_ts") + _LEVEL1_TAIL,
        "N1-B": _LEVEL1_BASE + ("last_trade",) + _LEVEL1_TAIL,
        "N1-C": ("symbol", "option_symbol", "price", "exp_date", "type", "strike", "moneyness",
                 "bid", "ask", "volume", "open_interest", "oi_chg", "vol_oi", "iv", "delta",
                 "last_trade") + _LEVEL1_TAIL,
        "N1-D": _LEVEL1_BASE + ("contract_symbol",) + _LEVEL1_TAIL,
        "N1-E": _LEVEL1_BASE + ("contract_symbol",) + _LEVEL1_TAIL + ("last_trade",),
    },
)

# --- Nivel 2: Time & Sales ---------------------------------------------------

LEVEL2 = Schema(
    level="nivel2",
    columns=(
        # identificación del contrato: el script las exige sin alias
        Column("symbol", required=True),
        Column("contract_symbol", required=True),
        Column("exp_date", required=True),
        Column("strike", required=True),
        Column("type", required=True),
        Column("fecha_consultada"),
        # trade: mismos alias que acepta el script
        Column("Time", aliases=_script_aliases("Time"), required=True),
        Column("Trade", aliases=_script_aliases("Trade"), required=True),
        Column("Trade Size", aliases=_script_aliases("Trade Size"), required=True),
        Column("Exchange", aliases=("lastExchange",)),
        Column("Bid", aliases=_script_aliases("Bid"), required=True),
        Column("Bid Size", aliases=("bidSize",)),
        Column("Bid Exchange", aliases=("bidExchange",)),
        Column("Ask", aliases=_script_aliases("Ask"), required=True),
        Column("Ask Size", aliases=("askSize",)),
        Column("Ask Exchange", aliases=("askExchange",)),
        # en la variante de la API, `tradeCondition` es el texto largo y
        # `tradeConditionCode` el código: no confundirlas
        Column("Trade Condition", aliases=_script_aliases("Trade Condition"), required=True),
        Column("Trade Condition Full", aliases=("tradeCondition",)),
        Column("Premium", aliases=_script_aliases("Premium"), required=True),
        Column("mid"),
        Column("half_spread"),
        Column("agresividad", required=True),
        Column("spread_cero"),
        Column("es_cancelacion"),
        Column("es_metadata_footer"),
    ),
    variants={
        "N2-A": ("symbol", "contract_symbol", "type", "strike", "exp_date", "fecha_consultada",
                 "Time", "Trade", "Trade Size", "Exchange", "Bid", "Bid Size", "Bid Exchange",
                 "Ask", "Ask Size", "Ask Exchange", "Trade Condition", "Premium", "mid",
                 "half_spread", "agresividad", "spread_cero", "es_cancelacion",
                 "es_metadata_footer"),
        "N2-B": ("symbol", "contract_symbol", "exp_date", "strike", "type", "fecha_consultada",
                 "tradeTime", "lastPrice", "tradeSize", "lastExchange", "bidPrice", "bidSize",
                 "bidExchange", "askPrice", "askSize", "askExchange", "tradeCondition",
                 "tradeConditionCode", "premium", "mid", "half_spread", "spread_cero",
                 "agresividad", "es_cancelacion"),
        "N2-C": ("symbol", "contract_symbol", "exp_date", "strike", "type", "fecha_consultada",
                 "Time", "Trade", "Trade Size", "Exchange", "Bid", "Bid Size", "Bid Exchange",
                 "Ask", "Ask Size", "Ask Exchange", "Trade Condition", "Trade Condition Full",
                 "Premium", "mid", "half_spread", "spread_cero", "agresividad", "es_cancelacion",
                 "es_metadata_footer"),
        "N2-D": ("symbol", "contract_symbol", "exp_date", "strike", "type", "fecha_consultada",
                 "Time", "Trade", "Trade Size", "Exchange", "Bid", "Bid Size", "Bid Exchange",
                 "Ask", "Ask Size", "Ask Exchange", "Trade Condition", "Premium", "mid",
                 "half_spread", "agresividad", "spread_cero", "es_cancelacion"),
        "N2-E": ("symbol", "contract_symbol", "exp_date", "strike", "type", "fecha_consultada",
                 "Time", "Trade", "Trade Size", "Exchange", "Bid", "Bid Size", "Bid Exchange",
                 "Ask", "Ask Size", "Ask Exchange", "Trade Condition", "Trade Condition Full",
                 "Premium", "mid", "half_spread", "agresividad", "spread_cero", "es_cancelacion"),
    },
)

# --- Nivel 3: operaciones (solo para validar la reconstrucción) --------------

LEVEL3_CURRENT = (
    "symbol", "estructura", "n_patas", "n_trades", "size_total", "premium_total_M",
    "precio_neto", "precio_neto_metodo", "agresividad_pond", "direccion", "trade_conditions",
    "multi_leg_declarado", "patas_incompletas", "stock_option", "hora_inicio", "hora_fin",
    "duracion_s", "strike", "fecha_expiracion", "fecha_operacion",
)

LEVEL3 = Schema(
    level="nivel3",
    columns=tuple(Column(name, required=True) for name in LEVEL3_CURRENT),
    variants={
        # versiones antiguas del script: sin filtro por umbral ni precio neto
        "N3-A": ("symbol", "estructura", "n_patas", "n_trades", "size_total", "premium_total",
                 "agresividad_pond", "direccion", "trade_conditions", "multi_leg_declarado",
                 "patas_incompletas", "stock_option", "hora_inicio", "hora_fin", "duracion_s",
                 "patas"),
        # con precio neto, pero sin strike, expiración ni fecha de operación
        "N3-B": ("symbol", "estructura", "n_patas", "n_trades", "size_total", "premium_total_M",
                 "precio_neto", "precio_neto_metodo", "agresividad_pond", "direccion",
                 "trade_conditions", "multi_leg_declarado", "patas_incompletas", "stock_option",
                 "hora_inicio", "hora_fin", "duracion_s", "patas"),
        "N3-C": LEVEL3_CURRENT,
    },
)
