"""Esquema canónico, alias y variantes de encabezado conocidas."""

import pytest

from pipeline import nivel3_agrupar as n3
from tape_dashboard.data import schemas


@pytest.mark.parametrize("schema", [schemas.LEVEL1, schemas.LEVEL2], ids=lambda s: s.level)
def test_every_known_variant_is_recognised_and_complete(schema):
    for variant, header in schema.variants.items():
        match = schemas.match_header(schema, header)
        assert match.variant == variant
        assert match.usable, (variant, match.missing_required)
        assert match.unknown == [], variant


def test_level3_variants_are_recognised():
    for variant, header in schemas.LEVEL3.variants.items():
        assert schemas.match_header(schemas.LEVEL3, header).variant == variant


def test_api_variant_maps_the_condition_code_not_the_long_text():
    match = schemas.match_header(schemas.LEVEL2, schemas.LEVEL2.variants["N2-B"])
    assert match.mapping["Trade Condition"] == "tradeConditionCode"
    assert match.mapping["Trade Condition Full"] == "tradeCondition"
    assert match.mapping["Time"] == "tradeTime"


def test_level2_aliases_are_the_ones_the_script_accepts():
    for name, aliases in n3.ALIASES_COLUMNA.items():
        column = schemas.LEVEL2.column(name)
        assert (column.name, *column.aliases) == tuple(aliases)
        assert column.required


def test_missing_required_columns_are_listed():
    header = [c for c in schemas.LEVEL2.variants["N2-E"] if c not in ("Premium", "agresividad")]
    match = schemas.match_header(schemas.LEVEL2, header)
    assert not match.usable
    assert match.missing_required == ["Premium", "agresividad"]


def test_reordered_header_is_a_new_but_usable_variant():
    match = schemas.match_header(schemas.LEVEL1, list(reversed(schemas.LEVEL1.variants["N1-E"])))
    assert match.variant is None
    assert match.usable
