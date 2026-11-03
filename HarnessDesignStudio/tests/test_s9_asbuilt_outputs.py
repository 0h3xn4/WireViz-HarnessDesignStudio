# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,attr-defined"
"""S9 (R6): what is written about the as-built records. The report and the *As-built* sheet exist only
for a project that has records; every other written file of a project without records is byte for
byte as before, and with records only the files that carry them differ; the independent verifier
reads them; the outputs are out of date when the records change."""

import io
from pathlib import Path

import pytest

from harness_design_studio.core import asbuilt, edit, templates
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.io import layout
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.build import (
    ASBUILT_CSV,
    ASBUILT_MD,
    build_outputs,
    outputs_status,
    write_outputs,
)
from harness_design_studio.core.outputs.buildsheet import ASBUILT_SHEET, SHEETS, sheet_names
from harness_design_studio.core.outputs.stamp import parse_csv
from harness_design_studio.core.outputs.verify import read_folder, verify_outputs
from harness_design_studio.core.outputs.xlsx_env import load_workbook


@pytest.fixture(scope="module")
def plain(tmp_path_factory) -> Project:
    return templates.create_project(tmp_path_factory.mktemp("o") / "p", "flatsat")


def recorded(project: Project, fill: dict) -> Project:
    work = edit.clone_with(project, [])
    table = asbuilt.template_rows(work, "W001")
    head = table[0]
    for row in table[1:]:
        for heading, value in fill.get((row[0], row[2]), {}).items():
            row[head.index(heading)] = value
    apply_ops(work, asbuilt.plan_asbuilt_import(work, table).ops)
    return work


FILL = {
    ("harness", "W001"): {"Serial number": "SN-1", "Built by": "A. Tech"},
    ("wire", "W001-001"): {"Cut length (m)": "3.46"},
    ("test", "T001"): {"Result": "pass", "Continuity (ohm)": "0.4"},
    ("test", "T002"): {"Result": "pass", "Continuity (ohm)": "1.4"},
}


@pytest.fixture(scope="module")
def with_records(plain) -> Project:
    return recorded(plain, FILL)


@pytest.fixture(scope="module")
def sets(plain, with_records):
    return build_outputs(plain, drawings=False), build_outputs(with_records, drawings=False)


def test_a_project_without_records_writes_no_asbuilt_file_and_no_extra_key(sets, plain) -> None:
    before, _after = sets
    assert not [f for f in before.files if "asbuilt" in f.lower()]
    import json

    assert "asbuilt_hash" not in json.loads(before.manifest(plain))
    assert sheet_names(plain, plain.harnesses["W001"]) == list(SHEETS)


def test_with_records_only_the_files_that_carry_them_differ(sets) -> None:
    before, after = sets
    assert set(after.files) - set(before.files) == {ASBUILT_MD, ASBUILT_CSV}
    changed = {f for f in before.files if before.files[f] != after.files[f]}
    assert changed == {
        "harnesses/W001/W001_build.xlsx"
    }  # every other file is byte for byte as before
    assert (
        before.stamp.model_hash == after.stamp.model_hash
    )  # the records are not in the model hash


def test_the_manifest_has_the_hash_of_the_records_only_while_there_are_some(sets, plain, with_records) -> None:  # fmt: skip
    import json

    assert json.loads(sets[1].manifest(with_records))["asbuilt_hash"] == asbuilt.asbuilt_fingerprint(with_records)  # fmt: skip
    assert asbuilt.asbuilt_fingerprint(plain) == ""


def test_the_report_is_text_to_print_and_says_it_is_not_a_signoff(sets, with_records) -> None:
    text = sets[1].files[ASBUILT_MD].decode("utf-8")
    assert text.splitlines()[0].startswith("<!-- harness-design-studio ")
    assert "# As-built report" in text and "This report is not a sign-off" in text
    assert "does not say that a harness is compliant" in text
    assert "| W001 | incomplete |" in text and "| W002 | not started |" in text
    out = text.split("## Out of limit", 1)[1].split("## ", 1)[0]
    assert "| W001 | test T002 | continuity resistance (ohm) | 1.4 | 1 | -0.4 |" in out
    assert "recorded as passed: the tool does not accept it" in out
    assert "differs from design" not in out  # that is its own section
    assert "| W001 | wire W001-001 | cut length (m) | 3.46 | 3.45 | 0.01 |" in text
    assert "passed the test" not in text and "is compliant" not in text.replace("does not say that a harness is compliant", "")  # fmt: skip
    assert text == asbuilt.report_markdown(with_records, sets[1].stamp.line)  # the same text twice


