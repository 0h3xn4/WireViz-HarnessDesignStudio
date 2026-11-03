"""D-191, S1: readiness, test limits, pin allocation, segmentation, labels, colours, shields and the choice
of a connector are explained by the code that makes them.

Each derivation is checked against the thing it explains: the open items against `buildsheet.readiness`
and against the *Ready to build* cell of the written workbook; the limits against the cells of the test
sheet; the labels against `tables.labels`; the group of a harness against `segmentation.segment`; the
shield groups against the groups that generation made. A setting changed in the project changes the
explanation with the result."""

import copy
import io
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import settings, templates
from harness_design_studio.core.derive import (
    Derivation,
    explain_object,
    explain_wire_all,
    render,
)
from harness_design_studio.core.derive_build import (
    explain_test,
    readiness_check_derivation,
    readiness_derivation,
    sheet_limit_derivation,
    shield_group_derivation,
    wire_colour_derivation,
    wire_label_derivation,
)
from harness_design_studio.core.derive_layout import (
    connector_choice_derivation,
    explain_interface,
    pin_allocation_derivation,
    segmentation_derivation,
)
from harness_design_studio.core.generate import segmentation
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import ConfigFile, Project, evolve
from harness_design_studio.core.outputs import buildsheet, tables
from harness_design_studio.core.outputs.stamp import stamp_of


def _set(project: Project, file: str, **values: object) -> None:
    base = project.config.get(file) or ConfigFile(name=file, placeholder=False, values={})
    project.config[file] = ConfigFile(
        name=file, placeholder=False, values={**copy.deepcopy(base.values), **values}
    )


@pytest.fixture(scope="module")
def flat() -> Iterator[Project]:
    with tempfile.TemporaryDirectory(prefix="s1-bl-") as tmp:
        yield templates.create_project(Path(tmp) / "flat", "flatsat")


@pytest.fixture
def work(tmp_path: Path) -> Project:
    return templates.create_project(tmp_path / "flat", "flatsat")


def _sheet_answer(project: Project, h) -> str:  # type: ignore[no-untyped-def]
    """The cell next to *Ready to build* in the written workbook."""
    from openpyxl import load_workbook

    data = buildsheet.build_workbook(project, h, stamp_of(project))
    ws = load_workbook(io.BytesIO(data))["Start here"]
    for row in ws.iter_rows(values_only=True):
        if row[0] == "Ready to build":
            return str(row[1])
    raise AssertionError("no Ready to build row")


# ---- (1) readiness ------------------------------------------------------------------------------


def test_readiness_is_the_answer_of_the_workbook_and_names_the_open_items(
    tmp_path: Path, flat: Project
) -> None:
    for project in (flat, templates.create_project(tmp_path / "small", "small-satellite")):
        generate_project(project) if not project.harnesses else None
        for h in project.harnesses.values():
            d = readiness_derivation(project, h)
            assert d.id == "readiness" and d.text == _sheet_answer(project, h), h.id
            checks = buildsheet.readiness(project, h)
            steps = {s.label: s for s in d.steps}
            for c in checks:
                assert steps[c.label].value == c.open and steps[c.label].unit == "open"
                one = readiness_check_derivation(project, h, c)
                assert one.value == c.open and one.id == "readiness-check"
                items = buildsheet.open_items(project, h)[c.label]
                assert len(items) == c.open and tuple(items) == c.items
                assert (one.inputs[0].value == "none") == (c.open == 0)
            blocking = sum(1 for c in checks if c.status == buildsheet.TO_FIX)
            assert d.check is not None and d.check.actual == blocking and d.check.limit == 0
            assert d.check.passes == (blocking == 0)


