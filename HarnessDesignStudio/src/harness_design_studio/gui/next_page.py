"""The Next step area, a page of its own: what to do now, in plain words, with one button.

    page = NextStepPage(theme, actions={"add_device": window.add_device_flow, ...,
                                        "show_everything": window.show_everything})
    page.show_next(next_step(facts))

One big card (the step, one sentence, the one primary button), the six steps below it, each with an
icon and a word for its state (never colour alone), and a small link-style button that switches the
role to Electrical / AIT engineer, and one that opens the library (both for the Systems engineer
role, whose rail has neither Home nor the detail areas). It only shows and calls back: `actions`
maps the key of a `Next` (and `new_harness`, `show_everything`, `library`) to a flow of the window.
The logic is in `gui/next_step.py`.
"""

from collections.abc import Callable, Mapping

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.next_step import Next, StepLine
from harness_design_studio.gui.pages import _card, _page
from harness_design_studio.gui.roles import SYSTEMS
from harness_design_studio.gui.theme import ThemeManager

ICON_PX = 16
# state -> (icon, colour token, the word)
_LOOK = {
    "done": ("pass", "success", strings.NEXT_STATE_DONE),
    "next": ("nav-next", "primary", strings.NEXT_STATE_NEXT),
    "todo": ("pending", "text-muted", strings.NEXT_STATE_TODO),
    "blocked": ("lock", "locked", strings.NEXT_STATE_BLOCKED),
}


class _StepRow(QWidget):
    """One step: an icon, the step, and the word for its state."""

    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self.theme = theme
        self.setObjectName("next-step")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, theme.space(4), 0, theme.space(4))
        lay.setSpacing(theme.space(8))
        self.icon_label = QLabel()
        self.icon_label.setObjectName("next-step-icon")
        self.icon_label.setFixedSize(theme.px(ICON_PX), theme.px(ICON_PX))
        self.label = QLabel()
        self.label.setObjectName("next-step-label")
        self.word = QLabel()
        self.word.setObjectName("next-step-state")
        self.word.setProperty("muted", True)
        lay.addWidget(self.icon_label)
        lay.addWidget(self.label, 1)
        lay.addWidget(self.word)
        self._state = ""
        theme.changed.connect(self._paint_icon)

    def show_line(self, line: StepLine) -> None:
        self._state = line.state
        _icon, _token, word = _LOOK[line.state]
        self.label.setText(line.label)
        self.word.setText(word)
        text = strings.NEXT_STEP_LINE.format(line.label, word)
        self.setAccessibleName(text)
        self.setToolTip(text)
        self._paint_icon()

    def _paint_icon(self) -> None:
        if not self._state:
            return
        name, token, _word = _LOOK[self._state]
        size = QSize(self.theme.px(ICON_PX), self.theme.px(ICON_PX))
        self.icon_label.setPixmap(icons.icon(name, self.theme, token).pixmap(size))


