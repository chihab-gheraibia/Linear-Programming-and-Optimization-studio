"""Chapter 4 sensitivity analysis, read directly from the final tableau.

A change of one coefficient keeps the same basis as long as all reduced costs
stay <= 0 (optimality) and all basic values stay >= 0 (feasibility). Inside
that domain x and z are updated by a formula, never by re-solving.
"""

from .dual import shadow_prices
from .model import F, LP, fmt
from .simplex import solve


def rational_part(value):
    """Return the rational part of an MNum, which must have no symbolic part."""
    if hasattr(value, "b") and value.b != 0:
        raise ValueError("A reduced cost still contains M; the tableau is not optimal.")
    return F(value.a) if hasattr(value, "a") else F(value)


def inside(value, lower, upper):
    """Check that a value lies inside an interval with open ends allowed."""
    return (lower is None or value >= lower) and (upper is None or value <= upper)


def interval_payload(index, name, current, lower, upper, clipped=True):
    """Build the common fields of a range bar used by the interface."""
    clipped_low = clipped and lower is not None and lower < 0
    return {
        "index": index,
        "name": name,
        "current": current,
        "delta_min": lower,
        "delta_max": upper,
        "lower": 0 if clipped_low else lower,
        "upper": upper,
        "raw_lower": lower,
        "clipped_at_zero": clipped_low,
    }


def basic_cost_bounds(result, j):
    """Intersect all inequalities that keep a basic variable in the basis."""
    final = result.final
    row = final["basis"].index(j)
    sign = final["internal_sign"]
    lower, upper = None, None
    for k in range(len(final["col_names"])):
        if k == j or final["kinds"][k] == "artificial":
            continue
        coefficient = -sign * final["T"][row][k]
        bound = -rational_part(final["delta"][k])
        if coefficient > 0:
            candidate = bound / coefficient
            upper = candidate if upper is None else min(upper, candidate)
        elif coefficient < 0:
            candidate = bound / coefficient
            lower = candidate if lower is None else max(lower, candidate)
        elif bound < 0:
            return None, None
    return lower, upper


def nonbasic_cost_bounds(result, j):
    """A non-basic variable may grow until its reduced cost becomes positive."""
    sign = result.final["internal_sign"]
    delta = rational_part(result.final["delta"][j])
    return (delta, None) if sign == -1 else (None, -delta)


def z_range(result, lower, upper, current_x):
    """Give the objective values at both ends of a coefficient interval."""
    start = result.z
    if current_x == 0 or lower is None and upper is None:
        return start, start
    low = start + current_x * lower if lower is not None else None
    high = start + current_x * upper if upper is not None else None
    return low, high


def cost_interval(result, j):
    """Return the optimality range of the objective coefficient c_j."""
    require_optimal(result)
    final = result.final
    basic = j in final["basis"]
    lower, upper = basic_cost_bounds(result, j) if basic else nonbasic_cost_bounds(result, j)
    current = result.lp.c[j]
    payload = interval_payload(j, result.lp.var_names[j], current,
                               current + lower if lower is not None else None,
                               current + upper if upper is not None else None, False)
    payload["delta_min"], payload["delta_max"] = lower, upper
    payload["basic"] = basic
    low, high = z_range(result, lower, upper,
                        result.x[j] if result.x is not None else F(0))
    payload["z_min"], payload["z_max"] = low, high
    payload["note"] = (
        "The variable stays in the basis; x is unchanged."
        if basic else "Above this value the variable enters the basis."
    )
    return payload


def require_optimal(result):
    """Refuse sensitivity analysis when there is no optimal basis to study."""
    if result.status != "optimal":
        raise ValueError("Sensitivity needs an optimal solution first.")


def rhs_direction(result, i):
    """Give how the tableau right-hand sides move when b_i changes by +1."""
    final = result.final
    column = final["n"] + i
    factor = 1 if final["ops"][i] == "<=" else -1 if final["ops"][i] == ">=" else 0
    return [factor * row[column] for row in final["T"]]


