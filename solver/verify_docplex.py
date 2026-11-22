"""Optional comparison with IBM CPLEX through docplex.

The import is wrapped: when docplex (or a usable CPLEX runtime) is missing the
application simply hides the comparison panel. The engine never calls this
module by itself.
"""

from time import perf_counter

from .model import LP


def solve_with_docplex(lp: LP):
    """Solve an LP with docplex when available and return a comparable summary."""
    try:
        from docplex.mp.model import Model
    except Exception:
        return {"available": False}

    started = perf_counter()
    try:
        model = Model(name="lp_studio")
        variables = [model.continuous_var(lb=0, name=name) for name in lp.var_names]
        for constraint in lp.constraints:
            expression = sum((coefficient * variable for coefficient, variable
                              in zip(constraint.coeffs, variables)), 0)
            if constraint.op == "<=":
                model.add_constraint(expression <= constraint.rhs)
            elif constraint.op == ">=":
                model.add_constraint(expression >= constraint.rhs)
            else:
                model.add_constraint(expression == constraint.rhs)
        objective = sum((coefficient * variable for coefficient, variable
                         in zip(lp.c, variables)), 0)
        if lp.sense == "max":
            model.maximize(objective)
        else:
            model.minimize(objective)
        solution = model.solve()
    except Exception as error:
        return {"available": False, "error": str(error)}

    elapsed = (perf_counter() - started) * 1000
    if solution is None:
        return {"available": True, "status": "no_solution", "time_ms": round(elapsed, 3)}
    return {
        "available": True,
        "status": "optimal",
        "z": float(solution.objective_value),
        "x": [float(solution[variable]) for variable in variables],
        "time_ms": round(elapsed, 3),
        "iterations": None,
    }
