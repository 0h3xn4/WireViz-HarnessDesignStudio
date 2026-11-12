# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index,union-attr"
"""REQ-MIGRATE-02: the migration safety net (M1 of the 2.0 programme, plan 2.3).

What is checked: the model hash does not depend on the format number, and the hashes of format-1
projects (those stored in `tests/fixtures/migration/hashes.json`, made with the code that had no such
rule) are what they were; the step from format 1 to 2 (real since D-226; it was a fake of the tests
in 1.17.0) is run over every fixture, example and scenario of `tests/migration_support.py`, written
in format 1, and changes no hash, no finding, no baseline and no byte of a full export; the dry run
writes nothing; the record is written; the check after the write puts everything back on any
difference; and a killed upgrade, a read-only folder and a linked file leave the project as it was.
A fake format one ahead of this tool (never shipped) gives the refusals something to refuse."""

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_design_studio.cli.jsonout import SHAPES
from harness_design_studio.cli.main import main
from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.io import canonical, layout, saver, upgrade
from harness_design_studio.core.io.layout import is_managed, model_hash, schema_one
from harness_design_studio.core.io.loader import disk_fingerprint, load_project
from harness_design_studio.core.model import evolve
from tests.helpers import FIXTURES, copy_project
from tests.migration_support import (
    GOLDEN,
    SCENARIOS,
    as_format,
    build,
    changing_step,
    folder_bytes,
    full_export,
    hashes_of,
    install_fake_format,
    lossy_step,
)

V0 = FIXTURES / "v0_project"
NAMES = list(SCENARIOS)


def managed(root: Path) -> dict[str, bytes]:
    """The project files the tool manages, by name (the state a rollback must give back)."""
    return {k: v for k, v in folder_bytes(root).items() if is_managed(k)}


