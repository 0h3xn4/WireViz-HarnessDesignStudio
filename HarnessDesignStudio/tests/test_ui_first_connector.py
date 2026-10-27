# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-13. Release 1.9 W1: the first connector in Add device, Add a connector inside the
connection window, Pair by pin number and Paste a pairing (the person accepts every proposal)."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import devices  # noqa: E402
from harness_design_studio.core import first_connector as fc  # noqa: E402
from harness_design_studio.core.commands import History  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.connector_picker import ConnectorPicker  # noqa: E402
from harness_design_studio.gui.devices_dialogs import NewDeviceDialog  # noqa: E402
from harness_design_studio.gui.link_dialog import (  # noqa: E402
    AddConnectorDialog,
    LinkDialog,
    PastePairingDialog,
)
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402


def project_with(*devices: tuple[str, str | None]):
    """A blank project with these (ID, first connector part or None) devices."""
    p = new_project()
    for uid, part in devices:
        ops, _u, _c = fc.plan_device_with_connector(p, part, unit_id=uid, name=uid)
        History(p).execute("add", ops)
    return p


def _plan_for(dlg, uid, part):
    d = AddConnectorDialog(dlg, dlg.theme, dlg.project, uid)
    d.picker.select(part)
    return d.plan()


def link_dialog(qtbot, project, **kw) -> LinkDialog:
    _ = QApplication.instance() or QApplication([])
    dlg = LinkDialog(None, ThemeManager(), project, **kw)
    qtbot.addWidget(dlg)
    dlg.show()
    return dlg


# ---- the picker and Add device ----------------------------------------------------------------


def test_the_picker_offers_family_pins_and_gender(qtbot) -> None:
    _ = QApplication.instance() or QApplication([])
    pick = ConnectorPicker(new_project())
    qtbot.addWidget(pick)
    families = [pick.family.itemText(i) for i in range(pick.family.count())]
    assert "Micro-D" in families and "D-sub" in families
    assert pick.select("EX-MICROD-15-F")
    assert [pick.pins.itemText(i) for i in range(pick.pins.count())] == ["9", "15", "21", "25", "31"]  # fmt: skip
    assert pick.part_id() == "EX-MICROD-15-F"
    assert [pick.gender.itemText(i) for i in range(pick.gender.count())] == ["male", "female"]
    pick.gender.setCurrentIndex(0)
    assert pick.part_id() == "EX-MICROD-15-M"
    pick.family.setCurrentIndex(pick.family.findText("D-sub"))
    assert pick.part_id().startswith("EX-DSUB-")
    for w in (pick.family, pick.pins, pick.gender):
        assert w.accessibleName() and w.toolTip()


def test_an_optional_picker_starts_with_no_connector(qtbot) -> None:
    _ = QApplication.instance() or QApplication([])
    pick = ConnectorPicker(new_project(), optional=True)
    qtbot.addWidget(pick)
    assert pick.family.currentText() == strings.CPICK_NONE == "No connector yet"
    assert pick.part_id() == "" and not pick.pins.isEnabled() and not pick.gender.isEnabled()
    assert pick.select("EX-RJ45-F") and pick.part_id() == "EX-RJ45-F"


def test_add_device_dialog_has_the_connector_and_says_none_by_default(qtbot) -> None:
    _ = QApplication.instance() or QApplication([])
    dlg = NewDeviceDialog(None, ThemeManager(), new_project())
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.connector.isVisibleTo(dlg) and dlg.connector_part() == ""
    dlg.name.setText("Computer")
    assert dlg.ok.isEnabled()
    assert dlg.values() == {"name": "Computer", "unit_id": "COMPUTER1", "subsystem": "general"}
    dlg.connector.select("EX-MICROD-9-F")
    assert dlg.connector_part() == "EX-MICROD-9-F" and dlg.ok.isEnabled()


def named_with_connector(name: str, part: str, count: int = 1):
    def fill(dlg):
        dlg.name.setText(name)
        dlg.connector.select(part)
        dlg.number.setValue(count)

    return fill


