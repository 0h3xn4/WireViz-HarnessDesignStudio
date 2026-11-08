# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index,union-attr"
"""SPIKE M4 (throw-away reference, not a release): a loose cable end as an ordinary connector.

What these tests pin down is what the spike found, so the report (docs/ait/SPIKE_M4_LOOSE_END.md) can
be checked against running code. They are not the tests of the real M4."""

import json
import re
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_design_studio.core import drc
from harness_design_studio.core.commands import History, Put, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io import layout, upgrade
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
from harness_design_studio.core.model import DiagramMark, Pin, evolve
from harness_design_studio.core.outputs.build import build_outputs, write_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.vcs.hashing import content_hash
from harness_design_studio.core.vcs.release import plan_release
from harness_design_studio.core.verify import verify_project
from tests.helpers import copy_project, pinout_project
from tests.loose_support import build_loose
from tests.migration_support import build, install_fake_format, noop_step


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


# ---- 1. the plans -----------------------------------------------------------------------------


def test_a_cable_from_a_port_has_one_end_loose_and_is_an_ordinary_harness():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    h = p.harnesses[r.harness_id]
    near = next(c for c in h.connectors if c.id == r.near_id)
    end = next(c for c in h.connectors if c.id == r.loose_id)
    assert (h.origin, h.generated, h.status) == ("drawn", False, "draft")
    assert (near.role, near.mates_with) == ("cable", "OBC-J01")
    assert (end.role, end.mates_with, end.part_id) == (LOOSE, None, TBD_PART_ID)
    assert [x.id for x in end.pins] == [
        "1",
        "2",
        "3",
        "4",
    ]  # the pins of the port that have a signal
    assert [w.signal for w in h.wires] == ["TX+", "TX-", "RX+", "RX-"]
    assert errors(p) == []
    part = p.parts[TBD_PART_ID]
    assert (part.category, part.approval, part.unverified, part.pin_count) == (
        "connector",
        "pending",
        True,
        None,
    )  # no pin count: any number of pins is fine, nothing is invented


def test_tbd_part_is_added_once_and_only_on_first_use():
    p = labelled()
    assert TBD_PART_ID not in p.parts
    apply_ops(p, plan_cable_from_port(p, "OBC-J01").ops)
    again = plan_cable_from_port(p, "PCDU-J02")
    assert not any(isinstance(o, Put) and o.collection == "parts" for o in again.ops)


def test_a_loose_end_is_not_a_connector_role_a_person_can_add_by_the_old_plan():
    p = labelled()
    ops, hid = plan_new_harness(p, "By hand")
    apply_ops(p, ops)
    with pytest.raises(EditError, match="connector role is one of"):
        plan_add_connector(p, hid, part_id="EX-DSUB-9-M", role="loose")


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


def test_plugging_by_number_says_where_the_names_disagree():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    # a port whose pins carry other names: only the numbers can meet
    other = p.connectors["PCDU-J02"]
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


def test_a_pin_with_no_partner_whose_number_is_taken_is_refused_not_renumbered():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    with pytest.raises(EditError, match="has no partner"):
        plan_plug_loose_end(p, r.harness_id, r.loose_id, "PCDU-J02", pairs=[("1", "1")])


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


def test_resolving_a_loose_end_gives_it_a_part_without_plugging_it():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    with pytest.raises(EditError, match="not a connector part"):
        plan_resolve_loose_end(p, r.harness_id, r.loose_id, TBD_PART_ID)
    apply_ops(p, plan_resolve_loose_end(p, r.harness_id, r.loose_id, "EX-DSUB-9-M"))
    assert loose_ends(p.harnesses[r.harness_id]) == []


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


# ---- 2. integrity -----------------------------------------------------------------------------


def test_integrity_says_nothing_of_a_valid_loose_end_and_errors_on_a_malformed_one():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    assert [i for i in check_integrity(p) if i.severity != "info"] == []
    h = p.harnesses[r.harness_id]
    bad = [evolve(c, mates_with="RW1-J02") if c.id == r.loose_id else c for c in h.connectors]
    apply_ops(p, [Put("harnesses", evolve(h, connectors=bad))])
    assert [i.code for i in check_integrity(p) if i.severity == "error"] == ["loose_end_mated"]
    # a generated harness may not hold one, and may not claim another origin
    apply_ops(p, [Put("harnesses", evolve(h, generated=True))])
    assert {i.code for i in check_integrity(p) if i.severity == "error"} >= {
        "loose_end_in_generated_harness",
        "origin_mismatch",
    }


# ---- 3. the file ------------------------------------------------------------------------------


