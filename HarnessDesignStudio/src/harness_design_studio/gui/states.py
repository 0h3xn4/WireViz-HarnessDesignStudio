"""State chips: pass, fail, pending, not checked, locked, released, stale ... as icon + word + pattern.

Colour is never the only cue. Every state has its own icon and its own word; *pending* (a dotted
border and dots) and *not checked* (a dashed border and hatching) also differ in pattern, so they
cannot be taken for pass or fail (solid border), nor for an empty cell (which shows nothing).

    paint_chip(painter, rect, "pending", theme, text="24 AWG?")   # inside any custom paint
    StateChip()                                                   # a widget (dock headers, cards)
    StateDelegate(theme)                                          # table cells with STATE_ROLE

`tables.DictTableModel` fills `STATE_ROLE` from a column's `state` spec.
"""

from dataclasses import dataclass
from typing import Final, Literal

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QPointF,
    QRectF,
    QSize,
    Qt,
)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QApplication,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from harness_design_studio.gui import strings
from harness_design_studio.gui.icons import draw_icon
from harness_design_studio.gui.theme import ThemeManager

STATE_ROLE: Final = int(Qt.ItemDataRole.UserRole) + 1  # item data role: the state key of a cell

Pattern = Literal["solid", "dotted", "hatched"]

FILL_ALPHA: Final = 0.04  # tint of the chip (the cell colour shows through)
PATTERN_ALPHA: Final = 0.30  # dots and hatching are faint, the text stays readable on them
PATTERN_COVERAGE: Final = {"hatched": 0.28, "dotted": 0.16}  # share of the chip the pattern inks


@dataclass(frozen=True)
class StateSpec:
    key: str
    icon: str  # name in gui/icons.py
    token: str  # colour token in gui/tokens.py
    label: str  # the word (plain language)
    pattern: Pattern  # solid border, or dotted / hatched for "nothing known yet"


def _spec(key: str, icon: str, token: str, pattern: Pattern = "solid") -> StateSpec:
    return StateSpec(key, icon, token, strings.STATE_LABELS[key], pattern)


STATES: Final[dict[str, StateSpec]] = {
    s.key: s
    for s in (
        _spec("pass", "pass", "success"),
        _spec("fail", "fail", "error"),
        _spec("warning", "warning", "warning"),
        _spec("info", "info", "info"),
        _spec("pending", "pending", "pending", "dotted"),
        _spec("not-checked", "not-checked", "not-checked", "hatched"),
        _spec("locked", "lock", "locked"),
        _spec("released", "release", "released"),
        _spec("stale", "stale", "stale"),
        _spec("draft", "draft", "text-muted"),
        _spec("in-review", "review", "info"),
        _spec("revised", "revised", "primary"),
    )
}


def spec_of(state: str) -> StateSpec:
    """The look of a state; an unknown key is a programming error."""
    return STATES[state]


def _hatch(painter: QPainter, rect: QRectF, colour: QColor, pattern: Pattern) -> None:
    painter.save()
    painter.setClipRect(rect)
    c = QColor(colour)
    c.setAlphaF(PATTERN_ALPHA)
    if pattern == "hatched":
        painter.setPen(QPen(c, 1))
        step = 5
        x = rect.left() - rect.height()
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.bottom()), QPointF(x + rect.height(), rect.top()))
            x += step
    else:  # dotted
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(c)
        y = rect.top() + 2.0
        while y < rect.bottom():
            x = rect.left() + 2.0
            while x < rect.right():
                painter.drawEllipse(QPointF(x, y), 0.9, 0.9)
                x += 4
            y += 4
    painter.restore()


def chip_size(state: str, theme: ThemeManager, text: str | None, font: QFont) -> QSize:
    """The room a chip needs: icon, word and padding."""
    f = QFont(font)
    f.setItalic(STATES[state].pattern != "solid")
    fm = QFontMetrics(f)
    label = text if text is not None else STATES[state].label
    icon = _icon_px(fm)
    pad = theme.space(8)
    return QSize(pad + icon + theme.space(4) + fm.horizontalAdvance(label) + pad, fm.height() + 6)


def _icon_px(fm: QFontMetrics) -> int:
    return max(12, fm.height() - 2)


