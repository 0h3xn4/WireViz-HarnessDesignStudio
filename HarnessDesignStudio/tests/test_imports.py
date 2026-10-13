"""REQ-IMPORT-01: CSV/XLSX import plans with per-row results; nothing changes until confirmed."""

from pathlib import Path

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import History
from harness_design_studio.core.imports import (
    ImportError_,
    guess_mapping,
    parse_csv,
    plan_interface_import,
    read_table,
)
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.samples import mini3

CSV = """Interface,Type,From unit,To unit,Redundancy
IF-010,Primary power,PCDU,OBC,nominal
IF-011,CAN,OBC,RW1,nominal
IF-012,RS-422,OBC,PCDU,nominal
IF-013,RS-423,OBC,RW1,nominal
IF-TM-RW1,Discrete / bilevel,OBC,PCDU,nominal
IF-014,Primary power,PCDU,GHOST,nominal
1bad,RS-422,OBC,PCDU,nominal
IF-015,RS-422,OBC,OBC,nominal
IF-016,RS-422,OBC,PCDU,sideways
"""


def test_plan_reports_every_row_and_builds_ops_for_good_rows() -> None:
    p = mini3()
    table = parse_csv(CSV)
    plan = plan_interface_import(p, table, guess_mapping(table[0]))
    msgs = {r.row_number: r.message for r in plan.rows}
    assert plan.ok_count == 2 and plan.error_count == 7
    assert msgs[2] == "" and msgs[4] == ""
    assert "No free CAN connector" in msgs[3] or "no free" in msgs[3].lower()
    assert msgs[5] == "Unknown interface type 'RS-423'"
    assert (
        "already used" in msgs[6]
        and "does not exist" in msgs[7]
        and "Invalid interface ID" in msgs[8]
    )
    assert "itself" in msgs[9] and "Redundancy must be" in msgs[10]


def test_plan_does_not_change_project_and_applies_as_one_undo_step() -> None:
    p = mini3()
    before = model_hash(p)
    table = parse_csv(CSV)
    plan = plan_interface_import(p, table, guess_mapping(table[0]))
    assert model_hash(p) == before  # planning is side-effect free
    h = History(p)
    h.execute("import", plan.ops)
    assert {"IF-010", "IF-012"} <= set(p.interfaces)
    assert all(e.auto for e in p.interfaces["IF-010"].endpoints)  # connectors chosen by the tool
    h.undo()
    assert model_hash(p) == before


def test_rows_in_the_same_file_compete_for_connectors() -> None:
    p = mini3()
    text = "id,type,from,to\nA1,RS-422,OBC,PCDU\nA2,RS-422,OBC,PCDU\nA3,RS-422,OBC,PCDU\n"
    table = parse_csv(text)
    plan = plan_interface_import(p, table, guess_mapping(table[0]))
    assert plan.ok_count == 1  # OBC-J03 is the only free RS-422 connector left on the computer
    assert all("no free" in r.message.lower() for r in plan.rows[1:])


def test_units_match_by_id_or_name_and_types_by_id_or_name() -> None:
    p = mini3()
    text = "id,type,from,to\nA1,rs422,On-board computer,Power control and distribution unit\n"
    table = parse_csv(text)
    plan = plan_interface_import(p, table, guess_mapping(table[0]))
    assert plan.ok_count == 1


def test_guess_mapping_by_header_names_and_by_position() -> None:
    assert guess_mapping(["Interface", "Type", "From unit", "To unit", "Redundancy"]) == {
        "id": 0, "type": 1, "from": 2, "to": 3, "redundancy": 4,
    }  # fmt: skip
    assert guess_mapping(["Destination", "Protocol", "Source", "ID"]) == {
        "to": 0,
        "type": 1,
        "from": 2,
        "id": 3,
    }
    assert guess_mapping(["x", "y", "z"]) == {"id": 0, "type": 1, "from": 2}


def test_empty_and_ragged_tables() -> None:
    p = mini3()
    assert plan_interface_import(p, [], {}).rows == []
    plan = plan_interface_import(p, [["a"], ["IF-1"]], {"id": 0, "type": 1})
    assert plan.error_count == 1
    assert parse_csv('a,b\n"x, y",2\n\n,\n') == [["a", "b"], ["x, y", "2"]]


def test_read_csv_and_xlsx_files(tmp_path: Path) -> None:
    csv_path = tmp_path / "icd.csv"
    csv_path.write_bytes(b"\xef\xbb\xbf" + CSV.encode("utf-8"))
    assert read_table(csv_path)[0][0] == "Interface"  # BOM tolerated
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    assert ws is not None
    for row in parse_csv(CSV):
        ws.append(row)
    ws.append([None, None])
    xlsx = tmp_path / "icd.xlsx"
    wb.save(xlsx)
    assert read_table(xlsx) == parse_csv(CSV)


def test_read_table_errors(tmp_path: Path) -> None:
    with pytest.raises(ImportError_, match="could not be read"):
        read_table(tmp_path / "missing.csv")
    bad = tmp_path / "bad.csv"
    bad.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(ImportError_, match="not UTF-8"):
        read_table(bad)
    fake = tmp_path / "fake.xlsx"
    fake.write_text("not a zip")
    with pytest.raises(ImportError_, match="not a valid .xlsx"):
        read_table(fake)
    other = tmp_path / "x.txt"
    other.write_text("a")
    with pytest.raises(ImportError_, match="Only .csv and .xlsx"):
        read_table(other)
    big = tmp_path / "big.csv"
    big.write_bytes(b"a,b\n" + b"x" * (9 * 1024 * 1024))
    with pytest.raises(ImportError_, match="too large"):
        read_table(big)
    with pytest.raises(ImportError_, match="too large"):
        parse_csv("x" * (9 * 1024 * 1024))
    with pytest.raises(ImportError_, match="more than"):
        parse_csv("a\n" * 20005)


def test_unit_compat_used_by_import_is_the_editor_rule() -> None:
    p = mini3()
    assert edit.unit_compat(p, "rs422", "PCDU").ok
