# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The keyboard way to a loose cable end (M4c): one small window that asks which end and which port.

    dlg = CableEndDialog(parent, theme, strings.LE_LEAVE_TITLE, strings.LE_LEAVE_INTRO,
                         strings.LE_LEAVE_OK, ports=[("OBC J01 (OBC-J01)", "OBC-J01"), ...])
    if run(dlg) == Accepted: dlg.port(), dlg.end()

The diagram does the same with the mouse (a cable dragged from a port and let go on empty ground,
a loose end dragged onto a port). The window behind *Edit > Cable ends* opens this for *Leave a
loose end…* (a port), *Plug loose end into…* (an end, unless one is picked, and a port) and
*Unplug a cable end…* (an end). It only chooses: the controller makes the change, as one undo step,
and says why when it is refused. A list that is empty says so, and OK stays off.
"""

from PySide6.QtWidgets import QComboBox, QFormLayout, QLabel, QVBoxLayout, QWidget

from harness_design_studio.gui import strings
from harness_design_studio.gui.dialog_base import Dialog
from harness_design_studio.gui.dialogs import _buttons
from harness_design_studio.gui.theme import ThemeManager

Choices = list[tuple[str, str]]  # (what the list shows, the ID)


class CableEndDialog(Dialog):
    """Choose a cable end (`ends`), a port (`ports`), or both; a list given as None is not asked."""

    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeManager,
        title: str,
        intro: str,
        ok_text: str,
        *,
        ends: Choices | None = None,
        ports: Choices | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cable-end-dialog")
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        lay = QVBoxLayout(self)
        text = QLabel(intro)
        text.setWordWrap(True)
        lay.addWidget(text)
        form = QFormLayout()
        self.end_box = self._combo("cable-end-choice", strings.LE_END, strings.LE_END_TIP, ends)
        self.port_box = self._combo(
            "cable-port-choice", strings.LE_PORT, strings.LE_PORT_TIP, ports
        )
        if ends is not None:
            form.addRow(strings.LE_END, self.end_box)
        if ports is not None:
            form.addRow(strings.LE_PORT, self.port_box)
        lay.addLayout(form)
        empty = (ends is not None and not ends) or (ports is not None and not ports)
        self.note = QLabel(
            strings.LE_NO_ENDS if ends is not None and not ends else strings.LE_NO_PORTS
        )
        self.note.setObjectName("cable-end-note")
        self.note.setWordWrap(True)
        self.note.setProperty("muted", True)
        self.note.setVisible(empty)
        lay.addWidget(self.note)
        self.ok, self.cancel, row = _buttons(self, ok_text)
        self.ok.setEnabled(not empty)
        lay.addLayout(row)
        self.setMinimumWidth(theme.px(420))
        (self.end_box if ends else self.port_box).setFocus()

    @staticmethod
    def _combo(name: str, label: str, tip: str, choices: Choices | None) -> QComboBox:
        box = QComboBox()
        box.setObjectName(name)
        box.setAccessibleName(label)
        box.setToolTip(tip)
        for text, ident in choices or []:
            box.addItem(text, ident)
        box.setVisible(choices is not None)
        return box

    def end(self) -> str:
        """The cable end chosen ("" when none was asked or the list is empty)."""
        return str(self.end_box.currentData() or "")

    def port(self) -> str:
        """The port chosen ("" when none was asked or the list is empty)."""
        return str(self.port_box.currentData() or "")


__all__ = ["CableEndDialog"]
