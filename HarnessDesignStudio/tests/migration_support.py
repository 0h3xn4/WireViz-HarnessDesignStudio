# mypy: disable-error-code="no-untyped-def,no-untyped-call,no-any-return,arg-type,attr-defined,index"
"""What the tests of the migration safety net (M1, plan 2.3) share: a fake format 2 that exists in
the test and nowhere else, and the projects it is run over.

The fake step is registered by the `fake_v2` fixture: it patches the format number of this tool to
2 and adds a step 1 to 2 to `MIGRATIONS`, and takes both away again. The default step adds nothing
(it only writes the new number); `lossy_step` drops a device and `changing_step` renames the project,
so that the safety net's refusals have something to refuse. Nothing here is shipped.

`SCENARIOS` is every project the step is run over: the fixtures and examples of the repository and
projects built here to hold what a real one holds (released harnesses with baselines and a change
log, a journal and overrides, connections and a harness made from one, as-built records). `python -m
tests.migration_support --write-goldens` writes the hashes of all of them (`GOLDEN`); a test checks
them against the hashes this tool computes: the hash of a format-1 project must never change.
"""

import copy
import json
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from harness_design_studio.core.commands import History, apply_ops
from harness_design_studio.core.io import loader, migrate, saver
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.resources import examples_path
from tests.helpers import FIXTURES, copy_project

GOLDEN = FIXTURES / "migration" / "hashes.json"
FAKE_VERSION = 2


# ---- the fake step ---------------------------------------------------------------------------------


def noop_step(files: dict[str, Any]) -> dict[str, Any]:
    """Format 2 that changes nothing but the number."""
    out = copy.deepcopy(files)
    out["project.json"]["schema_version"] = FAKE_VERSION
    return out


def lossy_step(files: dict[str, Any]) -> dict[str, Any]:
    """A step that loses a placement (and so would lose data without breaking the project): the
    dry run must refuse it."""
    out = noop_step(files)
    out["logical/layout.json"]["placements"].pop()
    return out


def changing_step(files: dict[str, Any]) -> dict[str, Any]:
    """A step that changes the design (the project name is in the model hash)."""
    out = noop_step(files)
    out["project.json"]["name"] = out["project.json"].get("name", "") + " (changed)"
    return out


def install_fake_format(
    monkeypatch: pytest.MonkeyPatch, step: Callable[[dict[str, Any]], dict[str, Any]] = noop_step
) -> None:
    for module in (migrate, loader, saver):
        monkeypatch.setattr(module, "SCHEMA_VERSION", FAKE_VERSION)
    steps = dict(migrate.MIGRATIONS)
    steps[1] = step
    monkeypatch.setattr(migrate, "MIGRATIONS", steps)


