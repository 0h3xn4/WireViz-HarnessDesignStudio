"""Plain-language captions for the diagram: what a link carries and what a connector is.

Pure functions of the project (no Qt). They only repeat what the project data says: a voltage or
a current shows when somebody entered it, and nothing is filled in from a standard.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from harness_design_studio.core.model import Part
from harness_design_studio.core.model.physical import Gender
from harness_design_studio.core.model.project import Project

_GENDER = {"male": "M", "female": "F"}


def _num(value: float) -> str:
    return f"{value:g}"


def link_caption(project: Project, interface_id: str) -> str:
    """ "CAN", or "Primary power · 28 V · 5 A" when the voltage and the current are set."""
    i = project.interfaces.get(interface_id)
    if i is None:
        return interface_id
    t = project.interface_types.get(i.type_id)
    parts = [t.name if t is not None else i.type_id]
    if i.voltage_v is not None:
        parts.append(f"{_num(i.voltage_v)} V")
    if i.max_current_a is not None:
        parts.append(f"{_num(i.max_current_a)} A")
    return " · ".join(parts)


def part_gender(part: Part | None) -> Gender:
    """ "male", "female" or "unspecified", as the library part says it in its description (e.g.
    "D-sub 9-pin, female"); where it says both ("male plug, mates with female socket") the first
    word counts. A part that does not say gives "unspecified"; nothing is guessed."""
    text = (part.description or "").lower() if part is not None else ""
    found = re.search(r"\b(female|male)\b", text)
    if found is None:
        return "unspecified"
    return "female" if found.group(1) == "female" else "male"


def link_values(project: Project, interface_id: str) -> str:
    """ "28 V · 5 A": only what somebody entered, nothing when neither is set."""
    i = project.interfaces.get(interface_id)
    if i is None:
        return ""
    parts = []
    if i.voltage_v is not None:
        parts.append(f"{_num(i.voltage_v)} V")
    if i.max_current_a is not None:
        parts.append(f"{_num(i.max_current_a)} A")
    return " · ".join(parts)


def connector_kind(project: Project, connector_id: str) -> str:
    """Short connector type: "D-sub 15-pin F" (from the part description and the gender)."""
    c = project.connectors.get(connector_id)
    if c is None:
        return ""
    part = project.parts.get(c.part_id)
    text = (part.description or part.part_number or part.id) if part is not None else c.part_id
    text = re.sub(r"\s*\([^)]*\)", "", text)  # "(example)" and the like
    text = re.sub(r",?\s*\b(fe)?male\b", "", text, flags=re.IGNORECASE).strip(" ,")
    gender = _GENDER.get(c.gender, "")
    return f"{text} {gender}".strip()


def connector_family(project: Project, connector_id: str) -> tuple[str, int, str]:
    """(family, pin count, gender) for drawing a connector: family is one of "dsub", "microd",
    "circular", "rj45", "coax" or "generic". It is read from the part's description."""
    c = project.connectors.get(connector_id) or project.all_connectors().get(connector_id)
    if c is None:
        return "generic", 0, ""
    part = project.parts.get(c.part_id)
    described = f"{part.description or ''} {part.part_number or ''}" if part is not None else ""
    text = f"{described} {c.part_id}".lower()
    pins = part.pin_count if part is not None and part.pin_count else 0
    family = "generic"
    for key, name in (
        ("micro-d", "microd"),
        ("microd", "microd"),
        ("mdm", "microd"),
        ("d-sub", "dsub"),
        ("dsub", "dsub"),
        ("circular", "circular"),
        ("38999", "circular"),
        ("rj45", "rj45"),
        ("coax", "coax"),
        ("sma", "coax"),
        ("tnc", "coax"),
    ):
        if re.search(
            rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", text
        ):  # a word, not part of one
            family = name
            break
    gender = c.gender if c.gender != "unspecified" else part_gender(part)
    return family, pins, gender


FAMILY_LABEL = {
    "dsub": "D-sub",
    "microd": "Micro-D / MDM",
    "circular": "Circular",
    "rj45": "RJ45",
    "coax": "Coax",
    "generic": "Other",
}


# ---- what a link still needs, and its summary (canvas states) -----------------------------------

VALUES_NEEDED: dict[str, tuple[str, ...]] = {"power": ("V", "A"), "pyro": ("A",)}
"""The interface categories whose links need a voltage ("V") and a current ("A") entered: the
current and voltage checks read them, and a blank would be taken for "does not apply". Other
categories (data, analog, discrete, RF ...) carry no such numbers, so nothing is asked for."""


def link_missing(project: Project, interface_id: str) -> tuple[str, ...]:
    """The values a link needs but nobody entered: "V" and/or "A", in that order; () for a link of
    a kind that does not need them, or one that has them all. It never fills anything in."""
    i = project.interfaces.get(interface_id)
    if i is None:
        return ()
    t = project.interface_types.get(i.type_id)
    needed = VALUES_NEEDED.get(t.category, ()) if t is not None else ()
    have = {"V": i.voltage_v, "A": i.max_current_a}
    return tuple(k for k in needed if have[k] is None)


