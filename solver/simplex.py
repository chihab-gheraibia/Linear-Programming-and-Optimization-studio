"""The Big-M simplex method, written by hand with exact arithmetic.

M is kept as a symbol (a + b*M), never as a huge number. Every iteration is
saved as a snapshot of the tableau before the pivot, so the interface can play
the algorithm like a video.
"""

from dataclasses import dataclass, field
from fractions import Fraction

from .model import F, fmt, LP


@dataclass(frozen=True, eq=False)
class MNum:
    """A number a + b*M, where M is an symbolic very large positive value."""

    a: object
    b: object

    @classmethod
    def of(cls, value):
        """Convert a plain number into an MNum with no M part."""
        if isinstance(value, MNum):
            return value
        return cls(F(value), F(0))

    def _pair(self):
        """Return the pair used by all comparisons: first b, then a."""
        return (self.b, self.a)

    def __eq__(self, other):
        """Compare with another MNum or with a plain number such as 0."""
        if not isinstance(other, (MNum, int, Fraction)):
            return NotImplemented
        return self._pair() == MNum.of(other)._pair()

    def __hash__(self):
        """Keep MNum usable in sets and as a dictionary key."""
        return hash((self.a, self.b))

    def __lt__(self, other):
        """Compare the M parts first, which is what 'M is huge' means."""
        return self._pair() < MNum.of(other)._pair()

    def __le__(self, other):
        """Less than or equal, using the same symbolic order."""
        return self._pair() <= MNum.of(other)._pair()

    def __gt__(self, other):
        """Greater than, using the same symbolic order."""
        return self._pair() > MNum.of(other)._pair()

    def __ge__(self, other):
        """Greater than or equal, using the same symbolic order."""
        return self._pair() >= MNum.of(other)._pair()

    def __add__(self, other):
        """Add the rational parts and the M parts separately."""
        other = MNum.of(other)
        return MNum(self.a + other.a, self.b + other.b)

    def __radd__(self, other):
        """Allow 0 + (a + b*M)."""
        return self.__add__(other)

    def __neg__(self):
        """Change both signs."""
        return MNum(-self.a, -self.b)

    def __sub__(self, other):
        """Subtract by adding the opposite."""
        return self.__add__(-MNum.of(other))

    def __rsub__(self, other):
        """Allow a plain number minus an MNum."""
        return MNum.of(other).__sub__(self)

    def __mul__(self, other):
        """Multiply by a plain rational; M stays symbolic."""
        if isinstance(other, MNum):
            raise ValueError("M is symbolic: multiplication by another MNum is not defined.")
        factor = F(other)
        return MNum(self.a * factor, self.b * factor)

    def __rmul__(self, other):
        """Allow a rational times an MNum."""
        return self.__mul__(other)

    def __truediv__(self, other):
        """Divide by a rational, or by an MNum that has no M part."""
        if isinstance(other, MNum):
            if other.b != 0:
                raise ValueError("Cannot divide by an expression containing M.")
            divisor = other.a
        else:
            divisor = F(other)
        return MNum(self.a / divisor, self.b / divisor)

    def __rtruediv__(self, other):
        """Allow a rational divided by a pure rational MNum."""
        if self.b != 0:
            raise ValueError("Cannot divide by an expression containing M.")
        return MNum.of(other) / self.a

    def __str__(self):
        """Print like the course: -M, 2M-5/3 or 100/3."""
        if self.b == 0:
            return fmt(self.a)
        name = "M" if abs(self.b) == 1 else f"{fmt(abs(self.b))}M"
        if self.b < 0:
            name = "-" + name
        if self.a == 0:
            return name
        if self.a > 0:
            return f"{name}+{fmt(self.a)}"
        return f"{name}-{fmt(abs(self.a))}"


def mstr(value) -> str:
    """Print a Fraction or an MNum as a JSON-ready string."""
    return str(MNum.of(value))


