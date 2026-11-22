"""The data model of a linear program.

Everything here uses fractions.Fraction so that the answer of the simplex is
exactly the same kind of number that we write by hand during the course.
"""

from dataclasses import dataclass
from fractions import Fraction
from typing import Iterable


def F(x):
    """Convert an int, float or string to an exact Fraction.

    Floats are converted through their string form (Fraction(str(0.5))) so
    that we never store a noisy binary approximation such as 0.49999999.
    """
    if isinstance(x, Fraction):
        return x
    if isinstance(x, bool):
        raise ValueError("A boolean is not a number here.")
    return Fraction(str(x).strip())


def fmt(fraction) -> str:
    """Print a Fraction as '7/2' or as '3' when it is a whole number."""
    value = F(fraction)
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def fmt_pair(value) -> str:
    """Print an exact value together with its decimal value, e.g. 7/2 (3.5)."""
    exact = F(value)
    text = fmt(exact)
    decimal = float(exact)
    rounded = round(decimal, 6)
    return f"{text} ({rounded})"


@dataclass
class Constraint:
    """One linear constraint: coeffs * x (op) rhs, with x >= 0 implicit."""

    coeffs: list
    op: str
    rhs: Fraction

    def __post_init__(self):
        """Normalise the numbers and the operator once, at construction time."""
        self.coeffs = [F(value) for value in self.coeffs]
        self.rhs = F(self.rhs)
        if self.op not in ("<=", ">=", "="):
            raise ValueError(f"Unknown operator {self.op!r}; use <=, >= or =.")

    def lhs_text(self, var_names: Iterable[str]) -> str:
        """Write the left hand side in the usual course notation."""
        parts = []
        for coefficient, name in zip(self.coeffs, var_names):
            if coefficient == 0:
                continue
            sign = "-" if coefficient < 0 else ("+" if parts else "")
            absolute = abs(coefficient)
            number = "" if absolute == 1 and sign else fmt(absolute)
            parts.append(f"{sign} {number}{name}".strip())
        return " ".join(parts) if parts else "0"

    def to_text(self, var_names: Iterable[str]) -> str:
        """Write the whole constraint, for example '2x1 + x2 <= 20'."""
        symbol = {"<=": "≤", ">=": "≥", "=": "="}[self.op]
        return f"{self.lhs_text(var_names)} {symbol} {fmt(self.rhs)}"


@dataclass
class LP:
    """A linear program: max or min c.x with constraints and x >= 0."""

    sense: str
    c: list
    constraints: list
    var_names: list

    def __post_init__(self):
        """Normalise all numbers and check that the sizes are consistent."""
        if self.sense not in ("max", "min"):
            raise ValueError("The sense must be 'max' or 'min'.")
        self.c = [F(value) for value in self.c]
        self.constraints = list(self.constraints)
        self.var_names = [str(name) for name in self.var_names]
        if len(self.c) != len(self.var_names):
            raise ValueError("The objective and the variable names have different sizes.")
        for index, constraint in enumerate(self.constraints, start=1):
            if len(constraint.coeffs) != self.n:
                raise ValueError(f"Constraint {index} has {len(constraint.coeffs)} coefficients, expected {self.n}.")

    @property
    def n(self) -> int:
        """Number of decision variables."""
        return len(self.c)

    @property
    def m(self) -> int:
        """Number of constraints."""
        return len(self.constraints)

    @classmethod
    def build(cls, sense, c, A, ops, b, var_names=None):
        """Build an LP from raw rows, validating sizes and operators first."""
        coefficients = [F(value) for value in c]
        names = list(var_names) if var_names is not None else [f"x{i + 1}" for i in range(len(coefficients))]
        if len(A) != len(ops) or len(A) != len(b):
            raise ValueError("A, ops and b must have the same number of rows.")
        if len(names) != len(coefficients):
            raise ValueError("var_names must have one name per objective coefficient.")
        constraints = []
        for index, row in enumerate(A):
            if len(row) != len(coefficients):
                raise ValueError(f"Row {index + 1} of A has the wrong number of coefficients.")
            constraints.append(Constraint(list(row), ops[index], F(b[index])))
        return cls(sense, coefficients, constraints, names)

    def evaluate(self, x) -> Fraction:
        """Compute c.x for a proposed vector x, without any optimisation."""
        if len(x) != self.n:
            raise ValueError("The proposed solution has the wrong number of variables.")
        return sum((coefficient * F(value) for coefficient, value in zip(self.c, x)), F(0))

    def is_feasible(self, x) -> bool:
        """Check x >= 0 and every constraint, used by the graphical method."""
        if any(F(value) < 0 for value in x):
            return False
        for constraint in self.constraints:
            left = sum((a * F(v) for a, v in zip(constraint.coeffs, x)), F(0))
            if constraint.op == "<=" and left > constraint.rhs:
                return False
            if constraint.op == ">=" and left < constraint.rhs:
                return False
            if constraint.op == "=" and left != constraint.rhs:
                return False
        return True

    def to_text(self) -> str:
        """Print the problem exactly like on a course sheet."""
        kind = "Max" if self.sense == "max" else "Min"
        objective = " + ".join(
            f"{fmt(value)}{name}" for value, name in zip(self.c, self.var_names)
        )
        lines = [f"{kind} z = {objective}", "s.c."]
        lines.extend(f"  {constraint.to_text(self.var_names)}" for constraint in self.constraints)
        lines.append("  " + ", ".join(self.var_names) + " ≥ 0")
        return "\n".join(lines)

    def to_dict(self):
        """Return a JSON-ready echo of the model for the frontend."""
        return {
            "sense": self.sense,
            "var_names": self.var_names,
            "c": [fmt(value) for value in self.c],
            "constraints": [
                {
                    "coeffs": [fmt(value) for value in constraint.coeffs],
                    "op": constraint.op,
                    "rhs": fmt(constraint.rhs),
                    "text": constraint.to_text(self.var_names),
                }
                for constraint in self.constraints
            ],
            "A": [[fmt(value) for value in constraint.coeffs] for constraint in self.constraints],
            "ops": [constraint.op for constraint in self.constraints],
            "b": [fmt(constraint.rhs) for constraint in self.constraints],
            "text": self.to_text(),
        }
