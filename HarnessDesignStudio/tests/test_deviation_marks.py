# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,attr-defined"
"""Transparency follow-up (D-191 (3), D-193; R7, R12): an override or a deviation shows on the tests
of the wire it is about: a band *Overrides and deviations* above the Tests sheet of the build
workbook, a last column *Deviations* in `tests.csv` (and so in the workbook of tables), and a note
on the as-built line of a measured wire. A project without one is written as before; the
independent verifier reads all of it and reports a wrong cell."""

import io

import pytest

from harness_design_studio import api
from harness_design_studio.cli.main import main
from harness_design_studio.core import asbuilt, edit, journal
from harness_design_studio.core.commands import apply_ops
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.buildsheet import FILE_SUFFIX
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.outputs.xlsx_env import load_workbook

OVERRIDE = "Smaller connector, ECR-12"
DEVIATION = "Accepted by the PA board, NCR-17"
COLOUR = "Harness colour fixed by the customer"
CELL_A = f"override gauge_awg: {OVERRIDE}; deviation current-over-wire: {DEVIATION}"
CELL_B = f"override colour: {COLOUR}"
BAND = [
    "Overrides and deviations",
    f"OVERRIDE W001-001 gauge_awg = 26: {OVERRIDE}",
    f"OVERRIDE W001-002 colour = red: {COLOUR}",
    f"DEVIATION current-over-wire.W001-001: Wire W001-001 (AWG 26) carries 0.8 A but allows 0.54 A "
    f"after derating (accepted, reason: {DEVIATION})",
]


@pytest.fixture(scope="module")
def plain_folder(tmp_path_factory):
    folder = tmp_path_factory.mktemp("plain") / "p"
    api.create_project(folder, "flatsat")
    return folder


@pytest.fixture(scope="module")
def marked_folder(tmp_path_factory):
    """flatsat with an override of a gauge that is too small, the deviation that accepts the error
    it makes, and an override of the colour of the next wire (the public commands, a fixed clock)."""
    folder = tmp_path_factory.mktemp("marked") / "p"
    api.create_project(folder, "flatsat")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(journal, "now", lambda: "2026-11-03T11:30:00Z")
        mp.setattr(journal, "author", lambda: "Ann Engineer")
        for argv in (
            ("override", folder, "W001-001", "gauge_awg", 26, "--reason", OVERRIDE),
            ("override", folder, "W001-002", "colour", "red", "--reason", COLOUR),
            ("deviation", folder, "current-over-wire.W001-001", "--reason", DEVIATION),
        ):
            assert main([*map(str, argv)]) == 0
    return folder


@pytest.fixture(scope="module")
def marked(marked_folder):
    return built(marked_folder)


def built(folder):
    p = load_project(folder).project
    return p, build_outputs(p, drawings=False).files


def sheet(files, name="Tests"):
    wb = load_workbook(io.BytesIO(files[f"harnesses/W001/W001{FILE_SUFFIX}"]), data_only=True)
    return [["" if v is None else str(v) for v in r] for r in wb[name].iter_rows(values_only=True)]


def codes(p, files):
    return {i.code for i in verify_outputs(p, files).errors}


def test_a_project_without_them_has_the_tests_as_before(plain_folder):
    p, files = built(plain_folder)
    table = parse_csv(files["harnesses/W001/tests.csv"])
    assert table[0] == ["Test", "Type", "From", "To", "Expected", "Limit", "Test voltage", "Wire"]
    rows = sheet(files)
    assert rows[0][:12] == [*table[0], "Measured", "Result", "Initials", "Date"]
    assert len(rows[0]) == 12  # no Deviations column, no band: the headings are the first row
    wb = load_workbook(io.BytesIO(files[f"harnesses/W001/W001{FILE_SUFFIX}"]))
    assert wb["Tests"].freeze_panes == "B2" and wb["Tests"].auto_filter.ref.startswith("A1:L")
    assert verify_outputs(p, files).ok


def test_the_csv_names_the_override_and_the_deviation_on_the_wires_they_are_about(marked):
    p, files = marked
    table = parse_csv(files["harnesses/W001/tests.csv"])
    assert table[0][-1] == "Deviations" and len(table[0]) == 9
    by = {(r[1], r[7]): r[8] for r in table[1:]}
    assert by[("continuity", "W001-001")] == CELL_A
    assert by[("isolation", "W001-001")] == CELL_A
    assert by[("continuity", "W001-002")] == CELL_B
    shield = next(r for r in table[1:] if r[7] == "W001-001;W001-002")
    assert shield[8] == f"W001-001: {CELL_A} | W001-002: {CELL_B}"
    assert not any(
        r[8] for r in table[1:] if r[7] not in ("W001-001", "W001-002") and ";" not in r[7]
    )
    # nothing about who or when
    for data in files.values():
        assert b"Ann Engineer" not in data and b"2026-11-03T11" not in data
    # the other harness has neither a column nor a mark
    assert parse_csv(files["harnesses/W002/tests.csv"])[0][-1] == "Wire"


