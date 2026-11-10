# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The Next step area, a page of its own: what to do now, in plain words, with one button.

    page = NextStepPage(theme, actions={"add_device": window.add_device_flow, ...,
                                        "show_everything": window.show_everything})
    page.show_next(next_step(facts))

One big card (the step, one sentence, the one primary button), the six steps below it, each with an
icon and a word for its state (never colour alone), and a small link-style button that switches the
role to Electrical engineer, and one that opens the library (both for the Systems engineer
role, whose rail has neither Home nor the detail areas). Below the steps a disclosure, closed until
it is opened, *What this step uses and makes* (S9): the project files and outputs the step uses and
makes, what can be looked at, and the state of all the steps of the workflow, from `core/workflow.py`
(the window gives `set_workflow_provider` the function that works the report out, and it is called
only while the disclosure is open). A quiet line says how many engineering values are still to set,
with a button, in every role (the status bar's own link is off for the Systems engineer role). It only
shows and calls back: `actions` maps the key of a `Next` (and `new_harness`, `show_everything`,
`library`, `values`, `asbuilt`) to a flow of the window. The logic is in `gui/next_step.py`.
"""

from collections.abc import Callable, Mapping

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import workflow as core_workflow
from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.next_step import Next, StepLine
from harness_design_studio.gui.pages import _card, _page
from harness_design_studio.gui.roles import AIT, SYSTEMS
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

        # the first problem: what to do, and Waive or Approve where they apply
        self.problem_card = QFrame()
        self.problem_card.setObjectName("next-problem")
        self.problem_card.setProperty("card", True)
        self.problem_card.setAccessibleName(strings.NEXT_PROBLEM_NAME)
        play = QVBoxLayout(self.problem_card)
        play.setContentsMargins(theme.space(16), theme.space(16), theme.space(16), theme.space(16))
        play.setSpacing(theme.space(8))
        self.problem_head = QLabel()
        self.problem_head.setObjectName("next-problem-head")
        self.problem_head.setProperty("muted", True)
        self.problem_title = QLabel()
        self.problem_title.setObjectName("next-problem-title")
        self.problem_title.setWordWrap(True)
        self.problem_todo = QLabel()
        self.problem_todo.setObjectName("next-problem-todo")
        self.problem_todo.setWordWrap(True)
        self.problem_more = QLabel()
        self.problem_more.setObjectName("next-problem-more")
        self.problem_more.setProperty("muted", True)
        prow = QHBoxLayout()
        self.problem_show = self._problem_button(
            "next-problem-show",
            strings.NEXT_PROBLEM_SHOW,
            strings.NEXT_PROBLEM_SHOW_TIP,
            "problem_show",
        )
        self.problem_waive = self._problem_button(
            "next-problem-waive",
            strings.NEXT_PROBLEM_WAIVE,
            strings.NEXT_PROBLEM_WAIVE_TIP,
            "problem_waive",
        )
        self.problem_approve = self._problem_button(
            "next-problem-approve",
            strings.NEXT_PROBLEM_APPROVE_PLAIN,
            strings.NEXT_PROBLEM_APPROVE_TIP,
            "problem_approve",
        )
        for button in (self.problem_show, self.problem_waive, self.problem_approve):
            prow.addWidget(button)
        prow.addStretch(1)
        for label in (self.problem_head, self.problem_title, self.problem_todo, self.problem_more):
            play.addWidget(label)
        play.addLayout(prow)
        column.addWidget(self.problem_card)
        self.problem_card.hide()

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

        # a quiet line, only while engineering values are still to set; the status bar's link to
        # them is off for the Systems engineer role, so the page that role starts on carries it
        self.pending = QFrame()
        self.pending.setObjectName("next-pending-values")
        self.pending.setAccessibleName(strings.NEXT_PENDING_NAME)
        prow = QHBoxLayout(self.pending)
        prow.setContentsMargins(0, 0, 0, 0)
        self.pending_text = QLabel()
        self.pending_text.setObjectName("next-pending-text")
        self.pending_text.setProperty("muted", True)
        self.pending_text.setWordWrap(True)
        self.pending_button = QPushButton(strings.NEXT_PENDING_BUTTON)
        self.pending_button.setObjectName("next-pending-button")
        self.pending_button.setProperty("ghost", True)
        self.pending_button.setToolTip(strings.NEXT_PENDING_TIP)
        self.pending_button.setAccessibleName(strings.NEXT_PENDING_BUTTON.rstrip("…"))
        self.pending_button.clicked.connect(lambda _c=False: self._call("values"))
        prow.addWidget(self.pending_text, 1)
        prow.addWidget(self.pending_button)
        self.pending.hide()
        column.addWidget(self.pending)

        # what this step uses and makes: closed until opened, worked out only while open (S9)
        self._provider: Callable[[], core_workflow.WorkflowReport] | None = None
        self._wf_step = ""
        self.wf_toggle = QToolButton()
        self.wf_toggle.setObjectName("next-wf-toggle")
        self.wf_toggle.setText(strings.NEXT_WF_TOGGLE)
        self.wf_toggle.setCheckable(True)
        self.wf_toggle.setChecked(False)
        self.wf_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self.wf_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.wf_toggle.setAccessibleName(strings.NEXT_WF_TOGGLE)
        self.wf_toggle.toggled.connect(self._wf_toggled)
        self.wf_body = QFrame()
        self.wf_body.setObjectName("next-wf-body")
        self.wf_body.setProperty("card", True)
        self.wf_body.setAccessibleName(strings.NEXT_WF_NAME)
        wlay = QVBoxLayout(self.wf_body)
        wlay.setContentsMargins(theme.space(16), theme.space(12), theme.space(16), theme.space(12))
        wlay.setSpacing(theme.space(8))
        self.wf_labels: dict[str, QLabel] = {}
        for key in ("step", "uses", "makes", "look", "all"):
            label = QLabel()
            label.setObjectName(f"next-wf-{key}")
            label.setWordWrap(True)
            if key in ("uses", "makes", "look", "all"):
                label.setProperty("muted", True)
            if key == "step":
                label.setProperty("heading", True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.wf_labels[key] = label
            wlay.addWidget(label)
        self.wf_body.hide()
        column.addWidget(self.wf_toggle, 0, Qt.AlignmentFlag.AlignLeft)
        column.addWidget(self.wf_body)

        # a quiet line, only while a file that was imported has changed since (D-193)
        self.imports_note = QLabel()
        self.imports_note.setObjectName("next-imports-changed")
        self.imports_note.setAccessibleName(strings.NEXT_IMPORTS_NAME)
        self.imports_note.setProperty("muted", True)
        self.imports_note.setWordWrap(True)
        self.imports_note.hide()
        column.addWidget(self.imports_note)

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
        # the way to the as-built records for the AIT role
        self.asbuilt = QPushButton(strings.NEXT_ASBUILT)
        self.asbuilt.setObjectName("next-asbuilt")
        self.asbuilt.setProperty("ghost", True)
        self.asbuilt.setAccessibleName(strings.NEXT_ASBUILT.rstrip("…"))
        self.asbuilt.setToolTip(strings.NEXT_ASBUILT_TIP)
        self.asbuilt.clicked.connect(lambda _c=False: self._call("asbuilt"))
        self.asbuilt.hide()
        column.addWidget(self.asbuilt, 0, Qt.AlignmentFlag.AlignLeft)
        column.addStretch(1)
        self.show_next_placeholder()

    def _problem_button(self, name: str, text: str, tip: str, key: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName(name)
        b.setAccessibleName(text.rstrip("…"))
        b.setToolTip(tip)
        b.clicked.connect(lambda _c=False: self._call(key))
        return b

    def _show_problem(self, n: Next) -> None:
        p = n.problem
        self.problem_card.setVisible(p is not None)
        if p is None:
            return
        self.problem_head.setText(strings.NEXT_PROBLEM_HEAD.get(p.severity, strings.NEXT_PROBLEM_HEAD["error"]))  # fmt: skip
        self.problem_title.setText(p.title)
        self.problem_todo.setText(strings.NEXT_PROBLEM_TODO.format(p.todo))
        self.problem_more.setText(strings.NEXT_PROBLEM_MORE[0 if p.more == 1 else 1].format(p.more) if p.more else "")  # fmt: skip
        self.problem_more.setVisible(bool(p.more))
        self.problem_waive.setVisible(p.can_waive)
        self.problem_approve.setVisible(bool(p.approve))
        if p.approve:
            text = strings.NEXT_PROBLEM_APPROVE.format(p.approve)
            self.problem_approve.setText(text)
            self.problem_approve.setAccessibleName(text.rstrip("…"))

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
        self.problem_card.hide()

    def show_import_note(self, text: str) -> None:
        """The line about imported files that changed ("" hides it)."""
        if text != self.imports_note.text():
            self.imports_note.setText(text)
        self.imports_note.setVisible(bool(text))

    def set_role(self, role: str) -> None:
        """The library and Show everything links are for the Systems engineer role, the as-built
        button for the AIT role."""
        self.links.setVisible(role == SYSTEMS)
        self.asbuilt.setVisible(role == AIT)

    def show_pending_values(self, count: int) -> None:
        """The line about engineering values still to set (0 hides it)."""
        self.pending.setVisible(count > 0)
        if count > 0:
            self.pending_text.setText(strings.NEXT_PENDING_VALUES[0 if count == 1 else 1].format(count))  # fmt: skip

    # ---- what this step uses and makes ----------------------------------------------------------
    def set_workflow_provider(self, provider: Callable[[], core_workflow.WorkflowReport]) -> None:
        """The function that works the workflow report out (called only while the disclosure is
        open)."""
        self._provider = provider

    def workflow_open(self) -> bool:
        return self.wf_toggle.isChecked()

    def _wf_toggled(self, on: bool) -> None:
        self.wf_toggle.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        self.wf_body.setVisible(on)
        if on:
            self.refresh_workflow()

    def refresh_workflow(self) -> None:
        """Fill the disclosure from the report (nothing is worked out while it is closed)."""
        if not self.wf_toggle.isChecked() or self._provider is None:
            return
        report = self._provider()
        current = core_workflow.NEXT_KEY_STEP.get(self._key, "")
        pairs = {d.key: (d, s) for d, s in report.steps}
        focus = pairs.get(current) or next(iter(pairs.values()), None)
        if focus is not None:
            d, _s = focus
            self.wf_labels["step"].setText(strings.NEXT_WF_STEP.format(d.title))
            self.wf_labels["uses"].setText(strings.NEXT_WF_USES.format("; ".join(i.name for i in d.consumes)))  # fmt: skip
            self.wf_labels["makes"].setText(strings.NEXT_WF_MAKES.format("; ".join(i.name for i in d.produces)))  # fmt: skip
            look = "; ".join(f"{i.what} ({i.how})" for i in d.inspect)
            self.wf_labels["look"].setText(strings.NEXT_WF_LOOK.format(look) if look else "")
            self.wf_labels["look"].setVisible(bool(look))
        lines = [strings.NEXT_WF_ALL]
        for d, s in report.steps:
            line = strings.NEXT_WF_LINE.format(d.title, strings.NEXT_WF_STATES[s.state], s.detail)
            if s.blocked_by:
                titles = ", ".join(core_workflow.step(k).title for k in s.blocked_by)
                line += " " + strings.NEXT_WF_BLOCKED_BY.format(titles)
            lines.append(line)
        self.wf_labels["all"].setText("\n".join(lines))

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
        self._show_problem(n)
        for row, line in zip(self.rows, n.steps, strict=True):
            row.show_line(line)
