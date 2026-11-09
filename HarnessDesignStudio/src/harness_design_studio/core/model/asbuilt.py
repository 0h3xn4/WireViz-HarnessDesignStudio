# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The as-built record: what was really built and measured (transparency work, S9, requirement R6).

One record for each thing a technician writes something down about: a harness, a part lot, a wire,
a connector, a pin, a test. The records are kept in `asbuilt/records.json`. The file is optional,
like the journal and the import records: a project that never recorded anything has none, and its
files, its model hash and every written output are as they were. The records are **not** part of the
model hash (they are what happened, not what was designed) and are never written into an output
file except the as-built report and the *As-built* sheet of the build workbook, which exist only
for a project that has records.

A record holds no time, no operator by login and no path: the names of the people who built and
inspected are typed text, and the journal (when the project has one) says who saved the record and
when. The tool never says that a result passed: a result that is out of its limit is reported as
such (`core/asbuilt.py`), and a recorded result is never changed by the tool.

Units are in the field names: `cut_length_m`, `strip_a_mm`, `continuity_ohm`, `isolation_mohm`,
`test_voltage_v`.
"""

from typing import ClassVar, Literal

from .base import Label, LengthM, LengthMm, Name, NonNegative, SparseEntity, Text

ASBUILT_FILE = "asbuilt/records.json"
AsBuiltKind = Literal["harness", "part", "wire", "connector", "pin", "test"]
AS_BUILT_KINDS: tuple[str, ...] = ("harness", "part", "wire", "connector", "pin", "test")
TestType = Literal["continuity", "isolation"]
Result = Literal["pass", "fail"]


def record_id(kind: str, harness_id: str, subject: str) -> str:
    """`<kind>:<harness>:<subject>`: the subject is the harness (for a harness), the part ID, the
    wire ID, the connector ID, `CONNECTOR.PIN` or the test number of the Tests sheet (`T001`)."""
    return f"{kind}:{harness_id}:{subject}"


class AsBuiltRecord(SparseEntity):
    """What was recorded about one thing of one harness. Every field after `subject` is optional and
    left out of the file while it is empty."""

    OMIT_WHEN_DEFAULT: ClassVar[frozenset[str]] = frozenset(
        {
            "serial_numbers", "lot", "cut_length_m", "strip_a_mm", "strip_b_mm", "crimp_tool",
            "crimp_tool_calibration_id", "built_by", "inspected_by", "test_type", "tested",
            "result", "continuity_ohm", "isolation_mohm", "test_voltage_v", "notes",
            "nonconformance",
        }
    )  # fmt: skip

    id: Name
    kind: AsBuiltKind
    harness_id: Name
    subject: Name
    serial_numbers: list[Label] = []  # of a harness, a connector, a wire
    lot: Label = ""  # the lot or batch of the part (kind `part`), by part ID in `subject`
    cut_length_m: LengthM | None = None  # a wire: the length that was cut
    strip_a_mm: LengthMm | None = None  # a wire: the strip length at the From end, as built
    strip_b_mm: LengthMm | None = None  # a wire: the strip length at the To end, as built
    crimp_tool: Label = ""  # a pin: the crimp tool that was used
    crimp_tool_calibration_id: Label = ""  # a pin: the calibration ID of that tool
    built_by: Label = ""  # a name typed by a person, not a login
    inspected_by: Label = ""
    test_type: Label = ""  # a test: continuity or isolation, as the Tests sheet says
    tested: Label = ""  # a test: the Wire column of the Tests sheet (what was tested)
    result: Result | None = None  # a test: as the technician recorded it
    continuity_ohm: NonNegative | None = None  # a continuity test: the resistance measured
    isolation_mohm: NonNegative | None = None  # an insulation test: the resistance measured
    test_voltage_v: NonNegative | None = None  # an insulation test: the voltage that was applied
    notes: Text = ""
    nonconformance: Text = ""  # what is not as designed, in words; never cleared by the tool


__all__ = [
    "AS_BUILT_KINDS",
    "ASBUILT_FILE",
    "AsBuiltKind",
    "AsBuiltRecord",
    "Result",
    "TestType",
    "record_id",
]
