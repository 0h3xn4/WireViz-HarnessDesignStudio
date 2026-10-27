"""Drawing preview: paints the same sheet description that becomes the SVG and PDF, so what you
see here is what is exported (title block stamped "preview" because no export has happened).

`SheetView` is a `QGraphicsView`: wheel zoom to the cursor, fit, drag to pan, and a hover and a
selection that are linked to the tables through the `(kind, id)` marks the drawing code puts on the
in-memory sheet (`Sheet.marks`; they never reach the SVG or PDF). `DrawingPreview` adds the
zoom buttons and the previous / next sheet buttons.
"""

import math
from collections.abc import Iterable, Sequence

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStyleOptionGraphicsItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.model import Harness, Project
from harness_design_studio.core.outputs.canvas import Curve, Line, Rect, Sheet, Text, text_width
from harness_design_studio.core.outputs.drawing import harness_sheets
from harness_design_studio.core.outputs.stamp import Stamp
from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.theme import ThemeManager, current_theme

Key = tuple[str, str]  # (kind, id) of a drawn object: "wire", "pin" ("J1/3"), "connector", "shield"

MAX_ZOOM = 24.0  # times the fit-to-window scale
MIN_TEXT_PX = 3.0  # text smaller than this on screen is skipped instead of drawn as a smear
HIT_PX = 4.0  # how near (in screen px) the pointer must be to a wire to pick it
_PRIORITY = {
    "wire": 0,
    "pin": 1,
    "connector": 2,
}  # what a click picks first (shields are only drawn)
_TEXT_K = 8.0  # text is set at 8 times its size and the painter scaled down: no rounding at 2.6 mm


def _item_rect(it: Line | Curve | Rect | Text) -> QRectF:
    if isinstance(it, Line | Curve):
        pad = it.width / 2
        return QRectF(
            QPointF(min(it.x1, it.x2) - pad, min(it.y1, it.y2) - pad),
            QPointF(max(it.x1, it.x2) + pad, max(it.y1, it.y2) + pad),
        )
    if isinstance(it, Rect):
        pad = it.width / 2
        return QRectF(it.x - pad, it.y - pad, it.w + it.width, it.h + it.width)
    w = text_width(it.s, it.size)
    return QRectF(it.left, it.y - it.size, w, it.size * 1.25)


def _curve_path(it: Curve) -> QPainterPath:
    path = QPainterPath(QPointF(it.x1, it.y1))
    xm = (it.x1 + it.x2) / 2
    path.cubicTo(QPointF(xm, it.y1), QPointF(xm, it.y2), QPointF(it.x2, it.y2))
    return path


class _Geometry:
    """What the view needs to find objects under the pointer, built once per sheet."""

    def __init__(self, sheet: Sheet) -> None:
        self.bounds = [_item_rect(i) for i in sheet.items]
        self.outline: dict[Key, QPainterPath] = {}  # thin strokes of a wire, for picking
        self.area: dict[Key, QRectF] = {}  # where a pin row, connector or shield sits
        for key, idx in sheet.marks.items():
            rect = QRectF()
            path = QPainterPath()
            for i in idx:
                it = sheet.items[i]
                rect = rect.united(self.bounds[i]) if not rect.isNull() else QRectF(self.bounds[i])
                if key[0] == "wire" and isinstance(it, Line | Curve):
                    if isinstance(it, Curve):
                        path.addPath(_curve_path(it))
                    else:
                        path.moveTo(it.x1, it.y1)
                        path.lineTo(it.x2, it.y2)
            self.area[key] = rect
            if key[0] == "wire":
                self.outline[key] = path

    def pick(self, p: QPointF, tolerance: float) -> Key | None:
        best: tuple[int, Key] | None = None
        for key, rect in self.area.items():
            rank = _PRIORITY.get(key[0])
            if rank is None or (best is not None and rank >= best[0]):
                continue
            if key[0] == "wire":
                path = self.outline[key]
                if rect.adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(p):
                    stroker = QPainterPathStroker()
                    stroker.setWidth(2 * tolerance)
                    if stroker.createStroke(path).contains(p):
                        best = (rank, key)
            elif rect.contains(p):
                best = (rank, key)
        return best[1] if best else None


