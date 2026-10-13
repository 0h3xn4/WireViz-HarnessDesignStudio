"""Check boxes, radio buttons and the tick boxes of item views, drawn from the theme's tokens.

The platform style draws these with the window colour darkened, which leaves an unticked box
invisible on the dark theme. Here every state is a small picture painted with `QPainter` in the
token colours (a visible border, a tick or a dash or a dot inside, never colour alone), written once
to a temporary folder and referred to from the style sheet:

    css = indicator_css(theme.tokens, theme.name, theme.scale)    # appended to the style sheet
"""

import atexit
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Final

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen

SIZE: Final = 16  # edge in px at 100 %
_cache: dict[tuple[str, int], Path] = {}


def _folder(name: str, scale: float) -> Path:
    key = (name, round(scale * 100))
    folder = _cache.get(key)
    if folder is None or not folder.is_dir():
        folder = Path(tempfile.mkdtemp(prefix="harness-indicators-"))
        atexit.register(shutil.rmtree, folder, True)
        _cache[key] = folder
    return folder


Draw = Callable[[QPainter, float], None]


def _image(px: int, draw: Draw) -> QImage:
    image = QImage(px, px, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw(p, float(px))
    p.end()
    return image


def _box(p: QPainter, edge: float, border: QColor, fill: QColor) -> QRectF:
    pen = QPen(border, max(1.0, edge / 10))
    p.setPen(pen)
    p.setBrush(fill)
    rect = QRectF(edge * 0.06, edge * 0.06, edge * 0.88, edge * 0.88)
    p.drawRect(rect)
    return rect


def _stroke(colour: QColor, edge: float) -> QPen:
    pen = QPen(colour, max(1.5, edge / 8))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


def _tick(p: QPainter, edge: float, colour: QColor) -> None:
    p.setPen(_stroke(colour, edge))
    p.drawPolyline(
        [
            QPointF(edge * 0.27, edge * 0.52),
            QPointF(edge * 0.43, edge * 0.68),
            QPointF(edge * 0.74, edge * 0.32),
        ]
    )


def _dash(p: QPainter, edge: float, colour: QColor) -> None:
    p.setPen(_stroke(colour, edge))
    p.drawLine(QPointF(edge * 0.3, edge * 0.5), QPointF(edge * 0.7, edge * 0.5))


def _write(folder: Path, tokens: dict[str, str], px: int) -> dict[str, str]:
    c = {k: QColor(v) for k, v in tokens.items()}
    pictures: dict[str, Draw] = {}

    def square(fill: str, border: str, mark: str | None, glyph: str = "tick") -> Draw:
        def draw(p: QPainter, edge: float) -> None:
            _box(p, edge, c[border], c[fill])
            if mark is not None:
                (_tick if glyph == "tick" else _dash)(p, edge, c[mark])

        return draw

    def round_(border: str, dot: str | None) -> Draw:
        def draw(p: QPainter, edge: float) -> None:
            p.setPen(QPen(c[border], max(1.0, edge / 10)))
            p.setBrush(c["bg"])
            p.drawEllipse(QRectF(edge * 0.06, edge * 0.06, edge * 0.88, edge * 0.88))
            if dot is not None:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(c[dot])
                p.drawEllipse(QRectF(edge * 0.3, edge * 0.3, edge * 0.4, edge * 0.4))

        return draw

    pictures["box-off"] = square("bg", "border", None)
    pictures["box-on"] = square("primary", "primary", "on-primary")
    pictures["box-part"] = square("primary", "primary", "on-primary", "dash")
    pictures["box-off-disabled"] = square("surface", "text-muted", None)
    pictures["box-on-disabled"] = square("surface-2", "text-muted", "text-muted")
    pictures["radio-off"] = round_("border", None)
    pictures["radio-on"] = round_("primary", "primary")
    pictures["radio-off-disabled"] = round_("text-muted", None)
    pictures["radio-on-disabled"] = round_("text-muted", "text-muted")
    out: dict[str, str] = {}
    for name, draw in pictures.items():
        path = folder / f"{name}.png"
        _image(px, draw).save(str(path))
        out[name] = path.as_posix()
    return out


def indicator_css(tokens: dict[str, str], name: str, scale: float) -> str:
    """Style sheet rules for check boxes, radio buttons and the tick boxes of tree and list views."""
    px = max(12, round(SIZE * scale))
    pic = _write(_folder(name, scale), tokens, px)
    size = f"{px}px"
    box = "QCheckBox::indicator, QAbstractItemView::indicator"
    return f"""
{box} {{ width: {size}; height: {size}; }}
QRadioButton::indicator {{ width: {size}; height: {size}; }}
{box.replace(", ", ":unchecked, ")}:unchecked {{ image: url({pic["box-off"]}); }}
{box.replace(", ", ":checked, ")}:checked {{ image: url({pic["box-on"]}); }}
{box.replace(", ", ":indeterminate, ")}:indeterminate {{ image: url({pic["box-part"]}); }}
QCheckBox::indicator:unchecked:disabled, QAbstractItemView::indicator:unchecked:disabled {{ image: url({pic["box-off-disabled"]}); }}
QCheckBox::indicator:checked:disabled, QAbstractItemView::indicator:checked:disabled {{ image: url({pic["box-on-disabled"]}); }}
QRadioButton::indicator:unchecked {{ image: url({pic["radio-off"]}); }}
QRadioButton::indicator:checked {{ image: url({pic["radio-on"]}); }}
QRadioButton::indicator:unchecked:disabled {{ image: url({pic["radio-off-disabled"]}); }}
QRadioButton::indicator:checked:disabled {{ image: url({pic["radio-on-disabled"]}); }}
QCheckBox, QRadioButton {{ spacing: {max(4, round(8 * scale))}px; border: 2px solid transparent; padding: 1px; }}
QCheckBox:focus, QRadioButton:focus {{ border: 2px solid {tokens["focus"]}; }}
"""
