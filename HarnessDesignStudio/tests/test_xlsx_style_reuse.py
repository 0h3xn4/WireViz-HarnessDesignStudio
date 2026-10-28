"""REQ-OUT-01, audit B-08. The build workbook used to make a font, a fill and an alignment object
for every cell (28,693 fonts for the flatsat) and the library found each again in its tables, which
was 70 % of an export. A cell style is now made once per combination and workbook and copied. The
bytes of every workbook must be the same as with a fresh style for every cell."""

import gc
import tempfile
from pathlib import Path

import pytest

from harness_design_studio.core import templates
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.outputs import buildsheet
from harness_design_studio.core.outputs.stamp import stamp_of

EXAMPLES = ("first-steps", "minimal-satellite", "small-satellite", "flatsat")


def project_of(name: str, folder: Path):  # type: ignore[no-untyped-def]
    p = templates.create_project(folder / name, name)
    if not p.harnesses:
        generate_project(p)
    return p


@pytest.mark.parametrize("name", EXAMPLES)
def test_workbooks_are_the_same_bytes_with_or_without_the_reuse(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    p = project_of(name, tmp_path)
    stamp = stamp_of(p)
    for h in p.harnesses.values():
        monkeypatch.setattr(buildsheet, "_REUSE_STYLES", False)
        fresh = buildsheet.build_workbook(p, h, stamp)
        monkeypatch.setattr(buildsheet, "_REUSE_STYLES", True)
        reused = buildsheet.build_workbook(p, h, stamp)
        assert reused == fresh, h.id


def test_a_font_is_made_once_per_style_not_once_per_cell(tmp_path: Path) -> None:
    Font = buildsheet._S["Font"]  # the class the workbook code uses (see outputs/xlsx_env.py)
    p = project_of("flatsat", tmp_path)
    stamp = stamp_of(p)
    made = [0]
    original = Font.__init__

    def counting(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        made[0] += 1
        original(self, *args, **kwargs)

    Font.__init__ = counting  # type: ignore[method-assign]
    try:
        buildsheet._font.cache_clear()
        for h in p.harnesses.values():
            buildsheet.build_workbook(p, h, stamp)
    finally:
        Font.__init__ = original  # type: ignore[method-assign]
    # a few dozen combinations in all; the library itself makes one default font per workbook
    assert made[0] < 300, made[0]


def test_the_remembered_styles_go_with_their_workbook() -> None:
    """The styles are numbers in the tables of one workbook: they must not be handed to another."""
    with tempfile.TemporaryDirectory() as tmp:
        p = project_of("minimal-satellite", Path(tmp))
        stamp = stamp_of(p)
        h = next(iter(p.harnesses.values()))
        buildsheet.build_workbook(p, h, stamp)
        gc.collect()
        assert len(buildsheet._CELL_STYLES) == 0  # nothing outlives its workbook
