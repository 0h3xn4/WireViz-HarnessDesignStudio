# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""REQ-WIRE-07, REQ-WIRE-08. Workshop feedback M3: the Edit wire tab changes a group that you made
(Change group…) and sets gauge, type, colour and length on many wires in one step (Edit all wires…,
also Edit > Edit all wires of the harness…, Ctrl+Shift+B)."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from harness_design_studio.core.commands import apply_ops  # noqa: E402
from harness_design_studio.core.generate.engine import (  # noqa: E402
    generate_project,
    plan_generation,
)
from harness_design_studio.core.manual_harness import (  # noqa: E402
    plan_add_connector,
    plan_new_harness,
)
from harness_design_studio.core.model import Part, evolve  # noqa: E402
from harness_design_studio.core.samples import sat15  # noqa: E402
from harness_design_studio.core.wires import plan_add_wire, plan_group_wires  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.harness_edit_dialogs import (  # noqa: E402
    BulkWireDialog,
    ChangeGroupDialog,
)
from tests.gui_helpers import DialogScript, action_named, make_window  # noqa: E402
from tests.test_ux_harness import make_view, theme  # noqa: E402, F401, F811


def project():
    p = sat15()
    generate_project(p)
    p.parts["EX-WIRE-22"] = Part(id="EX-WIRE-22", category="wire")
    return p


@pytest.fixture
def made(qtbot, theme):  # noqa: F811
    ctl, view = make_view(qtbot, theme, project())
    view.select_harness("W009")
    view.refresh()
    ed = view.wire_editor
    ed.set_harness("W009")
    return ctl, view, ed


def wire_ids(ctl, hid="W009"):
    return [w.id for w in ctl.project.harnesses[hid].wires]


def drive(ed, fn, accept=True):
    """Make the editor's windows call `fn(dialog)` and answer OK (or Cancel)."""
    seen = []

    def run(dlg):
        seen.append(dlg)
        fn(dlg)
        return int(QDialog.DialogCode.Accepted if accept else QDialog.DialogCode.Rejected)

    ed.run_dialog = run
    return seen


# ---- Edit all wires… ---------------------------------------------------------------------------


def test_the_button_is_there_named_and_on_for_a_harness_with_wires(made):
    _ctl, _view, ed = made
    assert ed.bulk_btn.text() == strings.WIRE_BULK == "Edit all wires…"
    assert ed.bulk_btn.accessibleName() and ed.bulk_btn.toolTip() and ed.bulk_btn.isEnabled()
    assert not ed.change_group_btn.isVisibleTo(ed)  # (no group of yours is selected)


def test_the_window_sets_the_values_on_all_wires_in_one_undo_step(made):
    ctl, _view, ed = made
    ids = wire_ids(ctl)

    def fill(dlg):
        assert dlg.scope.currentData() == "all" and dlg.windowTitle() == "Edit all wires of W009"
        assert not dlg.ok.isEnabled() and dlg.error.text() == strings.BULK_NOTHING
        dlg.gauge.setText("22")
        dlg.colour.setCurrentText("red")
        dlg.part.setCurrentIndex(dlg.part.findText("EX-WIRE-22"))
        dlg.length.setText("1,5")
        assert dlg.ok.isEnabled() and "4 of 4 wires" in dlg.sentence.text()

    drive(ed, fill)
    assert ed.bulk_edit()
    got = [w for w in ctl.project.harnesses["W009"].wires]
    assert {(w.gauge_awg, w.colour, w.length_m, w.part_id, w.locked) for w in got} == {
        (22, "red", 1.5, "EX-WIRE-22", True)
    }
    ctl.undo()
    assert all(not w.locked and w.gauge_awg is None for w in ctl.project.harnesses["W009"].wires)
    ctl.redo()
    apply_ops(ctl.project, plan_generation(ctl.project).ops)  # Generate keeps them
    assert {w.gauge_awg for w in ctl.project.harnesses["W009"].wires} == {22}
    assert ids


def test_the_selected_wires_are_offered_first_and_only_they_change(made):
    ctl, _view, ed = made
    ids = wire_ids(ctl)
    ed.show_wires(ids[:2])

    def fill(dlg):
        assert dlg.scope.currentData() == "selected"
        assert dlg.scope.itemText(0) == strings.BULK_SCOPE_SELECTED.format(2)
        dlg.colour.setCurrentText("green")

    drive(ed, fill)
    assert ed.bulk_edit()
    got = {w.id: w.colour for w in ctl.project.harnesses["W009"].wires}
    assert [got[i] for i in ids] == ["green", "green", None, None]


