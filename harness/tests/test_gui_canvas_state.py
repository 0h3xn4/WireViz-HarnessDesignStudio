# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""The canvas says what is wrong, pending, unchecked, auto-filled and locked (UX audit CV-6, CV-7,
CV-8, CV-10, CV-19, CV-21, CV-22, CV-23): badges on every unit card and link label, the lock and
"W001 A" of a release, "V ?" for a missing value, the picture and tags of a card, link tooltips,
far-zoom markers, the corner chip and the Why? entries. Driven offscreen on the flatsat example;
the pixel tests paint the real items into an image."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import QPointF, QRectF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyleOptionGraphicsItem  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import describe, templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.gui import canvas_badges, strings  # noqa: E402
from harness_design_studio.gui.canvas import (  # noqa: E402
    FAR_DASHES,
    METRICS,
    W,
    fit_groups,
)
from harness_design_studio.gui.canvas_state import NO_INDEX  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.helpers import time_limit  # noqa: E402
from tests.ux_rel import collect, flatsat_controller, release_all  # noqa: E402

LEFT = Qt.MouseButton.LeftButton


@pytest.fixture
def win(qtbot, tmp_path: Path):
    folder = tmp_path / "flatsat"
    templates.create_project(folder, "flatsat")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(load_project(folder).project, None, None)
    w.view.fit()
    QApplication.processEvents()
    w.ctl.run_drc_now()
    return w


@pytest.fixture
def released(qtbot, tmp_path: Path):
    """The flatsat with W001 exported and released (read from the folder it was saved to)."""
    ctl = flatsat_controller(tmp_path / "src")
    assert release_all(ctl, ["W001"]) == ["W001"]
    ctl.save()
    ctl.release()
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    assert ctl.root is not None
    w.ctl.open_path(ctl.root)
    w.view.fit()
    QApplication.processEvents()
    w.ctl.run_drc_now()
    return w


@pytest.fixture
def plain(qtbot, tmp_path: Path):
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    QApplication.processEvents()
    return w


def render_unit(win, uid: str, *, dx: float = 30.0, dy: float = 40.0) -> QImage:
    """The real unit item painted at 100 % into an image (its top left corner at (dx, dy))."""
    item = win.view.dscene.unit_items[uid]
    img = QImage(int(W + 2 * dx), int(item.height() + 2 * dy), QImage.Format.Format_ARGB32)
    img.fill(win.theme.color("bg"))
    p = QPainter(img)
    p.translate(dx, dy)
    opt = QStyleOptionGraphicsItem()
    opt.exposedRect = item.boundingRect()
    item.paint(p, opt, None)
    p.end()
    return img


def count_colour(img: QImage, rect: QRectF, colour: QColor, *, tol: int = 70) -> int:
    """How many pixels of `rect` (item coordinates) are close to `colour`."""
    n = 0
    for x in range(int(rect.left()), int(rect.right()) + 1):
        for y in range(int(rect.top()), int(rect.bottom()) + 1):
            c = QColor(img.pixel(x + 30, y + 40))
            if (
                abs(c.red() - colour.red())
                + abs(c.green() - colour.green())
                + abs(c.blue() - colour.blue())  # fmt: skip
                <= tol
            ):
                n += 1
    return n


def layout_of(win, uid: str):
    item = win.view.dscene.unit_items[uid]
    render_unit(win, uid)  # (a paint builds the layout of the marks)
    return item._card_cache


def scroll_to(win, kind: str, ident: str, zoom: float = 1.0) -> None:
    win.view._apply_scale(zoom)
    win.view.center_on_object(kind, ident)
    QApplication.processEvents()


# ---- CV-6: badges on unit cards ------------------------------------------------------------------------


def test_the_state_index_comes_from_the_controller_and_follows_the_check(win) -> None:
    scene = win.view.dscene
    assert scene.states is win.ctl.state_index()
    assert scene.states.of("unit", "HTR1").warnings >= 1  # the lookalike connectors of the audit
    assert scene.states.checked


def test_a_unit_with_findings_paints_a_warning_badge_and_one_without_paints_none(win) -> None:
    scene = win.view.dscene
    card = layout_of(win, "HTR1")
    (rect, state, text), *_ = card.badges
    assert state == "warning" and text == str(scene.states.of("unit", "HTR1").warnings)
    colour = win.theme.color("warning")
    with_badge = count_colour(render_unit(win, "HTR1"), rect, colour)
    scene.states = NO_INDEX  # the same unit when the index knows nothing
    without = count_colour(render_unit(win, "HTR1"), rect, colour)
    assert with_badge >= 8 and without == 0


