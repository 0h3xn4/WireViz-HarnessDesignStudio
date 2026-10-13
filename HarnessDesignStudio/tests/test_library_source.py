"""REQ-LIB-02: the parts library records where its data come from (source and date)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core.commands import History
from harness_design_studio.core.imports import ImportError_
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.library_import import describe_library, library_ops
from harness_design_studio.core.model import LibraryInfo
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.samples import mini3


def test_a_date_must_be_a_real_iso_date() -> None:
    assert LibraryInfo(date="2026-09-30").date == "2026-09-30"
    for bad in ("30.09.2026", "2026-13-01", "yesterday"):
        with pytest.raises(ValueError):
            LibraryInfo(date=bad)


def test_old_manifests_without_source_and_date_still_load() -> None:
    info = LibraryInfo.model_validate({"name": "x", "version": "1"})
    assert info.source is None and info.date is None


def test_recording_the_source_is_one_undoable_step() -> None:
    p = mini3()
    h = History(p)
    h.execute("source", library_ops(p, source="parts.csv", date="2026-10-01", version="4"))
    assert p.library_info.source == "parts.csv" and p.library_info.version == "4"
    h.undo()
    assert p.library_info.source is None and p.library_info.version == "0"
    assert library_ops(p) == [] and library_ops(p, version="0") == []  # nothing to change


def test_a_bad_date_is_refused_before_anything_changes() -> None:
    with pytest.raises(ImportError_, match="YYYY-MM-DD"):
        library_ops(mini3(), date="30.09.2026")


def test_the_description_says_what_is_missing() -> None:
    p = mini3()
    assert "source: not recorded" in describe_library(
        p
    ) and "date: not recorded" in describe_library(p)


def test_provenance_carries_the_library_source(tmp_path: Path) -> None:
    p = mini3()
    History(p).execute("s", library_ops(p, source="file.csv", date="2026-10-01"))
    doc = json.loads(build_outputs(p).files["system/provenance.json"])
    assert doc["library"]["source"] == "file.csv" and doc["library"]["date"] == "2026-10-01"


def test_cli_library_and_import_record_the_origin(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    proj = tmp_path / "p"
    assert main(["new", str(proj), "--template", "blank"]) == 0
    capsys.readouterr()
    assert main(["library", str(proj)]) == 0
    assert "source: not recorded" in capsys.readouterr().out
    assert main(["library", str(proj), "--library-date", "31.12.2026"]) == 2
    assert (
        main(["library", str(proj), "--library-version", "4", "--library-date", "2026-09-30"]) == 0
    )
    csv = tmp_path / "parts.csv"
    csv.write_text("id,category,approval\nX-1,connector,Yes\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["import-parts", str(proj), str(csv), "--approved", "Yes"]) == 0
    out = capsys.readouterr().out
    assert "parts.csv (sha256 " in out and "version 4" in out and "data of 2026-09-30" in out
    info = load_project(proj).project.library_info
    assert info.source and info.source.startswith("parts.csv (sha256 ")
    assert (
        main(
            [
                "import-parts",
                str(proj),
                str(csv),
                "--approved",
                "Yes",
                "--library-source",
                "ESCC file",
            ]
        )
        == 0
    )
    assert load_project(proj).project.library_info.source == "ESCC file"
