"""Layout (where things sit in the diagram) and review records (waivers)."""

from typing import Annotated, Literal

from pydantic import AfterValidator, StringConstraints

from harness_design_studio.core.ids import Id

from .base import Entity, Name, Text, _no_control_chars
from .logical import InterfaceInstance, Unit
from .physical import Connector, Harness

Justification = Annotated[
    str, StringConstraints(min_length=10, max_length=2000), AfterValidator(_no_control_chars)
]


class Placement(Entity):
    """Diagram position of one unit, in scene units. `id` is the unit's ID."""

    id: Id
    x: float
    y: float


class Waiver(Entity):
    """A recorded decision to accept a finding. The justification is mandatory."""

    id: Id  # "<rule>.<object>" so it is stable across sessions
    rule: Name
    object_id: Id
    justification: Justification
    notes: Text = ""


__all__ = ["Justification", "Placement", "Waiver"]


class Snapshot(Entity):
    """The parts of the design one harness release depends on, frozen at release."""

    units: list[Unit] = []
    interfaces: list[InterfaceInstance] = []
    connectors: list[Connector] = []  # box connectors the harness mates with
    harnesses: list[Harness] = []  # the released harness itself


class Baseline(Entity):
    """Frozen snapshot made when a harness revision is released. `id` is `<harness>.<revision>`."""

    id: Id
    harness_id: Id
    revision: Name
    released_on: Name
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
    when: Name
    comment: Text = ""
