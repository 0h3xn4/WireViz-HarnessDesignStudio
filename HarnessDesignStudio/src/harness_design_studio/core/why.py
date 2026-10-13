"""Why an object is the way it is: the recorded reasons of generation, shaped for a view.

Pure functions of the project (no Qt). The reasons are the ones generation logged (`explain_wire`,
`explain_harness` and the provenance lines for connectors and pins); nothing is guessed. A line
is "rule: sentence" and is split into the rule and the sentence. Alongside them come the reasons
a value is still *pending* (no gauge, no length, a connector the tool chose and nobody
confirmed) and the placeholder configuration the generated result rests on, so a view can show
"not known yet" next to "known and why".

    reasons(project, "wire", "W001-001")      -> [Reason("wiring", "PWR of IF-010 ..."), ...]
    pending_reasons(project, "wire", "W001-001")
    why_text(project, "connector", "W001-P1")  -> first lines as text, for a tooltip
"""

import re
from dataclasses import dataclass

from harness_design_studio.core import configcheck
from harness_design_studio.core.generate.explain import explain_harness, explain_wire
from harness_design_studio.core.model import Harness, Project
from harness_design_studio.core.vcs.snapshot import carried_interfaces

KINDS = ("unit", "interface", "harness", "wire", "connector", "pin")
_LINE = re.compile(r"^(?:(?P<where>\S+ pin \S+): )?(?P<rule>[a-z][a-z0-9-]*): (?P<text>.+)$")


@dataclass(frozen=True)
class Reason:
    """One recorded reason: the rule that decided, the sentence, and (for a line about a pin of
    something else) which pin."""

    rule: str
    text: str
    where: str = ""

    @property
    def line(self) -> str:
        """ "rule: sentence", with the pin first when the line is about one ("J1 pin 3: ...")."""
        base = f"{self.rule}: {self.text}" if self.rule else self.text
        return f"{self.where}: {base}" if self.where else base


def parse_line(line: str) -> Reason:
    """Split a provenance line into rule and sentence (a line without a rule keeps its text)."""
    m = _LINE.match(line)
    if m is None:
        return Reason("", line)
    return Reason(m.group("rule"), m.group("text"), m.group("where") or "")


def _prov(project: Project) -> dict[str, list[str]]:
    return project.generation.provenance if project.generation else {}


def _harness_of_wire(project: Project, wire_id: str) -> tuple[Harness, int] | None:
    for h in project.harnesses.values():
        for k, w in enumerate(h.wires):
            if w.id == wire_id:
                return h, k
    return None


def find_connector(project: Project, connector_id: str) -> tuple[Harness | None, bool] | None:
    """(harness, is_box) of a connector: a box connector has no harness, a cable connector
    belongs to one. None when there is no such connector."""
    if connector_id in project.connectors:
        return None, True
    for h in project.harnesses.values():
        if any(c.id == connector_id for c in h.connectors):
            return h, False
    return None


def split_pin(project: Project, pin_id: str) -> tuple[str, str] | None:
    """("connector", "pin") of a "connector.pin" ID; connector and pin IDs may contain dots, so
    each split is tried until the connector exists."""
    parts = pin_id.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        conn = ".".join(parts[:cut])
        if find_connector(project, conn) is not None:
            return conn, ".".join(parts[cut:])
    return None


def _lines(project: Project, keys: list[tuple[str, str]]) -> list[str]:
    prov = _prov(project)
    out: list[str] = []
    for key, where in keys:
        out.extend(where + line for line in prov.get(key, []))
    return out


def _box_pins(project: Project, box_id: str) -> list[tuple[str, str]]:
    box = project.connectors.get(box_id)
    if box is None:
        return []
    return [(f"pin:{box_id}.{p.id}", f"{box_id} pin {p.id}: ") for p in box.pins]


