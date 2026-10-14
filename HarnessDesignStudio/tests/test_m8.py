"""M8: routing sketch in drawings, drawing preview, outline panel, arrange and UI-scale diagram."""

import pytest

from harness_design_studio.core import edit
from harness_design_studio.core.commands import History, Op, Put, apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import BranchPoint, Harness, Project, Segment, evolve
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.drawing import (
    SKETCH_MAX_NODES,
    harness_sheets,
    sketch_layout,
)
from harness_design_studio.core.outputs.stamp import Stamp
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import sat15, sat15_full, stress_project
from tests.helpers import time_limit


def with_branch(p: Project, hid: str = "W010") -> Harness:
    h = p.harnesses[hid]
    a, b = h.connectors[0].id, h.connectors[1].id
    segs = [
        Segment(id=f"{hid}-L1", from_node=a, to_node=f"{hid}-B1", length_m=0.4),
        Segment(id=f"{hid}-L2", from_node=f"{hid}-B1", to_node=b, length_m=0.8),
    ]
    apply_ops(
        p,
        [
            Put(
                "harnesses",
                evolve(h, branch_points=[BranchPoint(id=f"{hid}-B1", name="B1")], segments=segs),
            )
        ],
    )
    return p.harnesses[hid]


# ---- routing sketch -------------------------------------------------------------------------------


def test_sketch_places_nodes_in_columns_by_distance() -> None:
    p = sat15_full()
    h = with_branch(p)
    layout = sketch_layout(h)
    assert layout is not None
    cols = {n: c for n, (c, _r) in layout.items()}
    assert sorted(cols.values()) == [0, 1, 2] and cols[f"{h.id}-B1"] == 1


def test_sketch_is_drawn_with_every_segment_and_length() -> None:
    p = sat15_full()
    h = with_branch(p)
    sheet = harness_sheets(p, h, Stamp("t", "t"), "A3")[0]
    text = " ".join(getattr(i, "s", "") for i in sheet.items)
    assert (
        "Routing (schematic" in text
        and "W010-L1 0.4 m" in text
        and "W010-L2 0.8 m" in text
        and "W010-B1" in text
    )


def test_regression_harness_with_segments_but_no_connectors_has_no_sketch() -> None:
    """Found by fuzzing a damaged project."""
    p = sat15_full()
    h = evolve(p.harnesses["W010"], connectors=[], wires=[], shields=[])
    assert sketch_layout(h) is None
    assert harness_sheets(p, h, Stamp("t", "t"), "A3")


def test_sketch_is_skipped_for_big_or_missing_trees() -> None:
    p = sat15_full()
    h = p.harnesses["W010"]
    assert sketch_layout(evolve(h, segments=[])) is None
    many = [BranchPoint(id=f"B{k}", name=f"B{k}") for k in range(SKETCH_MAX_NODES)]
    segs = [
        Segment(id=f"S{k}", from_node=h.connectors[0].id, to_node=f"B{k}")
        for k in range(SKETCH_MAX_NODES)
    ]
    assert sketch_layout(evolve(h, branch_points=many, segments=segs)) is None


def test_outputs_with_a_sketch_still_verify_and_paginate() -> None:
    p = sat15_full()
    with_branch(p)
    assert verify_outputs(p, build_outputs(p).files).ok


# ---- arrange ---------------------------------------------------------------------------------------


def test_arrange_keeps_lanes_never_overlaps_and_is_idempotent() -> None:
    p = sat15()
    ops = edit.ops_arrange(p)
    History(p).execute("arrange", ops)
    zones = edit.effective_zones(p)
    for uid, pl in p.placements.items():
        assert edit.zone_of_x(p, pl.x) == p.units[uid].zone, uid  # lanes unchanged
    pos = sorted((pl.x, pl.y) for pl in p.placements.values())
    for a, b in zip(pos, pos[1:], strict=False):
        assert a[0] != b[0] or b[1] - a[1] >= edit.UNIT_FOOTPRINT_H - 20
    assert edit.ops_arrange(p) == []  # a second run changes nothing
    assert len(zones) >= 1


def test_arrange_is_idempotent_at_stress_size() -> None:
    p = stress_project()
    apply_ops(p, edit.ops_arrange(p))
    assert edit.ops_arrange(p) == []  # B-22: it used to move 100 units on the second run


