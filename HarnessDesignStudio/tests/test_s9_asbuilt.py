# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,attr-defined"
"""S9 (R6): as-built capture. The sheet a technician fills in and its round trip, the comparison
with the test limits and the design with numbers worked out by hand, what is missing, the import
that echoes and refuses, the file that stays out of the model hash and holds no time, user or path,
the journal entries, the derivation, the commands and the scripting interface."""

import csv
import io
import json
from pathlib import Path

import pytest

from harness_design_studio import api
from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import main
from harness_design_studio.core import asbuilt, derive_asbuilt, journal, templates
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.derive import explain_object
from harness_design_studio.core.imports import ImportError_
from harness_design_studio.core.io import layout
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import AsBuiltRecord, Project
from harness_design_studio.core.model.asbuilt import record_id
from harness_design_studio.core.schemas import schemas
from harness_design_studio.core.vcs.hashing import content_hash


@pytest.fixture(scope="module")
def flat(tmp_path_factory) -> Project:
    return templates.create_project(tmp_path_factory.mktemp("s9") / "flat", "flatsat")


@pytest.fixture
def folder(tmp_path: Path) -> Path:
    templates.create_project(tmp_path / "p", "flatsat")
    return tmp_path / "p"


def sheet(project: Project, harness: str | None = "W001", fill: dict | None = None):
    """The sheet with cells filled in: `fill` maps (kind, item) to {heading: value}."""
    rows = asbuilt.template_rows(project, harness)
    head = rows[0]
    for r in rows[1:]:
        for heading, value in (fill or {}).get((r[0], r[2]), {}).items():
            r[head.index(heading)] = value
    return rows


def record(project: Project, fill: dict[tuple[str, str], dict[str, str]], harness="W001"):
    plan = asbuilt.plan_asbuilt_import(project, sheet(project, harness, fill=fill))
    assert plan.bad_count == 0, [r.message for r in plan.rows if not r.ok]
    apply_ops(project, plan.ops)
    return plan


def line(project: Project, kind: str, subject: str, field: str) -> asbuilt.Line:
    return next(
        ln
        for ln in asbuilt.asbuilt_report(project).lines
        if (ln.kind, ln.subject, ln.field) == (kind, subject, field)
    )


# ---- the data: no clock, no user, no path, not in the hash --------------------------------------


def test_a_record_leaves_out_what_is_empty_and_holds_no_time_user_or_path(folder: Path) -> None:
    project = load_project(folder).project
    before = layout.model_hash(project)
    record(project, {("wire", "W001-001"): {"Cut length (m)": "3.46"}})
    save_project(project, folder)
    text = (folder / "asbuilt" / "records.json").read_text(encoding="utf-8")
    data = json.loads(text)["asbuilt"]
    assert data == [{"cut_length_m": 3.46, "harness_id": "W001", "id": "wire:W001:W001-001",
                     "kind": "wire", "subject": "W001-001"}]  # fmt: skip
    assert str(folder) not in text and "T1" not in text and 'Z"' not in text
    assert layout.model_hash(project) == before  # not part of the model hash
    assert content_hash(load_project(folder).project) == content_hash(templates.create_project(folder.parent / "q", "flatsat"))  # fmt: skip


def test_a_project_without_records_has_no_file_and_the_same_bytes(tmp_path: Path) -> None:
    a = templates.create_project(tmp_path / "a", "flatsat")
    save_project(a, tmp_path / "a")
    assert not (tmp_path / "a" / "asbuilt").exists()
    again = load_project(tmp_path / "a").project
    assert again.asbuilt == {} and layout.serialize(again).keys() == layout.serialize(a).keys()
    assert "asbuilt/records.json" not in layout.serialize(a)


def test_the_file_is_in_the_schema_export_and_a_bad_record_is_set_aside(folder: Path) -> None:
    assert "asbuilt" in schemas()
    (folder / "asbuilt").mkdir()
    (folder / "asbuilt" / "records.json").write_text(
        json.dumps({"asbuilt": [{"id": "x", "kind": "wire", "harness_id": "W001", "subject": "a", "cut_length_m": -1}]})
    )  # fmt: skip
    result = load_project(folder)
    assert result.project.asbuilt == {} and result.project.quarantine


