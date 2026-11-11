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
        if url.endswith(".sha256"):
            return f"{'0' * 64}  {url.rsplit('/', 1)[1].removesuffix('.sha256')}\n".encode()
        return b"not the archive"

    monkeypatch.setattr(fs, "_get", fake_get)
    with pytest.raises(SystemExit, match="does not match"):
        fs.fetch_qt("6.11.2", tmp_path)


def test_a_matching_file_is_written_and_listed_with_its_sha256(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = b"archive bytes"
    sha = hashlib.sha256(data).hexdigest()

    def fake_get(url: str) -> bytes:
        if url.endswith(".sha256"):
            return f"{sha}  {url.rsplit('/', 1)[1].removesuffix('.sha256')}\n".encode()
        return data

    monkeypatch.setattr(fs, "_get", fake_get)
    files = fs.fetch_qt("6.11.2", tmp_path)
    assert len(files) == 4 and all(f.read_bytes() == data for f in files)
    listing = fs.manifest(files)
    assert hashlib.sha256(data).hexdigest() in listing and listing.startswith("name\tbytes\tsha256")


def test_only_https_is_used() -> None:
    with pytest.raises(SystemExit, match="https"):
        fs._get("http://example.org/x")


def test_each_qt_file_is_checked_against_its_own_published_sha256() -> None:
    """1.17.1rc1: Qt for Python publishes no md5sums.txt beside its source (the release run got a
    404), but download.qt.io serves `<file>.sha256` for every file."""
    for name, url, sums_url in fs.qt_downloads("6.11.2"):
        assert sums_url == f"{url}.sha256" and url.endswith(f"/{name}")


def test_a_sum_for_another_file_is_not_taken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = b"archive bytes"

    def fake_get(url: str) -> bytes:
        if url.endswith(".sha256"):
            return f"{hashlib.sha256(data).hexdigest()}  some-other-file.tar.xz\n".encode()
        return data

    monkeypatch.setattr(fs, "_get", fake_get)
    with pytest.raises(SystemExit, match="does not match"):
        fs.fetch_qt("6.11.2", tmp_path)


DSC = """Format: 3.0 (quilt)
Source: pcre2
Version: 10.42-4ubuntu2.1
Checksums-Sha1:
 aaaa 3 pcre2_10.42.orig.tar.bz2
Checksums-Sha256:
 {orig} 4 pcre2_10.42.orig.tar.bz2
 {deb} 3 pcre2_10.42-4ubuntu2.1.debian.tar.xz
Files:
 bbbb 4 pcre2_10.42.orig.tar.bz2
"""


class _Done:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def test_a_binary_package_is_mapped_to_its_source_package_and_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(args: list[str], **_kw: object) -> _Done:
        assert args[:2] == ["dpkg-query", "-W"] and args[-1] == "libpcre2-8-0"
        return _Done(0, "10.42-4ubuntu2.1\tpcre2\t10.42-4ubuntu2.1")

    monkeypatch.setattr("tools.fetch_sources.subprocess.run", fake_run)
    assert fs.source_of("libpcre2-8-0", "10.42-4ubuntu2.1") == ("pcre2", "10.42-4ubuntu2.1")
    with pytest.raises(SystemExit, match="is installed, but the package carries"):
        fs.source_of("libpcre2-8-0", "10.42-4ubuntu2")


def test_the_files_of_a_dsc_are_read_from_its_sha256_section() -> None:
    files = fs.dsc_files(DSC.format(orig="A" * 64, deb="b" * 64))
    assert files == [
        ("pcre2_10.42.orig.tar.bz2", "a" * 64),
        ("pcre2_10.42-4ubuntu2.1.debian.tar.xz", "b" * 64),
    ]
    with pytest.raises(SystemExit, match="Checksums-Sha256"):
        fs.dsc_files("Format: 3.0 (quilt)\n")


def test_a_version_gone_from_the_index_is_fetched_from_launchpad_and_checked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """1.17.1rc2: `apt-get source libpcre2-8-0=10.42-4ubuntu2.1` failed, because the archive
    index lists only the newest version of each pocket; Launchpad keeps every published one."""
    orig, deb = b"orig", b"deb"
    dsc = DSC.format(orig=hashlib.sha256(orig).hexdigest(), deb=hashlib.sha256(deb).hexdigest())
    asked: list[str] = []

    def fake_run(args: list[str], **_kw: object) -> _Done:
        if args[0] == "dpkg-query":
            return _Done(0, "10.42-4ubuntu2.1\tpcre2\t10.42-4ubuntu2.1")
        return _Done(100, stderr="E: Can not find version")

    def fake_get(url: str) -> bytes:
        asked.append(url)
        name = url.rsplit("/", 1)[1]
        return {"pcre2_10.42-4ubuntu2.1.dsc": dsc.encode(), "pcre2_10.42.orig.tar.bz2": orig}.get(
            name, deb
        )

    monkeypatch.setattr("tools.fetch_sources.subprocess.run", fake_run)
    monkeypatch.setattr(fs, "_get", fake_get)
    files = fs.fetch_debian(
        [("libpcre2-8-0", "10.42-4ubuntu2.1"), ("libpcre2-16-0", "10.42-4ubuntu2.1")], tmp_path
    )
    assert [f.name for f in files] == sorted(
        [
            "pcre2_10.42-4ubuntu2.1.dsc",
            "pcre2_10.42.orig.tar.bz2",
            "pcre2_10.42-4ubuntu2.1.debian.tar.xz",
        ]
    )
    assert all(u.startswith(f"{fs.LAUNCHPAD_FILES}/pcre2/10.42-4ubuntu2.1/") for u in asked)
    assert len(asked) == 3  # two binaries of one source package: fetched once


def test_a_launchpad_file_that_does_not_match_its_dsc_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dsc = DSC.format(orig="0" * 64, deb="0" * 64)

    def fake_get(url: str) -> bytes:
        return dsc.encode() if url.endswith(".dsc") else b"not the archive"

    monkeypatch.setattr(fs, "_get", fake_get)
    with pytest.raises(SystemExit, match="does not match the SHA-256 sum"):
        fs.fetch_launchpad("pcre2", "10.42-4ubuntu2.1", tmp_path)


def test_the_file_names_of_a_version_with_an_epoch_carry_no_epoch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []
    dsc = (
        "Checksums-Sha256:\n " + hashlib.sha256(b"x").hexdigest() + " 1 zlib_1.3.dfsg.orig.tar.gz\n"
    )

    def fake_get(url: str) -> bytes:
        asked.append(url)
        return dsc.encode() if url.endswith(".dsc") else b"x"

    monkeypatch.setattr(fs, "_get", fake_get)
    fs.fetch_launchpad("zlib", "1:1.3.dfsg-3.1ubuntu2", tmp_path)
    assert (
        asked[0] == f"{fs.LAUNCHPAD_FILES}/zlib/1:1.3.dfsg-3.1ubuntu2/zlib_1.3.dfsg-3.1ubuntu2.dsc"
    )
