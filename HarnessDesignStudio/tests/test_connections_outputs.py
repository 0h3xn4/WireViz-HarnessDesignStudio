# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type"
"""Release 1.9, W2 (REQ-OUT-09): the connection list (ICD style) as an output. `connections.csv`
and `connections.xlsx` are written for a project that has links, and only then; the links are in
the block diagram and in `traceability.csv`; a project with links and no harness exports; the
independent verifier checks the new files (every check has a mutation test). No Qt."""

import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.links import plan_add_link, plan_create_harness
from harness_design_studio.core.model import Pin, PinPair, evolve
from harness_design_studio.core.outputs import connections
from harness_design_studio.core.outputs.build import build_outputs, outputs_status, write_outputs
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of
from harness_design_studio.core.outputs.verify import (
    _xlsx_values,
    read_folder,
    verify_outputs,
)
from harness_design_studio.core.samples import mini3, sat15
from tests.helpers import pinout_project

CSV = "system/connections.csv"
XLSX = "system/connections.xlsx"
TRACE = "system/traceability.csv"
RS = ("OBC-J01", "RW1-J02")  # RS-422 pins 1 to 4 on both: TX+, TX-, RX+, RX-
PWR = ("PCDU-J02", "OBC-J02")  # pins 1 and 2: PWR, RTN


def linked(harness: bool = False, both: bool = True):
    """mini3 with labelled pins, no interface and no harness, and the links RS (L1) and PWR (L2);
    `harness` makes the harness of L1 from it."""
    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    for a, b in (RS, PWR) if both else (RS,):
        ops, _lid = plan_add_link(p, a, b)
        apply_ops(p, ops)
    if harness:
        ops, _hid = plan_create_harness(p, "L1")
        History(p).execute("Create harness", ops)
    return p


def build(p, **kw) -> dict[str, bytes]:
    return build_outputs(p, drawings=False, **kw).files


def codes(p, files) -> set[str]:
    return {i.code for i in verify_outputs(p, files).issues if i.severity == "error"}


def table(files, rel=CSV):
    return parse_csv(files[rel])


def put_table(files, rel, rows, p) -> None:
    files[rel] = csv_bytes(rows, stamp_of(p))


# ---- only for a project that has links ---------------------------------------------------------


@pytest.mark.parametrize("make", [mini3, sat15])
def test_a_project_without_links_keeps_its_files_and_its_columns(make) -> None:
    p = make()
    files = build(p)
    assert CSV not in files and XLSX not in files
    assert table(files, TRACE)[0] == [
        "Interface", "Name", "Type", "From", "To", "Harnesses", "Wires", "Routed",
    ]  # fmt: skip
    assert not codes(p, files)
    # the diagram has no label text for anything but boxes, zones and the legend
    assert b'font-size="2"' not in files["system/block_diagram.svg"]


def test_a_project_with_links_gets_the_two_files_and_they_are_in_the_manifest(tmp_path: Path):
    p = linked()
    out = build_outputs(p, drawings=False)
    assert {CSV, XLSX} <= set(out.files)
    listed = {f["path"] for f in json.loads(out.manifest(p))["files"]}
    assert {CSV, XLSX} <= listed
    write_outputs(p, tmp_path, out)
    assert (tmp_path / CSV).is_file() and (tmp_path / XLSX).is_file()
    assert outputs_status(p, tmp_path, deep=True).state == "current"
    assert not verify_outputs(p, read_folder(tmp_path)).issues  # the stamp, manifest, all of it


def test_deleting_the_last_link_removes_the_files_at_the_next_export(tmp_path: Path):
    p = linked()
    write_outputs(p, tmp_path)
    for lid in list(p.links):
        del p.links[lid]
    write_outputs(p, tmp_path)
    assert not (tmp_path / CSV).exists() and not (tmp_path / XLSX).exists()
    assert not verify_outputs(p, read_folder(tmp_path)).issues