# ---- the sheet and its round trip ---------------------------------------------------------------


def test_the_sheet_has_a_row_for_each_thing_with_the_designed_values_and_empty_asbuilt_columns(flat: Project) -> None:  # fmt: skip
    rows = asbuilt.template_rows(flat, "W001")
    head = rows[0]
    h = flat.harnesses["W001"]
    kinds = [r[0] for r in rows[1:]]
    assert kinds.count("harness") == 1 and kinds.count("wire") == len(h.wires)
    assert kinds.count("connector") == len(h.connectors)
    assert kinds.count("test") == len(asbuilt._tests(flat, h))  # noqa: SLF001
    w1 = next(r for r in rows if r[:3] == ["wire", "W001", "W001-001"])
    assert w1[head.index("Designed length (m)")] == "3.45"  # the designed value of the example
    assert all(w1[head.index(c)] == "" for c in ("Cut length (m)", "Strip A (mm)", "Serial number"))
    t1 = next(r for r in rows if r[:3] == ["test", "W001", "T001"])
    assert t1[head.index("Limit")] == "1 ohm max"
    assert t1[head.index("Test type")] == "continuity" and t1[head.index("Tested")] == "W001-001"
    t19 = next(r for r in rows if r[:3] == ["test", "W001", "T019"])
    assert t19[head.index("Limit")] == "100 Mohm min at 500 V"
    with pytest.raises(ImportError_):
        asbuilt.template_rows(flat, "NOPE")


def test_the_sheet_as_handed_out_imports_to_nothing(flat: Project) -> None:
    plan = asbuilt.plan_asbuilt_import(flat, asbuilt.template_rows(flat))
    assert plan.ops == [] and plan.rows == [] and plan.skipped == len(asbuilt.template_rows(flat)) - 1  # fmt: skip


def test_fill_in_import_and_export_again_is_a_round_trip(flat: Project) -> None:
    project = load_project_copy(flat)
    fill = {
        ("harness", "W001"): {
            "Serial number": "SN-1; SN-2",
            "Built by": "A. Tech",
            "Inspected by": "B. Insp",
            "Notes": "first article",
        },  # fmt: skip
        ("part", "EX-WIRE-SINGLE"): {"Lot": "LOT-7"},
        ("wire", "W001-001"): {
            "Cut length (m)": "3.45",
            "Strip A (mm)": "6",
            "Strip B (mm)": "6.5",
        },
        ("test", "T001"): {"Result": "pass", "Continuity (ohm)": "0.4"},
        ("test", "T019"): {
            "Result": "pass",
            "Isolation (Mohm)": "250",
            "Test voltage (V)": "500",
            "Non-conformance": "none",
        },  # fmt: skip
    }
    plan = record(project, fill)
    assert plan.counts() == {"added": 5, "changed": 0, "unchanged": 0, "refused": 0, "skipped": len(asbuilt.template_rows(project, "W001")) - 6}  # fmt: skip
    h = project.asbuilt[record_id("harness", "W001", "W001")]
    assert h.serial_numbers == ["SN-1", "SN-2"] and h.built_by == "A. Tech" and h.notes == "first article"  # fmt: skip
    # the sheet written again holds what is recorded, and reading it back changes nothing
    again = asbuilt.template_rows(project, "W001")
    head = again[0]
    row = next(r for r in again if r[:3] == ["wire", "W001", "W001-001"])
    assert row[head.index("Strip B (mm)")] == "6.5" and row[head.index("Cut length (m)")] == "3.45"
    second = asbuilt.plan_asbuilt_import(project, again)
    assert second.ops == [] and second.counts()["unchanged"] == 5 and second.counts()["added"] == 0  # fmt: skip


def load_project_copy(project: Project) -> Project:
    from harness_design_studio.core import edit

    return edit.clone_with(project, [])


