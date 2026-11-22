"""Engine tests, sections A-C of the specification.

Note for the teacher: the official corrigé of TD1 Part II contains two errors.
Ex2 claims the maximum is 30 at (0,6), but that point violates 2x+y>=8.
Ex4 claims 148, which is the maximum; the requested minimum is 100.
The values below are the correct ones.
"""

import sys
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app
from solver.complementary import check_optimality
from solver.dual import dual_solution, dualize, shadow_prices
from solver.examples import EXAMPLES, get_example
from solver.graphical import solve_graphical
from solver.sensitivity import cost_interval, rhs_interval, what_if
from solver.model import F, fmt
from solver.parser import ParseError, parse_lp
from solver.simplex import MNum, solve


def solve_text(text, status, values=None, objective=None):
    """Parse, solve with both engines and check the expected answer."""
    lp = parse_lp(text)
    result = solve(lp)
    assert result.status == status, f"simplex status: {result.status} != {status}"
    if values is not None:
        assert result.x == [F(value) for value in values], f"x = {result.x}"
    if objective is not None:
        assert result.z == F(objective), f"z = {result.z} != {objective}"
    if lp.n == 2:
        graph = solve_graphical(lp)
        assert graph["status"] == status, f"graphical status: {graph['status']}"
        if status == "optimal":
            if values is not None:
                assert graph["x"] == tuple(F(value) for value in values)
            if objective is not None:
                assert graph["z"] == F(objective)
    return result


def test_a1_video():
    """A1: the video example gives (300, 200) and z = 2200."""
    solve_text(EXAMPLES["video"]["text"], "optimal", [300, 200], 2200)


def test_a2_furniture():
    """A2: the furniture example gives (10, 2) and z = 3400."""
    solve_text(EXAMPLES["furniture"]["text"], "optimal", [10, 2], 3400)


def test_a3_td1_p1_ex1():
    """A3: only the first product is produced in TD1 P1 Ex1."""
    solve_text(EXAMPLES["td1_p1_ex1"]["text"], "optimal", [5, 0], 20000)


def test_a4_mixed_max():
    """A4: the mixed-constraint maximum is (2, 4)."""
    solve_text(EXAMPLES["td1_p2_ex2_max"]["text"], "optimal", [2, 4], 26)


def test_a5_mixed_min():
    """A5: the same region minimised gives (4, 0)."""
    solve_text(EXAMPLES["td1_p2_ex2_min"]["text"], "optimal", [4, 0], 12)


def test_a6_infeasible():
    """A6: the third example of TD1 Part II has an empty feasible region."""
    solve_text(EXAMPLES["td1_p2_ex3"]["text"], "infeasible")


def test_a7_equality_min():
    """A7: the equality example has minimum (10, 0) with z = 100."""
    solve_text(EXAMPLES["td1_p2_ex4"]["text"], "optimal", [10, 0], 100)


def test_a8_chapter4():
    """A8: the three-variable Chapter 4 exercise gives z = 3600."""
    solve_text(EXAMPLES["chapter4"]["text"], "optimal", [8, 6, 0], 3600)


def test_a9_chapter3_ex3():
    """A9: fractional answers stay exact (51/4)."""
    solve_text(EXAMPLES["chapter3_ex3"]["text"], "optimal",
               [Fraction(7, 2), Fraction(9, 4), 0], Fraction(51, 4))


def test_a10_chapter3_application():
    """A10: the four-constraint application gives z = 155."""
    solve_text(EXAMPLES["chapter3_app"]["text"], "optimal", [40, 15, 0], 155)


def test_a11_unbounded():
    """A11: both engines detect the unbounded direction."""
    solve_text(EXAMPLES["unbounded"]["text"], "unbounded")


def test_a12_alternative_optima():
    """A12: two vertices reach z = 4 and the flag is raised."""
    result = solve_text(EXAMPLES["alternative"]["text"], "optimal", None, 4)
    lp = parse_lp(EXAMPLES["alternative"]["text"])
    graph = solve_graphical(lp)
    assert result.multiple_optima is True
    assert len(graph["optimal_vertices"]) >= 2


