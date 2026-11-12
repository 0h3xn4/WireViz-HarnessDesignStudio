# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-222 (owner's answer B6, 2026-11-10): the files the tool writes hold a person's name only when
the person typed it. No user name of the operating system, no Git `user.name` and no computer name
is looked up: not in the run record, the change journal, the change log of a release, the release
record or the project lock file."""

import json
import platform
import re
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.errors import ProjectLockedError
from harness_design_studio.core.io import fs
from harness_design_studio.core.io.fs import ProjectLock
from harness_design_studio.core.io.saver import save_project
from tests.test_change_control import REASON, WHEN, full, releasable

LOGIN = "zq-login-name"
GIT_NAME = "Zq Git Person"
TYPED = "Typed Person"


@pytest.fixture
def no_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every place a name could be looked up has a distinctive one."""
    config = tmp_path / "gitconfig"
    config.write_text(f"[user]\n\tname = {GIT_NAME}\n", encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))
    for var in ("USER", "USERNAME", "LOGNAME"):
        monkeypatch.setenv(var, LOGIN)
    for var in ("GIT_AUTHOR_NAME", "GIT_COMMITTER_NAME"):
        monkeypatch.setenv(var, GIT_NAME)
    monkeypatch.delenv("HARNESS_AUTHOR", raising=False)


def _texts(folder: Path) -> dict[str, str]:
    return {
        str(p.relative_to(folder)): p.read_bytes().decode("utf-8", errors="replace")
        for p in sorted(folder.rglob("*"))
        if p.is_file() and p.suffix in {".json", ".csv", ".md", ".txt", ".yaml", ".lock", ""}
    }


def _host() -> str | None:
    """The computer's name, when it is long enough to be told apart from other text."""
    name = platform.node()
    return name if len(name) >= 4 else None


def _assert_no_looked_up_name(texts: dict[str, str]) -> None:
    host = _host()
    for name, text in texts.items():
        assert LOGIN not in text, name
        assert GIT_NAME not in text, name
        if host is not None:
            assert not re.search(rf"(?<![\w.-]){re.escape(host)}(?![\w.-])", text), name


