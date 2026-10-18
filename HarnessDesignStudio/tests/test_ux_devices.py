# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""CD-B3 (read-only Devices tab) of the custom device editor: the sixth main tab, the header, the
connector list and card, the pin table with its derived columns, the notes, the pinout as exported
and its export; empty, locked and read-only states; names for assistive tools; speed. Offscreen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from harness_design_studio.core import devices, edit  # noqa: E402
from harness_design_studio.core.commands import History  # noqa: E402
from harness_design_studio.core.model import Project  # noqa: E402
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of  # noqa: E402
from harness_design_studio.core.samples import new_project, sat15_full  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.devices_view import DevicesView  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.test_change_control import do_release, exported, full, releasable  # noqa: E402
from tests.test_edit_device import device, with_connector  # noqa: E402


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


def make_view(qtbot, theme, project: Project, size=(1280, 720)):
    ctl = EditorController()
    ctl._install(project, None, None)
    view = DevicesView(ctl, theme)
    qtbot.addWidget(view)
    view.resize(*size)
    view.show()
    return ctl, view


def custom() -> Project:
    """GYRO1 with one 6-pin connector: power on A1, A2 (fixed), CAN half there, a free-text signal."""
    p, cid = with_connector()
    h = History(p)
    h.execute("r", devices.ops_rename_pin(p, cid, "1", "A1"))
    h.execute("r", devices.ops_rename_pin(p, cid, "2", "A2"))
    h.execute("f", devices.fill_from_type(p, cid, ["A1", "A2"], "power_primary"))
    h.execute("s", devices.ops_set_pin(p, cid, "3", signal="CANH", mode="fixed"))
    h.execute("s", devices.ops_set_pin(p, cid, "4", signal="HEATER_ENABLE"))
    return p


def cell(view: DevicesView, row: int, key: str) -> str:
    return view.pin_model.text_at(row, view.pin_model.column_index(key))


def state_of(view: DevicesView, row: int, key: str) -> str | None:
    return view.pin_model.state_at(row, view.pin_model.column_index(key))


# ---- the tab --------------------------------------------------------------------------------


