# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,union-attr,arg-type,index,type-arg,attr-defined"
"""REQ-GUI-22 (the looks in the written and exported block diagram). Owner decision after the
device looks: *should the exported and written diagram show these looks too? yes, without
breaking anything*. The block diagram (`system/block_diagram.svg` and `.pdf` of every export, and
Export diagram's SVG, PDF and PNG) draws each device card with a band in the colour of its family
and a badge with the pictogram of its kind in the shape of its family, in the light theme's
colours, and a key to the kinds. The looks come from the model alone (name, ID, subsystem, links
and the kind set by hand) and are written with fixed decimals, so the same design gives the same
bytes everywhere. The harness overview and every other written file are as they were."""

import math
import re
from pathlib import Path

import pytest

from harness_design_studio.core import device_kinds as dk
from harness_design_studio.core import pictograms, templates
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.model import Unit, evolve
from harness_design_studio.core.outputs import looks, system
from harness_design_studio.core.outputs.build import build_outputs, write_outputs
from harness_design_studio.core.outputs.canvas import (
    Rect,
    Shape,
    Text,
    fit_sheet,
    item_bounds,
    path_data,
    to_pdf,
    to_svg,
)
from harness_design_studio.core.outputs.stamp import stamp_of
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3, sat15
from harness_design_studio.gui.theme.tokens import LIGHT


def sheet_of(project):
    return system.block_diagram(project, stamp_of(project))


def key_labels(sheet) -> list[str]:
    """The words of the key to the kinds (right of the key to the lines, in its text size)."""
    return [
        it.s
        for it in sheet.items
        if isinstance(it, Text) and it.x >= system.KEY_X and it.size == looks.KEY_TEXT
    ]


def flatsat(tmp_path: Path):
    templates.create_project(tmp_path / "f", "flatsat")
    return load_project(tmp_path / "f").project


def card_items(sheet, project, uid: str):
    """The shapes drawn on one card, with their place relative to its top left corner."""
    pos, _w, _h = system._layout(project)
    x, y = pos[uid]
    got = []
    for it in sheet.items:
        if isinstance(it, Shape):
            left, top, right, bottom = item_bounds(it)
            if (
                x - 0.5 <= left
                and right <= x + system.BOX_W + 0.5
                and y - 0.5 <= top <= y + system.BOX_H
            ):
                got.append(it)
    return x, y, got


def moved(shapes, x: float, y: float):
    """The shapes with their place taken from the card's corner: (fill, stroke, width, numbers).
    Numbers are written rounded to three decimals at two places, so two cards of one look agree
    to within a thousandth (`alike`)."""
    return [
        (
            s.fill,
            s.stroke,
            s.width,
            [
                (op, tuple(v - (x if k % 2 == 0 else y) for k, v in enumerate(pts)))
                for op, pts in s.path
            ],
        )
        for s in shapes
    ]


def alike(a, b) -> bool:
    if len(a) != len(b):
        return False
    for (f1, s1, w1, p1), (f2, s2, w2, p2) in zip(a, b, strict=True):
        if (f1, s1) != (f2, s2) or abs(w1 - w2) > 0.002 or len(p1) != len(p2):
            return False
        for (o1, n1), (o2, n2) in zip(p1, p2, strict=True):
            if (
                o1 != o2
                or len(n1) != len(n2)
                or any(abs(u - v) > 0.002 for u, v in zip(n1, n2, strict=True))
            ):
                return False
    return True


# ---- what the card shows -------------------------------------------------------------------------


def test_each_card_has_a_band_and_a_badge_of_its_kind(tmp_path) -> None:
    p = flatsat(tmp_path)
    sheet = sheet_of(p)
    for uid in p.units:
        looks_of = dk.looks_for(p, uid)
        _x, _y, shapes = card_items(sheet, p, uid)
        accent = looks.accent_of(looks_of)
        if accent is None:
            assert len(shapes) == 2 and shapes[0].fill == looks.LIGHT.plain_ground, uid
            continue
        assert len(shapes) == 3, uid  # the band, the badge and the pictogram
        band, badge, picture = shapes
        assert band.fill == badge.fill == accent and band.stroke is None
        assert picture.stroke == looks.LIGHT.ink and picture.fill in (None, looks.LIGHT.ink)
        assert (picture.fill is not None) == (looks_of.kind.key in pictograms.FILLED)


def test_the_colours_are_the_light_values_of_the_tokens_the_window_uses() -> None:
    for family, (light, _dark) in dk.ACCENTS.items():
        assert LIGHT[f"device.{family}"] == light  # the window's token is made from the same table
        assert looks.LIGHT.accents[family] == light.lower()
    assert looks.LIGHT.ink == LIGHT["accent.text"].lower()
    assert looks.LIGHT.plain_ink == LIGHT["text.muted"].lower()
    assert looks.LIGHT.plain_ground == LIGHT["bg.hover"].lower()


