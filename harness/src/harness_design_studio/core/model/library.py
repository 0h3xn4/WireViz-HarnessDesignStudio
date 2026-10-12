"""Parts library: real, qualified parts the plans refer to."""

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

from harness_design_studio.core.ids import Id

from .base import MAX_PIN_COUNT, Entity, Name, NonNegative, Text

PartCategory = Literal["connector", "contact", "backshell", "wire", "sleeving", "label"]
PART_CATEGORIES: tuple[PartCategory, ...] = (
    "connector", "contact", "backshell", "wire", "sleeving", "label",
)  # fmt: skip
Approval = Literal["approved", "pending", "not_approved"]


class Part(Entity):
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


def _iso_date(value: str | None) -> str | None:
    if value is not None:
        date.fromisoformat(value)  # ValueError (a validation error) unless YYYY-MM-DD
    return value


class LibraryInfo(Entity):
    """Where the parts of the library come from. `source` and `date` are entered by a person (or
    the import records the file name); the tool never reads a clock into project data."""

    name: Name = "Project parts library"
    version: Name = "0"
    source: Name | None = None  # for example the file or database the parts were imported from
    date: Annotated[str | None, AfterValidator(_iso_date)] = None  # date of that data, YYYY-MM-DD