def test_the_wires_of_one_signal_and_only_the_empty_ones(made):
    ctl, _view, ed = made

    def fill(dlg):
        i = dlg.scope.findData("signal")
        dlg.scope.setCurrentIndex(i)
        assert dlg.signal.isEnabled() and dlg.signal.currentText() == "TX+/RX+"
        dlg.gauge.setText("26")
        dlg.only_empty.setChecked(True)
        assert "2 of 2 wires" in dlg.sentence.text()

    drive(ed, fill)
    assert ed.bulk_edit()
    got = {w.signal: w.gauge_awg for w in ctl.project.harnesses["W009"].wires}
    assert got["TX+/RX+"] == 26 and got["TX-/RX-"] is None


def test_a_wrong_value_is_said_in_the_window_and_the_button_stays_off(made):
    _ctl, _view, ed = made
    seen = []

    def fill(dlg):
        seen.append(dlg)
        dlg.gauge.setText("abc")
        assert not dlg.ok.isEnabled() and "whole number" in dlg.error.text()
        dlg.gauge.setText("22")
        assert dlg.ok.isEnabled() and dlg.error.isHidden()
        dlg.gauge.setText("22")
        dlg.length.setText("far")
        assert "metres" in dlg.error.text() and not dlg.ok.isEnabled()

    drive(ed, fill, accept=False)
    assert not ed.bulk_edit()  # cancelled: nothing changed
    assert all(not w.locked for w in _ctl.project.harnesses["W009"].wires)


def test_the_same_values_again_change_nothing(made):
    ctl, _view, ed = made
    drive(ed, lambda d: d.colour.setCurrentText("green"))
    assert ed.bulk_edit()
    seen = drive(ed, lambda d: d.colour.setCurrentText("green"))
    n = len(ctl.history._undo) if hasattr(ctl.history, "_undo") else None
    assert not ed.bulk_edit()
    assert seen[0].error.text() == strings.BULK_SAME and not seen[0].ok.isEnabled()
    assert n is None or n == len(ctl.history._undo)


def test_the_button_is_off_for_a_released_harness_and_says_why(made):
    ctl, _view, ed = made
    ctl.project.harnesses["W009"] = evolve(ctl.project.harnesses["W009"], status="released")
    ed.set_harness("W009")
    assert not ed.bulk_btn.isEnabled() and "released" in ed.bulk_btn.toolTip()
    assert not ed.bulk_edit()


def test_the_menu_action_has_a_shortcut_and_opens_the_window_on_the_open_harness(tmp_path):
    win = make_window(tmp_path)
    win.ctl._install(project(), None, None)
    QApplication.processEvents()
    act = action_named(win, "act-bulk-wires")
    assert act.shortcut().toString() == "Ctrl+Shift+B" and "Ctrl+Shift+B" in act.toolTip()
    win.harness_view.select_harness("W009")

    def fill(dlg):
        assert isinstance(dlg, BulkWireDialog) and dlg.harness_id == "W009"
        dlg.colour.setCurrentText("blue")

    shown = DialogScript(win, fill)
    act.trigger()
    assert len(shown.seen) == 1
    assert {w.colour for w in win.ctl.project.harnesses["W009"].wires} == {"blue"}
    win.ctl.project.read_only = True
    win.ctl.stateChanged.emit()
    assert not act.isEnabled()
    win.close()


def test_without_a_harness_the_action_says_so(tmp_path):
    from harness_design_studio.core.samples import new_project

    win = make_window(tmp_path)
    win.ctl._install(new_project("Scratch"), None, None)
    shown = DialogScript(win)
    action_named(win, "act-bulk-wires").trigger()
    assert not shown.seen
    win.close()


# ---- Change group… -----------------------------------------------------------------------------


@pytest.fixture
def grouped(qtbot, theme):  # noqa: F811
    """A harness made by hand with four wires, two of them in a twisted pair of yours, beside the
    generated harnesses (whose groups come from the interface type)."""
    p = project()
    ops, hid = plan_new_harness(p, "Sensors")
    apply_ops(p, ops)
    for _ in range(2):
        ops, _cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
        apply_ops(p, ops)
    a, b = [c.id for c in p.harnesses[hid].connectors]
    for k in range(1, 5):
        apply_ops(p, plan_add_wire(p, hid, a, str(k), b, str(k), signal=f"S{k}"))
    ids = [w.id for w in p.harnesses[hid].wires]
    apply_ops(p, plan_group_wires(p, ids[:2], "twisted_pair"))
    ctl, view = make_view(qtbot, theme, p)
    view.select_harness(hid)
    view.refresh()
    ed = view.wire_editor
    ed.set_harness(hid)
    gid = ctl.project.harnesses[hid].shields[-1].id
    return ctl, view, ed, ids, gid


