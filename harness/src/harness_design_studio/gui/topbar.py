"""The top bar: which project, which design, what state it is in, and the three things to do next.

    bar = TopBar(theme)
    bar.generateClicked.connect(window.generate_flow)
    bar.checkClicked.connect(window.check_flow)
    bar.exportClicked.connect(window.export_dialog_flow)
    bar.apply(ShellStatus(name="Flatsat", model_hash="1a2b3c4d", dirty=True, generation="stale", ...))

Left to right: the project name, the short model hash in the monospace font, a dirty marker (a dot
and the words "Unsaved changes"), **Generate** (the one primary button of the window), Check,
Export and a status chip. The chip says, with an icon and words, whether the harness plans and the
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
    if s.generation == "none":
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
    return "pass", strings.CHIP_PLANS_CURRENT, strings.CHIP_PLANS_CURRENT_TIP


class TopBar(QWidget):
    """See the module text."""

    generateClicked = Signal()
    checkClicked = Signal()
    exportClicked = Signal()

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
        self.hash_label = QLabel()
        self.hash_label.setObjectName("topbar-hash")
        self.hash_label.setAccessibleName(strings.STATUS_HASH)
        mark_mono(self.hash_label)
        self.hash_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.dirty_label = QLabel()
        self.dirty_label.setObjectName("topbar-dirty")
        lay.addWidget(self.name_label)
        lay.addWidget(self.hash_label)
        lay.addWidget(self.dirty_label)
        lay.addStretch(1)

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
        self.export_btn = QPushButton()
        self.export_btn.setObjectName("topbar-export")
        icons.icon_button(
            self.export_btn, "export", theme, strings.TB_EXPORT_TIP, "Ctrl+E", text=strings.TB_EXPORT
        )  # fmt: skip
        self.export_btn.setAccessibleName(strings.A_EXPORT.rstrip("…"))
        self.chip = StateChip(theme)
        self.chip.setObjectName("topbar-chip")
        self.chip.setAccessibleName(strings.TB_CHIP_NAME)
        for w in (self.generate_btn, self.check_btn, self.export_btn):
            lay.addWidget(w)
        lay.addWidget(self.chip)
        self.generate_btn.clicked.connect(lambda _c=False: self.generateClicked.emit())
        self.check_btn.clicked.connect(lambda _c=False: self.checkClicked.emit())
        self.export_btn.clicked.connect(lambda _c=False: self.exportClicked.emit())
        # keyboard: Tab goes name -> Generate -> Check -> Export (the labels are not focusable)
        QWidget.setTabOrder(self.generate_btn, self.check_btn)
        QWidget.setTabOrder(self.check_btn, self.export_btn)
        self.apply(self.status)

    # ---- showing a status ----
    def apply(self, s: ShellStatus) -> None:
        self.status = s
        self.name_label.setText(s.name or strings.TB_UNSAVED_PROJECT)
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
        self._fit()

    # ---- fitting a narrow window ----
    def minimumSizeHint(self) -> QSize:  # noqa: N802
        """Small and constant: when the bar is narrow it folds parts away (`_fit`) instead of
        asking the window to grow."""
        return QSize(self.theme.px(480), self.lay.minimumSize().height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._fit()

    def _set_level(self, level: int) -> None:
        """0: everything. 1: the dirty marker is a dot. 2: the hash goes too. 3: Check and Export
        keep their icon and lose their word (the tooltip and the accessible name stay)."""
        s = self.status
        self._level = level
        if level >= 1:
            self.dirty_label.setText("●" if s.dirty else "")
            self.dirty_label.setVisible(s.dirty)
        else:
            self.dirty_label.setText(f"●  {strings.TB_DIRTY}" if s.dirty else strings.TB_CLEAN)
            self.dirty_label.setVisible(True)
        self.hash_label.setVisible(level < 2)
        for button, word in ((self.check_btn, strings.TB_CHECK), (self.export_btn, strings.TB_EXPORT)):  # fmt: skip
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

    def update_status(self, **changes: object) -> None:
        """Change some fields of the current status and show the result."""
        self.apply(replace(self.status, **changes))  # type: ignore[arg-type]

    def chip_text(self) -> str:
        return self.chip.text() or ""