def test_a13_td1_part_i():
    """A13: the real TD1 data gives (10,12,8)/32600 and (50,0,0)/3000."""
    expected = {
        "td1_part1_ex2": ([10, 12, 8], 32600),
        "td1_part1_ex3": ([50, 0, 0], 3000),
    }
    for key, (values, objective) in expected.items():
        lp = parse_lp(EXAMPLES[key]["text"])
        result = solve(lp)
        assert result.status == "optimal", key
        assert result.x == [F(value) for value in values], (key, result.x)
        assert result.z == F(objective), (key, result.z)
        assert lp.is_feasible(result.x), key
        assert result.z == sum((c * x for c, x in zip(lp.c, result.x)), F(0))


def expect_parse_error(text):
    """Check that invalid input raises a friendly ParseError."""
    try:
        parse_lp(text)
    except ParseError as error:
        assert error.message and len(error.message) > 10
        assert "Line" in error.message or "empty" in error.message
        return
    raise AssertionError(f"ParseError expected for {text!r}")


def test_b_nonnegativity_ignored():
    """B: the optional x>=0 line is ignored.

    Discrepancy in the specification: it says '2 constraints' for this text,
    but the text contains only one inequality plus a non-negativity declaration.
    Ignoring that declaration leaves exactly one explicit constraint.
    """
    lp = parse_lp("Max z = 3x1 + 2x2\nx1+x2<=4\nx1>=0,x2>=0")
    assert lp.m == 1
    assert lp.var_names == ["x1", "x2"]


def test_b_move_terms():
    """B: variables on both sides are moved to the left."""
    lp = parse_lp("Max z = x1\nx1 + 2 >= x2 + 5")
    constraint = lp.constraints[0]
    assert constraint.coeffs == [F(1), F(-1)]
    assert constraint.op == ">="
    assert constraint.rhs == F(3)


def test_b_numbers_and_symbols():
    """B: unicode operators, stars, decimals and fractions work."""
    text = "Max z = 2*x1 + 0.5x2 + 1/2x3\nx1 ≤ 3\nx2 ≥ 4\nx3 = 2"
    lp = parse_lp(text)
    assert lp.c == [F(2), Fraction(1, 2), Fraction(1, 2)]
    assert [constraint.op for constraint in lp.constraints] == ["<=", ">=", "="]
    assert [constraint.rhs for constraint in lp.constraints] == [F(3), F(4), F(2)]


def test_b_errors():
    """B: every malformed input gives a friendly message."""
    expect_parse_error("")
    expect_parse_error("x1 <= 3")
    expect_parse_error("Max z = x1\nx1 + 2")
    expect_parse_error("Max z = x1\nx1 +* 2 <= 3")


def test_b_single_variable_bounds():
    """B: x1>=3 is a real constraint, x1>=0 is only a declaration."""
    lp = parse_lp("Max z = x1\nx1 >= 3")
    assert lp.m == 1
    assert lp.constraints[0].rhs == F(3)
    lp = parse_lp("Max z = x1\nx1 >= 0")
    assert lp.m == 0


def test_c_mnum():
    """C: M is symbolic, ordered by its coefficient and printed nicely."""
    assert str(MNum(F(0), F(-1))) == "-M"
    assert str(MNum(Fraction(-5, 3), F(2))) == "2M-5/3"
    assert str(MNum(Fraction(100, 3), F(0))) == "100/3"
    assert MNum(F(0), F(-1)) < MNum(F(0), F(0)) < MNum(F(0), F(1))
    assert MNum(F(1000), F(0)) < MNum(F(0), F(1))
    assert MNum(F(1), F(1)) + MNum(F(-1), F(-1)) == MNum(F(0), F(0))


def test_c_artificial_variables():
    """C: A8, A9 and A10 need artificial variables in the first tableau."""
    for key in ("chapter4", "chapter3_ex3", "chapter3_app"):
        result = solve(parse_lp(EXAMPLES[key]["text"]))
        assert any(name.startswith("a") for name in result.steps[0]["basis"]), key
        assert result.status == "optimal", key


def test_c_furniture_tableaux():
    """C: the first and last furniture tableaux match the course sheet."""
    result = solve(parse_lp(EXAMPLES["furniture"]["text"]))
    assert result.steps[0]["basis"] == ["e1", "e2", "e3"]
    assert result.steps[0]["entering"] == "x1"
    assert result.steps[0]["delta"][0] == "300"
    last = result.steps[-1]
    assert last["zj"] == ["300", "200", "0", "100", "100"]
    assert last["delta"] == ["0", "0", "0", "-100", "-100"]


