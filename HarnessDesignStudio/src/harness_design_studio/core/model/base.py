"""Base class and shared field types for all model objects."""

import re
import unicodedata
from datetime import date
from typing import Annotated, Any, ClassVar

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    StringConstraints,
    model_serializer,
)

from harness_design_studio.core.units import AWG_MAX, AWG_MIN


class Entity(BaseModel):
    """Immutable, strictly validated model object. Change it with `evolve`, never in place."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", strict=True, allow_inf_nan=False, validate_default=True
    )


class SparseEntity(Entity):
    """An entity whose optional fields in `OMIT_WHEN_DEFAULT` are left out of every dump while they
    still have their default value. A field added after release 1.3.0 goes here, so a project that
    does not use the feature keeps byte-identical files (and the same model hash and outputs), and a
    project written by this tool can still be read by an older one until the field is used."""

    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset()

    @model_serializer(mode="wrap")
    def _leave_out_defaults(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        data: dict[str, Any] = handler(self)
        for name in self.OMIT_WHEN_DEFAULT:
            if name in data and data[name] == type(self).model_fields[name].default:
                del data[name]
        return data


def evolve[E: Entity](obj: E, **changes: Any) -> E:
    """Return a re-validated copy of `obj` with some fields replaced. The fields that are not
    replaced keep their objects (entities are immutable), so a copy of a harness shares the wires
    and connectors that the change did not touch: an undo step holds the changed part, not a second
    copy of the whole harness (audit A-12, +1.4 MB per step before)."""
    cls = type(obj)
    unknown = set(changes) - set(cls.model_fields)
    if unknown:
        raise TypeError(f"{cls.__name__} has no field(s) {sorted(unknown)}")
    data = {name: getattr(obj, name) for name in cls.model_fields if name not in changes}
    data.update(changes)
    return cls.model_validate(data)


# Characters that are not control characters but break lines or hide in text: line and paragraph
# separators and the byte-order mark. (Direction controls and zero-width characters stay allowed
# for now: whether to refuse them is an open owner decision, audit A-16.)
_INVISIBLE = frozenset("\u2028\u2029\ufeff")


def _no_control_chars(value: str) -> str:
    for ch in value:
        if (
            (unicodedata.category(ch) in ("Cc", "Cs") and ch not in "\n\t")
            or ch in "\ufffe\uffff"
            or ch in _INVISIBLE
            or unicodedata.category(ch) == "Co"  # private use: no agreed meaning
        ):
            raise ValueError(
                "must not contain control characters, line separators or private-use characters"
            )  # (U+FFFE/FFFF are not valid XML)
    return value


_ISO_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # ASCII digits only


def _iso_date(value: str) -> str:
    """A real calendar date written 2026-03-31 (not 20260331, not 2026-02-30)."""
    if not _ISO_DATE.fullmatch(value):
        raise ValueError("must be a date written YYYY-MM-DD")
    date.fromisoformat(value)  # ValueError (a validation error) for 2026-02-30
    return value


Name = Annotated[
    str,
    StringConstraints(min_length=1, max_length=200),
    AfterValidator(_no_control_chars),
]
Label = Annotated[
    str, StringConstraints(max_length=200), AfterValidator(_no_control_chars)
]  # a name that may be empty
IsoDate = Annotated[str, AfterValidator(_iso_date)]
Text = Annotated[str, StringConstraints(max_length=5000), AfterValidator(_no_control_chars)]

# Numeric domains. A value outside them is damage or a typing slip, never a design decision, so
# such an object is set aside on load and refused by the editor (DECISIONS: ranges are defaults).
MAX_LENGTH_M = 10_000.0
MAX_PIN_COUNT = 1000
Awg = Annotated[int, Field(ge=AWG_MIN, le=AWG_MAX)]
LengthM = Annotated[float, Field(ge=0, le=MAX_LENGTH_M)]
MAX_LENGTH_MM = 100_000.0  # a guard against a typing slip (10 m in millimetres), not a design limit
LengthMm = Annotated[float, Field(ge=0, le=MAX_LENGTH_MM)]
Positive = Annotated[float, Field(gt=0)]
NonNegative = Annotated[float, Field(ge=0)]
