# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""1.5.0: a harness made by hand in the Harness tab: New harness, the Connectors tab, wires between
the new connectors, and the whole journey from a blank project in the window."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.samples import new_project, sat15  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from tests.gui_helpers import action_named, make_window  # noqa: E402
from tests.test_ux_harness import make_view, theme  # noqa: E402, F401, F811


@pytest.fixture
def blank(qtbot, theme):  # noqa: F811
    ctl, view = make_view(qtbot, theme, new_project("Scratch"))
    return ctl, view


def test_a_project_without_harnesses_offers_to_make_one(blank):
    ctl, view = blank
    assert view.stack.currentWidget() is view.empty
    assert not view.empty_new.isHidden()
    assert strings.HV_EMPTY_BY_HAND.strip() in view.empty_body.text()
    view.empty_new.click()  # asks the window, which is not here: the signal is what counts


def test_new_harness_signal_comes_from_both_buttons(blank, qtbot):
    _ctl, view = blank
    with qtbot.waitSignal(view.newHarnessRequested, timeout=1000):
        view.empty_new.click()


def test_the_connectors_tab_adds_connectors_pins_and_wires(blank, qtbot):
    from harness_design_studio.core.manual_harness import plan_new_harness

    ctl, view = blank
    ops, hid = plan_new_harness(ctl.project, "By hand")
    assert ctl.run("New harness", ops)
    view.refresh()
    view.select_harness(hid)
    view.show_connectors()
    ed = view.connector_editor
    assert view.side_tabs.tabText(2) == strings.HV_CONNECTORS_TAB
    assert ed.add.isEnabled() and ed.note.isHidden()
    ed.part.setCurrentIndex(ed.part.findData("EX-DSUB-9-M"))
    assert ed.add_connector()
    ed.part.setCurrentIndex(ed.part.findData("EX-DSUB-9-F"))
    ed.name.setText("Far end")
    assert ed.add_connector()
    h = ctl.project.harnesses[hid]
    assert [c.name for c in h.connectors] == ["P1", "Far end"]
    # the wire form now offers the new connectors and pins
    nf = view.wire_editor.new_form
    assert nf.start.connector.count() == 2 and nf.start.pin.count() == 9
    nf.signal.setText("HEATER")
    assert nf.add_wire()
    assert [w.signal for w in ctl.project.harnesses[hid].wires] == ["HEATER"]
    # a pin gets its function and termination
    ed.connector.setCurrentIndex(0)
    ed._fill_pins()
    ed.pin.setCurrentIndex(0)
    ed.function.setText("HEATER +")
    ed.termination.setCurrentIndex(ed.termination.findData("solder"))
    assert ed.apply_pin()
    pin = ctl.project.harnesses[hid].connectors[0].pins[0]
    assert (pin.function, pin.termination) == ("HEATER +", "solder")
    # a connector with a wire cannot go; the reason is said in the form
    assert not ed.delete_connector()
    assert not ed.error.isHidden() and "has wires" in ed.error.text()
    # a connector can be taken apart again one undo step at a time
    ctl.history.undo()
    assert ctl.project.harnesses[hid].connectors[0].pins[0].function is None


def test_the_tab_explains_why_a_generated_harness_takes_no_connector(qtbot, theme):  # noqa: F811
    p = sat15()
    generate_project(p)
    ctl, view = make_view(qtbot, theme, p)
    ed = view.connector_editor
    assert not ed.add.isEnabled()
    assert not ed.note.isHidden() and "made by Generate" in ed.note.text()


def test_a_read_only_project_takes_no_connector(qtbot, theme):  # noqa: F811
    ctl, view = make_view(qtbot, theme, new_project("Scratch"))
    from harness_design_studio.core.manual_harness import plan_new_harness

    ops, hid = plan_new_harness(ctl.project, "By hand")
    ctl.run("New harness", ops)
    view.refresh()
    view.select_harness(hid)
    ctl.project.read_only = True
    ctl.stateChanged.emit()
    view.refresh()
    assert not view.connector_editor.add.isEnabled()
    assert not view.new_button.isEnabled()


def test_the_window_makes_a_harness_from_a_blank_project(tmp_path):
    win = make_window(tmp_path)
    win.ctl.new_project(tmp_path / "proj", "Scratch")
    win.ask_text = lambda _t, _l, _d: "Heater harness"  # type: ignore[assignment]
    action_named(win, "act-new-harness").trigger()
    QApplication.processEvents()
    assert list(win.ctl.project.harnesses) == ["W001"]
    h = win.ctl.project.harnesses["W001"]
    assert (h.name, h.generated) == ("Heater harness", False)
    assert win.harness_view.side_tabs.currentWidget() is win.harness_view.connector_scroll
    assert win.harness_view.harness_id() == "W001"
    # Undo takes the whole step back
    win.ctl.history.undo()
    assert win.ctl.project.harnesses == {}
    # a cancelled question changes nothing; a name that is taken says so
    win.ask_text = lambda _t, _l, _d: None  # type: ignore[assignment]
    action_named(win, "act-new-harness").trigger()
    assert win.ctl.project.harnesses == {}
    win.close()


def test_the_action_has_a_shortcut_a_tip_and_is_off_in_a_read_only_project(tmp_path):
    win = make_window(tmp_path)
    win.ctl.new_project(tmp_path / "proj", "Scratch")
    act = action_named(win, "act-new-harness")
    assert act.shortcut().toString() == "Ctrl+Shift+H"
    assert "Ctrl+Shift+H" in act.toolTip()
    win.close()
