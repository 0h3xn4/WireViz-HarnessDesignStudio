# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""Canvas state (CV-8, CV-10, CV-19, CV-23): what a link still needs, its summary for the tooltip,
the picture a unit's card carries and the sentences that say why the tool chose a connector.
All pure functions of the project; nothing is guessed or filled in."""

from pathlib import Path

import pytest

from harness_design_studio.core import describe, templates
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.model import evolve


@pytest.fixture
def project(tmp_path: Path):
    templates.create_project(tmp_path / "f", "flatsat")
    return load_project(tmp_path / "f").project


def power_link(project):
    return next(
        i
        for i in project.interfaces.values()
        if project.interface_types[i.type_id].category == "power"
    )


# ---- CV-8: a missing V / A is "?", not blank -------------------------------------------------------


def test_a_power_link_without_numbers_asks_for_both(project) -> None:
    link = power_link(project)
    bare = evolve(link, voltage_v=None, max_current_a=None)
    project.interfaces[link.id] = bare
    assert describe.link_missing(project, link.id) == ("V", "A")
    assert describe.link_label(project, link.id) == "V ? · A ?"


def test_only_the_missing_one_is_marked(project) -> None:
    link = power_link(project)
    project.interfaces[link.id] = evolve(link, voltage_v=28.0, max_current_a=None)
    assert describe.link_label(project, link.id) == "28 V · A ?"
    project.interfaces[link.id] = evolve(link, voltage_v=None, max_current_a=0.5)
    assert describe.link_label(project, link.id) == "V ? · 0.5 A"
    assert describe.link_missing(project, link.id) == ("V",)


def test_a_complete_link_reads_as_before(project) -> None:
    link = next(
        i for i in project.interfaces.values() if i.voltage_v is not None and i.max_current_a
    )
    assert describe.link_missing(project, link.id) == ()
    assert describe.link_label(project, link.id) == describe.link_values(project, link.id)


def test_a_data_link_is_never_asked_for_numbers(project) -> None:
    """A CAN link has no voltage or current to enter: blank means "does not apply" there."""
    can = next(i for i in project.interfaces.values() if i.type_id == "can")
    assert describe.link_missing(project, can.id) == ()
    assert describe.link_label(project, can.id) == ""


def test_an_unknown_link_says_nothing(project) -> None:
    assert describe.link_missing(project, "NOPE") == ()
    assert describe.link_label(project, "NOPE") == ""


# ---- CV-10: the summary for the tooltip ------------------------------------------------------------


def test_the_summary_names_harness_wires_state_and_lock(project) -> None:
    generated = next(
        i
        for i in project.interfaces.values()
        if any(w.interface_id == i.id for h in project.harnesses.values() for w in h.wires)
    )
    s = describe.link_summary(project, generated.id, locks=[("W001", "A")])
    n = sum(1 for h in project.harnesses.values() for w in h.wires if w.interface_id == s.id)
    assert s.wire_count == n > 0
    assert s.harnesses and all(h in project.harnesses for h in s.harnesses)
    assert s.state == f"Generated: {n} wire{'s' if n != 1 else ''}"
    rows = dict(s.facts())
    assert rows["Harness"] == ", ".join(s.harnesses)
    assert rows["Wires"] == str(n)
    assert rows["Lock"] == "Released in W001 A"
    assert rows["Ends"] == " ↔ ".join(e.unit_id for e in project.interfaces[s.id].endpoints)


def test_a_link_without_wires_is_not_generated_yet(project) -> None:
    link = power_link(project)
    for h in project.harnesses.values():  # nothing carries it
        h.wires[:] = [w for w in h.wires if w.interface_id != link.id]
        h.interfaces[:] = [x for x in h.interfaces if x != link.id]
    s = describe.link_summary(project, link.id)
    assert s.wire_count == 0 and s.state == "Not generated yet"
    assert dict(s.facts())["Harness"] == "none yet"
    assert "Lock" not in dict(s.facts())


def test_the_summary_lists_what_is_still_to_enter_and_the_auto_connectors(project) -> None:
    link = power_link(project)
    project.interfaces[link.id] = evolve(link, voltage_v=None, max_current_a=None)
    rows = dict(describe.link_summary(project, link.id).facts())
    assert rows["Still to enter"] == "voltage and current"
    auto = sum(e.auto for e in project.interfaces[link.id].endpoints)
    if auto:
        assert rows["Connectors"].startswith(f"{auto} chosen for you")


def test_the_summary_of_a_missing_link_is_harmless(project) -> None:
    s = describe.link_summary(project, "NOPE")
    assert s.id == "NOPE" and s.wire_count == 0 and s.ends == ()


# ---- CV-19: the picture of a unit ------------------------------------------------------------------


def test_every_flatsat_unit_gets_a_known_picture(project) -> None:
    got = {u: describe.unit_glyph(project, u) for u in project.units}
    assert set(got.values()) <= set(describe.UNIT_GLYPHS)
    assert got["OBC1"] == "computer" and got["TRX1"] == "comms"
    assert got["RW1"] == "actuator" and got["ST1"] == "sensor" and got["PYRO1"] == "pyro"
    assert len(set(got.values())) >= 6  # the kinds differ: that is the point of the picture


def test_the_picture_falls_back_to_the_links_when_the_words_say_nothing(project) -> None:
    uid = "OBC1"
    project.units[uid] = evolve(project.units[uid], name="Box 7", subsystem="x")
    assert describe.unit_glyph(project, uid) == "computer"  # it carries data links
    cats = describe.unit_categories(project)
    assert "data" in cats[uid]
    assert describe.unit_glyph(project, uid, cats) == "computer"


def test_a_unit_with_no_clue_is_a_plain_box(project) -> None:
    uid = "OBC1"
    project.units[uid] = evolve(project.units[uid], name="Box 7", subsystem="x")
    assert describe.unit_glyph(project, uid, {}) == "unit"
    assert describe.unit_glyph(project, "NOPE") == "unit"


# ---- CV-23: why the tool chose what it chose --------------------------------------------------------


def test_a_link_says_which_connectors_were_chosen_for_it_and_what_generation_recorded(
    project,
) -> None:
    auto = next(i for i in project.interfaces.values() if any(e.auto for e in i.endpoints))
    lines = describe.why_lines(project, "interface", auto.id)
    assert any("was chosen for you" in x for x in lines)
    assert any(x.startswith("wiring:") for x in lines)  # from core.generate.explain


def test_a_unit_lists_its_auto_connectors(project) -> None:
    lines = describe.why_lines(project, "unit", "OBC1")
    assert lines and all(x.startswith("OBC1:") for x in lines)


def test_a_confirmed_connector_has_nothing_to_explain(project) -> None:
    for iid, i in list(project.interfaces.items()):
        project.interfaces[iid] = evolve(i, endpoints=[evolve(e, auto=False) for e in i.endpoints])
    cid = next(iter(project.connectors))
    assert not any("was chosen for you" in x for x in describe.why_lines(project, "connector", cid))
    project.generation = None  # and with nothing recorded either, it says so
    assert describe.why_lines(project, "connector", cid)[0].startswith("Nothing to explain")


def test_before_generation_the_link_says_so(project) -> None:
    project.generation = None
    for i in project.interfaces.values():
        i.endpoints[:] = [evolve(e, auto=False) for e in i.endpoints]
    first = describe.why_lines(project, "interface", next(iter(project.interfaces)))
    assert len(first) == 1 and "not generated" in first[0]
