"""Transparency work, step 6 (D-191, D-193): the import record, the echo of what an import read,
dropped and converted, explicit units, the source-changed check, and the tool's own CSV files read
back by its importers."""

import hashlib
import json
from pathlib import Path

import pytest

from harness_design_studio import __version__
from harness_design_studio.cli.main import main as cli
from harness_design_studio.core import templates
from harness_design_studio.core.commands import History, Op
from harness_design_studio.core.import_record import (
    CHANGED,
    MISSING,
    UNCHANGED,
    UNCHECKED,
    ImportReport,
    check_sources,
    file_sha256,
    project_relative,
    record_ops,
)
from harness_design_studio.core.io import layout
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import ImportRecord, Part
from harness_design_studio.core.outputs.stamp import csv_bytes, stamp_of

RECORDS = "imports/records.json"
LENGTHS = "harness,segment,length\nW001,W001-L1,850\nW002,W002-L1,900\n"


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    """The first-steps example with its harnesses generated (so they have segments)."""
    dest = tmp_path / "design"
    templates.create_project(dest, "first-steps")
    assert cli(["generate", str(dest)]) == 0
    return dest


def run(capsys: pytest.CaptureFixture[str], *argv: object) -> tuple[int, str]:
    capsys.readouterr()
    code = cli([str(a) for a in argv])
    out = capsys.readouterr()
    return code, out.out + out.err


def records(folder: Path) -> list[dict[str, object]]:
    doc = json.loads((folder / RECORDS).read_text(encoding="utf-8"))
    return list(doc["imports"])


# ---- the record in the project -------------------------------------------------------------------


def test_a_project_that_never_imported_has_no_record_file_and_the_same_hash(proj: Path) -> None:
    assert not (proj / "imports").exists()
    p = load_project(proj).project
    assert p.import_records == {}
    before = layout.model_hash(p)
    assert RECORDS not in layout.serialize(p)
    save_project(p, proj)
    assert (
        not (proj / "imports").exists() and layout.model_hash(load_project(proj).project) == before
    )


def test_the_record_is_not_part_of_the_model_hash_and_is_carried_by_save_and_load(
    proj: Path, tmp_path: Path
) -> None:
    p = load_project(proj).project
    before = layout.model_hash(p)
    report = ImportReport("lengths", "x.csv", "a" * 64, rows_read=1)
    report.convert(row=2, field="length", read="5", unit="mm", stored="0.005 m")
    History(p).execute("Record", record_ops(p, report.record()))
    assert layout.model_hash(p) == before  # the design is the same design
    assert RECORDS in layout.serialize(p)
    save_project(p, proj)
    again = load_project(proj)
    assert not again.has_errors and again.project.import_records == p.import_records
    assert layout.model_hash(again.project) == before


def test_undo_takes_the_record_away_with_the_import(proj: Path) -> None:
    p = load_project(proj).project
    history = History(p)
    report = ImportReport("lengths", "x.csv", "b" * 64, rows_read=0)
    history.execute("Import", record_ops(p, report.record()))
    assert list(p.import_records) == ["lengths:x.csv"]
    history.undo()
    assert p.import_records == {}


def test_the_outputs_do_not_change_when_a_project_has_import_records(proj: Path) -> None:
    """The record says where data came from; it is not written into any output file, and the
    manifest (model hash, content hash, the hash of every file) is the same with or without it."""
    assert cli(["export", str(proj)]) == 0
    before = {
        str(f.relative_to(proj)): f.read_bytes()
        for f in sorted((proj / "outputs").rglob("*"))
        if f.is_file()
    }
    p = load_project(proj).project
    report = ImportReport("lengths", "lengths.csv", "d" * 64, rows_read=2)
    History(p).execute("Record", record_ops(p, report.record()))
    save_project(p, proj)
    assert (proj / RECORDS).is_file()
    assert cli(["export", str(proj)]) == 0
    after = {
        str(f.relative_to(proj)): f.read_bytes()
        for f in sorted((proj / "outputs").rglob("*"))
        if f.is_file()
    }
    assert before.keys() == after.keys()
    changed = [name for name in before if before[name] != after[name]]
    assert changed == [], changed
    assert all(
        b"records.json" not in data and b"lengths.csv" not in data for data in after.values()
    )


