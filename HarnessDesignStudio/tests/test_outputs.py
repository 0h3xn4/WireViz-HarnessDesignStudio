"""M5: output generation (drawings, tables, exports), the manifest and stale detection, and the
independent output verifier (every check has a mutation test that proves it can fail)."""

import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Callable
from pathlib import Path

import pytest

from harness_design_studio import __version__
from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core.commands import Put, apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.core.outputs import exports, system
from harness_design_studio.core.outputs.build import (
    MANIFEST,
    OutputSet,
    build_outputs,
    outputs_status,
    write_outputs,
)
from harness_design_studio.core.outputs.canvas import (
    SHEETS,
    Rect,
    Sheet,
    Text,
    fit,
    text_width,
    to_pdf,
    to_svg,
)
from harness_design_studio.core.outputs.stamp import csv_bytes, parse_csv, stamp_of
from harness_design_studio.core.outputs.verify import read_folder, verify_outputs
from harness_design_studio.core.samples import mini3, sat15, sat15_full

_CACHE: dict[str, tuple[Project, OutputSet]] = {}


def project_and_files(name: str) -> tuple[Project, dict[str, bytes]]:
    if name not in _CACHE:
        p = {"mini3": mini3, "sat15": sat15, "full": sat15_full}[name]()
        if name != "full":
            generate_project(p)
        _CACHE[name] = (p, build_outputs(p))
    p, result = _CACHE[name]
    from harness_design_studio.core import edit

    return edit.clone_with(p, []), dict(result.files)


def output_set(name: str) -> OutputSet:
    """The output set of a reference project, built once per process (it is the one
    `project_and_files` takes its files from), as a set of its own: a test may hand it to
    `write_outputs` instead of building the same files again."""
    project_and_files(name)
    result = _CACHE[name][1]
    return OutputSet(result.stamp, dict(result.files))


PROJECTS = ["mini3", "sat15", "full"]


@pytest.mark.parametrize("name", PROJECTS)
def test_verifier_is_clean_on_the_reference_projects(name: str) -> None:
    p, files = project_and_files(name)
    report = verify_outputs(p, files)
    assert report.ok, [i.render() for i in report.issues[:5]]
    assert report.wires_checked > 0


@pytest.mark.parametrize("name", PROJECTS)
def test_outputs_are_byte_identical_when_rebuilt(name: str) -> None:
    p, files = project_and_files(name)
    assert build_outputs(p).files == files


def test_every_output_type_is_produced() -> None:
    _, files = project_and_files("sat15")
    kinds = {Path(k).suffix for k in files}
    assert {".svg", ".pdf", ".csv", ".xlsx", ".yaml", ".json", ".md"} <= kinds
    for name in ("wirelist", "pinouts", "bom", "mass_length", "tests", "labels"):
        assert any(k.endswith(f"/{name}.csv") for k in files)
    assert {
        "system/block_diagram.svg",
        "system/harness_overview.pdf",
        "system/mating_matrix.csv",
        "system/traceability.csv",
        "system/drc_report.md",
        "system/export.json",
    } <= set(files)


# ---- drawings -------------------------------------------------------------------------------------


def test_svg_is_well_formed_and_uses_only_grey_without_wire_colours() -> None:
    _, files = project_and_files("sat15")
    svgs = [k for k in files if k.endswith(".svg") and k.startswith("harnesses/")]
    assert svgs
    for k in svgs:
        root = ET.fromstring(files[k])  # noqa: S314
        assert root.tag.endswith("svg")
        colours = set(re.findall(r'(?:stroke|fill)="(#[0-9a-f]{6})"', files[k].decode()))
        for c in colours:
            r, g, b = (int(c[i : i + 2], 16) for i in (1, 3, 5))
            assert abs(r - g) < 3 and abs(g - b) < 3, (
                f"{k} uses colour {c}; drawings must print in greyscale"
            )


