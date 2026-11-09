# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""REQ-OUT-08, REQ-GUI-10. The Export window can also write the open data (the files of the
`export-data` command) beside the outputs. The check box is off until the person ticks it and is
remembered; with it off the export writes exactly what it always wrote; with it on the same files
as the command go into the folder `data/` of the outputs folder, outside the manifest."""

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio import api  # noqa: E402
from harness_design_studio.core.outputs.build import build_outputs  # noqa: E402
from harness_design_studio.core.outputs.verify import (  # noqa: E402
    OPEN_DATA_FOLDER,
    read_folder,
    verify_outputs,
)
from harness_design_studio.gui import outputs_files, strings  # noqa: E402
from harness_design_studio.gui.export_dialog import ExportDialog  # noqa: E402
from tests.ux_rel import flatsat_controller, outputs_of, settings, themed  # noqa: E402


def export(dlg: ExportDialog, *, data: bool):
    dlg.open_data.setChecked(data)
    result = dlg.run()
    assert result is not None
    return result


def tree(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


@pytest.fixture(scope="module")
def both(tmp_path_factory):
    """One project exported twice: with the box off (the folder `off`), then with it on, and the
    files of `export-data` for the same project."""
    tmp = tmp_path_factory.mktemp("open-data")
    ctl = flatsat_controller(tmp)
    ui = settings(tmp)
    dlg = ExportDialog(ctl, themed(), settings=ui)
    assert not dlg.open_data.isChecked()  # (off by default)
    off = export(dlg, data=False)
    folder = outputs_of(ctl)
    before = tree(folder)
    on = export(dlg, data=True)
    after = tree(folder)
    cli = tmp / "cli-data"
    assert ctl.root is not None
    api.export_data(ctl.root, cli)
    yield {
        "ctl": ctl, "folder": folder, "off": off, "on": on, "before": before, "after": after,
        "cli": tree(cli), "ui": ui, "tmp": tmp,
    }  # fmt: skip
    dlg.close()


def test_the_check_box_is_off_by_default_and_worded_as_asked(qtbot, tmp_path) -> None:
    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed(), settings=settings(tmp_path))
    qtbot.addWidget(dlg)
    assert dlg.open_data.text() == strings.EXP_OPEN_DATA
    assert dlg.open_data.text() == "Include the open data (JSON and CSV of every result)"
    assert not dlg.open_data.isChecked() and dlg.open_data.isEnabled()
    assert dlg.open_data.accessibleName() and dlg.open_data.toolTip()
    bare = ExportDialog(flatsat_controller(tmp_path / "x"), themed())  # (no settings at all)
    qtbot.addWidget(bare)
    assert not bare.open_data.isChecked()


def test_the_choice_is_remembered_between_windows(qtbot, tmp_path) -> None:
    ui = settings(tmp_path)
    first = ExportDialog(flatsat_controller(tmp_path), themed(), settings=ui)
    qtbot.addWidget(first)
    first.open_data.setChecked(True)
    ui.sync()
    second = ExportDialog(
        flatsat_controller(tmp_path / "again"), themed(), settings=settings(tmp_path)
    )
    qtbot.addWidget(second)
    assert second.open_data.isChecked()
    second.open_data.setChecked(False)
    ui.sync()
    third = ExportDialog(
        flatsat_controller(tmp_path / "third"), themed(), settings=settings(tmp_path)
    )
    qtbot.addWidget(third)
    assert not third.open_data.isChecked()


def test_with_it_off_nothing_but_the_outputs_is_written(both) -> None:
    before = both["before"]
    assert not any(rel.startswith(f"{OPEN_DATA_FOLDER}/") for rel in before)
    assert both["off"].data == () and "manifest.json" in before


def test_the_bytes_of_an_export_with_it_off_are_those_of_the_core_build(both, tmp_path) -> None:
    ctl = both["ctl"]
    built = build_outputs(ctl.project, drawings=False)
    for rel, data in built.files.items():
        assert both["before"][rel] == data, rel
    listed = {rel for rel in both["before"] if rel != "manifest.json"}
    assert listed == set(built.files)  # (not one file more or less)


def test_with_it_on_the_files_of_export_data_are_written_into_data(both) -> None:
    cli = both["cli"]
    assert len(cli) > 30 and "provenance.json" in cli and "wire_sizing.csv" in cli
    written = {
        rel.removeprefix(f"{OPEN_DATA_FOLDER}/"): data
        for rel, data in both["after"].items()
        if rel.startswith(f"{OPEN_DATA_FOLDER}/")
    }
    assert written == cli  # (the same names and the same bytes as `export-data`)
    assert both["on"].data == tuple(sorted(cli))
    assert both["on"].count == both["off"].count  # (the outputs themselves are the same set)


def test_the_outputs_are_the_same_bytes_with_the_box_on_or_off(both) -> None:
    for rel, data in both["before"].items():
        assert both["after"][rel] == data, rel
    assert set(both["after"]) - set(both["before"]) == {
        f"{OPEN_DATA_FOLDER}/{name}" for name in both["cli"]
    }


def test_the_manifest_does_not_list_the_data_and_the_check_stays_quiet(both) -> None:
    folder = both["folder"]
    manifest = json.loads((folder / "manifest.json").read_text())
    assert not [f for f in manifest["files"] if f["path"].startswith(f"{OPEN_DATA_FOLDER}/")]
    assert both["after"]["manifest.json"] == both["before"]["manifest.json"]
    read = read_folder(folder)  # (what `verify DIR --outputs` reads: the data folder is no output)
    assert not [rel for rel in read if rel.startswith(f"{OPEN_DATA_FOLDER}/")]
    assert set(read) == set(both["before"])
    report = verify_outputs(both["ctl"].project, read)
    assert not [i for i in report.issues if i.code == "out_unlisted"]
    assert report.ok
    # a file that is not ours in another folder is still reported
    (folder / "extra").mkdir()
    (folder / "extra" / "note.txt").write_text("x")
    again = verify_outputs(both["ctl"].project, read_folder(folder))
    assert [i.object_id for i in again.issues if i.code == "out_unlisted"] == ["extra/note.txt"]
    (folder / "extra" / "note.txt").unlink()
    (folder / "extra").rmdir()


def test_the_result_says_where_the_data_went_and_the_outputs_tab_calls_it_open_data(
    both, qtbot
) -> None:
    dlg = ExportDialog(both["ctl"], themed(), settings=both["ui"])
    qtbot.addWidget(dlg)
    dlg.result_panel.set_result(both["on"])
    line = dlg.result_panel.data_line
    assert not line.isHidden()
    assert line.text() == strings.EXP_DATA_LINE.format(
        len(both["on"].data), both["folder"] / OPEN_DATA_FOLDER
    )
    dlg.result_panel.set_result(both["off"])
    assert dlg.result_panel.data_line.isHidden()
    facts = outputs_files.gather(both["folder"])
    by = {f.rel: outputs_files.state_of(f) for f in facts}
    assert by[f"{OPEN_DATA_FOLDER}/provenance.json"] == ("info", strings.OUT_STATE_OPEN_DATA)
    assert all(state[0] == "pass" for rel, state in by.items() if rel not in ("manifest.json",) and not rel.startswith(f"{OPEN_DATA_FOLDER}/"))  # fmt: skip


def test_unticking_it_leaves_an_earlier_data_folder_alone_and_the_outputs_unchanged(
    both, qtbot
) -> None:
    dlg = ExportDialog(both["ctl"], themed(), settings=both["ui"])
    qtbot.addWidget(dlg)
    again = export(dlg, data=False)
    assert again.data == ()
    assert tree(both["folder"]) == both["after"]  # (the same bytes, the data files still there)
    assert not dlg.open_data.isChecked()
    assert both["ui"].value("export/open_data") == "false"


def test_a_data_folder_that_cannot_be_written_is_a_warning_and_the_outputs_stay(
    qtbot, tmp_path
) -> None:
    ctl = flatsat_controller(tmp_path)
    dlg = ExportDialog(ctl, themed(), settings=settings(tmp_path))
    qtbot.addWidget(dlg)
    folder = outputs_of(ctl)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / OPEN_DATA_FOLDER).write_text("a file where the folder should be")
    result = export(dlg, data=True)
    assert result.data == () and (folder / "manifest.json").is_file()
    assert strings.EXP_DATA_FAILED.split("{")[0] in dlg.notice.text()
    assert not dlg.notice.isHidden()
