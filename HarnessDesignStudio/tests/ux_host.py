"""A tiny host for the UX foundation (theme, icons, state chips, shared tables): a window with an icon
gallery, one chip per state and a wire table. Tests drive it offscreen; `grab()` makes the pictures
in docs/ux/build/ux-found."""

from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui import icons, strings
from harness_design_studio.gui.states import STATES, StateChip
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager

WIRE_COLUMNS = [
    Column("id", "Wire", mono=True),
    Column("signal", "Signal"),
    Column("from", "From", mono=True),
    Column("to", "To", mono=True),
    Column("gauge", "Gauge", unit="AWG", numeric=True, state="gauge_state"),
    Column("length", "Length", unit="m", numeric=True, fmt=lambda v: "" if v is None else f"{v:g}"),
    Column("check", "Check", state="check_state", tooltip="check_note"),
]

WIRE_ROWS: list[dict[str, Any]] = [
    {"id": "W10", "signal": "TX+", "from": "J2.1", "to": "J7.4", "gauge": 24, "length": 0.45,
     "check": "pass", "check_state": "pass"},
    {"id": "W2", "signal": "TX-", "from": "J2.2", "to": "J7.5", "gauge": 24, "length": 0.45,
     "check": "fail", "check_state": "fail", "check_note": "Longer than the segment allows"},
    {"id": "W3", "signal": "28V", "from": "J1.1", "to": "J9.1", "gauge": None, "length": 1.2,
     "gauge_state": "pending", "gauge_text": "pending", "check": "not checked",
     "check_state": "not-checked", "check_note": "No ampacity table supplied"},
    {"id": "W4", "signal": "RTN", "from": "J1.2", "to": "J9.2", "gauge": 20, "length": None,
     "check": "locked", "check_state": "locked", "check_note": "Locked by release A"},
    {"id": "W11", "signal": "SHD", "from": "J2.9", "to": "J7.9", "gauge": 26, "length": 0.3},
]  # fmt: skip


def wire_model(theme: ThemeManager) -> DictTableModel:
    rows = [dict(r) for r in WIRE_ROWS]
    for r in rows:
        if r.get("gauge_state") == "pending":
            r["gauge"] = "pending"
    return DictTableModel(WIRE_COLUMNS, rows, theme)


class UxHost(QWidget):
    """Gallery of icons, state chips, buttons and a table, in the current theme."""

    def __init__(self, theme: ThemeManager, settings: QSettings | None = None) -> None:
        super().__init__()
        self.theme = theme
        self.setObjectName("ux-host")
        lay = QVBoxLayout(self)
        row = QHBoxLayout()
        self.buttons: list[QToolButton | QPushButton] = []
        for name, label, key in (
            ("zoom-in", strings.ZOOM_IN, "Ctrl+="),
            ("zoom-out", strings.ZOOM_OUT, "Ctrl+-"),
            ("fit", strings.FIT, "Ctrl+0"),
        ):
            b = QToolButton()
            icons.icon_button(b, name, theme, label, key)
            row.addWidget(b)
            self.buttons.append(b)
        for text in (strings.GENERATE, strings.EXPORT):
            p = QPushButton(text)
            p.setProperty("primary", text == strings.GENERATE)
            row.addWidget(p)
            self.buttons.append(p)
        row.addStretch(1)
        lay.addLayout(row)
        grid = QGridLayout()
        self.gallery: dict[str, QLabel] = {}
        for i, name in enumerate(icons.ICON_NAMES):
            cell = QLabel()
            cell.setPixmap(icons.icon(name, theme).pixmap(24, 24))
            cell.setToolTip(name)
            cell.setAccessibleName(name)
            grid.addWidget(cell, i // 14, i % 14)
            self.gallery[name] = cell
        lay.addLayout(grid)
        chips = QHBoxLayout()
        self.chips: dict[str, StateChip] = {}
        for state in STATES:
            chip = StateChip(theme, state)
            chips.addWidget(chip)
            self.chips[state] = chip
        chips.addStretch(1)
        lay.addLayout(chips)
        self.table = TableView(
            wire_model(theme), theme, name="Wire list", settings=settings, key="ux-host-wires"
        )
        lay.addWidget(self.table, 1)