def test_c_degenerate():
    """C: a degenerate optimum is solved and reported."""
    result = solve(parse_lp(get_example("degenerate")["text"]))
    assert result.status == "optimal"
    assert result.degenerate is True
    assert result.x == [F(4), F(0)]


def test_fmt():
    """Fractions are printed as on the blackboard."""
    assert fmt(Fraction(7, 2)) == "7/2"
    assert fmt(F(3)) == "3"


def dual_for(key):
    """Dualise a named example, using its explicit variable signs if present."""
    item = EXAMPLES[key]
    return dualize(parse_lp(item["text"]), item.get("var_signs"))


def test_d_furniture_dual():
    """D: the furniture dual is Min 20y1+22y2+12y3 with y=(0,100,100)."""
    lp = parse_lp(EXAMPLES["furniture"]["text"])
    dual = dual_for("furniture")
    assert dual.sense == "min"
    assert dual.c == [F(20), F(22), F(12)]
    assert dual.A == [[F(1), F(2), F(1)], [F(2), F(1), F(1)]]
    assert dual.ops == [">=", ">="]
    assert dual.b == [F(300), F(200)]
    assert dual.var_signs == [">=0"] * 3
    info = dual_solution(lp, solve(lp))
    assert info["y"] == [F(0), F(100), F(100)]
    assert info["w"] == F(3400)
    assert info["shadow_prices"] == [F(0), F(100), F(100)]


def test_d_series3_duals():
    """D: the four programs of Series 3 Ex1 match the slide results."""
    expected = {
        "series3_p1": ([60, 40, 80], [">=", ">=", ">="], [">=0"] * 3),
        "series3_p2": ([10, 7, 8], ["=", ">=", ">="], ["<=0", "free", ">=0"]),
        "series3_p3": ([12, 8, 6], [">=", ">="], ["<=0", "<=0", ">=0"]),
        "series3_p4": ([12, 18, 10], ["=", ">=", "="], [">=0", "free", "<=0"]),
    }
    for key, (c, ops, signs) in expected.items():
        dual = dual_for(key)
        assert dual.sense == "min", key
        assert dual.c == [F(value) for value in c], key
        assert dual.ops == ops, key
        assert dual.var_signs == signs, key
    dual = dual_for("series3_p2")
    assert dual.A == [[1, 3, 1], [2, -1, 0], [0, 1, 3]]
    assert dual.b == [F(3), F(1), F(-2)]
    dual = dual_for("series3_p4")
    assert [dual.A[0], dual.A[1], dual.A[2]] == [
        [2, 1, 3], [1, 2, 1], [1, 3, 2]
    ]


def test_d_strong_duality():
    """D: primal z and dual w agree for five different programs."""
    for key in ("video", "furniture", "chapter4", "chapter3_ex3", "chapter3_app"):
        lp = parse_lp(EXAMPLES[key]["text"])
        primal = solve(lp)
        info = dual_solution(lp, primal)
        assert primal.status == "optimal", key
        assert info["w"] == primal.z, (key, info["w"], primal.z)


def test_e_complementary_not_optimal():
    """E: Series 3 Ex2 P1 gives y=(1,1,0,1), which is not dual feasible."""
    item = EXAMPLES["series3_ex2_p1"]
    result = check_optimality(parse_lp(item["text"]), item["proposed"])
    assert result.verdict == "not optimal"
    assert result.y == [F(1), F(1), F(0), F(1)]
    assert any("Dual constraint 5" in step and ">= 3" in step for step in result.steps)


def test_e_complementary_optimal():
    """E: both other course examples pass complementary slackness."""
    cases = {
        "series3_ex2_p2": ([Fraction(1, 2), Fraction(3, 2), F(0), F(0), Fraction(3, 2), F(0)]),
        "chapter3_page9": ([F(5), F(10), F(0)]),
    }
    for key, expected_y in cases.items():
        item = EXAMPLES[key]
        result = check_optimality(parse_lp(item["text"]), item["proposed"])
        assert result.verdict == "optimal", (key, result.steps)
        assert result.y == expected_y, key
        assert result.dual_feasible is True


