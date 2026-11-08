"""Has the design changed since the harnesses were generated? A hash comparison, no generation
logic, so the verifier and the release checks can use it without importing the generator."""

import hashlib
import json
from typing import Any

from .model import ConfigFile, Project
from .model.config import ABOUT_KEY
from .vcs.roles import CONFIG_FILE as ROLES_FILE
from .vcs.roles import CONFIG_KEY as ROLES_KEY

# Keys that generation does not read (who may release, what a release asks of the as-built records,
# what the as-built report tolerates): switching one on, off or to another value does not make the
# harness plans out of date, and without any of them the dump is what it always was.
NOT_READ_BY_GENERATION: dict[str, tuple[str, ...]] = {
    ROLES_FILE: (ROLES_KEY, "release_requires_asbuilt"),
    "generation": ("asbuilt_cut_tolerance_mm", "asbuilt_strip_tolerance_mm"),
}


def _config_dump(c: ConfigFile) -> dict[str, Any]:
    """One config file as generation reads it, without the keys it does not read
    (`NOT_READ_BY_GENERATION`; `release_distinct_roles`, 1.9.0, was the first). The comments of the
    file (`_about`) are not an input either."""
    d = c.model_dump(mode="json")
    d.pop(ABOUT_KEY, None)
    skip = NOT_READ_BY_GENERATION.get(c.name, ())
    if any(k in c.values for k in skip):
        d["values"] = {k: v for k, v in d["values"].items() if k not in skip}
    return d


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
        # SPIKE M4: the library part of a loose end is added by the first cable a person drags out
        # of a port; Generate never reads it, so it must not make the plans look out of date
        "parts": dump(x for x in project.parts.values() if x.id != "TBD-CONNECTOR"),
        "zones": list(project.zones),
        "config": {n: _config_dump(c) for n, c in sorted(project.config.items())},
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