def test_a_badge_is_icon_plus_count_not_colour_alone(win) -> None:
    card = layout_of(win, "HTR1")
    rect, state, text = card.badges[0]
    assert text and rect.width() > canvas_badges.PAD * 2 + canvas_badges.ICON  # room for the count
    # the icon is drawn in the badge: the unit with the badge differs from the one without even
    # where the colour is ignored (compare light/dark values of the badge area)
    img = render_unit(win, "HTR1")
    win.view.dscene.states = NO_INDEX
    bare = render_unit(win, "HTR1")
    changed = sum(
        1
        for x in range(int(rect.left()), int(rect.right()))
        for y in range(int(rect.top()), int(rect.bottom()))
        if img.pixel(x + 30, y + 40) != bare.pixel(x + 30, y + 40)
    )
    assert changed > 20


def test_every_unit_card_has_a_state_mark_on_the_flatsat(win) -> None:
    """The audit counted 28 problems and no badge anywhere. Every unit has at least one mark now
    (a warning, a pending value or an auto-filled connector)."""
    scene = win.view.dscene
    assert all(not scene.states.of("unit", u).clear for u in win.ctl.project.units)


def test_before_the_first_check_every_card_says_not_checked_and_then_it_goes(plain) -> None:
    scene = plain.view.dscene
    scene.refresh_states()
    uid = next(iter(plain.ctl.project.units))
    assert not scene.states.checked
    assert ("not-checked", 1) in scene.states.of("unit", uid).badges()
    card = layout_of(plain, uid)
    assert [s for _r, s, _t in card.badges] == ["not-checked"]
    plain.ctl.run_drc_now()  # the result arrives: drcChanged
    assert scene.states.checked
    assert ("not-checked", 1) not in scene.states.of("unit", uid).badges()


def test_only_the_objects_whose_marks_changed_are_repainted(win) -> None:
    scene = win.view.dscene
    index = win.ctl.state_index()
    f = next(x for x in win.ctl.open_findings() if x.can_waive and x.severity == "warning")
    expected = {k for k in index.keys() if f.id in index.finding_ids(*k)}  # noqa: SIM118 (an index, not a dict)
    assert expected  # the waived finding is counted on a unit
    assert win.ctl.waive(f, "accepted for this test of the badges")
    updated: set[tuple[str, str]] = set()
    for uid, unit in scene.unit_items.items():
        unit.update = lambda _u=uid: updated.add(("unit", _u))  # type: ignore[method-assign]
    for iid, link in scene.link_items.items():
        link.update = lambda _i=iid: updated.add(("interface", _i))  # type: ignore[method-assign]
    scene.refresh_states()
    assert updated == expected, updated


def test_painting_never_rebuilds_the_index(win, monkeypatch) -> None:
    calls: list[int] = []
    real = win.ctl.state_index

    def counting():  # type: ignore[no-untyped-def]
        calls.append(1)
        return real()

    monkeypatch.setattr(win.ctl, "state_index", counting)
    win.view.viewport().repaint()
    win.view.grab()
    win.view.dscene.update()
    QApplication.processEvents()
    assert calls == []


def test_an_edit_rebuilds_the_marks_once_a_moment_later_not_inside_the_edit(win) -> None:
    scene = win.view.dscene
    before = scene.states
    win.ctl.update_unit("OBC1", name="Renamed")
    assert scene.states is before  # nothing happened inside the edit
    assert scene._state_timer.isActive()
    scene.refresh_states()  # (the timer's slot)
    assert scene.states is not before and not scene._state_timer.isActive()


def test_clicking_a_unit_badge_asks_for_the_problems_of_that_unit(win, qtbot) -> None:
    scroll_to(win, "unit", "HTR1")
    layout_of(win, "HTR1")
    win.view.viewport().repaint()
    item = win.view.dscene.unit_items["HTR1"]
    asked = collect(win.ctl.problemsRequested)
    rect = item._card_cache.badges[0][0]
    at = win.view.mapFromScene(item.mapToScene(rect.center()))
    start = item.pos()
    QTest.mouseClick(win.view.viewport(), LEFT, pos=at)
    assert asked == [("HTR1",)]
    assert win.ctl.selection is not None and win.ctl.selection.id == "HTR1"
    assert item.pos() == start  # a click on a badge never drags the unit


def test_a_badge_shows_a_hand_and_a_tooltip_that_says_what_it_counts(win) -> None:
    item = win.view.dscene.unit_items["HTR1"]
    layout_of(win, "HTR1")
    hit = item.hit_at(item._card_cache.badges[0][0].center())
    assert hit is not None and hit.kind == "state"
    n = win.view.dscene.states.of("unit", "HTR1").warnings
    tip = item.mark_tip(hit)
    assert f"{n} warning" in tip and "HTR1" in tip and strings.BADGE_CLICK in tip


