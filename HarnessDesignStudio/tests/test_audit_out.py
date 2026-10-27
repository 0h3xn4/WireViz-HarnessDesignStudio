"""Regression tests for the output, import and command-line findings of the October audit
(D-1, D-2, E-1, E-2, E-3)."""

import hashlib
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.imports import ImportError_, parse_csv, read_table, read_table_sheet
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.samples import mini3

# ---- E-1: a stray quote must not swallow the rows after it ----------------------------------------


def test_a_quote_that_never_closes_is_an_error_with_the_line() -> None:
    with pytest.raises(ImportError_, match=r"Line 2: unbalanced quote"):
        parse_csv('a,b\n"x,1\ny,2\n')
    with pytest.raises(ImportError_, match="unbalanced quote"):
        parse_csv('a,b\n"x"y,1\n')
    assert parse_csv('a,b\n"x, y",2\nx"y,3\n') == [["a", "b"], ["x, y", "2"], ['x"y', "3"]]


def test_import_parts_with_a_stray_quote_imports_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "p"
    save_project(mini3(), project)
    before = _snapshot(project)
    f = tmp_path / "parts.csv"
    f.write_text(
        "Part,Manufacturer,Description,Category,Approval\n"
        'P-001,Acme,"Micro-D 9 pin male,connector,Approved\n'
        "P-002,Acme,Other,connector,Approved\n"
    )
    rc = cli_main(
        ["import-parts", str(project), str(f), "--approved", "Approved", "--category", "connector"]
    )
    err = capsys.readouterr().err
    assert rc == 2 and "unbalanced quote" in err and "Traceback" not in err
    assert _snapshot(project) == before


# ---- E-3: the first visible sheet is read, not the active one -------------------------------------


def _two_sheet_book(path: Path, hidden_first: bool = False) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    first = wb.active
    assert first is not None
    first.title = "Data"
    first.append(["Wire", "Segment", "Length"])
    first.append(["W001", "W001-L1", "111"])
    second = wb.create_sheet("Notes")
    second.append(["Wire", "Segment", "Length"])
    second.append(["W002", "W002-L1", "222"])
    wb.active = 1  # the second sheet is the one shown when the file is opened
    if hidden_first:
        first.sheet_state = "hidden"
    wb.save(path)


def test_xlsx_import_reads_the_first_sheet_not_the_active_one(tmp_path: Path) -> None:
    book = tmp_path / "len.xlsx"
    _two_sheet_book(book)
    table, sheet = read_table_sheet(book)
    assert sheet == "Data" and table[1][0] == "W001"
    assert read_table(book)[1][0] == "W001"


def test_xlsx_import_skips_a_hidden_first_sheet(tmp_path: Path) -> None:
    book = tmp_path / "len.xlsx"
    _two_sheet_book(book, hidden_first=True)
    table, sheet = read_table_sheet(book)
    assert sheet == "Notes" and table[1][0] == "W002"