def test_devices_is_the_sixth_main_tab_with_ctrl_6(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    assert win.main_tabs.visible_names() == [
        "diagram",
        "harness",
        "lists",
        "checks",
        "releases",
        "devices",
    ]
    act = win.go_actions["devices"]
    assert act.shortcut().toString() == "Ctrl+6" and "Ctrl+6" in act.toolTip()
    assert strings.TAB_TIP.format(strings.TAB_DEVICES, 6) in win.main_tabs.tabToolTip(5)
    assert win.view_installed("devices") and isinstance(win.view_widget("devices"), DevicesView)
    act.trigger()
    assert win.main_tabs.currentWidget() is win.devices_view
    assert win.go_to("devices")
    assert act in win.menu_go.actions()


def test_a_unit_selected_on_the_diagram_or_in_the_tree_is_the_device_shown(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    p = sat15_full()
    win.ctl._install(p, None, None)
    win.go_actions["devices"].trigger()
    win.ctl.select("unit", "RW1")
    assert win.devices_view.unit_id() == "RW1" and win.devices_view.selector.currentData() == "RW1"
    assert win.devices_view.name.text() == p.units["RW1"].name
    win.ctl.select("unit", "SA1")
    assert win.devices_view.unit_id() == "SA1"
    # picking in the Devices tab selects the unit on the diagram and in the tree
    win.devices_view.selector.setCurrentIndex(win.devices_view.selector.findData("PL1"))
    assert win.ctl.selection is not None and win.ctl.selection.id == "PL1"


# ---- one device -----------------------------------------------------------------------------


def test_header_counts_state_and_connector_list(qtbot, theme) -> None:
    p = custom()
    ops, c2 = devices.ops_add_connector(p, "GYRO1", part_id="MY-PLAIN-4")
    History(p).execute("a", ops)
    ctl, view = make_view(qtbot, theme, p)
    assert view.unit_id() == "GYRO1" and view.connector_id() == "GYRO1-J01"
    assert view.name.text() == "Gyro unit"
    assert "aocs" in view.subsystem.text() and "Nominal chain" in view.subsystem.text()
    assert view.counts.text() == "2 connectors, 10 pins, 4 signals set, 0 interfaces"
    assert (view.state_chip.state(), view.state_chip.text()) == ("draft", "Draft")
    rows = view.conn_model.rows()
    assert [r["name"] for r in rows] == ["J01", "J02"] and [r["pins"] for r in rows] == [6, 4]
    assert view.conn_model.text_at(0, 0) == "J01"
    # J02 has a note (gender cannot be judged), so its chip says so; J01 has a note about CAN
    assert view.conn_model.state_at(1, view.conn_model.column_index("state")) == "warning"
    # choosing the second connector shows its pins
    view.conn_table.selectRow(1)
    assert view.connector_id() == "GYRO1-J02" and view.pin_model.rowCount() == 4
    assert view.pins_caption.text() == "PINS OF J02" or "J02" in view.pins_caption.text()


def test_pin_table_columns_and_derived_meaning(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, custom())
    m = view.pin_model
    assert [c.header for c in m.columns][:8] == [
        "Pin",
        "Signal",
        "Mode",
        "Interface",
        "Direction",
        "Class",
        "Wire",
        "Contact size",
    ]
    assert m.rowCount() == 6
    assert [cell(view, r, "pin") for r in range(6)] == ["A1", "A2", "3", "4", "5", "6"]
    assert (cell(view, 0, "signal"), cell(view, 0, "mode")) == ("PWR", "Fixed")
    assert (cell(view, 0, "direction"), cell(view, 0, "class")) == ("passive", "power")
    assert (cell(view, 2, "direction"), cell(view, 2, "class")) == ("bidir", "data")
    # free text: no direction, no class, the reason as tooltip; never guessed
    assert (cell(view, 3, "direction"), cell(view, 3, "class")) == ("", "")
    tip = m.data(m.index(3, m.column_index("direction")), Qt.ItemDataRole.ToolTipRole)
    assert "No interface type has a signal called 'HEATER_ENABLE'" in tip
    assert cell(view, 4, "state") == "Spare" and state_of(view, 4, "state") is None
    assert cell(view, 3, "state") == "Note" and state_of(view, 3, "state") == "info"
    # contact columns are hidden until asked for
    col = m.column_index("contact_size")
    assert view.pin_table.isColumnHidden(col)
    view.contact_btn.click()
    assert not view.pin_table.isColumnHidden(col)


def test_the_notes_name_the_pin_and_a_double_click_selects_it(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, custom())
    notes = view.notes()
    assert {n.code for n in notes} >= {"signal_unknown", "interface_incomplete"}
    assert view.note_model.rowCount() == len(notes)
    assert view.note_label.text() == f"{len(notes)} notes"
    row = next(r for r in view.note_model.rows() if r["check"] == "CD-K4")
    assert row["where"] == "4" and row["severity"] == "Note"
    k = view.note_model.rows().index(row)
    assert view.note_model.state_at(k, 0) == "info"
    view._note_activated(view.note_table.proxy.mapFromSource(view.note_model.index(k, 0)))
    assert view.current_pin() == "4"


def test_a_clean_connector_says_so(qtbot, theme) -> None:
    p, cid = with_connector()
    History(p).execute("g", devices.ops_update_connector(p, cid, gender="female"))
    ctl, view = make_view(qtbot, theme, p)
    assert view.note_label.text() == strings.DV_NOTES_NONE and not view.note_table.isVisibleTo(view)


def test_card_says_how_pins_are_allocated(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, custom())
    assert view.card_values["allocation"].text() == strings.DV_ALLOC_FIXED
    assert (
        "MY-HD-6-F" in view.card_values["part"].text()
        and view.card_values["gender"].text() == "female"
    )
    assert view.card_values["keying"].text() == strings.DV_CARD_NONE
    assert view.card_values["carries"].text() == strings.DV_CARD_ANY
    p = device()
    ops, _ = devices.ops_add_connector(p, "GYRO1", part_id="MY-HD-6-F", carries=["can"])
    History(p).execute("a", ops)
    ctl2, view2 = make_view(qtbot, theme, p)
    assert view2.card_values["allocation"].text() == strings.DV_ALLOC_AUTO
    assert view2.card_values["carries"].text() == "CAN"


def test_the_pin_table_filter_and_count(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, custom())
    assert view.pin_count.text() == "6 pins"
    view.pin_filter.setText("can")
    assert view.pin_table.proxy.rowCount() == 1 and view.pin_count.text() == "1 of 6 pins"
    view.pin_filter.setText("")
    view.pin_table.setFocus()
    view.activateWindow()
    qtbot.waitUntil(view.isActiveWindow)
    QTest.keyClick(view, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert view.pin_filter.hasFocus()


def test_the_pinout_as_exported_is_the_rows_of_box_pinouts_for_this_unit(
    qtbot, theme, tmp_path: Path
) -> None:
    p = custom()
    ctl, view = make_view(qtbot, theme, p)
    assert view.pinout() == devices.pinout_table(p, "GYRO1")
    assert view.preview_model.rowCount() == 6 and view.preview_model.columnCount() == 9
    assert view.preview_model.text_at(0, 0) == "GYRO1-J01"
    # the exported file is the file box_pinouts.csv would hold for the unit, with the same stamp
    target = view.export_to(tmp_path / "gyro")
    assert target.suffix == ".csv"
    assert target.read_bytes() == csv_bytes(devices.pinout_table(p, "GYRO1"), stamp_of(p))
    rows = parse_csv(target.read_bytes())
    assert (
        rows[0][:2] == ["Connector", "Role"]
        and ["GYRO1-J01", "box", "", "MY-HD-6-F", "A1", "PWR", "", "", "no"] in rows
    )
    xlsx = view.export_to(tmp_path / "gyro.xlsx")
    assert xlsx.read_bytes()[:2] == b"PK"


def test_export_through_the_window_asks_for_a_file_and_says_where_it_went(
    qtbot, tmp_path: Path
) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(custom(), None, None)
    win.go_actions["devices"].trigger()
    asked: dict[str, str] = {}

    def ask(title, suggested, filters):
        asked.update(title=title, suggested=suggested, filters=filters)
        return str(tmp_path / "out.csv")

    win.ask_save_path = ask
    win.devices_view.export_btn.click()
    assert asked["suggested"] == "GYRO1_pinout.csv" and "xlsx" in asked["filters"]
    assert (tmp_path / "out.csv").is_file()


def test_duplicate_is_one_undo_step_and_shows_the_copy(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(custom(), None, None)
    win.go_actions["devices"].trigger()
    before = set(win.ctl.project.units)
    win.devices_view.duplicate_btn.click()
    made = set(win.ctl.project.units) - before
    assert len(made) == 1
    assert win.devices_view.unit_id() in made  # the copy is selected, so it is the device shown
    win.ctl.undo()
    assert set(win.ctl.project.units) == before


# ---- states ---------------------------------------------------------------------------------


def test_empty_project_shows_an_empty_state_with_one_button(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, new_project())
    assert view.stack.currentWidget() is view.empty and view.unit_id() is None
    assert view.empty_add.isEnabled() and view.empty_add.toolTip()
    asked = []
    view.addRequested.connect(lambda: asked.append(1))
    view.empty_add.click()
    assert asked == [1]
    ctl.project.read_only = True
    view.refresh()
    assert not view.empty_add.isEnabled()


def test_a_unit_without_connectors_says_so(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, device())
    assert view.connector_id() is None and view.no_connectors.isVisibleTo(view)
    assert view.pin_model.rowCount() == 0 and view.counts.text().startswith("0 connectors")
    assert not view.export_btn.isEnabled()


def test_a_released_device_shows_locked_with_the_sentence_and_read_only_wins(
    qtbot, theme, tmp_path: Path
) -> None:
    p = full()
    hid = releasable(p)
    do_release(p, hid, exported(p, tmp_path))
    cid = next(c.mates_with for c in p.harnesses[hid].connectors if c.mates_with)
    unit = p.connectors[cid].unit_id
    ctl, view = make_view(qtbot, theme, p)
    view.show_unit(unit, cid)
    assert (view.state_chip.state(), view.state_chip.text()) == ("locked", "Locked")
    assert hid in view.state_chip.toolTip() and "released" in view.state_chip.toolTip()
    row = view.conn_model.rows()[0]
    assert row["state"] == "Locked" and hid in row["state_tip"]
    assert view.card.toolTip() and hid in view.card.toolTip()
    used = next(r for r in view.pin_model.rows() if r["state"] == "Locked")
    assert hid in used["state_tip"]
    ctl.project.read_only = True
    view._dirty = True
    view.refresh()
    assert view.state_chip.text() == "Read-only" and not view.duplicate_btn.isEnabled()


def test_auto_filled_pins_after_generate_have_a_chip_and_a_wire(qtbot, theme) -> None:
    p = sat15_full()
    ctl, view = make_view(qtbot, theme, p)
    view.show_unit("RW1")
    auto = [
        k
        for k in range(view.pin_model.rowCount())
        if cell(view, k, "state") == strings.DV_STATE_AUTO
    ]
    assert auto and state_of(view, auto[0], "state") == "info"
    assert cell(view, auto[0], "wire").startswith("W") and cell(
        view, auto[0], "interface"
    ).startswith("IF-")
    assert cell(view, auto[0], "direction") != ""  # the pin's own interface decides
    box = {r[4]: r for r in view.pinout()[1:] if r[0] == view.connector_id()}
    assert all(box[cell(view, k, "pin")][7] for k in auto)  # the export lists the same wires


def test_a_pin_double_click_asks_for_the_reasons(qtbot, theme) -> None:
    p = sat15_full()
    ctl, view = make_view(qtbot, theme, p)
    view.show_unit("RW1")
    asked = []
    view.whyRequested.connect(lambda kind, ident: asked.append((kind, ident)))
    view.select_pin("1")
    view._pin_activated(view.pin_table.currentIndex())
    assert asked == [("pin", f"{view.connector_id()}.1")]


# ---- names, themes, speed -------------------------------------------------------------------


def test_every_control_has_a_name_and_a_tooltip(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(custom(), None, None)
    win.go_actions["devices"].trigger()
    assert unnamed(win.devices_view) == []
    for button in (
        win.devices_view.duplicate_btn,
        win.devices_view.export_btn,
        win.devices_view.contact_btn,
    ):
        assert button.toolTip() and button.accessibleName()
    assert "Ctrl+D" in win.devices_view.duplicate_btn.toolTip()
    assert win.devices_view.selector.accessibleName() == strings.DV_DEVICE
    for table in (
        win.devices_view.conn_table,
        win.devices_view.pin_table,
        win.devices_view.note_table,
        win.devices_view.preview_table,
    ):
        assert table.accessibleName()
    win.ctl._install(new_project(), None, None)
    assert unnamed(win.devices_view) == []


@pytest.mark.parametrize(
    ("mode", "size"), [("light", (1280, 720)), ("dark", (1280, 720)), ("light", (1500, 950))]
)
def test_it_draws_in_both_themes_and_sizes(qtbot, qapp, mode: str, size: tuple[int, int]) -> None:
    th = ThemeManager()
    th.apply(qapp, mode, 1.0)
    try:
        ctl, view = make_view(qtbot, th, custom(), size)
        pixmap = view.grab()
        assert not pixmap.isNull() and pixmap.width() == size[0]
        assert view.minimumSizeHint().width() <= size[0] - 400  # the tab fits a 1280 px window
        for t in (view.pin_table, view.conn_table, view.note_table, view.preview_table):
            assert t.isVisibleTo(view) or t is view.note_table
    finally:
        ThemeManager().apply(qapp, "light", 1.0)


@pytest.mark.perf
def test_a_connector_with_1000_pins_in_a_100_unit_project_refreshes_fast(qtbot, theme) -> None:
    import time

    from harness_design_studio.core.model import Part
    from harness_design_studio.core.samples import stress_project
    from tests.helpers import time_limit

    p = stress_project(units=100, interfaces=600)
    p.parts["BIG-1000"] = Part(id="BIG-1000", category="connector", pin_count=1000)
    uid = next(iter(p.units))
    ops, cid = devices.ops_add_connector(p, uid, part_id="BIG-1000")
    History(p).execute("add", ops)
    ctl, view = make_view(qtbot, theme, p)
    view.show_unit(uid, cid)
    assert view.pin_model.rowCount() == 1000
    start = time.perf_counter()
    ctl.run("edit", devices.ops_set_pin(p, cid, "500", signal="PWR"))
    view.refresh()
    assert time.perf_counter() - start < time_limit(0.5)
    QApplication.processEvents()
    assert cell(view, 499, "signal") == "PWR"


def test_the_view_never_changes_the_project_itself() -> None:
    """The view asks the window (signals) and the controller; it has no plan, no History and no
    style sheet of its own."""
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "harness_design_studio"
        / "gui"
        / "devices_view.py"
    )
    text = src.read_text()
    assert "ops_" not in text and "History" not in text and "setStyleSheet" not in text


def test_widgets_are_children_of_the_view(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, custom())
    assert all(isinstance(w, QWidget) for w in view.findChildren(QWidget))
    assert edit.unit_connectors(ctl.project, "GYRO1")