def test_the_csv_has_one_row_for_each_value_with_the_margin(sets, with_records) -> None:
    rows = parse_csv(sets[1].files[ASBUILT_CSV])
    assert rows[0] == asbuilt.REPORT_HEADER == ["Harness", "Kind", "Item", "Value", "Status", "Actual", "Designed or limit", "Unit", "Margin", "Note"]  # fmt: skip
    row = next(r for r in rows if r[1:4] == ["test", "T002", "continuity resistance (ohm)"])
    assert row[4:9] == ["out of limit", "1.4", "1", "ohm", "-0.4"]
    assert rows == asbuilt.report_rows(with_records)
    assert {r[0] for r in rows[1:]} == {"W001"}  # the harnesses with no record have no line


def test_the_build_workbook_of_a_harness_with_records_has_an_asbuilt_sheet_before_about(sets, with_records) -> None:  # fmt: skip
    wb = load_workbook(io.BytesIO(sets[1].files["harnesses/W001/W001_build.xlsx"]), data_only=True)
    assert wb.sheetnames == [*SHEETS[:-1], ASBUILT_SHEET, "About"]
    rows = [[("" if v is None else str(v)) for v in r] for r in wb[ASBUILT_SHEET].iter_rows(values_only=True)]  # fmt: skip
    assert rows == asbuilt.report_rows(with_records, "W001")
    other = load_workbook(
        io.BytesIO(sets[1].files["harnesses/W002/W002_build.xlsx"]), data_only=True
    )
    assert other.sheetnames == list(SHEETS)  # a harness with no record keeps the sheets it had


def test_the_verifier_reads_the_report_and_the_sheet_and_can_fail(
    sets, plain, with_records
) -> None:
    assert verify_outputs(with_records, dict(sets[1].files)).ok
    assert verify_outputs(plain, dict(sets[0].files)).ok
    # the files are written only for a project that has records
    stray = dict(sets[0].files)
    stray[ASBUILT_CSV] = sets[1].files[ASBUILT_CSV]
    assert any(i.code == "out_asbuilt" for i in verify_outputs(plain, stray).issues)
    # a missing report, a report that differs, a sheet that differs
    missing = {k: v for k, v in sets[1].files.items() if k != ASBUILT_MD}
    assert any(i.code == "out_missing" for i in verify_outputs(with_records, missing).issues)
    wrong = dict(sets[1].files)
    wrong[ASBUILT_CSV] = wrong[ASBUILT_CSV].replace(b"out of limit", b"within limit")
    assert any(i.code == "out_asbuilt" for i in verify_outputs(with_records, wrong).issues)
    no_sheet = dict(sets[0].files)  # the workbook of the design alone, checked against records
    no_sheet["harnesses/W001/W001_build.xlsx"] = sets[0].files["harnesses/W001/W001_build.xlsx"]
    assert any(i.code == "out_build" for i in verify_outputs(with_records, {**sets[1].files, **no_sheet}).issues)  # fmt: skip


def test_the_outputs_are_out_of_date_when_the_records_change_not_the_design(plain, tmp_path: Path) -> None:  # fmt: skip
    first = recorded(plain, FILL)
    write_outputs(first, tmp_path / "o", build_outputs(first, drawings=False))
    assert outputs_status(first, tmp_path / "o").state == "current"
    assert verify_outputs(first, read_folder(tmp_path / "o")).ok
    more = recorded(first, {("wire", "W001-002"): {"Cut length (m)": "3.45"}})
    status = outputs_status(more, tmp_path / "o")
    assert status.state == "stale" and "as-built records changed" in status.detail
    write_outputs(more, tmp_path / "o", build_outputs(more, drawings=False))
    assert outputs_status(more, tmp_path / "o").state == "current"
    # a project that never had records: the status is as it always was
    write_outputs(plain, tmp_path / "q", build_outputs(plain, drawings=False))
    assert outputs_status(plain, tmp_path / "q").state == "current"


def test_the_release_gate_does_not_see_the_records(plain, with_records) -> None:
    from harness_design_studio.core.vcs.hashing import content_hash

    assert content_hash(plain) == content_hash(with_records)
    assert layout.model_hash(plain) == layout.model_hash(with_records)
