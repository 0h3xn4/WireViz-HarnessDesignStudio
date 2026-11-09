# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index,union-attr"
"""REQ-HARN-03: a loose cable end is an ordinary connector of the harness (M4a of the 2.0 programme,
D-200, D-201). The role `loose`, the library part `TBD-CONNECTOR`, the plans that make, plug, unplug
and decide one, the integrity errors, the origin that is worked out and never stored, the position
that is a mark outside the hash, the design-rule wording, and the property that any sequence of
those plans keeps the project valid and saves to the same hash.

The release gate is in `tests/test_loose_end_release.py`, the readiness check and the verifier in
`tests/test_loose_end_outputs.py`, the format step in `tests/test_loose_end_migration.py`."""

import json
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_design_studio.core import drc
from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.connector_edit import plan_edit_connector
from harness_design_studio.core.devices import connector_parts_to_choose
from harness_design_studio.core.edit import EditError, ops_set_connector_part
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.generation_status import generation_status
from harness_design_studio.core.integrity import IntegrityTracker, check_integrity
from harness_design_studio.core.io import layout
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.manual_harness import (
    LOOSE,
    TBD_PART_ID,
    loose_ends,
    plan_add_connector,
    plan_add_loose_end,
    plan_cable_from_port,
    plan_new_harness,
    plan_plug_loose_end,
    plan_resolve_loose_end,
    plan_unplug,
    propose_plug,
)
from harness_design_studio.core.model import DiagramMark, Link, Pin, PinPair, evolve
from harness_design_studio.core.origin import harness_link, harness_origin, harness_origins
from harness_design_studio.core.vcs.hashing import content_hash
from harness_design_studio.core.verify import verify_project
from tests.helpers import copy_project, pinout_project
from tests.loose_support import build_loose


def labelled():
    """mini3 with labelled pins on four ports and no harness (see `tests.helpers.pinout_project`)."""
    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    for cid, c in list(p.connectors.items()):
        p.connectors[cid] = evolve(c, pins=[evolve(x, interface_id=None) for x in c.pins])
    return p


def errors(p):
    return [i.render() for i in check_integrity(p) if i.severity == "error"]


@pytest.fixture(scope="module")
def loose_root(tmp_path_factory) -> Path:
    root = build_loose(tmp_path_factory.mktemp("loose") / "p")
    p = load_project(root).project
    generate_project(p)  # plans current: the release gate and the independent verifier ask for it
    save_project(p, root)
    return root


# ---- the plans --------------------------------------------------------------------------------


def test_a_cable_from_a_port_has_one_end_loose_and_is_an_ordinary_harness():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    h = p.harnesses[r.harness_id]
    near = next(c for c in h.connectors if c.id == r.near_id)
    end = next(c for c in h.connectors if c.id == r.loose_id)
    assert (h.generated, h.status, harness_origin(p, h.id)) == (False, "draft", "drawn")
    assert (near.role, near.mates_with) == ("cable", "OBC-J01")
    assert (end.role, end.mates_with, end.part_id) == (LOOSE, None, TBD_PART_ID)
    assert [x.id for x in end.pins] == ["1", "2", "3", "4"]  # the pins of the port with a signal
    assert [w.signal for w in h.wires] == ["TX+", "TX-", "RX+", "RX-"]
    assert errors(p) == []
    part = p.parts[TBD_PART_ID]
    assert (part.category, part.approval, part.unverified, part.pin_count) == (
        "connector",
        "pending",
        True,
        None,
    )  # no pin count: any number of pins is fine, nothing is invented


def test_the_tbd_part_is_added_once_and_put_back_when_it_is_gone():
    p = labelled()
    assert TBD_PART_ID not in p.parts
    first = plan_cable_from_port(p, "OBC-J01")
    assert any(isinstance(o, Put) and o.collection == "parts" for o in first.ops)
    apply_ops(p, first.ops)
    again = plan_cable_from_port(p, "PCDU-J02")
    assert not any(isinstance(o, Put) and o.collection == "parts" for o in again.ops)
    apply_ops(p, again.ops)
    del p.parts[TBD_PART_ID]  # a person took it away: the next plan that needs it adds it again
    apply_ops(p, plan_plug_loose_end(p, first.harness_id, first.loose_id, "RW1-J02"))
    ops = plan_unplug(p, first.harness_id, first.loose_id)
    assert [o.collection for o in ops if isinstance(o, Put)] == ["parts", "harnesses"]


