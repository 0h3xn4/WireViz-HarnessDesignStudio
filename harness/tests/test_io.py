"""REQ-IO-01: canonical, deterministic, lossless project files."""

import json
import sys
from pathlib import Path

import pytest

from harness_design_studio.core.io.layout import model_hash, serialize
from harness_design_studio.core.io.loader import disk_fingerprint, load_project, non_canonical_files
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Unit, evolve
from harness_design_studio.core.samples import mini3
from tests.helpers import MINI3


def tree(root: Path) -> dict[str, bytes]:
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and not p.name.endswith(".bak")
    }


def test_golden_mini3_matches_committed_fixture(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "p")
    assert tree(tmp_path / "p") == tree(MINI3)


def test_round_trip_is_byte_identical(tmp_path: Path) -> None:
    result = load_project(MINI3)
    assert not result.has_errors and not result.project.recovered
    save_project(result.project, tmp_path / "again")
    assert tree(tmp_path / "again") == tree(MINI3)


def test_serialization_is_deterministic_and_order_independent() -> None:
    a = mini3()
    b = mini3()
    b.units = dict(reversed(list(b.units.items())))
    b.parts = dict(reversed(list(b.parts.items())))
    assert serialize(a) == serialize(b)
    assert model_hash(a) == model_hash(b)


def test_model_hash_changes_with_model_not_tool_version() -> None:
    p = mini3()
    h = model_hash(p)
    p.meta = evolve(p.meta, tool_version="9.9.9")
    assert model_hash(p) == h
    p.units["OBC"] = evolve(p.units["OBC"], name="renamed")
    assert model_hash(p) != h


def test_files_are_grouped_per_subsystem() -> None:
    files = serialize(mini3())
    assert {
        "logical/units/avionics.json",
        "logical/units/power.json",
        "logical/units/aocs.json",
    } <= set(files)
    assert "physical/harnesses/W001.json" in files


def test_second_save_writes_nothing(tmp_path: Path) -> None:
    p = mini3()
    first = save_project(p, tmp_path / "p")
    assert first.written
    second = save_project(p, tmp_path / "p")
    assert second.written == [] and second.removed == []


def test_small_change_touches_one_file(tmp_path: Path) -> None:
    p = mini3()
    save_project(p, tmp_path / "p")
    p.units["OBC"] = evolve(p.units["OBC"], notes="changed")
    result = save_project(p, tmp_path / "p")
    assert result.written == ["logical/units/avionics.json"]
    assert (tmp_path / "p/logical/units/avionics.json.bak").exists()


def test_removed_object_file_is_kept_as_bak(tmp_path: Path) -> None:
    p = mini3()
    save_project(p, tmp_path / "p")
    del p.harnesses["W001"]
    result = save_project(p, tmp_path / "p")
    assert result.removed == ["physical/harnesses/W001.json"]
    assert (tmp_path / "p/physical/harnesses/W001.json.bak").exists()
    assert "W001" not in load_project(tmp_path / "p").project.harnesses


def test_subsystem_names_with_odd_characters(tmp_path: Path) -> None:
    p = mini3()
    for n, name in enumerate(("Антенна", "A/B:C", "CON", "..", "   ", "x" * 200)):
        p.units[f"U{n}"] = Unit(id=f"U{n}", name="n", subsystem=name)
    save_project(p, tmp_path / "p")
    loaded = load_project(tmp_path / "p")
    assert not loaded.has_errors
    assert {u.subsystem for u in loaded.project.units.values()} == {
        u.subsystem for u in p.units.values()
    }


def test_unicode_survives(tmp_path: Path) -> None:
    p = mini3()
    p.units["OBC"] = evolve(p.units["OBC"], notes="Bordcomputer – Überspannungsschutz ✓ 日本語")
    save_project(p, tmp_path / "p")
    assert load_project(tmp_path / "p").project.units["OBC"].notes.endswith("日本語")


def _can_name_files(name: str) -> bool:
    try:
        name.encode(sys.getfilesystemencoding(), "strict")
    except UnicodeEncodeError:
        return False
    return True


@pytest.mark.skipif(not _can_name_files("ü ñ p"), reason="the file system encoding is not Unicode")
def test_unicode_in_the_project_folder_name(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "ü ñ p")
    assert load_project(tmp_path / "ü ñ p").project.units["OBC"]


def test_gitignore_written_once(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "p")
    ignore = tmp_path / "p/.gitignore"
    assert "*.bak" in ignore.read_text()
    ignore.write_text("custom\n")
    save_project(mini3(), tmp_path / "p")
    assert ignore.read_text() == "custom\n"


def test_fingerprint_and_change_detection(tmp_path: Path) -> None:
    from harness_design_studio.core.errors import SaveError

    p = mini3()
    save_project(p, tmp_path / "p")
    fp = disk_fingerprint(tmp_path / "p")
    assert disk_fingerprint(tmp_path / "p") == fp
    (tmp_path / "p/logical/units/aocs.json").write_text('{"units": []}\n')  # e.g. a Git pull
    assert disk_fingerprint(tmp_path / "p") != fp
    try:
        save_project(p, tmp_path / "p", expected_fingerprint=fp)
    except SaveError as exc:
        assert "changed on disk" in str(exc)
    else:
        raise AssertionError("expected SaveError")


def test_non_canonical_detection(tmp_path: Path) -> None:
    root = tmp_path / "p"
    save_project(mini3(), root)
    f = root / "logical/units/power.json"
    f.write_text(
        json.dumps(json.loads(f.read_text(encoding="utf-8"))), encoding="utf-8"
    )  # same data, different formatting
    assert non_canonical_files(root, load_project(root).project) == ["logical/units/power.json"]


def test_integrity_errors_block_save(tmp_path: Path) -> None:
    import pytest

    from harness_design_studio.core.errors import SaveError

    p = mini3()
    p.interfaces["IF-TM-RW1"] = evolve(p.interfaces["IF-TM-RW1"], type_id="ghost")
    with pytest.raises(SaveError, match="consistency error"):
        save_project(p, tmp_path / "p")
    save_project(p, tmp_path / "p", allow_inconsistent=True)
