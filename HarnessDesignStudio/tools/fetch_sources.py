# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Fetch the corresponding source of the LGPL and GPL components of a release (decision D-213).

    python -m tools.fetch_sources INVENTORY.json --out DIR

The inventory is the file `tools/third_party.py inventory` wrote for the Linux package. The tool
fetches

- the Qt for Python source (`pyside-setup-everywhere-src-<version>.tar.xz`) and the Qt modules that
  the package carries (qtbase, qtsvg, qtwayland), each of the version of the Qt libraries in the
  package, from download.qt.io, and checks each against the SHA-256 sum that download.qt.io publishes
  for it (`<file>.sha256`; Qt for Python has no `md5sums.txt` beside its source);
- the Debian source package (`.dsc`, `.orig.tar.*`, `.debian.tar.*`) of every library of the
  operating system that the package carries. The binary package of the inventory is mapped to its
  source package and source version with `dpkg-query` (the libraries are installed on the machine
  that built the package). `apt-get source` fetches it when the archive index still lists that
  version (the machine needs `deb-src` lines; the release workflow adds them). The index lists only
  the newest version of each pocket, so an older update is fetched from Launchpad, which keeps every
  published version; each file is checked against the SHA-256 sums in its `.dsc`.

It writes `SOURCES.txt` into DIR: the file name, size and SHA-256 of everything it fetched. The
release workflow attaches the files to the release page, which is where the notices file says the
source is. The tool stops with an error when a file cannot be fetched or does not match.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

QT_BASE = "https://download.qt.io/official_releases"
LAUNCHPAD_FILES = "https://launchpad.net/ubuntu/+archive/primary/+sourcefiles"
QT_MODULES = ("qtbase", "qtsvg", "qtwayland")


def qt_downloads(version: str) -> list[tuple[str, str, str]]:
    """(file name, URL, URL of its published SHA-256 sum) for the Qt sources of `version`."""
    major_minor = ".".join(version.split(".")[:2])
    sub = f"{QT_BASE}/qt/{major_minor}/{version}/submodules"
    out = [
        (
            f"{m}-everywhere-src-{version}.tar.xz",
            f"{sub}/{m}-everywhere-src-{version}.tar.xz",
            f"{sub}/{m}-everywhere-src-{version}.tar.xz.sha256",
        )
        for m in QT_MODULES
    ]
    pyside = f"{QT_BASE}/QtForPython/pyside6/PySide6-{version}-src"
    name = f"pyside-setup-everywhere-src-{version}.tar.xz"
    out.append((name, f"{pyside}/{name}", f"{pyside}/{name}.sha256"))
    return out


def debian_packages(inventory: Mapping[str, Any]) -> list[tuple[str, str]]:
    """(package, version) of every Debian package behind a library of the Linux package."""
    seen: dict[str, str] = {}
    for row in inventory["components"]:
        if (
            row["kind"] == "system"
            and row["origin"].startswith("dpkg")
            and row["version"] != "unknown"
        ):
            seen[row["name"]] = row["version"]
    return sorted(seen.items())


def qt_version(inventory: Mapping[str, Any]) -> str:
    for row in inventory["components"]:
        if row["kind"] == "qt" and re.fullmatch(r"\d+\.\d+\.\d+", row["version"]):
            return str(row["version"])
    raise SystemExit("the inventory names no Qt version")


RETRY_WAITS = (10.0, 30.0, 90.0)  # seconds between the tries of one download


def _get(url: str) -> bytes:
    """The body of `url` (https only). A network error or a server error (5xx) is tried again
    after each wait of RETRY_WAITS; a client error (4xx, for example 404) is not, because it
    does not go away by waiting (the release run of 1.17.1rc2 lost the network to Launchpad for
    a moment: "Network is unreachable")."""
    if not url.startswith("https://"):
        raise SystemExit(f"only https is used: {url}")
    for wait in (*RETRY_WAITS, None):
        try:
            with urllib.request.urlopen(url, timeout=600) as response:  # noqa: S310 - https only, checked above
                return bytes(response.read())
        except urllib.error.HTTPError as err:
            if err.code < 500 or wait is None:
                raise
            reason = f"HTTP {err.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            if wait is None:
                raise
            reason = str(getattr(err, "reason", err))
        print(f"{url}: {reason}; trying again in {wait:.0f} s", file=sys.stderr)
        time.sleep(wait)
    raise AssertionError("not reached")


