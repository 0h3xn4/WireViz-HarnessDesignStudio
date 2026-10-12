"""Regression tests for the medium command-line, import, KiCad and change-control findings of the
October audit (E-6 to E-17, K-3, K-4, K-12, K-14, C-8 message)."""

import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import edit
from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.imports import ImportError_
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.kicad import NetlistError, NetlistPlan, parse_netlist, read_netlist
from harness_design_studio.core.kicad import plan_netlist_import as plan_netlist
from harness_design_studio.core.library_import import guess_mapping, library_ops, plan_parts_import
from harness_design_studio.core.model import (
    ChangeEntry,
    Connector,
    Part,
    Pin,
    Placement,
    Project,
    Waiver,
    evolve,
)
from harness_design_studio.core.samples import mini3, sat15_full
from harness_design_studio.core.vcs import diff as vdiff
from harness_design_studio.core.vcs.release import plan_submit_review
from harness_design_studio.core.vcs.report import changelog_rows, revision_report

REASON = "Test project: values are placeholders"
RELEASE = [
    "release", "{p}", "W001", "--by", "Ada", "--comment", "First release for the CDR",
    "--accept-placeholders", REASON, "--accept-unapproved-parts", REASON,
]  # fmt: skip


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str]:
    rc = main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out + cap.err


