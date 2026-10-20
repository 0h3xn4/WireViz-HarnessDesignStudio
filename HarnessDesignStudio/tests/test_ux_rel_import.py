# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-17: the import wizard (file, columns + preview, conflicts and placeholders, apply) for interfaces,
approved parts, segment lengths, engineering values and a KiCad netlist, on the flatsat example.
Each import is ONE undo step called "Import n rows", and Undo takes all of it back."""

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWizard  # noqa: E402

from harness_design_studio.core.errors import HarnessError  # noqa: E402
from harness_design_studio.core.imports import ImportError_  # noqa: E402
from harness_design_studio.gui import import_kinds, strings  # noqa: E402
from harness_design_studio.gui.import_wizard import (  # noqa: E402
    PAGE_APPLY,
    PAGE_CHECK,
    PAGE_FILE,
    PAGE_MAP,
    ImportWizard,
)
from harness_design_studio.resources import examples_path  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.ux_rel import collect, dict_rows, flatsat_controller, release_all, themed  # noqa: E402

TEMPLATES = examples_path() / "templates"  # type: ignore[operator]


@pytest.fixture
def ctl(qtbot, tmp_path: Path):
    themed()
    return flatsat_controller(tmp_path)


def make(qtbot, ctl, kind: str, path: Path | str | None = None) -> ImportWizard:
    w = ImportWizard(ctl, themed(), pick_file=lambda k, f: str(path) if path else None, kind=kind)
    qtbot.addWidget(w)
    w.show()
    return w


def next_(w: ImportWizard) -> int:
    button = w.button(QWizard.WizardButton.NextButton)
    assert button.isEnabled(), f"Next is disabled on page {w.currentId()}"
    button.click()
    return w.currentId()


def finish(w: ImportWizard) -> None:
    button = w.button(QWizard.WizardButton.FinishButton)
    assert button.isEnabled()
    button.click()


def rows_of(model) -> list[dict[Any, Any]]:
    return dict_rows(model)


def parts_to_the_page_with_words(w: ImportWizard) -> None:
    page = w.map_page
    page.word_edits["approved"].setText("Approved")
    page.word_edits["pending"].setText("Review")
    page.word_edits["rejected"].setText("Rejected")
    w.replan()


# ---- page 1 -------------------------------------------------------------------------------------


def test_the_first_page_offers_every_kind_and_waits_for_a_readable_file(qtbot, ctl, tmp_path) -> None:  # fmt: skip
    w = make(qtbot, ctl, "interfaces")
    assert w.currentId() == PAGE_FILE
    names = {r.accessibleName() for r in w.file_page.radios.values()}
    assert names == {k.title for k in import_kinds.KINDS} and len(names) == 6
    assert w.file_page.radios["interfaces"].isChecked()
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled()
    assert w.file_page.status.text() == strings.IMP_FILE_NONE
    assert w.load_file(str(tmp_path / "missing.csv")) is False
    assert w.file_page.notice.isVisible() and w.file_page.notice.severity == "error"
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled()
    bad = tmp_path / "list.txt"
    bad.write_text("x")
    assert w.load_file(str(bad)) is False
    assert "Only .csv, .tsv, .json and .xlsx" in w.file_page.notice.text()
    assert w.load_file(str(TEMPLATES / "interfaces.csv"))
    assert not w.file_page.notice.isVisible()
    assert (
        "interfaces.csv" in w.file_page.status.text() and "2 data rows" in w.file_page.status.text()
    )
    assert w.button(QWizard.WizardButton.NextButton).isEnabled()


def test_the_file_is_read_again_as_the_kind_changes(qtbot, ctl) -> None:
    w = make(qtbot, ctl, "parts")
    assert w.load_file(str(TEMPLATES / "approved-parts.csv"))
    w.file_page.radios["netlist"].click()
    assert w.kind == "netlist" and w.source is None  # a CSV is not a netlist
    assert w.file_page.notice.isVisible()  # why it cannot be read as a netlist
    w.file_page.path.setText(str(TEMPLATES / "wheel-connectors.net"))
    assert w.load_file(str(TEMPLATES / "wheel-connectors.net"))
    assert "components" in w.file_page.status.text()
    assert w.source is not None and w.source.netlist is not None


def test_a_read_only_project_cannot_import(qtbot, ctl) -> None:
    ctl.project.read_only = True
    w = make(qtbot, ctl, "parts", TEMPLATES / "approved-parts.csv")
    assert w.file_page.notice.isVisible() and w.file_page.notice.text() == strings.IMP_READ_ONLY
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled()
    assert w.source is None


# ---- approved parts: the whole journey ------------------------------------------------------------


def test_parts_import_is_one_undo_step_and_undo_reverts_it(qtbot, ctl) -> None:
    before_parts = dict(ctl.project.parts)
    before_info = ctl.project.library_info
    revision = ctl.history.revision
    w = make(qtbot, ctl, "parts")
    w.pick_file = lambda k, f: str(TEMPLATES / "approved-parts.csv")
    w.browse()
    assert next_(w) == PAGE_MAP
    page = w.map_page
    # the columns were matched from the headings
    assert page.map_boxes["part_number"].currentText() == "part number"
    assert page.map_boxes["approval"].currentText() == "approval status"
    parts_to_the_page_with_words(w)
    # the first rows, as they will be read, with their status as chips
    rows = rows_of(page.model)
    assert len(rows) == 5 and rows[0][1] == "EX-MICROD-9-F"
    assert page.model.state_at(0, len(page.model.columns) - 1) == "pass"
    assert ctl.history.revision == revision and ctl.project.parts == before_parts  # nothing yet
    assert next_(w) == PAGE_CHECK
    check = w.check_page
    assert "All 5 rows can be imported" in check.summary.text()
    pending = rows_of(check.pending_model)
    assert [p["item"] for p in pending] == ["EX-RJ45-F"]  # "Review" means not decided: pending
    assert pending[0]["pending_state"] == "pending" and "pending" in pending[0]["what"]
    assert "approved-parts.csv" in check.notes.text()  # where the library data came from
    assert next_(w) == PAGE_APPLY
    assert w.apply_page.head.text().count("5 rows") == 1
    assert "one undo step called “Import 5 rows”" in w.apply_page.detail.text()
    assert w.button(QWizard.WizardButton.FinishButton).text() == "Import 5 rows"
    done = collect(w.imported)
    finish(w)
    assert done == [(5,)]
    assert ctl.history.revision == revision + 1  # ONE step
    assert ctl.history.next_undo_label == "Import 5 rows"
    assert ctl.project.parts["EX-RJ45-F"].approval == "pending"
    assert "approved-parts.csv" in ctl.project.library_info.source
    ctl.undo()
    assert ctl.project.parts == before_parts and ctl.project.library_info == before_info
    ctl.redo()
    assert ctl.project.parts["EX-RJ45-F"].approval == "pending"


def test_parts_with_unknown_words_are_listed_with_the_exact_reason_and_block_the_import(qtbot, ctl, tmp_path) -> None:  # fmt: skip
    csv = tmp_path / "parts.csv"
    csv.write_text(
        "part number,category,approval status\n"
        "EX-A-1,connector,Approved\n"
        "EX-B-2,connector,Maybe\n"
        "bad id!,connector,Approved\n"
        "EX-C-3,gizmo,Approved\n"
    )
    w = make(qtbot, ctl, "parts", csv)
    w.browse()
    next_(w)
    w.map_page.word_edits["approved"].setText("Approved")
    w.replan()
    next_(w)
    check = w.check_page
    assert w.plan is not None and not w.plan.importable
    rows = {r["row"]: r for r in rows_of(check.rows_model)}
    assert rows["2"]["state"] == "pass"
    assert rows["3"]["reason"] == "Approval status 'Maybe' is not in your approved, pending or rejected lists; say what it means"  # fmt: skip
    assert "cannot be used as a part ID" in rows["4"]["reason"]
    assert rows["5"]["reason"].startswith("Category 'gizmo' is not one of connector")
    assert check.rows_model.state_at(2, 2) == "fail"
    assert "1 of 4 rows can be imported; 3 have problems" in check.summary.text()
    assert (
        strings.IMP_CHECK_BLOCKS in check.summary.text()
    )  # parts: one error stops all, as on the CLI
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled()
    # the filter hides what is fine; a reason is also the cell's tooltip
    assert check.only.isChecked() and check.rows.proxy.rowCount() == 3
    check.only.setChecked(False)
    assert check.rows.proxy.rowCount() == 4
    index = check.rows.proxy.index(1, 3)
    assert index.data(Qt.ItemDataRole.ToolTipRole) == rows["3"]["reason"]
    assert check.rows.wordWrap()


def test_two_approval_columns_are_said_in_words(qtbot, ctl, tmp_path) -> None:
    csv = tmp_path / "parts.csv"
    csv.write_text("part number,status,approval\nEX-A-1,Approved,Approved\n")
    w = make(qtbot, ctl, "parts")
    assert w.load_file(str(csv)) is False
    assert "both about the approval status" in w.file_page.notice.text()
    assert isinstance(ImportError_("x"), HarnessError)


# ---- segment lengths ------------------------------------------------------------------------------


def test_lengths_import_is_one_undo_step_in_the_chosen_unit(qtbot, ctl) -> None:
    before = {h: [s.length_m for s in x.segments] for h, x in ctl.project.harnesses.items()}
    revision = ctl.history.revision
    w = make(qtbot, ctl, "lengths", TEMPLATES / "segment-lengths.csv")
    w.browse()
    next_(w)
    assert w.map_page.unit_box.currentText() == "mm"
    rows = rows_of(w.map_page.model)
    assert [r[1] for r in rows] == ["W001", "W002"] and rows[0][3] == "850 mm"
    w.map_page.unit_box.setCurrentIndex(w.map_page.unit_box.findData("cm"))  # 850 cm: 8.5 m
    assert rows_of(w.map_page.model)[0][3] == "850 cm"
    w.map_page.unit_box.setCurrentIndex(w.map_page.unit_box.findData("mm"))
    next_(w)
    assert "All 2 rows can be imported" in w.check_page.summary.text()
    assert not w.check_page.pending.isVisible()  # nothing is left open by lengths
    next_(w)
    finish(w)
    seg = next(s for s in ctl.project.harnesses["W001"].segments if s.id == "W001-L1")
    assert seg.length_m == pytest.approx(0.85)
    assert ctl.history.revision == revision + 1 and ctl.history.next_undo_label == "Import 2 rows"
    ctl.undo()
    assert {h: [s.length_m for s in x.segments] for h, x in ctl.project.harnesses.items()} == before


def test_a_length_for_a_released_harness_is_refused_with_the_reason(qtbot, ctl, tmp_path) -> None:
    assert release_all(ctl) == ["W001", "W003"]
    w = make(qtbot, ctl, "lengths", TEMPLATES / "segment-lengths.csv")
    w.browse()
    next_(w)
    next_(w)
    reasons = {r["item"]: r["reason"] for r in rows_of(w.check_page.rows_model)}
    assert reasons["W001 / W001-L1"] == "Harness 'W001' is released and locked"
    assert reasons["W002 / W002-L1"] == ""
    assert w.plan is not None and not w.plan.importable  # one bad row stops all


def test_a_length_file_with_another_column_order_gets_the_hint(qtbot, ctl, tmp_path) -> None:
    csv = tmp_path / "lengths.csv"
    csv.write_text("segment,length,harness\nW001-L1,850,W001\n")
    w = make(qtbot, ctl, "lengths", csv)
    w.browse()
    next_(w)
    next_(w)
    assert "read by position" in w.check_page.notes.text()


# ---- engineering values --------------------------------------------------------------------------------


def ampacity_csv(tmp_path: Path) -> Path:
    csv = tmp_path / "ampacity.csv"
    csv.write_text("gauge,amperes\n24,2.5\n22,3.5\n20,5.5\n")
    return csv


def test_the_ampacity_table_import_names_the_placeholder_it_leaves(qtbot, ctl, tmp_path) -> None:
    before = ctl.project.config["derating"].values["ampacity_a_by_awg"]
    revision = ctl.history.revision
    w = make(qtbot, ctl, "values", ampacity_csv(tmp_path))
    w.browse()
    next_(w)
    assert [r[1] for r in rows_of(w.map_page.model)] == ["24", "22", "20"]
    next_(w)
    check = w.check_page
    assert "All 3 rows can be imported" in check.summary.text()
    pending = rows_of(check.pending_model)
    assert [p["item"] for p in pending] == ["config/derating.json"]
    assert "placeholder" in pending[0]["what"] and pending[0]["pending_state"] == "pending"
    assert "replaced" in check.notes.text()
    next_(w)
    finish(w)
    assert ctl.project.config["derating"].values["ampacity_a_by_awg"] == {"24": 2.5, "22": 3.5, "20": 5.5}  # fmt: skip
    assert ctl.project.config["derating"].placeholder is True  # still not reviewed
    assert ctl.history.revision == revision + 1 and ctl.history.next_undo_label == "Import 3 rows"
    ctl.undo()
    assert ctl.project.config["derating"].values["ampacity_a_by_awg"] == before


def test_the_same_ampacity_table_is_not_an_import(qtbot, ctl) -> None:
    w = make(qtbot, ctl, "values", TEMPLATES / "ampacity-DEMO-ONLY.csv")  # flatsat has these values
    w.browse()
    next_(w)
    assert w.plan is not None and w.plan.problem == strings.IMP_VALUES_SAME
    assert w.map_page.notice.isVisible()


def test_ampacity_rows_with_problems_are_named(qtbot, ctl, tmp_path) -> None:
    csv = tmp_path / "amp.csv"
    csv.write_text("gauge,amperes\n24,2.0\nxx,3\n22,-1\n24,5\n")
    w = make(qtbot, ctl, "values", csv)
    w.browse()
    next_(w)
    next_(w)
    reasons = {r["row"]: r["reason"] for r in rows_of(w.check_page.rows_model)}
    assert reasons["2"] == ""
    assert "are not a gauge and an ampere value" in reasons["3"]
    assert "not possible" in reasons["4"] and "appears twice" in reasons["5"]
    assert not w.plan.importable  # type: ignore[union-attr]


def test_a_released_project_refuses_the_ampacity_table_with_the_reason(qtbot, ctl, tmp_path) -> None:  # fmt: skip
    release_all(ctl)
    w = make(qtbot, ctl, "values", ampacity_csv(tmp_path))
    w.browse()
    next_(w)
    assert w.plan is not None and "blocked because it touches released items" in w.plan.problem
    next_(w)
    assert w.check_page.notice.isVisible() and "released" in w.check_page.notice.text()
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled()


# ---- interfaces ------------------------------------------------------------------------------------


def interface_csv(ctl, tmp_path: Path) -> Path:  # OBC1 and RFSU1 have a free RS-422 connector
    csv = tmp_path / "interfaces.csv"
    csv.write_text(
        "id,type,from,to,redundancy\n"
        "IF-900,rs422,OBC1,RFSU1,nominal\n"
        "IF-010,rs422,OBC1,RW1,nominal\n"
        "IF-901,nonsense,OBC1,RW1,nominal\n"
    )
    return csv


def test_interfaces_import_skips_rows_with_problems_and_is_one_step(qtbot, ctl, tmp_path) -> None:
    csv = interface_csv(ctl, tmp_path)
    revision = ctl.history.revision
    n_before = len(ctl.project.interfaces)
    w = make(qtbot, ctl, "interfaces", csv)
    w.browse()
    next_(w)
    assert w.map_page.map_boxes["id"].currentText() == "id"
    next_(w)
    check = w.check_page
    reasons = {r["item"]: r["reason"] for r in rows_of(check.rows_model)}
    assert reasons["IF-010"] == "ID IF-010 is already used"
    assert reasons["IF-901"] == "Unknown interface type 'nonsense'"
    assert w.plan is not None and w.plan.partial and w.plan.importable  # the good row can go in
    assert strings.IMP_CHECK_SKIPS in check.summary.text()
    # what is left unconfirmed is listed
    assert [p["item"] for p in rows_of(check.pending_model)] == ["IF-900"]
    assert "Auto" in rows_of(check.pending_model)[0]["what"]
    next_(w)
    assert "1 rows with problems" not in w.apply_page.detail.text()  # singular/plural kept simple
    finish(w)
    assert len(ctl.project.interfaces) == n_before + 1 and "IF-900" in ctl.project.interfaces
    assert ctl.history.revision == revision + 1 and ctl.history.next_undo_label == "Import 1 row"
    ctl.undo()
    assert len(ctl.project.interfaces) == n_before


def test_changing_a_column_choice_reads_the_rows_again(qtbot, ctl, tmp_path) -> None:
    csv = tmp_path / "interfaces.csv"
    csv.write_text("col1,col2,col3,col4,col5\nIF-900,rs422,OBC1,RFSU1,nominal\n")
    w = make(qtbot, ctl, "interfaces", csv)
    w.browse()
    next_(w)
    page = w.map_page
    assert [page.map_boxes[k].currentIndex() for k in ("id", "type", "from", "to")] == [
        1,
        2,
        3,
        4,
    ]  # by position
    assert rows_of(page.model)[0]["state"] == "pass"
    page.map_boxes["type"].setCurrentIndex(0)  # not used
    row = rows_of(page.model)[0]
    assert row[2] == "" and row["state"] == "fail" and "Unknown interface type" in row["reason"]


# ---- a KiCad netlist ----------------------------------------------------------------------------------


def test_netlist_needs_a_unit_and_says_what_to_enter_in_the_wizard_s_words(qtbot, ctl) -> None:
    w = make(qtbot, ctl, "netlist", TEMPLATES / "wheel-connectors.net")
    w.browse()
    assert next_(w) == PAGE_MAP
    page = w.map_page
    assert page.notice.text() == strings.IMP_NO_UNIT
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled()  # nothing to look at yet
    page.net_unit.setCurrentIndex(page.net_unit.findData("RW1"))
    assert not page.notice.isVisible()
    assert [r[0] for r in rows_of(page.model)] == ["J1", "J2"]
    # a prefix that matches nothing: the planner's CLI wording is translated
    page.prefix.setText("Z")
    page._timer.stop()
    w.replan()
    (row,) = rows_of(page.model)
    assert row["state"] == "fail"
    reason = w.plan.rows[0].reason  # type: ignore[union-attr]
    assert "No component starts with 'Z'" in reason and "--ref" not in reason
    assert "“Only these references”" in reason


def test_netlist_import_sets_fixed_signals_in_one_undo_step(qtbot, ctl) -> None:
    revision = ctl.history.revision
    before = ctl.project.connectors["RW1-J01"]
    w = make(qtbot, ctl, "netlist", TEMPLATES / "wheel-connectors.net")
    w.browse()
    next_(w)
    page = w.map_page
    page.net_unit.setCurrentIndex(page.net_unit.findData("RW1"))
    next_(w)
    rows = {r["row"]: r for r in rows_of(w.check_page.rows_model)}
    assert rows["J1"]["item"] == "J1 → RW1-J01" and rows["J1"]["result"] == strings.IMP_WILL_UPDATE
    assert rows["J1"]["state"] == "pass"
    # signals that match no interface type are listed as pending, not hidden
    assert w.plan is not None and w.plan.importable
    next_(w)
    assert w.button(QWizard.WizardButton.FinishButton).text() == "Import 2 rows"
    finish(w)
    after = ctl.project.connectors["RW1-J01"]
    assert after != before
    assert any(p.fixed and p.signal == "PWR" for p in after.pins)
    assert ctl.history.revision == revision + 1 and ctl.history.next_undo_label == "Import 2 rows"
    ctl.undo()
    assert ctl.project.connectors["RW1-J01"] == before


def test_a_new_connector_needs_a_part_and_the_wizard_says_where_to_enter_it(qtbot, ctl) -> None:
    w = make(qtbot, ctl, "netlist", TEMPLATES / "wheel-connectors.net")
    w.browse()
    next_(w)
    page = w.map_page
    page.net_unit.setCurrentIndex(page.net_unit.findData("SS1"))  # a unit with other connectors
    page.ids.setPlainText("J1=SS1-NEW1")
    w.replan()
    row = next(r for r in w.plan.rows if r.number == "J1")  # type: ignore[union-attr]
    assert row.state == "fail" and "enter J1=PART in “Part for each connector”" in row.reason
    assert "--part" not in row.reason
    page.parts.setPlainText("J1=EX-DSUB-9-F")
    w.replan()
    row = next(r for r in w.plan.rows if r.number == "J1")  # type: ignore[union-attr]
    assert row.state == "pass" and row.result == strings.IMP_WILL_ADD
    page.ids.setPlainText("J1")  # a malformed pair is a message on the page, not an exception
    w.replan()
    assert "must look like REF=VALUE" in w.plan.problem  # type: ignore[union-attr]


# ---- nothing before Finish, keyboard, names ----------------------------------------------------------------


def test_nothing_changes_before_finish_and_cancel_keeps_it_so(qtbot, ctl) -> None:
    revision, parts = ctl.history.revision, dict(ctl.project.parts)
    w = make(qtbot, ctl, "parts", TEMPLATES / "approved-parts.csv")
    w.browse()
    next_(w)
    parts_to_the_page_with_words(w)
    next_(w)
    next_(w)
    w.button(QWizard.WizardButton.CancelButton).click()
    assert ctl.history.revision == revision and ctl.project.parts == parts and not ctl.dirty


def test_a_refused_import_keeps_the_wizard_open_and_says_why(qtbot, ctl, monkeypatch) -> None:
    w = make(qtbot, ctl, "lengths", TEMPLATES / "segment-lengths.csv")
    w.browse()
    next_(w)
    next_(w)
    next_(w)
    monkeypatch.setattr(ctl, "run", lambda *a, **k: (ctl.message.emit("W001 is released.", False), False)[1])  # fmt: skip
    finish(w)
    assert w.currentId() == PAGE_APPLY and w.apply_page.notice.isVisible()
    assert "W001 is released." in w.apply_page.notice.text()


def test_keyboard_only(qtbot, ctl) -> None:
    w = make(qtbot, ctl, "interfaces")
    w.activateWindow()
    qtbot.waitActive(w)
    QApplication.processEvents()
    # choose a kind with the arrow keys, type the path, Enter reads it, Space on Next goes on
    radio = w.file_page.radios["interfaces"]
    radio.setFocus()
    QTest.keyClick(radio, Qt.Key.Key_Down)
    assert w.kind == "parts"
    w.file_page.path.setFocus()
    QTest.keyClicks(w.file_page.path, str(TEMPLATES / "approved-parts.csv"))
    QTest.keyClick(w.file_page.path, Qt.Key.Key_Return)
    assert w.source is not None and w.source.name == "approved-parts.csv"
    assert w.currentId() == PAGE_MAP  # Enter also pressed the default button, Next
    back = w.button(QWizard.WizardButton.BackButton)
    back.setFocus()
    QTest.keyClick(back, Qt.Key.Key_Space)
    assert w.currentId() == PAGE_FILE
    nxt = w.button(QWizard.WizardButton.NextButton)
    nxt.setFocus()
    QTest.keyClick(nxt, Qt.Key.Key_Space)
    assert w.currentId() == PAGE_MAP


def test_every_page_has_names_and_tooltips(qtbot, ctl) -> None:
    w = make(qtbot, ctl, "parts", TEMPLATES / "approved-parts.csv")
    w.browse()
    assert unnamed(w) == []
    for which in (QWizard.WizardButton.NextButton, QWizard.WizardButton.CancelButton):
        assert w.button(which).toolTip()
    next_(w)
    assert unnamed(w) == []
    parts_to_the_page_with_words(w)
    next_(w)
    assert unnamed(w) == []
    next_(w)
    assert unnamed(w) == [] and w.button(QWizard.WizardButton.FinishButton).toolTip()
    w.back()
    w.back()
    assert w.currentId() == PAGE_MAP