# ---- CV-7: release and lock --------------------------------------------------------------------------


def test_a_released_unit_shows_the_lock_the_harness_and_the_revision(released) -> None:
    scene = released.view.dscene
    locked = [u for u in released.ctl.project.units if scene.states.of("unit", u).locks]
    assert locked
    uid = locked[0]
    rev = released.ctl.project.harnesses["W001"].revision
    card = layout_of(released, uid)
    assert card.lock is not None and card.lock[1] == f"W001 {rev}"
    colour = released.theme.color("locked")
    assert count_colour(render_unit(released, uid), card.lock[0], colour) >= 8  # lock + text
    unlocked = next(u for u in released.ctl.project.units if not scene.states.of("unit", u).locks)
    assert layout_of(released, unlocked).lock is None


def test_a_released_unit_has_a_faint_tint_a_draft_unit_has_none(released) -> None:
    scene = released.view.dscene
    locked = next(u for u in released.ctl.project.units if scene.states.of("unit", u).locks)
    unlocked = next(u for u in released.ctl.project.units if not scene.states.of("unit", u).locks)
    spot = QPointF(W - 30, 56)  # the empty part of the card body, right of the name

    def body(uid: str) -> QColor:
        img = render_unit(released, uid)
        return QColor(img.pixel(int(spot.x()) + 30, int(spot.y()) + 40))

    a, b = body(locked), body(unlocked)
    assert a != b
    tint = released.theme.color("released")  # green in the light theme: more green than the draft
    assert (a.green() - a.red()) > (b.green() - b.red()) or tint.green() > tint.red()


def test_the_lock_tooltip_says_who_locks_it_and_what_stays_editable(released) -> None:
    scene = released.view.dscene
    uid = next(u for u in released.ctl.project.units if scene.states.of("unit", u).locks)
    item = scene.unit_items[uid]
    card = layout_of(released, uid)
    hit = item.hit_at(card.lock[0].center())
    tip = item.mark_tip(hit)
    assert "Locked by W001" in tip and "released as revision" in tip and "new revision" in tip
    assert strings.LOCK_TIP_COSMETIC.strip() in tip


def test_a_released_link_label_carries_the_lock_and_its_text(released) -> None:
    scene = released.view.dscene
    iid = next(i for i in released.ctl.project.interfaces if scene.states.of("interface", i).locks)
    link = scene.link_items[iid]
    st = scene.states.of("interface", iid)
    parts = link._label_parts(st)
    assert parts[-1] == ("lock", st.lock_text) and st.lock_text.startswith("W001 ")
    # the registered label is wide enough for it
    assert link._label_chars() >= len(st.lock_text) + 3
    free = next(
        i for i in released.ctl.project.interfaces if not scene.states.of("interface", i).locks
    )
    assert all(
        k != "lock"
        for k, _t in scene.link_items[free]._label_parts(scene.states.of("interface", free))
    )


def test_the_released_link_tooltip_names_the_harness_the_wires_the_state_and_the_lock(
    released,
) -> None:
    scene = released.view.dscene
    iid = next(i for i in released.ctl.project.interfaces if scene.states.of("interface", i).locks)
    html = scene.link_items[iid].tooltip_html()
    summary = describe.link_summary(
        released.ctl.project, iid, scene.states.of("interface", iid).locks
    )
    assert f"({iid})" in html and "Harness" in html and "W001" in html
    assert f"<td>{summary.wire_count}</td>" in html
    assert "Generated:" in html and "Released in W001" in html
    assert "Checks" in html and "Why?" in html


def test_a_released_connector_shows_the_lock_in_expert_mode(released) -> None:
    released.ctl.set_mode("expert")
    QApplication.processEvents()
    scene = released.view.dscene
    cid = next(
        c.id
        for c in released.ctl.project.connectors.values()
        if c.role == "box" and scene.states.of("connector", c.id).locks
    )
    uid = released.ctl.project.connectors[cid].unit_id
    item = scene.unit_items[uid]
    k = [c.id for c in item.connectors()].index(cid)
    rect = item.port_rect(k, cid)
    colour = released.theme.color("locked")
    assert count_colour(render_unit(released, uid), rect, colour, tol=90) >= 4
    free = (
        next(c for c in item.connectors() if not scene.states.of("connector", c.id).locks)
        if any(not scene.states.of("connector", c.id).locks for c in item.connectors())
        else None
    )
    if free is not None:
        j = [c.id for c in item.connectors()].index(free.id)
        assert (
            count_colour(render_unit(released, uid), item.port_rect(j, free.id), colour, tol=90) < 4
        )


