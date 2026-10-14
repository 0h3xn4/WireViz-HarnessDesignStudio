"""A-7 to A-11: stale locks (reboot, reused process number), saves never read through links,
migration backups, file modes under a umask, and temp files left by a killed save."""

import json
import os
import platform
import stat
import sys
from pathlib import Path

import pytest

from harness_design_studio.core.errors import ProjectLockedError, SaveError
from harness_design_studio.core.io import fs
from harness_design_studio.core.io.fs import ProjectLock, atomic_write_bytes
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import migrate_project, save_project
from harness_design_studio.core.model import Waiver, evolve
from harness_design_studio.core.samples import mini3
from tests.helpers import copy_project

V0 = Path(__file__).parent / "fixtures" / "v0_project"
LINUX = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="needs /proc")


def _write_lock(path: Path, **info: object) -> None:
    (path / ".harness.lock").write_text(json.dumps(info))


# ---- A-7: stale locks --------------------------------------------------------------------------


@LINUX
def test_a_lock_written_before_a_reboot_is_stale(tmp_path: Path) -> None:
    _write_lock(
        tmp_path, pid=os.getpid(), host=platform.node(), since=0, boot="an-older-boot", start="1"
    )
    with ProjectLock(tmp_path):  # our own pid is alive, but the lock is from another boot
        pass


@LINUX
def test_a_reused_process_number_is_stale(tmp_path: Path) -> None:
    boot = fs._boot_id()
    _write_lock(tmp_path, pid=os.getpid(), host=platform.node(), since=0, boot=boot, start="1")
    with ProjectLock(tmp_path):
        pass


@LINUX
def test_a_lock_of_a_live_process_still_blocks_and_names_the_file(tmp_path: Path) -> None:
    with ProjectLock(tmp_path):
        info = json.loads((tmp_path / ".harness.lock").read_text())
        assert info["boot"] == fs._boot_id() and info["start"] == fs._start_time(os.getpid())
        with pytest.raises(ProjectLockedError) as err:
            ProjectLock(tmp_path).acquire()
    text = str(err.value)
    assert "already open" in text and str(tmp_path / ".harness.lock") in text


@LINUX
def test_a_renamed_computer_is_recognised_by_the_boot_id(tmp_path: Path) -> None:
    _write_lock(
        tmp_path,
        pid=999999999,
        host="the-old-name",
        since=0,
        boot=fs._boot_id(),
        start="1",
    )
    with ProjectLock(tmp_path):  # same running system, process gone: stale
        pass


def test_a_lock_of_another_computer_is_kept_and_says_how_to_remove_it(tmp_path: Path) -> None:
    _write_lock(tmp_path, pid=1, host="other-machine", since=0, boot="not-our-boot")
    with pytest.raises(ProjectLockedError) as err:
        ProjectLock(tmp_path).acquire()
    text = str(err.value)
    assert "other-machine" in text and "delete the lock file" in text
    assert str(tmp_path / ".harness.lock") in text
    assert (tmp_path / ".harness.lock").exists()


# ---- A-8: no reading through links -------------------------------------------------------------


