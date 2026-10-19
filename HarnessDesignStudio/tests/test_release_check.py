"""The release gate (tools/release_check.py) must not pass vacuously."""

import os
import subprocess
from pathlib import Path

import pytest

from harness_design_studio import __version__
from tools import release_check as rc


def make_root(tmp_path: Path, changelog: str) -> Path:
    (tmp_path / "pyproject.toml").write_text(f'[project]\nversion = "{__version__}"\n')
    (tmp_path / "CHANGELOG.md").write_text(changelog)
    return tmp_path


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


CLEAN = f"# Changelog\n\n## Unreleased\n\n## {__version__} (released)\n\n- text\n"


@pytest.fixture
def release_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rc, "QUICK", False)


def test_unreleased_text_is_found_up_to_the_next_heading() -> None:
    assert rc.unreleased_text("## Unreleased (after 1.0)\n\nintro\n\n- a\n\n## 1.0\n\n- b\n") == (
        "intro\n\n- a"
    )
    assert rc.unreleased_text("## Unreleased\n\n## 1.0\n- b\n") == ""
    assert rc.unreleased_text("## 1.0\n- b\n") == ""


def test_a_release_with_text_under_unreleased_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release_run: None
) -> None:
    root = make_root(
        tmp_path, CLEAN.replace("## Unreleased\n", "## Unreleased\n\n- not released\n")
    )
    git(root, "init", "-q")
    monkeypatch.setattr(rc, "ROOT", root)
    ok, detail = rc.versions()
    assert not ok and "Unreleased" in detail


def test_a_release_that_reuses_a_tagged_version_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, release_run: None
) -> None:
    root = make_root(tmp_path, CLEAN)
    monkeypatch.setattr(rc, "ROOT", root)
    git(root, "init", "-q")
    ok, detail = rc.versions()
    assert ok, detail  # nothing tagged, nothing unreleased
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "x")
    git(root, "tag", f"v{__version__}")
    ok, detail = rc.versions()
    assert not ok and f"v{__version__} already exists" in detail


def test_a_quick_run_does_not_apply_the_release_time_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = make_root(tmp_path, CLEAN.replace("## Unreleased\n", "## Unreleased\n\n- a\n"))
    monkeypatch.setattr(rc, "ROOT", root)
    monkeypatch.setattr(rc, "QUICK", True)
    ok, _ = rc.versions()
    assert ok


def test_skipped_tests_are_counted_and_only_listed_reasons_are_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = (
        "SKIPPED [2] tests/test_prototype.py:33: no Chromium available\n"
        "SKIPPED [1] tests/test_atomic_lock.py:59: needs POSIX non-root\n"
        "3 passed, 3 skipped in 1s\n"
    )
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    total, refused = rc.skipped_tests(out)
    assert total == 3 and refused == ["tests/test_prototype.py:33 no Chromium available"]
    monkeypatch.setattr(
        os, "geteuid", lambda: 1000, raising=False
    )  # the root-only skip is fine only as root
    assert len(rc.skipped_tests(out)[1]) == 2
    assert rc.skipped_tests("5 passed in 1s\n") == (0, [])


def test_the_suite_step_fails_on_a_refused_skip_and_requires_the_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, str] = {}

    def fake_run(
        cmd: list[str], timeout: int = 0, env: dict[str, str] | None = None
    ) -> tuple[int, str]:
        seen.update(env or {})
        return 0, (
            "SKIPPED [1] tests/test_outputs.py:136: poppler not installed\n"
            "1 passed, 1 skipped in 1s"
        )

    monkeypatch.setattr(rc, "run", fake_run)
    ok, detail = rc.run_suite([])
    assert seen["HARNESS_REQUIRE_BROWSER"] == "1"
    assert not ok and "1 skipped" in detail and "poppler" in detail