def test_the_schema_of_the_file_is_exported() -> None:
    from harness_design_studio.core import schemas

    docs = schemas.schemas()
    assert "import-records" in docs
    assert "imports/records.json" in docs["import-records"]["description"]


# ---- import-lengths: the echo (D8) ----------------------------------------------------------------


def test_import_lengths_echoes_every_converted_value(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (proj / "lengths.csv").write_text(LENGTHS, encoding="utf-8")
    code, out = run(capsys, "import-lengths", proj, proj / "lengths.csv", "--dry-run")
    assert code == 0
    assert "row 2: OK W001 / W001-L1: 850 mm = 0.85 m" in out
    assert "row 3: OK W002 / W002-L1: 900 mm = 0.9 m" in out
    assert "Unit: length in mm (assumed; --unit says another)." in out
    assert not (proj / "imports").exists()  # a dry run writes nothing


def test_a_bare_number_shows_the_trap_the_audit_found(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """D8: a bare 5.0 became 0.005 m with "row 2: OK" and nothing else."""
    (proj / "lengths.csv").write_text(
        "harness,segment,length\nW001,W001-L1,5.0\n", encoding="utf-8"
    )
    code, out = run(capsys, "import-lengths", proj, proj / "lengths.csv")
    assert code == 0 and "5.0 mm = 0.005 m" in out


@pytest.mark.parametrize(
    "unit,expected",
    [("mm", "0.85"), ("cm", "8.5"), ("m", "850"), ("in", "21.59"), ("ft", "259.08")],
)
def test_the_unit_option_is_echoed_as_given_and_converted(
    proj: Path, capsys: pytest.CaptureFixture[str], unit: str, expected: str
) -> None:
    (proj / "lengths.csv").write_text(
        "harness,segment,length\nW001,W001-L1,850\n", encoding="utf-8"
    )
    code, out = run(capsys, "import-lengths", proj, proj / "lengths.csv", "--unit", unit)
    assert code == 0
    assert f"850 {unit} = {expected} m" in out
    assert f"Unit: length in {unit} (given with --unit)." in out
    rec = records(proj)[0]
    assert rec["unit"] == unit and rec["unit_given"] is True


def test_dropped_rows_and_unread_columns_are_named(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (proj / "lengths.csv").write_text(
        "harness,segment,length,remark\nW001,W001-L1,850,from CAD\nW009,W001-L1,5,x\n",
        encoding="utf-8",
    )
    code, out = run(capsys, "import-lengths", proj, proj / "lengths.csv")
    assert code == 1  # as before: one bad row stops the import
    assert "row 3: ERROR Harness 'W009' does not exist" in out
    assert "warning: the column 'remark' is not read; its values are not imported." in out
    assert not (proj / "imports").exists()


def test_the_default_unit_and_the_stored_lengths_are_what_they_were(proj: Path) -> None:
    (proj / "lengths.csv").write_text(LENGTHS, encoding="utf-8")
    assert cli(["import-lengths", str(proj), str(proj / "lengths.csv")]) == 0
    p = load_project(proj).project
    lengths = {s.id: s.length_m for h in p.harnesses.values() for s in h.segments}
    assert lengths["W001-L1"] == 0.85 and lengths["W002-L1"] == 0.9


# ---- what the record holds ------------------------------------------------------------------------


def test_the_record_format_holds_what_the_brief_lists_and_nothing_else(proj: Path) -> None:
    (proj / "data").mkdir()
    (proj / "data" / "lengths.csv").write_text(LENGTHS + ",,\n", encoding="utf-8")
    assert (
        cli(["import-lengths", str(proj), str(proj / "data" / "lengths.csv"), "--unit", "mm"]) == 0
    )
    (rec,) = records(proj)
    # the bytes on disk (Windows writes the text with CRLF), not the text in the source
    digest = hashlib.sha256((proj / "data" / "lengths.csv").read_bytes()).hexdigest()
    assert rec == {
        "columns_read": [
            {"column": "harness", "field": "harness"},
            {"column": "segment", "field": "segment"},
            {"column": "length", "field": "length"},
        ],
        "converted_count": 2,
        "dropped_count": 0,
        "id": "lengths:lengths.csv",
        "kind": "lengths",
        "rows_converted": [
            {
                "field": "length",
                "item": "W001 / W001-L1",
                "read": "850",
                "row": 2,
                "stored": "0.85 m",
                "unit": "mm",
            },
            {
                "field": "length",
                "item": "W002 / W002-L1",
                "read": "900",
                "row": 3,
                "stored": "0.9 m",
                "unit": "mm",
            },
        ],
        "rows_read": 2,
        "sha256": digest,
        "source_name": "lengths.csv",
        "source_path": "data/lengths.csv",
        "tool_version": __version__,
        "unit": "mm",
        "unit_given": True,
    }


def test_no_time_no_operator_no_absolute_path_in_the_record(proj: Path, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    (outside / "lengths.csv").write_text(LENGTHS, encoding="utf-8")
    assert cli(["import-lengths", str(proj), str(outside / "lengths.csv")]) == 0
    text = (proj / RECORDS).read_text(encoding="utf-8")
    assert str(tmp_path) not in text and "elsewhere" not in text
    (rec,) = records(proj)
    assert "source_path" not in rec  # outside the project folder: the name only
    for key in rec:
        assert not any(
            w in key for w in ("time", "date", "when", "operator", "user", "author", "host")
        )
    # nothing in the project data was read from a clock or the environment: a second project with
    # the same import has the same record bytes
    other = tmp_path / "other"
    templates.create_project(other, "first-steps")
    assert cli(["generate", str(other)]) == 0
    assert cli(["import-lengths", str(other), str(outside / "lengths.csv")]) == 0
    assert (other / RECORDS).read_bytes() == (proj / RECORDS).read_bytes()


def test_the_path_is_kept_only_inside_the_project_folder(tmp_path: Path) -> None:
    root = tmp_path / "p"
    (root / "a").mkdir(parents=True)
    f = root / "a" / "x.csv"
    f.write_text("x")
    assert project_relative(f, root) == "a/x.csv"
    assert project_relative(tmp_path / "y.csv", root) is None
    assert project_relative(root / ".." / "y.csv", root) is None
    assert project_relative(f, None) is None


def test_importing_the_same_source_again_replaces_its_record(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = proj / "lengths.csv"
    f.write_text(LENGTHS, encoding="utf-8")
    assert cli(["import-lengths", str(proj), str(f)]) == 0
    first = (proj / RECORDS).read_bytes()
    code, out = run(capsys, "import-lengths", proj, f)  # the same file: nothing changes
    assert code == 0 and (proj / RECORDS).read_bytes() == first and "Import record" not in out
    f.write_text(LENGTHS.replace("850", "860"), encoding="utf-8")
    code, out = run(capsys, "import-lengths", proj, f)
    assert code == 0 and "Import record: lengths:lengths.csv written" in out
    (rec,) = records(proj)  # one record, the new one
    assert rec["sha256"] == hashlib.sha256(f.read_bytes()).hexdigest()
    assert rec["rows_converted"][0]["read"] == "860"  # type: ignore[index]


def test_two_kinds_from_one_file_name_are_two_records(proj: Path) -> None:
    (proj / "data.csv").write_text(LENGTHS, encoding="utf-8")
    assert cli(["import-lengths", str(proj), str(proj / "data.csv")]) == 0
    (proj / "data.csv").write_text(
        "Wire,Strip A (mm),Strip B (mm)\nW001-001,6,6\n", encoding="utf-8"
    )
    assert cli(["import-build-data", str(proj), str(proj / "data.csv")]) == 0
    assert sorted(r["id"] for r in records(proj)) == ["lengths:data.csv", "strip-lengths:data.csv"]  # type: ignore[type-var]


# ---- has the source changed? ----------------------------------------------------------------------


def test_the_check_names_a_changed_source_and_exits_1(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = proj / "lengths.csv"
    f.write_text(LENGTHS, encoding="utf-8")
    assert cli(["import-lengths", str(proj), str(f)]) == 0
    code, out = run(capsys, "imports", proj, "--check")
    assert code == 0 and "unchanged" in out and "source changed" not in out
    f.write_text(LENGTHS.replace("900", "905"), encoding="utf-8")
    code, out = run(capsys, "imports", proj, "--check")
    assert code == 1 and "source changed" in out and "lengths:lengths.csv" in out
    code, out = run(capsys, "imports", proj)  # without --check it only reports
    assert code == 0 and "source changed" in out
    f.unlink()
    code, out = run(capsys, "imports", proj, "--check")
    assert code == 0 and "source not found" in out


def test_a_source_outside_the_project_is_checked_when_the_person_gives_the_path(
    proj: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    outside = tmp_path / "cad" / "lengths.csv"
    outside.parent.mkdir()
    outside.write_text(LENGTHS, encoding="utf-8")
    assert cli(["import-lengths", str(proj), str(outside)]) == 0
    code, out = run(capsys, "imports", proj, "--check")
    assert code == 0 and "not checked (no path)" in out
    code, out = run(capsys, "imports", proj, "--check", "--source", outside)
    assert code == 0 and "unchanged" in out
    outside.write_text(LENGTHS + "W001,W001-L1,1\n", encoding="utf-8")
    code, out = run(capsys, "imports", proj, "--check", "--source", outside)
    assert code == 1 and "source changed" in out


def test_the_json_output_is_deterministic_and_has_no_path(
    proj: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = proj / "lengths.csv"
    f.write_text(LENGTHS, encoding="utf-8")
    assert cli(["import-lengths", str(proj), str(f)]) == 0
    code, a = run(capsys, "imports", proj, "--json")
    _, b = run(capsys, "imports", proj, "--json")
    assert code == 0 and a == b and str(tmp_path) not in a
    doc = json.loads(a)
    assert doc["sources_changed"] == 0 and doc["count"] == 1 and doc["records_file"] == RECORDS
    assert doc["imports"][0]["status"] == UNCHANGED
    assert doc["imports"][0]["current_sha256"] == file_sha256(f)
    f.write_text("harness,segment,length\n", encoding="utf-8")
    code, a = run(capsys, "imports", proj, "--json", "--check")
    assert code == 1 and json.loads(a)["imports"][0]["status"] == CHANGED


def test_every_import_json_document_carries_what_the_text_reports(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = proj / "lengths.csv"
    f.write_text(LENGTHS, encoding="utf-8")
    code, text = run(capsys, "import-lengths", proj, str(f), "--dry-run", "--unit", "in")
    code_j, out = run(capsys, "import-lengths", proj, str(f), "--dry-run", "--unit", "in", "--json")
    assert code == code_j == 0
    doc = json.loads(out)
    assert list(doc)[-1] == "import" and str(proj) not in out
    imp = doc["import"]
    assert imp["unit"] == "in" and imp["unit_given"] is True and imp["record_written"] is False
    assert imp["rows_read"] == imp["converted_count"] and imp["columns_read"]
    assert f"Read {imp['rows_read']} row(s)" in text
    _, out = run(capsys, "import-lengths", proj, str(f), "--json")
    assert json.loads(out)["import"]["record_written"] is True
    assert json.loads(out)["import"]["id"] == "lengths:lengths.csv"


def test_no_records_is_said_and_is_fine(proj: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code, out = run(capsys, "imports", proj, "--check")
    assert code == 0 and "No imports are recorded" in out


def test_check_sources_statuses_and_the_confinement_to_the_project_folder(proj: Path) -> None:
    p = load_project(proj).project
    good = ImportReport("lengths", "a.csv", "0" * 64, rows_read=0, source_path="a.csv")
    away = ImportReport("lengths", "b.csv", "0" * 64, rows_read=0, source_path="../outside.csv")
    none = ImportReport("lengths", "c.csv", "0" * 64, rows_read=0)
    for r in (good, away, none):
        History(p).execute("r", record_ops(p, r.record()))
    (proj / "a.csv").write_text("x")
    (proj.parent / "outside.csv").write_text("x")
    status = {c.record.source_name: c.status for c in check_sources(p, proj)}
    # a hand-edited path that leaves the folder is not followed
    assert status == {"a.csv": CHANGED, "b.csv": UNCHECKED, "c.csv": UNCHECKED}
    (proj / "a.csv").unlink()
    assert check_sources(p, proj)[0].status == MISSING


# ---- the other importers: units, ratings, honesty ---------------------------------------------------

PARTS = (
    "part number,category,description,approval status,mass,Contact current (A),rated_voltage_v,Notes\n"
    "ZZ-CON-1,connector,Test connector,Approved,0.25,3.0,250,keep\n"
    "ZZ-WIRE-1,wire,Test wire,Approved,12,,,\n"
)


def import_parts(capsys: pytest.CaptureFixture[str], proj: Path, name: str, text: str, *extra: str):  # type: ignore[no-untyped-def]
    f = proj / name
    f.write_text(text, encoding="utf-8")
    return run(capsys, "import-parts", proj, f, "--approved", "Approved", *extra)


def test_the_parts_import_reads_ratings_and_names_the_columns_it_leaves_out(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = import_parts(capsys, proj, "parts.csv", PARTS)
    assert code == 0
    part = load_project(proj).project.parts["ZZ-CON-1"]
    assert part.ratings == {"contact_current_a": 3.0, "rated_voltage_v": 250.0}
    assert (
        "ratings.contact_current_a" in out
        and "Contact current (A) -> ratings.contact_current_a" in out
    )
    assert "warning: the column 'Notes' is not read" in out
    assert "Unit: mass in g (assumed; --mass-unit says another)." in out
    (rec,) = records(proj)
    assert rec["columns_ignored"] == ["Notes"] and rec["unit"] == "g" and "unit_given" not in rec


def test_a_rating_that_is_not_a_number_refuses_the_row(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = PARTS.replace("3.0", "lots")
    code, out = import_parts(capsys, proj, "parts.csv", text)
    assert code == 1 and "contact_current_a 'lots' is not a plain number" in out


def test_a_parts_file_without_the_new_columns_gives_the_same_parts_as_before(proj: Path) -> None:
    from harness_design_studio.core.library_import import guess_mapping, plan_parts_import

    table = [
        ["part number", "category", "description", "approval status", "mass"],
        ["ZZ-CON-1", "connector", "Test connector", "Approved", "0.25"],
    ]
    p = load_project(proj).project
    plan = plan_parts_import(p, table, guess_mapping(table[0]), approved=["Approved"])
    (op,) = plan.ops
    part = op.obj  # type: ignore[union-attr]
    assert isinstance(part, Part) and part.ratings == {} and part.mass_g == 0.25


def test_the_mass_unit_converts_and_is_echoed(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code, out = import_parts(capsys, proj, "parts.csv", PARTS, "--mass-unit", "kg")
    assert code == 0
    assert load_project(proj).project.parts["ZZ-CON-1"].mass_g == 250.0
    assert "Converted, row 2 (ZZ-CON-1): 0.25 kg = 250 g" in out
    assert "Unit: mass in kg (given with --mass-unit)." in out
    (rec,) = records(proj)
    assert rec["unit"] == "kg" and rec["unit_given"] is True and rec["converted_count"] == 2


def test_the_build_data_import_converts_a_unit_and_lists_a_decimal_comma(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = proj / "strips.csv"
    f.write_text(
        'Wire,Strip A (mm),Strip B (mm),Comment\nW001-001,"1,5",0.25,hand\n', encoding="utf-8"
    )
    code, out = run(capsys, "import-build-data", proj, f)
    assert code == 0
    assert "Converted, row 2: 1,5 mm = 1.5 mm" in out
    assert "warning: the column 'Comment' is not read" in out
    code, out = run(capsys, "import-build-data", proj, f, "--unit", "in", "--dry-run")
    assert code == 0
    assert "0.25 in = 6.35 mm" in out
    assert "The heading 'Strip A (mm)' says mm but the lengths are read in in." in out


def test_build_data_without_a_unit_option_reads_millimetres_as_before(proj: Path) -> None:
    f = proj / "strips.csv"
    f.write_text("Wire,Strip A (mm),Strip B (mm)\nW001-001,6,5\n", encoding="utf-8")
    assert cli(["import-build-data", str(proj), str(f)]) == 0
    wire = next(
        w
        for h in load_project(proj).project.harnesses.values()
        for w in h.wires
        if w.id == "W001-001"
    )
    assert (wire.strip_a_mm, wire.strip_b_mm) == (6.0, 5.0)


# ---- KiCad: the pin type and the design source are kept ---------------------------------------------

NETLIST = """(export (version "E")
  (design (source "/home/someone/proj/wheel.kicad_sch") (date "x"))
  (components
    (comp (ref "J1") (value "Conn_01x03") (footprint "Connector:Foo")
      (fields (field (name "HarnessConnector") "OBC1-J77") (field (name "HarnessPart") "EX-MICROD-9-F"))))
  (nets
    (net (code "1") (name "/power/28V") (node (ref "J1") (pin "1") (pintype "power_in")))
    (net (code "2") (name "TXD") (node (ref "J1") (pin "2") (pintype "output")))
    (net (code "3") (name "RXD") (node (ref "J1") (pin "3") (pintype "input")))))
"""


def netlist_project(tmp_path: Path) -> tuple[Path, Path]:
    dest = tmp_path / "net"
    templates.create_project(dest, "first-steps")
    (dest / "wheel.net").write_text(NETLIST, encoding="utf-8")
    return dest, dest / "wheel.net"


def test_the_netlist_record_keeps_pin_types_and_the_design_source_name(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest, net = netlist_project(tmp_path)
    code, out = run(capsys, "import-netlist", dest, net, "--device", "OBC1")
    assert code == 0, out
    (rec,) = records(dest)
    assert rec["pin_types"] == {
        "OBC1-J77.1": "power_in",
        "OBC1-J77.2": "output",
        "OBC1-J77.3": "input",
    }
    assert rec["notes"] == ["KiCad design source: wheel.kicad_sch"]  # the name only, no folder
    assert rec["columns_ignored"] == ["value", "footprint"]
    assert "/home/someone" not in (dest / RECORDS).read_text(encoding="utf-8")
    pins = {p.id: p for p in load_project(dest).project.connectors["OBC1-J77"].pins}
    assert pins["2"].direction == ""  # without the option nothing is set from a pin type


def test_the_pin_direction_option_fills_only_pins_that_have_none(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dest, net = netlist_project(tmp_path)
    code, out = run(capsys, "import-netlist", dest, net, "--device", "OBC1", "--pin-direction")
    assert code == 0, out
    pins = {p.id: p.direction for p in load_project(dest).project.connectors["OBC1-J77"].pins}
    # power_in names no direction: not guessed; the spare pins the part has stay as they are
    assert [pins[n] for n in "123"] == ["", "out", "in"] and set(pins[n] for n in "456789") == {""}


# ---- the tool's own CSV files can be read back --------------------------------------------------------


def test_the_bill_of_materials_the_tool_exports_is_read_back_by_the_parts_import(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli(["export", str(proj)]) == 0
    bom = proj / "outputs" / "system" / "bom.csv"
    assert bom.read_text(encoding="utf-8").startswith("# harness-design-studio ")
    code, out = run(
        capsys,
        "import-parts",
        proj,
        bom,
        "--approved",
        "approved",
        "--pending",
        "pending (example data)",
    )
    assert code == 0, out
    assert "Columns read: Part -> id" in out
    assert "warning: the column 'Quantity' is not read" in out


def test_a_lengths_file_with_the_stamp_line_is_read(proj: Path) -> None:
    table = [
        ["harness", "segment", "length"],
        ["W001", "W001-L1", "850"],
        ["W002", "W002-L1", "900"],
    ]
    (proj / "stamped.csv").write_bytes(csv_bytes(table, stamp_of(load_project(proj).project)))
    assert (proj / "stamped.csv").read_text(encoding="utf-8").startswith("# harness-design-studio")
    assert cli(["import-lengths", str(proj), str(proj / "stamped.csv")]) == 0


def test_a_build_data_file_with_the_stamp_line_is_read(proj: Path) -> None:
    table = [["Wire", "Strip A (mm)", "Strip B (mm)"], ["W001-001", "6", "5"]]
    (proj / "stamped.csv").write_bytes(csv_bytes(table, stamp_of(load_project(proj).project)))
    assert cli(["import-build-data", str(proj), str(proj / "stamped.csv")]) == 0


def test_a_text_the_tool_marked_for_spreadsheets_is_given_back_on_import(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`+28V` leaves the tool as `'+28V` (a spreadsheet would run it as a formula); the import of
    the tool's own file takes the apostrophe away again."""
    p = load_project(proj).project
    table = [["Connector", "Pin", "Signal"], ["OBC1-J01", "1", "+28V"], ["OBC1-J01", "2", "-5V"]]
    f = proj / "pins.csv"
    f.write_bytes(csv_bytes(table, stamp_of(p)))
    assert b"'+28V" in f.read_bytes()
    from harness_design_studio.core.imports import read_table

    assert read_table(f) == table
    from harness_design_studio.core.pinout_import import read_pinout_table

    assert read_pinout_table(f)[0] == table
    plain = proj / "plain.csv"  # a file the tool did not write is read exactly as it is
    plain.write_text("a,b\n'+28V,x\n", encoding="utf-8")
    assert read_table(plain) == [["a", "b"], ["'+28V", "x"]]


def test_export_pinout_then_import_pinout_round_trips(
    proj: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = proj / "obc.csv"
    assert cli(["export-pinout", str(proj), "--device", "OBC1", "-o", str(f)]) == 0
    assert cli(["import-pinout", str(proj), str(f), "--device", "OBC1"]) == 0
    code, out = run(capsys, "import-pinout", proj, f, "--device", "OBC1")
    assert code == 0 and "Already up to date." in out
    assert records(proj)[0]["kind"] == "pinout"


def test_the_ampacity_table_and_the_device_files_are_recorded(
    proj: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    amp = proj / "amp.csv"
    amp.write_text("gauge,amperes\n20,5\n22,3\n24,2\n", encoding="utf-8")
    code, out = run(capsys, "config", proj, "--ampacity-csv", amp)
    assert code in (0, 1) and "Read 3 row(s) of ampacity table from amp.csv" in out
    lib = tmp_path / "devices.json"
    assert cli(["export-devices", str(proj), str(lib), "--device", "OBC1"]) == 0
    code, out = run(capsys, "import-devices", proj, lib)
    assert code == 0 and "Read 1 device(s) of device library from devices.json" in out
    kinds = sorted(r["kind"] for r in records(proj))  # type: ignore[type-var]
    assert kinds == ["ampacity", "devices"]


def test_every_record_is_a_valid_entity_whatever_the_file_is_called(
    proj: Path, tmp_path: Path
) -> None:
    odd = tmp_path / ("x" * 190 + ".csv")
    odd.write_text(LENGTHS, encoding="utf-8")
    assert cli(["import-lengths", str(proj), str(odd)]) == 0
    p = load_project(proj)
    assert not p.has_errors and len(p.project.import_records) == 1
    rec = next(iter(p.project.import_records.values()))
    assert isinstance(rec, ImportRecord) and len(rec.id) <= 200


def test_op_type_is_a_put_of_the_collection() -> None:
    from harness_design_studio.core.model import Project

    ops: list[Op] = record_ops(
        Project(), ImportReport("parts", "p.csv", "c" * 64, rows_read=1).record()
    )
    assert len(ops) == 1
