# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The Assumptions window (D-191, S2): what the tool assumes for this project.

    AssumptionsDialog(parent, theme, project).exec()

Read-only, selectable text in a fixed-width font: the page that `harness-design-studio settings`
prints (`core.settings.render`): every setting with the value in force and where it comes from (the
project, the tool's own default, or not set), the assumptions built into the tool with the settings
that parameterise them, and the fixed definitions. Opened from **Help > Assumptions**.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from harness_design_studio.core import settings
from harness_design_studio.core.model import Project
from harness_design_studio.gui import strings
from harness_design_studio.gui.dialog_base import Dialog
from harness_design_studio.gui.theme import ThemeManager, mark_mono


class AssumptionsDialog(Dialog):
    def __init__(self, parent: QWidget | None, theme: ThemeManager, project: Project) -> None:
        super().__init__(parent)
        self.setObjectName("assumptions-dialog")
        self.setWindowTitle(strings.ASSUMPTIONS_TITLE)
        self.resize(theme.px(820), theme.px(600))
        lay = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setObjectName("assumptions-text")
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setAccessibleName(strings.ASSUMPTIONS_NAME)
        mark_mono(self.text)
        self.text.setPlainText(settings.render(project))
        lay.addWidget(self.text, 1)
        close = QPushButton(strings.CLOSE)
        close.setObjectName("assumptions-close")
        close.clicked.connect(self.accept)
        close.setDefault(True)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
