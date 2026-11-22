"""Dualisation using the Chapter 3 table, with the sign rules of the course.

The dual is first built as a display object because it may contain variables
that are <= 0 or free. The function dual_to_lp then substitutes y=-y' or
y=y+-y- so that the same simplex can solve it.
"""

from dataclasses import dataclass, field

from .model import Constraint, F, LP, fmt
from .simplex import mstr, solve


@dataclass
class DualProblem:
    """The dual written with the original y variables and their real signs."""

    sense: str
    c: list
    A: list
    ops: list
    b: list
    var_names: list
    var_signs: list
    primal_var_signs: list
    rules: list = field(default_factory=list)

    def evaluate(self, y):
        """Compute the dual objective w = c.y exactly."""
        return sum((coefficient * F(value) for coefficient, value in zip(self.c, y)), F(0))

    def sign_text(self):
        """Write the sign restrictions on one line."""
        return ", ".join(f"{name} {sign}" for name, sign in zip(self.var_names, self.var_signs))

    def to_text(self):
        """Print the dual like a course exercise statement."""
        kind = "Min" if self.sense == "min" else "Max"
        objective = " + ".join(f"{fmt(value)}{name}" for value, name in zip(self.c, self.var_names))
        lines = [f"{kind} w = {objective}", "s.c."]
        for row, op, rhs in zip(self.A, self.ops, self.b):
            line = " ".join(
                f"{'+' if value >= 0 else '-'} {fmt(abs(value))}{name}"
                for value, name in zip(row, self.var_names) if value != 0
            ).lstrip("+ ")
            symbol = {"<=": "≤", ">=": "≥", "=": "="}[op]
            lines.append(f"  {line} {symbol} {fmt(rhs)}")
        lines.append(f"  {self.sign_text()}")
        return "\n".join(lines)

    def to_dict(self):
        """Return a JSON-ready version for the dual panel."""
        return {
            "sense": self.sense,
            "c": [fmt(value) for value in self.c],
            "c_float": [float(value) for value in self.c],
            "A": [[fmt(value) for value in row] for row in self.A],
            "ops": self.ops,
            "b": [fmt(value) for value in self.b],
            "var_names": self.var_names,
            "var_signs": self.var_signs,
            "rules": self.rules,
            "text": self.to_text(),
        }


def constraint_sign(op, sense):
    """Give the sign of a dual variable from the primal constraint and sense."""
    if sense == "max":
        return {"<=": ">=0", ">=": "<=0", "=": "free"}[op]
    return {">=": ">=0", "<=": "<=0", "=": "free"}[op]


def variable_operator(sign, sense):
    """Give the dual constraint operator from a primal variable sign."""
    if sign == "free":
        return "="
    if sense == "max":
        return ">=" if sign == ">=0" else "<="
    return "<=" if sign == ">=0" else ">="


def explain_steps(lp, primal_signs, dual_signs, dual_ops):
    """List the Chapter 3 rules applied, one short sentence per rule."""
    kind = "maximisation" if lp.sense == "max" else "minimisation"
    target = "minimisation" if lp.sense == "max" else "maximisation"
    rules = [
        f"The primal is a {kind}, so the dual is a {target} with {lp.m} variable(s).",
        "The dual objective coefficients are the right-hand sides of the primal.",
        "The right-hand sides of the dual are the coefficients of the primal objective.",
    ]
    for i, (constraint, sign) in enumerate(zip(lp.constraints, dual_signs), start=1):
        rules.append(
            f"Primal constraint {i} is '{constraint.op}', so y{i} is {sign}."
        )
    for j, (name, sign, op) in enumerate(zip(lp.var_names, primal_signs, dual_ops), start=1):
        rules.append(
            f"Primal variable {name} is {sign}, so dual constraint {j} uses '{op}'."
        )
    return rules