def raw_lines(project: Project, kind: str, object_id: str) -> list[str]:
    """The provenance lines about an object, in a stable order."""
    p = project
    if kind == "wire":
        found = _harness_of_wire(p, object_id)
        return explain_wire(p, found[0], found[0].wires[found[1]]) if found else []
    if kind == "harness":
        h = p.harnesses.get(object_id)
        return explain_harness(p, h) if h else []
    if kind == "connector":
        located = find_connector(p, object_id)
        if located is None:
            return []
        if not located[1]:
            return _lines(p, [(f"connector:{object_id}", "")])
        return _lines(p, _box_pins(p, object_id))
    if kind == "pin":
        split = split_pin(p, object_id)
        if split is None:
            return []
        conn, pin = split
        h, is_box = find_connector(p, conn) or (None, True)
        box = conn
        if not is_box and h is not None:
            cable = next(c for c in h.connectors if c.id == conn)
            box = cable.mates_with or conn
        return _lines(p, [(f"pin:{box}.{pin}", "")])
    if kind == "unit":
        keys: list[tuple[str, str]] = []
        for c in sorted(p.connectors.values(), key=lambda c: c.id):
            if c.unit_id == object_id:
                keys.extend(_box_pins(p, c.id))
        return _lines(p, keys)
    if kind == "interface":
        i = p.interfaces.get(object_id)
        if i is None:
            return []
        keys = []
        for h in sorted(p.harnesses.values(), key=lambda x: x.id):
            if object_id in carried_interfaces(h):
                keys.append((f"harness:{h.id}", ""))
                keys.extend((f"wire:{w.id}", "") for w in h.wires if w.interface_id == object_id)
                keys.extend((f"gauge:{w.id}", "") for w in h.wires if w.interface_id == object_id)
        for c in sorted(p.connectors.values(), key=lambda c: c.id):
            keys.extend(
                (f"pin:{c.id}.{pin.id}", f"{c.id} pin {pin.id}: ")
                for pin in c.pins
                if pin.interface_id == object_id
            )
        return _lines(p, keys)
    return []


def reasons(project: Project, kind: str, object_id: str) -> list[Reason]:
    """The recorded reasons for an object of one of `KINDS`, each once, in the order generation
    logged them. Empty when nothing was generated for it."""
    seen: set[str] = set()
    out: list[Reason] = []
    for line in raw_lines(project, kind, object_id):
        if line not in seen:
            seen.add(line)
            out.append(parse_line(line))
    return out


# ---- what is still pending ---------------------------------------------------------------------


def _missing_for(project: Project, topic: str) -> list[str]:
    return [n.key for n in configcheck.missing(project) if topic in n.used_by]


def _wire_pending(project: Project, wire_id: str) -> list[str]:
    found = _harness_of_wire(project, wire_id)
    if found is None:
        return []
    w = found[0].wires[found[1]]
    out = []
    if w.gauge_awg is None:
        keys = _missing_for(project, "wire sizing")
        out.append(
            "The wire gauge is pending: wire sizing needs "
            + (", ".join(keys) if keys else "values that are not set yet")
            + "."
        )
    if w.length_m is None:
        out.append(
            "The length is pending: it comes from the segment lengths, which are not given yet."
        )
    return out


def _connector_pending(project: Project, connector_id: str) -> list[str]:
    out = []
    for i in sorted(project.interfaces.values(), key=lambda x: x.id):
        for e in i.endpoints:
            if e.connector_id == connector_id and e.auto:
                out.append(
                    f"The tool chose {connector_id} for {i.id}; it is not confirmed yet. "
                    "Confirm it in the inspector."
                )
    return out


def pending_reasons(project: Project, kind: str, object_id: str) -> list[str]:
    """Sentences that say why a value of this object is not known yet. Empty when nothing is
    pending."""
    if kind == "wire":
        return _wire_pending(project, object_id)
    if kind == "connector":
        return _connector_pending(project, object_id)
    if kind == "pin":
        split = split_pin(project, object_id)
        return _connector_pending(project, split[0]) if split else []
    if kind == "interface":
        i = project.interfaces.get(object_id)
        if i is None:
            return []
        out = [
            f"The connector at {e.unit_id} was chosen by the tool and is not confirmed yet."
            for e in i.endpoints
            if e.auto
        ]
        if i.voltage_v is None and i.max_current_a is None:
            t = project.interface_types.get(i.type_id)
            if t is not None and t.category == "power":
                out.append(
                    "Voltage and current are pending: nobody entered them for this power link."
                )
        return out
    return []


def placeholders_used(project: Project, kind: str, object_id: str) -> list[str]:
    """Configuration files still holding placeholder values that generation used, for an object
    generation made a decision about (it has recorded reasons). Empty otherwise."""
    if not reasons(project, kind, object_id) or project.generation is None:
        return []
    return sorted(project.generation.placeholders_used)


def why_text(project: Project, kind: str, object_id: str, limit: int = 3) -> str:
    """The first `limit` reasons as lines ("rule: sentence"), then "... and N more"; the
    pending reasons follow. For a tooltip. Empty when there is nothing to say."""
    lines = [r.line for r in reasons(project, kind, object_id)]
    shown = lines[:limit]
    if len(lines) > limit:
        shown.append(f"… and {len(lines) - limit} more")
    shown.extend(pending_reasons(project, kind, object_id))
    return "\n".join(shown)
