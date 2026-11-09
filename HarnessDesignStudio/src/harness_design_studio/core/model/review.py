"""Layout (where things sit in the diagram) and review records (waivers)."""

from typing import Annotated, Any, ClassVar, Literal

from pydantic import (
    AfterValidator,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
    model_validator,
)

from harness_design_studio.core.ids import Id

from .base import Entity, IsoDate, Name, SparseEntity, Text, _no_control_chars
from .library import Part
from .logical import InterfaceInstance, InterfaceType, Link, Unit
from .physical import Connector, Harness

Justification = Annotated[
    str, StringConstraints(min_length=10, max_length=2000), AfterValidator(_no_control_chars)
]


class Placement(Entity):
    """Diagram position of one unit, in scene units. `id` is the unit's ID."""

    id: Id
    x: float
    y: float


# The marks of things that sit ON a line (the pill of an interface, the label of a connection, the
# connector box at an end of one): where each is, is a position along the line. Any other mark
# ("bend", "route", "pos") is an offset, of a piece of the line or of a loose cable end, and a mark
# of a kind this tool does not know is not ours to read.
ALONG_MARK_KINDS = frozenset({"interface", "link", "end"})
OFFSET_MARK_KINDS = frozenset({"bend", "route", "pos"})


def mark_is_along(mark_id: str) -> bool:
    """Whether the mark `mark_id` ("interface:IF-1", "link:L1", "end:L1:0") is the place of a label
    on its line (a position along it), not the offset of a piece of the line."""
    return mark_id.partition(":")[0] in ALONG_MARK_KINDS


class DiagramMark(SparseEntity):
    """Where the person moved one thing in the diagram off the place the tool gave it, kept in
    `diagram/marks.json` (optional, like the import record; not part of the model hash and never
    written into an output file). `id` names the thing: "interface:IF-TM" (the pill of an
    interface), "link:L1" (the label of a connection), "end:L1:0" and "end:L1:1" (the connector box
    at its ends) sit ON their line and are a position along it, `t`, the fraction of the length of
    the line from its first point (0 to 1), so they follow the line when devices move and never
    leave it; "bend:L1" (the vertical piece of a connection) and "route:IF-TM" (that of an
    interface's route) are an offset, `dx` and `dy` in scene units, of that piece from where the
    tool put it; "pos:W009-P2" (M4) is the offset of a loose cable end, the connector `W009-P2`,
    from where the tool puts it (out of the port its cable plugs into), so that it follows its
    device and, like every mark, is outside the model hash. Release 1.14.0 and 1.15.0 also wrote an
    offset for the labels; it is still read
    (the tool turns it into `t` by taking the nearest point of the line, and writes `t` from then
    on)."""

    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"dx", "dy", "t"})

    id: Name
    dx: Annotated[float, Field(ge=-100_000.0, le=100_000.0)] | None = None
    dy: Annotated[float, Field(ge=-100_000.0, le=100_000.0)] | None = None
    t: Annotated[float, Field(ge=0.0, le=1.0)] | None = None

    @model_validator(mode="after")
    def _one_way_to_say_where(self) -> DiagramMark:
        """`dx` and `dy` together, or `t` alone; a bend or a route has an offset only."""
        offset = (self.dx is not None, self.dy is not None)
        if offset not in ((True, True), (False, False)):
            raise ValueError("dx and dy go together")
        if (self.t is not None) == offset[0]:
            raise ValueError("a mark has an offset (dx and dy) or a position (t), one of the two")
        if self.t is not None and self.id.partition(":")[0] in OFFSET_MARK_KINDS:
            raise ValueError(
                "a position t is for a label on a line, not for a bend, a route or a loose end"
            )
        return self


FindingHash = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{12}$")]


class Waiver(SparseEntity):
    """A recorded decision to accept a finding. The justification is mandatory. `finding_hash` ties
    the waiver to the statement of the finding it was made for (release 1.11, D-187): if the
    statement changes, the waiver no longer applies. A waiver without it (made before, or by hand)
    applies as it always did."""

    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"finding_hash"})

    id: Id  # "<rule>.<object>" so it is stable across sessions
    rule: Name
    object_id: Id
    justification: Justification
    notes: Text = ""
    finding_hash: FindingHash | None = None


__all__ = ["Justification", "Placement", "Waiver"]


class Snapshot(Entity):
    """The parts of the design one harness release depends on, frozen at release."""

    units: list[Unit] = []
    interfaces: list[InterfaceInstance] = []
    connectors: list[Connector] = []  # box connectors the harness mates with
    harnesses: list[Harness] = []  # the released harness itself
    # Frozen with the release as well. `None` = not recorded (a baseline made before these were
    # kept): nothing is compared then, and the field is left out of the file so that old
    # baselines are written back unchanged.
    parts: list[Part] | None = None  # every part the harness uses (see vcs.snapshot.used_part_ids)
    interface_types: list[InterfaceType] | None = None  # types of the interfaces it carries
    config: dict[str, dict[str, Any]] | None = None  # configuration it depends on, by file name
    waivers: list[Waiver] | None = None  # waivers that applied to it (recorded, not locked)
    links: list[Link] | None = (
        None  # the link the harness was made from (M2); none when it has none
    )

    @model_serializer(mode="wrap")
    def _leave_out_unrecorded(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        for name in ("parts", "interface_types", "config", "waivers", "links"):
            if data.get(name) is None:
                data.pop(name, None)
        return data


class Baseline(Entity):
    """Frozen snapshot made when a harness revision is released. `id` is `<harness>.<revision>`."""

    id: Id
    harness_id: Id
    revision: Name
    released_on: IsoDate
    by: Name
    comment: Justification
    content_hash: Name  # hash of the design content at release (see vcs.hashing)
    snapshot: Snapshot


ChangeKind = Literal["review", "release", "new_revision"]


class ChangeEntry(Entity):
    """One line of the change log: what happened to which harness, who did it, when and why."""

    id: Id  # C0001, C0002, ...
    harness_id: Id
    revision: Name
    kind: ChangeKind
    by: Name
    when: IsoDate
    comment: Text = ""
