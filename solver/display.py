"""Turn a saved tableau into aligned text for the terminal."""

from .simplex import mstr


def tableau_to_text(step):
    """Print one iteration exactly like a tableau written on the board."""
    headers = ["Basis", "Cb"] + list(step["col_names"]) + ["b"]
    rows = [
        [basis, cb] + list(line) + [value]
        for basis, cb, line, value in zip(
            step["basis"], step["cb"], step["rows"], step["b"]
        )
    ]
    rows.append(["Zj", ""] + list(step["zj"]) + [step["z"]])
    rows.append(["Cj-Zj", ""] + list(step["delta"]) + [""])
    widths = [
        max(len(str(row[i])) for row in [headers] + rows)
        for i in range(len(headers))
    ]
    lines = ["  ".join(str(text).ljust(widths[i]) for i, text in enumerate(headers))]
    lines.append("-" * (sum(widths) + 2 * (len(widths) - 1)))
    lines.extend(
        "  ".join(str(text).ljust(widths[i]) for i, text in enumerate(row))
        for row in rows
    )
    return "\n".join(lines)


def print_trace(result):
    """Print every tableau and the decision taken at that iteration."""
    print(f"Status: {result.status}")
    for step in result.steps:
        print(f"\n=== Iteration {step['iteration']} ===")
        print(tableau_to_text(step))
        print(step["message"])
    if result.x is not None:
        values = ", ".join(f"{name} = {value}" for name, value in zip(result.lp.var_names, result.x))
        print(f"\nSolution: {values}, z = {mstr(result.z)}")