def test_arrange_reduces_total_link_length_and_is_one_undo_step() -> None:
    p = sat15()

    def total(project) -> float:  # type: ignore[no-untyped-def]
        t = 0.0
        for i in project.interfaces.values():
            a, b = (project.placements[e.unit_id] for e in i.endpoints[:2])
            t += abs(a.y - b.y)
        return t

    # scramble the vertical order first
    import random

    rng = random.Random(3)
    ys = [40.0 + 140.0 * k for k in range(len(p.units))]
    rng.shuffle(ys)
    scrambled: list[Op] = [
        Put("placements", evolve(p.placements[u], y=ys[k])) for k, u in enumerate(sorted(p.units))
    ]
    apply_ops(p, scrambled)
    hist = History(p)
    before, h0 = total(p), model_hash(p)
    hist.execute("arrange", edit.ops_arrange(p))
    assert total(p) < before
    hist.undo()
    assert model_hash(p) == h0


def test_arrange_is_deterministic() -> None:
    assert edit.ops_arrange(sat15()) == edit.ops_arrange(sat15())


# ---- GUI -------------------------------------------------------------------------------------------


@pytest.fixture
def win(qtbot, tmp_path):  # type: ignore[no-untyped-def]
    pytest.importorskip("PySide6")  # only the editor tests need Qt: the headless ones above run
    from tests.gui_helpers import make_window

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    p = sat15_full()
    w.ctl._install(p, None, None)
    w.go_to("harness")
    return w


@pytest.mark.gui
def test_preview_shows_the_selected_harness_and_pages(win) -> None:  # type: ignore[no-untyped-def]
    view = win.harness_view  # the drawing of the Harness tab
    assert view.select_harness("W010")
    assert view.wait_idle()
    assert view.preview.sheets and "Sheet 1 of" in view.preview.label.text()
    assert not view.preview.prev.isEnabled()
    img = view.preview.view.grab()  # paints the real sheet without errors
    assert not img.isNull()


@pytest.mark.gui
def test_preview_follows_the_design(win) -> None:  # type: ignore[no-untyped-def]
    view = win.harness_view
    view.select_harness("W010")
    assert view.wait_idle()
    h = win.ctl.project.harnesses["W010"]
    win.ctl.run("rename", [Put("harnesses", evolve(h, name="Renamed harness"))])
    view.refresh()
    assert view.wait_idle()
    items = view.preview.sheets[0].items
    assert any("Renamed harness" in getattr(i, "s", "") for i in items)


@pytest.mark.gui
def test_preview_pagination_buttons(win) -> None:  # type: ignore[no-untyped-def]
    view = win.harness_view
    h = win.ctl.project.harnesses["W010"]
    many = [evolve(h.wires[k % len(h.wires)], id=f"W010-{k + 1:03d}") for k in range(70)]
    apply_ops(win.ctl.project, [Put("harnesses", evolve(h, wires=many, shields=[]))])
    view.refresh()
    view.select_harness("W010")
    assert view.wait_idle()
    n = len(view.preview.sheets)
    assert n >= 2 and view.preview.next.isEnabled()
    view.preview.next.click()
    assert view.preview.page == 1 and view.preview.prev.isEnabled()


@pytest.mark.gui
def test_the_project_tree_lists_units_and_interfaces_and_follows_selection(win) -> None:  # type: ignore[no-untyped-def]
    """Was the Outline: every unit and interface as a tree the keyboard and screen readers walk
    through, the selection following the diagram both ways."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    tree = win.project_tree
    p = win.ctl.project
    assert tree.child_ids("units") == sorted(p.units)
    assert tree.child_ids("interfaces") == sorted(p.interfaces)
    iid = sorted(p.interfaces)[0]
    tree.view.setCurrentIndex(tree.index_for("interface", iid))
    QTest.keyClick(tree.view, Qt.Key.Key_Return)  # picking in the tree selects in the diagram
    assert win.ctl.selection and (win.ctl.selection.kind, win.ctl.selection.id) == (
        "interface",
        iid,
    )
    unit = sorted(p.units)[3]
    win.ctl.select("unit", unit)  # and the other way round
    assert tree.current() == ("unit", unit)


@pytest.mark.gui
def test_arrange_action_runs_and_can_be_undone(win) -> None:  # type: ignore[no-untyped-def]
    p = win.ctl.project
    unit = sorted(p.units)[0]
    apply_ops(p, [Put("placements", evolve(p.placements[unit], y=900.0))])
    before = model_hash(p)
    win.act_arrange.trigger()
    assert model_hash(p) != before and "arranged" in win.toasts.messages[-1].lower()
    win.ctl.undo()
    assert model_hash(p) == before
    win.act_arrange.trigger()
    win.act_arrange.trigger()
    assert "already" in win.toasts.messages[-1].lower()


@pytest.mark.gui
def test_arrange_is_fast_at_stress_size() -> None:
    import time

    p = stress_project(units=200, interfaces=600)
    generate_project(p)
    t = time.perf_counter()
    ops = edit.ops_arrange(p)
    assert time.perf_counter() - t < time_limit(2.0) and ops
