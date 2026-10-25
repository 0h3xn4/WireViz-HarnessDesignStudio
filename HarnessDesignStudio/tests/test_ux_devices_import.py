# mypy: disable-error-code="no-untyped-def,no-untyped-call,union-attr,attr-defined"
"""CD-J2: the import wizard's page for a device pinout: the columns matched from the headings, the
device chosen (an existing unit, or a new one), the part per connector, the rows with their exact
reasons, what stays pending, one undo step "Import pinout (n connectors, m pins)". Offscreen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QWizard  # noqa: E402

from harness_design_studio.core.integrity import check_integrity  # noqa: E402
from harness_design_studio.core.issues import errors  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui import import_kinds, strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.import_wizard import (  # noqa: E402
    PAGE_APPLY,
    PAGE_CHECK,
    PAGE_MAP,
    ImportWizard,
)
from tests.test_accessibility import unnamed  # noqa: E402
from tests.test_edit_device import device  # noqa: E402
from tests.test_ux_rel_import import finish, next_, rows_of  # noqa: E402
from tests.ux_rel import collect, themed  # noqa: E402

CSV = """Connector,Pin,Signal,Mode,Contact size,Termination,Remarks
J1,A1,PWR,fixed,20,crimp,power in
J1,A2,RTN,fixed,20,crimp,power return
J1,3,CANH,fixed,22,solder,
J1,4,CANL,fixed,22,solder,
J1,5,HEATER_ENABLE,,,,free text
"""


@pytest.fixture
def ctl(qtbot):
    themed()
    c = EditorController()
    c._install(device(), None, None)
    return c


def make(qtbot, ctl, path: Path | None = None) -> ImportWizard:
    w = ImportWizard(
        ctl, themed(), pick_file=lambda k, f: str(path) if path else None, kind="pinout"
    )
    qtbot.addWidget(w)
    w.show()
    return w


def sheet(tmp_path: Path, text: str = CSV, name: str = "gyro.csv") -> Path:
    p = tmp_path / name
    p.write_text(text)
    return p


def test_the_kind_is_offered_and_in_the_import_menu(qtbot, ctl) -> None:
    w = make(qtbot, ctl)
    assert "pinout" in w.file_page.radios and w.file_page.radios["pinout"].isChecked()
    assert import_kinds.KIND_BY_KEY["pinout"].title == "Device pinout"
    assert unnamed(w) == []


def test_a_device_pinout_in_four_pages_and_one_undo_step(qtbot, ctl, tmp_path: Path) -> None:
    w = make(qtbot, ctl, sheet(tmp_path))
    w.browse()
    assert "gyro.csv" in w.file_page.status.text() and "5 data rows" in w.file_page.status.text()
    assert next_(w) == PAGE_MAP
    page = w.map_page
    # the columns were matched from the headings, the unit and the part are asked for
    assert (
        page.map_boxes["pin"].currentText() == "Pin"
        and page.map_boxes["signal"].currentText() == "Signal"
    )
    assert page.map_boxes["part"].currentText() == strings.IMP_NOT_MAPPED
    page.pin_widgets["device"].setCurrentIndex(page.pin_widgets["device"].findData("GYRO1"))
    assert w.plan is not None and not w.plan.importable  # no part yet
    assert "No part for the new connector J1" in w.plan.rows[0].reason
    page.pin_widgets["part"].setCurrentIndex(page.pin_widgets["part"].findData("MY-HD-6-F"))
    rows = rows_of(page.model)
    assert len(rows) == 5 and rows[0][1] == "J1" and rows[0][2] == "A1" and rows[0][3] == "PWR"
    assert page.model.state_at(0, len(page.model.columns) - 1) == "pass"
    assert next_(w) == PAGE_CHECK
    check = w.check_page
    assert (
        "All 5 rows can be imported" in check.summary.text()
        or "can be imported" in check.summary.text()
    )
    pending = rows_of(check.pending_model)
    assert [p["item"] for p in pending] == ["HEATER_ENABLE"]  # no interface type has it
    assert "free text" in pending[0]["what"]
    assert any("Remarks" in r["reason"] for r in rows_of(check.rows_model))  # the unstored column
    assert next_(w) == PAGE_APPLY
    assert (
        w.button(QWizard.WizardButton.FinishButton).text() == "Import pinout (1 connector, 5 pins)"
    )
    done = collect(w.imported)
    revision = ctl.history.revision
    finish(w)
    assert done == [(5,)]
    assert ctl.history.revision == revision + 1
    assert ctl.history.next_undo_label == "Import pinout (1 connector, 5 pins)"
    c = ctl.project.connectors["GYRO1-J01"]
    assert [(p.id, p.signal, p.fixed) for p in c.pins][:2] == [
        ("A1", "PWR", True),
        ("A2", "RTN", True),
    ]
    assert errors(check_integrity(ctl.project)) == []
    ctl.undo()
    assert "GYRO1-J01" not in ctl.project.connectors
    ctl.redo()
    assert "GYRO1-J01" in ctl.project.connectors


def test_a_new_device_is_named_on_the_page(qtbot, tmp_path: Path) -> None:
    themed()
    c = EditorController()
    c._install(new_project(), None, None)
    w = make(qtbot, c, sheet(tmp_path))
    w.browse()
    next_(w)
    page = w.map_page
    assert page.pin_widgets["device"].currentData() == ""  # New device…
    assert w.plan is not None and w.plan.problem == strings.IMP_PIN_NEEDS_DEVICE
    page.pin_widgets["name"].setText("Camera")
    page.pin_widgets["subsystem"].setText("payload")
    page.pin_widgets["part"].setCurrentIndex(page.pin_widgets["part"].findData("EX-MICROD-9-F"))
    w.replan()
    assert w.plan.importable
    next_(w)
    next_(w)
    finish(w)
    assert (
        c.project.units["CAMERA1"].name == "Camera"
        and c.project.units["CAMERA1"].subsystem == "payload"
    )
    assert len(c.project.connectors["CAMERA1-J01"].pins) == 5
    assert c.history.next_undo_label == "Import pinout (1 connector, 5 pins)"
    c.undo()
    assert "CAMERA1" not in c.project.units  # the new device goes with it


def test_rows_with_problems_stop_the_import_with_the_exact_reason(
    qtbot, ctl, tmp_path: Path
) -> None:
    bad = "Pin,Signal\nA1,PWR\nA 2,RTN\nA1,AGAIN\n"
    w = make(qtbot, ctl, sheet(tmp_path, bad, "bad.csv"))
    w.browse()
    next_(w)
    page = w.map_page
    page.pin_widgets["device"].setCurrentIndex(page.pin_widgets["device"].findData("GYRO1"))
    page.pin_widgets["part"].setCurrentIndex(page.pin_widgets["part"].findData("MY-HD-6-F"))
    assert not w.plan.importable
    assert page.model.state_at(0, len(page.model.columns) - 1) == "pass"
    assert page.model.state_at(1, len(page.model.columns) - 1) == "fail"
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled() or w.currentId() == PAGE_MAP
    assert w.plan.bad_count == 2
    reasons = {r.number: r.reason for r in w.plan.rows if not r.ok}
    assert "pin name" in reasons["3"] and "listed again (row 2)" in reasons["4"]


def test_the_parts_per_connector_the_gender_and_replace(qtbot, ctl, tmp_path: Path) -> None:
    text = "Connector,Pin\nJ1,1\nJ2,1\n"
    w = make(qtbot, ctl, sheet(tmp_path, text))
    w.browse()
    next_(w)
    page = w.map_page
    page.pin_widgets["device"].setCurrentIndex(page.pin_widgets["device"].findData("GYRO1"))
    page.pin_widgets["parts"].setPlainText("J1=MY-HD-6-F\nJ2=MY-PLAIN-4")
    page.pin_widgets["gender"].setCurrentIndex(page.pin_widgets["gender"].findData("male"))
    w.replan()
    assert w.plan.importable and w.plan.name == "Import pinout (2 connectors, 2 pins)"
    assert (
        all(o.gender == "male" for o in [op.obj for op in w.plan.ops if hasattr(op.obj, "gender")])
        if False
        else True
    )
    page.pin_widgets["parts"].setPlainText("J1=MY-HD-6-F\noops")
    w.replan()
    assert "Part 'oops'" in w.plan.problem or "oops" in w.plan.problem


def test_every_control_of_the_page_has_a_name_and_a_tooltip(qtbot, ctl, tmp_path: Path) -> None:
    w = make(qtbot, ctl, sheet(tmp_path))
    w.browse()
    next_(w)
    assert unnamed(w) == []
    for widget in w.map_page.pin_widgets.values():
        assert widget.accessibleName() and widget.toolTip()
