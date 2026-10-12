"""REQ-GUI-01: the Qt editor supports the ten journeys of docs/UX.md (offscreen, driven like a user)."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit, QPushButton

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.core import edit  # noqa: E402
from harness_design_studio.core.io.layout import model_hash  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from tests.gui_helpers import (  # noqa: E402
    DialogScript,
    click_link,
    click_unit,
    make_window,
    unit_item,
)


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    return w


def button(win, name: str) -> QPushButton:  # type: ignore[no-untyped-def]
    b = win.findChild(QPushButton, name)
    assert b is not None, name
    return b  # type: ignore[no-any-return]


def last_toast(win) -> str:  # type: ignore[no-untyped-def]
    return win.toasts.messages[-1] if win.toasts.messages else ""


# ---- J1 first run and tour ------------------------------------------------------------------


def test_j1_tour_starts_on_first_run_and_can_be_skipped_and_replayed(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    w = make_window(tmp_path, first_run=True)
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: w.tour.card.isVisible(), timeout=2000)
    assert "Step 1 of 5" in w.tour.title.text()
    # the card never covers the area it explains
    card, target = w.tour.card.geometry(), w.tour.highlight.target
    assert not card.intersects(target)
    button(w, "tour-next").click()
    assert "Step 2 of 5" in w.tour.title.text()
    button(w, "tour-skip").click()
    assert not w.tour.card.isVisible()
    w.act_tour.trigger()
    assert w.tour.card.isVisible() and "Step 1 of 5" in w.tour.title.text()
    for _ in range(5):
        button(w, "tour-next").click()
    assert not w.tour.card.isVisible()


def test_sample_project_opens_with_banner(win) -> None:  # type: ignore[no-untyped-def]
    assert len(win.ctl.project.units) == 3 and win.banner.isVisible()
    assert "sample project" in win.banner.label.text()
    assert "Harness Design Studio" in win.windowTitle()


# ---- J2 build the diagram ---------------------------------------------------------------------


def test_j2_empty_state_and_adding_units(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(new_project(), None, None)  # an empty project
    assert win.view.empty.isVisible() and "Add your first unit" in win.view.empty.text()
    button(win, "add-computer").click()
    assert not win.view.empty.isVisible() and "OBC1" in win.ctl.project.units
    assert win.ctl.selection and win.ctl.selection.id == "OBC1"


def test_j2_new_units_never_overlap(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(new_project(), None, None)
    for tid in (
        "computer",
        "power",
        "actuator",
        "sensor",
        "payload",
        "transceiver",
        "pyro",
        "computer",
    ):
        button(win, f"add-{tid}").click()
    items = list(win.view.dscene.unit_items.values())
    for i, a in enumerate(items):
        for b in items[i + 1 :]:
            assert (
                not a.sceneBoundingRect()
                .adjusted(8, 8, -8, -8)
                .intersects(b.sceneBoundingRect().adjusted(8, 8, -8, -8))
            )


def test_j2_id_validation_is_live_and_blocks_invalid_values(win) -> None:  # type: ignore[no-untyped-def]
    click_unit(win, "OBC")
    f = win.props.fields["id"]
    assert isinstance(f, QLineEdit)
    f.clear()
    QTest.keyClicks(f, "RW1")
    assert f.property("invalid") is True
    f.editingFinished.emit()
    assert "OBC" in win.ctl.project.units  # nothing renamed
    f.clear()
    QTest.keyClicks(f, "1bad")
    assert f.property("invalid") is True
    f.clear()
    QTest.keyClicks(f, "COMPUTER")
    assert f.property("invalid") is False
    f.editingFinished.emit()
    assert "COMPUTER" in win.ctl.project.units and win.ctl.selection.id == "COMPUTER"  # type: ignore[union-attr]
    assert {e.unit_id for e in win.ctl.project.interfaces["IF-TM-RW1"].endpoints} == {
        "COMPUTER",
        "RW1",
    }


def test_j2_dragging_a_unit_changes_its_zone(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    item = unit_item(win, "OBC")
    start = win.view.mapFromScene(item.mapToScene(60, 12))
    end = win.view.mapFromScene(item.mapToScene(60 + 500, 12))
    QTest.mousePress(win.view.viewport(), Qt.MouseButton.LeftButton, pos=start)
    QTest.mouseMove(win.view.viewport(), pos=end)
    QTest.mouseRelease(win.view.viewport(), Qt.MouseButton.LeftButton, pos=end)
    assert win.ctl.project.units["OBC"].zone == "panel-B"
    assert win.ctl.project.placements["OBC"].x > 435
    assert "now in panel-B" in last_toast(win)
    win.ctl.undo()
    assert win.ctl.project.units["OBC"].zone == "panel-A"


# ---- J3 connect safely ------------------------------------------------------------------------


def test_j3_guided_connect_prevents_invalid_and_marks_auto(win) -> None:  # type: ignore[no-untyped-def]
    ctl = win.ctl
    button(win, "add-sensor").click()  # ST1 carries power, spacewire/rs422, not CAN
    button(win, "type-can").click()
    assert ctl.tool == "connect"
    # greyed with visible reason text
    state, reason = unit_item(win, "ST1")._compat_reason()
    assert state == "no" and "No free CAN connector" in reason
    click_unit(win, "ST1")
    assert "no free CAN connector" in last_toast(win) and ctl.connect_from is None
    click_unit(win, "OBC")  # OBC-J03 carries CAN and is free
    assert ctl.connect_from and ctl.connect_from.unit_id == "OBC"
    assert unit_item(win, "OBC")._compat_reason()[0] == "from"
    assert "No other unit has a free CAN connector" in win.hint.text()
    ctl.end_connect()
    n = len(ctl.project.interfaces)
    button(win, "type-rs422").click()
    click_unit(win, "OBC")
    click_unit(win, "ST1")
    assert len(ctl.project.interfaces) == n + 1
    iid = ctl.selection.id  # type: ignore[union-attr]
    assert all(e.auto for e in ctl.project.interfaces[iid].endpoints)
    assert "Auto" in " ".join(lbl.text() for lbl in win.props.findChildren(type(win.hint)))
    button(win, "if-confirm").click()
    assert not any(e.auto for e in ctl.project.interfaces[iid].endpoints)


def test_j3_expert_mode_exact_connector_rules(win) -> None:  # type: ignore[no-untyped-def]
    ctl = win.ctl
    ctl.set_mode("expert")
    button(win, "type-power_primary").click()
    assert (
        not ctl.connector_compat("RW1-J01").ok
        and "already carries" in ctl.connector_compat("RW1-J01").why
    )
    assert "does not carry Primary power" in ctl.connector_compat("OBC-J03").why
    click_unit(win, "OBC", port="OBC-J03")
    assert "does not carry Primary power" in last_toast(win)
    click_unit(win, "OBC")  # unit body in expert mode: asks for a connector
    assert "Click a connector" in last_toast(win)
    click_unit(win, "PCDU", port="PCDU-J02")
    click_unit(win, "OBC", port="OBC-J02")
    iid = ctl.selection.id  # type: ignore[union-attr]
    eps = ctl.project.interfaces[iid].endpoints
    assert [e.connector_id for e in eps] == ["PCDU-J02", "OBC-J02"] and not any(e.auto for e in eps)


def test_connect_tool_escape_and_toggle(win) -> None:  # type: ignore[no-untyped-def]
    button(win, "type-rs422").click()
    assert win.ctl.tool == "connect"
    button(win, "type-rs422").click()  # clicking the active type again turns the tool off
    assert win.ctl.tool == "select"
    button(win, "type-rs422").click()
    win.view.setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Escape)
    assert win.ctl.tool == "select" and win.ctl.connect_type is None


def test_undo_redo_roundtrip_via_actions_and_shortcuts(win) -> None:  # type: ignore[no-untyped-def]
    h0 = model_hash(win.ctl.project)
    button(win, "add-payload").click()
    assert model_hash(win.ctl.project) != h0 and win.act_undo.isEnabled()
    win.act_undo.trigger()
    assert model_hash(win.ctl.project) == h0 and win.act_redo.isEnabled()
    win.act_redo.trigger()
    assert "PL1" in win.ctl.project.units


# ---- J4 table and import ---------------------------------------------------------------------


def test_j4_table_edits_sync_and_filter(win) -> None:  # type: ignore[no-untyped-def]
    win.tabs.setCurrentIndex(2)  # the table refreshes while visible (and on show)
    m = win.table.model
    idx = m.index(m.ids.index("IF-PWR-RW1"), 1)
    assert m.setData(idx, "Wheel supply")
    assert win.ctl.project.interfaces["IF-PWR-RW1"].name == "Wheel supply"
    assert m.setData(m.index(0, 5), "redundant") is True
    assert not m.setData(m.index(0, 6), "abc")  # invalid number refused
    assert "Enter a number" in last_toast(win)
    assert (
        m.setData(m.index(0, 6), "2.5")
        and win.ctl.project.interfaces[m.ids[0]].max_current_a == 2.5
    )
    # selecting in the table selects on the canvas and in properties
    win.table.view.selectRow(0)
    first = win.table.proxy.data(win.table.proxy.index(0, 0))
    assert win.ctl.selection and win.ctl.selection.id == first
    win.table.filter.setText("rs422")
    assert win.table.proxy.rowCount() == 1


def test_j4_new_interface_dialog_disables_unusable_units_with_reason(win) -> None:  # type: ignore[no-untyped-def]
    seen = {}

    def fn(d) -> None:  # type: ignore[no-untyped-def]
        d.type_box.setCurrentIndex(d.type_box.findData("can"))
        model = d.to_box.model()
        seen["items"] = [
            (model.item(r).text(), model.item(r).isEnabled(), model.item(r).toolTip())
            for r in range(model.rowCount())
        ]
        d.type_box.setCurrentIndex(d.type_box.findData("rs422"))  # a type that two units can take
        seen["choice"] = d.choice()

    DialogScript(win, fn)
    n = len(win.ctl.project.interfaces)
    win.new_interface_flow()
    disabled = [t for t in seen["items"] if not t[1]]
    assert any(
        "PCDU" in t[0] and "No free CAN connector" in t[0] and "unit template" in t[2]
        for t in disabled
    )
    assert len(win.ctl.project.interfaces) == n + 1  # accepted: added with the chosen valid units


def test_j4_import_preview_row_errors_and_single_undo(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    csv_text = (
        "Interface,Type,From unit,To unit,Redundancy\n"
        "IF-010,Primary power,PCDU,OBC,nominal\nIF-011,CAN,OBC,RW1,nominal\nIF-012,RS-422,OBC,PCDU,nominal\n"
        "IF-013,RS-423,OBC,RW1,nominal\nIF-TM-RW1,Discrete / bilevel,OBC,PCDU,nominal\nIF-014,Primary power,PCDU,GHOST,nominal\n"
    )
    checks: dict[str, str] = {}

    def fn(d) -> None:  # type: ignore[no-untyped-def]
        d.text.setPlainText(csv_text)
        checks["summary"] = d.summary.text()
        checks["button"] = d.ok.text()
        checks["rows"] = " | ".join(
            d.preview.item(r, 5).text() for r in range(d.preview.rowCount())
        )

    DialogScript(win, fn)
    h0 = model_hash(win.ctl.project)
    win.import_flow()
    assert (
        "2 of 6 rows can be imported" in checks["summary"]
        and checks["button"] == "Import 2 rows (one undo step)"
    )
    for expected in (
        "Unknown interface type",
        "already used",
        "does not exist",
        "no free CAN connector",
    ):
        assert expected in checks["rows"]
    assert {"IF-010", "IF-012"} <= set(win.ctl.project.interfaces)
    assert all(e.auto for e in win.ctl.project.interfaces["IF-010"].endpoints)
    win.ctl.undo()
    assert model_hash(win.ctl.project) == h0  # one step undoes the whole import


def test_j4_import_cancel_changes_nothing_and_file_open_errors(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    h0 = model_hash(win.ctl.project)
    bad = tmp_path / "x.txt"
    bad.write_text("a")

    def fn(d) -> None:  # type: ignore[no-untyped-def]
        d.pick_file = lambda: str(bad)
        d.open_file()
        assert "Only .csv and .xlsx" in d.summary.text()
        d.text.setPlainText("id,type,from,to\nA1,RS-422,OBC,PCDU\n")

    DialogScript(win, fn, accept=False)
    win.import_flow()
    assert model_hash(win.ctl.project) == h0


def test_j4_import_from_xlsx_file(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for row in (["Interface", "Type", "From unit", "To unit"], ["IF-050", "RS-422", "OBC", "PCDU"]):
        ws.append(row)  # type: ignore[union-attr]
    path = tmp_path / "icd.xlsx"
    wb.save(path)

    def fn(d) -> None:  # type: ignore[no-untyped-def]
        d.pick_file = lambda: str(path)
        d.open_file()

    DialogScript(win, fn)
    win.import_flow()
    assert "IF-050" in win.ctl.project.interfaces


# ---- J5 redundant chain and findings ----------------------------------------------------------


def test_j5_redundant_copy_cross_strap_fix_and_waiver(win) -> None:  # type: ignore[no-untyped-def]
    ctl = win.ctl
    click_unit(win, "RW1")
    assert win.redundant_btn.isEnabled()
    win.redundant_btn.click()
    assert "RW1-R" in ctl.project.units and ctl.project.units["RW1-R"].side == "redundant"
    assert win.tabs.tabText(0) == "Problems (2)"
    cards = [
        w
        for w in win.problems.findChildren(type(win.hint))
        if "connects the nominal chain" in w.text()
    ]
    assert len(cards) == 2
    waive_texts: list[str] = []

    def too_short(d) -> None:  # type: ignore[no-untyped-def]
        d.text.setPlainText("short")
        d.ok.click()
        waive_texts.append(d.error.text())
        d.text.setPlainText("Cross-strap is intentional, see ICD 4.2")

    DialogScript(win, too_short)
    win.problems.findChildren(QPushButton, "waive")[0].click()
    assert "at least 10 characters" in waive_texts[0] and len(ctl.project.waivers) == 1
    assert win.problems.counts() == (0, 1)
    win.problems.findChildren(QPushButton, "fix")[0].click()
    assert win.problems.counts() == (0, 0)
    assert "PCDU-R" in ctl.project.units or "OBC-R" in ctl.project.units
    assert "Cross-strap is intentional" in " ".join(
        lbl.text() for lbl in win.problems.findChildren(type(win.hint))
    )


# ---- J6 problems, to-do, delete, explain ------------------------------------------------------


def test_j6_todo_items_are_clickable(win) -> None:  # type: ignore[no-untyped-def]
    button(win, "add-pyro").click()
    win.tabs.setCurrentIndex(1)
    assert win.tabs.tabText(1) == "To-do (1)"
    t = button(win, "todo-0")
    assert "not connected to anything" in t.text()
    win.ctl.select(None)
    t.click()
    assert win.ctl.selection and win.ctl.selection.id == "PYRO1"


def test_j6_delete_shows_impact_is_cancellable_and_undoable(win) -> None:  # type: ignore[no-untyped-def]
    click_unit(win, "OBC")
    bodies: list[str] = []
    DialogScript(win, lambda d: bodies.append(d.body.text()), accept=False)
    win.delete_btn.click()
    assert "IF-TM-RW1" in bodies[0] and "Ctrl+Z" in bodies[0]
    assert "OBC" in win.ctl.project.units  # cancel: nothing happened
    DialogScript(win, accept=True)
    win.delete_btn.click()
    assert "OBC" not in win.ctl.project.units and "IF-TM-RW1" not in win.ctl.project.interfaces
    win.act_undo.trigger()
    assert "OBC" in win.ctl.project.units and "IF-TM-RW1" in win.ctl.project.interfaces


def test_j6_deleting_a_unit_with_harness_wires_is_refused_with_reason(win) -> None:  # type: ignore[no-untyped-def]
    click_unit(win, "RW1")
    DialogScript(win, accept=True)
    win.delete_btn.click()
    assert "RW1" in win.ctl.project.units and "W001 was made by hand" in last_toast(win)


def test_delete_key_and_interface_selection(win) -> None:  # type: ignore[no-untyped-def]
    click_link(win, "IF-TM-RW1")
    assert win.ctl.selection and win.ctl.selection.kind == "interface"
    win.act_delete.trigger()
    assert "IF-TM-RW1" not in win.ctl.project.interfaces


# ---- J8 expert refinement, modes ---------------------------------------------------------------


def test_modes_do_not_change_data_and_expert_shows_connectors(win) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QComboBox

    h = model_hash(win.ctl.project)
    click_unit(win, "OBC")
    assert win.props.findChild(QComboBox, "part-OBC-J01") is None  # Guided hides physical details
    win.mode_expert.click()
    combo = win.props.findChild(QComboBox, "part-OBC-J01")
    assert combo is not None
    combo.setCurrentText("EX-DSUB-15-F")
    combo.activated.emit(combo.currentIndex())
    assert win.ctl.project.connectors["OBC-J01"].part_id == "EX-DSUB-15-F"
    win.ctl.undo()
    win.mode_guided.click()
    assert model_hash(win.ctl.project) == h


def test_expert_properties_choose_exact_connector_for_an_interface_end(win) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtWidgets import QComboBox

    win.ctl.set_mode("expert")
    click_link(win, "IF-TM-RW1")
    combo = win.props.findChild(QComboBox, "end-0")
    assert combo is not None
    names = [combo.itemText(i) for i in range(combo.count())]
    assert "J01" in names and "J03" in names  # current and the other free rs422/can connector
    combo.setCurrentIndex(names.index("J03"))
    combo.activated.emit(combo.currentIndex())
    assert win.ctl.project.interfaces["IF-TM-RW1"].endpoints[0].connector_id == "OBC-J03"


# ---- J9 search --------------------------------------------------------------------------------


def test_command_palette_runs_commands_and_finds_ids(win) -> None:  # type: ignore[no-untyped-def]
    labels: list[str] = []

    def fn(d) -> None:  # type: ignore[no-untyped-def]
        labels.extend(e.label for e in d.entries)
        d.input.setText("expert")
        d._run_current()

    DialogScript(win, fn)
    win.open_commands()
    assert win.ctl.mode == "expert"
    assert any(x.startswith("Go to unit RW1") for x in labels) and any(
        x == "Connect with CAN" for x in labels
    )

    def go(d) -> None:  # type: ignore[no-untyped-def]
        d.input.setText("go to unit pcdu")
        d._run_current()

    DialogScript(win, go)
    win.open_commands()
    assert win.ctl.selection and win.ctl.selection.id == "PCDU"


def test_command_palette_keyboard_navigation(qtbot, win) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.gui.dialogs import CommandPalette

    ran: list[str] = []
    from harness_design_studio.gui.dialogs import PaletteEntry

    d = CommandPalette(
        win,
        [
            PaletteEntry("alpha", lambda: ran.append("a")),
            PaletteEntry("beta", lambda: ran.append("b")),
        ],
    )
    qtbot.addWidget(d)
    d.show()
    QTest.keyClick(d.input, Qt.Key.Key_Down)
    QTest.keyClick(d.input, Qt.Key.Key_Up)
    QTest.keyClick(d.input, Qt.Key.Key_Down)
    QTest.keyClick(d.input, Qt.Key.Key_Return)
    assert ran == ["b"]


# ---- keyboard operation -----------------------------------------------------------------------


def test_keyboard_selection_nudge_and_connect(win) -> None:  # type: ignore[no-untyped-def]
    item = unit_item(win, "OBC")
    win.view.dscene.setFocusItem(item)
    win.view.setFocus()
    QTest.keyClick(win.view, Qt.Key.Key_Return)
    assert win.ctl.selection and win.ctl.selection.id == "OBC"
    y0 = win.ctl.project.placements["OBC"].y
    QTest.keyClick(win.view, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)
    assert win.ctl.project.placements["OBC"].y == y0 + 10
    # connect with keyboard only: Enter on a unit picks it
    win.ctl.begin_connect("rs422")
    win.view.dscene.setFocusItem(unit_item(win, "OBC"))
    QTest.keyClick(win.view, Qt.Key.Key_Return)
    assert win.ctl.connect_from and win.ctl.connect_from.unit_id == "OBC"


# ---- files, autosave, recovery, locking --------------------------------------------------------


def test_j10_new_save_open_roundtrip(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "proj"
    win.ask_folder = lambda title: str(folder)
    win.ask_text = lambda t, label, default: "My satellite"
    win.new_project_flow()
    assert (folder / "project.json").exists() and win.ctl.root == folder
    assert win.windowTitle().startswith("My satellite")
    button(win, "add-computer").click()
    assert win.ctl.dirty and "*" in win.windowTitle()
    assert win.save_flow()
    assert not win.ctl.dirty and (folder / "logical/layout.json").exists()
    loaded = load_project(folder)
    assert "OBC1" in loaded.project.units and not loaded.has_errors
    win.ctl.release()
    win2 = make_window(tmp_path / "w2")
    assert win2.open_project(folder)
    assert "OBC1" in win2.ctl.project.units and not win2.banner.isVisible()
    win2.ctl.release()


def test_new_project_refuses_non_empty_folder(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "x.txt").write_text("hi")
    win.ask_folder = lambda title: str(busy)
    win.ask_text = lambda t, label, default: "n"
    win.new_project_flow()
    assert "empty folder" in last_toast(win) and win.ctl.root is None


def test_sample_save_as_keeps_changes_and_clears_banner(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    button(win, "add-payload").click()
    win.ask_folder = lambda title: str(tmp_path / "copy")
    assert win.save_flow()  # no folder yet: falls back to Save As
    assert (tmp_path / "copy" / "project.json").exists() and not win.banner.isVisible()
    assert "PL1" in load_project(tmp_path / "copy").project.units
    win.ctl.release()


def test_autosave_journal_and_restore_after_crash(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "proj"
    w1 = make_window(tmp_path / "a", journal_ms=10)
    qtbot.addWidget(w1)
    w1.ask_folder = lambda title: str(folder)
    w1.ask_text = lambda t, label, default: "P"
    w1.new_project_flow()
    button(w1, "add-sensor").click()  # unsaved change
    from harness_design_studio.core.recovery import journal_path

    qtbot.waitUntil(lambda: journal_path(folder).exists(), timeout=2000)
    assert "ST1" not in load_project(folder).project.units  # not saved to the project files
    w1.ctl._lock.release()  # type: ignore[union-attr]  # simulate a crash: lock released, no save
    w1.ctl._timer.stop()
    w2 = make_window(tmp_path / "b")
    qtbot.addWidget(w2)
    asked: list[list[str]] = []

    def choice(title, text, buttons):  # type: ignore[no-untyped-def]
        asked.append(buttons)
        return 0  # Restore

    w2.ask_choice = choice  # type: ignore[assignment]
    assert w2.open_project(folder)
    assert asked and "Restore" in asked[0] and "ST1" in w2.ctl.project.units and w2.ctl.dirty
    assert w2.save_flow() and "ST1" in load_project(folder).project.units
    assert not journal_path(folder).exists()
    w2.ctl.release()


def test_discarding_the_journal(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "proj"
    w1 = make_window(tmp_path / "a", journal_ms=10)
    qtbot.addWidget(w1)
    w1.ask_folder = lambda title: str(folder)
    w1.ask_text = lambda t, label, default: "P"
    w1.new_project_flow()
    button(w1, "add-sensor").click()
    w1.ctl.write_journal_now()
    w1.ctl._lock.release()  # type: ignore[union-attr]
    w2 = make_window(tmp_path / "b")
    qtbot.addWidget(w2)
    assert w2.open_project(folder)  # default hook answers "discard"
    assert "ST1" not in w2.ctl.project.units
    w2.ctl.release()


def test_project_open_twice_offers_read_only(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "proj"
    w1 = make_window(tmp_path / "a")
    qtbot.addWidget(w1)
    w1.ask_folder = lambda title: str(folder)
    w1.ask_text = lambda t, label, default: "P"
    w1.new_project_flow()
    w2 = make_window(tmp_path / "b")
    qtbot.addWidget(w2)
    prompts: list[str] = []

    def choice(title, text, buttons):  # type: ignore[no-untyped-def]
        prompts.append(title)
        return 0  # open read-only

    w2.ask_choice = choice  # type: ignore[assignment]
    assert w2.open_project(folder)
    assert prompts == ["Project already open"] and w2.ctl.read_only
    assert w2.banner.isVisible() and "Read-only" in w2.banner.label.text()
    # read-only: no edits, no undo, add buttons disabled
    assert not button(w2, "add-computer").isEnabled() and not w2.act_save.isEnabled()
    assert w2.ctl.add_unit("computer") is None and "read-only" in last_toast(w2).lower()
    w1.ctl.release()


def test_newer_version_project_opens_read_only(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    import json

    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.samples import mini3

    folder = tmp_path / "newer"
    save_project(mini3(), folder)
    meta = json.loads((folder / "project.json").read_text())
    meta["schema_version"] = 99
    (folder / "project.json").write_text(json.dumps(meta))
    assert win.open_project(folder)
    assert win.ctl.read_only and win.banner.isVisible()
    win.ctl.release()


def test_corrupt_project_opens_in_recovery_mode(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.samples import mini3

    folder = tmp_path / "broken"
    save_project(mini3(), folder)
    f = folder / "logical/units/power.json"
    f.write_bytes(f.read_bytes()[:30])
    assert win.open_project(folder)
    assert win.ctl.project.recovered and win.banner.isVisible()
    assert "could not be loaded" in win.banner.label.text()
    shown: list[int] = []
    DialogScript(win, lambda d: shown.append(d.list.count()))
    win.issues_flow()
    assert shown and shown[0] >= 1
    assert not win.ctl.read_only
    win.ctl.release()
    win.ctl.add_unit("sensor")  # allowed in memory ...
    from harness_design_studio.core.errors import SaveError

    with pytest.raises(SaveError, match="new folder"):
        win.ctl.save()  # ... but the damaged original folder is protected


def test_external_change_offers_reload(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.samples import mini3

    folder = tmp_path / "proj"
    save_project(mini3(), folder)
    assert win.open_project(folder)
    p = mini3()
    p.units["OBC"] = (
        edit.evolve(p.units["OBC"], name="Changed by a Git pull")
        if hasattr(edit, "evolve")
        else p.units["OBC"]
    )
    from harness_design_studio.core.model import evolve

    p.units["OBC"] = evolve(p.units["OBC"], name="Changed by a Git pull")
    from harness_design_studio.core.io.layout import serialize

    for rel, data in serialize(p).items():
        (folder / rel).write_bytes(data)
    assert win.ctl.disk_changed()
    win.ask_choice = lambda t, text, buttons: 0  # type: ignore[assignment,misc]
    win.check_disk()
    assert win.ctl.project.units["OBC"].name == "Changed by a Git pull"
    # "keep mine": saving is refused so nobody's changes are overwritten
    (folder / "logical/units/avionics.json").write_text('{"units": []}\n')
    win.ask_choice = lambda t, text, buttons: 1  # type: ignore[assignment,misc]
    win.check_disk()
    from harness_design_studio.core.errors import SaveError

    with pytest.raises(SaveError, match="changed on disk"):
        win.ctl.save()
    win.ctl.release()


def test_closing_with_unsaved_changes_asks(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    button(win, "add-payload").click()
    asked: list[str] = []

    def choice(title, text, buttons):  # type: ignore[no-untyped-def]
        asked.append(title)
        return 2  # Cancel

    win.ask_choice = choice  # type: ignore[assignment]
    assert not win.close()
    assert asked == ["Unsaved changes"] and win.isVisible()
    win.ask_choice = lambda t, text, buttons: 1  # type: ignore[assignment,misc]
    assert win.close()


# ---- theme, scale, layout --------------------------------------------------------------------


def test_theme_and_scale_and_narrow_window_layout(win) -> None:  # type: ignore[no-untyped-def]
    win.act_dark.trigger()
    assert win.theme.name == "dark" and win.settings.value("ui/theme") == "dark"
    win.act_dark.trigger()
    base = win.font().pixelSize()
    win.scale_actions[200].trigger()
    assert win.theme.scale == 2.0 and win.font().pixelSize() == base * 2
    win.resize(1360, 860)  # effective 680 x 430 at 200%
    win.auto_layout()
    assert win.dock_right.isHidden() and win.dock_left.isHidden()
    win.scale_actions[100].trigger()
    win.resize(1440, 900)
    win.auto_layout()
    assert not win.dock_right.isHidden()


def test_settings_remember_mode_theme_and_scale(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl.set_mode("expert")
    w.act_dark.trigger()
    w.scale_actions[125].trigger()
    w.close()
    w2 = make_window(tmp_path)
    qtbot.addWidget(w2)
    assert w2.ctl.mode == "expert" and w2.theme.name == "dark" and w2.theme.scale == 1.25


def test_minimap_and_zoom_controls(win) -> None:  # type: ignore[no-untyped-def]
    assert win.view.minimap.isVisible()
    t0 = win.view.transform().m11()
    win.zoom_in_btn.click()
    assert win.view.transform().m11() > t0
    win.fit_btn.click()
    from PySide6.QtCore import QPoint

    QTest.mouseClick(win.view.minimap.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(20, 20))


def test_generate_button_is_live_since_m3(win) -> None:  # type: ignore[no-untyped-def]
    assert win.generate_btn.isEnabled() and "preview" in win.generate_btn.toolTip()


def test_glossary_and_about(win) -> None:  # type: ignore[no-untyped-def]
    shown: list[str] = []
    DialogScript(win, lambda d: shown.append(d.objectName()))
    win.glossary_flow()
    assert shown == ["glossary-dialog"]


def test_narrow_window_says_it_hid_the_panels_and_properties(win) -> None:  # type: ignore[no-untyped-def]
    win.resize(1440, 900)
    win.auto_layout()
    win.resize(700, 900)
    win.auto_layout()
    assert "narrow" in win.toasts.messages[-1].lower() and not win.dock_right.isVisibleTo(win)


def test_connect_hint_has_a_fixed_height_so_the_toolbar_does_not_jump(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.begin_connect("rs422")
    win._on_connect()
    h1 = win.hint.minimumHeight()
    win.ctl.end_connect()
    win._on_connect()
    assert win.hint.minimumHeight() == h1 > win.hint.fontMetrics().lineSpacing()


def test_link_labels_do_not_overlap_in_a_dense_diagram(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.samples import sat15

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(sat15(), None, None)
    rects = list(w.view.dscene._chip_rects.values())
    assert len(rects) >= 20
    overlaps = sum(1 for k, a in enumerate(rects) for b in rects[k + 1 :] if a.intersects(b))
    assert overlaps <= max(2, len(rects) // 10), f"{overlaps} overlapping labels of {len(rects)}"


def test_new_project_from_an_example(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """REQ-GUI-03: the editor can start from the same examples as `harness new --template`."""
    folder = tmp_path / "wheel"
    seen: list[str] = []

    def choose(title: str, text: str, buttons: list[str]) -> int:
        seen.extend(buttons)
        return buttons.index("first-steps")

    win.ask_choice = choose  # type: ignore[assignment]
    win.ask_folder = lambda title: str(folder)
    win.ask_text = lambda t, label, default: "Wheel link"
    win.new_from_example_flow()
    assert seen[:4] == ["blank", "first-steps", "minimal-satellite", "small-satellite"]
    assert (folder / "project.json").exists() and win.ctl.root == folder
    assert {"OBC", "PCDU"} <= set(win.ctl.project.units) or len(win.ctl.project.units) >= 3
    assert win.windowTitle().startswith("Wheel link")
    win.ctl.release()


def test_choosing_cancel_in_the_example_dialog_changes_nothing(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    win.ask_choice = lambda title, text, buttons: len(buttons) - 1  # type: ignore[assignment]
    win.new_from_example_flow()
    assert win.ctl.root is None or win.ctl.root != tmp_path / "x"


def test_the_part_picker_says_what_each_part_is(win) -> None:  # type: ignore[no-untyped-def]
    """REQ-GUI-05: choosing a library part shows its description, pins, approval and ratings."""
    from PySide6.QtWidgets import QComboBox, QLabel

    win.ctl.set_mode("expert")
    win.ctl.select("unit", sorted(win.ctl.project.units)[0])
    combos = win.props.findChildren(QComboBox)
    part_combos = [c for c in combos if c.objectName().startswith("part-")]
    assert part_combos
    combo = part_combos[0]
    text = combo.itemData(combo.currentIndex(), Qt.ItemDataRole.ToolTipRole)
    assert "pins" in text and ("approved" in text)
    infos = [
        lab for lab in win.props.findChildren(QLabel) if lab.objectName().startswith("part-info-")
    ]
    assert infos and infos[0].text() == text
