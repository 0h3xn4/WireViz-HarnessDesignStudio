"""The window that shows how a number was calculated (D-191): the text of `harness-design-studio explain`.

    ExplainDialog(parent, theme, derivations).exec()

Read-only, selectable text in a fixed-width font, one derivation after the other, with a Close button.
It shows what `core.derive.render` gives, so the window, the Why tab and the command line say the
same, and under each derivation one quiet line, "Model page: docs/models/wire-sizing.md", that names
the page of the documentation which describes the model behind it (`core.derive_kinds`). It is text
only: nothing is opened and nothing goes to a network.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from harness_design_studio.core.derive import Derivation, render
from harness_design_studio.core.derive_kinds import KINDS
from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager, mark_mono


def model_page_line(d: Derivation) -> str:
    """ "Model page: docs/models/wire-sizing.md" for the kind of derivation `d` is, or "" for a kind
    the tool does not list (a rule of an extension has no page of its own)."""
    kind = KINDS.get(d.id)
    return strings.EXPLAIN_MODEL_PAGE.format(kind[0]) if kind is not None else ""


def render_with_page(d: Derivation) -> str:
    """The derivation as text, then its model page on a line of its own."""
    page = model_page_line(d)
    return f"{render(d)}\n{page}" if page else render(d)


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
            "\n\n".join(render_with_page(d) for d in derivations) or strings.EXPLAIN_NOTHING
        )
        lay.addWidget(self.text, 1)
        close = QPushButton(strings.CLOSE)
        close.setObjectName("explain-close")
        close.clicked.connect(self.accept)
        close.setDefault(True)
        lay.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
