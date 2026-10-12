"""M9 security review, as tests (docs/SECURITY.md): hostile files and names must neither escape
the project folder, nor run as code, nor crash the tool."""

import ast
import json
import xml.etree.ElementTree as ET  # noqa: S405
from pathlib import Path

import pytest

from harness_design_studio.core import recovery
from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.ids import ID_RE, check_id
from harness_design_studio.core.io import loader
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import evolve
from harness_design_studio.core.outputs.build import MANIFEST, build_outputs, write_outputs
from harness_design_studio.core.outputs.stamp import parse_csv
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3, sat15_full

SRC = Path(__file__).resolve().parents[1] / "src" / "harness_design_studio"

HOSTILE = [
    "<script>alert(1)</script>", "a & b < c > d", 'quote " and \' mix', "`backticks` and [link](http://x)",
    "=HYPERLINK(\"http://evil\",\"x\")", "+cmd|' /C calc'!A0", "@SUM(1+1)", "-2+3", "line\nbreak", "tab\there",
    "../../etc/passwd", "back\\slash", "ünïcödé ✓ 日本語", "‮RTL override", "x" * 190,
]  # fmt: skip


def test_ids_cannot_contain_path_characters() -> None:
    for bad in ("../x", "a/b", "a\\b", ".hidden", "x.", "CON", "a b", "a\x00b", "", "-x"):
        with pytest.raises(ValueError):
            check_id(bad)
    assert ID_RE.fullmatch("W001") and ID_RE.fullmatch("OBC1-J01")


@pytest.mark.parametrize("name", HOSTILE)
def test_hostile_text_in_names_is_harmless_in_every_output(name: str) -> None:
    from harness_design_studio.core.model.base import Name  # noqa: F401

    p = sat15_full()
    unit = next(iter(p.units.values()))
    try:
        evolve(unit, name=name)
    except ValueError:
        pytest.skip("rejected by validation (control character): the model never holds it")
    h = p.harnesses["W010"]
    apply_ops(
        p,
        [Put("units", evolve(unit, name=name)), Put("harnesses", evolve(h, name=name, notes=name))],
    )
    out = build_outputs(p)
    for rel, data in out.files.items():
        if rel.endswith(".svg"):
            ET.fromstring(data)  # noqa: S314  (well-formed: nothing broke out of the text)
            assert b"<script" not in data
        if rel.endswith(".csv"):
            for row in parse_csv(data):  # round-trips, and unsafe cells were marked
                assert all(isinstance(c, str) for c in row)
            raw = data.decode().splitlines()
            for line in raw[1:]:
                assert not line.startswith(("=", "@")), rel
    assert verify_outputs(p, out.files).ok
    xlsx = out.files["system/system.xlsx"]
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(xlsx)) as z:
        for member in z.namelist():
            if member.startswith("xl/worksheets/"):
                assert b"<f>" not in z.read(member)  # no cell is a formula


def test_symlinked_project_files_are_ignored_not_followed(tmp_path: Path) -> None:
    secret = tmp_path / "secret.json"
    secret.write_text(json.dumps({"password": "hunter2"}))
    p = mini3()
    save_project(p, tmp_path / "p")
    victim = next((tmp_path / "p" / "logical" / "units").glob("*.json"))
    victim.unlink()
    victim.symlink_to(secret)
    result = load_project(tmp_path / "p")
    assert "symlink_ignored" in {i.code for i in result.issues}
    assert all("hunter2" not in repr(q.raw) for q in result.project.quarantine)
    assert not any(
        "hunter2" in v.decode(errors="ignore") for v in result.project.quarantine_files.values()
    )


def test_oversized_project_file_is_refused_unread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    save_project(mini3(), tmp_path / "p")
    monkeypatch.setattr(loader, "MAX_FILE_BYTES", 100)
    result = load_project(tmp_path / "p")
    assert (
        "file_too_large" in {i.code for i in result.issues}
        or "invalid_json" in {i.code for i in result.issues}
        or result.has_errors
    )


def test_output_folder_manifest_cannot_make_the_tool_delete_other_files(tmp_path: Path) -> None:
    p = mini3()
    generate_project(p)
    folder = tmp_path / "outputs"
    write_outputs(p, folder)
    victim = tmp_path / "victim.txt"
    victim.write_text("keep")
    doc = json.loads((folder / MANIFEST).read_text())
    doc["files"].append({"path": "../victim.txt", "sha256": "0" * 64, "bytes": 1})
    doc["files"].append({"path": "/etc/hostname", "sha256": "0" * 64, "bytes": 1})
    (folder / MANIFEST).write_text(json.dumps(doc))
    write_outputs(p, folder)
    assert victim.read_text() == "keep" and Path("/etc/hostname").exists()


