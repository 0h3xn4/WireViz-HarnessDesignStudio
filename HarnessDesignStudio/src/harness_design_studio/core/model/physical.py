# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Physical layer: connectors, pins, wires, shields and harnesses."""

from typing import Annotated, ClassVar, Literal

from pydantic import Field, model_validator

from harness_design_studio.core.ids import Id, PinId

from .base import (
    Awg,
    Entity,
    IsoDate,
    LengthM,
    LengthMm,
    Name,
    Reason,
    SparseEntity,
    Text,
)

Gender = Literal["male", "female", "unspecified"]
Role = Literal["box", "cable", "inline", "feedthrough", "test", "loose"]
# "loose" is the end of a cable that is not on a connector yet (M4, D-200, D-201): an ordinary
# connector of the harness with pins that wires attach to, no `mates_with`, and the library part
# `TBD-CONNECTOR` until a person decides.
LOOSE_ROLE: Role = "loose"
TBD_PART_ID = "TBD-CONNECTOR"  # the library part of a loose end until a person chooses one
# Where a harness came from. It is worked out from what the files already say (`generated`, and the
# connection that names the harness), never stored: `links.harness_origin` (D-201).
Origin = Literal["interfaces", "link", "drawn"]
Termination = Literal["crimp", "solder", "unspecified"]
HarnessStatus = Literal["draft", "in_review", "released"]
ShieldKind = Literal["twisted_pair", "shielded_pair", "overall_shield", "quad", "coax"]
ShieldEnd = Literal["backshell_360", "pigtail", "floating"]
# The outer conductor of a coax carries the signal return, so it is bonded at both ends whatever the
# grounding concept of the project says about other shields (release 1.10, D-182).
COAX_SHIELD_END: ShieldEnd = "backshell_360"
PinRole = Literal["", "power", "return", "ground", "signal", "shield", "spare"]
PinDirection = Literal["", "in", "out", "bidir"]  # "" = not set: the name and the type decide


class Pin(SparseEntity):
    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset(
        {"function", "contact_part", "role", "direction"}
    )

    id: PinId
    signal: Name | None = None
    contact_size: Name | None = None
    termination: Termination = "unspecified"
    locked: bool = False  # manual allocation that generation must never move
    interface_id: Id | None = None  # interface this pin was allocated for (set by generation)
    fixed: bool = (
        False  # signal fixed by the unit design (KiCad): interfaces connect to it, it never moves
    )
    function: Name | None = (
        None  # a person's words for what the pin does (1.4.0); no meaning to the tool
    )
    contact_part: Id | None = (
        None  # the contact (a library part of category contact) the cable side uses here (1.7.0)
    )
    role: PinRole = ""  # what the pin is for; empty = derived from the signal name (M2)
    direction: PinDirection = (
        ""  # which way the signal runs at this pin, seen from the device (1.9.0); empty = not set:
        # the link checks and the pairing proposal then take it from the interface types
    )


class Connector(SparseEntity):
    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"label", "locked"})

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
    label: Name | None = (
        None  # text for the connector's label instead of its ID (a person's, 1.4.0)
    )
    locked: bool = (
        False  # a cable connector of a generated harness that a person edited: generation keeps
        # its part, gender, keying and pin details (workshop M3)
    )


# The four values of a generated wire that a person can set in place of the one generation chooses.
# Each can carry its own reason in `Wire.overrides` (S4, D-191 (3)).
OVERRIDABLE: tuple[str, ...] = ("gauge_awg", "part_id", "colour", "length_m")


class Wire(SparseEntity):
    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset(
        {"label", "note", "manual", "strip_a_mm", "strip_b_mm", "overrides"}
    )

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
    strip_a_mm: LengthMm | None = None  # insulation stripped at the From end (a person's, 1.7.0)
    strip_b_mm: LengthMm | None = None  # insulation stripped at the To end (a person's, 1.7.0)
    # Why a person set a value of `OVERRIDABLE` in place of the one generation chooses: field name
    # -> the reason (never empty). Who and when are in the journal (`journal.json`), never here, so
    # the file of a design holds no name and no time. A locked wire with no entry here is one from
    # before the reasons were kept ("locked, no reason recorded"): it keeps its meaning.
    overrides: dict[Name, Reason] = {}

    @model_validator(mode="after")
    def _overrides_are_recorded_overrides(self) -> Wire:
        for key in self.overrides:
            if key not in OVERRIDABLE:
                raise ValueError(f"'{key}' cannot be overridden (only {', '.join(OVERRIDABLE)})")
            if getattr(self, key) is None:
                raise ValueError(f"the override of '{key}' needs a value on the wire")
        if self.overrides and not self.locked:
            raise ValueError("a wire with an override must be locked")
        return self


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


AccessoryKind = Literal["sleeving", "heat_shrink", "label", "backshell", "other"]


class Accessory(Entity):
    """Something that goes on a harness besides its wires and connectors: sleeving, heat shrink, a
    label, a backshell (1.7.0). It says what, where (a connector or a wire of the harness, or the
    harness itself), in words how far from where, and how much. Nothing is computed from it."""

    id: Id
    kind: AccessoryKind
    part_id: Id | None = None  # a library part (sleeving, label, backshell ...), if there is one
    target: Id | None = None  # a connector or a wire of this harness; None means the harness
    position: Name | None = None  # in words: "50 mm from the P1 end"
    length_mm: LengthMm | None = None  # for sleeving and heat shrink: the length of one piece
    quantity: Annotated[int, Field(ge=1, le=9999)] = 1
    note: Text = ""


class Harness(SparseEntity):
    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"label", "accessories"})

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
    label: Name | None = None  # text for the harness label instead of its name (a person's, 1.4.0)
    accessories: list[Accessory] = []  # sleeving, heat shrink, labels, backshells (1.7.0)
