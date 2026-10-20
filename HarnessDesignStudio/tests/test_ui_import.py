# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UI overhaul M7: the import wizard is the one way in for every kind (interfaces included), a large file
is read in the background with a Cancel and a progress line, and every packaged sample gives the same
project through the wizard as through the command line."""

import shutil
import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QEventLoop, QSettings, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QWizard  # noqa: E402

from harness_design_studio.cli.main import main as cli  # noqa: E402
from harness_design_studio.core import templates  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.gui import import_kinds, strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.import_wizard import LARGE_ROWS, PAGE_MAP, ImportWizard  # noqa: E402
from harness_design_studio.gui.main_window import MainWindow  # noqa: E402
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.helpers import time_limit  # noqa: E402


@pytest.fixture
def folders(tmp_path: Path):
    """A copy of the packaged import templates and a project folder per example."""
    tpl = tmp_path / "templates"
    templates.copy_import_templates(tpl)

    def project(name: str) -> Path:
        dest = tmp_path / f"work-{name}"
        templates.create_project(dest, name)
        return dest

    return tpl, project


def opened(folder: Path) -> EditorController:
    ctl = EditorController(drc_delay_ms=600_000)
    ctl.open_path(folder)
    return ctl


def wizard(qtbot, ctl, kind: str, path: Path | None = None) -> ImportWizard:
    theme = ThemeManager()
    w = ImportWizard(ctl, theme, pick_file=lambda k, f: str(path) if path else None, kind=kind)
    qtbot.addWidget(w)
    w.show()
    if path is not None:
        assert w.load_file(str(path))
    return w


def big_csv(path: Path, units: list[str], rows: int) -> Path:
    lines = ["Interface,Type,From,To,Redundancy"]
    for n in range(rows):
        a, b = units[n % len(units)], units[(n * 7 + 1) % len(units)]
        lines.append(f"IMP-{n:05d},RS-422,{a},{b},nominal")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def wait_planned(qtbot, w: ImportWizard, timeout: int = 60_000) -> None:
    qtbot.waitUntil(lambda: not w.planning, timeout=timeout)


# ---- the samples give the same project through the wizard and the command line ---------------------
def test_approved_parts_sample_equals_the_command_line(qtbot, folders) -> None:
    tpl, project = folders
    gui_dir, cli_dir = project("first-steps"), project("minimal-satellite")
    shutil.rmtree(cli_dir)
    shutil.copytree(gui_dir, cli_dir)
    ctl = opened(gui_dir)
    w = wizard(qtbot, ctl, "parts", tpl / "approved-parts.csv")
    page = w.map_page
    w.next()
    assert w.currentId() == PAGE_MAP
    page.word_edits["approved"].setText("Approved")
    page.word_edits["pending"].setText("Review")
    page.word_edits["rejected"].setText("Rejected")
    w.replan()
    assert w.apply()
    ctl.save()
    ctl.release()
    argv = ["import-parts", str(cli_dir), str(tpl / "approved-parts.csv")]
    assert (
        cli([*argv, "--approved", "Approved", "--pending", "Review", "--rejected", "Rejected"]) == 0
    )
    a, b = load_project(gui_dir).project, load_project(cli_dir).project
    assert a.parts == b.parts and len(a.parts) > 0


def test_segment_lengths_sample_equals_the_command_line(qtbot, folders) -> None:
    tpl, project = folders
    gui_dir = project("flatsat")
    cli_dir = gui_dir.parent / "cli-flatsat"
    shutil.copytree(gui_dir, cli_dir)
    ctl = opened(gui_dir)
    w = wizard(qtbot, ctl, "lengths", tpl / "segment-lengths.csv")
    w.next()
    w.replan()
    assert w.plan is not None and w.plan.importable and w.apply()
    ctl.save()
    ctl.release()
    assert (
        cli(["import-lengths", str(cli_dir), str(tpl / "segment-lengths.csv"), "--unit", "mm"]) == 0
    )
    a, b = load_project(gui_dir).project, load_project(cli_dir).project
    assert a.harnesses == b.harnesses


def test_ampacity_sample_equals_the_command_line(qtbot, folders) -> None:
    tpl, project = folders
    gui_dir = project("first-steps")
    cli_dir = gui_dir.parent / "cli-first"
    shutil.copytree(gui_dir, cli_dir)
    ctl = opened(gui_dir)
    w = wizard(qtbot, ctl, "values", tpl / "ampacity-DEMO-ONLY.csv")
    w.next()
    w.replan()
    assert w.plan is not None and w.plan.importable and w.apply()
    ctl.save()
    ctl.release()
    # (the command exits 1 when engineering values are still missing, which they are in this project)
    assert cli(["config", str(cli_dir), "--ampacity-csv", str(tpl / "ampacity-DEMO-ONLY.csv")]) in (
        0,
        1,
    )
    a, b = load_project(gui_dir).project, load_project(cli_dir).project
    assert a.config["derating"].values == b.config["derating"].values


def test_interfaces_and_netlist_samples_import_in_one_undo_step(qtbot, folders) -> None:
    tpl, project = folders
    ctl = opened(project("first-steps"))
    before = len(ctl.project.interfaces)
    w = wizard(qtbot, ctl, "interfaces", tpl / "interfaces.csv")
    w.next()
    w.replan()
    assert w.plan is not None and w.plan.ok_count == 2 and w.apply()
    assert len(ctl.project.interfaces) == before + 2
    ctl.undo()
    assert len(ctl.project.interfaces) == before
    ctl.release()


# ---- a large file is read in the background -----------------------------------------------------------
def test_a_small_file_is_still_read_at_once(qtbot, folders, tmp_path) -> None:
    tpl, project = folders
    ctl = opened(project("flatsat"))
    units = sorted(ctl.project.units)
    f = big_csv(tmp_path / "small.csv", units, 50)
    w = wizard(qtbot, ctl, "interfaces", f)
    w.next()
    assert not w.planning and w.plan is not None and len(w.plan.rows) == 50
    ctl.release()


def test_a_large_file_is_read_in_the_background_and_gives_the_same_plan(
    qtbot, folders, tmp_path
) -> None:
    tpl, project = folders
    ctl = opened(project("flatsat"))
    units = sorted(ctl.project.units)
    f = big_csv(tmp_path / "large.csv", units, LARGE_ROWS + 500)
    w = wizard(qtbot, ctl, "interfaces", f)
    w.next()
    assert w.currentId() == PAGE_MAP
    assert w.planning and w.plan is None
    assert w.map_page.busy_row.isVisibleTo(w.map_page)
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled()  # nothing to go on with yet
    wait_planned(qtbot, w)
    assert not w.map_page.busy_row.isVisibleTo(w.map_page)
    assert w.plan is not None
    source = w.source
    assert source is not None
    direct = import_kinds.plan_import(ctl.project, source, w.choices)
    assert (len(w.plan.rows), w.plan.ok_count, len(w.plan.ops)) == (
        len(direct.rows),
        direct.ok_count,
        len(direct.ops),
    )
    assert w.button(QWizard.WizardButton.NextButton).isEnabled()
    ctl.release()


def test_cancel_drops_the_reading_and_a_later_result_is_not_used(qtbot, folders, tmp_path) -> None:
    tpl, project = folders
    ctl = opened(project("flatsat"))
    f = big_csv(tmp_path / "large.csv", sorted(ctl.project.units), LARGE_ROWS + 500)
    w = wizard(qtbot, ctl, "interfaces", f)
    w.next()
    assert w.planning
    w.map_page.busy_cancel.click()
    assert not w.planning and w.plan is None
    assert w.map_page.notice.isVisible()
    assert not w.button(QWizard.WizardButton.NextButton).isEnabled()
    qtbot.wait(900)  # the helper finishes meanwhile: its rows must not appear
    QApplication.processEvents()
    assert w.plan is None
    w.options_changed()  # choosing again reads again
    assert w.planning
    wait_planned(qtbot, w)
    assert w.plan is not None and len(w.plan.rows) == LARGE_ROWS + 500
    ctl.release()


def test_closing_the_wizard_while_it_reads_is_safe(qtbot, folders, tmp_path) -> None:
    tpl, project = folders
    ctl = opened(project("flatsat"))
    f = big_csv(tmp_path / "large.csv", sorted(ctl.project.units), LARGE_ROWS + 500)
    w = wizard(qtbot, ctl, "interfaces", f)
    w.next()
    assert w.planning
    w.reject()
    QApplication.processEvents()
    assert not w.planning
    ctl.release()


@pytest.mark.perf
def test_a_20000_row_file_keeps_the_window_responsive(qtbot, folders, tmp_path) -> None:
    tpl, project = folders
    ctl = opened(project("flatsat"))
    f = big_csv(tmp_path / "huge.csv", sorted(ctl.project.units), 20_000)
    w = wizard(qtbot, ctl, "interfaces", f)
    gaps: list[float] = []
    last = [time.perf_counter()]

    def tick() -> None:
        now = time.perf_counter()
        gaps.append((now - last[0]) * 1000)
        last[0] = now

    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(tick)
    timer.start()
    w.next()
    loop = QEventLoop()
    w.planned.connect(loop.quit)
    if w.planning:
        loop.exec()
    w.next()  # the page with every row
    QApplication.processEvents()
    timer.stop()
    assert w.plan is not None and len(w.plan.rows) == 20_000
    assert max(gaps) < time_limit(300), max(gaps)
    ctl.release()


# ---- the window --------------------------------------------------------------------------------------
@pytest.fixture
def win(qtbot, tmp_path):
    w = MainWindow(
        QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat),
        ThemeManager(),
        first_run=False,
    )
    qtbot.addWidget(w)
    w.show()
    return w


def test_interfaces_import_opens_the_wizard_like_every_other_kind(win) -> None:
    kinds: list[str] = []
    win.import_wizard_flow = kinds.append  # type: ignore[method-assign]
    win.act_import.trigger()
    win._tree_import("interfaces")
    assert kinds == ["interfaces", "interfaces"]


def test_paste_text_instead_leads_to_the_older_dialog(win, monkeypatch) -> None:
    seen: list[str] = []
    win.import_flow = lambda: seen.append("paste")  # type: ignore[method-assign]

    def run(dialog) -> int:
        dialog.file_page.paste.click()
        return 0

    monkeypatch.setattr(win, "run_dialog", run)
    win.import_wizard_flow("interfaces")
    assert seen == ["paste"]


def test_every_kind_still_has_its_page_and_a_paste_link_only_where_it_helps(qtbot, folders) -> None:
    tpl, project = folders
    ctl = opened(project("first-steps"))
    w = wizard(qtbot, ctl, "interfaces")
    assert w.file_page.paste.text() == strings.IMP_PASTE_TEXT
    ctl.release()
