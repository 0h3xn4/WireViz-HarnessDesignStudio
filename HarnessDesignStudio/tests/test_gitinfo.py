"""Who made the last change: the commit reader that never starts `git` (D-164). The tests build
real repositories with the `git` program (skipped when it is not installed) and compare."""

import shutil
import subprocess
import zlib
from pathlib import Path

import pytest

from harness_design_studio.core.vcs import gitinfo
from harness_design_studio.core.vcs.gitinfo import find_git_dir, last_commit

GIT = shutil.which("git")
needs_git = pytest.mark.skipif(GIT is None, reason="needs the git program")

ENV = {
    "GIT_AUTHOR_NAME": "Ada Lovelace",
    "GIT_AUTHOR_EMAIL": "ada@example.org",
    "GIT_COMMITTER_NAME": "Bob Committer",
    "GIT_COMMITTER_EMAIL": "bob@example.org",
    "GIT_AUTHOR_DATE": "2026-03-04T05:06:07-0230",
    "GIT_COMMITTER_DATE": "2026-03-04T05:06:07-0230",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
    "HOME": "/nonexistent",
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


def git(folder: Path, *args: str) -> str:
    done = subprocess.run(  # noqa: S603 (tests only: fixed arguments)
        [GIT or "git", *args], cwd=folder, env=ENV, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def repo(tmp_path: Path, commits: int = 1) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    for i in range(commits):
        (tmp_path / "project.txt").write_text(f"version {i}\n" * (i + 1))
        git(tmp_path, "add", "-A")
        git(tmp_path, "commit", "-q", "-m", f"Change number {i}\n\nA longer description.")
    return tmp_path


@needs_git
def test_a_loose_commit_is_read(tmp_path: Path) -> None:
    repo(tmp_path, 2)
    info = last_commit(tmp_path)
    assert info is not None
    assert info.commit == git(tmp_path, "rev-parse", "HEAD")
    assert (info.author, info.subject, info.branch) == ("Ada Lovelace", "Change number 1", "main")
    assert info.when == "2026-03-04 05:06 -0230"
    assert info.short == info.commit[:7]


@needs_git
def test_the_e_mail_address_is_not_kept(tmp_path: Path) -> None:
    repo(tmp_path)
    info = last_commit(tmp_path)
    assert info is not None
    assert "example.org" not in repr(info) and "Bob" not in repr(info)


@needs_git
def test_a_packed_repository_is_read(tmp_path: Path) -> None:
    repo(tmp_path, 6)
    git(tmp_path, "repack", "-adf", "--depth=50", "-q")
    git(tmp_path, "pack-refs", "--all")
    git(tmp_path, "prune-packed")
    assert not list((tmp_path / ".git" / "objects").glob("??/*"))  # nothing loose is left
    info = last_commit(tmp_path)
    assert info is not None
    assert info.commit == git(tmp_path, "rev-parse", "HEAD")
    assert info.subject == "Change number 5"


@needs_git
def test_a_folder_inside_the_repository_finds_it(tmp_path: Path) -> None:
    repo(tmp_path)
    deep = tmp_path / "a" / "b"
    deep.mkdir(parents=True)
    info = last_commit(deep)
    assert info is not None and info.author == "Ada Lovelace"


@needs_git
def test_a_detached_head_has_no_branch(tmp_path: Path) -> None:
    repo(tmp_path, 2)
    git(tmp_path, "checkout", "-q", "--detach", "HEAD~1")
    info = last_commit(tmp_path)
    assert info is not None and info.branch == "" and info.subject == "Change number 0"


@needs_git
def test_a_linked_worktree_is_read(tmp_path: Path) -> None:
    main = tmp_path / "main"
    main.mkdir()
    repo(main)
    other = tmp_path / "other"
    git(main, "worktree", "add", "-q", "-b", "side", str(other))
    info = last_commit(other)
    assert info is not None and info.branch == "side" and info.subject == "Change number 0"


def test_no_repository_gives_none(tmp_path: Path) -> None:
    assert last_commit(tmp_path) is None
    assert find_git_dir(tmp_path / "missing") is None


@needs_git
def test_a_repository_without_a_commit_gives_none(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q", "-b", "main")
    assert last_commit(tmp_path) is None


@needs_git
def test_damaged_files_give_none_not_an_error(tmp_path: Path) -> None:
    repo(tmp_path)
    sha = git(tmp_path, "rev-parse", "HEAD")
    obj = tmp_path / ".git" / "objects" / sha[:2] / sha[2:]
    obj.chmod(0o644)
    obj.write_bytes(b"not zlib at all")
    assert last_commit(tmp_path) is None
    obj.write_bytes(zlib.compress(b"commit 5\0short"))
    assert last_commit(tmp_path) is None
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/../../etc/passwd\n")
    assert last_commit(tmp_path) is None
    (tmp_path / ".git" / "HEAD").write_text("garbage")
    assert last_commit(tmp_path) is None


@needs_git
def test_a_bomb_in_an_object_is_refused(tmp_path: Path) -> None:
    repo(tmp_path)
    sha = git(tmp_path, "rev-parse", "HEAD")
    obj = tmp_path / ".git" / "objects" / sha[:2] / sha[2:]
    obj.chmod(0o644)
    obj.write_bytes(zlib.compress(b"commit 99999999\0" + b"\0" * (4 << 20)))
    assert last_commit(tmp_path) is None


@needs_git
def test_a_gitdir_file_pointing_nowhere_gives_none(tmp_path: Path) -> None:
    (tmp_path / ".git").write_text("gitdir: ../does-not-exist\n")
    assert last_commit(tmp_path) is None


def _delta(base: bytes, ops: list[bytes], result: int) -> bytes:
    def var(n: int) -> bytes:
        out = bytearray()
        while True:
            b = n & 0x7F
            n >>= 7
            out.append(b | (0x80 if n else 0))
            if not n:
                return bytes(out)

    return var(len(base)) + var(result) + b"".join(ops)


def test_a_delta_is_applied() -> None:
    base = b"0123456789"
    copy_2_to_5 = bytes([0x80 | 0x01 | 0x10, 2, 5])  # offset 2, size 5
    insert = bytes([3]) + b"abc"
    delta = _delta(base, [copy_2_to_5, insert], 8)
    assert gitinfo._apply_delta(base, delta) == b"23456abc"


def test_a_delta_that_lies_is_refused() -> None:
    base = b"0123456789"
    with pytest.raises(gitinfo._Unreadable):
        gitinfo._apply_delta(base, _delta(base, [bytes([0x80 | 0x01 | 0x10, 8, 5])], 5))  # past end
    with pytest.raises(gitinfo._Unreadable):
        gitinfo._apply_delta(base, _delta(b"x", [], 0))  # wrong base size
    with pytest.raises(gitinfo._Unreadable):
        gitinfo._apply_delta(base, _delta(base, [bytes([2]) + b"ab"], 9))  # wrong result size
