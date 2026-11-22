"""Print a complete simplex trace in the terminal."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from solver.display import print_trace
from solver.examples import get_example
from solver.parser import parse_lp
from solver.simplex import solve


def main():
    """Solve the furniture example and print all tableaux."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    problem = get_example("furniture")
    print(problem["name"])
    print(problem["text"])
    print("\n" + "=" * 60 + "\n")
    lp = parse_lp(problem["text"])
    print_trace(solve(lp))


if __name__ == "__main__":
    main()
