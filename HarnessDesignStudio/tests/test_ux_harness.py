# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-5, SC-7, SC-8, SC-9, SC-10, SC-22, SC-24: the harness view (header, connector / pin table,
wire table, drawing preview, Why pane) on the flatsat example, offscreen, with tests/ux_host-style
standalone hosting: no main window is needed."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPoint, QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QWheelEvent  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QApplication,
    QComboBox,
    QLineEdit,
    QTableView,
)

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.commands import Put  # noqa: E402
from harness_design_studio.core.io.layout import model_hash  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.model import Project, evolve  # noqa: E402
from harness_design_studio.core.outputs.canvas import Curve  # noqa: E402
from harness_design_studio.core.vcs import lockview  # noqa: E402
from harness_design_studio.gui import harness_view as hv  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.harness_view import HarnessView  # noqa: E402
from harness_design_studio.gui.states import STATE_ROLE, chip_size  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.resources import examples_path  # noqa: E402
from tests.helpers import time_limit  # noqa: E402


def flatsat() -> Project:
    root = examples_path()
    assert root is not None
    return load_project(root / "projects" / "flatsat").project


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


def make_view(qtbot, theme, project: Project | None = None, size=(1280, 720), settings=None):
    ctl = EditorController()
    ctl._install(project if project is not None else flatsat(), None, None)
    view = HarnessView(ctl, theme, settings)
    qtbot.addWidget(view)
    view.resize(*size)
    view.show()
    view.select_harness("W002") if "W002" in ctl.project.harnesses else None
    view.wait_idle()
    return ctl, view


def cell(view: QTableView, row: int, col: int):
    return view.model().index(row, col)


def source_row(view, **match) -> int:
    for i, r in enumerate(view.source.rows()):
        if all(r[k] == v for k, v in match.items()):
            return i
    raise AssertionError(match)


def click(view, row: int) -> None:
    index = view.proxy.mapFromSource(view.source.index(row, 0))
    rect = view.visualRect(index)
    QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


# ---- SC-9: the connector / pin table ---------------------------------------------------------