def test_the_files_are_the_same_every_time():
    a, b = build(linked()), build(linked())
    assert a[CSV] == b[CSV] and a[XLSX] == b[XLSX] and a[TRACE] == b[TRACE]
    with zipfile.ZipFile(io.BytesIO(a[XLSX])) as z:  # fixed timestamps, like the other workbooks
        assert {i.date_time for i in z.infolist()} == {(1980, 1, 1, 0, 0, 0)}
        assert b"2000-01-01T00:00:00Z" in z.read("docProps/core.xml")


# ---- what the list says --------------------------------------------------------------------------


def test_one_row_for_each_pair_with_devices_connectors_pins_signals_and_roles():
    p = linked()
    rows = table(build(p))
    assert rows[0] == connections.HEADER
    assert rows[1:] == [
        [
            "L1",
            "",
            "OBC",
            "OBC-J01",
            "1",
            "TX+",
            "signal",
            "RW1",
            "RW1-J02",
            "3",
            "RX+",
            "signal",
            "Ethernet or RS-422",
            "",
            "",
        ],  # fmt: skip
        [
            "L1",
            "",
            "OBC",
            "OBC-J01",
            "2",
            "TX-",
            "signal",
            "RW1",
            "RW1-J02",
            "4",
            "RX-",
            "signal",
            "Ethernet or RS-422",
            "",
            "",
        ],  # fmt: skip
        [
            "L1",
            "",
            "OBC",
            "OBC-J01",
            "3",
            "RX+",
            "signal",
            "RW1",
            "RW1-J02",
            "1",
            "TX+",
            "signal",
            "Ethernet or RS-422",
            "",
            "",
        ],  # fmt: skip
        [
            "L1",
            "",
            "OBC",
            "OBC-J01",
            "4",
            "RX-",
            "signal",
            "RW1",
            "RW1-J02",
            "2",
            "TX-",
            "signal",
            "Ethernet or RS-422",
            "",
            "",
        ],  # fmt: skip
        [
            "L2",
            "",
            "PCDU",
            "PCDU-J02",
            "1",
            "PWR",
            "power",
            "OBC",
            "OBC-J02",
            "1",
            "PWR",
            "power",
            "Primary power or Secondary power",
            "",
            "",
        ],  # fmt: skip
        [
            "L2",
            "",
            "PCDU",
            "PCDU-J02",
            "2",
            "RTN",
            "return",
            "OBC",
            "OBC-J02",
            "2",
            "RTN",
            "return",
            "Primary power or Secondary power",
            "",
            "",
        ],  # fmt: skip
    ]


def test_name_note_role_given_by_a_person_and_the_harness_are_written():
    p = linked(harness=True)
    p.links["L2"] = evolve(p.links["L2"], name="Main power", note="fused at the PCDU")
    c = p.connectors["PCDU-J02"]
    pins = [evolve(x, role="spare") if x.id == "2" else x for x in c.pins]
    p.connectors["PCDU-J02"] = evolve(c, pins=pins)
    files = build(p)
    rows = table(files)
    assert {r[13] for r in rows[1:] if r[0] == "L1"} == {p.links["L1"].harness_id} != {""}
    last = rows[-1]
    assert (last[0], last[1], last[4], last[6], last[14]) == ("L2", "Main power", "2", "spare", "fused at the PCDU")  # fmt: skip
    assert not codes(p, files)


def test_pins_come_in_natural_order_and_a_pin_without_a_signal_is_written_empty():
    p = linked(both=False)
    for cid in RS:
        c = p.connectors[cid]
        p.connectors[cid] = evolve(c, pins=[Pin(id=str(k)) for k in (1, 2, 10, 3)])
    a, b = p.connectors[RS[0]], p.connectors[RS[1]]
    p.links["L1"] = evolve(
        p.links["L1"], pairs=[PinPair(a_pin=x, b_pin=x) for x in ("10", "2", "1", "3")]
    )
    rows = table(build(p))
    assert [r[4] for r in rows[1:]] == ["1", "2", "3", "10"]
    assert all(r[5] == r[6] == r[10] == r[11] == r[12] == "" for r in rows[1:])
    assert a and b