def test_the_window_and_the_file_draw_the_same_pictograms() -> None:
    pytest.importorskip("PySide6")
    from harness_design_studio.gui import device_looks as dl

    assert set(dl.PICTOGRAMS) == set(pictograms.PICTOGRAMS) == set(dk.KIND)
    for key, path in pictograms.PICTOGRAMS.items():
        q = dl.PICTOGRAMS[key]
        ops = [q.elementAt(i).type for i in range(q.elementCount())]
        moves = sum(op == "M" for op, _ in path)
        assert sum(t.name == "MoveToElement" for t in ops) == moves, key  # the same subpaths
        r = q.boundingRect()
        xs = [v for _op, pts in path for v in pts[0::2]]
        assert abs(r.left() - min(xs)) < 1.0 and abs(r.right() - max(xs)) < 1.0, key


def test_two_devices_of_one_kind_look_alike_and_two_of_different_kinds_do_not(tmp_path) -> None:
    p = flatsat(tmp_path)
    sheet = sheet_of(p)
    a, b = (moved(card_items(sheet, p, u)[2], *card_items(sheet, p, u)[:2]) for u in ("RW1", "RW2"))
    assert alike(a, b)
    c = moved(card_items(sheet, p, "BAT1")[2], *card_items(sheet, p, "BAT1")[:2])
    d = moved(card_items(sheet, p, "OBC1")[2], *card_items(sheet, p, "OBC1")[:2])
    assert not alike(c, d) and not alike(a, c)


def test_a_kind_set_by_hand_wins_in_the_file(tmp_path) -> None:
    p = flatsat(tmp_path)
    before = moved(card_items(sheet_of(p), p, "RW1")[2], *card_items(sheet_of(p), p, "RW1")[:2])
    p.units["RW1"] = evolve(p.units["RW1"], kind="battery")
    sheet = sheet_of(p)
    x, y, shapes = card_items(sheet, p, "RW1")
    assert shapes[0].fill == looks.LIGHT.accents["power"]  # the colour of a battery's family
    bat = card_items(sheet, p, "BAT1")
    assert alike(moved(shapes, x, y), moved(bat[2], bat[0], bat[1]))  # the very look of a battery
    assert not alike(moved(shapes, x, y), before)
    p.units["RW1"] = evolve(p.units["RW1"], kind="device")  # the plain box can be forced
    shapes = card_items(sheet_of(p), p, "RW1")[2]
    assert len(shapes) == 2 and shapes[0].fill == looks.LIGHT.plain_ground


def test_the_looks_come_from_the_model_alone(tmp_path) -> None:
    """Not from the window: the same bytes whatever else exists in memory, and no theme, zoom or
    mark enters (the function takes only the project and its stamp)."""
    p = flatsat(tmp_path)
    first = to_svg(sheet_of(p), "m")
    from harness_design_studio.core.model import DiagramMark

    p.diagram_marks["end:L1:0"] = DiagramMark(id="end:L1:0", t=0.3)
    assert to_svg(sheet_of(p), "m") == first
    import inspect

    assert list(inspect.signature(system.block_diagram).parameters) == ["project", "stamp"]


# ---- the files -------------------------------------------------------------------------------------


def test_the_svg_and_the_pdf_are_the_same_bytes_every_time(tmp_path) -> None:
    p = flatsat(tmp_path)
    a, b = build_outputs(p).files, build_outputs(p).files
    for name in ("system/block_diagram.svg", "system/block_diagram.pdf"):
        assert a[name] == b[name] and len(a[name]) > 1000
    svg = a["system/block_diagram.svg"].decode()
    assert svg.count("<path ") > 3 * len(p.units)  # a band, a badge and a pictogram for each
    assert b"1 J 1 j" in a["system/block_diagram.pdf"]  # the strokes of the pictograms are round


def test_every_number_is_written_with_fixed_decimals_and_no_locale(tmp_path) -> None:
    svg = build_outputs(flatsat(tmp_path)).files["system/block_diagram.svg"].decode()
    for d in re.findall(r' d="([^"]*)"', svg):
        assert re.fullmatch(r"[MLCZ0-9 .\-]+", d), d  # no exponent, no comma, no other letter
        for num in re.findall(r"-?[0-9]+(?:\.[0-9]+)?", d):
            assert len(num.partition(".")[2]) <= 3 and num not in ("-0", "-0.0")
    assert "e+" not in svg and "e-" not in svg.replace("stroke-", "").replace("line", "")


