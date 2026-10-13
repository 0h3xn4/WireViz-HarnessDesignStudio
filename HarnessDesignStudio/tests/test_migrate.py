"""REQ-MIGRATE-01: lossless migration from every previous format, original kept."""

from pathlib import Path

from harness_design_studio.cli.main import main
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.migrate import MIGRATIONS
from harness_design_studio.core.io.saver import migrate_project, save_project
from harness_design_studio.core.model import SCHEMA_VERSION
from tests.helpers import FIXTURES, copy_project

V0 = FIXTURES / "v0_project"


def test_every_old_version_has_a_migration_and_fixture() -> None:
    assert sorted(MIGRATIONS) == list(range(SCHEMA_VERSION))
    assert V0.is_dir()


def test_v0_loads_migrated_in_memory(tmp_path: Path) -> None:
    root = copy_project(V0, tmp_path / "p")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    r = load_project(root)
    assert r.project.migrated_from == 0 and not r.has_errors
    assert r.project.units["OBC-A"].side == "nominal"
    assert r.project.units["OBC-B"].side == "redundant"
    assert r.project.meta.tool_version == "0.0.0" and r.project.meta.name == "legacy project"
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before  # disk untouched


def test_migrate_in_place_keeps_original(tmp_path: Path) -> None:
    root = copy_project(V0, tmp_path / "p")
    original = (root / "project.json").read_bytes()
    result = migrate_project(root)
    assert result is not None
    backup = root / ".migration-backup-v0"
    assert (backup / "project.json").read_bytes() == original
    assert (backup / "logical/units/avionics.json").exists()
    again = load_project(root)
    assert (
        again.project.migrated_from is None and again.project.meta.schema_version == SCHEMA_VERSION
    )
    assert again.project.units["OBC-B"].side == "redundant"
    assert migrate_project(root) is None


def test_plain_save_of_migrated_project_also_backs_up(tmp_path: Path) -> None:
    root = copy_project(V0, tmp_path / "p")
    r = load_project(root)
    out = save_project(r.project, root)
    assert out.backup_dir == ".migration-backup-v0"


def test_cli_migrate(tmp_path: Path, capsys: object) -> None:
    root = copy_project(V0, tmp_path / "p")
    assert main(["migrate", str(root)]) == 0
    assert main(["migrate", str(root)]) == 0
