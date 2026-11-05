# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-20. Owner feedback: *it would help if you could make different devices visually/
graphically more distinguishable*. A device card looks like the kind of equipment it is: a
pictogram in a badge whose colour and shape belong to its family, a band of that colour on the
card's left edge, a tinted box when the diagram is seen from far away. The kind is read from the
device's name, ID, subsystem and links with one table (`gui/device_kinds.py`); nothing is stored,
so the project files, the model hash and every written output are as they were. Colour is never the
only cue: the pictogram and the shape say the same, and the tooltip, the inspector and the legend
say it in words."""

import itertools
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QStyleOptionGraphicsItem  # noqa: E402

from harness_design_studio.core import describe, edit, templates  # noqa: E402
from harness_design_studio.core.io import layout  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.core.samples import mini3  # noqa: E402
from harness_design_studio.gui import device_kinds as dk  # noqa: E402
from harness_design_studio.gui import device_looks as dl  # noqa: E402
from harness_design_studio.gui.canvas import W  # noqa: E402
from harness_design_studio.gui.theme.tokens import DARK, LIGHT  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402

THEMES = {"light": LIGHT, "dark": DARK}


class Palette:
    """The colours of one theme, the way the painters ask for them (no window, no display)."""

    def __init__(self, tokens: dict[str, str]) -> None:
        self.tokens = tokens

    def color(self, token: str) -> QColor:
        return QColor(self.tokens[token])


def looks(kind: str) -> dk.Looks:
    return dk.Looks(dk.KIND[kind], "name", "")


# ---- the table ---------------------------------------------------------------------------------


def test_the_table_is_complete_and_has_no_duplicates() -> None:
    keys = [k.key for k in dk.KINDS]
    assert len(set(keys)) == len(keys) and "device" not in keys
    assert len({k.label for k in (*dk.KINDS, dk.GENERIC)}) == len(keys) + 1
    assert {f.key for f in dk.FAMILIES} == {k.family for k in (*dk.KINDS, dk.GENERIC)}
    assert set(dl.PICTOGRAMS) == set(dk.KIND)  # a pictogram for every kind, and no stray one
    assert all(f.shape in dk.SHAPES for f in dk.FAMILIES)
    assert [f.key for f in dk.FAMILIES if not f.token] == ["other"]  # only the plain box has none
    for fam in dk.FAMILIES:
        assert not fam.token or (fam.token in LIGHT and fam.token in DARK)


TEMPLATE_KINDS = {
    "computer": "computer", "power": "power_unit", "actuator": "reaction_wheel",
    "sensor": "star_tracker", "payload": "payload", "transceiver": "transceiver", "pyro": "pyro",
    "computer_xl": "computer", "pdu": "power_unit", "battery": "battery",
    "solar_array": "solar_array", "sun_sensor": "sun_sensor", "magnetorquer": "magnetorquer",
    "heater_panel": "heater",
}  # fmt: skip


def test_the_templates_of_the_add_device_menu_are_all_covered() -> None:
    assert set(edit.TEMPLATES) == set(TEMPLATE_KINDS)


@pytest.mark.parametrize(("template", "kind"), sorted(TEMPLATE_KINDS.items()))
def test_every_device_the_add_device_menu_makes_gets_its_kind(template: str, kind: str) -> None:
    t = edit.TEMPLATES[template]
    got = dk.looks_of(f"{t.prefix}1", f"{t.label} 1", t.subsystem)
    assert (got.kind.key, got.source) == (kind, "name")
    # ... and from the ID alone, when somebody has renamed the device
    by_id = dk.looks_of(f"{t.prefix}1", "Box 7", "zzz")
    assert (by_id.kind.key, by_id.source) == (kind, "id")


FLATSAT = {
    "MTQ1": "magnetorquer", "RW1": "reaction_wheel", "RW2": "reaction_wheel",
    "RW3": "reaction_wheel", "RW4": "reaction_wheel", "SS1": "sun_sensor", "SS2": "sun_sensor",
    "ST1": "star_tracker", "ST2": "star_tracker", "OBC1": "computer", "RIU1": "interface_unit",
    "TRX1": "transceiver", "GPSU1": "ground_support", "RFSU1": "ground_support",
    "SCOE1": "ground_support", "PYRO1": "pyro", "PL1": "payload", "BAT1": "battery",
    "PCDU1": "power_unit", "PDU2": "power_unit", "SA1": "solar_array", "HTR1": "heater",
    "HTR2": "heater",
}  # fmt: skip
SMALL = {
    "MTQ1": "magnetorquer", "RW1": "reaction_wheel", "RW2": "reaction_wheel",
    "SS1": "sun_sensor", "ST1": "star_tracker", "OBC1": "computer", "OBC1-R": "computer",
    "TRX1": "transceiver", "PL1": "payload", "BAT1": "battery", "PCDU1": "power_unit",
    "PCDU1-R": "power_unit", "SA1": "solar_array", "HTR1": "heater",
}  # fmt: skip
MINIMAL = {
    "RW1": "reaction_wheel", "SS1": "sun_sensor", "OBC1": "computer", "TRX1": "transceiver",
    "BAT1": "battery", "PCDU1": "power_unit", "SA1": "solar_array",
}  # fmt: skip
FIRST = {"RW1": "reaction_wheel", "OBC1": "computer", "PCDU1": "power_unit"}


@pytest.mark.parametrize(
    ("example", "expected"),
    [("flatsat", FLATSAT), ("small-satellite", SMALL), ("minimal-satellite", MINIMAL),
     ("first-steps", FIRST)],
)  # fmt: skip
def test_each_example_project_gets_the_expected_kinds(tmp_path: Path, example, expected) -> None:
    templates.create_project(tmp_path / example, example)
    project = load_project(tmp_path / example).project
    cats = describe.unit_categories(project)
    got = {}
    for u in project.units.values():
        lk = dk.looks_of(u.id, u.name, u.subsystem, describe.unit_glyph(project, u.id, cats))
        got[u.id] = lk.kind.key
        assert lk.source == "name", (u.id, lk)  # the examples never need the weaker clues
    assert got == expected


def test_the_flatsat_example_shows_many_kinds_in_few_families() -> None:
    kinds = set(FLATSAT.values())
    assert len(kinds) == 14
    assert len({dk.KIND[k].family for k in kinds}) == 9


def test_a_word_is_a_word_not_a_piece_of_one() -> None:
    assert dk.looks_of("SA1", "Solar array simulator", "power").kind.key == "solar_array"
    assert dk.looks_of("X1", "Pulse simulator", "x").generic  # `imu` hides in `simulator`
    assert dk.looks_of("X2", "Starter motor kit", "x").kind.key == "mechanism"  # not a star
    assert dk.looks_of("X3", "Wheels", "x").kind.key == "reaction_wheel"  # an ending, long keyword
    assert dk.looks_of("X4", "Obc1 board", "x").kind.key == "computer"  # the keyword and digits
    assert dk.looks_of("X5", "Ground power supply", "x").kind.key == "ground_support"
    assert dk.looks_of("X6", "Sensor (star tracker) 1", "x").kind.key == "star_tracker"
    assert dk.words_of("On-board computer (2)") == ["on", "board", "computer", "2"]
    assert dk.id_letters("PCDU1-R") == "pcdu" and dk.id_letters("1A") == ""


def test_the_clues_are_tried_in_the_order_name_id_subsystem_links() -> None:
    assert dk.looks_of("BAT1", "Heater", "power", "computer").kind.key == "heater"  # the name wins
    by_id = dk.looks_of("BAT1", "Unit 7", "thermal", "computer")
    assert (by_id.kind.key, by_id.source) == ("battery", "id")
    by_sub = dk.looks_of("Z9", "Unit 7", "thermal control", "computer")
    assert (by_sub.kind.key, by_sub.source, by_sub.clue) == ("heater", "subsystem", "thermal")
    by_links = dk.looks_of("Z9", "Unit 7", "zzz", "computer")
    assert (by_links.kind.key, by_links.source) == ("computer", "links")


def test_an_unknown_device_keeps_the_plain_box() -> None:
    plain = dk.looks_of("Z9", "Unit 7", "zzz")
    assert plain.generic and plain.source == "none" and plain.token == ""
    assert dk.looks_of("Z9", "Unit 7", "zzz", "unit").generic
    assert dk.looks_of("", "", "").generic


def test_the_sentence_names_the_kind_and_where_it_comes_from() -> None:
    s = dk.sentence(dk.looks_of("BAT1", "Battery 1", "power"), "Battery 1", "BAT1")
    assert s == "Looks like: Battery (from the name Battery 1)"
    s = dk.sentence(dk.looks_of("BAT1", "Unit", "x"), "Unit", "BAT1")
    assert s == "Looks like: Battery (from the ID BAT1)"
    s = dk.sentence(dk.looks_of("Z", "Unit", "comms"), "Unit", "Z")
    assert s == "Looks like: Transceiver (from the subsystem comms)"
    s = dk.sentence(dk.looks_of("Z", "Unit", "x", "power"), "Unit", "Z")
    assert s == "Looks like: Power distribution (from the links it carries)"
    assert dk.sentence(dk.looks_of("Z", "Unit", "x"), "Unit", "Z").startswith(
        "Looks like: Device ("
    )


# ---- the pictograms and the badges ----------------------------------------------------------------


def ink_image(kind: str, ink: QColor, side: int = 32) -> QImage:
    img = QImage(side, side, QImage.Format.Format_ARGB32)
    img.fill(QColor(0, 0, 0, 0))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    dl.draw_pictogram(p, kind, QRectF(2, 2, side - 4, side - 4), ink)
    p.end()
    return img


def covered(img: QImage, floor: int = 100) -> set[tuple[int, int]]:
    return {
        (x, y)
        for x in range(img.width())
        for y in range(img.height())
        if img.pixelColor(x, y).alpha() >= floor
    }


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("kind", sorted(dk.KIND))
def test_every_pictogram_paints_ink_in_light_and_dark(kind: str, theme: str) -> None:
    ink = QColor(THEMES[theme]["text.primary"])
    img = ink_image(kind, ink)
    assert len(covered(img)) >= 40, kind
    solid = covered(img, 255)
    assert solid, kind
    c = img.pixelColor(*sorted(solid)[0])
    assert (c.red(), c.green(), c.blue()) == (ink.red(), ink.green(), ink.blue())


def test_no_two_pictograms_are_alike() -> None:
    ink = QColor(LIGHT["text.primary"])
    shapes = {k: covered(ink_image(k, ink)) for k in dk.KIND}
    for a, b in itertools.combinations(sorted(shapes), 2):
        differ = len(shapes[a] ^ shapes[b])
        assert differ >= 60, f"{a} and {b} are drawn too much alike ({differ} pixels differ)"


@pytest.mark.parametrize("theme", THEMES)
def test_a_badge_is_the_accent_with_the_pictogram_in_the_ink_colour(theme: str) -> None:
    pal = Palette(THEMES[theme])
    for kind in dk.KIND:
        lk = looks(kind)
        img = QImage(48, 48, QImage.Format.Format_ARGB32)
        img.fill(pal.color("bg.surface"))
        p = QPainter(img)
        dl.draw_badge(p, pal, lk, QRectF(4, 4, 40, 40))
        p.end()
        accent = pal.color(lk.token) if lk.token else pal.color("text-muted")
        ink = pal.color("accent.text" if lk.token else "text-muted")
        n_accent = sum(1 for x in range(48) for y in range(48) if img.pixelColor(x, y) == accent)
        n_ink = sum(1 for x in range(48) for y in range(48) if img.pixelColor(x, y) == ink)
        assert n_ink >= 20, (theme, kind)
        assert n_accent >= (300 if lk.token else 20), (theme, kind)


def test_the_four_shapes_differ_and_belong_to_families() -> None:
    areas = {}
    for shape in dk.SHAPES:
        path = dl.shape_path(shape, QRectF(0, 0, 40, 40))
        assert not path.isEmpty()
        areas[shape] = round(path.boundingRect().width() * path.boundingRect().height())
    assert len({f.shape for f in dk.FAMILIES}) == 4
    img = {}
    for shape in dk.SHAPES:
        im = QImage(40, 40, QImage.Format.Format_ARGB32)
        im.fill(QColor(0, 0, 0, 0))
        p = QPainter(im)
        p.setBrush(QColor("black"))
        p.drawPath(dl.shape_path(shape, QRectF(1, 1, 38, 38)))
        p.end()
        img[shape] = covered(im)
    for a, b in itertools.combinations(dk.SHAPES, 2):
        assert len(img[a] ^ img[b]) >= 60, (a, b)


# ---- the card, the far-away box, the tooltip, the inspector and the legend ---------------------


@pytest.fixture
def win(qtbot, tmp_path):
    templates.create_project(tmp_path / "flatsat", "flatsat")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    assert w.open_project(tmp_path / "flatsat")
    w.view.fit()
    QApplication.processEvents()
    w.view.grab()
    return w


def render(win, uid: str, *, scale: float = 1.0, dx: float = 30.0, dy: float = 40.0) -> QImage:
    """The real card painted into an image at `scale` (1: all the details; under 0.45: the box)."""
    item = win.view.dscene.unit_items[uid]
    img = QImage(
        int((W + 2 * dx) * scale),
        int((item.height() + 2 * dy) * scale),
        QImage.Format.Format_ARGB32,
    )
    img.fill(win.theme.color("bg"))
    p = QPainter(img)
    p.scale(scale, scale)
    p.translate(dx, dy)
    opt = QStyleOptionGraphicsItem()
    opt.exposedRect = item.boundingRect()
    opt.levelOfDetail = scale
    item.paint(p, opt, None)
    p.end()
    return img


def near(img: QImage, x: float, y: float, colour: QColor, tol: int = 12) -> bool:
    c = QColor(img.pixel(int(x), int(y)))
    return (
        abs(c.red() - colour.red())
        + abs(c.green() - colour.green())
        + abs(c.blue() - colour.blue())
        <= tol
    )


def test_each_card_carries_the_looks_of_its_kind(win) -> None:
    scene = win.view.dscene
    got = {u: scene.unit_items[u].facts().looks.kind.key for u in win.ctl.project.units}
    assert got == FLATSAT


def test_a_card_has_a_band_in_the_accent_of_its_family_and_a_badge(win) -> None:
    for uid, kind in (("BAT1", "battery"), ("OBC1", "computer"), ("RW1", "reaction_wheel")):
        lk = looks(kind)
        accent = win.theme.color(lk.token)
        img = render(win, uid)
        h = win.view.dscene.unit_items[uid].height()
        assert near(img, 30 + 2, 40 + h / 4, accent), (
            uid
        )  # the band, a quarter down (a port may sit half way)
        assert near(img, 30 + 2, 40 + h - 8, accent), uid  # ... down to the foot
        ink = win.theme.color("accent.text")
        n = sum(
            1
            for x in range(30 + 6, 30 + 26)
            for y in range(40 + 5, 40 + 25)
            if near(img, x, y, ink, 30)
        )
        assert n >= 10, uid  # the pictogram is inside the badge


def test_two_cards_of_different_kinds_are_told_apart_by_colour_and_by_picture(win) -> None:
    a, b = render(win, "BAT1"), render(win, "OBC1")
    badge = [(x, y) for x in range(30 + 6, 30 + 26) for y in range(40 + 5, 40 + 25)]
    assert sum(1 for x, y in badge if a.pixel(x, y) != b.pixel(x, y)) >= 80
    c = render(win, "RW2")
    d = render(win, "RW1")  # two wheels look alike, which is right
    assert all(c.pixel(x, y) == d.pixel(x, y) for x, y in badge)


def test_a_device_with_no_clue_keeps_the_plain_box(win) -> None:
    ctl = win.ctl
    uid = ctl.add_device(name="Mystery box", subsystem="zzz")
    QApplication.processEvents()
    item = win.view.dscene.unit_items[uid]
    assert item.facts().looks.generic and item.facts().looks.source == "none"
    img = render(win, uid)
    h = item.height()
    assert not near(img, 30 + 2, 40 + h / 2, win.theme.color("device.power"), 60)  # no band
    muted = win.theme.color("text-muted")
    n = sum(
        1
        for x in range(30 + 6, 30 + 26)
        for y in range(40 + 5, 40 + 25)
        if near(img, x, y, muted, 12)
    )
    assert n >= 10  # the outlined box and its muted picture, as before
    # a renamed battery is read from its subsystem, the only clue that is left
    ctl.rename_unit("BAT1", "ZZ9")
    ctl.update_unit("ZZ9", name="Unit 7")
    QApplication.processEvents()
    lk = win.view.dscene.unit_items["ZZ9"].facts().looks
    assert (lk.kind.key, lk.source, lk.clue) == ("power_unit", "subsystem", "power")


def test_a_box_seen_from_far_away_has_a_band_a_tint_and_a_badge(win) -> None:
    item = win.view.dscene.unit_items["BAT1"]
    accent = win.theme.color(item.facts().looks.token)
    img = render(win, "BAT1", scale=0.4)
    h = item.height()
    assert near(img, (30 + 2) * 0.4, (40 + h / 2) * 0.4, accent, 20)  # the band
    tinted = dl.blend(win.theme.color("surface"), accent, dk.OVERVIEW_TINT)
    assert near(img, (30 + W - 12) * 0.4, (40 + h - 6) * 0.4, tinted, 12)  # the tint of the box
    ink = win.theme.color("accent.text")
    n = sum(1 for x in range(img.width()) for y in range(img.height()) if near(img, x, y, ink, 30))
    assert n >= 8  # the pictogram of the badge


def test_the_far_away_boxes_still_differ_between_kinds(win) -> None:
    a, b = render(win, "BAT1", scale=0.4), render(win, "OBC1", scale=0.4)
    band = (int((30 + 2) * 0.4), int((40 + 10) * 0.4))
    assert a.pixel(*band) != b.pixel(*band)


def test_the_overview_leaves_room_for_the_id(win) -> None:
    item = win.view.dscene.unit_items["PCDU1"]
    img = QImage(10, 10, QImage.Format.Format_ARGB32)
    p = QPainter(img)
    lead = dl.paint_overview(p, win.theme, item.facts().looks, W, item.height(), 0.4)
    tiny = dl.paint_overview(p, win.theme, item.facts().looks, W, item.height(), 0.05)
    p.end()
    assert 10 < lead < W / 2
    assert tiny <= W * 0.2  # a box a dozen pixels wide gets the band and no badge


class _Hover:
    def pos(self) -> QPointF:
        return QPointF(120, 40)

    def screenPos(self):  # pragma: no cover - only asked for when a refusal is shown
        raise AssertionError


def test_the_tooltip_says_the_kind_in_words(win) -> None:
    item = win.view.dscene.unit_items["RW1"]
    win.view.dscene.unit_items["RW1"].facts()
    render(win, "RW1")
    item.hoverMoveEvent(_Hover())
    tip = item.toolTip()
    assert tip.startswith(
        "RW1: Reaction wheel 1\nLooks like: Reaction wheel (from the name Reaction wheel 1)"
    )


def test_the_inspector_says_the_kind_in_words(win) -> None:
    win.ctl.select("unit", "BAT1")
    QApplication.processEvents()
    text = win.props.findChild(QLabel, "unit-looks-text")
    assert text is not None and text.text() == "Looks like: Battery (from the name Battery)"
    row = win.props.findChild(dl.QWidget, "unit-looks")
    assert "Rename the device" in row.toolTip()
    badge = row.findChild(dl.BadgeView)
    assert badge.accessibleName() == "Battery"
    win.ctl.update_unit("BAT1", name="Heater unit")
    QApplication.processEvents()
    text = win.props.findChild(QLabel, "unit-looks-text")
    assert text.text() == "Looks like: Heater and thermal (from the name Heater unit)"
    win.ctl.select("unit", "SS1")
    QApplication.processEvents()
    assert "Sun sensor" in win.props.findChild(QLabel, "unit-looks-text").text()


def test_the_legend_lists_the_kinds_the_diagram_shows(win) -> None:
    entries = [(k, p, t) for k, p, t in win.view.legend.bar._entries() if k == "device"]
    assert [p for _k, p, _t in entries] == [
        k.key for k in dk.KINDS if k.key in set(FLATSAT.values())
    ]
    assert {t for _k, _p, t in entries} >= {
        "Battery",
        "Reaction wheel",
        "Star tracker",
        "Interface unit",
    }


def test_a_project_of_plain_boxes_has_no_device_entries_in_the_legend() -> None:
    from harness_design_studio.core.model import Unit
    from harness_design_studio.gui.legend import LegendBar

    p = mini3()
    p.units = {f"Z{k}": Unit(id=f"Z{k}", name="Box", subsystem="zzz") for k in range(3)}
    assert LegendBar._device_kinds(p) == []
    p.units["B1"] = Unit(id="B1", name="Battery", subsystem="power")
    assert LegendBar._device_kinds(p) == ["battery", "device"]


# ---- nothing written changes --------------------------------------------------------------------


def test_the_kind_is_never_stored(tmp_path: Path) -> None:
    """The look is read, not saved: no field of a device holds it and no file is written for it."""
    from harness_design_studio.core.model import Unit

    assert not {"kind", "looks", "family"} & set(Unit.model_fields)
    templates.create_project(tmp_path / "f", "flatsat")
    project = load_project(tmp_path / "f").project
    assert not [rel for rel in layout.serialize(project) if rel.startswith("diagram/")]
