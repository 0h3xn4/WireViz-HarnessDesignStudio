"""REQ-OUT-07 (decision D-184): a cable pin shows the signal and the interface of the wires that
end on it (a pin of its own keeps what it has), and the wire list and the traceability matrix get a
`Requirement` column while any interface has a requirement ID. A project without requirement IDs
keeps those two tables as they were, and the independent verifier checks each new cell."""

import copy

import pytest

from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.outputs import tables
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import sat15_full

H = "W001"
REQ = "REQ-PWR-001"


@pytest.fixture(scope="module")
def plain() -> Project:
    return sat15_full()


@pytest.fixture(scope="module")
def plain_files(plain: Project) -> dict[str, bytes]:
    return build_outputs(plain, drawings=False).files


def _with_requirement(p: Project) -> Project:
    """The sample with a requirement ID on the interface of the first wire of W001."""
    q = copy.deepcopy(p)
    w = sorted(q.harnesses[H].wires, key=lambda x: x.id)[0]
    assert w.interface_id
    i = q.interfaces[w.interface_id]
    apply_ops(q, [Put("interfaces", evolve(i, requirement_id=REQ))])
    return q


@pytest.fixture(scope="module")
def project(plain: Project) -> Project:
    return _with_requirement(plain)


@pytest.fixture(scope="module")
def built(project: Project) -> dict[str, bytes]:
    return build_outputs(project, drawings=False).files


def _csv(files: dict[str, bytes], rel: str) -> list[list[str]]:
    return parse_csv(files[rel])


def _codes(project: Project, files: dict[str, bytes]) -> set[str]:
    return {i.code for i in verify_outputs(project, files).issues}


def _edited(project: Project, files: dict[str, bytes], rel: str, row: int, col: int, value: str) -> dict[str, bytes]:  # fmt: skip
    table = _csv(files, rel)
    table[row][col] = value
    return {**files, rel: csv_bytes(table, stamp_of(project))}


# ---- Signal and Interface on cable pins ----------------------------------------------------------


def test_a_cable_pin_shows_the_signal_and_interface_of_its_wire(plain: Project, plain_files: dict[str, bytes]) -> None:  # fmt: skip
    rows = _csv(plain_files, f"harnesses/{H}/pinouts.csv")
    by = {(r[0], r[4]): r for r in rows[1:]}
    for w in plain.harnesses[H].wires:
        for conn, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
            row = by[(conn, pin)]
            assert w.signal in row[5].split(";") and w.interface_id in row[6].split(";")
    spare = [r for r in rows[1:] if r[-1] == "yes"]
    assert spare and all(r[5] == "" and r[6] == "" for r in spare)


def test_two_signals_on_one_pin_are_joined_sorted_and_without_repeats(plain: Project) -> None:
    p = copy.deepcopy(plain)
    h = p.harnesses[H]
    a, b = sorted(h.wires, key=lambda x: x.id)[:2]
    wires = [
        evolve(x, to_connector=a.to_connector, to_pin=a.to_pin) if x.id == b.id else x
        for x in h.wires
    ]  # fmt: skip
    apply_ops(p, [Put("harnesses", evolve(h, wires=wires))])
    cell = {(r[0], r[4]): r for r in tables.pinouts(p, p.harnesses[H])[1:]}[(a.to_connector, a.to_pin)]  # fmt: skip
    assert cell[5] == ";".join(sorted({s for s in (a.signal, b.signal) if s})) and cell[6] == ";".join(
        sorted({x for x in (a.interface_id, b.interface_id) if x})
    )  # fmt: skip


def test_a_pin_with_a_signal_of_its_own_keeps_it(plain: Project) -> None:
    p = copy.deepcopy(plain)
    h = p.harnesses[H]
    w = sorted(h.wires, key=lambda x: x.id)[0]
    conns = [
        evolve(c, pins=[evolve(q, signal="OWN", interface_id="IF-OWN") if q.id == w.from_pin else q for q in c.pins])
        if c.id == w.from_connector else c
        for c in h.connectors
    ]  # fmt: skip
    apply_ops(p, [Put("harnesses", evolve(h, connectors=conns))])
    row = {(r[0], r[4]): r for r in tables.pinouts(p, p.harnesses[H])[1:]}[(w.from_connector, w.from_pin)]  # fmt: skip
    assert row[5] == "OWN" and row[6] == "IF-OWN"