def test_a_link_without_pairs_and_a_link_with_a_missing_connector_are_not_left_out():
    p = linked()
    p.links["L1"] = evolve(p.links["L1"], pairs=[])
    p.links["L2"] = evolve(p.links["L2"], b_connector="GONE-J09")
    files = build(p)
    rows = table(files)
    assert [r[0] for r in rows[1:]] == ["L1", "L2", "L2"]
    assert rows[1][4] == rows[1][9] == "" and rows[1][3] == "OBC-J01"
    assert rows[2][7:10] == ["", "GONE-J09", "1"] and rows[2][10:13] == ["", "", ""]
    summary = _xlsx_values(files[XLSX])["Summary"]
    assert [r[6] for r in summary[1:]] == ["0", "2"]
    assert not codes(p, files)  # (the integrity check says what is wrong with the link, not this)


def test_text_that_looks_like_a_formula_stays_text_in_both_files():
    p = linked(both=False)
    c = p.connectors[RS[0]]
    p.connectors[RS[0]] = evolve(
        c, pins=[evolve(x, signal="+5V") if x.id == "1" else x for x in c.pins]
    )
    p.links["L1"] = evolve(p.links["L1"], note="=1+1")
    files = build(p)
    assert table(files)[1][5] == "+5V" and table(files)[1][14] == "=1+1"
    assert b"'+5V" in files[CSV]  # the apostrophe that keeps a spreadsheet program from running it
    sheet = _xlsx_values(files[XLSX])["Connections"]
    assert sheet[1][5] == "+5V" and sheet[1][14] == "=1+1"
    assert not codes(p, files)


# ---- the workbook ---------------------------------------------------------------------------------


def test_the_workbook_has_the_rows_of_the_csv_a_summary_and_the_stamp():
    p = linked()
    files = build(p)
    sheets = _xlsx_values(files[XLSX])
    assert list(sheets) == list(connections.SHEETS)
    assert sheets["Connections"] == table(files)
    assert sheets["Summary"] == [
        connections.SUMMARY_HEADER,
        ["L1", "", "OBC", "OBC-J01", "RW1", "RW1-J02", "4", "Ethernet or RS-422, 4 wires", "", ""],
        [
            "L2",
            "",
            "PCDU",
            "PCDU-J02",
            "OBC",
            "OBC-J02",
            "2",
            "Primary power or Secondary power, 2 wires",
            "",
            "",
        ],  # fmt: skip
    ]
    assert sheets["About"][0] == ["Generated by", stamp_of(p).line]
    assert sheets["About"][1] == ["Model hash", stamp_of(p).model_hash]
    from harness_design_studio.core.outputs.xlsx_env import load_workbook

    ws = load_workbook(io.BytesIO(files[XLSX]))["Connections"]  # ready to hand over
    assert ws.freeze_panes == "A2" and ws.print_title_rows == "$1:$1"
    assert ws.page_setup.orientation == "landscape"
    assert not any(isinstance(c.value, str) and c.data_type == "f" for r in ws.iter_rows() for c in r)  # fmt: skip


# ---- the links in the other files ----------------------------------------------------------------


def test_traceability_lists_the_connections_under_the_interfaces():
    p = linked(harness=True)
    rows = table(build(p), TRACE)
    assert rows[0] == [
        "Interface or connection", "Name", "Type", "From", "To", "Harnesses", "Wires", "Routed",
        "Kind",
    ]  # fmt: skip
    hid = p.links["L1"].harness_id
    wires = ";".join(sorted(w.id for w in p.harnesses[hid].wires))
    assert rows[1] == ["L1", "OBC-J01 - RW1-J02", "ethernet;rs422", "OBC/OBC-J01", "RW1/RW1-J02", hid, wires, "yes", "connection"]  # fmt: skip
    assert rows[2] == ["L2", "PCDU-J02 - OBC-J02", "power_primary;power_secondary", "PCDU/PCDU-J02", "OBC/OBC-J02", "", "", "no", "connection"]  # fmt: skip


