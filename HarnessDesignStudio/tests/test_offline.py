# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""REQ-OFFLINE-01: the application never touches the network (static and runtime checks)."""

import ast
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from tests.static_scan import DYNAMIC, imported_names

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "harness_design_studio"
PACKAGING = ROOT / "packaging"  # the entry points of the packaged programs

BANNED_MODULES = {
    "socket", "ssl", "http", "urllib", "urllib3", "requests", "httpx", "aiohttp",
    "ftplib", "smtplib", "telnetlib", "xmlrpc", "websocket", "websockets", "asyncio",
    "webbrowser", "imaplib", "poplib", "nntplib", "socketserver",
}  # fmt: skip
BANNED_QT = {"QtNetwork", "QtWebEngineCore", "QtWebEngineWidgets", "QtWebChannel", "QtWebSockets"}


def _imported_names(path: Path) -> set[str]:
    """Absolute dotted names (relative imports resolved; importlib/__import__ strings included)."""
    return imported_names(path, SRC.parent)


def _banned(name: str) -> bool:
    parts = name.split(".")
    return parts[0] in BANNED_MODULES or bool(BANNED_QT & set(parts)) or name == DYNAMIC


def test_no_network_imports_in_source() -> None:
    offenders = [
        f"{path.relative_to(SRC)}: {name}"
        for path in SRC.rglob("*.py")
        for name in _imported_names(path)
        if _banned(name)
    ]
    assert not offenders, offenders


def test_scanner_detects_banned_import(tmp_path: Path) -> None:
    pkg = tmp_path / "harness_design_studio" / "core"
    pkg.mkdir(parents=True)
    f = pkg / "bad.py"
    f.write_text("import socket\nfrom urllib import request\nfrom PySide6.QtNetwork import X\n")
    names = imported_names(f, tmp_path)
    assert "socket" in names and "urllib" in names and "PySide6.QtNetwork" in names
    hidden = {
        "a.py": "import importlib\nimportlib.import_module('socket')\n",
        "b.py": "__import__('http.client')\n",
        "c.py": "from importlib import import_module\nimport_module(name)\n",
        "d.py": "from .. import QtNetwork\n",  # relative import of a banned Qt module
        "e.py": "from ..QtNetwork import Socket\n",
    }
    for fname, text in hidden.items():
        (pkg / fname).write_text(text)
        assert any(_banned(n) for n in imported_names(pkg / fname, tmp_path)), fname


def test_nothing_in_source_imports_a_module_by_a_computed_name() -> None:
    """A computed importlib/__import__ name could reach a banned module unseen by the scan."""
    assert not [str(p.relative_to(SRC)) for p in SRC.rglob("*.py") if DYNAMIC in _imported_names(p)]


def test_runtime_sockets_blocked_cli_and_gui(tmp_path: Path) -> None:
    """Run the CLI and an offscreen GUI window with sockets patched to raise."""
    code = textwrap.dedent(
        """
        import sys

        # `python -I` ignores PYTHONPATH: put the tree under test first, then check that it is
        # the one that was imported (an installed copy elsewhere must not stand in for it)
        sys.path.insert(0, {tree!r})
        import harness_design_studio
        assert harness_design_studio.__file__.startswith({tree!r}), harness_design_studio.__file__

        import socket

        def _blocked(*a, **k):
            raise AssertionError("network access attempted")

        socket.socket = _blocked
        socket.create_connection = _blocked
        socket.getaddrinfo = _blocked

        from harness_design_studio.cli.main import main
        assert main(["--version"]) == 0

        from PySide6.QtCore import QSettings
        from harness_design_studio.gui.app import create_window
        # a temporary ini: the test must not read or write the developer's own settings
        win = create_window(QSettings({ini!r}, QSettings.Format.IniFormat))
        win.show()
        assert win.windowTitle()
        banned = [m for m in sys.modules if m.endswith(("QtNetwork", "QtWebEngineCore"))]
        assert not banned, banned
        """
    ).format(tree=str(SRC.parent), ini=str(tmp_path / "ui.ini"))
    result = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True, text=True, timeout=120, check=False,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(SRC.parent)},
    )  # fmt: skip
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_network_imports_in_the_packaging_entry_points() -> None:
    """The packaged programs start from `packaging/gui_entry.py` and `cli_entry.py` (D-207)."""
    entries = sorted(PACKAGING.glob("*.py"))
    assert {p.name for p in entries} >= {"gui_entry.py", "cli_entry.py"}
    offenders = [
        f"{p.name}: {name}"
        for p in entries
        for name in imported_names(p, PACKAGING)
        if _banned(name)
    ]
    assert not offenders, offenders


def test_the_app_builds_no_web_address_and_installs_no_crash_or_update_hook() -> None:
    """A URL made of a literal that starts with http, a crash hook that could upload, or a call
    that opens a web page would be a network path the import scan cannot see (D-207)."""
    found: list[str] = []
    for path in [*SRC.rglob("*.py"), *PACKAGING.glob("*.py")]:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and getattr(node.func, "id", getattr(node.func, "attr", "")) == "QUrl"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and str(node.args[0].value).startswith(("http", "ftp", "//"))
            ):
                found.append(f"{path.name}:{node.lineno}: QUrl of a web address")
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr in (
                        "excepthook",
                        "unraisablehook",
                    ):
                        found.append(f"{path.name}:{node.lineno}: sets {target.attr}")
    assert not found, found
