"""Recorded deviations and overrides, as lines for the places that must show them (S4, D-191 (3)).

A **deviation** is an error of an electrical rule that a person has accepted with a reason: it is a
waiver of an error (`checks.deviate_op`). The finding stays on every list and every output, marked
as a deviation. An **override** is a value of a wire set by hand in place of the design's value
(`Wire.overrides`). Both are shown in the written outputs only when the project has one, so a
project that has none is written as before; the lines carry the reason but never a name or a time
(those are in the journal, which no output holds).
"""

from harness_design_studio.core.checks import Finding
from harness_design_studio.core.model import Harness, Project, Wire

MAX_REASON = 120


def _cut(text: str, limit: int = MAX_REASON) -> str:
    one = " ".join(text.split())
    return one if len(one) <= limit else one[: limit - 3] + "..."


def deviation_rules() -> frozenset[str]:
    from harness_design_studio.core.drc.rules import RULES

    return frozenset(r.id for r in RULES if r.can_deviate)


def may_have_deviations(project: Project) -> bool:
    """A cheap test: is there a waiver of a rule whose errors can be deviations? (No rule runs.)"""
    if not project.waivers:
        return False
    rules = deviation_rules()
    return any(w.rule in rules for w in project.waivers.values())


def active_deviations(project: Project, findings: list[Finding] | None = None) -> list[Finding]:
    """The findings accepted as deviations, by ID. `findings` are those of a check that ran."""
    if findings is None:
        if not may_have_deviations(project):
            return []
        from harness_design_studio.core import drc

        findings = drc.run(project)
    return sorted((f for f in findings if f.deviation), key=lambda f: f.id)


def deviation_line(f: Finding) -> str:
    reason = f.waiver.justification if f.waiver is not None else ""
    return f"DEVIATION {f.id}: {f.title} (accepted, reason: {_cut(reason, 200)})"


def deviation_lines(project: Project, h: Harness | None = None) -> list[str]:
    """One line for each deviation of the project, or of the harness `h` when given."""
    from harness_design_studio.core import drc

    out = []
    for f in active_deviations(project):
        if h is not None and drc.locate(project, f.object_id) != ("harness", h.id):
            continue
        out.append(deviation_line(f))
    return out


def uses_overrides(project: Project) -> bool:
    """True when any wire has an override with a reason: the tables and sheets then get the extra
    column or section; a project without one is written as before."""
    return any(w.overrides for h in project.harnesses.values() for w in h.wires)


def override_text(w: Wire) -> str:
    """The overrides of one wire in a cell: `gauge_awg: reason; length_m: reason`."""
    return "; ".join(f"{f}: {_cut(w.overrides[f])}" for f in sorted(w.overrides))


def override_lines(h: Harness) -> list[str]:
    """One line for each overridden value of the harness: wire, field, value and reason."""
    out = []
    for w in sorted(h.wires, key=lambda x: x.id):
        for f in sorted(w.overrides):
            out.append(f"OVERRIDE {w.id} {f} = {getattr(w, f)}: {_cut(w.overrides[f], 200)}")
    return out


def _deviation_wires(h: Harness, object_id: str) -> list[str]:
    """The wires of `h` that a finding is about: the wire itself; the wires of the interface for a
    finding on `INTERFACE.CONNECTOR` (a contact, connector voltage); the wires that end on a cable
    connector (the temperature margin of a connector part)."""
    head = object_id.partition(".")[0] if "." in object_id else ""
    return [
        w.id
        for w in h.wires
        if object_id in (w.id, w.from_connector, w.to_connector)
        or (head != "" and head == w.interface_id)
    ]


def wire_marks(project: Project, h: Harness) -> dict[str, str]:
    """For each wire of the harness that has an override or a deviation: the text of the
    `Deviations` cell of the tests of that wire (`tests.csv`, the Tests sheet), for example
    `override gauge_awg: reason; deviation current-over-wire: reason`. Empty for a project that has
    neither, so its tests are written as before. No name and no time (those are in the journal)."""
    marks: dict[str, list[str]] = {}
    for w in h.wires:
        for field in sorted(w.overrides):
            marks.setdefault(w.id, []).append(f"override {field}: {_cut(w.overrides[field])}")
    for dev in active_deviations(project):
        reason = dev.waiver.justification if dev.waiver is not None else ""
        for wid in _deviation_wires(h, dev.object_id):
            marks.setdefault(wid, []).append(f"deviation {dev.rule}: {_cut(reason)}")
    return {wid: "; ".join(parts) for wid, parts in marks.items()}


def tests_cell(marks: dict[str, str], wire_ids: str) -> str:
    """The `Deviations` cell of one test row: `wire_ids` is the Wire cell (one ID, or the IDs of a
    shield joined with `;`). A shield row names the wire in front of each mark."""
    ids = [x for x in wire_ids.split(";") if x]
    if len(ids) == 1:
        return marks.get(ids[0], "")
    return " | ".join(f"{x}: {marks[x]}" for x in ids if x in marks)


def tests_band(project: Project, h: Harness) -> list[str]:
    """The lines of the band above the tests of a harness (the Tests sheet): every override of the
    harness and every deviation located in it or about one of its wires (empty if there is none)."""
    from harness_design_studio.core import drc

    lines = override_lines(h)
    for f in active_deviations(project):
        if drc.locate(project, f.object_id) == ("harness", h.id) or _deviation_wires(
            h, f.object_id
        ):
            lines.append(deviation_line(f))
    return lines


def release_note(project: Project, h: Harness) -> str:
    """The sentence added to the comment of a release when the harness has overrides or the project
    has deviations ('' otherwise), so the release record shows them."""
    parts = []
    lines = override_lines(h)
    if lines:
        shown = "; ".join(x.removeprefix("OVERRIDE ") for x in lines[:4])
        more = f" and {len(lines) - 4} more" if len(lines) > 4 else ""
        parts.append(f"{len(lines)} overridden value(s): {_cut(shown, 300)}{more}")
    dev = deviation_lines(project, h)
    if dev:
        shown = "; ".join(x.removeprefix("DEVIATION ") for x in dev[:3])
        more = f" and {len(dev) - 3} more" if len(dev) > 3 else ""
        parts.append(f"{len(dev)} deviation(s): {_cut(shown, 400)}{more}")
    return f" [Released with {'; '.join(parts)}]" if parts else ""