def fetch_qt(version: str, out: Path) -> list[Path]:
    got = []
    for name, url, sums_url in qt_downloads(version):
        data = _get(url)
        sums = _get(sums_url).decode("utf-8", "replace")
        # "<sha256>  <file name>", as download.qt.io serves it for each file
        want = next(
            (
                ln.split()[0].lower()
                for ln in sums.splitlines()
                if len(ln.split()) == 2 and ln.split()[1].lstrip("*") == name
            ),
            None,
        )
        if want is None or hashlib.sha256(data).hexdigest() != want:
            raise SystemExit(
                f"{name}: does not match the SHA-256 sum that download.qt.io publishes"
            )
        (out / name).write_bytes(data)
        got.append(out / name)
    return got


def source_of(binary: str, version: str) -> tuple[str, str]:
    """(source package, source version) of an installed binary package, from `dpkg-query`."""
    result = subprocess.run(  # noqa: S603 - our own arguments, no shell
        ["dpkg-query", "-W", "-f=${Version}\t${source:Package}\t${source:Version}", binary],
        capture_output=True,
        text=True,
        check=False,
    )
    fields = result.stdout.strip().split("\t")
    if result.returncode != 0 or len(fields) != 3:
        raise SystemExit(f"dpkg-query {binary} failed:\n{result.stderr[-600:]}")
    installed, source, source_version = fields
    if installed != version:
        raise SystemExit(
            f"{binary}: {installed} is installed, but the package carries {version}; "
            "the source must be fetched on the machine that built the package"
        )
    return source, source_version


def dsc_files(dsc: str) -> list[tuple[str, str]]:
    """(file name, SHA-256) of every file a `.dsc` lists under `Checksums-Sha256`."""
    files: list[tuple[str, str]] = []
    in_section = False
    for line in dsc.splitlines():
        if line.startswith("Checksums-Sha256:"):
            in_section = True
        elif in_section and line.startswith(" "):
            sha, _size, name = line.split()
            files.append((name, sha.lower()))
        elif in_section:
            break
    if not files:
        raise SystemExit("the .dsc lists no Checksums-Sha256")
    return files


def fetch_launchpad(source: str, version: str, out: Path) -> list[Path]:
    """The source package `source` `version` from Launchpad, every file checked against its .dsc."""
    plain = version.split(":", 1)[-1]  # file names carry no epoch
    base = f"{LAUNCHPAD_FILES}/{source}/{version}"
    dsc_name = f"{source}_{plain}.dsc"
    dsc = _get(f"{base}/{dsc_name}")
    (out / dsc_name).write_bytes(dsc)
    got = [out / dsc_name]
    for name, sha in dsc_files(dsc.decode("utf-8", "replace")):
        data = _get(f"{base}/{name}")
        if hashlib.sha256(data).hexdigest() != sha:
            raise SystemExit(f"{name}: does not match the SHA-256 sum in {dsc_name}")
        (out / name).write_bytes(data)
        got.append(out / name)
    return got


def fetch_debian(packages: list[tuple[str, str]], out: Path) -> list[Path]:
    before = {p.name for p in out.iterdir()}
    sources = sorted({source_of(name, version) for name, version in packages})
    from_launchpad: list[str] = []
    for source, version in sources:
        result = subprocess.run(  # noqa: S603 - our own arguments, no shell
            ["apt-get", "source", "--download-only", f"{source}={version}"],
            cwd=out,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            fetch_launchpad(source, version, out)
            from_launchpad.append(f"{source}={version}")
    if from_launchpad:
        print(
            f"{len(from_launchpad)} source package(s) from Launchpad (no longer in the archive "
            f"index): {', '.join(from_launchpad)}",
            file=sys.stderr,
        )
    return sorted(p for p in out.iterdir() if p.name not in before)


def manifest(files: list[Path]) -> str:
    rows = ["name\tbytes\tsha256"]
    for f in sorted(files):
        rows.append(f"{f.name}\t{f.stat().st_size}\t{hashlib.sha256(f.read_bytes()).hexdigest()}")
    return "\n".join(rows) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inventory", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--skip-debian", action="store_true", help="only the Qt sources")
    args = ap.parse_args(argv)
    inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    files = fetch_qt(qt_version(inventory), args.out)
    if not args.skip_debian:
        files += fetch_debian(debian_packages(inventory), args.out)
    (args.out / "SOURCES.txt").write_text(manifest(files), encoding="utf-8")
    print(f"{len(files)} source file(s) in {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
