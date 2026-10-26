"""Logical layer: what must be connected, independent of pins and wires."""

from typing import ClassVar, Literal

from harness_design_studio.core.ids import Id, MaybeId, PinId

from .base import Awg, Entity, Label, Name, Positive, SparseEntity, Text

Side = Literal["nominal", "redundant", "none"]
Category = Literal[
    "power", "data", "analog", "rf", "pyro", "discrete", "thermal", "ground", "other"
]
Construction = Literal["single", "twisted_pair", "twisted_shielded_pair", "quad", "coax", "twinax"]
Shielding = Literal["none", "overall", "per_pair"]
Direction = Literal["out", "in", "bidir", "passive"]
Flow = Literal["unspecified", "a_to_b", "b_to_a", "bidirectional"]


class Unit(Entity):
    id: Id
    name: Name
    subsystem: Name
    zone: Name | None = None
    side: Side = "none"
    mass_relevant: bool = True
    notes: Text = ""


class SignalDef(Entity):
    name: Name
    direction: Direction = "passive"
    pair: Name | None = None  # signals sharing a pair name are routed as one twisted pair


class InterfaceType(Entity):
    id: Id
    name: Name
    category: Category
    signals: list[SignalDef]
    construction: Construction = "single"
    impedance_ohm: Positive | None = None
    shielding: Shielding = "none"
    emc_class: Name | None = None
    default_gauge_awg: Awg | None = None
    unverified: bool = False  # True for starter/example data nobody has confirmed
    notes: Text = ""


class Endpoint(Entity):
    unit_id: Id
    connector_id: Id | None = None  # a box connector on that unit, once chosen
    auto: bool = False  # connector was picked by the tool and not yet confirmed by a person
    role: Name | None = None


class InterfaceInstance(Entity):
    id: Id
    name: Name
    type_id: Id
    endpoints: list[Endpoint]
    redundancy: Side = "none"
    flow: Flow = "unspecified"
    max_current_a: Positive | None = None
    voltage_v: Positive | None = None
    requirement_id: Name | None = None
    notes: Text = ""


class PinPair(Entity):
    """Two pins that a link joins: a pin of its first connector and a pin of its second one."""

    a_pin: PinId
    b_pin: PinId


class Link(SparseEntity):
    """Two connectors of two devices that are joined pin to pin (M2, the pinout first). The pairs
    are a person's decision, proposed from the signal names and saved only when accepted; what the
    link carries (CAN, power ...) is derived from the pins, never stored. A harness made from the
    link is named in `harness_id`. Left out of the files while a project has no link."""

    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"name", "harness_id", "note"})

    id: Id
    name: Label = ""  # a label; empty means the ends are the name
    a_connector: Id
    b_connector: Id
    pairs: list[PinPair] = []
    harness_id: MaybeId = ""  # the harness made from this link, if any
    note: Text = ""
