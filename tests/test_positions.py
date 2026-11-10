"""Positions: the store and the P&L. All the figures are invented."""

import sqlite3
from dataclasses import replace
from datetime import date

import pytest

from tape_dashboard.positions import pnl
from tape_dashboard.positions.store import Leg, Position, PositionStore

OPENED = "2026-10-01"
EXP = "2026-12-18"


def leg(side="buy", strike=100.0, quantity=2, entry=2.0, option_type="call", exp=EXP, closed=None, price=None,
        symbol="xyz", id=None):
    return Leg(symbol, option_type, strike, exp, side, quantity, entry, closed, price, id)


def position(*legs, commissions=0.0, opened=OPENED):
    return Position(1, opened, commissions, "", (), "manual", None, tuple(legs))


@pytest.fixture
def store(tmp_path):
    return PositionStore(tmp_path / "positions.sqlite")


# --- store --------------------------------------------------------------------------------

def test_create_and_read(store):
    new = store.create(OPENED, [leg(), leg("sell", 110.0, entry=1.0)], 5.0, "a note", ["OP-1"])
    saved = store.get(new)
    assert (saved.opened_on, saved.commissions, saved.notes, saved.operation_ids, saved.source) == \
        (OPENED, 5.0, "a note", ("OP-1",), "manual")
    assert [(l.symbol, l.side, l.strike, l.closed) for l in saved.legs] == [("XYZ", "buy", 100.0, False),
                                                                            ("XYZ", "sell", 110.0, False)]


def test_positions_are_listed_most_recent_first(store):
    store.create("2026-09-01", [leg()])
    store.create("2026-10-01", [leg()])
    assert [p.opened_on for p in store.all()] == ["2026-10-01", "2026-09-01"]


def test_update_replaces_data_and_legs(store):
    new = store.create(OPENED, [leg(), leg("sell", 110.0)])
    store.update(new, "2026-10-02", [leg(strike=95.0, closed="2026-10-05", price=3.0)], 1.5, "edited", ["OP-2"])
    saved = store.get(new)
    assert (saved.opened_on, saved.commissions, saved.notes) == ("2026-10-02", 1.5, "edited")
    assert saved.operation_ids == ("OP-2",)
    assert [(l.strike, l.exit_date, l.exit_price) for l in saved.legs] == [(95.0, "2026-10-05", 3.0)]
    with pytest.raises(KeyError):
        store.update(999, OPENED, [leg()])


def test_closing_and_reopening_legs(store):
    new = store.create(OPENED, [leg(), leg("sell", 110.0)])
    first, second = store.get(new).legs
    store.set_exits(new, {first.id: ("2026-10-05", 3.0)})
    assert [l.closed for l in store.get(new).legs] == [True, False]
    store.set_exits(new, {first.id: None, second.id: ("2026-10-06", 0.5)})
    assert [(l.exit_date, l.exit_price) for l in store.get(new).legs] == [(None, None), ("2026-10-06", 0.5)]


def test_delete_removes_the_legs_and_links_too(store):
    new = store.create(OPENED, [leg()], operation_ids=["OP-1"])
    store.delete(new)
    assert store.get(new) is None
    with sqlite3.connect(store.path) as db:
        assert db.execute("SELECT COUNT(*) FROM position_legs").fetchone() == (0,)
        assert db.execute("SELECT COUNT(*) FROM position_links").fetchone() == (0,)


def test_several_operations_can_be_linked(store):
    new = store.create(OPENED, [leg()], operation_ids=["OP-2", "OP-1", "OP-2", ""])
    assert store.get(new).operation_ids == ("OP-2", "OP-1")             # in order, without repeats or blanks
    store.update(new, OPENED, [leg()], operation_ids=["OP-3"])
    assert store.get(new).operation_ids == ("OP-3",)
    store.update(new, OPENED, [leg()])
    assert store.get(new).operation_ids == ()
    store.update(new, OPENED, [leg()], operation_ids="OP-4")             # one ID given as text
    assert store.get(new).operation_ids == ("OP-4",)


def test_the_same_contract_can_appear_twice_to_close_part_of_a_leg(store):
    new = store.create(OPENED, [leg(quantity=5), leg(quantity=5)])
    assert len(store.get(new).legs) == 2