def test_a_draft_project_has_no_lock_anywhere(win) -> None:
    scene = win.view.dscene
    assert not any(scene.states.of("unit", u).locks for u in win.ctl.project.units)
    assert all(layout_of(win, u).lock is None for u in list(win.ctl.project.units)[:4])


def test_a_new_release_shows_up_without_reopening_the_project(tmp_path, qtbot) -> None:
    ctl = flatsat_controller(tmp_path / "p")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    folder = ctl.root
    assert folder is not None
    ctl.release()
    w.ctl.open_path(folder)
    scene = w.view.dscene
    assert not any(scene.states.of("unit", u).locks for u in w.ctl.project.units)
    release_all(w.ctl, ["W001"])
    scene.refresh_states()
    assert any(scene.states.of("unit", u).locks for u in w.ctl.project.units)
    assert w.ctl.locked_objects() is w.ctl.locked_objects()  # worked out once per revision


# ---- CV-8: auto-filled and pending ---------------------------------------------------------------------


def test_the_auto_count_shows_on_the_card_in_guided_mode_too(win) -> None:
    assert win.ctl.mode == "guided"
    card = layout_of(win, "PCDU1")
    n = win.view.dscene.states.of("unit", "PCDU1").auto
    assert n > 0 and card.auto is not None and card.auto[1] == f"{n} auto"
    colour = win.theme.color("auto-fill")
    assert count_colour(render_unit(win, "PCDU1"), card.auto[0], colour) >= 8


def test_a_missing_voltage_or_current_reads_v_question_mark_not_blank(plain) -> None:
    ctl = plain.ctl
    a, b = list(ctl.project.units)[:2]
    assert ctl.add_interface_between("power_primary", a, b)
    iid = ctl.selection.id
    plain.view.dscene.refresh_states()
    link = plain.view.dscene.link_items[iid]
    st = plain.view.dscene.states.of("interface", iid)
    assert st.pending == 2 and ("pending", 2) in st.badges()
    assert [p for p in link._label_parts(st) if p[0] == "pending"] == [
        ("pending", "V ?"),
        ("pending", "A ?"),
    ]
    assert ctl.update_interface(iid, voltage_v=28.0)
    plain.view.dscene.refresh_states()
    st = plain.view.dscene.states.of("interface", iid)
    assert link._label_parts(st)[0] == ("value", "28 V") and st.pending == 1


def test_a_pending_value_is_drawn_in_its_own_style_not_like_a_number(plain) -> None:
    ctl = plain.ctl
    a, b = list(ctl.project.units)[:2]
    assert ctl.add_interface_between("power_primary", a, b)
    iid = ctl.selection.id
    plain.view.dscene.refresh_states()
    scroll_to(plain, "interface", iid, 1.0)
    link = plain.view.dscene.link_items[iid]
    plain.view.viewport().repaint()
    img = plain.view.viewport().grab().toImage()
    chip = plain.view.mapFromScene(link._chip.center())
    pending = plain.theme.color("pending")
    n = sum(
        1
        for x in range(chip.x() - 40, chip.x() + 40)
        for y in range(chip.y() - 12, chip.y() + 12)
        if 0 <= x < img.width()
        and 0 <= y < img.height()
        and abs(QColor(img.pixel(x, y)).red() - pending.red())
        + abs(QColor(img.pixel(x, y)).green() - pending.green())
        + abs(QColor(img.pixel(x, y)).blue() - pending.blue())
        < 60  # fmt: skip
    )
    assert n >= 6


def test_a_link_with_an_unconfirmed_connector_gets_the_dashed_ring_in_guided_mode(win) -> None:
    scene = win.view.dscene
    iid = next(i for i, x in win.ctl.project.interfaces.items() if any(e.auto for e in x.endpoints))
    scroll_to(win, "interface", iid, 1.0)
    img = win.view.viewport().grab().toImage()
    link = scene.link_items[iid]
    c = win.view.mapFromScene(link._chip_center)
    ring = win.theme.color("auto-fill")
    n = sum(
        1
        for x in range(c.x() - 30, c.x() + 30)
        for y in range(c.y() - 20, c.y() + 20)
        if 0 <= x < img.width()
        and 0 <= y < img.height()
        and sum(
            abs(a - b)
            for a, b in zip(
                (
                    QColor(img.pixel(x, y)).red(),
                    QColor(img.pixel(x, y)).green(),
                    QColor(img.pixel(x, y)).blue(),
                ),
                (ring.red(), ring.green(), ring.blue()),
                strict=True,
            )
        )
        < 50
    )
    assert n >= 6