class NextStepPage(QScrollArea):
    def __init__(self, theme: ThemeManager, *, actions: Mapping[str, Callable[[], None]]) -> None:
        super().__init__()
        self.theme = theme
        self._actions = actions
        self._shown: Next | None = None
        self._key = ""
        self._alternative_key = ""
        page, column = _page(theme, "next-page", strings.NEXT_TITLE)
        self.setObjectName("next-page")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidget(page.takeWidget())
        self.setAccessibleName(strings.NEXT_TITLE)

        # the one thing to do now
        card = QFrame()
        card.setObjectName("next-card")
        card.setProperty("card", True)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(theme.space(24), theme.space(24), theme.space(24), theme.space(24))
        lay.setSpacing(theme.space(12))
        self.title = QLabel()
        self.title.setObjectName("next-title")
        self.title.setProperty("display", True)
        self.title.setWordWrap(True)
        self.why = QLabel()
        self.why.setObjectName("next-why")
        self.why.setWordWrap(True)
        self.note = QLabel()
        self.note.setObjectName("next-note")
        self.note.setProperty("muted", True)
        self.note.setWordWrap(True)
        self.button = QPushButton()
        self.button.setObjectName("next-button")
        self.button.setProperty("primary", True)
        self.button.setMinimumHeight(theme.control_height() * 3 // 2)
        self.button.clicked.connect(lambda _c=False: self._call(self._key))
        self.alternative_label = QLabel()
        self.alternative_label.setObjectName("next-alternative")
        self.alternative_label.setProperty("muted", True)
        self.alternative_button = QPushButton()
        self.alternative_button.setObjectName("next-alternative-button")
        self.alternative_button.clicked.connect(lambda _c=False: self._call(self._alternative_key))
        self.alternative_row = QWidget()
        alt = QHBoxLayout(self.alternative_row)
        alt.setContentsMargins(0, 0, 0, 0)
        alt.addWidget(self.alternative_label)
        alt.addWidget(self.alternative_button)
        alt.addStretch(1)
        row = QHBoxLayout()
        row.addWidget(self.button)
        row.addStretch(1)
        for w in (self.title, self.why, self.note):
            lay.addWidget(w)
        lay.addLayout(row)
        lay.addWidget(self.alternative_row)
        column.addWidget(card)

        # the six steps
        steps_card, steps_lay = _card(theme, strings.NEXT_STEPS_HEADING)
        steps_card.setObjectName("next-steps")
        steps_card.setAccessibleName(strings.NEXT_STEPS_NAME)
        self.rows: list[_StepRow] = []
        for _ in range(6):
            r = _StepRow(theme)
            steps_lay.addWidget(r)
            self.rows.append(r)
        column.addWidget(steps_card)

        # the library, and the way out to the Electrical / AIT engineer role (Systems engineer only)
        self.links = QWidget()
        links = QHBoxLayout(self.links)
        links.setContentsMargins(0, 0, 0, 0)
        self.library = QPushButton(strings.NEXT_LIBRARY)
        self.library.setObjectName("next-library")
        self.library.setProperty("ghost", True)
        self.library.setAccessibleName(strings.NEXT_LIBRARY)
        self.library.setToolTip(strings.NEXT_LIBRARY_TIP)
        self.library.clicked.connect(lambda _c=False: self._call("library"))
        self.everything = QPushButton(strings.NEXT_SHOW_EVERYTHING)
        self.everything.setObjectName("next-everything")
        self.everything.setProperty("ghost", True)
        self.everything.setAccessibleName(strings.NEXT_SHOW_EVERYTHING)
        self.everything.setToolTip(strings.NEXT_SHOW_EVERYTHING_TIP)
        self.everything.clicked.connect(lambda _c=False: self._call("show_everything"))
        links.addWidget(self.library)
        links.addWidget(self.everything)
        links.addStretch(1)
        column.addWidget(self.links, 0, Qt.AlignmentFlag.AlignLeft)
        column.addStretch(1)
        self.show_next_placeholder()

    def _call(self, key: str) -> None:
        action = self._actions.get(key)
        if action is not None:
            action()

    def show_next_placeholder(self) -> None:
        """Before the window gives the first result (an empty card is never shown)."""
        self.title.setText("")
        self.why.setText("")
        self.note.hide()
        self.button.hide()
        self.alternative_row.hide()

    def set_role(self, role: str) -> None:
        """The two links are for the Systems engineer role."""
        self.links.setVisible(role == SYSTEMS)

    def shown(self) -> Next | None:
        return self._shown

    def key(self) -> str:
        """The key of the result shown now ("" before the first one)."""
        return self._shown.key if self._shown is not None else ""

    def show_next(self, n: Next) -> None:
        """Show a result. The window calls this on every status refresh, so a result that did not
        change costs one comparison."""
        if n == self._shown:
            return
        self._shown = n
        self._key = n.key
        self.title.setText(n.title)
        self.why.setText(n.why)
        self.note.setText(n.note)
        self.note.setVisible(bool(n.note))
        self.button.setText(n.button)
        self.button.setVisible(bool(n.button))
        if n.button:
            self.button.setAccessibleName(n.button.rstrip("…"))
            self.button.setToolTip(strings.NEXT_BUTTON_TIPS.get(n.key, n.button))
        self._alternative_key = n.alternative_key
        self.alternative_label.setText(n.alternative)
        self.alternative_button.setText(n.alternative_button)
        self.alternative_row.setVisible(bool(n.alternative_key))
        if n.alternative_key:
            self.alternative_button.setAccessibleName(n.alternative_button.rstrip("…"))
            self.alternative_button.setToolTip(strings.NEXT_BUTTON_TIPS[n.alternative_key])
        for row, line in zip(self.rows, n.steps, strict=True):
            row.show_line(line)
