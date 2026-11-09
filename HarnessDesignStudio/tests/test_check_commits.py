# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-206: the commit check (author address and DCO sign-off) that CI runs on a pull request."""

import subprocess
from pathlib import Path

import pytest

from tools import check_commits as cc


def _git(repo: Path, *args: str, email: str = "a@users.noreply.github.com") -> str:
    env = {
        "GIT_AUTHOR_NAME": "A",
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": "A",
        "GIT_COMMITTER_EMAIL": email,
        "HOME": str(repo),
        "PATH": "/usr/bin:/bin:/usr/local/bin",
    }
    return subprocess.run(
        ["git", *args], cwd=repo, env=env, capture_output=True, text=True, check=True
    ).stdout.strip()


def _commit(repo: Path, name: str, message: str, email: str) -> None:
    (repo / name).write_text(name)
    _git(repo, "add", name, email=email)
    _git(repo, "commit", "-q", "-m", message, email=email)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _commit(tmp_path, "base.txt", "base", "base@users.noreply.github.com")
    return tmp_path


def test_addresses() -> None:
    assert cc.address_ok("123+someone@users.noreply.github.com")
    assert cc.address_ok("someone@users.noreply.github.com")
    assert cc.address_ok("noreply@anthropic.com")
    assert not cc.address_ok("someone@example.org")
    assert not cc.address_ok("noreply@github.com")


def test_signoff_must_match_the_author() -> None:
    msg = "Fix\n\nSigned-off-by: A B <a@users.noreply.github.com>\n"
    assert cc.signed_off("a@users.noreply.github.com", msg)
    assert cc.signed_off("A@users.noreply.github.com", msg)
    assert not cc.signed_off("other@users.noreply.github.com", msg)
    assert not cc.signed_off("a@users.noreply.github.com", "Fix\n")


def test_a_clean_pull_request_passes(repo: Path) -> None:
    mail = "a@users.noreply.github.com"
    _commit(repo, "x.txt", f"x\n\nSigned-off-by: A <{mail}>", mail)
    found = cc.commits("HEAD~1", "HEAD", repo)
    assert len(found) == 1 and cc.problems(found, owner_pr=False) == []


def test_a_private_address_and_a_missing_signoff_are_found(repo: Path) -> None:
    _commit(repo, "x.txt", "x", "someone@example.org")
    found = cc.commits("HEAD~1", "HEAD", repo)
    bad = cc.problems(found, owner_pr=False)
    assert len(bad) == 2 and "noreply" in bad[0] and "DCO" in bad[1]


def test_the_owner_pull_request_needs_no_signoff_but_still_a_noreply_address(repo: Path) -> None:
    _commit(repo, "x.txt", "x", "noreply@anthropic.com")
    assert cc.problems(cc.commits("HEAD~1", "HEAD", repo), owner_pr=True) == []
    _commit(repo, "y.txt", "y", "me@example.org")
    assert len(cc.problems(cc.commits("HEAD~2", "HEAD", repo), owner_pr=True)) == 1


def test_merge_commits_are_not_checked(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "-b", "side")
    _commit(
        repo,
        "s.txt",
        "s\n\nSigned-off-by: A <a@users.noreply.github.com>",
        "a@users.noreply.github.com",
    )
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", "merge", "side", email="x@example.org")
    found = cc.commits(base, "HEAD", repo)
    assert all(email != "x@example.org" for _, email, _ in found)
