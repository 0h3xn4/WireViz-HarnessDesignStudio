"""REQ-OUT-06 (decision D-169): the build workbook of a harness. A document to build from: a first
sheet that says what is ready and what is missing, a cut list in cut order, one block per connector,
the parts, labels and a test sheet with columns to fill in. Every check of the independent verifier
has a mutation test that proves it can fail."""

import copy
import io
import re
import zipfile
from pathlib import Path

import pytest

from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.model import Harness, Project, evolve
from harness_design_studio.core.outputs.build import (
    build_outputs,
    drawings_exported,
    outputs_status,
    write_outputs,
)
from harness_design_studio.core.outputs.buildsheet import SHEETS, build_workbook, readiness
from harness_design_studio.core.outputs.stamp import stamp_of
from harness_design_studio.core.outputs.verify import read_folder, verify_outputs
from harness_design_studio.core.outputs.xlsx_env import Workbook, load_workbook
from harness_design_studio.core.samples import sat15_full


@pytest.fixture(scope="module")
def project() -> Project:
    return sat15_full()


@pytest.fixture(scope="module")
def built(project: Project) -> dict[str, bytes]:
    """The output set without the drawings (quick to build, and all the workbook tests need)."""
    return build_outputs(project, drawings=False).files


@pytest.fixture(scope="module")
def harness_id(project: Project) -> str:
    return sorted(project.harnesses)[0]


