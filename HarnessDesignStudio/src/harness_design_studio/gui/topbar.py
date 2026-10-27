"""The top bar: which project, which design, what state it is in, and the three things to do next.

    bar = TopBar(theme)
    bar.generateClicked.connect(window.generate_flow)
    bar.checkClicked.connect(window.check_flow)
    bar.exportClicked.connect(window.export_dialog_flow)
    bar.apply(ShellStatus(name="Flatsat", model_hash="1a2b3c4d", dirty=True, generation="stale", ...))

Left to right: the project name, a save marker (a dot and the words "Unsaved changes", or "Saved"),
the revision, the short model hash in the monospace font, where you are (area › view), then the
edit buttons (Undo, Redo), the mode switch and the search field the window puts in with
`add_edit`, `add_mode` and `add_search`, **Generate** (the one primary button of the window),
Check, Export and a status chip. The chip says, with an icon and words, whether the harness plans and the
exported files match the diagram: up to date, plans out of date, outputs out of date, generating,
exporting or checking. `chip_for` is the pure rule behind it.

The bar only shows; it computes nothing. The window hands it a `ShellStatus` (hashes are cached by
model state there, because a hash of a big design takes a moment).
"""

from dataclasses import dataclass, replace

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QWidget

from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.icons import tooltip_text
from harness_design_studio.gui.shell import ElidedLabel
from harness_design_studio.gui.states import StateChip
from harness_design_studio.gui.theme import ThemeManager, mark_mono
from harness_design_studio.gui.workflow import WorkflowInputs, workflow


@dataclass(frozen=True)
class ShellStatus:
    """Everything the top bar and the banners show, gathered by the window."""

    name: str = ""
    model_hash: str = ""
    dirty: bool = False
    read_only: bool = False
    generation: str = "none"  # none | current | stale   (ctl.generation_status())
    outputs: str = "none"  # none | unsaved | current | stale | modified | unreadable
    running: str | None = None  # generate | export | arrange while a job runs
    checking: bool = False  # ctl.drc_busy()
    has_harnesses: bool = False
    generated_at: str = ""  # first 8 characters of the generation record's input hash
    revision: str = ""  # "A" or "A-C": the revisions of the project's harnesses
    checked: bool = False  # a rule check result is current
    failed: int = 0  # rules that failed
    unchecked: int = 0  # rules not checked or waiting for a value
    harnesses: int = 0
    in_review: int = 0
    released: int = 0
    units: int = 0  # devices in the project
    interfaces: int = 0  # connections in the project
    links: int = 0  # connections of two connectors (pin to pin)
    hand_made: int = 0  # harnesses a person made (generated=False)


_RUNNING = {
    "generate": strings.CHIP_GENERATING,
    "export": strings.CHIP_EXPORTING,
    "arrange": strings.CHIP_ARRANGING,
}


def chip_for(s: ShellStatus) -> tuple[str, str, str]:
    """(state key of `gui.states`, words, tooltip) for the status chip.

    A job that runs comes first; then anything out of date (the plans before the files, since the
    files can only be right after the plans are); then a running check; then up to date."""
    if s.running:
        return "info", _RUNNING.get(s.running, strings.CHIP_GENERATING), strings.CHIP_RUNNING_TIP
    if s.generation == "stale":
        return "stale", strings.CHIP_PLANS_STALE, strings.CHIP_PLANS_STALE_TIP
    by_hand = s.harnesses > 0 and s.hand_made == s.harnesses  # made from connections or by hand
    if s.generation == "none" and not by_hand:
        if s.checking:
            return "info", strings.CHIP_CHECKING, strings.CHIP_CHECKING_TIP
        return "draft", strings.CHIP_NOT_GENERATED, strings.CHIP_NOT_GENERATED_TIP
    if s.has_harnesses and s.outputs == "stale":
        return "stale", strings.CHIP_OUTPUTS_STALE, strings.CHIP_OUTPUTS_STALE_TIP
    if s.has_harnesses and s.outputs in ("modified", "unreadable"):
        return "stale", strings.CHIP_OUTPUTS_CHANGED, strings.CHIP_OUTPUTS_CHANGED_TIP
    if s.checking:
        return "info", strings.CHIP_CHECKING, strings.CHIP_CHECKING_TIP
    if s.has_harnesses and s.outputs == "current":
        return "pass", strings.CHIP_UP_TO_DATE, strings.CHIP_UP_TO_DATE_TIP
    if by_hand and s.generation == "none":
        return "pass", strings.CHIP_BY_HAND, strings.CHIP_BY_HAND_TIP
    return "pass", strings.CHIP_PLANS_CURRENT, strings.CHIP_PLANS_CURRENT_TIP


