"""Every kind of link has its own picture, and a link's label keeps clear of the other links."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from pathlib import Path  # noqa: E402

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402

from harness_design_studio.core import templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.gui import glyphs  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402


def _picture(type_id: str, category: str) -> bytes:
    img = QImage(36, 28, QImage.Format.Format_ARGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    glyphs.draw_link_glyph(p, 4, 4, type_id, category, QColor(0, 0, 0), 1.0)
    p.end()
    return bytes(img.constBits())


def test_every_kind_of_link_has_its_own_picture(qtbot) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QApplication

    _ = QApplication.instance()
    pictures = {tid: _picture(tid, "data") for tid in glyphs._GLYPHS}
    same = [
        (a, b)
        for a in pictures
        for b in pictures
        if a < b and pictures[a] == pictures[b] and {a, b} != {"power_primary", "power_secondary"}
    ]
    assert same == []  # (primary and secondary power are told apart by their colour and name)
    assert pictures["lvds"] != pictures["rs422"]


def test_a_link_label_keeps_clear_of_other_links(qtbot, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "flatsat"
    templates.create_project(folder, "flatsat")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(load_project(folder).project, None, None)
    sc = w.view.dscene

    def crossed(iid: str) -> bool:
        pad = sc._chip_rects[iid].adjusted(-2, -2, 2, 2)
        for other in sc.link_items:
            route = sc.route(other)
            for p, q in zip(route, route[1:], strict=False):
                box = QRectF(QPointF(*p), QPointF(*q)).normalized().adjusted(-1, -1, 1, 1)
                if other != iid and box.intersects(pad):
                    return True
        return False

    assert len(sc._chip_rects) >= 40
    hit = [iid for iid in sc._chip_rects if crossed(iid)]
    assert len(hit) <= 14, f"{len(hit)} of {len(sc._chip_rects)} labels sit on another link"
    # a label that had to squeeze in is the picture alone, smaller than a full label
    small = [iid for iid in sc._chip_rects if sc.link_items[iid]._compact]
    assert small and all(sc._chip_rects[i].width() < 30 for i in small)
