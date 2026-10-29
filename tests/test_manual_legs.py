"""The manual leg that completes an operation: parsing, candidate, operation types, preview and saving."""

from datetime import date

import pytest

from tape_dashboard.app import manual_legs as ml
from tape_dashboard.data.dataset import load_dataset
from tape_dashboard.edits.apply import apply_edits, pending_operations
from tape_dashboard.edits.store import EditStore
from tape_dashboard.rules import classification as c

D13 = date(2026, 10, 13)
INCOMPLETE = "20261013-BBB-13:00:00.000-MLAT"     # one call bought: BBB 2026-12-18 120, 3000 at 4.00
DEC = "2026-12-18"


@pytest.fixture
def dataset(synthetic_folder):
    return load_dataset(synthetic_folder)


@pytest.fixture
def pending(dataset):
    return next(op for op in dataset.captures[D13].operations if op.id == INCOMPLETE)


@pytest.fixture
def store(tmp_path):
    return EditStore(tmp_path / "edits.sqlite")


def leg(option_type="call", strike=130, exp_date=DEC, price=1.5, size=3000):
    parsed, errors = ml.parse_leg(option_type, strike, exp_date, price, size)
    assert not errors
    return parsed


# --- reading the form ---------------------------------------------------------------

def test_a_valid_leg():
    assert ml.parse_leg("put", "95.5", "2026-12-18T00:00:00", "2", "1500.0") == \
        (ml.LegInput("put", 95.5, DEC, 2.0, 1500), [])


@pytest.mark.parametrize("values, message", [
    ((None, 130, DEC, 1.5, 3000), "call or put"),
    (("call", None, DEC, 1.5, 3000), "strike"),
    (("call", 0, DEC, 1.5, 3000), "strike"),
    (("call", 130, None, 1.5, 3000), "expiration"),
    (("call", 130, "18/12/2026", 1.5, 3000), "expiration"),
    (("call", 130, DEC, -1, 3000), "price"),
    (("call", 130, DEC, "abc", 3000), "price"),
    (("call", 130, DEC, 1.5, 0), "size"),
    (("call", 130, DEC, 1.5, 10.5), "size"),
])
def test_invalid_legs(values, message):
    parsed, errors = ml.parse_leg(*values)
    assert parsed is None and len(errors) == 1 and message in errors[0]


def test_the_form_starts_from_the_known_leg(pending):
    assert ml.prefill(pending) == {"option_type": "call", "strike": None, "exp_date": DEC, "price": None,
                                   "size": 3000}


# --- candidate, operation types and preview -------------------------------------------

def test_candidate_is_recomputed_by_the_script(pending):
    completed, error = ml.candidate(pending, leg())
    assert error is None and len(completed.legs) == 2
    assert completed.id == INCOMPLETE and not completed.summary["patas_incompletas"]
    assert completed.premium == pytest.approx(1_200_000 + 450_000)


def test_the_same_contract_twice_is_refused(pending):
    completed, error = ml.candidate(pending, leg(strike=120))
    assert completed is None and "same contract" in error


@pytest.mark.parametrize("manual, types", [
    (dict(), ["bull_call", "bear_call", "unknown"]),
    (dict(option_type="put", strike=120), ["long_straddle", "short_straddle", "long_synthetic",
                                           "short_synthetic", "unknown"]),
    (dict(option_type="put", strike=100), ["long_strangle", "short_strangle", "bullish_risk_reversal",
                                           "bearish_risk_reversal", "unknown"]),
    (dict(exp_date="2027-01-15"), ["diagonal_buy_near", "diagonal_buy_far", "unknown"]),
])
def test_operation_types_follow_the_legs(pending, manual, types):
    completed, _ = ml.candidate(pending, leg(**manual))
    assert [key for key, _ in ml.type_options(completed)] == types


@pytest.mark.parametrize("strategy, expected", [
    ("bull_call", "debit vertical → net, bull, strike 120, 2026-12-18, +0.750M"),
    ("bear_call", "credit vertical → walls, resistance at 120, 2026-12-18, 0.750M"),
    ("unknown", "vertical → undetermined multi-leg, gross premium 1.650M"),
    (None, "vertical → undetermined multi-leg, gross premium 1.650M"),
])
def test_preview(pending, strategy, expected):
    completed, _ = ml.candidate(pending, leg())
    text, warnings = ml.preview(completed, strategy)
    assert text == expected and warnings == []


def test_preview_of_a_discarded_combination(pending):
    completed, _ = ml.candidate(pending, leg(option_type="put", strike=120))
    assert ml.preview(completed, "long_straddle")[0].startswith("straddle → discarded")


@pytest.mark.parametrize("manual, strategy, message", [
    (dict(strike=120), "bull_call", "same contract"),
    (dict(), None, "Choose the operation type"),
    (dict(), "long_straddle", "does not fit"),
])
def test_what_cannot_be_saved(pending, manual, strategy, message):
    (problem,) = ml.check(pending, leg(**manual), strategy)
    assert message in problem


# --- saving and deleting ---------------------------------------------------------------------

def test_saving_completes_the_operation(dataset, pending, store):
    ml.save(store, pending, leg(), "bull_call")
    edits = store.snapshot()
    (manual,) = edits.manual_legs[INCOMPLETE]
    assert (manual.option_type, manual.strike, manual.price, manual.size) == ("call", 130.0, 1.5, 3000)
    assert edits.overrides[INCOMPLETE].strategy == "bull_call"
    assert INCOMPLETE not in [i.operation.id for i in pending_operations(dataset, edits, D13)]
    item = apply_edits([pending], edits)[0]
    assert (item.classification.destination, item.classification.direction) == (c.NET, c.BULL)


def test_one_manual_leg_per_operation(pending, store):
    ml.save(store, pending, leg(), "bull_call")
    with pytest.raises(ValueError, match="already has a manual leg"):
        ml.save(store, pending, leg(strike=140), "bull_call")
    assert len(store.snapshot().manual_legs[INCOMPLETE]) == 1


def test_updating_the_leg_and_its_type(pending, store):
    ml.save(store, pending, leg(), "bull_call")
    (manual,) = store.snapshot().manual_legs[INCOMPLETE]
    ml.save(store, pending, leg(option_type="put", strike=100, price=2.0), "bullish_risk_reversal",
            leg_id=manual.id)
    edits = store.snapshot()
    assert ml.from_manual_leg(edits.manual_legs[INCOMPLETE][0]) == ml.LegInput("put", 100.0, DEC, 2.0, 3000)
    assert edits.overrides[INCOMPLETE].strategy == "bullish_risk_reversal"


def test_an_invalid_edit_writes_nothing(pending, store):
    with pytest.raises(ValueError, match="same contract"):
        ml.save(store, pending, leg(strike=120), "bull_call")
    with pytest.raises(ValueError, match="Choose the operation type"):
        ml.save(store, pending, leg(), None)
    edits = store.snapshot()
    assert edits.manual_legs == {} and edits.overrides == {}


def test_deleting_the_leg_sends_the_operation_back_to_tab_2(dataset, pending, store):
    ml.save(store, pending, leg(), "bull_call")
    (manual,) = store.snapshot().manual_legs[INCOMPLETE]
    ml.delete(store, INCOMPLETE, manual.id)
    edits = store.snapshot()
    assert edits.manual_legs == {} and edits.overrides == {}
    assert INCOMPLETE in [i.operation.id for i in pending_operations(dataset, edits, D13)]
