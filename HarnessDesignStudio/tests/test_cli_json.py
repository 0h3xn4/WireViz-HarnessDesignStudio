"""R11: `--json` on every command that has a result in data form.

What is checked: every command takes the option and has its document described (`SHAPES`, which
`docs/CLI.md` is made from); each document has exactly the keys the reference lists; the exit code
is the one the command has without the option; the text of a command without the option is not
changed; the document is the same twice, holds no absolute path, and is the same data the Python
interface (`harness_design_studio.api`) gives."""

import json
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pytest

from harness_design_studio import api
from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import build_parser, main
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.samples import mini3, sat15
from tests.test_edit_device import device
from tests.test_kicad import FIXTURE


def commands() -> dict[str, Any]:
    parser = build_parser()
    action = next(a for a in parser._actions if a.dest == "command")
    return dict(action.choices or {})


def run(
    capsys: pytest.CaptureFixture[str], *argv: str, rc: int = 0, tmp: Path | None = None
) -> dict[str, Any]:
    """Run a command with --json, check the exit code, and return its document."""
    assert main([*argv, "--json"]) == rc, argv
    got = capsys.readouterr()
    doc = json.loads(got.out)
    assert isinstance(doc, dict) and list(doc)[0] == "ok" and doc["ok"] is (rc == 0), argv
    if tmp is not None:
        assert str(tmp) not in got.out, "the document holds an absolute path"
    return doc


def keys(doc: dict[str, Any], shape: str) -> None:
    assert list(doc) == list(SHAPES[shape]), shape


@pytest.fixture
def small(tmp_path: Path) -> Path:
    """first-steps, generated and exported."""
    folder = tmp_path / "small"
    api.create_project(folder, "first-steps")
    assert api.generate(folder).ok and api.export(folder).ok
    return folder


# ---- the options and the reference -----------------------------------------------------------------


def test_every_command_takes_json_and_the_reference_describes_each() -> None:
    cmds = commands()
    for name, parser in cmds.items():
        options = {o for a in parser._actions for o in a.option_strings}
        assert "--json" in options, name
    described = {k.split()[0] for k in SHAPES}
    assert described == set(cmds), sorted(described ^ set(cmds))
    for shape, found in SHAPES.items():
        assert found[0] == "ok" or shape == "explain --all", shape


def test_the_json_section_of_the_reference_lists_every_shape() -> None:
    text = (Path(__file__).resolve().parents[1] / "docs" / "CLI.md").read_text(encoding="utf-8")
    for shape, found in SHAPES.items():
        assert f"`{shape}`" in text and ", ".join(f"`{k}`" for k in found) in text, shape


# ---- start, check, generate, export ----------------------------------------------------------------


def test_new_templates_schema_and_migrate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc = run(capsys, "new", str(tmp_path / "n"), "--template", "first-steps", tmp=tmp_path)
    keys(doc, "new")
    assert (doc["template"], doc["devices"], doc["interfaces"]) == ("first-steps", 3, 2)
    doc = run(capsys, "new", "--list", tmp=tmp_path)
    keys(doc, "new --list")
    assert [t["name"] for t in doc["templates"]] == [t.name for t in api.list_templates()]
    doc = run(capsys, "templates", str(tmp_path / "t"), tmp=tmp_path)
    keys(doc, "templates")
    assert doc["count"] == len(doc["files"]) and "README.md" in doc["files"]
    assert doc["files"] == sorted(doc["files"])
    doc = run(capsys, "schema", str(tmp_path / "s"), tmp=tmp_path)
    keys(doc, "schema")
    assert doc["files"][-1] == "editor-settings.json" and doc["count"] == len(doc["files"]) - 1
    doc = run(capsys, "migrate", str(tmp_path / "n"), tmp=tmp_path)
    keys(doc, "migrate")
    assert doc["migrated"] is False


def test_nothing_is_printed_when_the_command_cannot_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", str(tmp_path / "nowhere"), "--json"]) == 2
    got = capsys.readouterr()
    assert got.out == "" and "error" in got.err
    assert main(["new", "--json"]) == 2 and capsys.readouterr().out == ""


