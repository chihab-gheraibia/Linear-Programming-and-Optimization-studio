"""Complementary slackness as a hand-written exact linear system.

For a proposed point we set y_i = 0 on every non-saturated constraint and turn
each dual constraint of a positive variable into an equality. The small system
is solved with Gauss-Jordan on Fractions, then the dual signs and constraints
are checked to give an honest verdict.
"""

from dataclasses import dataclass

from .dual import dualize
from .model import F, fmt


@dataclass
class CheckResult:
    """The verdict and the full reasoning of a complementary-slackness test."""

    verdict: str
    y: object
    steps: list
    primal_feasible: bool
    dual_feasible: bool

    def to_dict(self):
        """Return a JSON-ready payload for the interpretation panel."""
        return {
            "ok": True,
            "verdict": self.verdict,
            "y": None if self.y is None else [fmt(value) for value in self.y],
            "steps": self.steps,
            "primal_feasible": self.primal_feasible,
            "dual_feasible": self.dual_feasible,
        }


def gauss_jordan(matrix, right_hand_side):
    """Solve A y = b exactly; report inconsistent or underdetermined systems."""
    rows = len(matrix)
    columns = len(matrix[0]) if rows else 0
    augmented = [list(matrix[i]) + [F(right_hand_side[i])] for i in range(rows)]
    pivots = []
    pivot_row = 0
    for column in range(columns):
        chosen = next((r for r in range(pivot_row, rows) if augmented[r][column] != 0), None)
        if chosen is None:
            continue
        augmented[pivot_row], augmented[chosen] = augmented[chosen], augmented[pivot_row]
        divide_row(augmented[pivot_row], column)
        for r in range(rows):
            if r != pivot_row and augmented[r][column] != 0:
                eliminate(augmented[r], augmented[pivot_row], column)
        pivots.append(column)
        pivot_row += 1
        if pivot_row == rows:
            break
    for row in range(pivot_row, rows):
        if all(value == 0 for value in row_values(augmented, row, columns)) and augmented[row][columns] != 0:
            return "inconsistent", None, pivots
    free = [column for column in range(columns) if column not in pivots]
    if free:
        return "underdetermined", None, free
    solution = [F(0)] * columns
    for r, column in enumerate(pivots):
        solution[column] = augmented[r][columns]
    return "unique", solution, []


def row_values(augmented, row, columns):
    """Return the coefficient part of one augmented row."""
    return augmented[row][:columns]


def divide_row(row, column):
    """Normalise a pivot row so that the pivot becomes 1."""
    divisor = row[column]
    for index in range(len(row)):
        row[index] /= divisor


def eliminate(row, pivot, column):
    """Clear one column using the normalised pivot row."""
    factor = row[column]
    for index in range(len(row)):
        row[index] -= factor * pivot[index]


def left_value(coefficients, values):
    """Compute a·y without any floating point arithmetic."""
    return sum((a * F(v) for a, v in zip(coefficients, values)), F(0))


def is_saturated(constraint, left):
    """Say whether a constraint is tight at the proposed point."""
    if constraint.op == "=":
        return True
    return left == constraint.rhs


def violation(lp, x):
    """Return the first violated constraint number, or None when feasible."""
    if any(F(value) < 0 for value in x):
        return "x >= 0"
    for index, constraint in enumerate(lp.constraints, start=1):
        left = left_value(constraint.coeffs, x)
        if constraint.op == "<=" and left > constraint.rhs:
            return index
        if constraint.op == ">=" and left < constraint.rhs:
            return index
        if constraint.op == "=" and left != constraint.rhs:
            return index
    return None


def dual_sign_problem(dual, y):
    """Return a sentence if a dual variable has the wrong sign."""
    for name, sign, value in zip(dual.var_names, dual.var_signs, y):
        if sign == ">=0" and value < 0:
            return f"{name} = {fmt(value)} is negative, but it must be >= 0."
        if sign == "<=0" and value > 0:
            return f"{name} = {fmt(value)} is positive, but it must be <= 0."
    return None