def ids_of(root: Path) -> set[str]:
    found: set[str] = set()

    def walk(x) -> None:
        if isinstance(x, dict):
            if isinstance(x.get("id"), str):
                found.add(x["id"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    for rel, data in managed(root).items():
        if rel not in ("journal.json", "journal.jsonl"):
            walk(json.loads(data))
    return found


# ---- the hash rule ------------------------------------------------------------------------------------


def test_schema_one_changes_only_a_project_file_that_is_not_in_format_one() -> None:
    one = canonical.dumps({"name": "x", "schema_version": 1, "tool_version": ""})
    two = canonical.dumps({"name": "x", "schema_version": 2, "tool_version": ""})
    assert schema_one("project.json", one) is one  # untouched, so every old hash stays
    assert schema_one("project.json", two) == one
    assert schema_one("config/derating.json", two) is two
    assert schema_one("project.json", b"{not json") == b"{not json"
    nothing = canonical.dumps({"name": "x"})
    assert schema_one("project.json", nothing) is nothing


@pytest.mark.parametrize("name", NAMES)
def test_the_model_hash_and_the_content_hash_do_not_depend_on_the_format_number(
    name: str, tmp_path: Path
) -> None:
    from harness_design_studio.core.vcs.hashing import content_hash

    p = load_project(build(name, tmp_path / "p")).project
    before = (model_hash(p), content_hash(p))
    p.meta = evolve(p.meta, schema_version=7)
    assert b'"schema_version": 7' in layout.serialize(p)["project.json"]  # the file says it
    assert (model_hash(p), content_hash(p)) == before


@pytest.mark.parametrize("name", NAMES)
def test_every_hash_of_a_format_1_project_is_what_it_was(name: str, tmp_path: Path) -> None:
    """The stored hashes were made with the code of master, which had no hash rule: the model hash,
    the content hash and the content hash stored in each baseline are byte for byte the same, in
    format 2 (this tool writes it, D-226) and when the file says format 1."""
    gold = json.loads(GOLDEN.read_text(encoding="utf-8"))[name]
    root = build(name, tmp_path / "p")
    assert hashes_of(root) == gold, "a hash of a format-1 project changed: the rule is wrong"
    as_format(root, 1)
    assert hashes_of(root) == gold


def test_released_baselines_keep_the_content_hash_they_were_released_with(tmp_path: Path) -> None:
    root = build("released", tmp_path / "p")
    project = load_project(root).project
    assert len(project.baselines) >= 2 and len(project.changelog) >= 3
    gold = json.loads(GOLDEN.read_text(encoding="utf-8"))["released"]
    for bid, b in project.baselines.items():
        assert b.content_hash == gold[f"baseline:{bid}"]


# ---- the fake step over everything -------------------------------------------------------------------------


@pytest.mark.parametrize("name", NAMES)
def test_the_step_from_1_to_2_changes_no_hash_no_finding_no_baseline_and_no_byte_of_an_export(
    name: str, tmp_path: Path
) -> None:
    root = build(name, tmp_path / "p")
    as_format(root, 1)
    had_journal = (root / "journal.json").exists()
    files = folder_bytes(root)
    old_export = full_export(root, migrate_old=False)
    old_hashes = hashes_of(root)
    old_findings = upgrade._folder_findings(root)
    old_ids = ids_of(root)

    plan = upgrade.plan_upgrade(root)  # the dry run
    assert folder_bytes(root) == files  # writes nothing
    assert plan is not None and plan.ok, plan.lost
    assert plan.hash_equal and plan.exports_equal and plan.baselines_intact is True
    if not plan.notes:  # (a note says a missing file is written with the values already in use)
        assert plan.counts_before == plan.counts_after or plan.journal_entry
    assert plan.journal_entry is had_journal
    assert plan.hash_before == plan.hash_after

    done = upgrade.upgrade_project(root)
    assert done is not None and all(done.self_check.values()), done.self_check
    after = folder_bytes(root)
    assert json.loads(after["project.json"])["schema_version"] == 2
    changed = {
        k for k in files if after.get(k) != files[k] and is_managed(k)
    }  # (the files the tool manages, not litter such as .bak)
    journal_files = {"journal.json"} if had_journal else set()  # moved to journal.jsonl (D-228)
    assert changed >= {"project.json"} | journal_files
    assert {k for k in {*after, *files} if is_managed(k) and files.get(k) != after.get(k)} == {
        k for k in plan.files if is_managed(k)
    }  # the dry run said exactly which files would change (or go)
    if not plan.notes:
        assert changed == {"project.json"} | journal_files
    assert {k for k in after if is_managed(k)} == {
        k for k in files if is_managed(k)
    } - journal_files | {
        k for k, how in plan.files.items() if how == "new" and is_managed(k)
    }  # (a file that was missing is written with the values in use; nothing else is removed)
    assert {k for k, how in plan.files.items() if how == "removed"} == journal_files
    if had_journal:
        assert after["journal.json.bak"] == files["journal.json"]  # (and in the backup folder)
    assert hashes_of(root) == old_hashes
    assert upgrade._folder_findings(root) == old_findings
    assert full_export(root) == old_export  # byte for byte
    assert ids_of(root) == old_ids  # no new ID
    for rel in files:
        if rel.startswith("baselines/"):
            assert after[rel] == files[rel]  # a baseline file is not touched
    backup = root / done.backup
    for rel, data in files.items():
        if is_managed(rel):
            assert (backup / rel).read_bytes() == data  # the original is in the backup
    record = json.loads((root / done.record).read_text(encoding="utf-8"))
    assert (record["status"], record["from_version"], record["to_version"]) == ("complete", 1, 2)
    assert record["model_hash"] == {
        "before": old_hashes["model_hash"],
        "after": old_hashes["model_hash"],
    }
    assert record["files"]["before"] == {
        k: hashlib.sha256(v).hexdigest() for k, v in files.items() if is_managed(k)
    }
    assert set(record["files"]["after"]) == set(record["files"]["before"]) - journal_files | {
        k for k, how in plan.files.items() if how == "new" and is_managed(k)
    }
    assert record["counts"]["before"] == plan.counts_before
    assert upgrade.upgrade_project(root) is None  # now current


def test_the_record_is_outside_the_hash_and_every_output(tmp_path: Path) -> None:
    root = build("mini3", tmp_path / "p")
    as_format(root, 1)
    fingerprint, export = disk_fingerprint(root), full_export(root, migrate_old=False)
    done = upgrade.upgrade_project(root)
    assert (root / done.record).is_file()
    assert not is_managed(done.record) and not layout.MANAGED_RE.match(done.record)
    assert not any("MIGRATION" in k for k in full_export(root))
    assert full_export(root) == export
    assert (
        disk_fingerprint(root) != fingerprint
    )  # (project.json says 2) but not because of the record
    assert upgrade.RECORD_NAME not in {k.split("/")[-1] for k in managed(root)}


def test_a_migration_writes_one_journal_entry_and_only_for_a_project_with_a_journal(
    tmp_path: Path,
) -> None:
    kept = build("journal-and-overrides", tmp_path / "j")
    as_format(kept, 1)
    before = load_project(kept).project.journal
    assert before is not None
    upgrade.upgrade_project(kept)
    after = load_project(kept)
    assert not after.has_errors  # the reader accepts it: the journal chain still verifies
    entries = list(after.project.journal)
    assert len(entries) == len(before) + 1
    assert entries[: len(before)] == list(before)
    last = entries[-1]
    assert (last.kind, last.object, last.reason) == ("edit", "project", "migrated from format 1")
    assert (last.old, last.new) == (1, 2)
    plain = as_format(build("mini3", tmp_path / "m"), 1)
    assert upgrade.upgrade_project(plain) is not None
    assert not (plain / "journal.json").exists()  # a migration does not start a journal


def test_the_journal_kind_is_one_an_older_tool_reads(tmp_path: Path) -> None:
    """No new kind: a journal that holds `migrated from format N` is still read by 1.16 (no format
    change is made for the journal entry)."""
    from harness_design_studio.core import journal
    from harness_design_studio.core.model.journal import KINDS

    rows = journal.migration_rows(1, 2)
    assert len(rows) == 1 and rows[0]["kind"] in KINDS


# ---- the dry run ------------------------------------------------------------------------------------------


def test_the_dry_run_of_a_current_project_says_so(tmp_path: Path, capsys) -> None:
    root = build("mini3", tmp_path / "p")
    assert main(["migrate", str(root), "--dry-run"]) == 0
    assert "Already up to date." in capsys.readouterr().out
    assert main(["migrate", str(root), "--dry-run", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert list(doc) == list(SHAPES["migrate --dry-run"]) and doc["up_to_date"] is True


def test_the_dry_run_prints_what_would_happen_and_writes_nothing(tmp_path: Path, capsys) -> None:
    root = build("journal-and-overrides", tmp_path / "p")
    as_format(root, 1)
    files = folder_bytes(root)
    assert main(["migrate", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "changed  project.json" in out and "removed  journal.json" in out
    assert "new      journal.jsonl" in out
    assert "Model hash:" in out and "(equal)" in out and "identical" in out
    assert "devices: " in out and "harness wires: " in out
    assert "migrated from format 1" in out and "Nothing is lost" in out
    assert folder_bytes(root) == files
    assert main(["migrate", str(root), "--dry-run", "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert list(doc) == list(SHAPES["migrate --dry-run"])
    assert doc["ok"] and doc["hash_equal"] and doc["exports_equal"] and doc["lost"] == []
    assert doc["model_hash_before"] == doc["model_hash_after"]
    assert {f["file"] for f in doc["files"]} - {".gitattributes"} == {
        "project.json", "journal.json", "journal.jsonl",
    }  # fmt: skip
    assert doc["counts_before"]["devices"] == doc["counts_after"]["devices"]
    assert folder_bytes(root) == files


def test_the_dry_run_of_a_real_old_project(tmp_path: Path, capsys) -> None:
    root = copy_project(V0, tmp_path / "p")
    files = folder_bytes(root)
    assert main(["migrate", str(root), "--dry-run"]) == 0
    assert "Project format 0; this tool writes format 2." in capsys.readouterr().out
    assert folder_bytes(root) == files


@pytest.mark.parametrize(
    ("step", "word"), [(lossy_step, "would not be carried over"), (changing_step, "model hash")]
)
def test_the_dry_run_fails_when_something_would_be_lost_or_changed(
    step, word: str, tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = build("sat15", tmp_path / "p")
    install_fake_format(monkeypatch, step)
    files = folder_bytes(root)
    assert main(["migrate", str(root), "--dry-run"]) == 1
    out = capsys.readouterr().out
    assert "Could not be carried over:" in out and word in out
    assert main(["migrate", str(root), "--dry-run", "--json"]) == 1
    doc = json.loads(capsys.readouterr().out)
    assert doc["ok"] is False and doc["lost"]
    assert folder_bytes(root) == files
    # and the upgrade itself refuses, before it writes a byte or makes a backup
    assert main(["migrate", str(root)]) == 1
    assert managed(root) == {k: v for k, v in files.items() if is_managed(k)}
    assert not (root / ".migration-backup-v2").exists()  # (the fake is one format ahead)


def test_a_project_in_a_newer_format_cannot_be_upgraded(tmp_path: Path, capsys) -> None:
    root = build("mini3", tmp_path / "p")
    meta = json.loads((root / "project.json").read_text(encoding="utf-8"))
    meta["schema_version"] = 9
    (root / "project.json").write_bytes(canonical.dumps(meta))
    with pytest.raises(upgrade.UpgradeError, match="newer"):
        upgrade.plan_upgrade(root)
    assert main(["migrate", str(root), "--dry-run"]) == 2  # read-only: refused as before


def test_a_damaged_project_is_refused_and_nothing_is_written(tmp_path: Path, capsys) -> None:
    root = build("mini3", tmp_path / "p")
    as_format(root, 1)
    unit_file = next((root / "logical" / "units").glob("*.json"))
    doc = json.loads(unit_file.read_text(encoding="utf-8"))
    doc["units"][0]["surprise"] = 1  # a field this tool does not know: the device is set aside
    unit_file.write_bytes(canonical.dumps(doc))
    files = folder_bytes(root)
    plan = upgrade.plan_upgrade(root)
    assert plan is not None and not plan.ok and "damaged" in plan.lost[0]
    with pytest.raises(upgrade.UpgradeError):
        upgrade.upgrade_project(root)
    assert folder_bytes(root) == files
    assert main(["migrate", str(root), "--dry-run"]) == 2


# ---- the command ------------------------------------------------------------------------------------------


def test_migrate_prints_the_record_and_the_check_and_is_then_up_to_date(
    tmp_path: Path, capsys
) -> None:
    root = build("sat15", tmp_path / "p")
    as_format(root, 1)
    assert main(["migrate", str(root), "--json"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert list(doc) == list(SHAPES["migrate"])
    assert doc["migrated"] and (doc["from_version"], doc["to_version"]) == (1, 2)
    assert doc["backup"] == ".migration-backup-v1" and doc["record"].endswith("MIGRATION.json")
    assert all(doc["self_check"].values())
    assert main(["migrate", str(root)]) == 0
    assert "Already up to date." in capsys.readouterr().out


def test_migrating_a_real_old_project_writes_the_record_and_checks_itself(tmp_path: Path) -> None:
    root = copy_project(V0, tmp_path / "p")
    original = managed(root)
    done = upgrade.upgrade_project(root)
    assert done is not None and (done.from_version, done.to_version) == (0, 2)
    assert done.self_check["reload"] and done.self_check["exports"]
    for rel, data in original.items():
        assert (root / ".migration-backup-v0" / rel).read_bytes() == data
    record = json.loads((root / done.record).read_text(encoding="utf-8"))
    assert record["model_hash"]["before"] is None  # format 0 cannot be read as it is
    assert record["model_hash"]["after"] == model_hash(load_project(root).project)
    assert load_project(root).project.migrated_from is None


# ---- failures: nothing is lost -----------------------------------------------------------------------------


def test_a_failure_while_the_backup_is_made_leaves_the_project_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = build("sat15", tmp_path / "p")
    as_format(root, 1)
    files = folder_bytes(root)
    real, calls = saver.shutil.copyfile, []

    def dying(src, dst, **kw):
        calls.append(src)
        if len(calls) == 4:
            raise OSError(28, "No space left on device")
        return real(src, dst, **kw)

    monkeypatch.setattr(saver.shutil, "copyfile", dying)
    with pytest.raises(upgrade.UpgradeError, match="backup"):
        upgrade.upgrade_project(root)
    assert folder_bytes(root) == files  # no half backup, no changed file
    assert not [p for p in root.iterdir() if p.name.startswith(".migration-backup")]
    monkeypatch.setattr(saver.shutil, "copyfile", real)
    assert upgrade.upgrade_project(root) is not None  # and it can be tried again


def test_a_kill_while_the_backup_is_made_leaves_a_partial_folder_that_is_not_used(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Killed(BaseException):
        pass

    root = build("sat15", tmp_path / "p")
    as_format(root, 1)
    files = folder_bytes(root)
    real, calls = saver.shutil.copyfile, []

    def dying(src, dst, **kw):
        calls.append(src)
        if len(calls) == 4:
            raise Killed
        return real(src, dst, **kw)

    monkeypatch.setattr(saver.shutil, "copyfile", dying)
    with pytest.raises(Killed):
        upgrade.upgrade_project(root)
    names = {p.name for p in root.iterdir()}
    assert (
        ".migration-backup-v1" not in names
    )  # only the .partial, which is never taken for a backup
    assert {k: v for k, v in folder_bytes(root).items() if is_managed(k)} == {
        k: v for k, v in files.items() if is_managed(k)
    }
    monkeypatch.setattr(saver.shutil, "copyfile", real)
    assert upgrade.upgrade_project(root) is not None
    assert not (root / ".migration-backup-v1.partial").exists()


def test_a_failure_while_the_files_are_written_puts_every_file_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = copy_project(V0, tmp_path / "p")  # (the real step 0 to 1 writes many files)
    files = managed(root)
    real, calls = saver.atomic_write_bytes, []

    def dying(path, data, **kw):
        calls.append(path)
        if len(calls) == 6:
            raise SaveError("The disk is full.")
        return real(path, data, **kw)

    monkeypatch.setattr(saver, "atomic_write_bytes", dying)
    with pytest.raises(upgrade.UpgradeFailed, match="Every file was put back") as err:
        upgrade.upgrade_project(root)
    assert err.value.rolled_back
    assert managed(root) == files and not (root / ".gitignore").exists()
    record = json.loads((root / ".migration-backup-v0.rolled-back" / "MIGRATION.json").read_text())
    assert record["status"] == "rolled_back" and "disk is full" in record["problems"][0]
    monkeypatch.setattr(saver, "atomic_write_bytes", real)
    assert upgrade.upgrade_project(root) is not None  # a new attempt starts clean


def test_a_kill_while_the_files_are_written_is_put_right_by_the_next_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Killed(BaseException):
        pass

    root = copy_project(V0, tmp_path / "p")
    files = managed(root)
    real, calls = saver.atomic_write_bytes, []

    def dying(path, data, **kw):
        calls.append(path)
        if len(calls) == 6:
            raise Killed
        return real(path, data, **kw)

    with monkeypatch.context() as m:
        m.setattr(saver, "atomic_write_bytes", dying)
        m.setattr(upgrade, "_restore", lambda *a, **k: (_ for _ in ()).throw(Killed()))  # no time
        with pytest.raises(Killed):
            upgrade.upgrade_project(root)
    assert managed(root) != files  # a mixed project, and a backup that says `started`
    started = json.loads((root / ".migration-backup-v0" / "MIGRATION.json").read_text())
    assert started["status"] == "started"
    assert json.loads((root / "project.json").read_text()).get("schema_version") is None  # last
    done = upgrade.upgrade_project(root)  # the next run puts the originals back, then upgrades
    assert done is not None and all(done.self_check.values())
    parked = root / ".migration-backup-v0.interrupted"
    assert json.loads((parked / "MIGRATION.json").read_text())["status"] == "interrupted"
    for rel, data in files.items():
        assert (
            (parked / rel).read_bytes()
            == data
            == (root / ".migration-backup-v0" / rel).read_bytes()
        )


def test_an_interrupt_while_the_files_are_written_puts_every_file_back_and_goes_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = copy_project(V0, tmp_path / "p")
    files = managed(root)
    real, calls = saver.atomic_write_bytes, []

    def interrupted(path, data, **kw):
        calls.append(path)
        if len(calls) == 6:
            raise KeyboardInterrupt
        return real(path, data, **kw)

    monkeypatch.setattr(saver, "atomic_write_bytes", interrupted)
    with pytest.raises(KeyboardInterrupt):
        upgrade.upgrade_project(root)
    assert managed(root) == files


def test_a_read_only_folder_is_refused_before_a_file_is_changed(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip(
            "a folder's read-only bit does not stop writes on Windows (the patched write failure below covers the path)"
        )
    if os.geteuid() == 0:
        pytest.skip("root writes to a read-only folder")
    root = build("mini3", tmp_path / "p")
    as_format(root, 1)
    files = folder_bytes(root)
    root.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(upgrade.UpgradeError):
            upgrade.upgrade_project(root)
    finally:
        root.chmod(stat.S_IRWXU)
    assert folder_bytes(root) == files


def test_a_folder_that_refuses_the_writes_gets_every_file_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """(The write fails after the backup: a folder that took the copy but not the project file.)"""
    root = build("journal-and-overrides", tmp_path / "p")
    as_format(root, 1)
    files = managed(root)

    def refuse(path, data, **kw):
        raise SaveError("'project.json' could not be written: the folder is read-only.")

    monkeypatch.setattr(saver, "atomic_write_bytes", refuse)
    with pytest.raises(upgrade.UpgradeFailed) as err:
        upgrade.upgrade_project(root)
    assert err.value.rolled_back and "put back" in str(err.value)
    assert managed(root) == files


def test_a_linked_project_file_is_not_read_or_copied_and_the_upgrade_is_refused(
    tmp_path: Path,
) -> None:
    secret = tmp_path / "elsewhere.json"
    root = build("sat15", tmp_path / "p")
    as_format(root, 1)
    unit_file = next((root / "logical" / "units").glob("*.json"))
    secret.write_bytes(unit_file.read_bytes())
    unit_file.unlink()
    unit_file.symlink_to(secret)
    files = folder_bytes(root)
    plan = upgrade.plan_upgrade(root)
    assert plan is not None and not plan.ok
    assert any("link" in x or "damaged" in x for x in plan.lost)  # (the device file is not read)
    with pytest.raises(upgrade.UpgradeError, match="nothing was changed"):
        upgrade.upgrade_project(root)
    assert folder_bytes(root) == files and unit_file.is_symlink()
    assert not (root / ".migration-backup-v1").exists()


def test_a_difference_found_after_the_write_puts_everything_back(tmp_path: Path) -> None:
    root = build("released", tmp_path / "p")
    as_format(root, 1)
    files = managed(root)

    def tamper() -> None:  # whatever goes wrong between the write and the check
        unit_file = next((root / "logical" / "units").glob("*.json"))
        doc = json.loads(unit_file.read_text(encoding="utf-8"))
        doc["units"][0]["name"] = doc["units"][0]["name"] + " (edited)"
        unit_file.write_bytes(canonical.dumps(doc))

    with pytest.raises(upgrade.UpgradeFailed, match="the check after the write") as err:
        upgrade.upgrade_project(root, on_written=tamper)
    assert err.value.rolled_back and "NOT" not in str(err.value)
    assert managed(root) == files  # the project is as it was, baselines and all
    assert any("model hash" in r for r in err.value.reasons)
    assert err.value.backup is not None
    record = json.loads((root / err.value.backup / "MIGRATION.json").read_text())
    assert record["status"] == "rolled_back"
    assert upgrade.upgrade_project(root) is not None  # and the next attempt works


def test_a_changed_baseline_is_found_by_the_check(tmp_path: Path) -> None:
    root = build("released", tmp_path / "p")
    as_format(root, 1)
    files = managed(root)

    def tamper() -> None:
        path = next(p for p in (root / "baselines").rglob("*.json"))
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["comment"] = doc["comment"] + " and more"
        path.write_bytes(canonical.dumps(doc))

    with pytest.raises(upgrade.UpgradeFailed) as err:
        upgrade.upgrade_project(root, on_written=tamper)
    assert any("baseline" in r.lower() for r in err.value.reasons)
    assert managed(root) == files


def test_a_failed_check_is_exit_1_on_the_command_line(
    tmp_path: Path, capsys, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = build("mini3", tmp_path / "p")
    as_format(root, 1)
    files = managed(root)
    monkeypatch.setattr(
        upgrade, "self_check", lambda *a, **k: ({"exports": False}, ["A full export differs."])
    )
    assert main(["migrate", str(root)]) == 1
    err = capsys.readouterr().err
    assert "Every file was put back" in err and "A full export differs." in err
    assert managed(root) == files


def test_an_earlier_backup_is_never_overwritten(tmp_path: Path) -> None:
    root = build("mini3", tmp_path / "p")
    as_format(root, 1)
    upgrade.upgrade_project(root)
    # the project goes back to format 1 (a Git checkout of an older state); the backup is still there
    meta = json.loads((root / "project.json").read_text(encoding="utf-8"))
    meta["schema_version"] = 1
    (root / "project.json").write_bytes(canonical.dumps(meta))
    with pytest.raises(upgrade.UpgradeError, match="earlier upgrade"):
        upgrade.upgrade_project(root)


# ---- random projects ------------------------------------------------------------------------------------------


_NAMES = st.text(
    alphabet=st.characters(categories=("L", "N"), max_codepoint=0x2FFF), min_size=1, max_size=18
).filter(lambda t: t.strip() == t)


@settings(max_examples=6, deadline=None, suppress_health_check=list(HealthCheck))
@given(
    st.sampled_from(["mini3", "sat15"]),
    st.lists(_NAMES, max_size=4),
    st.booleans(),
    st.booleans(),
)
def test_the_step_from_1_to_2_changes_nothing_in_a_random_project(
    base, names, generate, journal_on
) -> None:
    from harness_design_studio.core import journal
    from harness_design_studio.core.commands import Put, apply_ops
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.io.saver import save_project
    from harness_design_studio.core.samples import mini3, sat15

    with tempfile.TemporaryDirectory() as tmp:
        p = {"mini3": mini3, "sat15": sat15}[base]()
        for uid, name in zip(sorted(p.units), names, strict=False):
            apply_ops(p, [Put("units", evolve(p.units[uid], name=name))])
        if generate and not p.harnesses:
            generate_project(p)
        if journal_on:
            journal.start(p, "random")
        root = Path(tmp) / "p"
        save_project(p, root)
        old_hash, old_export = model_hash(load_project(root).project), full_export(root)
        as_format(root, 1)  # as a 1.17.x tool wrote it
        done = upgrade.upgrade_project(root)
        assert done is not None and all(done.self_check.values())
        assert model_hash(load_project(root).project) == old_hash
        assert full_export(root) == old_export
        assert ((root / "journal.jsonl").exists()) is journal_on
        assert not (root / "journal.json").exists()