def group_of(ctl, gid):
    return next(s for h in ctl.project.harnesses.values() for s in h.shields if s.id == gid)


def test_the_button_shows_for_a_group_you_made_only(grouped):
    ctl, _view, ed, ids, gid = grouped
    ed.show_wires(ids[:2])
    assert ed.change_group_btn.isVisibleTo(ed) and ed.change_group_btn.isEnabled()
    assert ed.change_group_btn.accessibleName() and ed.change_group_btn.toolTip()
    ed.show_wires([ids[3]])  # no group
    assert not ed.change_group_btn.isVisibleTo(ed)
    ed.set_harness("W009")
    generated = ctl.project.harnesses["W009"].shields[0]
    assert not generated.manual  # (the groups of the type stay as they are)
    ed.show_wires(list(generated.wire_ids))
    assert not ed.change_group_btn.isVisibleTo(ed)


def test_the_window_changes_kind_ends_and_wires_in_one_undo_step(grouped):
    ctl, _view, ed, ids, gid = grouped
    ed.show_wires(ids[:2])

    def fill(dlg):
        assert isinstance(dlg, ChangeGroupDialog) and dlg.windowTitle() == f"Change group {gid}"
        assert dlg.kind.currentData() == "twisted_pair" and not dlg.ok.isEnabled()
        assert dlg.error.text() == strings.GD_SAME
        dlg.kind.setCurrentIndex(dlg.kind.findData("shielded_pair"))
        dlg.end_a.setCurrentIndex(dlg.end_a.findData("backshell_360"))
        dlg.end_b.setCurrentIndex(dlg.end_b.findData("pigtail"))
        assert dlg.ok.isEnabled() and "this is a Shielded pair" in dlg.sentence.text()
        dlg.kind.setCurrentIndex(dlg.kind.findData("quad"))
        assert not dlg.ok.isEnabled() and "quad is made of 4 wires, not 2" in dlg.error.text()
        for i in range(dlg.wires.count()):  # tick all four wires of the harness
            dlg.wires.item(i).setCheckState(Qt.CheckState.Checked)
        assert dlg.ok.isEnabled() and len(dlg.wire_ids()) == 4

    drive(ed, fill)
    assert ed.change_group()
    s = group_of(ctl, gid)
    assert (s.kind, s.end_a, s.end_b, sorted(s.wire_ids)) == (
        "quad",
        "backshell_360",
        "pigtail",
        sorted(ids),
    )
    ctl.undo()
    s = group_of(ctl, gid)
    assert (s.kind, s.end_a, sorted(s.wire_ids)) == ("twisted_pair", "floating", sorted(ids[:2]))
    ctl.redo()
    apply_ops(ctl.project, plan_generation(ctl.project).ops)  # Generate keeps it
    assert group_of(ctl, gid).kind == "quad"


def test_cancel_changes_nothing_and_a_released_harness_turns_the_button_off(grouped):
    ctl, _view, ed, ids, gid = grouped
    ed.show_wires(ids[:2])
    drive(ed, lambda d: d.kind.setCurrentIndex(d.kind.findData("shielded_pair")), accept=False)
    assert not ed.change_group()
    assert group_of(ctl, gid).kind == "twisted_pair"
    hid = ids[0].split("-")[0]
    ctl.project.harnesses[hid] = evolve(ctl.project.harnesses[hid], status="released")
    ed.show_wires(ids[:2])
    assert not ed.change_group_btn.isEnabled()


def test_every_control_of_both_windows_has_a_name_and_a_tooltip(grouped):
    ctl, _view, ed, ids, gid = grouped
    hid = ids[0].split("-")[0]
    bulk = BulkWireDialog(None, ed.theme, ctl.project, hid, ids[:2])
    group = ChangeGroupDialog(None, ed.theme, ctl.project, gid)
    for w in (
        bulk.scope, bulk.signal, bulk.gauge, bulk.part, bulk.colour, bulk.length, bulk.only_empty,
        bulk.ok, group.kind, group.end_a, group.end_b, group.wires, group.ok,
    ):  # fmt: skip
        assert w.accessibleName() and w.toolTip(), w.objectName()
    texts = " ".join(
        v
        for k, v in vars(strings).items()
        if k.startswith(("BULK_", "GD_", "WIRE_BULK", "A_BULK")) and isinstance(v, str)
    )
    assert "unit" not in texts.lower().replace("community", "")
