"""The graphical method for problems with exactly two decision variables.

We intersect every pair of boundary lines with Cramer's rule, keep the points
that satisfy all constraints, and compare the objective at those vertices.
Directions parallel to a boundary line are used to detect an unbounded region.
"""

import math

from .model import F, fmt


def boundary_lines(lp):
    """Return every line used by the method: constraints plus the two axes."""
    lines = []
    for index, constraint in enumerate(lp.constraints, start=1):
        lines.append({
            "index": index,
            "label": f"R{index}: {constraint.to_text(lp.var_names)}",
            "a": constraint.coeffs[0],
            "b": constraint.coeffs[1],
            "rhs": constraint.rhs,
            "op": constraint.op,
            "kind": "constraint",
        })
    lines.append({"index": 0, "label": "x₁ ≥ 0", "a": F(1), "b": F(0),
                  "rhs": F(0), "op": ">=", "kind": "axis"})
    lines.append({"index": 0, "label": "x₂ ≥ 0", "a": F(0), "b": F(1),
                  "rhs": F(0), "op": ">=", "kind": "axis"})
    return lines


def intersect(first, second):
    """Solve two boundary lines with Cramer's rule, or return None if parallel."""
    determinant = first["a"] * second["b"] - first["b"] * second["a"]
    if determinant == 0:
        return None
    x1 = (first["rhs"] * second["b"] - first["b"] * second["rhs"]) / determinant
    x2 = (first["a"] * second["rhs"] - first["rhs"] * second["a"]) / determinant
    return (x1, x2)


def feasible_vertices(lp, lines):
    """Keep the intersections that satisfy every constraint, without duplicates."""
    vertices = []
    for i in range(len(lines)):
        for j in range(i + 1, len(lines)):
            point = intersect(lines[i], lines[j])
            if point is not None and lp.is_feasible(point) and point not in vertices:
                vertices.append(point)
    return vertices


def direction_is_allowed(lines, direction):
    """Check that moving along d never leaves the feasible region."""
    for line in lines:
        move = line["a"] * direction[0] + line["b"] * direction[1]
        if line["op"] == "<=" and move > 0:
            return False
        if line["op"] == ">=" and move < 0:
            return False
        if line["op"] == "=" and move != 0:
            return False
    return True


def recession_directions(lines):
    """List the useful directions (the two normals of every boundary line)."""
    directions = []
    for line in lines:
        candidates = [(-line["b"], line["a"]), (line["b"], -line["a"])]
        for direction in candidates:
            if direction == (0, 0) or direction[0] < 0 or direction[1] < 0:
                continue
            if direction_is_allowed(lines, direction) and direction not in directions:
                directions.append(direction)
    return directions


def improves(lp, direction):
    """Say whether the objective gets better when we move along d."""
    change = lp.c[0] * direction[0] + lp.c[1] * direction[1]
    return change > 0 if lp.sense == "max" else change < 0


def order_by_angle(points):
    """Order vertices around their centroid so an SVG can draw a polygon."""
    if not points:
        return []
    center_x = sum(float(point[0]) for point in points) / len(points)
    center_y = sum(float(point[1]) for point in points) / len(points)
    return sorted(
        points,
        key=lambda point: math.atan2(float(point[1]) - center_y, float(point[0]) - center_x),
    )


def line_for_drawing(line):
    """Convert one boundary line into floats and axis intercepts for the SVG."""
    a, b, rhs = float(line["a"]), float(line["b"]), float(line["rhs"])
    return {
        "label": line["label"],
        "a": a,
        "b": b,
        "rhs": rhs,
        "op": line["op"],
        "kind": line["kind"],
        "x_intercept": rhs / a if a != 0 else None,
        "y_intercept": rhs / b if b != 0 else None,
    }


def vertex_for_drawing(point, lp, best_z):
    """Convert one vertex into JSON-ready drawing data and a tooltip text."""
    x1, x2 = point
    value = lp.evaluate(point)
    return {
        "x": float(x1),
        "y": float(x2),
        "x_text": fmt(x1),
        "y_text": fmt(x2),
        "z": float(value),
        "z_text": fmt(value),
        "optimal": value == best_z,
        "tooltip": f"(x1, x2) = ({fmt(x1)}, {fmt(x2)}), z = {fmt(value)}",
    }


def solve_graphical(lp):
    """Solve a two-variable LP exactly and return vertices and drawing data."""
    if lp.n != 2:
        raise ValueError("The graphical method needs exactly two decision variables.")
    lines = boundary_lines(lp)
    vertices = feasible_vertices(lp, lines)
    directions = recession_directions(lines)
    region_bounded = not directions
    result = {
        "status": "infeasible",
        "x": None,
        "z": None,
        "vertices": vertices,
        "optimal_vertices": [],
        "region_bounded": region_bounded,
        "polygon": [],
        "lines": [line_for_drawing(line) for line in lines],
    }
    if not vertices:
        return result
    if any(improves(lp, direction) for direction in directions):
        result["status"] = "unbounded"
        result["polygon"] = drawing_polygon(vertices, lp, None)
        return result
    values = [lp.evaluate(point) for point in vertices]
    best_z = max(values) if lp.sense == "max" else min(values)
    best = [point for point, value in zip(vertices, values) if value == best_z]
    result["status"] = "optimal"
    result["x"] = best[0]
    result["z"] = best_z
    result["optimal_vertices"] = best
    result["polygon"] = drawing_polygon(vertices, lp, best_z)
    return result


def drawing_polygon(vertices, lp, best_z):
    """Order the vertices and attach the exact tooltip strings."""
    return [vertex_for_drawing(point, lp, best_z) for point in order_by_angle(vertices)]


def graphical_to_dict(result, lp):
    """Return a JSON-ready version of the graphical result."""
    x, z = result["x"], result["z"]
    return {
        "status": result["status"],
        "x": None if x is None else [fmt(value) for value in x],
        "x_float": None if x is None else [float(value) for value in x],
        "z": None if z is None else fmt(z),
        "region_bounded": result["region_bounded"],
        "polygon": result["polygon"],
        "lines": result["lines"],
        "optimal_vertices": [
            {"x": fmt(point[0]), "y": fmt(point[1])} for point in result["optimal_vertices"]
        ],
        "objective": {"c": [fmt(value) for value in lp.c], "sense": lp.sense},
    }