def rhs_bounds(result, i):
    """Require every basic value b + delta*d to stay non-negative."""
    final = result.final
    direction = rhs_direction(result, i)
    lower, upper = None, None
    for row, (value, move) in enumerate(zip(final["b"], direction)):
        if move > 0:
            candidate = -value / move
            lower = candidate if lower is None else max(lower, candidate)
        elif move < 0:
            candidate = -value / move
            upper = candidate if upper is None else min(upper, candidate)
    return lower, upper


def rhs_interval(result, i):
    """Return the validity domain of a right-hand side b_i."""
    require_optimal(result)
    lower, upper = rhs_bounds(result, i)
    current = result.lp.constraints[i].rhs
    payload = interval_payload(i, f"b{i + 1}", current,
                               current + lower if lower is not None else None,
                               current + upper if upper is not None else None)
    payload["delta_min"], payload["delta_max"] = lower, upper
    price = shadow_prices(result.lp, result)[i]
    payload["shadow_price"] = price
    payload["state"] = "binding" if price != 0 else "marginal"
    if lower is not None:
        low = result.z + price * lower
    else:
        low = None
    if upper is not None:
        high = result.z + price * upper
    else:
        high = None
    payload["z_min"], payload["z_max"] = low, high
    return payload


def sensitivity_report(lp, result=None):
    """Return every c_j and b_i interval for the sensitivity tab."""
    result = result or solve(lp)
    return {
        "ok": True,
        "objective": [cost_interval(result, j) for j in range(lp.n)],
        "rhs": [rhs_interval(result, i) for i in range(lp.m)],
    }


def changed_lp(lp, kind, index, value):
    """Build a copy of the LP with one coefficient replaced."""
    c = list(lp.c)
    b = [constraint.rhs for constraint in lp.constraints]
    if kind == "c":
        c[index] = F(value)
    else:
        b[index] = F(value)
    return LP.build(
        lp.sense, c,
        [list(constraint.coeffs) for constraint in lp.constraints],
        [constraint.op for constraint in lp.constraints], b, lp.var_names,
    )


def normalized_kind(kind):
    """Accept c, ci, cost, b, bi or rhs from the interface."""
    if kind in ("c", "ci", "cost", "objective"):
        return "c"
    if kind in ("b", "bi", "rhs"):
        return "b"
    raise ValueError("kind must be 'c' for an objective coefficient or 'b' for a right-hand side.")


def new_solution_payload(result, x, z, changed, message):
    """Format the formula result or the re-solved solution for the UI."""
    return {
        "ok": True,
        "basis_changed": changed,
        "x": [fmt(value) for value in x],
        "x_float": [float(value) for value in x],
        "z": fmt(z),
        "z_float": float(z),
        "message": message,
    }


def what_if(lp, kind, index, new_value):
    """Answer a slider move: formula inside the range, re-solve outside."""
    kind = normalized_kind(kind)
    result = solve(lp)
    if result.status != "optimal":
        return {"ok": False, "error": "The original problem has no optimal solution."}
    new_value = F(new_value)
    interval = cost_interval(result, index) if kind == "c" else rhs_interval(result, index)
    if inside(new_value, interval["lower"], interval["upper"]):
        return formula_answer(result, kind, index, new_value, interval)
    changed = solve(changed_lp(lp, kind, index, new_value))
    if changed.status != "optimal":
        return {"ok": False, "error": "The changed problem has no optimal solution."}
    payload = new_solution_payload(changed, changed.x, changed.z, True,
                                   "Basis changed — re-solved")
    payload["interval"] = interval
    return payload


def formula_answer(result, kind, index, new_value, interval):
    """Update x and z without re-solving, using the current basis."""
    delta = new_value - interval["current"]
    if kind == "c":
        x = list(result.x)
        z = result.z + result.x[index] * delta
    else:
        x = shifted_basic_values(result, index, delta)
        price = interval["shadow_price"]
        z = result.z + price * delta
    payload = new_solution_payload(result, x, z, False, "Basis unchanged ✓")
    payload["interval"] = interval
    return payload


def shifted_basic_values(result, index, delta):
    """Read the new basic values after a right-hand side change."""
    final = result.final
    direction = rhs_direction(result, index)
    values = [value + delta * move for value, move in zip(final["b"], direction)]
    x = [F(0)] * final["n"]
    for row, column in enumerate(final["basis"]):
        if column < final["n"]:
            x[column] = values[row]
    return x
