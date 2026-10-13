"""REQ-RECOVERY-01: corrupt or hostile files never crash the loader and never lose data silently."""

import json
from pathlib import Path

import pytest

from harness_design_studio.core.errors import LoadError, SaveError
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.issues import Issue
from tests.helpers import MINI3, copy_project, edit_json


def issue_codes(issues: list[Issue]) -> set[str]:
    return {i.code for i in issues}


@pytest.fixture
def proj(tmp_path: Path) -> Path:
    return copy_project(MINI3, tmp_path / "p")


def test_not_a_folder_or_project(tmp_path: Path) -> None:
    with pytest.raises(LoadError, match="not a folder"):
        load_project(tmp_path / "missing")
    with pytest.raises(LoadError, match="no project.json"):
        load_project(tmp_path)


def test_clean_project_has_only_info(proj: Path) -> None:
    r = load_project(proj)
    assert {i.severity for i in r.issues} == {"info"}
    assert "placeholder_config" in issue_codes(r.issues)


def test_truncated_json_is_quarantined_and_rest_loads(proj: Path) -> None:
    f = proj / "logical/units/power.json"
    f.write_bytes(f.read_bytes()[:40])
    r = load_project(proj)
    assert "invalid_json" in issue_codes(r.issues)
    assert r.project.recovered
    assert "OBC" in r.project.units and "PCDU" not in r.project.units
    assert "logical/units/power.json" in r.project.quarantine_files
    assert "unknown_unit" in issue_codes(r.issues)  # dependants are reported, not hidden


def test_invalid_utf8(proj: Path) -> None:
    (proj / "logical/units/power.json").write_bytes(b'{"units": "\xff\xfe"}')
    r = load_project(proj)
    assert "invalid_json" in issue_codes(r.issues)


def test_merge_conflict_markers_named(proj: Path) -> None:
    f = proj / "logical/units/aocs.json"
    f.write_text("<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> branch\n")
    assert "merge_conflict" in issue_codes(load_project(proj).issues)


def test_duplicate_json_keys_detected(proj: Path) -> None:
    f = proj / "logical/units/aocs.json"
    f.write_text('{"units": [], "units": []}')
    r = load_project(proj)
    assert "invalid_json" in issue_codes(r.issues) and r.project.recovered


def test_nan_rejected(proj: Path) -> None:
    (proj / "logical/units/aocs.json").write_text('{"units": [NaN]}')
    assert "invalid_json" in issue_codes(load_project(proj).issues)


def test_deeply_nested_json(proj: Path) -> None:
    (proj / "logical/units/aocs.json").write_text("[" * 100000 + "]" * 100000)
    assert "invalid_json" in issue_codes(load_project(proj).issues)


def test_bad_entity_is_quarantined_with_field_path_not_value(proj: Path) -> None:
    edit_json(
        proj / "logical/units/power.json", lambda d: d["units"][0].update(id="9 bad id SECRET")
    )
    r = load_project(proj)
    q = r.project.quarantine
    assert len(q) == 1 and q[0].kind == "unit" and "id" in q[0].reason
    assert "SECRET" not in q[0].reason
    assert all("SECRET" not in i.message for i in r.issues)


def test_unknown_field_rejected(proj: Path) -> None:
    edit_json(proj / "logical/units/power.json", lambda d: d["units"][0].update(future_field=1))
    assert load_project(proj).project.recovered


def test_wrong_structure(proj: Path) -> None:
    (proj / "logical/units/power.json").write_text('{"nope": []}')
    r = load_project(proj)
    assert r.project.quarantine[0].kind == "file"


def test_duplicate_id_across_files(proj: Path) -> None:
    edit_json(proj / "logical/units/power.json", lambda d: d["units"].append(dict(d["units"][0])))
    r = load_project(proj)
    assert any("duplicate ID" in q.reason for q in r.project.quarantine)
    other = proj / "logical/units/zzz.json"
    other.write_text(
        json.dumps(
            {"units": [json.loads((proj / "logical/units/avionics.json").read_text())["units"][0]]}
        )
    )
    assert any("duplicate ID" in q.reason for q in load_project(proj).project.quarantine)


def test_duplicate_harness_and_name_mismatch(proj: Path) -> None:
    src = (proj / "physical/harnesses/W001.json").read_text()
    (proj / "physical/harnesses/copy.json").write_text(src)
    r = load_project(proj)
    assert any(q.kind == "harness" for q in r.project.quarantine)


def test_harness_file_name_mismatch_warns(proj: Path) -> None:
    (proj / "physical/harnesses/W001.json").rename(proj / "physical/harnesses/renamed.json")
    r = load_project(proj)
    assert "file_name_mismatch" in issue_codes(r.issues) and not r.project.recovered


def test_dangling_reference_after_load(proj: Path) -> None:
    (proj / "physical/connectors/aocs.json").write_text('{"connectors": []}')
    r = load_project(proj)
    assert r.has_errors and not r.project.recovered
    errors = {i.code for i in r.issues if i.severity == "error"}
    assert errors == {"bad_endpoint_connector", "unknown_mate"}


def test_missing_config_defaults_and_unknown_config_quarantined(proj: Path) -> None:
    (proj / "config/derating.json").unlink()
    (proj / "config/other.json").write_text(
        json.dumps({"name": "other", "placeholder": False, "values": {}})
    )
    r = load_project(proj)
    assert "config_defaulted" in issue_codes(r.issues)
    assert r.project.config["derating"].placeholder
    assert r.project.recovered
    (proj / "config/naming.json").write_text("{}")
    assert any(
        "naming" in i.location
        for i in load_project(proj).issues
        if i.location and i.severity == "error"
    )


def test_config_name_mismatch(proj: Path) -> None:
    edit_json(proj / "config/emc.json", lambda d: d.update(name="segmentation"))
    assert load_project(proj).project.recovered


def test_corrupt_project_json_still_opens(proj: Path) -> None:
    (proj / "project.json").write_text("not json")
    r = load_project(proj)
    assert "invalid_json" in issue_codes(r.issues) and "OBC" in r.project.units


def test_unrecognized_files_ignored(proj: Path) -> None:
    (proj / "logical/notes.json").write_text("{}")
    assert "unrecognized_file" in issue_codes(load_project(proj).issues)


def test_newer_schema_is_read_only(proj: Path) -> None:
    edit_json(proj / "project.json", lambda d: d.update(schema_version=99))
    r = load_project(proj)
    assert r.project.read_only and "newer_version" in issue_codes(r.issues)
    with pytest.raises(SaveError, match="read-only"):
        save_project(r.project, proj)


def test_recovered_project_cannot_overwrite_but_can_save_as(proj: Path, tmp_path: Path) -> None:
    f = proj / "logical/units/power.json"
    original = f.read_bytes()
    f.write_bytes(original[:30])
    r = load_project(proj)
    with pytest.raises(SaveError, match="new folder"):
        save_project(r.project, proj)
    assert f.read_bytes() == original[:30]  # original untouched
    out = tmp_path / "salvaged"
    save_project(r.project, out, allow_inconsistent=True)
    assert (out / "quarantine/files/logical/units/power.json").read_bytes() == original[:30]


def test_quarantined_items_written_on_save_as(proj: Path, tmp_path: Path) -> None:
    edit_json(proj / "logical/units/power.json", lambda d: d["units"][0].update(id="9bad"))
    r = load_project(proj)
    out = tmp_path / "salvaged"
    save_project(r.project, out, allow_inconsistent=True)
    items = json.loads((out / "quarantine.json").read_text())["items"]
    assert items[0]["raw"]["id"] == "9bad"
