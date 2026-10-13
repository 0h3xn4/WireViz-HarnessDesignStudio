"""REQ-LIC-01: licence allow-list logic (the report itself is built by tools/licence_report.py)."""

import pytest

from tools.licence_report import classify


@pytest.mark.parametrize(
    "lic", ["MIT License", "BSD License", "Apache Software License", "ISC License (ISCL)",
            "GNU Lesser General Public License v3 (LGPLv3)", "LGPL-3.0-only", "MIT AND Python-2.0",
            "GNU Lesser General Public License v2 or later (LGPLv2+)"],
)  # fmt: skip
def test_allowed(lic: str) -> None:
    assert classify(lic) == "allowed"


@pytest.mark.parametrize(
    "lic",
    [
        "GNU General Public License v3 (GPLv3)",
        "GPL-3.0-only",
        "AGPL-3.0",
        "UNKNOWN",
        "",
        "GPL-3.0-only with LGPL exception",
        "GNU General Public License v3 plus LGPL-3.0 linking",
    ],
)
def test_rejected(lic: str) -> None:
    assert classify(lic) == "rejected"


@pytest.mark.parametrize(
    "lic", ["Miscellaneous", "Proprietary - limited use", "Mozilla Public License 2.0 (MPL 2.0)"]
)
def test_substrings_do_not_pass_as_allowed_licences(lic: str) -> None:
    assert classify(lic) == "rejected"


@pytest.mark.parametrize("lic", ["CC0 1.0 Universal", "Public Domain", "HPND"])
def test_other_permissive_licences_are_allowed(lic: str) -> None:
    assert classify(lic) == "allowed"
