"""REQ-OUT-07 (decision D-188): a wire part can say how many conductors one metre of it carries
(`conductors`, 2 for a twisted pair). Every wire that names the part is one conductor of it, so the
BOM and the mass count the sum of the wire lengths divided by that number: the metres of the cable.
A part that does not say it counts as before, the field is left out of the file while it is 1, and
the independent output check counts the same way."""

import copy
import json

import pytest

from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.generate import mass
from harness_design_studio.core.library_import import guess_mapping, plan_parts_import
from harness_design_studio.core.model import Part, Project, evolve
from harness_design_studio.core.outputs import tables
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import sat15_full
from harness_design_studio.core.starter import starter_parts

PAIR = "EX-WIRE-TWISTED-SHIELDED"


def _project(conductors: int) -> Project:
    p = copy.deepcopy(sat15_full())
    apply_ops(p, [Put("parts", evolve(p.parts[PAIR], conductors=conductors))])
    return p


def _pair_metres(p: Project, harness_id: str) -> tuple[float, int]:
    """The summed length of the wires that name the pair part, and how many there are."""
    h = p.harnesses[harness_id]
    wires = [w for w in h.wires if w.part_id == PAIR]
    from harness_design_studio.core.generate.lengths import wire_length

    return sum(wire_length(h, w) or 0.0 for w in wires), len(wires)


def _harness_with_pairs(p: Project) -> str:
    return next(hid for hid in sorted(p.harnesses) if _pair_metres(p, hid)[1] > 0)


def _bom_metres(p: Project, harness_id: str) -> float:
    rows = tables.bom(p, [p.harnesses[harness_id]])
    return float(next(r for r in rows[1:] if r[0] == PAIR)[6])


def test_a_part_without_the_field_counts_as_one_conductor_and_is_left_out_of_the_file() -> None:
    part = Part(id="X", category="wire")
    assert part.conductors == 1 and "conductors" not in json.loads(part.model_dump_json())
    two = evolve(part, conductors=2)
    assert json.loads(two.model_dump_json())["conductors"] == 2


def test_conductors_must_be_a_whole_number_from_1_to_64() -> None:
    for bad in (0, 65, -1):
        with pytest.raises(ValueError):
            Part(id="X", category="wire", conductors=bad)


def test_the_starter_pair_part_has_two_conductors_and_the_single_wire_one() -> None:
    by_id = {p.id: p for p in starter_parts()}
    assert by_id[PAIR].conductors == 2 and by_id["EX-WIRE-SINGLE"].conductors == 1


def test_the_bom_counts_the_metres_of_the_cable_not_of_every_conductor() -> None:
    one, two = _project(1), _project(2)
    hid = _harness_with_pairs(one)
    total, n = _pair_metres(one, hid)
    assert n >= 2 and total > 0
    assert _bom_metres(one, hid) == pytest.approx(total, abs=0.01)
    assert _bom_metres(two, hid) == pytest.approx(total / 2, abs=0.01)


def test_the_system_bom_and_the_mass_follow() -> None:
    one, two = _project(1), _project(2)
    hid = _harness_with_pairs(one)
    m1 = mass.harness_mass(one, one.harnesses[hid]).total_g
    m2 = mass.harness_mass(two, two.harnesses[hid]).total_g
    total, _n = _pair_metres(one, hid)
    per_m = one.parts[PAIR].mass_per_m_g or 0.0
    assert per_m > 0 and m1 - m2 == pytest.approx(per_m * total / 2, abs=0.01)


def test_the_outputs_of_a_project_with_pair_parts_verify() -> None:
    p = _project(2)
    report = verify_outputs(p, build_outputs(p, drawings=False).files)
    assert report.ok, [i.message for i in report.issues]


def test_the_verifier_checks_the_pair_part_metres() -> None:
    p = _project(2)
    files = build_outputs(p, drawings=False).files
    hid = _harness_with_pairs(p)
    rel = f"harnesses/{hid}/bom.csv"
    table = parse_csv(files[rel])
    row = next(r for r in table[1:] if r[0] == PAIR)
    total, _n = _pair_metres(p, hid)
    row[6] = f"{total:g}"  # every conductor counted, as before 1.11
    bad = {**files, rel: csv_bytes(table, stamp_of(p))}
    assert "out_bom" in {i.code for i in verify_outputs(p, bad).issues}


def test_the_parts_import_reads_a_conductors_column_for_wire_parts_only() -> None:
    p = copy.deepcopy(sat15_full())
    header = ["Part ID", "Category", "Approval", "Conductors"]
    table = [
        header,
        ["TWP-1", "wire", "ok", "2"],
        ["TWP-2", "wire", "ok", "0"],
        ["TWP-3", "wire", "ok", "two"],
        ["CON-1", "connector", "ok", "2"],
    ]
    plan = plan_parts_import(p, table, guess_mapping(header), approved=["ok"])
    assert [r.ok for r in plan.rows] == [True, False, False, True]
    assert "Conductors" in plan.rows[1].message and "Conductors" in plan.rows[2].message
    History(p).execute("import", plan.ops)
    assert p.parts["TWP-1"].conductors == 2 and p.parts["CON-1"].conductors == 1
