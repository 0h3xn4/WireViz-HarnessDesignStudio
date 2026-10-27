"""gui/strings.py: no name is assigned twice (the second silently wins) and no constant is dead.

E-F2 of the 1.8.0 audit: ``WAIVED`` and ``STEP_GENERATE`` were each defined twice, so the Problems
panel heading read as a whole sentence. ruff and mypy accept a module variable assigned twice.
E-F7: 67 constants nobody used. Both checks read the source with ``ast``; no Qt.
"""

import ast
import collections
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / "src" / "harness_design_studio" / "gui" / "strings.py"

# Names that are read by a prefix or a dictionary lookup, never by their own name. Each needs a
# reason. (None needed today: the prefix scans in the tests use ``vars(strings)`` on constants
# that the window also uses by name.)
ALLOWED_UNREFERENCED: dict[str, str] = {}


def _top_level_names() -> dict[str, list[int]]:
    names: dict[str, list[int]] = collections.defaultdict(list)
    for node in ast.parse(STRINGS.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names[target.id].append(node.lineno)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names[node.target.id].append(node.lineno)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names[node.name].append(node.lineno)
    return names


def test_no_name_in_strings_is_assigned_twice() -> None:
    twice = {n: lines for n, lines in _top_level_names().items() if len(lines) > 1}
    assert not twice, f"assigned more than once in gui/strings.py (the last one wins): {twice}"


def test_the_waived_heading_and_the_waived_toast_are_two_names() -> None:
    from harness_design_studio.gui import strings

    assert strings.WAIVED == "Waived"
    assert strings.WAIVED_TOAST.startswith("Waived. ")
    assert strings.STEP_GENERATE == "Generate"


@pytest.mark.slow
def test_every_string_constant_is_used_somewhere() -> None:
    names = _top_level_names()
    texts: list[str] = []
    for folder in ("src", "tests", "tools"):
        for path in (ROOT / folder).rglob("*.py"):
            if path == STRINGS or path == Path(__file__).resolve():
                continue
            texts.append(path.read_text(encoding="utf-8"))
    outside = "\n".join(texts)
    # Uses inside strings.py itself (one constant built from another) count, the definition does not.
    inside = STRINGS.read_text(encoding="utf-8")
    dead = []
    for name in names:
        if name in ALLOWED_UNREFERENCED:
            continue
        word = re.compile(r"\b" + re.escape(name) + r"\b")
        if not word.search(outside) and len(word.findall(inside)) <= 1:
            dead.append(name)
    assert not dead, (
        "constants in gui/strings.py that nothing uses (delete them, or list them in "
        f"ALLOWED_UNREFERENCED with the reason): {sorted(dead)}"
    )
