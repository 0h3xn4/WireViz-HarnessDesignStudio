"""An empty state for a table: a short title, one line on what to do and, if given, one action.

The overlay is a child of the view's viewport, so it needs no layout change and no extra widget in
the page. It shows when the view has no rows and tells "nothing here yet" (the list is empty) from
"no row matches" (a filter hides every row). Colours come from the palette, so a theme switch needs
no work here."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import strings


class EmptyState(QWidget):
    """The overlay. Use `attach_empty_state` to put one on a view."""

    def __init__(
        self,
        view: QAbstractItemView,
        title: str,
        hint: str = "",
        *,
        action: str = "",
        on_action: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(view.viewport())
        self.view = view
        self.setObjectName("empty-state")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, not action)
        lay = QVBoxLayout(self)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title = QLabel(title)
        self.title.setObjectName("empty-state-title")
        self.title.setProperty("heading", True)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title.setWordWrap(True)
        self.hint = QLabel(hint)
        self.hint.setObjectName("empty-state-hint")
        self.hint.setProperty("muted", True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setWordWrap(True)
        self.hint.setVisible(bool(hint))
        lay.addWidget(self.title)
        lay.addWidget(self.hint)
        self.button: QPushButton | None = None
        if action:
            self.button = QPushButton(action)
            self.button.setObjectName("empty-state-action")
            if on_action is not None:
                self.button.clicked.connect(on_action)
            lay.addWidget(self.button, 0, Qt.AlignmentFlag.AlignCenter)
        self._none = (title, hint)
        view.viewport().installEventFilter(self)
        model = view.model()
        if model is not None:
            self._watch(model)
        self.refresh()

    def _watch(self, model: object) -> None:
        for name in (
            "rowsInserted",
            "rowsRemoved",
            "modelReset",
            "layoutChanged",
        ):
            getattr(model, name).connect(self.refresh)
        source = model.sourceModel() if isinstance(model, QSortFilterProxyModel) else None
        if source is not None:
            for name in ("rowsInserted", "rowsRemoved", "modelReset"):
                getattr(source, name).connect(self.refresh)

    def set_text(self, title: str, hint: str = "") -> None:
        """Change what the empty list says (the controller's mode may change what to do next)."""
        self._none = (title, hint)
        self.refresh()

    @property
    def filtered_out(self) -> bool:
        """True when rows exist but the filter hides all of them."""
        model = self.view.model()
        if not isinstance(model, QSortFilterProxyModel) or model.rowCount() > 0:
            return False
        source = model.sourceModel()
        return source is not None and source.rowCount() > 0

    def refresh(self, *_args: object) -> None:
        model = self.view.model()
        empty = model is None or model.rowCount() == 0
        if empty:
            if self.filtered_out:
                self.title.setText(strings.EMPTY_FILTERED_TITLE)
                self.hint.setText(strings.EMPTY_FILTERED_HINT)
                self.hint.setVisible(True)
                if self.button is not None:
                    self.button.setVisible(False)
            else:
                self.title.setText(self._none[0])
                self.hint.setText(self._none[1])
                self.hint.setVisible(bool(self._none[1]))
                if self.button is not None:
                    self.button.setVisible(True)
            self._place()
        self.setVisible(empty)
        if empty:
            self.raise_()

    def _place(self) -> None:
        vp = self.view.viewport()
        head = 0
        self.setGeometry(0, head, vp.width(), vp.height())

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.view.viewport() and event.type() == QEvent.Type.Resize and self.isVisible():
            self._place()
        return False


def attach_empty_state(
    view: QAbstractItemView,
    title: str,
    hint: str = "",
    *,
    action: str = "",
    on_action: Callable[[], None] | None = None,
) -> EmptyState:
    """Show `title` and `hint` over `view` while it has no rows; `view.empty_state` holds the
    overlay."""
    state = EmptyState(view, title, hint, action=action, on_action=on_action)
    view.empty_state = state  # type: ignore[attr-defined]
    return state
