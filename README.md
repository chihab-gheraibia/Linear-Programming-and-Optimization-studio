# LP Studio

A hand-written linear programming solver with a modern web interface for operations research courses.

[![tests](https://github.com/chihab-gheraibia/Linear-Programming-and-Optimization-studio/actions/workflows/tests.yml/badge.svg)](https://github.com/chihab-gheraibia/Linear-Programming-and-Optimization-studio/actions/workflows/tests.yml)

## Features

- Exact arithmetic engine (`fractions.Fraction`, symbolic Big-M) for max and min problems.
- Big-M simplex with a stored trace of every tableau and a step-by-step player.
- Graphical method for two variables, drawn with hand-written SVG.
- Dualisation, shadow prices, complementary slackness and sensitivity analysis.
- What-if sliders that use the final tableau inside a range, then re-solve outside it.
- Flask JSON API for parsing, solving and interpreting a model.
- Single-page offline interface: no framework, no CDN, no external fonts.
- Optional comparison with docplex/CPLEX when it is installed locally.

## Quick start

Python 3.10 or newer is recommended.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5000>.

The app works offline: HTML, CSS and JavaScript are served from this repository.

## Using the interface

1. **Describe** — pick a course example or write your own notes.
2. **Model** — type the LP in text mode or switch to form mode. Parsing is live.
3. **Solve** — inspect the exact solution, play the simplex iterations, view the graph, read the dual and explore ranges.
4. **Interpret** — read the plain-language summary, compare with docplex, copy, download JSON or export a printable report.

Text syntax is one objective per model and one constraint per line:

```text
Max z = 300x1 + 200x2
x1 + 2x2 <= 20
2x1 + x2 <= 22
x1 + x2 <= 12
```

`<=`, `>=`, `=`, `≤`, `≥` and unicode coefficients are accepted.

## Project layout

```text
lp_studio/
├── app.py                     Flask app and JSON routes
├── templates/index.html       Single-page interface
├── static/css/styles.css      Design tokens, light/dark themes, print styles
├── static/js/app.js           State, API calls, simplex player, SVG, ranges
├── solver/
│   ├── model.py               Exact LP model and formatting
│   ├── parser.py              Free-text LP parser
│   ├── graphical.py           Two-variable method and drawing data
│   ├── simplex.py             Big-M simplex with symbolic M and tableaux
│   ├── dual.py                Dual rules, solution and shadow prices
│   ├── complementary.py       Exact complementary-slackness check
│   ├── sensitivity.py         Objective/rhs ranges and what-if
│   ├── examples.py            Course examples
│   ├── display.py             Console tableau helper
│   └── verify_docplex.py      Optional CPLEX comparison
└── tests/
    ├── test_engine.py         A–F course and regression suite
    └── fuzz_vs_scipy.py       Optional 300-LP cross-check
```

## API

All routes answer `{ "ok": true, ... }` or `{ "ok": false, "error": "..." }`.

| Route | Purpose |
| --- | --- |
| `GET /api/examples` | List ready-to-load examples |
| `POST /api/parse` | Echo the parsed model |
| `POST /api/solve` | Solve and return steps, flags, exact and decimal values |
| `POST /api/dual` | Dual, solution, rules and shadow prices |
| `POST /api/check` | Complementary-slackness verdict for a proposed `x` |
| `POST /api/sensitivity` | All coefficient and right-hand-side ranges |
| `POST /api/whatif` | Exact answer to one coefficient change |
| `POST /api/verify` | Optional docplex comparison |

Each POST accepts either `{ "text": "..." }` or a structured model with `sense`, `c`, `A`, `ops`, `b` and `names`.

## Tests

```bash
python tests/test_engine.py
python -m pytest tests/test_engine.py -q
python tests/fuzz_vs_scipy.py   # optional, needs scipy
```

GitHub Actions runs both test commands on Python 3.10 and 3.12.

## Optional validation

```bash
pip install scipy    # only for tests/fuzz_vs_scipy.py
pip install docplex  # only for the Compare button
```

The solver itself never depends on either package.

## Documentation

See [EXPLAIN.md](EXPLAIN.md) for the course-oriented explanation of every method, the dual conversion rules, Big-M, exact arithmetic and the validation strategy.

## Git workflow

Work happens on short feature branches (`feat/api`, `feat/ui-*`, `docs/explain`) with small commits. Each branch is merged into `main` with `--no-ff` and pushed. `v0.1-engine` and `v0.2-theory` mark the first two checkpoints; `v1.0` marks the complete application.
