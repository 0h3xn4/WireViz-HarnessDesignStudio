"""Basic software metrics (ECSS-Q-ST-80C 6.2.5.3, 7.1.4, 7.1.5, 7.1.6; gap G-05).

Size (source lines without blanks and comments), number of functions, McCabe-style complexity
(1 + decision points per function), number of tests, and optionally coverage from a `coverage json`
file. Standard library only. Prints JSON; `--write` stores it in compliance/metrics.json.
Fault density and failure intensity come from the problem reports (compliance/docs/PROBLEM_REPORTING.md).
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AREAS = {"core": "src/harness_design_studio/core", "gui": "src/harness_design_studio/gui", "cli": "src/harness_design_studio/cli",
         "tests": "tests", "tools": "tools"}  # fmt: skip
BRANCHES = (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.IfExp, ast.comprehension,
            ast.Assert, ast.match_case)  # fmt: skip


def source_lines(text: str) -> int:
    return sum(1 for x in text.splitlines() if x.strip() and not x.strip().startswith("#"))


def complexity(fn: ast.AST) -> int:
    n = 1
    for node in ast.walk(fn):
        if isinstance(node, BRANCHES):
            n += 1
        elif isinstance(node, ast.BoolOp):
            n += len(node.values) - 1
    return n


def area_metrics(folder: Path) -> dict[str, object]:
    lines = functions = tests = 0
    worst: list[tuple[int, str]] = []
    scores: list[int] = []
    for p in sorted(folder.rglob("*.py")):
        text = p.read_text(encoding="utf-8")
        lines += source_lines(text)
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                functions += 1
                tests += node.name.startswith("test_")
                c = complexity(node)
                scores.append(c)
                worst.append((c, f"{p.relative_to(ROOT)}:{node.name}"))
    worst.sort(key=lambda x: (-x[0], x[1]))
    return {
        "source_lines": lines,
        "functions": functions,
        "tests": tests,
        "complexity_mean": round(sum(scores) / len(scores), 2) if scores else 0,
        "complexity_max": worst[0][0] if worst else 0,
        "most_complex": [f"{n} {c}" for c, n in worst[:5]],
    }


def collect(coverage_json: Path | None = None) -> dict[str, object]:
    out: dict[str, object] = {a: area_metrics(ROOT / d) for a, d in AREAS.items()}
    if coverage_json is not None and coverage_json.is_file():
        data = json.loads(coverage_json.read_text(encoding="utf-8"))
        t = data["totals"]
        out["coverage_percent"] = {
            "statements": round(t["percent_statements_covered"], 2)
            if "percent_statements_covered" in t
            else round(t["percent_covered"], 2),
            "branches": round(100 * t["covered_branches"] / t["num_branches"], 2)
            if t.get("num_branches")
            else None,
        }
    return out


def main(argv: list[str]) -> int:
    cov = None
    if "--coverage" in argv:
        at = argv.index("--coverage") + 1
        if at >= len(argv):
            print(
                "usage: python -m tools.metrics [--coverage coverage.json] [--write]",
                file=sys.stderr,
            )
            return 2
        cov = Path(argv[at])
    text = json.dumps(collect(cov), indent=2, sort_keys=True) + "\n"
    if "--write" in argv:
        (ROOT / "compliance" / "metrics.json").write_text(text, encoding="utf-8")
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
