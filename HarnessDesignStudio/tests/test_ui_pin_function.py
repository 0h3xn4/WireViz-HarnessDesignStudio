# mypy: disable-error-code="no-untyped-def,no-untyped-call,union-attr,arg-type,var-annotated"
# ruff: noqa: F811  (the fixtures are those of test_ux_devices_edit, imported by name)
"""1.4.0 M3: the Function column of the Devices tab pin table edits in place and in one undo step."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.core import devices  # noqa: E402
from tests.test_edit_device import with_connector  # noqa: E402
from tests.test_ux_devices_edit import edit_cell, make_view, pin, theme  # noqa: E402, F401


def test_the_function_of_a_pin_is_typed_in_its_cell_and_undone_in_one_step(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    cid = "GYRO1-J01"
    assert view.pin_model.column_index("function") >= 0
    edit_cell(view, "1", "function", "Rate sensor power")
    assert pin(ctl, cid, "1").function == "Rate sensor power"
    assert ctl.history.next_undo_label == "Edit pin GYRO1-J01.1"
    ctl.undo()
    assert pin(ctl, cid, "1").function is None


def test_the_function_survives_clearing_the_signal(qtbot, theme) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    cid = "GYRO1-J01"
    edit_cell(view, "2", "signal", "PWR")
    edit_cell(view, "2", "function", "Main supply")
    ctl.run("clear the signal", devices.ops_set_pin(ctl.project, cid, "2", signal=""))
    got = pin(ctl, cid, "2")
    assert got.signal is None and got.function == "Main supply"


def test_the_label_of_a_box_connector_is_typed_on_its_card_and_undone_in_one_step(
    qtbot, theme
) -> None:
    ctl, view = make_view(qtbot, theme, with_connector()[0])
    cid = "GYRO1-J01"
    view.select_connector(cid)
    view.label_edit.setFocus()
    view.label_edit.setText("J1 power")
    view.label_edit.editingFinished.emit()
    assert ctl.project.connectors[cid].label == "J1 power"
    assert ctl.history.next_undo_label == "Edit GYRO1-J01"
    ctl.undo()
    assert ctl.project.connectors[cid].label is None
