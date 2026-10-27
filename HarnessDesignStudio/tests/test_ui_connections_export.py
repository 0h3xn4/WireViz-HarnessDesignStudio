# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-OUT-09, release 1.9 W2. A project with connections and no harness exports: the export window
opens, plans the connection list in its tree, writes it, and nothing says "generate first". The
Outputs area offers Export in its empty state, and a stale export is announced."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core.outputs.build import write_outputs  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui import export_docs, strings  # noqa: E402
from harness_design_studio.gui.export_dialog import ExportDialog  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.test_ui_export_flow import chooser, opens_dialog  # noqa: E402
from tests.test_ui_links import PWR, RS, bare_project, link_up  # noqa: E402

CSV, XLSX = "system/connections.csv", "system/connections.xlsx"


def linked_window(qtbot, tmp_path: Path, *, saved: bool = True):
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(bare_project(), None, None)
    assert link_up(win, *RS)
    assert not win.ctl.project.harnesses and win.ctl.project.links
    if saved:
        win.ctl.save_as(tmp_path / "proj")
    QApplication.processEvents()
    return win


def test_the_window_has_no_dead_end_and_plans_the_connection_list(qtbot, tmp_path) -> None:
    win = linked_window(qtbot, tmp_path)
    seen = opens_dialog(win)
    win.act_export.trigger()
    dlg = seen[0]
    assert dlg.blocker() is None and dlg.export_btn.isEnabled()
    assert not dlg.notice.isVisible() or dlg.notice.text() != strings.EXPORT_NO_HARNESSES
    top = [dlg.model.item(r) for r in range(dlg.model.rowCount())]
    assert [t.data(0x0100) for t in top] == ["system"]  # no harness, only the system documents
    keys = [top[0].child(r).data(0x0100) for r in range(top[0].rowCount())]
    assert "sys_connections" in keys and "sys_connections_xlsx" in keys
    assert dlg.checked_documents() >= {("system", "sys_connections"), ("system", "sys_connections_xlsx")}  # fmt: skip


def test_the_export_writes_the_files_and_names_them(qtbot, tmp_path) -> None:
    win = linked_window(qtbot, tmp_path)
    dlg = ExportDialog(win.ctl, win.theme, worker_factory=win.export_worker_factory)
    qtbot.addWidget(dlg)
    dlg.show()
    result = dlg.run()
    assert result is not None and result.count > 0
    names = {f.rel: f.doc for f in result.files}
    assert names[CSV].key == "sys_connections" and names[CSV].label == "Connection list"
    assert names[XLSX].key == "sys_connections_xlsx" and names[XLSX].kind == "XLSX"
    assert all(f.doc.key in export_docs.DOCS for f in result.files)  # no file is unknown
    out = tmp_path / "proj" / "outputs"
    assert (out / CSV).is_file() and (out / XLSX).is_file()


def test_a_project_without_a_folder_asks_where_to_save_before_the_window(qtbot, tmp_path) -> None:
    win = linked_window(qtbot, tmp_path, saved=False)
    assert win.ctl.outputs_folder() is None
    asked: list[str] = []
    chooser(win, tmp_path / "chosen", asked)
    seen = opens_dialog(win)
    win.act_export.trigger()
    assert asked and len(seen) == 1  # asked first, then the window
    assert win.ctl.outputs_folder() == tmp_path / "chosen" / "outputs"
    assert seen[0].blocker() is None


def test_a_project_with_nothing_still_says_there_is_nothing(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl.new_project(tmp_path / "blank", "Blank")
    assert not win.ctl.project.links and not win.ctl.project.harnesses
    seen = opens_dialog(win)
    win.act_export.trigger()
    assert seen[0].blocker() == strings.EXPORT_NO_HARNESSES and not seen[0].export_btn.isEnabled()
    win.export_flow()  # the older path says it as a message, not a window
    assert not (tmp_path / "blank" / "outputs").exists()


def test_the_older_export_flow_also_exports_connections_alone(qtbot, tmp_path) -> None:
    win = linked_window(qtbot, tmp_path)
    win.export_flow()
    assert (tmp_path / "proj" / "outputs" / CSV).is_file()


def test_the_outputs_area_offers_export_when_there_are_connections_and_no_harness(
    qtbot, tmp_path
) -> None:
    win = linked_window(qtbot, tmp_path)
    win.go_to("lists")
    win.lists_panel.refresh()
    panel = win.lists_panel
    assert panel.stack.currentWidget() is panel.empty
    assert panel.empty_export.isVisible() and not panel.empty_generate.isVisible()
    assert panel.empty_export.text() == strings.LP_EMPTY_EXPORT
    assert panel.empty_export.accessibleName() and panel.empty_export.toolTip()
    assert "connection list" in panel.empty_body.text()
    seen = opens_dialog(win)
    panel.empty_export.click()
    assert len(seen) == 1 and seen[0].blocker() in (None, "unsaved")
    # no connection, no button
    win.ctl._install(new_project(), None, None)
    panel.refresh()
    assert not panel.empty_export.isVisible()


def test_a_stale_export_of_connections_is_announced(qtbot, tmp_path) -> None:
    win = linked_window(qtbot, tmp_path)
    write_outputs(win.ctl.project, win.ctl.outputs_folder())
    win._outputs_epoch += 1  # (the window learns of files written elsewhere this way)
    status = win.shell_status()
    assert status.outputs == "current" and status.links == 1
    assert win.ctl.add_link(*PWR, [("1", "1"), ("2", "2")])
    QApplication.processEvents()
    status = win.shell_status()
    assert status.outputs == "stale" and not status.has_harnesses and status.links == 2
    win._update_alerts(status)
    assert win.alerts.is_showing("stale")


def test_generate_on_connections_only_is_not_a_dead_end(qtbot, tmp_path) -> None:
    from tests.gui_helpers import DialogScript

    win = linked_window(qtbot, tmp_path)
    script = DialogScript(win, accept=True)
    win.generate_flow()  # nothing to wire: the preview opens, is accepted, nothing is invented
    assert len(script.seen) <= 1
    assert not win.ctl.project.harnesses and win.ctl.project.links
    assert win.ctl.project.links["L1"].harness_id == ""
    assert "failed" not in " ".join(win.toasts.messages).lower()