class _SheetItem(QGraphicsItem):
    """The paper and everything drawn on it, painted straight from the sheet description (only
    what is in the exposed part, text only when it is big enough to read)."""

    def __init__(self, view: SheetView) -> None:
        super().__init__()
        self._view = view
        self._pens: dict[tuple[str, float, tuple[float, float] | None, float], QPen] = {}
        self._fonts: dict[tuple[float, bool], QFont] = {}

    def boundingRect(self) -> QRectF:  # noqa: N802
        s = self._view.sheet
        return QRectF(0, 0, s.width, s.height) if s else QRectF()

    def _pen(self, color: str, width: float, dash: tuple[float, float] | None, lod: float) -> QPen:
        w = max(width, 0.6 / lod)  # a hairline stays visible when zoomed out
        key = (color, round(w, 4), dash, 0.0)
        pen = self._pens.get(key)
        if pen is None:
            pen = QPen(QColor(color), w)
            if dash:
                pen.setDashPattern([dash[0] / max(w, 0.1), dash[1] / max(w, 0.1)])
            self._pens[key] = pen
        return pen

    def _font(self, size: float, bold: bool) -> QFont:
        key = (size, bold)
        font = self._fonts.get(key)
        if font is None:
            font = self._view.theme.mono_font()
            font.setPixelSize(max(1, round(size * _TEXT_K)))
            font.setBold(bold)
            font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            self._fonts[key] = font
        return font

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        sheet = self._view.sheet
        geo = self._view.geometry_of_sheet
        if sheet is None or geo is None:
            return
        lod = option.levelOfDetailFromTransform(painter.worldTransform()) or 1.0
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(QRectF(0, 0, sheet.width, sheet.height), self._view.theme.color("paper"))
        expose = option.exposedRect.adjusted(-1, -1, 1, 1)
        for i, it in enumerate(sheet.items):
            if not geo.bounds[i].intersects(expose):
                continue
            if isinstance(it, Line):
                painter.setPen(self._pen(it.color, it.width, it.dash, lod))
                painter.drawLine(QPointF(it.x1, it.y1), QPointF(it.x2, it.y2))
            elif isinstance(it, Curve):
                painter.setPen(self._pen(it.color, it.width, None, lod))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(_curve_path(it))
            elif isinstance(it, Rect):
                painter.setPen(self._pen(it.color, it.width, it.dash, lod))
                painter.setBrush(QColor(it.fill) if it.fill else Qt.BrushStyle.NoBrush)
                painter.drawRect(QRectF(it.x, it.y, it.w, it.h))
            elif it.size * lod >= MIN_TEXT_PX:
                painter.save()
                painter.translate(it.left, it.y)
                painter.scale(1 / _TEXT_K, 1 / _TEXT_K)
                painter.setFont(self._font(it.size, it.bold))
                painter.setPen(QColor(it.color))
                painter.drawText(QPointF(0, 0), it.s)
                painter.restore()


