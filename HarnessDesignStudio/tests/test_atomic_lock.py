"""REQ-ATOMIC-01 / REQ-LOCK-01: crash-safe writes, clear disk errors, single-instance lock."""

import errno
import json
import os
import platform
import sys
from pathlib import Path

import pytest

from harness_design_studio.core.errors import ProjectLockedError, SaveError
from harness_design_studio.core.io import fs
from harness_design_studio.core.io.fs import ProjectLock, atomic_write_bytes, long_path, slug
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import evolve
from harness_design_studio.core.samples import mini3


def test_crash_before_rename_keeps_old_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "f.json"
    atomic_write_bytes(target, b"old")

    def boom(*a: object, **k: object) -> None:
        raise OSError(errno.EIO, "simulated power loss")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(SaveError):
        atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"old"
    assert not list(tmp_path.glob("*.tmp"))  # no litter


def test_backup_keeps_previous_version(tmp_path: Path) -> None:
    target = tmp_path / "f.json"
    atomic_write_bytes(target, b"v1")
    atomic_write_bytes(target, b"v2")
    assert target.read_bytes() == b"v2" and (tmp_path / "f.json.bak").read_bytes() == b"v1"


@pytest.mark.parametrize(
    ("code", "text"),
    [(errno.ENOSPC, "disk is full"), (errno.EACCES, "read-only"), (errno.EROFS, "read-only"),
     (errno.ENAMETOOLONG, "too long"), (errno.EIO, "could not be saved")],
)  # fmt: skip
def test_disk_errors_have_plain_messages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, code: int, text: str
) -> None:
    def fail(*a: object, **k: object) -> None:
        raise OSError(code, "x")

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(SaveError, match=text):
        atomic_write_bytes(tmp_path / "f.json", b"data")


@pytest.mark.skipif(sys.platform == "win32" or os.geteuid() == 0, reason="needs POSIX non-root")
def test_read_only_folder(tmp_path: Path) -> None:
    root = tmp_path / "p"
    save_project(mini3(), root)
    root.chmod(0o500)
    p = mini3()
    p.meta = evolve(p.meta, name="changed")
    try:
        with pytest.raises(SaveError):
            save_project(p, root)
    finally:
        root.chmod(0o700)


def test_partial_save_failure_leaves_valid_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "p"
    p = mini3()
    save_project(p, root)
    p.units["OBC"] = evolve(p.units["OBC"], notes="n")
    p.units["PCDU"] = evolve(p.units["PCDU"], notes="n")
    real = os.replace
    calls = {"n": 0}

    def flaky(src: str, dst: str) -> None:
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError(errno.ENOSPC, "full")
        real(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    with pytest.raises(SaveError):
        save_project(p, root)
    monkeypatch.undo()
    result = load_project(root)  # every file on disk is whole JSON
    assert not result.project.recovered


def test_slug_rules() -> None:
    assert slug("Power & Thermal") == "power-thermal"
    assert slug("CON") == "_con"
    assert slug("Антенна").startswith("x")
    assert len(slug("a" * 200)) <= 60
    assert slug("Антенна") == slug("Антенна") != slug("Радио")


def test_long_path_noop_on_posix(tmp_path: Path) -> None:
    if sys.platform != "win32":
        assert long_path(tmp_path) == tmp_path


def _write_lock(path: Path, pid: int, host: str) -> None:
    (path / ".harness.lock").write_text(f'{{"pid": {pid}, "host": "{host}", "since": 0}}')


def test_lock_blocks_second_instance(tmp_path: Path) -> None:
    with ProjectLock(tmp_path):
        assert (tmp_path / ".harness.lock").exists()
        with pytest.raises(ProjectLockedError):
            ProjectLock(tmp_path).acquire()
    assert not (tmp_path / ".harness.lock").exists()


def test_lock_held_by_other_host_blocks(tmp_path: Path) -> None:
    _write_lock(tmp_path, 1, "other-machine")
    with pytest.raises(ProjectLockedError):
        ProjectLock(tmp_path).acquire()


def test_stale_lock_is_taken_over(tmp_path: Path) -> None:
    _write_lock(tmp_path, 999999999, platform.node())
    with ProjectLock(tmp_path):
        info = json.loads((tmp_path / ".harness.lock").read_text())
        assert info["pid"] == os.getpid() and info["host"] == platform.node()  # the new owner
    assert not (tmp_path / ".harness.lock").exists()  # released like any lock


def test_corrupt_lock_is_stale(tmp_path: Path) -> None:
    (tmp_path / ".harness.lock").write_text("garbage")
    with ProjectLock(tmp_path):
        info = json.loads((tmp_path / ".harness.lock").read_text())
        assert info["pid"] == os.getpid() and info["host"] == platform.node()
    assert not (tmp_path / ".harness.lock").exists()


def test_live_local_lock_blocks(tmp_path: Path) -> None:
    _write_lock(tmp_path, 1, platform.node())
    if sys.platform != "win32":  # pid 1 exists on POSIX hosts
        with pytest.raises(ProjectLockedError):
            ProjectLock(tmp_path).acquire()


def test_own_pid_lock_still_blocks(tmp_path: Path) -> None:
    held = ProjectLock(tmp_path)
    if sys.platform == "win32":
        held.acquire()  # a file written by hand has no handle behind it, so hold a real one
    else:
        _write_lock(tmp_path, os.getpid(), platform.node())
    try:
        with pytest.raises(ProjectLockedError):
            ProjectLock(tmp_path).acquire()
    finally:
        held.release()


def test_pid_alive_edge_cases() -> None:
    assert fs._pid_alive(os.getpid())
    assert not fs._pid_alive(0)
    assert not fs._pid_alive(-5)