def paint_chip(
    painter: QPainter,
    rect: QRectF,
    state: str,
    theme: ThemeManager,
    *,
    text: str | None = None,
    selected: bool = False,
    font: QFont | None = None,
) -> None:
    """Draw a state chip in `rect`: tinted box with a border, the icon, and the word (or `text`).
    `selected` draws it for a highlighted row (everything in the on-primary colour)."""
    spec = STATES[state]
    colour = theme.color("on-primary" if selected else spec.token)
    f = QFont(font if font is not None else QApplication.font())
    f.setItalic(spec.pattern != "solid")
    fm = QFontMetrics(f)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = rect.adjusted(0.5, 0.5, -0.5, -0.5)
    fill = QColor(colour)
    fill.setAlphaF(FILL_ALPHA)
    painter.fillRect(box, fill)
    if spec.pattern != "solid":
        _hatch(painter, box, colour, spec.pattern)
    pen = QPen(colour, 1)
    if spec.pattern == "dotted":
        pen.setStyle(Qt.PenStyle.DotLine)
    elif spec.pattern == "hatched":
        pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRect(box)
    pad, gap = theme.space(8), theme.space(4)
    side = min(_icon_px(fm), box.height() - 2)
    icon_rect = QRectF(box.left() + pad - 2, box.center().y() - side / 2, side, side)
    draw_icon(painter, spec.icon, icon_rect, colour, stroke=1.5)
    label = text if text is not None else spec.label
    text_left = icon_rect.right() + gap
    avail = max(0, int(box.right() - pad / 2 - text_left))
    painter.setFont(f)
    painter.setPen(colour)
    painter.drawText(
        QRectF(text_left, box.top(), avail, box.height()),
        int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
        fm.elidedText(label, Qt.TextElideMode.ElideRight, avail),
    )
    painter.restore()


class StateChip(QWidget):
    """A state chip as a widget: `set_state("locked", "Released in rev B")`."""

    def __init__(
        self, theme: ThemeManager, state: str = "not-checked", text: str | None = None
    ) -> None:
        super().__init__()
        self.theme = theme
        self._state, self._text = state, text
        theme.changed.connect(self.update)
        self._sync()

    def state(self) -> str:
        return self._state

    def text(self) -> str | None:
        return self._text

    def set_state(self, state: str, text: str | None = None) -> None:
        if state not in STATES:
            raise KeyError(f"unknown state {state!r}")
        self._state, self._text = state, text
        self._sync()

    def _sync(self) -> None:
        spec = STATES[self._state]
        shown = f"{spec.label}: {self._text}" if self._text else spec.label
        self.setAccessibleName(shown)
        self.setToolTip(shown)
        self.updateGeometry()
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return chip_size(self._state, self.theme, self._text, self.font())

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.sizeHint()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        paint_chip(
            p,
            QRectF(self.rect()),
            self._state,
            self.theme,
            text=self._text,
            font=self.font(),
        )
        p.end()


class StateDelegate(QStyledItemDelegate):
    """Paints cells that carry a `STATE_ROLE` as a state chip (icon + word + pattern); every other
    cell is painted as usual, so one delegate serves a whole table. A cell with a state shows its
    display text in the chip (or the state's word when the text is empty)."""

    def __init__(self, theme: ThemeManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.theme = theme

    @staticmethod
    def state_of(index: QModelIndex | QPersistentModelIndex) -> str | None:
        state = index.data(STATE_ROLE)
        return state if isinstance(state, str) and state in STATES else None

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        state = self.state_of(index)
        if state is None:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        text = opt.text
        opt.text = ""
        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        sel = bool(opt.state & QStyle.StateFlag.State_Selected)
        margin = self.theme.space(4)
        rect = QRectF(opt.rect).adjusted(margin, 2, -margin, -2)
        size = chip_size(state, self.theme, text or None, opt.font)
        full_width = rect.width()
        rect.setWidth(min(full_width, size.width()))
        rect.setHeight(min(rect.height(), size.height()))
        rect.moveTop(opt.rect.center().y() - rect.height() / 2)
        align = index.data(Qt.ItemDataRole.TextAlignmentRole)
        if isinstance(align, int) and align & int(Qt.AlignmentFlag.AlignRight):
            rect.moveRight(opt.rect.right() - margin)  # a number column keeps its right edge
        paint_chip(
            painter,
            rect,
            state,
            self.theme,
            text=text or None,
            selected=sel,
            font=opt.font,
        )

    def sizeHint(  # noqa: N802
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        base = super().sizeHint(option, index)
        state = self.state_of(index)
        if state is None:
            return base
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        size = chip_size(state, self.theme, opt.text or None, opt.font)
        margin = self.theme.space(4) * 2
        return QSize(
            max(base.width(), size.width() + margin), max(base.height(), size.height() + 4)
        )
