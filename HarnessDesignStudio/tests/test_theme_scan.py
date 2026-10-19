"""D-150: no colour, font family or font size is written in the GUI code outside `gui/theme/`.

Every value comes from the tokens (`theme.color`, `theme.type`, `theme.font`), so a theme change and
the design rules of CLAUDE.md reach every widget. Plain AST scan, no display needed."""

import ast
import re
from pathlib import Path

GUI = Path(__file__).resolve().parents[1] / "src" / "harness_design_studio" / "gui"
THEME = GUI / "theme"
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FAMILIES = {
    "Inter",
    "JetBrains Mono",
    "IBM Plex Sans",
    "IBM Plex Mono",
    "Segoe UI",
    "Consolas",
    "Arial",
    "Helvetica",
    "Courier",
    "Courier New",
    "Times New Roman",
    "monospace",
    "sans-serif",
    "system-ui",
}
SIZE_SETTERS = {"setPixelSize", "setPointSize", "setPointSizeF"}


def _files() -> list[Path]:
    return sorted(p for p in GUI.rglob("*.py") if THEME not in p.parents)


def _is_number(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, int | float)


def violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    found: list[str] = []
    for node in ast.walk(tree):
        where = f"{path.relative_to(GUI)}:{getattr(node, 'lineno', 0)}"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docstrings:
                continue
            text = node.value
            if HEX.search(text):
                found.append(f"{where}: colour {text!r}")
            if text in FAMILIES or "font-family" in text or "font-size" in text:
                found.append(f"{where}: font {text!r}")
        elif isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name == "QColor" and sum(_is_number(a) for a in node.args) >= 3:
                found.append(f"{where}: QColor with numbers")
            if name in SIZE_SETTERS and node.args and _is_number(node.args[0]):
                found.append(f"{where}: {name} with a number")
            if name == "QFont" and node.args and isinstance(node.args[0], ast.Constant):
                found.append(f"{where}: QFont with a family or size literal")
            if name == "setFamily" and node.args and isinstance(node.args[0], ast.Constant):
                found.append(f"{where}: setFamily with a literal")
    return found


def test_no_colour_font_family_or_font_size_outside_the_theme_package() -> None:
    assert THEME.is_dir() and _files()
    found = [v for p in _files() for v in violations(p)]
    assert not found, "write these as tokens in gui/theme/tokens.py:\n" + "\n".join(found)


def test_the_scan_sees_what_it_is_meant_to_see(tmp_path: Path) -> None:
    sample = tmp_path / "x.py"
    sample.write_text(
        "from PySide6.QtGui import QColor, QFont\n"
        'a = "#ABCDEF"\nb = QColor(1, 2, 3)\nc = "Inter"\nf = QFont()\nf.setPixelSize(12)\n'
        'g = "font-size: 12px"\n',
        encoding="utf-8",
    )
    # (the scan prints paths relative to the GUI folder, so check the kinds of finding only)
    kinds = {v.split(": ", 1)[1].split(" ", 1)[0] for v in _scan_outside(sample)}
    assert kinds >= {"colour", "QColor", "font", "setPixelSize"}


def _scan_outside(path: Path) -> list[str]:
    global GUI
    old = GUI
    GUI = path.parent
    try:
        return violations(path)
    finally:
        GUI = old
