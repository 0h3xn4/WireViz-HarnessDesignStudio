# mypy: allow-untyped-calls, no-warn-unused-ignores
"""Render screenshots of the real Qt editor (offscreen) into docs/ux/qt for the docs and the UX review.
Files 01 to 13 show the built-in sample; 14 and up show the views and dialogs of the editor on the
flatsat example (project tree, Harness, Lists, Checks, Releases, engineering values, export, import
wizard, release dialog, new project, stale banner). Usage: python -m tools.gui_screenshots"""

import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog, QPushButton

from harness_design_studio.gui.main_window import MainWindow
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.resources import examples_path

OUT = Path(__file__).resolve().parents[1] / "docs" / "ux" / "qt"
CSV = (
    "Interface,Type,From unit,To unit,Redundancy\nIF-010,Primary power,PCDU,OBC,nominal\n"
    "IF-011,CAN,OBC,RW1,nominal\nIF-012,RS-422,OBC,PCDU,nominal\nIF-013,RS-423,OBC,RW1,nominal\n"
    "IF-TM-RW1,Discrete / bilevel,OBC,PCDU,nominal\nIF-014,Primary power,PCDU,GHOST,nominal\n"
)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    settings = QSettings(str(Path(tempfile.mkdtemp()) / "ui.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings, ThemeManager(), first_run=False)
    win.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    win.resize(1440, 900)
    win.show()

    def shot(name: str, widget: object = None) -> None:
        if widget is None:
            _settle(win)  # the check has finished, so the pictures do not depend on timing
        app.processEvents()
        (widget or win).grab().save(str(OUT / f"{name}.png"))  # type: ignore[attr-defined]
        print(name)

    def btn(name: str) -> QPushButton:
        b = win.findChild(QPushButton, name)
        assert b is not None
        return b

    app.processEvents()
    win.view.fit()
    win.tour.start()
    shot("01-first-run-tour")
    win.tour.stop()
    shot("02-guided-main")
    btn("add-sensor").click()
    btn("type-can").click()
    win.ctl.pick("OBC")
    shot("03-connect-compatible-highlight")
    win.ctl.end_connect()
    win.ctl.set_mode("expert")
    btn("type-power_primary").click()
    shot("04-expert-connectors")
    win.ctl.end_connect()
    win.ctl.select("unit", "RW1")
    shot("05-expert-properties")
    win.ctl.set_mode("guided")
    win.ctl.redundant_copy("RW1")
    win.tabs.setCurrentIndex(0)
    shot("06-redundant-copy-and-problems")
    win.ctl.select("interface", "IF-TM-RW1")
    win.tabs.setCurrentIndex(2)
    shot("07-interface-table")

    def import_dialog(d):  # type: ignore[no-untyped-def]
        d.resize(900, 640)
        d.text.setPlainText(CSV)
        d.show()
        shot("08-import-preview", d)

    win.run_dialog = lambda d: (import_dialog(d), 0)[1]  # type: ignore[assignment,no-untyped-call]
    win.import_flow()
    win.ctl.select("unit", "OBC")

    def delete_dialog(d):  # type: ignore[no-untyped-def]
        d.show()
        shot("09-delete-impact", d)

    win.run_dialog = lambda d: (delete_dialog(d), 0)[1]  # type: ignore[assignment,misc]
    win.delete_btn.click()
    from harness_design_studio.core import checks

    f = checks.open_findings(win.ctl.project)
    cross = next(x for x in f if x.can_waive)

    def waive_dialog(d):  # type: ignore[no-untyped-def]
        d.show()
        d.text.setPlainText("short")
        d.ok.click()
        shot("10-waiver-requires-justification", d)

    win.run_dialog = lambda d: (waive_dialog(d), 0)[1]  # type: ignore[assignment,misc]
    win.waive_flow(cross)

    def palette(d):  # type: ignore[no-untyped-def]
        d.show()
        d.input.setText("conn")
        shot("11-command-palette", d)

    win.run_dialog = lambda d: (palette(d), 0)[1]  # type: ignore[assignment,misc]
    win.open_commands()
    win.act_dark.trigger()
    shot("12-dark-theme")
    win.act_dark.trigger()
    win.scale_actions[150].trigger()
    shot("13-scale-150")
    win.scale_actions[100].trigger()
    win.ctl.release()
    views()
    wizard_and_release()
    return 0


def _work_folder(name: str) -> Path:
    """A folder with a fixed name (the status bar shows the project path, so a random one would
    make the pictures differ from run to run)."""
    folder = Path(tempfile.gettempdir()) / "harness-screenshots" / name
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    return folder


def _wait(ms: int) -> None:
    """Wait while the event loop runs. A sleep (not QTest.qWait) lets the background threads have
    the interpreter lock: with qWait an export worker made hardly any progress."""
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        QApplication.processEvents()
        time.sleep(0.02)


def _settle(win: MainWindow, ms: int = 400, timeout: int = 30000) -> None:
    """Let timers and background jobs finish: wait until the design rule check has a current result."""
    _wait(ms)
    waited = 0
    while (win.ctl.drc_busy() or not win.ctl.drc_current) and waited < timeout:
        _wait(200)
        waited += 200
    waited = 0
    while win.toasts.isVisible() and waited < 8000:  # a message goes away after 5 s
        _wait(200)
        waited += 200
    _wait(ms)


def _grab(win: MainWindow, name: str, widget: Any = None) -> None:
    QApplication.processEvents()
    (widget or win).grab().save(str(OUT / f"{name}.png"))
    print(name)


def views() -> None:
    """Pictures 14 and up: the views and dialogs on the flatsat example."""
    from harness_design_studio.core.outputs.build import write_outputs
    from harness_design_studio.core.vcs.release import plan_release

    tmp = _work_folder("flatsat-views")
    root = examples_path()
    assert root is not None
    shutil.copytree(root / "projects" / "flatsat", tmp / "flatsat")
    settings = QSettings(str(tmp / "ui.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings, ThemeManager(), first_run=False)
    win.ask_choice = lambda t, x, b: 1  # type: ignore[assignment]
    win.resize(1440, 900)
    win.show()
    assert win.open_project(tmp / "flatsat")
    win.view.fit()
    _settle(win)

    win.ctl.select("unit", "PDU2")
    _settle(win)
    _grab(win, "14-flatsat-tree-and-inspector")
    win.go_to("harness")
    win.harness_view.select_harness("W001")
    _settle(win)
    _grab(win, "15-harness-tab")
    win.go_to("lists")
    _settle(win)
    _grab(win, "16-lists-tab")
    win.go_to("checks")
    _settle(win)
    _grab(win, "17-checks-tab")
    dialog = win.checks_panel.open_config()
    _wait(300)
    _grab(win, "18-engineering-values", dialog)
    dialog.close()

    # a design change after Generate: the chip and the banner say the plans are out of date
    win.go_to("diagram")
    win.ctl.update_unit("RW1", name="Reaction wheel 1 (renamed)")
    _settle(win, 700)
    win.view.fit()
    _grab(win, "19-plans-out-of-date")
    win.ctl.undo()
    _settle(win, 700)

    # export, then release W001: the lock and the revision show on the objects
    def export_dialog(d: QDialog) -> int:
        d.show()
        d.export_btn.click()  # type: ignore[attr-defined]
        waited = 0
        while d.export_result is None and waited < 30000:  # type: ignore[attr-defined]
            _wait(200)
            waited += 200
        _wait(500)
        _grab(win, "20-export-window", d)
        return 0

    win.run_dialog = export_dialog  # type: ignore[assignment]
    win.export_dialog_flow()
    folder = win.ctl.outputs_folder()
    assert folder is not None
    write_outputs(win.ctl.project, folder)
    plan = plan_release(
        win.ctl.project,
        "W001",
        by="A. Engineer",
        checker="B. Reviewer",
        comment="First release for the review",
        when="2026-03-01",
        outputs_folder=folder,
        accept_placeholders="Example values for the documentation",
        accept_unapproved_parts="Example parts for the documentation",
    )
    assert plan.ok and win.ctl.apply_change(plan, "W001 released")
    write_outputs(win.ctl.project, folder)  # export again so the drawings say released
    win._outputs_epoch += 1  # (the window reads the state of the outputs again)
    _settle(win)
    win.ctl.select("unit", "PDU2")
    win.view.fit()
    _grab(win, "21-released-locks")
    win.go_to("releases")
    win.releases_panel.select_harness("W001")
    win.releases_panel.compare("W001", "A")
    _settle(win)
    _grab(win, "22-releases-tab")

    def revise_dialog(d: QDialog) -> int:
        d.show()
        d.adjustSize()
        _grab(win, "23-new-revision-dialog", d)
        return 0

    win.run_dialog = revise_dialog  # type: ignore[assignment]
    win.change_flow("revise", "W001")

    def new_project(d: QDialog) -> int:
        d.show()
        _grab(win, "24-new-project-window", d)
        return 0

    win.run_dialog = new_project  # type: ignore[assignment]
    win.new_from_example_flow()
    _settle(win)
    win.close()


def wizard_and_release() -> None:
    """The import wizard on a parts list and the release dialog with what it locks."""
    from harness_design_studio.core import templates

    tmp = _work_folder("flatsat-import")
    templates.create_project(tmp / "flatsat", "flatsat")
    templates.copy_import_templates(tmp / "my-templates")
    parts = tmp / "my-templates" / "approved-parts.csv"
    settings = QSettings(str(tmp / "ui.ini"), QSettings.Format.IniFormat)
    win = MainWindow(settings, ThemeManager(), first_run=False)
    win.resize(1440, 900)
    win.show()
    assert win.open_project(tmp / "flatsat")
    win.ask_import_file = lambda kind, filters: str(parts)
    _settle(win)

    def wizard(d: QDialog) -> int:
        d.show()
        d.resize(900, 640)
        d.load_file(str(parts))  # type: ignore[attr-defined]
        d.next()  # type: ignore[attr-defined]
        d.map_page.word_edits["approved"].setText("Approved")  # type: ignore[attr-defined]
        d.map_page.word_edits["pending"].setText("Review")  # type: ignore[attr-defined]
        d.map_page.word_edits["rejected"].setText("Rejected")  # type: ignore[attr-defined]
        d.replan()  # type: ignore[attr-defined]
        _grab(win, "25-import-wizard-columns", d)
        return 0

    win.run_dialog = wizard  # type: ignore[assignment]
    win.import_wizard_flow("parts")

    def release(d: QDialog) -> int:
        d.show()
        d.resize(560, 900)  # the offscreen screen is small; a real one gives the dialog this room
        _grab(win, "26-release-dialog", d)
        return 0

    win.run_dialog = release  # type: ignore[assignment]
    win.change_flow("release", "W001")
    _settle(win)
    win.close()


if __name__ == "__main__":
    raise SystemExit(main())
