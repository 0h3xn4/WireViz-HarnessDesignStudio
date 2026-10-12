"""Regression tests for the rule, output and change-control findings of the October audit."""

import json
from pathlib import Path

import pytest

from harness_design_studio.core import drc, edit
from harness_design_studio.core.checks import Finding, finding_id, waive_op
from harness_design_studio.core.commands import History
from harness_design_studio.core.generate.mass import harness_mass
from harness_design_studio.core.model import (
    Connector,
    Harness,
    Project,
    Segment,
    Wire,
    evolve,
)
from harness_design_studio.core.outputs.build import build_outputs, write_outputs
from harness_design_studio.core.outputs.canvas import Line, Rect, Sheet
from harness_design_studio.core.outputs.drawing import _draw_sketch
from harness_design_studio.core.outputs.stamp import Stamp, csv_bytes, parse_csv
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3, sat15, sat15_full
from harness_design_studio.core.vcs.release import release_blockers
from tests.test_change_control import WHEN, exported, full, releasable


def _codes(blockers: list) -> set[str]:  # type: ignore[type-arg]
    return {b.code for b in blockers}


def test_the_release_gate_sees_current_over_contact_errors(tmp_path: Path) -> None:
    p = sat15_full()
    hid = releasable(p)
    iid = sorted(p.harnesses[hid].interfaces)[0]
    p.interfaces[iid] = evolve(p.interfaces[iid], max_current_a=50.0)  # far above any contact
    folder = exported(p, tmp_path)
    blockers = release_blockers(
        p, hid, by="Ada", comment="long enough text", when=WHEN, outputs_folder=folder
    )
    assert any(b.code == "rule_error" for b in blockers)


