# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""D-213: the corresponding source of the LGPL and GPL components (tools/fetch_sources.py).

The network and `apt-get` are replaced here; the release workflow runs the real fetch.
"""

import hashlib
from pathlib import Path

import pytest

from tools import fetch_sources as fs

INVENTORY = {
    "components": [
        {"name": "Qt (Core, Gui)", "version": "6.11.2", "kind": "qt", "origin": "x"},
        {
            "name": "libglib2.0-0t64",
            "version": "2.80.0-6",
            "kind": "system",
            "origin": "dpkg -S libglib-2.0.so.0",
        },
        {
            "name": "libffi8",
            "version": "3.4.6-1",
            "kind": "system",
            "origin": "dpkg -S libffi.so.8",
        },
        {
            "name": "ICU (libicu)",
            "version": "73",
            "kind": "system",
            "origin": "libicu*.so.N beside Qt",
        },
        {"name": "openpyxl", "version": "3.1.5", "kind": "python", "origin": "LICENSES/README.txt"},
    ]
}


def test_the_qt_downloads_are_of_the_version_in_the_package_and_https() -> None:
    names = [n for n, _url, _sums in fs.qt_downloads("6.11.2")]
    assert names == [
        "qtbase-everywhere-src-6.11.2.tar.xz",
        "qtsvg-everywhere-src-6.11.2.tar.xz",
        "qtwayland-everywhere-src-6.11.2.tar.xz",
        "pyside-setup-everywhere-src-6.11.2.tar.xz",
    ]
    assert all(
        url.startswith("https://download.qt.io/") for _n, url, _s in fs.qt_downloads("6.11.2")
    )
    assert "/qt/6.11/6.11.2/submodules/" in fs.qt_downloads("6.11.2")[0][1]


def test_the_debian_packages_and_the_qt_version_come_from_the_inventory() -> None:
    assert fs.debian_packages(INVENTORY) == [
        ("libffi8", "3.4.6-1"),
        ("libglib2.0-0t64", "2.80.0-6"),
    ]
    assert fs.qt_version(INVENTORY) == "6.11.2"
    with pytest.raises(SystemExit):
        fs.qt_version({"components": []})


def test_a_qt_file_that_does_not_match_the_published_sum_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_get(url: str) -> bytes:
        if url.endswith("md5sums.txt"):
            return b"0123456789abcdef0123456789abcdef  qtbase-everywhere-src-6.11.2.tar.xz\n"
        return b"not the archive"

    monkeypatch.setattr(fs, "_get", fake_get)
    with pytest.raises(SystemExit, match="does not match"):
        fs.fetch_qt("6.11.2", tmp_path)


def test_a_matching_file_is_written_and_listed_with_its_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = b"archive bytes"
    md5 = hashlib.md5(data).hexdigest()  # noqa: S324 - the sum Qt publishes

    def fake_get(url: str) -> bytes:
        if url.endswith("md5sums.txt"):
            return "".join(f"{md5}  {n}\n" for n, _u, _s in fs.qt_downloads("6.11.2")).encode()
        return data

    monkeypatch.setattr(fs, "_get", fake_get)
    files = fs.fetch_qt("6.11.2", tmp_path)
    assert len(files) == 4 and all(f.read_bytes() == data for f in files)
    listing = fs.manifest(files)
    assert hashlib.sha256(data).hexdigest() in listing and listing.startswith("name\tbytes\tsha256")


def test_only_https_is_used() -> None:
    with pytest.raises(SystemExit, match="https"):
        fs._get("http://example.org/x")
