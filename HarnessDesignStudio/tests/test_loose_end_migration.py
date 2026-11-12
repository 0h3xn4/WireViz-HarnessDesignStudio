# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index,union-attr"
"""REQ-MIGRATE-04: the real step from format 1 to format 2 is empty (M4a of the 2.0 programme,
D-201; in force since D-226). Format 2 is the format that may hold a loose cable end. The step writes
the number and nothing else: the origin of a harness is worked out and never stored, a loose end is
new content, so no hash, finding, baseline or written output of a format 1 project moves. A version
1.17.1 tool already wrote loose ends into format 1 files; these tests write such projects in format 1
(`as_format`) and run the migration safety net (REQ-MIGRATE-02) over a project that holds loose ends,
a harness released with a loose end, and a project with a harness made from a connection."""

import copy
import json
from pathlib import Path

import pytest

from harness_design_studio.core.generate.engine import generate_project
from harness_design_studio.core.io import layout, migrate, upgrade
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.manual_harness import loose_ends
from harness_design_studio.core.model import SCHEMA_VERSION
from harness_design_studio.core.origin import harness_origins
from harness_design_studio.core.outputs.build import write_outputs
from harness_design_studio.core.vcs.hashing import content_hash
from harness_design_studio.core.vcs.release import plan_release
from tests.helpers import copy_project
from tests.loose_support import build_loose
from tests.migration_support import as_format, build, folder_bytes, full_export


@pytest.fixture(scope="module")
def loose_root(tmp_path_factory) -> Path:
    root = build_loose(tmp_path_factory.mktemp("loose") / "p")
    p = load_project(root).project
    generate_project(p)
    save_project(p, root)
    return root


def test_the_step_writes_the_number_and_runs_for_a_format_1_project() -> None:
    assert SCHEMA_VERSION == 2 and migrate.current_version() == 2  # in force (D-226)
    assert sorted(migrate.MIGRATIONS) == [0, 1]
    files = {"project.json": {"name": "x", "schema_version": 1}, "logical/units/u.json": {"a": 1}}
    out = migrate.MIGRATIONS[1](files)
    assert out["project.json"] == {"name": "x", "schema_version": 2}
    assert out["logical/units/u.json"] == {"a": 1} and files["project.json"]["schema_version"] == 1
    assert migrate.migrate_raw(copy.deepcopy(files), 1) == out
    assert migrate.migrate_raw(copy.deepcopy(out), 2) == out  # nothing runs at format 2


def test_the_step_changes_only_the_number_of_a_project_that_holds_loose_ends(loose_root) -> None:
    raw = {
        rel: json.loads(data)
        for rel, data in layout.serialize(load_project(loose_root).project).items()
        if rel.endswith(".json")
    }
    raw["project.json"]["schema_version"] = 1  # as 1.17.1 wrote it
    out = migrate.MIGRATIONS[1](raw)
    assert {k for k in raw if raw[k] != out[k]} == {"project.json"}
    assert {**out["project.json"], "schema_version": 1} == raw["project.json"]


def test_the_net_upgrades_a_project_that_holds_loose_ends_with_only_the_number(
    loose_root, tmp_path
) -> None:
    root = as_format(copy_project(loose_root, tmp_path / "p"), 1)
    before_project = load_project(root).project
    before = (model_hash(before_project), content_hash(before_project))
    old_export = full_export(root)
    plan = upgrade.plan_upgrade(root)
    assert plan.ok and plan.hash_equal and plan.exports_equal, plan.lost
    assert plan.baselines_intact is not False
    assert sorted(plan.files) == ["project.json"]  # no harness file is rewritten
    done = upgrade.upgrade_project(root)
    assert done is not None and (root / done.backup / "project.json").is_file()
    after = load_project(root).project
    assert (model_hash(after), content_hash(after)) == before
    assert after.meta.schema_version == 2
    assert len(loose_ends(after.harnesses["W009"])) == 1 and len(loose_ends(after.harnesses["W011"])) == 2  # fmt: skip
    assert full_export(root) == old_export  # byte for byte, the stamp included
    assert upgrade.upgrade_project(root) is None  # now current


def test_the_net_keeps_the_baseline_of_a_harness_released_with_a_loose_end(
    loose_root, tmp_path
) -> None:
    root = copy_project(loose_root, tmp_path / "p")
    p = load_project(root).project
    out = tmp_path / "outputs"
    write_outputs(p, out)
    plan = plan_release(
        p, "W013", by="Ada", checker="Bob", comment="Release of W013", when="2026-11-08",
        outputs_folder=out, accept_placeholders="placeholders are fine here",
        accept_unapproved_parts="example parts, all of them",
        accept_loose_ends="the end waits for the supplier",
    )  # fmt: skip
    assert plan.ok
    from harness_design_studio.core.commands import History

    History(p).execute(plan.label, plan.ops)
    save_project(p, root)
    baselines = {k: v for k, v in folder_bytes(root).items() if k.startswith("baselines/")}
    assert baselines
    as_format(root, 1)
    plan_up = upgrade.plan_upgrade(root)
    assert plan_up.ok and plan_up.baselines_intact is True, plan_up.lost
    upgrade.upgrade_project(root)
    assert {k: v for k, v in folder_bytes(root).items() if k.startswith("baselines/")} == baselines
    q = load_project(root).project
    assert q.baselines["W013.A"].content_hash == content_hash(q)


def test_the_origin_of_a_hand_made_and_a_linked_harness_needs_no_stored_value(tmp_path) -> None:
    """The finding behind D-201: writing `origin` into the harness files changes the model hash and
    the export, and the net refuses. Worked out, it needs no file to change: the step is empty."""
    from harness_design_studio.core.commands import apply_ops
    from harness_design_studio.core.manual_harness import plan_add_connector, plan_new_harness

    root = build("links", tmp_path / "p")  # a harness made from a connection
    p = load_project(root).project
    ops, hid = plan_new_harness(p, "Hand made")
    apply_ops(p, ops)
    ops, _cid = plan_add_connector(p, hid, part_id="EX-DSUB-9-M")
    apply_ops(p, ops)
    save_project(p, root)
    origins = harness_origins(load_project(root).project)
    assert sorted(origins.values()) == ["drawn", "link"] and origins[hid] == "drawn"
    assert not any(b'"origin"' in data for data in folder_bytes(root).values())
    as_format(root, 1)
    plan = upgrade.plan_upgrade(root)
    assert plan.ok and plan.hash_equal and plan.exports_equal, plan.lost
    assert sorted(plan.files) == ["project.json"]


def test_a_tool_that_does_not_know_the_role_sets_the_whole_harness_aside(
    loose_root, tmp_path
) -> None:
    """What a 1.x tool does with a role it does not know (it is the reason format 2 exists: a 1.x
    tool opens a format 2 project read-only instead): the harness that holds it is quarantined,
    not shown in part."""
    root = copy_project(loose_root, tmp_path / "p")
    f = root / "physical" / "harnesses" / "W009.json"
    doc = json.loads(f.read_text())
    for c in doc["connectors"]:
        if c["role"] == "loose":
            c["role"] = "role-from-the-future"
    f.write_text(json.dumps(doc))
    res = load_project(root)
    assert "W009" not in res.project.harnesses
    assert any(i.code == "quarantined" for i in res.issues)
