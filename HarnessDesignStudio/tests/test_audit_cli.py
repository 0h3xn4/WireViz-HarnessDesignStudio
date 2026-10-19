"""Regression tests for the command line and importer findings of the October audit."""

import os
import shutil
import sys
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.imports import ImportError_, guess_mapping, parse_csv, read_table
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.library_import import plan_parts_import
from harness_design_studio.core.samples import mini3, sat15


def _project(tmp: Path, make=mini3) -> Path:  # type: ignore[no-untyped-def]
    save_project(make(), tmp / "p")
    return tmp / "p"


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    rc = main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out + cap.err


@pytest.mark.parametrize("kind", ["missing", "binary", "directory"])
def test_a_bad_ampacity_file_is_a_message_not_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], kind: str
) -> None:
    p = _project(tmp_path)
    f = tmp_path / "t.csv"
    if kind == "binary":
        f.write_bytes(b"\xff\xfe\x00\x01\x80")
    elif kind == "directory":
        f.mkdir()
    rc, text = _run(capsys, "config", str(p), "--ampacity-csv", str(f))
    assert rc == 2 and "error:" in text and "Traceback" not in text


def test_over_long_names_and_comments_are_messages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _project(tmp_path, sat15)
    rc, text = _run(capsys, "generate", str(p))
    assert rc == 0, text
    rc, text = _run(capsys, "review", str(p), "W001", "--by", "x" * 100000)
    assert rc in (1, 2) and "Traceback" not in text and len(text) < 2000


def test_a_project_name_that_is_too_long_for_the_file_system(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, text = _run(capsys, "validate", str(tmp_path / ("n" * 300)))
    assert rc == 2 and "Traceback" not in text


def test_export_into_a_read_only_place_is_a_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _project(tmp_path, sat15)
    assert main(["generate", str(p)]) == 0
    (p / "outputs").write_text("a file where the folder should be")
    rc, text = _run(capsys, "export", str(p))
    assert rc == 2 and "Traceback" not in text


def test_a_symlinked_outputs_folder_is_never_written_through(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _project(tmp_path, sat15)
    assert main(["generate", str(p)]) == 0
    victim = tmp_path / "victim"
    victim.mkdir()
    (p / "outputs").symlink_to(victim, target_is_directory=True)
    rc, text = _run(capsys, "export", str(p))
    assert rc == 2 and not list(victim.iterdir())


def test_a_command_that_writes_refuses_while_another_instance_holds_the_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.core.io.fs import ProjectLock

    p = _project(tmp_path, sat15)
    lock = ProjectLock(p)
    lock.acquire()
    try:
        # the lock is held by this process, which counts as another instance for a second open
        before = model_hash(load_project(p).project)
        rc, text = _run(capsys, "generate", str(p))
        assert rc == 1 and "already open" in text
        assert model_hash(load_project(p).project) == before
        rc, _ = _run(capsys, "validate", str(p))  # reading is always fine
        assert rc == 0
    finally:
        lock.release()


def _contents(folder: Path) -> dict[str, bytes]:
    return {
        str(x.relative_to(folder)): x.read_bytes() for x in sorted(folder.rglob("*")) if x.is_file()
    }


@pytest.mark.parametrize(("row", "rc"), [("W010,W010-L1,1500", 0), ("W010,NOPE,1500", 1)])
def test_dry_runs_do_not_take_the_lock_or_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], row: str, rc: int
) -> None:
    from tests.test_data_import import project_with_segments

    p = tmp_path / "p"
    save_project(project_with_segments(), p)
    f = tmp_path / "l.csv"
    f.write_text(f"harness,segment,length\n{row}\n")
    before = _contents(p)
    code, text = _run(capsys, "import-lengths", str(p), str(f), "--dry-run")
    assert code == rc, text
    assert _contents(p) == before  # not one byte changed, no lock file, no backup, no journal
    assert not list(p.rglob(".harness.lock*"))


# ---- tables -------------------------------------------------------------------------------------


def test_semicolon_files_and_decimal_commas_work() -> None:
    assert parse_csv("harness;segment;length\nW001;W001-L1;1,5\n") == [
        ["harness", "segment", "length"],
        ["W001", "W001-L1", "1,5"],
    ]
    assert parse_csv("a\tb\n1\t2\n") == [["a", "b"], ["1", "2"]]


def test_an_unquoted_decimal_comma_is_refused_not_cut_off() -> None:
    with pytest.raises(ImportError_, match="more columns"):
        parse_csv("harness,segment,length\nW001,W001-L1,1,5\n")
    assert parse_csv('harness,segment,length\nW001,W001-L1,"1,5"\n')[1][2] == "1,5"


@pytest.mark.skipif(sys.platform == "win32", reason="/dev/zero and named pipes are POSIX")
def test_special_files_are_refused_without_reading_them(tmp_path: Path) -> None:
    link = tmp_path / "zero.csv"
    link.symlink_to("/dev/zero")
    with pytest.raises(ImportError_, match="regular file"):
        read_table(link)
    fifo = tmp_path / "pipe.csv"
    os.mkfifo(fifo)
    with pytest.raises(ImportError_, match="regular file"):
        read_table(fifo)  # would hang forever if it were opened


