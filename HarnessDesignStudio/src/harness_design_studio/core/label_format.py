"""The text printed on the labels of a wire and of a cable connector: the named formats and the
templates (S3b, assumption A-LABEL-FORMAT).

The form of a label until D-191 was one (`standard`): the wire ID, the name, ' to ', the far end and
the EMC class in brackets. The setting `model.label_format` selects another:

- `standard` (default): `W001-001 PWR to W001-P11.1 [EMC x]`; a connector
  `name (ID mates BOX)`;
- `compact`: the shortest text that is still unambiguous, `W001-001 to W001-P11.1`; a connector
  `ID mates BOX` (no name, no tag);
- `descriptive`: the standard text with the interface the wire belongs to (`W001-001 PWR (IF-018
  RW1 power) to W001-P11.1`) and, on a connector, the device it plugs into (`ID mates BOX of
  DEVICE`);
- `custom`: the templates `model.label_wire_template` and `model.label_connector_template`, text
  with `{field}` places (WIRE_FIELDS, CONNECTOR_FIELDS). A template that is not set gives the
  standard text of its kind.

A template is only ever filled in by this module (a plain replacement of `{field}` by its text;
there is no format specification, no attribute and no call), and `check_template` refuses a field
that does not exist, naming it. The colour table (`generation.wire_colour_by_signal`) is a
setting of its own and is not part of the format. The texts are made by
`core.outputs.tables.wire_label_texts` and `connector_label_text`, which the Labels table, the
Labels sheet and the explanation all call.
"""

import re
from collections.abc import Mapping

from harness_design_studio.core import settings
from harness_design_studio.core.model import Project

FORMATS = ("standard", "compact", "descriptive", "custom")
DEFAULT_FORMAT = "standard"
FORMAT_TEXT = {
    "standard": (
        "wire ID, name, 'to', the far end and the EMC class; "
        "a connector: name (ID mates DEVICE-CONNECTOR)"
    ),
    "compact": "wire ID, 'to' and the far end; a connector: ID mates DEVICE-CONNECTOR",
    "descriptive": (
        "the standard text with the interface of the wire, "
        "and with the device a connector plugs into"
    ),
    "custom": "the templates of model.label_wire_template and model.label_connector_template",
}
WIRE_FIELDS = ("harness", "wire", "signal", "name", "interface", "emc", "end", "from", "to")
CONNECTOR_FIELDS = ("harness", "connector", "name", "mates", "device")
FIELD_TEXT = {
    "harness": "the harness ID",
    "wire": "the wire ID",
    "signal": "the signal of the wire",
    "name": (
        "the label a person gave the wire (connector: the label of the connector), else the signal"
    ),
    "interface": "the ID of the interface of the wire",
    "emc": "the EMC class of the interface type, or nothing",
    "end": "A or B: the end the label is printed at",
    "from": "connector and pin at the end the label is printed at",
    "to": "connector and pin at the far end",
    "connector": "the cable connector ID",
    "mates": "the device connector it plugs into",
    "device": "the device that connector belongs to",
}
TEMPLATE_KEYS = {"wire": "label_wire_template", "connector": "label_connector_template"}
MAX_TEMPLATE = 200  # characters; a label is a few lines of text on a small sticker

_TOKEN = re.compile(r"\{\{|\}\}|\{([^{}]*)\}")


def format_of(project: Project) -> str:
    """The label format in force: the one function the tables and `explain` call."""
    value = settings.effective(project, "model", "label_format").value
    return str(value) if value in FORMATS else DEFAULT_FORMAT


def template_of(project: Project, kind: str) -> str | None:
    """The template of `kind` ("wire" or "connector"): None when not set, empty or not usable."""
    value = settings.effective(project, "model", TEMPLATE_KEYS[kind]).value
    fields = WIRE_FIELDS if kind == "wire" else CONNECTOR_FIELDS
    if not isinstance(value, str) or not value.strip() or check_template(value, fields):
        return None
    return value


def check_template(text: str, fields: tuple[str, ...]) -> str | None:
    """Why a template is not acceptable, or None. A field that does not exist is named."""
    if len(text) > MAX_TEMPLATE:
        return f"is longer than {MAX_TEMPLATE} characters"
    for m in _TOKEN.finditer(text):
        name = m.group(1)
        if name is not None and name not in fields:
            known = ", ".join(fields)
            return f"uses the field {{{name}}}, which does not exist (the fields are {known})"
    if re.search(r"[{}]", _TOKEN.sub("", text)):
        return "has a single brace; write {{ and }} for a brace in the text"
    return None


def fill(text: str, values: Mapping[str, str]) -> str:
    """The template with every `{field}` replaced by its text (and `{{` `}}` by a brace)."""

    def one(m: re.Match[str]) -> str:
        whole, name = m.group(0), m.group(1)
        if name is None:
            return whole[0]
        return values[name]

    return _TOKEN.sub(one, text)
