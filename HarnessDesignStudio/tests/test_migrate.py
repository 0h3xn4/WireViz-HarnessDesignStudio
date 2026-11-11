# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""REQ-MIGRATE-01: lossless migration from every previous format, original kept."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core.errors import SaveError
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.migrate import MIGRATIONS
from harness_design_studio.core.io.saver import migrate_project, save_project
from harness_design_studio.core.model import SCHEMA_VERSION
from tests.helpers import FIXTURES, copy_project

V0 = FIXTURES / "v0_project"
V1 = FIXTURES / "v1_project"  # written by 1.17.1 (tests/test_format2.py)


def test_every_old_version_has_a_migration_and_fixture() -> None:
    # every format before the current one has its step and a fixture written in it
    assert sorted(MIGRATIONS) == list(range(SCHEMA_VERSION))
    assert V0.is_dir() and V1.is_dir() and SCHEMA_VERSION == 2


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


@pytest.mark.parametrize("old", [V0, V1])
def test_a_plain_save_does_not_upgrade_an_old_project_in_place(old: Path, tmp_path: Path) -> None:
    """No silent upgrade (D-226): only `migrate` (with its record and its check) writes an older
    project in the format of this tool into its own folder; a plain save says so and writes nothing."""
    root = copy_project(old, tmp_path / "p")
    before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
    r = load_project(root)
    with pytest.raises(SaveError, match="migrate"):
        save_project(r.project, root)
    assert {p: p.read_bytes() for p in root.rglob("*") if p.is_file()} == before
    assert not list(root.glob(".migration-backup-v*"))


def test_cli_migrate(tmp_path: Path, capsys: object) -> None:
    root = copy_project(V0, tmp_path / "p")
    assert main(["migrate", str(root)]) == 0
    assert main(["migrate", str(root)]) == 0
