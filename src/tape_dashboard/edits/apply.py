"""
Aplicación de las ediciones manuales sobre las operaciones reconstruidas.

Orden, como pide la especificación: se reconstruyen todas las operaciones,
se añaden las patas manuales (recalculando con las funciones del script), se
clasifica con las correcciones del usuario y, al final, se filtra por umbral.
"""

from dataclasses import dataclass, replace

from pipeline import nivel3_agrupar as n3

from ..data.loading import build_contract_symbol
from ..rules.classification import PENDING, Override, classify


@dataclass(frozen=True)
class ClassifiedOperation:
    operation: object                 # Operation, con las patas manuales ya incluidas
    classification: object            # Classification
    override: Override | None = None
    manual_legs: tuple = ()           # ManualLeg aplicadas
    problems: tuple = ()              # ediciones que no se han podido aplicar

    @property
    def edited(self):
        return self.override is not None or bool(self.manual_legs)


def _manual_trade_row(operation, leg):
    """
    Una pata manual como fila de trade, para que el script la agrupe con las
    demás. Sin agresividad (decisión 0011): el lado lo fija el tipo de
    operación que elige el usuario. Hora y Trade Condition son las del primer
    trade, así que el ID de la operación no cambia.
    """
    first = min(operation.trades, key=lambda r: r["t"])
    existing = operation.legs[0]
    # mismo formato de tipo y strike que las patas del fichero: el script
    # compara esos textos para reconocer la estructura
    option_type = leg.option_type.capitalize() if existing["type"][:1].isupper() else leg.option_type
    strike = next((l["strike"] for l in operation.legs if float(l["strike"]) == leg.strike),
                  f"{leg.strike:.2f}")
    contract = build_contract_symbol(operation.symbol, leg.exp_date, leg.strike, leg.option_type)
    if any(l["contract_symbol"] == contract for l in operation.legs):
        raise ValueError(f"manual leg {leg.id} repeats the operation's contract {contract}")
    return {
        "symbol": operation.symbol, "contract_symbol": contract, "type": option_type,
        "strike": strike, "exp_date": leg.exp_date, "Time": first["Time"],
        "Trade": repr(float(leg.price)), "Trade Size": str(int(leg.size)), "Bid": "", "Ask": "",
        "Trade Condition": first["Trade Condition"],
        "Premium": repr(round(leg.price * leg.size * 100, 2)), "agresividad": "",
    }


def with_manual_legs(operation, legs):
    """La operación con sus patas manuales, recalculada con el script."""
    if not legs:
        return operation
    rows = [_manual_trade_row(operation, leg) for leg in legs]
    group = operation.trades + n3.preparar_filas(rows, list(rows[0]))
    summary = n3.resumen(group)
    return replace(operation, summary=summary, legs=n3.patas_de(group), trades=group,
                   passes_threshold=n3.pasa_umbral(summary["premium_total"], operation.price))


def apply_edits(operations, edits):
    """Aplica patas manuales y correcciones; devuelve las operaciones clasificadas."""
    result = []
    for op in operations:
        legs = tuple(edits.manual_legs.get(op.id, ()))
        override = edits.overrides.get(op.id)
        problems = ()
        try:
            edited = with_manual_legs(op, legs)
        except ValueError as error:
            # una pata mal formada no debe tumbar la carga: se muestra
            edited, legs, problems = op, (), (str(error),)
        result.append(ClassifiedOperation(edited, classify(edited, override), override, legs, problems))
    return result


def classified_operations(dataset, edits, start, end):
    """
    Operaciones del rango de fechas de captura para la pestaña 1 y los
    gráficos: con las ediciones aplicadas, por encima del umbral y sin las
    pendientes de completar.
    """
    classified = apply_edits(dataset.operations(start, end, passing_only=False), edits)
    return [c for c in classified
            if c.operation.passes_threshold and c.classification.destination != PENDING]


def pending_operations(dataset, edits, day):
    """Operaciones de una captura con patas por completar y por encima del umbral (pestaña 2)."""
    capture = dataset.captures.get(day)
    if capture is None or not capture.usable:
        return []
    classified = apply_edits(capture.operations, edits)
    return [c for c in classified
            if c.operation.passes_threshold and c.classification.destination == PENDING]


@dataclass(frozen=True)
class Orphan:
    kind: str           # "correction" o "manual leg"
    operation_id: str
    detail: str


def orphans(dataset, edits):
    """Ediciones cuyo ID de operación no existe en ninguna captura. No se borran."""
    known = {op.id for day in dataset.usable_dates for op in dataset.captures[day].operations}
    found = []
    for op_id, override in sorted(edits.overrides.items()):
        if op_id not in known:
            found.append(Orphan("correction", op_id, override.direction or override.strategy))
    for op_id, legs in sorted(edits.manual_legs.items()):
        if op_id not in known:
            for leg in legs:
                found.append(Orphan("manual leg", op_id,
                                    f"{leg.option_type} {leg.strike:g} {leg.exp_date} ×{leg.size} at {leg.price:g}"))
    return found
