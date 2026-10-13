"""Building blocks of the app shell: tabs with slots for views that arrive later, empty states,
persistent banners, and the words of a refusal.

    tabs = SlotTabs()
    tabs.add_slot("harness", "Harness", EmptyStateWidget(theme, "Harness", "..."), installed=False)
    tabs.install("harness", HarnessView(ctl, theme))      # replaces the placeholder, shows the tab
    banners = BannerStack(theme)
    banners.show_banner("stale", "warning", "Plans are out of date", actions=[("Generate", go)])
    banners.clear("stale")

A slot whose view is not installed keeps an `EmptyStateWidget` (what the view is for and what to do)
and its tab stays hidden, so a view that has not been written yet never shows as a dead tab. The
window registers its slots in `MainWindow._view_slots`; `MainWindow.install_view(name, widget)`
plugs a finished view in.
"""

import re
from collections.abc import Callable, Sequence

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.theme import ThemeManager

# ---- empty state -------------------------------------------------------------------------------


class EmptyStateWidget(QWidget):
    """A centred title and sentence for a view that has nothing to show yet; an optional button
    does the one thing that fills it."""

    def __init__(
        self,
        theme: ThemeManager,
        title: str,
        text: str,
        *,
        icon: str | None = None,
        button: str | None = None,
        callback: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("empty-state")
        self.setAccessibleName(f"{title}. {text}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(theme.space(24), theme.space(24), theme.space(24), theme.space(24))
        lay.addStretch(1)
        if icon is not None:
            glyph = QLabel()
            glyph.setPixmap(
                icons.icon(icon, theme, "text-muted").pixmap(theme.px(32), theme.px(32))
            )
            glyph.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            glyph.setAccessibleName(title)
            lay.addWidget(glyph)
        self.title = QLabel(title)
        self.title.setProperty("heading", True)
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.body = QLabel(text)
        self.body.setWordWrap(True)
        self.body.setProperty("muted", True)
        self.body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.title)
        lay.addWidget(self.body)
        self.button: QPushButton | None = None
        if button is not None:
            self.button = QPushButton(button)
            self.button.setAccessibleName(button)
            if callback is not None:
                self.button.clicked.connect(lambda _c=False: callback())
            lay.addWidget(self.button, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch(2)

    def text(self) -> str:
        return self.body.text()


# ---- tabs with slots ---------------------------------------------------------------------------


class SlotTabs(QTabWidget):
    """A tab widget whose tabs are named slots. A slot can start empty and hidden and be filled
    later with `install`. The tab bar itself hides while at most `min_bar` tabs are visible
    (a single tab needs no bar)."""

    def __init__(self, parent: QWidget | None = None, *, min_bar: int = 1) -> None:
        super().__init__(parent)
        self._names: list[str] = []
        self._installed: dict[str, bool] = {}
        self._min_bar = min_bar
        self.currentChanged.connect(lambda _i: self._sync_bar())

    # ---- slots ----
    def add_slot(
        self,
        name: str,
        title: str,
        widget: QWidget,
        *,
        installed: bool = True,
        tip: str = "",
    ) -> int:
        index = self.addTab(widget, title)
        self._names.append(name)
        self._installed[name] = installed
        if tip:
            self.setTabToolTip(index, tip)
        self.setTabVisible(index, installed)
        self._ensure_visible_current()
        self._sync_bar()
        return index

    def _ensure_visible_current(self) -> None:
        """The current tab must be one that shows (a hidden first tab must not stay current)."""
        if self.count() and not self.isTabVisible(self.currentIndex()):
            for i in range(self.count()):
                if self.isTabVisible(i):
                    self.setCurrentIndex(i)
                    return

    def names(self) -> list[str]:
        return list(self._names)

    def index_of(self, name: str) -> int:
        return self._names.index(name)

    def has_slot(self, name: str) -> bool:
        return name in self._installed

    def is_installed(self, name: str) -> bool:
        return self._installed.get(name, False)

    def widget_of(self, name: str) -> QWidget:
        w = self.widget(self.index_of(name))
        if w is None:
            raise KeyError(name)
        return w

    def install(self, name: str, widget: QWidget, *, show: bool = False) -> QWidget:
        """Put `widget` in the slot (replacing the placeholder or an earlier view) and show its
        tab. Returns the widget that was replaced (it is scheduled for deletion)."""
        index = self.index_of(name)
        old = self.widget_of(name)
        title, tip = self.tabText(index), self.tabToolTip(index)
        was_current = self.currentIndex() == index
        self.blockSignals(True)
        self.removeTab(index)
        self.insertTab(index, widget, title)
        self.setTabToolTip(index, tip)
        self.setTabVisible(index, True)
        if was_current:
            self.setCurrentIndex(index)
        self.blockSignals(False)
        self._installed[name] = True
        old.setParent(None)
        if isinstance(old, EmptyStateWidget):
            old.deleteLater()  # a placeholder; a real panel that is replaced stays alive
        if show:
            self.setCurrentIndex(index)
        self._sync_bar()
        self.currentChanged.emit(self.currentIndex())
        return old

    def show_slot(self, name: str) -> bool:
        """Make the slot's tab current; False when its view is not installed."""
        if not self.is_installed(name):
            return False
        self.setCurrentIndex(self.index_of(name))
        return True

    def visible_names(self) -> list[str]:
        return [n for i, n in enumerate(self._names) if self.isTabVisible(i)]

    def _sync_bar(self) -> None:
        shown = sum(1 for i in range(self.count()) if self.isTabVisible(i))
        self.tabBar().setVisible(shown > self._min_bar)


# ---- persistent banners ------------------------------------------------------------------------

_BANNER_ICON = {"error": ("fail", "error"), "warning": ("stale", "stale"), "info": ("info", "info")}
_BANNER_WORD = {"error": "Error", "warning": "Notice", "info": "Note"}


class StackBanner(QFrame):
    """One persistent message: icon and words, optional details, action buttons and a dismiss
    button. The kind is in the icon and the word as well as the colour."""

    dismissed = Signal(str)

    def __init__(self, key: str, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.key, self.theme = key, theme
        self.severity = "warning"
        self.setProperty("banner", True)
        self.setObjectName(f"banner-{key}")
        outer = QHBoxLayout(self)
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        col = QVBoxLayout()
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setTextFormat(Qt.TextFormat.PlainText)
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setProperty("muted", True)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        col.addWidget(self.label)
        col.addWidget(self.details)
        outer.addLayout(col, 1)
        self.buttons: list[QPushButton] = []
        self._button_row = QHBoxLayout()
        outer.addLayout(self._button_row)
        self.dismiss = QPushButton()
        self.dismiss.setObjectName(f"banner-{key}-dismiss")
        icons.icon_button(self.dismiss, "close", theme, strings.BN_DISMISS)
        self.dismiss.clicked.connect(lambda _c=False: self.dismissed.emit(self.key))
        outer.addWidget(self.dismiss, 0, Qt.AlignmentFlag.AlignTop)
        theme.changed.connect(self._restyle)
        self.hide()

    def _restyle(self) -> None:
        name, role = _BANNER_ICON[self.severity]
        px = self.theme.icon_size(16)
        self.icon.setPixmap(icons.icon(name, self.theme, role).pixmap(px, px))
        self.style().unpolish(self)
        self.style().polish(self)

    def set_content(
        self,
        severity: str,
        text: str,
        details: Sequence[str],
        actions: Sequence[tuple[str, Callable[[], None]]],
        dismissible: bool,
    ) -> None:
        self.severity = severity if severity in _BANNER_ICON else "warning"
        self.setProperty("severity", self.severity)
        self.label.setText(text)
        self.details.setText("\n".join(details))
        self.details.setVisible(bool(details))
        for b in self.buttons:
            self._button_row.removeWidget(b)
            b.deleteLater()
        self.buttons = []
        for label, callback in actions:
            b = QPushButton(label)
            b.setObjectName(f"banner-{self.key}-action")
            b.setAccessibleName(label)
            b.setToolTip(label)
            b.clicked.connect(lambda _c=False, cb=callback: cb())
            self._button_row.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
            self.buttons.append(b)
        self.dismiss.setVisible(dismissible)
        self.setAccessibleName(f"{_BANNER_WORD[self.severity]}: {text}")
        self._restyle()
        self.show()

    def action_texts(self) -> list[str]:
        return [b.text() for b in self.buttons]

    def text(self) -> str:
        return "\n".join(t for t in (self.label.text(), self.details.text()) if t)


class BannerStack(QWidget):
    """Banners one above the other, each under a key. Showing a key again replaces its content; a
    banner stays until `clear(key)` or the person dismisses it (`dismissed(key)`)."""

    dismissed = Signal(str)

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme
        self.setObjectName("banner-stack")
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(0, 0, 0, 0)
        self.lay.setSpacing(0)
        self._banners: dict[str, StackBanner] = {}

    def show_banner(
        self,
        key: str,
        severity: str,
        text: str,
        *,
        details: Sequence[str] = (),
        actions: Sequence[tuple[str, Callable[[], None]]] = (),
        dismissible: bool = True,
    ) -> StackBanner:
        banner = self._banners.get(key)
        if banner is None:
            banner = StackBanner(key, self.theme)
            banner.dismissed.connect(self._dismissed)
            self._banners[key] = banner
            self.lay.addWidget(banner)
        banner.set_content(severity, text, details, actions, dismissible)
        return banner

    def _dismissed(self, key: str) -> None:
        self.clear(key)
        self.dismissed.emit(key)

    def clear(self, key: str) -> None:
        banner = self._banners.get(key)
        if banner is not None:
            banner.hide()

    def banner(self, key: str) -> StackBanner | None:
        return self._banners.get(key)

    def is_showing(self, key: str) -> bool:
        banner = self._banners.get(key)
        return banner is not None and not banner.isHidden()

    def keys(self) -> list[str]:
        return [k for k, b in self._banners.items() if not b.isHidden()]


# ---- the words of a refusal -------------------------------------------------------------------

_RELEASED = re.compile(r"\b([A-Za-z][A-Za-z0-9_.-]*) is released \(revision")
_RELEASED_CONFIG = re.compile(r"released harness\(es\) ([A-Za-z0-9_.-]+)")


def refusal_harness(text: str) -> str | None:
    """The released harness a lock refusal names ("... W001 is released (revision A); start a new
    revision to change it."), or None when the message is about something else."""
    for pattern in (_RELEASED, _RELEASED_CONFIG):
        m = pattern.search(text)
        if m:
            return m.group(1)
    return None


# ---- text that is too long for its room ---------------------------------------------------------


class ElidedLabel(QLabel):
    """A label that cuts a long text in the middle ("/home/ann/…/flatsat") instead of making the
    window wider; the whole text is the tooltip."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    def set_full_text(self, text: str, tip: str | None = None) -> None:
        self._full = text
        self.setToolTip(tip if tip is not None else text)
        self.setAccessibleDescription(text)
        self.update()

    def full_text(self) -> str:
        return self._full

    def shown_text(self) -> str:
        """What is drawn now (the whole text or its middle cut out)."""
        fm = self.fontMetrics()
        room = max(0, self.width() - self.contentsMargins().left() - self.contentsMargins().right())
        return fm.elidedText(self._full, Qt.TextElideMode.ElideMiddle, room)

    def text(self) -> str:
        return self._full

    def setText(self, text: str) -> None:  # noqa: N802
        self.set_full_text(text)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(
            self.fontMetrics().horizontalAdvance("…") * 4, super().minimumSizeHint().height()
        )

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(
            self.fontMetrics().horizontalAdvance(self._full) + 4, super().sizeHint().height()
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        m = self.contentsMargins()
        p.setPen(self.palette().color(self.foregroundRole()))
        p.setFont(self.font())
        p.drawText(
            self.rect().adjusted(m.left(), m.top(), -m.right(), -m.bottom()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            self.shown_text(),
        )
        p.end()


# ---- the first UI scale ---------------------------------------------------------------------------


def auto_scale(logical_height: int, device_pixel_ratio: float = 1.0) -> int:
    """The UI scale in percent for a screen that is `logical_height` px high (in the logical px Qt
    reports) with `device_pixel_ratio`. The system already enlarges everything when the ratio is
    1.5 or more, so then 100 % is right; on a 4K screen at ratio 1 the text would otherwise stay
    13 px. The person's own choice (View > Interface size) always wins and is saved."""
    if device_pixel_ratio >= 1.5:
        return 100
    if logical_height >= 2000:
        return 200
    if logical_height >= 1600:
        return 150
    if logical_height >= 1300:
        return 125
    return 100
