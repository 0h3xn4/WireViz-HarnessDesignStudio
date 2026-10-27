"""Small drawn parts of the diagram's state marks: the compact badge (icon + count), the lock badge,
the tag chips, the auto-filled chip, the flight/ground mapping of zone names and the corner chip that
says whether the harnesses and outputs are up to date.

A badge is the compact form of a state chip (`gui/states.py`): the state's icon, its colour token and
its border pattern (solid, dotted for pending, dashed for not checked), so colour is never the only
cue; the word is in the tooltip and in the legend. Sizes are in scene units like the cards.
"""

import json
from typing import NamedTuple

from PySide6.QtCore import QRectF, QSettings, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

from harness_design_studio.gui import strings
from harness_design_studio.gui.icons import draw_icon
from harness_design_studio.gui.states import STATES, StateChip
from harness_design_studio.gui.theme import ThemeManager

PAD = 3.0  # inside a badge, left and right
ICON = 11.0
GAP = 4.0  # between two marks
TINT = 0.10  # share of the state colour in a badge's fill


class Hit(NamedTuple):
    """A mark on a card or a chip that answers the pointer: where it is (item coordinates), what
    it is ("state", "lock", "auto", "conn", "tag"), the tooltip, and the state key if any."""

    rect: QRectF
    kind: str
    tip: str
    state: str = ""


def badge_width(text_w: float, text: str) -> float:
    return PAD * 2 + ICON + (2.0 + text_w if text else 0.0)


def paint_badge(
    painter: QPainter,
    rect: QRectF,
    state: str,
    text: str,
    theme: ThemeManager,
    font: QFont,
    *,
    ground: str = "surface",
) -> None:
    """A compact state badge: tinted box, the state's border pattern, its icon and `text`."""
    spec = STATES[state]
    colour = theme.color(spec.token)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    fill = QColor(theme.color(ground))
    painter.setBrush(fill)
    painter.setPen(Qt.PenStyle.NoPen)
    box = rect.adjusted(0.5, 0.5, -0.5, -0.5)
    painter.drawRoundedRect(box, 3, 3)
    tint = QColor(colour)
    tint.setAlphaF(TINT)
    painter.setBrush(tint)
    pen = QPen(colour, 1.2)
    if spec.pattern == "dotted":
        pen.setStyle(Qt.PenStyle.DotLine)
    elif spec.pattern == "hatched":
        pen.setStyle(Qt.PenStyle.DashLine)
    painter.setPen(pen)
    painter.drawRoundedRect(box, 3, 3)
    side = min(ICON, box.height() - 2)
    draw_icon(
        painter,
        spec.icon,
        QRectF(box.left() + PAD - 0.5, box.center().y() - side / 2, side, side),
        colour,
        stroke=1.5,
    )
    if text:
        f = QFont(font)
        f.setItalic(spec.pattern != "solid")
        painter.setFont(f)
        painter.setPen(colour)
        painter.drawText(
            QRectF(box.left() + PAD + ICON + 1.0, box.top(), box.width(), box.height()),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            text,
        )
    painter.restore()


def paint_tag(
    painter: QPainter,
    rect: QRectF,
    text: str,
    theme: ThemeManager,
    font: QFont,
    *,
    token: str = "text-muted",  # noqa: S107 (a colour token, not a secret)
    dashed: bool = False,
) -> None:
    """A little word in a rounded outline (REDUNDANT, FLIGHT ...); dashed for a redundant chain."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    colour = theme.color(token)
    pen = QPen(colour, 1.0, Qt.PenStyle.DashLine if dashed else Qt.PenStyle.SolidLine)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
    painter.setFont(font)
    painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
    painter.restore()


def paint_auto(
    painter: QPainter, rect: QRectF, text: str, theme: ThemeManager, font: QFont
) -> None:
    """ "3 auto": the key's own dashed outline in the auto-fill colour (same as the legend entry)."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    colour = theme.color("auto-fill")
    painter.setPen(QPen(colour, 1.4, Qt.PenStyle.DashLine))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect.adjusted(0.7, 0.7, -0.7, -0.7), 3, 3)
    painter.setFont(font)
    painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
    painter.restore()


# ---- flight / ground tags: the zone names are the only thing the model has to go on ----------------


