# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""What the real-platform lane runs on: a printed report of the Qt platform, the screen, the
desktop session and the fonts (`python -m tests.real_platform_report`).

The lane (`.github/workflows/harness-real-platform.yml`) prints this before the tests so
that a failure on a runner can be read against what the runner gave Qt: which platform plug-in,
what screen size and scaling, whether a desktop session is there, and which font stands in for the
bundled Inter and JetBrains Mono for the characters the program's texts use. It prints only; it
fails nothing, writes no file, and a window it opens is closed again.

`python -m tests.real_platform_report --screen 1920x1080` first asks Windows for the largest
display mode up to that size (the hosted Windows runner starts at 1024 x 768, which is smaller than
the windows the layout sweep asks for; Windows then makes them smaller). It does nothing on other
systems.
"""

import ctypes
import hashlib
import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase, QFontInfo, QFontMetrics
from PySide6.QtWidgets import QApplication

PANGRAM = "The quick brown fox jumps over the lazy dog 0123456789 W-1234 J01:A1 Ω µ ° ±"


def windows_modes() -> list[tuple[int, int]]:
    """The display modes (width, height) the Windows display driver lists, smallest first."""
    if sys.platform != "win32":
        return []
    found: set[tuple[int, int]] = set()
    mode = _devmode()
    index = 0
    while ctypes.windll.user32.EnumDisplaySettingsW(None, index, ctypes.byref(mode)):
        if mode.dmBitsPerPel >= 24:
            found.add((mode.dmPelsWidth, mode.dmPelsHeight))
        index += 1
    return sorted(found)


def _devmode():  # type: ignore[no-untyped-def]
    """A DEVMODEW (the Windows structure that describes a display mode), ready to be filled."""
    from ctypes import wintypes

    class DEVMODEW(ctypes.Structure):
        _fields_ = [  # noqa: RUF012
            ("dmDeviceName", ctypes.c_wchar * 32),
            ("dmSpecVersion", wintypes.WORD),
            ("dmDriverVersion", wintypes.WORD),
            ("dmSize", wintypes.WORD),
            ("dmDriverExtra", wintypes.WORD),
            ("dmFields", wintypes.DWORD),
            ("dmPositionX", wintypes.LONG),
            ("dmPositionY", wintypes.LONG),
            ("dmDisplayOrientation", wintypes.DWORD),
            ("dmDisplayFixedOutput", wintypes.DWORD),
            ("dmColor", ctypes.c_short),
            ("dmDuplex", ctypes.c_short),
            ("dmYResolution", ctypes.c_short),
            ("dmTTOption", ctypes.c_short),
            ("dmCollate", ctypes.c_short),
            ("dmFormName", ctypes.c_wchar * 32),
            ("dmLogPixels", wintypes.WORD),
            ("dmBitsPerPel", wintypes.DWORD),
            ("dmPelsWidth", wintypes.DWORD),
            ("dmPelsHeight", wintypes.DWORD),
            ("dmDisplayFlags", wintypes.DWORD),
            ("dmDisplayFrequency", wintypes.DWORD),
            ("dmICMMethod", wintypes.DWORD),
            ("dmICMIntent", wintypes.DWORD),
            ("dmMediaType", wintypes.DWORD),
            ("dmDitherType", wintypes.DWORD),
            ("dmReserved1", wintypes.DWORD),
            ("dmReserved2", wintypes.DWORD),
            ("dmPanningWidth", wintypes.DWORD),
            ("dmPanningHeight", wintypes.DWORD),
        ]

    mode = DEVMODEW()
    mode.dmSize = ctypes.sizeof(DEVMODEW)
    return mode


def raise_screen(width: int, height: int) -> str:
    """Ask Windows for the largest listed mode that is at most `width` x `height`; say what came
    of it. Nothing happens on other systems."""
    if sys.platform != "win32":
        return "screen: not Windows, nothing to set"
    modes = [m for m in windows_modes() if m[0] <= width and m[1] <= height]
    if not modes:
        return f"screen: no listed mode up to {width}x{height}: {windows_modes()}"
    best = max(modes, key=lambda m: m[0] * m[1])
    mode = _devmode()
    mode.dmPelsWidth, mode.dmPelsHeight = best
    mode.dmFields = 0x80000 | 0x100000  # DM_PELSWIDTH | DM_PELSHEIGHT
    result = ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(mode), 0)
    return (
        f"screen: asked for {best[0]}x{best[1]}, ChangeDisplaySettings returned {result} (0 = done)"
    )


def session_lines() -> list[str]:
    """What Windows says about the desktop the process runs in (nothing on other systems)."""
    if sys.platform != "win32":
        return []
    k32 = ctypes.windll.kernel32
    user32 = ctypes.windll.user32
    pid = k32.GetCurrentProcessId()
    own = ctypes.c_ulong(0)
    k32.ProcessIdToSessionId(pid, ctypes.byref(own))
    out = [
        f"windows session of this process: {own.value}",
        f"windows active console session: {k32.WTSGetActiveConsoleSessionId()}",
        f"GetSystemMetrics SM_CXSCREEN x SM_CYSCREEN: "
        f"{user32.GetSystemMetrics(0)} x {user32.GetSystemMetrics(1)}",
        f"SM_REMOTESESSION (1 = a remote desktop session): {user32.GetSystemMetrics(0x1000)}",
    ]
    desktop = user32.OpenInputDesktop(0, False, 0x0100)  # DESKTOP_SWITCHDESKTOP
    out.append(f"input desktop can be opened by this process: {bool(desktop)}")
    if desktop:
        user32.CloseDesktop(desktop)
    return out


def used_characters() -> list[str]:
    """The characters above ASCII in the program's own texts (`gui/strings.py`)."""
    text = (
        Path(__file__).resolve().parents[1] / "src" / "harness_design_studio" / "gui" / "strings.py"
    ).read_text(encoding="utf-8")
    return sorted({c for c in text if ord(c) > 126})


