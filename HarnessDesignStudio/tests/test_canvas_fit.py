# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""`fit_sheet`: a sheet cut down to its content, nothing moved. No Qt."""

import pytest

from harness_design_studio.core.outputs import system
from harness_design_studio.core.outputs.canvas import (
    Line,
    Rect,
    Sheet,
    Text,
    fit_sheet,
    item_bounds,
)
from harness_design_studio.core.outputs.stamp import stamp_of
from harness_design_studio.core.samples import mini3, sat15


def inside(sheet: Sheet) -> bool:
    return all(
        x0 >= -1e-9 and y0 >= -1e-9 and x1 <= sheet.width + 1e-9 and y1 <= sheet.height + 1e-9
        for x0, y0, x1, y1 in (item_bounds(it) for it in sheet.items)
    )


def test_the_sheet_ends_a_margin_after_the_last_thing_drawn() -> None:
    s = Sheet(420, 297, title="T")
    s.add(Rect(2, 2, 416, 293, width=0.5))
    s.add(Rect(10, 20, 44, 12, width=0.4), Text(11, 30, "ABC", size=3.0))
    s.add(Line(54, 25, 100, 60, width=0.3))
    fitted = fit_sheet(s, 8.0)
    assert fitted.width == pytest.approx(100.15 + 8.0) and fitted.height == pytest.approx(60.15 + 8.0)  # fmt: skip
    assert fitted.title == "T" and (s.width, s.height) == (420, 297)  # (a copy: the sheet stays)


def test_nothing_moves_and_the_border_follows_the_new_size() -> None:
    s = Sheet(420, 297)
    s.add(Rect(2, 2, 416, 293, width=0.5), Rect(10, 20, 44, 12), Text(11, 30, "ABC"))
    fitted = fit_sheet(s)
    assert fitted.items[1:] == s.items[1:]  # every other item is the same object
    frame = fitted.items[0]
    assert isinstance(frame, Rect) and (frame.x, frame.y) == (2, 2)
    assert (frame.w, frame.h) == (fitted.width - 4, fitted.height - 4) and frame.width == 0.5


def test_it_never_makes_a_sheet_larger_and_leaves_an_empty_one_alone() -> None:
    s = Sheet(50, 40)
    s.add(Rect(2, 2, 46, 36), Text(5, 10, "a very long title that runs far past the edge", size=3))
    fitted = fit_sheet(s)
    assert fitted.width == 50 and fitted.height < 40  # (the long title is cut by the sheet)
    empty = Sheet(50, 40)
    assert fit_sheet(empty) is empty


def test_a_small_block_diagram_is_cut_and_everything_lies_inside() -> None:
    p = mini3()
    sheet = system.block_diagram(p, stamp_of(p))
    fitted = fit_sheet(sheet)
    assert (sheet.width, sheet.height) == (420, 297)
    assert fitted.width < 300 and fitted.height < 200
    assert inside(fitted)
    texts = {it.s for it in fitted.items if isinstance(it, Text)}
    assert {"OBC", "PCDU", "RW1", fitted.title} <= texts  # (the title and the devices stay)
    assert any(t.startswith("harness-design-studio") for t in texts)  # (and the stamp)


def test_a_big_diagram_keeps_its_size_and_clips_nothing() -> None:
    p = sat15()
    sheet = system.block_diagram(p, stamp_of(p))
    fitted = fit_sheet(sheet)
    assert inside(sheet) and inside(fitted)
    assert fitted.width <= sheet.width and fitted.height <= sheet.height
    assert [it for it in fitted.items[1:]] == [it for it in sheet.items[1:]]
