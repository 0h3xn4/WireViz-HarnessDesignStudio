# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""R11: the scripting interface is stable, and it has no Qt in it.

`tests/fixtures/api_snapshot.json` holds the names of `harness_design_studio.api.__all__`, the
signature of each function, the fields of each result type and the base classes of each exception.
It changes only on purpose: `python -m tools.gen_api_snapshot`, then follow
docs/developer/api-stability.md. A second test imports the interface in a process where Qt cannot
be imported at all."""

import json
import subprocess
import sys
from pathlib import Path

from harness_design_studio import api
from tools.gen_api_snapshot import TARGET, render, snapshot

ROOT = Path(__file__).resolve().parents[1]


def test_the_interface_is_the_one_in_the_snapshot() -> None:
    assert TARGET.read_text(encoding="utf-8") == render(), (
        "The scripting interface changed. If that is on purpose: python -m tools.gen_api_snapshot, "
        "read the diff, raise API_VERSION for a change that can break a script, and update "
        "docs/developer/api-stability.md and the CHANGELOG."
    )


def test_every_public_name_is_listed_and_documented() -> None:
    public = {n for n in vars(api) if not n.startswith("_")}
    listed = set(api.__all__)
    assert len(api.__all__) == len(listed), "a name is listed twice"
    assert listed <= public
    for name in public - listed:  # what is not listed is an import, never something defined here
        assert getattr(getattr(api, name), "__module__", "") != api.__name__, name
    for name in listed:
        obj = getattr(api, name)
        if callable(obj) and not isinstance(obj, type):
            assert obj.__doc__ and len(obj.__doc__.split()) > 8, f"{name} has no docstring"
        elif isinstance(obj, type) and obj.__module__.startswith("harness_design_studio.api"):
            assert obj.__doc__, name
    assert api.__doc__ and "Qt" in api.__doc__


def test_the_snapshot_covers_the_result_types_and_the_error_tree() -> None:
    snap = snapshot()
    assert snap["api_version"] == api.API_VERSION == 1
    for name in ("GenerateResult", "CheckResult", "ExportResult", "ConfigReport", "FindingRecord"):
        assert snap["types"][name]["fields"], name
        assert "to_dict" in snap["types"][name]["methods"], name
    for name, bases in snap["errors"].items():
        assert "HarnessError" in bases or name == "HarnessError", name
    assert snap["errors"]["ProjectDamagedError"][:2] == ["LoadError", "HarnessError"]
    assert snap["errors"]["ConfigValueError"][:2] == ["EditError", "HarnessError"]


BLOCK_QT = """
import sys

class NoQt:
    BLOCKED = ("PySide6", "PyQt5", "PyQt6", "shiboken6", "shiboken2", "PySide2")

    def find_spec(self, name, path=None, target=None):
        if name.split(".")[0] in self.BLOCKED:
            raise ImportError(f"{name} is blocked for this test")
        return None

sys.meta_path.insert(0, NoQt())
for name in list(sys.modules):
    assert name.split(".")[0] not in NoQt.BLOCKED, name

import tempfile
from pathlib import Path
from harness_design_studio import api

with tempfile.TemporaryDirectory() as work:
    folder = Path(work) / "p"
    api.create_project(folder, "first-steps")
    assert api.generate(folder).ok
    assert api.run_checks(folder).rules_run == 39
    assert api.explain_all(folder)
    assert api.export(folder).written
    assert api.get_config(folder).total == 17
    assert api.set_config(folder, "derating", "bundle_derating", 0.8).value == 0.8

bad = [m for m in sys.modules if m.split(".")[0] in NoQt.BLOCKED or m.startswith("harness_design_studio.gui")]
assert not bad, bad
print("ok")
"""


def test_the_interface_works_where_qt_cannot_be_imported(tmp_path: Path) -> None:
    done = subprocess.run(  # noqa: S603 (tests only: our own interpreter and a fixed script)
        [sys.executable, "-c", BLOCK_QT],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
        env={
            "PYTHONPATH": str(ROOT / "src"),
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
        },
        check=False,
    )
    assert done.returncode == 0 and done.stdout.strip() == "ok", done.stderr[-2000:]


def test_the_blocker_really_blocks_qt() -> None:
    """The test above would pass vacuously if the blocker did nothing."""
    script = (
        BLOCK_QT.split("import tempfile")[0]
        + "\ntry:\n    import PySide6\nexcept ImportError:\n    print('blocked')\n"
    )
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert done.stdout.strip() == "blocked", done.stderr[-1000:]


def test_the_snapshot_file_is_plain_json() -> None:
    assert json.loads(TARGET.read_text(encoding="utf-8"))["all"] == sorted(api.__all__)
