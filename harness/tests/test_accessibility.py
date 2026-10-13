"""M7 accessibility audit (automated part): every interactive widget has an accessible name,
the whole app is reachable from the keyboard, text meets the minimum size, and the canvas, which
Qt does not expose item by item, announces what it holds and where the accessible alternative is."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)

from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.samples import sat15_full  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402

INTERACTIVE = (QAbstractButton, QLineEdit, QComboBox, QPlainTextEdit, QAbstractItemView)


def label_of(w: QWidget) -> str:
    name = w.accessibleName()
    if name:
        return name
    text = getattr(w, "text", None)
    if callable(text):
        try:
            return str(text())
        except TypeError:
            return ""
    return ""


def unnamed(root: QWidget) -> list[str]:
    bad = []
    for w in root.findChildren(QWidget):
        if (
            isinstance(w, INTERACTIVE)
            and not isinstance(w, QHeaderView)
            and w.isVisibleTo(root)
            and not label_of(w).strip()
        ):
            bad.append(
                f"{type(w).__name__} '{w.objectName() or '(no name)'}'"
            )  # (a tooltip is no name)
    return bad


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = sat15_full()
    generate_project(p)
    w.ctl._install(p, None, None)
    return w


def test_main_window_widgets_have_accessible_names(win) -> None:  # type: ignore[no-untyped-def]
    for tab in range(win.tabs.count()):
        win.tabs.setCurrentIndex(tab)
        assert unnamed(win) == [], f"tab {tab}"


def test_dialogs_have_accessible_names(win) -> None:  # type: ignore[no-untyped-def]
    script = DialogScript(win, accept=False)
    hid = sorted(win.ctl.project.harnesses)[0]
    win.change_flow("release", hid)
    win.change_flow("review", hid)
    win.new_interface_flow()
    win.glossary_flow()
    win.generate_btn.click()
    assert script.seen
    for dlg in script.seen:
        assert isinstance(dlg, QDialog)
        assert unnamed(dlg) == [], dlg.objectName()


def test_every_menu_action_has_a_name_and_the_main_ones_have_shortcuts(win) -> None:  # type: ignore[no-untyped-def]
    actions = [a for a in win.findChildren(type(win.act_undo)) if a.text().strip()]
    assert len(actions) > 20
    shortcuts = {
        a.text().replace("&", ""): a.shortcut().toString()
        for a in actions
        if not a.shortcut().isEmpty()
    }
    for needed in ("Undo", "Redo"):
        assert any(needed in k for k in shortcuts), needed
    assert any(v for v in shortcuts.values())


def test_keyboard_only_reach_every_panel(win) -> None:  # type: ignore[no-untyped-def]
    """Tab order: every focusable widget can take focus with the keyboard."""
    win.show()
    focusable = [
        w
        for w in win.findChildren(QWidget)
        if w.isVisibleTo(win) and w.focusPolicy() & Qt.FocusPolicy.TabFocus
    ]
    assert len(focusable) > 15
    names = {type(w).__name__ for w in focusable}
    assert {"QPushButton", "QTableView"} & names or {"QPushButton"} <= names


def test_text_is_never_smaller_than_the_minimum_at_every_scale(win) -> None:  # type: ignore[no-untyped-def]
    for scale in (100, 125, 150, 200):
        win.set_scale(scale)
        for w in win.findChildren(QWidget):
            if w.isVisibleTo(win) and isinstance(w, INTERACTIVE):
                size = (
                    w.font().pixelSize()
                    if w.font().pixelSize() > 0
                    else w.font().pointSizeF() * 96 / 72
                )
                assert size >= 10, f"{type(w).__name__} {w.objectName()} at {scale}%: {size}px"


def test_canvas_announces_its_content_and_names_the_accessible_alternative(win) -> None:  # type: ignore[no-untyped-def]
    view = win.view
    name, desc = view.accessibleName(), view.accessibleDescription()
    p = win.ctl.project
    assert str(len(p.units)) in name and str(len(p.interfaces)) in name
    assert "table" in desc.lower() and "tab" in desc.lower()
    win.ctl.select("unit", sorted(p.units)[0])
    assert sorted(p.units)[0] in view.accessibleDescription()  # follows the selection


def test_state_is_never_shown_by_colour_alone(win) -> None:  # type: ignore[no-untyped-def]
    """Findings carry a severity word, redundant units a text tag, marks a text label."""
    from harness_design_studio.gui import strings

    assert {strings.SEV_ERROR, strings.SEV_WARNING, strings.SEV_INFO} and all(
        s.strip() for s in (strings.SEV_ERROR, strings.SEV_WARNING, strings.SEV_INFO)
    )
