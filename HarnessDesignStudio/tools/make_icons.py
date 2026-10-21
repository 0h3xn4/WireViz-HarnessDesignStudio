"""Draw the application icon as files for the Windows package (D-149).

The icon is the logo that `gui/appicon.py` paints in code (the packaged program has no Qt SVG
module); the same drawing is rendered offscreen here, so the icon on disk, the window icon and
`packaging/ubuntu/harness-design-studio.svg` show the same picture.
  .ico   PNG images of 16 to 256 pixels in one file (Windows Vista and later read PNG entries)
Usage: python -m tools.make_icons ico FILE | png FILE [SIZE]
"""

import os
import struct
import sys
from pathlib import Path

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _png(size: int) -> bytes:
    """The logo as PNG bytes, `size` pixels square."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtWidgets import QApplication

    from harness_design_studio.gui.appicon import _pixmap

    app = QApplication.instance() or QApplication(sys.argv[:1])
    assert app is not None
    canvas = _pixmap(size)
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


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("ico", "png"):
        print(__doc__, file=sys.stderr)
        return 2
    target = Path(argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    if argv[0] == "ico":
        write_ico(target)
    else:
        write_png(target, int(argv[2]) if len(argv) > 2 else 256)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
