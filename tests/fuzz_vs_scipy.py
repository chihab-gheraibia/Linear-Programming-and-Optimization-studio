"""Optional fuzz test: compare our engine with scipy's HiGHS solver.

Run with: python tests/fuzz_vs_scipy.py
Nothing in the engine depends on this file; it is skipped when scipy is absent.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from solver.model import LP
from solver.simplex import solve


def random_lp(rng):
    """Generate a small LP with integer data and mixed constraint types."""
    n = rng.randint(2, 4)
    m = rng.randint(2, 5)
    A = [[rng.randint(-3, 5) for _ in range(n)] for _ in range(m)]
    b = [rng.randint(-2, 12) for _ in range(m)]
    ops = [rng.choice(["<=", ">=", "="]) for _ in range(m)]
    c = [rng.randint(-5, 10) for _ in range(n)]
    sense = rng.choice(["max", "min"])
    return LP.build(sense, c, A, ops, b)


def scipy_status(code):
    """Translate scipy's numeric status into our three status words."""
    return {0: "optimal", 2: "infeasible", 3: "unbounded"}.get(code, "iteration_limit")


def scipy_solve(lp):
    """Convert our LP into linprog arrays and return (status, z)."""
    from scipy.optimize import linprog

    sign = -1 if lp.sense == "max" else 1
    objective = [sign * float(value) for value in lp.c]
    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    for constraint in lp.constraints:
        row = [float(value) for value in constraint.coeffs]
        if constraint.op == "<=":
            A_ub.append(row)
            b_ub.append(float(constraint.rhs))
        elif constraint.op == ">=":
            A_ub.append([-value for value in row])
            b_ub.append(-float(constraint.rhs))
        else:
            A_eq.append(row)
            b_eq.append(float(constraint.rhs))
    answer = linprog(objective, A_ub=A_ub or None, b_ub=b_ub or None,
                     A_eq=A_eq or None, b_eq=b_eq or None,
                     bounds=(0, None), method="highs")
    if answer.status not in (0, 2, 3) or answer.fun is None:
        return scipy_status(answer.status), None
    return scipy_status(answer.status), float(sign * answer.fun)


def main():
    """Solve 300 random LPs and print every disagreement."""
    try:
        import scipy  # noqa: F401
    except ImportError:
        print("SKIPPED: scipy is not installed (optional test only).")
        return
    rng = random.Random(2026)
    mismatches = []
    for number in range(300):
        lp = random_lp(rng)
        ours = solve(lp)
        status, value = scipy_solve(lp)
        if ours.status != status:
            mismatches.append((number, "status", ours.status, status, lp.to_text()))
        elif ours.status == "optimal" and value is not None and abs(float(ours.z) - value) > 1e-6:
            mismatches.append((number, "objective", float(ours.z), value, lp.to_text()))
    print(f"Fuzz: 300 random LPs, {len(mismatches)} mismatch(es).")
    for number, kind, ours, theirs, text in mismatches[:5]:
        print(f"\n#{number} {kind}: ours={ours}, scipy={theirs}\n{text}")
    if mismatches:
        raise AssertionError("Our engine disagrees with scipy on random instances.")


if __name__ == "__main__":
    main()
