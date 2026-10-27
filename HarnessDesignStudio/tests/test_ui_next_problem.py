# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-17. Release 1.9 W1: the Next step page after the first harness. It shows the first
problem and what to do, offers Waive and Approve where they apply, and a warning never holds it."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import links  # noqa: E402
from harness_design_studio.core.commands import History  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from tests.gui_helpers import DialogScript, make_window  # noqa: E402
from tests.helpers import pinout_project  # noqa: E402


def with_harness():
    """Two linked devices and the harness made from the link: only warnings fail."""
    p = pinout_project()
    p.harnesses, p.interfaces, p.baselines = {}, {}, {}
    h = History(p)
    ops, lid = links.plan_add_link(p, "OBC-J01", "RW1-J02", [("1", "3"), ("2", "4")])
    h.execute("link", ops)
    ops, _hid = links.plan_create_harness(p, lid)
    h.execute("harness", ops)
    return p


def settle(win) -> None:
    win.ctl.run_drc_now()
    win._show_status(path=False)
    QApplication.processEvents()


def window(qtbot, tmp_path: Path, project=None, role: str = "systems"):
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(project or with_harness(), None, None)
    win.set_role(role)
    win.set_area("next")
    settle(win)
    return win


def waive_all_but(win, rule: str) -> None:
    for f in list(win.ctl.open_findings()):
        if f.rule != rule and f.can_waive:
            assert win.ctl.waive(f, "waived in the test for the first problem")
    settle(win)


def test_warnings_do_not_hold_the_page_and_the_first_one_is_on_a_card(qtbot, tmp_path) -> None:
    win = window(qtbot, tmp_path)
    page = win.next_page
    assert page.key() not in ("fix", "check"), page.key()
    assert page.problem_card.isVisibleTo(page)
    n = page.shown()
    assert n.problem.severity == "warning" and n.problem.title
    assert page.problem_head.text() == strings.NEXT_PROBLEM_HEAD["warning"]
    assert page.problem_todo.text().startswith("What to do: ")
    assert "warnings are left" in page.note.text() or "warning is left" in page.note.text()
    assert page.problem_waive.isVisibleTo(page)


def test_the_first_problem_is_the_first_failed_rule_and_names_what_to_do(qtbot, tmp_path) -> None:
    win = window(qtbot, tmp_path)
    waive_all_but(win, "part-unapproved")
    page = win.next_page
    p = page.shown().problem
    assert p.rule == "part-unapproved" and "not approved" in p.title
    assert p.approve.startswith("EX-") and p.can_waive
    assert page.problem_todo.text() == "What to do: " + p.todo
    assert "approve" in p.todo.lower()
    assert page.problem_approve.isVisibleTo(page) and p.approve in page.problem_approve.text()
    assert p.more >= 0


def test_waive_asks_for_a_reason_and_the_next_problem_comes(qtbot, tmp_path) -> None:
    win = window(qtbot, tmp_path)
    waive_all_but(win, "part-unapproved")
    page = win.next_page
    first = page.shown().problem.finding_id

    def reason(dlg):
        dlg.text.setPlainText("The supplier owns the parts list; checked on the datasheet.")

    script = DialogScript(win, reason)
    page.problem_waive.click()
    assert script.seen and script.seen[0].objectName() == "waiver-dialog"
    assert first in win.ctl.project.waivers
    assert win.ctl.history.next_undo_label == f"Waive {first}"
    settle(win)
    nxt = page.shown().problem
    assert nxt is None or nxt.finding_id != first


def test_cancelling_the_waiver_window_waives_nothing(qtbot, tmp_path) -> None:
    win = window(qtbot, tmp_path)
    waive_all_but(win, "part-unapproved")
    before = dict(win.ctl.project.waivers)
    DialogScript(win, accept=False)
    win.next_page.problem_waive.click()
    assert win.ctl.project.waivers == before


