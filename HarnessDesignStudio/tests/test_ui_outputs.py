# mypy: disable-error-code="no-untyped-def,no-untyped-call"
# ruff: noqa: F811  (the fixtures are those of test_ux_rel_panel, imported by name)
"""UI overhaul M8: the Outputs area lists every exported file with its SHA-256 (worked out from the
files on disk in a helper thread) and says whether it still equals the export; the Revisions diff
agrees with the change records of `core.vcs` and carries the diff tints."""

import hashlib
import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt, QUrl  # noqa: E402
from PySide6.QtGui import QBrush  # noqa: E402

from harness_design_studio.core.outputs.build import MANIFEST, write_outputs  # noqa: E402
from harness_design_studio.core.vcs.diff import to_table  # noqa: E402
from harness_design_studio.core.vcs.timeline import compare_revisions  # noqa: E402
from harness_design_studio.gui import outputs_files, strings  # noqa: E402
from harness_design_studio.gui.lists_panel import ListsPanel  # noqa: E402
from harness_design_studio.gui.outputs_files import OutputsFiles  # noqa: E402
from tests.test_ux_rel_panel import (  # noqa: E402, F401
    ctl,
    make_panel,
    released,
    revise_and_edit,
)
from tests.ux_rel import dict_rows, themed  # noqa: E402


@pytest.fixture
def exported(ctl):
    folder = ctl.outputs_folder()
    assert folder is not None
    write_outputs(ctl.project, folder)
    return folder


def make_files(
    qtbot, ctl, opened: list[QUrl] | None = None, folder_answer: str | None = None
) -> OutputsFiles:
    panel = OutputsFiles(
        ctl,
        themed(),
        opener=(opened.append if opened is not None else lambda url: True),  # type: ignore[arg-type,return-value]
        ask_folder=lambda title: folder_answer,
    )
    qtbot.addWidget(panel)
    panel.resize(1000, 400)
    panel.show()
    panel.refresh()
    assert panel.wait_idle()
    return panel


