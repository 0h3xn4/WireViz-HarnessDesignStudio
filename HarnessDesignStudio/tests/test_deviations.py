# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,func-returns-value"
"""S4 (D-191 (3)): an error of an electrical rule can be accepted as a recorded deviation. The finding
stays on every list and output, marked DEVIATION, with its reason; who and when are in the journal. An
error of another rule still cannot be waived."""

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import checks, deviations, drc, journal, templates
from harness_design_studio.core.commands import History
from harness_design_studio.core.drc.report import render_markdown
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Waiver
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.wires import plan_override

RULES = {
    "current-over-contact", "current-over-wire", "voltage-drop", "bundle-current",
    "connector-voltage", "wire-voltage", "temperature-margin",
}  # fmt: skip


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr(journal, "now", lambda: "2026-11-03T11:30:00Z")
    monkeypatch.setattr(journal, "author", lambda: "Ann Engineer")


@pytest.fixture
def folder(tmp_path, clock):
    """flatsat with a gauge too small for its current: an error of current-over-wire."""
    templates.create_project(tmp_path / "p", "flatsat", journal=True)
    p = load_project(tmp_path / "p").project
    wid = p.harnesses["W001"].wires[0].id
    History(p).execute(
        "override", plan_override(p, wid, "gauge_awg", 26, "Smaller connector, ECR-12")
    )
    save_project(p, tmp_path / "p")
    return tmp_path / "p"


def the_error(p) -> checks.Finding:
    return next(f for f in drc.run(p) if f.rule == "current-over-wire")


def test_which_rules_can_carry_a_deviation():
    assert deviations.deviation_rules() == RULES
    from harness_design_studio.core.drc.rules import RULES as ALL

    assert all(r.severity == "error" for r in ALL if r.can_deviate)


def test_an_override_that_is_too_small_is_an_open_error_that_cannot_be_waived(folder):
    p = load_project(folder).project
    f = the_error(p)
    assert f.severity == "error" and f.waiver is None and not f.can_waive and f.can_deviate
    with pytest.raises(EditError, match="cannot be waived"):
        checks.waive_op(f, "this is fine, honestly")


def test_a_deviation_needs_a_reason(folder):
    p = load_project(folder).project
    with pytest.raises(EditError, match="at least 10 characters"):
        checks.deviate_op(the_error(p), "ok")


def test_an_error_of_another_rule_cannot_be_a_deviation(folder):
    p = load_project(folder).project
    other = next(f for f in drc.run(p) if f.rule == "part-unapproved")
    with pytest.raises(EditError, match="cannot be accepted as a deviation"):
        checks.deviate_op(other, "a long enough reason")


def accept(folder, reason="Accepted by the PA board, NCR-17"):
    p = load_project(folder).project
    History(p).execute("deviation", [checks.deviate_op(the_error(p), reason)])
    save_project(p, folder)
    return load_project(folder).project


def test_a_deviation_keeps_the_finding_visible_and_marked(folder):
    p = accept(folder)
    f = the_error(p)
    assert f.deviation and f.waiver is not None and f.severity == "error"
    assert f.waiver.justification == "Accepted by the PA board, NCR-17"
    assert f.waived_mark == "deviation"
    # it is on the list of findings, not removed from it
    assert f.id in {x.id for x in drc.run(p)}
    # a waiver of a warning is not a deviation
    w = next(x for x in drc.run(p) if x.rule == "part-unapproved")
    assert not w.deviation and w.waived_mark == ""


def test_the_deviation_says_who_and_when_from_the_journal(folder, capsys):
    p = accept(folder)
    f = the_error(p)
    assert journal.who_and_when(p, f.id) == "by Ann Engineer on 2026-11-03"
    entry = journal.waiver_record(p, f.id)
    assert entry is not None and entry.kind == "deviation" and entry.field == "(added)"
    assert entry.reason == "Accepted by the PA board, NCR-17"
    capsys.readouterr()
    assert main(["deviation", str(folder)]) == 0
    out = capsys.readouterr().out
    assert "DEVIATION current-over-wire" in out and "NCR-17" in out
    assert "by Ann Engineer on 2026-11-03" in out


def test_a_waiver_of_a_warning_also_carries_who_and_when(folder):
    p = load_project(folder).project
    f = next(x for x in drc.run(p) if x.rule == "connector-lookalike")
    History(p).execute("waive", [checks.waive_op(f, "Keyed differently, see the ICD")])
    save_project(p, folder)
    p = load_project(folder).project
    entry = journal.waiver_record(p, f.id)
    assert entry is not None and entry.kind == "waiver"
    assert journal.who_and_when(p, f.id) == "by Ann Engineer on 2026-11-03"


