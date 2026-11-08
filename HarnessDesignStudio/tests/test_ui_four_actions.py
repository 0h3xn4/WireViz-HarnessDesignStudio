# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type,assignment"
"""REQ-GUI-27. A systems engineer gets from nothing to a block diagram on disk in four actions:
New project, Add device (twice), Connect, Export diagram. This test plays that person and counts
what they have to do: the clicks (a button pressed, a gesture of the mouse from a port to a port)
and the dialogs that open (the program's own windows, the file and folder choosers, the question
boxes). It fails when either count is more than `FOUR_ACTIONS_BUDGET`.

It plays the person on the widgets (a mouse press on the button, a drag on the port), not through
the program's functions, so a button that stops working, a dialog that is added to the path, or a
second click that a step now needs shows here. It runs offscreen with the rest of the suite and on
the real platform of the lane `harness-real-platform.yml` (REQ-GUI-26), where each window it opens
is also held to the layout audit.

What it does not count: typing (the name of the project, of two devices, the folder) and the set-up
that comes before the four actions (the role, Quick mode). What the counts are for: a path that is
quick today stays quick when someone adds a question to it.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPoint, QPointF, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QApplication,
    QDialog,
    QFileDialog,
    QInputDialog,
    QMessageBox,
)

from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.layout_audit import audit  # noqa: E402

LEFT = Qt.MouseButton.LeftButton


@dataclass(frozen=True)
class Budget:
    clicks: int
    dialogs: int


# THE BUDGET of the systems engineer's four actions, in Quick mode (the quick-diagram path, the
# setting ui/quick, on after the role is chosen). These are the numbers the path costs today,
# counted by playing it; the failure message prints what was counted, step by step. A change that
# makes the path cost more fails the test. If a change makes it cheaper, lower the numbers in the
# same change, so that the gain cannot be given back unnoticed; if a step really has to get a click
# or a dialog more, say why in the pull request and raise it here, in this one place.
# Clicks: Home, New project..., Browse..., Create (4); Add device and OK, twice (4); the drag from
# port to port (1); Export diagram and Save in the chooser (2). Dialogs: New project, the folder
# chooser, the two Add device windows, the file chooser of Export diagram.
FOUR_ACTIONS_BUDGET = Budget(clicks=11, dialogs=5)


@dataclass
class Trail:
    """What the person did, in order, with the counts."""

    steps: list[str] = field(default_factory=list)
    clicks: int = 0
    dialogs: int = 0
    typed: int = 0
    stray: list[str] = field(default_factory=list)  # dialogs that opened outside the hooks
    findings: list[str] = field(default_factory=list)  # layout problems of the windows it opened

    def note(self, text: str) -> None:
        self.steps.append(text)

    def __str__(self) -> str:
        return (
            f"{self.clicks} clicks, {self.dialogs} dialogs, {self.typed} fields typed\n"
            + "\n".join(f"  {s}" for s in self.steps)
        )


class Person:
    """Uses the window with the mouse, and counts."""

    def __init__(self, win: MainWindow, trail: Trail, folder: Path, target: Path) -> None:
        self.win, self.trail, self.folder, self.target = win, trail, folder, target
        self.names = iter(("Star tracker", "Reaction wheel"))
        win.run_dialog = self.dialog  # type: ignore[assignment]
        win.ask_save_path = self.save_chooser  # type: ignore[assignment]
        for hook in ("ask_folder", "ask_text", "ask_choice", "ask_file"):
            setattr(win, hook, self._stray(hook))

    # ---- the mouse ------------------------------------------------------------------------
    def click(self, button: QAbstractButton, what: str) -> None:
        assert button.isVisible() and button.isEnabled(), f"{what}: the button is not there"
        self.trail.clicks += 1
        self.trail.note(f"click: {what}")
        QTest.mouseClick(button, LEFT)
        QApplication.processEvents()

    def drag(self, a: QPoint, b: QPoint, what: str) -> None:
        """One gesture: press on a port, carry, let go on a port (counted as one click)."""
        view = self.win.view.viewport()
        QTest.mousePress(view, LEFT, pos=a)
        for k in range(1, 5):
            QTest.mouseMove(view, pos=a + (b - a) * k / 4)
            QApplication.processEvents()
        QTest.mouseRelease(view, LEFT, pos=b)
        QApplication.processEvents()
        self.trail.clicks += 1
        self.trail.note(f"drag: {what}")

    def type_into(self, field_: Any, text: str, what: str) -> None:
        field_.setText(text)
        self.trail.typed += 1
        self.trail.note(f"type: {what}")

    # ---- the dialogs ----------------------------------------------------------------------
    def dialog(self, dlg: QDialog) -> int:
        """The program's own window: shown, looked at, filled in and answered with its button."""
        self.trail.dialogs += 1
        title = dlg.windowTitle() or type(dlg).__name__
        self.trail.note(f"dialog: {title}")
        dlg.show()
        for _ in range(5):
            QApplication.processEvents()
        self.trail.findings += [f"{title}: {f}" for f in audit(dlg)]
        name = type(dlg).__name__
        if name == "NewProjectDialog":
            dlg.ask_folder = self.folder_chooser
            self.click(dlg.browse, "Browse...")
            self.type_into(dlg.name, "Demo", "project name")
        elif name == "QuickDeviceDialog":
            self.type_into(dlg.name, next(self.names), "device name")
        else:
            raise AssertionError(f"a dialog the path did not have before: {name}")
        QApplication.processEvents()
        self.click(dlg.ok, f"{dlg.ok.text()} ({title})")
        return int(dlg.result())

    def folder_chooser(self, title: str) -> str:
        self.trail.dialogs += 1
        self.trail.note(f"dialog: folder chooser ({title})")
        return str(self.folder)

    def save_chooser(self, title: str, suggested: str, filters: str) -> str:
        self.trail.dialogs += 1
        self.trail.note(f"dialog: file chooser ({title})")
        self.trail.clicks += 1
        self.trail.note("click: Save in the file chooser")
        return str(self.target)

    def _stray(self, hook: str):
        def asked(*args: object) -> None:
            self.trail.stray.append(f"{hook}{args!r}")

        return asked