def test_wire_colours_are_drawn_and_written_as_codes() -> None:
    """A wire with a colour is drawn in it (on a dark outline) and carries its IEC 60757 code as
    text, so a greyscale print loses nothing; a colour that is not set is drawn grey."""
    p, _ = project_and_files("sat15")
    h = p.harnesses["W010"]
    wires = [
        evolve(w, colour=c) for w, c in zip(h.wires, ["red", "BK", "blue", None], strict=False)
    ]
    apply_ops(p, [Put("harnesses", evolve(h, wires=[*wires, *h.wires[len(wires) :]]))])
    svg = build_outputs(p, harness_ids=["W010"]).files["harnesses/W010/drawing_A3_s1.svg"].decode()
    for code, hexcolour in (("RD", "#e02020"), ("BK", "#1a1a1a"), ("BU", "#1e5bd8")):
        assert hexcolour in svg
        assert re.search(rf">{wires[0].id[:4]}-\d+  {code}<", svg)
    assert "#808080" in svg  # the wire without a colour


def test_the_drawing_shows_connector_tables_and_cable_blocks() -> None:
    p, files = project_and_files("sat15")
    h = p.harnesses["W001"]
    text = " ".join(
        re.findall(r"<text[^>]*>([^<]*)</text>", files["harnesses/W001/drawing_A3_s1.svg"].decode())
    )
    for c in h.connectors:
        assert c.id in text and c.part_id in text
    assert "male" in text or "female" in text  # the gender, in words
    assert re.search(r"\d+x +(AWG|pending)", text)  # the cable block summary


@pytest.mark.skipif(shutil.which("pdfinfo") is None, reason="poppler not installed")
def test_pdfs_open_in_a_real_reader_with_the_right_page_size(tmp_path: Path) -> None:
    _, files = project_and_files("sat15")
    for rel, size in (
        ("harnesses/W010/drawing_A3.pdf", (1190.6, 841.9)),
        ("harnesses/W010/drawing_A4.pdf", (841.9, 595.3)),
    ):
        f = tmp_path / "x.pdf"
        f.write_bytes(files[rel])
        info = subprocess.run(
            ["pdfinfo", str(f)], capture_output=True, text=True, check=True
        ).stdout
        m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", info)
        assert m and abs(float(m.group(1)) - size[0]) < 1 and abs(float(m.group(2)) - size[1]) < 1


def test_long_harness_paginates_and_numbers_its_sheets() -> None:
    p, files = project_and_files("sat15")
    h = p.harnesses["W010"]
    many = [evolve(h.wires[k % len(h.wires)], id=f"W010-{k + 1:03d}") for k in range(70)]
    apply_ops(p, [Put("harnesses", evolve(h, wires=many, shields=[]))])
    out = build_outputs(p, harness_ids=["W010"])
    sheets = sorted(k for k in out.files if re.search(r"drawing_A3_s\d+\.svg", k))
    assert len(sheets) >= 2
    assert f"1 / {len(sheets)}" in " ".join(
        re.findall(r"<text[^>]*>([^<]*)</text>", out.files[sheets[0]].decode())
    )
    assert "(continued)" in out.files[sheets[1]].decode()


def test_title_block_carries_status_revision_and_stamp() -> None:
    p, files = project_and_files("sat15")
    text = files["harnesses/W001/drawing_A3_s1.svg"].decode()
    for needle in ("W001", "draft", stamp_of(p).short, __version__):
        assert needle in text


def test_text_metrics_are_exact_for_the_monospaced_font() -> None:
    assert text_width("abcd", 10) == pytest.approx(24.0)
    assert fit("abcdefghij", text_width("abcde", 3.0), 3.0).endswith("~")
    assert fit("abc", 100, 3.0) == "abc"


def test_pdf_and_svg_escape_special_characters() -> None:
    s = Sheet(*SHEETS["A4"])
    s.add(Text(10, 10, "a<b & (c) \\ é ✓"), Rect(1, 1, 5, 5))
    ET.fromstring(to_svg(s, "m"))  # noqa: S314
    # parentheses and the backslash are escaped inside the PDF string; the accent is cp1252
    assert b"(a<b & \\(c\\) \\\\ \xe9" in to_pdf([s], "t", "m")


# ---- system outputs ---------------------------------------------------------------------------------