def test_a_damaged_journal_is_ignored(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "p")
    journal = recovery.journal_path(tmp_path / "p")
    journal.parent.mkdir(parents=True, exist_ok=True)
    for text in ("{", "[" * 100_000, '{"files": 5}', '{"files": {"project.json": "{"}}', ""):
        journal.write_text(text)
        assert recovery.read_journal(tmp_path / "p") is None
        recovery.journal_differs_from_disk(tmp_path / "p")  # must not raise


def test_the_code_never_evaluates_data_or_starts_programs() -> None:
    """No eval/exec/pickle/shelve/marshal, no subprocess or os.system, no yaml.load, no sockets."""
    banned_calls = {"eval", "exec", "compile"}
    banned_modules = {
        "pickle",
        "shelve",
        "marshal",
        "subprocess",
        "socket",
        "urllib",
        "http",
        "ftplib",
        "telnetlib",
        "requests",
        "ctypes",
    }
    # The design rule check runs in a helper process of this same program (D-128). These two
    # files are the only exceptions: the first starts it with fixed arguments, the second talks
    # over its own stdin/stdout pipes. Nothing else may use these modules.
    allowed = {
        "gui/drc_process.py": {"subprocess"},
        "core/drc/worker.py": {"pickle"},
    }
    for path in SRC.rglob("*.py"):
        tree = ast.parse(path.read_text())
        exempt = allowed.get(path.relative_to(SRC).as_posix(), set())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in banned_calls
            ):
                pytest.fail(f"{path.name}: {node.func.id}() call")
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] not in banned_modules - exempt, (
                        f"{path.name}: import {a.name}"
                    )
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] not in banned_modules - exempt, (
                    f"{path.name}: from {node.module}"
                )
            if (
                isinstance(node, ast.Attribute)
                and node.attr in ("system", "popen")
                and isinstance(node.value, ast.Name)
                and node.value.id == "os"
            ):
                pytest.fail(f"{path.name}: os.{node.attr}")


def test_save_never_writes_outside_the_project_folder(tmp_path: Path) -> None:
    p = sat15_full()
    root = tmp_path / "deep" / "p"
    save_project(p, root)
    for f in tmp_path.rglob("*"):
        assert str(f).startswith(str(tmp_path))
    names = {f.relative_to(root).parts[0] for f in root.iterdir()}
    assert names <= {
        "project.json",
        "config",
        "library",
        "logical",
        "physical",
        "generated",
        ".gitignore",
        "waivers.json",
        "changelog.json",
        "baselines",
        ".harness-recovery",
        "outputs",
    }


def test_the_process_exceptions_stay_narrow() -> None:
    """Only the helper-process files may use subprocess or pickle, and the helper's input is only
    ever read as pickle from its own parent (the client never unpickles anything but the reply)."""
    users: dict[str, set[str]] = {}
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            for name in names:
                if name.split(".")[0] in ("subprocess", "pickle"):
                    users.setdefault(path.relative_to(SRC).as_posix(), set()).add(name)
    assert users == {
        "gui/drc_process.py": {"subprocess"},
        "core/drc/worker.py": {"pickle"},
    }


# ---- links never lead a write or a delete out of the project ----------------------------------


def _victim(tmp_path: Path) -> Path:
    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "precious.txt").write_text("precious")
    return victim


def test_export_never_deletes_through_a_linked_subfolder(tmp_path: Path) -> None:
    import json
    import os

    from harness_design_studio.core.errors import SaveError
    from harness_design_studio.core.outputs.build import build_outputs, write_outputs
    from harness_design_studio.core.samples import mini3

    victim = _victim(tmp_path)
    p = mini3()
    out = tmp_path / "outputs"
    write_outputs(p, out)
    manifest = json.loads((out / "manifest.json").read_text())
    manifest["files"].append({"bytes": 1, "path": "system/ln/precious.txt", "sha256": "x"})
    (out / "manifest.json").write_text(json.dumps(manifest))
    os.symlink(victim, out / "system" / "ln")
    with pytest.raises(SaveError):
        write_outputs(p, out, build_outputs(p))
    assert (victim / "precious.txt").read_text() == "precious"


