"""The job indicator of the status bar: what runs in the background, with progress and Cancel.

    jobs = JobStatus(theme)
    jobs.start("Checking", cancel=ctl.cancel_check)     # a busy bar and a Cancel button
    jobs.finish("Last check 12:03")                      # back to idle, with the last result

Generating, exporting, arranging and checking all show up here, so the person always sees that
something runs and can stop it. The bar is indeterminate: the jobs report no steady fraction
(the generate and export dialogs show theirs). The widget only shows; the window says when a job
starts and ends.
"""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QWidget

from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager


class JobStatus(QWidget):
    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("job-status")
        self.setAccessibleName(strings.JOB_NAME)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(theme.space(8), 0, theme.space(8), 0)
        lay.setSpacing(theme.space(8))
        self.label = QLabel(strings.JOB_IDLE)
        self.label.setObjectName("job-label")
        self.label.setProperty("muted", True)
        self.bar = QProgressBar()
        self.bar.setObjectName("job-progress")
        self.bar.setRange(0, 0)  # busy, no fraction
        self.bar.setTextVisible(False)
        self.bar.setFixedSize(theme.px(96), theme.px(6))
        self.bar.setAccessibleName(strings.JOB_NAME)
        self.cancel_btn = QPushButton(strings.JOB_CANCEL)
        self.cancel_btn.setObjectName("job-cancel")
        self.cancel_btn.setProperty("ghost", True)
        self.cancel_btn.setToolTip(strings.JOB_CANCEL_TIP)
        self.cancel_btn.setAccessibleName(strings.JOB_CANCEL_TIP)
        self.cancel_btn.clicked.connect(lambda _c=False: self._cancel())
        for w in (self.label, self.bar, self.cancel_btn):
            lay.addWidget(w)
        self._cancel_cb: Callable[[], None] | None = None
        self._last = ""
        self._show_idle()

    # ---- what the window says -----------------------------------------------------------------
    def start(self, text: str, *, cancel: Callable[[], None] | None = None) -> None:
        """A job runs: the bar moves, and Cancel is there when it can be cancelled."""
        self._cancel_cb = cancel
        self.label.setText(strings.JOB_RUNNING.format(text))
        self.label.setProperty("muted", False)
        self.bar.setVisible(True)
        self.cancel_btn.setVisible(cancel is not None)
        self._repolish()

    def finish(self, last: str | None = None) -> None:
        """The job ended; `last` (when given) is what to show as the last result."""
        if last is not None:
            self._last = last
        self._cancel_cb = None
        self._show_idle()

    def is_running(self) -> bool:
        return self.bar.isVisibleTo(self)

    def text(self) -> str:
        return self.label.text()

    # ---- inside -------------------------------------------------------------------------------
    def _show_idle(self) -> None:
        self.label.setText(self._last or strings.JOB_IDLE)
        self.label.setProperty("muted", True)
        self.bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self._repolish()

    def _cancel(self) -> None:
        if self._cancel_cb is not None:
            self._cancel_cb()

    def _repolish(self) -> None:
        self.label.style().unpolish(self.label)
        self.label.style().polish(self.label)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