def test_a_loose_end_is_not_a_role_the_old_plan_can_add():
    p = labelled()
    ops, hid = plan_new_harness(p, "By hand")
    apply_ops(p, ops)
    with pytest.raises(EditError, match="connector role is one of"):
        plan_add_connector(p, hid, part_id="EX-DSUB-9-M", role="loose")
    with pytest.raises(EditError, match="not a connector part"):
        plan_add_connector(p, hid, part_id=TBD_PART_ID)  # the stand-in is not one to choose


def test_plugging_pairs_by_signal_name_tx_to_rx_included():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    prop = propose_plug(p, r.harness_id, r.loose_id, "RW1-J02")
    assert prop.by == "signal"
    assert [(x.a_pin, x.b_pin) for x in prop.pairs] == [
        ("1", "3"),
        ("2", "4"),
        ("3", "1"),
        ("4", "2"),
    ]
    apply_ops(p, plan_plug_loose_end(p, r.harness_id, r.loose_id, "RW1-J02"))
    h = p.harnesses[r.harness_id]
    end = next(c for c in h.connectors if c.id == r.loose_id)
    assert (end.role, end.mates_with) == ("cable", "RW1-J02")
    assert end.part_id == p.parts[p.connectors["RW1-J02"].part_id].mates_with  # the mating part
    assert len(end.pins) == len(p.connectors["RW1-J02"].pins)  # every position of the port
    assert [(w.from_pin, w.to_pin) for w in h.wires] == [
        ("1", "3"),
        ("2", "4"),
        ("3", "1"),
        ("4", "2"),
    ]
    assert errors(p) == []


def test_plugging_by_number_where_the_names_disagree_is_refused_with_the_reason():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    other = p.connectors["PCDU-J02"]  # a port whose pins carry other names: only numbers can meet
    pins = [
        Pin(id="1", signal="PWR"),
        Pin(id="2", signal="RTN"),
        Pin(id="3"),
        Pin(id="4"),
        Pin(id="5"),
    ]
    p.connectors["PCDU-J02"] = evolve(other, pins=pins)
    prop = propose_plug(p, r.harness_id, r.loose_id, "PCDU-J02")
    assert prop.by == "number"
    assert any("carries TX+, but pin 1 of PCDU-J02 is named PWR" in n for n in prop.notes)
    assert len(prop.disagreements) == 2
    before = model_hash(p)
    with pytest.raises(EditError, match="carries TX\\+, but pin 1 of PCDU-J02 is named PWR"):
        plan_plug_loose_end(p, r.harness_id, r.loose_id, "PCDU-J02")
    assert model_hash(p) == before  # a plan only returns ops: nothing was half done
    # a person who pairs the pins by hand has decided: that is allowed, and the wires follow
    by_hand = [("1", "1"), ("2", "2"), ("3", "3"), ("4", "4")]
    apply_ops(p, plan_plug_loose_end(p, r.harness_id, r.loose_id, "PCDU-J02", pairs=by_hand))
    assert errors(p) == []


def test_a_loose_end_that_nothing_can_be_paired_with_is_refused():
    p = labelled()
    ops, hid = plan_new_harness(p, "By hand")
    apply_ops(p, ops)
    ops, cid = plan_add_loose_end(p, hid, pin_ids=["A", "B"])
    apply_ops(p, ops)
    assert propose_plug(p, hid, cid, "RW1-J02").by == "none"
    with pytest.raises(EditError, match="No pin of .* can be paired"):
        plan_plug_loose_end(p, hid, cid, "RW1-J02")


