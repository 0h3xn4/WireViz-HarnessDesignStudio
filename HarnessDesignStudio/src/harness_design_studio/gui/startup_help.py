"""Why the editor did not start on Linux, said in one sentence a person can act on.

The packages carry their own Python, Qt and most of what Qt needs. What they cannot carry is the
graphics and window-system basics of the machine (OpenGL, EGL and the X11 client library): those
belong to the graphics driver and the desktop. A normal Ubuntu desktop has them; a minimal image
may not. Without this module the editor then ends with a Python traceback, or with nothing at all
when it was started from the menu.

    missing = missing_libraries(ctypes.CDLL)      # [] when everything is there (always [] off Linux)
    if missing:
        print(message(missing))                   # names the files and the `sudo apt install` line

This module does not import Qt, so it still works when Qt cannot be loaded, and it starts no
program. The entry point of the package (`packaging/gui_entry.py`) shows the message and
`install.sh` prints it; `--check-system` runs this check on its own.
"""

import re
import sys
from collections.abc import Callable, Mapping

# (the file the loader looks for, the Ubuntu and Debian package that has it)
REQUIRED: tuple[tuple[str, str], ...] = (
    ("libGL.so.1", "libgl1"),
    ("libEGL.so.1", "libegl1"),
    ("libxcb.so.1", "libxcb1"),
)
# Libraries that the message knows by name when the loader reports one that is not in REQUIRED
# (the text of an ImportError, or a library that a newer Qt needs).
KNOWN: dict[str, str] = {
    **dict(REQUIRED),
    "libGLX.so.0": "libglx0",
    "libGLdispatch.so.0": "libglvnd0",
    "libX11.so.6": "libx11-6",
    "libX11-xcb.so.1": "libx11-xcb1",
    "libXau.so.6": "libxau6",
    "libXdmcp.so.6": "libxdmcp6",
    "libxkbcommon.so.0": "libxkbcommon0",
    "libxkbcommon-x11.so.0": "libxkbcommon-x11-0",
    "libxcb-cursor.so.0": "libxcb-cursor0",
    "libfontconfig.so.1": "libfontconfig1",
    "libdbus-1.so.3": "libdbus-1-3",
}
EXIT_CODE = 3  # what `--check-system` and a refused start return

_NOT_FOUND = re.compile(r"(lib[\w.+-]+\.so(?:\.\d+)*): cannot open shared object file")
Loader = Callable[[str], object]


def missing_libraries(load: Loader, platform: str = sys.platform) -> list[tuple[str, str]]:
    """(file, package) of each required system library that `load` cannot open. `load` is
    `ctypes.CDLL` in the program (the entry point passes it: no source file may import `ctypes`,
    tests/test_security.py) and a stand-in in tests. Only Linux needs this: the Windows
    packages bring everything but the system itself."""
    if not platform.startswith("linux"):
        return []
    out: list[tuple[str, str]] = []
    for soname, package in REQUIRED:
        try:
            load(soname)
        except OSError:
            out.append((soname, package))
    return out


def no_display(env: Mapping[str, str], platform: str = sys.platform) -> bool:
    """True on Linux when there is no graphical session to open a window in (a text-only login, an
    SSH session without X forwarding), unless Qt was told to draw offscreen."""
    if not platform.startswith("linux") or env.get("QT_QPA_PLATFORM"):
        return False
    return not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY"))


NO_DISPLAY_MESSAGE = (
    "Harness Design Studio has no graphical session to open its window in (no DISPLAY and no "
    "WAYLAND_DISPLAY). Start it from the desktop, or use the command line tool, which needs "
    "no window: harness-design-studio --help"
)


def from_error(text: str) -> list[tuple[str, str]]:
    """The libraries that an ImportError or a loader message names as missing, as (file, package);
    the package is "" for a file this module does not know."""
    found: list[tuple[str, str]] = []
    for soname in _NOT_FOUND.findall(text):
        item = (soname, KNOWN.get(soname, ""))
        if item not in found:
            found.append(item)
    return found


def message(missing: list[tuple[str, str]]) -> str:
    """What to tell a person: what is missing and the command that fixes it."""
    files = ", ".join(f for f, _p in missing)
    packages = sorted({p for _f, p in missing if p})
    text = (
        "Harness Design Studio cannot start because this computer lacks system libraries "
        f"for the graphics and the window system: {files}."
    )
    if packages:
        text += (
            f"\nInstall them with:  sudo apt install {' '.join(packages)}"
            "\n(Ubuntu and Debian; on another Linux install the packages that provide these files.)"
        )
    text += (
        "\nThe program itself needs nothing else: Python and Qt are inside it. "
        "A normal desktop installation already has these libraries."
    )
    return text
