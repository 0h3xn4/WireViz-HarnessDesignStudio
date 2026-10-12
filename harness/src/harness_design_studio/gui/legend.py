"""The key under the diagram: every kind of link and connector in the project, drawn."""

from typing import cast

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

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
        )
        self.project = project
        if sig != self._signature:
            self._signature = sig
            self._layout(self.width())
            self.update()

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
        out += [
            ("line", "nominal", strings.NOMINAL),
            ("line", "redundant", strings.REDUNDANT),
            ("auto", None, strings.AUTO_LEGEND),
            (
                "gender",
                None,
                strings.LEGEND_GENDER,
            ),
        ]
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