@pytest.mark.parametrize("opened, legs, commissions, message", [
    ("01/10/2026", [leg()], 0, "opening date"),
    (OPENED, [], 0, "at least one leg"),
    (OPENED, [leg()], -1, "Commissions"),
    (OPENED, [leg(symbol=" ")], 0, "underlying"),
    (OPENED, [leg(option_type="stock")], 0, "call or put"),
    (OPENED, [leg(side="hold")], 0, "buy or sell"),
    (OPENED, [leg(strike=0)], 0, "strike"),
    (OPENED, [leg(quantity=0)], 0, "quantity"),
    (OPENED, [leg(quantity=1.5)], 0, "quantity"),
    (OPENED, [leg(entry=-1)], 0, "entry price"),
    (OPENED, [leg(exp="soon")], 0, "expiration"),
    (OPENED, [leg(exp="2026-09-01")], 0, "expires before"),
    (OPENED, [leg(closed="2026-10-05")], 0, "both a date and a price"),
    (OPENED, [leg(price=1.0)], 0, "both a date and a price"),
    (OPENED, [leg(closed="2026-10-05", price=-1.0)], 0, "closing price"),
    (OPENED, [leg(closed="2026-09-01", price=1.0)], 0, "closes before"),
])
def test_invalid_positions_write_nothing(store, opened, legs, commissions, message):
    with pytest.raises(ValueError, match=message):
        store.create(opened, legs, commissions)
    assert store.all() == []


def test_an_invalid_update_or_close_changes_nothing(store):
    new = store.create(OPENED, [leg()])
    before = store.get(new)
    with pytest.raises(ValueError):
        store.update(new, OPENED, [leg(strike=-1.0)])
    with pytest.raises(ValueError, match="closes before"):
        store.set_exits(new, {before.legs[0].id: ("2026-09-01", 1.0)})
    with pytest.raises(ValueError, match="not part of this position"):
        store.set_exits(new, {999: ("2026-10-05", 1.0)})
    with pytest.raises(KeyError):
        store.set_exits(999, {})
    assert store.get(new) == before


def test_a_failure_while_writing_leaves_nothing_half_done(store, monkeypatch):
    new = store.create(OPENED, [leg(), leg("sell", 110.0)])
    before = store.get(new)
    import tape_dashboard.positions.store as module

    def boom(db, position_id, legs):
        raise sqlite3.OperationalError("disk full")

    monkeypatch.setattr(module, "_insert_legs", boom)
    with pytest.raises(sqlite3.OperationalError):
        store.update(new, "2026-10-02", [leg()])
    with pytest.raises(sqlite3.OperationalError):
        store.create(OPENED, [leg()])
    assert store.get(new) == before and len(store.all()) == 1


def test_an_imported_position_cannot_be_duplicated(store):
    store.create(OPENED, [leg()], source="broker", external_id="A1")
    store.create(OPENED, [leg()], source="other", external_id="A1")
    store.create(OPENED, [leg()])
    store.create(OPENED, [leg()])                       # manual positions have no external ID
    with pytest.raises(sqlite3.IntegrityError):
        store.create(OPENED, [leg()], source="broker", external_id="A1")


# --- P&L ------------------------------------------------------------------------------------

def test_a_long_leg_makes_money_when_the_price_rises():
    assert pnl.leg_pnl(leg(entry=2.0, quantity=2, closed="2026-10-05", price=3.0)) == 200.0


def test_a_short_leg_makes_money_when_the_price_falls():
    assert pnl.leg_pnl(leg("sell", entry=2.0, quantity=2, closed="2026-10-05", price=0.5)) == 300.0


def test_an_open_leg_has_no_result():
    assert pnl.leg_pnl(leg()) is None


def test_debit_spread():
    p = position(leg("buy", 100.0, 1, 5.0, closed="2026-10-11", price=7.0),
                 leg("sell", 110.0, 1, 3.0, closed="2026-10-11", price=4.0), commissions=0.0)
    assert pnl.entry_net(p) == 200.0                     # paid 2.00
    assert pnl.net_pnl(p) == 100.0                       # worth 3.00 at the close
    assert pnl.pnl_pct(p) == 50.0
    assert pnl.days_held(p) == 10


def test_credit_spread():
    p = position(leg("sell", 100.0, 1, 3.0, closed="2026-10-05", price=1.0),
                 leg("buy", 90.0, 1, 2.0, closed="2026-10-05", price=0.5))
    assert pnl.entry_net(p) == -100.0                    # received 1.00
    assert pnl.net_pnl(p) == 50.0                        # bought back at 0.50
    assert pnl.pnl_pct(p) == 50.0


def test_commissions_are_part_of_the_result():
    p = position(leg(entry=2.0, quantity=1, closed="2026-10-05", price=3.0), commissions=10.0)
    assert pnl.net_pnl(p) == 90.0 and pnl.pnl_pct(p) == 45.0


def test_a_loss_is_negative():
    p = position(leg(entry=2.0, quantity=1, closed="2026-10-05", price=0.5))
    assert pnl.net_pnl(p) == -150.0 and pnl.pnl_pct(p) == -75.0