def _sheets(data: bytes) -> dict[str, list[list[object]]]:
    wb = load_workbook(io.BytesIO(data), data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def _with_harness(project: Project, h: Harness) -> Project:
    """A copy of the project in which harness `h` replaces the one of the same ID."""
    p = copy.deepcopy(project)
    apply_ops(p, [Put("harnesses", h)])
    return p


def _codes(project: Project, files: dict[str, bytes]) -> set[str]:
    return {i.code for i in verify_outputs(project, files).issues}


def _replace_cell(data: bytes, sheet: str, row: int, col: int, value: object) -> bytes:
    """The workbook with one cell changed (read with the library, written with it: the layout is
    not the original, but the values are what the verifier reads)."""
    wb = load_workbook(io.BytesIO(data))
    wb[sheet].cell(row=row, column=col).value = value
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


# ---- the file ------------------------------------------------------------------------------------


def test_every_harness_gets_a_build_workbook_with_the_seven_sheets(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    files = built
    for hid in project.harnesses:
        data = files[f"harnesses/{hid}/{hid}_build.xlsx"]
        assert list(_sheets(data)) == list(SHEETS)


def test_the_same_model_gives_the_same_bytes(project: Project, harness_id: str) -> None:
    h = project.harnesses[harness_id]
    a = build_workbook(project, h, stamp_of(project))
    assert a == build_workbook(project, h, stamp_of(project))
    with zipfile.ZipFile(io.BytesIO(a)) as z:  # a fixed time stamp in every entry
        assert {i.date_time for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}


def test_the_workbook_has_no_formulas(project: Project, harness_id: str) -> None:
    data = build_workbook(project, project.harnesses[harness_id], stamp_of(project))
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            if name.startswith("xl/worksheets/sheet"):
                assert "<f>" not in z.read(name).decode() and "<f " not in z.read(name).decode()


def test_text_that_looks_like_a_formula_is_stored_as_text(
    project: Project, harness_id: str
) -> None:
    h = project.harnesses[harness_id]
    w = sorted(h.wires, key=lambda x: x.id)[0]
    hostile = evolve(w, label='=HYPERLINK("http://x","y")', note="-1+2")
    p = _with_harness(project, evolve(h, wires=[hostile if x.id == w.id else x for x in h.wires]))
    data = build_workbook(p, p.harnesses[harness_id], stamp_of(p))
    cut = _sheets(data)["Cut list"]
    row = next(r for r in cut if r[1] == w.id)
    assert row[8] == '=HYPERLINK("http://x","y")' and row[10] == "-1+2"
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert b"<f>" not in z.read("xl/worksheets/sheet2.xml")


def test_it_is_laid_out_to_work_with(project: Project, harness_id: str) -> None:
    data = build_workbook(project, project.harnesses[harness_id], stamp_of(project))
    wb = load_workbook(io.BytesIO(data))
    cut, conns, tests = wb["Cut list"], wb["Connectors"], wb["Tests"]
    assert cut.freeze_panes == "C2" and cut.auto_filter.ref and tests.auto_filter.ref
    assert cut["A1"].font.b and cut["A1"].fill.fgColor.rgb.endswith("1F3A5F")
    for ws in wb.worksheets[:-1]:  # every sheet but About prints on A4, landscape, with the stamp
        assert ws.page_setup.orientation == "landscape" and ws.page_setup.paperSize == 9
        assert stamp_of(project).line in ws.oddFooter.left.text
        assert ws.column_dimensions["A"].width and ws.column_dimensions["A"].width > 5
    assert wb["Start here"].page_setup.fitToHeight == 1  # the first sheet is one page
    assert conns.freeze_panes == "A2"
    assert any(dv.sqref for dv in tests.data_validations.dataValidation)  # Pass / Fail list


# ---- what each sheet holds -----------------------------------------------------------------------


def test_the_cut_list_has_each_wire_once_thick_before_thin(
    project: Project, harness_id: str
) -> None:
    h = project.harnesses[harness_id]
    data = build_workbook(project, h, stamp_of(project))
    cut = _sheets(data)["Cut list"]
    rows = [r for r in cut[1:-1] if r[1]]
    assert sorted(str(r[1]) for r in rows) == sorted(w.id for w in h.wires)
    gauges = [r[3] for r in rows if isinstance(r[3], int)]
    assert gauges == sorted(gauges)  # the lowest AWG number (the thickest wire) first
    assert cut[-1][1] == f"{len(h.wires)} wires"


def test_a_wire_colour_is_shown_as_a_fill_and_in_words(project: Project, harness_id: str) -> None:
    h = project.harnesses[harness_id]
    data = build_workbook(project, h, stamp_of(project))
    wb = load_workbook(io.BytesIO(data))
    ws = wb["Cut list"]
    first = next(r for r in range(2, ws.max_row) if ws.cell(r, 2).value)
    cell = ws.cell(first, 3)
    assert cell.value and cell.fill.fgColor.rgb not in ("00000000", None)
    assert re.match(r"[a-z]", str(cell.value))  # the colour name, never colour alone


def test_every_pin_of_every_connector_is_in_a_block(project: Project, harness_id: str) -> None:
    h = project.harnesses[harness_id]
    data = build_workbook(project, h, stamp_of(project))
    rows = _sheets(data)["Connectors"]
    heads = [str(r[0]).split("   ·   ")[0] for r in rows if r[0] and "   ·   " in str(r[0])]
    assert sorted(heads) == sorted(c.id for c in h.connectors)
    pins = [r for r in rows if r[0] and "   ·   " not in str(r[0]) and r[0] != "Pin"]
    assert len(pins) == sum(len(c.pins) for c in h.connectors)


def test_the_test_sheet_has_empty_columns_for_the_result(project: Project, harness_id: str) -> None:
    rows = _sheets(build_workbook(project, project.harnesses[harness_id], stamp_of(project)))[
        "Tests"
    ]
    assert rows[0][-4:] == ["Measured", "Result", "Initials", "Date"]
    assert all(not any(r[-4:]) for r in rows[1:])


def test_the_first_sheet_says_what_is_open(project: Project, harness_id: str) -> None:
    h = project.harnesses[harness_id]
    checks = {c.label: c for c in readiness(project, h)}
    assert set(checks) >= {"Wires without a length", "Wires without a gauge", "Pins in use without a termination"}  # fmt: skip
    rows = _sheets(build_workbook(project, h, stamp_of(project)))["Start here"]
    table = {r[0]: r for r in rows if r and r[2] in ("OK", "TO FIX", "NOTE")}
    for label, c in checks.items():
        assert table[label][1] == c.open and table[label][2] == c.status


def test_a_wire_without_length_or_gauge_stops_the_harness_being_ready(project: Project, harness_id: str) -> None:  # fmt: skip
    h = project.harnesses[harness_id]
    w = sorted(h.wires, key=lambda x: x.id)[0]
    bare = evolve(w, length_m=None, gauge_awg=None, colour=None)
    h2 = evolve(h, wires=[bare if x.id == w.id else x for x in h.wires], segments=[])
    checks = {c.label: c for c in readiness(project, h2)}
    assert checks["Wires without a gauge"].status == "TO FIX"
    assert checks["Wires without a colour"].status == "TO FIX"
    p = _with_harness(project, h2)
    start = _sheets(build_workbook(p, p.harnesses[harness_id], stamp_of(p)))["Start here"]
    assert next(r for r in start if r and r[0] == "Ready to build")[1] == "no"
    cut = _sheets(build_workbook(p, p.harnesses[harness_id], stamp_of(p)))["Cut list"]
    assert (
        next(r for r in cut if r[1] == w.id)[3] == "to fill in"
    )  # shown as to fill in, never guessed


# ---- the export ----------------------------------------------------------------------------------


def test_the_drawings_are_optional_and_everything_else_stays(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    with_d = build_outputs(project).files
    without = built
    gone = set(with_d) - set(without)
    assert gone and all(re.search(r"/drawing_(A3|A4)(_s\d+)?\.(pdf|svg)$", k) for k in gone)
    assert not set(without) - set(with_d)
    assert verify_outputs(project, without).ok and verify_outputs(project, with_d).ok


def test_a_set_with_drawings_for_only_some_harnesses_is_reported(project: Project) -> None:
    files = dict(build_outputs(project).files)
    first = sorted(project.harnesses)[0]
    for k in [k for k in files if k.startswith(f"harnesses/{first}/drawing_")]:
        del files[k]
    assert "out_missing" in _codes(project, files)


def test_the_folder_remembers_whether_it_has_drawings(project: Project, tmp_path: Path) -> None:
    folder = tmp_path / "outputs"
    write_outputs(project, folder, build_outputs(project, drawings=False))
    assert drawings_exported(folder) is False
    write_outputs(project, folder, build_outputs(project))
    assert drawings_exported(folder) is True
    assert outputs_status(project, folder, deep=True).state == "current"
    write_outputs(project, folder, build_outputs(project, drawings=False))
    assert not list(folder.rglob("drawing_*"))  # the drawings of the earlier export are removed
    assert verify_outputs(project, read_folder(folder)).ok


# ---- the verifier catches a wrong workbook -------------------------------------------------------


def _tampered(built: dict[str, bytes], project: Project, hid: str, sheet: str, row: int, col: int, value: object) -> set[str]:  # fmt: skip
    files = dict(built)
    rel = f"harnesses/{hid}/{hid}_build.xlsx"
    files[rel] = _replace_cell(files[rel], sheet, row, col, value)
    return _codes(project, files)


def test_the_verifier_notices_a_changed_length(
    built: dict[str, bytes], project: Project, harness_id: str
) -> None:
    data = built[f"harnesses/{harness_id}/{harness_id}_build.xlsx"]
    ws = load_workbook(io.BytesIO(data))["Cut list"]
    row = next(r for r in range(2, ws.max_row) if isinstance(ws.cell(r, 6).value, int | float))
    assert "out_build" in _tampered(built, project, harness_id, "Cut list", row, 6, 999.0)


def test_the_verifier_notices_a_wrong_wire_end_a_wrong_pin_and_a_wrong_count(built: dict[str, bytes], project: Project, harness_id: str) -> None:  # fmt: skip
    assert "out_build" in _tampered(built, project, harness_id, "Cut list", 2, 7, "X.9")
    assert "out_build" in _tampered(built, project, harness_id, "Connectors", 3, 4, "W999-001")
    assert "out_build" in _tampered(built, project, harness_id, "Start here", 7, 2, 99)


def test_the_verifier_notices_a_result_written_before_any_test(built: dict[str, bytes], project: Project, harness_id: str) -> None:  # fmt: skip
    assert "out_build" in _tampered(built, project, harness_id, "Tests", 2, 10, "Pass")


def test_the_verifier_notices_a_missing_workbook_and_a_damaged_one(built: dict[str, bytes], project: Project, harness_id: str) -> None:  # fmt: skip
    files = dict(built)
    rel = f"harnesses/{harness_id}/{harness_id}_build.xlsx"
    del files[rel]
    assert "out_missing" in _codes(project, files)
    files[rel] = b"not a workbook"
    assert "out_unreadable" in _codes(project, files)


def test_the_verifier_notices_a_workbook_of_another_design(built: dict[str, bytes], project: Project, harness_id: str) -> None:  # fmt: skip
    files = dict(built)
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("About")
    ws.append(["Generated by", "harness-design-studio 0.0.1 model 000000000000"])
    ws.append(["Model hash", "0" * 64])
    raw = io.BytesIO()
    wb.save(raw)
    files[f"harnesses/{harness_id}/{harness_id}_build.xlsx"] = raw.getvalue()
    assert {"out_stamp", "out_build"} <= _codes(project, files)
