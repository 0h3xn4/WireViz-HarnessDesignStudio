"""First-run tour: a card beside each highlighted area. Skippable and replayable."""

from collections.abc import Callable

import shiboken6
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager


class _Highlight(QWidget):
    def __init__(self, parent: QWidget, theme: ThemeManager) -> None:
        super().__init__(parent)
        self.theme = theme
        self.target = QRect()
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def paintEvent(self, _event: object) -> None:
        if self.target.isNull():
            return
        p = QPainter(self)
        p.setPen(QPen(self.theme.color("primary"), 4))
        p.drawRoundedRect(self.target.adjusted(-3, -3, 3, 3), 6, 6)


class Tour:
    def __init__(
        self,
        window: QWidget,
        theme: ThemeManager,
        targets: dict[str, QWidget],
        reveals: dict[str, Callable[[], None]] | None = None,
    ) -> None:
        self.window, self.theme, self.targets = window, theme, targets
        self.reveals = reveals or {}  # what to bring to the front before a step points at it
        self.index = -1
        self.on_stop: Callable[[], None] | None = None
        self.highlight = _Highlight(window, theme)
        self.card = QFrame(window)
        self.card.setObjectName("tour-card")
        self.card.setProperty("card", True)
        self.card.setFrameShape(QFrame.Shape.StyledPanel)
        lay = QVBoxLayout(self.card)
        self.title = QLabel("")
        self.title.setObjectName("tour-title")
        self.text = QLabel("")
        self.text.setWordWrap(True)
        self.text.setMinimumWidth(280)
        self.text.setMaximumWidth(320)
        lay.addWidget(self.title)
        lay.addWidget(self.text)
        row = QHBoxLayout()
        self.skip = QPushButton(strings.TOUR_SKIP)
        self.skip.setObjectName("tour-skip")
        self.back = QPushButton(strings.TOUR_BACK)
        self.back.setObjectName("tour-back")
        self.next = QPushButton(strings.TOUR_NEXT)
        self.next.setObjectName("tour-next")
        self.next.setProperty("primary", True)
        row.addWidget(self.skip)
        row.addStretch(1)
        row.addWidget(self.back)
        row.addWidget(self.next)
        lay.addLayout(row)
        self.skip.clicked.connect(self.stop)
        self.back.clicked.connect(lambda: self.show_step(self.index - 1))
        self.next.clicked.connect(lambda: self.show_step(self.index + 1))
        self.card.hide()

    @property
    def active(self) -> bool:
        return self.index >= 0

    def start(self) -> None:
        # (the first-run timer can fire after the window was closed or deleted)
        if not shiboken6.isValid(self.window) or not self.window.isVisible():
            return
        self.show_step(0)

    def _shown_steps(self) -> list[int]:
        """The steps whose target is on screen now (a high UI scale or a small window hides docks)."""
        out = []
        for k, (key, _text) in enumerate(strings.TOUR_STEPS):
            target = self.targets[key]
            if target.isVisibleTo(self.window) and not target.size().isEmpty():
                out.append(k)
        return out

    def stop(self) -> None:
        was_active = self.index >= 0
        self.index = -1
        self.card.hide()
        self.highlight.hide()
        if was_active and self.on_stop is not None:
            self.on_stop()  # skipping or finishing both count: the tour is not shown again

    def show_step(self, i: int) -> None:
        steps = strings.TOUR_STEPS
        if i < 0:
            return
        shown = self._shown_steps()
        forward = i >= self.index
        if i < len(steps) and i not in shown:  # skip a step that would point at nothing
            later = [k for k in shown if (k > i if forward else k < i)]
            if not later and not forward:
                return  # nothing earlier to go back to
            i = (later[0] if forward else later[-1]) if later else len(steps)
        if i >= len(steps):
            self.stop()
            return
        self.index = i
        key, text = steps[i]
        if key in self.reveals:
            self.reveals[key]()
        target = self.targets[key]
        self.title.setText(f"<b>{strings.TOUR_STEP.format(shown.index(i) + 1, len(shown))}</b>")
        self.text.setText(text)
        self.back.setEnabled(i > shown[0])
        self.next.setText(strings.TOUR_FINISH if i == shown[-1] else strings.TOUR_NEXT)
        self.highlight.setGeometry(self.window.rect())
        top_left = target.mapTo(self.window, target.rect().topLeft())
        rect = QRect(top_left, target.size())
        self.highlight.target = rect
        self.highlight.show()
        self.highlight.raise_()
        self.card.adjustSize()
        self.card.move(self._place(rect))
        self.card.show()
        self.card.raise_()
        self.next.setFocus()

    def _place(self, r: QRect):  # type: ignore[no-untyped-def]
        from PySide6.QtCore import QPoint

        w, h = self.card.width(), self.card.height()
        win = self.window.rect()
        if r.right() + 12 + w < win.right():
            return QPoint(r.right() + 12, max(8, min(win.bottom() - h - 8, r.top() + 8)))
        if r.bottom() + 12 + h < win.bottom():
            return QPoint(max(8, min(win.right() - w - 8, r.right() - w)), r.bottom() + 12)
        if r.top() - 12 - h > 0:
            return QPoint(max(8, r.left() + 16), r.top() - h - 12)
        return QPoint(r.center().x() - w // 2, r.center().y() - h // 2)