def _xlsx(tmp: Path, name: str, edit) -> Path:  # type: ignore[no-untyped-def]
    import zipfile

    from openpyxl import Workbook

    src = tmp / "ok.xlsx"
    wb = Workbook()
    wb.active.append(["harness", "segment", "length"])  # type: ignore[union-attr]
    wb.active.append(["W001", "W001-L1", "1.5"])  # type: ignore[union-attr]
    wb.save(src)
    out = tmp / name
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w") as zout:
        for item in zin.infolist():
            zout.writestr(item, edit(item.filename, zin.read(item)))
    return out


def test_damaged_workbooks_are_a_message(tmp_path: Path) -> None:
    cut = _xlsx(tmp_path, "cut.xlsx", lambda n, d: d[: len(d) // 2] if "sheet1" in n else d)
    bad_styles = _xlsx(tmp_path, "styles.xlsx", lambda n, d: d[:20] if "styles" in n else d)
    for f in (cut, bad_styles):
        with pytest.raises(ImportError_):
            read_table(f)


def test_a_workbook_that_declares_a_one_cell_sheet_is_still_read(tmp_path: Path) -> None:
    import re

    f = _xlsx(
        tmp_path,
        "dim.xlsx",
        lambda n, d: (
            re.sub(rb'<dimension ref="[^"]*"', b'<dimension ref="A1"', d) if "sheet1" in n else d
        ),
    )
    assert read_table(f)[1][:2] == ["W001", "W001-L1"]


def test_two_columns_for_the_same_thing_are_refused() -> None:
    with pytest.raises(ImportError_):
        guess_mapping(["id", "type", "from", "to", "to"])


# ---- lengths and parts --------------------------------------------------------------------------


def test_lengths_rounding_headers_and_strange_numbers(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.core.generate.lengths import plan_length_import

    p = sat15()
    generate_project(p)
    hid = next(h.id for h in p.harnesses.values() if h.segments)
    sid = p.harnesses[hid].segments[0].id
    plan = plan_length_import(p, [["h", "s", "l"], [hid, sid, "1234,7"]], scale=0.001)
    assert plan.rows[0].ok and "1.2347" in repr(plan.ops[0])
    for bad in ("1e300", "1_0", "-1", "inf", "10000001"):
        assert not plan_length_import(p, [["h", "s", "l"], [hid, sid, bad]]).rows[0].ok
    first = plan_length_import(p, [[hid, sid, "1.5"]])
    assert not first.rows[0].ok and "headings" in first.rows[0].message
    f = tmp_path / "empty.csv"
    f.write_text("harness,segment,length\n")
    pr = _project(tmp_path)
    rc, text = _run(capsys, "import-lengths", str(pr), str(f))
    assert rc == 2 and "no rows" in text


def test_parts_that_differ_only_in_case_and_overlapping_status_lists() -> None:
    p = mini3()
    table = [
        ["id", "category", "approval"],
        ["PX-1", "connector", "yes"],
        ["px-1", "connector", "yes"],
    ]
    mapping = guess_mapping(table[0]) | {"category": 1, "approval": 2}
    plan = plan_parts_import(p, table, mapping, approved=["yes"])
    assert [r.ok for r in plan.rows] == [True, False] and "case" in plan.rows[1].message
    with pytest.raises(ImportError_):
        plan_parts_import(p, table, mapping, approved=["Both"], rejected=["both"])


def test_a_mating_part_that_does_not_exist_is_a_row_error() -> None:
    p = mini3()
    table = [["id", "category", "mates"], ["PX-9", "connector", "NO-SUCH-PART"]]
    mapping = {"id": 0, "category": 1, "mates_with": 2}
    plan = plan_parts_import(p, table, mapping, approved=["yes"])
    assert not plan.rows[0].ok and "Mating part" in plan.rows[0].message and not plan.ops


# ---- exit codes ---------------------------------------------------------------------------------


def test_exit_codes_are_consistent_for_unknown_harnesses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = _project(tmp_path, sat15)
    for cmd in ("review", "diff"):
        rc, _ = _run(capsys, cmd, str(p), "NOPE", *(["--by", "Ada"] if cmd == "review" else []))
        assert rc == 2, cmd
    rc, _ = _run(capsys, "log", str(p), "NOPE")
    assert rc == 2


def test_a_read_only_project_is_not_exported_or_migrated(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    p = _project(tmp_path, sat15)
    assert main(["generate", str(p)]) == 0
    meta = json.loads((p / "project.json").read_text())
    meta["schema_version"] = 99
    (p / "project.json").write_text(json.dumps(meta))
    for cmd in ("export", "migrate"):
        rc, text = _run(capsys, cmd, str(p))
        assert rc == 2 and "read-only" in text, cmd
    assert not (p / "outputs").exists()


def test_overlapping_approval_lists_are_a_usage_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.rmtree(tmp_path / "x", ignore_errors=True)
    p = _project(tmp_path)
    f = tmp_path / "parts.csv"
    f.write_text("id,category,approval\nPX-1,connector,yes\n")
    rc, _ = _run(
        capsys,
        "import-parts",
        str(p),
        str(f),
        "--approved",
        "yes",
        "--approved",
        "Yes",
        "--rejected",
        "yes",
    )
    assert rc == 2  # overlapping lists are a usage error
