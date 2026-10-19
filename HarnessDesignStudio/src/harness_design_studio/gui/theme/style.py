"""The widget style: Fusion, with check boxes and radio buttons drawn from the palette.

The platform styles draw these with the window colour darkened, which leaves an unticked box invisible
on the dark theme, and a picture file per theme would need the style sheet to change on every theme
switch (a repolish of every widget). Here each state is painted with `QPainter` in the palette's
colours (a visible border, a tick or a dash or a dot inside, never colour alone), so a palette change
is enough.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleOption, QWidget

from harness_design_studio.gui.theme.tokens import RADIUS_CONTROL

INDICATOR_PX = 16  # edge at 100 %
_SIZE_METRICS = (
    QStyle.PixelMetric.PM_IndicatorWidth,
    QStyle.PixelMetric.PM_IndicatorHeight,
    QStyle.PixelMetric.PM_ExclusiveIndicatorWidth,
    QStyle.PixelMetric.PM_ExclusiveIndicatorHeight,
)
_BOXES = (
    QStyle.PrimitiveElement.PE_IndicatorCheckBox,
    QStyle.PrimitiveElement.PE_IndicatorItemViewItemCheck,
)


class ThemeStyle(QProxyStyle):
    """Fusion plus the theme's indicators; `scale` is the UI scale."""

    def __init__(self) -> None:
        super().__init__("Fusion")
        self.scale = 1.0

    def pixelMetric(
        self,
        metric: QStyle.PixelMetric,
        option: QStyleOption | None = None,
        widget: QWidget | None = None,
    ) -> int:
        if metric in _SIZE_METRICS:
            return max(12, round(INDICATOR_PX * self.scale))
        return super().pixelMetric(metric, option, widget)

    def drawPrimitive(
        self,
        element: QStyle.PrimitiveElement,
        option: QStyleOption,
        painter: QPainter,
        widget: QWidget | None = None,
    ) -> None:
        if element in _BOXES:
            self._draw(painter, option, round_=False)
        elif element == QStyle.PrimitiveElement.PE_IndicatorRadioButton:
            self._draw(painter, option, round_=True)
        else:
            super().drawPrimitive(element, option, painter, widget)

    def _draw(self, p: QPainter, option: QStyleOption, *, round_: bool) -> None:
        state = option.state
        pal = option.palette
        enabled = bool(state & QStyle.StateFlag.State_Enabled)
        on = bool(state & QStyle.StateFlag.State_On)
        part = bool(state & QStyle.StateFlag.State_NoChange)
        group = QPalette.ColorGroup.Active if enabled else QPalette.ColorGroup.Disabled
        border = pal.color(group, QPalette.ColorRole.Shadow)  # border.control
        accent = pal.color(group, QPalette.ColorRole.Highlight)
        tick = pal.color(group, QPalette.ColorRole.HighlightedText)
        if not enabled:  # disabled: the muted tone for the outline, the tick and the fill
            border = accent = pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
            tick = pal.color(QPalette.ColorRole.Base)
        edge = float(min(option.rect.width(), option.rect.height()))
        rect = QRectF(option.rect).adjusted(0, 0, 0, 0)
        box = QRectF(
            rect.center().x() - edge * 0.44,
            rect.center().y() - edge * 0.44,
            edge * 0.88,
            edge * 0.88,
        )
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        filled = on or part
        p.setPen(QPen(accent if filled else border, max(1.0, edge / 10)))
        p.setBrush(accent if filled and not round_ else pal.color(QPalette.ColorRole.Base))
        if round_:
            p.drawEllipse(box)
            if on:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(accent)
                p.drawEllipse(box.adjusted(edge * 0.24, edge * 0.24, -edge * 0.24, -edge * 0.24))
        else:
            radius = RADIUS_CONTROL * edge / INDICATOR_PX / 2
            p.drawRoundedRect(box, radius, radius)
            if filled:
                pen = QPen(tick, max(1.5, edge / 8))
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                x, y = box.x(), box.y()
                w = box.width()
                if part:
                    p.drawLine(
                        QPointF(x + w * 0.28, y + w * 0.5), QPointF(x + w * 0.72, y + w * 0.5)
                    )
                else:
                    p.drawPolyline(
                        [
                            QPointF(x + w * 0.24, y + w * 0.52),
                            QPointF(x + w * 0.42, y + w * 0.70),
                            QPointF(x + w * 0.76, y + w * 0.30),
                        ]
                    )
        p.restore()
