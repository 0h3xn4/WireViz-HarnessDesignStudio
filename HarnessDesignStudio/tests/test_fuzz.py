"""M9: robustness. Corrupt, hostile or random input must never crash the tool: loaders either
accept data (and then every later stage copes with it) or set it aside with a clear message.
`HARNESS_FUZZ_EXAMPLES=5000 pytest tests/test_fuzz.py` runs the long version (tools/fuzz.py)."""

import contextlib
import copy
import json
import os
import zipfile
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from harness_design_studio.core import checks, drc
from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.generate.engine import generate_project, plan_generation
from harness_design_studio.core.imports import (
    ImportError_,
    parse_csv,
    plan_interface_import,
    read_table,
)
from harness_design_studio.core.integrity import check_integrity
from harness_design_studio.core.io.canonical import loads_strict
from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.io.loader import load_from_files, load_project, read_tree
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.outputs.build import build_outputs, outputs_status
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.verify import verify_project
from tests.helpers import time_limit

pytestmark = pytest.mark.filterwarnings(
    "ignore::hypothesis.errors.HypothesisWarning"
)  # reprs of corrupted projects are large
EXAMPLES = int(os.environ.get("HARNESS_FUZZ_EXAMPLES", "40"))
FUZZ = settings(max_examples=EXAMPLES, deadline=None, suppress_health_check=list(HealthCheck))

_PROJECT = mini3()
generate_project(_PROJECT)
BASE_FILES: dict[str, Any] = {rel: loads_strict(data) for rel, data in serialize(_PROJECT).items()}
BASE_OUTPUTS = build_outputs(_PROJECT).files

scalar = st.one_of(
    st.none(), st.booleans(), st.integers(-(2**40), 2**40), st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=40), st.just(""), st.just("A" * 300), st.just("\x00"), st.just("../../etc/passwd"),
)  # fmt: skip
json_value = st.recursive(
    scalar,
    lambda kids: st.one_of(
        st.lists(kids, max_size=4), st.dictionaries(st.text(max_size=8), kids, max_size=4)
    ),
    max_leaves=12,
)


