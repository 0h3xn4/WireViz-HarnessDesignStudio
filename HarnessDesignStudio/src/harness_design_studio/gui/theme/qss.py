"""The application style sheet, generated from the tokens.

It holds no colour: every colour is a palette role (`palette(base)`, see palette.py), so the same
sheet serves the light and the dark theme and a theme switch does not re-parse it. It depends only on
the UI scale and the name of the monospace family. Widgets pick up rules with dynamic properties
(`primary`, `danger`, `ghost`, `align`, `mono`, `muted`, `heading`, `card`, `banner` ...) instead of
calling `setStyleSheet` themselves.
"""

from harness_design_studio.gui.theme.palette import role
from harness_design_studio.gui.theme.tokens import (
    CONTROL_HEIGHT,
    FOCUS_RING,
    RADIUS_CONTROL,
    RADIUS_PANEL,
    TYPE_SCALE,
)


def stylesheet(scale: float = 1.0, mono: str = "monospace") -> str:
    def px(v: float) -> str:
        return f"{max(1, round(v * scale))}px"

    c = role
    base, small, caption = (
        px(TYPE_SCALE["base"]),
        px(TYPE_SCALE["small"]),
        px(TYPE_SCALE["caption"]),
    )
    section = px(TYPE_SCALE["section"])
    s4, s8, s16 = px(4), px(8), px(16)
    r_ctl, r_panel = px(RADIUS_CONTROL), px(RADIUS_PANEL)
    ring = px(FOCUS_RING)
    inner = (
        f"{max(1, round(CONTROL_HEIGHT * scale) - 2)}px"  # the box is min-height plus 1 px borders
    )
    icon = px(16)
    bar = px(10)
    return f"""
QWidget {{ color: {c("text.primary")}; font-size: {base}; font-weight: 400; }}
QWidget[mono="true"] {{ font-family: "{mono}"; }}
QMainWindow, QDialog {{ background: {c("bg.canvas")}; }}
QToolBar {{ background: {c("bg.surface")}; border: none; border-bottom: 1px solid {c("border.subtle")}; spacing: {s4}; padding: {s4}; }}
QToolBar#main-toolbar {{ background: {c("bg.surface")}; border: none; border-bottom: 1px solid {c("border.subtle")}; padding: 0; }}
QToolBar#rail-toolbar {{ background: {c("bg.surface")}; border: none; border-right: 1px solid {c("border.subtle")}; padding: 0; }}
QFrame#nav-rail {{ background: transparent; border: none; }}
QToolButton[rail="true"] {{ background: transparent; border: none; border-left: {px(3)} solid transparent; border-radius: {r_ctl}; padding: {s4} {s4}; color: {c("text.secondary")}; font-size: {caption}; min-height: {px(52)}; max-height: {px(64)}; }}
QToolButton[rail="true"][iconOnly="true"] {{ min-height: {inner}; max-height: {inner}; padding: 0; }}
QToolButton[rail="true"]:hover {{ background: {c("bg.hover")}; color: {c("text.primary")}; }}
QToolButton[rail="true"]:checked {{ background: {c("bg.selected")}; color: {c("text.primary")}; border-left: {px(3)} solid {c("accent")}; font-weight: 600; }}
QToolButton[rail="true"]:focus {{ border: {ring} solid {c("focus")}; }}
QMenuBar {{ background: {c("bg.canvas")}; }}
QMenuBar::item {{ padding: {s4} {s8}; border-radius: {r_ctl}; background: transparent; }}
QMenuBar::item:selected {{ background: {c("bg.hover")}; }}
QMenu {{ background: {c("bg.raised")}; border: 1px solid {c("border.strong")}; padding: {s4}; }}
QMenu::item {{ padding: {s4} {s16}; border-radius: {r_ctl}; }}
QMenu::item:selected {{ background: {c("bg.hover")}; }}
QMenu::item:disabled {{ color: {c("text.muted")}; }}
QMenu::separator {{ height: 1px; background: {c("border.subtle")}; margin: {s4} {s8}; }}
QDockWidget {{ border: 1px solid {c("border.subtle")}; }}
QDockWidget::title {{ background: {c("bg.surface")}; border-bottom: 1px solid {c("border.subtle")}; padding: {s8}; font-weight: 600; }}
QStatusBar {{ background: {c("bg.surface")}; color: {c("text.secondary")}; border-top: 1px solid {c("border.subtle")}; font-size: {small}; }}
QStatusBar::item {{ border: none; }}
QSplitter::handle {{ background: transparent; }}
QPushButton, QToolButton {{ background: {c("bg.raised")}; border: 1px solid {c("border.strong")}; border-radius: {r_ctl}; padding: 0 {s8}; min-height: {inner}; max-height: {inner}; qproperty-iconSize: {icon} {icon}; }}
QToolButton[iconOnly="true"] {{ padding: 0 {s8}; min-width: {inner}; }}
QPushButton:hover:enabled, QToolButton:hover:enabled {{ background: {c("bg.hover")}; }}
QPushButton:pressed:enabled, QToolButton:pressed:enabled {{ background: {c("bg.selected")}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {c("text.muted")}; border-color: {c("border.subtle")}; }}
QPushButton[primary="true"] {{ background: {c("accent")}; color: {c("accent.text")}; border-color: {c("accent")}; font-weight: 600; }}
QPushButton[primary="true"]:hover:enabled, QPushButton[primary="true"]:pressed:enabled {{ background: {c("accent.hover")}; border-color: {c("accent.hover")}; }}
QPushButton[primary="true"]:disabled {{ background: {c("bg.hover")}; color: {c("text.muted")}; border-color: {c("border.subtle")}; }}
QPushButton[danger="true"] {{ border-color: {c("status.critical")}; color: {c("status.critical")}; }}
QPushButton[ghost="true"], QToolButton[ghost="true"] {{ background: transparent; border-color: transparent; }}
QPushButton[ghost="true"]:hover:enabled, QToolButton[ghost="true"]:hover:enabled {{ background: {c("bg.hover")}; }}
QPushButton[step="done"] {{ border-bottom: {px(3)} solid {c("status.normal")}; }}
QPushButton[step="attention"] {{ border-bottom: {px(3)} solid {c("status.caution")}; }}
QPushButton[step="running"] {{ border-bottom: {px(3)} solid {c("status.standby")}; }}
QPushButton[step="blocked"] {{ color: {c("text.muted")}; }}
QPushButton[align="left"] {{ text-align: left; }}
QToolButton:checked, QPushButton:checked {{ background: {c("accent")}; color: {c("accent.text")}; border-color: {c("accent")}; }}
QToolButton[toggle="true"]:checked, QPushButton[toggle="true"]:checked {{ background: {c("bg.selected")}; color: {c("text.primary")}; border: 1px solid {c("accent")}; font-weight: 600; }}
QPushButton:focus, QToolButton:focus, QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border: {ring} solid {c("focus")}; }}
QPushButton[primary="true"]:focus {{ border: {ring} solid {c("text.primary")}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {c("bg.surface")}; border: 1px solid {c("border.control")}; border-radius: {r_ctl}; padding: 0 {s8}; min-height: {inner}; max-height: {inner}; selection-background-color: {c("accent")}; selection-color: {c("accent.text")}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{ background: {c("bg.canvas")}; color: {c("text.muted")}; border-color: {c("border.subtle")}; }}
QTextEdit, QPlainTextEdit {{ background: {c("bg.surface")}; border: 1px solid {c("border.control")}; border-radius: {r_ctl}; padding: {s4} {s8}; selection-background-color: {c("accent")}; selection-color: {c("accent.text")}; }}
QLineEdit[invalid="true"] {{ border: {ring} solid {c("status.critical")}; }}
QComboBox QAbstractItemView {{ background: {c("bg.raised")}; border: 1px solid {c("border.strong")}; selection-background-color: {c("bg.selected")}; selection-color: {c("text.primary")}; }}
QTabWidget::pane {{ background: {c("bg.surface")}; border: 1px solid {c("border.subtle")}; border-radius: {r_panel}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {c("text.secondary")}; padding: {s8} {s16}; border: none; border-bottom: {ring} solid transparent; }}
QTabBar::tab:hover:!selected {{ background: {c("bg.hover")}; color: {c("text.primary")}; }}
QTabBar::tab:selected {{ color: {c("text.primary")}; font-weight: 600; border-bottom: {ring} solid {c("accent")}; }}
QTabBar::tab:focus {{ border-bottom: {ring} solid {c("focus")}; }}
QTableView, QTreeView, QListView, QListWidget {{ background: {c("bg.surface")}; alternate-background-color: {c("bg.surface")}; gridline-color: {c("border.subtle")}; selection-background-color: {c("bg.selected")}; selection-color: {c("text.primary")}; border: 1px solid {c("border.subtle")}; border-radius: {r_ctl}; }}
QTableView, QTreeView {{ font-size: {small}; }}
QTableView::item:hover, QTreeView::item:hover, QListView::item:hover {{ background: {c("bg.hover")}; }}
QTableView::item:selected, QTreeView::item:selected, QListView::item:selected {{ background: {c("bg.selected")}; color: {c("text.primary")}; }}
QListWidget[nav="true"] {{ background: {c("bg.canvas")}; border: none; border-right: 1px solid {c("border.subtle")}; border-radius: 0; padding: {s8}; outline: none; }}
QListWidget[nav="true"]::item {{ min-height: {inner}; padding: 0 {s8}; border-left: {px(3)} solid transparent; border-radius: {r_ctl}; }}
QListWidget[nav="true"]::item:selected {{ border-left: {px(3)} solid {c("accent")}; font-weight: 600; }}
QHeaderView::section {{ background: {c("bg.surface")}; color: {c("text.secondary")}; border: 0; border-bottom: 1px solid {c("border.subtle")}; padding: {s4} {s8}; font-weight: 500; }}
QTableCornerButton::section {{ background: {c("bg.surface")}; border: 0; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: {bar}; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: {bar}; margin: 0; }}
QScrollBar::handle:vertical {{ background: {c("border.strong")}; border-radius: {px(4)}; min-height: {px(24)}; margin: {px(1)}; }}
QScrollBar::handle:horizontal {{ background: {c("border.strong")}; border-radius: {px(4)}; min-width: {px(24)}; margin: {px(1)}; }}
QScrollBar::handle:hover {{ background: {c("border.control")}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; background: none; border: none; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QCheckBox, QRadioButton {{ spacing: {s8}; border: {ring} solid transparent; padding: 1px; }}
QCheckBox:focus, QRadioButton:focus {{ border: {ring} solid {c("focus")}; }}
QLabel[muted="true"] {{ color: {c("text.secondary")}; }}
QLabel[error="true"] {{ color: {c("status.critical")}; }}
QLabel[title="true"] {{ font-size: {section}; font-weight: 600; }}
QLabel[dirty="true"] {{ color: {c("status.caution")}; font-weight: 600; }}
QLabel#checks-stale {{ color: palette(tooltip-text); font-weight: 600; }}
QLabel[heading="true"] {{ color: {c("text.secondary")}; font-size: {caption}; font-weight: 600; }}
QFrame[card="true"] {{ background: {c("bg.surface")}; border: 1px solid {c("border.subtle")}; border-radius: {r_panel}; }}
QFrame[card="true"][severity="warning"] {{ border-left: {px(6)} solid {c("status.caution")}; }}
QFrame[card="true"][severity="error"] {{ border-left: {px(6)} solid {c("status.critical")}; }}
QFrame[card="true"][severity="info"] {{ border-left: {px(6)} solid {c("status.standby")}; }}
QFrame[banner="true"] {{ background: {c("bg.hover")}; border: 1px solid {c("status.caution")}; border-radius: {r_ctl}; }}
QFrame[banner="true"] QLabel {{ background: transparent; }}
QFrame[banner="true"][severity="error"] {{ border: 1px solid {c("status.critical")}; border-left: {px(6)} solid {c("status.critical")}; }}
QFrame[banner="true"][severity="info"] {{ border: 1px solid {c("status.standby")}; border-left: {px(6)} solid {c("status.standby")}; }}
QToolTip {{ background: {c("bg.raised")}; color: {c("text.primary")}; border: 1px solid {c("border.strong")}; padding: {s4} {s8}; }}
QProgressBar {{ background: {c("bg.hover")}; border: none; border-radius: {px(4)}; text-align: center; }}
QProgressBar::chunk {{ background: {c("accent")}; border-radius: {px(4)}; }}
"""
