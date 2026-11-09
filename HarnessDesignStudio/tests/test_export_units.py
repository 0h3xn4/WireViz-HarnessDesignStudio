# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""R5 units everywhere (release 1.13, D-195): every numeric field of `system/export.json` states its
unit in the object `field_units`, written from one table (`core/outputs/export_units.py`). The table
is held against the fields of the model (a field added without an entry fails) and against the
numbers of real files (an entry that names no field fails)."""

import json
import types
import typing
from pathlib import Path
from typing import Any, get_args, get_origin

from pydantic import BaseModel

from harness_design_studio.core import templates
from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.library_import import RATING_KEYS
from harness_design_studio.core.model import (
    Accessory,
    Connector,
    Harness,
    InterfaceInstance,
    InterfaceType,
    Part,
    Project,
    Unit,
    evolve,
)
from harness_design_studio.core.outputs import export_units
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.export_units import (
    FIELD_UNITS,
    RATING_UNITS,
    RATINGS,
    field_units,
    missing_units,
    numeric_paths,
    rating_unit,
)
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3, sat15, sat15_full

# the model class behind each list of export.json (the harness dump holds everything below it)
TOP_LEVEL: dict[str, type[BaseModel]] = {
    "units": Unit,
    "interface_types": InterfaceType,
    "interfaces": InterfaceInstance,
    "box_connectors": Connector,
    "harnesses": Harness,
    "parts": Part,
}


def _is_number(tp: Any) -> bool:
    return tp in (int, float)


def _numeric_paths_of(model: type[BaseModel], prefix: str) -> set[str]:
    """The paths of the int and float fields of a model class, below `prefix` (a bool is not a
    number; a dict of numbers is `prefix.<key>`)."""
    found: set[str] = set()
    for name, info in model.model_fields.items():
        found |= _walk(info.annotation, f"{prefix}.{name}")
    return found


def _walk(tp: Any, path: str) -> set[str]:
    origin = get_origin(tp)
    if origin is typing.Annotated:
        return _walk(get_args(tp)[0], path)
    if origin in (typing.Union, types.UnionType):
        out: set[str] = set()
        for arg in get_args(tp):
            out |= _walk(arg, path)
        return out
    if origin is list:
        return _walk(get_args(tp)[0], path + "[]")
    if origin is dict:
        return _walk(get_args(tp)[1], path + ".<key>")
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return _numeric_paths_of(tp, path)
    return {path} if _is_number(tp) else set()


def model_numeric_paths() -> set[str]:
    out = {"format_version"}
    for key, model in TOP_LEVEL.items():
        out |= _numeric_paths_of(model, key + "[]")
    return out


def _table_paths() -> set[str]:
    """The table, with the ratings written as the model writes them: one `<key>`."""
    return {
        (RATINGS + "<key>") if p.startswith(RATINGS) else p
        for p in set(FIELD_UNITS) | {RATINGS + k for k in RATING_UNITS}
    }


def test_every_numeric_field_of_the_model_has_an_entry_and_every_entry_names_a_field() -> None:
    fields = model_numeric_paths()
    table = _table_paths()
    assert fields - table == set(), "a numeric field of the model has no unit in export_units.py"
    assert table - fields == set(), "an entry of export_units.py names no field of the model"


def test_the_known_ratings_are_the_ratings_the_import_reads() -> None:
    assert set(RATING_UNITS) == set(RATING_KEYS)


def test_no_unit_is_empty() -> None:
    for path, unit in {**FIELD_UNITS, **RATING_UNITS}.items():
        assert unit.strip(), path
    # a number without a unit says what it is
    for path, unit in {**FIELD_UNITS, **RATING_UNITS}.items():
        if unit.startswith("none"):
            assert unit.startswith("none (") and unit.endswith(")"), path


def test_the_units_of_a_name_that_carries_one_agree_with_the_name() -> None:
    suffix = {"_m": "m", "_mm": "mm", "_a": "A", "_v": "V", "_ohm": "ohm", "_g": "g", "_awg": "AWG"}
    for path, unit in FIELD_UNITS.items():
        name = path.rsplit(".", 1)[-1]
        for end, expected in suffix.items():
            if name.endswith(end) and not name.endswith("per_m_g"):
                assert unit == expected, path
    assert FIELD_UNITS["parts[].mass_per_m_g"] == "g/m"


def _project_with_everything() -> Project:
    """The full satellite plus every optional number: strip lengths, an accessory, a segment
    length, an impedance, a rating of the project's own and a rating with no unit in its name."""
    p = sat15_full()
    h = next(iter(sorted(p.harnesses.values(), key=lambda x: x.id)))
    w = h.wires[0]
    apply_ops(
        p,
        [
            Put(
                "harnesses",
                evolve(
                    h,
                    wires=[evolve(w, strip_a_mm=6.0, strip_b_mm=7.5), *h.wires[1:]],
                    accessories=[
                        Accessory(id="ACC-001", kind="heat_shrink", length_mm=30.0, quantity=2)
                    ],
                ),
            )
        ],
    )
    for it in list(p.interface_types.values())[:1]:
        apply_ops(p, [Put("interface_types", evolve(it, impedance_ohm=50.0))])
    part = next(iter(sorted(p.parts.values(), key=lambda x: x.id)))
    apply_ops(
        p,
        [Put("parts", evolve(part, ratings={"torque_n_m": 1.0, "weird": 2.0, "max_mass_g": 3.0}))],
    )
    return p