def paths(node: Any, prefix: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    out = [prefix]
    if isinstance(node, dict):
        for k, v in node.items():
            out += paths(v, (*prefix, k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out += paths(v, (*prefix, i))
    return out


def mutate(doc: Any, path: tuple[Any, ...], how: str, value: Any) -> Any:
    if not path:
        return value
    node = doc
    for step in path[:-1]:
        node = node[step]
    last = path[-1]
    if how == "delete":
        del node[last]
    elif how == "duplicate" and isinstance(node, list):
        node.insert(last, copy.deepcopy(node[last]))
    else:
        node[last] = value
    return doc


@st.composite
def corrupted_files(draw: Any) -> dict[str, Any]:
    files = copy.deepcopy(BASE_FILES)
    for _ in range(draw(st.integers(1, 3))):
        rel = draw(st.sampled_from(sorted(files)))
        how = draw(st.sampled_from(["replace", "delete", "duplicate", "replace"]))
        path = draw(st.sampled_from(paths(files[rel])))
        try:
            files[rel] = mutate(files[rel], path, how, draw(json_value))
        except (KeyError, IndexError, TypeError):
            continue
    if draw(st.booleans()):  # sometimes a whole file is dropped or replaced
        files[draw(st.sampled_from(sorted(files)))] = draw(json_value)
    if draw(st.integers(0, 9)) == 0:
        files.pop("project.json", None)
    return files


@FUZZ
@given(corrupted_files())
def test_any_accepted_project_survives_every_later_stage(files: dict[str, Any]) -> None:
    result = load_from_files(files)
    p = result.project
    assert isinstance(result.issues, list)
    check_integrity(p)
    model_hash(p)
    serialize(p)
    checks.find(p)
    drc.run(p)
    verify_project(p)
    plan_generation(p)
    if not p.read_only and p.harnesses:
        out = build_outputs(p)
        verify_outputs(p, out.files)


@FUZZ
@given(st.data())
def test_byte_level_damage_on_disk_never_crashes_the_loader(data: st.DataObject) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "p"
        save_project(_PROJECT, root)
        files = sorted(p for p in root.rglob("*.json"))
        for _ in range(data.draw(st.integers(1, 3))):
            f = data.draw(st.sampled_from(files))
            raw = bytearray(f.read_bytes())
            kind = data.draw(
                st.sampled_from(["truncate", "flip", "garbage", "empty", "bom", "nested"])
            )
            if kind == "truncate":
                raw = raw[: data.draw(st.integers(0, max(0, len(raw))))]
            elif kind == "flip" and raw:
                for _ in range(data.draw(st.integers(1, 6))):
                    raw[data.draw(st.integers(0, len(raw) - 1))] ^= data.draw(st.integers(1, 255))
            elif kind == "garbage":
                raw = bytearray(data.draw(st.binary(max_size=200)))
            elif kind == "empty":
                raw = bytearray()
            elif kind == "bom":
                raw = bytearray(b"\xef\xbb\xbf") + raw
            else:
                raw = bytearray(
                    b"[" * 50_000 + b"]" * 50_000
                )  # nesting far past the parser's depth
            f.write_bytes(bytes(raw))
        try:
            result = load_project(root)
        except Exception as exc:  # only the documented error type may escape
            assert type(exc).__name__ == "LoadError", repr(exc)
            return
        read_tree(root)
        check_integrity(result.project)
        if result.project.recovered:  # a damaged project must refuse to overwrite its own folder
            with pytest.raises(SaveError, match="could not be loaded|protect"):
                save_project(result.project, root)


@FUZZ
@given(st.text(max_size=3000), st.lists(st.integers(0, 6), min_size=5, max_size=5))
def test_csv_import_survives_any_text(text: str, cols: list[int]) -> None:
    try:
        table = parse_csv(text)
    except ImportError_:
        return
    plan = plan_interface_import(
        _PROJECT, table, dict(zip(("id", "type", "from", "to", "redundancy"), cols, strict=True))
    )
    assert len(plan.rows) == max(len(table) - 1, 0)  # one verdict per data row, whatever the text
    assert plan.ok_count + plan.error_count == len(plan.rows)


@FUZZ
@given(st.binary(max_size=3000))
def test_xlsx_import_rejects_random_bytes_politely(raw: bytes) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "x.xlsx"
        f.write_bytes(raw)
        with contextlib.suppress(ImportError_):
            read_table(f)


def test_zip_bomb_workbook_is_refused_quickly(tmp_path: Path) -> None:
    import time

    f = tmp_path / "bomb.xlsx"
    with zipfile.ZipFile(f, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        z.writestr("xl/workbook.xml", "<workbook/>")
        z.writestr(
            "xl/worksheets/sheet1.xml",
            "<worksheet><sheetData>" + "<row><c/></row>" * 5_000_000 + "</sheetData></worksheet>",
        )
    assert f.stat().st_size < 8 * 1024 * 1024
    t = time.perf_counter()
    with pytest.raises(ImportError_):
        read_table(f)
    assert time.perf_counter() - t < time_limit(5)


@FUZZ
@given(st.data())
def test_damaged_outputs_never_crash_the_verifier(data: st.DataObject) -> None:
    files = dict(BASE_OUTPUTS)
    for _ in range(data.draw(st.integers(1, 4))):
        rel = data.draw(st.sampled_from(sorted(files)))
        raw = bytearray(files[rel])
        kind = data.draw(st.sampled_from(["truncate", "flip", "garbage", "delete"]))
        if kind == "delete":
            files.pop(rel)
            continue
        if kind == "truncate":
            raw = raw[: data.draw(st.integers(0, len(raw)))]
        elif kind == "flip" and raw:
            raw[data.draw(st.integers(0, len(raw) - 1))] ^= 0xFF
        else:
            raw = bytearray(data.draw(st.binary(max_size=100)))
        files[rel] = bytes(raw)
    verify_outputs(_PROJECT, files)


@FUZZ
@given(json_value)
def test_any_manifest_content_is_handled(doc: Any) -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "manifest.json").write_text(json.dumps(doc))
        outputs_status(_PROJECT, tmp, deep=True)
        verify_outputs(_PROJECT, {"manifest.json": json.dumps(doc).encode()})


def test_regression_bare_carriage_returns_are_read_as_line_breaks() -> None:
    """Found by fuzzing: a file with old-Mac line endings made the csv module raise."""
    assert parse_csv("id,type\rIF-1,rs422\rIF-2,can") == [
        ["id", "type"],
        ["IF-1", "rs422"],
        ["IF-2", "can"],
    ]
    assert parse_csv("a\r\nb") == [["a"], ["b"]]
