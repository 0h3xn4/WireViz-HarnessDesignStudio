# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""The docks inside the real window: the tree on the left, the inspector on the right with the
properties and problems panels. They must pass the accessible-name audit and stay in step."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.samples import sat15_full  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402


@pytest.fixture
def wired(qtbot, tmp_path: Path):
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    p = sat15_full()
    generate_project(p)
    win.ctl._install(p, None, None)
    tree, insp = win.project_tree, win.inspector  # the window plugs them in itself
    win.dock_left.show()
    win.dock_right.show()
    tree.selectionRequested.connect(insp.show_object)
    QApplication.processEvents()
    return win, tree, insp


def test_the_new_docks_pass_the_accessible_name_audit(wired) -> None:
    win, tree, insp = wired
    win.ctl.select("interface", sorted(win.ctl.project.interfaces)[0])
    for tab in ("inspector", "why", "problems"):
        insp.show_tab(tab)
        QApplication.processEvents()
        assert unnamed(win) == [], tab
    for kind, oid in (
        ("harness", sorted(win.ctl.project.harnesses)[0]),
        ("config", "derating"),
        ("part", sorted(win.ctl.project.parts)[0]),
    ):
        tree.selectionRequested.emit(kind, oid)
        insp.show_tab("inspector")
        assert unnamed(win) == [], kind


def test_the_tree_and_the_canvas_stay_in_step(wired) -> None:
    win, tree, _ = wired
    iid = sorted(win.ctl.project.interfaces)[3]
    tree.select("interface", iid)
    tree.selectionRequested.emit("interface", iid)
    assert win.ctl.selection is not None  # the inspector asked the controller
    win.ctl.select("unit", sorted(win.ctl.project.units)[0])
    assert tree.current() == ("unit", sorted(win.ctl.project.units)[0])


def test_the_tree_is_reachable_with_the_keyboard(wired) -> None:
    win, tree, _ = wired
    focusable = [
        w
        for w in win.findChildren(QWidget)
        if w.isVisibleTo(win) and w.focusPolicy() & Qt.FocusPolicy.TabFocus
    ]
    assert tree.view in focusable and tree.filter_edit in focusable


def test_problems_panel_still_lives_in_the_window_and_the_inspector(wired) -> None:
    win, _, insp = wired
    assert insp.problems_panel() is win.problems
    insp.show_tab("problems")
    QApplication.processEvents()
    assert win.problems.isVisible()