def test_print_palette_has_contrast_and_dash_differences() -> None:
    def lum(c: str) -> float:
        v = [int(c[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]

    for name, (color, _dash) in system.CATEGORY_STYLE.items():
        assert 1.05 / (lum(color) + 0.05) >= 3.0, name
    for color in (system.NOMINAL_COLOR, system.REDUNDANT_COLOR):
        assert 1.05 / (lum(color) + 0.05) >= 3.0
    assert system.REDUNDANT_DASH is not None  # redundant differs from nominal without colour


def test_tables_never_invent_numbers() -> None:
    _, files = project_and_files("sat15")
    wl = parse_csv(files["harnesses/W001/wirelist.csv"])
    assert {row[7] for row in wl[1:]} == {"pending"}
    tests = parse_csv(files["harnesses/W001/tests.csv"])
    assert {row[5] for row in tests[1:]} == {"TBD (placeholder)"}
    ml = parse_csv(files["system/mass_length.csv"])
    assert ml[-1][8] == "no"


def test_full_example_has_gauges_lengths_mass_and_limits() -> None:
    p, files = project_and_files("full")
    ml = parse_csv(files["system/mass_length.csv"])
    assert ml[-1][8] == "yes" and float(ml[-1][5]) > 0
    tests = parse_csv(files["harnesses/W001/tests.csv"])
    assert {row[5] for row in tests[1:] if row[1] == "continuity"} == {"1 ohm max"}
    assert any(w.gauge_awg for h in p.harnesses.values() for w in h.wires)  # type: ignore[attr-defined]


def test_csv_cells_that_look_like_formulas_are_marked() -> None:
    st = stamp_of(mini3())
    data = csv_bytes([["a", "b"], ["=SUM(A1)", "-5"], ["@x", "+y"]], st)
    assert b"'=SUM(A1)" in data and b",-5" in data and b"'@x" in data
    assert parse_csv(data) == [["a", "b"], ["=SUM(A1)", "-5"], ["@x", "+y"]]


def test_xlsx_is_deterministic_and_keeps_formula_text_as_text() -> None:
    st = stamp_of(mini3())
    a = exports.xlsx_bytes({"T": [["h"], ["=1+1"]]}, st)
    assert a == exports.xlsx_bytes({"T": [["h"], ["=1+1"]]}, st)
    with zipfile.ZipFile(__import__("io").BytesIO(a)) as z:
        sheet = z.read("xl/worksheets/sheet2.xml").decode()
    assert "<f>" not in sheet and "=1+1" in sheet


def test_wireviz_yaml_and_json_export_have_the_documented_shape() -> None:
    p, files = project_and_files("mini3")
    y = files["harnesses/W001/wireviz.yaml"].decode()
    assert "connectors:" in y and "cables:" in y and "connections:" in y
    doc = json.loads(files["system/export.json"])
    assert doc["format"] == "harness-design-studio-export" and doc["format_version"] == 1
    assert doc["model_hash"] == stamp_of(p).model_hash  # type: ignore[arg-type]
    assert {
        "units",
        "interfaces",
        "harnesses",
        "parts",
        "interface_types",
        "box_connectors",
    } <= set(doc)


# ---- manifest, folder, stale detection --------------------------------------------------------------


def test_write_status_and_stale_detection(tmp_path: Path) -> None:
    p, _ = project_and_files("sat15")
    folder = tmp_path / "outputs"
    assert outputs_status(p, folder).state == "none"  # type: ignore[arg-type]
    write_outputs(p, folder, output_set("sat15"))  # type: ignore[arg-type]
    assert outputs_status(p, folder).state == "current"  # type: ignore[arg-type]
    assert verify_outputs(p, read_folder(folder)).ok  # type: ignore[arg-type]
    (folder / "system" / "bom.csv").write_bytes(b"# tampered\n")
    assert outputs_status(p, folder).state == "current"  # type: ignore[arg-type]  # quick check
    assert outputs_status(p, folder, deep=True).state == "modified"  # type: ignore[arg-type]
    unit = next(iter(p.units.values()))  # type: ignore[attr-defined]
    apply_ops(p, [Put("units", evolve(unit, name="Renamed"))])  # type: ignore[arg-type]
    assert outputs_status(p, folder).state == "stale"  # type: ignore[arg-type]
    report = verify_outputs(p, read_folder(folder))  # type: ignore[arg-type]
    assert report.stale and "out_stale" in {i.code for i in report.errors}


def test_write_keeps_foreign_files_and_removes_retired_ones(tmp_path: Path) -> None:
    p, _ = project_and_files("sat15")
    folder = tmp_path / "outputs"
    write_outputs(p, folder, output_set("sat15"))  # type: ignore[arg-type]
    (folder / "my-notes.txt").write_text("keep me")
    gone = sorted(p.harnesses)[-1]  # type: ignore[attr-defined]
    from harness_design_studio.core.commands import Delete

    apply_ops(p, [Delete("harnesses", gone)])  # type: ignore[arg-type]
    write_outputs(p, folder)  # type: ignore[arg-type]
    assert (folder / "my-notes.txt").read_text() == "keep me"
    assert not (folder / "harnesses" / gone).exists() or not any(
        (folder / "harnesses" / gone).iterdir()
    )
    assert outputs_status(p, folder).state == "current"  # type: ignore[arg-type]


def test_unreadable_manifest_is_reported(tmp_path: Path) -> None:
    p, _ = project_and_files("mini3")
    folder = tmp_path / "o"
    write_outputs(p, folder, output_set("mini3"))  # type: ignore[arg-type]
    (folder / MANIFEST).write_text("{not json")
    assert outputs_status(p, folder).state == "unreadable"  # type: ignore[arg-type]
    assert "out_manifest" in {i.code for i in verify_outputs(p, read_folder(folder)).errors}  # type: ignore[arg-type]


def test_cancel_stops_the_build() -> None:
    from harness_design_studio.core.outputs.build import OutputsCancelled

    p, _ = project_and_files("sat15")
    with pytest.raises(OutputsCancelled):
        build_outputs(p, cancel=lambda: True)  # type: ignore[arg-type]
    seen: list[float] = []
    build_outputs(p, harness_ids=["W001", "W002"], progress=lambda f, _t: seen.append(f))  # type: ignore[arg-type]
    assert seen == sorted(seen) and seen


# ---- verifier mutation tests (each check must be able to fail) -------------------------------------


def edit_csv(
    files: dict[str, bytes], rel: str, fn: Callable[[list[list[str]]], object], p: object
) -> None:
    table = parse_csv(files[rel])
    fn(table)
    files[rel] = csv_bytes(table, stamp_of(p))  # type: ignore[arg-type]


def codes(p: object, files: dict[str, bytes]) -> set[str]:
    return {i.code for i in verify_outputs(p, files).errors}  # type: ignore[arg-type]


H = "harnesses/W010"


def test_detects_a_missing_file() -> None:
    p, f = project_and_files("sat15")
    del f[f"{H}/labels.csv"]
    assert "out_missing" in codes(p, f)


def test_detects_wire_missing_duplicated_extra_and_different() -> None:
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/wirelist.csv", lambda t: t.pop(1), p)
    assert "out_wire_missing" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/wirelist.csv", lambda t: t.append(list(t[1])), p)
    assert "out_wire_duplicated" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/wirelist.csv", lambda t: t.append(["W010-999", *t[1][1:]]), p)
    assert "out_wire_extra" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/wirelist.csv", lambda t: t[1].__setitem__(6, "99"), p)
    assert "out_wire_differs" in codes(p, f)
    p, f = project_and_files("full")
    edit_csv(f, f"{H}/wirelist.csv", lambda t: t[1].__setitem__(10, "9.9"), p)
    assert "out_wire_differs" in codes(p, f)


def test_detects_wrong_pinouts_bom_tests_labels_yaml_xlsx() -> None:
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/pinouts.csv", lambda t: t[1].__setitem__(7, "W999"), p)
    assert "out_pinout" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/bom.csv", lambda t: t[1].__setitem__(6, "99"), p)
    assert "out_bom" in codes(p, f)
    p, f = project_and_files("full")
    edit_csv(
        f, f"{H}/bom.csv", lambda t: [r.__setitem__(6, "0.5") for r in t[1:] if r[7] == "m"], p
    )
    assert "out_bom" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/tests.csv", lambda t: t.pop(1), p)
    assert "out_tests" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/tests.csv", lambda t: t.pop(-1), p)
    assert "out_tests" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, f"{H}/labels.csv", lambda t: t.pop(), p)
    assert "out_labels" in codes(p, f)
    p, f = project_and_files("sat15")
    f[f"{H}/wireviz.yaml"] = f[f"{H}/wireviz.yaml"].replace(b"  - - ", b"  - x ", 1)
    assert "out_yaml" in codes(p, f)
    p, f = project_and_files("sat15")
    st = stamp_of(p)
    f[f"{H}/W010.xlsx"] = exports.xlsx_bytes({"Wire list": [["Wire"], ["W010-001"]]}, st)
    assert "out_xlsx" in codes(p, f)


def test_detects_drawing_problems() -> None:
    p, f = project_and_files("sat15")
    f[f"{H}/drawing_A3_s1.svg"] = f[f"{H}/drawing_A3_s1.svg"].replace(b"W010-001", b"W010-XXX")
    assert "out_drawing" in codes(p, f)
    p, f = project_and_files("sat15")
    f[f"{H}/drawing_A3_s1.svg"] = f[f"{H}/drawing_A3_s1.svg"].replace(b"1 / 1", b"1 / 9")
    assert "out_drawing" in codes(p, f)
    p, f = project_and_files("sat15")
    del f[f"{H}/drawing_A3_s1.svg"]
    assert codes(p, f) == {"out_missing"}
    p, f = project_and_files("sat15")
    f[f"{H}/drawing_A4.pdf"] = f[f"{H}/drawing_A4.pdf"].replace(b"W010-001", b"W010-XXX")
    assert "out_drawing" in codes(p, f)


def test_detects_wrong_stamps() -> None:
    p, f = project_and_files("sat15")
    f[f"{H}/bom.csv"] = f[f"{H}/bom.csv"].replace(stamp_of(p).short.encode(), b"000000000000", 1)
    assert "out_stamp" in codes(p, f)
    p, f = project_and_files("sat15")
    f["system/block_diagram.svg"] = f["system/block_diagram.svg"].replace(
        stamp_of(p).short.encode(), b"000000000000"
    )
    assert "out_stamp" in codes(p, f)
    p, f = project_and_files("sat15")
    f["system/drc_report.md"] = b"<!-- harness-design-studio 0 model 000000000000 -->\nWaived:"
    assert "out_stamp" in codes(p, f)


def test_detects_system_level_problems() -> None:
    p, f = project_and_files("sat15")
    edit_csv(f, "system/mass_length.csv", lambda t: t[-1].__setitem__(1, "1"), p)
    assert "out_mass" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, "system/bom.csv", lambda t: t[1].__setitem__(6, "1"), p)
    assert "out_bom" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, "system/mating_matrix.csv", lambda t: t.pop(1), p)
    assert "out_matrix" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, "system/traceability.csv", lambda t: t[1].__setitem__(7, "no"), p)
    assert "out_trace" in codes(p, f)
    p, f = project_and_files("sat15")
    f["system/export.json"] = f["system/export.json"].replace(b'"units": [', b'"units": [{}, ', 1)
    assert "out_json" in codes(p, f)
    p, f = project_and_files("sat15")
    f["system/block_diagram.svg"] = f["system/block_diagram.svg"].replace(b">OBC1<", b">XXXX<")
    assert "out_diagram" in codes(p, f)
    p, f = project_and_files("sat15")
    edit_csv(f, "system/drc_findings.csv", lambda t: t.pop(1), p)
    assert "out_drc" in codes(p, f)