@pytest.mark.usefixtures("no_names")
def test_run_record_journal_release_and_lock_hold_only_typed_names(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = tmp_path / "proj"
    save_project(p, folder)
    assert cli_main(["journal", str(folder), "--start"]) == 0
    # a change of a configuration value: a journal entry without a typed name
    assert cli_main(["config", str(folder), "--distinct-roles", "on"]) in (0, 1)
    assert cli_main(["--author", TYPED, "config", str(folder), "--distinct-roles", "off"]) in (0, 1)
    assert cli_main(["generate", str(folder), "--run-record"]) in (0, 1)
    assert cli_main(["export", str(folder)]) in (0, 1)
    common = ["--date", WHEN]
    assert cli_main(["review", str(folder), hid, "--by", TYPED, *common]) == 0
    release = ["release", str(folder), hid, "--by", TYPED, "--checker", "Checking Person"]
    release += ["--comment", "a long enough comment", *common]
    release += ["--accept-placeholders", REASON, "--accept-unapproved-parts", REASON]
    assert cli_main(release) == 0
    with ProjectLock(folder):
        lock = json.loads((folder / fs.LOCK_NAME).read_text(encoding="utf-8"))
        texts = _texts(folder)
    assert set(lock) <= {"pid", "install", "host", "since", "boot", "start"}
    assert lock["host"] == fs.HOST_NOT_RECORDED and lock["install"] == fs.install_id()
    _assert_no_looked_up_name(texts)
    record = json.loads((folder / "outputs" / "run_record.json").read_text(encoding="utf-8"))
    assert record["operator"] == "unknown"
    lines = (folder / "journal.jsonl").read_text(encoding="utf-8").splitlines()
    authors = {json.loads(line)["author"] for line in lines}
    assert "unknown" in authors and TYPED in authors  # nothing looked up; a typed name is kept
    assert any(TYPED in text for name, text in texts.items() if "journal" not in name)


@pytest.mark.usefixtures("no_names")
def test_a_typed_author_is_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p = full()
    folder = tmp_path / "proj"
    save_project(p, folder)
    monkeypatch.setenv("HARNESS_AUTHOR", "Set By The Person")
    assert cli_main(["generate", str(folder), "--run-record", "--author", TYPED]) in (0, 1)
    record = json.loads((folder / "outputs" / "run_record.json").read_text(encoding="utf-8"))
    assert record["operator"] == TYPED
    assert cli_main(["generate", str(folder), "--run-record"]) in (0, 1)
    record = json.loads((folder / "outputs" / "run_record.json").read_text(encoding="utf-8"))
    assert record["operator"] == "Set By The Person"


def test_the_install_id_is_random_kept_and_says_nothing(tmp_path: Path) -> None:
    first = fs.install_id()
    assert re.fullmatch(r"[0-9a-f]{32}", first) and fs.install_id() == first
    stored = fs.install_id.__globals__["_ids"]  # a new process reads it back from the file
    stored.clear()
    assert fs.install_id() == first
    host = _host()
    assert host is None or host.lower() not in first


def test_a_damaged_id_file_is_replaced(tmp_path: Path) -> None:
    from harness_design_studio.core.extensions.trust import settings_dir

    path = settings_dir() / fs.ID_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not an id\n", encoding="ascii")
    fs.install_id.__globals__["_ids"].clear()
    made = fs.install_id()
    assert path.read_text(encoding="ascii").strip() == made


def test_a_lock_file_of_an_older_version_is_respected(tmp_path: Path) -> None:
    """Versions before D-222 wrote the computer's name under "host" and no install id. Such a
    file cannot be checked from here: the project counts as open elsewhere (the way out is to
    delete the lock file), and the name in it is not repeated."""
    (tmp_path / fs.LOCK_NAME).write_text(
        json.dumps({"pid": 1, "host": platform.node() or "a-computer", "since": 0}),
        encoding="utf-8",
    )
    with pytest.raises(ProjectLockedError) as err:
        ProjectLock(tmp_path).acquire()
    text = str(err.value)
    assert "delete the lock file" in text and str(tmp_path / fs.LOCK_NAME) in text
    host = _host()
    assert host is None or f"'{host}'" not in text
    assert (tmp_path / fs.LOCK_NAME).exists()


def _no_settings_folder() -> Path:
    raise RuntimeError("Could not determine home directory.")


def test_a_lock_is_taken_when_no_settings_folder_can_be_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A program started with an empty environment has no home folder (Path.home() raises on
    Windows): the lock still works, with an id for this process alone that stays the same."""
    from harness_design_studio.core.extensions import trust

    monkeypatch.setattr(trust, "settings_dir", _no_settings_folder)
    first = fs.install_id()
    assert re.fullmatch(r"[0-9a-f]{32}", first) and fs.install_id() == first
    with ProjectLock(tmp_path):
        lock = json.loads((tmp_path / fs.LOCK_NAME).read_text(encoding="utf-8"))
        assert lock["install"] == first
        with pytest.raises(ProjectLockedError):  # the same process: still refused
            ProjectLock(tmp_path).acquire()
    assert not (tmp_path / fs.LOCK_NAME).exists()


def test_a_lock_is_taken_when_the_settings_folder_cannot_be_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    blocked = tmp_path / "a-file-not-a-folder"
    blocked.write_text("x", encoding="utf-8")
    monkeypatch.setenv("HARNESS_DESIGN_STUDIO_CONFIG_DIR", str(blocked / "settings"))
    fs.install_id.__globals__["_ids"].clear()
    first = fs.install_id()
    assert re.fullmatch(r"[0-9a-f]{32}", first) and fs.install_id() == first
    assert not (blocked / "settings").exists()
    project = tmp_path / "p"
    project.mkdir()
    with ProjectLock(project):
        lock = json.loads((project / fs.LOCK_NAME).read_text(encoding="utf-8"))
        assert lock["install"] == first
    assert not (project / fs.LOCK_NAME).exists()


def test_a_program_with_an_empty_environment_can_take_a_lock(tmp_path: Path) -> None:
    """The case of the Windows runner, made on any system: no HOME, no APPDATA, no settings
    folder override, and Path.home() raising."""
    import subprocess
    import sys

    script = (
        "import pathlib, sys\n"
        "def no_home(cls):\n"
        "    raise RuntimeError('Could not determine home directory.')\n"
        "pathlib.Path.home = classmethod(no_home)\n"
        "from harness_design_studio.core.io.fs import ProjectLock\n"
        "with ProjectLock(pathlib.Path(sys.argv[1])):\n"
        "    pass\n"
        "print('ok')\n"
    )
    root = Path(__file__).resolve().parents[1]
    done = subprocess.run(  # noqa: S603 (our own interpreter and a fixed script)
        [sys.executable, "-c", script, str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=120,
        env={"PYTHONPATH": str(root / "src"), "PATH": "/usr/bin:/bin"},
        check=False,
    )
    assert done.returncode == 0 and done.stdout.strip() == "ok", done.stderr[-2000:]