def test_approve_asks_first_then_changes_only_that_part_in_one_undo_step(qtbot, tmp_path) -> None:
    win = window(qtbot, tmp_path)
    waive_all_but(win, "part-unapproved")
    page = win.next_page
    pid = page.shown().problem.approve
    others = {k: v for k, v in win.ctl.project.parts.items() if k != pid}
    asked: list[tuple[str, str, list[str]]] = []

    def say_no(title, text, buttons):
        asked.append((title, text, buttons))
        return 1  # Cancel (also the answer to the question on closing: discard)

    win.ask_choice = say_no
    page.problem_approve.click()
    assert asked and pid in asked[0][1] and asked[0][2][0] == "Approve"
    assert win.ctl.project.parts[pid].approval == "pending"  # (a no changes nothing)
    win.ask_choice = lambda t, x, b: 0 if t == strings.NEXT_PROBLEM_APPROVE_TITLE else 1
    page.problem_approve.click()
    p = win.ctl.project
    assert p.parts[pid].approval == "approved" and not p.parts[pid].unverified
    assert {k: v for k, v in p.parts.items() if k != pid} == others
    assert win.ctl.history.next_undo_label == f"Approve part {pid}"
    win.ctl.undo()
    assert win.ctl.project.parts[pid].approval == "pending"


def test_show_it_goes_to_the_part(qtbot, tmp_path) -> None:
    win = window(qtbot, tmp_path)
    waive_all_but(win, "part-unapproved")
    win.next_page.problem_show.click()
    QApplication.processEvents()
    assert win.area() == "model" and win.main_tabs.currentWidget() is win.devices_view


def test_an_error_holds_the_page_on_fix_with_the_card_and_no_waive(qtbot, tmp_path) -> None:
    from harness_design_studio.core.samples import mini3

    win = window(qtbot, tmp_path, mini3())
    page = win.next_page
    assert page.key() == "fix"
    p = page.shown().problem
    assert p.severity == "error" and not p.can_waive
    assert page.problem_head.text() == strings.NEXT_PROBLEM_HEAD["error"]
    assert not page.problem_waive.isVisibleTo(page)
    assert page.button.text() == "Show the problems"


def test_no_card_while_nothing_failed_or_before_the_check(qtbot, tmp_path) -> None:
    from harness_design_studio.core.samples import new_project

    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(new_project(), None, None)
    win.set_role("systems")
    win.set_area("next")
    QApplication.processEvents()
    assert win.next_page.key() == "add_device" and not win.next_page.problem_card.isVisibleTo(win.next_page)  # fmt: skip


# ---- the Systems engineer stays on the Next step page after each step ------------------------------


def bare_links_project():
    """Two linked devices and no harness yet."""
    p = pinout_project()
    p.harnesses, p.interfaces, p.baselines = {}, {}, {}
    ops, _lid = links.plan_add_link(p, "OBC-J01", "RW1-J02", [("1", "3"), ("2", "4")])
    History(p).execute("link", ops)
    return p


def test_create_harness_keeps_the_systems_engineer_on_the_next_step_page(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(bare_links_project(), None, None)
    win.set_role("systems")
    win.set_area("next")
    QApplication.processEvents()
    assert win.next_page.key() == "make_harness"
    DialogScript(win)
    win.next_page.button.click()
    QApplication.processEvents()
    assert win.ctl.project.harnesses and win.area() == "next"
    win.set_role("electrical")
    win.ctl.undo()
    win.set_area("model")
    DialogScript(win)
    win.create_harness_flow("L1")
    assert win.area() == "drawings"  # (the other role goes to the harness, as before)


def test_generate_keeps_the_systems_engineer_where_they_are(qtbot, tmp_path) -> None:
    from harness_design_studio.core.samples import mini3

    p = mini3()
    p.harnesses, p.generation = {}, None
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(p, None, None)
    win.set_role("systems")
    win.set_area("next")
    DialogScript(win)
    win.generate_flow()
    QApplication.processEvents()
    assert win.ctl.project.harnesses and win.area() == "next"


def test_from_another_area_the_next_step_page_opens(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(bare_links_project(), None, None)
    win.set_role("systems")
    win.set_area("checks")
    DialogScript(win)
    win.create_harness_flow("L1")
    assert win.area() == "next"
