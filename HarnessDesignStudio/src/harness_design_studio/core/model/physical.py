"""Physical layer: connectors, pins, wires, shields and harnesses."""

from typing import ClassVar, Literal

from harness_design_studio.core.ids import Id, PinId

from .base import Awg, Entity, IsoDate, LengthM, Name, SparseEntity, Text

Gender = Literal["male", "female", "unspecified"]
Role = Literal["box", "cable", "inline", "feedthrough", "test"]
Termination = Literal["crimp", "solder", "unspecified"]
HarnessStatus = Literal["draft", "in_review", "released"]
ShieldKind = Literal["twisted_pair", "shielded_pair", "overall_shield", "quad", "coax"]
ShieldEnd = Literal["backshell_360", "pigtail", "floating"]


class Pin(Entity):
    id: PinId
    signal: Name | None = None
    contact_size: Name | None = None
    termination: Termination = "unspecified"
    locked: bool = False  # manual allocation that generation must never move
    interface_id: Id | None = None  # interface this pin was allocated for (set by generation)
    fixed: bool = (
        False  # signal fixed by the unit design (KiCad): interfaces connect to it, it never moves
    )


class Connector(Entity):
    id: Id
    name: Name
    role: Role
    part_id: Id
    unit_id: Id | None = None  # box connectors only
    gender: Gender = "unspecified"
    keying: Name | None = None
    carries: list[Id] = []  # interface types this connector is meant for (empty = any)
    mates_with: Id | None = None  # cable connectors: the box connector this one plugs into
    pins: list[Pin] = []
    notes: Text = ""


class Wire(SparseEntity):
    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"label", "note", "manual"})

    id: Id
    signal: Name | None = None
    from_connector: Id
    from_pin: PinId
    to_connector: Id
    to_pin: PinId
    gauge_awg: Awg | None = None
    part_id: Id | None = None
    colour: Name | None = None
    length_m: LengthM | None = None
    interface_id: Id | None = None
    locked: bool = False  # user-set gauge, colour, part and length: regeneration keeps them
    label: Name | None = None  # text for the wire labels instead of the signal name (a person's)
    note: Text = ""  # a person's remark; generation always keeps it
    manual: bool = False  # drawn by a person: generation keeps it as it is and never matches it


class ShieldGroup(SparseEntity):
    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"manual"})

    id: Id
    kind: ShieldKind
    wire_ids: list[Id]
    end_a: ShieldEnd = "floating"
    end_b: ShieldEnd = "floating"
    manual: bool = False  # made by a person (twisted, shielded or overall); generation keeps it


class Splice(Entity):
    id: Id
    name: Name
    wire_ids: list[Id]


class BranchPoint(Entity):
    id: Id
    name: Name


class Segment(Entity):
    id: Id
    from_node: Id  # a connector or branch point of the same harness
    to_node: Id
    length_m: LengthM | None = None


class Harness(Entity):
    id: Id
    name: Name
    revision: Name = "A"
    status: HarnessStatus = "draft"
    connectors: list[Connector] = []
    wires: list[Wire] = []
    splices: list[Splice] = []
    shields: list[ShieldGroup] = []
    branch_points: list[BranchPoint] = []
    segments: list[Segment] = []
    generated: bool = False  # created by generation (regeneration may replace it)
    group_key: str = ""  # segmentation key it was generated for
    interfaces: list[Id] = []  # interfaces this harness carries
    author: Name | None = None  # who put it into review (change control)
    checker: Name | None = None  # who checked it at release
    approver: Name | None = None  # who released it
    released_on: IsoDate | None = None  # date of the release (YYYY-MM-DD)
    notes: Text = ""