class ZoneTags:
    """Which zones are drawn with a FLIGHT or GROUND tag. The model has no such field, so this is a
    setting of the viewer's (QSettings key `canvas/zone_tags`, a JSON object zone name -> tag); until
    somebody sets one nothing is tagged. Setting a tag never touches the project."""

    KEY = "canvas/zone_tags"
    TAGS = ("flight", "ground")

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings: QSettings | None = None
        self._map: dict[str, str] = {}
        if settings is not None:
            self.attach(settings)

    def attach(self, settings: QSettings | None) -> None:
        self._settings = settings
        self._map = {}
        if settings is None:
            return
        try:
            raw = json.loads(str(settings.value(self.KEY, "") or "{}"))
        except ValueError:
            raw = {}
        if isinstance(raw, dict):
            self._map = {str(k): str(v) for k, v in raw.items() if v in self.TAGS}

    def tag_of(self, zone: str) -> str:
        """ "flight", "ground" or "" (no tag)."""
        return self._map.get(zone, "")

    def set_tag(self, zone: str, tag: str) -> None:
        if tag in self.TAGS:
            self._map[zone] = tag
        else:
            self._map.pop(zone, None)
        if self._settings is not None:
            self._settings.setValue(self.KEY, json.dumps(self._map, sort_keys=True))

    def any(self) -> bool:
        return bool(self._map)


# ---- the corner chip: are the harnesses and the outputs up to date? ----------------------------------

CORNER_DELAY_MS = 400  # how long after the last change the status is read again
CORNER_BIG_DELAY_MS = 1500  # ... in a project with more than BIG_PROJECT links
BIG_PROJECT = 500


def corner_states(gen: str, out: str, has_links: bool) -> list[tuple[str, str]]:
    """(state key, text) of the chips for a generation status ("none", "current", "stale") and an
    outputs state ("none", "current", "stale", "modified", "unreadable", "unsaved"). Nothing at all
    for a project with no links; one "pass" chip when everything is current."""
    if not has_links:
        return []
    chips: list[tuple[str, str]] = []
    if gen == "stale":
        chips.append(("stale", strings.CORNER_GEN_STALE))
    elif gen == "none":
        chips.append(("draft", strings.CORNER_GEN_NONE))
    if out == "stale":
        chips.append(("stale", strings.CORNER_OUT_STALE))
    elif out == "none" and gen == "current":  # (nothing to export before the harnesses exist)
        chips.append(("draft", strings.CORNER_OUT_NONE))
    elif out == "modified":
        chips.append(("fail", strings.CORNER_OUT_MODIFIED))
    elif out == "unreadable":
        chips.append(("fail", strings.CORNER_OUT_UNREADABLE))
    if not chips and gen == "current":
        chips.append(
            ("pass", strings.CORNER_ALL_CURRENT if out == "current" else strings.CORNER_GEN_CURRENT)
        )
    return chips


class CornerStatus(QFrame):
    """The chip(s) in the top left corner of the canvas: harnesses and outputs out of date, not
    generated, not exported, or all current (CV-22). It reads `ctl.generation_status()` and
    `ctl.outputs_state()` a moment after the last change, not on every edit."""

    def __init__(self, ctl: object, theme: ThemeManager, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("canvas-status")
        self.setProperty(
            "card", True
        )  # an opaque card, so lane names behind it stay out of the way
        self.ctl = ctl
        self.theme = theme
        self._chips: list[StateChip] = []
        self._wanted = True  # View > Show problem notices
        lay = QHBoxLayout(self)
        lay.setContentsMargins(4, 3, 4, 3)
        lay.setSpacing(4)
        self._lay = lay
        self.setAccessibleName(strings.CORNER_NAME)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(CORNER_DELAY_MS)
        self._timer.timeout.connect(self.refresh)
        for sig in ("changed", "stateChanged"):
            getattr(ctl, sig).connect(self._soon)
        self.refresh()

    def _soon(self, *_args: object) -> None:
        """Read the status after a pause (longer for a big project: the model hash and the output
        manifest cost real time there)."""
        big = len(self.ctl.project.interfaces) > BIG_PROJECT  # type: ignore[attr-defined]
        self._timer.start(CORNER_BIG_DELAY_MS if big else CORNER_DELAY_MS)

    def set_wanted(self, on: bool) -> None:
        """Show the chips (True) or keep the corner empty (View > Show problem notices)."""
        self._wanted = on
        self.setVisible(on and any(not c.isHidden() for c in self._chips))

    def states(self) -> list[tuple[str, str]]:
        """(state, text) of the chips now shown."""
        return [(c.state(), c.text() or "") for c in self._chips if not c.isHidden()]

    def refresh(self) -> None:
        """Read the status now (a test, or the timer)."""
        ctl = self.ctl
        project = ctl.project  # type: ignore[attr-defined]
        want = corner_states(
            ctl.generation_status(),  # type: ignore[attr-defined]
            ctl.outputs_state(),  # type: ignore[attr-defined]
            bool(project.interfaces),
        )
        while len(self._chips) < len(want):
            chip = StateChip(self.theme)
            self._chips.append(chip)
            self._lay.addWidget(chip)
        for k, chip in enumerate(self._chips):
            if k < len(want):
                chip.set_state(*want[k])
                chip.show()
            else:
                chip.hide()
        self.setVisible(bool(want) and self._wanted)
        self.adjustSize()
