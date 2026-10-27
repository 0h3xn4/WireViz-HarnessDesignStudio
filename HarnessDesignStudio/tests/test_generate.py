"""M3: generation (segmentation, pins, wiring, IDs, regeneration) and the independent verifier."""

import time

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.commands import Delete, History, Put, apply_ops
from harness_design_studio.core.generate.engine import (
    GenerationCancelled,
    generate_project,
    generation_status,
    input_hash,
    plan_generation,
)
from harness_design_studio.core.generate.lengths import path_length
from harness_design_studio.core.generate.wiring import links_of
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Harness, evolve
from harness_design_studio.core.samples import mini3, sat15, stress_project
from harness_design_studio.core.verify import verify_project
from tests.helpers import within


def generated(project):
    generate_project(project)
    return project


def test_sat15_generates_and_verifies():
    p = generated(sat15())
    report = verify_project(p)
    assert report.ok, report.summary()
    assert report.interfaces_checked == 24
    assert report.wires_checked == 54  # Ethernet has four signals, SpaceWire had eight
    assert generation_status(p) == "current"


def test_regeneration_is_byte_identical():
    p = generated(sat15())
    before = model_hash(p)
    plan = plan_generation(p)
    assert plan.empty
    apply_ops(p, plan.ops)
    assert model_hash(p) == before


def test_regeneration_from_scratch_is_identical():
    a = generated(sat15())
    b = generated(sat15())
    assert model_hash(a) == model_hash(b)


def test_input_hash_ignores_outputs():
    p = generated(sat15())
    h0 = input_hash(p)
    assert p.generation is not None and p.generation.input_hash == h0
    apply_ops(p, plan_generation(p).ops)
    assert input_hash(p) == h0


def test_status_goes_stale_when_inputs_change():
    p = generated(sat15())
    assert generation_status(p) == "current"
    unit = next(iter(p.units.values()))
    apply_ops(p, [Put("units", evolve(unit, name=unit.name + " x"))])
    assert generation_status(p) == "stale"
    assert generation_status(sat15()) == "none"


def test_ids_stay_stable_when_an_interface_is_removed():
    p = generated(sat15())
    ids = {h.id: h.group_key for h in p.harnesses.values()}
    victim = sorted(p.interfaces)[-1]
    apply_ops(p, [Delete("interfaces", victim)])
    plan = plan_generation(p)
    apply_ops(p, plan.ops)
    assert plan.report.changed or plan.report.removed
    for hid, key in ids.items():
        if hid in p.harnesses:
            assert p.harnesses[hid].group_key == key
    assert verify_project(p).ok


def test_released_harness_is_frozen():
    p = generated(sat15())
    hid = sorted(p.harnesses)[0]
    h = p.harnesses[hid]
    apply_ops(p, [Put("harnesses", evolve(h, status="released"))])
    victim = next(i for i in h.interfaces)
    apply_ops(p, [Delete("interfaces", victim)])
    plan = plan_generation(p)
    assert hid in plan.report.frozen
    apply_ops(p, plan.ops)
    assert p.harnesses[hid].wires == h.wires


def test_locked_wire_keeps_user_values():
    p = generated(sat15())
    h = next(x for x in p.harnesses.values() if x.wires)
    w = evolve(h.wires[0], locked=True, gauge_awg=22, length_m=1.5)
    apply_ops(p, [Put("harnesses", evolve(h, wires=[w, *h.wires[1:]]))])
    plan = plan_generation(p)
    apply_ops(p, plan.ops)
    kept = next(x for x in p.harnesses[h.id].wires if x.id == w.id)
    assert (kept.gauge_awg, kept.length_m, kept.locked) == (22, 1.5, True)


def test_sizing_is_pending_with_placeholders():
    p = generated(sat15())
    assert all(w.gauge_awg is None for h in p.harnesses.values() for w in h.wires)


def test_cancel_changes_nothing():
    p = sat15()
    before = model_hash(p)
    with pytest.raises(GenerationCancelled):
        plan_generation(p, cancel=lambda: True)
    assert model_hash(p) == before


def test_progress_is_reported():
    seen: list[float] = []
    plan_generation(sat15(), progress=lambda f, _t: seen.append(f))
    assert seen
    assert seen == sorted(seen)


def test_undo_restores_everything():
    p = sat15()
    before = model_hash(p)
    h = History(p)
    h.execute("Generate harnesses", plan_generation(p).ops)
    assert p.harnesses
    h.undo()
    assert model_hash(p) == before


def test_wiring_pairs_out_with_in():
    p = mini3()
    links, _ = links_of(p.interface_types["rs422"])
    labels = {link.label for link in links}
    assert any("/" in x for x in labels)


def test_path_length_missing_is_none():
    p = generated(sat15())
    h = next(iter(p.harnesses.values()))
    a = h.connectors[0].id
    assert path_length(h, a, "no-such-node") is None


def test_manual_harness_untouched():
    p = mini3()
    manual = p.harnesses["W001"]
    generate_project(p)
    assert p.harnesses["W001"] == manual
    assert verify_project(p).ok


def test_mini3_matches_golden_and_verifies():
    p = generated(mini3())
    assert verify_project(p).ok
    again = plan_generation(p)
    assert again.empty


# ---- verifier mutation tests ---------------------------------------------------------------------


def codes(p):
    return {i.code for i in verify_project(p).errors}