def install_real_format_2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make this tool write format 2 with the REAL step 1 to 2 of `core/io/migrate.py` (M4, D-201),
    not a fake one: only the format number is patched, to what the lead will set in the end."""
    for module in (migrate, loader, saver):
        monkeypatch.setattr(module, "SCHEMA_VERSION", FAKE_VERSION)


@pytest.fixture
def fake_v2(monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    """Call it to make this tool write format 2 with the fake step. Call it after the project has
    been built: a save made while the fake is on writes format 2."""
    return lambda: install_fake_format(monkeypatch)


# ---- the projects ----------------------------------------------------------------------------------


def _saved(project, dest: Path) -> Path:
    save_project(project, dest)
    return dest


def _copy(src: Path) -> Callable[[Path], Path]:
    return lambda dest: copy_project(src, dest)


def _example(name: str) -> Callable[[Path], Path]:
    def make(dest: Path) -> Path:
        root = examples_path()
        assert root is not None
        return copy_project(root / "projects" / name, dest)

    return make


def _mini3(dest: Path) -> Path:
    from harness_design_studio.core.samples import mini3

    return _saved(mini3(), dest)


def _sat15(dest: Path) -> Path:
    from harness_design_studio.core.samples import sat15

    return _saved(sat15(), dest)


def _sat15_full(dest: Path) -> Path:
    from harness_design_studio.core.samples import sat15_full

    return _saved(sat15_full(), dest)


def _released(dest: Path) -> Path:
    """sat15_full with one harness released (baseline and change log), a second one released and
    then given a new revision (two revisions in the change log), a third sent to review."""
    from harness_design_studio.core.outputs.build import write_outputs
    from harness_design_studio.core.samples import sat15_full
    from harness_design_studio.core.vcs.release import (
        plan_new_revision,
        plan_release,
        plan_submit_review,
    )

    p = sat15_full()
    ready = [
        h.id
        for h in sorted(p.harnesses.values(), key=lambda x: x.id)
        if all(w.gauge_awg and w.length_m for w in h.wires)
    ]
    first, second, third = ready[:3]
    outputs = dest.parent / f"{dest.name}-outputs"
    write_outputs(p, outputs)
    history = History(p)
    reason = "Test project: values are placeholders"
    for hid in (first, second):
        plan = plan_release(
            p, hid, by="Ada", checker="Bob", comment="First release for the CDR", when="2026-03-01",
            outputs_folder=outputs, accept_placeholders=reason, accept_unapproved_parts=reason,
        )  # fmt: skip
        assert plan.ok, [b.message for b in plan.blockers]
        history.execute(plan.label, plan.ops)
    plan = plan_new_revision(p, second, by="Ada", comment="Change after the CDR", when="2026-04-01")
    assert plan.ok, [b.message for b in plan.blockers]
    history.execute(plan.label, plan.ops)
    plan = plan_submit_review(p, third, by="Ada", when="2026-04-02")
    assert plan.ok, [b.message for b in plan.blockers]
    history.execute(plan.label, plan.ops)
    shutil.rmtree(outputs, ignore_errors=True)
    return _saved(p, dest)


def _journal_and_overrides(dest: Path) -> Path:
    """A project with a change journal whose entries include two overrides."""
    from harness_design_studio.core import journal
    from harness_design_studio.core.samples import sat15_full
    from harness_design_studio.core.wires import plan_override

    p = sat15_full()
    journal.start(p, "Test project.")
    _saved(p, dest)
    wires = [w for h in sorted(p.harnesses.values(), key=lambda x: x.id) for w in h.wires]
    apply_ops(p, plan_override(p, wires[0].id, "gauge_awg", 20, "ECR-7: heavier wire"))
    apply_ops(p, plan_override(p, wires[1].id, "colour", "pink", "ECR-8: colour"))
    save_project(p, dest)
    return dest


def _links(dest: Path) -> Path:
    """Connections between device connectors, and a harness made from one of them."""
    from harness_design_studio.core.links import plan_add_link, plan_create_harness
    from tests.helpers import pinout_project

    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    ops, link_id = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    ops, _hid = plan_create_harness(p, link_id)
    apply_ops(p, ops)
    ops, _other = plan_add_link(p, "PCDU-J02", "OBC-J02")
    apply_ops(p, ops)
    return _saved(p, dest)


def _asbuilt(dest: Path) -> Path:
    """The flatsat example with an as-built record of a wire."""
    from harness_design_studio.core import asbuilt

    copy = _example("flatsat")(dest)
    p = load_project(copy).project
    rows = asbuilt.template_rows(p, "W001")
    head = rows[0]
    for r in rows[1:]:
        if (r[0], r[2]) == ("wire", "W001-001"):
            r[head.index("Cut length (m)")] = "3.46"
    plan = asbuilt.plan_asbuilt_import(p, rows)
    assert plan.bad_count == 0
    apply_ops(p, plan.ops)
    save_project(p, copy)
    return copy


def _diagram_marks(dest: Path) -> Path:
    """A diagram mark (outside the hash)."""
    from harness_design_studio.core.model import DiagramMark
    from harness_design_studio.core.samples import mini3

    p = mini3()
    first = next(iter(p.interfaces))
    p.diagram_marks[f"interface:{first}"] = DiagramMark(id=f"interface:{first}", t=0.4)
    return _saved(p, dest)


SCENARIOS: dict[str, Callable[[Path], Path]] = {
    "mini3": _mini3,
    "sat15": _sat15,
    "sat15_full": _sat15_full,
    "fixture-mini3": _copy(FIXTURES / "projects" / "mini3"),
    "fixture-sat15": _copy(FIXTURES / "projects" / "sat15"),
    "custom_device": _copy(FIXTURES / "projects" / "custom_device"),
    "m1_project": _copy(FIXTURES / "m1_project"),
    "example-first-steps": _example("first-steps"),
    "example-minimal-satellite": _example("minimal-satellite"),
    "example-small-satellite": _example("small-satellite"),
    "example-flatsat": _example("flatsat"),
    "released": _released,
    "journal-and-overrides": _journal_and_overrides,
    "links": _links,
    "asbuilt": _asbuilt,
    "diagram-marks": _diagram_marks,
}
HEAVY = {"sat15_full", "released", "journal-and-overrides", "example-flatsat", "asbuilt"}


def build(name: str, dest: Path) -> Path:
    return SCENARIOS[name](dest)


# ---- reading a folder as bytes -------------------------------------------------------------------------


def folder_bytes(root: Path) -> dict[str, bytes]:
    """Every file of the folder (the backup folder included), by relative path."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def full_export(root: Path, *, migrate_old: bool = True) -> dict[str, bytes]:
    """Every file a full in-memory export of the project writes, byte for byte. `migrate_old=False`
    reads the folder as it is, without the steps (an old file tree as the old tool read it)."""
    from harness_design_studio.core.outputs.build import build_outputs

    return dict(build_outputs(load_project(root, migrate=migrate_old).project).files)


def hashes_of(root: Path) -> dict[str, str]:
    from harness_design_studio.core.io.layout import model_hash
    from harness_design_studio.core.vcs.hashing import content_hash

    project = load_project(root).project
    out = {"model_hash": model_hash(project), "content_hash": content_hash(project)}
    for bid, b in sorted(project.baselines.items()):
        out[f"baseline:{bid}"] = b.content_hash
    return out


def write_goldens() -> None:  # pragma: no cover - run on purpose
    import tempfile

    gold: dict[str, dict[str, str]] = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name in SCENARIOS:
            gold[name] = hashes_of(build(name, Path(tmp) / name))
    GOLDEN.parent.mkdir(parents=True, exist_ok=True)
    GOLDEN.write_text(json.dumps(gold, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{len(gold)} projects written to {GOLDEN}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--write-goldens"]:
        write_goldens()
    else:
        print(__doc__)
