# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-211: Harness Design Studio does not copy or import WireViz code.

The part that a test can show is the import: no Python file of this folder imports `wireviz`, and
the package does not list it as a dependency. (That nothing was copied was checked once by token
comparison and the git history; see compliance/legal/legal-audit.md, area 3.)
"""

import ast
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".venv", "__pycache__", "build", "dist", "harness_design_studio.egg-info"}


def _imports(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "__import__"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.add(node.args[0].value.split(".")[0])
    return names


def test_no_file_imports_wireviz() -> None:
    offenders = []
    for path in sorted(ROOT.rglob("*.py")):
        if SKIP & set(path.relative_to(ROOT).parts):
            continue
        if "wireviz" in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            offenders.append(path.relative_to(ROOT).as_posix())
    assert not offenders, offenders


def test_the_package_does_not_depend_on_wireviz() -> None:
    meta = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    deps = list(meta["dependencies"])
    for extra in meta["optional-dependencies"].values():
        deps += extra
    assert not [d for d in deps if d.lower().startswith("wireviz")]


def test_the_check_finds_an_import() -> None:
    assert "wireviz" in _imports(ast.parse("import wireviz.Harness"))
    assert "wireviz" in _imports(ast.parse("from wireviz import wireviz"))
    assert "wireviz" in _imports(ast.parse("__import__('wireviz')"))
    assert "wireviz" not in _imports(ast.parse("x = 'import wireviz'"))