def dualize(lp: LP, primal_var_signs=None) -> DualProblem:
    """Build the dual display problem from a primal LP and optional var signs."""
    signs = list(primal_var_signs) if primal_var_signs is not None else [">=0"] * lp.n
    if len(signs) != lp.n:
        raise ValueError("primal_var_signs must have one entry per primal variable.")
    if any(sign not in (">=0", "<=0", "free") for sign in signs):
        raise ValueError("Variable signs must be '>=0', '<=0' or 'free'.")
    dual_signs = [constraint_sign(constraint.op, lp.sense) for constraint in lp.constraints]
    dual_ops = [variable_operator(sign, lp.sense) for sign in signs]
    matrix = [
        [lp.constraints[i].coeffs[j] for i in range(lp.m)] for j in range(lp.n)
    ]
    dual = DualProblem(
        "min" if lp.sense == "max" else "max",
        [constraint.rhs for constraint in lp.constraints],
        matrix,
        dual_ops,
        list(lp.c),
        [f"y{i + 1}" for i in range(lp.m)],
        dual_signs,
        signs,
    )
    dual.rules = explain_steps(lp, signs, dual_signs, dual_ops)
    return dual


def build_substitutions(dual):
    """Replace y<=0 by -y' and free y by y+ - y-, with explicit indices."""
    substitutions = []
    names = []
    for i, (name, sign) in enumerate(zip(dual.var_names, dual.var_signs)):
        if sign == ">=0":
            substitutions.append(("direct", i, len(names)))
            names.append(name)
        elif sign == "<=0":
            substitutions.append(("negative", i, len(names)))
            names.append(name + "'")
        else:
            substitutions.append(("free", i, len(names), len(names) + 1))
            names.extend([name + "+", name + "-"])
    return substitutions, names


def dual_to_lp(dual: DualProblem):
    """Convert the display dual into a solvable LP (all variables >= 0)."""
    substitutions, names = build_substitutions(dual)
    rows = [[F(0)] * len(names) for _ in range(len(dual.A))]
    objective = [F(0)] * len(names)
    for item in substitutions:
        original = item[1]
        if item[0] == "free":
            places = [(item[2], F(1)), (item[3], F(-1))]
        else:
            places = [(item[2], F(-1) if item[0] == "negative" else F(1))]
        for place, factor in places:
            objective[place] = dual.c[original] * factor
            for row_index, row in enumerate(rows):
                row[place] = dual.A[row_index][original] * factor
    constraints = [
        Constraint(row, op, rhs) for row, op, rhs in zip(rows, dual.ops, dual.b)
    ]
    return LP(dual.sense, objective, constraints, names), substitutions


def recover_y(substitutions, x):
    """Read the original y values back from the substituted LP solution."""
    values = [F(0)] * len(substitutions)
    for item in substitutions:
        original = item[1]
        if item[0] == "direct":
            values[original] = x[item[2]]
        elif item[0] == "negative":
            values[original] = -x[item[2]]
        else:
            values[original] = x[item[2]] - x[item[3]]
    return values


def shadow_prices(lp, result):
    """Read the marginal values of the right-hand sides in the final tableau."""
    if result is None or result.status != "optimal":
        return [None] * lp.m
    final = result.final
    prices = []
    for i, op in enumerate(final["ops"]):
        column = final["n"] + i
        value = final["zj"][column]
        price = value.a * final["internal_sign"]
        if op == "<=":
            prices.append(price)
        elif op == ">=":
            prices.append(-price)
        else:
            prices.append(F(0))
    return prices


def dual_solution(lp, primal_result=None, primal_var_signs=None):
    """Solve the dual and return y, w, the rules and the shadow prices."""
    dual = dualize(lp, primal_var_signs)
    solvable, substitutions = dual_to_lp(dual)
    solved = solve(solvable)
    y = recover_y(substitutions, solved.x) if solved.status == "optimal" else None
    w = dual.evaluate(y) if y is not None else None
    return {
        "dual": dual,
        "solution": solved,
        "y": y,
        "w": w,
        "rules": dual.rules,
        "shadow_prices": shadow_prices(lp, primal_result),
    }


def dual_solution_to_dict(info):
    """Return a JSON-ready dual panel payload."""
    y, w = info["y"], info["w"]
    return {
        "ok": True,
        "dual": info["dual"].to_dict(),
        "y": None if y is None else [mstr(value) for value in y],
        "y_float": None if y is None else [float(value) for value in y],
        "w": None if w is None else mstr(w),
        "w_float": None if w is None else float(w),
        "rules": info["rules"],
        "shadow_prices": [
            None if price is None else mstr(price) for price in info["shadow_prices"]
        ],
    }
