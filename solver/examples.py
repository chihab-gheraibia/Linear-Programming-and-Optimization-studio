"""All the course examples, ready to load in the interface or in the tests."""

from .model import F


EXAMPLES = {
    "video": {
        "name": "Video example",
        "description": "Two products, three limited resources (max, 2 variables).",
        "text": """Max z = 4xA + 5xB
2xA + xB <= 800
xA + 2xB <= 700
xB <= 300""",
    },
    "furniture": {
        "name": "Furniture",
        "description": "Tables and chairs: the reference example for sensitivity.",
        "text": """Max z = 300x1 + 200x2
x1 + 2x2 <= 20
2x1 + x2 <= 22
x1 + x2 <= 12""",
    },
    "td1_p1_ex1": {
        "name": "TD1 P1 Ex1",
        "description": "Two products and two workshop capacities.",
        "text": """Max z = 4000x1 + 4500x2
10x1 + 20x2 <= 50
12x1 + 16x2 <= 60""",
    },
    "td1_p2_ex2_max": {
        "name": "TD1 P2 Ex2 (max)",
        "description": "A mixed <= / >= region with two variables.",
        "text": """Max z = 3x + 5y
x + y <= 6
2x + y >= 8""",
    },
    "td1_p2_ex2_min": {
        "name": "TD1 P2 Ex2 (min)",
        "description": "Same constraints, but we minimise the cost.",
        "text": """Min z = 3x + 5y
x + y <= 6
2x + y >= 8""",
    },
    "td1_p2_ex3": {
        "name": "TD1 P2 Ex3",
        "description": "An empty feasible region (infeasible).",
        "text": """Max z = 3x1 + x2
x1 - x2 <= 4
-x1 - x2 <= -3
2x1 + x2 <= 2""",
    },
    "td1_p2_ex4": {
        "name": "TD1 P2 Ex4",
        "description": "An equality and two simple bounds (min).",
        "text": """Min z = 10x1 + 20x2
10x1 + 8x2 = 100
x1 >= 3
x2 <= 4""",
    },
    "chapter4": {
        "name": "Chapter 4 exercise",
        "description": "Three products, one >= and two <= constraints.",
        "text": """Max z = 300x1 + 200x2 + 150x3
x1 + x2 + x3 >= 10
x1 + 2x2 + x3 <= 20
2x1 + x2 + x3 <= 22""",
    },
    "chapter3_ex3": {
        "name": "Chapter 3 Ex3",
        "description": "Minimisation with artificial variables.",
        "text": """Min z = 3x1 + x2 + x3
x1 + 2x2 >= 8
3x1 - 2x2 + x3 >= 6""",
    },
    "chapter3_app": {
        "name": "Chapter 3 application",
        "description": "Four >= constraints and three decision variables.",
        "text": """Min z = 2x1 + 5x2 + 3x3
x1 >= 10
x2 >= 15
x1 + 2x2 + x3 >= 60
2x1 + x2 + 2x3 >= 95""",
    },
    "unbounded": {
        "name": "Unbounded region",
        "description": "One weak constraint: the objective can grow forever.",
        "text": """Max z = x1 + x2
x1 - x2 <= 1""",
    },
    "alternative": {
        "name": "Alternative optima",
        "description": "Two vertices give the same best value.",
        "text": """Max z = x1 + x2
x1 + x2 <= 4
x1 <= 3""",
    },
    "degenerate": {
        "name": "Degenerate solution",
        "description": "A basic variable is zero; Bland's rule prevents cycling.",
        "text": """Max z = 3x1 + 2x2
x1 + x2 <= 4
x1 <= 4
x2 <= 4""",
    },
    "td1_part1_ex2": {
        "name": "TD1 Part I Ex2",
        "description": "Three processes sharing four resources (real TD1 data).",
        "text": """Max z = 1100x1 + 1200x2 + 900x3
3x1 + 2x2 + 4x3 <= 86
2x1 + 3x2 + x3 <= 64
3x1 + 6x2 + 4x3 <= 156
5x1 + 4x2 + 5x3 <= 138""",
    },
    "td1_part1_ex3": {
        "name": "TD1 Part I Ex3",
        "description": "Net profits 60 / 30 / 60 with four raw materials (real TD1 data).",
        "text": """Max z = 60x1 + 30x2 + 60x3
2x2 + 3x3 <= 50
3x1 + 2x2 + x3 <= 200
4x1 + 4x2 + 6x3 <= 200
2x3 <= 100""",
    },
    "series3_p1": {
        "name": "Series 3 Ex1 P1",
        "description": "Primal whose dual has three non-negative variables.",
        "text": """Max z = 2x1 + 4x2 + 3x3
3x1 + 2x2 + x3 <= 60
4x1 + x2 + 3x3 <= 40
2x1 + 2x2 + 2x3 <= 80""",
    },
    "series3_p2": {
        "name": "Series 3 Ex1 P2",
        "description": "Primal with one free variable (x1) and mixed operators.",
        "text": """Max z = 3x1 + x2 - 2x3
x1 + 2x2 >= 10
3x1 - x2 + x3 = 7
x1 + 3x3 <= 8""",
        "var_signs": ["free", ">=0", ">=0"],
    },
    "series3_p3": {
        "name": "Series 3 Ex1 P3",
        "description": "Primal giving two non-positive dual variables.",
        "text": """Max z = 10x1 + 14x2
x1 + x2 >= 12
x1 >= 8
x2 <= 6""",
    },
    "series3_p4": {
        "name": "Series 3 Ex1 P4",
        "description": "Primal with two free variables and a free dual variable.",
        "text": """Max z = 5x1 + 3x2 + 4x3
2x1 + x2 + x3 <= 12
x1 + 2x2 + 3x3 = 18
3x1 + x2 + 2x3 >= 10""",
        "var_signs": ["free", ">=0", "free"],
    },
    "series3_ex2_p1": {
        "name": "Series 3 Ex2 P1",
        "description": "A proposed point that fails complementary slackness.",
        "text": """Max z = 7x1 + 6x2 + 5x3 - 2x4 + 3x5
x1 + 3x2 + 5x3 - 2x4 + 2x5 <= 4
4x1 + 2x2 - 2x3 + x4 + x5 <= 3
2x1 + 4x2 + 4x3 - 2x4 + 5x5 <= 5
3x1 + x2 + 2x3 - x4 - 2x5 <= 1""",
        "proposed": ["0", "4/3", "2/3", "5/3", "0"],
    },
    "series3_ex2_p2": {
        "name": "Series 3 Ex2 P2",
        "description": "A proposed point that passes complementary slackness.",
        "text": """Max z = 4x1 + 5x2 + x3 + 3x4 - 5x5 + 8x6
x1 - 4x3 + 3x4 + x5 + x6 <= 1
5x1 + 3x2 + x3 - 5x5 + 3x6 <= 4
4x1 + 5x2 - 3x3 + 3x4 - 4x5 + x6 <= 4
-x2 + 2x4 + x5 - 5x6 <= 5
-2x1 + x2 + x3 + x4 + 2x5 + 2x6 <= 7
2x1 - 3x2 + 2x3 - x4 + 4x5 + 5x6 <= 5""",
        "proposed": ["0", "0", "5/2", "7/2", "0", "1/2"],
    },
    "chapter3_page9": {
        "name": "Chapter 3 page 9",
        "description": "Complementary slackness check on a two-variable maximum.",
        "text": """Max z = 15x1 + 25x2
x1 + 3x2 <= 96
x1 + x2 <= 40
7x1 + 4x2 <= 238""",
        "proposed": ["12", "28"],
    },
}


def list_examples():
    """Return the short list used by the example cards in the interface."""
    return [
        {"key": key, "name": item["name"], "description": item["description"]}
        for key, item in EXAMPLES.items()
    ]


def get_example(key):
    """Return one example, or None when the key is unknown."""
    return EXAMPLES.get(key)


def example_numbers(key):
    """Return the numeric arrays (sense, c, A, ops, b) of an example."""
    from .parser import parse_lp

    lp = parse_lp(EXAMPLES[key]["text"])
    return {
        "sense": lp.sense,
        "c": [F(value) for value in lp.c],
        "A": [list(constraint.coeffs) for constraint in lp.constraints],
        "ops": [constraint.op for constraint in lp.constraints],
        "b": [constraint.rhs for constraint in lp.constraints],
        "names": lp.var_names,
    }