def test_e_series3_p2_strong_duality():
    """E: for the real P2 the proposed point has z = w = 17."""
    item = EXAMPLES["series3_ex2_p2"]
    lp = parse_lp(item["text"])
    optimal = solve(lp)
    info = dual_solution(lp, optimal)
    assert optimal.z == F(17)
    assert info["w"] == F(17)


def test_e_infeasible_proposed_point():
    """E: a point outside the feasible region is rejected immediately."""
    lp = parse_lp(EXAMPLES["furniture"]["text"])
    result = check_optimality(lp, ["100", "100"])
    assert result.verdict == "not optimal"
    assert result.primal_feasible is False


def check_interval(payload, lower, upper, z_low=None, z_high=None):
    """Compare one sensitivity interval with the expected exact values."""
    if lower is None:
        assert payload["lower"] is None, (payload["name"], payload["lower"])
    else:
        assert payload["lower"] == F(lower), (payload["name"], payload["lower"], lower)
    assert payload["upper"] == F(upper) if upper is not None else payload["upper"] is None
    if z_low is not None:
        assert payload["z_min"] == F(z_low)
    if z_high is not None:
        assert payload["z_max"] == F(z_high)


def test_f_furniture_sensitivity():
    """F: all furniture ranges and z ranges match Chapter 4."""
    lp = parse_lp(EXAMPLES["furniture"]["text"])
    result = solve(lp)
    check_interval(cost_interval(result, 0), 200, 400, 2400, 4400)
    check_interval(cost_interval(result, 1), 150, 300, 3300, 3600)
    check_interval(rhs_interval(result, 0), 14, None, 3400)
    check_interval(rhs_interval(result, 1), 16, 24, 2800, 3600)
    check_interval(rhs_interval(result, 2), 11, 14, 3300, 3600)
    assert rhs_interval(result, 0)["state"] == "marginal"
    assert rhs_interval(result, 1)["state"] == "binding"


def test_f_chapter4_sensitivity():
    """F: the Chapter 4 exercise has the expected ranges, including c3."""
    lp = parse_lp(EXAMPLES["chapter4"]["text"])
    result = solve(lp)
    check_interval(cost_interval(result, 0), 250, 400, 3200, 4400)
    check_interval(cost_interval(result, 2), None, Fraction(500, 3))
    assert cost_interval(result, 2)["basic"] is False
    check_interval(rhs_interval(result, 0), None, 14)
    check_interval(rhs_interval(result, 1), 11, 44)
    check_interval(rhs_interval(result, 2), 10, 40)


def test_f_min_sensitivity():
    """F: a minimisation problem uses the sign of the internal -z correctly."""
    lp = parse_lp(EXAMPLES["td1_p2_ex2_min"]["text"])
    result = solve(lp)
    check_interval(cost_interval(result, 0), 0, 10, 0, 40)
    check_interval(cost_interval(result, 1), Fraction(3, 2), None, 12, 12)
    check_interval(rhs_interval(result, 1), 0, 12, 0, 18)


def test_f_what_if():
    """F: c1=350 keeps the basis, c1=450 triggers a re-solve."""
    lp = parse_lp(EXAMPLES["furniture"]["text"])
    same = what_if(lp, "c", 0, 350)
    assert same["basis_changed"] is False
    assert F(same["z"]) == F(3900)
    different = what_if(lp, "c", 0, 450)
    assert different["basis_changed"] is True
    assert "Basis changed" in different["message"]
    assert F(different["z"]) != F(3900)


def test_g_examples_api_contract():
    """G: the examples endpoint is a list of complete example cards."""
    payload = create_app().test_client().get("/api/examples").get_json()
    assert payload["ok"] is True
    assert isinstance(payload["examples"], list)
    assert payload["examples"]
    for item in payload["examples"]:
        assert {"id", "title", "description", "text"} <= set(item), item
        assert isinstance(item["id"], str) and item["id"]
        assert isinstance(item["title"], str) and item["title"]
        assert isinstance(item["description"], str)
        assert isinstance(item["text"], str) and "z =" in item["text"]


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\n{len(tests)} tests passed.")
