# How LP Studio works

This document explains the mathematics implemented in the solver and how each web panel relates to the course methods.

## 1. The model

A linear program is stored as

```text
max/min z = cᵀx
A x (≤, ≥, =) b
x_j ≥ 0, x_j ≤ 0 or x_j free
```

`solver/model.py` keeps every coefficient as `fractions.Fraction`. The input parser accepts decimal strings such as `0.5` because `Fraction("0.5")` is exact, but no solver decision is ever made with a binary float. Floats are produced only at the very end for display and for optional external comparisons.

That choice matters for the course examples: values such as `4/3`, `5/2` and `32600` must stay exact, and reduced costs containing the symbolic Big-M must not be rounded into zero.

## 2. Parsing

`solver/parser.py` reads one objective and one constraint per line. It supports:

- `Max`, `Min`, `maximize`, `minimise`, and French `s.c.` headers;
- `<=`, `>=`, `=`, `≤`, `≥`;
- terms on both sides of a constraint;
- variables such as `x1`, `xA`, `x_2`;
- decimals and fractions.

A non-negativity line is ignored because it is metadata for the solver, not a resource constraint. Bad lines produce a `ParseError` with the line number, which the interface highlights in the editor gutter.

## 3. Big-M simplex

`solver/simplex.py` implements the primal simplex by hand.

For every `≥` row a surplus variable `-s` and an artificial variable `+a` are added. For every `=` row one artificial variable is added. Artificial columns receive cost `M`, represented by the small `MNum(a, b)` class as `a + b·M`.

The entering column uses Δj = Cj − Zj for a maximisation. A minimisation is solved as `max −z`, and the reported `z` is converted back at the end. The leaving row uses the minimum ratio test, with Bland's rule as a deterministic fallback to prevent cycling.

Each pivot is saved as a snapshot containing:

- the basis and Cb column;
- the full tableau, b column, Zj and Δj rows;
- the entering and leaving variables, pivot cell and ratios;
- a plain-language sentence explaining the pivot.

Those snapshots feed the simplex player, so the UI never recomputes history.

An infeasible problem is detected when an artificial variable remains positive in the final basis. An unbounded problem is detected when the entering column has no positive pivot. Both checks are applied even when Δj still looks improving.

## 4. Graphical method

For two decision variables, `solver/graphical.py` enumerates every intersection of two boundary lines, keeps the points that satisfy all constraints, and evaluates the objective at each feasible vertex. Recession directions are examined to distinguish a bounded optimum from an unbounded region.

The same module converts exact vertices into drawing data. The interface draws the constraint lines, the feasible polygon, vertex tooltips and a dashed objective line controlled by a slider. Moving the slider changes only the line `c₁x₁ + c₂x₂ = k`; the underlying exact solution never changes.

## 5. The dual

The dual is built by the rules below. They are the rules approved for the course and are implemented exactly in `dualize()`.

| Primal feature | Max primal | Min primal |
| --- | --- | --- |
| constraint `≤` | dual variable `y ≥ 0` | dual variable `y ≤ 0` |
| constraint `≥` | dual variable `y ≤ 0` | dual variable `y ≥ 0` |
| constraint `=` | dual variable free | dual variable free |
| variable `x ≥ 0` | dual constraint `≥` | dual constraint `≤` |
| variable `x ≤ 0` | dual constraint `≤` | dual constraint `≥` |
| variable free | dual constraint `=` | dual constraint `=` |

The dual objective coefficients are the primal right-hand sides; its right-hand sides are the primal objective coefficients.

To solve a dual whose variables are non-positive or free, `dual_to_lp()` substitutes:

- `y ≤ 0` becomes `−y'`, with `y' ≥ 0`;
- free `y` becomes `y⁺ − y⁻`, with both parts non-negative.

`recover_y()` maps the substituted solution back to the displayed dual variables. When both problems are optimal, the interface verifies w = z (strong duality).

Shadow prices are the dual variables attached to the primal constraints. A non-zero shadow price means the constraint is binding: one extra unit of that resource changes the objective by that price while the basis stays valid.

## 6. Complementary slackness

`solver/complementary.py` tests a proposed point `x` without asking the user to guess multipliers.

For every primal constraint that is not saturated, the corresponding dual variable is set to zero. For every positive primal variable, the associated dual constraint is turned into an equality. The remaining small linear system is solved with exact Gauss-Jordan elimination. The module then checks the dual signs and all dual constraints and returns one of `optimal` or `not optimal`, with the reasoning steps.

This is what the Series 3 Ex2 checks use. A point can be primal feasible yet fail because one derived dual constraint is violated.

## 7. Sensitivity analysis

`solver/sensitivity.py` studies one coefficient change at a time.

For an objective coefficient `cⱼ`:

- if `xⱼ` is basic, the range is the intersection of all inequalities keeping the basic variables non-negative;
- if `xⱼ` is non-basic, its reduced cost may move until it becomes favourable.

For a right-hand side `bᵢ`, the direction vector is read from the slack/surplus column of the final tableau. The range keeps every basic value `b + Δ·d` non-negative.

Inside a valid range the optimum moves by a formula and the basis does not change. Outside it the module re-solves the changed LP and reports that the basis changed. The web sliders use this distinction, so the displayed `z` is exact in both cases.

## 8. Validation

The project is validated in three layers:

1. `tests/test_engine.py` contains 34 course-based and regression tests labelled A–F. They cover parsing, graphical solution, simplex tableaux, dual rules, complementary slackness and sensitivity.
2. `tests/fuzz_vs_scipy.py` generates 300 random LPs and compares optimal values and solutions with SciPy. SciPy is optional and is never used by the engine.
3. `solver/verify_docplex.py` optionally compares a solved model with CPLEX through docplex. If docplex or a CPLEX runtime is absent, the Compare panel simply reports that it is unavailable.

The real TD1 Part I data and the real Series 3 Ex2 LPs are included in `solver/examples.py`, so the exact course answers are regression-tested rather than typed only into documentation.

The §9-B exercise is kept as printed: its text contains one explicit constraint, so the test asserts one constraint and ignores the non-negativity line.

## 9. Interface map

| Panel | Engine module |
| --- | --- |
| Solution | `simplex.py` result flags and exact values |
| Simplex player | stored tableaux from `simplex.py` |
| Graph | drawing data from `graphical.py`, SVG written in `app.js` |
| Dual | `dual.py` plus `complementary.py` |
| Sensitivity | `sensitivity.py` ranges and what-if answers |
| Interpret | summary built from all of the above, optional `verify_docplex.py` |

The interface is a single HTML page with vanilla JavaScript. It stores the last text, notes, theme and result in `localStorage`, supports light and dark themes, keyboard focus rings, responsive layouts and a print stylesheet used by the report export.