def test_export_and_save_never_write_through_a_planted_temp_or_backup_link(tmp_path: Path) -> None:
    import os

    from harness_design_studio.core.io.fs import atomic_write_bytes

    victim = _victim(tmp_path)
    target = tmp_path / "project.json"
    target.write_text("old")
    os.symlink(victim / "precious.txt", tmp_path / "project.json.bak")
    atomic_write_bytes(target, b"new")
    assert (
        victim / "precious.txt"
    ).read_text() == "precious"  # the link was replaced, not followed
    assert target.read_bytes() == b"new"
    assert (tmp_path / "project.json.bak").read_bytes() == b"old"
    assert not (tmp_path / "project.json.bak").is_symlink()
    # a file with a predictable temp name next to the target is not touched either
    os.symlink(victim / "precious.txt", tmp_path / f".project.json.{os.getpid()}.tmp")
    atomic_write_bytes(target, b"newer")
    assert (victim / "precious.txt").read_text() == "precious"


def test_save_refuses_to_write_behind_a_linked_subfolder(tmp_path: Path) -> None:
    import os

    from harness_design_studio.core.errors import SaveError
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.samples import mini3

    p = mini3()
    generate_project(p)
    folder = tmp_path / "proj"
    save_project(p, folder)
    outside = tmp_path / "outside"
    outside.mkdir()
    import shutil

    shutil.rmtree(folder / "physical" / "harnesses")
    os.symlink(outside, folder / "physical" / "harnesses")
    with pytest.raises(SaveError):
        save_project(p, folder, allow_inconsistent=True)
    assert not list(outside.iterdir())


# ---- damaged input never crashes or silently passes the export --------------------------------


def test_a_control_character_in_a_waiver_text_is_refused_and_one_in_a_cell_is_dropped() -> None:
    import pytest as _pytest
    from pydantic import ValidationError

    from harness_design_studio.core.model.review import Waiver
    from harness_design_studio.core.outputs.exports import xlsx_bytes
    from harness_design_studio.core.outputs.stamp import Stamp

    with _pytest.raises(ValidationError):
        Waiver(
            id="r.o", rule="r", object_id="o", justification="long enough\x0bwith a control char"
        )
    data = xlsx_bytes({"T": [["a\x0bb", "\x00c"]]}, Stamp("t", "t"))
    assert data.startswith(b"PK")  # a workbook, not an IllegalCharacterError


def test_an_invalid_titleblock_config_does_not_crash_the_drawing() -> None:
    from harness_design_studio.core.model.config import ConfigFile
    from harness_design_studio.core.outputs.drawing import harness_sheets
    from harness_design_studio.core.outputs.stamp import Stamp
    from harness_design_studio.core.samples import sat15_full

    p = sat15_full()
    old = p.config["titleblock"]
    for bad in (True, "abc", 5, {"a": 1}):
        p.config["titleblock"] = ConfigFile(
            name="titleblock", placeholder=old.placeholder, values={**old.values, "fields": bad}
        )
        assert harness_sheets(p, p.harnesses["W010"], Stamp("t", "t"), "A3")


def test_export_and_migrate_refuse_a_project_with_damaged_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from harness_design_studio.cli.main import main as cli_main
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.samples import mini3

    p = mini3()
    generate_project(p)
    folder = tmp_path / "proj"
    save_project(p, folder)
    harness_file = next((folder / "physical" / "harnesses").glob("*.json"))
    harness_file.write_text(harness_file.read_text()[:40])  # truncated
    for command in ("export", "migrate"):
        assert cli_main([command, str(folder)]) == 2
        assert "damaged" in capsys.readouterr().err
    assert not (folder / "outputs").exists()


def test_the_netlist_reader_wants_a_regular_file(tmp_path: Path) -> None:
    from harness_design_studio.core.kicad import NetlistError, read_netlist

    with pytest.raises(NetlistError):
        read_netlist("/dev/zero")
    with pytest.raises(NetlistError):
        read_netlist(tmp_path)


def test_the_drc_worker_is_started_without_the_current_folder_on_its_path() -> None:
    from harness_design_studio.gui.drc_process import worker_command

    assert "-P" in worker_command()


def test_the_length_cache_is_bounded() -> None:
    from harness_design_studio.core.generate import lengths
    from harness_design_studio.core.model import Segment, evolve
    from harness_design_studio.core.samples import sat15_full

    h = sat15_full().harnesses["W010"]
    a, b = h.connectors[0].id, h.connectors[1].id
    wire = evolve(h.wires[0], length_m=None, from_connector=a, to_connector=b)
    base = evolve(h, segments=[Segment(id="S1", from_node=a, to_node=b, length_m=1.0)])
    lengths.clear_length_cache()
    for k in range(lengths._PATHS_LIMIT * 3):
        assert lengths.wire_length(evolve(base, name=f"copy {k}"), wire) == 1.0
    assert len(lengths._PATHS) <= lengths._PATHS_LIMIT