def test_traceability_keeps_interfaces_first_and_marks_each_row():
    q = pinout_project()
    ops, _lid = plan_add_link(q, *RS)
    apply_ops(q, ops)
    rows = table(build(q), TRACE)
    kinds = [r[-1] for r in rows[1:]]
    assert kinds == ["interface"] * len(q.interfaces) + ["connection"]


def test_the_block_diagram_draws_each_connection_with_its_id():
    p = linked()
    files = build(p)
    svg = files["system/block_diagram.svg"].decode()
    texts = re.findall(r"<text[^>]*>([^<]*)</text>", svg)
    assert "L1" in texts and "L2" in texts
    assert svg.count("<line") >= len(build(mini3())["system/block_diagram.svg"].decode().split("<line")) - 1 + 2  # fmt: skip
    assert b"L1" in files["system/block_diagram.pdf"]
    # a connection inside one device has no line
    q = linked()
    c = q.connectors[PWR[1]]
    q.connectors[PWR[1]] = evolve(c, unit_id=q.connectors[PWR[0]].unit_id)
    texts = re.findall(r"<text[^>]*>([^<]*)</text>", build(q)["system/block_diagram.svg"].decode())
    assert "L1" in texts and "L2" not in texts


# ---- export without a harness --------------------------------------------------------------------


def test_the_export_and_the_check_work_with_links_and_no_harness(tmp_path: Path, capsys) -> None:
    p = linked()
    save_project(p, tmp_path)
    assert not p.harnesses
    assert cli_main(["export", str(tmp_path)]) == 0
    assert (tmp_path / "outputs" / CSV).is_file() and (tmp_path / "outputs" / XLSX).is_file()
    assert "files written" in capsys.readouterr().out
    assert cli_main(["verify", str(tmp_path), "--outputs"]) == 0
    capsys.readouterr()
    assert cli_main(["generate", str(tmp_path)]) == 0  # nothing to generate, and no dead end
    assert "2 connection(s) and no interface" in capsys.readouterr().out
    assert cli_main(["export", str(tmp_path)]) == 0


def test_a_project_with_neither_harness_nor_links_still_says_to_generate(tmp_path, capsys):
    p = linked()
    p.links.clear()
    save_project(p, tmp_path)
    assert cli_main(["export", str(tmp_path)]) == 1
    assert "there are no harnesses to export" in capsys.readouterr().err


# ---- the verifier: each check can fail -------------------------------------------------------------


def mutate_rows(p, change) -> dict[str, bytes]:
    files = build(p)
    rows = table(files)
    change(rows)
    put_table(files, CSV, rows, p)
    return files


def test_the_verifier_accepts_the_untouched_files_with_and_without_a_harness():
    for harness in (False, True):
        p = linked(harness=harness)
        assert not verify_outputs(p, build(p)).issues


@pytest.mark.parametrize(
    "name,change",
    [
        ("signal", lambda rows: rows[1].__setitem__(5, "XX")),
        ("role", lambda rows: rows[5].__setitem__(6, "ground")),
        ("pin", lambda rows: rows[2].__setitem__(9, "9")),
        ("device", lambda rows: rows[1].__setitem__(2, "PCDU")),
        ("connector", lambda rows: rows[1].__setitem__(8, "RW1-J09")),
        ("harness", lambda rows: rows[1].__setitem__(13, "W404")),
        ("note", lambda rows: rows[1].__setitem__(14, "added by hand")),
        ("interface", lambda rows: rows[1].__setitem__(12, "CAN")),
        ("empty interface", lambda rows: rows[5].__setitem__(12, "")),
        ("row removed", lambda rows: rows.pop(3)),
        ("row repeated", lambda rows: rows.append(list(rows[2]))),
        ("header", lambda rows: rows[0].__setitem__(3, "Connector A")),
        ("order", lambda rows: rows.__setitem__(slice(1, None), rows[:0:-1])),
    ],
)
def test_changing_the_connection_list_is_an_error(name, change) -> None:
    p = linked()
    files = mutate_rows(p, change)
    assert "out_connections" in codes(p, files), name


