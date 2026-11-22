"""Complementary slackness with exact equations and a simplex parameter search.

For a proposed point we set y_i = 0 on every non-saturated constraint and turn
each dual constraint of a positive variable into an equality. If that system is
under-determined, we parametrise it and use our own simplex to search the free
parameters under all dual signs and dual constraints.
"""

from dataclasses import dataclass, field

from .dual import dualize
from .model import Constraint, F, LP, fmt
from .simplex import solve


@dataclass
class CheckResult:
    """The verdict, a possible dual vector and the full reasoning."""

    verdict: str
    y: object
    steps: list
    primal_feasible: bool
    dual_feasible: bool
    reason: str = ""

    def to_dict(self):
        """Return a JSON-ready payload for the interpretation panel."""
        return {
            "ok": True,
            "verdict": self.verdict,
            "y": None if self.y is None else [fmt(value) for value in self.y],
            "steps": self.steps,
            "primal_feasible": self.primal_feasible,
            "dual_feasible": self.dual_feasible,
            "reason": self.reason,
        }


def gauss_jordan(matrix, right_hand_side):
    """Solve A y = b exactly and return a particular solution plus directions."""
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
            return "inconsistent", None, []
    free = [column for column in range(columns) if column not in pivots]
    if free:
        family = parametrize(augmented, pivots, free, columns)
        return "underdetermined", family, free
    solution = [F(0)] * columns
    for r, column in enumerate(pivots):
        solution[column] = augmented[r][columns]
    return "unique", solution, []


def parametrize(augmented, pivots, free, columns):
    """Write every solution as particular + one direction per free variable."""
    particular = [F(0)] * columns
    directions = []
    for row, column in enumerate(pivots):
        particular[column] = augmented[row][columns]
    for free_column in free:
        direction = [F(0)] * columns
        direction[free_column] = F(1)
        for row, column in enumerate(pivots):
            direction[column] = -augmented[row][free_column]
        directions.append(direction)
    return {"particular": particular, "directions": directions, "free": free}


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
            return f"{name} = {fmt(value)} is negative, but it must be ≥ 0."
        if sign == "<=0" and value > 0:
            return f"{name} = {fmt(value)} is positive, but it must be ≤ 0."
    return None


def dual_constraint_problem(dual, y):
    """Return a sentence if one dual constraint is not satisfied."""
    for index, (row, op, rhs) in enumerate(zip(dual.A, dual.ops, dual.b), start=1):
        left = left_value(row, y)
        symbol = {"<=": "≤", ">=": "≥", "=": "="}[op]
        if op == ">=" and left < rhs:
            return f"Dual constraint {index}: {fmt(left)} {symbol} {fmt(rhs)} is false."
        if op == "<=" and left > rhs:
            return f"Dual constraint {index}: {fmt(left)} {symbol} {fmt(rhs)} is false."
        if op == "=" and left != rhs:
            return f"Dual constraint {index}: {fmt(left)} {symbol} {fmt(rhs)} is false."
    return None


def dual_problem(dual, y):
    """Return the first dual infeasibility sentence, if any."""
    return dual_sign_problem(dual, y) or dual_constraint_problem(dual, y)


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


def coefficient_text(value):
    """Print a coefficient, hiding 1 and -1 in front of a parameter."""
    if value == 1:
        return ""
    if value == -1:
        return "-"
    return fmt(value)


def format_parametrization(dual, family):
    """Write the affine family in a readable y = (...) form."""
    expressions = []
    for index in range(len(dual.var_names)):
        terms = []
        constant = family["particular"][index]
        if constant != 0:
            terms.append(fmt(constant))
        for number, direction in enumerate(family["directions"], start=1):
            coefficient = direction[index]
            if coefficient == 0:
                continue
            symbol = f"t{number}"
            if coefficient > 0:
                terms.append(f"{coefficient_text(coefficient)}{symbol}")
            else:
                terms.append(f"-{coefficient_text(-coefficient)}{symbol}")
        if not terms:
            terms = ["0"]
        expression = terms[0]
        for term in terms[1:]:
            if term.startswith("-"):
                expression += f" - {term[1:]}"
            else:
                expression += f" + {term}"
        expressions.append(expression)
    names = ", ".join(f"t{number}" for number in range(1, len(family["directions"]) + 1))
    return f"y = ({', '.join(expressions)}), with {names} free"


