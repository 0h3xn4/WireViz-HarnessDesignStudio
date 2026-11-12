# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index,union-attr"
"""REQ-MIGRATE-05: format 2 is in force (M4 of the 2.0 programme, D-226).

This tool writes `schema_version` 2. Format 2 is format 1 plus the number: the step from 1 to 2
(`core/io/migrate.py`) writes the number and nothing else, because a loose cable end is new content
(a connector with the role `loose` and the part `TBD-CONNECTOR`), the origin of a harness is worked
out and never stored (D-201), and the place of a loose end on the diagram is the mark
`pos:<connector id>` in `diagram/marks.json`, outside the model hash. A version 1.x tool opens a
format 2 project read-only.

`tests/fixtures/v1_project` is a format 1 project written by the tool of version 1.17.1 (the code of
`master` before this change): the `mini3` fixture with a cable drawn from the port `OBC-J01` whose far
end `W002-P2` is loose, and the mark `pos:W002-P2`. `V1_HASH` is its model hash as 1.17.1 computed it.
"""

import contextlib
import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_design_studio import __version__
from harness_design_studio.cli.main import main
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.io import layout, migrate, upgrade
from harness_design_studio.core.io.layout import is_managed, model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.manual_harness import loose_ends
from harness_design_studio.core.model import SCHEMA_VERSION
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.vcs.hashing import content_hash
from harness_design_studio.resources import examples_path
from tests.helpers import FIXTURES, copy_project
from tests.migration_support import as_format, build, folder_bytes, full_export

V1 = FIXTURES / "v1_project"
# the model hash (and the content hash) of `v1_project` as the tool of version 1.17.1 computed it
V1_HASH = "268eab67114456c27afdb90209a9d86efb1dac6679def48b9abf2c6fb0e2acbf"
# kept in an older format on purpose: format 0; 1.17.1 with a loose end; written by 0.0.1 (M1)
OLD_FIXTURES = {"v0_project": None, "v1_project": 1, "m1_project": 1}


def managed(root: Path) -> dict[str, bytes]:
    return {k: v for k, v in folder_bytes(root).items() if is_managed(k)}


def project_roots() -> list[Path]:
    examples = examples_path()
    assert examples is not None
    roots = [p.parent for p in FIXTURES.rglob("project.json")]
    roots += [p.parent for p in (examples / "projects").glob("*/project.json")]
    return sorted(roots)


# ---- the number ----------------------------------------------------------------------------------------


def test_this_tool_writes_format_2_and_has_a_step_for_every_older_format() -> None:
    assert SCHEMA_VERSION == 2 and migrate.current_version() == 2
    assert sorted(migrate.MIGRATIONS) == [0, 1]
    assert layout.HASH_SCHEMA_VERSION == 1  # the hash is of the design, never of the format
    assert V1.is_dir() and (FIXTURES / "v0_project").is_dir()


def test_every_fixture_and_every_shipped_example_is_in_format_2() -> None:
    roots = project_roots()
    assert len(roots) >= 10
    for root in roots:
        doc = json.loads((root / "project.json").read_text(encoding="utf-8"))
        want = OLD_FIXTURES.get(root.name, SCHEMA_VERSION)
        assert doc.get("schema_version") == want, root