@pytest.fixture
def no_other_dialogs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Every way a window can open that does not go through the hooks of the main window is
    recorded, and refused (a test must never wait on a window nobody answers)."""
    seen: list[str] = []

    def refuse(name: str):
        def opened(*args: object, **kwargs: object) -> int:
            seen.append(name)
            return int(QDialog.DialogCode.Rejected)

        return opened

    for cls, names in (
        (QDialog, ("exec", "open")),
        (QMessageBox, ("exec",)),
        (QFileDialog, ("exec",)),
        (QInputDialog, ("exec",)),
    ):
        for n in names:
            monkeypatch.setattr(cls, n, refuse(f"{cls.__name__}.{n}"))
    for cls, names in (
        (QFileDialog, ("getExistingDirectory", "getSaveFileName", "getOpenFileName")),
        (QInputDialog, ("getText",)),
        (QMessageBox, ("question", "information", "warning", "critical")),
    ):
        for n in names:
            monkeypatch.setattr(cls, n, staticmethod(refuse(f"{cls.__name__}.{n}")))
    return seen


def centre(win: MainWindow, port) -> QPoint:
    """Where a port is on the screen of the view (the point a person would press on)."""
    inside = -4.0 if port.side == "right" else 4.0
    return win.view.mapFromScene(QPointF(port.x + inside, port.y))


def play(tmp_path: Path, other: list[str]) -> tuple[Trail, MainWindow, Path]:
    win = make_window(tmp_path)
    win.set_role("systems")
    win.act_quick.trigger()  # (the set-up before the four actions: a role and Quick mode)
    assert win.quick_on() and win.ctl.root is None
    folder, target = tmp_path / "project", tmp_path / "diagram" / "demo.svg"
    target.parent.mkdir()
    trail = Trail()
    me = Person(win, trail, folder, target)

    # 1. New project
    me.click(win.findChild(QAbstractButton, "rail-home"), "Home")
    me.click(win.findChild(QAbstractButton, "home-new"), "New project...")
    assert win.ctl.root == folder, str(trail)

    # 2. Add device, twice
    add = win.findChild(QAbstractButton, "tool-add-device")
    for _ in range(2):
        me.click(add, "Add device")
    assert len(win.ctl.project.units) == 2, str(trail)

    # 3. Connect: from a port of the first device to a port of the second
    win.view.fit()
    QApplication.processEvents()
    scene = win.view.dscene
    first, second = (scene.unit_items[u] for u in sorted(scene.unit_items))
    a = scene.cable.ports_of(first)[0]
    b = scene.cable.ports_of(second)[0]
    me.drag(centre(win, a), centre(win, b), "Connect, port to port")
    assert len(win.ctl.project.links) == 1, str(trail)

    # 4. Export diagram
    me.click(win.findChild(QAbstractButton, "topbar-export-diagram"), "Export diagram")
    trail.stray += other
    return trail, win, target


def test_four_actions_cost_no_more_than_the_budget(qtbot, tmp_path, no_other_dialogs) -> None:
    trail, win, target = play(tmp_path, no_other_dialogs)
    qtbot.addWidget(win)
    budget = FOUR_ACTIONS_BUDGET
    # the four actions happened
    assert win.ctl.root is not None and len(win.ctl.project.units) == 2
    assert len(win.ctl.project.links) == 1
    assert [target.with_suffix(s).is_file() for s in (".svg", ".pdf", ".png")] == [True] * 3
    # nothing asked outside the hooks, and the windows it opened have room for their content
    assert trail.stray == [], f"windows nobody planned for: {trail.stray}\n{trail}"
    assert trail.findings == [], "\n".join(trail.findings)
    # the budget
    assert trail.clicks <= budget.clicks, f"more clicks than the budget {budget}\n{trail}"
    assert trail.dialogs <= budget.dialogs, f"more dialogs than the budget {budget}\n{trail}"


def test_the_counter_notices_a_dialog_that_the_path_did_not_have(
    qtbot, tmp_path, no_other_dialogs
) -> None:
    """The count is only worth something if it can go up: a window opened outside the hooks is
    recorded."""
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    QMessageBox.question(win, "t", "x")
    box = QMessageBox(win)
    box.exec()
    assert no_other_dialogs == ["QMessageBox.question", "QMessageBox.exec"]
