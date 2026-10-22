"""M5 (GUI): export outputs (status in the Harness tab), with progress, independent check and
a stale indicator."""

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QPushButton  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core.commands import Put  # noqa: E402
from harness_design_studio.core.generate.engine import generate_project  # noqa: E402
from harness_design_studio.core.io.saver import save_project  # noqa: E402
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.outputs.build import write_outputs  # noqa: E402
from harness_design_studio.core.samples import new_project, sat15  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = sat15()
    generate_project(p)
    save_project(p, tmp_path / "proj")
    assert w.open_project(tmp_path / "proj")
    return w


def test_export_writes_outputs_and_the_harness_tab_status_turns_current(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    view = win.harness_view
    win.go_to("harness")
    view.refresh()
    assert view.wait_idle()
    assert view.outputs_chip.state() == "not-checked"  # nothing exported yet
    assert "not exported" in view.outputs_chip.toolTip()
    win.export_flow()
    folder = tmp_path / "proj" / "outputs"
    assert (folder / "manifest.json").is_file()
    assert view.wait_idle()
    assert view.outputs_chip.state() == "pass" and "up to date" in view.outputs_chip.toolTip()
    assert "files written" in win.toasts.messages[-1]


def test_the_quick_export_follows_the_last_export_in_the_folder(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """D-169: no drawings unless the folder's last export had them; then they are kept."""
    folder = tmp_path / "proj" / "outputs"

    def has_drawings() -> bool:
        return any(p.name.startswith("drawing_") for p in folder.rglob("*"))

    win.export_flow()
    assert not has_drawings() and (folder / "harnesses" / "W001" / "W001_build.xlsx").is_file()
    win.export_flow()
    assert not has_drawings()
    write_outputs(win.ctl.project, folder)  # an export with the drawings (the library default)
    assert has_drawings()
    win.export_flow()
    assert has_drawings()
    assert "files written" in win.toasts.messages[-1]


def test_the_export_button_of_the_harness_tab_opens_the_export_window(win) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.gui.export_dialog import ExportDialog

    win.go_to("harness")
    script = DialogScript(win, accept=False)
    win.harness_view.action_buttons["export"].click()
    assert script.seen and isinstance(script.seen[0], ExportDialog)


def test_status_goes_stale_after_an_edit(win) -> None:  # type: ignore[no-untyped-def]
    win.go_to("harness")  # hidden views refresh lazily
    win.export_flow()
    unit = next(iter(win.ctl.project.units.values()))
    win.ctl.run("rename", [Put("units", evolve(unit, name="Renamed"))])
    view = win.harness_view
    view.refresh()
    assert view.wait_idle()
    assert view.outputs_chip.state() == "stale" and "out of date" in view.outputs_chip.toolTip()


def test_export_needs_a_saved_project_and_harnesses(win, qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    win.ctl._install(new_project("x"), None, None)
    win.export_flow()
    assert "Save the project" in win.toasts.messages[-1]
    win.ctl._install(sat15(), None, None)
    win.ctl.root = tmp_path / "somewhere"
    win.export_flow()
    assert "no harnesses" in win.toasts.messages[-1].lower()


def test_cancelled_export_writes_nothing(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    win.compute_outputs = lambda: None
    win.export_flow()
    assert not (tmp_path / "proj" / "outputs").exists()
    assert "cancelled" in win.toasts.messages[-1].lower()


def test_failed_independent_check_blocks_the_write(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    from harness_design_studio.core.outputs.build import build_outputs
    from harness_design_studio.core.outputs.verify import verify_outputs

    built = build_outputs(win.ctl.project)
    from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv

    table = parse_csv(built.files["harnesses/W001/wirelist.csv"])
    del table[1]
    built.files["harnesses/W001/wirelist.csv"] = csv_bytes(table, built.stamp)
    report = verify_outputs(win.ctl.project, built.files)
    assert not report.ok
    win.compute_outputs = lambda: (built, report)
    DialogScript(win, accept=True)
    win.export_flow()
    assert not (tmp_path / "proj" / "outputs").exists()
    assert "failed" in win.toasts.messages[-1]


def test_real_worker_exports(win, tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = win._compute_outputs()
    assert result is not None and result[1].ok


def test_nothing_to_export_until_there_are_harnesses(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(new_project("x"), None, None)
    w.harness_view.refresh()
    assert w.harness_view.stack.currentWidget() is w.harness_view.empty  # no Export button shown
    assert not w.harness_view.action_buttons["export"].isVisible()
    assert w.findChild(QPushButton, "topbar-export") is not None  # the top bar's Export stays


def test_a_toast_that_expires_after_the_window_is_gone_does_not_raise(qtbot, tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Regression: a late timer on a closed window raised in the Qt event loop and failed an
    unrelated test that ran later (flaky full-suite failure)."""
    from PySide6.QtWidgets import QApplication

    w = make_window(tmp_path)
    host = w.toasts
    host.show_message("hello", None, ms=10)
    w.close()
    w.deleteLater()
    QApplication.processEvents()
    # the expiry timer fires after the window was deleted; pytest-qt fails the test if the event
    # loop raised, so reaching the next line is the check
    qtbot.wait(60)
