# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-220 (the owner's answer B3, 2026-11-10): every file of upstream WireViz in this repository is
byte for byte as at the fork base `e4fe099f`, so "unchanged" in the README and the NOTICE is true.
The Git blob id of each file is in tests/fixtures/upstream_e4fe099f.json; a sync with upstream
(docs/developer/upstream-sync.md) updates that file in the same change."""

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
LIST = json.loads((ROOT / "tests" / "fixtures" / "upstream_e4fe099f.json").read_text("utf-8"))


def blob_id(data: bytes) -> str:
    """The id Git gives a file with these bytes (`git hash-object`)."""
    return hashlib.sha1(b"blob %d\0" % len(data) + data, usedforsecurity=False).hexdigest()


def test_the_list_holds_the_whole_upstream_tree() -> None:
    files = LIST["files"]
    assert len(files) == 186 and LIST["base"].startswith("e4fe099f")
    for name in ("setup.py", ".gitignore", "docs/README.md", ".github/workflows/main.yml"):
        assert name in files
    assert sum(1 for f in files if f.startswith("src/wireviz/") and f.endswith(".py")) == 12
    assert not [f for f in files if f.startswith("HarnessDesignStudio/")]


@pytest.mark.parametrize("name", sorted(LIST["files"]))
def test_the_upstream_file_is_unchanged(name: str) -> None:
    path = REPO / name
    if not (REPO / "src" / "wireviz").is_dir():
        pytest.skip("the repository root is not here")
    assert path.is_file(), f"{name} was removed"
    data = path.read_bytes()
    found = blob_id(data)
    if found != LIST["files"][name] and b"\0" not in data:
        found = blob_id(data.replace(b"\r\n", b"\n"))  # a Windows checkout may write CRLF
    assert found == LIST["files"][name], f"{name} differs from the fork base e4fe099f"


def test_no_manifest_is_added_next_to_the_upstream_setup() -> None:
    """MANIFEST.in was added after the fork for a changed setup.py; it went with the restore."""
    if not (REPO / "setup.py").is_file():
        pytest.skip("the repository root is not here")
    assert not (REPO / "MANIFEST.in").exists()