class _Overlay(QGraphicsItem):
    """The hovered and the selected objects drawn again on top: the selection with a thick
    solid outline, the hover with a dashed one, so they differ without colour."""

    def __init__(self, view: SheetView) -> None:
        super().__init__()
        self._view = view
        self.setZValue(1)

    def boundingRect(self) -> QRectF:  # noqa: N802
        s = self._view.sheet
        return QRectF(0, 0, s.width, s.height) if s else QRectF()

    def paint(
        self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None
    ) -> None:
        sheet, geo = self._view.sheet, self._view.geometry_of_sheet
        if sheet is None or geo is None:
            return
        lod = option.levelOfDetailFromTransform(painter.worldTransform()) or 1.0
        theme = self._view.theme
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for keys, token, dashed in (
            (self._view.hover_keys, "focus", True),
            (self._view.selected_keys, "primary", False),
        ):
            colour = theme.color(token)
            for key in keys:
                for i in sheet.marks.get(key, []):
                    it = sheet.items[i]
                    if key[0] == "wire" and isinstance(it, Line | Curve):
                        halo = QColor(colour)
                        halo.setAlphaF(0.55)
                        width = max(it.width * 2.4, 3.0 / lod)
                        pen = QPen(halo, width)
                        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                        if dashed:
                            pen.setStyle(Qt.PenStyle.DashLine)
                        painter.setPen(pen)
                        if isinstance(it, Curve):
                            painter.setBrush(Qt.BrushStyle.NoBrush)
                            painter.drawPath(_curve_path(it))
                        else:
                            painter.drawLine(QPointF(it.x1, it.y1), QPointF(it.x2, it.y2))
                if key[0] != "wire":
                    rect = geo.area.get(key)
                    if rect is not None and not rect.isNull():
                        fill = QColor(colour)
                        fill.setAlphaF(0.14)
                        pen = QPen(colour, max(1.6 / lod, 0.5))
                        if dashed:
                            pen.setStyle(Qt.PenStyle.DashLine)
                        painter.setPen(pen)
                        painter.setBrush(fill)
                        painter.drawRect(rect)


