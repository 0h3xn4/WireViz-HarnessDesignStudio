# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined"
"""REQ-GUI-22. Owner feedback: the diagram must not trap devices. A device may be put anywhere,
past the edge and below zero, and stays there. The part with no screen in it: a position outside
the lanes is stored and read back as it is (the layout file, the reopened project, the model
hash), aligning never moves a device back to zero, and the written block diagram and the exported
picture frame every device however far out it sits (they draw by lane and row, never by the
position on the canvas)."""

import json
from pathlib import Path

from harness_design_studio.core import edit
from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.links import plan_add_link
from harness_design_studio.core.outputs import system
from harness_design_studio.core.outputs.canvas import Sheet, fit_sheet, item_bounds, to_svg
from harness_design_studio.core.outputs.stamp import stamp_of
from harness_design_studio.core.samples import mini3
from tests.helpers import pinout_project

FAR = {"OBC": (-5000.0, -3200.5), "PCDU": (250000.0, 120000.0), "RW1": (-1.0e6, 9.0e5)}


def far_project():
    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    ops, _ = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    apply_ops(p, edit.ops_move_units(p, FAR))
    return p


def inside(sheet: Sheet) -> bool:
    return all(
        x0 >= -1e-9 and y0 >= -1e-9 and x1 <= sheet.width + 1e-9 and y1 <= sheet.height + 1e-9
        for x0, y0, x1, y1 in (item_bounds(it) for it in sheet.items)
    )


def test_a_position_below_zero_or_far_out_is_stored_as_it_is(tmp_path: Path) -> None:
    p = far_project()
    for uid, (x, y) in FAR.items():
        assert (p.placements[uid].x, p.placements[uid].y) == (x, y)
    save_project(p, tmp_path)
    saved = json.loads((tmp_path / "logical" / "layout.json").read_text(encoding="utf-8"))
    got = {q["id"]: (q["x"], q["y"]) for q in saved["placements"]}
    assert got == FAR


def test_a_reopened_project_has_every_device_where_it_was_left_and_the_same_hash(
    tmp_path: Path,
) -> None:
    p = far_project()
    save_project(p, tmp_path)
    again = load_project(tmp_path).project
    assert {uid: (q.x, q.y) for uid, q in again.placements.items()} == FAR
    assert model_hash(again) == model_hash(p)
    assert {uid: edit.position_of(again, uid) for uid in FAR} == FAR


def test_a_move_past_the_edge_is_one_undo_step_and_undo_puts_the_old_place_back() -> None:
    p = mini3()
    h = History(p)
    before = edit.position_of(p, "OBC")
    h.execute("Move OBC", edit.ops_move_unit(p, "OBC", -800.0, -400.0))
    assert edit.position_of(p, "OBC") == (-800.0, -400.0) and len(h._undo) == 1
    h.undo()
    assert edit.position_of(p, "OBC") == before
    h.redo()
    assert edit.position_of(p, "OBC") == (-800.0, -400.0)


def test_a_device_moved_far_left_is_in_the_first_lane_and_far_right_in_the_last() -> None:
    p = mini3()
    zones = edit.effective_zones(p)
    apply_ops(p, edit.ops_move_units(p, {"OBC": (-9000.0, 10.0), "RW1": (9000.0, 10.0)}))
    assert p.units["OBC"].zone == zones[0] and p.units["RW1"].zone == zones[-1]


def test_aligning_does_not_pull_devices_back_to_zero() -> None:
    p = mini3()
    apply_ops(p, edit.ops_move_units(p, {"OBC": (0.0, -900.0), "PCDU": (0.0, -500.0)}))
    apply_ops(p, edit.ops_align(p, ["OBC", "PCDU"], "top"))
    assert edit.position_of(p, "OBC")[1] == -900.0 and edit.position_of(p, "PCDU")[1] == -900.0
    apply_ops(p, edit.ops_align(p, ["OBC", "PCDU"], "left"))
    assert edit.position_of(p, "OBC")[0] == edit.position_of(p, "PCDU")[0]


def test_no_rule_keeps_devices_from_overlapping_when_they_are_moved() -> None:
    """Moving is free: two devices may sit on each other (only a new device is put in a free
    place, and the written drawings never overlap the boxes: they lay devices out by row)."""
    p = mini3()
    apply_ops(p, edit.ops_move_units(p, {"OBC": (200.0, 200.0), "PCDU": (200.0, 200.0)}))
    assert edit.position_of(p, "OBC") == edit.position_of(p, "PCDU") == (200.0, 200.0)


def test_the_written_block_diagram_does_not_depend_on_where_devices_sit_on_the_canvas() -> None:
    near = far_project()
    stamp = stamp_of(near)  # (the stamp carries the model hash, which follows the layout file)
    near_sheet = system.block_diagram(near, stamp)
    shifted = far_project()
    # the same lanes (zones), other places on the canvas: far out in the lane's direction
    apply_ops(
        shifted,
        edit.ops_move_units(
            shifted, {uid: (x * 7.0, y * 3.0 - 11.0) for uid, (x, y) in FAR.items()}
        ),
    )
    shifted_sheet = system.block_diagram(shifted, stamp)
    assert to_svg(near_sheet, "m") == to_svg(shifted_sheet, "m")


def test_the_written_block_diagram_and_the_cut_sheet_frame_every_device_however_far_out() -> None:
    p = far_project()
    sheet = system.block_diagram(p, stamp_of(p))
    assert (sheet.width, sheet.height) == (420, 297) and inside(sheet)
    fitted = fit_sheet(sheet)
    assert inside(fitted)
    drawn = " ".join(getattr(it, "s", "") for it in fitted.items)
    for uid in FAR:
        assert uid in drawn  # every device is on the sheet
    assert (
        max(item_bounds(it)[2] for it in fitted.items if it is not fitted.items[0]) <= fitted.width
    )


def test_many_devices_far_out_still_frame_within_a_sheet_that_grows_with_the_lanes_only() -> None:
    p = mini3()
    far = {uid: (-1.0e5 + 7 * k, 5.0e5 - 3 * k) for k, uid in enumerate(sorted(p.units))}
    apply_ops(p, edit.ops_move_units(p, far))
    sheet = system.block_diagram(p, stamp_of(p))
    assert inside(sheet) and inside(fit_sheet(sheet))
