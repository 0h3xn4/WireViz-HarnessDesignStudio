# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""A dense diagram stays readable: units never overlap, a link leaves on the edge that faces its
other end, the links on one edge are ordered by the height of their other ends, and a selection
puts its links in focus while everything else fades."""

from pathlib import Path

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtTest import QTest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.core import routing, templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.samples import sat15  # noqa: E402
from harness_design_studio.gui.canvas import W  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path: Path):  # type: ignore[no-untyped-def]
    folder = tmp_path / "flatsat"
    templates.create_project(folder, "flatsat")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(load_project(folder).project, None, None)
    return w


@pytest.mark.parametrize("mode", ["guided", "expert"])
def test_units_never_overlap_in_either_mode(win, mode) -> None:
    win.ctl.set_mode(mode)
    items = list(win.view.dscene.unit_items.values())
    boxes = [(it.unit_id, it.sceneBoundingRect().adjusted(14, 30, -14, -70)) for it in items]
    for k, (a, ra) in enumerate(boxes):
        for b, rb in boxes[k + 1 :]:
            assert not ra.intersects(rb), (a, b, mode)


@pytest.mark.parametrize("mode", ["guided", "expert"])
def test_a_link_leaves_on_the_edge_that_faces_its_other_end(win, mode) -> None:
    win.ctl.set_mode(mode)
    scene = win.view.dscene
    checked = 0
    for i in win.ctl.project.interfaces.values():
        a, b = (scene.unit_items[e.unit_id] for e in i.endpoints)
        if a.lane() == b.lane():
            continue
        left, right = (a, b) if a.lane() < b.lane() else (b, a)
        ends = {e.unit_id: e.connector_id for e in i.endpoints}
        assert left.anchor(ends[left.unit_id], i.id).x() == left.pos().x() + W, i.id
        assert right.anchor(ends[right.unit_id], i.id).x() == right.pos().x(), i.id
        checked += 1
    assert checked > 20  # the flatsat has many links between lanes


def test_connectors_are_drawn_where_their_link_leaves(win) -> None:
    win.ctl.set_mode("expert")
    scene = win.view.dscene
    obc = scene.unit_items["OBC1"]
    sides = set()
    for k, c in enumerate(obc.connectors()):
        iid = scene.connector_link(c.id)
        side = obc.link_side(iid) if iid else obc.side()
        assert obc.port_rect(k, c.id).x() == (W - 7 if side == "right" else -7)
        sides.add(side)
    assert sides == {"left", "right"}  # the computer has links to units on both sides


def test_links_on_one_edge_are_ordered_by_the_height_of_their_other_ends(win) -> None:
    scene = win.view.dscene
    for uid, item in scene.unit_items.items():
        for edge in ("left", "right"):
            ids = [
                (iid, scene.partner_item(uid, iid).pos().y())
                for iid in scene.adjacent(uid)
                if item.link_side(iid) == edge
            ]
            expected = routing.order_links(ids)
            ys = [item.anchor(None, iid).y() for iid in expected]
            assert ys == sorted(ys), (uid, edge)


def test_a_selected_unit_puts_its_links_in_focus_and_fades_the_rest(win) -> None:
    scene = win.view.dscene
    assert all(link.opacity() == 1.0 for link in scene.link_items.values())
    win.ctl.select("unit", "PDU2")
    links, units = routing.focus(win.ctl.project, "unit", "PDU2")
    assert links and "PDU2" in units
    for iid, link in scene.link_items.items():
        assert (link.opacity() == 1.0) == (iid in links), iid
    for uid, item in scene.unit_items.items():
        assert (item.opacity() == 1.0) == (uid in units), uid
    win.ctl.select(None)
    assert all(link.opacity() == 1.0 for link in scene.link_items.values())
    assert all(item.opacity() == 1.0 for item in scene.unit_items.values())


def test_a_selected_interface_puts_only_itself_and_its_units_in_focus(win) -> None:
    scene = win.view.dscene
    iid = sorted(scene.link_items)[0]
    win.ctl.select("interface", iid)
    assert [i for i, link in scene.link_items.items() if link.opacity() == 1.0] == [iid]
    ends = {e.unit_id for e in win.ctl.project.interfaces[iid].endpoints}
    assert {u for u, item in scene.unit_items.items() if item.opacity() == 1.0} == ends


def test_the_focus_and_the_show_filter_work_together(win) -> None:
    scene = win.view.dscene
    win.ctl.select("unit", "OBC1")
    focus_links, _ = routing.focus(win.ctl.project, "unit", "OBC1")
    scene.set_category_filter("power")
    keep = scene.matching_interfaces()
    assert keep is not None
    for iid, link in scene.link_items.items():
        assert (link.opacity() == 1.0) == (iid in keep and iid in focus_links), iid
    scene.set_category_filter(None)
    for iid, link in scene.link_items.items():
        assert (link.opacity() == 1.0) == (iid in focus_links), iid


def test_a_click_on_the_background_or_escape_ends_the_focus(win) -> None:
    scene = win.view.dscene
    win.view.fit()
    win.ctl.select("unit", "OBC1")
    assert win.ctl.selection is not None
    empty = win.view.mapFromScene(QPointF(scene.zone_items[3].pos().x() + 380, 60))
    QTest.mouseClick(win.view.viewport(), Qt.MouseButton.LeftButton, pos=empty)
    assert win.ctl.selection is None
    assert all(link.opacity() == 1.0 for link in scene.link_items.values())
    win.ctl.select("unit", "OBC1")
    win.view.setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Escape)
    assert win.ctl.selection is None


def test_every_kind_of_link_and_connector_has_its_own_picture(win) -> None:
    """Meaning is drawn, not spelled: each link type and connector family gets a distinct,
    non-empty picture."""
    from PySide6.QtGui import QColor, QImage, QPainter

    from harness_design_studio.gui import glyphs

    def render(draw) -> bytes:  # type: ignore[no-untyped-def]
        img = QImage(40, 24, QImage.Format.Format_ARGB32)
        img.fill(QColor("white"))
        p = QPainter(img)
        draw(p)
        p.end()
        return bytes(img.constBits())

    blank = render(lambda p: None)
    types = win.ctl.project.interface_types
    pictures = {
        tid: render(
            lambda p, t=t: glyphs.draw_link_glyph(p, 4, 4, t.id, t.category, QColor("black"))
        )
        for tid, t in types.items()
    }
    assert all(pic != blank for pic in pictures.values())
    assert len(set(pictures.values())) >= len(pictures) - 2  # a few related types may share one
    shapes = {
        fam: render(
            lambda p, f=fam: glyphs.draw_connector(
                p, 4, 4, f, 9, "male", QColor("black"), QColor("white")
            )
        )
        for fam in ("dsub", "microd", "circular", "rj45", "coax", "generic")
    }
    assert len(set(shapes.values())) == len(shapes)


def test_the_key_lists_what_the_project_uses(win) -> None:
    entries = win.legend._entries()
    labels = {label for _kind, _p, label in entries}
    assert {"CAN", "Primary power", "Ethernet"} <= labels
    assert any(kind == "conn" for kind, _p, _l in entries)


@pytest.mark.parametrize("right", [False, True])
@pytest.mark.parametrize("count", [False, True])
def test_a_port_row_stays_inside_its_half(right, count) -> None:
    """Nothing in a port row may touch the line down the middle or leave the unit."""
    from harness_design_studio.gui import glyphs

    row = glyphs.port_row(W, right, count)
    assert glyphs.row_fits(W, row, right), row
    spans = sorted(row.values())
    assert all(a[1] <= b[0] + 0.01 for a, b in zip(spans, spans[1:], strict=False)), (
        spans
    )  # no overlap


def test_tab_walks_the_units_and_links_and_then_leaves_the_diagram(win) -> None:
    view = win.view
    order = view.focus_order()
    units = [it for it in order if hasattr(it, "unit_id")]
    assert len(units) == len(view.dscene.unit_items) and len(order) > len(units)
    seen = []
    while view.step_focus():
        seen.append(view.dscene.focusItem())
    assert seen == order  # every unit, then every link, once each
    assert not view.step_focus()  # past the last: Tab goes on to the next control
    assert view.step_focus(backwards=True)  # Shift+Tab goes back one
    assert view.dscene.focusItem() is order[-2]


def test_the_first_run_tour_is_not_shown_again_after_skipping_it(win) -> None:
    win.settings.setValue("tour/done", False)
    win.tour.start()
    assert win.tour.active
    win.tour.skip.click()
    assert not win.tour.active and win.settings.value("tour/done", False, bool) is True


def test_clicking_the_active_mode_button_keeps_it_checked(win) -> None:
    win.mode_guided.click()
    assert win.mode_guided.isChecked() and not win.mode_expert.isChecked()
    win.mode_expert.click()
    win.mode_expert.click()
    assert win.mode_expert.isChecked() and not win.mode_guided.isChecked()


def test_a_unit_with_no_free_connector_is_not_told_to_do_the_impossible() -> None:
    from harness_design_studio.core import edit

    p = sat15()
    hints = [
        c.why
        for uid in p.units
        for tid in p.interface_types
        for c in [edit.unit_compat(p, tid, uid)]
        if not c.ok and "no free" in c.why
    ]
    assert hints and all("Switch to Expert mode" not in h for h in hints)