def test_origin_is_left_out_of_the_file_while_it_is_interfaces_and_written_otherwise():
    p = labelled()
    r = plan_cable_from_port(p, "OBC-J01")
    apply_ops(p, r.ops)
    files = layout.serialize(p)
    hf = json.loads(files[f"physical/harnesses/{r.harness_id}.json"])
    assert hf["origin"] == "drawn"
    q = pinout_project()
    for rel, data in layout.serialize(q).items():
        if rel.startswith("physical/harnesses/"):
            assert b'"origin"' not in data  # a harness of Generate: the file is as it was


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


def test_a_project_without_a_loose_end_hashes_as_it_did(tmp_path):
    """The hash goldens of the migration safety net (made on master) hold: nothing here is dense."""
    gold = json.loads(
        (Path(__file__).parent / "fixtures" / "migration" / "hashes.json").read_text()
    )
    from tests.migration_support import hashes_of

    for name in ("mini3", "example-flatsat", "released"):
        assert hashes_of(build(name, tmp_path / name)) == gold[name]


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


# ---- 4. everything over the project ----------------------------------------------------------


def test_generate_leaves_every_harness_a_person_drew(loose_root, tmp_path):
    root = copy_project(loose_root, tmp_path / "p")
    p = load_project(root).project
    drawn = {h.id: h for h in p.harnesses.values() if not h.generated}
    assert len(drawn) == 5
    generate_project(p)
    assert all(p.harnesses[k] == v for k, v in drawn.items())


def test_the_independent_verifier_passes_every_written_output_of_the_project(loose_root, tmp_path):
    p = load_project(loose_root).project
    write_outputs(p, tmp_path / "outputs")
    report = verify_outputs(p, build_outputs(p).files)
    assert [e for e in report.issues if e.severity == "error"] == []
    assert [e for e in verify_project(p).issues if e.severity == "error"] == []


def test_the_wording_of_the_outputs_for_a_loose_end(loose_root):
    p = load_project(loose_root).project
    files = build_outputs(p).files
    pin = files["harnesses/W009/pinouts.csv"].decode()
    assert "W009-P2,loose,open end,TBD-CONNECTOR (loose end),1,PWR" in pin
    assert "W009-P2 open end" in files["harnesses/W009/labels.csv"].decode()
    bom = files["harnesses/W009/bom.csv"].decode()
    assert "(open end),connector,,,Connector not chosen yet (loose end),to fill in,1,ea" in bom
    assert "TBD-CONNECTOR" not in bom  # it is not a part anyone buys
    sheet = {k: v for k, v in files.items() if k.endswith("W013_build.xlsx")}
    assert sheet  # (the cell values are in tests of the verifier above)


def test_a_complete_harness_with_a_loose_end_is_not_ready_to_build(loose_root):
    from harness_design_studio.core.outputs import buildsheet

    p = load_project(loose_root).project
    checks = {c.label: c for c in buildsheet.readiness(p, p.harnesses["W013"])}
    assert checks["Wires without a length"].open == 0  # every wire is complete ...
    assert checks["Ends not decided"].open == 1 and checks["Ends not decided"].blocking
    assert "Ends not decided" not in {c.label for c in buildsheet.readiness(p, p.harnesses["W001"])}


def test_the_drc_asks_for_a_choice_not_an_approval(loose_root):
    p = load_project(loose_root).project
    hits = [f for f in drc.run(p) if "TBD" in f.object_id]
    assert hits and "loose end" in hits[0].title
    assert "not approved" not in hits[0].title


def test_explain_of_a_harness_with_a_loose_end_does_not_crash(loose_root):
    from harness_design_studio.core.derive import explain_object

    p = load_project(loose_root).project
    text = "\n".join(str(d) for d in explain_object(p, "W013"))
    assert "Ends not decided" in text


def test_the_loose_end_changes_only_the_outputs_that_say_something_about_it(loose_root):
    """The 34 files that read the ends of a wire need no change: resolve every loose end to a real
    part and the outputs differ in six kinds of file per harness, and in the system files that sum
    them. Nothing else changes (stamps aside)."""
    p = load_project(loose_root).project
    q = load_project(loose_root).project
    for h in list(q.harnesses.values()):
        for c in h.connectors:
            if c.role == LOOSE:
                part = (
                    "EX-MICROD-9-M"
                    if len(c.pins) <= 9
                    else "EX-MICROD-15-M"
                    if len(c.pins) <= 15
                    else "EX-MICROD-31-M"
                )
                apply_ops(q, plan_resolve_loose_end(q, h.id, c.id, part))
    a, b = build_outputs(p).files, build_outputs(q).files
    assert set(a) == set(b)
    stamp = re.compile(rb"model [0-9a-f]{12}")

    def same(k: str) -> bool:
        if k.endswith((".pdf", ".xlsx")):  # (timestamps and compression: read as values elsewhere)
            return True
        return stamp.sub(b"model X", a[k]) == stamp.sub(b"model X", b[k])

    differ = sorted(k for k in a if not same(k))
    kinds = {k.rsplit("/", 1)[-1] for k in differ if k.startswith("harnesses/")}
    assert kinds == {
        "bom.csv",
        "drawing_A3_s1.svg",
        "labels.csv",
        "mass_length.csv",
        "pinouts.csv",
        "wireviz.yaml",
    }
    assert {k.split("/")[1] for k in differ if k.startswith("harnesses/")} == {
        "W009",
        "W011",
        "W012",
        "W013",
    }
    assert [k for k in differ if k.startswith("system/")] == [
        "system/bom.csv",
        "system/drc_findings.csv",
        "system/drc_report.md",
        "system/export.json",
        "system/mass_length.csv",
        "system/provenance.json",
    ]