def test_the_outputs_gate_checks_the_files_not_just_the_manifest(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)

    def blockers() -> set[str]:
        return _codes(
            release_blockers(
                p, hid, by="Ada", comment="long enough text", when=WHEN, outputs_folder=folder
            )
        )

    assert "outputs_modified" not in blockers() and "outputs_missing" not in blockers()
    victim = next(f for f in sorted(folder.rglob("wirelist.csv")))
    victim.write_text(victim.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    assert "outputs_modified" in blockers()
    write_outputs(p, folder)
    for f in list(folder.rglob("*")):
        if f.is_file() and f.name != "manifest.json":
            f.unlink()
    assert "outputs_modified" in blockers()


def test_a_subset_export_does_not_satisfy_the_gate(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    other = next(h for h in sorted(p.harnesses) if h != hid)
    folder = tmp_path / "outputs"
    write_outputs(p, folder, build_outputs(p, harness_ids=[other]))
    got = _codes(
        release_blockers(
            p, hid, by="Ada", comment="long enough text", when=WHEN, outputs_folder=folder
        )
    )
    assert "outputs_missing" in got


@pytest.mark.parametrize(
    "when", ["2026-02-30", "0000-00-00", "2026-13-45", "２０２６-０１-０１", "2026-03-01\n"]
)
def test_impossible_dates_block_a_release(when: str, tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    got = _codes(
        release_blockers(
            p,
            hid,
            by="Ada",
            comment="long enough text",
            when=when,
            outputs_folder=exported(p, tmp_path),
        )
    )
    assert "bad_date" in got


def test_signal_and_class_findings_can_be_waived() -> None:
    p = mini3()
    for obj in ("IF-014.OBC1-J04.TX+", "W001.power+data", "a b"):
        fid = finding_id("signal-unassigned", obj)
        f = Finding(fid, "signal-unassigned", "warning", obj, "t", "w", None, True, None)
        History(p).execute("waive", [waive_op(f, "a reason that is long enough")])
        assert fid in p.waivers


def test_a_reason_that_is_too_short_is_an_edit_error_not_a_crash() -> None:
    f = Finding("x.y", "x", "warning", "y", "t", "w", None, True, None)
    with pytest.raises(edit.EditError):
        waive_op(f, "short")


def test_skipped_current_checks_are_listed_not_silent() -> None:
    p = sat15_full()
    cfg = p.config["derating"]
    p.config["derating"] = evolve(
        cfg, values={**cfg.values, "ampacity_a_by_awg": {"26": 1.0, "24": 2.0}}
    )
    for i in list(p.interfaces.values()):
        p.interfaces[i.id] = evolve(i, max_current_a=500.0)
    notes = [f for f in drc.run(p) if f.rule == "unchecked-config"]
    assert any("AWG 20" in f.title for f in notes), [f.title for f in notes]
    for part in p.parts.values():
        if part.category == "connector":
            p.parts[part.id] = evolve(part, ratings={})
    notes = [f for f in drc.run(p) if f.rule == "unchecked-config"]
    assert any("no contact rating" in f.title for f in notes)


def test_a_gauge_outside_the_wire_sizes_is_a_finding_not_a_crash() -> None:
    p = sat15_full()
    hid = sorted(p.harnesses)[0]
    h = p.harnesses[hid]
    w = h.wires[0]
    iid = w.interface_id or ""
    p.interfaces[iid] = evolve(p.interfaces[iid], max_current_a=1.0)
    # the model refuses this value now; the rule must still cope if one gets through (a bug elsewhere)
    odd = Wire.model_construct(**{**w.model_dump(), "gauge_awg": 50})
    fields = {name: getattr(h, name) for name in Harness.model_fields}
    p.harnesses[hid] = Harness.model_construct(**{**fields, "wires": [odd, *h.wires[1:]]})
    findings = drc.run(p)
    assert any("not a wire size" in f.title for f in findings)


def test_segment_lengths_count_in_mass_the_release_gate_and_the_tables(tmp_path: Path) -> None:
    p = sat15_full()
    hid = releasable(p)
    h = p.harnesses[hid]
    before = harness_mass(p, h)
    p.harnesses[hid] = evolve(h, wires=[evolve(w, length_m=None) for w in h.wires])
    seg = [evolve(s, length_m=1.0) for s in h.segments]
    p.harnesses[hid] = evolve(p.harnesses[hid], segments=seg)
    after = harness_mass(p, p.harnesses[hid])
    assert after.complete and after.total_g > 0
    blockers = release_blockers(
        p, hid, by="Ada", comment="long enough text", when=WHEN, outputs_folder=None
    )
    assert "length_unknown" not in _codes(blockers)
    assert before.complete


# ---- the output verifier now compares values ----------------------------------------------------


def _files(p: Project) -> dict[str, bytes]:
    return dict(build_outputs(p).files)


def _mutate(files: dict[str, bytes], rel: str, old: str, new: str) -> dict[str, bytes]:
    out = dict(files)
    text = out[rel].decode()
    assert old in text, (rel, old)
    out[rel] = text.replace(old, new, 1).encode()
    return out


def test_the_verifier_is_quiet_on_every_sample() -> None:
    for make in (mini3, sat15, sat15_full):
        p = make()
        assert verify_outputs(p, _files(p)).ok


@pytest.mark.parametrize(
    "rel,old,new",
    [
        ("harnesses/W001/wirelist.csv", ",EX-WIRE-SINGLE,", ",EX-WIRE-OTHER,"),
        ("harnesses/W001/wirelist.csv", ",1.2,", ",1.9,"),
        ("harnesses/W001/wirelist.csv", ",IF-010,", ",IF-011,"),
        ("harnesses/W001/mass_length.csv", ",33.6,", ",30.6,"),
        ("harnesses/W001/mass_length.csv", ",2.4,", ",2.5,"),
        (
            "harnesses/W001/tests.csv",
            "W001-P1.1,W001-P2.1,continuous",
            "W001-P1.9,W001-P2.1,continuous",
        ),
        ("harnesses/W001/labels.csv", "W001-001-A", "W001-777-A"),
        ("system/mass_length.csv", "W001,2,2,2.4,0,33.6", "W001,2,2,2.4,0,13.6"),
    ],
)
def test_changed_cells_are_caught_by_the_output_verifier(rel: str, old: str, new: str) -> None:
    p = sat15_full()
    files = _mutate(_files(p), rel, old, new)
    assert not verify_outputs(p, files).ok, (rel, old, new)


def test_a_workbook_that_differs_from_its_wire_list_is_caught() -> None:
    p = sat15_full()
    files = _files(p)
    rel = "harnesses/W001/wirelist.csv"
    files[rel] = files[rel].replace(
        b",20,", b",18,", 1
    )  # the CSV now disagrees with xlsx and model
    assert not verify_outputs(p, files).ok


def test_the_json_export_must_match_every_harness() -> None:
    p = sat15_full()
    files = _files(p)
    doc = json.loads(files["system/export.json"])
    doc["harnesses"][0]["wires"][0]["gauge_awg"] = 99
    files["system/export.json"] = json.dumps(doc).encode()
    assert not verify_outputs(p, files).ok


# ---- csv, text and drawings ---------------------------------------------------------------------


def test_a_cell_that_starts_with_a_hash_survives_the_csv_round_trip() -> None:
    stamp = Stamp("0.1", "abcdef123456")
    table = [["a", "b"], ["x", "line one\n# a note\nline three"], ["\t=cmd", "plain"]]
    assert parse_csv(csv_bytes(table, stamp)) == table


def test_characters_that_are_not_valid_xml_are_refused_in_names() -> None:
    p = mini3()
    with pytest.raises(ValueError):
        evolve(p.units["OBC"], name="bad ￿ name")


def _chain(n: int) -> Harness:
    conns = [
        Connector(id=f"C{k:02d}", name=f"C{k}", role="cable", part_id="EX-DSUB-9-M")
        for k in range(n)
    ]
    segs = [
        Segment(id=f"L{k}", from_node=f"C{k:02d}", to_node=f"C{k + 1:02d}", length_m=1.0)
        for k in range(n - 1)
    ]
    return Harness(id="H1", name="chain", connectors=conns, segments=segs, branch_points=[])


def test_a_long_routing_sketch_stays_on_the_sheet() -> None:
    sheet = Sheet(297.0, 210.0)
    _draw_sketch(sheet, _chain(13), 20.0, 297.0)
    rects = [i for i in sheet.items if isinstance(i, Rect)]
    assert rects and max(r.x + r.w for r in rects) <= 297.0 - 5.0


def test_the_block_diagram_legend_is_below_the_boxes() -> None:
    from harness_design_studio.core.outputs.system import block_diagram

    p = sat15()
    sheet = block_diagram(p, Stamp("0.1", "abcdef123456"))
    rects = [i for i in sheet.items if isinstance(i, Rect) and i.w > 20]
    lowest = max(r.y + r.h for r in rects if r.h < 20)
    legend_lines = [i for i in sheet.items if isinstance(i, Line) and i.x1 < 20 and i.y1 > lowest]
    assert len(legend_lines) >= 5
