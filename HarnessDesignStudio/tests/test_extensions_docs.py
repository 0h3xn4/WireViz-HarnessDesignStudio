# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""S8: the documents of the extensions say what the code does (the lists in them come from the code)."""

import re
from pathlib import Path

from harness_design_studio.cli.main import build_parser
from harness_design_studio.core.extensions import expr, fields, plugins, registry, schema, trust

ROOT = Path(__file__).resolve().parents[1]
DEV = (ROOT / "docs" / "developer" / "extensions.md").read_text(encoding="utf-8")
MANUAL = (ROOT / "docs" / "user-manual" / "extend-the-tool.md").read_text(encoding="utf-8")


def test_the_developer_page_lists_every_field_and_function() -> None:
    for fid, _unit, _kind, doc in fields.catalogue_rows():
        assert f"| `{fid}` |" in DEV and doc in DEV, fid
    for name in (*expr.FUNCTIONS, *expr.SPECIAL):
        assert f"| `{name}` |" in DEV, name
    for kind in registry.KINDS:
        assert f"| `{kind}` |" in DEV, kind


def test_the_developer_page_lists_the_keys_of_the_file_format() -> None:
    for spec in (schema.RULE, schema.TABLE, schema.LOOKUP, schema.PARAMETER):
        for key, _s in spec.props:
            assert f'"{key}"' in DEV, key
    for key, _s in schema.FILE.props:
        assert f"`{key}`" in DEV, key


def test_the_pages_state_the_risk_and_the_absence_of_a_sandbox() -> None:
    for text in (DEV, MANUAL, (ROOT / "docs" / "SECURITY.md").read_text(encoding="utf-8")):
        flat = " ".join(text.split())
        assert "no sandbox" in flat.lower()
        assert "rights" in flat
    assert "cannot say that its code is trusted" in " ".join(
        MANUAL.split()
    ) or "cannot trust itself" in " ".join(MANUAL.split())


def test_the_pages_name_the_real_commands_the_real_store_and_the_real_group() -> None:
    commands = set(next(a for a in build_parser()._actions if a.dest == "command").choices or ())
    assert {"extensions", "trust", "import-plugin"} <= commands
    for cmd in (
        "harness-design-studio extensions",
        "harness-design-studio trust",
        "harness-design-studio import-plugin",
    ):
        assert cmd in MANUAL, cmd
    assert plugins.ENTRY_POINT_GROUP in DEV and plugins.ENTRY_POINT_GROUP in MANUAL
    assert trust.FILE_NAME in MANUAL and trust.FILE_NAME in DEV
    assert trust.ENV_DIR in DEV
    assert plugins.PLUGIN_DIR in MANUAL


def test_the_example_readme_names_the_real_files_and_the_rule_count() -> None:
    readme = (ROOT / "docs" / "examples" / "extensions" / "README.md").read_text(encoding="utf-8")
    assert "Rules run: 41" in readme  # 39 + two data rules + one plug-in rule
    assert re.search(r"`x-min-gauge-power\.W001-001`", readme)


def test_the_indexes_link_the_new_pages() -> None:
    assert "extend-the-tool.md" in (ROOT / "docs" / "user-manual" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "extensions.md" in (ROOT / "docs" / "developer" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "extensions/README.md" in (ROOT / "docs" / "examples" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "extend-the-tool.md" in (ROOT / "docs" / "RULES.md").read_text(encoding="utf-8")
    assert "extend-the-tool.md" in (ROOT / "docs" / "models" / "README.md").read_text(
        encoding="utf-8"
    )
    assert "Unreleased" in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")[:300]