def test_saving_over_a_link_does_not_copy_the_linked_content_into_a_backup(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET OUTSIDE")
    p = mini3()
    p.waivers["r.OBC"] = Waiver(
        id="r.OBC", rule="r", object_id="OBC", justification="accepted by the team"
    )
    root = tmp_path / "proj"
    save_project(p, root)
    (root / "waivers.json").unlink()
    (root / "waivers.json").symlink_to(secret)  # planted while the project was open
    p.waivers["r.OBC"] = evolve(p.waivers["r.OBC"], justification="accepted again by the team")
    save_project(p, root)
    assert not (root / "waivers.json").is_symlink()
    assert secret.read_text() == "TOP SECRET OUTSIDE"
    for f in root.rglob("*"):
        if f.is_file():
            assert b"TOP SECRET" not in f.read_bytes(), f


def test_a_link_whose_content_equals_the_new_file_is_still_replaced(tmp_path: Path) -> None:
    p = mini3()
    root = tmp_path / "proj"
    save_project(p, root)
    target = root / "project.json"
    same = tmp_path / "same.json"
    same.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(same)
    p.meta = evolve(p.meta, tool_version="")  # a save writes the same bytes as `same`
    save_project(p, root)
    assert not target.is_symlink()


def test_the_migration_backup_does_not_copy_linked_files(tmp_path: Path) -> None:
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET OUTSIDE")
    root = copy_project(V0, tmp_path / "p")
    units = root / "logical" / "units" / "avionics.json"
    loaded = load_project(root)
    units.unlink()
    units.symlink_to(secret)
    save_project(loaded.project, root)
    backup = root / ".migration-backup-v0"
    assert backup.is_dir() and not (backup / "logical" / "units" / "avionics.json").exists()
    for f in root.rglob("*"):
        if f.is_file():
            assert b"TOP SECRET" not in f.read_bytes(), f


# ---- A-9: the migration backup ------------------------------------------------------------------


def test_a_backup_name_that_is_a_link_is_refused(tmp_path: Path) -> None:
    root = copy_project(V0, tmp_path / "p")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / ".migration-backup-v0").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(SaveError, match="migration-backup"):
        migrate_project(root)
    assert not list(elsewhere.iterdir())
    assert load_project(root).project.migrated_from == 0  # nothing was upgraded


def test_a_dangling_backup_link_is_refused_and_a_good_backup_leaves_no_partial_folder(
    tmp_path: Path,
) -> None:
    root = copy_project(V0, tmp_path / "p")
    (root / ".migration-backup-v0").symlink_to(tmp_path / "nowhere", target_is_directory=True)
    with pytest.raises(SaveError):
        migrate_project(root)
    (root / ".migration-backup-v0").unlink()
    (root / ".migration-backup-v0.partial").mkdir()  # left by a killed upgrade
    (root / ".migration-backup-v0.partial" / "junk").write_text("x")
    assert migrate_project(root) is not None
    assert (root / ".migration-backup-v0" / "project.json").is_file()
    assert not (root / ".migration-backup-v0.partial").exists()


# ---- A-10: modes and litter ---------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
@pytest.mark.parametrize(("umask", "mode"), [(0o077, 0o600), (0o022, 0o644), (0o002, 0o664)])
def test_a_new_file_follows_the_umask(tmp_path: Path, umask: int, mode: int) -> None:
    old = os.umask(umask)
    try:
        atomic_write_bytes(tmp_path / "f.json", b"{}")
    finally:
        os.umask(old)
    assert stat.S_IMODE((tmp_path / "f.json").stat().st_mode) == mode


def test_locking_a_folder_that_is_not_a_project_leaves_nothing_behind(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_text("hello")
    with ProjectLock(tmp_path):
        assert sorted(p.name for p in tmp_path.iterdir()) == ["notes.txt"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["notes.txt"]


def test_an_empty_folder_and_a_project_are_still_locked(tmp_path: Path) -> None:
    with ProjectLock(tmp_path):
        assert (tmp_path / ".harness.lock").exists()
    save_project(mini3(), tmp_path / "p")
    with ProjectLock(tmp_path / "p"), pytest.raises(ProjectLockedError):
        ProjectLock(tmp_path / "p").acquire()


# ---- A-11: temp files of a killed save ---------------------------------------------------------


def test_a_save_removes_temp_files_left_by_a_killed_save(tmp_path: Path) -> None:
    root = tmp_path / "p"
    p = mini3()
    save_project(p, root)
    left = [
        root / ".waivers.json.4j31mntn.tmp",
        root / "logical" / ".layout.json.ab12cd34.tmp",
        root / "config" / ".derating.json.bak.zz99yy88.tmp",
    ]
    keep = [root / ".notes.tmp", root / "mine.tmp", root / "logical" / ".keep.txt.ab12cd34.tmp"]
    for f in [*left, *keep]:
        f.write_text("{}")
    p.meta = evolve(p.meta, name="changed")
    save_project(p, root)
    assert not any(f.exists() for f in left)
    assert all(f.exists() for f in keep)