def test_a_pin_with_no_partner_whose_number_is_taken_is_refused_not_renumbered():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    with pytest.raises(EditError, match="has no partner"):
        plan_plug_loose_end(p, r.harness_id, r.loose_id, "PCDU-J02", pairs=[("1", "1")])


def test_a_port_pin_that_a_connection_already_pairs_is_not_offered():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    p.links["L1"] = Link(
        id="L1",
        a_connector="RW1-J02",
        b_connector="PCDU-J02",
        pairs=[PinPair(a_pin="3", b_pin="1")],
    )
    prop = propose_plug(p, r.harness_id, r.loose_id, "RW1-J02")
    assert "3" not in [x.b_pin for x in prop.pairs]
    assert any("already paired in link L1" in n for n in prop.notes)


def test_unplugging_gives_back_a_loose_end_and_keeps_pins_and_wires():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    apply_ops(p, plan_plug_loose_end(p, r.harness_id, r.loose_id, "RW1-J02"))
    wires = p.harnesses[r.harness_id].wires
    apply_ops(p, plan_unplug(p, r.harness_id, r.loose_id))
    h = p.harnesses[r.harness_id]
    end = next(c for c in h.connectors if c.id == r.loose_id)
    assert (end.role, end.mates_with, end.part_id, end.gender, end.keying) == (
        LOOSE,
        None,
        TBD_PART_ID,
        "unspecified",
        None,
    )
    assert h.wires == wires
    assert len(end.pins) == len(p.connectors["RW1-J02"].pins)
    assert errors(p) == []
    with pytest.raises(EditError, match="not plugged"):
        plan_unplug(p, r.harness_id, r.loose_id)


def test_the_near_end_of_a_cable_can_be_unplugged_too():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    apply_ops(p, plan_unplug(p, r.harness_id, r.near_id))
    assert len(loose_ends(p.harnesses[r.harness_id])) == 2
    assert errors(p) == []


def test_unplugging_a_harness_made_from_a_connection_is_refused_in_plain_words():
    from harness_design_studio.core.links import plan_add_link, plan_create_harness

    p = labelled()
    ops, link_id = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    ops, hid = plan_create_harness(p, link_id)
    apply_ops(p, ops)
    assert harness_origin(p, hid) == "link" and harness_link(p, hid) == link_id
    for c in p.harnesses[hid].connectors:
        with pytest.raises(EditError, match=f"made from the connection {link_id}"):
            plan_unplug(p, hid, c.id)
    assert "link_harness_not_mated" not in {i.code for i in check_integrity(p)}


def test_resolving_a_loose_end_gives_it_a_part_without_plugging_it():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    with pytest.raises(EditError, match="not chosen yet"):
        plan_resolve_loose_end(p, r.harness_id, r.loose_id, TBD_PART_ID)
    apply_ops(p, plan_resolve_loose_end(p, r.harness_id, r.loose_id, "EX-DSUB-9-M"))
    end = next(c for c in p.harnesses[r.harness_id].connectors if c.id == r.loose_id)
    assert (end.role, end.mates_with, end.part_id) == ("cable", None, "EX-DSUB-9-M")
    assert loose_ends(p.harnesses[r.harness_id]) == []
    assert errors(p) == []


def test_choosing_a_part_in_the_connector_editor_resolves_the_end_too():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    with pytest.raises(EditError, match="not chosen yet"):
        plan_edit_connector(p, r.harness_id, r.loose_id, part_id=TBD_PART_ID)
    apply_ops(p, plan_edit_connector(p, r.harness_id, r.loose_id, part_id="EX-DSUB-9-F"))
    end = next(c for c in p.harnesses[r.harness_id].connectors if c.id == r.loose_id)
    assert (end.role, end.part_id) == ("cable", "EX-DSUB-9-F")
    assert end.gender == "female"  # what the part says
    assert errors(p) == []
    # a name or a keying alone does not decide an end
    q = labelled()
    s = plan_cable_from_port(q, "OBC-J01")
    apply_ops(q, s.ops)
    apply_ops(q, plan_edit_connector(q, s.harness_id, s.loose_id, keying="A"))
    assert [c.role for c in q.harnesses[s.harness_id].connectors if c.id == s.loose_id] == [LOOSE]


