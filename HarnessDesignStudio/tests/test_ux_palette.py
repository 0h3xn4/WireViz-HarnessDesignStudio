# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SH-11: Ctrl+K opens the command palette as a non-modal overlay centred over the window: a search
box and a list, arrow keys and Enter, Esc closes, a move of the focus or a click elsewhere closes it;
it lists every enabled action with its shortcut, ranks by prefix and has no result cap."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.command_palette import (  # noqa: E402
    CommandPalette,
    PaletteEntry,
    rank_entries,
)
from tests.gui_helpers import DialogScript, make_window  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path: Path):
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.activateWindow()
    QApplication.processEvents()
    return w


def opened(win) -> CommandPalette:
    win.open_commands()
    QApplication.processEvents()
    palette = win.command_palette
    assert palette is not None and palette.isVisible()
    assert isinstance(palette, CommandPalette)
    return palette


def test_ctrl_k_opens_an_overlay_not_a_dialog(win) -> None:
    script = DialogScript(win)  # any dialog the window ran would be recorded here
    assert win.act_commands.shortcut().toString() == "Ctrl+K"
    win.act_commands.trigger()
    palette = win.command_palette
    assert palette is not None and palette.isVisible()
    assert not isinstance(palette, QDialog) and palette.parentWidget() is win
    assert not palette.isModal() if hasattr(palette, "isModal") else True
    assert script.seen == []
    assert win.isEnabled()  # the window under it is not blocked
    win.ctl.select("unit", "OBC")  # and keeps working while the palette is open
    assert win.ctl.selection is not None and palette.isVisible()


