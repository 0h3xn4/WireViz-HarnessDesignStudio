"""A parts-program export (InvenTree) as the parts library import reads it, offline (D-165)."""

import json
from pathlib import Path

import pytest

from harness_design_studio.core.commands import Put
from harness_design_studio.core.imports import ImportError_, parse_json_table, read_table
from harness_design_studio.core.library_import import (
    _category_word,
    guess_mapping,
    plan_parts_import,
)
from harness_design_studio.core.model import Part, Project

CSV = """ID,Name,IPN,Description,Category,Active,Manufacturer,MPN,Units,Weight
12,D-Sub 9 plug,CON-DE9P,Connector D-Sub 9 pin plug,Connectors/D-Sub,True,Amphenol,L77SDE09P,pcs,12.5
13,Hook-up wire 22 AWG,WIR-22,PTFE wire 22 AWG,Wires,True,Alpha Wire,5855,m,
"""


def table(tmp_path: Path, name: str, text: str) -> list[list[str]]:
    f = tmp_path / name
    f.write_text(text, encoding="utf-8")
    return read_table(f)


def test_the_ipn_column_is_the_part_id_and_the_database_id_is_not(tmp_path: Path) -> None:
    t = table(tmp_path, "parts.csv", CSV)
    m = guess_mapping(t[0])
    assert t[0][m["id"]] == "IPN"
    assert t[0][m["description"]] == "Description"
    assert t[0][m["part_number"]] == "MPN"
    assert t[0][m["manufacturer"]] == "Manufacturer"
    assert t[0][m["mass_g"]] == "Weight"


def test_a_csv_export_becomes_parts(tmp_path: Path) -> None:
    t = table(tmp_path, "parts.csv", CSV)
    plan = plan_parts_import(Project(), t, guess_mapping(t[0]), approved=[], pending=["true"])
    assert [(r.ok, r.part_id, r.message) for r in plan.rows] == [
        (True, "CON-DE9P", ""),
        (True, "WIR-22", ""),
    ]
    parts = {
        op.obj.id: op.obj for op in plan.ops if isinstance(op, Put) and isinstance(op.obj, Part)
    }
    assert parts["CON-DE9P"].category == "connector"
    assert parts["CON-DE9P"].part_number == "L77SDE09P"
    assert parts["CON-DE9P"].approval == "pending"  # never approved by a guess
    assert parts["WIR-22"].category == "wire"


def test_a_tsv_and_a_json_export_give_the_same_table(tmp_path: Path) -> None:
    csv_table = table(tmp_path, "parts.csv", CSV)
    tsv = table(tmp_path, "parts.tsv", CSV.replace(",", "\t"))
    assert tsv == csv_table
    records = [dict(zip(csv_table[0], row, strict=True)) for row in csv_table[1:]]
    js = table(tmp_path, "parts.json", json.dumps(records))
    assert js == csv_table
    paged = table(tmp_path, "paged.json", json.dumps({"count": 2, "results": records}))
    assert paged == csv_table


def test_json_values_become_text() -> None:
    t = parse_json_table('[{"a": 1, "b": null, "c": true}, {"a": 2.5, "d": "x"}]')
    assert t == [["a", "b", "c", "d"], ["1", "", "true", ""], ["2.5", "", "", "x"]]


@pytest.mark.parametrize(
    "text",
    ["{", "[]", "[1, 2]", '{"a": 1}', '[{"a": {"b": 1}}]', '[{"a": [1]}]', "[" * 100000],
)
def test_json_that_is_not_a_flat_list_is_refused(text: str) -> None:
    with pytest.raises(ImportError_):
        parse_json_table(text)


def test_categories_are_the_six_words_or_refused() -> None:
    assert _category_word("Connectors/D-Sub") == "connector"
    assert _category_word("Electronics > Contacts") == "contact"
    assert _category_word("Backshell") == "backshell"
    assert _category_word("Resistors") == "resistors"  # not a category of this tool: refused later
