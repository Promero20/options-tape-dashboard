"""
Almacén de ediciones manuales (decisiones 0003 y 0019).

Un fichero SQLite en la carpeta de datos del usuario, nunca en la de datos del pipeline
ni en git. Cada edición apunta a un ID de operación; si el ID deja de
existir, la edición queda huérfana y se muestra para revisarla, pero no se
borra. El esquema está en docs/data-contract.md.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ..rules import strategies
from ..rules.classification import BEAR, BULL, UNDETERMINED, Override

FILE_NAME = "ediciones.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS overrides (
    operation_id TEXT PRIMARY KEY,
    direction    TEXT CHECK (direction IN ('bull', 'bear', 'indeterminado')),
    strategy     TEXT,
    updated_at   TEXT NOT NULL,
    CHECK ((direction IS NULL) <> (strategy IS NULL))
);
CREATE TABLE IF NOT EXISTS manual_legs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    operation_id TEXT NOT NULL,
    option_type  TEXT NOT NULL CHECK (option_type IN ('call', 'put')),
    strike       REAL NOT NULL CHECK (strike > 0),
    exp_date     TEXT NOT NULL,
    price        REAL NOT NULL CHECK (price >= 0),
    size         INTEGER NOT NULL CHECK (size > 0),
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS manual_legs_by_operation ON manual_legs (operation_id);
"""


@dataclass(frozen=True)
class ManualLeg:
    id: int
    operation_id: str
    option_type: str
    strike: float
    exp_date: str
    price: float
    size: int


@dataclass(frozen=True)
class Edits:
    """Instantánea de todas las ediciones, para aplicarlas sin tocar la base de datos."""
    overrides: dict          # id de operación -> Override
    manual_legs: dict        # id de operación -> [ManualLeg]

    @classmethod
    def empty(cls):
        return cls({}, {})


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _validate_leg(option_type, strike, exp_date, price, size):
    if option_type not in ("call", "put"):
        raise ValueError(f"tipo de opción no válido: {option_type!r}")
    date.fromisoformat(exp_date)
    if strike <= 0 or price < 0 or size <= 0 or int(size) != size:
        raise ValueError("strike y tamaño deben ser positivos, el tamaño entero y el precio no negativo")


class EditStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)

    def _connect(self):
        return sqlite3.connect(self.path)

    # --- correcciones de dirección o de tipo de operación ---------------

    def set_direction(self, operation_id, direction):
        if direction not in (BULL, BEAR, UNDETERMINED):
            raise ValueError(f"dirección no válida: {direction!r}")
        self._set_override(operation_id, direction, None)

    def set_strategy(self, operation_id, strategy):
        if strategy not in strategies.BY_KEY:
            raise ValueError(f"tipo de operación desconocido: {strategy!r}")
        self._set_override(operation_id, None, strategy)

    def _set_override(self, operation_id, direction, strategy):
        with self._connect() as db:
            db.execute(
                "INSERT INTO overrides (operation_id, direction, strategy, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (operation_id) DO UPDATE SET direction = excluded.direction, "
                "strategy = excluded.strategy, updated_at = excluded.updated_at",
                (operation_id, direction, strategy, _now()))

    def clear_override(self, operation_id):
        with self._connect() as db:
            db.execute("DELETE FROM overrides WHERE operation_id = ?", (operation_id,))

    # --- patas añadidas a mano -------------------------------------------

    def add_manual_leg(self, operation_id, option_type, strike, exp_date, price, size):
        _validate_leg(option_type, strike, exp_date, price, size)
        now = _now()
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO manual_legs (operation_id, option_type, strike, exp_date, price, size, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (operation_id, option_type, float(strike), exp_date, float(price), int(size), now, now))
            return cursor.lastrowid

    def update_manual_leg(self, leg_id, option_type, strike, exp_date, price, size):
        _validate_leg(option_type, strike, exp_date, price, size)
        with self._connect() as db:
            cursor = db.execute(
                "UPDATE manual_legs SET option_type = ?, strike = ?, exp_date = ?, price = ?, size = ?, "
                "updated_at = ? WHERE id = ?",
                (option_type, float(strike), exp_date, float(price), int(size), _now(), leg_id))
            if cursor.rowcount == 0:
                raise KeyError(f"no existe la pata manual {leg_id}")

    def delete_manual_leg(self, leg_id):
        with self._connect() as db:
            db.execute("DELETE FROM manual_legs WHERE id = ?", (leg_id,))

    # --- lectura ----------------------------------------------------------

    def snapshot(self):
        with self._connect() as db:
            return _read(db)


def _read(db):
    overrides = {op_id: Override(direction, strategy)
                 for op_id, direction, strategy in db.execute(
                     "SELECT operation_id, direction, strategy FROM overrides")}
    legs = {}
    for row in db.execute("SELECT id, operation_id, option_type, strike, exp_date, price, size "
                          "FROM manual_legs ORDER BY id"):
        leg = ManualLeg(*row)
        legs.setdefault(leg.operation_id, []).append(leg)
    return Edits(overrides, legs)


def read_edits(path):
    """Lee las ediciones sin crear ni modificar nada; vacías si el fichero no existe."""
    path = Path(path)
    if not path.is_file():
        return Edits.empty()
    db = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return _read(db)
    finally:
        db.close()