def test_the_legend_lists_the_marks_that_are_on_the_diagram_and_only_those(win, plain) -> None:
    bar = win.view.legend.bar
    kinds = {(k, p) for k, p, _t in bar._entries() if k == "badge"}
    assert ("badge", "warning") in kinds and ("badge", "pending") in kinds
    assert ("badge", "fail") not in kinds and ("badge", "locked") not in kinds  # none of them here
    plain_entries = {p for k, p, _t in plain.view.legend.bar._entries() if k == "badge"}
    plain.ctl.run_drc_now()
    assert plain_entries <= {"not-checked", "pending", "warning", "fail"}


def test_the_auto_legend_entry_goes_when_no_connector_is_auto(win) -> None:
    ctl = win.ctl
    assert any(k == "auto" for k, _p, _t in win.view.legend.bar._entries())
    ids = [i for i, x in ctl.project.interfaces.items() if any(e.auto for e in x.endpoints)]
    for i in ids:
        ctl.confirm_interface(i)
    QApplication.processEvents()
    assert not any(k == "auto" for k, _p, _t in win.view.legend.bar._entries())


def test_the_lock_legend_entry_appears_with_a_release(released) -> None:
    kinds = {p for k, p, _t in released.view.legend.bar._entries() if k == "badge"}
    assert "locked" in kinds


# ---- CV-19: the card ---------------------------------------------------------------------------------------


def test_the_card_carries_the_picture_of_its_kind_of_unit(win) -> None:
    scene = win.view.dscene
    got = {u: scene.unit_items[u].facts().glyph for u in win.ctl.project.units}
    assert got == {u: describe.unit_glyph(win.ctl.project, u) for u in win.ctl.project.units}
    # the picture is drawn: the header's left corner is not empty
    img = render_unit(win, "OBC1")
    ink = win.theme.color("text-muted")
    assert count_colour(img, QRectF(8, 8, 18, 14), ink, tol=120) >= 6


def test_the_header_counts_all_connectors_and_the_row_never_drops_groups_silently(win) -> None:
    item = win.view.dscene.unit_items["PCDU1"]
    card = layout_of(win, "PCDU1")
    facts = item.facts()
    assert facts.total == 12 and card.conn is not None and card.conn[1] == "12 conn"
    assert card.limit < W - 8  # the connector row stops before the count and the auto chip


def test_connector_pictures_that_do_not_fit_say_how_many_were_left_out() -> None:
    assert fit_groups([40, 40, 40], 200) == 3  # all fit: nothing to say
    assert fit_groups([40, 40, 40, 40], 100) == 1  # 40 + room for "+N" (26) <= 100; 80 + 26 > 100
    assert fit_groups([40], 10) == 0  # not even one: the whole count goes into the "+N"
    assert fit_groups([], 50) == 0


def test_a_card_with_more_connectors_than_room_draws_a_plus_n(win) -> None:
    card = layout_of(win, "SCOE1")
    facts = win.view.dscene.unit_items["SCOE1"].facts()
    widths = [40.5 + (22 if n > 9 else 16 if n > 1 else 0) + 4 for _k, n in facts.groups]
    shown = fit_groups(widths, card.limit - 10.0)
    assert shown < len(
        widths
    )  # SCOE1 has 14 connectors of mixed kinds beside "14 conn" and "4 auto"
    left = sum(n for _k, n in facts.groups[shown:])
    assert left > 0
    img = render_unit(win, "SCOE1")
    ink = win.theme.color("text-muted")
    x0 = 10 + sum(widths[:shown])
    assert count_colour(img, QRectF(x0, 50, 26, 20), ink, tol=120) >= 4  # the "+N" is there


def test_nominal_appears_only_where_there_is_a_redundant_chain(plain) -> None:
    ctl = plain.ctl
    scene = plain.view.dscene
    uid = next(iter(ctl.project.units))
    item = scene.unit_items[uid]
    assert strings.TAG_NOMINAL not in [t[0] for t in item._tag_specs(ctl.project.units[uid], "")]
    ctl.redundant_copy(uid)
    QApplication.processEvents()
    texts = [t[0] for t in item._tag_specs(ctl.project.units[uid], "")]
    assert strings.TAG_NOMINAL in texts
    twin = scene.unit_items[f"{uid}-R"]
    assert strings.TAG_REDUNDANT in [
        t[0] for t in twin._tag_specs(ctl.project.units[f"{uid}-R"], "")
    ]