def test_a_platform_whose_sine_differs_in_the_last_digit_writes_the_same_file(monkeypatch) -> None:
    """Windows' libm may give a cosine one binary digit away from Linux's. The geometry is
    rounded when it is made, so the path data does not change."""
    want = pictograms.PICTOGRAMS
    real_cos, real_sin = math.cos, math.sin
    monkeypatch.setattr(math, "cos", lambda v: real_cos(v) * (1 + 3e-16))
    monkeypatch.setattr(math, "sin", lambda v: real_sin(v) * (1 - 3e-16) + 1e-17)
    assert pictograms._build() == want
    for shape in pictograms.SHAPES:
        assert pictograms.shape_path(shape, 1.0, 2.0, 7.0, 7.0) is not None
    sample = pictograms.shape_path("hexagon", 1.0, 2.0, 7.0, 7.0)
    monkeypatch.undo()
    assert pictograms.shape_path("hexagon", 1.0, 2.0, 7.0, 7.0) == sample


def test_no_coordinate_sits_on_a_rounding_edge(monkeypatch) -> None:
    """The geometry is rounded to four decimals when it is made. A raw number a hair from the
    middle of two four-decimal steps could round either way on two platforms; none is. (A number
    that is already on the four-decimal grid is written the same everywhere: it is one double.)"""
    raw: list[float] = []

    def record(v: float) -> float:
        raw.append(v)
        return round(v, pictograms.DECIMALS)

    monkeypatch.setattr(pictograms, "_r", record)
    pictograms._build()
    for shape in pictograms.SHAPES:
        pictograms.shape_path(shape, 0.0, 0.0, looks.BADGE, looks.BADGE)
        pictograms.shape_path(shape, 0.0, 0.0, looks.KEY_BADGE, looks.KEY_BADGE)
    assert len(raw) > 1000
    step = 10**pictograms.DECIMALS
    for v in raw:
        assert abs(v * step % 1 - 0.5) > 1e-6, v


def test_the_path_data_is_plain_text() -> None:
    d = path_data(
        (("M", (1.0, 2.0)), ("L", (3.25, 4.0)), ("C", (1, 2, 3, 4, 5, 6.123456)), ("Z", ()))
    )
    assert d == "M 1 2 L 3.25 4 C 1 2 3 4 5 6.123 Z"


def test_the_key_lists_the_kinds_the_project_has_with_their_pictograms(tmp_path) -> None:
    p = flatsat(tmp_path)
    sheet = sheet_of(p)
    labels = key_labels(sheet)
    used = dk.used_kinds(p)
    assert labels == [dk.KIND[k].label for k in used] and len(used) == 14
    pos, _w, _h = system._layout(p)
    below = max(y for _x, y in pos.values()) + system.BOX_H  # the key is under the last card
    keys = [it for it in sheet.items if isinstance(it, Shape) and item_bounds(it)[1] > below]
    assert len(keys) == 2 * len(used)  # a badge and its picture for each, no band
    sat = sheet_of(sat15())
    assert any(isinstance(it, Text) and it.s == "Battery" for it in sat.items)


def test_a_project_of_plain_boxes_has_no_key_for_kinds() -> None:
    p = mini3()
    p.units = {f"Z{k}": Unit(id=f"Z{k}", name="Box", subsystem="zzz") for k in range(3)}
    p.interfaces.clear()
    p.links.clear()
    p.placements.clear()
    sheet = sheet_of(p)
    assert key_labels(sheet) == []
    shapes = [it for it in sheet.items if isinstance(it, Shape)]
    assert len(shapes) == 2 * 3  # a plain badge and its picture on each card, no band


def test_a_long_name_stays_inside_its_card_and_clear_of_the_badge() -> None:
    p = mini3()
    p.units["RW1"] = evolve(
        p.units["RW1"], name="A reaction wheel with a very long name indeed, over any width"
    )
    sheet = sheet_of(p)
    pos, _w, _h = system._layout(p)
    x, y = pos["RW1"]
    texts = [
        it for it in sheet.items
        if isinstance(it, Text) and y < it.y < y + system.BOX_H and x < it.x < x + system.BOX_W
    ]  # fmt: skip
    assert [t.s for t in texts][0] == "RW1" and len(texts) == 2
    for t in texts:
        assert t.left >= x + looks.TEXT_X - 1e-6  # clear of the band and the badge
        assert t.left + len(t.s) * t.size * 0.6 <= x + system.BOX_W + 1e-6  # inside the card
    assert texts[1].s.endswith("~") and len(texts[1].s) < len(p.units["RW1"].name)  # a name is cut


