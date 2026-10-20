"""The licences of what the program draws with: fonts and icons, as the About page shows them.

    entries()          the components with their licence and what they are used for
    text_of(key)       the licence text of one (fonts from the bundled OFL files, icons from here)

No widgets here. The Lucide and Feather notices are kept in this one place; `tools/collect_licences.py`
writes the same text to the LICENSES folder of a package.
"""

from dataclasses import dataclass
from pathlib import Path

from harness_design_studio.gui import strings
from harness_design_studio.gui.theme.tokens import FONT_MONO, FONT_UI
from harness_design_studio.resources import fonts_path

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


@dataclass(frozen=True)
class Component:
    key: str
    name: str
    licence: str
    use: str
    file: str | None = None  # the licence file inside the bundled fonts folder, when there is one


COMPONENTS = (
    Component("inter", FONT_UI, "SIL Open Font License 1.1", "Interface text", "OFL-1.1-Inter.txt"),
    Component(
        "jetbrains",
        FONT_MONO,
        "SIL Open Font License 1.1",
        "IDs, pin and part numbers, hashes, paths",
        "OFL-1.1-JetBrains-Mono.txt",
    ),
    Component("lucide", "Lucide and Feather icons", "ISC and MIT", "Icons"),
    Component(
        "qt",
        "Qt for Python (PySide6)",
        "GNU LGPL 3.0",
        "The program's windows and widgets (used unchanged, as a library)",
    ),
)


def entries() -> tuple[Component, ...]:
    return COMPONENTS


def text_of(key: str) -> str:
    """The licence text of component `key`; for Qt a pointer to where the texts ship."""
    c = next((c for c in COMPONENTS if c.key == key), None)
    if c is None:
        return ""
    if key == "lucide":
        return LUCIDE_LICENCES
    if key == "qt":
        return strings.LICENCE_QT
    folder = fonts_path()
    path = folder / c.file if folder and c.file else None
    if isinstance(path, Path) and path.is_file():
        return path.read_text(encoding="utf-8")
    return strings.LICENCE_MISSING.format(c.name)
