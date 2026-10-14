"""Why panel (SC-8, CV-23): the reasons behind the selected object, as a list of "rule: sentence".

    panel = WhyPanel(ctl, theme)      # follows ctl.selection (unit or link)
    panel.show_object("wire", "W001-003")   # anything else: a harness, wire, connector or pin
    panel.why_text("connector", "W001-P1")  # first lines as text, for a tooltip anywhere

The reasons are the ones generation recorded (`core.why`, built on `core.generate.explain`); the
panel adds nothing of its own. Below them it says what is still *pending* for the object and
which placeholder configuration the result rests on, with the same chips as everywhere else.
The first lines show at once and "Show all" opens the rest.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from harness_design_studio.core import why
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.panels import clear_layout, heading, muted, scroll_body
from harness_design_studio.gui.states import StateChip
from harness_design_studio.gui.theme import ThemeManager, mark_mono

FIRST_LINES = 5  # reasons shown before "Show all"
SELECTION_KINDS = ("unit", "interface")  # what the controller's selection can hold


class WhyPanel(QScrollArea):
    """The Why tab of the right dock. It follows the controller's selection; `show_object` points
    it at an object the canvas cannot select (harness, wire, connector, pin)."""

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl, self.theme = ctl, theme
        self.setObjectName("why-panel")
        self.setAccessibleName(strings.WHY_NAME)
        self.lay = scroll_body(self)
        self._target: tuple[str, str] | None = None
        self._expanded = False
        self._signature: object = None
        self._dirty = True
        self.rows: list[QLabel] = []  # the reason labels now shown
        self.show_all_button: QPushButton | None = None
        ctl.selectionChanged.connect(self._follow_selection)
        ctl.changed.connect(lambda _d: self._invalidate())
        ctl.stateChanged.connect(self._invalidate)
        theme.changed.connect(self._invalidate)
        self._follow_selection()

    # ---- public ------------------------------------------------------------------------------

    def why_text(self, kind: str, object_id: str, limit: int = 3) -> str:
        """The first `limit` reasons of an object ("rule: sentence" per line, then how many
        more) followed by what is pending; "" when nothing is known. For tooltips."""
        return why.why_text(self.ctl.project, kind, object_id, limit)

    def show_object(self, kind: str, object_id: str) -> None:
        """Show the reasons of an object of `core.why.KINDS`."""
        target = (kind, object_id)
        if target != self._target:
            self._expanded = False
        self._target = target
        self.refresh()

    def clear(self) -> None:
        self._target = None
        self.refresh()

    def shown(self) -> tuple[str, str] | None:
        """(kind, id) of the object the panel is about, or None."""
        return self._target

    def reason_lines(self) -> list[str]:
        """The "rule: sentence" lines now on screen."""
        return [r.accessibleName() for r in self.rows]

    # ---- following the controller ------------------------------------------------------------

    def _follow_selection(self) -> None:
        s = self.ctl.selection
        target = (s.kind, s.id) if s is not None and s.kind in why.KINDS else None
        if target != self._target:
            self._expanded = False
        self._target = target
        self.refresh()

    def _invalidate(self) -> None:
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    # ---- drawing -----------------------------------------------------------------------------

    def _content(self) -> tuple[list[why.Reason], list[str], list[str]]:
        if self._target is None:
            return [], [], []
        project = self.ctl.project
        kind, oid = self._target
        return (
            why.reasons(project, kind, oid),
            why.pending_reasons(project, kind, oid),
            why.placeholders_used(project, kind, oid),
        )

    def refresh(self) -> None:
        self._dirty = False
        reasons, pending, placeholders = self._content()
        signature = (
            self._target,
            self._expanded,
            tuple(r.line for r in reasons),
            tuple(pending),
            tuple(placeholders),
        )
        if signature == self._signature:
            return
        self._signature = signature
        clear_layout(self.lay)
        self.rows = []
        self.show_all_button = None
        if self._target is None:
            self.lay.addWidget(heading(strings.WHY_NAME))
            self.lay.addWidget(muted(strings.WHY_EMPTY))
            self.lay.addStretch(1)
            return
        kind, oid = self._target
        self.lay.addWidget(heading(strings.WHY_TITLE.format(strings.WHY_KIND.get(kind, kind), oid)))
        if not reasons and not pending:
            self.lay.addWidget(muted(strings.WHY_NONE))
        else:
            self.lay.addWidget(muted(strings.WHY_INTRO))
        shown = reasons if self._expanded else reasons[:FIRST_LINES]
        for r in shown:
            self.lay.addWidget(self._row(r))
        if len(reasons) > FIRST_LINES:
            self.show_all_button = QPushButton(
                strings.WHY_SHOW_FEWER
                if self._expanded
                else strings.WHY_SHOW_ALL.format(len(reasons))
            )
            self.show_all_button.setObjectName("why-show-all")
            self.show_all_button.setToolTip(strings.WHY_SHOW_ALL_TIP)
            self.show_all_button.setAccessibleName(
                strings.WHY_SHOW_FEWER
                if self._expanded
                else strings.WHY_SHOW_ALL.format(len(reasons))
            )
            self.show_all_button.clicked.connect(self._toggle)
            self.lay.addWidget(self.show_all_button)
        if pending:
            self.lay.addWidget(self._chipped("pending", strings.WHY_PENDING, pending))
        if placeholders:
            self.lay.addWidget(
                self._chipped(
                    "pending",
                    strings.WHY_PLACEHOLDER,
                    [strings.WHY_PLACEHOLDER_NOTE.format(", ".join(placeholders))],
                )
            )
        self.lay.addStretch(1)

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        self.refresh()
        if self.show_all_button is not None:
            self.show_all_button.setFocus()

    def _row(self, reason: why.Reason) -> QWidget:
        box = QFrame()
        box.setProperty("card", True)
        box.setProperty("severity", "info")
        lay = QVBoxLayout(box)
        lay.setSpacing(self.theme.space(4))
        head = QLabel(f"{reason.where}: {reason.rule}" if reason.where else reason.rule)
        head.setProperty("muted", True)
        head.setObjectName("why-rule")
        mark_mono(head)
        head.setAccessibleName(strings.WHY_RULE_NAME.format(reason.rule))
        text = QLabel(reason.text)
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        text.setObjectName("why-reason")
        text.setAccessibleName(reason.line)
        if reason.rule:
            lay.addWidget(head)
        lay.addWidget(text)
        self.rows.append(text)
        return box

    def _chipped(self, state: str, word: str, lines: list[str]) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, self.theme.space(8), 0, 0)
        lay.setSpacing(self.theme.space(4))
        chip = StateChip(self.theme, state, word if word != strings.STATE_LABELS[state] else None)
        lay.addWidget(chip, 0, Qt.AlignmentFlag.AlignLeft)
        for line in lines:
            lab = muted(line)
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lay.addWidget(lab)
        return box
