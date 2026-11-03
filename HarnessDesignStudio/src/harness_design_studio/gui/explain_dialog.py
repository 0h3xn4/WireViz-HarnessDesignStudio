"""The window that shows how a number was calculated (D-191): the text of `harness-design-studio explain`.

    ExplainDialog(parent, theme, derivations).exec()

Read-only, selectable text in a fixed-width font, one derivation after the other, with a Close button.
It shows what `core.derive.render` gives and nothing of its own, so the window, the Why tab and the
command line say the same.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from harness_design_studio.core.derive import Derivation, render
from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager, mark_mono


class ExplainDialog(QDialog):
    def __init__(
        self, parent: QWidget | None, theme: ThemeManager, derivations: list[Derivation]
    ) -> None:
        super().__init__(parent)
        self.setObjectName("explain-dialog")
        subject = derivations[0].subject if derivations else ""
        self.setWindowTitle(strings.EXPLAIN_DIALOG_TITLE.format(subject))
        self.resize(theme.px(720), theme.px(520))
        lay = QVBoxLayout(self)
        self.text = QPlainTextEdit()
        self.text.setObjectName("explain-text")
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setAccessibleName(strings.EXPLAIN_DIALOG_NAME)
        mark_mono(self.text)
        self.text.setPlainText(
            "\n\n".join(render(d) for d in derivations) or strings.EXPLAIN_NOTHING
        )
        lay.addWidget(self.text, 1)
        close = QPushButton(strings.CLOSE)
        close.setObjectName("explain-close")
        close.clicked.connect(self.accept)
        close.setDefault(True)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
