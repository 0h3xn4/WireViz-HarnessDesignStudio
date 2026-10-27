# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-18, REQ-GUI-19. Release 1.9 W1, the smaller items: the tour of the Systems engineer role, release
blockers without command-line words, Generate as the primary button only when there is something
to generate, "Made by hand" in the status bar, the problem counts that agree, the chip of the
independent check that never says "passed" next to a failed rule, and the pin role column."""

import time
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication, QComboBox  # noqa: E402

pytestmark = pytest.mark.gui

from harness_design_studio.core import devices  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.core.vcs.release import release_blockers  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.devices_view import role_cell  # noqa: E402
from harness_design_studio.gui.release_text import plain_blocker  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.test_ui_next_problem import settle, with_harness  # noqa: E402


def window(qtbot, tmp_path: Path, project=None, role: str | None = None):
    win = make_window(tmp_path)
    qtbot.addWidget(win)
    win.ctl._install(project or new_project(), None, None)
    if role:
        win.set_role(role)
    QApplication.processEvents()
    return win


# ---- the tour of the Systems engineer role -----------------------------------------------------


def test_the_systems_tour_walks_the_next_step_page_and_connect(qtbot, tmp_path: Path) -> None:
    win = window(qtbot, tmp_path, role="systems")
    win.set_area("next")
    keys = [k for k, _t in strings.TOUR_STEPS_SYSTEMS]
    assert keys == ["next", "next_button", "connect", "role"]
    seen = []
    win.tour.start()
    while win.tour.active:
        seen.append(strings.TOUR_STEPS_SYSTEMS[win.tour.index][0])
        win.tour.next.click()
    assert seen == keys  # all four steps are shown, none is skipped for a hidden target
    text = " ".join(t for _k, t in strings.TOUR_STEPS_SYSTEMS)
    for word in ("Next step", "Add a device", "Connect", "pin number", "accept"):
        assert word in text
    assert "panel" not in text.lower()


def test_the_electrical_tour_is_the_old_one_with_pin_number_words(qtbot, tmp_path: Path) -> None:
    win = window(qtbot, tmp_path, role="electrical")
    assert win.tour.steps() is strings.TOUR_STEPS
    assert "pin number" in strings.TOUR_STEPS[2][1] and "accept" in strings.TOUR_STEPS[2][1]
    win.set_role("systems")
    assert win.tour.steps() is strings.TOUR_STEPS_SYSTEMS


def test_each_tour_step_of_the_systems_role_points_at_something_that_exists(
    qtbot, tmp_path: Path
) -> None:
    win = window(qtbot, tmp_path, role="systems")
    assert win.tour.targets["next"] is win.next_page
    assert win.tour.targets["next_button"] is win.next_page.button
    assert win.tour.targets["connect"] is win.tool_connect
    win.tour.start()
    win.tour.show_step(2)
    assert win.area() == "model" and win.tool_connect.isVisibleTo(win)
    win.tour.skip.click()


# ---- release blockers without command-line words -----------------------------------------------


def test_command_line_words_are_replaced_by_places_in_the_program() -> None:
    gauge = (
        "3 wire(s) have no gauge decided (first: W1). Fill in the derating values (the file "
        "config/derating.json; `harness-design-studio config DIR` lists what is missing) or set "
        "the gauge by hand."
    )
    length = (
        "3 wire(s) have no length (first: W1). Enter the routing segment lengths "
        "(`harness-design-studio import-lengths DIR FILE` loads them from a table)."
    )
    placeholder = (
        "These configuration files are still placeholders: derating. Have an engineer review the "
        'values and set "placeholder" to false in each file (`harness-design-studio config DIR` '
        "lists them). Or release on placeholders with a written reason (command line: "
        "--accept-placeholders REASON); the reason is kept in the change log."
    )
    parts = (
        "2 part(s) used by H1 are not approved: A, B. Approve them in the parts list, or release "
        "with a written reason (command line: --accept-unapproved-parts REASON); the reason is "
        "kept in the change log."
    )
    for text in (gauge, length, placeholder, parts):
        out = plain_blocker(text)
        assert "harness-design-studio" not in out and "command line" not in out
        assert "--accept" not in out and "`" not in out
    assert plain_blocker(gauge).startswith("3 wire(s) have no gauge decided (first: W1).")
    assert "Engineering values" in plain_blocker(gauge)
    assert "Harness tab" in plain_blocker(length) and "Segment lengths" in plain_blocker(length)
    assert plain_blocker(parts).endswith("with a written reason; the reason is kept in the change log.")  # fmt: skip
    assert plain_blocker("Nothing to change here.") == "Nothing to change here."


def test_the_real_blockers_of_a_release_read_without_commands(qtbot, tmp_path: Path) -> None:
    p = with_harness()
    hid = next(iter(p.harnesses))
    found = release_blockers(
        p, hid, by="A", comment="a long enough reason", when="2026-10-27", outputs_folder=tmp_path
    )
    assert found
    for b in found:
        out = plain_blocker(b.message)
        assert "harness-design-studio" not in out and "command line" not in out, out


# ---- Generate: primary only when there is something to generate --------------------------------


def test_generate_is_the_primary_button_only_with_interfaces(qtbot, tmp_path: Path) -> None:
    from harness_design_studio.core.samples import mini3

    win = window(qtbot, tmp_path)  # a blank project: no device
    assert not win.generate_btn.property("primary")
    win.ctl._install(mini3(), None, None)
    win._show_status(path=False)
    assert win.generate_btn.property("primary") is True
    win.ctl._install(new_project(), None, None)
    win._show_status(path=False)
    assert not win.generate_btn.property("primary")
    assert win.generate_btn.isEnabled()  # (still there, and it still works)


# ---- "Made by hand" in the status bar ---------------------------------------------------------


def test_the_status_bar_does_not_say_not_generated_about_connections(qtbot, tmp_path) -> None:
    win = window(qtbot, tmp_path)
    win._show_status(path=False)
    assert win.status_generated.text() == strings.STATUS_NOT_GENERATED  # a blank project
    win.ctl._install(with_harness(), None, None)
    win._show_status(path=False)
    assert win.status_generated.text() == strings.CHIP_BY_HAND
    assert win.status_generated.toolTip() == strings.CHIP_BY_HAND_TIP


# ---- problem counts that agree -----------------------------------------------------------------


def test_the_problems_list_says_n_of_total_under_a_filter(qtbot, tmp_path: Path) -> None:
    win = window(qtbot, tmp_path, with_harness())
    settle(win)
    win.dock_problems.show()
    panel = win.problems_list
    panel.refresh()
    total = panel.total()
    assert total >= 2 and panel.count.text() == f"Problems ({total})"
    assert win.problems_btn.text() == f"Problems ({total})"  # the button counts the whole list
    panel.filters["error"].click()
    shown = panel.table.proxy.rowCount()
    if shown != total:
        assert panel.count.text() == f"Problems ({shown} of {total})"
    panel.filters["warning"].click()
    shown = panel.table.proxy.rowCount()
    assert 0 < shown < total or shown == total
    assert panel.count.text() == (
        f"Problems ({shown} of {total})" if shown != total else f"Problems ({total})"
    )
    panel.filters["all"].click()
    assert panel.count.text() == f"Problems ({total})"


def test_the_problems_tab_of_the_inspector_explains_its_smaller_number(qtbot, tmp_path) -> None:
    win = window(qtbot, tmp_path, with_harness())
    settle(win)
    win.inspector.refresh_badges()
    n = sum(win.ctl.severity_counts())
    total = len(win.ctl.open_findings())
    tip = win.inspector.tabs.tabToolTip(2)
    if n and total != n:
        assert tip == strings.INS_TAB_PROBLEMS_TIP.format(n, total)
    else:
        assert tip == ""


# ---- the chip of the independent check ---------------------------------------------------------


def wait_chip(view) -> None:
    t = time.time()
    while time.time() - t < 5 and view.verify_chip.state() == "pending":
        QApplication.processEvents()


def test_the_chip_never_says_passed_next_to_a_failed_rule(qtbot, tmp_path: Path) -> None:
    win = window(qtbot, tmp_path, with_harness(), role="electrical")
    win.set_area("drawings")
    wait_chip(win.harness_view)
    view = win.harness_view
    # no check has run: the independent check alone passed, and the chip does not claim more
    assert view.verify_chip.state() == "pass" and view.verify_chip.text() == strings.HV_VERIFY_OK
    assert strings.HV_VERIFY_OK == "Independent check passed"
    settle(win)  # the design rules run: some fail
    failed = view._failed_rules()
    assert failed > 0
    assert view.verify_chip.state() == "warning"
    assert view.verify_chip.text() == strings.HV_VERIFY_OK_RULES.format(failed)
    assert "failed" in view.verify_chip.text()


# ---- the pin role column -----------------------------------------------------------------------


def device_window(qtbot, tmp_path: Path):
    win = window(qtbot, tmp_path)
    ctl = win.ctl
    ops, _u = devices.ops_add_device(ctl.project, unit_id="OBC", name="Computer")
    assert ctl.run("device", ops)
    ops, cid = devices.ops_add_connector(ctl.project, "OBC", part_id="EX-MICROD-9-F")
    assert ctl.run("connector", ops)
    ops = devices.ops_set_pin(ctl.project, cid, "1", signal="PWR")
    assert ctl.run("pin 1", ops)
    ops = devices.ops_set_pin(ctl.project, cid, "2", signal="RTN")
    assert ctl.run("pin 2", ops)
    win.go_to("devices")
    win.devices_view.show_unit("OBC")
    win.devices_view.refresh()
    QApplication.processEvents()
    return win, cid


def test_the_role_column_shows_the_given_role_or_the_one_from_the_signal(qtbot, tmp_path) -> None:
    win, cid = device_window(qtbot, tmp_path)
    dv = win.devices_view
    col = dv.pin_model.column_index("role")
    assert dv.pin_model.columns[col].title == "Role"
    cells = {r["pin"]: r["role"] for r in dv.pin_model.rows()}
    assert cells["1"] == "Power (auto)" and cells["2"] == "Return (auto)" and cells["3"] == ""
    assert role_cell("shield", "shield") == "Shield" and role_cell("", "") == ""


def test_the_role_can_be_changed_in_the_table_as_one_undo_step(qtbot, tmp_path) -> None:
    win, cid = device_window(qtbot, tmp_path)
    dv = win.devices_view
    col = dv.pin_model.column_index("role")
    row = dv._pin_index["3"]
    index = dv.pin_model.index(row, col)
    assert dv.pin_model.flags(index) & dv.pin_model.flags(index).ItemIsEditable
    assert dv.pin_model.setData(index, "shield")
    QApplication.processEvents()
    pin = next(x for x in win.ctl.project.connectors[cid].pins if x.id == "3")
    assert pin.role == "shield"
    assert win.ctl.history.next_undo_label == f"Edit pin {cid}.3"
    dv.refresh()
    assert {r["pin"]: r["role"] for r in dv.pin_model.rows()}["3"] == "Shield"
    # back to Automatic (an empty role): the signal name decides again
    assert dv.pin_model.setData(dv.pin_model.index(dv._pin_index["3"], col), "")
    pin = next(x for x in win.ctl.project.connectors[cid].pins if x.id == "3")
    assert pin.role == ""
    win.ctl.undo()
    win.ctl.undo()
    assert next(x for x in win.ctl.project.connectors[cid].pins if x.id == "3").role == ""


def test_the_role_editor_offers_automatic_and_the_six_roles(qtbot, tmp_path) -> None:
    win, cid = device_window(qtbot, tmp_path)
    dv = win.devices_view
    col = dv.pin_model.column_index("role")
    index = dv.pin_table.proxy.index(dv._pin_index["1"], col)
    editor = dv.pin_table.itemDelegate().createEditor(dv.pin_table, None, index)
    assert isinstance(editor, QComboBox)
    assert [editor.itemData(i) for i in range(editor.count())] == [
        "", "power", "return", "ground", "signal", "shield", "spare",
    ]  # fmt: skip
    assert editor.accessibleName() == "Role" and editor.toolTip()
    editor.deleteLater()


def test_a_read_only_project_does_not_edit_the_role(qtbot, tmp_path) -> None:
    win, cid = device_window(qtbot, tmp_path)
    dv = win.devices_view
    win.ctl.project.read_only = True
    dv.refresh()
    dv.pin_model.read_only = True
    index = dv.pin_model.index(0, dv.pin_model.column_index("role"))
    assert not (dv.pin_model.flags(index) & dv.pin_model.flags(index).ItemIsEditable)
