"""M2a: the files of a project with links. `logical/links.json` is there only when a link is, the
hash follows the link, the command line reads such a project, and a project that uses no link or
role is written exactly as before (FILE_FORMAT.md, "Links")."""

import json
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import schemas
from harness_design_studio.core.commands import History
from harness_design_studio.core.devices import ops_set_pin
from harness_design_studio.core.io.layout import is_managed, model_hash, serialize
from harness_design_studio.core.io.loader import disk_fingerprint, load_project, non_canonical_files
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.links import plan_add_link, plan_create_harness, plan_set_pairs
from harness_design_studio.core.model import Link, Project
from harness_design_studio.core.outputs.build import build_outputs
from harness_design_studio.core.outputs.verify import verify_outputs
from harness_design_studio.core.samples import mini3
from harness_design_studio.core.vcs.hashing import content_hash
from tests.helpers import MINI3, pinout_project

LINKS = "logical/links.json"


def with_link() -> tuple[Project, str]:
    p = pinout_project()
    ops, lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    History(p).execute("Link connectors", ops)
    return p, lid


def test_the_links_file_is_absent_while_there_is_no_link_and_present_with_one() -> None:
    assert LINKS not in serialize(pinout_project())
    p, lid = with_link()
    files = serialize(p)
    assert is_managed(LINKS)
    doc = json.loads(files[LINKS])
    assert list(doc) == ["links"] and doc["links"][0]["id"] == lid
    assert doc["links"][0]["pairs"][0] == {"a_pin": "1", "b_pin": "3"}
    assert "harness_id" not in doc["links"][0] and "note" not in doc["links"][0]  # sparse


def test_a_project_that_uses_none_of_it_is_written_as_it_always_was(tmp_path: Path) -> None:
    save_project(mini3(), tmp_path / "p")
    files = serialize(
        mini3(), tool_version=json.loads((MINI3 / "project.json").read_text())["tool_version"]
    )
    for rel, data in files.items():
        assert (MINI3 / rel).read_bytes() == data, rel
    on_disk = sorted(
        p.relative_to(tmp_path / "p").as_posix() for p in (tmp_path / "p").rglob("*.json")
    )
    assert LINKS not in on_disk


def test_the_hash_follows_the_link() -> None:
    p, lid = with_link()
    no_link = pinout_project()
    h0, c0 = model_hash(p), content_hash(p)
    assert h0 != model_hash(no_link) and c0 != content_hash(no_link)
    History(p).execute("Pairs", plan_set_pairs(p, lid, [("1", "3")]))
    assert model_hash(p) != h0 and content_hash(p) != c0
    again = pinout_project()
    again.links[lid] = p.links[lid]
    assert model_hash(again) == model_hash(p)


def test_a_saved_link_is_loaded_again_and_a_removed_one_leaves_no_file(tmp_path: Path) -> None:
    p, lid = with_link()
    History(p).execute("Role", ops_set_pin(p, "OBC-J01", "5", role="spare"))
    root = tmp_path / "p"
    save_project(p, root)
    assert (root / LINKS).is_file()
    r = load_project(root)
    assert not r.has_errors and r.project.links == p.links
    assert non_canonical_files(root, r.project) == []
    fingerprint = disk_fingerprint(root)
    del r.project.links[lid]
    result = save_project(r.project, root)
    assert LINKS in result.removed and not (root / LINKS).exists()
    assert disk_fingerprint(root) != fingerprint


def test_a_damaged_links_file_is_set_aside_not_lost(tmp_path: Path) -> None:
    p, _lid = with_link()
    root = tmp_path / "p"
    save_project(p, root)
    path = root / LINKS
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["links"][0]["a_pin"] = "x"  # not a field of a link
    path.write_text(json.dumps(doc), encoding="utf-8")
    r = load_project(root)
    assert r.has_errors and r.project.links == {} and r.project.quarantine


def test_validate_and_check_accept_a_project_with_links(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p, lid = with_link()
    ops, _hid = plan_create_harness(p, lid)
    History(p).execute("Create harness", ops)
    root = tmp_path / "p"
    save_project(p, root, allow_inconsistent=True)
    capsys.readouterr()
    assert main(["validate", str(root)]) == 0
    assert "0 error(s)" in capsys.readouterr().out
    assert main(["check", str(root)]) in (
        0,
        1,
    )  # the checks run; the example data has open findings
    out = capsys.readouterr().out
    assert "Traceback" not in out
    assert main(["drc", str(root)]) in (0, 1)
    assert "Rules run: 39." in capsys.readouterr().out


def test_the_json_export_has_a_links_key_only_when_there_are_links() -> None:
    assert (
        b'"links"'
        not in build_outputs(pinout_project(), drawings=False).files["system/export.json"]
    )
    p, lid = with_link()
    files = build_outputs(p, drawings=False).files
    assert json.loads(files["system/export.json"])["links"][0]["id"] == lid
    assert [i for i in verify_outputs(p, files).issues if i.severity == "error"] == []
    tampered = dict(files)
    doc = json.loads(files["system/export.json"])
    del doc["links"]
    tampered["system/export.json"] = json.dumps(doc).encode()
    assert any(i.code == "out_json" for i in verify_outputs(p, tampered).issues)


def test_the_schema_of_the_links_file_comes_from_the_model() -> None:
    docs = schemas.schemas()
    assert "links" in docs and "links" in docs["links"]["properties"]
    kinds = {name: pattern for name, pattern, _ in schemas._kinds()}
    assert kinds["links"] == LINKS
    p, _ = with_link()
    props = docs["links"]["$defs"]["Link"]["properties"]
    assert set(json.loads(serialize(p)[LINKS])["links"][0]) <= set(props)
    assert "role" in schemas.schemas()["connectors"]["$defs"]["Pin"]["properties"]


def test_link_model_rejects_what_a_file_must_not_hold() -> None:
    with pytest.raises(ValueError):
        Link(id="L1", a_connector="A", b_connector="B", surprise=1)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        Link(id="1bad", a_connector="A", b_connector="B")
