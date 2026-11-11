# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""A word-wrapped label that tells its container how high it needs to be at its width.

A `QLabel` with word wrap knows its height only for a given width (`heightForWidth`). Box layouts
ask for it, but a splitter, a stacked widget and a scroll area do not: they use the label's
*minimum size hint*, which Qt takes at the narrowest width (one word per line) or as one line, so
the pane can be made shorter than the text needs and the text is cut off or lies over what is
below it. `WrapLabel` answers the minimum size hint for the width it has now, so every container
(and the window's own smallest size) counts all of its lines.

    hint = WrapLabel("A long sentence ...")

Three more helpers for text in a narrow panel: `breakable` lets a long name such as
`derating.connector_temperature_margin_c` break at its dots and underscores (a word-wrapped label
is otherwise at least as wide as its longest word, and so is the panel around it),
`WrapButton` is a push button whose text wraps instead of setting the panel's width, and
`FlowRow` is a row of buttons that goes on in a second line when the panel is narrower than the
row.
"""

import re

from PySide6.QtCore import QPoint, QRect, QSize, Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QLabel,
    QLayout,
    QLayoutItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui.theme import ThemeManager

LONG_WORD = 20  # characters; a shorter word is never broken
_LONG = re.compile(rf"\S{{{LONG_WORD},}}")
_JOINT = re.compile(r"([._/\\])(?=\S)")
SOFT_BREAK = "\u200b"  # zero-width space: a place where a line may break, not drawn


def breakable(text: str) -> str:
    """`text` with a soft break after each dot, underscore and slash inside a word of 20 or more
    characters, so a wrapped label can break a long name. Shorter words and spaces are untouched."""
    return _LONG.sub(lambda m: _JOINT.sub(r"\1" + SOFT_BREAK, m.group(0)), text)


class WrapLabel(QLabel):
    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setWordWrap(True)
        self._lines_height = -1

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        hint = super().minimumSizeHint()
        if self.width() > 0 and self.hasHeightForWidth():
            return QSize(hint.width(), max(hint.height(), self.heightForWidth(self.width())))
        return hint

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        need = self.heightForWidth(self.width()) if self.hasHeightForWidth() else -1
        if need != self._lines_height:  # the number of lines changed: the containers must ask again
            self._lines_height = need
            self.updateGeometry()


class WrapButton(QPushButton):
    """A push button whose text wraps onto more lines when the button is narrow (a plain
    `QPushButton` is at least as wide as its text). `text()` gives the whole text; it is also the
    accessible name."""

    def __init__(self, text: str, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("wrap", True)  # the style sheet frees the height of the control
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.space(8), theme.space(4), theme.space(8), theme.space(4))
        lay.addWidget(self.label)
        self._text = ""
        self.setText(text)

    def text(self) -> str:
        return self._text

    def setText(self, text: str) -> None:  # noqa: N802
        self._text = text
        self.label.setText(text)
        self.setAccessibleName(text)

    def sizeHint(self) -> QSize:  # noqa: N802
        lay = self.layout()
        return lay.sizeHint() if lay is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        lay = self.layout()
        return lay.minimumSize() if lay is not None else super().minimumSizeHint()


class FlowRow(QLayout):
    """Widgets side by side, left to right, that go on in the next line when the room ends (a
    `QHBoxLayout` is at least as wide as all of them together). Its height follows its width."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []

    def addItem(self, item: QLayoutItem) -> None:  # noqa: N802
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int) -> QLayoutItem | None:  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self) -> Qt.Orientation:  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._place(QRect(0, 0, width, 0), move=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._place(rect, move=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        m = self.contentsMargins()
        width = sum(i.sizeHint().width() for i in self._shown()) + self._gap() * max(
            0, len(self._shown()) - 1
        )
        height = max((i.sizeHint().height() for i in self._shown()), default=0)
        return QSize(width + m.left() + m.right(), height + m.top() + m.bottom())

    def minimumSize(self) -> QSize:  # noqa: N802
        m = self.contentsMargins()
        size = QSize()
        for item in self._shown():
            size = size.expandedTo(item.minimumSize())
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _shown(self) -> list[QLayoutItem]:
        return [i for i in self._items if not i.isEmpty()]

    def _gap(self) -> int:
        if self.spacing() >= 0:
            return self.spacing()
        parent = self.parentWidget()
        if parent is None:
            return 0
        return parent.style().layoutSpacing(
            QSizePolicy.ControlType.PushButton,
            QSizePolicy.ControlType.PushButton,
            Qt.Orientation.Horizontal,
        )

    def _place(self, rect: QRect, *, move: bool) -> int:
        """Lay the items out in `rect` (or only measure) and return the height they take."""
        m = self.contentsMargins()
        area = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        gap = self._gap()
        x, y, line = area.x(), area.y(), 0
        for item in self._shown():
            hint = item.sizeHint().boundedTo(QSize(area.width(), 1 << 20))
            if x > area.x() and x + hint.width() > area.right() + 1:
                x, y, line = area.x(), y + line + gap, 0
            if move:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + gap
            line = max(line, hint.height())
        return y + line - rect.y() + m.bottom()
