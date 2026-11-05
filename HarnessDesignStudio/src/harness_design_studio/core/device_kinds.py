"""What kind of equipment a device is, so that its card can look like it (no Qt in this module).

The kind is **read** from what the device says about itself, with the table below and nothing
else, unless a person set it by hand (`Unit.kind`, optional and written only when set):

0. the kind set by hand (`Unit.kind`, one of the IDs of `KIND`; `device` forces the plain box);
1. the words of its name (`Reaction wheel 1`, `S-band transceiver`); a word matches when it is the
   keyword, the keyword followed by digits (`obc1`), or, for keywords of five letters or more, the
   keyword with an ending (`wheels`); `Solar array simulator` is a solar array, and `simulator`
   does not hide an `imu`;
2. the letters of its ID before the first digit (`BAT1`, `PCDU1`, `OBC1-R` give `bat`, `pcdu`,
   `obc`);
3. the words of its subsystem (`power`, `comms`, `thermal`) as a coarse hint;
4. the kinds of link it carries (`describe.unit_glyph`: a spark line, RF, mostly power, data), which
   the card already used for its small picture before this module existed;
5. else the plain box: *Device*.

Inside each step the kinds are tried in the order of `KINDS`, the specific ones first (a star
tracker before a sensor, a battery before a power unit, ground support before power so that a
`Ground power supply` is ground support). Nothing is learned and nothing is stored but the kind a
person set: rename a device or change its subsystem and its look follows.

Each kind belongs to a *family* that has an accent colour (a token `device.<family>` in both
themes, whose values are `ACCENTS` below, so the window and the written files read one table), a
badge shape and a label; the kind has its own pictogram (`core/pictograms.py`, drawn by
`gui/device_looks.py` in the window and by `core/outputs/looks.py` in the written diagram). Colour
is never the only cue: the pictogram, the shape and the words of the tooltip, the inspector and
the legend say the same.

This module is in `core` because the written block diagram (`system/block_diagram.svg`) draws the
same looks from the model alone; the words of the screen (`sentence`) stay in `gui/device_kinds.py`.
"""


from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from harness_design_studio.core import describe
from harness_design_studio.core.model import Project

SHAPES: Final[tuple[str, ...]] = ("square", "circle", "hexagon", "octagon")
OVERVIEW_TINT: Final = 0.12  # the share of the accent laid over a box seen from far away: its ID
# (`text.primary`) keeps 4.5:1 on it in every family and both themes (tests/test_tokens.py)

# The accent of each family as (light theme, dark theme). `gui/theme/tokens.py` builds the tokens
# `device.<family>` from this table, and the written diagram (`core/outputs/looks.py`) draws with
# the light values, so a colour is set once and the window and the file cannot drift. In the light
# theme each is a badge fill with white on it (4.5:1) and 3:1 against every surface.
ACCENTS: Final[dict[str, tuple[str, str]]] = {
    "control": ("#3730C9", "#6E8BFF"),
    "power": ("#B45309", "#F0A04B"),
    "attitude": ("#15803D", "#5FD38A"),
    "sensing": ("#0E7490", "#4FC3D9"),
    "comms": ("#A21CAF", "#E08CF2"),
    "payload": ("#BE123C", "#FF7F9A"),
    "thermal": ("#7C2D12", "#FF6B5E"),
    "mechanism": ("#6B7B13", "#C5D94A"),
    "ground": ("#475569", "#AAB7C8"),
}
# What a plain device (no accent) is drawn with in the light theme: the muted text colour for the
# outline and the picture, `bg.hover` behind it; and the ink of a picture on an accent fill
# (`accent.text`). tests/test_device_kind.py checks them against the tokens of the light theme.
INK_ON_ACCENT_LIGHT: Final = "#FFFFFF"
PLAIN_INK_LIGHT: Final = "#646A72"
PLAIN_GROUND_LIGHT: Final = "#F0F1F3"


@dataclass(frozen=True)
class Family:
    key: str
    label: str
    token: str  # the accent colour token `device.<family>` (values in ACCENTS); "" has none
    shape: str  # the outline of the badge (one of SHAPES)


FAMILIES: Final[tuple[Family, ...]] = (
    Family("control", "Control and data", "device.control", "square"),
    Family("power", "Power", "device.power", "hexagon"),
    Family("attitude", "Attitude actuators", "device.attitude", "circle"),
    Family("sensing", "Sensors", "device.sensing", "octagon"),
    Family("comms", "Communication", "device.comms", "hexagon"),
    Family("payload", "Payload", "device.payload", "square"),
    Family("thermal", "Thermal", "device.thermal", "octagon"),
    Family("mechanism", "Mechanisms and pyro", "device.mechanism", "circle"),
    Family("ground", "Ground support", "device.ground", "square"),
    Family("other", "Other device", "", "square"),
)
FAMILY: Final[dict[str, Family]] = {f.key: f for f in FAMILIES}


