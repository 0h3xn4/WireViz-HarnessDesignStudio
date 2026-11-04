# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""Quick mode's Connect: two devices are joined with no window, as one undo step, and the toast
says what was joined and offers Undo and Edit pairs. Without Quick mode the Link connectors
window behaves as before."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from harness_design_studio.core import devices, edit  # noqa: E402
from harness_design_studio.core.commands import Put, apply_ops  # noqa: E402
from harness_design_studio.core.model import Pin  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.link_dialog import LinkDialog  # noqa: E402
from tests.gui_helpers import DialogScript, click_unit, make_window  # noqa: E402
from tests.helpers import pinout_project  # noqa: E402


def window(tmp_path, *, quick: bool):
    win = make_window(tmp_path)
    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    win.ctl._install(p, None, None)
    if quick:
        win.act_quick.trigger()
    QApplication.processEvents()
    return win


def buttons(win, name: str) -> list[QPushButton]:
    return [b for b in win.toasts.findChildren(QPushButton, name) if b.isVisibleTo(win.toasts)]


def test_quick_connect_makes_the_link_without_the_window_in_one_step(qtbot, tmp_path) -> None:
    win = window(tmp_path, quick=True)
    script = DialogScript(win)
    before = win.ctl.history.revision
    lid = win.quick_link_flow("OBC", "RW1")
    assert script.seen == [] and lid == "L1"
    assert win.ctl.history.revision == before + 1  # ONE step
    link = win.ctl.project.links[lid]
    assert (link.a_connector, link.b_connector) == ("OBC-J01", "RW1-J02") and len(link.pairs) == 4
    assert win.ctl.selected_link == lid
    assert strings.QL_CONNECTED.format(a="OBC", b="RW1") in win.toasts.messages[-1]
    assert strings.QL_PAIRS_SIGNALS.format(n=4) in win.toasts.messages[-1]
    assert buttons(win, "toast-undo") and buttons(win, "toast-action")
    assert buttons(win, "toast-action")[0].text() == strings.QL_EDIT_PAIRS == "Edit pairs"


def test_the_connect_tool_in_quick_mode_joins_on_the_second_click(qtbot, tmp_path) -> None:
    win = window(tmp_path, quick=True)
    script = DialogScript(win)
    win.ctl.begin_link()
    click_unit(win, "OBC")
    click_unit(win, "RW1")
    QApplication.processEvents()
    assert script.seen == [] and list(win.ctl.project.links) == ["L1"]


def test_without_quick_the_connect_tool_still_opens_the_window(qtbot, tmp_path) -> None:
    win = window(tmp_path, quick=False)
    script = DialogScript(win)
    win.ctl.begin_link()
    click_unit(win, "OBC")
    click_unit(win, "RW1")
    QApplication.processEvents()
    assert len(script.seen) == 1 and isinstance(script.seen[0], LinkDialog)
    assert script.seen[0].windowTitle() == strings.LINK_TITLE == "Link connectors"
    assert len(win.ctl.project.links) == 1  # (accepted as before)


def test_the_toast_undo_takes_the_whole_connection_away(qtbot, tmp_path) -> None:
    win = window(tmp_path, quick=True)
    win.quick_link_flow("OBC", "RW1")
    buttons(win, "toast-undo")[0].click()
    assert win.ctl.project.links == {}


def test_the_toast_edit_pairs_opens_the_window_on_that_link(qtbot, tmp_path) -> None:
    win = window(tmp_path, quick=True)
    win.quick_link_flow("OBC", "RW1")
    script = DialogScript(win)
    buttons(win, "toast-action")[0].click()
    assert len(script.seen) == 1 and script.seen[0].link_id == "L1"


def test_a_device_without_a_connector_gets_one_in_the_same_step(qtbot, tmp_path) -> None:
    win = window(tmp_path, quick=True)
    ops, uid = devices.ops_add_device(win.ctl.project, name="Camera")
    win.ctl.run("Add device", ops)
    before = win.ctl.history.revision
    lid = win.quick_link_flow("OBC", uid)
    assert lid and win.ctl.history.revision == before + 1
    assert [c.id for c in win.ctl.project.connectors.values() if c.unit_id == uid]
    assert "got the connector" in win.toasts.messages[-1]
    win.ctl.undo()
    assert not [c for c in win.ctl.project.connectors.values() if c.unit_id == uid]
    assert lid not in win.ctl.project.links


def test_the_command_without_devices_uses_the_only_two_or_asks(qtbot, tmp_path) -> None:
    win = make_window(tmp_path)
    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    win.ctl._install(p, None, None)
    win.act_quick.trigger()
    script = DialogScript(win, accept=False)
    win.act_link_connectors.trigger()  # three devices: the window asks which
    assert len(script.seen) == 1
    win.ctl.run("Delete", edit.ops_delete_unit(win.ctl.project, "PCDU"))
    script.seen.clear()
    win.act_link_connectors.trigger()  # two devices: it just connects them
    assert script.seen == [] and len(win.ctl.project.links) == 1


def test_a_link_with_no_pair_is_made_and_edit_pairs_can_pair_it(qtbot, tmp_path) -> None:
    win = window(tmp_path, quick=True)
    p = win.ctl.project
    for cid, ids in (("PCDU-J02", ("A", "B")), ("OBC-J02", ("X", "Y"))):
        c = p.connectors[cid].model_copy(update={"pins": [Pin(id=i) for i in ids]})
        apply_ops(p, [Put("connectors", c)])
    lid = win.quick_link_flow("PCDU", "OBC", a_connector="PCDU-J02", b_connector="OBC-J02")
    assert lid and win.ctl.project.links[lid].pairs == []
    assert strings.QL_PAIRS_NONE in win.toasts.messages[-1]
    script = DialogScript(win)
    win.edit_link_flow(lid)  # (Edit pairs opens the window on the link with no pair)
    assert script.seen[0].link_id == lid


def test_a_read_only_project_and_a_same_device_pair_are_refused_with_a_reason(
    qtbot, tmp_path
) -> None:
    win = window(tmp_path, quick=True)
    assert win.quick_link_flow("OBC", "OBC") is None
    assert "same device" in win.toasts.messages[-1]
    assert win.ctl.project.links == {}
    win.ctl.project.read_only = True
    messages: list[str] = []
    win.ctl.message.connect(lambda t, _u: messages.append(t))
    win.link_flow("OBC", "", "RW1", "")
    assert win.ctl.project.links == {} and messages
