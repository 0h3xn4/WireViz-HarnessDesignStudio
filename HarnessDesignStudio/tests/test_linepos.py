"""REQ-GUI-13. The place of a label on its line, in pure geometry (`core/linepos.py`): a fraction `t`
of the length of the polyline, the nearest point of the line to the pointer, the clamp at the ends
and for a line that got shorter, and the reading of a free offset of an earlier version."""

import math

import pytest

from harness_design_studio.core import linepos
from harness_design_studio.core.model import mark_is_along

# an orthogonal route with two corners, as the router draws one: 92 across, 98.5 down, 108 across
ROUTE = [(270.0, 114.0), (362.0, 114.0), (362.0, 212.5), (470.0, 212.5)]
LENGTH = 92.0 + 98.5 + 108.0


def test_the_length_is_the_sum_of_the_pieces_corners_included() -> None:
    assert linepos.length(ROUTE) == pytest.approx(LENGTH)
    assert linepos.length([(0.0, 0.0), (3.0, 4.0)]) == 5.0
    assert linepos.length([(1.0, 1.0)]) == 0.0
    assert linepos.length([]) == 0.0


def test_a_fraction_is_a_point_of_the_line_and_the_corners_are_passed() -> None:
    assert linepos.point_at(ROUTE, 0.0) == (270.0, 114.0)
    assert linepos.point_at(ROUTE, 1.0) == (470.0, 212.5)
    assert linepos.point_at(ROUTE, 46.0 / LENGTH) == pytest.approx((316.0, 114.0))
    corner = 92.0 / LENGTH
    assert linepos.point_at(ROUTE, corner) == pytest.approx((362.0, 114.0))
    x, y = linepos.point_at(ROUTE, (92.0 + 50.0) / LENGTH)  # round the first corner
    assert (round(x, 6), round(y, 6)) == (362.0, 164.0)
    assert linepos.point_at(ROUTE, (92.0 + 98.5 + 8.0) / LENGTH) == pytest.approx((370.0, 212.5))
    # outside 0..1 the ends hold
    assert linepos.point_at(ROUTE, -3.0) == (270.0, 114.0)
    assert linepos.point_at(ROUTE, 7.0) == (470.0, 212.5)
    assert linepos.point_at([(5.0, 6.0)], 0.5) == (5.0, 6.0)
    assert linepos.point_at([], 0.5) == (0.0, 0.0)


def test_every_point_of_the_line_goes_there_and_back() -> None:
    for k in range(0, 101):
        t = k / 100
        p = linepos.point_at(ROUTE, t)
        back, foot, away = linepos.project(ROUTE, p)
        assert back == pytest.approx(t, abs=1e-9)
        assert foot == pytest.approx(p) and away == pytest.approx(0.0, abs=1e-9)


def test_the_nearest_point_of_the_line_is_found_on_a_piece_and_at_a_corner() -> None:
    t, foot, away = linepos.project(ROUTE, (300.0, 80.0))  # above the first piece
    assert foot == (300.0, 114.0) and away == 34.0 and t == pytest.approx(30.0 / LENGTH)
    t, foot, away = linepos.project(ROUTE, (400.0, 160.0))  # right of the vertical piece
    assert foot == (362.0, 160.0) and away == 38.0
    assert t == pytest.approx((92.0 + 46.0) / LENGTH)
    # outside the corner: the corner itself is the nearest point
    t, foot, away = linepos.project(ROUTE, (380.0, 100.0))
    assert foot == (362.0, 114.0) and away == pytest.approx(math.hypot(18.0, 14.0))
    assert t == pytest.approx(92.0 / LENGTH)
    # far beyond either end: the end
    assert linepos.project(ROUTE, (-500.0, -500.0))[0] == 0.0
    assert linepos.project(ROUTE, (5000.0, 5000.0))[0] == 1.0


