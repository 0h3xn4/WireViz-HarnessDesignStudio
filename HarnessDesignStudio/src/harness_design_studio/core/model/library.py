"""Parts library: real, qualified parts the plans refer to."""

from typing import Annotated, ClassVar, Literal

from pydantic import Field

from harness_design_studio.core.ids import Id

from .base import MAX_PIN_COUNT, Entity, IsoDate, Name, NonNegative, SparseEntity, Text

PartCategory = Literal["connector", "contact", "backshell", "wire", "sleeving", "label"]
PART_CATEGORIES: tuple[PartCategory, ...] = (
    "connector", "contact", "backshell", "wire", "sleeving", "label",
)  # fmt: skip
Approval = Literal["approved", "pending", "not_approved"]


class Part(SparseEntity):
    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset({"tool", "conductors"})

    id: Id
    category: PartCategory
    manufacturer: Name | None = None
    part_number: Name | None = None
    specification: Name | None = None
    description: Name | None = None
    approval: Approval = "pending"
    unverified: bool = False  # example data that no engineer has checked
    pin_count: Annotated[int, Field(ge=1, le=MAX_PIN_COUNT)] | None = None
    mates_with: Id | None = None  # connector parts: the mating counterpart (e.g. male for female)
    mass_g: NonNegative | None = None
    mass_per_m_g: NonNegative | None = None
    ratings: dict[Name, NonNegative] = {}
    notes: Text = ""
    tool: Name | None = None  # the crimp tool or its setting for a contact part (a person's, 1.7.0)
    # Wire parts: how many conductors one metre of the part carries (a twisted pair is 2). Every
    # wire that names the part is one conductor of it, so the bill of materials and the mass count
    # the sum of their lengths divided by this number: the metres of the cable (1.11, D-188).
    conductors: Annotated[int, Field(ge=1, le=64)] = 1


class LibraryInfo(Entity):
    """Where the parts of the library come from. `source` and `date` are entered by a person (or
    the import records the file name); the tool never reads a clock into project data."""

    name: Name = "Project parts library"
    version: Name = "0"
    source: Name | None = None  # for example the file or database the parts were imported from
    date: IsoDate | None = None  # date of that data, YYYY-MM-DD