class SheetView(QGraphicsView):
    """Draws one `Sheet` on a paper-coloured page (the `paper` token is white in both themes: it
    is a picture of paper) over the `pasteboard` token. Text is drawn in the monospace font, as in
    the exported drawing.

    Wheel (or Ctrl+wheel) zooms to the cursor, drag pans, `+` `-` zoom, `0` or `F` fits, Page Up
    and Page Down ask for the previous and next sheet. `hovered` and `clicked` say which drawn
    object the pointer is on; `set_hover` and `set_selected` draw objects given by `(kind, id)`."""

    hovered = Signal(str, str)  # kind, id of the object under the pointer ("", "" for none)
    clicked = Signal(str, str)  # kind, id of the object clicked ("", "" for empty paper)
    zoomChanged = Signal(float)  # times the fit-to-window size
    sheetStep = Signal(int)  # -1 / +1: the previous / next sheet was asked for

    def __init__(self, theme: ThemeManager | None = None) -> None:
        super().__init__()
        self.theme = theme or current_theme()
        self.theme.changed.connect(self._restyle)
        self.sheet: Sheet | None = None
        self.geometry_of_sheet: _Geometry | None = None
        self.hover_keys: tuple[Key, ...] = ()
        self.selected_keys: tuple[Key, ...] = ()
        self.zoom = 1.0  # relative to fit; 1.0 = fit to the window
        self._hover_hit: Key | None = None
        self._pan_from: QPointF | None = None
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._paper = _SheetItem(self)
        self._overlay = _Overlay(self)
        self._scene.addItem(self._paper)
        self._scene.addItem(self._overlay)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.MinimalViewportUpdate)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(240, 170)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAccessibleName(strings.PREVIEW_SHEET)
        self.setToolTip(strings.PREVIEW_HELP)
        self._restyle()
        self._scrollbars()

    # ---- content -------------------------------------------------------------------------
    def set_sheet(self, sheet: Sheet | None) -> None:
        self.sheet = sheet
        self.geometry_of_sheet = _Geometry(sheet) if sheet else None
        self._hover_hit = None
        self.hover_keys = ()
        self._scene.setSceneRect(QRectF(0, 0, sheet.width, sheet.height) if sheet else QRectF())
        self._paper.prepareGeometryChange()
        self._overlay.prepareGeometryChange()
        self._paper.update()
        self._overlay.update()
        self.fit()

    def set_selected(self, keys: Iterable[Key]) -> None:
        self.selected_keys = tuple(keys)
        self._overlay.update()

    def set_hover(self, keys: Iterable[Key]) -> None:
        self.hover_keys = tuple(keys)
        self._overlay.update()

    def has_object(self, key: Key) -> bool:
        return bool(self.sheet and key in self.sheet.marks)

    def object_rect(self, key: Key) -> QRectF | None:
        """Where an object sits on the sheet, in mm."""
        geo = self.geometry_of_sheet
        rect = geo.area.get(key) if geo else None
        return rect if rect is not None and not rect.isNull() else None

    def object_at(self, view_pos: QPointF) -> Key | None:
        """The drawn object under a point of the viewport (a wire first, then pin, connector)."""
        geo = self.geometry_of_sheet
        if geo is None:
            return None
        scene = self.mapToScene(view_pos.toPoint())
        return geo.pick(scene, HIT_PX / max(self._scale(), 1e-6))

    def reveal(self, key: Key) -> None:
        """Scroll so that the object is in view (zoomed in only)."""
        rect = self.object_rect(key)
        if rect is not None and self.zoom > 1.0:
            self.ensureVisible(rect, 40, 40)

    # ---- zoom ----------------------------------------------------------------------------
    def _scale(self) -> float:
        return float(self.transform().m11())

    def _fit_scale(self) -> float:
        s = self.sheet
        if s is None:
            return 1.0
        size = self.viewport().size()
        return max(0.01, min((size.width() - 8) / s.width, (size.height() - 8) / s.height))

    def _scrollbars(self) -> None:
        policy = (
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            if self.zoom <= 1.0
            else Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.setHorizontalScrollBarPolicy(policy)
        self.setVerticalScrollBarPolicy(policy)

    def _apply(self, zoom: float, anchor: QPointF | None = None) -> None:
        """Set the zoom (times the fit size). With `anchor`, a point of the viewport, the part of
        the sheet under it stays under it."""
        zoom = max(1.0, min(MAX_ZOOM, zoom))
        self.zoom = zoom
        self._scrollbars()
        scale = self._fit_scale() * zoom
        held = self.mapToScene(anchor.toPoint()) if anchor is not None else None
        self.setTransform(self.transform().fromScale(scale, scale))
        if zoom <= 1.0 and self.sheet:
            self.centerOn(self.sheet.width / 2, self.sheet.height / 2)
        elif held is not None and anchor is not None:
            moved = self.mapToScene(anchor.toPoint()) - held
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - round(moved.x() * scale)
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - round(moved.y() * scale)
            )
        self.zoomChanged.emit(zoom)

    def fit(self) -> None:
        self._apply(1.0)

    def zoom_to(self, zoom: float) -> None:
        self._apply(zoom, QPointF(self.viewport().rect().center()))

    def zoom_in(self) -> None:
        self.zoom_to(self.zoom * 1.25)

    def zoom_out(self) -> None:
        self.zoom_to(self.zoom / 1.25)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        if self.zoom <= 1.0:
            self._apply(1.0)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        steps = event.angleDelta().y() / 120.0
        if steps == 0:
            super().wheelEvent(event)
            return
        old = self.zoom
        self._apply(old * math.pow(1.2, steps), event.position())
        event.accept()

    # ---- pointer and keys ----------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        pos = event.position()
        if event.button() == Qt.MouseButton.LeftButton:
            hit = self.object_at(pos)
            if hit is not None:
                self.clicked.emit(*hit)
                event.accept()
                return
            self.clicked.emit("", "")
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._pan_from = pos
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position()
        if self._pan_from is not None:
            delta = pos - self._pan_from
            self._pan_from = pos
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - round(delta.x())
            )
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - round(delta.y()))
            event.accept()
            return
        hit = self.object_at(pos)
        if hit != self._hover_hit:
            self._hover_hit = hit
            self.viewport().setCursor(
                Qt.CursorShape.PointingHandCursor if hit else Qt.CursorShape.ArrowCursor
            )
            self.hovered.emit(*(hit or ("", "")))
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._pan_from is not None:
            self._pan_from = None
            self.viewport().setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        if self._hover_hit is not None:
            self._hover_hit = None
            self.hovered.emit("", "")
        super().leaveEvent(event)  # type: ignore[arg-type]

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
            self.zoom_out()
        elif key in (Qt.Key.Key_0, Qt.Key.Key_F):
            self.fit()
        elif key == Qt.Key.Key_PageUp:
            self.sheetStep.emit(-1)
        elif key == Qt.Key.Key_PageDown:
            self.sheetStep.emit(1)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def drawForeground(self, painter: QPainter, rect: QRectF | QRect) -> None:  # noqa: N802
        if self.hasFocus():  # the keyboard focus ring (the sheet itself has no widget frame)
            painter.save()
            painter.resetTransform()
            pen = QPen(self.theme.color("focus"), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.viewport().rect().adjusted(1, 1, -1, -1))
            painter.restore()

    def focusInEvent(self, event: object) -> None:  # noqa: N802
        super().focusInEvent(event)  # type: ignore[arg-type]
        self.viewport().update()

    def focusOutEvent(self, event: object) -> None:  # noqa: N802
        super().focusOutEvent(event)  # type: ignore[arg-type]
        self.viewport().update()

    def _restyle(self) -> None:
        self.setBackgroundBrush(self.theme.color("pasteboard"))
        self.viewport().update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(480, 340)