@dataclass
class StandardForm:
    """The tableau and all information needed to pivot and to do sensitivity."""

    T: list
    b: list
    basis: list
    cj: list
    col_names: list
    kinds: list
    artificial_of: list
    ops: list
    n: int
    m: int
    artificial_cols: set = field(default_factory=set)


def flip_operator(op: str) -> str:
    """Reverse an operator when a negative right-hand side is multiplied by -1."""
    if op == "<=":
        return ">="
    if op == ">=":
        return "<="
    return "="


def normalized_row(constraint):
    """Multiply a row by -1 when its right-hand side is negative."""
    if constraint.rhs < 0:
        return (
            [-coefficient for coefficient in constraint.coeffs],
            -constraint.rhs,
            flip_operator(constraint.op),
        )
    return list(constraint.coeffs), constraint.rhs, constraint.op


def allocate_columns(rows, n):
    """Give one surplus/slack column per row and one artificial where needed."""
    artificial_of = [None] * len(rows)
    next_column = n + len(rows)
    for index, (_, _, op) in enumerate(rows):
        if op in (">=", "="):
            artificial_of[index] = next_column
            next_column += 1
    return artificial_of, next_column


def build_standard_form(lp: LP) -> StandardForm:
    """Turn the LP into an initial Big-M tableau with a starting basis."""
    rows = [normalized_row(constraint) for constraint in lp.constraints]
    artificial_of, total_columns = allocate_columns(rows, lp.n)
    n, m = lp.n, lp.m
    T = [[F(0)] * total_columns for _ in range(m)]
    b = [F(0)] * m
    basis = [0] * m
    kinds = ["decision"] * n + ["slack"] * m + ["artificial"] * (total_columns - n - m)
    names = list(lp.var_names) + [f"e{i + 1}" for i in range(m)]
    names += [f"a{i + 1}" for i in range(m) if artificial_of[i] is not None]
    artificial_cols = set()
    for i, (coefficients, rhs, op) in enumerate(rows):
        fill_initial_row(T, b, basis, kinds, i, coefficients, rhs, op, artificial_of[i])
        if artificial_of[i] is not None:
            artificial_cols.add(artificial_of[i])
    cj = build_costs(lp, total_columns, n, m, artificial_cols)
    return StandardForm(T, b, basis, cj, names, kinds, artificial_of,
                        [row[2] for row in rows], n, m, artificial_cols)


def fill_initial_row(T, b, basis, kinds, i, coefficients, rhs, op, artificial):
    """Put one constraint into the tableau and choose its basic variable."""
    n = len(coefficients)
    for j, value in enumerate(coefficients):
        T[i][j] = value
    b[i] = rhs
    slack = n + i
    if op == "<=":
        T[i][slack] = F(1)
        basis[i] = slack
    elif op == ">=":
        T[i][slack] = F(-1)
        kinds[slack] = "surplus"
        T[i][artificial] = F(1)
        basis[i] = artificial
    else:
        kinds[slack] = "equality"
        T[i][artificial] = F(1)
        basis[i] = artificial


def build_costs(lp, total_columns, n, m, artificial_cols):
    """Costs of the internal maximisation: -c for a min problem, -M artificial."""
    sign = 1 if lp.sense == "max" else -1
    cj = [MNum.of(sign * value) for value in lp.c]
    cj += [MNum(F(0), F(0)) for _ in range(total_columns - n)]
    for column in artificial_cols:
        cj[column] = MNum(F(0), F(-1))
    return cj


def compute_row_values(sf, cB):
    """Compute Zj for every column and the current value of the objective."""
    zj = []
    for j in range(len(sf.col_names)):
        total = MNum(F(0), F(0))
        for i in range(sf.m):
            total += cB[i] * sf.T[i][j]
        zj.append(total)
    z = MNum(F(0), F(0))
    for i in range(sf.m):
        z += cB[i] * sf.b[i]
    return zj, z


