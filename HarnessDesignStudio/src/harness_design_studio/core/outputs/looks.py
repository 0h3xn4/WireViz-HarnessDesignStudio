"""The looks of a device in the written block diagram: a band down the left edge of the card in
the colour of its family, and a badge with the kind's pictogram in the shape of the family, the
same looks the window gives a card (`gui/device_looks.py`).

The written files are paper, so they use the light theme's colours. Those are the two values of
`device_kinds.ACCENTS` that the window's tokens `device.*` are made from, and the pictograms and
badge outlines are the path data of `core/pictograms.py` that the window paints too, so the file
and the window cannot drift. Everything here comes from the model (name, ID, subsystem, links and
the kind a person set), never from the window, its theme, its zoom or its marks, and every number
is a millimetre written with at most three decimals (`canvas._n`), so equal designs give equal
bytes on every platform.
"""

from dataclasses import dataclass
from typing import Final

from harness_design_studio.core import device_kinds as dk
from harness_design_studio.core import pictograms

from .canvas import Shape

BAND_W: Final = 1.6  # the band on the left edge of a card, mm
BADGE: Final = 7.0  # the side of a badge on a card, mm
BADGE_GAP: Final = 1.4  # between the band and the badge, and between the badge and the text, mm
TEXT_X: Final = (
    BAND_W + 2 * BADGE_GAP + BADGE
)  # where the ID and the name start, from the card edge
INNER: Final = 0.17  # the share of the badge's side left empty round its pictogram
PLAIN_LINE: Final = 0.25  # the outline of the badge of a device that is only a box, mm
KEY_BADGE: Final = 4.0  # the badge of the key (legend), mm
KEY_PITCH: Final = 5.0  # one row of the key, mm (the same as the key of the lines)
KEY_COLUMN: Final = 52.0  # one column of the key, mm
KEY_TEXT: Final = 2.6  # the size of the words of the key, mm (the same as the key of the lines)


@dataclass(frozen=True)
class Palette:
    """The colours a device look is drawn with."""

    accents: dict[str, str]  # family key -> colour
    ink: str  # a pictogram on an accent fill
    plain_ink: str  # the outline and the pictogram of a device that is only a box
    plain_ground: str  # what lies behind it


LIGHT: Final = Palette(
    accents={family: light.lower() for family, (light, _dark) in dk.ACCENTS.items()},
    ink=dk.INK_ON_ACCENT_LIGHT.lower(),
    plain_ink=dk.PLAIN_INK_LIGHT.lower(),
    plain_ground=dk.PLAIN_GROUND_LIGHT.lower(),
)


def accent_of(looks: dk.Looks, palette: Palette = LIGHT) -> str | None:
    """The colour of the device's family, or None for a device that is only a box."""
    return palette.accents.get(looks.family.key)


def band(x: float, y: float, h: float, looks: dk.Looks, palette: Palette = LIGHT) -> list[Shape]:
    """The band of a card at (x, y), `h` high, drawn just inside the card's outline; none for a
    device that is only a box."""
    colour = accent_of(looks, palette)
    if colour is None:
        return []
    inset = 0.2  # (half the line of the card, so the band does not cover it)
    path = pictograms.shape_path("rect", x + inset, y + inset, BAND_W - inset, h - 2 * inset)
    return [Shape(path, fill=colour)]


def badge(
    x: float, y: float, side: float, looks: dk.Looks, palette: Palette = LIGHT
) -> list[Shape]:
    """The badge of a device in the square at (x, y): the family's shape filled with its accent and
    the pictogram of the kind in the ink of an accent fill; a device that is only a box gets an
    outline and a muted pictogram."""
    colour = accent_of(looks, palette)
    outline = pictograms.shape_path(looks.family.shape, x, y, side, side)
    pad = side * INNER
    scale = (side - 2 * pad) / pictograms.BOX
    picture = pictograms.placed(
        pictograms.PICTOGRAMS.get(looks.kind.key, pictograms.PICTOGRAMS[dk.GENERIC.key]),
        scale,
        x + pad,
        y + pad,
    )
    solid = looks.kind.key in pictograms.FILLED
    width = pictograms.STROKE * scale
    if colour is None:
        ink = palette.plain_ink
        return [
            Shape(outline, fill=palette.plain_ground, stroke=ink, width=PLAIN_LINE),
            Shape(picture, fill=ink if solid else None, stroke=ink, width=width),
        ]
    return [
        Shape(outline, fill=colour),
        Shape(picture, fill=palette.ink if solid else None, stroke=palette.ink, width=width),
    ]


def card(x: float, y: float, h: float, looks: dk.Looks, palette: Palette = LIGHT) -> list[Shape]:
    """The band and the badge of a card whose top left corner is (x, y) and whose height is `h`."""
    return [
        *band(x, y, h, looks, palette),
        *badge(x + BAND_W + BADGE_GAP, y + (h - BADGE) / 2, BADGE, looks, palette),
    ]
