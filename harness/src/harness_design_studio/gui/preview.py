"""Drawing preview: paints the same sheet description that becomes the SVG and PDF, so what you
see here is what is exported (title block stamped "preview" because no export has happened)."""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from harness_design_studio.core.model import Harness, Project
from harness_design_studio.core.outputs.canvas import Curve, Line, Rect, Sheet, Text, text_width
from harness_design_studio.core.outputs.drawing import harness_sheets
from harness_design_studio.core.outputs.stamp import Stamp
from harness_design_studio.gui import strings
from harness_design_studio.gui.theme import ThemeManager, current_theme


class SheetView(QWidget):
    """Draws one `Sheet` scaled to fit, on a paper-coloured page (the `paper` token is white in
    both themes: it is a picture of paper) over the `pasteboard` token. Text is drawn in the
    monospace font, as in the exported drawing."""

    def __init__(self, theme: ThemeManager | None = None) -> None:
        super().__init__()
        self.theme = theme or current_theme()
        self.theme.changed.connect(self.update)
        self.sheet: Sheet | None = None
        self.setMinimumSize(240, 170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_sheet(self, sheet: Sheet | None) -> None:
        self.sheet = sheet
        self.update()

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), self.theme.color("pasteboard"))
        sheet = self.sheet
        if sheet is None:
            return
        scale = min((self.width() - 8) / sheet.width, (self.height() - 8) / sheet.height)
        ox, oy = (
            (self.width() - sheet.width * scale) / 2,
            (self.height() - sheet.height * scale) / 2,
        )
        painter.fillRect(
            QRectF(ox, oy, sheet.width * scale, sheet.height * scale), self.theme.color("paper")
        )

        def pen(color: str, width: float, dash: tuple[float, float] | None) -> QPen:
            p = QPen(QColor(color), max(0.6, width * scale))
            if dash:
                p.setDashPattern([dash[0] / max(width, 0.1), dash[1] / max(width, 0.1)])
            return p

        for it in sheet.items:
            if isinstance(it, Line):
                painter.setPen(pen(it.color, it.width, it.dash))
                painter.drawLine(
                    QPointF(ox + it.x1 * scale, oy + it.y1 * scale),
                    QPointF(ox + it.x2 * scale, oy + it.y2 * scale),
                )
            elif isinstance(it, Curve):
                painter.setPen(pen(it.color, it.width, None))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                path = QPainterPath(QPointF(ox + it.x1 * scale, oy + it.y1 * scale))
                xm = ox + (it.x1 + it.x2) / 2 * scale
                path.cubicTo(
                    QPointF(xm, oy + it.y1 * scale),
                    QPointF(xm, oy + it.y2 * scale),
                    QPointF(ox + it.x2 * scale, oy + it.y2 * scale),
                )
                painter.drawPath(path)
            elif isinstance(it, Rect):
                painter.setPen(pen(it.color, it.width, it.dash))
                painter.setBrush(QColor(it.fill) if it.fill else Qt.BrushStyle.NoBrush)
                painter.drawRect(
                    QRectF(ox + it.x * scale, oy + it.y * scale, it.w * scale, it.h * scale)
                )
            elif isinstance(it, Text):
                px = it.size * scale
                if px < 3:  # too small to read at this zoom: skip instead of drawing a smear
                    continue
                font = self.theme.mono_font()
                font.setPixelSize(max(3, round(px)))  # the drawing's own size at this zoom
                font.setBold(it.bold)
                painter.setFont(font)
                painter.setPen(QColor(it.color))
                painter.drawText(QPointF(ox + it.left * scale, oy + it.y * scale), it.s)
        painter.end()


class DrawingPreview(QWidget):
    """Sheet view with previous and next buttons for multi-sheet harnesses."""

    pageChanged = Signal(int, int)  # page, total

    def __init__(self, theme: ThemeManager | None = None) -> None:
        super().__init__()
        self.setObjectName("drawing-preview")
        self.sheets: list[Sheet] = []
        self.page = 0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.view = SheetView(theme)
        self.view.setObjectName("drawing-sheet")
        self.view.setAccessibleName(strings.PREVIEW_SHEET)
        lay.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.prev = QPushButton(strings.PREVIEW_PREV)
        self.prev.setObjectName("preview-prev")
        self.next = QPushButton(strings.PREVIEW_NEXT)
        self.next.setObjectName("preview-next")
        self.label = QLabel()
        self.label.setObjectName("preview-label")
        self.prev.clicked.connect(lambda: self.go(-1))
        self.next.clicked.connect(lambda: self.go(1))
        row.addWidget(self.prev)
        row.addWidget(self.label, 1)
        row.addWidget(self.next)
        lay.addLayout(row)
        self.show_harness(None, None)

    def show_harness(self, project: Project | None, h: Harness | None) -> None:
        if project is None or h is None:
            self.sheets, self.page = [], 0
        else:
            self.sheets = harness_sheets(project, h, Stamp("preview", "preview"), "A3")
            self.page = min(self.page, len(self.sheets) - 1)
        self._refresh()

    def go(self, step: int) -> None:
        self.page = max(0, min(len(self.sheets) - 1, self.page + step))
        self._refresh()

    def _refresh(self) -> None:
        n = len(self.sheets)
        self.view.set_sheet(self.sheets[self.page] if n else None)
        self.label.setText(
            strings.PREVIEW_PAGE.format(self.page + 1, n) if n else strings.PREVIEW_NONE
        )
        self.prev.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < n - 1)
        self.pageChanged.emit(self.page + 1, n)


__all__ = ["DrawingPreview", "SheetView", "text_width"]