def test_verifier_detects_missing_wire():
    p = generated(sat15())
    h = next(x for x in p.harnesses.values() if x.generated and len(x.wires) > 1)
    apply_ops(p, [Put("harnesses", evolve(h, wires=h.wires[1:]))])
    assert "signal_missing" in codes(p)


def test_verifier_detects_swapped_pins():
    p = generated(sat15())
    h = next(x for x in p.harnesses.values() if x.generated and len(x.wires) > 1)
    a, b = h.wires[0], h.wires[1]
    swapped = [
        evolve(a, to_pin=b.to_pin, to_connector=b.to_connector),
        evolve(b, to_pin=a.to_pin, to_connector=a.to_connector),
        *h.wires[2:],
    ]
    apply_ops(p, [Put("harnesses", evolve(h, wires=swapped))])
    assert "wire_signal_mismatch" in codes(p)


def test_verifier_detects_duplicate_wire():
    p = generated(sat15())
    h = next(x for x in p.harnesses.values() if x.generated and x.wires)
    dup = evolve(h.wires[0], id=h.wires[0].id + "-dup")
    apply_ops(p, [Put("harnesses", evolve(h, wires=[*h.wires, dup]))])
    assert {"pin_reused", "signal_duplicated"} <= codes(p)


def test_verifier_detects_missing_end_connector():
    p = generated(sat15())
    h = next(x for x in p.harnesses.values() if x.generated and x.wires)
    w = evolve(h.wires[0], to_connector="NOPE")
    apply_ops(p, [Put("harnesses", evolve(h, wires=[w, *h.wires[1:]]))])
    assert "wire_end_missing" in codes(p)


def test_verifier_flags_outdated_outputs():
    p = generated(sat15())
    unit = next(iter(p.units.values()))
    apply_ops(p, [Put("units", evolve(unit, name="renamed"))])
    assert verify_project(p).stale


# ---- property: regeneration never changes anything -----------------------------------------------


@settings(max_examples=8, deadline=None)
@given(
    units=st.integers(2, 6),
    interfaces=st.integers(2, 12),
    signals=st.integers(2, 6),
    zones=st.integers(1, 3),
)
def test_property_regeneration_idempotent(units, interfaces, signals, zones):
    p = stress_project(units=units, interfaces=interfaces, zones=zones, signals=signals)
    generate_project(p)
    first = model_hash(p)
    plan = plan_generation(p)
    assert plan.empty
    apply_ops(p, plan.ops)
    assert model_hash(p) == first
    assert verify_project(p).ok


@pytest.mark.perf
def test_stress_generates_fast():
    p = stress_project()
    t0 = time.perf_counter()
    plan = plan_generation(p)
    apply_ops(p, plan.ops)
    report = verify_project(p)
    within(time.perf_counter() - t0, 10, "generate and verify the stress project, s")
    assert report.ok
    assert report.wires_checked >= 10_000


# ---- persistence and CLI -------------------------------------------------------------------------


def test_generated_project_round_trips(tmp_path):
    p = generated(sat15())
    save_project(p, tmp_path / "p")
    q = load_project(tmp_path / "p").project
    assert model_hash(q) == model_hash(p)
    assert q.generation == p.generation
    assert generation_status(q) == "current"
    assert all(isinstance(h, Harness) for h in q.harnesses.values())


def test_cli_generate_then_verify(tmp_path, capsys):
    save_project(sat15(), tmp_path / "p")
    assert cli_main(["generate", str(tmp_path / "p")]) == 0
    assert cli_main(["verify", str(tmp_path / "p")]) == 0
    out = capsys.readouterr().out
    assert "0 error(s)" in out
    assert cli_main(["generate", str(tmp_path / "p")]) == 0  # second run changes nothing


def test_generated_projects_match_golden_fixtures(tmp_path):
    from pathlib import Path

    for name, make in (("sat15", sat15),):
        p = generated(make())
        save_project(p, tmp_path / name)
        golden = Path(__file__).parent / "fixtures" / "projects" / name
        files = sorted(x.relative_to(golden) for x in golden.rglob("*.json"))
        assert files == sorted(
            x.relative_to(tmp_path / name) for x in (tmp_path / name).rglob("*.json")
        )
        for rel in files:
            assert (golden / rel).read_bytes() == (tmp_path / name / rel).read_bytes(), (name, rel)


def test_wire_colour_comes_only_from_the_owners_signal_mapping():
    """No mapping, no colour; with `wire_colour_by_signal` the wires of those signals get it and
    a locked wire keeps its own."""
    from harness_design_studio.core.model.config import ConfigFile

    plain = generated(sat15())
    assert all(w.colour is None for h in plain.harnesses.values() for w in h.wires)
    p = sat15()
    old = p.config["generation"]
    signal = next(
        w.signal for h in generated(sat15()).harnesses.values() for w in h.wires if w.signal
    )
    p.config["generation"] = ConfigFile(
        name="generation",
        placeholder=old.placeholder,
        values={**old.values, "wire_colour_by_signal": {signal: "red"}},
    )
    out = generated(p)
    coloured = [w for h in out.harnesses.values() for w in h.wires if w.signal == signal]
    assert coloured and all(w.colour == "red" for w in coloured)
    assert all(
        w.colour is None for h in out.harnesses.values() for w in h.wires if w.signal != signal
    )
