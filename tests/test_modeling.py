"""Tests for the guided Modeling Lab (M1).

The athlete and furniture specs are the two built-in course examples: every
number below is checked with exact Fractions, never with floating point.
"""

import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solver.model import F, fmt
from solver.modeling import (
    INTERPRETATION_TEMPLATES, MODEL_TEMPLATES, ModelingError, analyze,
    build_model, get_modeling_example, join_words, numbers_in_text, usage,
)
from solver.parser import parse_lp


def athlete(lang="fr"):
    """Return the built-in diet example, optionally in English."""
    spec = get_modeling_example("athlete")
    spec["lang"] = lang
    return spec


def furniture():
    """Return the built-in production example."""
    return get_modeling_example("furniture")


def check_interval(payload, lower, upper):
    """Compare one exact sensitivity interval with the hand-checked value."""
    assert payload["lower"] == (None if lower is None else F(lower)), payload
    assert payload["upper"] == (None if upper is None else F(upper)), payload


def test_athlete_model_text_parses_to_expected_lp():
    """M1: the generated text parses to the same LP as the expected model."""
    model = build_model(athlete())
    parsed = parse_lp(model.lp_text)
    expected = parse_lp(
        "Min z = 20x1 + 40x2; 2x1+x2>=16; x1+x2>=12; x1+3x2>=18"
    )
    assert parsed.sense == expected.sense == "min"
    assert parsed.c == expected.c == [F(20), F(40)]
    assert parsed.var_names == ["x1", "x2"]
    for actual, wanted in zip(parsed.constraints, expected.constraints):
        assert actual.coeffs == wanted.coeffs
        assert actual.op == wanted.op
        assert actual.rhs == wanted.rhs
    assert len(model.steps) == 5
    assert [step["number"] for step in model.steps] == [1, 2, 3, 4, 5]
    assert "Soit P la quantité" in model.steps[0]["text"]
    assert "au moins 16 g de protéines" in model.steps[2]["text"]


def test_athlete_engine_results():
    """M1: solution, vertices, slack, dual and sensitivity match the corrigé."""
    report = analyze(athlete())
    assert report.status == "optimal"
    assert report.simplex.x == [F(9), F(3)]
    assert report.simplex.z == F(300)
    assert [F(price) for price in report.dual["shadow_prices"]] == [F(0), F(10), F(10)]
    assert [F(y) for y in report.dual["y"]] == [F(0), F(10), F(10)]
    assert F(report.dual["w"]) == F(300)
    vertices = {(F(point["x_text"]), F(point["y_text"])): F(point["z_text"])
                for point in report.graphical["polygon"]}
    assert vertices == {(0, 16): F(640), (4, 8): F(400),
                        (9, 3): F(300), (18, 0): F(360)}
    first, second, third = [usage(row, report.simplex.x) for row in report.model.rows]
    assert first == (F(21), F(5), False)
    assert second == (F(12), F(0), True)
    assert third == (F(18), F(0), True)
    costs = report.sensitivity["objective"]
    check_interval(costs[0], Fraction(40, 3), 40)
    check_interval(costs[1], 20, 60)
    rhs = report.sensitivity["rhs"]
    check_interval(rhs[0], None, 21)
    check_interval(rhs[1], 10, 18)
    check_interval(rhs[2], 12, 28)


def test_furniture_production_results():
    """M1: production results and production vocabulary are correct in FR/EN."""
    specification = get_modeling_example("furniture")
    report = analyze(specification)
    assert report.status == "optimal"
    assert report.simplex.x == [F(10), F(2)]
    assert report.simplex.z == F(3400)
    assert [F(price) for price in report.dual["shadow_prices"]] == [F(0), F(100), F(100)]
    costs = report.sensitivity["objective"]
    check_interval(costs[0], 200, 400)
    check_interval(costs[1], 150, 300)
    rhs = report.sensitivity["rhs"]
    check_interval(rhs[0], 14, None)
    check_interval(rhs[1], 16, 24)
    check_interval(rhs[2], 11, 14)
    fr_text = report.interpretation["plain_text"]
    assert "profit de M1" in fr_text
    assert "le gain reste inchangé" in fr_text
    assert "La ressource « Menuiserie » : prix fictif nul" in fr_text
    assert "Les ressources qui pilotent la solution : Assemblage et Vernissage." in fr_text
    assert "prix de M1" not in fr_text
    english = dict(specification, lang="en")
    en_text = analyze(english).interpretation["plain_text"]
    assert "profit of M1" in en_text
    assert "the gain is unchanged" in en_text
    assert "The 'Menuiserie' resource: zero shadow price" in en_text
    assert "The resources that drive the solution: Assemblage and Vernissage." in en_text
    assert "price of M1" not in en_text