def test_the_box_pinouts_are_as_they_were(plain: Project, plain_files: dict[str, bytes]) -> None:
    rows = _csv(plain_files, "system/box_pinouts.csv")
    assert rows[0][5:7] == ["Signal", "Interface"]


def test_the_verifier_checks_the_signal_and_interface_cells(plain: Project, plain_files: dict[str, bytes]) -> None:  # fmt: skip
    rel = f"harnesses/{H}/pinouts.csv"
    assert verify_outputs(plain, plain_files).ok
    rows = _csv(plain_files, rel)
    used = next(n for n, r in enumerate(rows) if n and r[-1] == "no")
    assert "out_pinout" in _codes(plain, _edited(plain, plain_files, rel, used, 5, "WRONG"))
    assert "out_pinout" in _codes(plain, _edited(plain, plain_files, rel, used, 6, "IF-WRONG"))
    assert "out_pinout" in _codes(plain, _edited(plain, plain_files, rel, used, 5, ""))


# ---- the Requirement column ----------------------------------------------------------------------


def test_a_project_without_requirement_ids_has_no_requirement_column(plain: Project, plain_files: dict[str, bytes]) -> None:  # fmt: skip
    for rel, data in plain_files.items():
        if rel.endswith(("wirelist.csv", "traceability.csv")):
            assert "Requirement" not in parse_csv(data)[0], rel


def test_the_wire_list_gets_the_requirement_column_after_the_emc_class(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    rows = _csv(built, f"harnesses/{H}/wirelist.csv")
    at = rows[0].index("Requirement")
    assert at == 13 + (1 if "EMC class" in rows[0] else 0)
    by = {r[0]: r for r in rows[1:]}
    w = sorted(project.harnesses[H].wires, key=lambda x: x.id)[0]
    assert by[w.id][at] == REQ
    other = _csv(built, "harnesses/W002/wirelist.csv")  # its interface has no requirement ID
    assert other[0].index("Requirement") == at and all(r[at] == "" for r in other[1:])
    assert tables.requirement_of(project, w) == REQ


def test_the_traceability_matrix_gets_the_requirement_column_before_kind(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    rows = _csv(built, "system/traceability.csv")
    head = rows[0]
    at = head.index("Requirement")
    assert head[at - 1] == "Routed" and (at == len(head) - 1 or head[at + 1] == "Kind")
    by = {r[0]: r for r in rows[1:]}
    iid = sorted(i.id for i in project.interfaces.values() if i.requirement_id)[0]
    assert by[iid][at] == REQ
    assert all(r[at] == "" for r in rows[1:] if r[0] != iid)


def test_the_outputs_with_requirement_ids_verify(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    report = verify_outputs(project, built)
    assert report.ok, [i.message for i in report.issues]


def test_the_verifier_checks_the_requirement_cells(project: Project, built: dict[str, bytes]) -> None:  # fmt: skip
    rel = f"harnesses/{H}/wirelist.csv"
    at = _csv(built, rel)[0].index("Requirement")
    row = next(n for n, r in enumerate(_csv(built, rel)) if r[at] == REQ)
    assert "out_wire_differs" in _codes(project, _edited(project, built, rel, row, at, "REQ-X"))
    assert "out_wire_differs" in _codes(project, _edited(project, built, rel, row, at, ""))
    trace = "system/traceability.csv"
    tat = _csv(built, trace)[0].index("Requirement")
    trow = next(n for n, r in enumerate(_csv(built, trace)) if r[tat] == REQ)
    assert "out_trace" in _codes(project, _edited(project, built, trace, trow, tat, "REQ-X"))


def test_the_verifier_checks_the_requirement_columns_exist_exactly_when_used(project: Project, built: dict[str, bytes], plain: Project, plain_files: dict[str, bytes]) -> None:  # fmt: skip
    rel = f"harnesses/{H}/wirelist.csv"
    table = _csv(built, rel)
    at = table[0].index("Requirement")
    gone = [r[:at] + r[at + 1 :] for r in table]
    assert "out_wire_differs" in _codes(project, {**built, rel: csv_bytes(gone, stamp_of(project))})  # fmt: skip
    plain_table = _csv(plain_files, rel)
    added = [[*r[:13], "Requirement" if n == 0 else "", *r[13:]] for n, r in enumerate(plain_table)]  # fmt: skip
    assert "out_wire_differs" in _codes(plain, {**plain_files, rel: csv_bytes(added, stamp_of(plain))})  # fmt: skip
