"""
Real positions, in their own SQLite file in the user-data folder (decision 0031).

Every write is one transaction and validates first, so an invalid edit leaves
nothing behind. `source` and `external_id` are there for a future read-only
import: an imported position can be recognised instead of duplicated.
"""

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from ..rules.sides import BUY, SELL

FILE_NAME = "positions.sqlite"
MANUAL = "manual"

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    opened_on    TEXT NOT NULL,
    commissions  REAL NOT NULL DEFAULT 0 CHECK (commissions >= 0),
    notes        TEXT NOT NULL DEFAULT '',
    operation_id TEXT,
    source       TEXT NOT NULL DEFAULT 'manual',
    external_id  TEXT,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    UNIQUE (source, external_id)
);
CREATE TABLE IF NOT EXISTS position_legs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id  INTEGER NOT NULL REFERENCES positions (id) ON DELETE CASCADE,
    symbol       TEXT NOT NULL,
    option_type  TEXT NOT NULL CHECK (option_type IN ('call', 'put')),
    strike       REAL NOT NULL CHECK (strike > 0),
    exp_date     TEXT NOT NULL,
    side         TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    entry_price  REAL NOT NULL CHECK (entry_price >= 0),
    exit_date    TEXT,
    exit_price   REAL CHECK (exit_price >= 0),
    CHECK ((exit_date IS NULL) = (exit_price IS NULL))
);
CREATE INDEX IF NOT EXISTS legs_by_position ON position_legs (position_id);
"""


@dataclass(frozen=True)
class Leg:
    symbol: str
    option_type: str        # call / put
    strike: float
    exp_date: str           # ISO date
    side: str               # buy / sell
    quantity: int
    entry_price: float
    exit_date: str | None = None
    exit_price: float | None = None
    id: int | None = None

    @property
    def closed(self):
        return self.exit_date is not None


@dataclass(frozen=True)
class Position:
    id: int
    opened_on: str          # ISO date
    commissions: float      # total of the position: opening and closing
    notes: str
    operation_id: str | None
    source: str
    external_id: str | None
    legs: tuple


def _is_date(value):
    try:
        date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def check(opened_on, legs, commissions):
    """Every reason not to store this position; empty if it can be stored."""
    errors = []
    if not _is_date(opened_on):
        errors.append("The opening date is not valid.")
    if commissions < 0:
        errors.append("Commissions cannot be negative.")
    if not legs:
        errors.append("A position needs at least one leg.")
    for number, leg in enumerate(legs, 1):
        errors += [f"Leg {number}: {problem}" for problem in _leg_problems(leg, opened_on)]
    return errors


def _leg_problems(leg, opened_on):
    problems = []
    if not leg.symbol.strip():
        problems.append("the underlying is missing.")
    if leg.option_type not in ("call", "put"):
        problems.append("choose call or put.")
    if leg.side not in (BUY, SELL):
        problems.append("choose buy or sell.")
    if leg.strike <= 0:
        problems.append("the strike must be above 0.")
    if leg.quantity <= 0 or int(leg.quantity) != leg.quantity:
        problems.append("the quantity must be a whole number above 0.")
    if leg.entry_price < 0:
        problems.append("the entry price cannot be negative.")
    if not _is_date(leg.exp_date):
        problems.append("the expiration date is not valid.")
    elif _is_date(opened_on) and leg.exp_date < opened_on:
        problems.append("it expires before the position was opened.")
    return problems + _exit_problems(leg.exit_date, leg.exit_price, opened_on)


def _exit_problems(exit_date, exit_price, opened_on):
    if exit_date is None and exit_price is None:
        return []
    if exit_date is None or exit_price is None:
        return ["a close needs both a date and a price."]
    problems = []
    if exit_price < 0:
        problems.append("the closing price cannot be negative.")
    if not _is_date(exit_date):
        problems.append("the closing date is not valid.")
    elif _is_date(opened_on) and exit_date < opened_on:
        problems.append("it closes before the position was opened.")
    return problems


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _insert_legs(db, position_id, legs):
    db.executemany(
        "INSERT INTO position_legs (position_id, symbol, option_type, strike, exp_date, side, quantity, "
        "entry_price, exit_date, exit_price) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(position_id, leg.symbol.strip().upper(), leg.option_type, float(leg.strike), leg.exp_date, leg.side,
          int(leg.quantity), float(leg.entry_price), leg.exit_date,
          None if leg.exit_price is None else float(leg.exit_price)) for leg in legs])


class PositionStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path)
        try:
            db.execute("PRAGMA foreign_keys = ON")
            with db:
                yield db
        finally:
            db.close()

    def create(self, opened_on, legs, commissions=0.0, notes="", operation_id=None, source=MANUAL, external_id=None):
        errors = check(opened_on, legs, commissions)
        if errors:
            raise ValueError(" ".join(errors))
        now = _now()
        with self._db() as db:
            cursor = db.execute(
                "INSERT INTO positions (opened_on, commissions, notes, operation_id, source, external_id, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (opened_on, float(commissions), notes, operation_id, source, external_id, now, now))
            _insert_legs(db, cursor.lastrowid, legs)
            return cursor.lastrowid

    def update(self, position_id, opened_on, legs, commissions=0.0, notes="", operation_id=None):
        """Replaces the position's data and legs; each leg carries its own close, if it has one."""
        errors = check(opened_on, legs, commissions)
        if errors:
            raise ValueError(" ".join(errors))
        with self._db() as db:
            cursor = db.execute(
                "UPDATE positions SET opened_on = ?, commissions = ?, notes = ?, operation_id = ?, updated_at = ? "
                "WHERE id = ?", (opened_on, float(commissions), notes, operation_id, _now(), position_id))
            if cursor.rowcount == 0:
                raise KeyError(f"position {position_id} does not exist")
            db.execute("DELETE FROM position_legs WHERE position_id = ?", (position_id,))
            _insert_legs(db, position_id, legs)

    def set_exits(self, position_id, exits):
        """Closes or reopens legs: {leg id: (exit date, exit price), or None to reopen it}."""
        position = self.get(position_id)
        if position is None:
            raise KeyError(f"position {position_id} does not exist")
        ids = {leg.id for leg in position.legs}
        errors = [f"leg {leg_id} is not part of this position." for leg_id in exits if leg_id not in ids]
        for number, leg in enumerate(position.legs, 1):
            if exits.get(leg.id) is not None:
                exit_date, exit_price = exits[leg.id]
                errors += [f"Leg {number}: {p}" for p in _exit_problems(exit_date, exit_price, position.opened_on)]
        if errors:
            raise ValueError(" ".join(errors))
        with self._db() as db:
            for leg_id, close in exits.items():
                exit_date, exit_price = close if close is not None else (None, None)
                db.execute("UPDATE position_legs SET exit_date = ?, exit_price = ? WHERE id = ?",
                           (exit_date, None if exit_price is None else float(exit_price), leg_id))
            db.execute("UPDATE positions SET updated_at = ? WHERE id = ?", (_now(), position_id))

    def delete(self, position_id):
        with self._db() as db:
            db.execute("DELETE FROM positions WHERE id = ?", (position_id,))

    def all(self):
        """Every position, the most recently opened first."""
        with self._db() as db:
            legs = {}
            for row in db.execute("SELECT position_id, symbol, option_type, strike, exp_date, side, quantity, "
                                  "entry_price, exit_date, exit_price, id FROM position_legs ORDER BY id"):
                legs.setdefault(row[0], []).append(Leg(*row[1:]))
            return [Position(*row, tuple(legs.get(row[0], ()))) for row in db.execute(
                "SELECT id, opened_on, commissions, notes, operation_id, source, external_id FROM positions "
                "ORDER BY opened_on DESC, id DESC")]

    def get(self, position_id):
        return next((p for p in self.all() if p.id == position_id), None)
