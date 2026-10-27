"""Regression tests for the low output findings of the October audit: D-14 (write_outputs with a
damaged manifest, empty folders left behind, links met by the checks) and D-17 (routing
preconditions)."""

import json
import shutil
from pathlib import Path

import pytest

from harness_design_studio.core.commands import Delete, apply_ops
from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.model import Project
from harness_design_studio.core.outputs.build import (
    MANIFEST,
    damaged_files,
    outputs_status,
    write_outputs,
)
from harness_design_studio.core.outputs.verify import read_folder
from harness_design_studio.core.routing import Geometry, RouteLink, route_links
from harness_design_studio.core.samples import sat15


@pytest.fixture(scope="module")
def written_sat15(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The output set of the generated sample written to a folder once per module (building and
    writing it takes several seconds). A test never works in this folder: `exported` copies it."""
    p = sat15()
    generate_project(p)
    folder = tmp_path_factory.mktemp("written_sat15") / "outputs"
    write_outputs(p, folder)
    return folder


def exported(tmp_path: Path, written: Path) -> tuple[Project, Path]:
    """A new generated sample and a folder of its own that holds its written output set (a copy
    of the one written once)."""
    p = sat15()
    generate_project(p)
    folder = tmp_path / "outputs"
    shutil.copytree(written, folder)
    return p, folder


# ---- D-14 -------------------------------------------------------------------------------------------


def test_a_manifest_that_lists_a_folder_does_not_make_every_export_fail(
    tmp_path: Path, written_sat15: Path
) -> None:
    p, folder = exported(tmp_path, written_sat15)
    doc = json.loads((folder / MANIFEST).read_text())
    doc["files"].append({"path": "harnesses", "sha256": "0" * 64})
    (folder / MANIFEST).write_text(json.dumps(doc))
    write_outputs(p, folder)  # it was "The outputs could not be written (Is a directory)"
    assert (folder / "harnesses").is_dir()
    assert outputs_status(p, folder, deep=True).state == "current"


def test_the_empty_folder_of_a_removed_harness_is_removed_too(
    tmp_path: Path, written_sat15: Path
) -> None:
    p, folder = exported(tmp_path, written_sat15)
    gone, kept = sorted(p.harnesses)[-1], sorted(p.harnesses)[-2]
    (folder / "harnesses" / kept / "my-notes.txt").write_text("keep me")
    apply_ops(p, [Delete("harnesses", gone), Delete("harnesses", kept)])
    write_outputs(p, folder)
    assert not (folder / "harnesses" / gone).exists()  # it was left behind, empty
    assert (folder / "harnesses" / kept / "my-notes.txt").read_text() == "keep me"
    assert (folder / "harnesses").is_dir() and (folder / "system").is_dir()


def test_the_deep_status_treats_a_linked_output_file_as_changed(
    tmp_path: Path, written_sat15: Path
) -> None:
    p, folder = exported(tmp_path, written_sat15)
    target = folder / "system" / "bom.csv"
    copy = tmp_path / "bom-copy.csv"
    copy.write_bytes(target.read_bytes())
    target.unlink()
    target.symlink_to(copy)
    assert damaged_files(folder) == ["system/bom.csv"]
    status = outputs_status(p, folder, deep=True)
    assert status.state == "modified" and "system/bom.csv" in status.detail


def test_reading_an_output_folder_does_not_follow_a_file_link(
    tmp_path: Path, written_sat15: Path
) -> None:
    _p, folder = exported(tmp_path, written_sat15)
    secret = tmp_path / "secret.txt"
    secret.write_text("not part of the outputs")
    (folder / "system" / "link.txt").symlink_to(secret)
    assert "system/link.txt" not in read_folder(folder)


# ---- D-17 -------------------------------------------------------------------------------------------


def test_routing_names_the_missing_gap_instead_of_raising_a_key_error() -> None:
    geo = Geometry(
        gaps={0: (206.0, 460.0)},
        edges={0: (30.0, 206.0), 1: (460.0, 636.0), 2: (890.0, 1066.0)},
        blocks={0: [], 1: [], 2: []},
    )

    def link(iid: str, lane_a: int, lane_b: int) -> RouteLink:
        return RouteLink(iid, "U", "V", lane_a, lane_b, (206.0, 5.0), (890.0, 7.0), "right", "data")

    assert route_links([link("A", 0, 1)], geo)["A"]  # the gap between lanes 0 and 1 is known
    with pytest.raises(ValueError, match="'B'.*lane 1 and lane 2"):
        route_links([link("B", 1, 2)], geo)
    with pytest.raises(ValueError, match="'C'"):
        route_links([link("C", -1, 0)], geo)