@pytest.fixture(scope="module")
def _exported_once(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("m5") / "p"
    save_project(sat15_full(), root)
    assert main(["export", str(root)]) == 0
    return root


@pytest.fixture
def exported(_exported_once: Path, tmp_path: Path) -> Path:
    dest = tmp_path / "p"
    shutil.copytree(_exported_once, dest, symlinks=True)
    return dest


def release_args(p: Path, *extra: str) -> list[str]:
    return [a.replace("{p}", str(p)) for a in RELEASE] + list(extra)


@pytest.fixture
def released(exported: Path, capsys: pytest.CaptureFixture[str]) -> Path:
    rc, text = run(capsys, *release_args(exported))
    assert rc == 0, text
    return exported


def netlist_xml(pins: dict[str, str], ref: str = "J1", fields: str = "") -> bytes:
    nets = "".join(
        f'<net code="{k}" name="{net}"><node ref="{ref}" pin="{n}"/></net>'
        for k, (n, net) in enumerate(pins.items(), start=1)
    )
    return (
        f'<export version="E"><components><comp ref="{ref}"><fields>{fields}</fields></comp>'
        f"</components><nets>{nets}</nets></export>"
    ).encode()


OBC_FIELDS = (
    '<field name="HarnessConnector">OBC-J01</field><field name="HarnessPart">EX-MICROD-9-F</field>'
)


def _pins(plan: NetlistPlan) -> dict[str, Pin]:
    op = plan.ops[0]
    assert isinstance(op, Put) and isinstance(op.obj, Connector)
    return {x.id: x for x in op.obj.pins}


def obc_project() -> Project:
    p = mini3()
    p.connectors["OBC-J01"] = evolve(p.connectors["OBC-J01"], part_id="EX-MICROD-9-F")
    return p


# ---- E-6: data commands and the release lock -----------------------------------------------------


def test_a_data_command_blocked_by_a_release_says_so_in_the_preview_and_the_real_run(
    released: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    f = tmp_path / "bat.net"
    f.write_bytes(
        netlist_xml(
            {"1": "/RTN", "2": "/PWR"},
            fields='<field name="HarnessConnector">BAT1-J01</field>'
            '<field name="HarnessPart">EX-MICROD-9-F</field>',
        )
    )
    base = ["import-netlist", str(released), str(f), "--unit", "BAT1"]
    rc, text = run(capsys, *base, "--dry-run")
    assert rc == 1 and "W001" in text and "released" in text and "blocked" in text.lower(), text
    rc, text = run(capsys, *base)
    assert rc == 1 and "W001" in text and "released" in text, text
    pins = {x.id: x.signal for x in load_project(released).project.connectors["BAT1-J01"].pins}
    assert pins["1"] == "PWR"


# ---- E-7: netlist import and pins --------------------------------------------------------------


def test_a_locked_pin_is_skipped_with_a_warning() -> None:
    p = obc_project()
    box = p.connectors["OBC-J01"]
    pins = [evolve(x, locked=True, signal="MINE") if x.id == "1" else x for x in box.pins]
    apply_ops(p, [Put("connectors", evolve(box, pins=pins))])
    n = parse_netlist(netlist_xml({"1": "/OTHER", "2": "/B"}, fields=OBC_FIELDS))
    plan = plan_netlist(p, n, "OBC")
    assert plan.rows[0].ok
    new = _pins(plan)
    assert (new["1"].signal, new["1"].locked, new["1"].fixed) == ("MINE", True, False)
    assert new["2"].signal == "B"
    assert any("pin 1" in w and "locked" in w for w in plan.warnings)


def test_a_cleared_signal_clears_the_interface_too() -> None:
    p = obc_project()
    box = p.connectors["OBC-J01"]
    pins = [evolve(x, signal="PWR", interface_id="IF-001") if x.id == "1" else x for x in box.pins]
    apply_ops(p, [Put("connectors", evolve(box, pins=pins))])
    n = parse_netlist(netlist_xml({"1": "Net-(J1-Pad1)"}, fields=OBC_FIELDS))
    plan = plan_netlist(p, n, "OBC")
    new = _pins(plan)
    assert new["1"].signal is None and new["1"].interface_id is None and not new["1"].fixed


# ---- E-8: compare ----------------------------------------------------------------------------------


def _changed_kinds(a: Project, b: Project) -> set[str]:
    return {c.kind for c in vdiff.diff_projects(a, b).changes}


def test_compare_sees_waivers_name_zones_library_and_layout() -> None:
    a = mini3()
    assert vdiff.diff_projects(a, edit.clone_with(a, [])).empty
    b = edit.clone_with(
        a,
        [
            Put(
                "waivers",
                Waiver(id="r.x", rule="r", object_id="x", justification="a long enough reason"),
            )
        ],
    )
    assert "waiver" in _changed_kinds(a, b)
    c = edit.clone_with(a, [])
    c.meta = evolve(c.meta, name="Another name")
    assert "project" in _changed_kinds(a, c)
    d = edit.clone_with(a, [])
    d.zones = [*d.zones, "Far zone"]
    assert "zones" in _changed_kinds(a, d)
    e = edit.clone_with(a, [])
    e.library_info = evolve(e.library_info, version="99")
    assert "library" in _changed_kinds(a, e)
    f = edit.clone_with(a, [])
    uid = next(iter(f.units))
    f.placements = {uid: Placement(id=uid, x=1.0, y=2.0)}
    assert "placement" in _changed_kinds(a, f)


def test_compare_command_says_what_it_does_not_compare(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(mini3(), tmp_path / "a")
    save_project(mini3(), tmp_path / "b")
    rc, text = run(capsys, "compare", str(tmp_path / "a"), str(tmp_path / "b"))
    assert rc == 0 and "No differences" in text and "Not compared" in text


# ---- E-9: Ctrl-C --------------------------------------------------------------------------------


def test_ctrl_c_is_a_message_and_exit_130(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    save_project(mini3(), tmp_path / "p")

    def boom(_args: Any) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr("harness_design_studio.cli.main._dispatch", boom)
    rc, text = run(capsys, "validate", str(tmp_path / "p"))
    assert rc == 130 and "interrupted" in text and "Traceback" not in text


# ---- E-10: release and the outputs folder ----------------------------------------------------------


def test_a_linked_outputs_folder_blocks_the_release_before_anything_is_saved(
    exported: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    real = tmp_path / "elsewhere"
    shutil.move(str(exported / "outputs"), str(real))
    (exported / "outputs").symlink_to(real, target_is_directory=True)
    rc, text = run(capsys, *release_args(exported))
    assert rc == 1 and "outputs_linked" in text, text
    assert not load_project(exported).project.baselines
    assert not load_project(exported).project.changelog


def test_a_failed_restamp_says_the_release_was_recorded(
    exported: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def full_disk(*_a: object, **_k: object) -> None:
        raise SaveError("The outputs could not be written (No space left on device).")

    monkeypatch.setattr("harness_design_studio.core.outputs.build.write_outputs", full_disk)
    rc, text = run(capsys, *release_args(exported))
    assert rc != 0 and "release was recorded" in text and "harness export" in text
    assert "W001.A" in load_project(exported).project.baselines


# ---- E-11, K-3: the library fields ------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,word",
    [
        ({"version": ""}, "version"),
        ({"name": ""}, "name"),
        ({"name": "x" * 500}, "name"),
        ({"source": "a\x01b"}, "source"),
        ({"date": "31.12.2026"}, "date"),
        ({"date": "20260101"}, "date"),
        ({"date": "2026-W02-3"}, "date"),
        ({"date": "2026-W02"}, "date"),
        ({"date": "２０２６-01-01"}, "date"),
    ],
)
def test_only_dates_give_the_date_message(kwargs: dict[str, str], word: str) -> None:
    with pytest.raises(ImportError_) as exc:
        library_ops(mini3(), **kwargs)
    text = str(exc.value).lower()
    assert word in text and ("YYYY-MM-DD" in str(exc.value)) == (word == "date")


# ---- E-12: import-parts --------------------------------------------------------------------------------


def _parts(rows: list[list[str]], header: str = "id,category,approval,mass,pins") -> Any:
    table = [header.split(","), *rows]
    return plan_parts_import(mini3(), table, guess_mapping(table[0]), approved=["yes"])


def test_a_part_id_twice_in_the_file_is_an_error_row() -> None:
    plan = _parts([["P-1", "connector", "yes", "1", "9"], ["P-1", "connector", "no", "2", "9"]])
    assert [r.ok for r in plan.rows] == [True, False]
    assert "already in row 2" in plan.rows[1].message


@pytest.mark.parametrize("bad", ["1e3", "1_0", "1,234", "-0", "1e23", "inf", "nan", "٣"])
def test_strange_numbers_are_refused(bad: str) -> None:
    plan = _parts([["P-1", "wire", "yes", bad, ""]])
    assert not plan.rows[0].ok and "mass" in plan.rows[0].message.lower()
    if bad == "1,234":
        assert "point" in plan.rows[0].message


def test_plain_numbers_and_decimal_commas_are_read() -> None:
    plan = _parts([["P-1", "wire", "yes", "12.5", ""], ["P-2", "wire", "yes", "1,5", ""]])
    assert [r.ok for r in plan.rows] == [True, True]
    masses = {
        op.obj.id: op.obj.mass_g
        for op in plan.ops
        if isinstance(op, Put) and isinstance(op.obj, Part)
    }
    assert masses == {"P-1": 12.5, "P-2": 1.5}


@pytest.mark.parametrize("bad", ["1e1", "99999999", "1001", "0", "-3", "2.5"])
def test_pin_counts_are_whole_numbers_up_to_1000(bad: str) -> None:
    plan = _parts([["P-1", "connector", "yes", "", bad]])
    assert not plan.rows[0].ok and "1000" in plan.rows[0].message
    assert _parts([["P-1", "connector", "yes", "", "1000"]]).rows[0].ok


def test_a_bad_description_names_the_field() -> None:
    header = "id,category,approval,description"
    for bad in ("x" * 300, "a\x01b"):
        plan = _parts([["P-1", "connector", "yes", bad]], header)
        assert not plan.rows[0].ok and "Description" in plan.rows[0].message
        assert "validation error" not in plan.rows[0].message


def test_two_approval_columns_are_refused() -> None:
    with pytest.raises(ImportError_):
        guess_mapping(["id", "category", "status", "approved"])


# ---- E-14: names and comments ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "opt,value",
    [("--by", "a\x01b"), ("--by", "x" * 201), ("--by", "line\nbreak"), ("--checker", "a\x01b"),
     ("--comment", "a long comment\x01 with a control character")],
)  # fmt: skip
def test_bad_names_and_comments_are_blockers_that_name_the_option(
    exported: Path, capsys: pytest.CaptureFixture[str], opt: str, value: str
) -> None:
    args = release_args(exported)
    if opt == "--checker":
        args += ["--checker", value]
    else:
        args[args.index(opt) + 1] = value
    rc, text = run(capsys, *args)
    assert rc == 1 and opt in text and "Traceback" not in text, text
    assert not load_project(exported).project.baselines


def test_a_comment_with_a_line_break_cannot_fake_a_log_entry() -> None:
    p = sat15_full()
    entry = ChangeEntry(
        id="C0001", harness_id="W001", revision="A", kind="release", by="Ada",
        when="2026-03-01", comment="fine\n- 2026-03-02, Boss: revision A released",
    )  # fmt: skip
    p.changelog = {"C0001": entry}
    report = revision_report(p, "stamp")
    assert not any(line.startswith("- 2026-03-02, Boss") for line in report.splitlines())
    assert all("\n" not in c for row in changelog_rows(p)[1:] for c in row)


# ---- E-15: the date ------------------------------------------------------------------------------------------


def test_an_empty_date_is_an_error_not_today(
    exported: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, text = run(capsys, *release_args(exported, "--date", ""))
    assert rc == 1 and "bad_date" in text
    plan = plan_submit_review(sat15_full(), "W001", by="Ada", when="")
    assert {b.code for b in plan.blockers} == {"bad_date"}


# ---- E-16: KiCad XML written in UTF-16 or UTF-32 without a byte order mark ----------------------------------


@pytest.mark.parametrize("codec", ["utf-16-le", "utf-16-be", "utf-32-le", "utf-32-be", "utf-16"])
def test_the_entity_guard_also_covers_wide_encodings(codec: str) -> None:
    text = '<?xml version="1.0"?><!DOCTYPE export [<!ENTITY a "bbbb">]><export>&a;</export>'
    with pytest.raises(NetlistError, match="DOCTYPE"):
        parse_netlist(text.encode(codec))


def test_a_wide_netlist_without_a_doctype_is_still_read() -> None:
    data = netlist_xml({"1": "/A"}, fields=OBC_FIELDS).decode()
    for codec in ("utf-16-le", "utf-32-be"):
        assert "J1" in parse_netlist(data.encode(codec)).components


# ---- K-4, E-17: a closed pipe ---------------------------------------------------------------------------------


class ClosedPipe:
    """A stdout whose reader went away after the first line."""

    def __init__(self) -> None:
        self.writes = 0

    def write(self, text: str) -> int:
        self.writes += 1
        if self.writes > 2:
            raise BrokenPipeError(32, "Broken pipe")
        return len(text)

    def flush(self) -> None:
        if self.writes > 2:
            raise BrokenPipeError(32, "Broken pipe")

    def isatty(self) -> bool:
        return False


def test_generate_is_saved_when_the_reader_closes_the_pipe(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    save_project(mini3(), tmp_path / "p")
    monkeypatch.setattr(sys, "stdout", ClosedPipe())
    rc = main(["generate", str(tmp_path / "p")])
    err = capsys.readouterr().err
    assert rc == 0 and "file or folder" not in err and "Traceback" not in err
    assert load_project(tmp_path / "p").project.harnesses


# ---- K-12: a missing netlist --------------------------------------------------------------------------------------


def test_a_missing_netlist_is_not_called_irregular(tmp_path: Path) -> None:
    with pytest.raises(NetlistError, match="could not be read"):
        read_netlist(tmp_path / "nofile.net")
    with pytest.raises(NetlistError, match="regular file"):
        read_netlist(tmp_path)


# ---- K-14: messages ---------------------------------------------------------------------------------------------


def test_help_texts_do_not_point_at_repository_files(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for cmd in ("import-lengths", "import-netlist"):
        with pytest.raises(SystemExit):
            from harness_design_studio.cli.main import build_parser

            build_parser().parse_args([cmd, "--help"])
        assert "docs/" not in capsys.readouterr().out


def test_release_blockers_name_the_options_that_accept_them(
    exported: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rc, text = run(
        capsys, "release", str(exported), "W001", "--by", "Ada", "--comment", "a long comment"
    )
    assert rc == 1 and "--accept-placeholders" in text and "--accept-unapproved-parts" in text


# ---- C-8: the closing message of --apply-profile ---------------------------------------------------------------


def test_apply_profile_names_the_files_that_are_placeholders(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(mini3(), tmp_path / "p")
    rc, text = run(capsys, "config", str(tmp_path / "p"), "--apply-profile", "ecss-q-st-30-11c")
    names = load_project(tmp_path / "p").project.placeholder_configs()
    assert names
    closing = next(line for line in text.splitlines() if line.startswith("Profile "))
    after = text[text.index(closing) :]
    assert all(f"{n}.json" in after for n in names)