def test_a_wire_without_a_colour_makes_the_harness_not_ready_and_is_named(work: Project) -> None:
    h = work.harnesses["W001"]
    wires = list(h.wires)
    wires[3] = evolve(wires[3], colour=None)
    work.harnesses["W001"] = evolve(h, wires=wires)
    h = work.harnesses["W001"]
    d = readiness_derivation(work, h)
    assert d.text == "no" == _sheet_answer(work, h)
    assert d.check is not None and not d.check.passes and "Wires without a colour" in d.check.text
    check = next(c for c in buildsheet.readiness(work, h) if c.label == "Wires without a colour")
    one = readiness_check_derivation(work, h, check)
    assert one.inputs[0].value == wires[3].id and one.check is not None and not one.check.passes
    assert "this check blocks Ready to build" in one.check.text
    assert "Set the colour" in one.check.text  # what to do
    # the setting that decides: only the approval of parts blocks now; the colour is a note
    _set(work, "model", readiness_blocking=["Parts that are not approved"])
    d2 = readiness_derivation(work, h)
    assert d2.text == "no" == _sheet_answer(work, h)
    assert d2.check is not None and "Parts that are not approved" in d2.check.text
    assert d2.inputs[0].value == "Parts that are not approved"
    assert "set by the project" in d2.inputs[0].source
    colour = next(c for c in buildsheet.readiness(work, h) if c.label == "Wires without a colour")
    note = readiness_check_derivation(work, h, colour)
    assert not colour.blocking and note.check is None  # a note has no limit to compare with
    assert next(x for x in note.steps if x.label == "Effect on Ready to build").text == "note"
    # nothing blocks: ready
    _set(work, "model", readiness_blocking=[])
    assert readiness_derivation(work, h).text.startswith("yes") == _sheet_answer(
        work, h
    ).startswith("yes")


def test_a_yes_that_rests_on_placeholders_says_so_like_the_sheet(flat: Project) -> None:
    h = flat.harnesses["W001"]
    d = readiness_derivation(flat, h)
    assert "placeholder configuration" in d.text and d.text == _sheet_answer(flat, h)
    assert any(i.name == "Placeholder configuration files" for i in d.inputs)