class TopBar(QWidget):
    """See the module text."""

    generateClicked = Signal()
    checkClicked = Signal()
    exportClicked = Signal()
    releaseClicked = Signal()

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.status = ShellStatus()
        self._level = 0  # how much has been folded away to fit (see `_fit`)
        self._fitting = False
        self.setObjectName("topbar")
        self.setAccessibleName(strings.TB_ACCESSIBLE)
        lay = QHBoxLayout(self)
        self.lay = lay
        lay.setSizeConstraint(QLayout.SizeConstraint.SetNoConstraint)  # the bar folds, see `_fit`
        lay.setContentsMargins(theme.space(8), theme.space(4), theme.space(8), theme.space(4))
        lay.setSpacing(theme.space(8))

        self.name_label = ElidedLabel()  # a long name is cut in the middle in a narrow window
        self.name_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        self.name_label.setObjectName("topbar-name")
        self.name_label.setAccessibleName(strings.TB_NAME)
        self.name_label.setProperty("title", True)
        self.name_label.setMaximumWidth(
            theme.px(260)
        )  # a long name is cut: the bar has more to say
        self.hash_label = QLabel()
        self.hash_label.setObjectName("topbar-hash")
        self.hash_label.setAccessibleName(strings.STATUS_HASH)
        mark_mono(self.hash_label)
        self.hash_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.dirty_label = QLabel()
        self.dirty_label.setObjectName("topbar-dirty")
        self.revision_label = QLabel()
        self.revision_label.setObjectName("topbar-revision")
        self.revision_label.setAccessibleName(strings.TB_REVISION_NAME)
        self.revision_label.setProperty("muted", True)
        self.crumbs = ElidedLabel()  # where you are: area, then view
        self.crumbs.setObjectName("topbar-crumbs")
        self.crumbs.setAccessibleName(strings.CRUMBS_NAME)
        self.crumbs.setProperty("muted", True)
        lay.addWidget(self.name_label)
        lay.addWidget(self.dirty_label)
        lay.addWidget(self.revision_label)
        lay.addWidget(self.hash_label)
        lay.addWidget(self.crumbs, 1)
        lay.addStretch(1)
        self._edit: list[QWidget] = []
        self._search: QWidget | None = None
        self._search_text = ""

        self.generate_btn = QPushButton()
        self.generate_btn.setObjectName("generate")
        self.generate_btn.setProperty("primary", True)
        icons.icon_button(
            self.generate_btn, "generate", theme, strings.GENERATE, "Ctrl+G",
            text=strings.TB_GENERATE, role="on-primary",
        )  # fmt: skip
        self.generate_btn.setToolTip(tooltip_text(strings.GENERATE_TIP, "Ctrl+G"))
        self.check_btn = QPushButton()
        self.check_btn.setObjectName("topbar-check")
        icons.icon_button(
            self.check_btn, "check", theme, strings.TB_CHECK_TIP, "F5", text=strings.TB_CHECK
        )
        self.check_btn.setAccessibleName(strings.TB_CHECK)
        self.release_btn = QPushButton()
        self.release_btn.setObjectName("topbar-release")
        icons.icon_button(
            self.release_btn, "release", theme, strings.TB_RELEASE_TIP, text=strings.TB_RELEASE
        )
        self.release_btn.setAccessibleName(strings.STEP_RELEASE)
        self.chevrons = [QLabel("›"), QLabel("›")]  # between the three steps
        for c in self.chevrons:
            c.setProperty("muted", True)
            c.setAccessibleName("")
        self.export_btn = QPushButton()
        self.export_btn.setObjectName("topbar-export")
        icons.icon_button(
            self.export_btn, "export", theme, strings.TB_EXPORT_TIP, "Ctrl+E", text=strings.TB_EXPORT
        )  # fmt: skip
        self.export_btn.setAccessibleName(strings.A_EXPORT.rstrip("…"))
        self.chip = StateChip(theme)
        self.chip.setObjectName("topbar-chip")
        self.chip.setAccessibleName(strings.TB_CHIP_NAME)
        for w in (
            self.generate_btn, self.chevrons[0], self.check_btn, self.chevrons[1],
            self.release_btn, self.export_btn,
        ):  # fmt: skip
            lay.addWidget(w)
        lay.addWidget(self.chip)
        self.steps_buttons = (self.generate_btn, self.check_btn, self.release_btn)
        self.generate_btn.clicked.connect(lambda _c=False: self.generateClicked.emit())
        self.check_btn.clicked.connect(lambda _c=False: self.checkClicked.emit())
        self.export_btn.clicked.connect(lambda _c=False: self.exportClicked.emit())
        self.release_btn.clicked.connect(lambda _c=False: self.releaseClicked.emit())
        # keyboard: Tab goes name -> Generate -> Check -> Release -> Export (the labels are not focusable)
        QWidget.setTabOrder(self.generate_btn, self.check_btn)
        QWidget.setTabOrder(self.check_btn, self.release_btn)
        QWidget.setTabOrder(self.release_btn, self.export_btn)
        self.apply(self.status)

    # ---- what the window puts into the bar ----
    def _insert(self, widget: QWidget) -> None:
        self.lay.insertWidget(self.lay.indexOf(self.generate_btn), widget)

    def add_edit(self, widget: QWidget) -> None:
        """Undo and Redo go here, left of the mode switch."""
        self._insert(widget)
        self._edit.append(widget)

    def add_mode(self, widget: QWidget) -> None:
        self._insert(widget)

    def add_search(self, widget: QWidget) -> None:
        """The search field (it opens the command palette); it keeps its word until level 3."""
        self._insert(widget)
        self._search = widget

    def set_crumbs(self, text: str) -> None:
        self.crumbs.set_full_text(text)

    # ---- showing a status ----
    def apply(self, s: ShellStatus) -> None:
        self.status = s
        self.name_label.setText(s.name or strings.TB_UNSAVED_PROJECT)
        self.revision_label.setText(strings.TB_REVISION.format(s.revision) if s.revision else "")
        self.revision_label.setToolTip(
            strings.TB_REVISION_TIP.format(s.revision) if s.revision else ""
        )
        self.hash_label.setText(s.model_hash)
        self.hash_label.setToolTip(strings.TB_HASH_TIP.format(s.model_hash))
        self.dirty_label.setAccessibleName(strings.TB_DIRTY if s.dirty else strings.TB_CLEAN)
        self.dirty_label.setToolTip(strings.TB_DIRTY_TIP if s.dirty else strings.TB_CLEAN_TIP)
        self.dirty_label.setProperty("dirty", s.dirty)
        self.dirty_label.setProperty("muted", not s.dirty)
        self.dirty_label.style().unpolish(self.dirty_label)
        self.dirty_label.style().polish(self.dirty_label)
        state, text, tip = chip_for(s)
        self.chip.set_state(state, text)
        self.chip.setToolTip(tip)
        self.chip.setAccessibleName(f"{strings.TB_CHIP_NAME}: {text}")
        busy = s.running is not None
        self.generate_btn.setEnabled(not s.read_only and not busy)
        if s.read_only:
            self.generate_btn.setToolTip(strings.TB_GENERATE_READ_ONLY)
        else:
            self.generate_btn.setToolTip(tooltip_text(strings.GENERATE_TIP, "Ctrl+G"))
        self.check_btn.setEnabled(not busy)
        self.export_btn.setEnabled(not busy)
        self.release_btn.setEnabled(not busy and not s.read_only and s.harnesses > 0)
        self._show_steps(s)
        self._fit()

    def steps(self) -> tuple[object, object, object]:
        """The three workflow steps for the status shown now (see `gui/workflow.py`)."""
        s = self.status
        return workflow(
            WorkflowInputs(
                generation=s.generation, running=s.running, checking=s.checking, checked=s.checked,
                failed=s.failed, unchecked=s.unchecked, harnesses=s.harnesses,
                in_review=s.in_review, released=s.released, read_only=s.read_only,
            )
        )  # fmt: skip

    def _show_steps(self, s: ShellStatus) -> None:
        """Each step button carries its state (colour of its edge, the property `step`) and says
        what it means in its tooltip, after what the button does and its key; the words say it too,
        never the colour alone."""
        base = {
            self.generate_btn: (
                strings.TB_GENERATE_READ_ONLY
                if s.read_only
                else tooltip_text(strings.GENERATE_TIP, "Ctrl+G")
            ),
            self.check_btn: tooltip_text(strings.TB_CHECK_TIP, "F5"),
            self.release_btn: strings.TB_RELEASE_TIP,
        }
        for button, step in zip(self.steps_buttons, self.steps(), strict=True):
            button.setProperty("step", step.state)  # type: ignore[attr-defined]
            button.setToolTip(f"{base[button]}\n{step.tooltip}")  # type: ignore[attr-defined]
            button.setAccessibleDescription(step.detail)  # type: ignore[attr-defined]
            button.style().unpolish(button)
            button.style().polish(button)

    # ---- fitting a narrow window ----
    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Small and constant: when the bar is narrow it folds parts away (`_fit`) instead of
        asking the window to grow."""
        return QSize(self.theme.px(480), self.lay.minimumSize().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit()

    def _set_level(self, level: int) -> None:
        """0: everything. 1: the dirty marker is a dot and the breadcrumbs go. 2: the hash and the
        revision go too. 3: Check, Export and the search field keep their icon and lose their word
        (the tooltip and the accessible name stay)."""
        s = self.status
        self._level = level
        self.crumbs.setVisible(level < 1 and bool(self.crumbs.full_text()))
        if level >= 1:
            self.dirty_label.setText("●" if s.dirty else "")
            self.dirty_label.setVisible(s.dirty)
        else:
            self.dirty_label.setText(f"●  {strings.TB_DIRTY}" if s.dirty else strings.TB_CLEAN)
            self.dirty_label.setVisible(True)
        self.hash_label.setVisible(level < 2)
        self.revision_label.setVisible(level < 2 and bool(s.revision))
        search = self._search
        if isinstance(search, QPushButton):
            if search.text():
                self._search_text = search.text()
            search.setText("" if level >= 3 else self._search_text)
            search.setProperty("iconOnly", level >= 3)
            search.style().unpolish(search)
            search.style().polish(search)
        for c in self.chevrons:
            c.setVisible(level < 3)
        for button, word in (
            (self.check_btn, strings.TB_CHECK),
            (self.release_btn, strings.TB_RELEASE),
            (self.export_btn, strings.TB_EXPORT),
        ):  # fmt: skip
            button.setText("" if level >= 3 else word)
            button.setProperty("iconOnly", level >= 3)
            button.style().unpolish(button)
            button.style().polish(button)

    def level(self) -> int:
        return self._level

    def _fit(self) -> None:
        if self._fitting:
            return
        self._fitting = True
        try:
            for level in range(4):
                self._set_level(level)
                self.lay.activate()
                # the name may shrink to 160 px (it is cut in the middle) before anything else folds
                give = max(0, self.name_label.sizeHint().width() - self.theme.px(160))
                if self.lay.sizeHint().width() - give <= self.width():
                    break
        finally:
            self._fitting = False

    def set_notices(self, on: bool) -> None:
        """Show or hide the status chip (View > Show problem notices). The workflow buttons and
        their states stay: they are the steps the person takes, not a notice."""
        self.chip.setVisible(on)

    def update_status(self, **changes: object) -> None:
        """Change some fields of the current status and show the result."""
        self.apply(replace(self.status, **changes))  # type: ignore[arg-type]

    def chip_text(self) -> str:
        return self.chip.text() or ""
