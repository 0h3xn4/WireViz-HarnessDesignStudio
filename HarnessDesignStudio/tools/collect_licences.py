"""Collect the licence texts of the shipped runtime packages into a LICENSES folder.

Qt for Python (PySide6, shiboken6) is LGPL-3.0: its licence text, and the GPL-3 text it refers to,
ship with the package. The texts of the other packages come from their own metadata. The build
fails when a runtime package has no licence file or when the LGPL text cannot be found.

Usage: python -m tools.collect_licences DEST
"""

import re
import shutil
import sys
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement

COMMON = Path("/usr/share/common-licenses")  # Debian and Ubuntu base-files
LICENCE_FILE = re.compile(r"(^|/)(licen[sc]e|copying|notice|authors)[^/]*$", re.IGNORECASE)


LUCIDE_LICENCES = """Lucide (https://lucide.dev), ISC licence

Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT).
All other copyright (c) for Lucide are held by Lucide Contributors 2022.

Permission to use, copy, modify, and/or distribute this software for any purpose with or without
fee is hereby granted, provided that the above copyright notice and this permission notice appear
in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH REGARD TO THIS
SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT,
NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
OF THIS SOFTWARE.

Feather (https://feathericons.com), MIT licence, for the icons derived from it

Copyright (c) 2013-present Cole Bemis

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions: the above copyright notice and this
permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def runtime_distributions(root: str = "harness-design-studio") -> dict[str, metadata.Distribution]:
    """The installed distributions the app needs at run time: its dependencies (and the `gui` extra),
    and theirs, never the `dev` extra."""
    found: dict[str, metadata.Distribution] = {}
    todo = [(root, {"gui"})]
    while todo:
        name, extras = todo.pop()
        key = _norm(name)
        if key in found:
            continue
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            continue
        found[key] = dist
        for line in dist.requires or []:
            req = Requirement(line)
            if req.marker is not None and not any(
                req.marker.evaluate({"extra": e}) for e in (extras | {""})
            ):
                continue
            todo.append((req.name, set()))
    found.pop(_norm(root), None)
    return found


def collect(dest: Path) -> list[str]:
    dest.mkdir(parents=True, exist_ok=True)
    rows, problems, lgpl = [], [], False
    for key, dist in sorted(runtime_distributions().items()):
        meta = dist.metadata
        licence = (
            meta.get("License-Expression")
            or meta.get("License")
            or ", ".join(
                c.split("::")[-1].strip()
                for c in meta.get_all("Classifier", [])
                if "License ::" in c
            )
        )
        lgpl = lgpl or "lgpl" in licence.lower() or "lesser general" in licence.lower()
        rows.append(f"{meta['Name']} {meta['Version']}: {licence or 'see its files'}")
        files = [f for f in (dist.files or []) if LICENCE_FILE.search(f.as_posix())]
        if not files and "lgpl" not in licence.lower():
            problems.append(f"{meta['Name']} ships no licence file")
        for f in files:
            target = dest / key / Path(f.as_posix()).name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(str(dist.locate_file(f))), target)
    plex = Path(__file__).resolve().parents[1] / "src/harness_design_studio/resources/fonts"
    ofl = plex / "OFL-1.1-IBM-Plex.txt"
    if ofl.is_file():  # the bundled fonts are not Python packages: record them here
        rows.append("IBM Plex Sans 1.1.0 and IBM Plex Mono 2.5.0 (fonts): OFL-1.1")
        (dest / "ibm-plex").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ofl, dest / "ibm-plex" / ofl.name)
    else:
        problems.append("the licence text of the bundled IBM Plex fonts is missing")
    rows.append(
        "Lucide icon outlines in gui/icons.py (lucide-static 1.56.0): ISC; some derive from Feather: MIT"
    )
    (dest / "lucide").mkdir(parents=True, exist_ok=True)
    (dest / "lucide" / "LICENSE.txt").write_text(LUCIDE_LICENCES, encoding="utf-8")
    if lgpl:
        for name in ("LGPL-3", "GPL-3"):
            src = COMMON / name
            if not src.is_file():
                problems.append(f"{src} not found: build on Ubuntu or Debian")
                continue
            shutil.copyfile(src, dest / f"{name}.txt")
    (dest / "README.txt").write_text(
        "Licences of the components shipped with Harness Design Studio\n"
        "====================================================\n\n"
        + "\n".join(rows)
        + "\n\nQt for Python (PySide6, shiboken6) is used under the GNU Lesser General Public "
        "License version 3 (LGPL-3.txt, which refers to GPL-3.txt). It is a separate library in "
        "this package: you may replace it with another build of the same version. Its source is "
        "available from the Qt Project (https://code.qt.io, Qt for Python).\n",
        encoding="utf-8",
    )
    if problems:
        raise SystemExit("Licence texts are incomplete:\n- " + "\n- ".join(problems))
    return rows


if __name__ == "__main__":
    for row in collect(Path(sys.argv[1])):
        print(row)
