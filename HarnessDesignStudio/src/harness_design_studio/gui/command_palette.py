"""The command palette (Ctrl+K): a non-modal overlay with a search box and a list of every enabled
action of the window, each with its shortcut, plus adding units, connecting and going to an object.

    palette = CommandPalette(window, entries)     # entries: `MainWindow.palette_entries()`
    palette.open()

It is a child widget of the window, centred over it, not a dialog: the window stays usable under it.
Up and Down move in the list, Enter runs the command, Esc closes it, and so does a click anywhere else
or any other move of the keyboard focus out of it. The list ranks labels that start with what was
typed first and is never cut off: it scrolls (SH-11).
"""

import contextlib
from collections.abc import Callable
from dataclasses import dataclass

import shiboken6
from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import current_theme

PALETTE_W = 560  # the overlay's size at 100 %; it keeps a margin when the window is smaller
PALETTE_H = 380


@dataclass
class PaletteEntry:
    label: str
    run: Callable[[], None]
    hint: str = ""


def rank_entries(entries: list[PaletteEntry], text: str) -> list[PaletteEntry]:
    """The entries whose label holds every word of `text`, best first: a label that starts with
    the text, then a label with a word that starts with it, then the rest in their own order.
    There is no cap: the list scrolls."""
    words = text.lower().split()
    if not words:
        return list(entries)
    whole = text.lower().strip()
    ranked: list[tuple[int, int, PaletteEntry]] = []
    for position, e in enumerate(entries):
        label = e.label.lower()
        if not all(w in label for w in words):
            continue
        if label.startswith(whole):
            rank = 0
        elif any(part.startswith(words[0]) for part in label.replace("(", " ").split()):
            rank = 1
        else:
            rank = 2
        ranked.append((rank, position, e))
    ranked.sort(key=lambda r: (r[0], r[1]))
    return [e for _r, _p, e in ranked]


