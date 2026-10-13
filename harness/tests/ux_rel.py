"""Shared set-up for the release / export / import view tests: the flatsat example as a real project
folder behind an `EditorController`, and a project with released harnesses."""

import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from harness_design_studio.core.outputs.build import write_outputs
from harness_design_studio.core.vcs.release import plan_release
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.tables import DictTableModel
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.resources import examples_path


def app() -> QApplication:
    return QApplication.instance() or QApplication([])  # type: ignore[return-value]


def themed(name: str = "light") -> ThemeManager:
    theme = ThemeManager()
    theme.apply(app(), name)  # type: ignore[arg-type]
    return theme


def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)


def flatsat_controller(tmp_path: Path) -> EditorController:
    """A controller with a private copy of the flatsat example open (so the lock file and any
    outputs go into `tmp_path`)."""
    root = examples_path()
    assert root is not None
    folder = tmp_path / "flatsat"
    shutil.copytree(root / "projects" / "flatsat", folder)
    ctl = EditorController(drc_delay_ms=600_000)  # no background check during a test
    ctl.open_path(folder)
    ctl.today = lambda: "2026-03-01"
    return ctl


def release_all(ctl: EditorController, harnesses: list[str] | None = None) -> list[str]:
    """Export the outputs, then release the harnesses of the open project that can be released
    (placeholders and unapproved parts are accepted, as in a test project; on flatsat only W001
    and W003 have every gauge decided). Returns the IDs released."""
    done: list[str] = []
    folder = ctl.outputs_folder()
    assert folder is not None
    write_outputs(ctl.project, folder)
    for hid in harnesses or sorted(ctl.project.harnesses):
        plan = plan_release(
            ctl.project,
            hid,
            by="Ada",
            checker="Bob",
            comment="Release for the review",
            when="2026-03-01",
            outputs_folder=folder,
            accept_placeholders="Example values for a test",
            accept_unapproved_parts="Example parts for a test",
        )
        if plan.ok and ctl.apply_change(plan, "released"):
            done.append(hid)
    return done


def collect(signal) -> list[tuple]:  # type: ignore[no-untyped-def,type-arg]
    """The arguments of every emission of `signal`, in order (a list that fills as it is emitted)."""
    calls: list[tuple] = []  # type: ignore[type-arg]
    signal.connect(lambda *args: calls.append(args))
    return calls


def dict_rows(model: DictTableModel) -> list[dict[Any, Any]]:
    """The rows of a table model that were given as dicts."""
    return [dict(r) for r in model.rows() if isinstance(r, Mapping)]


def outputs_of(ctl: EditorController) -> Path:
    """The outputs folder of a saved project."""
    folder = ctl.outputs_folder()
    assert folder is not None
    return folder