def test_an_empty_cell_never_clears_and_a_new_value_replaces(flat: Project) -> None:
    project = load_project_copy(flat)
    record(project, {("wire", "W001-001"): {"Cut length (m)": "3.45", "Strip A (mm)": "6"}})
    plan = asbuilt.plan_asbuilt_import(project, sheet(project, fill={("wire", "W001-001"): {"Cut length (m)": "3.5"}}))  # fmt: skip
    assert plan.counts()["changed"] == 1
    apply_ops(project, plan.ops)
    rec = project.asbuilt[record_id("wire", "W001", "W001-001")]
    assert (
        rec.cut_length_m == 3.5 and rec.strip_a_mm == 6.0
    )  # the empty Strip A cell did not clear it


# ---- the comparison, by hand --------------------------------------------------------------------


def test_a_continuity_value_is_compared_with_the_limit_of_one_ohm(flat: Project) -> None:
    project = load_project_copy(flat)
    record(project, {("test", "T001"): {"Result": "pass", "Continuity (ohm)": "0.4"},
                     ("test", "T002"): {"Result": "pass", "Continuity (ohm)": "1.4"},
                     ("test", "T003"): {"Result": "pass", "Continuity (ohm)": "1"}})  # fmt: skip
    within = line(project, "test", "T001", "continuity resistance (ohm)")
    assert (within.status, within.actual, within.designed, within.margin) == (asbuilt.WITHIN, 0.4, 1.0, 0.6)  # fmt: skip
    out = line(project, "test", "T002", "continuity resistance (ohm)")
    assert (out.status, out.margin) == (asbuilt.OUT, -0.4)
    assert "recorded as passed: the tool does not accept it" in out.text  # never auto-accepted
    edge = line(project, "test", "T003", "continuity resistance (ohm)")
    assert edge.status == asbuilt.WITHIN and edge.margin == 0.0  # a margin of exactly 0 is within


def test_an_insulation_value_is_compared_with_the_limit_of_100_megohm_at_500_volt(flat: Project) -> None:  # fmt: skip
    project = load_project_copy(flat)
    record(project, {("test", "T019"): {"Result": "pass", "Isolation (Mohm)": "250", "Test voltage (V)": "500"},  # fmt: skip
                     ("test", "T020"): {"Result": "fail", "Isolation (Mohm)": "50", "Test voltage (V)": "250"}})  # fmt: skip
    good = line(project, "test", "T019", "insulation resistance (Mohm)")
    assert (good.status, good.margin) == (asbuilt.WITHIN, 150.0)
    assert line(project, "test", "T019", "test voltage (V)").status == asbuilt.AS_DESIGNED
    bad = line(project, "test", "T020", "insulation resistance (Mohm)")
    assert (bad.status, bad.margin) == (asbuilt.OUT, -50.0)
    volts = line(project, "test", "T020", "test voltage (V)")
    assert volts.status == asbuilt.DIFFERS and volts.margin == -250.0


def test_a_result_of_fail_is_out_of_limit_even_when_the_number_is_inside(flat: Project) -> None:
    project = load_project_copy(flat)
    record(project, {("test", "T001"): {"Result": "fail", "Continuity (ohm)": "0.2"}})
    rep = asbuilt.asbuilt_report(project)
    outs = [ln for ln in rep.lines if ln.status == asbuilt.OUT]
    assert [(ln.subject, ln.field) for ln in outs] == [("T001", "result")]


def test_cut_and_strip_lengths_are_compared_with_the_design_and_no_tolerance_is_applied(flat: Project) -> None:  # fmt: skip
    project = load_project_copy(flat)
    h = project.harnesses["W001"]
    designed = next(w for w in h.wires if w.id == "W001-001")
    assert designed.strip_a_mm is None  # the flatsat has no strip lengths: nothing to compare with
    record(project, {("wire", "W001-001"): {"Cut length (m)": "3.46", "Strip A (mm)": "6"},
                     ("wire", "W001-002"): {"Cut length (m)": "3.45"}})  # fmt: skip
    cut = line(project, "wire", "W001-001", "cut length (m)")
    assert cut.status == asbuilt.DIFFERS and cut.margin == 0.01 and "+10 mm" in cut.text
    assert "no tolerance applied" in cut.text
    assert line(project, "wire", "W001-002", "cut length (m)").status == asbuilt.AS_DESIGNED
    assert line(project, "wire", "W001-001", "strip A (mm)").status == asbuilt.RECORDED
    assert line(project, "wire", "W001-003", "cut length (m)").status == asbuilt.MISSING