class CommandPalette(QFrame):
    """Ctrl+K: every enabled action and every unit/interface ID in one searchable list, as a
    non-modal overlay centred over the window (SH-11).

        palette = CommandPalette(window, entries)
        palette.open()          # shows it, the keyboard in the search box

    It is a child of the window, not a dialog: the window stays usable under it. Up and Down (also
    Page Up and Page Down) move in the list, Enter runs the chosen command, Esc closes it, and so does
    a click anywhere else, or any other move of the keyboard focus out of it. The list is never cut:
    it scrolls. `closed()` is emitted whenever it goes away."""

    closed = Signal()

    def __init__(self, parent: QWidget, entries: list[PaletteEntry]) -> None:
        super().__init__(parent)
        self.entries = entries
        self._before: QWidget | None = None  # where the keyboard was, to give it back on Esc
        self.setObjectName("command-palette")
        self.setProperty("card", True)
        self.setAccessibleName(strings.COMMANDS_TITLE)
        self.setAccessibleDescription(strings.COMMANDS_HELP)
        gap = current_theme().space(8)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(gap, gap, gap, gap)
        lay.setSpacing(gap)
        self.input = QLineEdit()
        self.input.setObjectName("palette-input")
        self.input.setPlaceholderText(strings.COMMANDS_PLACEHOLDER)
        self.input.setAccessibleName(strings.COMMANDS_PLACEHOLDER)
        self.input.setClearButtonEnabled(True)
        self.list = QListWidget()
        self.list.setObjectName("palette-list")
        self.list.setAccessibleName(strings.COMMANDS_LIST)
        self.list.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # the arrow keys work from the search box
        self.keys = QLabel(strings.COMMANDS_KEYS)
        self.keys.setObjectName("palette-keys")
        self.keys.setProperty("muted", True)
        lay.addWidget(self.input)
        lay.addWidget(self.list, 1)
        lay.addWidget(self.keys)
        self.input.textChanged.connect(self._filter)
        self.input.installEventFilter(self)
        self.list.itemActivated.connect(lambda _i: self._run_current())
        self.list.itemClicked.connect(lambda _i: self._run_current())
        self._filter("")
        self.hide()

    # ---- showing and closing -------------------------------------------------------------------
    def open(self) -> None:
        """Show the palette in the middle of the window, empty search, the keyboard in the box."""
        self._before = QApplication.focusWidget()
        self.input.clear()
        self.reposition()
        self.show()
        self.raise_()
        self.input.setFocus()
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.focusChanged.connect(self._focus_changed)
            app.installEventFilter(self)  # a click on something that takes no focus closes it too

    def reposition(self) -> None:
        """Centre it over the window; it keeps a margin when the window is small."""
        host = self.parentWidget()
        if host is None:
            return
        theme = current_theme()
        margin = theme.space(32)
        width = max(theme.px(280), min(theme.px(PALETTE_W), host.width() - 2 * margin))
        height = max(theme.px(200), min(theme.px(PALETTE_H), host.height() - 2 * margin))
        self.resize(width, height)
        self.move((host.width() - width) // 2, (host.height() - height) // 2)

    def dismiss(self, *, give_back_focus: bool = True) -> None:
        """Close it without running anything."""
        app = QApplication.instance()
        if isinstance(app, QApplication):
            with contextlib.suppress(RuntimeError, TypeError):
                app.focusChanged.disconnect(self._focus_changed)
            app.removeEventFilter(self)
        was_open = self.isVisible()
        self.hide()
        before, self._before = self._before, None
        if give_back_focus and before is not None and shiboken6.isValid(before):
            before.setFocus()
        if was_open:
            self.closed.emit()

    def _focus_changed(self, _old: QWidget | None, new: QWidget | None) -> None:
        """Any move of the keyboard out of the palette (a click elsewhere, Tab to another panel,
        another window) closes it."""
        if self.isVisible() and (new is None or not (new is self or self.isAncestorOf(new))):
            self.dismiss(give_back_focus=False)

    # ---- the list --------------------------------------------------------------------------------
    def _filter(self, text: str) -> None:
        self.list.clear()
        shown = rank_entries(self.entries, text)
        for e in shown:
            item = QListWidgetItem(f"{e.label}    {e.hint}".rstrip())
            item.setData(Qt.ItemDataRole.UserRole, e)
            self.list.addItem(item)
        if shown:
            self.list.setCurrentRow(0)
        else:
            none = QListWidgetItem(strings.PALETTE_NO_MATCH)
            none.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(none)

    def shown_labels(self) -> list[str]:
        """The labels listed now, best match first (for tests and screen readers)."""
        out = []
        for i in range(self.list.count()):
            entry = self.list.item(i).data(Qt.ItemDataRole.UserRole)
            if entry is not None:
                out.append(entry.label)
        return out

    def _run_current(self) -> None:
        item = self.list.currentItem()
        if item is None:
            return
        entry: PaletteEntry | None = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        self.dismiss(give_back_focus=False)  # closed first: the command may open a window
        entry.run()

    def _move(self, step: int) -> None:
        last = self.list.count() - 1
        if last >= 0:
            self.list.setCurrentRow(max(0, min(last, self.list.currentRow() + step)))

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and self.isVisible()
            and isinstance(event, QMouseEvent)
            and not self.rect().contains(self.mapFromGlobal(event.globalPosition().toPoint()))
        ):
            # a click outside the palette. (The same press is seen again as it passes up the
            # parents of the widget that was hit, so the place of the click decides, not `obj`.)
            self.dismiss(give_back_focus=False)  # the click itself goes on to what was clicked
            return False
        if (
            obj is self.input
            and event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
        ):
            key = event.key()
            page = max(1, self.list.height() // max(1, self.list.sizeHintForRow(0)))
            steps: dict[int, int] = {
                Qt.Key.Key_Down.value: 1,
                Qt.Key.Key_Up.value: -1,
                Qt.Key.Key_PageDown.value: page,
                Qt.Key.Key_PageUp.value: -page,
            }
            if key in steps:
                self._move(steps[key])
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self._run_current()
                return True
            if key == Qt.Key.Key_Escape:
                self.dismiss()
                return True
        return super().eventFilter(obj, event)