def test_the_stand_in_part_is_not_offered_and_cannot_be_chosen_for_a_device():
    p = labelled()
    apply_ops(p, plan_cable_from_port(p, "OBC-J01").ops)
    assert TBD_PART_ID in p.parts
    assert TBD_PART_ID not in {x.id for x in connector_parts_to_choose(p)}
    assert "EX-DSUB-9-M" in {x.id for x in connector_parts_to_choose(p)}
    with pytest.raises(EditError, match="not a connector part"):
        ops_set_connector_part(p, "OBC-J01", TBD_PART_ID)


def test_generated_and_released_harnesses_refuse_loose_ends():
    from harness_design_studio.core.samples import sat15

    p = sat15()
    generate_project(p)
    hid = next(h.id for h in p.harnesses.values() if h.generated)
    with pytest.raises(EditError, match="made by Generate"):
        plan_add_loose_end(p, hid, pin_ids=["1"])


def test_undo_of_a_cable_from_a_port_is_one_step():
    p = labelled()
    before = model_hash(p)
    h = History(p)
    h.execute("cable", plan_cable_from_port(p, "OBC-J01").ops)
    assert model_hash(p) != before
    h.undo()
    assert model_hash(p) == before


# ---- integrity --------------------------------------------------------------------------------


def test_integrity_says_nothing_of_a_valid_loose_end_and_errors_on_a_malformed_one():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    assert [i for i in check_integrity(p) if i.severity != "info"] == []
    h = p.harnesses[r.harness_id]
    bad = [evolve(c, mates_with="RW1-J02") if c.id == r.loose_id else c for c in h.connectors]
    apply_ops(p, [Put("harnesses", evolve(h, connectors=bad))])
    assert [i.code for i in check_integrity(p) if i.severity == "error"] == ["loose_end_mated"]
    # a harness Generate makes may not hold a loose end (Generate would replace it)
    apply_ops(p, [Put("harnesses", evolve(h, generated=True))])
    assert "loose_end_in_generated_harness" in {
        i.code for i in check_integrity(p) if i.severity == "error"
    }


def test_a_connection_cannot_say_it_made_a_harness_that_generate_makes():
    """The origin of a harness is worked out from `generated` and the connection that names it, so
    a harness that is both is the one combination with two answers: a warning (not an error, so that
    a project that already has such a link is not blocked; generated wins)."""
    from harness_design_studio.core.links import plan_add_link, plan_create_harness

    p = labelled()
    ops, link_id = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    ops, hid = plan_create_harness(p, link_id)
    apply_ops(p, ops)
    assert errors(p) == []
    apply_ops(p, [Put("harnesses", evolve(p.harnesses[hid], generated=True))])
    assert errors(p) == []  # (a warning: such a link is not blocked)
    found = [i for i in check_integrity(p) if i.code == "origin_mismatch"]
    assert [i.severity for i in found] == ["warning"]
    assert "Generate makes" in found[0].message and link_id in found[0].message
    assert harness_origin(p, hid) == "interfaces"  # generated wins, and the warning says so


def test_the_incremental_integrity_tracker_agrees_on_loose_end_errors():
    p = labelled()
    tracker = IntegrityTracker(p)
    h = History(p)
    r = plan_cable_from_port(p, "OBC-J01")
    h.execute("cable", r.ops)
    assert not tracker.errors()
    hh = p.harnesses[r.harness_id]
    bad = [evolve(c, mates_with="RW1-J02") if c.id == r.loose_id else c for c in hh.connectors]
    apply_ops(p, [Put("harnesses", evolve(hh, connectors=bad))])
    keys = {k[1] for k in tracker.errors()}
    assert "loose_end_mated" in keys
    apply_ops(p, [Put("harnesses", hh)])
    assert not tracker.errors()


# ---- the origin: worked out, never stored ----------------------------------------------------