# ---- 5. the release gate ---------------------------------------------------------------------


def test_a_loose_end_blocks_a_release_and_the_parts_waiver_does_not_cover_it(loose_root, tmp_path):
    root = copy_project(loose_root, tmp_path / "p")
    p = load_project(root).project
    out = tmp_path / "outputs"
    write_outputs(p, out)
    common = dict(by="Ada", checker="Bob", comment="Release of W013", when="2026-11-08",
                  outputs_folder=out, accept_placeholders="placeholders are fine here",
                  accept_unapproved_parts="example parts, all of them")  # fmt: skip
    plan = plan_release(p, "W013", **common)
    assert [b.code for b in plan.blockers] == ["loose_end_unresolved"]
    short = plan_release(p, "W013", accept_loose_ends="x", **common)
    assert [b.code for b in short.blockers] == ["loose_end_reason_short"]
    ok = plan_release(p, "W013", accept_loose_ends="the end waits for the supplier", **common)
    assert ok.ok
    note = [o for o in ok.ops if isinstance(o, Put) and o.collection == "changelog"][0].obj.comment
    assert "Released with a loose end (W013-P2); accepted by Ada: the end waits" in note
    assert "TBD-CONNECTOR" not in note  # the open end is not "a part that is not approved"


def test_resolving_the_end_lifts_the_blocker(loose_root, tmp_path):
    root = copy_project(loose_root, tmp_path / "p")
    p = load_project(root).project
    apply_ops(p, plan_resolve_loose_end(p, "W013", "W013-P2", "EX-MICROD-9-M"))
    out = tmp_path / "outputs"
    write_outputs(p, out)
    plan = plan_release(p, "W013", by="Ada", checker="Bob", comment="Release of W013",
                        when="2026-11-08", outputs_folder=out,
                        accept_placeholders="placeholders are fine here",
                        accept_unapproved_parts="example parts, all of them")  # fmt: skip
    assert plan.ok


def test_a_frozen_baseline_still_matches_after_a_loose_end_is_released(loose_root, tmp_path):
    root = copy_project(loose_root, tmp_path / "p")
    p = load_project(root).project
    out = tmp_path / "outputs"
    write_outputs(p, out)
    plan = plan_release(p, "W013", by="Ada", checker="Bob", comment="Release of W013",
                        when="2026-11-08", outputs_folder=out,
                        accept_placeholders="placeholders are fine here",
                        accept_unapproved_parts="example parts, all of them",
                        accept_loose_ends="the end waits for the supplier")  # fmt: skip
    History(p).execute(plan.label, plan.ops)
    save_project(p, root)
    q = load_project(root).project
    assert q.baselines["W013.A"].content_hash == content_hash(q)
    snap = q.baselines["W013.A"].snapshot.harnesses[0]
    assert [c.role for c in snap.connectors if c.id == "W013-P2"] == [LOOSE]
    assert TBD_PART_ID in {x.id for x in q.baselines["W013.A"].snapshot.parts}  # frozen with it


# ---- 6. migration -----------------------------------------------------------------------------


def _origin_step(files):
    """The step the plan describes (2.4, Origin): `link` if a connection names the harness, else
    `drawn`, written into every harness a person made."""
    out = noop_step(files)
    linked = {x.get("harness_id") for x in out.get("logical/links.json", {}).get("links", [])}
    for rel, h in out.items():
        if (
            rel.startswith("physical/harnesses/")
            and isinstance(h, dict)
            and h.get("generated") is False
        ):
            h["origin"] = "link" if h["id"] in linked else "drawn"
    return out


