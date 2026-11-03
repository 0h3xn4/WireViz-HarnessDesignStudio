"""How many wires make the bundle of a wire: the number the bundle factor K is looked up for (S3).

The model of the tool until D-191 was **every wire of the harness** (`all_wires`): the bundle is the
whole harness, signal wires and unloaded wires included, each taken as fully loaded; this is
conservative and is the default. Two alternatives are selectable with the setting
`model.bundle_basis`:

- `loaded_wires`: only the wires that carry a current (their interface has a Max current) count, so
  a harness with many signal wires and a few power wires is not derated by the signal wires;
- `busiest_segment`: the bundle of a wire is the busiest routing segment of its path: the largest
  number of wires that run through one segment the wire runs through. A wire with no path (no
  routing segments, or none that connects its connectors) takes every wire of the harness.

The counting is one pure function (`bundle_counts`), used by generation (for the wires it is about to
make) and by the design rules and the explanations (for the wires of a harness), so the three cannot
disagree. The assumption is A-BUNDLE-ALL (`core.assumptions`).
"""

from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass

from harness_design_studio.core import settings
from harness_design_studio.core.generate.lengths import path_trail
from harness_design_studio.core.model import Harness, Project, Wire

BASES = ("all_wires", "loaded_wires", "busiest_segment")
BASIS_TEXT = {
    "all_wires": "every wire of the harness",
    "loaded_wires": "the wires that carry a current",
    "busiest_segment": "the busiest routing segment of the path of the wire",
}


@dataclass(frozen=True)
class BundleWire:
    """What the count needs to know about a wire."""

    key: Hashable
    loaded: bool  # it carries a current: its interface has a Max current
    segments: tuple[str, ...] | None  # the IDs of the segments of its path; None: no path known


def basis(project: Project) -> str:
    value = settings.effective(project, "model", "bundle_basis").value
    return str(value) if value in BASES else "all_wires"


def bundle_counts(basis_name: str, wires: Sequence[BundleWire]) -> dict[Hashable, int]:
    """The bundle size of each wire, by the basis chosen. Pure."""
    n = len(wires)
    if basis_name == "loaded_wires":
        m = sum(1 for w in wires if w.loaded)
        return {w.key: m for w in wires}
    if basis_name == "busiest_segment":
        use: Counter[str] = Counter()
        for w in wires:
            use.update(set(w.segments or ()))
        return {
            w.key: max((use[s] for s in w.segments), default=n) if w.segments else n for w in wires
        }
    return {w.key: n for w in wires}


def _wire_info(project: Project, h: Harness, w: Wire) -> BundleWire:
    i = project.interfaces.get(w.interface_id or "")
    trail = path_trail(h, w.from_connector, w.to_connector) if h.segments else None
    return BundleWire(
        w.id,
        i is not None and i.max_current_a is not None,
        None if trail is None else tuple(sid for sid, _ in trail),
    )


_SIZES: dict[int, tuple[Harness, str, dict[Hashable, int]]] = {}
_SIZES_LIMIT = 256  # bounded, like the cache of the lengths


def clear_cache() -> None:
    _SIZES.clear()


def bundle_sizes(project: Project, h: Harness) -> dict[Hashable, int]:
    """The bundle size of every wire of a harness (by wire ID) under the basis of the project."""
    name = basis(project)
    if name == "all_wires":
        return dict.fromkeys((w.id for w in h.wires), len(h.wires))
    hit = _SIZES.get(id(h))
    if hit is None or hit[0] is not h or hit[1] != name:  # the identity check guards reused ids
        if len(_SIZES) >= _SIZES_LIMIT:
            _SIZES.clear()
        counts = bundle_counts(name, [_wire_info(project, h, w) for w in h.wires])
        hit = _SIZES[id(h)] = (h, name, counts)
    return hit[2]


def bundle_size(project: Project, h: Harness, w: Wire) -> int:
    """How many wires make the bundle of this wire (the bundle factor K is looked up for it)."""
    return bundle_sizes(project, h).get(w.id, len(h.wires))
