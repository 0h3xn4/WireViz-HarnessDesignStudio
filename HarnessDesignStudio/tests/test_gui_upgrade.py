# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-MIGRATE-03. No silent upgrade in the editor (plan 2.3, point 5): a project in an older file
format is not upgraded, not even in memory for editing, until the person says so. The question is
asked once, on opening, with *Upgrade*, *Open read-only* and *Cancel*; the format used here is the
fake one of `tests/migration_support.py` (the shipped tool has only one format)."""

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core.io import upgrade  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.dialogs import UpgradeDialog  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.migration_support import (  # noqa: E402
    build,
    folder_bytes,
    install_fake_format,
)
from tests.migration_support import fake_v2 as fake_v2  # noqa: E402,F401  (a fixture)


@pytest.fixture
def win(qtbot, tmp_path):
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    return w


def old_project(tmp_path: Path, fake_v2) -> Path:
    root = build("sat15", tmp_path / "old")
    fake_v2()  # (this tool now writes format 2 and the project is in format 1)
    return root


def answers(win, *replies: str) -> list[tuple[int, int]]:
    asked: list[tuple[int, int]] = []
    queue = list(replies)

    def ask(old: int, new: int) -> str:
        asked.append((old, new))
        return queue.pop(0)

    win.ask_upgrade = ask
    return asked


def test_upgrade_is_asked_once_and_does_the_upgrade(win, tmp_path: Path, fake_v2) -> None:
    root = old_project(tmp_path, fake_v2)
    original = {k: v for k, v in folder_bytes(root).items() if k.endswith(".json")}
    asked = answers(win, "upgrade")
    assert win.open_project(root)
    assert asked == [(1, 2)]  # once
    assert not win.ctl.read_only and win.ctl.project.migrated_from is None
    assert json.loads((root / "project.json").read_text())["schema_version"] == 2
    backup = root / ".migration-backup-v1"
    assert (backup / "MIGRATION.json").is_file()
    for rel, data in original.items():
        assert (backup / rel).read_bytes() == data  # the original is kept
    assert any("Upgraded from format 1 to 2." in m for m in win.toasts.messages)
    win.ctl.release()


def test_open_read_only_changes_nothing_on_disk(win, tmp_path: Path, fake_v2) -> None:
    root = old_project(tmp_path, fake_v2)
    files = folder_bytes(root)
    asked = answers(win, "read_only")
    assert win.open_project(root)
    assert asked == [(1, 2)] and win.ctl.read_only
    assert win.ctl.project.migrated_from == 1  # read in memory only
    assert folder_bytes(root) == files and not (root / ".migration-backup-v1").exists()
    win.ctl.release()


def test_cancel_opens_nothing_and_changes_nothing(win, tmp_path: Path, fake_v2) -> None:
    root = old_project(tmp_path, fake_v2)
    files = folder_bytes(root)
    answers(win, "cancel")
    assert win.open_project(root) is False
    assert win.ctl.root is None
    assert folder_bytes(root) == files


def test_a_current_project_is_not_asked_about(win, tmp_path: Path) -> None:
    root = build("mini3", tmp_path / "now")
    asked = answers(win)  # no reply ready: asking would fail
    assert win.open_project(root)
    assert asked == [] and not win.ctl.read_only
    win.ctl.release()


def test_the_controller_never_opens_an_old_format_for_editing_without_the_answer(
    tmp_path: Path, fake_v2, qtbot
) -> None:
    from harness_design_studio.gui.controller import EditorController

    root = old_project(tmp_path, fake_v2)
    files = folder_bytes(root)
    ctl = EditorController(drc_delay_ms=600_000)
    ctl.open_path(root)  # (no `upgrade=True`)
    assert ctl.read_only and strings.OPEN_OLD_FORMAT.format(old=1) == ctl.open_note
    assert folder_bytes(root) == files
    ctl.release()


def test_a_failed_upgrade_says_so_and_leaves_the_project_as_it_was(
    win, tmp_path: Path, fake_v2, monkeypatch
) -> None:
    root = old_project(tmp_path, fake_v2)
    files = {k: v for k, v in folder_bytes(root).items() if k.endswith(".json")}
    monkeypatch.setattr(
        upgrade, "self_check", lambda *a, **k: ({"exports": False}, ["A full export differs."])
    )
    answers(win, "upgrade")
    assert win.open_project(root) is False
    assert any("was not upgraded" in m and "put back" in m for m in win.toasts.messages)
    assert win.ctl.root is None
    after = {k: v for k, v in folder_bytes(root).items() if k.endswith(".json")}
    assert {k: v for k, v in after.items() if ".migration" not in k} == files


def test_the_question_has_the_words_of_the_plan(qtbot) -> None:
    dlg = UpgradeDialog(None, 1, 2)
    qtbot.addWidget(dlg)
    dlg.show()
    assert dlg.body.text() == (
        "This project is in format 1. Upgrade? A copy of the original stays in "
        ".migration-backup-v1. Older tools can no longer edit it."
    )
    assert [b.text() for b in (dlg.upgrade, dlg.read_only, dlg.cancel)] == [
        "Upgrade",
        "Open read-only",
        "Cancel",
    ]
    assert dlg.cancel.isDefault() and not dlg.upgrade.isDefault()  # the safe answer is the default
    assert dlg.choice == "cancel"


@pytest.mark.parametrize(
    ("button", "choice", "accepted"),
    [("upgrade", "upgrade", True), ("read_only", "read_only", True), ("cancel", "cancel", False)],
)
def test_each_button_gives_its_answer(qtbot, button: str, choice: str, accepted: bool) -> None:
    dlg = UpgradeDialog(None, 1, 2)
    qtbot.addWidget(dlg)
    dlg.show()
    getattr(dlg, button).click()
    assert dlg.choice == choice and bool(dlg.result()) is accepted
    QApplication.processEvents()


def test_the_fake_format_helper_leaves_the_real_format_alone(tmp_path: Path, monkeypatch) -> None:
    from harness_design_studio.core.io import migrate

    before = migrate.current_version()
    with monkeypatch.context() as m:
        install_fake_format(m)
        assert migrate.current_version() == 2
    assert migrate.current_version() == before == 1