def test_a_missing_limit_is_not_compared_and_nothing_is_made_up(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "w", "first-steps")  # no test limit set
    if not project.harnesses:
        from harness_design_studio.core.generate.engine import generate_project

        generate_project(project)
    hid = sorted(project.harnesses)[0]
    record(project, {("test", "T001"): {"Result": "pass", "Continuity (ohm)": "0.4"}}, hid)
    ln = line(project, "test", "T001", "continuity resistance (ohm)")
    assert ln.status == asbuilt.NOT_COMPARED and ln.margin is None and "is not set" in ln.text
    d = derive_asbuilt.result_derivation(project, project.harnesses[hid], "T001")
    assert d.check is None and d.missing and "generation.test_continuity_max_ohm" in d.missing[0]


def test_what_is_missing_is_what_the_sheet_asks_of_a_started_harness(flat: Project) -> None:
    project = load_project_copy(flat)
    rep = asbuilt.asbuilt_report(project)
    assert not rep.has_records and rep.lines == () and not rep.complete  # nothing recorded
    record(project, {("harness", "W001"): {"Serial number": "SN-1"}})
    rep = asbuilt.asbuilt_report(project)
    h = project.harnesses["W001"]
    rows = asbuilt._tests(flat, h).values()  # noqa: SLF001
    continuity = sum(r[1] == "continuity" for r in rows)
    isolation = sum(r[1] == "isolation" for r in rows)
    parts = len(asbuilt._parts_of(h))  # noqa: SLF001
    # built by and inspected by; a lot for each part; a cut length for each wire; the result and the
    # resistance of a continuity test; the result, the resistance and the voltage of an insulation test
    assert rep.missing == 2 + parts + len(h.wires) + 2 * continuity + 3 * isolation
    assert (continuity, isolation, parts, len(h.wires)) == (
        18,
        27,
        2,
        18,
    )  # hand count, flatsat W001
    states = {s.harness_id: s for s in rep.harnesses}
    assert states["W001"].started and not states["W001"].complete
    assert (
        not states["W002"].started and states["W002"].missing == 0
    )  # not started, nothing missing


def test_a_record_of_something_the_design_no_longer_has_is_stale(flat: Project) -> None:
    project = load_project_copy(flat)
    record(project, {("wire", "W001-001"): {"Cut length (m)": "3.45"},
                     ("test", "T001"): {"Result": "pass", "Continuity (ohm)": "0.4"}})  # fmt: skip
    from harness_design_studio.core.commands import Put
    from harness_design_studio.core.model import evolve

    rec = project.asbuilt[record_id("test", "W001", "T001")]
    apply_ops(project, [Put("asbuilt", evolve(rec, tested="W001-099"))])  # the test list moved
    gone = AsBuiltRecord(id="wire:W001:W001-999", kind="wire", harness_id="W001", subject="W001-999", cut_length_m=1.0)  # fmt: skip
    apply_ops(project, [Put("asbuilt", gone)])
    rep = asbuilt.asbuilt_report(project)
    stale = {(ln.kind, ln.subject) for ln in rep.lines if ln.status == asbuilt.STALE}
    assert stale == {("test", "T001"), ("wire", "W001-999")}
    assert not rep.complete


# ---- the import: echo, units, refusals ---------------------------------------------------------


def test_the_import_reads_units_from_the_headings_and_lists_each_conversion(flat: Project) -> None:
    project = load_project_copy(flat)
    table = [
        [
            "Kind",
            "Harness",
            "Item",
            "Cut length (mm)",
            "Continuity (mOhm)",
            "Isolation (Gohm)",
            "Test voltage (kV)",
        ],  # fmt: skip
        ["wire", "W001", "W001-001", "3460", "", "", ""],
        ["test", "W001", "T001", "", "400", "", ""],
        ["test", "W001", "T019", "", "", "0.25", "0,5"],
    ]
    plan = asbuilt.plan_asbuilt_import(project, table)
    assert plan.bad_count == 0
    got = {(row, key): (text, stored) for row, key, text, _unit, stored in plan.conversions}
    assert got[(2, "cut_length_m")] == ("3460", "3.46 m")
    assert got[(3, "continuity_ohm")] == ("400", "0.4 ohm")
    assert got[(4, "isolation_mohm")] == ("0.25", "250 Mohm")
    assert got[(4, "test_voltage_v")] == ("0,5", "500 V")  # a decimal comma and kV
    apply_ops(project, plan.ops)
    assert project.asbuilt[record_id("wire", "W001", "W001-001")].cut_length_m == 3.46
    assert project.asbuilt[record_id("test", "W001", "T019")].test_voltage_v == 500.0


