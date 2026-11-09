# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""A layout audit for any widget: does everything that is shown have room, and nothing on top of
anything else?

`audit(widget)` looks at a widget that is shown (the caller has called `show()` and processed
events) and returns a list of `Finding`s, each with the rule that was broken, where, and what was
measured. An empty list means the layout holds. The rules:

- `overlap`: two siblings that are both visible cover each other (more than a sliver). A widget
  that is meant to sit on top of another (a banner over the canvas, the zoom buttons over a view)
  carries the property `overlay`.
- `outside`: a visible child reaches beyond its parent's rectangle, so part of it is cut off.
- `squeezed`: a widget is smaller than its own minimum size hint (controls given less room than
  they asked for: the typical result of a window that is shorter than its content).
- `wrap-clipped`: a label with word wrap is shorter than its text needs at its width.
- `text-cut`: a label or button is narrower than its own text (where cutting is not intended: an
  elided label carries the property `elide`).
- `window-short`: a window is shorter than its layout needs at its width (height for width).

It looks only at what Qt lays out. It cannot know that a font on another machine is wider than the
one used here (see `docs/developer/gui-layout.md`), which is why the tests run it at several
interface sizes and font sizes; and it does not see what a widget paints itself.
"""

from dataclasses import dataclass

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractScrollArea,
    QAbstractSpinBox,
    QComboBox,
    QDockWidget,
    QGraphicsView,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollBar,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QSplitterHandle,
    QStackedWidget,
    QTabBar,
    QWidget,
)

SLIVER = 2  # px of overlap or overhang that is not worth a finding (borders, focus rings)
# px a widget may be smaller than its minimum hint before it is a finding: the style gives a few
# px of padding that nobody sees when it is missing (a tool button 3 px narrower than its hint)
SQUEEZE_H = 3
SQUEEZE_W = 7
# widgets that are one control made of parts: their insides are the style's business
_COMPOSITE = (
    QAbstractSpinBox,
    QComboBox,
    QLineEdit,
    QAbstractItemView,
    QGraphicsView,
    QTabBar,
    QMenu,
    QScrollBar,
    QSizeGrip,
    QSplitterHandle,
)


@dataclass(frozen=True)
class Finding:
    rule: str
    where: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.where}: {self.detail}"


def describe(w: QWidget, top: QWidget) -> str:
    """A path from the audited widget down to `w` that a person can find in the code: the class
    and, where it has one, the object name or the text."""
    parts: list[str] = []
    node: QWidget | None = w
    while node is not None:
        label = type(node).__name__
        if node.objectName():
            label += f"#{node.objectName()}"
        elif isinstance(node, QLabel | QAbstractButton | QGroupBox) and _text(node):
            label += f"[{_text(node)[:24]!r}]"
        parts.append(label)
        if node is top:
            break
        node = node.parentWidget()
    return " > ".join(reversed(parts))


def _text(w: QWidget) -> str:
    if isinstance(w, QLabel):
        return w.text() if w.textFormat() != Qt.TextFormat.RichText else ""
    if isinstance(w, QAbstractButton):
        return w.text()
    if isinstance(w, QGroupBox):
        return w.title()
    return ""


def _visible_children(w: QWidget) -> list[QWidget]:
    return [
        c
        for c in w.children()
        if isinstance(c, QWidget) and not c.isWindow() and c.isVisible() and not c.isHidden()
    ]


def _is_overlay(w: QWidget) -> bool:
    return bool(w.property("overlay"))


def _descend(w: QWidget) -> bool:
    """Whether the children of `w` are laid out by us (and not by the style, as the parts of a
    combo box are)."""
    if isinstance(w, _COMPOSITE):
        return False
    return not isinstance(
        w, QAbstractScrollArea
    )  # its viewport and contents are walked on their own


def _walk(root: QWidget, scrolled: bool = True) -> list[QWidget]:
    """Every visible widget under `root` (and `root`); the contents of scroll areas too when
    `scrolled` (a window made as small as it goes scrolls them, so they are not looked at then)."""
    out: list[QWidget] = []
    stack = [root]
    while stack:
        w = stack.pop()
        out.append(w)
        if isinstance(w, QAbstractScrollArea) and not isinstance(w, QAbstractItemView):
            vp = w.viewport()
            if scrolled and vp is not None and vp.isVisible():
                stack.append(vp)
            continue
        if not _descend(w):
            continue
        stack.extend(_visible_children(w))
    return out


def _overlaps(parent: QWidget, top: QWidget) -> list[Finding]:
    found: list[Finding] = []
    if not _descend(parent):
        return found
    kids = [
        c
        for c in _visible_children(parent)
        if not _is_overlay(c) and c.width() > 0 and c.height() > 0
    ]
    for i, a in enumerate(kids):
        for b in kids[i + 1 :]:
            common = a.geometry().intersected(b.geometry())
            if common.width() >= SLIVER and common.height() >= SLIVER:
                found.append(
                    Finding(
                        "overlap",
                        f"{describe(a, top)} / {describe(b, top)}",
                        f"{a.geometry().getRect()} over {b.geometry().getRect()}",
                    )
                )
    return found


def _outside(parent: QWidget, top: QWidget) -> list[Finding]:
    found: list[Finding] = []
    if isinstance(parent, QStackedWidget) or not _descend(parent):
        return found
    holder = parent.parentWidget()
    if isinstance(holder, QAbstractScrollArea) and holder.viewport() is parent:
        return found  # the contents of a scroll area are meant to be larger than its viewport
    room = parent.rect()
    for c in _visible_children(parent):
        if _is_overlay(c) or c.width() <= 0 or c.height() <= 0:
            continue
        g: QRect = c.geometry()
        over = max(
            room.left() - g.left(),
            room.top() - g.top(),
            g.right() - room.right(),
            g.bottom() - room.bottom(),
        )
        if over >= SLIVER:
            found.append(
                Finding(
                    "outside",
                    describe(c, top),
                    f"{g.getRect()} reaches {over} px beyond its parent {room.getRect()}",
                )
            )
    return found


def _squeezed(w: QWidget, top: QWidget) -> list[Finding]:
    if w.isWindow() or _is_overlay(w) or isinstance(w, QAbstractScrollArea | QDockWidget):
        return []
    if isinstance(w, _COMPOSITE) and not isinstance(w, QLineEdit | QComboBox | QAbstractSpinBox):
        return []
    if isinstance(w.parentWidget(), QSplitter):
        return []  # the parts of a splitter may be collapsed by the person
    pol = w.sizePolicy()
    hint = w.minimumSizeHint()
    lay = w.layout()
    if lay is not None and lay.hasHeightForWidth() and w.width() > 0:
        # with wrapped text the height the contents need depends on the width, and the hint
        # (taken at the narrowest width) is not it
        hint = QSize(hint.width(), lay.minimumHeightForWidth(w.width()))
    # what the layout asks for: the larger of the hint and the set minimum, but never more than
    # the set maximum (the style sheet gives fields a fixed height that is below their hint)
    want_h = min(max(hint.height(), w.minimumHeight()), w.maximumHeight())
    want_w = min(max(hint.width(), w.minimumWidth()), w.maximumWidth())
    found: list[Finding] = []
    # a word-wrapped label's minimum hint is one word wide; its height is judged by `wrap-clipped`
    wrapped = isinstance(w, QLabel) and w.wordWrap()
    if (
        not wrapped
        and hint.height() > 0
        and pol.verticalPolicy() != QSizePolicy.Policy.Ignored
        and w.height() < want_h - SQUEEZE_H
    ):
        found.append(
            Finding("squeezed", describe(w, top), f"{w.height()} px high, its minimum is {want_h}")
        )
    if (
        hint.width() > 0
        and pol.horizontalPolicy() != QSizePolicy.Policy.Ignored
        and w.width() < want_w - SQUEEZE_W
        and not _is_elided(w)
    ):
        found.append(
            Finding("squeezed", describe(w, top), f"{w.width()} px wide, its minimum is {want_w}")
        )
    return found


def _is_elided(w: QWidget) -> bool:
    """A label that cuts its own text with an ellipsis (`ElidedLabel`, or any label with the
    property `elide`)."""
    return bool(w.property("elide")) or "Elide" in type(w).__name__ or hasattr(w, "is_elided")


def _wrap_clipped(w: QWidget, top: QWidget) -> list[Finding]:
    if not isinstance(w, QLabel) or not w.wordWrap() or not w.hasHeightForWidth():
        return []
    need = w.heightForWidth(w.width())
    if need > w.height() + 1 and w.maximumHeight() >= need:
        return [
            Finding(
                "wrap-clipped",
                describe(w, top),
                f"{w.height()} px high, its text needs {need} at {w.width()} px wide",
            )
        ]
    if need > w.height() + 1:
        return [
            Finding(
                "wrap-clipped",
                describe(w, top),
                f"{w.height()} px high, its text needs {need} at {w.width()} px wide "
                f"(maximum height {w.maximumHeight()})",
            )
        ]
    return []


def _text_cut(w: QWidget, top: QWidget) -> list[Finding]:
    if _is_elided(w) or not isinstance(w, QLabel | QAbstractButton):
        return []
    if isinstance(w, QLabel) and (w.wordWrap() or not w.pixmap().isNull() or not w.text()):
        return []
    text = _text(w)
    if not text or "\n" in text or "<" in text:
        return []  # (a label with markup is judged by its size hint: the font is not the base one)
    need = w.fontMetrics().horizontalAdvance(text.replace("&", ""))
    if need > w.width():
        return [Finding("text-cut", describe(w, top), f"{w.width()} px wide, the text is {need}")]
    return []


def _window_short(w: QWidget, top: QWidget) -> list[Finding]:
    lay = w.layout()
    if not w.isWindow() or lay is None or not lay.hasHeightForWidth():
        return []
    need = max(lay.minimumHeightForWidth(w.width()), lay.totalMinimumSize().height())
    if w.height() < need - 1:
        return [
            Finding(
                "window-short",
                describe(w, top),
                f"{w.height()} px high, its layout needs {need} at {w.width()} px wide",
            )
        ]
    return []


def audit(root: QWidget, *, scrolled: bool = True) -> list[Finding]:
    """Everything that is wrong with the layout of `root`, which is shown."""
    found: list[Finding] = []
    for w in _walk(root, scrolled):
        found += _window_short(w, root)
        found += _overlaps(w, root)
        if not isinstance(w, QAbstractScrollArea):
            found += _outside(w, root)
        found += _squeezed(w, root)
        found += _wrap_clipped(w, root)
        found += _text_cut(w, root)
    seen: set[str] = set()
    unique: list[Finding] = []
    for f in found:
        if str(f) not in seen:
            seen.add(str(f))
            unique.append(f)
    return unique
