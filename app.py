"""Flask routes for LP Studio.

Every endpoint answers with {ok: true, ...} or {ok: false, error: "..."}.
No stack trace is ever sent to the browser.
"""

from fractions import Fraction

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from solver.complementary import check_optimality
from solver.dual import dual_solution, dual_solution_to_dict
from solver.examples import list_examples
from solver.graphical import graphical_to_dict, solve_graphical
from solver.model import LP, fmt
from solver.parser import operator_hints, parse_lp
from solver.sensitivity import sensitivity_report, what_if
from solver.simplex import solve
from solver.verify_docplex import solve_with_docplex


def jsonable(value):
    """Convert exact numbers to strings so that every payload can be serialized."""
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item) for item in value]
    if isinstance(value, (Fraction, bool, str, int, float)) or value is None:
        return value if not isinstance(value, Fraction) else str(value)
    if hasattr(value, "a") and hasattr(value, "b"):
        return str(value)
    return str(value)


def fmt_decimal(value):
    """Print a decimal with at most six digits and no trailing zeros."""
    if value is None:
        return None
    text = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def ok_response(**payload):
    """Wrap a successful payload in the common JSON envelope."""
    return jsonify(jsonable({"ok": True, **payload}))


def error_response(message, status=400):
    """Wrap a friendly error in the common JSON envelope."""
    return jsonify(jsonable({"ok": False, "error": str(message)})), status


def request_data():
    """Read the JSON body and reject requests that are not JSON objects."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("Send a JSON object with a 'text' field or a structured model.")
    return data


def load_model(data):
    """Build an LP from free text or from the structured form payload."""
    if data.get("text") is not None:
        return parse_lp(data["text"])
    if "c" in data and "A" in data:
        return LP.build(
            data.get("sense", "max"),
            data["c"],
            data["A"],
            data["ops"],
            data["b"],
            data.get("names") or data.get("var_names"),
        )
    raise ValueError("Provide either 'text' or sense, c, A, ops, b and names.")


def create_app():
    """Create the Flask application and register all routes."""
    app = Flask(__name__)

    @app.errorhandler(Exception)
    def handle_error(error):
        if isinstance(error, HTTPException):
            return error_response(error.description, error.code)
        return error_response(error.message if hasattr(error, "message") else str(error), 400)

    @app.route("/")
    def index():
        """Serve the single-page interface."""
        return render_template("index.html")

    @app.route("/api/examples")
    def api_examples():
        """List the ready-to-load course examples."""
        examples = list_examples()
        return ok_response(examples=examples, items=examples)

    @app.route("/api/parse", methods=["POST"])
    def api_parse():
        """Echo the model that the parser understood."""
        data = request_data()
        lp = load_model(data)
        hints = operator_hints(data["text"]) if isinstance(data.get("text"), str) else []
        return ok_response(model=lp.to_dict(), hints=hints)

    @app.route("/api/solve", methods=["POST"])
    def api_solve():
        """Solve with the simplex and, when possible, with the graphical method."""
        data = request_data()
        lp = load_model(data)
        result = solve(lp)
        payload = result.to_dict()
        payload["model"] = lp.to_dict()
        payload["hints"] = operator_hints(data["text"]) if isinstance(data.get("text"), str) else []
        payload["z_display"] = fmt_decimal(payload["z_float"])
        payload["x_display"] = None if payload["x_float"] is None else [fmt_decimal(value) for value in payload["x_float"]]
        payload["graphical"] = None
        if lp.n == 2:
            payload["graphical"] = graphical_to_dict(solve_graphical(lp), lp)
        return ok_response(**payload)

    @app.route("/api/dual", methods=["POST"])
    def api_dual():
        """Return the dual, its solution, the rules and the shadow prices."""
        data = request_data()
        lp = load_model(data)
        primal = solve(lp)
        info = dual_solution(lp, primal, data.get("var_signs"))
        payload = dual_solution_to_dict(info)
        payload["strong_duality"] = (
            primal.status == "optimal" and info["w"] is not None and info["w"] == primal.z
        )
        payload["z_primal"] = None if primal.z is None else fmt(primal.z)
        payload["z_float"] = None if primal.z is None else float(primal.z)
        payload["z_display"] = fmt_decimal(payload["z_float"])
        payload["y_display"] = None if info["y"] is None else [fmt_decimal(value) for value in info["y"]]
        payload["w_display"] = fmt_decimal(payload["w_float"])
        return ok_response(**payload)

    @app.route("/api/check", methods=["POST"])
    def api_check():
        """Run complementary slackness on a proposed solution."""
        data = request_data()
        lp = load_model(data)
        proposed = data.get("x") or data.get("proposed")
        if not isinstance(proposed, list):
            raise ValueError("Send 'x' as a list of values, one per decision variable.")
        return ok_response(**check_optimality(lp, proposed).to_dict())

    @app.route("/api/sensitivity", methods=["POST"])
    def api_sensitivity():
        """Return all optimality and validity ranges."""
        lp = load_model(request_data())
        return ok_response(**sensitivity_report(lp))

    @app.route("/api/whatif", methods=["POST"])
    def api_whatif():
        """Answer a slider move with a formula result or a re-solve."""
        data = request_data()
        lp = load_model(data)
        if "kind" not in data or "index" not in data or "new_value" not in data:
            raise ValueError("Send kind ('c' or 'b'), index and new_value.")
        answer = what_if(lp, data["kind"], int(data["index"]), data["new_value"])
        return jsonify(jsonable(answer))

    @app.route("/api/verify", methods=["POST"])
    def api_verify():
        """Compare our answer with docplex when the optional solver is installed."""
        lp = load_model(request_data())
        comparison = solve_with_docplex(lp)
        if not comparison.get("available"):
            return jsonify(jsonable({"ok": False, "available": False,
                                     "error": comparison.get("error", "docplex is not installed")})), 404
        ours = solve(lp)
        match = (
            ours.status == "optimal" and comparison["status"] == "optimal"
            and abs(float(ours.z) - comparison["z"]) < 1e-6
        )
        return ok_response(
            docplex=comparison,
            ours={"z": None if ours.z is None else fmt(ours.z),
                  "z_float": None if ours.z is None else float(ours.z),
                  "iterations": max(len(ours.steps) - 1, 0)},
            match=match,
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