def test_the_tests_sheet_has_the_band_above_the_table_and_the_column(marked):
    p, files = marked
    rows = sheet(files)
    assert [r[0] for r in rows[:4]] == BAND and not any(rows[4]) and rows[5][0] == "Test"
    assert rows[5][:13] == [
        "Test", "Type", "From", "To", "Expected", "Limit", "Test voltage", "Wire",
        "Measured", "Result", "Initials", "Date", "Deviations",
    ]  # fmt: skip
    first = next(r for r in rows[6:] if r[1] == "continuity" and r[7] == "W001-001")
    assert first[12] == CELL_A and first[8:12] == ["", "", "", ""]
    wb = load_workbook(io.BytesIO(files[f"harnesses/W001/W001{FILE_SUFFIX}"]))
    ws = wb["Tests"]
    assert ws.auto_filter.ref.startswith("A6:M") and ws.print_title_rows == "$6:$6"
    assert ws.freeze_panes is None
    assert verify_outputs(p, files).ok


def test_the_workbook_of_tables_carries_the_column(marked):
    p, files = marked
    xlsx = load_workbook(io.BytesIO(files["harnesses/W001/W001.xlsx"]), data_only=True)
    assert [c.value for c in xlsx["Tests"][1]][-1] == "Deviations"


def test_the_verifier_reports_a_wrong_cell_in_the_csv(marked):
    p, files = marked
    assert codes(p, files) == set()
    table = parse_csv(files["harnesses/W001/tests.csv"])
    table[1][8] = "deviation current-over-wire: nothing to see"
    bad = dict(files, **{"harnesses/W001/tests.csv": csv_bytes(table, stamp_of(p))})
    assert "out_tests" in codes(p, bad)
    # a column that is not there when it should be
    plain = [r[:8] for r in parse_csv(files["harnesses/W001/tests.csv"])]
    bad = dict(files, **{"harnesses/W001/tests.csv": csv_bytes(plain, stamp_of(p))})
    assert "out_tests" in codes(p, bad)


def replace_cell(data, sheet_name, row, col, value):
    wb = load_workbook(io.BytesIO(data))
    wb[sheet_name].cell(row=row, column=col).value = value
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def test_the_verifier_reports_a_wrong_cell_or_band_in_the_workbook(marked):
    p, files = marked
    rel = f"harnesses/W001/W001{FILE_SUFFIX}"
    wrong_cell = dict(files, **{rel: replace_cell(files[rel], "Tests", 7, 13, "no deviations")})
    assert "out_build" in codes(p, wrong_cell)
    wrong_band = dict(files, **{rel: replace_cell(files[rel], "Tests", 4, 1, "DEVIATION none")})
    assert "out_build" in codes(p, wrong_band)
    no_band = dict(files, **{rel: replace_cell(files[rel], "Tests", 2, 1, None)})
    assert "out_build" in codes(p, no_band)


def test_a_deviation_on_the_interface_of_a_wire_marks_its_tests_too(marked_folder):
    # the contact and connector-voltage rules are placed on INTERFACE.CONNECTOR
    from harness_design_studio.core.deviations import _deviation_wires

    p = load_project(marked_folder).project
    w = p.harnesses["W001"].wires[0]
    assert w.interface_id
    assert w.id in _deviation_wires(p.harnesses["W001"], f"{w.interface_id}.J9")
    assert w.id in _deviation_wires(p.harnesses["W001"], w.from_connector)
    assert _deviation_wires(p.harnesses["W001"], "elsewhere") == []


def test_the_asbuilt_line_of_a_measured_wire_repeats_the_marks(marked_folder):
    p = load_project(marked_folder).project
    work = edit.clone_with(p, [])
    table = asbuilt.template_rows(work, "W001")
    head = table[0]
    for row in table[1:]:
        if (row[0], row[2]) in (("test", "T001"), ("test", "T002")):
            row[head.index("Result")] = "pass"
            row[head.index("Continuity (ohm)")] = "0.4"
    apply_ops(work, asbuilt.plan_asbuilt_import(work, table).ops)
    lines = [ln for ln in asbuilt.harness_lines(work, work.harnesses["W001"]) if ln.kind == "test"]
    one = next(ln for ln in lines if ln.subject == "T001" and ln.field.startswith("continuity"))
    assert one.text.endswith(f"; design: {CELL_A}")
    two = next(ln for ln in lines if ln.subject == "T002" and ln.field.startswith("continuity"))
    assert two.text.endswith(f"; design: {CELL_B}")
    files = build_outputs(work, drawings=False).files
    assert verify_outputs(work, files).ok
    assert CELL_A in files["system/asbuilt_report.csv"].decode()