def test_a_line_that_doubles_back_gives_the_nearest_piece_and_a_tie_the_earlier_one() -> None:
    u = [(0.0, 0.0), (100.0, 0.0), (100.0, 20.0), (0.0, 20.0)]
    assert linepos.project(u, (50.0, 4.0))[1] == (50.0, 0.0)
    assert linepos.project(u, (50.0, 16.0))[1] == (50.0, 20.0)
    assert linepos.project(u, (50.0, 10.0))[1] == (50.0, 0.0)  # (equally near: the earlier)


def test_a_line_with_no_length_is_its_first_point() -> None:
    dot = [(4.0, 4.0), (4.0, 4.0)]
    t, foot, away = linepos.project(dot, (9.0, 9.0))
    assert (t, foot) == (0.0, (4.0, 4.0)) and away == pytest.approx(math.hypot(5, 5))
    assert linepos.project([], (1.0, 1.0))[0] == 0.0
    assert linepos.slide(dot, (9.0, 9.0), 0.0, 5.0) == 0.0
    assert linepos.clamp_t(dot, 0.7, 5.0) == 0.0


def test_a_label_is_kept_inside_the_line_by_its_half_width() -> None:
    m = 30.0
    assert linepos.clamp_t(ROUTE, 0.0, m) == pytest.approx(m / LENGTH)
    assert linepos.clamp_t(ROUTE, 1.0, m) == pytest.approx(1 - m / LENGTH)
    assert linepos.clamp_t(ROUTE, 0.5, m) == 0.5
    assert linepos.clamp_t(ROUTE, -4.0, m) == pytest.approx(m / LENGTH)  # (a stored t is 0..1)
    x, y = linepos.place(ROUTE, 0.0, m)
    assert (x, y) == (300.0, 114.0)


def test_a_line_that_gets_shorter_holds_the_label_in_its_middle_and_gives_it_back() -> None:
    short = [(0.0, 0.0), (40.0, 0.0)]
    assert linepos.clamp_t(short, 0.1, 30.0) == 0.5  # 40 < 2 x 30: the middle
    assert linepos.place(short, 0.9, 30.0) == (20.0, 0.0)
    assert linepos.clamp_t(short, 0.1, 20.0) == 0.5  # exactly two margins: the middle too
    # a stored t is not changed by drawing: the longer line gives the label its place back
    t = 0.8
    assert linepos.place([(0.0, 0.0), (400.0, 0.0)], t, 30.0) == (320.0, 0.0)
    assert linepos.place(short, t, 30.0) == (20.0, 0.0)
    assert linepos.place([(0.0, 0.0), (400.0, 0.0)], t, 30.0) == (320.0, 0.0)


def test_a_label_keeps_its_relative_place_when_the_line_changes() -> None:
    t = 0.25
    before = linepos.point_at(ROUTE, t)
    moved = [(270.0, 114.0), (400.0, 114.0), (400.0, 300.0), (600.0, 300.0)]  # a device moved
    after = linepos.point_at(moved, t)
    assert after != before
    on_line = linepos.project(moved, after)
    assert on_line[2] == pytest.approx(0.0, abs=1e-9)  # (still on the new line)
    assert on_line[0] == pytest.approx(t)  # (at the same fraction of it)


