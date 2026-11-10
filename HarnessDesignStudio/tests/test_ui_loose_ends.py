# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type,type-arg,assignment,index"
"""REQ-GUI-28 (M4c of the programme towards 2.0, D-201): loose cable ends in the editor.

A cable dragged from a port and let go on empty ground is a harness drawn by hand whose far end is
loose (`tests/test_ui_tactile_connect.py` holds the gestures on the diagram). Here: the project
tree lists the end under its harness, the inspector shows the origin of a harness and the fields
of an end (name, part, plug, unplug), the keyboard way (Edit > Cable ends), the right-click menus,
the release window's reason for a loose end, the problem card and the Next step page, and the
journey drag, drop, save, reload, plug, generate, export. Every change is one undo step.
"""

import shutil

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QLabel  # noqa: E402

from harness_design_studio.core import part_approval  # noqa: E402
from harness_design_studio.core.devices import connector_parts_to_choose  # noqa: E402
from harness_design_studio.core.model.physical import TBD_PART_ID  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.cable_end_dialog import CableEndDialog  # noqa: E402
from harness_design_studio.gui.dialogs import ChangeDialog  # noqa: E402
from harness_design_studio.gui.inspector import facts_for  # noqa: E402
from tests.gui_helpers import DialogScript, show_problems  # noqa: E402
from tests.test_ui_tactile_connect import World, expert, loose_items, make_loose  # noqa: E402


def one_end(w: World):
    make_loose(w, QPointF(420, 120))
    (item,) = loose_items(w)
    return item.connector_id, item.end.harness_id


def connector(w: World, cid: str):
    return next(c for h in w.project.harnesses.values() for c in h.connectors if c.id == cid)


def facts(w: World, kind: str, oid: str) -> dict[str, dict]:
    return {r["name"]: r for r in facts_for(w.project, kind, oid)}


# ---- the project tree --------------------------------------------------------------------------


def test_the_project_tree_lists_a_loose_end_under_its_harness_and_a_click_picks_it(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path, quick=False)  # (Quick mode shows no pending chip in the tree)
    cid, hid = one_end(w)
    tree = w.win.project_tree
    node = tree.model.find("loose_end", cid)
    assert node is not None and node.parent.id == hid
    assert tree.state_of("loose_end", cid) == ("pending", strings.TREE_LOOSE_STATE)
    assert tree.view.isExpanded(tree.index_for("harness", hid))  # the harness row opens
    assert cid in tree.model.tooltip(node)
    w.win.ctl.select_end(None)
    tree._select_kind("loose_end", cid)
    assert w.win.ctl.selected_end == cid
    assert w.win.inspector.current() == ("cable_end", cid)
    assert w.win.ctl.plug_loose_end(cid, "RW1-J02")
    assert not tree.has("loose_end", cid)  # decided: no longer listed as loose
    w.win.ctl.undo()
    assert tree.has("loose_end", cid)


# ---- the inspector ----------------------------------------------------------------------------


