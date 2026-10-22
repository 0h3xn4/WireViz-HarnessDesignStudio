"""The build data in the outputs (decision D-170): strip lengths, contact parts, tools and
accessories show in the tables only where they are used, always in the build workbook, and the
independent verifier checks each of them (one mutation test per check). A project that uses none
of them keeps its tables and files as they were (`tools.output_hashes` proves that for the
examples; the first tests here prove it for the sample)."""

import copy
import io

import pytest

from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.model import Part, Project, evolve
from harness_design_studio.core.model.physical import Accessory
from harness_design_studio.core.outputs import exports, tables
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.buildsheet import SHEETS, build_workbook, readiness
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.outputs.xlsx_env import load_workbook
from harness_design_studio.core.samples import sat15_full

H, H2 = "W001", "W002"
TOOL = "Crimp tool M22520/2 setting 6"


def _data_project() -> Project:
    """The sample with build data on W001 (W002 has none): strip lengths on two wires (one end
    only on the second), contact parts on the pins in use, a tool for one contact part, five
    accessories and a contact part on one box connector pin."""
    p = copy.deepcopy(sat15_full())
    p.parts["EX-CONTACT-20"] = Part(id="EX-CONTACT-20", category="contact", tool=TOOL)
    p.parts["EX-CONTACT-22"] = Part(id="EX-CONTACT-22", category="contact")
    p.parts["EX-BACKSHELL"] = Part(id="EX-BACKSHELL", category="backshell")
    h = p.harnesses[H]
    used = {(w.from_connector, w.from_pin) for w in h.wires}
    used |= {(w.to_connector, w.to_pin) for w in h.wires}
    contact = {"1": "EX-CONTACT-20", "2": "EX-CONTACT-22"}
    conns = [
        evolve(c, pins=[
            evolve(q, contact_part=contact[q.id]) if (c.id, q.id) in used and q.id in contact else q
            for q in c.pins
        ])
        for c in h.connectors
    ]  # fmt: skip
    wires = [
        evolve(w, strip_a_mm=6.0, strip_b_mm=7.5) if n == 0
        else evolve(w, strip_a_mm=5.0) if n == 1 else w
        for n, w in enumerate(sorted(h.wires, key=lambda x: x.id))
    ]  # fmt: skip
    first, second = sorted(c.id for c in h.connectors)[:2]
    accessories = [
        Accessory(id="A001", kind="sleeving", part_id="EX-SLEEVE", target=wires[0].id,
                  position="full length", length_mm=1000.0, quantity=2, note="black"),
        Accessory(id="A002", kind="sleeving", part_id="EX-SLEEVE", position="over the breakout", quantity=3),
        Accessory(id="A003", kind="label", target=first, position="50 mm from the P1 end"),
        Accessory(id="A004", kind="backshell", part_id="EX-BACKSHELL", target=second),
        Accessory(id="A005", kind="heat_shrink", part_id="EX-SLEEVE", length_mm=25.0, quantity=4),
    ]  # fmt: skip
    apply_ops(
        p, [Put("harnesses", evolve(h, connectors=conns, wires=wires, accessories=accessories))]
    )
    box = sorted(p.connectors.values(), key=lambda c: c.id)[0]
    pins = [evolve(box.pins[0], contact_part="EX-CONTACT-20"), *box.pins[1:]]
    apply_ops(p, [Put("connectors", evolve(box, pins=pins))])
    return p


@pytest.fixture(scope="module")
def plain() -> Project:
    return sat15_full()


@pytest.fixture(scope="module")
def plain_files(plain: Project) -> dict[str, bytes]:
    return build_outputs(plain, drawings=False).files


@pytest.fixture(scope="module")
def project() -> Project:
    return _data_project()


@pytest.fixture(scope="module")
def built(project: Project) -> dict[str, bytes]:
    return build_outputs(project, drawings=False).files


def _csv(files: dict[str, bytes], rel: str) -> list[list[str]]:
    return parse_csv(files[rel])


