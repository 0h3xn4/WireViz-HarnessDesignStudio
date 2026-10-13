"""An inline message inside a dialog or view: icon, words, details and an optional action button.

It replaces the pop-up for anything that is not a question: a failed check, a project that has no
folder yet, a copy that went wrong. It stays until it is dismissed or the next attempt succeeds, so
it is never missed the way a toast that fades is. The kind is always in the icon and in the words
as well as the colour (`error`, `warning`, `info`).

    notice = InlineNotice(theme)
    notice.show_notice("error", "The check found 2 problems.", details=["...", "..."])
    notice.show_notice("warning", "Save the project first.", button="Save project…", callback=save)
    notice.clear()
"""

from collections.abc import Callable
from typing import Final, Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.theme import ThemeManager

Severity = Literal["error", "warning", "info"]
_ICON: Final = {"error": "fail", "warning": "warning", "info": "info"}
_NAME: Final = {"error": "Error", "warning": "Warning", "info": "Note"}


class InlineNotice(QFrame):
    """One message at a time; hidden until `show_notice` is called."""

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setProperty("banner", True)
        self.setObjectName("inline-notice")
        self.severity: Severity = "info"
        self._callback: Callable[[], None] | None = None
        outer = QHBoxLayout(self)
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addWidget(self.icon)
        col = QVBoxLayout()
        self.label = QLabel()
        self.label.setObjectName("inline-notice-text")
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details = QLabel()
        self.details.setObjectName("inline-notice-details")
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.label)
        col.addWidget(self.details)
        outer.addLayout(col, 1)
        self.action = QPushButton()
        self.action.setObjectName("inline-notice-action")
        self.action.clicked.connect(self._fire)
        self.dismiss = QPushButton()
        self.dismiss.setObjectName("inline-notice-dismiss")
        icons.icon_button(self.dismiss, "close", theme, strings.EXP_BANNER_DISMISS_TIP)
        self.dismiss.clicked.connect(self.clear)
        outer.addWidget(self.action, 0, Qt.AlignmentFlag.AlignTop)
        outer.addWidget(self.dismiss, 0, Qt.AlignmentFlag.AlignTop)
        theme.changed.connect(self._restyle)
        self.hide()

    def _restyle(self) -> None:
        self.icon.setPixmap(
            icons.icon(_ICON[self.severity], self.theme, self.severity).pixmap(self.theme.icon_size(16), self.theme.icon_size(16))  # fmt: skip
        )
        self.style().unpolish(self)
        self.style().polish(self)

    def _fire(self) -> None:
        if self._callback is not None:
            self._callback()

    def show_notice(
        self,
        severity: Severity,
        text: str,
        *,
        details: list[str] | None = None,
        button: str | None = None,
        tooltip: str | None = None,
        callback: Callable[[], None] | None = None,
    ) -> None:
        """Show `text` (and a bullet list of `details`); `button` adds an action."""
        self.severity = severity
        self.setProperty("severity", severity)
        self._callback = callback
        self.label.setText(text)
        self.details.setText("\n".join(f"• {d}" for d in details or []))
        self.details.setVisible(bool(details))
        self.action.setVisible(button is not None)
        if button is not None:
            self.action.setText(button)
            self.action.setAccessibleName(button)
            self.action.setToolTip(tooltip or button)
        self.setAccessibleName(f"{_NAME[severity]}: {text}")
        self._restyle()
        self.show()

    def clear(self) -> None:
        self._callback = None
        self.label.clear()
        self.details.clear()
        self.hide()

    def text(self) -> str:
        """The message and its details, for tests and screen readers."""
        return "\n".join(t for t in (self.label.text(), self.details.text()) if t)