def test_the_cli_names_the_sheet_it_read(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "p"
    save_project(mini3(), project)
    book = tmp_path / "len.xlsx"
    _two_sheet_book(book)
    cli_main(["import-lengths", str(project), str(book), "--unit", "m", "--dry-run"])
    assert "Reading sheet 'Data'" in capsys.readouterr().out


# ---- E-2: damaged projects are reported, never used or saved over ---------------------------------


def _snapshot(folder: Path) -> dict[str, str]:
    return {
        str(p.relative_to(folder)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and not p.name.startswith(".harness.lock")  # the lock is not data
    }


def _damaged(tmp_path: Path, what: str) -> Path:
    project = tmp_path / "p"
    save_project(mini3(), project)
    if what == "config":
        target = project / "config" / "derating.json"
        target.write_bytes(target.read_bytes()[:20])
    else:
        (project / "changelog.json").write_text('{"changelog": [')
    return project


def _commands(project: Path, tmp_path: Path) -> list[list[str]]:
    csv = tmp_path / "x.csv"
    csv.write_text("Part,Manufacturer\nP-1,Acme\n")
    lengths = tmp_path / "len.csv"
    lengths.write_text("Wire,Segment,Length\nW001,W001-L1,1\n")
    netlist = tmp_path / "n.xml"
    netlist.write_text("<export/>")
    p = str(project)
    return [
        ["drc", p],
        ["verify", p],
        ["generate", p],
        ["log", p],
        ["diff", p, "W001"],
        ["compare", p, p],
        ["config", p],
        ["config", p, "--apply-profile", "ecss-q-st-30-11c"],
        ["library", p],
        ["library", p, "--library-name", "Lib"],
        ["import-parts", p, str(csv), "--category", "connector"],
        ["import-lengths", p, str(lengths), "--unit", "m"],
        ["import-netlist", p, str(netlist), "--unit", "AOCS"],
        ["review", p, "W001", "--by", "Ada"],
        ["release", p, "W001", "--by", "Ada", "--comment", "long enough text"],
        ["revise", p, "W001", "--by", "Ada", "--comment", "long enough text"],
    ]


@pytest.mark.parametrize("what", ["config", "changelog"])
def test_every_command_refuses_a_damaged_project_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], what: str
) -> None:
    project = _damaged(tmp_path, what)
    before = _snapshot(project)
    for argv in _commands(project, tmp_path):
        capsys.readouterr()
        rc = cli_main(argv)
        err = capsys.readouterr().err
        assert rc == 2, argv
        assert "damaged files" in err and "nothing was" in err, argv
        assert _snapshot(project) == before, argv
    # validate and check keep reporting the damage themselves
    assert cli_main(["validate", str(project)]) == 1


def test_a_sound_project_still_works(tmp_path: Path) -> None:
    project = tmp_path / "p"
    save_project(mini3(), project)
    assert cli_main(["log", str(project)]) == 0
    assert cli_main(["library", str(project)]) == 0
    assert cli_main(["compare", str(project), str(project)]) == 0


# ---- D-1: lengths keep their digits in the data files ---------------------------------------------


def _exports_cleanly(project: Project) -> dict[str, bytes]:
    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.verify import verify_outputs

    files = build_outputs(project).files
    report = verify_outputs(project, files)
    assert report.ok, [i.render() for i in report.errors]
    return files


def _with_lengths(*lengths: float) -> Project:
    from harness_design_studio.core.model import evolve

    p = mini3()
    h = p.harnesses["W001"]
    wires = [
        evolve(w, length_m=n, part_id="EX-WIRE-SINGLE", gauge_awg=22)
        for w, n in zip(h.wires, lengths, strict=True)
    ]
    p.harnesses["W001"] = evolve(h, wires=wires)
    return p


@pytest.mark.parametrize("length", [1.234567, 12.34567, 123.4567, 1234.567, 9999.875])
def test_a_length_with_many_digits_exports_and_verifies(length: float) -> None:
    files = _exports_cleanly(_with_lengths(length, 1.0))
    rows = files["harnesses/W001/wirelist.csv"].decode().splitlines()
    assert any(f",{length!r}," in r for r in rows)  # every digit is in the file


def test_totals_do_not_show_floating_point_noise() -> None:
    files = _exports_cleanly(_with_lengths(0.1, 0.2))
    bom = files["harnesses/W001/bom.csv"].decode()
    assert ",0.3,m," in bom and "0.30000000000000004" not in bom
    mass = files["harnesses/W001/mass_length.csv"].decode()
    assert "0.30000000000000004" not in mass


@pytest.mark.slow
def test_a_cad_length_in_millimetres_survives_the_round_trip(tmp_path: Path) -> None:
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.io.loader import load_project
    from harness_design_studio.core.samples import sat15

    project = tmp_path / "p"
    p = sat15()
    generate_project(p)
    save_project(p, project)
    hid = sorted(p.harnesses)[0]
    seg = p.harnesses[hid].segments[0]
    f = tmp_path / "len.csv"
    f.write_text(f"Harness,Segment,Length\n{hid},{seg.id},1234.567\n")
    assert cli_main(["import-lengths", str(project), str(f), "--unit", "mm"]) == 0
    assert cli_main(["generate", str(project)]) == 0
    loaded = load_project(project).project
    _exports_cleanly(loaded)
    assert cli_main(["export", str(project)]) == 0
    assert cli_main(["verify", str(project), "--outputs"]) == 0