def _v1_with_hand_made_harness(dest: Path) -> Path:
    from harness_design_studio.core.links import plan_add_link, plan_create_harness  # noqa: F401

    root = build("links", dest)  # a harness made from a connection
    p = load_project(root).project
    ops, hid = plan_new_harness(p, "Hand made")
    apply_ops(p, ops)
    ops, _cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
    apply_ops(p, ops)
    save_project(p, root)
    return root


def test_writing_origin_into_hand_made_harnesses_changes_the_hash_and_the_safety_net_refuses(
    tmp_path, monkeypatch
):
    """The finding that the plan got wrong: 'content_hash ignores origin' is not enough. The model
    hash is made of the harness files, so a step that adds `origin` to them changes it, and so does
    every stamp, and the net (rightly) calls that a change of the design."""
    root = _v1_with_hand_made_harness(tmp_path / "p")
    install_fake_format(monkeypatch, _origin_step)
    plan = upgrade.plan_upgrade(root)
    assert plan.hash_equal is False and not plan.ok
    assert any("model hash would change" in x for x in plan.lost)
    assert sorted(plan.files) == [
        "physical/harnesses/W001.json",
        "physical/harnesses/W002.json",
        "project.json",
    ]


def test_if_the_hash_leaves_origin_out_the_same_step_passes(tmp_path, monkeypatch):
    root = _v1_with_hand_made_harness(tmp_path / "p")
    real = layout.bytes_for_hash

    def without_origin(rel: str, data: bytes) -> bytes:
        data = real(rel, data)
        if rel.startswith("physical/harnesses/") and b'"origin"' in data:
            doc = json.loads(data)
            doc.pop("origin", None)
            from harness_design_studio.core.io import canonical

            return canonical.dumps(doc)
        return data

    monkeypatch.setattr(layout, "bytes_for_hash", without_origin)
    install_fake_format(monkeypatch, _origin_step)
    plan = upgrade.plan_upgrade(root)
    assert plan.hash_equal, plan.lost
    # ... but the net still stops it: `system/export.json` lists the fields of every harness, so a
    # field that is there in one file and not the other is a difference of the written output
    assert plan.lost == ["A full export would differ (system/export.json: differs)."]


def test_or_origin_is_derived_and_the_step_has_nothing_to_write(tmp_path, monkeypatch):
    """The alternative the spike recommends: what a harness's origin is can be read from what
    format 1 already says (generated, and the link that names it); only a value that cannot be read
    from there is stored. Then the step rewrites no harness file and the hash is untouched."""
    root = _v1_with_hand_made_harness(tmp_path / "p")
    p = load_project(root).project
    linked = {x.harness_id for x in p.links.values() if x.harness_id}

    def derived(h) -> str:
        return "interfaces" if h.generated else "link" if h.id in linked else "drawn"

    stepped = _origin_step(
        {
            rel: json.loads(data)
            for rel, data in layout.serialize(p).items()
            if rel.endswith(".json")
        }
    )
    for rel, doc in stepped.items():
        if rel.startswith("physical/harnesses/"):
            assert doc.get("origin", "interfaces") == derived(p.harnesses[doc["id"]])
    install_fake_format(monkeypatch)  # only the number
    plan = upgrade.plan_upgrade(root)
    assert plan.hash_equal and plan.ok and plan.exports_equal, plan.lost
    assert sorted(plan.files) == ["project.json"]


def test_the_net_upgrades_a_project_that_holds_loose_ends_with_only_the_number(
    loose_root, tmp_path, monkeypatch
):
    root = copy_project(loose_root, tmp_path / "p")
    before = model_hash(load_project(root).project)
    install_fake_format(monkeypatch)
    plan = upgrade.plan_upgrade(root)
    assert plan.ok and plan.hash_equal and plan.exports_equal and plan.baselines_intact is not False
    upgrade.upgrade_project(root)
    after = load_project(root).project
    assert model_hash(after) == before
    assert len(loose_ends(after.harnesses["W009"])) == 1 and after.meta.schema_version == 2


def test_a_tool_that_does_not_know_the_role_sets_the_whole_harness_aside(loose_root, tmp_path):
    """What a 1.x tool does with a loose end: the harness that holds one is quarantined, not shown
    in part (the reason the plan puts it in format 2, where 1.x opens the project read-only)."""
    root = copy_project(loose_root, tmp_path / "p")
    f = root / "physical" / "harnesses" / "W009.json"
    doc = json.loads(f.read_text())
    for c in doc["connectors"]:
        if c["role"] == LOOSE:
            c["role"] = "role-from-the-future"
    f.write_text(json.dumps(doc))
    res = load_project(root)
    assert "W009" not in res.project.harnesses
    assert any(i.code == "quarantined" for i in res.issues)


# ---- 7. property ------------------------------------------------------------------------------

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
        made = sorted(x.id for x in p.harnesses.values() if x.origin == "drawn")
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