def test_the_inspector_shows_the_origin_of_a_harness_and_of_a_harness_made_from_a_connection(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    cid, hid = one_end(w)
    rows = facts(w, "harness", hid)
    assert rows[strings.INS_FACT_ORIGIN]["value"] == strings.INS_ORIGIN["drawn"]
    assert rows[strings.INS_FACT_LOOSE]["value"] == "1"
    lid = w.win.ctl.add_link("OBC-J02", "PCDU-J02", [("1", "1"), ("2", "2")])
    made = w.win.ctl.create_harness_from_link(lid)
    assert facts(w, "harness", made)[strings.INS_FACT_ORIGIN]["value"] == (
        strings.INS_ORIGIN_LINK.format(link=lid)
    )
    w.win.inspector.show_object("harness", made)
    assert w.win.inspector.facts_title.text().endswith(made)


def test_the_inspector_shows_a_loose_end_and_names_and_decides_it_in_one_step_each(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    cid, _hid = one_end(w)
    ins = w.win.inspector
    assert ins.current() == ("cable_end", cid)
    rows = facts(w, "cable_end", cid)
    assert rows[strings.INS_FACT_ORIGIN]["value"] == strings.INS_ORIGIN["drawn"]
    assert rows[strings.INS_FACT_PART]["value"] == strings.INS_END_TBD
    assert rows[strings.INS_FACT_PART]["state"] == "pending"
    assert rows[strings.INS_FACT_PLUGGED]["value"] == strings.INS_END_OPEN
    box = ins.end_box
    assert box.isVisibleTo(ins) and box.plug.isEnabled() and not box.unplug.isEnabled()
    assert box.part.findData(TBD_PART_ID) < 0  # the stand-in is never offered as a part
    n = w.steps()
    box.name.setText("Free end")
    box.rename.click()
    assert connector(w, cid).name == "Free end" and w.steps() == n + 1
    assert connector_parts_to_choose(w.project), "the example library has connector parts"
    box.part.setCurrentIndex(0)
    part = box.part.currentData()
    box.use_part.click()
    c = connector(w, cid)
    assert (c.role, c.part_id, c.mates_with) == ("cable", part, None) and w.steps() == n + 2
    assert facts(w, "cable_end", cid)[strings.INS_FACT_PLUGGED]["value"] == strings.INS_END_FREE
    w.win.ctl.undo()
    assert connector(w, cid).role == "loose"


def test_unplug_turns_a_plugged_end_loose_again_and_it_plugs_in_again(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    cid, hid = one_end(w)
    w.drag(QPointF(420, 120), w.drop_spot(w.port("RW1", "RW1-J02")))
    assert connector(w, cid).mates_with == "RW1-J02"
    wires = len(w.project.harnesses[hid].wires)
    w.win.ctl.select_end(cid)
    box = w.win.inspector.end_box
    assert box.unplug.isEnabled() and not box.plug.isEnabled()
    n = w.steps()
    box.unplug.click()
    c = connector(w, cid)
    assert (c.role, c.mates_with, c.part_id) == ("loose", None, TBD_PART_ID)
    assert len(w.project.harnesses[hid].wires) == wires and w.steps() == n + 1  # wires stay
    w.settle()
    item = w.scene.end_items[cid]
    assert item.end.loose and item.spot == pytest.approx(item.home(), abs=1.0)
    w.drag(QPointF(*item.spot), w.drop_spot(w.port("RW1", "RW1-J02")))  # re-plug
    assert connector(w, cid).mates_with == "RW1-J02" and w.steps() == n + 2


def test_a_harness_made_from_a_connection_refuses_to_unplug_and_the_menu_says_why(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    lid = w.win.ctl.add_link("OBC-J01", "RW1-J02", [("1", "3"), ("2", "4")])
    hid = w.win.ctl.create_harness_from_link(lid)
    plug = next(c.id for c in w.project.harnesses[hid].connectors if c.mates_with == "RW1-J02")
    why = w.win.ctl.why_not_unplug(plug)
    assert lid is not None and lid in why and "made from the connection" in why
    menu = w.view.build_context_menu("unit", "RW1", QPointF(600, 220), connector="RW1-J02")
    entry = next(a for a in menu.actions() if a.text().startswith(f"Unplug {plug}"))
    assert not entry.isEnabled() and entry.toolTip() == why
    leave = next(a for a in menu.actions() if a.text().startswith("Leave a loose end from"))
    assert not leave.isEnabled()  # a cable is plugged in there already
    n = w.steps()
    assert not w.win.ctl.unplug(plug) and w.steps() == n
    assert "made from the connection" in w.win.toasts.messages[-1]


def test_the_right_click_menu_of_a_connector_leaves_a_loose_end_and_that_of_the_end_plugs_it(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    menu = w.view.build_context_menu("unit", "OBC", QPointF(100, 100), connector="OBC-J03")
    leave = next(a for a in menu.actions() if a.text().startswith("Leave a loose end from"))
    assert leave.isEnabled()
    leave.trigger()
    (item,) = loose_items(w)
    assert connector(w, item.end.harness_id + "-P1").mates_with == "OBC-J03"
    menu = w.view.build_context_menu("cable_end", item.connector_id, QPointF(*item.spot))
    texts = [a.text() for a in menu.actions()]
    assert any(t.startswith(strings.A_PLUG_LOOSE_MENU) for t in texts)
    assert any(
        t.startswith(strings.CM_END_HARNESS.format(harness=item.end.harness_id)) for t in texts
    )
    reset = next(a for a in menu.actions() if a.text().startswith(strings.CM_END_RESET))
    assert not reset.isEnabled()  # it hangs where the tool puts it


# ---- the keyboard way: Edit > Cable ends ------------------------------------------------------------


def test_the_keyboard_way_leaves_plugs_and_unplugs_a_loose_end_from_the_menu(
    qtbot, tmp_path
) -> None:
    w = World(tmp_path, quick=False, mode="guided")
    w.win.ctl.select("unit", "OBC")
    seen: list[CableEndDialog] = []

    def choose(port: str):
        def fn(dlg) -> None:
            seen.append(dlg)
            k = dlg.port_box.findData(port)
            assert k >= 0, port
            dlg.port_box.setCurrentIndex(k)

        return fn

    DialogScript(w.win, choose("OBC-J01"))
    assert (
        w.win.act_leave_loose.isEnabled() and w.win.menu_cable_ends.title() == strings.M_CABLE_ENDS
    )
    w.win.act_leave_loose.trigger()
    ports = [seen[0].port_box.itemData(k) for k in range(seen[0].port_box.count())]
    assert ports and all(p.startswith("OBC-") for p in ports)  # the selected device's ports
    cid = w.win.ctl.selected_end
    assert cid is not None and connector(w, cid).role == "loose" and w.steps() == 1
    DialogScript(w.win, choose("RW1-J02"))
    w.win.act_plug_loose.trigger()
    assert not seen[1].end_box.isVisibleTo(seen[1])  # the picked end is not asked again
    assert connector(w, cid).mates_with == "RW1-J02" and w.steps() == 2
    script = DialogScript(w.win)
    w.win.act_unplug.trigger()  # the picked end is plugged: unplugged at once
    assert script.seen == [] and connector(w, cid).role == "loose" and w.steps() == 3


def test_the_menu_window_says_when_there_is_nothing_to_choose(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    script = DialogScript(w.win, accept=False)
    w.win.act_plug_loose.trigger()
    (dlg,) = script.seen
    assert isinstance(dlg, CableEndDialog)
    assert not dlg.ok.isEnabled() and dlg.note.isVisibleTo(dlg)
    assert dlg.note.text() == strings.LE_NO_ENDS


# ---- the release window, the problem card and the Next step page ------------------------------------


def test_the_release_window_asks_for_a_reason_for_a_loose_end(qtbot, tmp_path, monkeypatch) -> None:
    from harness_design_studio.gui import main_window

    w = expert(tmp_path)
    cid, hid = one_end(w)
    w.win.ctl.save_as(tmp_path / "proj")
    script = DialogScript(w.win, accept=False)
    w.win.change_flow("release", hid)
    (dlg,) = script.seen
    assert isinstance(dlg, ChangeDialog)
    assert all("loose" not in b for b in dlg.blockers)  # asked for below, not a blocker
    warn = dlg.findChild(QLabel, "change-loose-warning")
    assert warn is not None and cid in warn.text()
    assert strings.HINT_LOOSE_REASON in dlg.missing()
    dlg.loose_reason.setText("short")
    assert strings.HINT_LOOSE_REASON in dlg.missing()
    dlg.loose_reason.setText("Bench cable, end decided at integration")
    assert strings.HINT_LOOSE_REASON not in dlg.missing()
    assert dlg.accepted_loose_ends() == "Bench cable, end decided at integration"
    seen: dict = {}

    def fake_release(project, harness_id, **kw):
        seen.update(kw)
        raise main_window.HarnessError("stop here")

    def fill(d: ChangeDialog) -> None:
        d.by.setText("Ada")
        d.comment.setPlainText("First release for the bench")
        d.loose_reason.setText("Bench cable, end decided at integration")

    monkeypatch.setattr(main_window, "plan_release", fake_release)
    DialogScript(w.win, fill)
    with pytest.raises(main_window.HarnessError):
        w.win.change_flow("release", hid)
    assert seen["accept_loose_ends"] == "Bench cable, end decided at integration"


def test_the_problem_card_of_a_loose_end_says_how_to_decide_it_and_show_goes_to_the_end(
    qtbot, tmp_path
) -> None:
    w = expert(tmp_path)
    cid, _hid = one_end(w)
    w.win.ctl.select("unit", "RW1")
    w.win.ctl.run_drc_now()
    panel = show_problems(w.win)
    f = next(x for x in w.win.ctl.open_findings() if x.object_id == TBD_PART_ID)
    card = panel._card(f)
    texts = " ".join(lbl.text() for lbl in card.findChildren(QLabel))
    assert strings.LOOSE_CARD_WHY in texts and "Approve the part" not in texts
    w.win.show_object(TBD_PART_ID)  # the card's Show
    assert w.win.ctl.selected_end == cid and w.win.inspector.current() == ("cable_end", cid)
    assert part_approval.approval_blocker(w.project, TBD_PART_ID)  # never approved from a page
    facts_ = w.win._next_problem_facts()
    problem = facts_["problem"]
    assert problem is None or problem.approve != TBD_PART_ID


# ---- the journey --------------------------------------------------------------------------------


def test_journey_drag_drop_save_reload_plug_generate_and_export(qtbot, tmp_path) -> None:
    w = expert(tmp_path)
    cid, hid = one_end(w)
    folder = tmp_path / "proj"
    w.win.ctl.save_as(folder)
    copy = tmp_path / "copy"
    shutil.copytree(folder, copy, ignore=shutil.ignore_patterns(".harness.lock"))
    w2 = World(tmp_path / "second", quick=False, mode="expert")
    assert w2.win.open_project(copy)
    w2.win.ctl.set_mode("expert")
    w2.view.zoom_100()
    w2.view.centerOn(QPointF(400, 260))
    w2.settle()
    (item,) = loose_items(w2)
    assert item.connector_id == cid
    w2.drag(QPointF(*item.spot), w2.drop_spot(w2.port("RW1", "RW1-J02")))
    assert connector(w2, cid).mates_with == "RW1-J02"
    w2.win.ctl.save()
    drawn = w2.project.harnesses[hid]
    DialogScript(w2.win)
    w2.win.generate_flow()
    assert w2.project.harnesses[hid] == drawn  # Generate leaves a harness drawn by hand alone
    w2.win.export_flow()
    out = copy / "outputs" / "harnesses" / hid
    assert out.is_dir() and any(out.iterdir())