def _codes(project: Project, files: dict[str, bytes]) -> set[str]:
    return {i.code for i in verify_outputs(project, files).issues}


def _edited(project: Project, files: dict[str, bytes], rel: str, row: int, col: int, value: str) -> dict[str, bytes]:  # fmt: skip
    """The files with one cell of a CSV table changed."""
    table = _csv(files, rel)
    table[row][col] = value
    return {**files, rel: csv_bytes(table, stamp_of(project))}


def _sheets(data: bytes) -> dict[str, list[list[object]]]:
    wb = load_workbook(io.BytesIO(data), data_only=True)
    return {ws.title: [list(r) for r in ws.iter_rows(values_only=True)] for ws in wb.worksheets}


def _replace_cell(data: bytes, sheet: str, row: int, col: int, value: object) -> bytes:
    wb = load_workbook(io.BytesIO(data))
    wb[sheet].cell(row=row, column=col).value = value
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _row_of(data: bytes, sheet: str, first: str) -> int:
    rows = _sheets(data)[sheet]
    return next(n for n, r in enumerate(rows, start=1) if r and r[0] == first)


# ---- a project that does not use the fields keeps its tables --------------------------------------


def test_a_project_without_build_data_has_none_of_the_new_columns_or_files(plain: Project, plain_files: dict[str, bytes]) -> None:  # fmt: skip
    assert not any(k.endswith("accessories.csv") for k in plain_files)
    for rel, data in plain_files.items():
        if rel.endswith(("wirelist.csv", "pinouts.csv", "box_pinouts.csv")):
            header = parse_csv(data)[0]
            assert "Strip A (mm)" not in header and "Contact" not in header, rel
    assert "Accessories" not in _sheets(plain_files[f"harnesses/{H}/{H}.xlsx"])
    assert verify_outputs(plain, plain_files).ok


# ---- the tables ----------------------------------------------------------------------------------


def test_the_wire_list_gets_the_strip_columns_last(built: dict[str, bytes]) -> None:
    rows = _csv(built, f"harnesses/{H}/wirelist.csv")
    assert rows[0][-2:] == ["Strip A (mm)", "Strip B (mm)"] and rows[0][-3] == "Locked"
    by = {r[0]: r for r in rows[1:]}
    assert by[f"{H}-001"][-2:] == ["6", "7.5"] and by[f"{H}-002"][-2:] == ["5", ""]
    other = _csv(built, f"harnesses/{H2}/wirelist.csv")  # the columns belong to the project
    assert other[0][-2:] == ["Strip A (mm)", "Strip B (mm)"] and other[1][-2:] == ["", ""]


def test_the_strip_columns_follow_the_optional_label_and_note_columns(project: Project) -> None:
    p = copy.deepcopy(project)
    h = p.harnesses[H]
    w = sorted(h.wires, key=lambda x: x.id)[0]
    apply_ops(p, [Put("harnesses", evolve(h, wires=[evolve(w, label="PWR 1") if x.id == w.id else x for x in h.wires]))])  # fmt: skip
    header = tables.wire_list(p, p.harnesses[H])[0]
    assert header[-4:] == ["Label", "Note", "Strip A (mm)", "Strip B (mm)"]
    assert verify_outputs(p, build_outputs(p, drawings=False).files).ok


def test_the_pinout_tables_get_the_contact_column_last(built: dict[str, bytes]) -> None:
    rows = _csv(built, f"harnesses/{H}/pinouts.csv")
    assert rows[0][-1] == "Contact"
    got = {(r[0], r[4]): r[-1] for r in rows[1:]}
    assert got[(f"{H}-P1", "1")] == "EX-CONTACT-20" and got[(f"{H}-P1", "2")] == "EX-CONTACT-22"
    assert got[(f"{H}-P1", "3")] == ""
    box = _csv(built, "system/box_pinouts.csv")
    assert box[0][-1] == "Contact" and sum(1 for r in box[1:] if r[-1] == "EX-CONTACT-20") == 1


