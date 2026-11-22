"""Flask routes for LP Studio.

Every endpoint answers with {ok: true, ...} or {ok: false, error: "..."}.
No stack trace is ever sent to the browser.
"""

from fractions import Fraction

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from solver.examples import EXAMPLES, list_examples
from solver.graphical import graphical_to_dict, solve_graphical
from solver.model import LP
from solver.parser import parse_lp
from solver.simplex import solve


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
        return ok_response(examples=list_examples(), items=EXAMPLES)

    @app.route("/api/parse", methods=["POST"])
    def api_parse():
        """Echo the model that the parser understood."""
        lp = load_model(request_data())
        return ok_response(model=lp.to_dict())

    @app.route("/api/solve", methods=["POST"])
    def api_solve():
        """Solve with the simplex and, when possible, with the graphical method."""
        lp = load_model(request_data())
        result = solve(lp)
        payload = result.to_dict()
        payload["model"] = lp.to_dict()
        payload["graphical"] = None
        if lp.n == 2:
            payload["graphical"] = graphical_to_dict(solve_graphical(lp), lp)
        return ok_response(**payload)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