@pytest.mark.parametrize(
    ("row", "why"),
    [
        (["wire", "W001", "W001-999", "3.4"], "is not a wire of W001"),
        (["wire", "W009", "W001-001", "3.4"], "Harness 'W009' does not exist"),
        (["tube", "W001", "W001-001", "3.4"], "is not one of harness, part, wire"),
        (["wire", "W001", "W001-001", "three"], "cut length (m): 'three' is not a number"),
        (
            ["wire", "W001", "W001-001", "-1"],
            "cut length (m): Input should be greater than or equal to 0",
        ),
        (["test", "W001", "T999", "3.4"], "has no test T999"),
        (["pin", "W001", "W001-P1.99", "3.4"], "is not a pin"),
        (["connector", "W001", "NOPE", "3.4"], "is not a connector"),
        (["part", "W001", "NOPE", "3.4"], "is not a part of a wire or connector"),
        (["harness", "W001", "W002", "3.4"], "the harness ID (W001)"),
    ],
)
def test_a_row_the_design_cannot_take_is_refused_with_its_reason_and_changes_nothing(
    flat: Project, row: list[str], why: str
) -> None:
    project = load_project_copy(flat)
    table = [
        ["Kind", "Harness", "Item", "Cut length (m)"],
        ["wire", "W001", "W001-001", "3.45"],
        row,
    ]
    plan = asbuilt.plan_asbuilt_import(project, table)
    bad = [r for r in plan.rows if not r.ok]
    assert len(bad) == 1 and why.lower() in bad[0].message.lower(), bad
    assert plan.ops == []  # the good row is not kept either


def test_a_test_row_with_another_type_or_wire_than_the_design_is_refused(flat: Project) -> None:
    table = [["Kind", "Harness", "Item", "Test type", "Result"], ["test", "W001", "T001", "isolation", "pass"]]  # fmt: skip
    plan = asbuilt.plan_asbuilt_import(flat, table)
    assert "The test list changed" in plan.rows[0].message and plan.ops == []
    table = [["Kind", "Harness", "Item", "Result"], ["test", "W001", "T001", "maybe"]]
    assert "pass or fail" in asbuilt.plan_asbuilt_import(flat, table).rows[0].message


def test_a_sheet_with_other_headings_is_not_read(flat: Project) -> None:
    with pytest.raises(ImportError_, match="kind, harness, item"):
        asbuilt.plan_asbuilt_import(flat, [["Wire", "Length"], ["W001-001", "3"]])


def test_a_serial_number_list_a_note_and_a_cell_with_control_characters(flat: Project) -> None:
    project = load_project_copy(flat)
    table = [["Kind", "Harness", "Item", "Serial number", "Notes"], ["harness", "W001", "W001", "A; B ;;C", "line\x07bell"]]  # fmt: skip
    plan = asbuilt.plan_asbuilt_import(flat, table)
    apply_ops(project, plan.ops)
    rec = project.asbuilt[record_id("harness", "W001", "W001")]
    assert rec.serial_numbers == ["A", "B", "C"] and "\x07" not in rec.notes


# ---- the journal -------------------------------------------------------------------------------


