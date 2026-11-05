"""What kind of equipment a device is, so that its card can look like it (no Qt in this module).

The model has no device kind, and a project file must not gain one (the model hash and every
written file stay as they are). The kind is therefore read, every time, from what the device
already says about itself, with the table below and nothing else:

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
`Ground power supply` is ground support). Nothing is learned and nothing is stored: rename a
device or change its subsystem and its look follows. Whether a person should be able to set the
kind by hand is an open decision (it would need a field in a project file).

Each kind belongs to a *family* that has an accent colour (a token `device.<family>` in both
themes), a badge shape and a label; the kind has its own pictogram (`gui/device_looks.py`). Colour
is never the only cue: the pictogram, the shape and the words of the tooltip, the inspector and
the legend say the same.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from harness_design_studio.core import describe
from harness_design_studio.core.model import Project
from harness_design_studio.gui import strings

SHAPES: Final[tuple[str, ...]] = ("square", "circle", "hexagon", "octagon")
OVERVIEW_TINT: Final = 0.12  # the share of the accent laid over a box seen from far away: its ID
# (`text.primary`) keeps 4.5:1 on it in every family and both themes (tests/test_tokens.py)


@dataclass(frozen=True)
class Family:
    key: str
    label: str
    token: str  # the accent colour in gui/theme/tokens.py (both themes); "" has none
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

# what `describe.unit_glyph` (words of the name and subsystem, else the kinds of link) says -> kind
FROM_LINKS: Final[dict[str, str]] = {
    "computer": "computer", "power": "power_unit", "comms": "transceiver", "thermal": "heater",
    "payload": "payload", "mechanism": "mechanism", "pyro": "pyro", "sensor": "sensor",
    "actuator": "mechanism", "egse": "ground_support", "unit": "device",
}  # fmt: skip


@dataclass(frozen=True)
class Looks:
    """What a device looks like and why: the kind, where the tool read it from (`source`:
    `name`, `id`, `subsystem`, `links` or `none`) and the words that decided it (`clue`)."""

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


def looks_of(unit_id: str, name: str, subsystem: str, links_glyph: str = "unit") -> Looks:
    """The look of one device. `links_glyph` is `describe.unit_glyph` for it (the card has it
    already); it counts only when the name, the ID and the subsystem say nothing."""
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
    return looks_of(u.id, u.name, u.subsystem, describe.unit_glyph(project, unit_id, categories))


def sentence(looks: Looks, name: str, unit_id: str) -> str:
    """One plain sentence for the inspector and the tooltip: `Looks like: Battery (from the name
    Battery 1)`."""
    if looks.source == "name":
        why = strings.LOOKS_FROM_NAME.format(name=name)
    elif looks.source == "id":
        why = strings.LOOKS_FROM_ID.format(id=unit_id)
    elif looks.source == "subsystem":
        why = strings.LOOKS_FROM_SUBSYSTEM.format(word=looks.clue)
    elif looks.source == "links":
        why = strings.LOOKS_FROM_LINKS
    else:
        why = strings.LOOKS_FROM_NOTHING
    return strings.LOOKS_LIKE.format(kind=looks.kind.label, why=why)