def test_a_zone_tag_is_a_setting_of_the_viewer_not_of_the_project(win, tmp_path) -> None:
    scene = win.view.dscene
    item = scene.unit_items["PCDU1"]
    assert scene.zone_tags.tag_of("bus") == ""  # default: no tag
    assert not [t for t in item._tag_specs(win.ctl.project.units["PCDU1"], "") if t[0] == "FLIGHT"]
    ini = QSettings(str(tmp_path / "tags.ini"), QSettings.Format.IniFormat)
    win.view.set_settings(ini)
    before = win.ctl.history.revision
    win.view.set_zone_tag("bus", "flight")
    texts = [t[0] for t in item._tag_specs(win.ctl.project.units["PCDU1"], "")]
    assert "FLIGHT" in texts
    assert win.ctl.history.revision == before  # the project did not change
    again = canvas_badges.ZoneTags(
        QSettings(str(tmp_path / "tags.ini"), QSettings.Format.IniFormat)
    )
    assert again.tag_of("bus") == "flight" and again.tag_of("egse") == ""
    win.view.set_zone_tag("bus", "")
    assert scene.zone_tags.tag_of("bus") == ""


def test_the_unit_menu_offers_the_zone_tag(win) -> None:
    menu = win.view.build_context_menu("unit", "PCDU1", QPointF(0, 0))
    sub = next(a.menu() for a in menu.actions() if a.menu() and "Tag zone" in a.text())
    assert [a.text() for a in sub.actions()] == ["Flight", "Ground", "No tag"]
    sub.actions()[0].trigger()
    assert win.view.dscene.zone_tags.tag_of("bus") == "flight"


# ---- CV-21: from far away ----------------------------------------------------------------------------------


def test_each_kind_of_link_has_its_own_dashes_from_far_away() -> None:
    patterns = list(FAR_DASHES.values())
    assert len(set(patterns)) == len(patterns)  # no two categories look alike
    assert "power" not in FAR_DASHES and "data" not in FAR_DASHES  # the solid kinds


def test_far_pens_carry_the_category_dashes(win) -> None:
    scene = win.view.dscene
    assert scene.far_pen("analog", 1.5).dashPattern() == list(FAR_DASHES["analog"])
    assert scene.far_pen("power", 3.5).style() == Qt.PenStyle.SolidLine
    assert scene.far_pen("analog", 1.5) is scene.far_pen("analog", 1.5)  # cached


def test_at_the_default_fit_every_link_still_shows_what_kind_it_is(win) -> None:
    """The audit: at Fit the chips are hidden and CAN, RS-422 and Ethernet share navy. A small
    plate with the kind's picture is drawn at a fixed size on screen."""
    win.view.fit()
    QApplication.processEvents()
    assert win.view.zoom_scale() < METRICS.far_lod
    img = win.view.viewport().grab().toImage()
    scene = win.view.dscene
    lit = 0
    for link in list(scene.link_items.values())[:20]:
        c = win.view.mapFromScene(link._chip_center)
        if not win.view.viewport().rect().contains(c):
            continue
        cat = win.theme.color("bg")
        around = [
            img.pixel(c.x() + dx, c.y() + dy) for dx in range(-8, 9, 4) for dy in range(-5, 6, 5)
        ]
        lit += sum(1 for px in around if QColor(px) != cat)
    assert lit > 20


def test_the_chip_of_a_selected_or_hovered_link_is_never_smaller_than_the_minimum(win) -> None:
    link = next(iter(win.view.dscene.link_items.values()))
    win.ctl.select("interface", link.interface_id)
    win.view.fit()
    QApplication.processEvents()
    lod = win.view.zoom_scale()
    assert lod < METRICS.far_lod
    grow = METRICS.min_chip_px / (METRICS.chip_h * lod)
    assert grow > 1.0
    img = win.view.viewport().grab().toImage()
    c = win.view.mapFromScene(link._chip_center)
    half = int(METRICS.min_chip_px) // 2  # the plate reaches this far from the centre, at least
    assert win.view.viewport().rect().contains(c)
    ink = {QColor(img.pixel(c.x() + dx, c.y())).name() for dx in range(-half, half)}
    assert len(ink) > 1  # something is drawn across the readable plate


# ---- CV-22: harnesses and outputs out of date ----------------------------------------------------------


