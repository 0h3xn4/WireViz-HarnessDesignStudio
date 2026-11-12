# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""JSON Schemas of the project files, made from the model itself.

For people who edit project files by hand in an editor that understands JSON Schema (completion,
checks, hover text). Nothing is downloaded; the schemas come from the same strict models the
loader uses, so they cannot drift from the format.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, create_model

from harness_design_studio.core.model import (
    PART_CATEGORIES,
    AsBuiltRecord,
    Baseline,
    ChangeEntry,
    ConfigFile,
    Connector,
    DiagramMark,
    GenerationRecord,
    Harness,
    ImportRecord,
    InterfaceInstance,
    InterfaceType,
    JournalEntry,
    LibraryInfo,
    Link,
    Part,
    Placement,
    ProjectMeta,
    Unit,
    Waiver,
)


def _list_file(name: str, key: str, item: type[BaseModel]) -> type[BaseModel]:
    fields: dict[str, Any] = {key: (list[item], ...)}  # type: ignore[valid-type]
    return create_model(name, **fields)


def _layout_file() -> type[BaseModel]:
    fields: dict[str, Any] = {"zones": (list[str], ...), "placements": (list[Placement], ...)}
    return create_model("LayoutFile", **fields)


# (schema name, file pattern, model)
def _kinds() -> list[tuple[str, str, type[BaseModel]]]:
    return [
        ("project", "project.json", ProjectMeta),
        ("config", "config/*.json", ConfigFile),
        ("library-info", "library/manifest.json", LibraryInfo),
        *[
            ("parts", f"library/{category}.json", _list_file("PartsFile", "parts", Part))
            for category in PART_CATEGORIES
        ],  # the parts files only: library/manifest.json has its own schema
        (
            "interface-types",
            "logical/interface_types.json",
            _list_file("InterfaceTypesFile", "interface_types", InterfaceType),
        ),  # fmt: skip
        ("layout", "logical/layout.json", _layout_file()),
        ("links", "logical/links.json", _list_file("LinksFile", "links", Link)),
        ("units", "logical/units/*.json", _list_file("UnitsFile", "units", Unit)),
        (
            "interfaces",
            "logical/interfaces/*.json",
            _list_file("InterfacesFile", "interfaces", InterfaceInstance),
        ),  # fmt: skip
        (
            "connectors",
            "physical/connectors/*.json",
            _list_file("ConnectorsFile", "connectors", Connector),
        ),  # fmt: skip
        ("harness", "physical/harnesses/*.json", Harness),
        ("generation", "generated/generation.json", GenerationRecord),
        ("waivers", "waivers.json", _list_file("WaiversFile", "waivers", Waiver)),
        ("journal", "journal.jsonl", JournalEntry),  # one entry per line (M7a, D-228)
        ("changelog", "changelog.json", _list_file("ChangeFile", "changelog", ChangeEntry)),
        (
            "import-records",
            "imports/records.json",
            _list_file("ImportRecordsFile", "imports", ImportRecord),
        ),  # fmt: skip
        (
            "asbuilt",
            "asbuilt/records.json",
            _list_file("AsBuiltRecordsFile", "asbuilt", AsBuiltRecord),
        ),  # fmt: skip
        (
            "diagram-marks",
            "diagram/marks.json",
            _list_file("DiagramMarksFile", "marks", DiagramMark),
        ),  # fmt: skip
        ("baseline", "baselines/*/*.json", Baseline),
    ]


def schemas() -> dict[str, dict[str, Any]]:
    """Schema name to JSON Schema (draft 2020-12, as pydantic writes it)."""
    out = {}
    for name, pattern, model in _kinds():
        if name in out:
            continue  # one schema for the six parts files
        schema = model.model_json_schema()
        schema.setdefault("title", name)
        shown = "library/<category>.json" if name == "parts" else pattern
        schema["description"] = (
            f"Harness Design Studio project file {shown}. Generated from the model."
            if name != "journal"
            else f"One line of the Harness Design Studio project file {shown} (one entry per "
            "line). Generated from the model."
        )
        out[name] = schema
    from harness_design_studio.core.extensions import schema as extension_schema

    out.update(extension_schema.schemas())  # S8: the two files of an extensions folder
    return out


def editor_settings() -> dict[str, Any]:
    """A `.vscode/settings.json` fragment that maps the files of a project to the schemas, with
    paths relative to the project folder (the schemas folder placed inside it)."""
    return {
        "json.schemas": [
            {"fileMatch": [f"/{pattern}"], "url": f"./schemas/{name}.schema.json"}
            for name, pattern, _ in _kinds()
        ]
        + [
            {
                "fileMatch": ["/extensions/*.json", "!/extensions/enabled.json"],
                "url": "./schemas/extension.schema.json",
            },
            {
                "fileMatch": ["/extensions/enabled.json"],
                "url": "./schemas/extensions-enabled.schema.json",
            },
        ]
    }


def dumps(doc: object) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"
