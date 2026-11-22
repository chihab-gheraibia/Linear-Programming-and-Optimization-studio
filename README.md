# LP Studio

A hand-written linear programming solver with a modern web interface for operations research courses.

## Features

- Exact arithmetic engine (`fractions.Fraction`, symbolic Big-M) for max and min problems
- Big-M simplex with a stored trace of every tableau
- Graphical method for two variables, with hand-written SVG
- Dualisation, complementary slackness and Chapter 4 sensitivity analysis
- Flask JSON API for parsing, solving and interpreting a model
- Single-page offline interface: no framework, no CDN, no external fonts

## Run

```bash
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5000>.

## Tests

[![tests](https://github.com/chihab-gheraibia/Linear-Programming-and-Optimization-studio/actions/workflows/tests.yml/badge.svg)](https://github.com/chihab-gheraibia/Linear-Programming-and-Optimization-studio/actions/workflows/tests.yml)

```bash
python tests/test_engine.py
python -m pytest tests/test_engine.py -q
```
