# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""S4 in the editor: the Edit wire tab asks for a reason when a value of a generated wire is changed
(no Apply without it), the wire table flags overrides, the Help > Change history window lists the
journal with a filter, and an error of an electrical rule can be accepted as a deviation."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

from harness_design_studio.core import journal, templates  # noqa: E402
from harness_design_studio.core.commands import History  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.wires import find_wire, plan_override  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.harness_view import wire_rows  # noqa: E402
from harness_design_studio.gui.journal_dialog import JournalDialog  # noqa: E402
from tests.gui_helpers import action_named, make_window  # noqa: E402
from tests.test_ux_harness import make_view, theme  # noqa: E402, F401, F811


@pytest.fixture
def made(qtbot, theme):  # noqa: F811
    ctl, view = make_view(qtbot, theme)
    view.select_harness("W001")
    view.refresh()
    ed = view.wire_editor
    ed.set_harness("W001")
    return ctl, view, ed


def first_wire(ctl, hid="W001"):
    return ctl.project.harnesses[hid].wires[0]


def reason_row_visible(ed) -> bool:
    return ed.form.isRowVisible(ed.reason)


# ---- the Edit wire tab -------------------------------------------------------------------------


def test_the_reason_box_is_hidden_until_a_value_of_a_generated_wire_is_changed(made):
    ctl, _view, ed = made
    ed.show_wires([first_wire(ctl).id])
    assert not reason_row_visible(ed)
    ed.label.setText("Bus A")
    ed.label.textEdited.emit("Bus A")
    assert not reason_row_visible(ed) and ed.apply.isEnabled()  # a label needs no reason
    ed.gauge.setText("20")
    ed.gauge.textEdited.emit("20")
    assert reason_row_visible(ed)
    assert not ed.apply.isEnabled()  # no OK without a reason
    assert ed.reason.placeholderText() == strings.WIRE_REASON_PLACEHOLDER


def test_apply_is_off_until_the_reason_is_written_and_then_the_override_is_recorded(made):
    ctl, _view, ed = made
    wid = first_wire(ctl).id
    ed.show_wires([wid])
    ed.gauge.setText("20")
    ed.gauge.textEdited.emit("20")
    assert not ed.apply.isEnabled() and not ed.apply_changes()
    assert find_wire(ctl.project, wid)[1].overrides == {}
    ed.reason.setText("   ")
    ed.reason.textEdited.emit("   ")
    assert not ed.apply.isEnabled()  # blanks are no reason
    ed.reason.setText("Heater added, ECR-3")
    ed.reason.textEdited.emit("Heater added, ECR-3")
    assert ed.apply.isEnabled()
    assert ed.apply_changes()
    w = find_wire(ctl.project, wid)[1]
    assert w.gauge_awg == 20 and w.locked and w.overrides == {"gauge_awg": "Heater added, ECR-3"}
    assert "Heater added, ECR-3" in ed.state.text() and not reason_row_visible(ed)


def test_a_wire_that_was_drawn_by_a_person_needs_no_reason(made):
    ctl, _view, ed = made
    from harness_design_studio.core.wires import plan_add_wire

    h = ctl.project.harnesses["W001"]
    c = sorted(h.connectors, key=lambda c: c.id)
    ctl.run(
        "add",
        plan_add_wire(ctl.project, "W001", c[0].id, c[0].pins[-1].id, c[1].id, c[1].pins[-1].id),
    )
    new = next(w for w in ctl.project.harnesses["W001"].wires if w.manual)
    ed.show_wires([new.id])
    ed.gauge.setText("20")
    ed.gauge.textEdited.emit("20")
    assert not reason_row_visible(ed) and ed.apply.isEnabled()


def test_the_state_line_says_when_a_wire_is_locked_with_no_reason(made):
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

    ctl, _view, ed = made
    h = ctl.project.harnesses["W001"]
    w = h.wires[0]
    ctl.run("lock", [Put("harnesses", evolve(h, wires=[evolve(w, locked=True), *h.wires[1:]]))])
    ed.show_wires([w.id])
    assert ed.state.text() == strings.WIRE_STATE_OVERRIDDEN_LEGACY


def test_the_wire_table_flags_an_override_and_says_why(made):
    ctl, view, _ed = made
    wid = first_wire(ctl).id
    before = {r["id"]: r for r in wire_rows(ctl.project, ctl.project.harnesses["W001"])}
    assert before[wid]["locked"] == ""
    ctl.run(
        "override", plan_override(ctl.project, wid, "colour", "pink", "colour code of the program")
    )
    rows = {r["id"]: r for r in wire_rows(ctl.project, ctl.project.harnesses["W001"])}
    assert rows[wid]["locked"] == strings.HV_OVERRIDDEN_WORD
    assert "colour code of the program" in rows[wid]["locked_why"]
    assert rows[wid]["locked_state"] == "locked"


def test_the_bulk_window_asks_for_a_reason_too(made):
    from harness_design_studio.gui.harness_edit_dialogs import BulkWireDialog

    ctl, _view, _ed = made
    dlg = BulkWireDialog(None, theme_of(made), ctl.project, "W001", [])
    dlg.colour.setCurrentText("green")
    assert not dlg.ok.isEnabled() and "needs a reason" in dlg.error.text()
    dlg.reason.setText("colour code")
    assert dlg.ok.isEnabled() and dlg.ops()