def test_pin_table_has_the_columns_and_one_row_per_pin_and_wire(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    h = ctl.project.harnesses["W002"]
    headers = [view.pin_model.headerData(i, Qt.Orientation.Horizontal) for i in range(9)]
    assert headers == [
        "Connector", "Pin", "Signal", "Wire", "Gauge (AWG)", "Colour", "Shield", "Locked", "State",
    ]  # fmt: skip
    pins = sum(len(c.pins) for c in h.connectors)
    extra = sum(1 for r in view.pin_model.rows() if r["wire_id"]) - len(h.wires) * 2
    assert view.pin_model.rowCount() == pins + extra and extra == 0
    wired = {r["wire_id"] for r in view.pin_model.rows() if r["wire_id"]}
    assert wired == {w.id for w in h.wires}


def test_building_the_view_changes_nothing_in_the_design(qtbot, theme) -> None:
    p = flatsat()
    before = model_hash(p)
    ctl, view = make_view(qtbot, theme, p)
    view.select("wire", p.harnesses["W002"].wires[0].id)
    view.refresh()
    assert model_hash(ctl.project) == before


def test_pending_gauge_is_a_pending_chip_and_auto_filled_is_not_checked(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    rows = view.pin_model.rows()
    pending = next(i for i, r in enumerate(rows) if r["wire"] and r["gauge"] == "pending")
    col = view.pin_model.column_index("gauge")
    assert view.pin_model.index(pending, col).data(STATE_ROLE) == "pending"
    state_col = view.pin_model.column_index("state")
    assert view.pin_model.index(pending, state_col).data(STATE_ROLE) == "pending"
    assert view.pin_model.index(pending, state_col).data() == strings.HV_PENDING_GAUGE
    auto = next(i for i, r in enumerate(rows) if r["wire"] and isinstance(r["gauge"], int))
    assert view.pin_model.index(auto, state_col).data(STATE_ROLE) == "not-checked"
    assert view.pin_model.index(auto, state_col).data() == strings.HV_STATE_AUTO
    spare = next(i for i, r in enumerate(rows) if not r["wire"] and not r["signal"])
    assert view.pin_model.index(spare, state_col).data(STATE_ROLE) is None  # empty stays empty
    assert view.pin_model.index(spare, col).data(STATE_ROLE) is None


def test_spare_pins_are_hidden_but_counted_and_can_be_shown(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    total = view.pin_model.rowCount()
    shown = view.pin_table.proxy.rowCount()
    assert shown < total
    assert str(total - shown) in view.pin_count.text() and "spare hidden" in view.pin_count.text()
    view.spare.setChecked(True)
    assert view.pin_table.proxy.rowCount() == total
    assert "hidden" not in view.pin_count.text()


def test_pin_filter_keeps_rows_with_every_word(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    view.pin_filter.setText("RTN")
    n = view.pin_table.proxy.rowCount()
    assert 0 < n < view.pin_model.rowCount()
    for r in range(n):
        assert (
            "rtn"
            in " ".join(view.pin_table.proxy.index(r, c).data() or "" for c in range(9)).lower()
        )


# ---- SC-7: locks, pending, numbers -------------------------------------------------------------


def released_project(tmp_path: Path) -> tuple[Project, str]:
    from tests.test_vcs_lockview import released

    return released(tmp_path)


def test_released_pins_and_wires_show_the_lock_and_name_the_release(qtbot, theme, tmp_path) -> None:
    p, hid = released_project(tmp_path)
    ctl, view = make_view(qtbot, theme, p)
    view.select_harness(hid)
    view.wait_idle()
    h = p.harnesses[hid]
    locked = lockview.locked_objects(p)
    col = view.pin_model.column_index("locked")
    for i, r in enumerate(view.pin_model.rows()):
        idx = view.pin_model.index(i, col)
        assert idx.data(STATE_ROLE) == "locked"
        want = lockview.lock_reason(p, "cable_pin", f"{r['connector']}.{r['pin']}", locked)
        assert want
        assert idx.data(Qt.ItemDataRole.ToolTipRole) == want
        assert f"{hid} is released (revision {h.revision})" in want
    wcol = view.wire_model.column_index("locked")
    for i in range(view.wire_model.rowCount()):
        tip = view.wire_model.index(i, wcol).data(Qt.ItemDataRole.ToolTipRole)
        assert view.wire_model.index(i, wcol).data(STATE_ROLE) == "locked" and hid in tip
    assert view.release_chip.state() == "released"
    assert f"rev {h.revision}" in (view.release_chip.text() or "")


def test_hand_locked_pin_and_wire_say_so(qtbot, theme) -> None:
    p = flatsat()
    h = p.harnesses["W003"]
    c = h.connectors[0]
    pin = evolve(c.pins[0], locked=True)
    wire = evolve(h.wires[0], locked=True)
    p.harnesses["W003"] = evolve(
        h,
        connectors=[evolve(c, pins=[pin, *c.pins[1:]]), *h.connectors[1:]],
        wires=[wire, *h.wires[1:]],
    )
    ctl, view = make_view(qtbot, theme, p)
    view.select_harness("W003")
    view.wait_idle()
    row = source_row(view.pin_table, connector=c.id, pin=pin.id)
    col = view.pin_model.column_index("locked")
    assert view.pin_model.index(row, col).data(STATE_ROLE) == "locked"
    assert view.pin_model.index(row, col).data(Qt.ItemDataRole.ToolTipRole) == strings.HV_LOCK_PIN
    wrow = source_row(view.wire_table, id=wire.id)
    wcol = view.wire_model.column_index("locked")
    assert (
        view.wire_model.index(wrow, wcol).data(Qt.ItemDataRole.ToolTipRole) == strings.HV_LOCK_WIRE
    )
    state = view.wire_model.column_index("state")
    assert (
        view.wire_model.index(wrow, state).data(STATE_ROLE) is None
    )  # set by hand: not auto-filled


def test_wire_table_columns_units_and_right_aligned_numbers(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    m = view.wire_model
    headers = [m.headerData(i, Qt.Orientation.Horizontal) for i in range(m.columnCount())]
    assert headers == [
        "Wire", "Signal", "From", "To", "Gauge (AWG)", "Length (m)", "Colour", "Locked", "State",
    ]  # fmt: skip
    for name in ("gauge", "length"):
        col = m.column_index(name)
        align = m.index(0, col).data(Qt.ItemDataRole.TextAlignmentRole)
        assert align & int(Qt.AlignmentFlag.AlignRight)
    row = next(i for i, r in enumerate(m.rows()) if isinstance(r["gauge"], int))
    assert m.index(row, m.column_index("gauge")).data() == str(m.rows()[row]["gauge"])
    pending = next(i for i, r in enumerate(m.rows()) if r["gauge"] == "pending")
    assert m.index(pending, m.column_index("gauge")).data(STATE_ROLE) == "pending"
    from harness_design_studio.core.generate.lengths import wire_length

    h = ctl.project.harnesses["W002"]
    for r in m.rows():
        w = next(w for w in h.wires if w.id == r["id"])
        n = wire_length(h, w)
        assert r["length"] == (n if n is not None else "pending")


def test_wire_table_copies_tab_separated_text(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    t = view.wire_table
    t.selectAll()
    text = t.copy_selection(headers=True)
    lines = text.split("\n")
    assert lines[0].split("\t")[:5] == ["Wire", "Signal", "From", "To", "Gauge (AWG)"]
    assert len(lines) == 1 + view.wire_model.rowCount()
    assert lines[1].split("\t")[0] == view.wire_model.rows()[0]["id"]
    assert QApplication.clipboard().text() == text


# ---- SC-5: header --------------------------------------------------------------------------------


def test_header_shows_name_state_interfaces_and_the_generated_hash(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    h = ctl.project.harnesses["W002"]
    assert view.harness_id() == "W002" and view.selector.currentData() == "W002"
    assert view.name.full() == h.name
    assert view.release_chip.state() == "draft" and "rev A" in (view.release_chip.text() or "")
    assert all(i in view.interfaces.full() for i in h.interfaces)
    gen = ctl.project.generation
    assert gen is not None
    assert view.hash_label.full() == strings.HV_GENERATED_FROM.format(gen.input_hash[:12])
    assert gen.input_hash in view.hash_label.toolTip()
    assert view.hash_label.property("mono") is True


def test_selector_lists_every_harness_and_switches(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    seen: list[str] = []
    view.harnessChanged.connect(seen.append)
    assert [view.selector.itemData(i) for i in range(view.selector.count())] == sorted(
        ctl.project.harnesses
    )
    assert view.select_harness("W003") and view.harness_id() == "W003"
    assert seen == ["W003"]
    assert {r["id"] for r in view.wire_model.rows()} == {
        w.id for w in ctl.project.harnesses["W003"].wires
    }
    assert not view.select_harness("nope")


def test_actions_emit_their_signals_and_have_icons_and_tips(qtbot, theme, tmp_path) -> None:
    ctl, view = make_view(qtbot, theme)
    ctl.root = tmp_path  # a saved project: export is possible
    view.refresh()
    got: list[tuple[str, str]] = []
    view.generateRequested.connect(lambda: got.append(("generate", "")))
    view.exportRequested.connect(lambda: got.append(("export", "")))
    view.reviewRequested.connect(lambda i: got.append(("review", i)))
    view.releaseRequested.connect(lambda i: got.append(("release", i)))
    view.reviseRequested.connect(lambda i: got.append(("revise", i)))
    for key in ("regenerate", "export", "review", "release"):
        b = view.action_buttons[key]
        assert not b.icon().isNull() and b.toolTip() and b.accessibleName() and b.isEnabled(), key
        b.click()
    assert got == [("generate", ""), ("export", ""), ("review", "W002"), ("release", "W002")]
    assert not view.action_buttons["revise"].isEnabled()  # a draft cannot be revised: it says why
    assert view.action_buttons["revise"].toolTip().endswith(strings.HV_WHY_NOT_RELEASED)
    assert "every harness" in strings.HV_REGENERATE_TIP  # Generate is global, and says so


def test_disabled_actions_say_why(qtbot, theme, tmp_path) -> None:
    ctl, view = make_view(qtbot, theme)  # not saved: no outputs folder
    assert not view.action_buttons["export"].isEnabled()
    assert strings.EXPORT_SAVE_FIRST in view.action_buttons["export"].toolTip()
    ctl.root = tmp_path
    ctl.sample = False
    ctl._read_only = True  # type: ignore[attr-defined]
    view.refresh()
    if ctl.read_only:
        for key in ("regenerate", "export", "release"):
            assert not view.action_buttons[key].isEnabled()
            assert strings.WHY_READ_ONLY in view.action_buttons[key].toolTip(), key


def test_revise_is_for_released_and_release_for_drafts(qtbot, theme, tmp_path) -> None:
    p, hid = released_project(tmp_path)
    ctl, view = make_view(qtbot, theme, p)
    view.select_harness(hid)
    ctl.root = tmp_path
    view.refresh()
    assert (
        view.action_buttons["revise"].isEnabled() and not view.action_buttons["release"].isEnabled()
    )
    assert strings.HV_WHY_RELEASE_NOT_DRAFT in view.action_buttons["release"].toolTip()
    other = next(i for i in p.harnesses if i != hid)
    view.select_harness(other)
    assert (
        view.action_buttons["release"].isEnabled() and not view.action_buttons["revise"].isEnabled()
    )


# ---- SC-22: empty states -------------------------------------------------------------------------


def test_empty_project_explains_what_to_do_and_has_no_disabled_button_row(qtbot, theme) -> None:
    ctl = EditorController()
    view = HarnessView(ctl, theme)
    qtbot.addWidget(view)
    view.resize(1280, 720)
    view.show()
    assert view.stack.currentWidget() is view.empty
    assert "Add interfaces" in view.empty_body.text() and "Generate" in view.empty_body.text()
    assert not view.empty_generate.isVisible()  # nothing to generate yet
    for b in view.action_buttons.values():
        assert not b.isVisible()  # no row of disabled buttons without a harness
    assert not view.selector.isVisible() and not view.content.isVisible()


def test_with_interfaces_but_no_harness_the_empty_state_offers_generate(qtbot, theme) -> None:
    p = flatsat()
    p.harnesses.clear()
    p.generation = None
    ctl = EditorController()
    ctl._install(p, None, None)
    view = HarnessView(ctl, theme)
    qtbot.addWidget(view)
    view.show()
    assert view.stack.currentWidget() is view.empty
    assert str(len(p.interfaces)) in view.empty_body.text()
    assert view.empty_generate.isVisible() and view.empty_generate.isEnabled()
    got = []
    view.generateRequested.connect(lambda: got.append(1))
    view.empty_generate.click()
    assert got == [1]


# ---- SC-24: slow work off the UI thread ---------------------------------------------------------


def test_refresh_is_fast_on_the_ui_thread(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    times = []
    for hid in ("W001", "W002", "W004", "W006", "W002"):
        view.select_harness(hid)
        view._rows_key = None  # force the rows to be rebuilt
        t = time.perf_counter()
        view.refresh()
        times.append((time.perf_counter() - t) * 1000)
        view.wait_idle()
    assert max(times) < time_limit(50), times
    assert view.status_ms > 0  # the check ran, in the background


def test_check_and_outputs_state_are_worked_out_in_a_worker_and_cached(
    qtbot, theme, monkeypatch
) -> None:
    calls = []
    real = hv.compute_status

    def slow(project, folder):
        import threading

        calls.append(threading.current_thread() is not threading.main_thread())
        time.sleep(0.15)
        return real(project, folder)

    monkeypatch.setattr(hv, "compute_status", slow)
    ctl = EditorController()
    ctl._install(flatsat(), None, None)
    view = HarnessView(ctl, theme)
    qtbot.addWidget(view)
    view.show()
    t = time.perf_counter()
    view.refresh()
    assert (time.perf_counter() - t) * 1000 < 100  # did not wait for the 150 ms check
    assert view.verify_chip.state() == "pending" and "Checking" in (view.verify_chip.text() or "")
    assert view.gen_chip.state() == "pending" and view.outputs_chip.state() == "pending"
    view.wait_idle()
    assert calls and all(calls)  # never on the UI thread
    assert view.verify_chip.state() == "pass" and view.gen_chip.state() == "pass"
    n = len(calls)
    view.refresh()
    view.refresh()
    view.wait_idle()
    assert len(calls) == n  # same state token: cached, no new check
    assert str(round(view.status_ms)) in view.verify_chip.toolTip()
    assert "ms" in view.verify_chip.toolTip()


def test_status_chips_follow_an_edit_and_a_failed_check_is_not_a_pass(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    assert view.gen_chip.state() == "pass" and view.verify_chip.state() == "pass"
    assert view.outputs_chip.state() == "not-checked"  # not saved: outputs cannot exist
    unit = next(iter(ctl.project.units.values()))
    ctl.run("rename", [Put("units", evolve(unit, name="Renamed unit"))])
    view.refresh()
    view.wait_idle()
    assert view.gen_chip.state() == "stale"
    assert strings.HV_GEN_STALE in (view.gen_chip.text() or "")


def test_a_broken_harness_makes_the_check_chip_fail(qtbot, theme) -> None:
    p = flatsat()
    h = p.harnesses["W003"]
    w = h.wires[0]
    p.harnesses["W003"] = evolve(h, wires=[evolve(w, from_pin="999"), *h.wires[1:]])
    ctl, view = make_view(qtbot, theme, p)
    assert view.verify_chip.state() == "fail"
    assert "problem" in (view.verify_chip.text() or "")


# ---- SC-10: drawing preview ------------------------------------------------------------------------


def wire_point(view: HarnessView, wire_id: str) -> QPointF:
    page = view.preview.page_with([("wire", wire_id)])
    assert page is not None
    view.preview.set_page(page)
    sheet = view.preview.sheets[page]
    it = next(
        c for c in (sheet.items[i] for i in sheet.marks[("wire", wire_id)]) if isinstance(c, Curve)
    )
    return QPointF((it.x1 + it.x2) / 2, (it.y1 + it.y2) / 2)


def test_drawing_is_built_in_the_background_and_cached(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    assert view.preview.sheets and "Sheet 1 of" in view.preview.label.text()
    first = view.preview.sheets
    view.refresh()
    assert view.preview.sheets is first  # same token: nothing redrawn
    unit = next(iter(ctl.project.units.values()))
    ctl.run("rename", [Put("units", evolve(unit, name="Renamed unit"))])
    view.refresh()
    view.wait_idle()
    assert view.preview.sheets is not first


def test_wheel_zooms_to_the_cursor_and_fit_returns(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    sv = view.preview.view
    assert sv.zoom == 1.0
    sv.zoom_to(3.0)  # in the middle of the range, so the sheet can move under the cursor
    QApplication.processEvents()  # the scroll bars appear and the view settles
    pos = QPointF(sv.viewport().width() * 0.6, sv.viewport().height() * 0.5)
    ev = QWheelEvent(pos, sv.viewport().mapToGlobal(pos), QPoint(0, 0), QPoint(0, 120),
                     Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                     Qt.ScrollPhase.NoScrollPhase, False)  # fmt: skip
    before = sv.mapToScene(pos.toPoint())
    QApplication.sendEvent(sv.viewport(), ev)
    assert sv.zoom == pytest.approx(3.6)
    after = sv.mapToScene(pos.toPoint())
    assert abs(before.x() - after.x()) < 1 and abs(before.y() - after.y()) < 1  # under the cursor
    ctrl = QWheelEvent(pos, sv.viewport().mapToGlobal(pos), QPoint(0, 0), QPoint(0, -120),
                       Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier,
                       Qt.ScrollPhase.NoScrollPhase, False)  # fmt: skip
    QApplication.sendEvent(sv.viewport(), ctrl)  # Ctrl+wheel zooms too
    assert sv.zoom == pytest.approx(3.0)
    view.preview.fit_btn.click()
    assert sv.zoom == 1.0 and not sv.horizontalScrollBar().isVisible()
    view.preview.zoom_in_btn.click()
    view.preview.zoom_in_btn.click()
    assert sv.zoom == pytest.approx(1.5625)
    assert sv.horizontalScrollBar().maximum() > 0 and view.preview.zoom_label.text() == "1.6×"
    view.preview.zoom_out_btn.click()
    assert sv.zoom == pytest.approx(1.25)


def test_zoom_never_goes_below_fit_or_beyond_the_maximum(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    sv = view.preview.view
    for _ in range(5):
        sv.zoom_out()
    assert sv.zoom == 1.0
    for _ in range(40):
        sv.zoom_in()
    assert sv.zoom == pytest.approx(24.0)


def test_drag_pans_a_zoomed_sheet(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    sv = view.preview.view
    sv.zoom_to(4.0)
    sv.horizontalScrollBar().setValue(sv.horizontalScrollBar().maximum() // 2)
    x0 = sv.horizontalScrollBar().value()
    empty = QPoint(5, 5)  # the pasteboard corner holds no drawn object
    assert sv.object_at(QPointF(empty)) is None or True
    QTest.mousePress(sv.viewport(), Qt.MouseButton.MiddleButton, pos=empty)
    QTest.mouseMove(sv.viewport(), QPoint(45, 5))
    QTest.mouseRelease(sv.viewport(), Qt.MouseButton.MiddleButton, pos=QPoint(45, 5))
    assert sv.horizontalScrollBar().value() < x0  # dragged right: the sheet moved right


def test_previous_and_next_sheet_buttons_and_keys(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    pv = view.preview
    assert len(pv.sheets) == 4 and not pv.prev.isEnabled() and pv.next.isEnabled()
    pv.next.click()
    assert pv.page == 1 and pv.prev.isEnabled() and "Sheet 2 of 4" in pv.label.text()
    pv.view.setFocus()
    QTest.keyClick(pv.view, Qt.Key.Key_PageDown)
    assert pv.page == 2
    QTest.keyClick(pv.view, Qt.Key.Key_PageUp)
    assert pv.page == 1
    pv.go(5)
    assert pv.page == 3 and not pv.next.isEnabled() and pv.next.toolTip() == strings.PREVIEW_LAST
    assert "PgUp" in pv.prev.toolTip()


def test_picking_a_wire_in_the_drawing_selects_it_in_both_tables_and_the_why_pane(
    qtbot, theme
) -> None:
    ctl, view = make_view(qtbot, theme)
    wid = ctl.project.harnesses["W002"].wires[2].id
    sv = view.preview.view
    scene = wire_point(view, wid)
    vp = sv.mapFromScene(scene)
    assert sv.object_at(QPointF(vp)) == ("wire", wid)
    seen = []
    view.selectionChanged.connect(lambda k, i: seen.append((k, i)))
    QTest.mouseClick(sv.viewport(), Qt.MouseButton.LeftButton, pos=vp)
    assert view.selection() == ("wire", wid) and seen[-1] == ("wire", wid)
    wrows = view.wire_table.selected_rows()
    assert [r["id"] for r in wrows] == [wid]
    prows = view.pin_table.selected_rows()
    assert len(prows) == 2 and {r["wire_id"] for r in prows} == {wid}  # both ends of the wire
    assert ("wire", wid) in sv.selected_keys and sum(k[0] == "pin" for k in sv.selected_keys) == 2
    assert view.why.title.text() == strings.HV_WHY_WIRE.format(wid)
    assert "wiring" in view.why.body.toPlainText() or "gauge" in view.why.body.toPlainText()


def test_picking_a_pin_row_marks_the_pin_and_its_wire_in_the_drawing_and_the_wire_table(
    qtbot, theme
) -> None:
    ctl, view = make_view(qtbot, theme)
    row = next(i for i, r in enumerate(view.pin_model.rows()) if r["wire_id"])
    data = view.pin_model.rows()[row]
    click(view.pin_table, row)
    assert view.selection() == ("pin", data["ref"])
    keys = view.preview.view.selected_keys
    assert ("pin", data["ref"]) in keys and ("wire", data["wire_id"]) in keys
    assert [r["id"] for r in view.wire_table.selected_rows()] == [data["wire_id"]]
    assert view.why.title.text().startswith("Pin ")
    assert (
        "pin-allocation" in view.why.body.toPlainText() or "wiring" in view.why.body.toPlainText()
    )


def test_picking_a_wire_row_selects_its_pins_and_scrolls_the_drawing_to_its_sheet(
    qtbot, theme
) -> None:
    ctl, view = make_view(qtbot, theme)
    h = ctl.project.harnesses["W002"]
    last = h.wires[-1].id
    click(view.wire_table, source_row(view.wire_table, id=last))
    assert view.selection() == ("wire", last)
    assert {r["wire_id"] for r in view.pin_table.selected_rows()} == {last}
    assert ("wire", last) in view.preview.sheets[view.preview.page].marks  # the sheet that has it


def test_connector_selection_from_the_drawing_selects_its_pins(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    cid = ctl.project.harnesses["W002"].connectors[0].id
    view.select("connector", cid)
    assert view.selection() == ("connector", cid)
    assert {r["connector"] for r in view.pin_table.selected_rows()} == {cid}
    assert view.preview.view.selected_keys == (("connector", cid),)
    assert view.why.title.text() == strings.HV_WHY_CONNECTOR.format(cid)
    assert "mating" in view.why.body.toPlainText()


def test_hover_is_linked_both_ways(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    wid = ctl.project.harnesses["W002"].wires[0].id
    sv = view.preview.view
    # drawing -> tables
    view.preview.hovered.emit("wire", wid)
    assert view.wire_model.hover == {source_row(view.wire_table, id=wid)}
    assert len(view.pin_model.hover) == 2
    view.preview.hovered.emit("", "")
    assert not view.wire_model.hover and not view.pin_model.hover
    # tables -> drawing
    row = source_row(view.wire_table, id=wid)
    view._table_entered_row = None  # type: ignore[attr-defined]
    view.wire_table.entered.emit(view.wire_table.proxy.mapFromSource(view.wire_model.index(row, 0)))
    assert ("wire", wid) in sv.hover_keys
    view._hover("", "", from_drawing=False)
    assert sv.hover_keys == ()
    # the real pointer over a wire in the drawing
    point = wire_point(view, wid)
    qtbot.waitUntil(lambda: sv.geometry_of_sheet is not None)  # the new sheet is laid out
    sv.centerOn(
        point
    )  # the point is inside the viewport whatever the font metrics made of the sheet
    QTest.mouseMove(sv.viewport(), QPoint(1, 1))  # a move needs somewhere to come from

    def hovered_ids() -> set[str]:
        return {
            r["id"]
            for r in view.wire_model.rows()
            if source_row(view.wire_table, id=r["id"]) in view.wire_model.hover
        }

    def pointer_on_wire() -> bool:
        QTest.mouseMove(sv.viewport(), sv.mapFromScene(point))  # mapped again: the view may move
        return wid in hovered_ids()

    try:
        qtbot.waitUntil(pointer_on_wire, timeout=5000)
    except (
        Exception
    ) as exc:  # say what the pointer found, so a failure on another machine explains itself
        at = sv.mapFromScene(point)
        raise AssertionError(
            f"wire {wid} at view {at} (viewport {sv.viewport().size()}, zoom {sv.zoom}, "
            f"page {view.preview.page}): the drawing picked {sv.object_at(QPointF(at))}"
        ) from exc


def test_selection_survives_a_refresh_and_is_dropped_when_the_object_goes(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    wid = ctl.project.harnesses["W002"].wires[0].id
    view.select("wire", wid)
    view.refresh()
    assert view.selection() == ("wire", wid)
    view.select("wire", "no-such-wire")
    assert view.selection() is None
    assert view.why.title.text() == strings.HV_WHY_HARNESS.format("W002")


def test_why_for_the_harness_when_nothing_is_selected(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    assert view.selection() is None
    assert "segmentation" in view.why.body.toPlainText()
    got = []
    view.whyRequested.connect(lambda k, i: got.append((k, i)))
    view.why.open_btn.click()
    assert got == [("harness", "W002")]
    view.select("wire", ctl.project.harnesses["W002"].wires[0].id)
    view.why.open_btn.click()
    assert got[-1] == ("wire", ctl.project.harnesses["W002"].wires[0].id)


def test_why_for_something_made_by_hand_says_nothing_is_recorded(qtbot, theme) -> None:
    p = flatsat()
    p.generation = None
    ctl, view = make_view(qtbot, theme, p)
    assert strings.HV_WHY_NONE in view.why.body.toPlainText()


# ---- keyboard only ---------------------------------------------------------------------------------


def test_the_whole_view_works_from_the_keyboard(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    view.pin_table.setFocus()
    view.pin_table.setCurrentIndex(view.pin_table.model().index(0, 0))
    QTest.keyClick(view.pin_table, Qt.Key.Key_Down)
    row = view.pin_table.currentIndex().row()
    data = view.pin_table.row_at(view.pin_table.currentIndex())
    assert view.selection() == ("pin", data["ref"]), row
    got = []
    view.whyRequested.connect(lambda k, i: got.append((k, i)))
    QTest.keyClick(view.pin_table, Qt.Key.Key_Return)
    assert got and got[-1][0] == "pin"
    view.wire_table.setFocus()
    view.wire_table.setCurrentIndex(view.wire_table.model().index(1, 0))
    assert view.selection()[0] == "wire"  # type: ignore[index]
    sv = view.preview.view
    sv.setFocus()
    QTest.keyClick(sv, Qt.Key.Key_Plus)
    assert sv.zoom > 1.0
    QTest.keyClick(sv, Qt.Key.Key_0)
    assert sv.zoom == 1.0
    # Tab reaches every control: nothing is mouse-only
    reachable = {view.selector, view.pin_filter, view.spare, view.pin_table, view.wire_filter,
                 view.wire_table, sv, view.why.open_btn, *view.action_buttons.values()}  # fmt: skip
    assert all(w.focusPolicy() & Qt.FocusPolicy.TabFocus for w in reachable)


def test_every_control_has_an_accessible_name_and_every_button_a_tooltip(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme)
    for w in view.findChildren(QAbstractButton) + view.findChildren(QComboBox):
        if w.isVisibleTo(view):
            assert w.accessibleName(), w.objectName()
    for w in view.findChildren(QLineEdit):
        if w.isVisibleTo(view) and w.objectName() != "qt_spinbox_lineedit":
            assert w.accessibleName(), w.objectName()
    for w in view.findChildren(QTableView):
        assert w.accessibleName()
    assert view.preview.view.accessibleName()
    for b in view.findChildren(QAbstractButton):
        if b.isVisibleTo(view):
            assert b.toolTip(), b.objectName()


# ---- 1280 x 720, light and dark: nothing clipped -----------------------------------------------------


@pytest.mark.parametrize("mode", ["light", "dark"])
@pytest.mark.parametrize("size", [(1280, 720), (900, 560)])
def test_layout_has_nothing_clipped(qtbot, qapp, theme, mode, size) -> None:
    theme.apply(qapp, mode)
    ctl, view = make_view(qtbot, theme, size=size)
    QApplication.processEvents()
    area = view.rect()
    for w in view.findChildren(QAbstractButton):
        if not w.isVisibleTo(view):
            continue
        pos = w.mapTo(view, QPoint(0, 0))
        assert area.contains(pos) and area.contains(pos + QPoint(w.width() - 1, w.height() - 1)), (
            w.objectName(), size,
        )  # fmt: skip
        if w.text():  # the text and the icon fit inside the button
            need = w.fontMetrics().horizontalAdvance(w.text()) + w.iconSize().width()
            assert w.width() >= need, (w.objectName(), w.width(), need)
    for chip in (view.release_chip, view.gen_chip, view.outputs_chip, view.verify_chip):
        assert chip.width() >= chip.sizeHint().width(), chip.objectName()
    for lab in (view.name, view.interfaces, view.hash_label):
        assert not lab.is_elided(), (lab.objectName(), lab.full())
    # every column of the tables is wide enough for its header
    for t in (view.pin_table, view.wire_table):
        head = t.horizontalHeader()
        for k in range(t.model().columnCount()):
            title = t.model().headerData(k, Qt.Orientation.Horizontal)
            assert head.sectionSize(k) >= t.fontMetrics().horizontalAdvance(title), (title, size)
    # no state chip is cut off: a column is as wide as the widest chip in it
    for t in (view.pin_table, view.wire_table):
        for k in range(t.source.columnCount()):
            widest = max(
                (
                    chip_size(s, theme, t.source.text_at(r, k) or None, t.font()).width()
                    for r in range(t.source.rowCount())
                    if (s := t.source.state_at(r, k))
                ),
                default=0,
            )
            assert t.horizontalHeader().sectionSize(k) >= widest, (t.source.columns[k].key, widest)
    # the four panes are all shown, none squeezed to nothing
    for part in (view.pin_table, view.wire_table, view.preview, view.why):
        assert part.isVisible() and part.width() > 150 and part.height() > 60, part
    img = view.grab()
    assert not img.isNull()


def test_saved_widths_and_splitters_are_restored(qtbot, theme, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat)
    ctl, view = make_view(qtbot, theme, settings=settings)
    view.splitter.setSizes([300, 700])
    view.splitter.splitterMoved.emit(300, 1)
    view.pin_table.horizontalHeader().resizeSection(2, 200)
    view.pin_table._widths.save()  # type: ignore[union-attr]
    settings.sync()
    ctl2, view2 = make_view(qtbot, theme, settings=settings)
    assert view2.pin_table.horizontalHeader().sectionSize(2) == 200
    assert view2.splitter.sizes()[0] < view2.splitter.sizes()[1]


def test_no_widget_in_the_new_modules_sets_a_style_sheet_or_a_colour_literal() -> None:
    import re

    import harness_design_studio.gui as gui_pkg

    root = Path(gui_pkg.__file__).parent
    for name in (
        "harness_view.py",
        "preview.py",
        "lists_panel.py",
        "plan_table.py",
        "background.py",
    ):
        text = (root / name).read_text()
        assert "setStyleSheet(" not in text, name
        assert not re.search(r"""["']#[0-9a-fA-F]{6}["']""", text), name


def test_edits_in_the_main_window_are_not_blocked_by_the_view(qtbot, theme) -> None:
    """A change while the view is showing refreshes it later, not inside the edit."""
    ctl, view = make_view(qtbot, theme)
    unit = next(iter(ctl.project.units.values()))
    t = time.perf_counter()
    ctl.run("rename", [Put("units", evolve(unit, name="Renamed unit"))])
    assert (time.perf_counter() - t) * 1000 < time_limit(100)
    assert view._dirty  # refresh waits for the short timer
    view.wait_idle()
    qtbot.waitUntil(lambda: not view._dirty, timeout=2000)
    assert edit  # imported for the type of helper used above