def test_every_number_in_real_files_has_a_unit_and_every_unit_names_a_number_or_a_known_field() -> (
    None
):
    for make in (mini3, sat15, _project_with_everything):
        p = make()
        if make is not _project_with_everything:
            generate_project(p)
        doc = json.loads(build_outputs(p).files["system/export.json"])
        units = doc["field_units"]
        paths = numeric_paths(doc)
        assert paths - set(units) == set(), make.__name__
        assert missing_units(doc) == []
        # an entry of the file is a field of the model (the ratings of a project are free names)
        for path in units:
            assert path in FIELD_UNITS or path.startswith(RATINGS), path
        # an entry that is a number of this file, or a field the model has but this project left empty
        assert set(units) == set(field_units(p))


def test_the_optional_numbers_are_in_the_file_and_have_their_units() -> None:
    doc = json.loads(build_outputs(_project_with_everything()).files["system/export.json"])
    paths = numeric_paths(doc)
    for must in (
        "harnesses[].wires[].strip_a_mm",
        "harnesses[].accessories[].length_mm",
        "harnesses[].accessories[].quantity",
        "interface_types[].impedance_ohm",
        "parts[].ratings.torque_n_m",
    ):
        assert must in paths, must
    units = doc["field_units"]
    assert units["harnesses[].wires[].strip_a_mm"] == "mm"
    assert units["harnesses[].accessories[].length_mm"] == "mm"
    assert units["parts[].ratings.max_mass_g"] == "g"
    assert (
        units["parts[].ratings.torque_n_m"] == export_units.NOT_STATED
    )  # newton metres: not guessed
    assert units["parts[].ratings.weird"] == export_units.NOT_STATED


def test_the_gauge_stays_the_plain_awg_number_and_existing_fields_do_not_move(
    tmp_path: Path,
) -> None:
    p = templates.create_project(tmp_path / "flatsat", "flatsat")
    doc = json.loads(build_outputs(p).files["system/export.json"])
    wire = doc["harnesses"][0]["wires"][0]
    assert isinstance(wire["gauge_awg"], int)
    assert doc["field_units"]["harnesses[].wires[].gauge_awg"] == "AWG"
    assert doc["format_version"] == 1  # additive: a reader of version 1 still reads the file
    assert "units" in doc and isinstance(doc["units"], list)  # the devices keep the name `units`
    assert "field_units" in doc and isinstance(doc["field_units"], dict)
    without = {k: v for k, v in doc.items() if k != "field_units"}
    assert set(without) >= {"format", "model_hash", "project", "harnesses", "parts", "interfaces"}


def test_a_missing_unit_is_found_and_an_old_file_is_still_accepted(tmp_path: Path) -> None:
    p = templates.create_project(tmp_path / "flatsat", "flatsat")
    files = build_outputs(p).files
    doc = json.loads(files["system/export.json"])
    del doc["field_units"]["harnesses[].wires[].length_m"]
    assert missing_units(doc) == ["harnesses[].wires[].length_m"]
    files["system/export.json"] = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    assert "out_json" in {i.code for i in verify_outputs(p, files).errors}
    # a file from before 1.13 has no field_units: it is not asked for one
    del doc["field_units"]
    assert missing_units(doc) == []
    files["system/export.json"] = (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()
    assert "out_json" not in {i.code for i in verify_outputs(p, files).errors}


def test_rating_unit_reads_the_end_of_a_name_and_otherwise_says_it_does_not_know() -> None:
    assert rating_unit("contact_current_a") == "A"
    assert rating_unit("my_limit_v") == "V"
    assert rating_unit("max_temp_c") == "degC"
    assert rating_unit("something") == export_units.NOT_STATED