def open_errors(p) -> list[str]:
    """The errors nobody has accepted (the outputs of a folder never exported are always out of date)."""
    return sorted(
        f.rule
        for f in [*checks.find(p), *drc.run(p)]
        if f.severity == "error" and f.waiver is None and f.rule != "verify-mismatch"
    )


def test_the_exit_code_and_the_release_gate_treat_a_deviation_as_accepted(folder, capsys):
    assert open_errors(load_project(folder).project) == ["current-over-wire"]
    assert main(["drc", str(folder)]) == 1
    capsys.readouterr()
    p = accept(folder)
    assert open_errors(p) == []
    assert main(["drc", str(folder)]) == 1  # (only the outputs that were never exported)
    report = capsys.readouterr().out
    assert "## Deviations (1)" in report and "**DEVIATION**" in report and "NCR-17" in report
    assert "Deviations: 1." in report
    assert "Open: 1 error(s)" in report  # the verifier's finding on the missing outputs, not ours


def test_a_project_without_a_deviation_has_the_same_drc_report(folder):
    p = load_project(folder).project
    text = render_markdown(p)
    assert "Deviation" not in text.replace("DEVIATION", "")
    assert "## Deviations" not in text


def test_the_outputs_show_the_deviation_and_the_verifier_accepts_them(folder):
    p = accept(folder)
    result = build_outputs(p, drawings=False)
    rows = result.files["system/drc_findings.csv"].decode().splitlines()
    mine = next(r for r in rows if r.startswith("current-over-wire."))
    assert ",error," in mine and ",deviation," in mine and "NCR-17" in mine
    report_md = result.files["system/drc_report.md"].decode()
    assert "DEVIATION" in report_md
    assert verify_outputs(p, result.files).ok
    # the harness it is about says so in its build workbook (the header section)
    from io import BytesIO

    from openpyxl import load_workbook

    from harness_design_studio.core.outputs.buildsheet import FILE_SUFFIX

    book = load_workbook(BytesIO(result.files[f"harnesses/W001/W001{FILE_SUFFIX}"]))
    start = " ".join(str(c.value) for row in book["Start here"].iter_rows() for c in row if c.value)
    assert "Overrides and deviations" in start and "NCR-17" in start
    # and the drawing notes
    from harness_design_studio.core.outputs.drawing import _extras

    assert any("DEVIATION" in line for line in _extras(p.harnesses["W001"], p))
    # no name and no time are in any output
    for data in result.files.values():
        assert b"Ann Engineer" not in data and b"2026-11-03T11" not in data


def test_a_release_record_names_the_deviations_and_the_overrides(folder):
    p = accept(folder)
    note = deviations.release_note(p, p.harnesses["W001"])
    assert note.startswith(" [Released with 1 overridden value(s)")
    assert "1 deviation(s): current-over-wire." in note and "NCR-17" in note
    assert deviations.release_note(p, p.harnesses["W002"]) == ""


def test_the_cli_records_and_takes_back_a_deviation(folder, capsys):
    finding = the_error(load_project(folder).project).id
    assert main(["deviation", str(folder), finding]) == 2  # no reason
    assert "needs a reason" in capsys.readouterr().err
    assert main(["deviation", str(folder), finding, "--reason", "short"]) == 1
    assert main(["deviation", str(folder), "nope.W9", "--reason", "a long enough reason"]) == 2
    assert main(["deviation", str(folder), finding, "--reason", "Accepted, NCR-17 refers"]) == 0
    assert "does not meet the requirement" in capsys.readouterr().out
    p = load_project(folder).project
    assert the_error(p).deviation
    assert [e.kind for e in p.journal if e.object == f"waiver:{finding}"] == ["deviation"]
    assert main(["deviation", str(folder), finding, "--remove"]) == 0
    p = load_project(folder).project
    assert not the_error(p).deviation and the_error(p).waiver is None
    assert main(["deviation", str(folder), finding, "--remove"]) == 1  # no longer one


def test_a_hand_made_waiver_of_an_error_does_not_close_it(folder):
    """A waiver without the finding hash (made by hand) is not a deviation: the tool records what a
    deviation is for. The error stays open and the exit code stays 1."""
    p = load_project(folder).project
    f = the_error(p)
    p.waivers[f.id] = Waiver(
        id=f.id, rule=f.rule, object_id="W001-001", justification="written by hand, no hash"
    )
    still = the_error(p)
    assert still.waiver is None and not still.deviation


def test_a_deviation_for_a_finding_that_changed_no_longer_applies(folder):
    p = accept(folder)
    f = the_error(p)
    old = p.waivers[f.id]
    p.waivers[f.id] = Waiver(
        id=old.id,
        rule=old.rule,
        object_id=old.object_id,
        justification=old.justification,
        finding_hash="0" * 12,
    )
    again = the_error(p)
    assert again.waiver is None and again.waiver_changed
