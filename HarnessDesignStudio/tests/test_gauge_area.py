"""D2 (D-193): the cross-section in mm² beside every AWG gauge a person reads, and in no file.

The core helpers, the explanations, the Assumptions page and the command line text. The editor's
tables, forms and panels are in `test_ui_gauge_area.py`. The files the tool writes keep the plain
gauge: `test_numbers_snapshot.py` and `test_output_hashes.py` hold that, and the last test here
looks for the cross-section in the written files."""

import json
import math
import re
from pathlib import Path

import pytest

from harness_design_studio import api
from harness_design_studio.cli.main import main
from harness_design_studio.core import settings, templates
from harness_design_studio.core.derive import Input, explain_wire, render
from harness_design_studio.core.derive_export import explain_all, to_json_bytes
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.units import (
    awg_to_area_mm2,
    format_awg,
    format_gauge,
    gauge_short,
    with_area,
)


def test_the_helpers_write_the_gauge_with_its_area() -> None:
    assert awg_to_area_mm2(24) == pytest.approx(0.2047, abs=1e-4)
    assert format_gauge(24) == "24 AWG (0.205 mm²)"
    assert gauge_short(24) == "24 (0.205 mm²)"
    assert format_awg(24) == "AWG 24 (0.205 mm²)"
    assert format_gauge(0) == "0 AWG (53.475 mm²)" and format_gauge(40) == "40 AWG (0.005 mm²)"
    # a gauge outside 0 to 40 is not made up a cross-section
    assert format_gauge(41) == "41 AWG" and gauge_short(-1) == "-1"


def test_with_area_names_every_gauge_of_a_sentence_once() -> None:
    assert with_area("Wire W1 (AWG 24) carries 2 A") == "Wire W1 (AWG 24 (0.205 mm²)) carries 2 A"
    assert with_area("Gauge = 22 AWG [wire W1]") == "Gauge = 22 AWG (0.326 mm²) [wire W1]"
    assert with_area("AWG 20 and 26 AWG") == "AWG 20 (0.518 mm²) and 26 AWG (0.129 mm²)"
    once = with_area("AWG 24 and 22 AWG")
    assert with_area(once) == once  # a gauge that has its area is left alone
    assert with_area("AWG 99 and 99 AWG") == "AWG 99 and 99 AWG"  # not a gauge
    assert with_area("AWG 2024 and 12 AWGs") == "AWG 2024 and 12 AWGs"
    assert with_area("no gauge here: 5 A") == "no gauge here: 5 A"


@pytest.fixture(scope="module")
def flatsat(tmp_path_factory: pytest.TempPathFactory):  # type: ignore[no-untyped-def]
    return templates.create_project(tmp_path_factory.mktemp("area") / "flat", "flatsat")


def test_an_explanation_shows_the_gauge_with_its_area(flatsat) -> None:  # type: ignore[no-untyped-def]
    wire = next(w for h in flatsat.harnesses.values() for w in h.wires if w.gauge_awg is not None)
    text = "\n".join(render(d) for d in explain_wire(flatsat, wire.id))
    assert f"Gauge = {format_gauge(wire.gauge_awg or 0)}" in text
    assert f"Base ampacity of {format_awg(wire.gauge_awg or 0)} = " in text
    assert re.search(r"\d AWG(?! \()", text) is None, text  # no bare gauge left in the text


def test_the_data_keeps_the_number_and_adds_the_area(flatsat) -> None:  # type: ignore[no-untyped-def]
    found = explain_all(flatsat)
    gauges = [i for d in found for i in d.inputs if i.unit == "AWG"]
    assert gauges
    for i in gauges:
        assert isinstance(i.value, int) and i.area_mm2 == awg_to_area_mm2(i.value)
        assert i.to_dict() == {
            "name": i.name, "value": i.value, "unit": "AWG", "source": i.source,
            "area_mm2": i.area_mm2,
        }  # fmt: skip
    plain = Input("Current I", 0.8, "A", "x")
    assert plain.area_mm2 is None and "area_mm2" not in plain.to_dict()
    assert Input("Gauge", 99, "AWG", "x").area_mm2 is None  # outside 0 to 40
    doc = json.loads(to_json_bytes(flatsat, found))
    seen = [i for d in doc["derivations"] for i in d["inputs"] if i["unit"] == "AWG"]
    assert seen and all(math.isclose(i["area_mm2"], awg_to_area_mm2(i["value"])) for i in seen)
    # only a gauge has the key
    assert all("area_mm2" not in i for d in doc["derivations"] for i in d["inputs"] if i["unit"] != "AWG")  # fmt: skip


def test_the_assumptions_page_names_the_gauges_of_the_ampacity_table(flatsat) -> None:  # type: ignore[no-untyped-def]
    page = settings.render(flatsat)
    assert "ampacity_a_by_awg = AWG 16 (1.309 mm²): 10.0, AWG 18" in page
    row = next(r for r in settings.rows(flatsat) if r.setting.key == "ampacity_a_by_awg")
    assert isinstance(row.value, dict) and set(row.value) == {"16", "18", "20", "22", "24", "26"}
    # the value as data is the table, not the text
    out = settings.to_dict(flatsat)["settings"]
    assert next(s for s in out if s["id"] == "derating.ampacity_a_by_awg")["value"] == row.value  # type: ignore[index, attr-defined]


def test_the_command_line_text_has_the_area_and_the_data_does_not(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "p"
    api.create_project(folder, "flatsat")
    wire = next(
        w for h in api.load_project(folder).harnesses.values() for w in h.wires if w.gauge_awg == 24
    )
    assert main(["explain", str(folder), wire.id]) == 0
    assert "Gauge = 24 AWG (0.205 mm²)" in capsys.readouterr().out
    assert main(["explain", str(folder), wire.id, "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    gauge = next(i for d in data for i in d["inputs"] if i["unit"] == "AWG")
    assert gauge["value"] == 24 and gauge["area_mm2"] == pytest.approx(0.2047, abs=1e-4)
    assert "mm²)" not in json.dumps(data).replace("(mm²)", "")
    assert main(["settings", str(folder)]) == 0
    assert "AWG 24 (0.205 mm²): 2.0" in capsys.readouterr().out
    assert main(["settings", str(folder), "--json"]) == 0
    table = next(
        s["value"] for s in json.loads(capsys.readouterr().out)["settings"]
        if s["id"] == "derating.ampacity_a_by_awg"
    )  # fmt: skip
    assert table["24"] == 2.0  # the data is the table as it was set


def test_no_written_output_holds_the_area(flatsat) -> None:  # type: ignore[no-untyped-def]
    built = build_outputs(flatsat, drawings=False)
    for name, data in built.files.items():
        if name.endswith((".csv", ".yaml", ".md", ".svg", ".json")):
            assert "mm²".encode() not in data, name