def test_explain_a_harness_from_the_command_line_shows_readiness(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    templates.create_project(tmp_path / "flat", "flatsat")
    assert main(["explain", str(tmp_path / "flat"), "W001"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("Harness W001. Mass:")
    for must in (
        "Ready to build:",
        "readiness_blocking",
        "Wires without a length",
        "A-READY-CHECKS",
    ):
        assert must in out


# ---- (2) test limits ---------------------------------------------------------------------------


def test_every_limit_of_the_test_sheet_is_explained_with_its_key(flat: Project) -> None:
    for h in flat.harnesses.values():
        rows = tables.tests(flat, h)[1:]
        assert rows
        cont = sheet_limit_derivation(flat, h, "test_continuity_max_ohm")
        iso = sheet_limit_derivation(flat, h, "test_isolation_min_mohm")
        volts = sheet_limit_derivation(flat, h, "test_isolation_voltage_v")
        for r in rows:
            if r[1] == "continuity":
                assert r[5] == cont.steps[0].text
            else:
                assert r[5] == iso.steps[0].text and r[6] == f"{volts.value:g} V"
        assert (cont.value, iso.value, volts.value) == (1.0, 100.0, 500.0)
        assert cont.unit == "ohm" and iso.unit == "Mohm" and volts.unit == "V"
        assert "config/generation.json: test_continuity_max_ohm" in cont.inputs[0].source
        assert (
            f"T001 to T{sum(1 for r in rows if r[1] == 'continuity'):03d}" in cont.inputs[1].source
        )
        assert "placeholder" in cont.inputs[0].source  # the file is not reviewed
        assert cont.assumptions == ("A-TEST-LIMITS", "A-TEST-LIST")


def test_a_limit_that_is_not_set_says_tbd_and_names_the_key(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "flat", "flatsat")
    _set(project, "generation", test_continuity_max_ohm=None)
    h = project.harnesses["W001"]
    d = sheet_limit_derivation(project, h, "test_continuity_max_ohm")
    assert d.value is None and d.steps[0].text == tables.TBD
    assert "generation.test_continuity_max_ohm" in d.missing[0] and tables.TBD in d.missing[0]
    assert tables.tests(project, h)[1][5] == tables.TBD
    text = render(d)
    assert "Not decided yet" in text and "TBD (placeholder)" in text


def test_a_test_can_be_asked_for_by_harness_and_number(
    flat: Project, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = tables.tests(flat, flat.harnesses["W001"])
    cont, iso = rows[1], next(r for r in rows if r[1] == "isolation")
    (d,) = explain_test(flat, f"W001.{cont[0]}")
    assert d.id == "test-limit" and d.inputs[0].name == "Test" and cont[2] in str(d.inputs[0].value)
    two = explain_test(flat, f"W001.{iso[0]}")
    assert [x.quantity for x in two] == ["Smallest insulation resistance", "Isolation test voltage"]
    assert explain_test(flat, "W001.T999") == [] and explain_test(flat, "W999.T001") == []
    assert [x.id for x in explain_object(flat, f"W001.{iso[0]}")] == ["test-limit", "test-limit"]
    templates.create_project(tmp_path / "cli", "flatsat")
    assert main(["explain", str(tmp_path / "cli"), "W001.T001"]) == 0
    assert "test_continuity_max_ohm" in capsys.readouterr().out


# ---- (3) pin allocation and segmentation -------------------------------------------------------------


def test_every_pin_of_every_connector_is_explained(flat: Project) -> None:
    seen = 0
    for conn in flat.connectors.values():
        for p in conn.pins:
            d = pin_allocation_derivation(flat, conn.id, p.id)
            assert d.id == "pin-allocation" and d.text and not d.missing
            if p.signal:
                assert p.signal in d.text and (p.interface_id or "") in d.text
                assert any(s.label == "Recorded when it was generated" for s in d.steps)
                seen += 1
            else:
                assert d.text == "unassigned"
    assert seen > 100
    gone = pin_allocation_derivation(flat, "NO-SUCH", "1")
    assert gone.missing and not gone.known


def test_the_cable_end_of_a_pin_is_explained_by_the_pin_of_the_device(flat: Project) -> None:
    h = flat.harnesses["W001"]
    w = h.wires[0]
    cable = next(c for c in h.connectors if c.id == w.from_connector)
    a = pin_allocation_derivation(flat, cable.id, w.from_pin)
    b = pin_allocation_derivation(flat, cable.mates_with or "", w.from_pin)
    assert a == b and a.subject == f"Pin {w.from_pin} of {cable.mates_with}"
    ids = [d.id for d in explain_wire_all(flat, w.id)]
    assert ids.count("pin-allocation") == 2


def test_the_order_of_the_categories_is_the_setting_and_changes_the_pins(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "flat", "flatsat")
    before = {c.id: [(p.id, p.signal) for p in c.pins] for c in project.connectors.values()}
    d = pin_allocation_derivation(project, "PDU2-J02", "1")
    order = next(i for i in d.inputs if i.name == "Order of the categories")
    assert order.value == "power, ground" and "the tool's own default" in order.source
    # the other order: ground before power, and data after both
    _set(project, "model", pin_allocation_categories=["ground", "power"])
    generate_project(project)
    after = {c.id: [(p.id, p.signal) for p in c.pins] for c in project.connectors.values()}
    d2 = pin_allocation_derivation(project, "PDU2-J02", "1")
    order2 = next(i for i in d2.inputs if i.name == "Order of the categories")
    assert order2.value == "ground, power" and "set by the project" in order2.source
    assert settings.names(project, "model", "pin_allocation_categories") == ("ground", "power")
    assert before != after or order.value != order2.value
    for c in project.connectors.values():
        for p in c.pins:
            if p.signal:
                step = next(
                    s
                    for s in pin_allocation_derivation(project, c.id, p.id).steps
                    if s.label == "Place of the category in the order"
                )
                assert step.text  # a category is placed, listed or not


def test_a_locked_pin_is_said_to_be_locked(work: Project) -> None:
    conn = next(c for c in work.connectors.values() if any(p.signal for p in c.pins))
    pin = next(p for p in conn.pins if p.signal)
    pins = [evolve(p, locked=True) if p.id == pin.id else p for p in conn.pins]
    work.connectors[conn.id] = evolve(conn, pins=pins)
    d = pin_allocation_derivation(work, conn.id, pin.id)
    assert (
        "locked" in d.text and next(i for i in d.inputs if i.name == "Pin is locked").value == "yes"
    )


def test_the_gaps_between_power_and_signal_are_inputs(work: Project) -> None:
    _set(work, "generation", power_signal_gap_pins=2, power_return_gap_pins=1)
    d = pin_allocation_derivation(work, "PDU2-J02", "1")
    gaps = {i.name: i for i in d.inputs if "between" in i.name or "Contacts" in i.name}
    assert gaps["Pins between power and signal"].value == 2
    assert "not set" not in gaps["Pins between power and signal"].source
    assert gaps["Contacts between power and return"].value == 1


def test_the_group_of_a_harness_follows_the_mode_and_the_zones(tmp_path: Path) -> None:
    for mode in ("per_connector_pair", "per_unit_pair", "per_zone_pair"):
        project = templates.create_project(tmp_path / mode, "flatsat")
        _set(project, "segmentation", mode=mode)
        generate_project(project)
        seg = segmentation.segment(project)
        groups = {g.key: g for g in seg.groups}
        assert project.harnesses
        for h in project.harnesses.values():
            d = segmentation_derivation(project, h)
            g = groups[h.group_key]
            assert d.id == "segmentation" and not d.missing, (mode, h.id)
            assert d.inputs[0].value == mode and mode == g.mode
            assert str(len(h.interfaces)) in d.text and g.label in d.text
            assert {f"Interface {i}" for i in h.interfaces} <= {i.name for i in d.inputs}
            assert (
                next(s for s in d.steps if s.label == "Group key of the harness").text
                == h.group_key
            )
            assert any("segmentation:" in s.expression for s in d.steps)  # the Why-tab line
            assert (g.zones is not None) == (mode == "per_zone_pair")
            assert any(s.label == "Zones of the group" for s in d.steps) == (
                mode == "per_zone_pair"
            )


def test_a_harness_drawn_by_hand_has_no_segmentation_rule(work: Project) -> None:
    h = work.harnesses["W001"]
    work.harnesses["W001"] = evolve(h, generated=False, group_key="")
    d = segmentation_derivation(work, work.harnesses["W001"])
    assert "drawn by hand" in d.text


def test_an_interface_is_explained_with_its_harness_connectors_and_pins(flat: Project) -> None:
    found = explain_interface(flat, "IF-001")
    kinds = [d.id for d in found]
    assert kinds[0] == "segmentation" and "connector-choice" in kinds and "pin-allocation" in kinds
    assert "contact-current" in kinds
    assert [d.id for d in explain_object(flat, "IF-001")] == kinds


def test_an_interface_in_no_harness_says_why(tmp_path: Path) -> None:
    project = templates.create_project(tmp_path / "first", "first-steps")
    i = sorted(project.interfaces)[0]
    (d,) = explain_interface(project, i)[:1]
    assert d.id == "segmentation" and d.text.startswith("in no harness")


def test_the_choice_of_a_connector_is_the_tools_or_the_librarys(flat: Project) -> None:
    box = connector_choice_derivation(flat, "GPSU1-J01")
    assert any("chosen by the tool, not confirmed" in str(i.value) for i in box.inputs)
    assert box.assumptions == ("A-CONNECTOR-CHOICE",) and box.text == "EX-MICROD-9-F"
    cable = connector_choice_derivation(flat, "W001-P1")
    assert cable.text == "EX-MICROD-9-M mates with MTQ1-J01"
    assert any("mating" in s.expression or "mating" in s.text for s in cable.steps)
    assert connector_choice_derivation(flat, "NOPE").missing


# ---- (4) labels, colours, shields ------------------------------------------------------------------


def test_the_labels_explained_are_the_labels_of_the_tables(flat: Project) -> None:
    from harness_design_studio.core.derive_build import connector_label_derivation

    for h in flat.harnesses.values():
        rows = {r[0]: r[2] for r in tables.labels(flat, h)[1:]}
        for w in h.wires:
            d = wire_label_derivation(flat, h, w)
            assert f'{w.id}-A "{rows[w.id + "-A"]}"' in d.text
            assert f'{w.id}-B "{rows[w.id + "-B"]}"' in d.text
        for c in h.connectors:
            assert connector_label_derivation(flat, h, c).text == rows[c.id]


def test_a_label_a_person_gave_and_an_emc_class_are_part_of_the_text(work: Project) -> None:
    h = work.harnesses["W001"]
    w = h.wires[0]
    wires = [evolve(w, label="MAIN BUS +") if x.id == w.id else x for x in h.wires]
    work.harnesses["W001"] = evolve(h, wires=wires)
    itype = work.interface_types[work.interfaces[w.interface_id or ""].type_id]
    work.interface_types[itype.id] = evolve(itype, emc_class="B")
    h = work.harnesses["W001"]
    d = wire_label_derivation(work, h, h.wires[0])
    rows = {r[0]: r[2] for r in tables.labels(work, h)[1:]}
    assert "MAIN BUS +" in rows[f"{w.id}-A"] and "[EMC B]" in rows[f"{w.id}-A"]
    assert rows[f"{w.id}-A"] in d.text
    name = next(i for i in d.inputs if i.name == "Name printed")
    assert name.value == "MAIN BUS +" and "label a person gave" in name.source
    assert next(i for i in d.inputs if i.name == "EMC class").value == "B"


def test_the_colour_comes_from_the_table_or_from_a_person_or_is_missing(work: Project) -> None:
    h = work.harnesses["W001"]
    w0 = h.wires[0]
    assert w0.colour and w0.signal
    d = wire_colour_derivation(work, h, w0)
    assert d.text == w0.colour and "from the table of the project" in d.steps[0].expression
    assert next(i for i in d.inputs if i.name == "IEC 60757 code").value
    wires = list(h.wires)
    wires[1] = evolve(wires[1], colour="orange")
    wires[2] = evolve(wires[2], colour=None)
    work.harnesses["W001"] = evolve(h, wires=wires)
    h = work.harnesses["W001"]
    typed = wire_colour_derivation(work, h, h.wires[1])
    assert typed.text == "orange" and "typed or imported" in typed.steps[0].expression
    empty = wire_colour_derivation(work, h, h.wires[2])
    assert not empty.known or empty.text == "" and empty.missing
    _set(work, "generation", wire_colour_by_signal=None)
    h = work.harnesses["W001"]
    none = wire_colour_derivation(work, h, h.wires[2])
    assert "the table is not set" in none.inputs[2].source


def test_every_shield_group_is_explained_by_the_rule_that_made_it(tmp_path: Path) -> None:
    kinds: set[str] = set()
    for name in ("flatsat", "small-satellite"):
        project = templates.create_project(tmp_path / name, name)
        if not project.harnesses:
            generate_project(project)
        for h in project.harnesses.values():
            for s in h.shields:
                d = shield_group_derivation(project, h, s)
                steps = {x.label: x for x in d.steps}
                assert "no rule of the generator" not in steps["Why the group exists"].expression
                assert d.text == f"{s.kind}, end A {s.end_a}, end B {s.end_b}"
                kinds.add(s.kind)
                if s.kind == "coax":
                    assert "fixed by the file format" in d.inputs[2].source
                else:
                    assert "grounding concept" in d.inputs[2].source
    assert {"twisted_pair", "coax"} <= kinds


def test_a_shield_that_differs_from_the_concept_is_named(work: Project) -> None:
    h = work.harnesses["W001"]
    shields = list(h.shields)
    shields[0] = evolve(shields[0], end_b="backshell_360", manual=True)
    work.harnesses["W001"] = evolve(h, shields=shields)
    h = work.harnesses["W001"]
    d = shield_group_derivation(work, h, h.shields[0])
    assert "made by hand" in d.steps[0].expression
    ends = next(s for s in d.steps if s.label == "Ends against the grounding concept")
    assert "not applicable" in ends.text or "different" in ends.text


# ---- every derivation as files -----------------------------------------------------------------


def test_every_kind_a_project_makes_is_listed_with_its_page(tmp_path: Path) -> None:
    from harness_design_studio.core.derive_export import explain_all
    from harness_design_studio.core.derive_kinds import KINDS, page_of

    models = Path(__file__).resolve().parent.parent / "docs" / "models"
    produced: set[str] = set()
    for name in ("flatsat", "flatsat-tight", "small-satellite", "first-steps"):
        from tools.numbers_snapshot import SCENARIOS

        example, change = SCENARIOS[name]
        project = templates.create_project(tmp_path / name, example)
        if not project.harnesses:
            generate_project(project)
        if change is not None:
            change(project)
        _set(project, "derating", spare_pin_fraction=0.6)  # a rule-limit finding
        produced |= {d.id for d in explain_all(project)}
    assert produced <= set(KINDS), produced - set(KINDS)
    assert set(KINDS) <= produced, set(KINDS) - produced
    for kind, (page, what) in KINDS.items():
        text = (models / page).read_text(encoding="utf-8")
        assert f"`{kind}`" in text, (kind, page)
        assert what and page_of(kind) == page


def test_the_files_have_the_text_column_and_the_same_design_gives_the_same_bytes(
    tmp_path: Path,
) -> None:
    import csv as csv_mod
    import json

    from harness_design_studio.core.derive_export import (
        CSV_HEADER,
        explain_all,
        to_csv_bytes,
        to_json_bytes,
    )

    project = templates.create_project(tmp_path / "flat", "flatsat")
    found = explain_all(project)
    assert to_json_bytes(project, found) == to_json_bytes(project, explain_all(project))
    assert to_csv_bytes(found) == to_csv_bytes(explain_all(project))
    assert CSV_HEADER[-1] == "Text" and CSV_HEADER[-2] == "Missing"
    rows = list(csv_mod.reader(io.StringIO(to_csv_bytes(found).decode("utf-8"))))
    by = {(r[0], r[1]): r for r in rows[1:]}
    ready = by[("readiness", "Harness W001")]
    assert ready[-1].startswith("yes") and ready[3] == ""  # the answer is a text, not a number
    colour = by[("wire-colour", "Wire W001-001")]
    assert colour[-1] == "red"
    doc = json.loads(to_json_bytes(project, found))
    assert doc["format"] == 2
    texts = [d for d in doc["derivations"] if "text" in d]
    assert texts and all(d["text"] for d in texts)
    plain = next(d for d in doc["derivations"] if d["id"] == "wire-length")
    assert "text" not in plain  # a derivation with a number is written as before
    text_step = next(s for d in doc["derivations"] for s in d["steps"] if "text" in s)
    assert text_step["value"] is None
    # nothing of the machine in the files
    raw = to_json_bytes(project, found).decode("utf-8")
    assert str(tmp_path) not in raw and "T00:" not in raw


def test_a_derivation_with_a_text_is_known_and_one_without_a_value_is_not(flat: Project) -> None:
    ready = readiness_derivation(flat, flat.harnesses["W001"])
    assert ready.value is None and ready.known
    nothing = Derivation("x", "s", "q", None, "", "e")
    assert not nothing.known
    assert Derivation("x", "s", "q", 0.0, "", "e").known


def test_explain_all_counts_what_has_no_result(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    templates.create_project(tmp_path / "flat", "flatsat")
    assert main(["explain", str(tmp_path / "flat"), "--all", "--out", str(tmp_path / "o")]) == 0
    out = capsys.readouterr().out
    assert "derivations written" in out and "without a value" in out


def test_explain_takes_the_new_kinds_of_object(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    templates.create_project(tmp_path / "flat", "flatsat")
    flat = str(tmp_path / "flat")
    for oid, must in (
        ("IF-001", "Why these interfaces share a harness"),
        ("MTQ1-J01.1", "Pin allocation: PWR of IF-018 on pin 1"),
        ("W001-S1", "Shield group:"),
        ("W001-P1", "Choice of connector"),
        ("GPSU1-J01", "Choice of connector"),
    ):
        assert main(["explain", flat, oid]) == 0, oid
        assert must in capsys.readouterr().out, oid
    assert main(["explain", flat, "W001-001", "--json"]) == 0
    assert main(["explain", flat, "NOPE.NOPE"]) == 2
    assert "nor an interface, a connector" in capsys.readouterr().err