def link_label(project: Project, interface_id: str) -> str:
    """What the label of a link says: "28 V · 5 A", with "V ?" or "A ?" in place of a value that
    is needed and missing ("28 V · A ?"); "" for a link with nothing to say."""
    i = project.interfaces.get(interface_id)
    if i is None:
        return ""
    missing = link_missing(project, interface_id)
    out: list[str] = []
    for key, value in (("V", i.voltage_v), ("A", i.max_current_a)):
        if value is not None:
            out.append(f"{_num(value)} {key}")
        elif key in missing:
            out.append(f"{key} ?")
    return " · ".join(out)


@dataclass(frozen=True)
class LinkSummary:
    """The facts for the tooltip of a link: where it ends, which harness and how many wires carry
    it, what is still missing, and which release locks it."""

    id: str
    name: str
    type_name: str
    caption: str  # "Primary power · 28 V · 5 A"
    ends: tuple[str, ...]  # unit IDs
    connectors: tuple[str, ...]  # box connector IDs ("" while not chosen)
    auto: int  # ends whose connector the tool picked and nobody confirmed
    harnesses: tuple[str, ...]  # harnesses that carry it (their wires, or listing it)
    wire_count: int
    missing: tuple[str, ...]  # "V" / "A"
    locks: tuple[tuple[str, str], ...]  # (harness ID, revision) of the releases that lock it

    @property
    def state(self) -> str:
        """ "Not generated yet", "N wire(s) in W001" or the like, in a few plain words."""
        if not self.wire_count:
            return "Not generated yet"
        s = "s" if self.wire_count != 1 else ""
        return f"Generated: {self.wire_count} wire{s}"

    def facts(self) -> list[tuple[str, str]]:
        """(label, value) rows for a tooltip, only the ones that have something to say."""
        rows = [("Type", self.caption), ("Ends", " ↔ ".join(self.ends))]
        rows.append(("Harness", ", ".join(self.harnesses) if self.harnesses else "none yet"))
        rows.append(("Wires", str(self.wire_count)))
        rows.append(("State", self.state))
        if self.missing:
            names = {"V": "voltage", "A": "current"}
            rows.append(("Still to enter", " and ".join(names[m] for m in self.missing)))
        if self.auto:
            rows.append(("Connectors", f"{self.auto} chosen for you, not confirmed"))
        if self.locks:
            rows.append(("Lock", "Released in " + ", ".join(f"{h} {r}" for h, r in self.locks)))
        return rows


def link_summary(
    project: Project, interface_id: str, locks: Sequence[tuple[str, str]] = ()
) -> LinkSummary:
    """The summary of one link (pure: nothing here changes the project). `locks` are the
    (harness, revision) pairs that lock it, from `core.vcs.lockview.locked_objects`."""
    i = project.interfaces.get(interface_id)
    if i is None:
        return LinkSummary(interface_id, interface_id, "", interface_id, (), (), 0, (), 0, (), ())
    t = project.interface_types.get(i.type_id)
    harnesses: list[str] = []
    wires = 0
    for h in sorted(project.harnesses.values(), key=lambda x: x.id):
        n = sum(1 for w in h.wires if w.interface_id == i.id)
        if n or i.id in h.interfaces:
            harnesses.append(h.id)
            wires += n
    return LinkSummary(
        id=i.id,
        name=i.name,
        type_name=t.name if t is not None else i.type_id,
        caption=link_caption(project, i.id),
        ends=tuple(e.unit_id for e in i.endpoints),
        connectors=tuple(e.connector_id or "" for e in i.endpoints),
        auto=sum(1 for e in i.endpoints if e.auto),
        harnesses=tuple(harnesses),
        wire_count=wires,
        missing=link_missing(project, i.id),
        locks=tuple((h, r) for h, r in locks),
    )


# ---- the picture on a unit's card ---------------------------------------------------------------

UNIT_GLYPHS: tuple[str, ...] = (
    "computer", "power", "comms", "thermal", "payload", "mechanism", "pyro", "sensor", "actuator",
    "egse", "unit",
)  # fmt: skip
_NAME_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("actuator", ("wheel", "magnetorquer", "thruster", "actuator", "motor")),
    ("sensor", ("tracker", "sensor", "gyro", "imu", "gps", "magnetometer")),
    ("power", ("battery", "solar", "pcdu", "pdu", "power")),
    ("thermal", ("heater", "thermal", "thermistor")),
    ("comms", ("transceiver", "antenna", "radio", "transmitter", "receiver")),
    ("payload", ("payload", "camera", "instrument")),
    ("pyro", ("pyro", "squib", "initiator")),
    ("computer", ("computer", "obc", "processor", "riu", "controller")),
)
_SUBSYSTEM_WORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("power", ("power", "eps")),
    ("thermal", ("thermal", "tcs")),
    ("comms", ("comm", "telecom", "ttc", "rf")),
    ("payload", ("payload", "instrument")),
    ("mechanism", ("mechanism", "deploy", "structure")),
    ("computer", ("avionics", "obdh", "cdh", "data", "computer")),
    ("egse", ("egse", "ground", "test")),
)