def choose_entering(delta, iteration):
    """Choose the largest positive Cj−Zj, or the first one after 50 iterations."""
    positive = [(j, value) for j, value in enumerate(delta) if value > 0]
    if not positive:
        return None, None, False
    if iteration >= 50:
        column, value = positive[0]
        return column, value, True
    column, value = max(positive, key=lambda item: (item[1], -item[0]))
    return column, value, False


def choose_leaving(sf, column):
    """Choose the smallest ratio b/T[i][column], with a deterministic tie break."""
    ratios = []
    for i in range(sf.m):
        if sf.T[i][column] > 0:
            ratios.append((i, sf.b[i] / sf.T[i][column]))
    if not ratios:
        return None, None, []
    row, ratio = min(ratios, key=lambda item: (item[1], sf.basis[item[0]]))
    return row, ratio, ratios


def pivot(sf, row, column):
    """Normalise the pivot row, clear the pivot column and update the basis."""
    value = sf.T[row][column]
    sf.T[row] = [entry / value for entry in sf.T[row]]
    sf.b[row] /= value
    for i in range(sf.m):
        if i == row or sf.T[i][column] == 0:
            continue
        factor = sf.T[i][column]
        sf.T[i] = [sf.T[i][j] - factor * sf.T[row][j] for j in range(len(sf.col_names))]
        sf.b[i] -= factor * sf.b[row]
    sf.basis[row] = column


def make_message(lp, entering_name, value, bland, leaving_name, ratio, row, status):
    """Explain in one sentence what the algorithm just decided."""
    if status == "optimal":
        return "Every Cj−Zj is ≤ 0, so the current solution is optimal."
    if status == "unbounded" or leaving_name is None:
        return "The entering column has no positive coefficient, so z can improve forever."
    first = "Bland's rule picks " if bland else "Cj−Zj is largest for "
    prefix = f"{first}{entering_name} ({mstr(value)}) → {entering_name} enters."
    if lp.sense == "min":
        prefix += " (We maximise −z internally.)"
    return f"{prefix} Min ratio = {mstr(ratio)} on row {row + 1} → {leaving_name} leaves."


def make_snapshot(iteration, sf, cB, zj, delta, z, entering, leaving, row, ratios, message):
    """Save a tableau and all decisions of one iteration as strings."""
    ratio_text = [mstr(value) for _, value in ratios]
    by_row = ["—"] * sf.m
    for i, value in ratios:
        by_row[i] = mstr(value)
    return {
        "iteration": iteration,
        "col_names": list(sf.col_names),
        "cj": [mstr(value) for value in sf.cj],
        "basis": [sf.col_names[column] for column in sf.basis],
        "cb": [mstr(value) for value in cB],
        "rows": [[mstr(value) for value in line] for line in sf.T],
        "b": [mstr(value) for value in sf.b],
        "zj": [mstr(value) for value in zj],
        "delta": [mstr(value) for value in delta],
        "z": mstr(z),
        "entering": sf.col_names[entering] if entering is not None else None,
        "leaving": sf.col_names[leaving] if leaving is not None else None,
        "pivot": None if row is None else {"row": row + 1, "col": sf.col_names[entering]},
        "ratios": [
            {"row": str(i + 1), "value": mstr(value)} for i, value in ratios
        ],
        "ratio_by_row": by_row,
        "message": message,
    }


@dataclass
class SimplexResult:
    """The answer of the simplex, with flags and the full trace."""

    status: str
    x: object
    z: object
    steps: list
    notes: list
    multiple_optima: bool
    degenerate: bool
    final: dict
    lp: LP

    def to_dict(self):
        """Return a JSON-ready result with both exact strings and floats."""
        x = self.x
        return {
            "status": self.status,
            "x": None if x is None else [fmt(value) for value in x],
            "x_float": None if x is None else [float(value) for value in x],
            "z": None if self.z is None else fmt(self.z),
            "z_float": None if self.z is None else float(self.z),
            "steps": self.steps,
            "notes": self.notes,
            "multiple_optima": self.multiple_optima,
            "degenerate": self.degenerate,
            "iterations": max(len(self.steps) - 1, 0),
        }


