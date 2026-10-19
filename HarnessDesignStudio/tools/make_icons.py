"""Draw the application icon as files for the Windows and macOS packages (D-149).

The icon is the logo that `gui/appicon.py` paints in code (the packaged program has no Qt SVG
module); the same drawing is rendered offscreen here, so the icon on disk, the window icon and
`packaging/ubuntu/harness-design-studio.svg` show the same picture.
  .ico   PNG images of 16 to 256 pixels in one file (Windows Vista and later read PNG entries)
  .icns  the iconset of Apple (16 to 1024 pixels) turned into an .icns by `iconutil` (macOS only)
Usage: python -m tools.make_icons ico FILE | icns FILE | png FILE [SIZE]
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
MAC_MARGIN = 0.8  # macOS icons keep a transparent border (about 10 % on each side)
ICONSET = (  # file name, pixels
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
)  # fmt: skip


def _png(size: int, margin: float = 1.0) -> bytes:
    """The logo as PNG bytes, `size` pixels square; margin < 1 shrinks it into the middle."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QPainter, QPixmap
    from PySide6.QtWidgets import QApplication

    from harness_design_studio.gui.appicon import _pixmap

    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert app is not None
    inner = max(1, round(size * margin))
    logo = _pixmap(inner)
    if inner == size:
        canvas = logo
    else:
        canvas = QPixmap(size, size)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawPixmap((size - inner) // 2, (size - inner) // 2, logo)
        painter.end()
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    if not canvas.save(buf, "PNG"):
        raise SystemExit(f"error: Qt could not write a {size} pixel PNG")
    buf.close()
    return bytes(data.data())


def write_png(target: Path, size: int = 256) -> Path:
    target.write_bytes(_png(size))
    return target


def ico_bytes(images: list[tuple[int, bytes]]) -> bytes:
    """An .ico file that holds (size, PNG bytes) images; 256 is stored as 0 in the directory."""
    head = struct.pack("<HHH", 0, 1, len(images))
    offset = len(head) + 16 * len(images)
    entries, payload = b"", b""
    for size, png in images:
        side = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", side, side, 0, 0, 1, 32, len(png), offset)
        payload += png
        offset += len(png)
    return head + entries + payload


def write_ico(target: Path) -> Path:
    target.write_bytes(ico_bytes([(size, _png(size)) for size in ICO_SIZES]))
    return target


def write_icns(target: Path) -> Path:
    """The .icns of the logo; needs `iconutil` (macOS)."""
    if shutil.which("iconutil") is None:
        raise SystemExit("error: iconutil not found: the .icns is made on macOS")
    with tempfile.TemporaryDirectory(prefix="harness-iconset-") as tmp:
        iconset = Path(tmp) / "harness-design-studio.iconset"
        iconset.mkdir()
        for name, size in ICONSET:
            (iconset / name).write_bytes(_png(size, MAC_MARGIN))
        subprocess.run(["iconutil", "-c", "icns", "-o", str(target), str(iconset)], check=True)
    return target


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("ico", "icns", "png"):
        print(__doc__, file=sys.stderr)
        return 2
    target = Path(argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    if argv[0] == "ico":
        write_ico(target)
    elif argv[0] == "icns":
        write_icns(target)
    else:
        write_png(target, int(argv[2]) if len(argv) > 2 else 256)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
