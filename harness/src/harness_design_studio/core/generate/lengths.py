"""Wire lengths from routing segments, and CSV import of segment lengths (from CAD exports)."""

import re
from collections import deque
from dataclasses import dataclass, field

from harness_design_studio.core.commands import Op, Put
from harness_design_studio.core.imports import Table
from harness_design_studio.core.model import Harness, Project, Segment, Wire, evolve


def path_length(h: Harness, start: str, end: str) -> float | None:
    """Sum of segment lengths along the (unique) path in the harness tree; None if any is unknown."""
    graph: dict[str, list[tuple[str, float | None]]] = {}
    for s in h.segments:
        graph.setdefault(s.from_node, []).append((s.to_node, s.length_m))
        graph.setdefault(s.to_node, []).append((s.from_node, s.length_m))
    seen = {start}
    queue: deque[tuple[str, list[float | None]]] = deque([(start, [])])
    while queue:
        node, trail = queue.popleft()
        if node == end:
            return (
                None
                if any(x is None for x in trail)
                else float(sum(x for x in trail if x is not None))
            )
        for nxt, length in graph.get(node, []):
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, [*trail, length]))
    return None


_PATHS: dict[tuple[int, str, str], tuple[Harness, float | None]] = {}
_PATHS_LIMIT = (
    512  # the cache keeps its harnesses alive: bounded, so a long editing session cannot grow it
)


def clear_length_cache() -> None:
    _PATHS.clear()


def wire_length(h: Harness, w: Wire) -> float | None:
    """The wire's own length, else the sum of routing segments between its connectors.
    The one place that answers 'how long is this wire' (tables, mass, rules and the release gate)."""
    if w.length_m is not None:
        return w.length_m
    if not h.segments:
        return None
    key = (id(h), w.from_connector, w.to_connector)
    hit = _PATHS.get(key)
    if hit is None or hit[0] is not h:  # the identity check guards against reused object ids
        if len(_PATHS) >= _PATHS_LIMIT:
            _PATHS.clear()
        hit = _PATHS[key] = (h, path_length(h, w.from_connector, w.to_connector))
    return hit[1]


@dataclass
class LengthRow:
    row_number: int
    ok: bool
    message: str
    values: tuple[str, ...]


@dataclass
class LengthPlan:
    rows: list[LengthRow] = field(default_factory=list)
    ops: list[Op] = field(default_factory=list)
    hint: str = ""  # shown after the row messages when they all share one likely cause


_NUMBER = re.compile(r"[0-9]+([.,][0-9]+)?|[.,][0-9]+")  # no exponents, signs or underscores
MAX_LENGTH_M = 10_000.0


def plan_length_import(
    project: Project,
    table: Table,
    columns: tuple[int, int, int] = (0, 1, 2),
    scale: float = 1.0,
) -> LengthPlan:
    """Rows: harness ID, segment ID, length. `scale` converts the file's unit to metres (0.001 for
    millimetres, D-13). Applies as one undo step after confirmation."""
    plan = LengthPlan()
    if table and len(table[0]) > columns[2] and _NUMBER.fullmatch(table[0][columns[2]].strip()):
        plan.rows.append(
            LengthRow(
                1,
                False,
                "The first row must be the column headings (harness, segment, length), not data",
                tuple(table[0][c] if c < len(table[0]) else "" for c in columns),
            )
        )
        return plan
    pending: dict[str, Harness] = {}
    for n, row in enumerate(table[1:], start=2):
        vals = tuple(row[c].strip() if c < len(row) else "" for c in columns)
        hid, sid, text = vals
        error = ""
        h = pending.get(hid) or project.harnesses.get(hid)
        if h is None:
            error = f"Harness '{hid}' does not exist"
        elif h.status == "released":
            error = f"Harness '{hid}' is released and locked"
        elif sid not in {s.id for s in h.segments}:
            error = f"Harness '{hid}' has no segment '{sid}'"
        else:
            try:
                if not _NUMBER.fullmatch(text.strip()):
                    raise ValueError
                length = round(float(text.strip().replace(",", ".")) * scale, 9)
                if not 0 <= length <= MAX_LENGTH_M:
                    raise ValueError
            except ValueError:
                error = f"'{text}' is not a length (digits with a decimal point or comma)"
        if not error and h is not None:
            segs = [evolve(s, length_m=length) if s.id == sid else s for s in h.segments]
            pending[hid] = evolve(h, segments=segs)
        plan.rows.append(LengthRow(n, not error, error, vals))
    plan.ops = [Put("harnesses", h) for h in pending.values()]
    if plan.rows and all(r.message.endswith("does not exist") for r in plan.rows):
        # the columns are read by position, so a file with another order fails on every row
        # with a message about the harness name, which hides the real cause
        head = ", ".join(c.strip() or "(empty)" for c in table[0][:3])
        plan.hint = (
            "Every row failed on the harness name. The columns are read by position: harness, "
            f"segment, length. The headings of the file read: {head}. If they are in another "
            "order, reorder the columns and try again."
        )
    return plan


def segment_lengths_known(h: Harness) -> bool:
    return bool(h.segments) and all(s.length_m is not None for s in h.segments)


__all__ = [
    "LengthPlan",
    "LengthRow",
    "Segment",
    "path_length",
    "plan_length_import",
    "segment_lengths_known",
]
