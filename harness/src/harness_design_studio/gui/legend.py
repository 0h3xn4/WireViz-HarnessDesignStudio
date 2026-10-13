"""The key to the diagram: every kind of link and connector the project uses, drawn. It is an
overlay in a corner of the canvas that can be switched off (View > Show legend) or folded."""

from typing import cast

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QFrame, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from harness_design_studio.core import describe
from harness_design_studio.core.model.project import Project
from harness_design_studio.gui import glyphs, strings
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.gui.tokens import CATEGORIES, style_category

ROW = 26
GAP = 18


class LegendBar(QWidget):
    def __init__(self, theme: ThemeManager) -> None:
        super().__init__()
        self.setObjectName("legend")
        self.theme = theme
        self.project: Project | None = None
        self._signature: object = None
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName(strings.LEGEND_NAME)
        theme.changed.connect(self.update)

    def set_project(self, project: Project) -> None:
        """Remember the project and redraw only when the kinds shown changed."""
        sig = (
            sorted((t.id, t.name, t.category) for t in project.interface_types.values()),
            sorted(describe.connector_family(project, cid)[0] for cid in project.all_connectors()),
            sorted({i.type_id for i in project.interfaces.values()}),  # the kinds drawn
            self._extras(project),
        )
        self.project = project
        if sig != self._signature:
            self._signature = sig
            self._layout(self.width())
            self.update()

    @staticmethod
    def _extras(p: Project) -> tuple[bool, bool, bool]:
        """(a redundant chain is drawn, a connector was filled in by the tool, genders are known):
        the entries that only mean something when the diagram shows them."""
        redundant = any(i.redundancy == "redundant" for i in p.interfaces.values()) or any(
            u.side == "redundant" for u in p.units.values()
        )
        auto = any(e.auto for i in p.interfaces.values() for e in i.endpoints)
        genders = any(describe.connector_family(p, cid)[2] for cid in p.all_connectors())
        return redundant, auto, genders

    # ---- entries: (kind, payload, label), laid out in rows ------------------------------------
    def _entries(self) -> list[tuple[str, object, str]]:
        out: list[tuple[str, object, str]] = []
        p = self.project
        if p is None:
            return out
        order = list(CATEGORIES)
        used_types = {i.type_id for i in p.interfaces.values()}
        types = [t for t in p.interface_types.values() if t.id in used_types]
        types.sort(key=lambda t: (order.index(style_category(t.category)), t.name))
        out += [("link", (t.id, t.category), t.name) for t in types]
        families = sorted(
            {describe.connector_family(p, cid)[0] for cid in p.all_connectors()},
            key=list(describe.FAMILY_LABEL).index,
        )
        out += [("conn", f, describe.FAMILY_LABEL[f]) for f in families]
        redundant, auto, genders = self._extras(p)
        if redundant:  # nominal and redundant lines mean nothing without a redundant chain
            out += [
                ("line", "nominal", strings.NOMINAL),
                ("line", "redundant", strings.REDUNDANT),
            ]
        if auto:
            out.append(("auto", None, strings.AUTO_LEGEND))
        if genders:
            out.append(("gender", None, strings.LEGEND_GENDER))
        return out

    def _font(self) -> QFont:
        f = QFont(self.font())
        f.setPixelSize(self.theme.px(11))
        return f

    def _positions(self, width: int) -> tuple[list[tuple[float, float, float]], int]:
        fm = QFontMetrics(self._font())
        x = y = 0.0
        out = []
        for kind, _payload, label in self._entries():
            icon = {
                "conn": glyphs.CONNECTOR_W,
                "gender": 2 * (glyphs.CONNECTOR_W + 2),
            }.get(kind, 26.0)
            w = icon + 6 + fm.horizontalAdvance(label)
            if x and x + w > width:
                x, y = 0.0, y + ROW
            out.append((x, y, w))
            x += w + GAP
        return out, int(y + ROW + 4)

    def _layout(self, width: int) -> None:
        self.setFixedHeight(self._positions(max(width, 200))[1])

    def resizeEvent(self, event: object) -> None:
        self._layout(self.width())

    def paintEvent(self, event: QPaintEvent) -> None:
        th = self.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self._font())
        positions, _ = self._positions(self.width())
        for (kind, payload, label), (x, y, _w) in zip(self._entries(), positions, strict=True):
            cy = y + ROW / 2
            icon = 26.0
            if kind == "link":
                tid, cat = cast(tuple[str, str], payload)
                colour = th.color(f"cat-{style_category(cat)}")
                glyphs.draw_link_glyph(p, x + 4, cy - 7, tid, cat, colour)
            elif kind == "conn":
                icon = glyphs.CONNECTOR_W
                glyphs.draw_connector(
                    p, x, cy - 11, str(payload), 15, "female", th.color("text"), th.color("bg")
                )
            elif kind == "gender":
                icon = 2 * (glyphs.CONNECTOR_W + 2)
                for k, g in enumerate(("male", "female")):
                    gx = x + k * (glyphs.CONNECTOR_W + 2)
                    glyphs.draw_connector(
                        p, gx, cy - 11, "dsub", 15, g, th.color("text"), th.color("bg")
                    )
            elif kind == "line":
                pen = QPen(th.color("text"), 2)
                if payload == "redundant":
                    pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.drawLine(int(x), int(cy), int(x + 22), int(cy))
            elif kind == "auto":
                p.setPen(QPen(th.color("auto-fill"), 2, Qt.PenStyle.DashLine))
                p.drawRoundedRect(QRectF(x + 4, cy - 6, 14, 12), 3, 3)
            p.setPen(th.color("auto-fill") if kind == "auto" else th.color("text"))
            room = max(20.0, self.width() - (x + icon + 6) - 4)
            text = p.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(room))
            p.drawText(QRectF(x + icon + 6, y, room + 4, ROW), Qt.AlignmentFlag.AlignVCenter, text)
        p.end()