def test_validate_check_and_drc_equal_the_api_and_keep_their_exit_codes(
    small: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for command in ("validate", "check"):
        doc = run(capsys, command, str(small), tmp=small.parent)
        keys(doc, command)
        assert doc == api.validate(small, merge_check=command == "check").to_dict()
        assert main([command, str(small)]) == 0 and "0 error(s)" in capsys.readouterr().out
    doc = run(capsys, "drc", str(small), tmp=small.parent)
    keys(doc, "drc")
    assert doc == api.run_checks(small).to_dict()
    assert doc["rules_run"] == len(api.list_rules()) == 39
    ids = [f["id"] for f in doc["findings"]]
    assert ids and all(f["rule"] and f["why"] and f["severity"] for f in doc["findings"])
    order = [{"error": 0, "warning": 1, "info": 2}[f["severity"]] for f in doc["findings"]]
    assert order == sorted(order)


def test_a_project_with_an_error_fails_in_both_forms(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "bad"
    api.create_project(folder, "first-steps")
    victim = folder / "logical" / "interfaces" / "avionics.json"
    data = json.loads(victim.read_text())
    data["interfaces"][0]["endpoints"][0]["unit_id"] = "NOPE"  # an interface that ends nowhere
    victim.write_text(json.dumps(data))
    assert main(["validate", str(folder)]) == 1
    text = capsys.readouterr().out
    doc = run(capsys, "validate", str(folder), rc=1, tmp=tmp_path)
    assert doc["errors"] >= 1 and f"{doc['errors']} error(s)" in text
    assert any(i["severity"] == "error" for i in doc["issues"])
    # every other command refuses the damaged project in both forms
    assert main(["drc", str(folder), "--json"]) == main(["drc", str(folder)]) == 2
    assert capsys.readouterr().out == ""


def test_generate_in_both_forms(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text_project, json_project = tmp_path / "a", tmp_path / "b"
    for folder in (text_project, json_project):
        api.create_project(folder, "first-steps")
    assert main(["generate", str(text_project)]) == 0
    capsys.readouterr()
    doc = run(capsys, "generate", str(json_project), tmp=tmp_path)
    keys(doc, "generate")
    assert doc["saved"] and doc["added"] == sorted(doc["added"]) and doc["added"]
    assert model_hash(load_project(text_project).project) == model_hash(
        load_project(json_project).project
    )
    again = run(capsys, "generate", str(json_project))
    assert again["added"] == [] and again["unchanged"] == doc["added"]


def test_generate_that_finds_an_error_prints_its_document_and_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "p"
    api.create_project(folder, "flatsat")
    api.set_config(folder, "derating", "bundle_derating", 0.5)  # no gauge fits
    before = model_hash(load_project(folder).project)
    assert main(["generate", str(folder)]) == 1
    text = capsys.readouterr()
    assert "Not saved" in text.err
    doc = run(capsys, "generate", str(folder), rc=1)
    assert doc["ok"] is False and doc["saved"] is False
    assert any(f["severity"] == "error" for f in doc["findings"])
    assert model_hash(load_project(folder).project) == before
    result = api.generate(folder)
    assert result.to_dict() == doc


def test_verify_and_export(small: Path, capsys: pytest.CaptureFixture[str]) -> None:
    doc = run(capsys, "verify", str(small), tmp=small.parent)
    keys(doc, "verify")
    assert doc == api.verify(small).to_dict() and doc["wires_checked"] == 6
    doc = run(capsys, "verify", str(small), "--outputs", tmp=small.parent)
    assert doc == api.verify(small, outputs=True).to_dict()
    fresh = small.parent / "fresh"
    api.create_project(fresh, "first-steps")
    assert main(["verify", str(fresh), "--outputs", "--json"]) == 1  # no outputs folder yet
    assert capsys.readouterr().out == ""
    # a wire missing from the harnesses fails in both forms, with the same exit code
    assert (
        main(["verify", str(fresh)]) == 1 and "hint: there are no wires" in capsys.readouterr().out
    )
    doc = run(capsys, "verify", str(fresh), rc=1)
    assert doc["wires_checked"] == 0 and doc["issues"]

    doc = run(capsys, "export", str(small), tmp=small.parent)
    keys(doc, "export")
    assert doc["written"] and doc["blocked"] == "" and doc["file_count"] == len(doc["files"])
    assert [f["path"] for f in doc["files"]] == sorted(f["path"] for f in doc["files"])
    manifest = json.loads((small / "outputs" / "manifest.json").read_text())
    assert {f["path"]: f["sha256"] for f in manifest["files"]} == {
        f["path"]: f["sha256"] for f in doc["files"]
    }
    assert doc["model_hash"] == manifest["model_hash"][:12]
    assert doc == api.export(small).to_dict()


def test_export_into_another_folder(small: Path, capsys: pytest.CaptureFixture[str]) -> None:
    default = {p.relative_to(small / "outputs"): p.read_bytes() for p in (small / "outputs").rglob("*") if p.is_file()}  # fmt: skip
    shutil.rmtree(small / "outputs")
    elsewhere = small.parent / "elsewhere" / "deep"
    assert main(["export", str(small), "--out", str(elsewhere)]) == 0
    text = capsys.readouterr().out
    assert f"files written to {elsewhere} (model " in text
    assert not (small / "outputs").exists()  # nothing went to the default place
    got = {p.relative_to(elsewhere): p.read_bytes() for p in elsewhere.rglob("*") if p.is_file()}
    assert got == default  # byte for byte what the default export writes
    result = api.export(small, small.parent / "api-out")
    assert result.written and (small.parent / "api-out" / "manifest.json").is_file()
    doc = run(capsys, "export", str(small), "--out", str(small.parent / "again"))
    assert doc["files"] == result.to_dict()["files"]
    assert str(small.parent) not in json.dumps(doc)


def test_export_without_harnesses_prints_the_refusal(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "empty"
    api.create_project(folder, "first-steps")
    assert main(["export", str(folder)]) == 1
    assert "no harnesses to export" in capsys.readouterr().err
    doc = run(capsys, "export", str(folder), rc=1)
    assert (doc["written"], doc["blocked"], doc["files"]) == (False, "nothing_to_export", [])
    assert not (folder / "outputs").exists()


def test_explain_all_prints_the_summary_and_writes_the_same_files(
    small: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = small.parent / "d"
    doc = run(capsys, "explain", str(small), "--all", "--out", str(out), tmp=small.parent)
    keys(doc, "explain --all")
    assert doc["files"] == ["derivations.json", "derivations.csv"]
    other = small.parent / "e"
    written = api.write_derivations(small, other)
    assert doc["count"] == written.count and doc["without_value"] == written.without_value
    for name in doc["files"]:
        assert (out / name).read_bytes() == (other / name).read_bytes()
    # the form of one object stays a list, as before
    assert main(["explain", str(small), "W001", "--json"]) == 0
    assert isinstance(json.loads(capsys.readouterr().out), list)


# ---- configuration and library ----------------------------------------------------------------------


def test_config_and_library(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    save_project(sat15(), tmp_path / "p")
    p = str(tmp_path / "p")
    doc = run(capsys, "config", p, rc=1, tmp=tmp_path)
    keys(doc, "config")
    assert doc == {**api.get_config(p).to_dict(), "changes": []} | {"ok": False}
    assert doc["set_count"] == 0 and doc["total"] == 17 and not doc["problems"]
    first = doc["values"][0]
    assert (first["file"], first["key"], first["missing"], first["unit"]) == (
        "derating", "ampacity_a_by_awg", True, "A",
    )  # fmt: skip
    assert [v["optional"] for v in doc["values"]].count(False) == 17
    doc = run(capsys, "config", p, "--apply-profile", "ecss-q-st-30-11c", rc=1)
    assert any(c.startswith("set derating.") for c in doc["changes"])
    assert doc["set_count"] > 0
    text_project = tmp_path / "t"
    save_project(sat15(), text_project)
    assert main(["config", str(text_project), "--apply-profile", "ecss-q-st-30-11c"]) == 1
    printed = capsys.readouterr().out
    assert all(change in printed for change in doc["changes"])  # the same lines, as data

    doc = run(capsys, "library", p, "--library-version", "9", tmp=tmp_path)
    keys(doc, "library")
    assert (doc["version"], doc["changed"]) == ("9", True)
    assert run(capsys, "library", p)["changed"] is False


def test_a_config_that_changes_nothing_prints_no_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(sat15(), tmp_path / "p")
    assert main(["config", str(tmp_path / "p"), "--counterparts", "TX", "--json"]) == 1
    got = capsys.readouterr()
    assert got.out == "" and "Nothing was changed" in got.err


# ---- imports and exports of data --------------------------------------------------------------------


def test_import_parts_and_lengths(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    save_project(sat15(), tmp_path / "p")
    p = str(tmp_path / "p")
    f = tmp_path / "parts.csv"
    f.write_text("Part number,Category,Status\nNEW-1,connector,A\nNEW-2,wire,X\n")
    doc = run(capsys, "import-parts", p, str(f), "--approved", "A", rc=1, tmp=tmp_path)
    keys(doc, "import-parts")
    assert doc["problems"] == 1 and doc["changed"] is False
    assert [r["ok"] for r in doc["rows"]] == [True, False]
    doc = run(capsys, "import-parts", p, str(f), "--approved", "A", "--rejected", "X", "--dry-run")
    assert doc["dry_run"] is True and doc["changed"] is False and doc["ready"] == 2
    assert "NEW-1" not in load_project(tmp_path / "p").project.parts
    doc = run(capsys, "import-parts", p, str(f), "--approved", "A", "--rejected", "X")
    assert doc["changed"] is True and "NEW-1" in load_project(tmp_path / "p").project.parts
    assert (
        run(capsys, "import-parts", p, str(f), "--approved", "A", "--rejected", "X")["changed"]
        is False
    )  # already up to date

    from tests.test_data_import import project_with_segments

    save_project(project_with_segments(), tmp_path / "q")
    q = str(tmp_path / "q")
    g = tmp_path / "len.csv"
    g.write_text("harness,segment,length\nW010,W010-L1,800\nW010,NOPE,5\n")
    doc = run(capsys, "import-lengths", q, str(g), rc=1)
    keys(doc, "import-lengths")
    assert doc["problems"] == 1 and doc["ready"] == 1 and doc["changed"] is False
    g.write_text("harness,segment,length\nW010,W010-L1,800\n")
    doc = run(capsys, "import-lengths", q, str(g))
    assert doc["changed"] is True and doc["rows"] == [{"row": 2, "ok": True, "message": ""}]


def test_import_build_data_netlist_and_pinout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = sat15()
    from harness_design_studio.core.generate.engine import generate_project

    generate_project(project)
    wire = next(iter(project.harnesses.values())).wires[0].id
    save_project(project, tmp_path / "p")
    f = tmp_path / "strip.csv"
    f.write_text(f"Wire,Strip A (mm)\n{wire},6\n")
    doc = run(capsys, "import-build-data", str(tmp_path / "p"), str(f), "--dry-run", tmp=tmp_path)
    keys(doc, "import-build-data")
    assert doc["counts"] == {"added": 1, "changed": 0, "unchanged": 0, "refused": 0}
    assert doc["rows"][0]["target"] == wire and doc["changed"] is False
    assert run(capsys, "import-build-data", str(tmp_path / "p"), str(f))["changed"] is True

    save_project(mini3(), tmp_path / "m")
    base = ["import-netlist", str(tmp_path / "m"), str(FIXTURE), "--unit", "OBC", "--ref", "J1"]
    doc = run(capsys, *base, "--dry-run", tmp=tmp_path)
    keys(doc, "import-netlist")
    assert doc["rows"][0]["connector"] == "TST1-J01" and doc["rows"][0]["action"] == "added"
    assert doc["changed"] is False and "TST1-J01" not in load_project(tmp_path / "m").project.connectors  # fmt: skip
    assert run(capsys, *base)["changed"] is True

    save_project(device(), tmp_path / "d")
    csv = tmp_path / "gyro.csv"
    csv.write_text("Connector,Pin,Signal,Mode,Remarks\nJ1,A1,PWR,fixed,x\nJ1,A2,RTN,fixed,\n")
    base = ["import-pinout", str(tmp_path / "d"), str(csv), "--unit", "GYRO1"]
    doc = run(capsys, *base, "--default-part", "MY-HD-6-F", "--dry-run", tmp=tmp_path)
    keys(doc, "import-pinout")
    assert doc["connectors"] == [{"connector": "GYRO1-J01", "action": "added", "pins": 2}]
    assert doc["pins"] == 2 and doc["changed"] is False
    assert any("Remarks" in w for w in doc["warnings"])
    assert run(capsys, *base, "--default-part", "MY-HD-6-F")["changed"] is True

    doc = run(capsys, "export-pinout", str(tmp_path / "d"), "--device", "GYRO1", tmp=tmp_path)
    keys(doc, "export-pinout")
    assert doc["pin_rows"] == len(doc["rows"]) and doc["written"] is False
    assert {"Connector", "Pin", "Signal"} <= set(doc["columns"])
    out = tmp_path / "gyro.tsv"
    assert (
        run(capsys, "export-pinout", str(tmp_path / "d"), "--device", "GYRO1", "-o", str(out))[
            "written"
        ]
        is True
        and out.is_file()
    )


def test_export_pinout_that_cannot_write_prints_no_document(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    save_project(device(), tmp_path / "d")
    csv = tmp_path / "gyro.csv"
    csv.write_text("Connector,Pin,Signal\nJ1,A1,PWR\n")
    assert main(["import-pinout", str(tmp_path / "d"), str(csv), "--unit", "GYRO1", "--default-part", "MY-HD-6-F"]) == 0  # fmt: skip
    capsys.readouterr()
    target = tmp_path / "nowhere" / "gyro.csv"
    assert main(["export-pinout", str(tmp_path / "d"), "--device", "GYRO1", "-o", str(target), "--json"]) == 2  # fmt: skip
    got = capsys.readouterr()
    assert got.out == "" and "does not exist" in got.err and not target.exists()


def test_device_and_subsystem_libraries(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src, dst = tmp_path / "src", tmp_path / "dst"
    api.create_project(src, "small-satellite")
    api.create_project(dst, "blank")
    units = sorted(load_project(src).project.units)[:2]
    lib = tmp_path / "devices.json"
    doc = run(capsys, "export-devices", str(src), str(lib), "--device", units[0], tmp=tmp_path)
    keys(doc, "export-devices")
    assert doc["devices"] == 1 and doc["connectors"] >= 1
    doc = run(capsys, "import-devices", str(dst), str(lib), "--list", tmp=tmp_path)
    keys(doc, "import-devices --list")
    assert doc["devices"][0]["id"] == units[0]
    doc = run(capsys, "import-devices", str(dst), str(lib), "--dry-run")
    keys(doc, "import-devices")
    assert doc["rows"][0]["new_id"] == units[0] and doc["changed"] is False
    assert run(capsys, "import-devices", str(dst), str(lib))["changed"] is True
    again = run(capsys, "import-devices", str(dst), str(lib))
    assert again["rows"][0]["new_id"] == f"{units[0]}-2"  # a taken ID gets the next free one

    sub = tmp_path / "sub.json"
    doc = run(capsys, "export-subsystem", str(src), str(sub), "--device", units[0], "--name", "S")
    keys(doc, "export-subsystem")
    assert (doc["name"], doc["devices"]) == ("S", 1)
    doc = run(capsys, "import-subsystem", str(dst), str(sub), "--show", tmp=tmp_path)
    keys(doc, "import-subsystem --show")
    assert doc["device_list"][0]["id"] == units[0]
    other = tmp_path / "other"
    api.create_project(other, "blank")
    doc = run(capsys, "import-subsystem", str(other), str(sub), "--dry-run")
    keys(doc, "import-subsystem")
    assert doc["name"] == "S" and doc["changed"] is False
    assert run(capsys, "import-subsystem", str(other), str(sub))["changed"] is True


# ---- merge-fix and change control ---------------------------------------------------------------------


def test_merge_fix_without_a_conflict(small: Path, capsys: pytest.CaptureFixture[str]) -> None:
    doc = run(capsys, "merge-fix", str(small), tmp=small.parent)
    keys(doc, "merge-fix")
    assert (doc["result"], doc["conflicts"], doc["generate"], doc["check"]) == (
        "nothing_to_fix", [], None, None,
    )  # fmt: skip


def test_merge_fix_with_a_conflict_in_the_record(
    small: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = small / "generated" / "generation.json"
    ours = record.read_text()
    record.write_text(f"<<<<<<< HEAD\n{ours}=======\n{ours}>>>>>>> other\n")
    other = small / "logical" / "units"
    marker = next(other.glob("*.json"))
    keep = marker.read_text()
    marker.write_text(f"<<<<<<< HEAD\n{keep}=======\n{keep}>>>>>>> other\n")
    assert main(["merge-fix", str(small)]) == 1  # another file in conflict: refused
    capsys.readouterr()
    doc = run(capsys, "merge-fix", str(small), rc=1, tmp=small.parent)
    assert doc["result"] == "refused" and doc["conflicts"] == [marker.relative_to(small).as_posix()]
    marker.write_text(keep)
    doc = run(capsys, "merge-fix", str(small), tmp=small.parent)
    assert doc["result"] == "fixed" and doc["generate"]["ok"] and doc["check"]["ok"]
    assert list(doc["generate"]) == list(SHAPES["generate"])
    assert list(doc["check"]) == list(SHAPES["check"])


@pytest.mark.slow
def test_change_control_commands(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from tests.test_change_control import REASON, WHEN, full, releasable

    project = full()
    hid = releasable(project)
    folder = tmp_path / "p"
    save_project(project, folder)
    args = [str(folder), hid]
    assert main(["export", str(folder)]) == 0
    capsys.readouterr()
    who = ["--by", "Ada", "--comment", "First release for CDR", "--date", WHEN]
    doc = run(capsys, "release", *args, *who, rc=1, tmp=tmp_path)  # placeholders, no reason
    keys(doc, "release")
    assert doc["blockers"] and doc["outputs"] is None and doc["by"] == "Ada"
    assert {"code", "message", "about"} == set(doc["blockers"][0])
    doc = run(
        capsys, "release", *args, *who, "--checker", "Bob", "--accept-placeholders", REASON,
        "--accept-unapproved-parts", REASON, tmp=tmp_path,
    )  # fmt: skip
    assert doc["blockers"] == [] and isinstance(doc["outputs"], int) and doc["outputs"] > 0
    assert doc["action"].startswith("Release")

    doc = run(capsys, "log", str(folder), tmp=tmp_path)
    keys(doc, "log")
    assert doc["harness"] is None and doc["entries"][0]["event"] == "released"
    assert set(doc["entries"][0]) == {
        "entry",
        "harness",
        "revision",
        "event",
        "by",
        "date",
        "comment",
    }
    assert run(capsys, "log", str(folder), hid)["harness"] == hid
    assert main(["log", str(folder), "NOPE", "--json"]) == 2 and capsys.readouterr().out == ""

    doc = run(capsys, "revise", *args, "--by", "Ada", "--comment", "Rework for the build",
              "--date", "2026-04-01")  # fmt: skip
    keys(doc, "revise")
    doc = run(capsys, "diff", *args, tmp=tmp_path)
    keys(doc, "diff")
    assert (doc["from"], doc["to"], doc["harness"]) == ("A", "working", hid)
    assert any(f["name"] == "revision" for c in doc["changes"] for f in c["fields"])
    assert run(capsys, "diff", *args, "--from", "A", "--to", "A")["changes"] == []
    assert main(["diff", *args, "--from", "Q", "--json"]) == 2 and capsys.readouterr().out == ""
    doc = run(capsys, "review", *args, "--by", "Ada", "--date", "2026-04-02")
    keys(doc, "review")

    other = tmp_path / "q"
    shutil.copytree(folder, other)
    unit = next((other / "logical" / "units").glob("*.json"))
    unit.write_text(unit.read_text().replace('"name": "', '"name": "Changed ', 1))
    doc = run(capsys, "compare", str(folder), str(other), tmp=tmp_path)
    keys(doc, "compare")
    assert doc["changed"] == 1 and doc["changes"][0]["kind"] == "unit"
    assert doc["not_compared"].startswith("Not compared:")


# ---- the same twice, and no path --------------------------------------------------------------------


def test_the_document_is_the_same_twice_and_has_no_path_or_time(
    small: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first = {}
    for command in ("validate", "drc", "verify", "config", "export"):
        assert main([command, str(small), "--json"]) in (0, 1)
        first[command] = capsys.readouterr().out
    for command, text in first.items():
        assert main([command, str(small), "--json"]) in (0, 1)
        assert capsys.readouterr().out == text, command
        assert str(small.parent) not in text and tempfile.gettempdir() not in text, command
        assert not re.search(r"\b20\d\d-\d\d-\d\d[T ]\d\d:\d\d", text), command