def test_the_corner_states_for_every_generation_and_outputs_state() -> None:
    cs = canvas_badges.corner_states
    assert cs("current", "current", True) == [("pass", strings.CORNER_ALL_CURRENT)]
    assert cs("stale", "current", True) == [("stale", strings.CORNER_GEN_STALE)]
    assert cs("none", "none", True) == [("draft", strings.CORNER_GEN_NONE)]
    assert cs("current", "stale", True) == [("stale", strings.CORNER_OUT_STALE)]
    assert cs("current", "none", True) == [("draft", strings.CORNER_OUT_NONE)]
    assert cs("current", "modified", True) == [("fail", strings.CORNER_OUT_MODIFIED)]
    assert cs("current", "unreadable", True) == [("fail", strings.CORNER_OUT_UNREADABLE)]
    assert cs("current", "unsaved", True) == [("pass", strings.CORNER_GEN_CURRENT)]
    assert cs("stale", "stale", True) == [
        ("stale", strings.CORNER_GEN_STALE),
        ("stale", strings.CORNER_OUT_STALE),
    ]
    assert cs("current", "current", False) == []  # nothing to generate yet


def test_the_corner_chip_follows_the_outputs(qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path / "c")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    ctl.release()
    assert ctl.root is not None
    w.ctl.open_path(ctl.root)
    status = w.view.status
    status.refresh()
    assert status.states() == [("draft", strings.CORNER_OUT_NONE)]  # generated, never exported
    from harness_design_studio.core.outputs.build import write_outputs

    folder = w.ctl.outputs_folder()
    assert folder is not None
    write_outputs(w.ctl.project, folder)
    status.refresh()
    assert status.states() == [("pass", strings.CORNER_ALL_CURRENT)]
    w.ctl.update_unit("OBC1", notes="changed after the export")
    status.refresh()
    kinds = [s for s, _t in status.states()]
    assert "stale" in kinds
    assert status.accessibleName() == strings.CORNER_NAME and status.isVisibleTo(w.view)


def test_the_corner_chip_is_not_refreshed_on_every_edit(win) -> None:
    status = win.view.status
    status.refresh()
    win.ctl.update_unit("OBC1", name="x")
    assert status._timer.isActive()  # read a moment after the last change, off the edit's path


# ---- CV-23: Why on the canvas -------------------------------------------------------------------------------


def test_the_auto_chip_says_why_the_connectors_were_chosen(win) -> None:
    item = win.view.dscene.unit_items["PCDU1"]
    card = layout_of(win, "PCDU1")
    hit = item.hit_at(card.auto[0].center())
    assert hit is not None and hit.kind == "auto"
    tip = item.mark_tip(hit)
    assert "chosen for you" in tip and "first free" in tip and "PCDU1" in tip


def test_a_click_on_the_auto_chip_asks_why(win) -> None:
    scroll_to(win, "unit", "PCDU1")
    card = layout_of(win, "PCDU1")
    win.view.viewport().repaint()
    item = win.view.dscene.unit_items["PCDU1"]
    asked = collect(win.ctl.whyRequested)
    QTest.mouseClick(
        win.view.viewport(), LEFT, pos=win.view.mapFromScene(item.mapToScene(card.auto[0].center()))
    )
    assert asked == [("unit", "PCDU1")]


def test_an_expert_connector_tooltip_says_why_it_was_chosen(win) -> None:
    win.ctl.set_mode("expert")
    QApplication.processEvents()
    item = win.view.dscene.unit_items["PCDU1"]
    auto = sorted(item._auto_connectors())
    assert auto
    lines = describe.why_lines(win.ctl.project, "connector", auto[0])
    assert any("was chosen for you" in x for x in lines)


def test_the_link_menu_has_why_and_it_asks_for_the_link(win) -> None:
    iid = next(i for i, x in win.ctl.project.interfaces.items() if any(e.auto for e in x.endpoints))
    asked = collect(win.ctl.whyRequested)
    menu = win.view.build_context_menu("interface", iid, QPointF(0, 0))
    why = next(a for a in menu.actions() if a.text() == strings.CM_WHY)
    assert why.isEnabled()
    why.trigger()
    assert asked == [("interface", iid)]


def test_the_unit_menu_has_why_only_where_something_was_chosen(win) -> None:
    menu = win.view.build_context_menu("unit", "PCDU1", QPointF(0, 0))
    assert next(a for a in menu.actions() if a.text() == strings.CM_WHY).isEnabled()
    for iid in list(win.ctl.project.interfaces):
        win.ctl.confirm_interface(iid)
    win.view.dscene.refresh_states()
    menu = win.view.build_context_menu("unit", "PCDU1", QPointF(0, 0))
    why = next(a for a in menu.actions() if a.text().startswith(strings.CM_WHY))
    assert not why.isEnabled() and strings.WHY_NOTHING_CHOSEN in why.text()  # the reason is named