@dataclass(frozen=True)
class Kind:
    key: str  # also the key of the pictogram in gui/device_looks.py
    label: str
    family: str
    words: tuple[str, ...]  # words of the name (see the module text for how a word matches)
    ids: tuple[str, ...]  # the letters of the ID before its first digit
    subsystems: tuple[str, ...] = ()  # words of the subsystem: a coarse hint, tried last


# The order is the priority: the first kind with a match wins, step by step.
KINDS: Final[tuple[Kind, ...]] = (
    Kind("battery", "Battery", "power", ("battery", "batteries", "accumulator"), ("bat", "batt")),
    Kind("solar_array", "Solar array", "power", ("solar", "photovoltaic"), ("sa", "sap", "pv")),
    Kind(
        "ground_support",
        "Ground support equipment",
        "ground",
        ("egse", "gse", "scoe", "ground", "checkout", "test"),
        ("egse", "gse", "scoe", "gpsu", "rfsu"),
        ("egse", "ground", "test"),
    ),  # fmt: skip
    Kind(
        "power_unit",
        "Power distribution",
        "power",
        ("pcdu", "pdu", "eps", "psu", "pcu", "power", "converter", "regulator", "distribution"),
        ("pcdu", "pdu", "eps", "psu", "pcu"),
        ("power", "eps"),
    ),  # fmt: skip
    Kind(
        "reaction_wheel", "Reaction wheel", "attitude", ("wheel", "flywheel"), ("rw", "rwa", "mw")
    ),
    Kind(
        "magnetorquer",
        "Magnetorquer",
        "attitude",
        ("magnetorquer", "magnetotorquer", "torquer", "mtq"),
        ("mtq", "mtr"),
    ),  # fmt: skip
    Kind(
        "thruster",
        "Thruster",
        "attitude",
        ("thruster", "propulsion", "valve"),
        ("thr", "prop"),
    ),  # fmt: skip
    Kind("star_tracker", "Star tracker", "sensing", ("tracker", "star"), ("st", "str", "stt")),
    Kind("sun_sensor", "Sun sensor", "sensing", ("sun",), ("ss", "css", "dss", "fss")),
    Kind(
        "gyro",
        "Gyro / inertial unit",
        "sensing",
        ("gyro", "gyroscope", "imu", "iru", "accelerometer"),
        ("gyr", "imu", "iru"),
    ),  # fmt: skip
    Kind(
        "sensor",
        "Sensor",
        "sensing",
        ("sensor", "gps", "gnss", "magnetometer", "detector", "probe"),
        ("gps", "gnss", "mag", "sns"),
    ),  # fmt: skip
    Kind(
        "transceiver",
        "Transceiver",
        "comms",
        ("transceiver", "transmitter", "receiver", "transponder", "radio", "modem", "trx"),
        ("trx", "tx", "rx", "xcvr", "tcv"),
        ("comm", "comms", "telecom", "ttc", "rf"),
    ),  # fmt: skip
    Kind("antenna", "Antenna", "comms", ("antenna", "dipole", "whip"), ("ant",)),
    Kind(
        "payload",
        "Payload",
        "payload",
        ("payload", "camera", "imager", "instrument", "spectrometer", "telescope", "experiment"),
        ("pl", "pld", "cam", "img"),
        ("payload", "instrument"),
    ),  # fmt: skip
    Kind(
        "heater",
        "Heater and thermal",
        "thermal",
        ("heater", "thermistor", "thermal", "thermostat", "radiator", "tcs"),
        ("htr", "heat", "tcs"),
        ("thermal", "tcs"),
    ),  # fmt: skip
    Kind(
        "pyro", "Pyro unit", "mechanism", ("pyro", "squib", "initiator", "cutter"), ("pyro", "pyr")
    ),
    Kind(
        "mechanism",
        "Mechanism",
        "mechanism",
        ("mechanism", "deployment", "deployer", "hinge", "gimbal", "actuator", "motor"),
        ("mech", "dep", "act"),
        ("mechanism", "deploy", "structure"),
    ),  # fmt: skip
    Kind(
        "computer",
        "Computer",
        "control",
        ("computer", "obc", "processor", "cpu", "mcu", "controller", "obdh", "cdh"),
        ("obc", "cpu", "mcu", "cdh", "obdh"),
        ("avionics", "obdh", "cdh", "data", "computer"),
    ),  # fmt: skip
    Kind(
        "interface_unit",
        "Interface unit",
        "control",
        ("riu", "rtu", "dhu", "interface", "gateway", "bridge", "hub", "switch"),
        ("riu", "rtu", "dhu", "iu"),
    ),  # fmt: skip
)
GENERIC: Final[Kind] = Kind("device", "Device", "other", (), ())
KIND: Final[dict[str, Kind]] = {k.key: k for k in (*KINDS, GENERIC)}
KIND_IDS: Final[tuple[str, ...]] = tuple(KIND)  # the values `Unit.kind` may hold (the model has the
# same list as a `Literal`, `core/model/logical.py`; tests/test_device_kind.py keeps them equal)