def test_the_step_from_1_to_2_is_a_list_of_parts_that_can_take_one_more_before_2_0_0(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Format 2 is frozen only when 2.0.0 is tagged; a change that is still to come is one more part
    of the same step, not a format 3. The journal of M7a is the second part (D-228)."""
    assert (migrate._v2_number, migrate._v2_journal_lines) == migrate.V1_TO_V2_PARTS
    files = {"project.json": {"name": "x", "schema_version": 1}, "journal.json": {"journal": []}}
    out = migrate.migrate_raw(files, 1)
    assert out == {"project.json": {"name": "x", "schema_version": 2}, "journal.jsonl": {"journal": []}}  # fmt: skip
    assert files == {"project.json": {"name": "x", "schema_version": 1}, "journal.json": {"journal": []}}  # fmt: skip

    def later_part(tree):
        tree["project.json"]["later"] = True
        return tree

    monkeypatch.setattr(migrate, "V1_TO_V2_PARTS", (*migrate.V1_TO_V2_PARTS, later_part))
    assert migrate.migrate_raw(files, 1)["project.json"]["later"] is True


# ---- a format 1 project of 1.17.1 -------------------------------------------------------------------------


def test_the_project_of_1_17_1_opens_upgraded_in_memory_and_the_disk_is_untouched(
    tmp_path: Path,
) -> None:
    root = copy_project(V1, tmp_path / "p")
    before = folder_bytes(root)
    r = load_project(root)
    p = r.project
    assert p.migrated_from == 1 and p.meta.schema_version == 2 and not r.has_errors
    assert any(i.code == "migrated" for i in r.issues)
    assert [c.id for c in loose_ends(p.harnesses["W002"])] == ["W002-P2"]
    assert "pos:W002-P2" in p.diagram_marks
    assert model_hash(p) == content_hash(p) == V1_HASH  # what 1.17.1 computed
    assert folder_bytes(root) == before


def test_format_2_is_format_1_with_another_number(tmp_path: Path) -> None:
    """Saved again by this tool (to a new folder, the way *Save as* does), the project of 1.17.1 is
    the same bytes in every file but `project.json`, and there only the number differs (and the
    version of the tool that saved it, once this tool is no longer 1.17.1)."""
    p = load_project(V1).project
    out = tmp_path / "copy"
    save_project(p, out)
    old, new = folder_bytes(V1), folder_bytes(out)
    assert set(old) == set(new)
    assert {k for k in old if old[k] != new[k]} == {"project.json"}
    a, b = json.loads(old["project.json"]), json.loads(new["project.json"])
    numbers = (a.pop("schema_version"), b.pop("schema_version"))
    versions = (a.pop("tool_version"), b.pop("tool_version"))
    assert numbers == (1, 2) and a == b
    assert versions == ("1.17.1", __version__)
    assert model_hash(load_project(out).project) == V1_HASH


def test_the_dry_run_of_the_project_of_1_17_1_writes_nothing(tmp_path: Path, capsys) -> None:
    root = copy_project(V1, tmp_path / "p")
    before = folder_bytes(root)
    assert main(["migrate", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Project format 1; this tool writes format 2." in out and "Nothing is lost" in out
    assert main(["migrate", str(root), "--dry-run", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert (doc["from_version"], doc["to_version"], doc["up_to_date"]) == (1, 2, False)
    assert doc["ok"] and doc["hash_equal"] and doc["exports_equal"] and doc["lost"] == []
    assert doc["model_hash_before"] == doc["model_hash_after"] == V1_HASH
    assert doc["files"] == [{"file": "project.json", "change": "changed"}]
    assert folder_bytes(root) == before


def test_migrate_upgrades_the_project_of_1_17_1_with_a_backup_and_a_record(
    tmp_path: Path, capsys
) -> None:
    root = copy_project(V1, tmp_path / "p")
    before = managed(root)
    assert main(["migrate", str(root)]) == 0
    assert "Format 1 to 2." in capsys.readouterr().out
    backup = root / ".migration-backup-v1"
    for rel, data in before.items():
        assert (backup / rel).read_bytes() == data  # the original is kept, every file
    record = json.loads((backup / upgrade.RECORD_NAME).read_text(encoding="utf-8"))
    assert (record["from_version"], record["to_version"], record["status"]) == (1, 2, "complete")
    after = managed(root)
    assert {k for k in after if after[k] != before.get(k)} == {"project.json"}
    assert json.loads(after["project.json"])["schema_version"] == 2
    r = load_project(root)
    p = r.project
    assert p.migrated_from is None and not any(i.code == "migrated" for i in r.issues)
    assert model_hash(p) == content_hash(p) == V1_HASH
    assert [c.id for c in loose_ends(p.harnesses["W002"])] == ["W002-P2"]
    assert p.diagram_marks["pos:W002-P2"].dx == 120.0
    assert not (root / "journal.json").exists()  # a migration does not start a journal
    assert not (root / "journal.jsonl").exists()
    assert main(["migrate", str(root)]) == 0
    assert "Already up to date." in capsys.readouterr().out


def test_a_journal_gets_one_migrated_entry_and_still_reads(tmp_path: Path) -> None:
    root = as_format(build("journal-and-overrides", tmp_path / "j"), 1)
    before = load_project(root, migrate=False).project.journal
    assert before is not None
    done = upgrade.upgrade_project(root)
    assert done is not None and all(done.self_check.values())
    after = load_project(root)
    assert not after.has_errors  # the reader accepts the entry and the chain still holds
    entries = list(after.project.journal)
    assert entries[: len(before)] == list(before) and len(entries) == len(before) + 1
    last = entries[-1]
    assert (last.kind, last.object, last.reason, last.old, last.new) == (
        "edit", "project", "migrated from format 1", 1, 2,
    )  # fmt: skip


def test_the_editor_question_is_the_one_of_1_17_0() -> None:
    from harness_design_studio.gui import strings

    body = strings.UPGRADE_BODY.format(old=1, backup=".migration-backup-v1")
    assert body.startswith("This project is in format 1. Upgrade?")


# ---- commands that save do not upgrade silently ----------------------------------------------------------


def test_a_command_that_saves_refuses_a_format_1_project_and_names_migrate(
    tmp_path: Path, capsys
) -> None:
    """No silent upgrade (plan 2.3, point 5): `migrate` is the one way to write a format 1 project
    in format 2 in place; a command that would save it says so and writes nothing (D-226)."""
    root = copy_project(V1, tmp_path / "p")
    before = folder_bytes(root)
    assert main(["generate", str(root)]) != 0
    err = capsys.readouterr().err
    assert "format 1" in err and "migrate" in err
    assert managed(root) == {k: v for k, v in before.items() if is_managed(k)}
    assert not (root / ".migration-backup-v1").exists()
    with pytest.raises(SaveError, match="migrate"):
        save_project(load_project(root).project, root)
    assert managed(root) == {k: v for k, v in before.items() if is_managed(k)}


def test_a_format_1_project_can_be_saved_to_a_new_folder(tmp_path: Path) -> None:
    root = copy_project(V1, tmp_path / "p")
    before = folder_bytes(root)
    out = tmp_path / "copy"
    save_project(load_project(root).project, out)
    assert json.loads((out / "project.json").read_text())["schema_version"] == 2
    assert folder_bytes(root) == before


# ---- newer than this tool ----------------------------------------------------------------------------------


@pytest.mark.parametrize("version", [3, 99])
def test_a_project_of_a_newer_format_is_read_only(version: int, tmp_path: Path, capsys) -> None:
    root = as_format(copy_project(FIXTURES / "projects" / "mini3", tmp_path / "p"), version)
    before = folder_bytes(root)
    r = load_project(root)
    assert r.project.read_only
    (warning,) = [i for i in r.issues if i.code == "newer_version"]
    assert warning.severity == "warning"
    assert f"format {version}; this tool understands up to 2" in warning.message
    with pytest.raises(SaveError):
        save_project(r.project, root)
    for command in (["generate"], ["export"], ["migrate"], ["migrate", "--dry-run"]):
        assert main([command[0], str(root), *command[1:]]) == 2, command
    assert "read-only" in capsys.readouterr().err
    assert managed(root) == {k: v for k, v in before.items() if is_managed(k)}


# ---- written outputs ---------------------------------------------------------------------------------------


def test_no_written_file_holds_the_format_number(tmp_path: Path) -> None:
    """The format number is in `project.json` and nowhere else: a full export of a project in
    format 1 and of the same project in format 2 is the same, byte for byte, and no written file
    names `schema_version`."""
    root = copy_project(V1, tmp_path / "p")
    old = full_export(root, migrate_old=False)  # read as 1.17.1 read it (no step)
    upgrade.upgrade_project(root)
    new = full_export(root)
    assert new == old
    assert not [rel for rel, data in new.items() if b"schema_version" in data]


def test_a_format_2_project_without_a_loose_end_writes_what_format_1_wrote(tmp_path: Path) -> None:
    root = copy_project(FIXTURES / "projects" / "mini3", tmp_path / "p2")
    p = load_project(root).project
    assert p.meta.schema_version == 2 and not any(loose_ends(h) for h in p.harnesses.values())
    old = as_format(copy_project(root, tmp_path / "p1"), 1)
    assert full_export(root) == full_export(old, migrate_old=False)


# ---- save, reload, same hash (property) --------------------------------------------------------------------


@settings(max_examples=8, deadline=None, suppress_health_check=list(HealthCheck))
@given(
    st.sampled_from(["mini3", "sat15"]),
    st.lists(st.integers(min_value=0, max_value=50), max_size=3),
    st.booleans(),
)
def test_save_reload_and_upgrade_keep_the_model_hash(base, ports, plug) -> None:
    """Any project, with cables drawn by hand and loose ends: saved and reloaded, it has the same
    hash and a second save writes the same bytes; written in format 1 and upgraded, the same hash."""
    import tempfile

    from harness_design_studio.core.commands import apply_ops
    from harness_design_studio.core.manual_harness import plan_cable_from_port, plan_plug_loose_end
    from harness_design_studio.core.model import DiagramMark
    from harness_design_studio.core.samples import mini3, sat15

    p = {"mini3": mini3, "sat15": sat15}[base]()
    for n in ports:
        used = {c.mates_with for h in p.harnesses.values() for c in h.connectors}
        free = sorted(c.id for c in p.connectors.values() if c.role == "box" and c.id not in used)
        if len(free) < 2:
            break
        cable = plan_cable_from_port(p, free[n % len(free)])
        apply_ops(p, cable.ops)
        p.diagram_marks[f"pos:{cable.loose_id}"] = DiagramMark(id=f"pos:{cable.loose_id}", dx=n, dy=-n)  # fmt: skip
        if plug:
            target = [c for c in free if c != free[n % len(free)]][0]
            with contextlib.suppress(EditError):  # a plug the pins refuse: the end stays loose
                apply_ops(p, plan_plug_loose_end(p, cable.harness_id, cable.loose_id, target))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "p"
        save_project(p, root)
        first = managed(root)
        q = load_project(root).project
        assert q.meta.schema_version == 2
        h = model_hash(q)
        assert h == model_hash(p)
        save_project(q, root)
        assert managed(root) == first  # nothing moves on a second save
        as_format(root, 1)
        assert model_hash(load_project(root).project) == h  # in memory, upgraded
        done = upgrade.upgrade_project(root)
        assert done is not None and all(done.self_check.values())
        assert model_hash(load_project(root).project) == h
        assert managed(root) == first


def test_the_outputs_of_the_shipped_examples_name_no_format() -> None:
    examples = examples_path()
    assert examples is not None
    p = load_project(examples / "projects" / "first-steps").project
    assert p.meta.schema_version == 2 and p.migrated_from is None
    files = build_outputs(p).files
    assert files and not [rel for rel, data in files.items() if b"schema_version" in data]