def test_the_menu_key_opens_the_menu_of_the_unit_or_link_that_has_the_focus(win) -> None:
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QContextMenuEvent

    shown: list = []
    win.view.exec_menu = lambda menu, at: shown.append(menu)
    key = QContextMenuEvent.Reason.Keyboard
    win.view.dscene.unit_items["HTR1"].setFocus()
    at = QPoint(3, 3)
    QApplication.sendEvent(
        win.view.viewport(), QContextMenuEvent(key, at, win.view.mapToGlobal(at))
    )
    texts = [a.text() for a in shown[-1].actions()]
    assert strings.CM_SHOW_PROBLEMS in texts and strings.CM_WHY in [
        t.split(" — ")[0] for t in texts
    ]
    assert win.ctl.selection is not None and win.ctl.selection.id == "HTR1"
    iid = next(iter(win.view.dscene.link_items))
    win.view.dscene.link_items[iid].setFocus()
    QApplication.sendEvent(
        win.view.viewport(), QContextMenuEvent(key, at, win.view.mapToGlobal(at))
    )
    assert win.ctl.selection.id == iid


def test_the_expert_menu_on_a_connector_asks_why_for_that_connector(win) -> None:
    win.ctl.set_mode("expert")
    item = win.view.dscene.unit_items["PCDU1"]
    cid = sorted(item._auto_connectors())[0]
    asked = collect(win.ctl.whyRequested)
    menu = win.view.build_context_menu("unit", "PCDU1", QPointF(0, 0), connector=cid)
    next(a for a in menu.actions() if a.text() == strings.CM_WHY).trigger()
    assert asked == [("connector", cid)]


def test_show_problems_in_the_menu_asks_for_the_object_and_says_why_when_there_is_nothing(
    win, plain
) -> None:
    asked = collect(win.ctl.problemsRequested)
    menu = win.view.build_context_menu("unit", "HTR1", QPointF(0, 0))
    show = next(a for a in menu.actions() if a.text() == strings.CM_SHOW_PROBLEMS)
    assert show.isEnabled()
    show.trigger()
    assert asked == [("HTR1",)]
    plain.view.dscene.states = NO_INDEX  # nothing to show for any object
    uid = next(iter(plain.ctl.project.units))
    menu = plain.view.build_context_menu("unit", uid, QPointF(0, 0))
    entry = next(a for a in menu.actions() if a.text().startswith(strings.CM_SHOW_PROBLEMS))
    assert not entry.isEnabled() and strings.WHY_NOTHING_TO_SHOW in entry.text()


# ---- speed -----------------------------------------------------------------------------------------------


def stress_window(qtbot, tmp_path, units: int = 100, links: int = 800):
    from tools.bench_stress import build

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(build(units, links, 20, 400), None, None)
    w.view.fit()
    QApplication.processEvents()
    return w


def test_marks_stay_inside_the_edit_budget_at_100_units_and_800_links(qtbot, tmp_path) -> None:
    w = stress_window(qtbot, tmp_path)
    scene = w.view.dscene
    assert len(scene.unit_items) == 100 and len(scene.link_items) == 800
    scene.refresh_states()
    w.ctl.update_unit("U001", name="warm")
    QApplication.processEvents()

    def edit_ms() -> float:
        t = time.perf_counter()
        w.ctl.update_unit("U001", name=f"n{time.perf_counter()}")
        QApplication.processEvents()
        return (time.perf_counter() - t) * 1000

    assert min(edit_ms() for _ in range(3)) < time_limit(100)  # the edit itself
    t = time.perf_counter()
    scene.refresh_states()  # what the timer runs a moment later
    assert (time.perf_counter() - t) * 1000 < time_limit(100)


def test_a_full_repaint_with_marks_costs_little_at_100_units(qtbot, tmp_path) -> None:
    w = stress_window(qtbot, tmp_path)
    w.view.grab()  # warm
    t = time.perf_counter()
    w.view.grab()
    assert (time.perf_counter() - t) * 1000 < time_limit(2500)


def test_the_state_marks_of_a_unit_are_laid_out_once_not_on_every_paint(win, monkeypatch) -> None:
    item = win.view.dscene.unit_items["PCDU1"]
    render_unit(win, "PCDU1")
    first = item._card_cache
    render_unit(win, "PCDU1")
    render_unit(win, "PCDU1")
    assert item._card_cache is first  # the same layout object: nothing was recomputed
    win.ctl.update_unit("PCDU1", name="x")  # an edit stamps a new revision: laid out again
    render_unit(win, "PCDU1")
    assert item._card_cache is not first