def test_a_harness_with_accessories_gets_accessories_csv_sorted_by_id(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    rows = _csv(built, f"harnesses/{H}/accessories.csv")
    assert rows[0] == ["Accessory", "Kind", "Part", "Target", "Position", "Length (mm)", "Quantity", "Note"]  # fmt: skip
    assert [r[0] for r in rows[1:]] == ["A001", "A002", "A003", "A004", "A005"]
    assert rows[1][1:] == ["sleeving", "EX-SLEEVE", f"{H}-001", "full length", "1000", "2", "black"]
    assert rows[3][3] == f"{H}-P1" and rows[2][3] == ""  # no target: the harness
    assert f"harnesses/{H2}/accessories.csv" not in built
    assert "Accessories" in _sheets(built[f"harnesses/{H}/{H}.xlsx"])
    assert "Accessories" not in _sheets(built[f"harnesses/{H2}/{H2}.xlsx"])


def test_the_bom_counts_contacts_per_pin_in_use_and_accessories_by_quantity_or_length(built: dict[str, bytes]) -> None:  # fmt: skip
    rows = {(r[0], r[7]): r for r in _csv(built, f"harnesses/{H}/bom.csv")[1:]}
    assert rows[("EX-CONTACT-20", "ea")][6] == "2"  # pin 1 of each of the two connectors
    assert rows[("EX-CONTACT-22", "ea")][6] == "2" and rows[("EX-CONTACT-20", "ea")][1] == "contact"
    assert rows[("EX-BACKSHELL", "ea")][6] == "1"
    assert rows[("EX-SLEEVE", "ea")][6] == "3"  # A002, no length: its quantity
    assert rows[("EX-SLEEVE", "m")][6] == "2.1"  # (1000 x 2 + 25 x 4) / 1000
    assert rows[("EX-SLEEVE", "m")][8] == ""  # "wires without length" belongs to wire parts only
    system = {(r[0], r[7]): r for r in _csv(built, "system/bom.csv")[1:]}
    assert system[("EX-SLEEVE", "m")][6] == "2.1" and system[("EX-CONTACT-20", "ea")][6] == "2"


def test_a_pin_without_a_wire_gets_no_contact_line(project: Project) -> None:
    p = copy.deepcopy(project)
    h = p.harnesses[H]
    c = sorted(h.connectors, key=lambda x: x.id)[0]
    spare = evolve(c.pins[4], contact_part="EX-CONTACT-22")  # pin 5: no wire
    apply_ops(p, [Put("harnesses", evolve(h, connectors=[evolve(c, pins=[*c.pins[:4], spare, *c.pins[5:]]) if x.id == c.id else x for x in h.connectors]))])  # fmt: skip
    rows = {(r[0], r[7]): r for r in tables.bom(p, [p.harnesses[H]])[1:]}
    assert rows[("EX-CONTACT-22", "ea")][6] == "2"


# ---- the build workbook always shows them -----------------------------------------------------------


def test_the_workbook_has_the_accessories_sheet_between_parts_and_labels(project: Project, plain: Project) -> None:  # fmt: skip
    assert SHEETS[3:6] == ("Parts", "Accessories", "Labels") and len(SHEETS) == 8
    for p, hid in ((project, H), (plain, H)):
        data = build_workbook(p, p.harnesses[hid], stamp_of(p))
        assert list(_sheets(data)) == list(SHEETS)


def test_the_cut_list_shows_strip_lengths_or_to_fill_in(project: Project, plain: Project) -> None:
    data = build_workbook(project, project.harnesses[H], stamp_of(project))
    rows = {r[1]: r for r in _sheets(data)["Cut list"][1:-1]}
    assert _sheets(data)["Cut list"][0][6:8] == ["Strip A (mm)", "Strip B (mm)"]
    assert rows[f"{H}-001"][6:8] == [6, 7.5] and rows[f"{H}-002"][6:8] == [5, "to fill in"]
    bare = build_workbook(plain, plain.harnesses[H], stamp_of(plain))  # shown even when never used
    assert all(r[6:8] == ["to fill in", "to fill in"] for r in _sheets(bare)["Cut list"][1:-1])
    ws = load_workbook(io.BytesIO(bare))["Cut list"]
    assert ws["G2"].fill.fgColor.rgb.endswith("FFE699")  # amber


def test_the_connectors_sheet_shows_contact_and_tool(project: Project, plain: Project) -> None:
    data = build_workbook(project, project.harnesses[H], stamp_of(project))
    rows = _sheets(data)["Connectors"]
    assert rows[0][9:11] == ["Contact", "Tool"] and rows[0][11:] == ["Terminated (x)", "Inserted (x)", "Checked (x)"]  # fmt: skip
    pins = [r for r in rows if r[0] in ("1", "2", "3")]
    assert [r[9:11] for r in pins[:3]] == [["EX-CONTACT-20", TOOL], ["EX-CONTACT-22", None], [None, None]]  # fmt: skip
    bare = _sheets(build_workbook(plain, plain.harnesses[H], stamp_of(plain)))["Connectors"]
    used = [r for r in bare if r[3] and str(r[3]).startswith(f"{H}-0")]
    assert used and all(r[9] == "to fill in" and not r[10] for r in used)


def test_the_accessories_sheet_lists_them_and_says_when_there_are_none(project: Project) -> None:
    rows = _sheets(build_workbook(project, project.harnesses[H], stamp_of(project)))["Accessories"]
    assert rows[0][0] == "Done (x)" and [r[1] for r in rows[1:]] == ["A001", "A002", "A003", "A004", "A005"]  # fmt: skip
    assert rows[1][6:8] == [1000, 2] and rows[2][4] == "(harness)" and not any(r[0] for r in rows[1:])  # fmt: skip
    none = _sheets(build_workbook(project, project.harnesses[H2], stamp_of(project)))["Accessories"]
    assert len(none) == 2 and none[0][0] == "Done (x)" and none[1][0] == "No accessories entered."


def test_the_start_sheet_notes_missing_strip_lengths_and_contacts(project: Project, plain: Project) -> None:  # fmt: skip
    checks = {c.label: c for c in readiness(project, project.harnesses[H])}
    assert checks["Wires without strip lengths"].open == 1  # the second wire has one end only
    assert checks["Pins in use without a contact part"].open == 0
    for c in (checks["Wires without strip lengths"], checks["Pins in use without a contact part"]):
        assert not c.blocking
    bare = {c.label: c for c in readiness(plain, plain.harnesses[H])}
    assert bare["Wires without strip lengths"].open == len(plain.harnesses[H].wires)
    assert bare["Wires without strip lengths"].status == "NOTE"
    assert bare["Pins in use without a contact part"].open == 4  # two wires, two ends each


def test_the_parts_sheet_has_the_new_bom_lines(project: Project) -> None:
    rows = _sheets(build_workbook(project, project.harnesses[H], stamp_of(project)))["Parts"]
    lines = {(r[0], r[7]): r[6] for r in rows[1:]}
    assert lines[("EX-CONTACT-20", "ea")] == 2 and lines[("EX-SLEEVE", "m")] == 2.1


# ---- the verifier -------------------------------------------------------------------------------


def test_the_outputs_of_a_project_with_build_data_verify(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    report = verify_outputs(project, built)
    assert report.ok, [i.message for i in report.issues]


def test_the_verifier_checks_the_strip_columns(project: Project, built: dict[str, bytes]) -> None:
    rel = f"harnesses/{H}/wirelist.csv"
    assert "out_wire_differs" in _codes(project, _edited(project, built, rel, 1, -2, "9"))
    assert "out_wire_differs" in _codes(project, _edited(project, built, rel, 2, -1, "3"))
    table = [r[:-2] for r in _csv(built, rel)]  # the columns taken away
    assert "out_wire_differs" in _codes(
        project, {**built, rel: csv_bytes(table, stamp_of(project))}
    )


def test_the_verifier_notices_strip_columns_on_a_project_that_has_none(plain: Project, plain_files: dict[str, bytes]) -> None:  # fmt: skip
    rel = f"harnesses/{H}/wirelist.csv"
    table = [[*r, "Strip A (mm)", "Strip B (mm)"] if n == 0 else [*r, "", ""] for n, r in enumerate(_csv(plain_files, rel))]  # fmt: skip
    assert "out_wire_differs" in _codes(plain, {**plain_files, rel: csv_bytes(table, stamp_of(plain))})  # fmt: skip


def test_the_verifier_checks_the_contact_column(project: Project, built: dict[str, bytes]) -> None:
    rel = f"harnesses/{H}/pinouts.csv"
    assert "out_pinout" in _codes(project, _edited(project, built, rel, 1, -1, "EX-CONTACT-22"))
    assert "out_pinout" in _codes(project, _edited(project, built, rel, 3, -1, "EX-CONTACT-20"))
    box = "system/box_pinouts.csv"
    assert "out_box_pinouts" in _codes(project, _edited(project, built, box, 2, -1, "EX-CONTACT-20"))  # fmt: skip


def test_the_verifier_checks_accessories_csv(project: Project, built: dict[str, bytes]) -> None:
    rel = f"harnesses/{H}/accessories.csv"
    for row, col, value in ((1, 6, "9"), (2, 2, "EX-LABEL"), (3, 5, "12"), (4, 3, f"{H}-P1")):
        assert "out_accessories" in _codes(project, _edited(project, built, rel, row, col, value)), (row, col)  # fmt: skip
    table = _csv(built, rel)
    del table[2]  # a row missing
    assert "out_accessories" in _codes(project, {**built, rel: csv_bytes(table, stamp_of(project))})
    table = _csv(built, rel)
    table[1], table[2] = table[2], table[1]  # not in ID order
    assert "out_accessories" in _codes(project, {**built, rel: csv_bytes(table, stamp_of(project))})


def test_the_file_is_required_only_for_a_harness_with_accessories(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    files = dict(built)
    del files[f"harnesses/{H}/accessories.csv"]
    assert "out_missing" in _codes(project, files)
    assert f"harnesses/{H2}/accessories.csv" not in built and verify_outputs(project, built).ok
    extra = {**built, f"harnesses/{H2}/accessories.csv": built[f"harnesses/{H}/accessories.csv"]}
    assert "out_accessories" in _codes(project, extra)


def test_the_verifier_checks_the_new_bom_lines(project: Project, built: dict[str, bytes]) -> None:
    rel = f"harnesses/{H}/bom.csv"
    rows = _csv(built, rel)
    line = {(r[0], r[7]): n for n, r in enumerate(rows)}
    for key, value in ((("EX-CONTACT-20", "ea"), "3"), (("EX-SLEEVE", "ea"), "2"), (("EX-SLEEVE", "m"), "2.0"), (("EX-BACKSHELL", "ea"), "2")):  # fmt: skip
        assert "out_bom" in _codes(project, _edited(project, built, rel, line[key], 6, value)), key
    gone = [r for r in rows if r[:1] != ["EX-CONTACT-22"]]
    assert "out_bom" in _codes(project, {**built, rel: csv_bytes(gone, stamp_of(project))})
    system = "system/bom.csv"
    n = next(i for i, r in enumerate(_csv(built, system)) if r[0] == "EX-SLEEVE" and r[7] == "m")
    assert "out_bom" in _codes(project, _edited(project, built, system, n, 6, "5"))


def test_the_verifier_checks_the_accessories_sheet_of_the_per_harness_workbook(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    rel = f"harnesses/{H}/{H}.xlsx"
    table = _csv(built, f"harnesses/{H}/accessories.csv")
    table[1][4] = "somewhere else"
    sheets = {"Wire list": _csv(built, f"harnesses/{H}/wirelist.csv"), "Accessories": table}
    wrong = exports.xlsx_bytes(sheets, stamp_of(project))
    assert "out_xlsx" in _codes(project, {**built, rel: wrong})
    plain_book = f"harnesses/{H2}/{H2}.xlsx"  # a sheet for a harness that has none
    sheets = {"Wire list": _csv(built, f"harnesses/{H2}/wirelist.csv"), "Accessories": table}
    assert "out_xlsx" in _codes(project, {**built, plain_book: exports.xlsx_bytes(sheets, stamp_of(project))})  # fmt: skip


def _tampered(project: Project, built: dict[str, bytes], hid: str, sheet: str, row: int, col: int, value: object) -> set[str]:  # fmt: skip
    rel = f"harnesses/{hid}/{hid}_build.xlsx"
    return _codes(project, {**built, rel: _replace_cell(built[rel], sheet, row, col, value)})


def test_the_verifier_checks_the_strip_cells_of_the_cut_list(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    for col, value in ((7, 99.0), (8, 99.0), (7, "to fill in"), (8, 7.5)):
        assert "out_build" in _tampered(project, built, H, "Cut list", 2 if col == 7 else 3, col, value), (col, value)  # fmt: skip
    assert "out_build" in _tampered(project, built, H2, "Cut list", 2, 7, 6.0)  # none entered


def test_the_verifier_checks_contact_and_tool_in_the_connectors_sheet(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    rel = f"harnesses/{H}/{H}_build.xlsx"
    pin1 = next(n for n, r in enumerate(_sheets(built[rel])["Connectors"], start=1) if r[0] == "1")
    assert "out_build" in _tampered(project, built, H, "Connectors", pin1, 10, "EX-CONTACT-22")
    assert "out_build" in _tampered(project, built, H, "Connectors", pin1, 11, "another tool")
    assert "out_build" in _tampered(project, built, H, "Connectors", pin1 + 1, 11, TOOL)
    assert "out_build" in _tampered(project, built, H, "Connectors", pin1, 10, "to fill in")
    assert "out_build" in _tampered(project, built, H, "Connectors", pin1 + 2, 10, "EX-CONTACT-20")  # a spare pin  # fmt: skip


def test_the_verifier_checks_the_accessories_sheet(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    for row, col, value in ((2, 3, "heat_shrink"), (2, 8, 7), (3, 5, "(harness) "), (3, 5, "W001-001"), (2, 1, "x"), (1, 5, "Targets")):  # fmt: skip
        assert "out_build" in _tampered(project, built, H, "Accessories", row, col, value), (row, col)  # fmt: skip
    assert "out_build" in _tampered(project, built, H2, "Accessories", 2, 1, "A001")  # not "none"
    assert "out_build" in _tampered(project, built, H2, "Accessories", 2, 1, "No accessories")


def test_the_verifier_checks_the_new_start_here_counts(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    rel = f"harnesses/{H}/{H}_build.xlsx"
    for label in ("Wires without strip lengths", "Pins in use without a contact part"):
        row = _row_of(built[rel], "Start here", label)
        assert "out_build" in _tampered(project, built, H, "Start here", row, 2, 7), label
        assert "out_build" in _tampered(project, built, H, "Start here", row, 3, "OK" if label.startswith("Wires") else "NOTE"), label  # fmt: skip


def test_the_parts_sheet_is_checked_for_the_new_bom_lines(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    rel = f"harnesses/{H}/{H}_build.xlsx"
    rows = _sheets(built[rel])["Parts"]
    n = next(i for i, r in enumerate(rows, start=1) if r[0] == "EX-SLEEVE" and r[7] == "m")
    assert "out_build" in _tampered(project, built, H, "Parts", n, 7, 9.0)
    n = next(i for i, r in enumerate(rows, start=1) if r[0] == "EX-CONTACT-20")
    assert "out_build" in _tampered(project, built, H, "Parts", n, 7, 9)
