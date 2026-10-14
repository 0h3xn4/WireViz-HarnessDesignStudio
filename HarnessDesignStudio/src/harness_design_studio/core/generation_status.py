"""Has the design changed since the harnesses were generated? A hash comparison, no generation
logic, so the verifier and the release checks can use it without importing the generator."""

import hashlib
import json
from typing import Any

from .model import Project


def input_hash(project: Project) -> str:
    """Hash of everything generation reads. Outputs (generated pins, wires) are excluded."""

    def dump(objs: Any) -> list[object]:
        return [o.model_dump(mode="json") for o in sorted(objs, key=lambda x: x.id)]

    boxes = []
    for c in sorted(project.connectors.values(), key=lambda x: x.id):
        d = c.model_dump(mode="json")
        d["pins"] = [
            {
                **p.model_dump(mode="json"),
                "interface_id": None,
                "signal": p.signal if (p.locked or p.fixed or p.interface_id is None) else None,
            }
            for p in c.pins
        ]
        boxes.append(d)
    generated = [h for h in project.harnesses.values() if h.generated]
    payload: dict[str, Any] = {
        "units": dump(project.units.values()),
        "interfaces": dump(project.interfaces.values()),
        "interface_types": dump(project.interface_types.values()),
        "parts": dump(project.parts.values()),
        "zones": list(project.zones),
        "config": {n: c.model_dump(mode="json") for n, c in sorted(project.config.items())},
        "box_connectors": boxes,
        "locked_wires": sorted(
            (w.model_dump(mode="json") for h in generated for w in h.wires if w.locked),
            key=lambda d: d["id"],
        ),
        "segment_lengths": {
            h.id: sorted((s.id, s.length_m) for s in h.segments) for h in generated
        },
    }
    # Interfaces that manual harnesses route are left out of generation. Only added when there are
    # any, so a project without manual harnesses keeps its hash. Never the release status.
    manual = sorted(
        {
            w.interface_id
            for h in project.harnesses.values()
            if not h.generated
            for w in h.wires
            if w.interface_id
        }
    )
    if manual:
        payload["manual_interfaces"] = manual
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def generation_status(project: Project) -> str:
    """ "none" (never generated), "current" or "stale" (the model changed since)."""
    if project.generation is None:
        return "none"
    return "current" if project.generation.input_hash == input_hash(project) else "stale"
