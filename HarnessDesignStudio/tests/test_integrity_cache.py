"""The integrity check reuses results for unchanged objects; it must never hide a new problem."""

from harness_design_studio.core.commands import Delete, Put, apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.model import evolve
from harness_design_studio.core.samples import sat15


def codes(p) -> set[str]:  # type: ignore[no-untyped-def]
    return {i.code for i in check_integrity(p)}


def test_cache_never_hides_new_problems_and_forgets_fixed_ones() -> None:
    p = sat15()
    generate_project(p)
    assert codes(p) == set()
    assert codes(p) == set()  # second run answers from the cache
    h = next(iter(p.harnesses.values()))
    w = h.wires[0]
    good = h
    apply_ops(
        p, [Put("harnesses", evolve(h, wires=[evolve(w, to_connector="NOPE"), *h.wires[1:]]))]
    )
    assert "dangling_wire" in codes(p)
    apply_ops(p, [Put("harnesses", good)])
    assert codes(p) == set()
    # a change somewhere else that the cached results depend on
    part = p.parts[good.connectors[0].part_id]
    apply_ops(p, [Put("parts", evolve(part, pin_count=1))])
    assert "too_many_pins" in codes(p)
    apply_ops(p, [Put("parts", part)])
    assert codes(p) == set()
    iid = next(iter(p.interfaces))
    apply_ops(p, [Delete("interfaces", iid)])
    assert "orphan_pin_assignment" in codes(p) or "unknown_interface" in codes(p)