def test_without_net_premium_there_is_no_percentage():
    p = position(leg("buy", 100.0, 1, 2.0, closed="2026-10-05", price=3.0),
                 leg("sell", 110.0, 1, 2.0, closed="2026-10-05", price=1.0))
    assert pnl.entry_net(p) == 0.0 and pnl.net_pnl(p) == 200.0 and pnl.pnl_pct(p) is None


def test_legs_can_close_on_different_days():
    p = position(leg("buy", 100.0, 1, 2.0, closed="2026-10-05", price=3.0), leg("sell", 110.0, 1, 1.0))
    assert pnl.status(p) == pnl.PARTIAL
    assert (pnl.net_pnl(p), pnl.pnl_pct(p), pnl.closing_date(p), pnl.days_held(p)) == (None, None, None, None)

    done = position(p.legs[0], replace(p.legs[1], exit_date="2026-10-20", exit_price=0.5))
    assert pnl.status(done) == pnl.CLOSED
    assert (pnl.closing_date(done), pnl.days_held(done), pnl.net_pnl(done)) == ("2026-10-20", 19, 150.0)


def test_an_untouched_position_is_open():
    assert pnl.status(position(leg())) == pnl.OPEN


def test_open_legs_past_their_expiration_are_flagged():
    gone = leg(exp="2026-10-10")
    closed = leg(exp="2026-10-10", closed="2026-10-09", price=1.0)
    alive = leg()
    p = position(gone, closed, alive)
    assert pnl.expired_legs(p, date(2026, 10, 11)) == [gone]
    assert pnl.expired_legs(p, date(2026, 10, 10)) == []          # still alive on expiration day


def test_cumulative_series():
    closes = [("2026-10-05", 100.0), ("2026-10-01", -40.0), ("2026-10-05", 10.0)]
    assert pnl.cumulative(closes) == [("2026-10-01", -40.0), ("2026-10-05", 70.0)]
    assert pnl.cumulative([]) == []


# --- default commissions --------------------------------------------------------------------

@pytest.mark.parametrize("quantities, expected", [([3], 3.0), ([25], 10.0), ([5, 20], 15.0), ([], 0.0)])
def test_commissions_are_one_dollar_per_contract_up_to_ten_per_leg(quantities, expected):
    assert pnl.opening_commissions(quantities) == expected


# --- files written with a single link ---------------------------------------------------------

SINGLE_LINK_SCHEMA = """
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, opened_on TEXT NOT NULL,
    commissions REAL NOT NULL DEFAULT 0 CHECK (commissions >= 0), notes TEXT NOT NULL DEFAULT '',
    operation_id TEXT, source TEXT NOT NULL DEFAULT 'manual', external_id TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE (source, external_id));
CREATE TABLE position_legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, position_id INTEGER NOT NULL REFERENCES positions (id) ON DELETE CASCADE,
    symbol TEXT NOT NULL, option_type TEXT NOT NULL, strike REAL NOT NULL, exp_date TEXT NOT NULL, side TEXT NOT NULL,
    quantity INTEGER NOT NULL, entry_price REAL NOT NULL, exit_date TEXT, exit_price REAL);
INSERT INTO positions VALUES (1, '2026-10-01', 4.0, 'linked', 'OP-1', 'manual', NULL, 't', 't');
INSERT INTO positions VALUES (2, '2026-10-02', 0.0, 'not linked', NULL, 'manual', NULL, 't', 't');
INSERT INTO position_legs VALUES (1, 1, 'XYZ', 'call', 100.0, '2026-12-18', 'buy', 2, 2.0, '2026-10-11', 3.0);
INSERT INTO position_legs VALUES (2, 2, 'XYZ', 'put', 90.0, '2026-12-18', 'sell', 1, 1.0, NULL, NULL);
"""


def test_a_file_with_single_links_is_migrated_and_kept_as_a_copy(tmp_path):
    path = tmp_path / "positions.sqlite"
    with sqlite3.connect(path) as db:
        db.executescript(SINGLE_LINK_SCHEMA)

    store = PositionStore(path)
    second, first = store.all()
    assert (first.id, first.operation_ids, first.notes, first.commissions) == (1, ("OP-1",), "linked", 4.0)
    assert (second.operation_ids, second.legs[0].side) == ((), "sell")
    assert (first.legs[0].exit_date, first.legs[0].exit_price) == ("2026-10-11", 3.0)
    with sqlite3.connect(path) as db:
        assert "operation_id" not in [row[1] for row in db.execute("PRAGMA table_info(positions)")]

    backup = tmp_path / "positions.before-links.sqlite"
    with sqlite3.connect(backup) as db:
        assert db.execute("SELECT operation_id FROM positions ORDER BY id").fetchall() == [("OP-1",), (None,)]

    again = PositionStore(path)                         # opening it again changes nothing
    assert again.all() == store.all()
