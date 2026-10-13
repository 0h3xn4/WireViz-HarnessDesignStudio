# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""What the diagram shows about a link and a connector comes from the project data, never from
a guess: values appear only when entered, and the connector family is read from the part."""

from pathlib import Path

import pytest

from harness_design_studio.core import describe, templates
from harness_design_studio.core.io.loader import load_project


@pytest.fixture
def project(tmp_path: Path):
    templates.create_project(tmp_path / "f", "flatsat")
    return load_project(tmp_path / "f").project


def test_a_link_shows_the_voltage_and_current_that_were_entered(project) -> None:
    powered = next(i for i in project.interfaces.values() if i.voltage_v is not None)
    values = describe.link_values(project, powered.id)
    assert values.startswith(f"{powered.voltage_v:g} V")
    assert describe.link_caption(project, powered.id).startswith("Primary power")


def test_a_link_without_values_shows_none(project) -> None:
    can = next(i for i in project.interfaces.values() if i.type_id == "can")
    assert describe.link_values(project, can.id) == ""
    assert describe.link_caption(project, can.id) == "CAN"


def test_every_connector_has_a_known_family_and_gender(project) -> None:
    families = {describe.connector_family(project, cid)[0] for cid in project.all_connectors()}
    assert families <= set(describe.FAMILY_LABEL)
    assert {"microd", "rj45", "coax"} <= families  # the flatsat uses all three
    sample = next(iter(project.connectors))
    family, pins, gender = describe.connector_family(project, sample)
    assert pins > 0 and gender in ("male", "female", "unspecified")


def test_the_harness_drawing_states_the_gender_of_cable_connectors(project) -> None:
    from harness_design_studio.core.outputs.drawing import harness_sheets
    from harness_design_studio.core.outputs.stamp import Stamp

    harness = next(iter(project.harnesses.values()))
    sheets = harness_sheets(project, harness, Stamp("t", "t"), "A3")
    text = " ".join(getattr(i, "s", "") for sh in sheets for i in sh.items)
    assert "male, pins" in text or "female, sockets" in text