def test_a_missing_file_a_wrong_workbook_and_files_that_should_not_be_there_are_errors(
    monkeypatch,
) -> None:
    p = linked()
    files = build(p)
    for rel in (CSV, XLSX):
        gone = dict(files)
        del gone[rel]
        assert "out_missing" in codes(p, gone), rel
    # a workbook of another project (right stamp, other rows)
    other = linked(both=False)
    wrong = dict(files)
    wrong[XLSX] = connections.connections_workbook(other, stamp_of(p))
    assert "out_connections" in codes(p, wrong)
    # a workbook whose Connections sheet differs from the CSV file
    rows = table(files)
    rows[1][5] = "XX"
    skewed = dict(files)
    skewed[XLSX] = _workbook_with(p, rows, monkeypatch)
    assert "out_connections" in codes(p, skewed)
    # a project without links does not have them
    q = linked()
    q.links.clear()
    extra = build(q)
    extra[CSV], extra[XLSX] = files[CSV], files[XLSX]
    assert "out_connections" in codes(q, extra)


def _workbook_with(p, rows, monkeypatch) -> bytes:
    monkeypatch.setattr(connections, "connection_rows", lambda _p: rows)
    return connections.connections_workbook(p, stamp_of(p))


def test_changing_the_summary_sheet_is_an_error(monkeypatch) -> None:
    p = linked()
    files = build(p)
    real = connections.summary_rows

    def wrong(project):
        rows = real(project)
        rows[1][6] = "9"
        return rows

    monkeypatch.setattr(connections, "summary_rows", wrong)
    files[XLSX] = connections.connections_workbook(p, stamp_of(p))
    assert "out_connections" in codes(p, files)


def test_the_workbook_stamp_is_checked_like_the_other_workbooks() -> None:
    p = linked()
    files = build(p)
    other = linked(both=False)
    files[XLSX] = connections.connections_workbook(other, stamp_of(other))
    assert "out_stamp" in codes(p, files)


def test_changing_the_traceability_of_a_connection_is_an_error() -> None:
    p = linked(harness=True)
    files = build(p)
    good = table(files, TRACE)
    assert not codes(p, files)
    for col, value in (
        (6, ""),
        (7, "no"),
        (5, ""),
        (3, "OBC/OBC-J09"),
        (8, "interface"),
        (2, "can"),
    ):
        rows = [list(r) for r in good]
        rows[1][col] = value
        put_table(files, TRACE, rows, p)
        assert "out_trace" in codes(p, files), col
    rows = [list(r) for r in good]
    del rows[2]  # a connection missing
    put_table(files, TRACE, rows, p)
    assert "out_trace" in codes(p, files)
    rows = [list(r) for r in good]
    rows[0][0] = "Interface"
    put_table(files, TRACE, rows, p)
    assert "out_trace" in codes(p, files)


def test_the_block_diagram_must_show_every_connection() -> None:
    p = linked()
    files = build(p)
    files["system/block_diagram.svg"] = files["system/block_diagram.svg"].replace(
        b">L2</text>", b">LL</text>"
    )
    found = [i for i in verify_outputs(p, files).issues if i.code == "out_diagram"]
    assert found and "connection L2" in found[0].message


def test_a_connection_that_was_added_after_the_export_is_found_by_the_check(tmp_path: Path):
    p = linked(both=False)
    write_outputs(p, tmp_path)
    ops, _ = plan_add_link(p, *PWR)
    apply_ops(p, ops)
    out = verify_outputs(p, read_folder(tmp_path))
    assert out.stale and "out_stale" in {i.code for i in out.issues}


def test_the_put_of_a_link_changes_the_files_not_the_other_tables() -> None:
    """Adding a link changes only the files that show links (and the stamped ones)."""
    p = linked(both=False)
    before = build(p)
    ops, _ = plan_add_link(p, *PWR)
    apply_ops(p, ops)
    after = build(p)
    assert before["system/bom.csv"].split(b"\n", 1)[1] == after["system/bom.csv"].split(b"\n", 1)[1]
    assert before[CSV] != after[CSV]