def test_origin_is_interfaces_link_or_drawn_and_is_never_written_to_a_file():
    from harness_design_studio.core.links import plan_add_link, plan_create_harness
    from harness_design_studio.core.samples import sat15

    p = labelled()
    apply_ops(p, plan_cable_from_port(p, "OBC-J01").ops)
    ops, link_id = plan_add_link(p, "PCDU-J02", "OBC-J02")
    apply_ops(p, ops)
    ops, linked = plan_create_harness(p, link_id)
    apply_ops(p, ops)
    origins = harness_origins(p)
    assert sorted(origins.values()) == ["drawn", "link"] and origins[linked] == "link"
    q = sat15()
    generate_project(q)
    assert set(harness_origins(q).values()) == {"interfaces"}
    for project in (p, q):
        for rel, data in layout.serialize(project).items():
            if rel.startswith("physical/harnesses/"):
                assert b'"origin"' not in data  # nothing is stored: no hash, no export moves


def test_a_project_without_a_loose_end_hashes_as_it_did(tmp_path):
    """The hash goldens of the migration safety net (made on master before this change) hold."""
    from tests.migration_support import build, hashes_of

    gold = json.loads(
        (Path(__file__).parent / "fixtures" / "migration" / "hashes.json").read_text()
    )
    for name in ("mini3", "example-flatsat", "released", "links"):
        assert hashes_of(build(name, tmp_path / name)) == gold[name]


def test_the_tbd_part_does_not_make_the_generated_plans_stale():
    from harness_design_studio.core.samples import sat15

    p = sat15()
    generate_project(p)
    assert generation_status(p) == "current"
    free = next(c.id for c in p.connectors.values() if c.role == "box")
    apply_ops(p, plan_cable_from_port(p, free).ops)  # adds the part TBD-CONNECTOR and a harness
    assert TBD_PART_ID in p.parts
    assert generation_status(p) == "current"


# ---- the file ---------------------------------------------------------------------------------


def test_save_and_reload_give_the_same_hash_and_the_same_bytes(loose_root, tmp_path):
    a = load_project(loose_root).project
    dest = tmp_path / "again"
    save_project(a, dest)
    b = load_project(dest).project
    assert model_hash(a) == model_hash(b) == model_hash(load_project(loose_root).project)
    assert content_hash(a) == content_hash(b)
    for rel, data in layout.serialize(a).items():
        assert (dest / rel).read_bytes() == data or rel == "project.json"
    assert len(loose_ends(b.harnesses["W009"])) == 1
    assert b.harnesses["W009"].wires == a.harnesses["W009"].wires


def test_the_position_of_a_loose_end_is_a_mark_outside_the_hash(loose_root, tmp_path):
    root = copy_project(loose_root, tmp_path / "p")
    p = load_project(root).project
    before = (model_hash(p), content_hash(p))
    apply_ops(p, [Put("diagram_marks", DiagramMark(id="pos:W009-P2", dx=120.0, dy=-40.0))])
    assert (model_hash(p), content_hash(p)) == before  # moving it does not make outputs stale
    save_project(p, root)
    assert json.loads((root / "diagram" / "marks.json").read_text())["marks"] == [
        {"dx": 120.0, "dy": -40.0, "id": "pos:W009-P2"}
    ]
    q = load_project(root).project
    assert q.diagram_marks["pos:W009-P2"].dx == 120.0
    with pytest.raises(ValueError, match="not for a bend, a route or a loose end"):
        DiagramMark(id="pos:W009-P2", t=0.5)  # an offset, never a position along a line
    # the mark goes with the connector: orphan marks are dropped, not kept for ever
    h = q.harnesses["W009"]
    apply_ops(
        q,
        [
            Put(
                "harnesses",
                evolve(h, connectors=[c for c in h.connectors if c.id != "W009-P2"], wires=[]),
            )
        ],
    )
    assert layout.mark_is_orphan(q, "pos:W009-P2")
    assert not layout.mark_is_orphan(load_project(root).project, "pos:W009-P2")


# ---- the checks and the rest of the tool over the project -------------------------------------