class DrawingPreview(QWidget):
    """Sheet view with zoom buttons and previous / next buttons for multi-sheet harnesses.

    `show_harness(project, harness)` draws the sheets itself; `set_sheets(sheets)` takes sheets that
    were drawn elsewhere (in a worker). `set_selected` and `set_hover` take `(kind, id)` keys and
    show the sheet that has them; `hovered` and `clicked` pass the view's signals on."""

    pageChanged = Signal(int, int)  # page, total
    hovered = Signal(str, str)
    clicked = Signal(str, str)

    def __init__(self, theme: ThemeManager | None = None) -> None:
        super().__init__()
        theme = theme or current_theme()
        self.setObjectName("drawing-preview")
        self.sheets: list[Sheet] = []
        self.page = 0
        self._selected: tuple[Key, ...] = ()
        self._empty_text = strings.PREVIEW_NONE
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        row = QHBoxLayout()
        self.zoom_out_btn, self.zoom_in_btn, self.fit_btn = (
            QToolButton(),
            QToolButton(),
            QToolButton(),
        )
        for b, name, label, key, oid in (
            (self.zoom_out_btn, "zoom-out", strings.ZOOM_OUT, "-", "preview-zoom-out"),
            (self.zoom_in_btn, "zoom-in", strings.ZOOM_IN, "+", "preview-zoom-in"),
            (self.fit_btn, "fit", strings.FIT, "0", "preview-fit"),
        ):
            icons.icon_button(b, name, theme, label, key)
            b.setObjectName(oid)
            row.addWidget(b)
        self.zoom_label = QLabel()
        self.zoom_label.setObjectName("preview-zoom")
        self.zoom_label.setProperty("muted", True)
        row.addWidget(self.zoom_label)
        row.addStretch(1)
        self.prev = QPushButton()
        self.prev.setObjectName("preview-prev")
        icons.icon_button(
            self.prev,
            "chevron-left",
            theme,
            strings.PREVIEW_PREV,
            "PgUp",
            text=strings.PREVIEW_PREV,
        )
        self.label = QLabel()
        self.label.setObjectName("preview-label")
        self.label.setProperty("muted", True)
        self.next = QPushButton()
        self.next.setObjectName("preview-next")
        icons.icon_button(
            self.next,
            "chevron-right",
            theme,
            strings.PREVIEW_NEXT,
            "PgDn",
            text=strings.PREVIEW_NEXT,
        )
        row.addWidget(self.prev)
        row.addWidget(self.label)
        row.addWidget(self.next)
        lay.addLayout(row)
        self.view = SheetView(theme)
        self.view.setObjectName("drawing-sheet")
        lay.addWidget(self.view, 1)
        self.zoom_out_btn.clicked.connect(self.view.zoom_out)
        self.zoom_in_btn.clicked.connect(self.view.zoom_in)
        self.fit_btn.clicked.connect(self.view.fit)
        self.prev.clicked.connect(lambda: self.go(-1))
        self.next.clicked.connect(lambda: self.go(1))
        self.view.sheetStep.connect(self.go)
        self.view.hovered.connect(self.hovered)
        self.view.clicked.connect(self.clicked)
        self.view.zoomChanged.connect(self._zoom_text)
        self.setFocusProxy(self.view)
        self.show_harness(None, None)

    def _zoom_text(self, zoom: float) -> None:
        self.zoom_label.setText(strings.PREVIEW_ZOOM_FIT if zoom <= 1.0 else f"{zoom:.1f}×")

    def show_harness(self, project: Project | None, h: Harness | None) -> None:
        if project is None or h is None:
            self.set_sheets([])
        else:
            self.set_sheets(harness_sheets(project, h, Stamp("preview", "preview"), "A3"))

    def set_sheets(self, sheets: Sequence[Sheet], empty_text: str | None = None) -> None:
        """Show these sheets; with none, the label says `empty_text` (default: select a harness)."""
        self.sheets = list(sheets)
        self._empty_text = empty_text or strings.PREVIEW_NONE
        self.page = max(0, min(self.page, len(self.sheets) - 1))
        self._refresh()

    def go(self, step: int) -> None:
        old = self.page
        self.page = max(0, min(len(self.sheets) - 1, self.page + step))
        if self.page != old:
            self._refresh()

    def set_page(self, page: int) -> None:
        self.go(page - self.page)

    def _refresh(self) -> None:
        n = len(self.sheets)
        self.view.set_sheet(self.sheets[self.page] if n else None)
        self.view.set_selected(self._selected)
        self.label.setText(strings.PREVIEW_PAGE.format(self.page + 1, n) if n else self._empty_text)
        self.prev.setEnabled(self.page > 0)
        self.next.setEnabled(self.page < n - 1)
        self.prev.setToolTip(
            strings.PREVIEW_PREV + " (PgUp)" if self.page > 0 else strings.PREVIEW_FIRST
        )
        self.next.setToolTip(
            strings.PREVIEW_NEXT + " (PgDn)" if self.page < n - 1 else strings.PREVIEW_LAST
        )
        for b in (self.zoom_in_btn, self.zoom_out_btn, self.fit_btn):
            b.setEnabled(bool(n))
        self._zoom_text(self.view.zoom)
        self.pageChanged.emit(self.page + 1, n)

    def page_with(self, keys: Iterable[Key]) -> int | None:
        """The first sheet (0-based) that draws one of the objects, the current one first."""
        wanted = list(keys)
        order = [i for i in (self.page,) if i < len(self.sheets)]  # (no sheets yet: none)
        order += [i for i in range(len(self.sheets)) if i != self.page]
        for i in order:
            if any(k in self.sheets[i].marks for k in wanted):
                return i
        return None

    def set_selected(self, keys: Iterable[Key]) -> None:
        """Select drawn objects and show the sheet they are on."""
        self._selected = tuple(keys)
        target = self.page_with(self._selected)
        if target is not None and target != self.page:
            self.set_page(target)
        else:
            self.view.set_selected(self._selected)
        if self._selected:
            self.view.reveal(self._selected[0])

    def set_hover(self, keys: Iterable[Key]) -> None:
        self.view.set_hover(keys)


__all__ = ["DrawingPreview", "SheetView", "text_width"]