def font_lines(app: QApplication) -> list[str]:
    from harness_design_studio.gui.theme import fonts

    loaded = fonts.load_fonts()
    out = [f"bundled families loaded: {loaded}"]
    system = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont)
    out.append(f"system general font: {system.family()} {system.pointSizeF()} pt")
    out.append(
        "system fixed font: "
        + QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    )
    chars = used_characters()
    out.append(f"characters above ASCII used in gui/strings.py: {len(chars)}: {''.join(chars)}")
    widths = hashlib.sha256()
    for family in (fonts.UI_FAMILY, fonts.MONO_FAMILY):
        font = QFont(family)
        font.setPixelSize(13)
        info = QFontInfo(font)
        metrics = QFontMetrics(font)
        missing = [c for c in chars if not metrics.inFontUcs4(ord(c))]
        width = metrics.horizontalAdvance(PANGRAM)
        widths.update(f"{family}:{width}:{metrics.height()}".encode())
        out.append(
            f"{family} at 13 px: resolved to {info.family()!r} (exact match: {info.exactMatch()}), "
            f"line height {metrics.height()} px, the test line is {width} px wide, "
            f"characters it does not have: {''.join(missing) or 'none'}"
        )
    out.append(f"fingerprint of those widths: {widths.hexdigest()[:12]}")
    return out


def report() -> list[str]:
    app = QApplication.instance() or QApplication([])
    assert isinstance(app, QApplication)
    out = [
        f"python {sys.version.split()[0]} on {sys.platform}",
        f"qt platform: {app.platformName()}",
    ]
    out += [f"screen {s.name()!r}: {s.geometry().getRect()}, available {s.availableGeometry().getRect()}, "
            f"{s.logicalDotsPerInch():.1f} dpi, device pixel ratio {s.devicePixelRatio()}" for s in app.screens()]  # fmt: skip
    out += session_lines()
    if sys.platform == "win32":
        out.append(f"display modes the driver lists: {windows_modes()}")
    out += font_lines(app)
    return out


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--screen":
        wanted = sys.argv[2].split("x")
        print(raise_screen(int(wanted[0]), int(wanted[1])))
    print("\n".join(report()))