def theme_of(made):
    return made[1].theme


# ---- the change history window -----------------------------------------------------------------


def a_project_with_a_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "now", lambda: "2026-11-03T10:00:00Z")
    monkeypatch.setattr(journal, "author", lambda: "Ann Engineer")
    folder = tmp_path / "p"
    templates.create_project(folder, "flatsat", journal=True)
    p = load_project(folder).project
    wid = p.harnesses["W001"].wires[0].id
    History(p).execute("override", plan_override(p, wid, "colour", "pink", "colour code"))
    save_project(p, folder)
    return folder


def test_the_history_window_lists_the_journal_and_filters_it(qtbot, theme, tmp_path, monkeypatch):  # noqa: F811
    folder = a_project_with_a_journal(tmp_path, monkeypatch)
    p = load_project(folder).project
    dlg = JournalDialog(None, theme, p)
    qtbot.addWidget(dlg)
    assert dlg.table.rowCount() == 2 and dlg.visible_rows() == 2
    assert not dlg.start_button.isVisibleTo(dlg)
    assert (
        dlg.table.item(1, 2).text() == "Ann Engineer"
        and dlg.table.item(1, 8).text() == "colour code"
    )
    dlg.filter.setText("colour")
    assert dlg.visible_rows() == 1
    dlg.filter.setText("nobody")
    assert dlg.visible_rows() == 0
    dlg.filter.setText("")
    assert dlg.visible_rows() == 2
    assert dlg.note.text() == strings.HISTORY_NOTE.format(2)


def test_the_history_window_of_a_project_without_a_journal_offers_to_start_one(
    qtbot, theme, tmp_path
):  # noqa: F811
    templates.create_project(tmp_path / "p", "flatsat")
    p = load_project(tmp_path / "p").project
    started = []
    dlg = JournalDialog(None, theme, p, start_journal=lambda: started.append(1) or True)
    qtbot.addWidget(dlg)
    assert dlg.note.text() == strings.HISTORY_NONE and dlg.table.rowCount() == 0
    assert not dlg.filter.isEnabled()
    dlg.start_button.click()
    assert started == [1]


def test_help_has_the_change_history_and_it_starts_a_journal(qtbot, tmp_path):
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    folder = tmp_path / "proj"
    templates.create_project(folder, "flatsat")
    assert win.open_project(folder)
    seen = []

    def run(dlg):
        seen.append(dlg)
        assert isinstance(dlg, JournalDialog) and dlg.table.rowCount() == 0
        dlg.start_button.click()
        assert dlg.table.rowCount() == 1
        return int(QDialog.DialogCode.Accepted)

    win.run_dialog = run
    action_named(win, "act-history").trigger()
    assert seen and (folder / "journal.json").is_file()
    assert load_project(folder).project.journal[0].kind == "start"
    win.ctl.release()


def test_new_project_in_the_editor_starts_a_journal(qtbot, tmp_path):
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl.new_project(tmp_path / "fresh", "Fresh")
    assert (tmp_path / "fresh" / "journal.json").is_file()
    assert win.ctl.project.journal is not None and win.ctl.project.journal[0].object == "project"
    win.ctl.release()


# ---- deviations in the editor ------------------------------------------------------------------


def test_an_error_of_an_electrical_rule_can_be_accepted_from_the_problems_list(
    qtbot, tmp_path, monkeypatch
):
    from tests.gui_helpers import show_problems

    monkeypatch.setattr(journal, "now", lambda: "2026-11-03T10:00:00Z")
    monkeypatch.setattr(journal, "author", lambda: "Ann Engineer")
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    folder = tmp_path / "proj"
    templates.create_project(folder, "flatsat", journal=True)
    assert win.open_project(folder)
    wid = win.ctl.project.harnesses["W001"].wires[0].id
    win.ctl.run(
        "override", plan_override(win.ctl.project, wid, "gauge_awg", 26, "Smaller connector")
    )
    panel = show_problems(win)
    qtbot.waitUntil(lambda: win.ctl.drc_current, timeout=20000)
    QApplication.processEvents()
    assert panel.findChild(QPushButton, "deviate") is not None
    errors = [f for f in win.ctl.open_findings() if f.can_deviate]
    assert errors, "the too small gauge is an open error of current-over-wire"
    asked = []

    def run(dlg):
        asked.append(dlg.windowTitle())
        dlg.text.setPlainText("Accepted by the PA board, NCR-17")
        return int(QDialog.DialogCode.Accepted)

    win.run_dialog = run
    assert win.ctl.deviate(errors[0], "no") is False  # too short: refused
    win.deviate_flow(errors[0])
    assert asked == [strings.DEVIATE_TITLE]
    assert win.ctl.project.waivers[errors[0].id].justification == "Accepted by the PA board, NCR-17"
    QApplication.processEvents()
    assert errors[0].id not in {f.id for f in win.ctl.open_findings()}
    win.ctl.save()
    assert (
        journal.who_and_when(load_project(folder).project, errors[0].id)
        == "by Ann Engineer on 2026-11-03"
    )
    win.ctl.release()