# ---- D-2: long IDs are shrunk in the drawing, never cut -------------------------------------------


def _project_with_ids(wire_id: str, connector_id: str, mixed: bool = False):  # type: ignore[no-untyped-def]
    from harness_design_studio.core.model import Connector, Harness, Pin, Wire, evolve

    p = mini3()
    for hid in list(p.harnesses):
        del p.harnesses[hid]
    ends = [
        Connector(
            id=connector_id + s,
            name=s,
            role="cable",
            part_id=part,
            mates_with=mate,
            pins=[Pin(id="1"), Pin(id="2")],
        )
        for s, part, mate in (("A", "EX-DSUB-9-M", "PCDU-J01"), ("B", "EX-DSUB-9-F", "RW1-J01"))
    ]
    wires = [
        Wire(
            id=f"{wire_id}{n}",
            from_connector=ends[0].id,
            from_pin=str(n),
            to_connector=ends[1].id,
            to_pin=str(n),
        )
        for n in (1, 2)
    ]
    if mixed:  # different gauge and length: the label carries more text
        wires = [
            evolve(wires[0], gauge_awg=20, length_m=1.5, colour="red"),
            evolve(wires[1], gauge_awg=22, length_m=12.345, colour="blue"),
        ]
    p.harnesses["H1"] = Harness(id="H1", name="h", connectors=ends, wires=wires)
    return p


@pytest.mark.parametrize(
    ("wire_id", "connector_id", "mixed"),
    [
        ("W", "C" * 33, False),  # 34 characters with the suffix
        ("W", "C" * 63, False),  # 64 characters, the longest the model allows
        ("W" * 62, "C", False),  # 63 characters with the number
        ("W" * 62, "C", True),
        ("W" + "x" * 59, "C", True),  # 61 characters: used to vanish from a mixed block
        ("W" + "x" * 45, "C", True),  # used to lose the end of "AWG n  length" silently
    ],
)
def test_long_ids_export_and_stay_whole_in_the_drawing(
    wire_id: str, connector_id: str, mixed: bool
) -> None:
    from harness_design_studio.core.outputs.canvas import text_width

    p = _project_with_ids(wire_id, connector_id, mixed)
    files = _exports_cleanly(p)
    import re

    svg = files["harnesses/H1/drawing_A3_s1.svg"].decode()
    texts = re.findall(r"<text[^>]*>([^<]*)</text>", svg)
    assert connector_id + "A" in texts and connector_id + "B" in texts  # the table headers
    assert any(t.split()[0] == f"{wire_id}1" for t in texts if t.strip())
    assert not any("~" in t for t in texts if t.startswith(wire_id[:5]))
    # nothing is drawn wider than the box it sits in
    for size_str, t in re.findall(r'font-size="([\d.]+)"[^>]*>([^<]*)</text>', svg):
        if t.startswith(("W" * 5, "C" * 5)):
            assert text_width(t, float(size_str)) <= 96.0


def test_normal_ids_are_drawn_exactly_as_before() -> None:
    from harness_design_studio.core.outputs.canvas import fit_size

    assert fit_size("C" * 33, 56.0, 2.8, 1.4) == 2.8  # the longest that fitted before
    assert fit_size("C" * 34, 56.0, 2.8, 1.4) < 2.8
    assert fit_size("W001-P1", 56.0, 2.8, 1.4) == 2.8
    assert fit_size("W" * 62, 94.0, 2.5, 1.4) == 2.5
    assert 1.4 <= fit_size("C" * 64, 56.0, 2.8, 1.4) < 1.5
