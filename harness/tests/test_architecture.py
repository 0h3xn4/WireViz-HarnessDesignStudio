"""REQ-ARCH-01: the headless core must not depend on GUI or CLI code."""

from pathlib import Path

from tests.static_scan import imported_names

ROOT = Path(__file__).resolve().parents[1] / "src"
CORE = ROOT / "harness_design_studio" / "core"
FORBIDDEN_PREFIXES = (
    "harness_design_studio.gui",
    "harness_design_studio.cli",
    "PySide6",
    "PyQt5",
    "PyQt6",
    "shiboken",
)


def _imports(path: Path, root: Path = ROOT) -> list[str]:
    """Absolute names imported by a file: relative imports are resolved with their level."""
    return sorted(imported_names(path, root))


def _forbidden(names: list[str] | set[str]) -> list[str]:
    return [
        n
        for n in sorted(names)
        if n.startswith(FORBIDDEN_PREFIXES) or n == "<dynamic import>" or n.startswith("<outside")
    ]


def test_core_has_no_gui_or_cli_imports() -> None:
    bad = [f"{p.name}: {m}" for p in CORE.rglob("*.py") for m in _forbidden(_imports(p))]
    assert not bad, bad


def test_relative_imports_are_resolved_before_they_are_checked(tmp_path: Path) -> None:
    """`from ..gui import fonts` inside core/units.py is harness_design_studio.gui: the old scan
    saw only the module name 'gui' and let it through."""
    pkg = tmp_path / "harness_design_studio" / "core"
    pkg.mkdir(parents=True)
    bad = {
        "a.py": "from ..gui import fonts\n",
        "b.py": "from .. import cli\n",
        "c.py": "from ..gui.widgets import Foo\n",
        "d.py": "import importlib\nimportlib.import_module('PySide6.QtWidgets')\n",
        "e.py": "__import__('harness_design_studio.gui')\n",
        "f.py": "from ...gui import x\n",  # climbs out of the package
        "g.py": "import importlib\nimportlib.import_module(name)\n",  # a computed name
        "__init__.py": "from ..cli import main\n",
    }
    for name, text in bad.items():
        (pkg / name).write_text(text)
        assert _forbidden(_imports(pkg / name, tmp_path)), name
    names = _imports(pkg / "a.py", tmp_path)
    assert "harness_design_studio.gui" in names and "harness_design_studio.gui.fonts" in names
    ok = pkg / "ok.py"
    ok.write_text("from . import units\nfrom .ids import check_id\nfrom ..core import x\n")
    names = _imports(ok, tmp_path)
    assert "harness_design_studio.core.units" in names
    assert "harness_design_studio.core.ids" in names
    assert not _forbidden(names)