def test_interpretation_both_languages():
    """M1: FR/EN interpretations use wording that matches the example type."""
    fr = analyze(athlete("fr")).interpretation
    en = analyze(athlete("en")).interpretation
    fr_text, en_text = fr["plain_text"], en["plain_text"]
    for token in ("9", "3", "300", "dh", "10", "5 g"):
        assert token in fr_text, token
    assert "300" in en_text and "dh" in en_text
    sections = {"decision", "resources", "shadow", "sensitivity",
                "verification", "recommendations"}
    assert set(fr["sections"]) == set(en["sections"]) == sections
    assert "13,33 (40/3)" in fr_text
    assert "13.33 (40/3)" in en_text
    assert fr["sections"]["decision"]["title"] == "Décision optimale"
    assert "9 unités de P et 3 unités de Q" in fr_text
    assert "9 units of P and 3 units of Q" in en_text
    assert "L'exigence « protéines » : prix fictif nul" in fr_text
    assert "The 'protéines' requirement: zero shadow price" in en_text
    assert "Le plan reste optimal tant que le prix de P" in fr_text
    assert "le coût reste inchangé" in fr_text
    assert "the price of P" in en_text
    assert "the cost is unchanged" in en_text
    assert "profit of P" not in en_text and "profit de P" not in fr_text
    assert "Les exigences qui pilotent la solution : vitamines et calcium." in fr_text
    assert "The requirements that drive the solution: vitamines and calcium." in en_text
    assert "son prix ne peut baisser que de 6,67" in fr_text
    assert "(33 %)" in fr_text
    assert "its price can only decrease by 6.67" in en_text
    assert "(33%)" in en_text
    assert join_words(["A", "B"], "fr") == "A et B"
    assert join_words(["A", "B"], "en") == "A and B"
    assert join_words(["A", "B", "C"], "fr") == "A, B et C"
    assert join_words(["A", "B", "C"], "en") == "A, B and C"


def infeasible_spec():
    """A diet whose last requirement cannot possibly be satisfied."""
    return {
        "lang": "fr", "type": "diet", "currency": "dh", "title": "Irréalisable",
        "items": [{"name": "A", "unit": "unité", "price": "1"},
                  {"name": "B", "unit": "unité", "price": "1"}],
        "resources": [
            {"name": "prot", "unit": "g", "amount": "1", "op": "<=",
             "content": {"A": "1", "B": "0"}},
            {"name": "vit", "unit": "g", "amount": "1", "op": "<=",
             "content": {"A": "0", "B": "1"}},
            {"name": "cal", "unit": "g", "amount": "100", "content": {"A": "1", "B": "1"}},
        ],
    }


def unbounded_spec():
    """A production item consumes nothing, so profit can grow forever."""
    return {
        "lang": "en", "type": "production", "currency": "dh", "title": "Unbounded",
        "items": [{"name": "A", "unit": "unit", "price": "1"},
                  {"name": "B", "unit": "unit", "price": "5"}],
        "resources": [
            {"name": "Time", "unit": "hours", "amount": "10", "op": "<=",
             "content": {"A": "1", "B": "0"}},
        ],
    }


def test_special_statuses_do_not_crash():
    """M1: infeasible and unbounded problems return clear text, not a traceback."""
    infeasible = analyze(infeasible_spec())
    assert infeasible.status == "infeasible"
    assert infeasible.dual is None and infeasible.sensitivity is None
    assert "Aucune combinaison" in infeasible.interpretation["plain_text"]
    unbounded = analyze(unbounded_spec())
    assert unbounded.status == "unbounded"
    assert "without limit" in unbounded.interpretation["plain_text"]
    assert len(unbounded.interpretation["sections"]) == 6


def expect_error(spec, lang, fragment):
    """Check one friendly validation message in the requested language."""
    spec = dict(spec)
    spec["lang"] = lang
    try:
        build_model(spec)
    except ModelingError as error:
        assert fragment in error.message, error.message
        return
    raise AssertionError(f"ModelingError expected for {fragment!r}")


def test_friendly_validation_in_both_languages():
    """M1: empty data, duplicates, bad numbers and zero rows are explained."""
    base = athlete()
    empty = dict(base, items=[])
    expect_error(empty, "fr", "Ajoutez au moins un aliment")
    expect_error(empty, "en", "Add at least one food")
    duplicate = dict(base, items=[base["items"][0], dict(base["items"][1])])
    duplicate["items"][1]["name"] = "P"
    expect_error(duplicate, "fr", "même nom")
    expect_error(duplicate, "en", "same name")
    negative = dict(base, items=[dict(base["items"][0], price="-2")] + base["items"][1:])
    expect_error(negative, "fr", "négatif")
    expect_error(negative, "en", "negative")
    zero_row = dict(base, resources=[dict(base["resources"][0], content={"P": "0", "Q": "0"})])
    expect_error(zero_row, "fr", "aucun coefficient")
    expect_error(zero_row, "en", "no non-zero")
    bad_number = dict(base, items=[dict(base["items"][0], price="abc")] + base["items"][1:])
    expect_error(bad_number, "fr", "invalide")
    expect_error(bad_number, "en", "invalid")


def test_number_formats_and_highlighter():
    """M1: decimals, commas and fractions are found with exact positions."""
    text = "16g de protéines, 12g ... 3,5 ... 1/2"
    found = numbers_in_text(text)
    assert [(item["value"], item["unit"]) for item in found] == [
        ("16", "g"), ("12", "g"), ("7/2", ""), ("1/2", ""),
    ]
    for item in found:
        assert text[item["start"]:item["end"]] == item["raw"]
    assert found[0]["raw"] == "16g"
    assert F(found[2]["value"]) == Fraction(7, 2)
    spec = dict(athlete(), items=[dict(athlete()["items"][0], price="3,5")])
    assert build_model(spec).lp.c[0] == Fraction(7, 2)
    spec = dict(athlete(), items=[dict(athlete()["items"][0], price="1/2")])
    assert build_model(spec).lp.c[0] == Fraction(1, 2)


def test_template_dictionaries_have_the_same_keys():
    """M1: no sentence is missing in either language."""
    assert set(MODEL_TEMPLATES["fr"]) == set(MODEL_TEMPLATES["en"])
    assert set(INTERPRETATION_TEMPLATES["fr"]) == set(INTERPRETATION_TEMPLATES["en"])
    for templates in (MODEL_TEMPLATES, INTERPRETATION_TEMPLATES):
        for lang in ("fr", "en"):
            assert all(isinstance(value, str) and value
                       for value in templates[lang].values()), lang


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)} modeling tests passed.")
