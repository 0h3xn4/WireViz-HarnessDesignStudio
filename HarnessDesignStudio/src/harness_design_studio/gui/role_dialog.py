"""The question of the first start: *Who are you working as?* (workshop feedback M5, D-176).

    dlg = RoleDialog(parent, theme)
    dlg.exec()
    role = dlg.choice          # "systems", "electrical", or None when the window was closed

Two big buttons, each with one plain sentence, and a note that the role can be changed later in
View > Role. The window asks once, on a settings file with nothing stored (`MainWindow.ask_role_flow`);
a test or CI sets `roles.FIRST_RUN_ROLE` and the window never shows this one.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from harness_design_studio.gui import strings
from harness_design_studio.gui.roles import ELECTRICAL, SYSTEMS
from harness_design_studio.gui.theme import ThemeManager


class _Choice(QPushButton):
    """A big button: the name of the role, and under it one sentence."""

    def __init__(self, theme: ThemeManager, name: str, title: str, sentence: str, tip: str) -> None:
        super().__init__()
        self.setObjectName(name)
        self.setAccessibleName(title)
        self.setAccessibleDescription(sentence)
        self.setToolTip(tip)
        self.setProperty("choice", True)  # the style sheet frees the height of a control
        self.setMinimumHeight(theme.px(72))
        self.setMinimumWidth(theme.px(420))
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.space(16), theme.space(12), theme.space(16), theme.space(12))
        lay.setSpacing(theme.space(4))
        head = QLabel(title)
        head.setProperty("heading", True)
        body = QLabel(sentence)
        body.setWordWrap(True)
        for label in (head, body):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(label)


class RoleDialog(QDialog):
    def __init__(self, parent: QWidget | None, theme: ThemeManager) -> None:
        super().__init__(parent)
        self.choice: str | None = None
        self.setObjectName("role-dialog")
        self.setWindowTitle(strings.ROLE_DIALOG_TITLE)
        self.setAccessibleName(strings.ROLE_DIALOG_NAME)
        self.setModal(True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.space(24), theme.space(24), theme.space(24), theme.space(24))
        lay.setSpacing(theme.space(12))
        title = QLabel(strings.ROLE_DIALOG_TITLE)
        title.setObjectName("role-dialog-title")
        title.setProperty("title", True)
        text = QLabel(strings.ROLE_DIALOG_TEXT)
        text.setWordWrap(True)
        self.systems_btn = _Choice(
            theme,
            "role-choice-systems",
            strings.ROLE_DIALOG_SYSTEMS,
            strings.ROLE_DIALOG_SYSTEMS_TEXT,
            strings.ROLE_SYSTEMS_TIP,
        )
        self.electrical_btn = _Choice(
            theme,
            "role-choice-electrical",
            strings.ROLE_DIALOG_ELECTRICAL,
            strings.ROLE_DIALOG_ELECTRICAL_TEXT,
            strings.ROLE_ELECTRICAL_TIP,
        )
        later = QLabel(strings.ROLE_DIALOG_LATER)
        later.setObjectName("role-dialog-later")
        later.setProperty("muted", True)
        later.setWordWrap(True)
        for w in (title, text, self.systems_btn, self.electrical_btn, later):
            lay.addWidget(w)
        self.systems_btn.clicked.connect(lambda _c=False: self._pick(SYSTEMS))
        self.electrical_btn.clicked.connect(lambda _c=False: self._pick(ELECTRICAL))
        self.systems_btn.setFocus()

    def _pick(self, role: str) -> None:
        self.choice = role
        self.accept()