def dual_constraint_problem(dual, y):
    """Return a sentence if one dual constraint is not satisfied."""
    for index, (row, op, rhs) in enumerate(zip(dual.A, dual.ops, dual.b), start=1):
        left = left_value(row, y)
        if op == ">=" and left < rhs:
            return f"Dual constraint {index}: {fmt(left)} >= {fmt(rhs)} is false."
        if op == "<=" and left > rhs:
            return f"Dual constraint {index}: {fmt(left)} <= {fmt(rhs)} is false."
        if op == "=" and left != rhs:
            return f"Dual constraint {index}: {fmt(left)} = {fmt(rhs)} is false."
    return None


def build_equations(lp, dual, x):
    """Write y_i = 0 on slack constraints and equalities for positive x_j."""
    matrix = []
    right_hand_side = []
    for i, constraint in enumerate(lp.constraints):
        if not is_saturated(constraint, left_value(constraint.coeffs, x)):
            row = [F(0)] * lp.m
            row[i] = F(1)
            matrix.append(row)
            right_hand_side.append(F(0))
    for j, value in enumerate(x):
        if value > 0:
            matrix.append(list(dual.A[j]))
            right_hand_side.append(dual.b[j])
    return matrix, right_hand_side


def check_optimality(lp, x_proposed, primal_var_signs=None):
    """Check whether a proposed primal point is optimal, with full reasoning."""
    if len(x_proposed) != lp.n:
        return CheckResult("not optimal", None, ["The point has the wrong size."], False, False)
    x = [F(value) for value in x_proposed]
    steps = []
    bad = violation(lp, x)
    if bad is not None:
        steps.append(f"The point is not primal feasible: {bad} is violated.")
        return CheckResult("not optimal", None, steps, False, False)
    steps.append("The point is primal feasible: x >= 0 and every constraint holds.")
    dual = dualize(lp, primal_var_signs)
    matrix, right_hand_side = build_equations(lp, dual, x)
    steps.extend(system_steps(lp, dual, x, matrix))
    return finish_check(dual, matrix, right_hand_side, steps)


def system_steps(lp, dual, x, matrix):
    """Explain which complementary-slackness equations were written."""
    steps = []
    for i, constraint in enumerate(lp.constraints):
        if not is_saturated(constraint, left_value(constraint.coeffs, x)):
            steps.append(f"Constraint {i + 1} is not saturated, so y{i + 1} = 0.")
    for j, value in enumerate(x):
        if value > 0:
            steps.append(
                f"x{j + 1} = {fmt(value)} > 0, so dual constraint {j + 1} is an equality."
            )
    steps.append(f"Solving the {len(matrix)} equation(s) by Gauss-Jordan gives:")
    return steps


def finish_check(dual, matrix, right_hand_side, steps):
    """Solve the system and check dual feasibility to give the final verdict."""
    status, y, information = gauss_jordan(matrix, right_hand_side)
    if status == "inconsistent":
        steps.append("The equations are contradictory, so no dual y exists; the point is not optimal.")
        return CheckResult("not optimal", None, steps, True, False)
    if status == "underdetermined":
        names = [dual.var_names[i] for i in information]
        steps.append(f"The system leaves {', '.join(names)} free: the verdict is undetermined.")
        return CheckResult("undetermined", None, steps, True, False)
    steps.append("y = (" + ", ".join(fmt(value) for value in y) + ").")
    problem = dual_sign_problem(dual, y) or dual_constraint_problem(dual, y)
    if problem is not None:
        steps.append(problem)
        steps.append("This y is not dual feasible, so the point is not optimal.")
        return CheckResult("not optimal", y, steps, True, False)
    steps.append("All dual constraints and signs hold: the duality gap is zero, so the point is optimal.")
    return CheckResult("optimal", y, steps, True, True)