def test_generate_leaves_every_harness_a_person_drew(loose_root, tmp_path):
    root = copy_project(loose_root, tmp_path / "p")
    p = load_project(root).project
    drawn = {h.id: h for h in p.harnesses.values() if not h.generated}
    assert len(drawn) == 5
    generate_project(p)
    assert all(p.harnesses[k] == v for k, v in drawn.items())


def test_the_design_rule_asks_for_a_choice_not_an_approval(loose_root):
    p = load_project(loose_root).project
    hits = [f for f in drc.run(p) if f.rule == "part-unapproved" and "TBD" in f.object_id]
    assert len(hits) == 1
    assert "cable end(s) have no connector chosen yet (loose end)" in hits[0].title
    assert "not approved" not in hits[0].title
    assert hits[0].severity == "warning"
    assert len(drc.RULES) == 39  # no new rule


def test_the_rest_of_the_design_checks_run_over_the_project_without_a_crash(loose_root):
    p = load_project(loose_root).project
    assert errors(p) == []
    assert [i for i in verify_project(p).issues if i.severity == "error"] == []


def test_explain_of_a_harness_with_a_loose_end_names_the_ninth_check(loose_root):
    """The crash the spike found: `explain` looked a check up by its label and the ninth had none."""
    from harness_design_studio.core.derive import explain_object
    from harness_design_studio.core.derive_build import CHECK_MEANING
    from harness_design_studio.core.outputs import buildsheet

    p = load_project(loose_root).project
    text = "\n".join(str(d) for d in explain_object(p, "W013"))
    assert "Ends not decided" in text and "always blocks" in text
    labels = [label for label, _ in buildsheet.READINESS_CHECKS] + [buildsheet.LOOSE_CHECK[0]]
    assert set(labels) <= set(CHECK_MEANING)  # every check the sheet can show has its meaning
    plain = "\n".join(str(d) for d in explain_object(p, "W001"))
    assert "eight checks" in plain and "Ends not decided" not in plain


# ---- property ---------------------------------------------------------------------------------

_PORTS = ("OBC-J01", "OBC-J02", "PCDU-J02", "RW1-J02", "PCDU-J03")


@settings(
    max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    steps=st.lists(
        st.tuples(st.sampled_from("cpurd"), st.sampled_from(_PORTS), st.integers(0, 3)), max_size=14
    )
)
def test_any_sequence_of_cable_plug_unplug_resolve_keeps_the_project_valid_and_saves_to_the_same_hash(
    steps, tmp_path_factory
):
    p = labelled()
    h = History(p)
    for kind, port, k in steps:
        made = sorted(x.id for x in p.harnesses.values() if not x.generated)
        hid = made[k % len(made)] if made else None
        try:
            if kind == "c":
                h.execute("cable", plan_cable_from_port(p, port).ops)
            elif hid is None:
                continue
            else:
                hh = p.harnesses[hid]
                end = loose_ends(hh)
                plugged = [c for c in hh.connectors if c.role == "cable" and c.mates_with]
                if kind == "p" and end:
                    h.execute("plug", plan_plug_loose_end(p, hid, end[0].id, port))
                elif kind == "u" and plugged:
                    h.execute("unplug", plan_unplug(p, hid, plugged[-1].id))
                elif kind == "r" and end:
                    h.execute("resolve", plan_resolve_loose_end(p, hid, end[0].id, "EX-DSUB-9-M"))
                elif kind == "d":
                    h.undo()
        except EditError:
            continue  # a plan may refuse (a taken number, a full part); it must never half-do it
        assert errors(p) == []
    dest = tmp_path_factory.mktemp("prop") / "p"
    save_project(p, dest)
    q = load_project(dest).project
    assert model_hash(q) == model_hash(p)
    assert {k: v for k, v in q.harnesses.items()} == {k: v for k, v in p.harnesses.items()}
    assert errors(q) == []
    if any(not x.generated for x in q.harnesses.values()):
        report = verify_project(q)
        assert [i for i in report.issues if i.severity == "error"] == []