def result_notes(lp, status, sf, multiple, degenerate):
    """Build the short explanations shown under the solution."""
    notes = []
    if lp.sense == "min":
        notes.append("A minimisation is solved by maximising −z; the reported z is the original objective.")
    if status == "infeasible":
        notes.append("An artificial variable stayed positive: the feasible region is empty.")
    if status == "unbounded":
        notes.append("No pivot is possible in the entering column: the objective can improve forever.")
    if degenerate:
        notes.append("A basic variable is zero: this solution is degenerate.")
    if multiple and status == "optimal":
        notes.append("A non-basic column has Cj−Zj = 0: other optimal solutions exist.")
    return notes


def final_tableau(sf, zj, delta, lp):
    """Keep the raw final tableau for the sensitivity module."""
    return {
        "T": sf.T,
        "b": sf.b,
        "basis": sf.basis,
        "cj": sf.cj,
        "col_names": sf.col_names,
        "kinds": sf.kinds,
        "artificial_of": sf.artificial_of,
        "artificial_cols": sf.artificial_cols,
        "ops": sf.ops,
        "delta": delta,
        "zj": zj,
        "n": sf.n,
        "m": sf.m,
        "sense": lp.sense,
        "internal_sign": 1 if lp.sense == "max" else -1,
    }


def solve(lp: LP) -> SimplexResult:
    """Run the Big-M simplex and return the solution plus every tableau."""
    sf = build_standard_form(lp)
    steps = []
    status = "iteration_limit"
    for iteration in range(500):
        cB = [sf.cj[column] for column in sf.basis]
        zj, z = compute_row_values(sf, cB)
        delta = [cost - value for cost, value in zip(sf.cj, zj)]
        entering, value, bland = choose_entering(delta, iteration)
        row, ratio, ratios = None, None, []
        if entering is not None:
            row, ratio, ratios = choose_leaving(sf, entering)
        if entering is None:
            decision = "optimal"
        elif row is None:
            decision = "unbounded"
        else:
            decision = None
        entering_name = sf.col_names[entering] if entering is not None else None
        leaving_name = sf.col_names[sf.basis[row]] if row is not None else None
        message = make_message(lp, entering_name, value, bland, leaving_name,
                               ratio, row, decision)
        steps.append(make_snapshot(iteration, sf, cB, zj, delta, z,
                                   entering, sf.basis[row] if row is not None else None,
                                   row, ratios, message))
        if entering is None:
            status = "optimal"
            break
        if row is None:
            status = "unbounded"
            break
        pivot(sf, row, entering)
    return finish(lp, sf, steps, status)


def finish(lp, sf, steps, status):
    """Decide feasibility, extract x and z, and compute the two flags."""
    artificial_positive = any(
        column in sf.artificial_cols and sf.b[i] > 0 for i, column in enumerate(sf.basis)
    )
    if status in ("optimal", "unbounded") and artificial_positive:
        status = "infeasible"
    cB = [sf.cj[column] for column in sf.basis]
    zj, _ = compute_row_values(sf, cB)
    delta = [cost - value for cost, value in zip(sf.cj, zj)]
    degenerate = any(value == 0 for value in sf.b)
    multiple = any(
        delta[j] == 0 and j not in sf.basis and j not in sf.artificial_cols
        for j in range(len(sf.col_names))
    )
    x, objective = None, None
    if status == "optimal":
        x = [F(0)] * lp.n
        for i, column in enumerate(sf.basis):
            if column < lp.n:
                x[column] = sf.b[i]
        objective = lp.evaluate(x)
    notes = result_notes(lp, status, sf, multiple, degenerate)
    return SimplexResult(status, x, objective, steps, notes, multiple, degenerate,
                         final_tableau(sf, zj, delta, lp), lp)
