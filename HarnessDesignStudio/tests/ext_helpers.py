"""Helpers for the tests of the extensions (S8): a generated project, a folder of extension files."""

import json
from pathlib import Path
from typing import Any

from harness_design_studio.core import templates
from harness_design_studio.core.extensions import manager
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Project, evolve

FORMAT = "harness-design-studio-extension"
ENABLED_FORMAT = "harness-design-studio-extensions-enabled"


def generated(folder: Path, template: str = "flatsat") -> Project:
    """An example project, generated (so it has wires, gauges and lengths)."""
    project = templates.create_project(folder / template, template)
    if not project.harnesses:
        generate_project(project)
    return project


def set_wire(project: Project, wire_id: str, **changes: Any) -> None:
    """Change fields of one wire in place (the model objects are immutable, the lists are not)."""
    for h in project.harnesses.values():
        for n, w in enumerate(h.wires):
            if w.id == wire_id:
                h.wires[n] = evolve(w, **changes)
                return
    raise KeyError(wire_id)


def ext_file(
    name: str = "t", rules: list[dict[str, Any]] | None = None, **more: Any
) -> dict[str, Any]:
    doc: dict[str, Any] = {"format": FORMAT, "format_version": 1, "name": name, "version": "1.0.0"}
    if rules is not None:
        doc["rules"] = rules
    doc.update(more)
    return doc


def gauge_rule(**changes: Any) -> dict[str, Any]:
    rule: dict[str, Any] = {
        "id": "gauge",
        "title": "Gauge",
        "severity": "warning",
        "applies_to": "wire",
        "condition": "wire.gauge_awg <= 22",
        "unit": "AWG",
        "message": "Wire {object} is AWG {actual}, limit {limit}, margin {margin}",
        "why": "w",
        "how": "h",
    }
    rule.update(changes)
    return rule


def write_extensions(
    root: Path,
    files: dict[str, dict[str, Any] | str],
    enabled: list[str] | None = None,
    plugins: list[str] | None = None,
) -> Path:
    """Write `files` (name -> document or raw text) into `<root>/extensions/` and enable `enabled`
    (default: all of them)."""
    folder = root / "extensions"
    folder.mkdir(parents=True, exist_ok=True)
    for name, doc in files.items():
        (folder / name).write_text(
            doc if isinstance(doc, str) else json.dumps(doc, indent=1), encoding="utf-8"
        )
    on = list(files) if enabled is None else enabled
    (folder / "enabled.json").write_text(
        json.dumps(
            {
                "format": ENABLED_FORMAT,
                "format_version": 1,
                "declarative": on,
                "plugins": plugins or [],
            }
        ),
        encoding="utf-8",
    )
    return folder


def with_extensions(project: Project, root: Path) -> Project:
    """Attach the extensions folder of `root` to a project that lives in memory."""
    project.extensions = manager.discover(root)
    assert project.extensions is not None and not project.extensions.issues, [
        i.render() for i in project.extensions.issues
    ]
    return project
