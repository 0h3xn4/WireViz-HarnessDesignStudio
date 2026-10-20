# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""The state index must not scan every wire for every finding (11 s at stress size, D-154)."""

import time

import pytest

from harness_design_studio.core import drc
from harness_design_studio.core.checks import Finding
from harness_design_studio.gui.canvas_state import _resolver, build_index
from tests.helpers import time_limit
from tools.bench_stress import build

# the second test measures time, so the first rides along in the serial run
pytestmark = pytest.mark.perf


def _finding(oid: str, n: int) -> Finding:
    return Finding(f"f{n}", "r", "warning", oid, "t", "w")


def reference(project, oid: str):
    """What the resolver did before: `drc.locate` for every other ID."""
    got = None
    where = drc.locate(project, oid)
    if where is not None and where[0] in ("unit", "interface"):
        got = [where]
    return got


def test_the_resolver_answers_as_drc_locate_does_for_every_kind_of_id() -> None:
    p = build(units=12, interfaces=30, harnesses=6, wires=120)
    wire = next(w for h in p.harnesses.values() for w in h.wires)
    hconn = next((c for h in p.harnesses.values() for c in h.connectors), None)
    part = next(iter(p.parts))
    ids = [
        "U001", "IF0003", "U003-J01", wire.id, hconn.id if hconn else "none", next(iter(p.harnesses)),
        f"wire-spec.{part}", f"mating-cycles.{part}", "emc-class.x.U002", "emc-class.x.nope",
        f"shield-parts.{next(iter(p.harnesses))}.x", "U001.something", "nothing", "a.b.c",
        f"{wire.id}.signal", f"{wire.id}.x.y",
    ]  # fmt: skip
    resolve = _resolver(p)
    for oid in ids:
        where = drc.locate(p, oid)
        expected = [where] if where is not None and where[0] in ("unit", "interface") else None
        got = resolve(oid)
        if expected is not None:
            assert got == expected, oid
        else:  # the resolver's own fall-backs (a wire of a link) apply to both
            assert all(k in ("unit", "interface") for k, _ in got), oid


def test_building_the_index_for_many_wire_findings_is_fast() -> None:
    p = build()
    wires = [w.id for h in p.harnesses.values() for w in h.wires]
    findings = [_finding(w, n) for n, w in enumerate(wires)]
    t = time.perf_counter()
    build_index(p, findings, {}, checked=True)
    took = time.perf_counter() - t
    assert took < time_limit(3), took