def on_disk(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def test_every_file_is_listed_with_the_sha256_of_the_file_on_disk(qtbot, ctl, exported) -> None:
    panel = make_files(qtbot, ctl)
    rows = panel.rows()
    disk = on_disk(exported)
    assert {r["rel"] for r in rows} == set(disk)
    for r in rows:
        assert r["sha_full"] == disk[r["rel"]] and r["sha"] == disk[r["rel"]][:12]
    listed = json.loads((exported / MANIFEST).read_text())["files"]
    assert all(r["state"] == "pass" for r in rows if r["rel"] != MANIFEST)  # every file matches
    assert {f["path"] for f in listed} <= set(disk)
    manifest_row = next(r for r in rows if r["rel"] == MANIFEST)
    assert manifest_row["result"] == strings.OUT_STATE_MANIFEST
    assert "files in" in panel.summary.text()


def test_a_changed_a_missing_and_an_extra_file_are_told_apart_in_words(
    qtbot, ctl, exported
) -> None:
    panel = make_files(qtbot, ctl)
    some = [r["rel"] for r in panel.rows() if r["rel"] != MANIFEST][:2]
    (exported / some[0]).write_bytes(b"edited by hand")
    (exported / some[1]).unlink()
    (exported / "notes.txt").write_text("hello")
    panel.verify_btn.click()
    assert panel.wait_idle()
    by = {r["rel"]: r for r in panel.rows()}
    assert by[some[0]]["result"] == strings.OUT_STATE_CHANGED and by[some[0]]["state"] == "fail"
    assert by[some[1]]["result"] == strings.OUT_STATE_MISSING and by[some[1]]["state"] == "fail"
    assert (
        by["notes.txt"]["result"] == strings.OUT_STATE_UNLISTED
        and by["notes.txt"]["state"] == "warning"
    )
    assert by[some[0]]["sha_full"] == hashlib.sha256(b"edited by hand").hexdigest()
    assert "2 differ" in panel.summary.text()


def test_documents_have_their_type_format_scope_and_time(qtbot, ctl, exported) -> None:
    panel = make_files(qtbot, ctl)
    by = {r["rel"]: r for r in panel.rows()}
    wl = by["harnesses/W001/wirelist.csv"]
    assert (wl["doc"], wl["format"], wl["scope"]) == ("Wire list", "CSV", "W001")
    assert by["system/bom.csv"]["scope"] == strings.EXP_SYSTEM_SCOPE
    build = by["harnesses/W001/W001_build.xlsx"]  # the build workbook (D-169)
    assert (build["doc"], build["format"], build["scope"]) == ("Build workbook", "XLSX", "W001")
    assert by["harnesses/W001/W001.xlsx"]["doc"] == "Workbook (all tables)"
    assert len(wl["when"]) == len("2026-10-19 12:00") and wl["size"] > 0


def test_the_hashes_are_worked_out_in_a_helper_thread(qtbot, ctl, exported) -> None:
    panel = OutputsFiles(ctl, themed())
    qtbot.addWidget(panel)
    panel.refresh()
    assert panel.reading  # the call returned before the files were read
    assert panel.wait_idle() and panel.rows()
    panel.refresh()
    panel.refresh()  # a newer request replaces the one that runs
    assert panel.wait_idle() and len(panel.rows()) == len(on_disk(exported))


def test_nothing_exported_yet_says_so(qtbot, ctl) -> None:
    panel = make_files(qtbot, ctl)
    assert panel.rows() == [] and panel.table.empty_state.isVisibleTo(panel.table)  # type: ignore[attr-defined]


def test_open_reveal_and_copy_act_on_the_selected_files(qtbot, ctl, exported, tmp_path) -> None:
    opened: list[QUrl] = []
    dest = tmp_path / "copy"
    panel = make_files(qtbot, ctl, opened, str(dest))
    assert not panel.open_btn.isEnabled()
    assert panel.select_file("harnesses/W001/wirelist.csv") and panel.open_btn.isEnabled()
    panel.open_btn.click()
    panel.reveal_btn.click()
    assert [Path(u.toLocalFile()) for u in opened] == [  # (a URL has / where Windows has \)
        exported / "harnesses/W001/wirelist.csv",
        exported / "harnesses/W001",
    ]
    assert panel.copy_selected() == 1
    assert (dest / "harnesses/W001/wirelist.csv").read_bytes() == (
        exported / "harnesses/W001/wirelist.csv"
    ).read_bytes()
    assert panel.copy_selected() == 0  # the folder is not empty now
    assert panel.notice.isVisibleTo(panel)
    assert not (dest / MANIFEST).exists()


def test_the_manifest_is_never_copied(qtbot, ctl, exported, tmp_path) -> None:
    panel = make_files(qtbot, ctl)
    assert panel.select_file(MANIFEST)
    assert panel.copy_selected(tmp_path / "x") == 0
    assert not (tmp_path / "x").exists()


def test_the_lists_tab_shows_the_files_under_the_lists(qtbot, ctl, exported) -> None:
    panel = ListsPanel(ctl, themed())
    qtbot.addWidget(panel)
    panel.resize(1000, 700)
    panel.show()
    assert isinstance(panel.files, OutputsFiles)
    assert panel.split.widget(0) is panel.tabs and panel.split.widget(1) is panel.files
    panel.files.invalidate()
    assert panel.files.wait_idle() and panel.files.rows()


def test_gather_is_the_same_as_hashing_the_folder_by_hand(ctl, exported) -> None:
    facts = outputs_files.gather(exported)
    assert {f.rel: f.sha256 for f in facts} == on_disk(exported)
    assert all(f.listed == f.sha256 for f in facts if f.rel != MANIFEST)


# ---- Revisions ---------------------------------------------------------------------------------
def test_the_diff_agrees_with_the_change_records_of_core_vcs(qtbot, released, tmp_path) -> None:
    revise_and_edit(released)
    panel = make_panel(qtbot, released, tmp_path)
    panel.select_harness("W001")
    rows = dict_rows(panel.diff_model)
    diff = compare_revisions(released.project, "W001", "A", None)
    table = to_table(diff)[1:]
    assert len(rows) == len(table) > 0
    assert sorted((r["change_key"], r["id"]) for r in rows) == sorted((t[0], t[2]) for t in table)
    assert panel.summary.text().endswith(diff.summary()) or diff.summary() in panel.summary.text()


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_diff_rows_carry_the_tint_of_their_change_in_both_themes(
    qtbot, qapp, released, tmp_path, mode
) -> None:
    revise_and_edit(released)
    panel = make_panel(qtbot, released, tmp_path)
    theme = panel.diff_model.theme
    assert theme is not None
    theme.apply(qapp, mode)
    panel.select_harness("W001")
    model = panel.diff_model
    seen = set()
    for r, row in enumerate(dict_rows(model)):
        brush = model.data(model.index(r, 0), Qt.ItemDataRole.BackgroundRole)
        assert isinstance(brush, QBrush)
        assert brush.color() == theme.color(f"diff.{row['change_key']}")
        assert row["change"]  # the word says it too, never the colour alone
        seen.add(row["change_key"])
    assert "changed" in seen


def test_the_revisions_area_says_what_a_release_locks(qtbot, released, tmp_path) -> None:
    panel = make_panel(qtbot, released, tmp_path)
    panel.select_harness("W001")
    counts = panel.lock_counts("W001")
    assert counts.get("unit", 0) > 0 and counts.get("interface", 0) > 0
    assert panel.locks.isVisibleTo(panel) and "W001 revision A is released" in panel.locks.text()
    assert f"{counts['unit']} unit(s)" in panel.locks.text()
    panel.select_harness("W002")  # a draft locks nothing
    assert panel.lock_counts("W002") == {} and not panel.locks.isVisibleTo(panel)