def _word_match(text: str, table: tuple[tuple[str, tuple[str, ...]], ...]) -> str | None:
    text = text.lower()
    for glyph, words in table:
        if any(w in text for w in words):
            return glyph
    return None


def unit_categories(project: Project) -> dict[str, list[str]]:
    """Unit ID -> the categories of the interfaces that end on it (one pass over the project; the
    canvas asks once per edit and hands it to `unit_glyph` for every card)."""
    out: dict[str, list[str]] = {}
    for i in project.interfaces.values():
        t = project.interface_types.get(i.type_id)
        if t is None:
            continue
        for u in {e.unit_id for e in i.endpoints}:
            out.setdefault(u, []).append(t.category)
    return out


def unit_glyph(
    project: Project, unit_id: str, categories: Mapping[str, Sequence[str]] | None = None
) -> str:
    """Which picture a unit's card carries (one of `UNIT_GLYPHS`), worked out from what the project
    says and nothing else (the model has no unit kind): first the words in the unit's name, then
    in its subsystem, then the kinds of interface it carries (a spark line: pyro; RF: comms;
    mostly power: power; analog, thermal or discrete signals: sensor; data: computer), then its
    connector families (coax: comms); otherwise "unit". `categories` is `unit_categories(project)`,
    to avoid scanning the interfaces once per unit."""
    u = project.units.get(unit_id)
    if u is None:
        return "unit"
    hit = _word_match(u.name, _NAME_WORDS) or _word_match(u.subsystem, _SUBSYSTEM_WORDS)
    if hit:
        return hit
    cats = list(
        (categories if categories is not None else unit_categories(project)).get(unit_id, ())
    )
    if cats:
        for key, glyph in (("pyro", "pyro"), ("rf", "comms")):
            if key in cats:
                return glyph
        if cats.count("power") * 2 >= len(cats):
            return "power"
        if any(c in ("analog", "thermal", "discrete") for c in cats):
            return "sensor"
        if "data" in cats:
            return "computer"
    for c in project.connectors.values():
        if (
            c.unit_id == unit_id
            and c.role == "box"
            and connector_family(project, c.id)[0] == "coax"
        ):
            return "comms"
    return "unit"


# ---- why the tool chose what it chose -----------------------------------------------------------


def why_lines(project: Project, kind: str, ident: str) -> list[str]:
    """Plain sentences saying why a link, a unit's connectors or one connector is the way it is:
    a connector the tool picked (first free one that carries the type), then what generation
    recorded for the wires and pins (`core.generate.explain`). Never empty."""
    from harness_design_studio.core.generate.explain import explain_wire  # (a cycle at import)

    out: list[str] = []

    def chosen(iid: str, only_unit: str | None = None, only_connector: str | None = None) -> None:
        i = project.interfaces.get(iid)
        if i is None:
            return
        t = project.interface_types.get(i.type_id)
        tname = t.name if t is not None else i.type_id
        for e in i.endpoints:
            if not e.auto or (only_unit and e.unit_id != only_unit):
                continue
            if only_connector and e.connector_id != only_connector:
                continue
            c = project.connectors.get(e.connector_id or "")
            where = f"{e.connector_id} ({c.name})" if c is not None else (e.connector_id or "?")
            out.append(
                f"{e.unit_id}: connector {where} was chosen for you, the first free {tname} "
                f"connector on {e.unit_id}. Confirm it to accept it, or pick another one."
            )

    def wires(iid: str) -> None:
        for h in sorted(project.harnesses.values(), key=lambda x: x.id):
            for w in h.wires:
                if w.interface_id == iid:
                    out.extend(x for x in explain_wire(project, h, w) if x not in out)

    if kind == "interface":
        chosen(ident)
        wires(ident)
    elif kind == "unit":
        for i in sorted(project.interfaces.values(), key=lambda x: x.id):
            if any(e.unit_id == ident for e in i.endpoints):
                chosen(i.id, only_unit=ident)
    elif kind == "connector":
        for i in sorted(project.interfaces.values(), key=lambda x: x.id):
            if any(e.connector_id == ident for e in i.endpoints):
                chosen(i.id, only_connector=ident)
        prov = project.generation.provenance if project.generation else {}
        for key in sorted(k for k in prov if k.startswith(f"pin:{ident}.")):
            out.extend(f"{key[4:]}: {line}" for line in prov[key])
    if not out:
        if kind == "interface" and project.generation is None:
            out.append(
                "Nothing to explain yet: the connectors were your choice and the harnesses are "
                "not generated. Generate them to see why wires, gauges and pins were chosen."
            )
        else:
            out.append("Nothing to explain: you chose these yourself, and nothing was recorded.")
    return out