def test_a_project_with_a_journal_enters_each_record_with_who_and_when(tmp_path: Path, monkeypatch) -> None:  # fmt: skip
    monkeypatch.setattr(journal, "now", lambda: "2026-11-03T11:30:00Z")
    monkeypatch.setattr(journal, "_AUTHOR", "Ann Engineer")
    templates.create_project(tmp_path / "p", "flatsat", journal=True)
    project = load_project(tmp_path / "p").project
    record(project, {("wire", "W001-001"): {"Cut length (m)": "3.46"}})
    save_project(project, tmp_path / "p")
    entries = [e for e in load_project(tmp_path / "p").project.journal if e.kind == "asbuilt"]
    assert [(e.object, e.field, e.author, e.when) for e in entries] == [
        ("asbuilt:wire:W001:W001-001", "(recorded)", "Ann Engineer", "2026-11-03T11:30:00Z")
    ]
    assert entries[0].new["cut_length_m"] == 3.46
    project = load_project(tmp_path / "p").project  # a changed value is one entry for the field
    record(project, {("wire", "W001-001"): {"Cut length (m)": "3.5"}})
    save_project(project, tmp_path / "p")
    last = load_project(tmp_path / "p").project.journal[-1]
    assert (last.kind, last.field, last.old, last.new) == ("asbuilt", "cut_length_m", 3.46, 3.5)
    # the records themselves still hold neither a name nor a time
    text = (tmp_path / "p" / "asbuilt" / "records.json").read_text()
    assert "Ann Engineer" not in text and "2026-11-03" not in text


def test_a_big_import_is_one_entry_in_the_journal(tmp_path: Path) -> None:
    templates.create_project(tmp_path / "p", "flatsat", journal=True)
    project = load_project(tmp_path / "p").project
    fill = {("wire", w.id): {"Cut length (m)": "3.4"} for w in project.harnesses["W001"].wires}
    fill.update({("test", r[0]): {"Result": "pass"} for r in asbuilt._tests(project, project.harnesses["W001"]).values()})  # fmt: skip
    record(project, fill)
    assert len(project.asbuilt) > asbuilt_bulk()
    save_project(project, tmp_path / "p")
    entries = [e for e in load_project(tmp_path / "p").project.journal if "asbuilt" in e.object]
    assert len(entries) == 1 and entries[0].kind == "import" and "objects" in entries[0].new


def asbuilt_bulk() -> int:
    return journal.BULK


def test_the_import_is_one_undo_step_and_undo_takes_the_records_away(flat: Project) -> None:
    project = load_project_copy(flat)
    plan = asbuilt.plan_asbuilt_import(project, sheet(project, fill={("wire", "W001-001"): {"Cut length (m)": "3.4"}}))  # fmt: skip
    history = History(project)
    history.execute("Import as-built records", plan.ops)
    assert len(project.asbuilt) == 1
    history.undo()
    assert project.asbuilt == {}


# ---- the explanation ---------------------------------------------------------------------------


def test_explain_gives_the_asbuilt_result_of_a_test_and_a_cut_length(flat: Project) -> None:
    project = load_project_copy(flat)
    record(project, {("test", "T002"): {"Result": "pass", "Continuity (ohm)": "1.4"},
                     ("wire", "W001-001"): {"Cut length (m)": "3.46"}})  # fmt: skip
    found = [d for d in explain_object(project, "W001.T002") if d.id == "asbuilt-result"]
    assert len(found) == 1
    d = found[0]
    assert (d.value, d.unit) == (1.4, "ohm") and d.check is not None
    assert (d.check.actual, d.check.limit, d.check.margin, d.check.passes) == (
        1.4,
        1.0,
        -0.4,
        False,
    )
    assert "OUT OF THE LIMIT" in d.check.text and "asbuilt/records.json" in d.inputs[0].source
    wires = [d for d in explain_object(project, "W001-001") if d.id == "asbuilt-result"]
    assert [(x.value, x.unit) for x in wires] == [(0.01, "m")]
    # no derivation of this kind for a project with no record
    assert not [d for d in explain_object(flat, "W001.T002") if d.id == "asbuilt-result"]


# ---- the commands and the interface ------------------------------------------------------------

BENCH = """Kind,Harness,Item,Serial number,Lot,Cut length (m),Built by,Inspected by,Result,Continuity (ohm),Isolation (Mohm),Test voltage (V)
harness,W001,W001,SN-0042,,,A. Technician,B. Inspector,,,,
part,W001,EX-WIRE-SINGLE,,LOT-2611-A,,,,,,,
wire,W001,W001-001,,,"3,46",,,,,,
test,W001,T001,,,,,,pass,0.4,,
test,W001,T002,,,,,,pass,1.4,,
"""