def test_an_id_is_shrunk_and_never_cut() -> None:
    p = mini3()
    uid = "X" * 22  # longer than the room beside the badge at the usual size
    p.units[uid] = Unit(id=uid, name="Long", subsystem="x")
    sheet = sheet_of(p)
    texts = [it for it in sheet.items if isinstance(it, Text) and it.s == uid]
    assert len(texts) == 1 and texts[0].size < system.ID_SIZE and texts[0].size >= system.ID_FLOOR
    room = system.BOX_W - looks.TEXT_X - system.CARD_PAD
    assert len(uid) * texts[0].size * 0.6 <= room + 1e-6


def test_the_page_still_fits_with_the_band_the_badge_and_the_key(tmp_path) -> None:
    p = flatsat(tmp_path)
    sheet = sheet_of(p)
    assert (sheet.width, sheet.height) == (420.0, 297.0)  # the sheet is the size it was
    for it in sheet.items:
        left, top, right, bottom = item_bounds(it)
        assert left >= 0 and right <= sheet.width and top >= 0 and bottom <= sheet.height
    cut = fit_sheet(sheet, 8.0)
    assert cut.width <= sheet.width and cut.height <= sheet.height
    for it in cut.items:
        assert item_bounds(it)[2] <= cut.width and item_bounds(it)[3] <= cut.height
    assert any(isinstance(it, Rect) for it in cut.items)  # the border is redrawn to match


def test_the_key_of_twenty_kinds_makes_columns_and_stays_on_the_sheet() -> None:
    p = mini3()
    p.interfaces.clear()
    p.links.clear()
    p.units.clear()
    p.connectors.clear()
    p.placements.clear()
    p.harnesses.clear()
    for k, kind in enumerate(dk.KIND_IDS):
        p.units[f"U{k}"] = Unit(id=f"U{k}", name=f"Box {k}", subsystem="zzz", kind=kind)
    sheet = sheet_of(p)
    labels = key_labels(sheet)
    assert labels == [dk.KIND[k].label for k in dk.KIND_IDS]
    for it in sheet.items:
        assert item_bounds(it)[2] <= sheet.width and item_bounds(it)[3] <= sheet.height


# ---- nothing else changes ---------------------------------------------------------------------------


def test_the_harness_overview_has_no_looks() -> None:
    p = mini3()
    over = system.harness_overview(p, stamp_of(p))
    assert not [it for it in over.items if isinstance(it, Shape)]
    assert "<path" not in to_svg(over, "m").decode()


def test_the_pdf_has_the_same_texts_as_the_svg_and_the_verifier_passes(tmp_path) -> None:
    from harness_design_studio.core.generate.engine import generate_project

    p = sat15()
    generate_project(p)
    result = write_outputs(p, tmp_path / "out")
    report = verify_outputs(p, result.files)
    assert report.errors == [], [e.message for e in report.errors]
    svg = (tmp_path / "out" / "system" / "block_diagram.svg").read_text(encoding="utf-8")
    assert "<path " in svg


def test_the_verifier_still_finds_a_missing_device_in_the_new_diagram() -> None:
    p = mini3()
    files = dict(build_outputs(p).files)
    files["system/block_diagram.svg"] = files["system/block_diagram.svg"].replace(b">OBC<", b">OB<")
    report = verify_outputs(p, files)
    assert any(e.code == "out_diagram" for e in report.errors)


def test_the_pdf_page_draws_filled_and_stroked_shapes() -> None:
    p = mini3()
    sheet = sheet_of(p)
    pdf = to_pdf([sheet], sheet.title, "m")
    assert pdf.count(b" B Q") >= 1 or pdf.count(b" f Q") >= 1  # filled badges
    assert b" S Q" in pdf and b" h " in pdf  # stroked pictograms, closed paths


# ---- the exported picture ---------------------------------------------------------------------------


def test_the_exported_png_paints_the_looks(qtbot) -> None:
    pytest.importorskip("PySide6")
    from PySide6.QtGui import QColor, QImage

    from harness_design_studio.gui import diagram_export as de

    p = mini3()
    sheet = de.diagram_sheet(p)
    png = de.render_png(sheet)
    image = QImage.fromData(png)
    assert not image.isNull()
    scale = image.width() / sheet.width
    pos, _w, _h = system._layout(p)
    x, y = pos["OBC"]  # a computer: the colour of the control family, in the band
    px = image.pixelColor(round((x + 1.0) * scale), round((y + system.BOX_H / 2) * scale))
    want = QColor(looks.LIGHT.accents["control"])
    assert (
        abs(px.red() - want.red()) + abs(px.green() - want.green()) + abs(px.blue() - want.blue())
        < 40
    )
    svg = to_svg(sheet, "m")
    assert svg == to_svg(de.diagram_sheet(p), "m")  # the same sheet gives the same file