def test_dragging_follows_the_projection_of_the_pointer_and_never_leaves_the_line() -> None:
    m = 15.0
    far = (300.0, -4000.0)  # the pointer is far above the line
    t = linepos.slide(ROUTE, far, 0.0, m)
    x, y = linepos.point_at(ROUTE, t)
    assert (x, y) == pytest.approx((300.0, 114.0), abs=0.05)  # (t is stored to four decimals)
    assert linepos.project(ROUTE, (x, y))[2] == pytest.approx(0.0, abs=0.05)
    # round the corner the label follows the vertical piece
    x, y = linepos.point_at(ROUTE, linepos.slide(ROUTE, (900.0, 150.0), 0.0, m))
    assert x == pytest.approx(362.0, abs=0.05) or y == pytest.approx(212.5, abs=0.05)
    x, y = linepos.point_at(ROUTE, linepos.slide(ROUTE, (380.0, 150.0), 0.0, m))
    assert (x, y) == pytest.approx((362.0, 150.0), abs=0.05)
    # clamped to the path at both ends, however far the pointer is
    assert linepos.slide(ROUTE, (-9e4, 0.0), 0.0, m) == pytest.approx(m / LENGTH, abs=1e-4)
    assert linepos.slide(ROUTE, (9e4, 9e4), 0.0, m) == pytest.approx(1 - m / LENGTH, abs=1e-4)


def test_a_label_taken_by_its_edge_does_not_jump_to_the_pointer() -> None:
    centre, pointer = (316.0, 114.0), (330.0, 120.0)  # taken 14 along the line from its centre
    grab = linepos.grab_offset(ROUTE, pointer, centre)
    assert grab == pytest.approx(-14.0)
    assert linepos.slide(ROUTE, pointer, grab, 15.0) == pytest.approx(46.0 / LENGTH, abs=1e-4)
    t = linepos.slide(ROUTE, (350.0, 90.0), grab, 15.0)  # moves by what the pointer moved
    assert linepos.point_at(ROUTE, t) == pytest.approx((336.0, 114.0), abs=0.05)


def test_a_mark_of_an_earlier_version_is_read_as_the_nearest_point_of_the_line() -> None:
    auto = (316.0, 114.0)  # the automatic place: on the first piece
    # the label was dragged 50 right and 40 up: that is above the line, near x = 366
    t = linepos.from_offset(ROUTE, auto, 50.0, -40.0)
    x, y = linepos.point_at(ROUTE, t)
    assert linepos.project(ROUTE, (x, y))[2] == pytest.approx(0.0, abs=0.05)
    assert (x, y) == pytest.approx((362.0, 114.0), abs=0.05)  # (the corner: nearest to (366, 74))
    # an offset along the line alone gives that point
    t = linepos.from_offset(ROUTE, auto, 30.0, 0.0)
    assert linepos.point_at(ROUTE, t) == pytest.approx((346.0, 114.0), abs=0.05)
    # no offset: where it was
    assert linepos.point_at(ROUTE, linepos.from_offset(ROUTE, auto, 0.0, 0.0)) == pytest.approx(
        auto, abs=0.05
    )
    # a huge offset ends at the end of the line
    assert linepos.from_offset(ROUTE, auto, 90000.0, 90000.0) == 1.0
    assert linepos.from_offset(ROUTE, auto, -90000.0, 0.0) == 0.0


def test_the_direction_of_the_line_where_the_label_is() -> None:
    assert linepos.direction_at(ROUTE, 0.1) == linepos.HORIZONTAL
    assert linepos.direction_at(ROUTE, (92.0 + 40.0) / LENGTH) == linepos.VERTICAL
    assert linepos.direction_at(ROUTE, 0.9) == linepos.HORIZONTAL
    assert linepos.direction_at(ROUTE, 92.0 / LENGTH) == linepos.CORNER
    assert linepos.direction_at([(0.0, 0.0), (10.0, 10.0)], 0.5) == linepos.SLANTED
    assert linepos.direction_at([], 0.5) == linepos.HORIZONTAL
    # (a label kept inside the line is looked at where it is drawn)
    assert linepos.direction_at(ROUTE, 0.0, 30.0) == linepos.HORIZONTAL


def test_the_marks_that_are_a_place_on_a_line_and_those_that_are_an_offset() -> None:
    for mark in ("interface:IF-1", "link:L1", "end:L1:0", "end:L1:1"):
        assert mark_is_along(mark)
    for mark in ("bend:L1", "route:IF-1", "later:kind", "nothing"):
        assert not mark_is_along(mark)