def doc(capsys, *argv, rc=0):
    assert main([*map(str, argv)]) == rc, argv
    return json.loads(capsys.readouterr().out)


def test_import_asbuilt_echoes_records_the_file_and_the_journal_and_is_idempotent(
    folder: Path, tmp_path: Path, capsys
) -> None:
    bench = tmp_path / "bench.csv"
    bench.write_text(BENCH, encoding="utf-8")
    assert main(["import-asbuilt", str(folder), str(bench), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Read 5 row(s) of as-built records from bench.csv" in out
    assert "Converted, row 4: 3,46 m = 3.46 m" in out and "Dry run: nothing was changed." in out
    assert not (folder / "asbuilt").exists()  # a dry run writes nothing
    assert main(["import-asbuilt", str(folder), str(bench)]) == 0
    out = capsys.readouterr().out
    assert "5 added, 0 changed, 0 unchanged, 0 refused" in out
    assert "import record asbuilt:bench.csv written to imports/records.json" in out
    project = load_project(folder).project
    assert len(project.asbuilt) == 5 and "asbuilt:bench.csv" in project.import_records
    assert project.import_records["asbuilt:bench.csv"].converted_count == 1
    before = (folder / "asbuilt" / "records.json").read_bytes()
    assert main(["import-asbuilt", str(folder), str(bench)]) == 0
    assert "Already up to date." in capsys.readouterr().out
    assert (folder / "asbuilt" / "records.json").read_bytes() == before


def test_a_refused_row_changes_nothing_and_exits_1(folder: Path, tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("Kind,Harness,Item,Cut length (m)\nwire,W001,W001-001,3.4\nwire,W001,NOPE,3.4\n")
    assert main(["import-asbuilt", str(folder), str(bad)]) == 1
    out = capsys.readouterr().out
    assert "row 3: ERROR 'NOPE' is not a wire of W001." in out and "Nothing was changed." in out
    assert not (folder / "asbuilt").exists() and not (folder / "imports").exists()
    notsheet = tmp_path / "other.csv"
    notsheet.write_text("Wire,Length\nW001-001,3\n")
    assert main(["import-asbuilt", str(folder), str(notsheet)]) == 2


def test_asbuilt_reports_and_exits_1_for_a_value_out_of_its_limit(folder: Path, tmp_path: Path, capsys) -> None:  # fmt: skip
    assert main(["asbuilt", str(folder)]) == 0  # nothing recorded
    assert "No as-built record" in capsys.readouterr().out
    bench = tmp_path / "bench.csv"
    bench.write_text(BENCH, encoding="utf-8")
    main(["import-asbuilt", str(folder), str(bench)])
    capsys.readouterr()
    assert main(["asbuilt", str(folder)]) == 1
    out = capsys.readouterr().out
    assert "OUT OF LIMIT: W001 test T002" in out and "recorded as passed: the tool does not accept it" in out  # fmt: skip
    assert "DIFFERS FROM DESIGN: W001 wire W001-001" in out and "W002: not started" in out
    assert "passed" not in out.replace("recorded as passed", "")  # it never says a harness passed
    # a bench with nothing out of limit is exit 0, and 1 with --complete while values are missing
    good = tmp_path / "good.csv"
    good.write_text("Kind,Harness,Item,Result,Continuity (ohm)\ntest,W001,T002,pass,0.9\n")
    main(["import-asbuilt", str(folder), str(good)])
    capsys.readouterr()
    assert main(["asbuilt", str(folder)]) == 0
    capsys.readouterr()
    assert main(["asbuilt", str(folder), "--complete"]) == 1


def test_the_json_documents_have_the_keys_of_their_shapes_and_no_path_or_time(
    folder: Path, tmp_path: Path, capsys
) -> None:
    bench = tmp_path / "bench.csv"
    bench.write_text(BENCH, encoding="utf-8")
    got = doc(capsys, "import-asbuilt", folder, bench, "--dry-run", "--json")
    assert list(got) == list(SHAPES["import-asbuilt"]) and got["counts"]["added"] == 5
    assert got["import"]["kind"] == "asbuilt" and got["import"]["record_written"] is False
    doc(capsys, "import-asbuilt", folder, bench, "--json")
    rep = doc(capsys, "asbuilt", folder, "--json", rc=1)
    assert list(rep) == list(SHAPES["asbuilt"]) and rep["out_of_limit"] == 1
    assert [ln["subject"] for ln in rep["lines"] if ln["status"] == "out of limit"] == ["T002"]
    assert rep["records"] == 5
    sheet_file = tmp_path / "s.xlsx"
    got = doc(capsys, "export-asbuilt", folder, sheet_file, "--harness", "W001", "--json")
    assert list(got) == list(SHAPES["export-asbuilt"]) and got["written"] == "s.xlsx"
    got = doc(capsys, "workflow", folder, "--json")
    assert list(got) == list(SHAPES["workflow"]) and len(got["steps"]) == 9
    text = json.dumps([rep, got])
    assert str(tmp_path) not in text and "T11:" not in text


def test_the_xlsx_sheet_is_filled_in_and_read_back(folder: Path, tmp_path: Path, capsys) -> None:
    from openpyxl import load_workbook

    out = tmp_path / "s.xlsx"
    assert main(["export-asbuilt", str(folder), str(out), "--harness", "W001"]) == 0
    capsys.readouterr()
    wb = load_workbook(out)
    assert wb.sheetnames[-1] == "About" or "As-built" in wb.sheetnames
    ws = wb["As-built"]
    head = [c.value for c in ws[1]]
    for row in ws.iter_rows(min_row=2):
        if row[0].value == "test" and row[2].value == "T001":
            row[head.index("Result")].value = "pass"
            row[head.index("Continuity (ohm)")].value = 0.4  # a number cell, not text
    filled = tmp_path / "filled.xlsx"
    wb.save(filled)
    assert main(["import-asbuilt", str(folder), str(filled)]) == 0
    capsys.readouterr()
    rec = load_project(folder).project.asbuilt[record_id("test", "W001", "T001")]
    assert (rec.result, rec.continuity_ohm) == ("pass", 0.4)


def test_the_csv_sheet_is_the_same_bytes_twice_and_has_the_stamp_line(folder: Path, tmp_path: Path) -> None:  # fmt: skip
    project = load_project(folder).project
    one = asbuilt.template_bytes(project, ".csv", "W001")
    assert one == asbuilt.template_bytes(project, ".csv", "W001")
    assert one.decode().startswith("# harness-design-studio ")
    rows = list(csv.reader(io.StringIO(one.decode().split("\n", 1)[1])))
    assert rows[0] == asbuilt.TEMPLATE_HEADER
    with pytest.raises(ImportError_):
        asbuilt.template_bytes(project, ".txt")


def test_the_scripting_interface_does_what_the_commands_do(folder: Path, tmp_path: Path) -> None:
    bench = tmp_path / "bench.csv"
    bench.write_text(BENCH, encoding="utf-8")
    dry = api.import_asbuilt(folder, bench, dry_run=True)
    assert dry.changed is False and dry.counts["added"] == 5 and not (folder / "asbuilt").exists()
    done = api.import_asbuilt(folder, bench)
    assert done.changed is True and done.to_dict()["counts"]["added"] == 5
    assert any(line.startswith("Converted, row 4") for line in done.echo)
    report = api.get_asbuilt(folder)
    assert report.out_of_limit == 1 and report.to_dict()["records"] == 5
    assert api.get_asbuilt(templates.create_project(tmp_path / "q", "flatsat")).records == 0
    sheet_file = api.write_asbuilt_sheet(folder, tmp_path / "t.csv", harness="W001")
    assert sheet_file.read_bytes().startswith(b"# harness-design-studio")
    steps = api.get_workflow(folder).to_dict()["steps"]
    assert [s["key"] for s in steps][-1] == "as-built" and steps[-1]["state"] == "attention"
    bad = tmp_path / "bad.csv"
    bad.write_text("Kind,Harness,Item,Cut length (m)\nwire,W001,NOPE,3\n")
    refused = api.import_asbuilt(folder, bad)
    assert refused.changed is False and refused.counts["refused"] == 1
    with pytest.raises(ImportError_):
        api.import_asbuilt(folder, tmp_path / "missing.csv")