def parameter_row(weights, size):
    """Convert t = t⁺ - t⁻ weights into a row of the feasibility LP."""
    row = [F(0)] * size
    for index, weight in enumerate(weights):
        row[2 * index] = weight
        row[2 * index + 1] = -weight
    return row


def search_parameters(dual, family):
    """Use our simplex to find free parameters giving a dual-feasible y."""
    free_count = len(family["directions"])
    size = 2 * free_count
    names = []
    for number in range(1, free_count + 1):
        names.extend([f"t{number}+", f"t{number}-"])
    rows = []
    ops = []
    bounds = []
    for index, sign in enumerate(dual.var_signs):
        if sign == "free":
            continue
        weights = [direction[index] for direction in family["directions"]]
        constant = family["particular"][index]
        operator = ">=" if sign == ">=0" else "<="
        rows.append(parameter_row(weights, size))
        ops.append(operator)
        bounds.append(-constant)
    for coefficients, operator, rhs in zip(dual.A, dual.ops, dual.b):
        weights = [
            sum((value * direction[index] for index, value in enumerate(coefficients)), F(0))
            for direction in family["directions"]
        ]
        constant = left_value(coefficients, family["particular"])
        rows.append(parameter_row(weights, size))
        ops.append(operator)
        bounds.append(rhs - constant)
    objective = [F(1)] * size
    constraints = [Constraint(row, op, bound) for row, op, bound in zip(rows, ops, bounds)]
    solved = solve(LP("min", objective, constraints, names))
    if solved.status != "optimal":
        return "none" if solved.status == "infeasible" else "unknown", None, None, solved.status
    parameters = [
        solved.x[2 * index] - solved.x[2 * index + 1]
        for index in range(free_count)
    ]
    y = [
        family["particular"][index]
        + sum((direction[index] * value for direction, value in zip(family["directions"], parameters)), F(0))
        for index in range(len(dual.var_names))
    ]
    return "feasible", y, parameters, ""


def check_optimality(lp, x_proposed, primal_var_signs=None):
    """Check whether a proposed primal point is optimal, with full reasoning."""
    if len(x_proposed) != lp.n:
        return CheckResult("not optimal", None, ["The point has the wrong size."], False, False,
                           "no dual vector derived")
    x = [F(value) for value in x_proposed]
    steps = []
    bad = violation(lp, x)
    if bad is not None:
        steps.append(f"The point is not primal feasible: {bad} is violated.")
        return CheckResult("not optimal", None, steps, False, False, "no dual vector derived")
    steps.append("The point is primal feasible: x ≥ 0 and every constraint holds.")
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
    return steps


def finish_check(dual, matrix, right_hand_side, steps):
    """Solve the system and check dual feasibility to give the final verdict."""
    status, solution, information = gauss_jordan(matrix, right_hand_side)
    equation_count = len(matrix)
    if status == "inconsistent":
        steps.append("The equations are contradictory, so no dual y exists; the point is not optimal.")
        return CheckResult("not optimal", None, steps, True, False, "no dual vector derived")
    if status == "unique":
        steps.append(f"Solving the {equation_count} equation(s) by Gauss-Jordan gives y = ({', '.join(fmt(value) for value in solution)}).")
        problem = dual_problem(dual, solution)
        if problem is not None:
            steps.append(problem)
            steps.append("This y is not dual feasible, so the point is not optimal.")
            return CheckResult("not optimal", solution, steps, True, False, problem)
        steps.append("All dual constraints and signs hold: the duality gap is zero, so the point is optimal.")
        return CheckResult("optimal", solution, steps, True, True)
    steps.append(
        f"Solving the {equation_count} equation(s) by Gauss-Jordan gives the family "
        f"{format_parametrization(dual, solution)}."
    )
    search_status, y, parameters, reason = search_parameters(dual, solution)
    if search_status == "feasible":
        steps.append(
            "Our simplex searched the free parameters and found "
            f"t = ({', '.join(fmt(value) for value in parameters)}), hence y = ({', '.join(fmt(value) for value in y)})."
        )
        steps.append("All dual constraints and signs hold: the duality gap is zero, so the point is optimal.")
        return CheckResult("optimal", y, steps, True, True)
    if search_status == "none":
        steps.append("Our simplex searched every sign and dual constraint: no feasible y exists, so the point is not optimal.")
        return CheckResult("not optimal", None, steps, True, False, "no dual vector derived")
    steps.append(f"The parametric search could not decide the verdict: {reason}.")
    return CheckResult("undetermined", None, steps, True, False, reason)
