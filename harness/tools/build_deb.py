"""Build a .deb from dist/harness-design-studio (run tools.build_installer first).
Reproducible: fixed file times (SOURCE_DATE_EPOCH or the last commit), root ownership, xz.
Usage: python -m tools.build_deb"""

import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from harness_design_studio import __version__

ROOT = Path(__file__).resolve().parents[1]
# libc6: the bundled libpython (Python 3.12/3.13 of the 24.04 build host) needs GLIBC_2.38 and the
# build host has glibc 2.39; the supported system is Ubuntu 24.04 or newer
DEPENDS = (
    "libc6 (>= 2.39), libegl1, libgl1, libxkbcommon0, libxkbcommon-x11-0, libfontconfig1, "
    "libdbus-1-3, libxcb-cursor0, libxcb-icccm4, libxcb-image0, libxcb-keysyms1, libxcb-randr0, "
    "libxcb-render-util0, libxcb-shape0, libxcb-xinerama0"
)
COPYRIGHT = """Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: harness-design-studio

Files: *
Copyright: the repository owner (GitHub account 0h3xn4)
License: LicenseRef-Proprietary
 Not chosen yet by the owner (decision D-02, deliberately left open for 1.0.0).
 No licence is granted by this file.

Files: opt/harness-design-studio/_internal/* opt/harness-design-studio/cli/_internal/*
Copyright: the authors of the bundled libraries
License: see /usr/share/doc/harness-design-studio/LICENSES/
 Qt for Python (PySide6, shiboken6) is used under LGPL-3; the full text of every licence
 is in /usr/share/doc/harness-design-studio/LICENSES/ (the file README.txt lists them).
"""


def control(size_kb: int) -> str:
    return (
        "Package: harness-design-studio\n"
        f"Version: {__version__.replace('rc', '~rc')}\n"
        "Section: science\nPriority: optional\nArchitecture: amd64\n"
        f"Depends: {DEPENDS}\n"
        f"Installed-Size: {size_kb}\n"
        "Maintainer: Harness Design Studio maintainers <noreply@example.invalid>\n"
        "Description: Offline spacecraft electrical harness design tool\n"
        " Designs harnesses from a block diagram, checks them, writes drawings and\n"
        " lists, and keeps a change-controlled record. Never uses the network.\n"
    )


def epoch() -> int:
    if os.environ.get("SOURCE_DATE_EPOCH"):
        return int(os.environ["SOURCE_DATE_EPOCH"])
    out = subprocess.run(
        ["git", "log", "-1", "--format=%ct"], capture_output=True, text=True, check=False, cwd=ROOT
    )
    return (
        int(out.stdout.strip() or 0)
        if out.returncode == 0 and out.stdout.strip()
        else 1_700_000_000
    )


def build(app: Path, out_dir: Path) -> Path:
    stage = Path(tempfile.mkdtemp(prefix="deb-")) / f"harness-design-studio_{__version__}_amd64"
    opt = stage / "opt" / "harness-design-studio"
    shutil.copytree(app, opt, symlinks=True)
    for script in (
        "install.sh",
        "uninstall.sh",
        "README.txt",  # tells the reader to run ./install.sh
        "harness-design-studio.desktop.in",  # dpkg installs the finished entry and the icon below
        "harness-design-studio.svg",
    ):  # dpkg owns these files; the scripts are for tarballs
        (opt / script).unlink(missing_ok=True)
    (stage / "usr" / "bin").mkdir(parents=True)
    (stage / "usr" / "bin" / "harness-design-studio").symlink_to(
        "/opt/harness-design-studio/harness-design-studio"
    )
    (stage / "usr" / "bin" / "harness").symlink_to("/opt/harness-design-studio/cli/harness")
    pk = ROOT / "packaging" / "ubuntu"
    apps = stage / "usr" / "share" / "applications"
    apps.mkdir(parents=True)
    (apps / "harness-design-studio.desktop").write_text(
        (pk / "harness-design-studio.desktop.in")
        .read_text()
        .replace("@EXEC@", "/usr/bin/harness-design-studio")
        .replace("@ICON@", "harness-design-studio")
    )
    icons = stage / "usr" / "share" / "icons" / "hicolor" / "scalable" / "apps"
    icons.mkdir(parents=True)
    shutil.copy(pk / "harness-design-studio.svg", icons / "harness-design-studio.svg")
    doc = stage / "usr" / "share" / "doc" / "harness-design-studio"
    doc.mkdir(parents=True)
    (doc / "copyright").write_text(COPYRIGHT)
    if (opt / "LICENSES").is_dir():
        shutil.copytree(opt / "LICENSES", doc / "LICENSES")
    size_kb = sum(f.stat().st_size for f in stage.rglob("*") if f.is_file()) // 1024
    (stage / "DEBIAN").mkdir()
    (stage / "DEBIAN" / "control").write_text(control(size_kb))
    stamp = epoch()
    for path in [stage, *stage.rglob("*")]:
        os.utime(path, (stamp, stamp), follow_symlinks=False)
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() or os.access(path, os.X_OK) else 0o644)
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"harness-design-studio_{__version__}_amd64.deb"
    subprocess.run(  # SOURCE_DATE_EPOCH also fixes the time stamps in the ar archive itself
        ["dpkg-deb", "--root-owner-group", "-Zxz", "--build", str(stage), str(target)],
        check=True,
        env={**os.environ, "SOURCE_DATE_EPOCH": str(stamp)},
    )
    shutil.rmtree(stage.parent, ignore_errors=True)
    return target


def main() -> int:
    if platform.machine().lower() not in ("x86_64", "amd64"):
        print(
            f"the .deb is built for amd64 only, this machine is {platform.machine()}",
            file=sys.stderr,
        )
        return 1
    app = ROOT / "dist" / "harness-design-studio"
    if not (app / "harness-design-studio").is_file():
        print("run `python -m tools.build_installer` first", file=sys.stderr)
        return 1
    print(build(app, ROOT / "dist"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
