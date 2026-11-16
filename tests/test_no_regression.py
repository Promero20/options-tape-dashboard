"""
No regresión de nivel3_agrupar.py.

The script's output has changed deliberately twice since the frozen version
of 01/10/2026, and each change is checked against its own oracle:

1. 19/10/2026, cancellations dropped together with the trade they cancel
   (decision 0015). The frozen copy of 21/10/2026 must produce, byte for
   byte, what the copy of 01/10 produces on the same level 2 without those
   rows. This keeps the history of the output proven.

2. 16/11/2026, the grouping rule (decision 0036). Its output is new, so it
   is compared with the copy of 21/10 by invariants: operations of
   multi-leg conditions keep the same trades and summary, every new
   single-leg operation is contained in an old one, no trade or dollar of
   premium is lost, and the console and the CSV keep their format.

Both are checked on the synthetic scenario in every level-2 schema variant
and on the real data of every day with level 2.
"""

import csv
import importlib.util
import re

import pytest

from helpers import LEGACY_SCRIPT, NEW_SCRIPT, PREVIOUS_SCRIPT, days_with_level2, run_script
from synthetic import LEVEL2_VARIANTS, scenario, trade, write_level1, write_level2

CANCEL_CONDITIONS = {"CANC", "CNCL", "CNCO", "CNOL"}
CONSOLE = re.compile(rb"\d+ trades -> \d+ operaciones agrupadas -> \d+ tras el umbral de premium "
                     rb"\(\d+ descartadas\)")
NEW_COLUMNS = ("lado", "n_trozos", "premium_trozo_mayor_M", "lado_de_trozo_menor")
# keys of the summary that the 0.25 boundary of decision 0036 can change
BOUNDARY_KEYS = {"direccion", "precio_neto", "precio_neto_metodo"}