def test_add_device_with_a_connector_is_one_undo_step(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    DialogScript(win, named_with_connector("Star tracker", "EX-MICROD-15-F"))
    win.add_device_flow()
    p = win.ctl.project
    c = p.connectors["STAR1-J01"]
    assert c.unit_id == "STAR1" and c.part_id == "EX-MICROD-15-F" and len(c.pins) == 15
    assert win.ctl.history.next_undo_label == "Add device STAR1"
    win.ctl.undo()
    assert "STAR1" not in win.ctl.project.units and "STAR1-J01" not in win.ctl.project.connectors


def test_a_number_of_devices_each_get_the_connector(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    DialogScript(win, named_with_connector("Gyro", "EX-DSUB-9-M", count=2))
    win.add_device_flow()
    p = win.ctl.project
    assert sorted(p.units) == ["GYRO1", "GYRO1-R"]
    assert {c.unit_id for c in p.connectors.values()} == {"GYRO1", "GYRO1-R"}


def test_add_device_without_a_connector_is_as_before(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    DialogScript(win, lambda d: d.name.setText("Plain"))
    win.add_device_flow()
    assert list(win.ctl.project.units) == ["PLAIN1"] and not win.ctl.project.connectors


def test_the_systems_role_stays_on_the_next_step_page_after_add_device(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    win.set_role("systems")
    win.set_area("next")
    DialogScript(win, named_with_connector("Computer", "EX-DSUB-9-M"))
    win.add_device_flow()
    QApplication.processEvents()
    assert win.area() == "next" and "COMPUTER1" in win.ctl.project.units


# ---- Add a connector in the connection window --------------------------------------------------


def test_add_connector_dialog_checks_and_plans(qtbot) -> None:
    _ = QApplication.instance() or QApplication([])
    p = project_with(("OBC", None))
    dlg = AddConnectorDialog(None, ThemeManager(), p, "OBC")
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.name_edit.placeholderText() == "J01"
    assert dlg.ok.isEnabled()
    dlg.picker.select("EX-DSUB-15-F")
    dlg.name_edit.setText("Data")
    ops, cid = dlg.plan()
    assert cid == "OBC-J01" and ops[0].obj.name == "Data" and len(ops[0].obj.pins) == 15
    assert not p.connectors  # (the project is not touched)


def test_the_connection_window_adds_a_connector_for_a_device_that_has_none(qtbot) -> None:
    p = project_with(("OBC", "EX-MICROD-9-F"), ("RW1", None))
    dlg = link_dialog(qtbot, p, a_unit="OBC", b_unit="RW1")
    assert dlg.b_conn.count() == 0 and not dlg.ok.isEnabled()
    assert strings.LINK_NO_CONNECTOR.format("RW1") in dlg.problem.text()
    assert dlg.add_b_connector.isEnabled() and dlg.add_b_connector.text() == "Add a connector…"

    def ask(uid):
        d = AddConnectorDialog(dlg, dlg.theme, dlg.project, uid)
        d.picker.select("EX-MICROD-9-M")
        return d.plan()

    dlg.ask_connector = ask
    dlg.add_b_connector.click()
    assert dlg.b_connector_id() == "RW1-J01" and dlg.b_conn.count() == 1
    assert [o.obj.id for o in dlg.extra_ops] == ["RW1-J01"]
    assert "RW1-J01" not in p.connectors  # (the person's project waits for OK)
    assert not dlg.problem.isVisibleTo(dlg) or "no connector" not in dlg.problem.text()


def test_cancel_in_the_add_connector_window_changes_nothing(qtbot) -> None:
    p = project_with(("OBC", "EX-MICROD-9-F"), ("RW1", None))
    dlg = link_dialog(qtbot, p, a_unit="OBC", b_unit="RW1")
    dlg.ask_connector = lambda uid: None
    dlg.add_b_connector.click()
    assert dlg.b_conn.count() == 0 and not dlg.extra_ops


def test_an_existing_connection_cannot_add_connectors(qtbot, tmp_path: Path) -> None:
    p = project_with(("OBC", "EX-MICROD-9-F"), ("RW1", "EX-MICROD-9-M"))
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(p, None, None)
    lid = win.ctl.add_link("OBC-J01", "RW1-J01", [("1", "1")])
    dlg = link_dialog(qtbot, win.ctl.project, link_id=lid)
    assert not dlg.add_a_connector.isEnabled() and not dlg.add_b_connector.isEnabled()


# ---- Pair by pin number and Paste a pairing ----------------------------------------------------


def numbered(qtbot, a="EX-MICROD-9-F", b="EX-MICROD-9-M"):
    p = project_with(("OBC", a), ("RW1", b))
    return link_dialog(qtbot, p, a_unit="OBC", b_unit="RW1")


def test_the_dialog_with_unlabelled_pins_starts_with_no_pairs(qtbot) -> None:
    dlg = numbered(qtbot)
    assert dlg.pairs() == [] and not dlg.ok.isEnabled()
    assert dlg.pair_numbers.isEnabled() and dlg.paste_pairs.isEnabled()
    assert not dlg.offer_box.isVisibleTo(dlg)


def test_pair_by_number_shows_a_proposal_and_waits_for_accept(qtbot) -> None:
    dlg = numbered(qtbot)
    dlg.pair_numbers.click()
    assert dlg.offer_box.isVisibleTo(dlg) and dlg.pairs() == [] and not dlg.ok.isEnabled()
    assert dlg.offer_model.rowCount() == 9
    assert "9 pairs proposed" in dlg.offer_title.text()
    assert "Nothing is paired until you accept" in dlg.offer_title.text()
    dlg.offer_accept.click()
    assert not dlg.offer_box.isVisibleTo(dlg)
    assert dlg.pairs() == [(str(k), str(k)) for k in range(1, 10)] and dlg.ok.isEnabled()
    assert dlg.model.rowCount() == 9


def test_discard_forgets_the_proposal(qtbot) -> None:
    dlg = numbered(qtbot)
    dlg.pair_numbers.click()
    dlg.offer_discard.click()
    assert dlg.offer() is None and dlg.pairs() == [] and not dlg.offer_box.isVisibleTo(dlg)


def test_changing_a_connector_drops_a_waiting_proposal(qtbot) -> None:
    p = project_with(("OBC", "EX-MICROD-9-F"), ("RW1", "EX-MICROD-9-M"))
    ops, _ = devices.ops_add_connector(p, "RW1", part_id="EX-DSUB-9-M")
    History(p).execute("more", ops)
    dlg = link_dialog(qtbot, p, a_unit="OBC", b_unit="RW1")
    dlg.pair_numbers.click()
    assert dlg.offer() is not None
    dlg.b_conn.setCurrentIndex(1)
    assert dlg.offer() is None and not dlg.offer_box.isVisibleTo(dlg)


def test_accepted_pairs_do_not_offer_the_same_pins_again(qtbot) -> None:
    dlg = numbered(qtbot)
    dlg.offer_pasted("1\t2\n3\t4")
    dlg.offer_accept.click()
    assert dlg.pairs() == [("1", "2"), ("3", "4")]
    found = dlg.offer_by_number()
    pairs = [(x.a_pin, x.b_pin) for x in found.pairs]
    # (A1 and A3 and B2 and B4 are in the table already; A2 would meet B2, A4 would meet B4)
    assert pairs == [(str(k), str(k)) for k in range(5, 10)]
    dlg.offer_accept.click()
    assert len(dlg.pairs()) == 2 + len(pairs)


def test_paste_a_pairing_shows_the_proposal_and_names_bad_lines(qtbot) -> None:
    dlg = numbered(qtbot)
    dlg.ask_paste = lambda: "Pin A\tPin B\n1\t4\n2\t3\n77\t1\n"
    dlg.paste_pairs.click()
    assert dlg.pairs() == [] and dlg.offer_box.isVisibleTo(dlg)
    assert dlg.offer_model.rowCount() == 2 and "2 pairs proposed" in dlg.offer_title.text()
    assert "Line 4" in dlg.offer_notes.text() and "no pin '77'" in dlg.offer_notes.text()
    dlg.offer_accept.click()
    assert dlg.pairs() == [("1", "4"), ("2", "3")]


def test_cancelling_the_paste_window_shows_nothing(qtbot) -> None:
    dlg = numbered(qtbot)
    dlg.ask_paste = lambda: None
    dlg.paste_pairs.click()
    assert dlg.offer() is None


def test_nothing_pasted_leaves_accept_off(qtbot) -> None:
    dlg = numbered(qtbot)
    dlg.offer_pasted("nothing useful here")
    assert not dlg.offer_accept.isEnabled() and dlg.offer_notes.isVisibleTo(dlg)


def test_the_paste_window_takes_a_table_from_the_clipboard(qtbot) -> None:
    _ = QApplication.instance() or QApplication([])
    QApplication.clipboard().setText("1\t2\n3\t4")
    dlg = PastePairingDialog(None, ThemeManager(), "OBC-J01", "RW1-J01")
    qtbot.addWidget(dlg)
    assert dlg.pasted() == "1\t2\n3\t4" and dlg.ok.isEnabled()
    dlg.text.clear()
    assert not dlg.ok.isEnabled()
    QApplication.clipboard().clear()


def test_the_buttons_are_off_for_the_same_device(qtbot) -> None:
    p = project_with(("OBC", "EX-MICROD-9-F"), ("RW1", "EX-MICROD-9-M"))
    dlg = link_dialog(qtbot, p, a_unit="OBC", b_unit="OBC")
    assert not dlg.pair_numbers.isEnabled() and not dlg.paste_pairs.isEnabled()
    assert dlg.offer_by_number() is None


# ---- the whole path from a blank project -------------------------------------------------------


def test_from_two_devices_with_no_connector_to_a_saved_link(qtbot, tmp_path: Path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(project_with(("OBC", None), ("RW1", None)), None, None)

    def fill(dlg):
        for side, part in (("a", "EX-MICROD-9-F"), ("b", "EX-MICROD-9-M")):
            dlg.ask_connector = lambda uid, part=part: _plan_for(dlg, uid, part)
            getattr(dlg, f"add_{side}_connector").click()
        dlg.pair_numbers.click()
        dlg.offer_accept.click()

    DialogScript(win, fill)
    win.link_flow("OBC", "", "RW1", "")
    p = win.ctl.project
    assert {"OBC-J01", "RW1-J01"} <= set(p.connectors) and len(p.links) == 1
    link = next(iter(p.links.values()))
    assert len(link.pairs) == 9
    assert win.ctl.history.next_undo_label.startswith("Link")  # one step for all of it
    win.ctl.undo()
    assert not win.ctl.project.links and not win.ctl.project.connectors


def test_cancelling_the_connection_window_leaves_the_added_connector_out(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(project_with(("OBC", "EX-MICROD-9-F"), ("RW1", None)), None, None)

    def fill(dlg):
        dlg.ask_connector = lambda uid: _plan_for(dlg, uid, "EX-MICROD-9-M")
        dlg.add_b_connector.click()

    DialogScript(win, fill, accept=False)
    win.link_flow("OBC", "", "RW1", "")
    assert "RW1-J01" not in win.ctl.project.connectors and not win.ctl.project.links
