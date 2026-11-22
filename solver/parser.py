"""Turn a free-text course statement into an LP object.

The parser is deliberately small: it reads terms one by one, moves everything
to the left of a constraint and reports a friendly message with the line number
as soon as it sees something it cannot understand.
"""

import re

from .model import F, LP, Constraint

NUMBER_RE = re.compile(r"\d+/\d+|\d*\.\d+|\d+")
VAR_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
OPERATOR_RE = re.compile(r"<=|>=|≤|≥|=<|=>|=|<|>")
OBJECTIVE_RE = re.compile(
    r"^\s*(maximiser|maximize|maximum|max|minimiser|minimize|minimum|min)\b",
    re.IGNORECASE,
)
OBJECTIVE_NAME_RE = re.compile(r"^\s*(?:z|w|f|objectif)\s*(?:\([^)]*\))?\s*=\s*", re.IGNORECASE)
LABEL_RE = re.compile(
    r"^(?:s\.?c\.?|s\.?t\.?|sous\s+contraintes?|subject\s+to|such\s+that|avec|"
    r"contraintes?|constraints?|sc|st)\s*:?\s*\.?$"
)
NONNEG_RE = re.compile(
    r"^(?:[A-Za-z][A-Za-z0-9_]*,)*(?:[A-Za-z][A-Za-z0-9_]*)"
    r"(?:>=|≥|=)0(?:,[A-Za-z][A-Za-z0-9_]*(?:>=|≥|=)0)*$"
)
OPERATORS = {
    "<=": "<=", "≤": "<=", "=<": "<=", "<": "<=",
    ">=": ">=", "≥": ">=", "=>": ">=", ">": ">=",
    "=": "=",
}


class ParseError(ValueError):
    """A friendly error raised for invalid input, always with a line number."""

    def __init__(self, message: str):
        """Store the message that will be shown directly in the interface."""
        super().__init__(message)
        self.message = message


def natural_key(name: str):
    """Sort x1, x2, x10 in the natural order instead of x1, x10, x2."""
    pieces = re.split(r"(\d+)", name)
    return tuple(
        (1, int(piece), "") if piece.isdigit() else (0, piece.lower(), "")
        for piece in pieces
        if piece
    )


def is_label_line(line: str) -> bool:
    """Recognise lines such as 's.c.' that only separate two parts of a text."""
    return bool(LABEL_RE.match(line.strip().lower()))


def is_nonnegativity_line(line: str) -> bool:
    """Recognise 'x1,x2 >= 0' or 'x1>=0, x2>=0' and ignore them."""
    return bool(NONNEG_RE.match(re.sub(r"\s+", "", line)))


def normalize_operator(text: str) -> str:
    """Convert <=, ≥, => and friends into the three operators of the engine."""
    return OPERATORS[text]


def operator_hints(text: str):
    """Report loose '<' or '>' tokens that are interpreted as ≤ or ≥."""
    hints = []
    for token in OPERATOR_RE.findall(text):
        if token == "<":
            hint = "'<' is treated as '<='"
        elif token == ">":
            hint = "'>' is treated as '>='"
        else:
            continue
        if hint not in hints:
            hints.append(hint)
    return hints


def parse_expression(text: str, line_no: int):
    """Read one sum of signed terms and return coefficients plus a constant.

    A term is an optional sign, an optional number and an optional variable:
    '3x1', '-x2', '2*x1', '0.5x2' and '1/2x1' are all accepted.
    """
    coefficients = {}
    constant = F(0)
    index = 0
    while index < len(text):
        if text[index].isspace() or text[index] == ",":
            index += 1
            continue
        sign, index = read_sign(text, index, line_no)
        number, index = read_number(text, index)
        if index < len(text) and text[index] == "*":
            index += 1
            while index < len(text) and text[index].isspace():
                index += 1
        match = VAR_RE.match(text, index)
        if match:
            name = match.group(0)
            amount = sign * (number if number is not None else F(1))
            coefficients[name] = coefficients.get(name, F(0)) + amount
            index = match.end()
        elif number is not None:
            constant += sign * number
        else:
            raise ParseError(
                f"Line {line_no}: cannot understand the term near '{text[index:index + 12]}'."
            )
    return coefficients, constant


def read_sign(text: str, index: int, line_no: int):
    """Return the sign of the next term and the position just after it."""
    if text[index] not in "+-":
        return 1, index
    sign = -1 if text[index] == "-" else 1
    index += 1
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or text[index] in "+-*":
        raise ParseError(f"Line {line_no}: a number or a variable is missing after the sign.")
    return sign, index


def read_number(text: str, index: int):
    """Read an optional integer, fraction or decimal from the current term."""
    match = NUMBER_RE.match(text, index)
    if match is None:
        return None, index
    return F(match.group(0)), match.end()


def split_items(text: str):
    """Split the input into (line number, item) pairs, keeping line numbers."""
    items = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        for piece in raw.split(";"):
            if piece.strip():
                items.append((line_no, piece.strip()))
    return items


def read_objective(line: str, line_no: int):
    """Read 'Max z = ...' and return the sense and the objective coefficients."""
    match = OBJECTIVE_RE.match(line)
    if match is None:
        return None
    sense = "max" if match.group(1).lower().startswith("max") else "min"
    rest = line[match.end():]
    rest = OBJECTIVE_NAME_RE.sub("", rest, count=1)
    if OPERATOR_RE.search(rest):
        raise ParseError(f"Line {line_no}: the objective must not contain <=, >= or =.")
    coefficients, _ = parse_expression(rest, line_no)
    if not coefficients:
        raise ParseError(f"Line {line_no}: the objective needs at least one variable.")
    return sense, coefficients


def read_constraint(line: str, line_no: int):
    """Move all terms to the left and return (coefficients, operator, rhs)."""
    match = OPERATOR_RE.search(line)
    if match is None:
        raise ParseError(
            f"Line {line_no}: constraint '{line}' has no operator; use <=, >= or =."
        )
    left, right = line[:match.start()], line[match.end():]
    left_coeffs, left_constant = parse_expression(left, line_no)
    right_coeffs, right_constant = parse_expression(right, line_no)
    names = set(left_coeffs) | set(right_coeffs)
    coefficients = {
        name: left_coeffs.get(name, F(0)) - right_coeffs.get(name, F(0))
        for name in names
    }
    return coefficients, normalize_operator(match.group(0)), right_constant - left_constant


def parse_lp(text: str) -> LP:
    """Convert a whole free-text problem into an LP or raise a ParseError."""
    items = split_items(text)
    if not items:
        raise ParseError("The problem is empty. Start with a line like 'Max z = 3x1 + 2x2'.")
    sense = None
    objective = {}
    raw_constraints = []
    for line_no, line in items:
        if is_label_line(line):
            continue
        found = read_objective(line, line_no)
        if found is not None:
            if sense is not None:
                raise ParseError(f"Line {line_no}: there is already one objective; remove the second one.")
            sense, objective = found
            continue
        if is_nonnegativity_line(line):
            continue
        raw_constraints.append(read_constraint(line, line_no))
    if sense is None:
        raise ParseError("Line 1: missing objective. Begin with 'Max' or 'Min', for example 'Max z = 3x1'.")
    names = sorted(set(objective) | set().union(*(set(item[0]) for item in raw_constraints)), key=natural_key)
    c = [objective.get(name, F(0)) for name in names]
    rows = [[item[0].get(name, F(0)) for name in names] for item in raw_constraints]
    constraints = [
        Constraint(numeric_row, op, rhs)
        for numeric_row, (_, op, rhs) in zip(rows, raw_constraints)
    ]
    return LP(sense, c, constraints, names)