def without_cancellations(level2, output):
    """
    Copia del nivel 2 sin las cancelaciones ni los trades que anulan. Es una
    implementación independiente de la del script, a partir del CSV crudo,
    para no comprobar el script consigo mismo. Devuelve cuántas
    cancelaciones había.
    """
    with open(level2, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header, rows = reader.fieldnames, list(reader)
    api = "tradeTime" in header
    time, price, size = ("tradeTime", "lastPrice", "tradeSize") if api else ("Time", "Trade", "Trade Size")
    condition = "tradeConditionCode" if api else "Trade Condition"

    cancels = sorted((r for r in rows if r[condition] in CANCEL_CONDITIONS), key=lambda r: r[time])
    removed = {id(c) for c in cancels}
    for c in cancels:
        candidates = [r for r in rows
                      if id(r) not in removed and r[time]
                      and r["contract_symbol"] == c["contract_symbol"]
                      and float(r[size]) == float(c[size]) and float(r[price]) == float(c[price])
                      and r[time] <= c[time]]
        if candidates:
            removed.add(id(max(candidates, key=lambda r: r[time])))

    with open(output, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(r for r in rows if id(r) not in removed)
    return len(cancels)


# --- 1. the history: cancellations (decision 0015) ------------------------------------------------

def assert_previous_same_as_legacy(level2, level1, tmp_path):
    filtered = tmp_path / "nivel2_sin_cancelaciones.csv"
    n_cancels = without_cancellations(level2, filtered)
    legacy_output, previous_output = tmp_path / "legacy.csv", tmp_path / "previous.csv"
    # El legacy necesita el modo UTF-8 para escribir '→' en Windows (en el
    # Linux del pipeline es el comportamiento por defecto).
    legacy = run_script(LEGACY_SCRIPT, filtered, level1, legacy_output, utf8_mode=True)
    assert legacy.returncode == 0, legacy.stderr.decode()
    previous = run_script(PREVIOUS_SCRIPT, level2, level1, previous_output, utf8_mode=False)
    assert previous.returncode == 0, previous.stderr.decode()

    assert previous_output.read_bytes() == legacy_output.read_bytes()
    legacy_lines, previous_lines = legacy.stdout.splitlines(), previous.stdout.splitlines()
    assert previous_lines[0] == legacy_lines[0]
    if n_cancels:
        assert previous_lines[1].startswith(f"{n_cancels} cancelaciones quitadas".encode())
    else:
        assert previous.stdout == legacy.stdout
    return previous_output


# --- 2. the grouping rule (decision 0036) ----------------------------------------------------------

def _module(path):
    spec = importlib.util.spec_from_file_location(f"frozen_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PREVIOUS = _module(PREVIOUS_SCRIPT)


def _groups(module, level2, level1, **kwargs):
    """Groups of a script on a capture, as sets of trade positions, with their summary."""
    rows, _ = module.quitar_cancelaciones(module.cargar(level2))
    position = {id(r): i for i, r in enumerate(rows)}
    groups = module.agrupar(rows, **kwargs)
    return rows, {frozenset(position[id(r)] for r in g): g for g in groups.values()}


def _near_boundary(group):
    return any(abs(abs(leg["agr"]) - 0.25) <= 1e-9 for leg in PREVIOUS.patas_de(group) if leg["agr"] is not None)


def assert_rule_invariants(level2, level1, tmp_path):
    from pipeline import nivel3_agrupar as n3

    old_rows, old = _groups(PREVIOUS, level2, level1)
    precios, estimados = n3.cargar_nivel1(level1)
    new_rows, new = _groups(n3, level2, level1, precios=precios, estimados=estimados)
    key = ("t", "contract_symbol", "Trade Condition", "size", "premium")
    assert [tuple(r[k] for k in key) for r in new_rows] == [tuple(r[k] for k in key) for r in old_rows]

    # every trade is in exactly one operation, and the premium is the same
    assert sorted(i for g in new for i in g) == list(range(len(new_rows)))
    assert sum(r["premium"] for r in new_rows) == pytest.approx(sum(r["premium"] for r in old_rows))

    def multi_leg(group):
        return group[0]["Trade Condition"] in n3.MULTI_LEG

    # operations of multi-leg conditions keep their trades and their summary
    assert {g for g, rows in new.items() if multi_leg(rows)} == {g for g, rows in old.items() if multi_leg(rows)}
    for g, rows in new.items():
        if multi_leg(rows):
            before, after = PREVIOUS.resumen(old[g]), n3.resumen(rows)
            changed = {k for k in before if before[k] != after[k]}
            assert not changed or (changed <= BOUNDARY_KEYS and _near_boundary(old[g])), (sorted(changed), g)
            assert all(after[k] == "" for k in ("lado", "n_trozos", "premium_trozo_mayor", "lado_de_trozo_menor"))

    # every single-leg operation is a part of an old one, and has one condition
    owner = {i: g for g in old for i in g}
    for g, rows in new.items():
        if not multi_leg(rows):
            assert g <= owner[next(iter(g))]
            assert len({r["Trade Condition"] for r in rows}) == 1

    # the command line: same console line and cancellations, CSV with the new columns at the end
    previous_output, new_output = tmp_path / "previous.csv", tmp_path / "new.csv"
    previous = run_script(PREVIOUS_SCRIPT, level2, level1, previous_output, utf8_mode=False)
    current = run_script(NEW_SCRIPT, level2, level1, new_output, utf8_mode=False)
    assert previous.returncode == 0 and current.returncode == 0, current.stderr.decode()
    previous_lines, new_lines = previous.stdout.splitlines(), current.stdout.splitlines()
    assert CONSOLE.fullmatch(new_lines[0].rstrip(b"\r")) is not None
    assert new_lines[0].split(b" -> ")[0] == previous_lines[0].split(b" -> ")[0]   # same trades
    assert new_lines[1:] == previous_lines[1:]                                     # same cancellations
    with open(previous_output, encoding="utf-8") as f:
        old_header = next(csv.reader(f))
    with open(new_output, encoding="utf-8") as f:
        assert next(csv.reader(f)) == old_header + list(NEW_COLUMNS)
    return new_output


def rule_scenario():
    """The synthetic scenario plus single-leg trades that the old rule chained into one operation."""
    return scenario() + [
        trade("AAA", "2026-11-20", 40, "call", "10:20:00.000", 5.0, 1000, 4.9, 5.0, "AUTO"),    # bought
        trade("AAA", "2026-11-20", 45, "call", "10:20:00.020", 2.0, 1000, 1.9, 2.0, "AUTO"),    # 20 ms later
        trade("AAA", "2026-11-20", 40, "call", "10:20:30.000", 4.9, 1000, 4.9, 5.0, "AUTO"),    # sold
        trade("AAA", "2026-11-20", 40, "call", "10:21:00.000", 5.0, 10, 4.9, 5.0, "AUTO"),      # small
    ]


@pytest.mark.parametrize("variant", LEVEL2_VARIANTS)
def test_no_regression_synthetic(variant, tmp_path):
    trades = rule_scenario()
    level2 = tmp_path / "nivel2_trades_20261013.csv"
    level1 = tmp_path / "nivel1_candidatos_20261013.csv"
    write_level2(level2, trades, variant)
    write_level1(level1, trades)

    output = assert_previous_same_as_legacy(level2, level1, tmp_path)
    # el calendar del escenario obliga a escribir '→'
    assert "→" in output.read_text(encoding="utf-8")
    output = assert_rule_invariants(level2, level1, tmp_path)
    assert "→" in output.read_text(encoding="utf-8")


def test_without_cancellations_the_previous_output_is_untouched(tmp_path):
    trades = [t for t in scenario() if t["Trade Condition"] not in CANCEL_CONDITIONS]
    level2, level1 = tmp_path / "n2.csv", tmp_path / "n1.csv"
    write_level2(level2, trades)
    write_level1(level1, trades)
    legacy = run_script(LEGACY_SCRIPT, level2, level1, tmp_path / "legacy.csv", utf8_mode=True)
    previous = run_script(PREVIOUS_SCRIPT, level2, level1, tmp_path / "previous.csv", utf8_mode=False)
    assert previous.stdout == legacy.stdout
    assert (tmp_path / "previous.csv").read_bytes() == (tmp_path / "legacy.csv").read_bytes()


def test_the_rule_changes_the_synthetic_output(tmp_path):
    """The old rule chained the added trades into one operation; the new one splits them in four."""
    trades = rule_scenario()
    level2, level1 = tmp_path / "n2.csv", tmp_path / "n1.csv"
    write_level2(level2, trades)
    write_level1(level1, trades)
    from pipeline import nivel3_agrupar as n3
    precios, estimados = n3.cargar_nivel1(level1)
    assert len(_groups(n3, level2, level1, precios=precios, estimados=estimados)[1]) == \
        len(_groups(PREVIOUS, level2, level1)[1]) + 3


@pytest.mark.real_data
@pytest.mark.parametrize("day", days_with_level2())
def test_no_regression_real_data(day, data_dir, tmp_path):
    level2, level1 = data_dir / f"nivel2_trades_{day}.csv", data_dir / f"nivel1_candidatos_{day}.csv"
    assert_previous_same_as_legacy(level2, level1, tmp_path)
    assert_rule_invariants(level2, level1, tmp_path)
