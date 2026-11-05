"""A word-wrapped label that tells its container how high it needs to be at its width.

A `QLabel` with word wrap knows its height only for a given width (`heightForWidth`). Box layouts
ask for it, but a splitter, a stacked widget and a scroll area do not: they use the label's
*minimum size hint*, which Qt takes at the narrowest width (one word per line) or as one line, so
the pane can be made shorter than the text needs and the text is cut off or lies over what is
below it. `WrapLabel` answers the minimum size hint for the width it has now, so every container
(and the window's own smallest size) counts all of its lines.

    hint = WrapLabel("A long sentence ...")
"""

from PySide6.QtCore import QSize
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QLabel, QWidget


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
