# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-11, REQ-GUI-12. Workshop feedback M2b: connections, the pinout first. The Link connectors window, the
Connect tool, the project tree, the diagram, Create harness, Check my connections and the Next step
page."""

import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core.links import check_links  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.link_dialog import (  # noqa: E402
    CreateHarnessDialog,
    LinkDialog,
    harness_preview,
)
from harness_design_studio.gui.next_step import NextInputs, next_step  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import DialogScript, click_unit, make_window  # noqa: E402
from tests.helpers import pinout_project  # noqa: E402

RS = ("OBC-J01", "RW1-J02")  # RS-422: pins 1 to 4 TX+, TX-, RX+, RX-; pin 5 has no signal
PWR = ("PCDU-J02", "OBC-J02")  # pins 1 and 2: PWR, RTN; pin 3 has no signal


def bare_project():
    """The pinout project with no interface and no harness: only devices with labelled pins."""
    p = pinout_project()
    p.harnesses, p.interfaces, p.baselines = {}, {}, {}
    return p


def window(tmp_path, workspace: str | None = None):
    win = make_window(tmp_path)
    win.ctl._install(bare_project(), None, None)
    if workspace:
        win.set_workspace(workspace)
    QApplication.processEvents()
    return win


def dialog(qtbot, project, **kw) -> LinkDialog:
    _ = QApplication.instance() or QApplication([])
    dlg = LinkDialog(None, ThemeManager(), project, **kw)
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg


def link_up(win, a=RS[0], b=RS[1], *pairs):
    return win.ctl.add_link(a, b, list(pairs) or [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")])


# ---- the window -------------------------------------------------------------------------------


def test_the_window_proposes_the_pairs_by_signal_name(qtbot, tmp_path) -> None:
    win = window(tmp_path)
    dlg = dialog(qtbot, win.ctl.project, a_unit="OBC", b_unit="RW1")
    assert dlg.windowTitle() == strings.LINK_TITLE == "Link connectors"
    assert dlg.a_connector_id() == "OBC-J01" and dlg.b_connector_id() == "RW1-J02"
    assert dlg.pairs() == [("1", "3"), ("2", "4"), ("3", "1"), ("4", "2")]  # TX+ meets RX+
    rows = dlg.rows()
    assert [(r["a_signal"], r["b_signal"]) for r in rows] == [
        ("TX+", "RX+"),
        ("TX-", "RX-"),
        ("RX+", "TX+"),
        ("RX-", "TX-"),
    ]
    assert dlg.model.rowCount() == 4 and dlg.ok.isEnabled()
    assert "5 (" not in dlg.unpaired.text()  # a pin with no signal is not asked about


def test_every_control_has_a_name_and_a_tooltip(qtbot, tmp_path) -> None:
    dlg = dialog(qtbot, window(tmp_path).ctl.project, a_unit="OBC", b_unit="RW1")
    for w in (
        dlg.name_edit, dlg.a_device, dlg.a_conn, dlg.b_device, dlg.b_conn, dlg.a_pin, dlg.b_pin,
        dlg.a_role, dlg.b_role, dlg.add_pair, dlg.change_pair, dlg.remove_pair, dlg.ok,
    ):  # fmt: skip
        assert w.accessibleName() and w.toolTip(), w.objectName()
    assert "the line the current of a signal comes back on" in strings.LINK_ROLE_HELP
    assert "unit" not in " ".join(
        v for k, v in vars(strings).items() if k.startswith("LINK_") and isinstance(v, str)
    ).lower().replace("community", "")


def test_a_pair_can_be_changed_added_and_removed(qtbot, tmp_path) -> None:
    dlg = dialog(qtbot, window(tmp_path).ctl.project, a_unit="OBC", b_unit="RW1")
    dlg.table.selectRow(0)  # the pair 1 - 3 loads its pins
    assert (dlg.a_pin.currentData(), dlg.b_pin.currentData()) == ("1", "3")
    dlg.b_pin.setCurrentIndex(dlg.b_pin.findData("4"))  # change it to 1 - 4 (TX+ to RX-)
    dlg.change_pair.click()
    assert dlg.pairs()[0] == ("1", "4")
    # a pin in two pairs is refused inline, and OK goes off
    assert not dlg.ok.isEnabled() and "two pairs" in dlg.problem.text()
    dlg.table.selectRow(1)
    dlg.remove_pair.click()
    dlg.table.selectRow(2)
    dlg.remove_pair.click()
    assert dlg.pairs() == [("1", "4"), ("3", "1")] and dlg.ok.isEnabled()
    dlg.a_pin.setCurrentIndex(dlg.a_pin.findData("2"))
    dlg.b_pin.setCurrentIndex(dlg.b_pin.findData("3"))
    dlg.add_pair.click()
    assert dlg.pairs()[-1] == ("2", "3") and dlg.model.rowCount() == 3


def test_a_review_is_written_under_the_table_and_a_role_changes_it(qtbot, tmp_path) -> None:
    win = window(tmp_path)
    dlg = dialog(
        qtbot, win.ctl.project, a_unit="PCDU", a_connector=PWR[0], b_unit="OBC", b_connector=PWR[1]
    )  # PWR and RTN
    assert dlg.pairs() == [("1", "1"), ("2", "2")] and not dlg.review.isVisibleTo(dlg)
    dlg.table.selectRow(1)  # take the return pair out: power without a return
    dlg.remove_pair.click()
    assert dlg.review.isVisibleTo(dlg) and "no return" in dlg.review.text()
    assert dlg.ok.isEnabled()  # the review warns, it does not forbid
    # a pin called Spare is not asked about any more
    assert "PCDU-J02" in dlg.unpaired.text()
    dlg.a_pin.setCurrentIndex(dlg.a_pin.findData("2"))
    dlg.a_role.setCurrentIndex(dlg.a_role.findData("spare"))
    assert dlg.roles() == {("PCDU-J02", "2"): "spare"}
    assert "PCDU-J02" not in dlg.unpaired.text() and "OBC-J02" in dlg.unpaired.text()


def test_the_notes_of_the_proposal_are_shown_in_plain_words(qtbot, tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win)
    dlg = dialog(qtbot, win.ctl.project, a_unit="OBC", a_connector="OBC-J01", b_unit="RW1")
    assert "already paired in link L1" in dlg.notes.text()
    assert dlg.pairs() == [] and not dlg.ok.isEnabled() and dlg.problem.text()


def test_the_same_device_twice_is_refused_inline(qtbot, tmp_path) -> None:
    dlg = dialog(qtbot, window(tmp_path).ctl.project, a_unit="OBC", b_unit="OBC")
    assert not dlg.ok.isEnabled() and "different devices" in dlg.problem.text()


# ---- making and changing a connection --------------------------------------------------------------


def test_ok_makes_one_undoable_connection_with_the_roles(tmp_path) -> None:
    win = window(tmp_path)

    def fill(dlg) -> None:
        assert dlg.a_device.currentData() != dlg.b_device.currentData()  # two devices to start with
        dlg.a_device.setCurrentIndex(dlg.a_device.findData("OBC"))
        dlg.b_device.setCurrentIndex(dlg.b_device.findData("RW1"))
        dlg.a_conn.setCurrentIndex(dlg.a_conn.findData("OBC-J01"))
        dlg.b_conn.setCurrentIndex(dlg.b_conn.findData("RW1-J02"))
        dlg.a_pin.setCurrentIndex(dlg.a_pin.findData("5"))
        dlg.a_role.setCurrentIndex(dlg.a_role.findData("spare"))
        dlg.name_edit.setText("Telemetry")

    DialogScript(win, fill)
    win.act_link_connectors.trigger()
    p = win.ctl.project
    assert list(p.links) == ["L1"] and p.links["L1"].name == "Telemetry"
    assert [(x.a_pin, x.b_pin) for x in p.links["L1"].pairs] == [
        ("1", "3"), ("2", "4"), ("3", "1"), ("4", "2"),
    ]  # fmt: skip
    pin5 = next(x for x in p.connectors["OBC-J01"].pins if x.id == "5")
    assert pin5.role == "spare"
    assert win.ctl.selected_link == "L1"
    win.ctl.undo()  # one step takes the connection and the role back
    assert not win.ctl.project.links
    assert next(x for x in win.ctl.project.connectors["OBC-J01"].pins if x.id == "5").role == ""
    win.ctl.redo()
    assert "L1" in win.ctl.project.links


def test_cancel_changes_nothing(tmp_path) -> None:
    win = window(tmp_path)
    DialogScript(win, accept=False)
    win.act_link_connectors.trigger()
    assert not win.ctl.project.links and not win.ctl.history.can_undo


def test_the_pairs_of_a_connection_can_be_edited(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"

    def fewer(dlg) -> None:
        assert dlg.link_id == "L1" and not dlg.a_device.isEnabled()
        dlg.table.selectRow(3)
        dlg.remove_pair.click()

    shown = DialogScript(win, fewer)
    win.edit_link_flow("L1")
    assert shown.seen and len(win.ctl.project.links["L1"].pairs) == 3
    win.ctl.undo()
    assert len(win.ctl.project.links["L1"].pairs) == 4


# ---- the Connect tool -----------------------------------------------------------------------------


def test_the_connect_tool_opens_the_window_with_the_two_devices(tmp_path) -> None:
    win = window(tmp_path)
    seen: list[LinkDialog] = []
    DialogScript(win, seen.append, accept=False)
    win.act_connect_tool.trigger()
    assert win.ctl.tool == "connect" and win.ctl.linking and win.tool_connect.isChecked()
    assert win.hint.text() == strings.LINK_HINT_FIRST
    click_unit(win, "OBC")
    assert win.ctl.connect_from.unit_id == "OBC"
    assert "OBC" in win.hint.text()
    click_unit(win, "OBC")  # the same device again is refused in words
    assert not seen
    click_unit(win, "RW1")
    assert len(seen) == 1
    dlg = seen[0]
    assert (dlg.a_device.currentData(), dlg.b_device.currentData()) == ("OBC", "RW1")
    assert win.ctl.connect_from is None and win.ctl.tool == "connect"  # ready for the next one


def test_the_shortcut_and_the_button_start_the_pinout_way_and_the_type_way_stays(tmp_path) -> None:
    win = window(tmp_path)
    assert win.act_connect_tool.shortcut().toString() == "C"
    win.tool_connect.click()
    assert win.ctl.linking
    win.ctl.end_connect()
    assert win.menu_connect.title() == strings.M_CONNECT_WITH_TYPE
    win.menu_connect.actions()[0].trigger()  # an interface type: the older way
    assert win.ctl.tool == "connect" and win.ctl.connect_type and not win.ctl.linking
    assert win.act_link_connectors.shortcut().toString() == "Ctrl+Shift+K"


def test_a_read_only_project_refuses_to_link(tmp_path) -> None:
    win = window(tmp_path)
    win.ctl.project.read_only = True
    win.ctl.begin_link()
    messages: list[str] = []
    win.ctl.message.connect(lambda t, _u: messages.append(t))
    click_unit(win, "OBC")
    assert messages and win.ctl.connect_from is None


# ---- the tree, the diagram, the selection ---------------------------------------------------------------


def test_the_tree_lists_connections_with_their_actions(tmp_path) -> None:
    win = window(tmp_path)
    tree = win.project_tree
    assert tree.child_ids("links") == []
    assert link_up(win) == "L1"
    assert tree.child_ids("links") == ["L1"]
    node = tree.model.find("link", "L1")
    assert node.name == "OBC-J01 - RW1-J02" and node.ident == "L1"
    assert strings.TREE_ROOTS["links"] == "Connections"
    assert "4 pairs" in tree.model.tooltip(node) and "RS-422" in tree.model.tooltip(node)
    menu = tree.build_menu("link", "L1")
    names = {a.objectName() for a in menu.actions() if a.objectName()}
    assert {"tree-link-edit", "tree-link-rename", "tree-link-harness", "tree-link-delete"} <= names
    # a click selects it on the diagram; selecting a device puts it down again
    tree._select_kind("link", "L1")
    assert win.ctl.selected_link == "L1"
    win.ctl.select("unit", "OBC")
    assert win.ctl.selected_link is None
    win.ctl.select_link("L1")
    assert tree.current() == ("link", "L1") and win.ctl.selection is None
    tree.model.refresh_counts()


def test_a_connection_is_drawn_between_its_devices_and_follows_them(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    scene = win.view.dscene
    item = scene.connection_items["L1"]
    assert len(item.poly) >= 4 and "RS-422" in item.text
    assert "RS-422, 4 wires" in item.tooltip_html() and "OBC-J01 - RW1-J02" in item.tooltip_html()
    before = list(item.poly)
    win.ctl.move_unit("RW1", 900.0, 400.0)
    QApplication.processEvents()
    assert item.poly != before
    first, last = item.poly[0], item.poly[-1]
    ua, ub = scene.unit_items["OBC"], scene.unit_items["RW1"]
    assert ua.pos().x() <= first[0] <= ua.pos().x() + 260 and ub.pos().x() <= last[0] + 260
    win.ctl.undo()
    win.ctl.undo()
    assert "L1" not in scene.connection_items
    win.ctl.redo()
    assert "L1" in scene.connection_items


def test_the_empty_hint_goes_when_a_connection_exists(tmp_path) -> None:
    win = window(tmp_path)
    assert not win.view.empty.isHidden() and win.view.empty.text() == strings.EMPTY_NO_LINKS
    link_up(win)
    assert win.view.empty.isHidden()
    win.ctl.undo()
    assert not win.view.empty.isHidden()


def test_picking_a_connection_on_the_diagram_selects_it(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.ctl.select(None)
    item = win.view.dscene.connection_items["L1"]
    item.mousePressEvent(_press())
    assert win.ctl.selected_link == "L1"
    assert win.act_link_edit.isEnabled() and win.act_link_harness.isEnabled()
    win.ctl.select("unit", "OBC")
    assert not win.act_link_edit.isEnabled()


def _press():
    class Event:
        def button(self):
            return Qt.MouseButton.LeftButton

        def accept(self):
            pass

        def ignore(self):
            pass

    return Event()


# ---- Create harness: only on the button ---------------------------------------------------------------


def test_nothing_makes_a_harness_but_the_button(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    win.ctl.run_drc_now()
    assert not win.ctl.project.harnesses  # a connection, a check and a generate plan: no harness
    sentence = harness_preview(win.ctl.project, "L1")
    assert "4 wires" in sentence and "OBC-J01 - RW1-J02" in sentence
    shown = DialogScript(win, accept=False)  # Cancel: nothing happens
    win.act_link_harness.trigger()
    assert isinstance(shown.seen[0], CreateHarnessDialog) and not win.ctl.project.harnesses
    DialogScript(win)  # OK
    win.act_link_harness.trigger()
    p = win.ctl.project
    assert len(p.harnesses) == 1 and p.links["L1"].harness_id in p.harnesses
    h = p.harnesses[p.links["L1"].harness_id]
    assert not h.generated and len(h.wires) == 4 and all(w.manual for w in h.wires)
    assert not win.act_link_harness.isEnabled()  # one harness per connection
    win.ctl.undo()
    assert not win.ctl.project.harnesses and not win.ctl.project.links["L1"].harness_id


def test_the_harness_button_says_why_it_cannot(tmp_path) -> None:
    win = window(tmp_path)
    assert win.ctl.add_link(*RS, [("1", "3")]) == "L1"
    DialogScript(win)
    win.act_link_harness.trigger()
    assert len(win.ctl.project.harnesses) == 1
    messages: list[str] = []
    win.toasts.show_message = lambda text, *a, **k: messages.append(text)
    win.create_harness_flow("L1")
    assert messages and "has the harness" in messages[-1]


# ---- Check my connections --------------------------------------------------------------------------


def test_check_my_connections_shows_findings_as_cards_that_lead_to_the_connection(tmp_path) -> None:
    win = window(tmp_path)
    messages: list[str] = []
    win.toasts.show_message = lambda text, *a, **k: messages.append(text)
    win.act_check_connections.trigger()
    assert messages[-1] == strings.LINK_CHECK_NONE
    # pins 3 and 4 are left out: two pins with a signal are not paired
    assert win.ctl.add_link(*RS, [("1", "3"), ("2", "4")]) == "L1"
    found = check_links(win.ctl.project)
    assert {f.code for f in found} == {"link_pin_unpaired"} and len(found) == 4
    win.act_check_connections.trigger()
    assert "4 things" in messages[-1] and win.dock_problems.isVisible()
    win.ctl.run_drc_now()
    win.problems_list.refresh()
    assert win.problems_list.filters["links"].isChecked()
    rows = win.problems_list.rows()
    assert sum(r["rule"] == "link-unpaired" for r in rows) == 4
    visible = win.problems_list.table.proxy.rowCount()
    assert visible == 4
    # the card's "Show" goes to the connection on the diagram
    win.ctl.select(None)
    win.show_object("L1")
    assert win.ctl.selected_link == "L1"
    # and the state index puts the warnings on the connection itself
    assert win.view.dscene.states.of("link", "L1").warnings == 4


def test_a_clean_review_says_so(tmp_path) -> None:
    win = window(tmp_path)
    assert link_up(win) == "L1"
    messages: list[str] = []
    win.toasts.show_message = lambda text, *a, **k: messages.append(text)
    win.act_check_connections.trigger()
    assert messages[-1] == strings.LINK_CHECK_CLEAN


# ---- the Next step page ----------------------------------------------------------------------------


def key(**kw) -> str:
    return next_step(NextInputs(**kw)).key


def test_connections_count_as_connected() -> None:
    assert key(units=2) == "connect"
    assert key(units=2, links=1) == "make_harness"  # the one button makes the harness
    n = next_step(NextInputs(units=2, links=1))
    assert n.button == "Create harness" and n.steps[1].state == "done"
    assert n.steps[2].state == "next"
    # a harness made from a connection is a harness by hand: Generate is not forced
    assert key(units=2, links=1, harnesses=1, hand_made_harnesses=1) == "check"
    assert key(units=2, links=1, harnesses=1, hand_made_harnesses=1, checked=True) == "build_sheets"
    # interfaces keep their way; mixed harnesses still generate
    assert key(units=2, interfaces=1) == "generate"
    assert key(units=2, links=1, interfaces=1, harnesses=1, hand_made_harnesses=0) == "generate"
    assert "connector" in strings.NEXT_CONNECT_WHY


def test_the_next_page_follows_the_connections_in_both_workspaces(tmp_path) -> None:
    for workspace in ("simple", "full"):
        win = window(tmp_path / workspace, workspace)
        win.ctl.new_project(tmp_path / f"blank-{workspace}", "Blank")
        a, b = win.ctl.add_unit("computer"), win.ctl.add_unit("power")
        QApplication.processEvents()
        page = win.next_page
        assert page.key() == "connect"
        assert win.ctl.add_link  # (a window of the pinout needs connectors: the sample has them)
        win.ctl._install(bare_project(), None, None)
        assert link_up(win)
        QApplication.processEvents()
        assert page.key() == "make_harness" and page.button.text() == "Create harness"
        DialogScript(win)
        page.button.click()
        QApplication.processEvents()
        assert len(win.ctl.project.harnesses) == 1
        assert page.key() == "check", (workspace, page.key())
        assert a and b


def test_the_connect_tool_works_in_the_simple_workspace(tmp_path) -> None:
    win = window(tmp_path, "simple")
    seen: list[QDialog] = []
    DialogScript(win, seen.append, accept=False)
    win.act_connect_tool.trigger()
    win.ctl.pick("OBC")
    win.ctl.pick("RW1")
    assert len(seen) == 1 and win.ctl.linking


# ---- the keyboard and the screen reader ----------------------------------------------------------------


def test_the_windows_open_in_both_themes_with_names_and_no_qt_warnings(tmp_path) -> None:
    from PySide6.QtCore import QtMsgType, qInstallMessageHandler

    from tests.test_accessibility import unnamed

    win = window(tmp_path)
    assert link_up(win) == "L1"
    seen: list[str] = []

    def handler(kind, _context, message) -> None:
        if kind in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg):
            seen.append(message)

    previous = qInstallMessageHandler(handler)
    try:
        for theme in ("light", "dark"):
            win.set_theme_mode(theme)
            win.go_to("diagram")
            win.ctl.select_link("L1")
            QApplication.processEvents()
            assert unnamed(win) == []
            for dlg in (
                LinkDialog(win, win.theme, win.ctl.project, link_id="L1"),
                LinkDialog(win, win.theme, win.ctl.project, a_unit="PCDU", b_unit="OBC"),
                CreateHarnessDialog(win, win.theme, harness_preview(win.ctl.project, "L1")),
            ):
                dlg.show()
                QApplication.processEvents()
                assert unnamed(dlg) == [], type(dlg).__name__
                dlg.close()
    finally:
        qInstallMessageHandler(previous)
    assert [m for m in seen if "propagateSizeHints" not in m] == []
