"""J5/J6 (M3): generate harnesses from the editor: preview, one undo step, status, Explain."""

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QPushButton  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core.commands import Put  # noqa: E402
from harness_design_studio.core.io.layout import model_hash  # noqa: E402
from harness_design_studio.core.model import evolve  # noqa: E402
from harness_design_studio.core.samples import sat15  # noqa: E402
from harness_design_studio.gui.dialogs import GeneratePreviewDialog  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w.ctl._install(sat15(), None, None)
    return w


def test_generate_button_is_enabled_and_shows_a_preview(win) -> None:  # type: ignore[no-untyped-def]
    btn = win.findChild(QPushButton, "generate")
    assert btn.isEnabled()
    script = DialogScript(win, accept=False)
    before = model_hash(win.ctl.project)
    btn.click()
    assert script.seen, "a preview must be shown before anything changes"
    dlg = script.seen[0]
    assert isinstance(dlg, GeneratePreviewDialog)
    assert "create" in dlg.summary.text() and "Undo" in dlg.summary.text()
    assert not dlg.placeholders.isHidden()  # placeholders in use are always disclosed
    assert model_hash(win.ctl.project) == before  # cancelled: nothing changed
    assert win.ctl.generation_status() == "none"


def test_apply_is_one_undo_step_and_fills_the_plans_tab(win) -> None:  # type: ignore[no-untyped-def]
    before = model_hash(win.ctl.project)
    DialogScript(win, accept=True)
    win.findChild(QPushButton, "generate").click()
    p = win.ctl.project
    assert p.harnesses and win.ctl.generation_status() == "current"
    panel = win.harness_panel
    assert win.tabs.currentWidget() is panel
    assert panel.harnesses.rowCount() == len(p.harnesses)
    assert "Up to date" in panel.status.text()
    assert "0 error(s)" in panel.verify.text()
    win.ctl.undo()
    assert model_hash(win.ctl.project) == before
    assert not win.ctl.project.harnesses


def test_second_generate_reports_nothing_to_do(win) -> None:  # type: ignore[no-untyped-def]
    script = DialogScript(win, accept=True)
    btn = win.findChild(QPushButton, "generate")
    btn.click()
    shown = len(script.seen)
    btn.click()
    assert len(script.seen) == shown  # no preview: nothing would change
    assert "up to date" in win.toasts.messages[-1].lower()


def test_status_goes_out_of_date_after_an_edit(win) -> None:  # type: ignore[no-untyped-def]
    DialogScript(win, accept=True)
    win.findChild(QPushButton, "generate").click()
    unit = next(iter(win.ctl.project.units.values()))
    win.ctl.run("rename", [Put("units", evolve(unit, name="Renamed unit"))])
    win.harness_panel.refresh()
    assert "Out of date" in win.harness_panel.status.text()


def test_explain_shows_recorded_reasons(win, qtbot) -> None:  # type: ignore[no-untyped-def]
    DialogScript(win, accept=True)
    win.findChild(QPushButton, "generate").click()
    panel = win.harness_panel
    panel.harnesses.selectRow(0)
    assert panel.wires.rowCount() > 0
    panel.wires.selectRow(0)
    text = panel.explain.text()
    assert "wiring:" in text or "segmentation:" in text


def test_cancelled_worker_changes_nothing(win) -> None:  # type: ignore[no-untyped-def]
    win.compute_plan = lambda: None
    before = model_hash(win.ctl.project)
    DialogScript(win, accept=True)
    win.findChild(QPushButton, "generate").click()
    assert model_hash(win.ctl.project) == before
    assert "cancelled" in win.toasts.messages[-1].lower()


def test_default_worker_computes_a_plan(win) -> None:  # type: ignore[no-untyped-def]
    plan = win._compute_plan()
    assert plan is not None and plan.report.added


def test_read_only_project_cannot_generate(win) -> None:  # type: ignore[no-untyped-def]
    win.ctl.project.read_only = True
    before = model_hash(win.ctl.project)
    script = DialogScript(win, accept=True)
    win.generate_flow()
    assert not script.seen
    assert model_hash(win.ctl.project) == before  # nothing generated, nothing changed
