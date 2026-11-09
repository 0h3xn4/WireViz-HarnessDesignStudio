# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-211: the inventory of the third-party components of a built package (tools/third_party.py).

The tests build a small fake package folder, so they need no PyInstaller and no Debian system; the
real packages are checked in CI (`python -m tools.third_party check`).
"""

import json
from pathlib import Path

import pytest

from tools import third_party as tp
from tools.licence_report import classify


def _fake_package(root: Path) -> Path:
    app = root / "pkg"
    (app / "_internal" / "PySide6").mkdir(parents=True)
    (app / "_internal" / "libQt6Core.so.6").write_bytes(b"x")
    (app / "_internal" / "libQt6Gui.so.6").write_bytes(b"x")
    (app / "_internal" / "libpython3.14.so.1.0").write_bytes(b"\x003.14.10\x00")
    (app / "_internal" / "fonts").mkdir()
    (app / "_internal" / "fonts" / "Inter-Regular.ttf").write_bytes(b"f")
    (app / "_internal" / "fonts" / "OFL-1.1-Inter.txt").write_text(
        "Copyright (c) 2016 The Inter Project Authors\n"
    )
    di = app / "_internal" / "demo-1.0.dist-info"
    di.mkdir()
    (di / "METADATA").write_text(
        "Metadata-Version: 2.4\nName: demo\nVersion: 1.0\nLicense-Expression: MIT\n"
    )
    (di / "licenses").mkdir()
    (di / "licenses" / "LICENSE").write_text("Copyright (c) 2026 Demo Authors\nMIT text\n")
    lic = app / "LICENSES"
    lic.mkdir()
    (lic / "README.txt").write_text(
        "Licences of the components\n====\n\nPySide6_Essentials 6.11.2: LGPL-3.0-only OR GPL-3.0-only\n"
        "openpyxl 3.1.5: MIT\n"
    )
    (lic / "LGPL-3.txt").write_text("LGPL text")
    (lic / "GPL-3.txt").write_text("GPL text")
    return app


def test_the_inventory_names_python_distributions_qt_and_the_runtime(tmp_path: Path) -> None:
    parts = {c.name: c for c in tp.inventory(_fake_package(tmp_path), "windows")}
    assert parts["demo"].licence == "MIT" and "Demo Authors" in parts["demo"].copyright
    assert parts["openpyxl"].version == "3.1.5"  # from LICENSES/README.txt of the package
    qt = next(c for n, c in parts.items() if n.startswith("Qt ("))
    assert qt.version == "6.11.2" and "Core" in qt.name and "Gui" in qt.name
    assert set(qt.texts) == {"LGPL-3.txt", "GPL-3.txt"}
    assert parts["CPython runtime"].version == "3.14.10"
    assert any(c.kind == "font" for c in parts.values())


def test_no_problem_in_a_known_package_and_one_for_an_unknown_licence(tmp_path: Path) -> None:
    app = _fake_package(tmp_path)
    assert tp.problems(tp.inventory(app, "windows")) == []
    (app / "LICENSES" / "README.txt").write_text(
        (app / "LICENSES" / "README.txt").read_text() + "mystery 1.0: Proprietary - limited use\n"
    )
    assert any("mystery" in p for p in tp.problems(tp.inventory(app, "windows")))


def test_an_unclassified_windows_dll_is_a_finding(tmp_path: Path) -> None:
    app = _fake_package(tmp_path)
    (app / "_internal" / "surprise.dll").write_bytes(b"x")
    (app / "_internal" / "vcruntime140.dll").write_bytes(b"x")
    parts = {c.name: c for c in tp.inventory(app, "windows")}
    assert "unclassified DLL" in parts and parts["unclassified DLL"].licence == tp.UNKNOWN
    assert "Microsoft Visual C++ Runtime" in parts
    assert any("unclassified DLL" in p for p in tp.problems(list(parts.values())))


def test_drift_between_the_package_and_the_committed_inventory(tmp_path: Path) -> None:
    app = _fake_package(tmp_path)
    committed = json.loads(tp.to_json(tp.inventory(app, "windows"), "1.0", "windows"))
    assert tp.drift(tp.inventory(app, "windows"), committed) == []
    (app / "_internal" / "libQt6Network.so.6").write_bytes(b"x")  # a new library
    found = tp.drift(tp.inventory(app, "windows"), committed)
    assert any("libQt6Network" in line and "not in the inventory" in line for line in found)


def test_the_notices_hold_the_licence_texts_and_the_source_offer(tmp_path: Path) -> None:
    parts = tp.inventory(_fake_package(tmp_path), "windows")
    text = tp.to_notices(parts, "1.0", "windows")
    assert "GNU General Public Licence, version 3 only" in text
    assert "SOURCE CODE" in text and "three years" in text and "replace" in text
    assert "LGPL text" in text and "MIT text" in text and "Demo Authors" in text


def test_the_sbom_is_cyclonedx_and_lists_every_component(tmp_path: Path) -> None:
    parts = tp.inventory(_fake_package(tmp_path), "windows")
    sbom = json.loads(tp.to_cyclonedx(parts, "1.0", "windows"))
    assert sbom["bomFormat"] == "CycloneDX" and len(sbom["components"]) == len(parts)
    assert sbom["metadata"]["component"]["licenses"][0]["license"]["id"] == "GPL-3.0-only"


@pytest.mark.parametrize("package", sorted(tp.SYSTEM_LICENCES))
def test_every_reviewed_system_licence_is_on_the_allow_list(package: str) -> None:
    assert classify(tp.SYSTEM_LICENCES[package]) == "allowed", package