def test_it_opens_in_the_middle_of_the_window_and_follows_a_resize(win) -> None:
    palette = opened(win)
    centre = palette.geometry().center()
    assert abs(centre.x() - win.width() // 2) <= 1 and abs(centre.y() - win.height() // 2) <= 1
    assert win.rect().contains(palette.geometry())
    win.resize(900, 600)
    QApplication.processEvents()
    centre = palette.geometry().center()
    assert abs(centre.x() - win.width() // 2) <= 1 and abs(centre.y() - win.height() // 2) <= 1
    win.resize(420, 300)  # a small window: it keeps inside it
    QApplication.processEvents()
    assert win.rect().contains(palette.geometry())


def test_the_search_box_has_the_keyboard_and_starts_empty(win) -> None:
    palette = opened(win)
    assert QApplication.focusWidget() is palette.input and palette.input.text() == ""
    palette.input.setText("gene")
    palette.dismiss()
    again = opened(win)
    assert again.input.text() == "" and len(again.shown_labels()) > 14  # a fresh, full list


def test_arrow_keys_choose_and_enter_runs_then_the_palette_is_gone(win) -> None:
    ran: list[tuple[str, bool]] = []
    palette = CommandPalette(
        win,
        [
            PaletteEntry("Alpha", lambda: ran.append(("a", palette.isVisible()))),
            PaletteEntry("Beta", lambda: ran.append(("b", palette.isVisible()))),
            PaletteEntry("Gamma", lambda: ran.append(("g", palette.isVisible()))),
        ],
    )
    palette.open()
    assert palette.list.currentRow() == 0
    QTest.keyClick(palette.input, Qt.Key.Key_Down)
    QTest.keyClick(palette.input, Qt.Key.Key_Down)
    QTest.keyClick(palette.input, Qt.Key.Key_Down)  # stops at the last one
    assert palette.list.currentRow() == 2
    QTest.keyClick(palette.input, Qt.Key.Key_Up)
    QTest.keyClick(palette.input, Qt.Key.Key_Return)
    assert ran == [("b", False)]  # it was closed first: the command may open a window
    assert not palette.isVisible()


def test_page_keys_move_a_page_in_a_long_list(win) -> None:
    palette = opened(win)
    total = len(palette.shown_labels())
    assert total > 30
    QTest.keyClick(palette.input, Qt.Key.Key_PageDown)
    assert palette.list.currentRow() > 1
    QTest.keyClick(palette.input, Qt.Key.Key_PageUp)
    assert palette.list.currentRow() == 0


def test_escape_closes_it_and_the_keyboard_goes_back_where_it_was(win) -> None:
    win.view.setFocus()
    QApplication.processEvents()
    assert QApplication.focusWidget() is win.view
    palette = opened(win)
    QTest.keyClick(palette.input, Qt.Key.Key_Escape)
    QApplication.processEvents()
    assert not palette.isVisible()
    assert QApplication.focusWidget() is win.view


def test_ctrl_k_again_closes_it(win) -> None:
    palette = opened(win)
    win.act_commands.trigger()
    assert not palette.isVisible()


def test_it_closes_when_the_keyboard_goes_elsewhere(win) -> None:
    palette = opened(win)
    win.view.setFocus()  # focus loss: another widget takes the keyboard
    QApplication.processEvents()
    assert not palette.isVisible()


def test_a_click_elsewhere_closes_it_even_on_a_widget_that_takes_no_focus(win) -> None:
    palette = opened(win)
    assert not win.status_saved.focusPolicy() & Qt.FocusPolicy.ClickFocus
    QTest.mouseClick(win.status_saved, Qt.MouseButton.LeftButton, pos=QPoint(2, 2))
    QApplication.processEvents()
    assert not palette.isVisible()


def test_a_click_inside_the_palette_keeps_it_open(win) -> None:
    palette = opened(win)
    QTest.mouseClick(palette.keys, Qt.MouseButton.LeftButton)
    QApplication.processEvents()
    assert palette.isVisible()


def test_it_lists_every_enabled_action_with_its_shortcut_and_no_disabled_one(win) -> None:
    palette = opened(win)
    shown = {e.label: e.hint for e in palette.entries}
    enabled = [
        a
        for a in win.actions()
        if a.text() and a.isEnabled() and a.objectName().startswith(("act-", "menu-"))
    ]
    assert len(enabled) > 40
    for act in enabled:
        label = act.text().replace("&", "")
        assert label in shown, label
        assert shown[label] == act.shortcut().toString(), label
    disabled = [
        a.text().replace("&", "")
        for a in win.findChildren(QAction)
        if a.text() and not a.isEnabled() and a.objectName().startswith(("act-", "menu-"))
    ]
    assert disabled  # an empty project has no harness to review, for one
    assert not [d for d in disabled if d in shown and d not in {a.text() for a in enabled}]
    assert shown["Generate harnesses"] == "Ctrl+G" and shown["Export…"] == "Ctrl+E"
    row = palette.list.item(0).text()
    assert row.split("    ")[0] in shown  # the shortcut is on the row, after the label


def test_the_shortcut_is_shown_on_the_row(win) -> None:
    palette = opened(win)
    palette.input.setText("generate harnesses")
    first = palette.list.item(0).text()
    assert first.startswith("Generate harnesses") and first.endswith("Ctrl+G")


def test_it_ranks_a_label_that_starts_with_the_text_first_and_has_no_cap() -> None:
    entries = [PaletteEntry(f"Go to unit U{i}", lambda: None) for i in range(300)]
    entries.insert(10, PaletteEntry("Regenerate everything", lambda: None))
    entries.append(PaletteEntry("Generate harnesses", lambda: None))
    assert [e.label for e in rank_entries(entries, "gene")][:2] == [
        "Generate harnesses",
        "Regenerate everything",
    ]
    assert len(rank_entries(entries, "")) == 302  # nothing is cut off


def test_the_list_scrolls_instead_of_cutting_results(win) -> None:
    palette = opened(win)
    assert len(palette.shown_labels()) == len(palette.entries) > 14
    assert palette.list.verticalScrollBar().maximum() > 0


def test_it_is_named_for_screen_readers(win) -> None:
    palette = opened(win)
    assert palette.accessibleName() == strings.COMMANDS_TITLE
    assert palette.accessibleDescription() == strings.COMMANDS_HELP
    assert palette.input.accessibleName() and palette.list.accessibleName()
    assert unnamed(win) == []
    palette.input.setText("zzzzqq")
    assert palette.shown_labels() == []
    assert palette.list.item(0).text() == strings.PALETTE_NO_MATCH


def test_a_command_that_opens_a_dialog_finds_the_palette_gone(win) -> None:
    script = DialogScript(win, accept=False)
    palette = opened(win)
    palette.input.setText("new interface")
    QTest.keyClick(palette.input, Qt.Key.Key_Return)
    assert not palette.isVisible() and script.seen  # the form opened over a closed palette


def test_the_search_button_of_the_toolbar_opens_it(win) -> None:
    win.search_btn.click()
    assert win.command_palette is not None and win.command_palette.isVisible()
