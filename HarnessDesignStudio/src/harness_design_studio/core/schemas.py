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
    Baseline,
    ChangeEntry,
    ConfigFile,
    Connector,
    GenerationRecord,
    Harness,
    InterfaceInstance,
    InterfaceType,
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
        ("changelog", "changelog.json", _list_file("ChangeFile", "changelog", ChangeEntry)),
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
        )
        out[name] = schema
    return out


def editor_settings() -> dict[str, Any]:
    """A `.vscode/settings.json` fragment that maps the files of a project to the schemas, with
    paths relative to the project folder (the schemas folder placed inside it)."""
    return {
        "json.schemas": [
            {"fileMatch": [f"/{pattern}"], "url": f"./schemas/{name}.schema.json"}
            for name, pattern, _ in _kinds()
        ]
    }


def dumps(doc: object) -> str:
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"
