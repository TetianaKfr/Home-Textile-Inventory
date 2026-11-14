from app.services.compatibility import (
    match_curtain,
    match_duvet_cover,
    match_fitted_sheet,
    match_flat_sheet,
    match_pillowcase,
    match_tablecloth,
)
from app.services.dimensions import parse_dimension_pair, usable_measure


def test_negative_measurements_are_not_results():
    assert usable_measure(-12) is None
    assert usable_measure(0) == 0
    assert usable_measure("190.5") == 190.5
    sheet = match_flat_sheet({"width": -140, "length": 190}, {"width": 200, "length": 260})
    cloth = match_tablecloth(
        {"shape": "rectangular", "width": 90, "length": -160, "overhang": -25},
        {"shape": "rectangular", "width": 140, "length": 210},
    )
    curtain = match_curtain(
        {"width": -160, "rail_width": -200, "desired_length": -30, "fullness": -2},
        {"panel_width": 200, "panel_count": 2, "length": 250, "attachment": "eyelets"},
        fullness_is_default=False,
    )
    for verdict in (sheet, cloth, curtain):
        text = " ".join([verdict.explanation, *verdict.discrepancies, *verdict.warnings])
        assert "-" not in text


def test_dimension_parser_keeps_width_first():
    assert parse_dimension_pair("140 × 190") == (140, 190)
    assert parse_dimension_pair("140x190") == (140, 190)
    assert parse_dimension_pair("140/190") == (140, 190)
    assert parse_dimension_pair("140 by 190") == (140, 190)
    assert parse_dimension_pair("140 на 190") == (140, 190)
    assert parse_dimension_pair("140,5 x 190,5") == (140.5, 190.5)
    assert parse_dimension_pair("not a size") is None


def test_fitted_sheet_exact_and_too_small():
    mattress = {"width": 140, "length": 190, "depth": 20}
    exact = match_fitted_sheet(mattress, {"width": 140, "length": 190, "mattress_depth": 25})
    assert exact.status == "exact"
    small = match_fitted_sheet(mattress, {"width": 90, "length": 190, "mattress_depth": 25})
    assert small.status == "incompatible"
    shallow = match_fitted_sheet(mattress, {"width": 140, "length": 190, "mattress_depth": 12})
    assert shallow.status == "incompatible"


def test_flat_sheet_uses_suggested_overhang():
    mattress = {"width": 140, "length": 190, "depth": 20}
    sheet = match_flat_sheet(mattress, {"width": 200, "length": 260})
    assert sheet.status in {"exact", "acceptable"}
    assert any("suggestion" in warning.lower() for warning in sheet.warnings)


def test_duvet_does_not_treat_a_large_gap_as_acceptable():
    duvet = {"width": 220, "length": 200}
    assert match_duvet_cover(duvet, {"width": 220, "length": 200}).status == "exact"
    assert match_duvet_cover(duvet, {"width": 180, "length": 140}).status == "incompatible"


def test_pillowcase_allowance():
    pillow = {"width": 60, "length": 60}
    assert match_pillowcase(pillow, {"width": 65, "length": 65}).status == "acceptable"
    assert match_pillowcase(pillow, {"width": 40, "length": 40}).status == "incompatible"


def test_tablecloth_calculation():
    table = {"shape": "rectangular", "width": 90, "length": 160}
    cloth = match_tablecloth(table, {"shape": "rectangular", "width": 140, "length": 210})
    assert cloth.status == "exact"
    assert any("suggestion" in warning.lower() for warning in cloth.warnings)
    wrong_shape = match_tablecloth(table, {"shape": "round", "diameter": 150})
    assert wrong_shape.status == "incompatible"


def test_curtain_uses_rail_width_and_fullness():
    window = {
        "width": 160,
        "rail_width": 200,
        "fullness": 2,
        "desired_length": 250,
        "attachment": "eyelets",
    }
    good = match_curtain(
        window,
        {"panel_width": 200, "panel_count": 2, "length": 250, "attachment": "eyelets"},
        fullness_is_default=False,
    )
    assert good.status == "exact"
    assert any("rail width" in line.lower() for line in good.discrepancies)
    short = match_curtain(
        window,
        {"panel_width": 80, "panel_count": 1, "length": 100, "attachment": "loops"},
        fullness_is_default=False,
    )
    assert short.status == "incompatible"
