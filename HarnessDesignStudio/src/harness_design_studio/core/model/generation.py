"""Record of the last generation: what it was computed from and why each choice was made."""

from typing import Annotated

from pydantic import Field

from .base import Entity, Name


class GenerationRecord(Entity):
    input_hash: str  # hash of everything generation reads (see generate.engine.input_hash)
    generator_version: Name
    next_harness_number: Annotated[int, Field(ge=1)] = (
        1  # monotonic: retired harness numbers are never reused
    )
    placeholders_used: list[Name] = []  # configuration files still holding placeholder values
    provenance: dict[str, list[str]] = {}  # object key -> "rule: reason" lines (the Explain data)