def test_detects_modified_and_unlisted_files_in_a_folder(tmp_path: Path) -> None:
    p, _ = project_and_files("mini3")
    folder = tmp_path / "o"
    write_outputs(p, folder, output_set("mini3"))  # type: ignore[arg-type]
    (folder / "system" / "bom.csv").write_bytes(
        (folder / "system" / "bom.csv").read_bytes() + b"x,y\n"
    )
    (folder / "extra.txt").write_text("hi")
    r = verify_outputs(p, read_folder(folder))  # type: ignore[arg-type]
    assert "out_modified" in {i.code for i in r.errors}
    assert "out_unlisted" in {i.code for i in r.issues}
    (folder / "system" / "bom.csv").unlink()
    assert "out_missing" in {i.code for i in verify_outputs(p, read_folder(folder)).errors}  # type: ignore[arg-type]


# ---- CLI --------------------------------------------------------------------------------------------


def test_cli_export_then_verify_outputs(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    p, _ = project_and_files("sat15")
    save_project(p, tmp_path / "p")  # type: ignore[arg-type]
    assert cli_main(["export", str(tmp_path / "p")]) == 0
    assert (tmp_path / "p" / "outputs" / MANIFEST).is_file()
    assert cli_main(["verify", str(tmp_path / "p"), "--outputs"]) == 0
    (tmp_path / "p" / "outputs" / "system" / "bom.csv").write_bytes(b"# x\n")
    assert cli_main(["verify", str(tmp_path / "p"), "--outputs"]) == 1
    assert "out_modified" in capsys.readouterr().out


def test_cli_export_needs_harnesses(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "m")
    # mini3 has a manual harness, so export works; an empty project does not
    from harness_design_studio.core.samples import new_project

    save_project(new_project("empty"), tmp_path / "e")
    assert cli_main(["export", str(tmp_path / "e")]) == 1
    assert cli_main(["verify", str(tmp_path / "m"), "--outputs"]) == 1  # no outputs folder yet


def test_outputs_of_a_saved_project_do_not_change_its_model_hash(tmp_path: Path) -> None:
    from harness_design_studio.core.io.layout import model_hash
    from harness_design_studio.core.io.loader import load_project

    p, _ = project_and_files("sat15")
    save_project(p, tmp_path / "p")  # type: ignore[arg-type]
    before = model_hash(load_project(tmp_path / "p").project)
    cli_main(["export", str(tmp_path / "p")])
    assert model_hash(load_project(tmp_path / "p").project) == before


# ---- golden files -------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["mini3", "sat15", "full"])
def test_outputs_match_the_golden_digests(name: str) -> None:
    from tests.helpers import FIXTURES, output_digests

    _, files = project_and_files(name)
    golden = json.loads(
        (FIXTURES / "outputs" / f"{'sat15_full' if name == 'full' else name}.json").read_text(
            encoding="utf-8"
        )
    )
    got = output_digests(files)
    assert sorted(got) == sorted(golden)
    assert [k for k in got if got[k] != golden[k]] == []


def test_mini3_text_outputs_match_the_reviewable_golden_files() -> None:
    from tests.helpers import FIXTURES

    _, files = project_and_files("mini3")
    root = FIXTURES / "outputs" / "mini3"
    checked = 0
    for rel, data in files.items():
        if rel.endswith((".csv", ".svg", ".yaml", ".md", ".json")):
            assert (root / rel).read_bytes() == data, rel
            checked += 1
    assert checked > 20


def test_shields_are_drawn_as_sleeves_around_their_wires() -> None:
    """Each shield gets a header with its ID and kind and a jacket round its wires; the end
    terminations are drawn (a solid bar for a 360 degree backshell)."""
    p, files = project_and_files("sat15")
    shielded = [(h, s) for h in p.harnesses.values() for s in h.shields]
    assert shielded
    h, s = shielded[0]
    key = f"harnesses/{h.id}/drawing_A3_s1.svg"
    svg = files[key].decode()
    text = " ".join(re.findall(r"<text[^>]*>([^<]*)</text>", svg))
    assert f"{s.id}  {s.kind}" in text
    assert "#e9e9e9" in svg  # the jacket
    for end in (s.end_a, s.end_b):
        assert {"backshell_360": "backshell 360", "pigtail": "pigtail", "floating": "floating"}[
            end
        ] in text
