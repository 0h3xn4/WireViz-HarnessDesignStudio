"""Exact limits and rarely exercised behaviours (audit area I): a value on the limit passes, one
step over fails; each test is tied to a behaviour that no other test pinned."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import checks, edit
from harness_design_studio.core.checks import Finding
from harness_design_studio.core.commands import History, Put, SetConfig
from harness_design_studio.core.drc import apply_waivers
from harness_design_studio.core.generate.lengths import MAX_LENGTH_M, plan_length_import
from harness_design_studio.core.generate.segmentation import _class_of, segment
from harness_design_studio.core.ids import check_id, check_pin_id
from harness_design_studio.core.imports import guess_mapping, parse_csv, plan_interface_import
from harness_design_studio.core.io import layout
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import ConfigFile, Pin, Waiver, evolve
from harness_design_studio.core.samples import mini3, sat15
from harness_design_studio.core.units import AWG_MAX, AWG_MIN, awg_to_area_mm2, awg_to_diameter_mm
from harness_design_studio.core.vcs import diff as vd
from harness_design_studio.core.vcs.release import release_blockers
from tests.test_change_control import REASON, WHEN, full, releasable
from tests.test_data_import import project_with_segments

TEN = "0123456789"  # exactly the 10 characters the documented minimum asks for


# ---- release: reason and comment length (M22, M23) -----------------------------------------------


def _blockers(**kw: str | None) -> set[str]:
    p = full()
    args: dict[str, str | None] = {
        "by": "Ada", "comment": "a long enough comment", "when": WHEN,
        "accept_placeholders": REASON, "accept_unapproved_parts": REASON,
    }  # fmt: skip
    args.update(kw)
    found = release_blockers(p, releasable(p), outputs_folder=None, **args)  # type: ignore[arg-type]
    return {b.code for b in found}


def test_release_comment_needs_exactly_ten_characters() -> None:
    assert "comment_short" in _blockers(comment=TEN[:9])
    assert "comment_short" not in _blockers(comment=TEN)
    assert "comment_short" in _blockers(comment="   " + TEN[:9] + "   ")  # spaces do not count
    assert "comment_short" not in _blockers(comment="   " + TEN + "   ")


def test_reason_for_releasing_on_placeholders_needs_exactly_ten_characters() -> None:
    assert "placeholder_reason_short" in _blockers(accept_placeholders=TEN[:9])
    assert "placeholder_reason_short" not in _blockers(accept_placeholders=TEN)
    assert "placeholder_reason_short" in _blockers(accept_placeholders=" " + TEN[:9] + " ")


def test_reason_for_releasing_unapproved_parts_needs_exactly_ten_characters() -> None:
    assert "parts_reason_short" in _blockers(accept_unapproved_parts=TEN[:9])
    assert "parts_reason_short" not in _blockers(accept_unapproved_parts=TEN)
    assert "parts_reason_short" in _blockers(accept_unapproved_parts=" " + TEN[:9] + " ")


# ---- waiver justification (M72) ------------------------------------------------------------------


def test_waiver_justification_needs_exactly_ten_characters() -> None:
    def make(text: str) -> Waiver:
        return Waiver(id="r.x", rule="r", object_id="x", justification=text)

    with pytest.raises(ValidationError):
        make(TEN[:9])
    assert make(TEN).justification == TEN
    assert make("x" * 2000)
    with pytest.raises(ValidationError):
        make("x" * 2001)


def test_waive_op_reports_a_short_reason_in_plain_words() -> None:
    f = Finding("r.x", "r", "warning", "x", "title", "why", can_waive=True)
    with pytest.raises(edit.EditError, match="at least 10 characters"):
        checks.waive_op(f, TEN[:9])
    with pytest.raises(edit.EditError, match="at least 10 characters"):
        checks.waive_op(f, "  " + TEN[:9] + "  ")  # trimmed before it is counted
    op = checks.waive_op(f, " " + TEN + " ")
    assert isinstance(op, Put) and isinstance(op.obj, Waiver) and op.obj.justification == TEN


# ---- lengths and gauges (M58, M59, M73): the current behaviour ------------------------------------


def _length_rows(*texts: str) -> list[tuple[bool, str]]:
    p = project_with_segments()
    table = [["harness", "segment", "length"], *[["W010", "W010-L1", t] for t in texts]]
    plan = plan_length_import(p, table, scale=1.0)
    return [(r.ok, r.message) for r in plan.rows]


def test_a_segment_length_of_zero_is_accepted() -> None:
    assert _length_rows("0") == [(True, "")]
    assert _length_rows("0.000") == [(True, "")]


def test_a_segment_length_is_accepted_up_to_exactly_10000_metres() -> None:
    assert MAX_LENGTH_M == 10_000.0
    assert _length_rows("10000", "9999.999") == [(True, ""), (True, "")]
    over = _length_rows("10000.001", "10001")
    assert [ok for ok, _ in over] == [False, False]
    assert all("is not a length" in m for _, m in over)


def test_lengths_in_millimetres_reach_the_limit_after_conversion() -> None:
    p = project_with_segments()
    table = [["harness", "segment", "length"], ["W010", "W010-L1", "10000000"]]
    assert plan_length_import(p, table, scale=0.001).rows[0].ok
    table[1][2] = "10000001"
    assert not plan_length_import(p, table, scale=0.001).rows[0].ok


def test_the_supported_wire_sizes_are_awg_0_to_40() -> None:
    assert (AWG_MIN, AWG_MAX) == (0, 40)
    assert awg_to_diameter_mm(0) > awg_to_diameter_mm(40) > 0
    assert awg_to_area_mm2(40) > 0
    for bad in (-1, 41):
        with pytest.raises(ValueError, match="outside the supported range 0..40"):
            awg_to_diameter_mm(bad)


# ---- waivers match the finding, not the object (M20) -------------------------------------------


def test_a_waiver_waives_only_its_own_finding_not_every_finding_of_the_object() -> None:
    p = mini3()
    a = Finding("rule-a.W001-001", "rule-a", "warning", "W001-001", "A", "why", can_waive=True)
    b = Finding("rule-b.W001-001", "rule-b", "warning", "W001-001", "B", "why", can_waive=True)
    p.waivers[a.id] = Waiver(id=a.id, rule=a.rule, object_id=a.object_id, justification=TEN)
    out = {f.id: f for f in apply_waivers(p, [a, b])}
    waiver = out[a.id].waiver
    assert waiver is not None and waiver.justification == TEN
    assert out[b.id].waiver is None
    # a waiver filed under another finding ID never matches by object alone
    p.waivers.clear()
    p.waivers["other.W001-001"] = Waiver(
        id="other.W001-001", rule="other", object_id="W001-001", justification=TEN
    )
    assert all(f.waiver is None for f in apply_waivers(p, [a, b]))


# ---- the model hash covers file names (M54) ---------------------------------------------------------


def test_model_hash_changes_when_content_moves_between_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    p = mini3()

    def fake(files: dict[str, bytes]):  # type: ignore[no-untyped-def]
        return lambda project, tool_version="": files

    monkeypatch.setattr(layout, "serialize", fake({"a.json": b"one", "b.json": b"two"}))
    base = layout.model_hash(p)
    monkeypatch.setattr(layout, "serialize", fake({"a.json": b"two", "b.json": b"one"}))
    assert layout.model_hash(p) != base  # same bytes, other file names
    monkeypatch.setattr(layout, "serialize", fake({"a2.json": b"one", "b.json": b"two"}))
    assert layout.model_hash(p) != base  # a file renamed


# ---- import-lengths --unit cm (M56) ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("unit", "text", "metres"), [("cm", "150", 1.5), ("mm", "1500", 1.5), ("m", "1.5", 1.5)]
)
def test_import_lengths_converts_every_unit(
    tmp_path: Path, unit: str, text: str, metres: float
) -> None:
    save_project(project_with_segments(), tmp_path / "p")
    f = tmp_path / "len.csv"
    f.write_text(f"harness,segment,length\nW010,W010-L1,{text}\n")
    assert cli_main(["import-lengths", str(tmp_path / "p"), str(f), "--unit", unit]) == 0
    got = load_project(tmp_path / "p").project.harnesses["W010"].segments[0].length_m
    assert got == pytest.approx(metres)


# ---- identifiers (M63) ---------------------------------------------------------------------------


def test_pin_ids_may_not_end_with_a_dot() -> None:
    assert check_pin_id("A.1") == "A.1"
    for bad in ("1.", "A.", "a.b."):
        with pytest.raises(ValueError, match="pin names"):
            check_pin_id(bad)
    with pytest.raises(ValidationError):
        Pin(id="12.")
    assert Pin(id="12").id == "12"
    with pytest.raises(ValueError, match="must not end with a dot"):
        check_id("J1.")


# ---- segmentation (N04, N05) -----------------------------------------------------------------------


def test_zone_names_that_look_like_an_escape_do_not_share_a_harness() -> None:
    p = sat15()
    History(p).execute(
        "mode",
        [
            SetConfig(
                ConfigFile(name="segmentation", placeholder=False, values={"mode": "per_zone_pair"})
            )
        ],
    )
    for uid in p.units:
        p.units[uid] = evolve(p.units[uid], zone=f"z-{uid}")
    # IF-014 (OBC1-TRX1) and IF-016 (OBC1-ST1) end in the zone pairs ("a|b", "c") and ("a%7Cb", "c")
    p.units["OBC1"] = evolve(p.units["OBC1"], zone="c")
    p.units["TRX1"] = evolve(p.units["TRX1"], zone="a|b")
    p.units["ST1"] = evolve(p.units["ST1"], zone="a%7Cb")
    groups = {iid: g for g in segment(p).groups for iid in g.interface_ids}
    assert groups["IF-014"].key != groups["IF-016"].key
    assert groups["IF-014"].zones == ("a|b", "c") and groups["IF-016"].zones == ("a%7Cb", "c")


def test_pyro_interfaces_are_kept_apart_by_default() -> None:
    p = sat15()
    pyro = evolve(p.interfaces["IF-020"], type_id="pyro")
    assert _class_of(p, pyro, {}, {}) == "pyro"  # setting absent: the safe default
    assert _class_of(p, pyro, {}, {"forbid_pyro_with_other": None}) == "pyro"
    assert _class_of(p, pyro, {}, {"forbid_pyro_with_other": True}) == "pyro"
    assert _class_of(p, pyro, {}, {"forbid_pyro_with_other": False}) == "main"


# ---- interface import: duplicate IDs ignore case (N09) --------------------------------------------


def test_import_refuses_an_interface_id_that_differs_only_in_case() -> None:
    p = mini3()
    existing = next(iter(p.interfaces))
    table = parse_csv(
        "Interface,Type,From unit,To unit,Redundancy\n"
        f"{existing.lower()},Primary power,PCDU,OBC,nominal\n"
        "IF-NEW,Primary power,PCDU,OBC,nominal\n"
        "if-new,Primary power,PCDU,OBC,nominal\n"
    )
    plan = plan_interface_import(p, table, guess_mapping(table[0]))
    assert [r.ok for r in plan.rows] == [False, True, False]
    assert "already used" in plan.rows[0].message and "already used" in plan.rows[2].message


# ---- diff (N10, N11) ------------------------------------------------------------------------------


def test_diff_ignores_the_order_of_a_list_of_objects_but_sees_other_changes() -> None:
    one = {("harness", "H"): {"wires": [{"id": "W1", "n": 1}, {"id": "W2", "n": 2}]}}
    reordered = {("harness", "H"): {"wires": [{"id": "W2", "n": 2}, {"id": "W1", "n": 1}]}}
    changed = {("harness", "H"): {"wires": [{"id": "W2", "n": 2}, {"id": "W1", "n": 9}]}}
    assert vd.diff_flat(one, reordered).empty
    assert vd.diff_flat(one, changed).counts() == {"added": 0, "removed": 0, "changed": 1}
    plain = {("harness", "H"): {"names": ["b", "a"]}}
    assert not vd.diff_flat(
        plain, {("harness", "H"): {"names": ["a", "b"]}}
    ).empty  # plain lists keep order


def test_diff_reports_a_configuration_change() -> None:
    a, b = sat15(), sat15()
    values = {**b.config["generation"].values, "default_gauge_awg": 22}
    History(b).execute(
        "gauge", [SetConfig(ConfigFile(name="generation", placeholder=False, values=values))]
    )
    d = vd.diff_projects(a, b)
    cfg = [c for c in d.changes if c.kind == "config"]
    assert [(c.id, c.change) for c in cfg] == [("generation", "changed")]
    assert {f.name for f in cfg[0].fields} >= {"values"}
    assert vd.diff_projects(a, sat15()).empty


# ---- generation arithmetic that nothing asserted ---------------------------------------------------


def test_the_service_loop_is_added_at_both_ends_of_every_generated_wire() -> None:
    from harness_design_studio.core.generate.engine import generate_project
    from harness_design_studio.core.model import Segment

    p = sat15()
    generate_project(p)
    h = p.harnesses["W010"]
    seg = Segment(id="W010-L1", from_node=h.connectors[0].id, to_node=h.connectors[1].id)
    History(p).execute(
        "segment", [Put("harnesses", evolve(h, segments=[evolve(seg, length_m=1.0)]))]
    )
    values = {**p.config["generation"].values, "service_loop_m": 0.25}
    History(p).execute(
        "loop", [SetConfig(ConfigFile(name="generation", placeholder=False, values=values))]
    )
    generate_project(p)
    assert {w.length_m for w in p.harnesses["W010"].wires} == {1.5}  # 1.0 + 2 * 0.25
    assert [s.length_m for s in p.harnesses["W010"].segments] == [1.0]  # the route is unchanged


def test_bundle_factor_uses_the_next_listed_count_and_never_a_better_one() -> None:
    from harness_design_studio.core.generate.sizing import bundle_k

    table = {"3": 0.9, "7": 0.8}
    assert [bundle_k(table, n) for n in (1, 3, 4, 7)] == [0.9, 0.9, 0.8, 0.8]
    assert bundle_k(table, 8) is None  # larger than the table lists
    assert bundle_k({}, 3) is None and bundle_k(None, 3) is None


def test_a_wire_keeps_its_own_length_over_the_routing_segments() -> None:
    from harness_design_studio.core.generate.lengths import wire_length
    from harness_design_studio.core.model import Segment

    p = sat15()
    from harness_design_studio.core.generate.engine import generate_project

    generate_project(p)
    h = p.harnesses["W010"]
    a, b = h.connectors[0].id, h.connectors[1].id
    h = evolve(h, segments=[Segment(id="S", from_node=a, to_node=b, length_m=2.0)])
    wire = h.wires[0]
    assert wire_length(h, evolve(wire, length_m=None)) == 2.0  # from the route
    assert wire_length(h, evolve(wire, length_m=3.5)) == 3.5  # its own length wins
