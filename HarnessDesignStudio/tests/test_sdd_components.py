"""REQ-TRACE-02: component table and requirement-to-component trace of the SDD
(ECSS-E-ST-40C 5.5.2, Annex F section 6)."""

from __future__ import annotations

import csv
from pathlib import Path

from tools import gen_sdd_components as sdd

ROOT = Path(__file__).resolve().parent.parent


def test_component_table_is_current() -> None:
    with (ROOT / "compliance" / "sdd_components.csv").open(newline="", encoding="utf-8") as f:
        assert list(csv.reader(f)) == [sdd.HEADER, *sdd.build()]


def test_every_module_states_its_purpose() -> None:
    bare = [r[0] for r in sdd.build() if not r[2] and not r[0].endswith("__init__")]
    assert not bare, bare


def test_core_components_do_not_depend_on_the_outer_layers() -> None:
    bad = [
        (r[0], d)
        for r in sdd.build()
        if r[1] == "core"
        for d in r[3].split()
        if d.split("/")[0] in ("gui", "cli")
    ]
    assert not bad, bad
