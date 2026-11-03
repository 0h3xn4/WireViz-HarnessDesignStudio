# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""S9 (R6): the Next step page's disclosure *What this step uses and makes* (closed by default,
filled from `core/workflow.py` only while open) and the As-built page (what is missing and out of its
limit, the import and the sheet to fill in)."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core import asbuilt, templates, workflow  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.roles import AIT, SYSTEMS  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402

BENCH = """Kind,Harness,Item,Cut length (m),Result,Continuity (ohm)
wire,W001,W001-001,"3,46",,
test,W001,T001,,pass,0.4
test,W001,T002,,pass,1.4
"""


@pytest.fixture
def win(qtbot, tmp_path: Path):
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    templates.create_project(tmp_path / "p", "flatsat")
    w.open_project(tmp_path / "p")
    QApplication.processEvents()
    return w


def test_the_disclosure_is_closed_until_it_is_opened_and_then_shows_the_step(win) -> None:
    page = win.next_page
    win.set_area("next")
    assert not page.wf_toggle.isChecked() and not page.wf_body.isVisibleTo(page)
    called: list[int] = []
    inner = page._provider  # noqa: SLF001

    def counted():
        called.append(1)
        return inner()

    page.set_workflow_provider(counted)
    win._update_next(win.shell_status(compute=False))  # noqa: SLF001
    assert called == []  # nothing is worked out while it is closed
    page.wf_toggle.click()
    assert page.wf_body.isVisibleTo(page) and called == [1]
    key = page.key()
    step = workflow.step(workflow.NEXT_KEY_STEP[key])
    assert step.title in page.wf_labels["step"].text()
    assert step.consumes[0].name in page.wf_labels["uses"].text()
    assert step.produces[0].name in page.wf_labels["makes"].text()
    lines = page.wf_labels["all"].text().splitlines()
    assert lines[0] == strings.NEXT_WF_ALL and len(lines) == 1 + len(workflow.STEPS)
    assert lines[1].startswith("Define the devices: done ")
    assert "Blocked by: " in page.wf_labels["all"].text()  # what a step waits for is named
    page.wf_toggle.click()
    assert not page.wf_body.isVisibleTo(page)


def test_the_disclosure_follows_the_project(win) -> None:
    page = win.next_page
    win.set_area("next")
    page.wf_toggle.click()
    before = page.wf_labels["all"].text()
    win.ctl.new_project(win.ctl.root.parent / "other", "Blank")  # an empty project: nothing is done
    QApplication.processEvents()
    after = page.wf_labels["all"].text()
    assert before != after and "Define the devices: to do" in after


def test_the_as_built_page_lists_what_needs_attention_and_the_buttons_work(win, tmp_path: Path) -> None:  # fmt: skip
    win.set_role(AIT)
    win.set_area("asbuilt")
    page = win.asbuilt_page
    assert strings.ASB_NONE in page.summary.text() and page.rows() == []
    bench = tmp_path / "bench.csv"
    bench.write_text(BENCH, encoding="utf-8")
    win.ask_open_path = lambda title, filters: str(bench)  # type: ignore[method-assign]
    page.import_button.click()
    QApplication.processEvents()
    project = win.ctl.project
    assert len(project.asbuilt) == 3 and "asbuilt:bench.csv" in project.import_records
    rows = page.rows()
    assert rows[0]["status"] == asbuilt.OUT and rows[0]["item"] == "test T002"  # out of limit first
    assert rows[0]["actual"] == "1.4" and rows[0]["designed"] == "1"
    statuses = {r["status"] for r in rows}
    assert statuses == {
        asbuilt.OUT,
        asbuilt.DIFFERS,
        asbuilt.MISSING,
    }  # nothing as designed or within
    assert "1 out of limit" in page.summary.text() and "1 different from the design" in page.summary.text()  # fmt: skip
    page.show_all.setChecked(True)
    assert {r["status"] for r in page.rows()} - statuses == {"within limit"}
    assert not any(
        "pass" in r["status"] for r in page.rows()
    )  # the page never says that anything passed
    win.ctl.undo()  # one undo step
    win.set_area("asbuilt")
    assert win.ctl.project.asbuilt == {}


def test_a_row_the_design_cannot_take_changes_nothing_and_says_which(win, tmp_path: Path) -> None:
    bad = tmp_path / "bad.csv"
    bad.write_text("Kind,Harness,Item,Cut length (m)\nwire,W001,NOPE,3\n")
    win.ask_open_path = lambda title, filters: str(bad)  # type: ignore[method-assign]
    win.asbuilt_import_flow()
    assert win.ctl.project.asbuilt == {}
    shown = [
        str(w.text()) for w in win.toasts.findChildren(type(win.asbuilt_page.summary)) if w.text()
    ]
    assert any("Nothing was changed" in t and "NOPE" in t for t in shown)


def test_the_sheet_to_fill_in_is_saved_by_the_page(win, tmp_path: Path) -> None:
    target = tmp_path / "sheet.csv"
    win.ask_save_path = lambda title, suggested, filters: str(target)  # type: ignore[method-assign]
    win.asbuilt_page.export_button.click()
    assert target.read_bytes().startswith(b"# harness-design-studio")
    other = tmp_path / "sheet.xlsx"
    win.ask_save_path = lambda title, suggested, filters: str(other)  # type: ignore[method-assign]
    win.asbuilt_export_flow()
    assert other.read_bytes()[:2] == b"PK"
    noext = tmp_path / "plain"
    win.ask_save_path = lambda title, suggested, filters: str(noext)  # type: ignore[method-assign]
    win.asbuilt_export_flow()
    assert (tmp_path / "plain.csv").is_file()
    assert (
        load_project(tmp_path / "p").project.asbuilt == {}
    )  # a sheet changes nothing in the project


def test_the_menu_entries_run_the_same_flows(win, tmp_path: Path) -> None:
    bench = tmp_path / "bench.csv"
    bench.write_text(BENCH, encoding="utf-8")
    win.ask_open_path = lambda title, filters: str(bench)  # type: ignore[method-assign]
    win.set_role(SYSTEMS)  # (left out of this role's menus, run by the palette)
    entries = {e.label: e for e in win.palette_entries()}
    entries[strings.A_IMPORT_ASBUILT].run()
    assert len(win.ctl.project.asbuilt) == 3
    entries[strings.GO_ASBUILT].run()
    assert win.area() == "asbuilt" and win.rail.buttons["asbuilt"].isVisibleTo(win.rail)
