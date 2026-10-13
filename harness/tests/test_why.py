# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""SC-8 / CV-23: the recorded reasons of generation as a list, and what is still pending."""

from pathlib import Path

import pytest

from harness_design_studio.core import templates, why
from harness_design_studio.core.generate.explain import explain_harness, explain_wire
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.model import Project, evolve


@pytest.fixture(scope="module")
def flat(tmp_path_factory) -> Project:
    folder = tmp_path_factory.mktemp("why") / "flat"
    templates.create_project(folder, "flatsat")
    return load_project(folder).project


def a_wire(p: Project):
    h = p.harnesses["W001"]
    return h, h.wires[0]


def test_a_line_is_split_into_rule_and_sentence() -> None:
    r = why.parse_line("wiring: PWR of IF-010 connects A pin 1 to B pin 1 (X drives)")
    assert (r.rule, r.where) == ("wiring", "")
    assert r.text.startswith("PWR of IF-010") and r.line.startswith("wiring: PWR")
    pin = why.parse_line("PDU2-J02 pin 1: pin-allocation: PWR of IF-010 (power and return grouped)")
    assert (pin.where, pin.rule) == ("PDU2-J02 pin 1", "pin-allocation")
    assert pin.line.startswith("PDU2-J02 pin 1: pin-allocation: ")
    bare = why.parse_line("Something without a rule")
    assert (bare.rule, bare.text) == ("", "Something without a rule")


def test_a_wire_has_the_reasons_explain_wire_logs(flat: Project) -> None:
    h, w = a_wire(flat)
    got = [r.line for r in why.reasons(flat, "wire", w.id)]
    assert got == list(dict.fromkeys(explain_wire(flat, h, w)))
    assert {"wiring", "wire-sizing", "segmentation"} <= {
        r.rule for r in why.reasons(flat, "wire", w.id)
    }


def test_a_harness_has_the_reasons_explain_harness_logs(flat: Project) -> None:
    h = flat.harnesses["W001"]
    got = why.reasons(flat, "harness", h.id)
    assert [r.line for r in got] == explain_harness(flat, h)
    assert got and got[0].rule == "segmentation"


def test_a_cable_connector_says_which_box_connector_it_mates_with(flat: Project) -> None:
    c = flat.harnesses["W001"].connectors[0]
    got = why.reasons(flat, "connector", c.id)
    assert got and got[0].rule == "mating" and (c.mates_with or "") in got[0].text


def test_a_box_connector_collects_the_reasons_of_its_pins(flat: Project) -> None:
    box = next(c for c in flat.connectors.values() if any(p.interface_id for p in c.pins))
    got = why.reasons(flat, "connector", box.id)
    assert got and all(r.where.startswith(box.id + " pin ") for r in got)


def test_a_pin_of_a_box_or_of_the_cable_end_has_the_same_reasons(flat: Project) -> None:
    cable = flat.harnesses["W001"].connectors[0]
    pin = cable.pins[0].id
    via_cable = why.reasons(flat, "pin", f"{cable.id}.{pin}")
    via_box = why.reasons(flat, "pin", f"{cable.mates_with}.{pin}")
    assert via_cable == via_box
    assert via_box and via_box[0].rule == "pin-allocation"


def test_connector_and_pin_ids_with_dots_still_resolve(flat: Project) -> None:
    assert why.split_pin(flat, "PDU2-J02.1") == ("PDU2-J02", "1")
    assert why.split_pin(flat, "nothing.1") is None
    assert why.find_connector(flat, "PDU2-J02") == (None, True)
    h, is_box = why.find_connector(flat, "W001-P1") or (None, True)
    assert h is not None and h.id == "W001" and not is_box


def test_a_unit_gathers_the_pin_reasons_of_its_connectors(flat: Project) -> None:
    uid = next(
        c.unit_id
        for c in flat.connectors.values()
        if c.unit_id and any(p.interface_id for p in c.pins)
    )
    got = why.reasons(flat, "unit", uid or "")
    assert got and {r.rule for r in got} == {"pin-allocation"}


def test_an_interface_gathers_its_harness_wires_and_pins(flat: Project) -> None:
    got = why.reasons(flat, "interface", "IF-010")
    rules = {r.rule for r in got}
    assert {"segmentation", "wiring", "wire-sizing", "pin-allocation"} <= rules


def test_unknown_objects_have_no_reasons(flat: Project) -> None:
    for kind in why.KINDS:
        assert why.reasons(flat, kind, "no-such-thing") == []
    assert why.reasons(flat, "config", "derating") == []
    assert why.why_text(flat, "wire", "no-such-thing") == ""


def test_reasons_are_never_repeated(flat: Project) -> None:
    got = [r.line for r in why.reasons(flat, "interface", "IF-010")]
    assert len(got) == len(set(got))


def test_why_text_has_the_first_lines_and_says_how_many_more(flat: Project) -> None:
    h, w = a_wire(flat)
    all_lines = [r.line for r in why.reasons(flat, "wire", w.id)]
    text = why.why_text(flat, "wire", w.id, limit=2)
    assert text.splitlines()[:2] == all_lines[:2]
    assert text.splitlines()[2] == f"… and {len(all_lines) - 2} more"
    assert why.why_text(flat, "wire", w.id, limit=99).splitlines()[: len(all_lines)] == all_lines


def test_a_wire_without_gauge_or_length_says_what_it_waits_for(flat: Project) -> None:
    from harness_design_studio.core import edit

    h, w = a_wire(flat)
    bare = evolve(w, gauge_awg=None, length_m=None)
    q = edit.clone_with(flat, [])
    q.harnesses["W001"] = evolve(h, wires=[bare, *h.wires[1:]])
    got = why.pending_reasons(q, "wire", w.id)
    assert len(got) == 2
    assert "gauge is pending" in got[0] and "length is pending" in got[1]
    assert why.pending_reasons(flat, "wire", w.id) == ([] if w.gauge_awg and w.length_m else got)


def test_an_unconfirmed_connector_choice_is_pending(flat: Project) -> None:
    from harness_design_studio.core import edit

    q = edit.clone_with(flat, [])
    iid = next(i for i, x in q.interfaces.items() if all(e.connector_id for e in x.endpoints))
    i = q.interfaces[iid]
    ends = [evolve(i.endpoints[0], auto=True), *i.endpoints[1:]]
    q.interfaces[iid] = evolve(i, endpoints=ends)
    cid = ends[0].connector_id or ""
    got = why.pending_reasons(q, "connector", cid)
    assert got and "not confirmed" in got[0] and iid in got[0]
    assert why.pending_reasons(q, "interface", iid)


def test_placeholders_used_are_listed_for_generated_objects_only(flat: Project) -> None:
    h, w = a_wire(flat)
    assert flat.generation is not None and flat.generation.placeholders_used
    assert why.placeholders_used(flat, "wire", w.id) == sorted(flat.generation.placeholders_used)
    assert why.placeholders_used(flat, "wire", "nope") == []


def test_the_module_reads_only(flat: Project, tmp_path: Path) -> None:
    before = (flat.generation, dict(flat.harnesses), dict(flat.interfaces))
    why.reasons(flat, "interface", "IF-010")
    why.pending_reasons(flat, "wire", a_wire(flat)[1].id)
    assert (flat.generation, dict(flat.harnesses), dict(flat.interfaces)) == before