# what `describe.unit_glyph` (words of the name and subsystem, else the kinds of link) says -> kind
FROM_LINKS: Final[dict[str, str]] = {
    "computer": "computer", "power": "power_unit", "comms": "transceiver", "thermal": "heater",
    "payload": "payload", "mechanism": "mechanism", "pyro": "pyro", "sensor": "sensor",
    "actuator": "mechanism", "egse": "ground_support", "unit": "device",
}  # fmt: skip


@dataclass(frozen=True)
class Looks:
    """What a device looks like and why: the kind, where the tool read it from (`source`:
    `manual` (set by hand), `name`, `id`, `subsystem`, `links` or `none`) and the words that decided
    it (`clue`)."""

    kind: Kind
    source: str
    clue: str

    @property
    def family(self) -> Family:
        return FAMILY[self.kind.family]

    @property
    def generic(self) -> bool:
        return self.kind is GENERIC

    @property
    def token(self) -> str:
        return self.family.token


def words_of(text: str) -> list[str]:
    """The lower-case words of a name: runs of letters and digits (`On-board computer (1)` gives
    `on`, `board`, `computer`, `1`)."""
    out: list[str] = []
    word = ""
    for ch in text.lower():
        if ch.isalnum():
            word += ch
        elif word:
            out.append(word)
            word = ""
    if word:
        out.append(word)
    return out


def _matches(word: str, keyword: str) -> bool:
    if word == keyword:
        return True
    if not word.startswith(keyword):
        return False
    rest = word[len(keyword) :]
    return rest.isdigit() or len(keyword) >= 5  # `obc1`, `wheels`


def id_letters(unit_id: str) -> str:
    """The lower-case letters of an ID before its first digit (`PCDU1` gives `pcdu`)."""
    letters = ""
    for ch in unit_id.lower():
        if not ch.isalpha():
            break
        letters += ch
    return letters


def _by_words(kind_words: tuple[str, ...], words: list[str]) -> str:
    for word in words:
        for kw in kind_words:
            if _matches(word, kw):
                return word
    return ""


def looks_of(
    unit_id: str, name: str, subsystem: str, links_glyph: str = "unit", manual: str | None = None
) -> Looks:
    """The look of one device. `manual` is `Unit.kind` (a key of `KIND`, `device` for the plain
    box); when it is set nothing else is read. `links_glyph` is `describe.unit_glyph` for it (the
    card has it already); it counts only when the name, the ID and the subsystem say nothing."""
    if manual in KIND:
        return Looks(KIND[manual], "manual", "")
    name_words = words_of(name)
    for kind in KINDS:
        hit = _by_words(kind.words, name_words)
        if hit:
            return Looks(kind, "name", hit)
    letters = id_letters(unit_id)
    for kind in KINDS:
        if letters and letters in kind.ids:
            return Looks(kind, "id", unit_id)
    sub_words = words_of(subsystem)
    for kind in KINDS:
        hit = _by_words(kind.subsystems, sub_words)
        if hit:
            return Looks(kind, "subsystem", hit)
    key = FROM_LINKS.get(links_glyph, "device")
    if key != "device":
        return Looks(KIND[key], "links", "")
    return Looks(GENERIC, "none", "")


def looks_for(
    project: Project, unit_id: str, categories: Mapping[str, Sequence[str]] | None = None
) -> Looks:
    """The look of a device of a project (`categories` is `describe.unit_categories(project)`, to
    avoid scanning the links once for each device)."""
    u = project.units.get(unit_id)
    if u is None:
        return Looks(GENERIC, "none", "")
    return looks_of(
        u.id, u.name, u.subsystem, describe.unit_glyph(project, unit_id, categories), u.kind
    )


def automatic_looks(
    project: Project, unit_id: str, categories: Mapping[str, Sequence[str]] | None = None
) -> Looks:
    """What the tool would pick for a device if no kind were set by hand (the first entry of the
    Kind list of the inspector says it: `Automatic: Battery`)."""
    u = project.units.get(unit_id)
    if u is None:
        return Looks(GENERIC, "none", "")
    return looks_of(u.id, u.name, u.subsystem, describe.unit_glyph(project, unit_id, categories))


def used_kinds(project: Project, categories: Mapping[str, Sequence[str]] | None = None) -> list[str]:
    """The kinds of device the project has, in the order of the table (`KINDS`, then the plain
    device); none while every device is a plain box, because then there is nothing to tell apart.
    The legend of the window and of the written diagram list these."""
    cats = categories if categories is not None else describe.unit_categories(project)
    found = {looks_for(project, u, cats).kind.key for u in project.units}
    if found <= {GENERIC.key}:
        return []
    order = [k.key for k in (*KINDS, GENERIC)]
    return sorted(found, key=order.index)
