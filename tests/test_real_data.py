"""
Capa de datos sobre los datos reales. Se omite si no hay carpeta
de datos (por ejemplo, en GitHub).
"""

from datetime import date, datetime

import pytest

from helpers import NEW_SCRIPT, days_with_level2, run_script, snapshot
from pipeline import nivel3_agrupar as n3
from tape_dashboard import report
from tape_dashboard.data import validation
from tape_dashboard.data.dataset import load_dataset
from tape_dashboard.data.issues import ERROR
from tape_dashboard.edits.apply import apply_edits
from tape_dashboard.edits.store import Edits
from tape_dashboard.rules import classification as c

pytestmark = pytest.mark.real_data

# Estado conocido del nivel 3 guardado en las capturas analizadas al empezar
# el proyecto (ver docs/data-quality.md). Las capturas posteriores deben ser
# idénticas a la reconstrucción.
KNOWN_VALIDATION = {
    "20260812": validation.NO_LEVEL3,
    "20260817": validation.NO_LEVEL3,
    "20260825": validation.OLD_FORMAT,
    "20260909": validation.OLD_FORMAT,
    "20260911": validation.LABEL_ONLY,
    "20260915": validation.LABEL_ONLY,
    "20260916": validation.LABEL_ONLY,
    "20260922": validation.LEVEL3_WITHOUT_LEVEL2,
    "20260924": validation.LABEL_ONLY,
    "20261001": validation.LABEL_ONLY,
    "20261002": validation.PREVIOUS_VERSION,   # tiene una cancelación
    "20261006": validation.IDENTICAL,
    "20261007": validation.PREVIOUS_VERSION,   # tiene una cancelación
    "20261013": validation.IDENTICAL,
    "20261015": validation.IDENTICAL,
}


@pytest.fixture(scope="module")
def dataset(data_dir):
    return load_dataset(data_dir)


def test_every_file_matches_a_known_variant(dataset):
    for capture in dataset.captures.values():
        for data in (capture.level1, capture.level2):
            if data is not None:
                assert data.variant is not None, data.path.name
    assert [str(i) for i in dataset.issues if i.severity == ERROR] == []


def test_usable_days(dataset):
    expected = [datetime.strptime(d, "%Y%m%d").date() for d in days_with_level2()]
    assert dataset.usable_dates == expected
    assert date(2026, 9, 22) in dataset.captures
    assert date(2026, 9, 22) not in dataset.usable_dates


@pytest.mark.parametrize("day", days_with_level2())
def test_reconstruction_is_identical_to_the_script(day, dataset, data_dir, tmp_path):
    capture = dataset.captures[datetime.strptime(day, "%Y%m%d").date()]
    cli = run_script(NEW_SCRIPT, data_dir / f"nivel2_trades_{day}.csv",
                     data_dir / f"nivel1_candidatos_{day}.csv", tmp_path / "cli.csv", utf8_mode=False)
    assert cli.returncode == 0, cli.stderr.decode()
    n3.escribir_operaciones(tmp_path / "rebuilt.csv", [op.summary for op in capture.operations],
                            [op.summary for op in capture.passing])
    assert (tmp_path / "rebuilt.csv").read_bytes() == (tmp_path / "cli.csv").read_bytes()


def test_validation_against_stored_level3(dataset):
    for day, capture in dataset.captures.items():
        status = validation.validate_capture(capture).status
        key = day.strftime("%Y%m%d")
        if key in KNOWN_VALIDATION:
            assert status == KNOWN_VALIDATION[key], key
        elif capture.files.level3 is not None:
            assert status == validation.IDENTICAL, key


def test_operation_ids_are_unique_within_each_capture(dataset):
    for capture in dataset.captures.values():
        ids = [op.id for op in capture.operations]
        assert len(ids) == len(set(ids))


def test_loading_and_reporting_leave_the_data_folder_untouched(data_dir):
    before = snapshot(data_dir)
    report.render(load_dataset(data_dir), show_info=True)
    assert snapshot(data_dir) == before
    assert not list(data_dir.rglob("__pycache__"))


def test_every_real_operation_gets_one_consistent_destination(dataset):
    for day in dataset.usable_dates:
        for x in apply_edits(dataset.captures[day].operations, Edits.empty()):
            summary, destination = x.operation.summary, x.classification.destination
            assert destination in c.DESTINATIONS
            if summary["stock_option"]:
                assert destination == c.DISCARDED
            elif summary["patas_incompletas"]:
                assert destination == c.PENDING
            elif len(x.operation.legs) >= 3:
                assert destination == c.DISCARDED
            elif destination in (c.NET, c.WALLS):
                assert x.classification.strike is not None and x.classification.direction in (c.BULL, c.BEAR)


def test_the_operations_grid_builds_for_the_whole_period(data_dir, dataset, tmp_path):
    from tape_dashboard.app.state import AppState
    from tape_dashboard.app.tabs.operations.callbacks import detail_content, grid_content
    from tape_dashboard.config import Settings

    state = AppState(Settings(data_dir=data_dir, user_data_dir=tmp_path / "user"))
    first, last = min(dataset.usable_dates), max(dataset.usable_dates)
    rows, _, summary = grid_content(state, "custom", first.isoformat(), last.isoformat())

    assert rows and summary.startswith(f"{len(rows)} operations above the threshold")
    assert len({r["id"] for r in rows}) == len(rows)
    assert all(r["destination"] in c.DESTINATIONS and r["destination"] != c.PENDING for r in rows)
    assert detail_content(state, rows[0]["id"])[0].children.endswith(rows[0]["id"])


def test_the_charts_account_for_every_dollar_of_every_underlying(dataset):
    from tape_dashboard.charts import aggregate as agg
    from tape_dashboard.charts import figures

    first, last = min(dataset.usable_dates), max(dataset.usable_dates)
    items = apply_edits(dataset.operations(first, last, passing_only=True), Edits.empty())
    items = [i for i in items if i.classification.destination != c.PENDING]
    for symbol, _ in agg.symbol_counts(items):
        mine = agg.for_symbol(items, symbol)
        buckets = agg.net_buckets(mine, agg.EXPIRATION)
        totals = agg.side_totals(mine)
        levels = agg.wall_levels(mine)
        charted = (sum(b.net + b.undetermined for b in buckets) + sum(l.premium for l in levels)
                   + totals.undetermined_multi + totals.discarded)
        assert charted == pytest.approx(sum(i.classification.premium for i in mine))

        price = dataset.price_on_or_before(symbol, last)
        assert price is not None
        figures.net_figure(buckets, agg.EXPIRATION)
        figures.net_figure(agg.net_buckets(mine, agg.STRIKE), agg.STRIKE, price[1])
        figures.walls_figure(levels, price[1], price[0].isoformat())


def test_every_real_pending_operation_can_be_completed_in_the_form(dataset):
    from tape_dashboard.app import manual_legs as ml
    from tape_dashboard.edits.apply import pending_operations

    checked = 0
    for day in dataset.usable_dates:
        for item in pending_operations(dataset, Edits.empty(), day):
            op = item.operation
            values = ml.prefill(op)
            values["strike"] = round(float(op.legs[0]["strike"]) * 1.1 + 1, 2)     # an invented second leg
            values["price"] = 1.0
            fields = tuple(values[k] for k in ("option_type", "strike", "exp_date", "price", "size"))
            form = ml.form_state(op, fields, None)
            assert not form.errors and form.options[-1][0] == "unknown"
            assert ml.form_state(op, fields, form.options[0][0]).text
            checked += 1
    assert checked > 0
