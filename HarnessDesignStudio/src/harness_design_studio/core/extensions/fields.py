"""The documented fields an expression may read (the *derived models* of S8).

A field belongs to a scope (the kind of object a rule or a table runs over) and is worked out by a
function from the objects of the design. Every built-in field calls the function the tool already
uses for the same number (`wire_length`, `awg_to_area_mm2`, `wire_current_limit`, `voltage_drop_v`),
so a field cannot disagree with a table or a rule of the tool. A field whose input is not known is
`None` ("not known"), never a guess.

The fields are registered in the registry like every other item (`builtins.install`), and a Python
plug-in can add fields of its own; `catalogue_rows` is the list that `docs/developer/extensions.md`
shows.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from harness_design_studio.core import settings
from harness_design_studio.core.drc.rules import _wire_current_limit
from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.generate.mass import harness_mass
from harness_design_studio.core.generate.sizing import voltage_drop_v
from harness_design_studio.core.model import Connector, Harness, InterfaceInstance, Project, Wire
from harness_design_studio.core.units import AWG_MAX, AWG_MIN, awg_to_area_mm2

from .expr import Value

SCOPES = ("wire", "connector", "interface", "harness")
# What a rule or a table that "applies to" an object can read: the object and its surroundings.
READABLE = {
    "wire": ("wire", "harness", "interface"),
    "connector": ("connector", "harness"),
    "interface": ("interface",),
    "harness": ("harness",),
}


@dataclass(frozen=True)
class Context:
    """The objects a field is worked out for. A scope that does not apply is None."""

    project: Project
    harness: Harness | None = None
    wire: Wire | None = None
    connector: Connector | None = None
    interface: InterfaceInstance | None = None


@dataclass(frozen=True)
class FieldDef:
    scope: str
    name: str
    unit: str
    kind: str  # "number" | "text" | "flag"
    doc: str
    fn: Callable[[Context], Value]

    @property
    def id(self) -> str:
        return f"{self.scope}.{self.name}"


def _interface_of(c: Context) -> InterfaceInstance | None:
    if c.interface is not None:
        return c.interface
    return c.project.interfaces.get(c.wire.interface_id or "") if c.wire else None


def _category(c: Context) -> Value:
    i = _interface_of(c)
    t = c.project.interface_types.get(i.type_id) if i else None
    return t.category if t else None


def _construction(c: Context) -> Value:
    i = _interface_of(c)
    t = c.project.interface_types.get(i.type_id) if i else None
    return t.construction if t else None


def _emc(c: Context) -> Value:
    i = _interface_of(c)
    t = c.project.interface_types.get(i.type_id) if i else None
    return (t.emc_class or None) if t else None


def _wire_mm2(c: Context) -> Value:
    w = c.wire
    if w is None or w.gauge_awg is None or not AWG_MIN <= w.gauge_awg <= AWG_MAX:
        return None
    return awg_to_area_mm2(w.gauge_awg)


def _wire_length(c: Context) -> Value:
    return wire_length(c.harness, c.wire) if c.harness and c.wire else None


def _wire_drop(c: Context) -> Value:
    """The calculation of the rule voltage-drop: current x resistivity x length / area x conductors."""
    w, i = c.wire, _interface_of(c)
    t = c.project.interface_types.get(i.type_id) if i else None
    rho, _missing = settings.resistivity(c.project)
    length = _wire_length(c)
    if not (w and i and t and rho is not None and length and i.max_current_a is not None):
        return None
    if w.gauge_awg is None or not AWG_MIN <= w.gauge_awg <= AWG_MAX:
        return None
    n = settings.drop_conductors(c.project, t.category)
    return voltage_drop_v(i.max_current_a, rho, float(length), w.gauge_awg, n)  # type: ignore[arg-type]


def _wire_limit(c: Context) -> Value:
    if c.wire is None or c.wire.gauge_awg is None:
        return None
    return _wire_current_limit(c.project, c.wire, c.harness)


def _harness_length(c: Context) -> Value:
    h = c.harness
    if h is None or not h.wires:
        return None
    lengths = [wire_length(h, w) for w in h.wires]
    if any(x is None for x in lengths):
        return None
    return float(sum(x for x in lengths if x is not None))


def _harness_mass(c: Context) -> Value:
    if c.harness is None:
        return None
    report = harness_mass(c.project, c.harness)
    return round(report.total_g, 9) if report.complete else None


def _wires_of_interface(c: Context) -> Value:
    i = c.interface
    if i is None:
        return None
    return sum(1 for h in c.project.harnesses.values() for w in h.wires if w.interface_id == i.id)


def _pins_used(c: Context) -> Value:
    conn = c.connector
    return None if conn is None else sum(1 for p in conn.pins if p.signal)


def _opt(value: str | None) -> Value:
    return value if value else None


def _build() -> list[FieldDef]:
    f = FieldDef
    return [
        f("wire", "id", "", "text", "The wire's ID.", lambda c: c.wire.id if c.wire else None),
        f("wire", "harness", "", "text", "The ID of the harness the wire is in.", lambda c: c.harness.id if c.harness else None),
        f("wire", "signal", "", "text", "The signal the wire carries.", lambda c: _opt(c.wire.signal) if c.wire else None),
        f("wire", "gauge_awg", "AWG", "number", "The gauge as the AWG number (a larger number is a thinner wire); not known while unset.", lambda c: c.wire.gauge_awg if c.wire else None),
        f("wire", "mm2", "mm2", "number", "The cross-section of the gauge in mm2 (a solid round conductor of the AWG diameter, definition D-AWG).", _wire_mm2),
        f("wire", "length_m", "m", "number", "The length: the wire's own, else the sum of the routing segments between its connectors; not known without either.", _wire_length),
        f("wire", "colour", "", "text", "The wire colour as written.", lambda c: _opt(c.wire.colour) if c.wire else None),
        f("wire", "part", "", "text", "The library wire part.", lambda c: _opt(c.wire.part_id) if c.wire else None),
        f("wire", "interface", "", "text", "The ID of the interface the wire implements.", lambda c: _opt(c.wire.interface_id) if c.wire else None),
        f("wire", "category", "", "text", "The category of the interface type the wire carries (power, ground, signal ...).", _category),
        f("wire", "construction", "", "text", "The construction of the interface type (single, twisted_pair ...).", _construction),
        f("wire", "emc_class", "", "text", "The EMC class of the interface type.", _emc),
        f("wire", "current_a", "A", "number", "The largest current of the interface the wire implements; not known when none is given.", lambda c: i.max_current_a if (i := _interface_of(c)) else None),
        f("wire", "voltage_v", "V", "number", "The voltage of the interface the wire implements; not known when none is given.", lambda c: i.voltage_v if (i := _interface_of(c)) else None),
        f("wire", "ampacity_limit_a", "A", "number", "The current the wire's gauge may carry after the bundle and temperature derating (the limit of the rule current-over-wire); not known while a derating value is missing.", _wire_limit),
        f("wire", "voltage_drop_v", "V", "number", "The voltage the wire drops at the interface current (the figure of the rule voltage-drop); not known while an input is missing.", _wire_drop),
        f("wire", "locked", "", "flag", "True when a person set the gauge, colour, part and length and generation keeps them.", lambda c: c.wire.locked if c.wire else None),
        f("connector", "id", "", "text", "The connector's ID.", lambda c: c.connector.id if c.connector else None),
        f("connector", "name", "", "text", "The connector's name.", lambda c: c.connector.name if c.connector else None),
        f("connector", "role", "", "text", "box, cable, inline, feedthrough, test or loose (a cable end with no connector chosen yet).", lambda c: c.connector.role if c.connector else None),
        f("connector", "part", "", "text", "The library part.", lambda c: c.connector.part_id if c.connector else None),
        f("connector", "gender", "", "text", "male, female or unspecified.", lambda c: c.connector.gender if c.connector else None),
        f("connector", "unit", "", "text", "The device a box connector belongs to.", lambda c: _opt(c.connector.unit_id) if c.connector else None),
        f("connector", "harness", "", "text", "The harness a cable connector belongs to.", lambda c: c.harness.id if c.harness else None),
        f("connector", "pins", "", "number", "The number of pins.", lambda c: len(c.connector.pins) if c.connector else None),
        f("connector", "pins_used", "", "number", "The number of pins that carry a signal.", _pins_used),
        f("interface", "id", "", "text", "The interface's ID.", lambda c: c.interface.id if c.interface else None),
        f("interface", "name", "", "text", "The interface's name.", lambda c: c.interface.name if c.interface else None),
        f("interface", "type", "", "text", "The ID of the interface type.", lambda c: c.interface.type_id if c.interface else None),
        f("interface", "category", "", "text", "The category of the type.", _category),
        f("interface", "construction", "", "text", "The construction of the type.", _construction),
        f("interface", "emc_class", "", "text", "The EMC class of the type.", _emc),
        f("interface", "redundancy", "", "text", "none, nominal or redundant.", lambda c: c.interface.redundancy if c.interface else None),
        f("interface", "max_current_a", "A", "number", "The largest current; not known when none is given.", lambda c: c.interface.max_current_a if c.interface else None),
        f("interface", "voltage_v", "V", "number", "The voltage; not known when none is given.", lambda c: c.interface.voltage_v if c.interface else None),
        f("interface", "requirement", "", "text", "The requirement ID the interface traces to.", lambda c: _opt(c.interface.requirement_id) if c.interface else None),
        f("interface", "endpoints", "", "number", "The number of ends.", lambda c: len(c.interface.endpoints) if c.interface else None),
        f("interface", "wires", "", "number", "The number of wires that implement it, in every harness.", _wires_of_interface),
        f("harness", "id", "", "text", "The harness's ID.", lambda c: c.harness.id if c.harness else None),
        f("harness", "name", "", "text", "The harness's name.", lambda c: c.harness.name if c.harness else None),
        f("harness", "revision", "", "text", "The revision letter.", lambda c: c.harness.revision if c.harness else None),
        f("harness", "status", "", "text", "draft, in_review or released.", lambda c: c.harness.status if c.harness else None),
        f("harness", "wires", "", "number", "The number of wires.", lambda c: len(c.harness.wires) if c.harness else None),
        f("harness", "connectors", "", "number", "The number of cable connectors.", lambda c: len(c.harness.connectors) if c.harness else None),
        f("harness", "length_m", "m", "number", "The sum of the wire lengths; not known while a wire has none.", _harness_length),
        f("harness", "mass_g", "g", "number", "The mass from the library data without the margin; not known while a part has no mass.", _harness_mass),
    ]  # fmt: skip


BUILTIN_FIELDS: tuple[FieldDef, ...] = tuple(_build())


def vocabulary_fields(applies_to: str, defs: Sequence[FieldDef] | None = None) -> frozenset[str]:
    """The ids of the fields a rule or a table that applies to `applies_to` may read."""
    scopes = READABLE[applies_to]
    return frozenset(
        d.id for d in (defs if defs is not None else BUILTIN_FIELDS) if d.scope in scopes
    )


def catalogue_rows() -> list[tuple[str, str, str, str]]:
    """(field, unit, kind, what it is) for every built-in field, for the documentation."""
    return [(d.id, d.unit, d.kind, d.doc) for d in BUILTIN_FIELDS]


def setting_value(project: Project, name: str) -> Value:
    """`setting('file.key')`: the value in force (the project's, else the tool's default)."""
    file, _, key = name.partition(".")
    if settings.setting(file, key) is None:
        return None
    value = settings.effective(project, file, key).value
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list | tuple) and all(isinstance(v, str | int | float) for v in value):
        return list(value)
    return None  # a table or pairs: read it with a lookup table of the extension instead


def known_settings() -> frozenset[str]:
    return frozenset(s.id for s in settings.SETTINGS if s.kind not in ("table", "pairs"))
