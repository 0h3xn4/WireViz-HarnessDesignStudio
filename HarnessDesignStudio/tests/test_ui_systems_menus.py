# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-18. Release 1.9 W1: the Systems engineer role does not list the engineering entries of
the menus; they stay in the command palette (Ctrl+K) and keep their shortcuts."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenu  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.gui import areas  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402


def listed(win) -> set[str]:
    """The object names of the entries a person sees in the menus (submenus included)."""
    out: set[str] = set()

    def walk(menu: QMenu) -> None:
        for a in menu.actions():
            if a.menu() is not None:
                if a.isVisible():
                    walk(a.menu())
            elif a.isVisible() and not a.isSeparator() and a.objectName():
                out.add(a.objectName())

    for top in win.menuBar().actions():
        walk(top.menu())
    return out


def test_the_systems_role_hides_the_engineering_entries_and_the_other_role_lists_all(
    qtbot, tmp_path: Path
) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    everything = listed(win)
    hidden = {n for n in areas.SYSTEMS_HIDDEN_ACTIONS if not n.startswith("menu:")}
    assert hidden <= everything, hidden - everything  # (the names are real actions)
    win.set_role("systems")
    QApplication.processEvents()
    lean = listed(win)
    assert not (hidden & lean)
    assert len(lean) < len(everything) - 20
    # what a Systems engineer works with stays
    for name in ("act-add-device", "act-link-connectors", "act-generate", "act-check", "act-export",
                 "act-save", "act-open", "act-library", "act-undo", "act-guide", "act-commands"):  # fmt: skip
        assert name in lean, name
    win.set_role("electrical")
    QApplication.processEvents()
    assert listed(win) == everything


def test_the_connect_with_a_type_and_align_menus_are_hidden_too(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.set_role("systems")
    edit_menu = (
        win.menu_add.parent()
        if False
        else next(t.menu() for t in win.menuBar().actions() if t.menu().title().endswith("Edit"))
    )
    shown = [a.menu() for a in edit_menu.actions() if a.menu() is not None]
    assert win.menu_connect not in shown and not set(win._role_menus.values()) & set(shown)
    assert win.menu_add in shown and win.menu_connection in shown
    win.set_role("electrical")
    shown = [a.menu() for a in edit_menu.actions() if a.menu() is not None]
    assert win.menu_connect in shown and set(win._role_menus.values()) <= set(shown)
    # (and back in their old places)
    assert [a.menu().title() for a in edit_menu.actions() if a.menu()][:3] == [
        "Align",
        "Space evenly",
        "Add device",
    ]


def test_every_hidden_entry_stays_in_the_command_palette(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    before = {e.label for e in win.palette_entries()}
    win.set_role("systems")
    after = {e.label for e in win.palette_entries()}
    assert before <= after and after - before == {
        "Show side panels"
    }  # (that one is the role's own)
    by_name = {a.objectName(): a for a in win.findChildren(QAction)}
    for name in areas.SYSTEMS_HIDDEN_ACTIONS:
        if name.startswith("menu:") or not by_name[name].isEnabled():
            continue  # (a disabled entry, such as Duplicate with nothing selected, is not listed)
        label = by_name[name].text().replace("&", "")
        assert label in after, f"{name}: {label}"


def test_a_hidden_entry_still_runs_from_the_palette_and_keeps_its_shortcut(
    qtbot, tmp_path: Path
) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.set_role("systems")
    act = next(a for a in win.findChildren(QAction) if a.objectName() == "act-new-harness")
    assert act.isEnabled() and act.shortcut().toString() == "Ctrl+Shift+H"
    assert act.objectName() not in listed(win)
    entry = next(e for e in win.palette_entries() if e.label == act.text().replace("&", ""))
    asked = []
    win.ask_text = lambda *a: asked.append(a)  # (the entry opens the question for the name)
    entry.run()
    assert asked


def test_the_choice_follows_the_role_not_the_project(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.set_role("systems")
    win.set_role("systems")  # (twice: nothing is hidden twice or lost)
    win.set_role("electrical")
    win.set_role("systems")
    assert not {n for n in areas.SYSTEMS_HIDDEN_ACTIONS if n.startswith("act-")} & listed(win)