class LegendOverlay(QFrame):
    """The legend as a card in the bottom left corner of the canvas, with a button that folds it
    to one line (it starts folded in a short window, where it would hide the diagram)."""

    def __init__(self, theme: ThemeManager, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("legend-overlay")
        self.setProperty("card", True)
        self.setAccessibleName(strings.LEGEND_NAME)
        self.bar = LegendBar(theme)
        self.toggle = QToolButton()
        self.toggle.setObjectName("legend-toggle")
        self.toggle.setCheckable(True)
        self.toggle.setToolTip(strings.LEGEND_TOGGLE_TIP)
        self.toggle.setAccessibleName(strings.LEGEND_TOGGLE_NAME)
        self.toggle.setAutoRaise(True)
        self.toggle.clicked.connect(self._clicked)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(2)
        lay.addWidget(self.toggle, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addWidget(self.bar)
        self.user_choice: bool | None = None  # None: follows the height of the window
        self._room = 0
        self._width = 360
        self._set_open(True)

    def set_project(self, project: Project) -> None:
        self.bar.set_project(project)
        self._fit()

    @property
    def is_open(self) -> bool:
        return self.toggle.isChecked()

    def _set_open(self, open_: bool) -> None:
        self.toggle.setChecked(open_)
        self.toggle.setText(("▾ " if open_ else "▸ ") + strings.LEGEND_TITLE)
        self.bar.setVisible(open_)

    def _clicked(self) -> None:
        self.user_choice = self.toggle.isChecked()
        self._set_open(self.toggle.isChecked())
        self._fit()
        self.place(self._area, self._width)

    _area = QRect(0, 0, 400, 300)

    def place(self, area: QRect, width: int) -> None:
        """Put the card in the bottom left of `area`, at most `width` wide. Starts folded when the
        area is short, unless the person opened it."""
        self._area, self._width = area, width
        if self.user_choice is None:
            from harness_design_studio.gui.canvas import METRICS

            want = area.height() >= METRICS.legend_collapse_below
            if want != self.toggle.isChecked():
                self._set_open(want)
        self._fit()
        self.move(area.left() + 12, area.bottom() - self.height() - 12)

    def _fit(self) -> None:
        inner = max(120, self._width - 14)
        self.bar.setFixedWidth(inner)
        self.bar._layout(inner)
        self.setFixedWidth(self._width if self.is_open else min(self._width, 160))
        self.adjustSize()
