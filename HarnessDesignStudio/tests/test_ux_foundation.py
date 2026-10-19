# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""UX foundation: theme (palette, system/light/dark, scales, fonts), icon set, state chips and the
shared table code (model, proxy, TSV copy, saved widths). Offscreen, driven by tests/ux_host.py."""

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import QRect, QSettings, Qt  # noqa: E402
from PySide6.QtGui import (  # noqa: E402
    QColor,
    QFont,
    QFontInfo,
    QFontMetrics,
    QGuiApplication,
    QIcon,
    QImage,
    QPainter,
    QPalette,
)
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QAbstractButton,
    QComboBox,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStyleOptionViewItem,
    QTableView,
    QToolBar,
    QToolButton,
    QWidget,
)

import harness_design_studio.gui as gui_pkg  # noqa: E402
from harness_design_studio.gui import icons, strings  # noqa: E402
from harness_design_studio.gui.states import (  # noqa: E402
    FILL_ALPHA,
    PATTERN_ALPHA,
    PATTERN_COVERAGE,
    STATE_ROLE,
    STATES,
    StateChip,
    StateDelegate,
    paint_chip,
)
from harness_design_studio.gui.tables import (  # noqa: E402
    SORT_ROLE,
    Column,
    DictTableModel,
    TableProxy,
    TableView,
    copy_tsv,
    natural_key,
    persist_widths,
)
from harness_design_studio.gui.theme import (  # noqa: E402
    MODES,
    ROLES,
    ThemeManager,
    build_palette,
    mark_mono,
    mono_family,
)
from harness_design_studio.gui.theme import manager as theme_mod  # noqa: E402
from harness_design_studio.gui.theme.tokens import (  # noqa: E402
    DARK,
    LIGHT,
    SPACING,
    TYPE_SCALE,
    contrast,
)
from tests.gui_helpers import make_window, show_problems  # noqa: E402
from tests.ux_host import WIRE_COLUMNS, WIRE_ROWS, UxHost, wire_model  # noqa: E402

GUI_DIR = Path(gui_pkg.__file__).parent


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


# ---- SH-19: palette, system / light / dark -------------------------------------------------------


@pytest.mark.parametrize("name,tokens", [("light", LIGHT), ("dark", DARK)])
def test_palette_comes_from_the_tokens(qapp, theme, name, tokens) -> None:
    theme.apply(qapp, name)
    pal = qapp.palette()
    assert pal.color(QPalette.ColorRole.Window).name().upper() == tokens["bg"]
    assert pal.color(QPalette.ColorRole.WindowText).name().upper() == tokens["text"]
    assert pal.color(QPalette.ColorRole.Highlight).name().upper() == tokens["primary"]
    assert pal.color(QPalette.ColorRole.HighlightedText).name().upper() == tokens["on-primary"]
    assert pal.color(QPalette.ColorRole.AlternateBase).name().upper() == tokens["bg.hover"]
    for token, (_, qt_role) in ROLES.items():  # every token the style sheet names has its role
        assert pal.color(qt_role).name().upper() == tokens[token], token
    disabled = pal.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
    assert disabled.name().upper() == tokens["text-muted"]
    assert build_palette(tokens).color(QPalette.ColorRole.Link).name().upper() == tokens["info"]


def test_default_mode_is_system_and_follows_the_os_scheme(qapp, theme, monkeypatch) -> None:
    assert ThemeManager().mode == "system" and MODES == ("system", "light", "dark")
    monkeypatch.setattr(theme_mod, "os_scheme", lambda: "dark")
    theme.apply(qapp, "system")
    assert (theme.mode, theme.name) == ("system", "dark")
    monkeypatch.setattr(theme_mod, "os_scheme", lambda: "light")
    theme._os_changed()  # the OS switched while the program runs
    assert (theme.mode, theme.name) == ("system", "light")
    theme.apply(qapp, "dark")  # an explicit choice ignores the OS
    monkeypatch.setattr(theme_mod, "os_scheme", lambda: "light")
    theme._os_changed()
    assert theme.name == "dark"


def test_the_os_colour_scheme_signal_reapplies_a_system_theme(qapp, theme, monkeypatch) -> None:
    """The offscreen platform has no colour scheme, so the platform's signal is emitted by hand."""
    assert theme_mod.os_scheme() == "light"  # the platform says nothing: light
    theme.apply(qapp, "system")
    seen: list[str] = []
    theme.changed.connect(lambda: seen.append(theme.name))
    monkeypatch.setattr(theme_mod, "os_scheme", lambda: "dark")
    QGuiApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert theme.name == "dark" and seen == ["dark"]
    assert qapp.palette().color(QPalette.ColorRole.Window).name().upper() == DARK["bg"]
    theme.apply(qapp, "light")  # an explicit choice is not moved by the OS
    monkeypatch.setattr(theme_mod, "os_scheme", lambda: "dark")
    QGuiApplication.styleHints().colorSchemeChanged.emit(Qt.ColorScheme.Dark)
    assert theme.name == "light"


def test_window_stores_the_theme_choice_and_defaults_to_system(qtbot, tmp_path) -> None:
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    assert w.theme.mode == "system" and w.theme_actions["system"].isChecked()
    assert [a.text() for a in w.theme_actions.values()] == [
        strings.A_THEME_SYSTEM,
        strings.A_THEME_LIGHT,
        strings.A_THEME_DARK,
    ]
    w.theme_actions["dark"].trigger()
    assert w.theme.name == "dark" and w.settings.value("ui/theme") == "dark"
    assert w.act_dark.isChecked()
    w.theme_actions["system"].trigger()
    assert w.settings.value("ui/theme") == "system" and w.theme.mode == "system"
    w2 = make_window(tmp_path)
    qtbot.addWidget(w2)
    assert w2.theme.mode == "system"
    w.theme_actions["light"].trigger()
    w3 = make_window(tmp_path)
    qtbot.addWidget(w3)
    assert w3.theme.mode == "light" and w3.theme_actions["light"].isChecked()


def test_a_damaged_theme_setting_falls_back_to_system(qtbot, tmp_path) -> None:
    QSettings(str(tmp_path / "ui.ini"), QSettings.Format.IniFormat).setValue("ui/theme", "pink")
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    assert w.theme.mode == "system"


# ---- SH-22: type scale and spacing ----------------------------------------------------------


def test_type_and_space_follow_the_standard_and_the_ui_scale(qapp, theme) -> None:
    assert [theme.type(k) for k in TYPE_SCALE] == [11, 12, 13, 15, 18, 22]
    assert [theme.space(n) for n in SPACING] == [4, 8, 12, 16, 24, 32]
    theme.apply(qapp, scale=1.5)
    assert theme.type("title") == 27 and theme.space(8) == 12
    with pytest.raises(ValueError):
        theme.space(5)
    with pytest.raises(KeyError):
        theme.type("huge")
    assert list(TYPE_SCALE.values()) == [11, 12, 13, 15, 18, 22]
    assert qapp.font().pixelSize() == theme.type("base")


def test_no_literal_pixel_sizes_and_no_hard_coded_colours_in_gui() -> None:
    """New code asks the theme: no `setPixelSize(12)`, no `setStyleSheet`, no "#RRGGBB" outside
    tokens (the logo in appicon.py keeps its brand colours)."""
    literal = re.compile(r"setPixelSize\(\s*[\d.]")
    computed_ok = {
        "theme.py",
        "preview.py",
        "panels.py",
        "canvas.py",
    }  # sizes computed from a zoom or a box
    from_theme = re.compile(r"setPixelSize\((?:[\w.]*\.type\(|OVERVIEW_FONT_PX)")
    hexcolour = re.compile(r"""["']#[0-9a-fA-F]{6}["']""")
    for f in sorted(GUI_DIR.glob("*.py")):
        text = f.read_text(encoding="utf-8")
        assert not literal.search(text), f"{f.name}: literal pixel size, use theme.type()"
        calls = text.count("setPixelSize(")
        assert calls == len(from_theme.findall(text)) or f.name in computed_ok, (
            f"{f.name}: a font size that does not come from theme.type()"
        )
        if f.name != "theme.py":
            assert "setStyleSheet(" not in text, f"{f.name}: use a theme rule"
        if f.name not in ("tokens.py", "appicon.py"):
            assert not hexcolour.search(text), f"{f.name}: colour literal, use a token"


# ---- SH-21: monospace -----------------------------------------------------------------------


def test_mono_font_is_jetbrains_mono_and_follows_the_scale(qapp, theme) -> None:
    f = theme.mono_font()
    assert f.family() == mono_family() == "JetBrains Mono"
    assert f.pixelSize() == 13 and theme.mono_font("small").pixelSize() == 12
    theme.apply(qapp, scale=2.0)
    assert theme.mono_font().pixelSize() == 26
    assert theme.font("section", bold=True).weight() == QFont.Weight.DemiBold


def test_mono_property_gives_a_widget_the_monospace_font(qapp, theme, qtbot) -> None:
    edit = QLineEdit("REQ-001")
    qtbot.addWidget(edit)
    plain = QFontInfo(edit.font()).family()
    mark_mono(edit)
    edit.ensurePolished()
    assert QFontInfo(edit.font()).family() == "JetBrains Mono" != plain
    assert edit.styleSheet() == ""  # the theme's rule did it, not a widget style sheet


def test_status_bar_hash_ids_and_pin_columns_are_monospace(qtbot, tmp_path) -> None:
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    w._update_hash()
    w.status_hash.ensurePolished()
    assert re.fullmatch(r"[0-9a-f]{8}|-{8}", w.status_hash.text())
    assert QFontInfo(w.status_hash.font()).family() == "JetBrains Mono"
    w.show_interfaces()
    model = w.interface_table.model
    model.reload()
    assert model.rowCount() > 0
    mono = model.index(0, 0).data(Qt.ItemDataRole.FontRole)
    assert mono.family() == "JetBrains Mono"  # ID
    assert model.index(0, 7).data(Qt.ItemDataRole.FontRole).family() == "JetBrains Mono"
    assert model.index(0, 1).data(Qt.ItemDataRole.FontRole) is None  # the name stays in Sans


def test_drawing_preview_uses_tokens_and_the_mono_font(qapp, theme, qtbot) -> None:
    from harness_design_studio.core.outputs.canvas import Sheet, Text
    from harness_design_studio.gui.preview import SheetView

    view = SheetView(theme)
    qtbot.addWidget(view)
    view.resize(300, 220)
    view.set_sheet(Sheet(100, 70, [Text(10, 30, "W1", 8)]))
    for name, tokens in (("light", LIGHT), ("dark", DARK)):
        theme.apply(qapp, name)
        img = view.grab().toImage()
        assert QColor(img.pixel(1, 1)).name().upper() == tokens["pasteboard"]
        assert QColor(img.pixel(150, 110)).name().upper() == tokens["paper"]


# ---- SH-20: no style sheet in widgets ---------------------------------------------------------


def test_todo_buttons_are_left_aligned_by_a_theme_rule(qtbot, tmp_path) -> None:
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    from harness_design_studio.core import checks
    from harness_design_studio.gui.panels import ProblemsPanel

    monkey = checks.Todo("a thing to do", "unit", "X")
    w.ctl.todos = lambda: [monkey]  # type: ignore[method-assign]
    panel = ProblemsPanel(w.ctl)  # the to-do lines are the top of the Problems list
    qtbot.addWidget(panel)
    panel.refresh()
    b = panel.findChild(QPushButton, "todo-0")
    assert b is not None and b.styleSheet() == "" and b.property("align") == "left"


# ---- SH-23: equal control heights -----------------------------------------------------------


@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5, 2.0])
@pytest.mark.parametrize("name", ["light", "dark"])
def test_all_controls_have_one_height(qapp, theme, qtbot, name, scale) -> None:
    theme.apply(qapp, name, scale)
    host = QWidget()
    qtbot.addWidget(host)
    bar = QToolBar(host)
    tool_in_bar = QToolButton()
    tool_in_bar.setText("Undo")
    bar.addWidget(tool_in_bar)
    primary = QPushButton("Generate")
    primary.setProperty("primary", True)
    danger = QPushButton("Delete")
    danger.setProperty("danger", True)
    icon_only = QToolButton()
    icons.icon_button(icon_only, "zoom-in", theme, "Zoom in", "Ctrl+=")
    combo = QComboBox()
    combo.addItem("All")
    widgets = [QPushButton("Check"), primary, danger, QToolButton(), icon_only, tool_in_bar,
               combo, QLineEdit("x"), QSpinBox()]  # fmt: skip
    widgets[3].setText("Fit")  # type: ignore[attr-defined]
    from PySide6.QtWidgets import QHBoxLayout

    lay = QHBoxLayout(host)
    for x in widgets:
        if x is not tool_in_bar:
            lay.addWidget(x)
    lay.addWidget(bar)
    host.show()
    QTest.qWait(10)
    heights = {type(x).__name__ + str(i): x.height() for i, x in enumerate(widgets)}
    assert set(heights.values()) == {theme.control_height()}, heights


def test_toolbar_and_canvas_buttons_of_the_main_window_have_one_height(qtbot, tmp_path) -> None:
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    QTest.qWait(10)
    buttons = [w.generate_btn, w.mode_guided, w.mode_expert, w.search_btn, w.tool_select,
               w.tool_connect, w.zoom_in_btn, w.zoom_out_btn, w.fit_btn, w.delete_btn,
               w.redundant_btn]  # fmt: skip
    assert {b.height() for b in buttons} == {w.theme.control_height()}


# ---- SH-25: icons ---------------------------------------------------------------------------

REQUIRED_ICONS = [
    "undo", "redo", "generate", "check", "export", "import", "zoom-in", "zoom-out", "fit",
    "search", "lock", "unlock", "release", "review", "revise", "folder-open", "reveal",
    "warning", "error", "info", "pass", "fail", "not-checked", "pending", "chevron-up",
    "chevron-down", "chevron-left", "chevron-right", "close", "filter", "tree", "list", "table",
    "diagram", "harness", "releases",
]  # fmt: skip


def test_every_required_icon_exists_parses_and_stays_in_its_grid() -> None:
    assert set(REQUIRED_ICONS) <= set(icons.ICON_NAMES)
    for name in icons.ICON_NAMES:
        r = icons.icon_path(name).boundingRect()
        assert r.width() > 2 and r.height() > 2, name
        assert r.left() >= -1 and r.right() <= 25 and r.top() >= -1 and r.bottom() <= 25, name


def test_svg_path_parser_handles_arcs_flags_and_relative_commands() -> None:
    box = icons.parse_path("M0 0h10v10H0z").boundingRect()
    assert (box.width(), box.height()) == (10, 10)
    arc = icons.parse_path("M0 0a5 5 0 0 1 10 0").boundingRect()  # clockwise: over the top
    assert arc.width() == pytest.approx(10, abs=0.01) and arc.top() == pytest.approx(-5, abs=0.05)
    under = icons.parse_path("M0 0a5 5 0 0 0 10 0").boundingRect()
    assert under.bottom() == pytest.approx(5, abs=0.05)
    packed = icons.parse_path("M15.9 4a1.5 1.5 0 00-2.474-1.561")  # flags without separators
    assert packed.elementCount() > 2
    line_to = icons.parse_path("m1 1 2 2 2-2").boundingRect()  # implicit line-tos after a move
    assert (line_to.width(), line_to.height()) == (4, 2)
    with pytest.raises(ValueError):
        icons.parse_path("M1 1 L")


def _rgb(colour: str) -> tuple[int, int, int]:
    c = QColor(colour)
    return (c.red(), c.green(), c.blue())


def _ink(img: QImage) -> list[tuple[int, int, int, int]]:
    """The (r, g, b, a) of every almost opaque pixel."""
    img = img.convertToFormat(QImage.Format.Format_ARGB32)
    out = []
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor.fromRgba(img.pixel(x, y))
            if c.alpha() > 200:
                out.append((c.red(), c.green(), c.blue(), c.alpha()))
    return out


def _main_colour(img: QImage) -> tuple[int, int, int]:
    from collections import Counter

    ink = Counter(p[:3] for p in _ink(img) if p[3] == 255)
    return ink.most_common(1)[0][0]


@pytest.mark.parametrize("name", icons.ICON_NAMES)
def test_every_icon_paints_ink_in_the_requested_colour(name) -> None:
    img = icons.pixmap(name, 24, QColor("#336699")).toImage()
    ink = _ink(img)
    assert len(ink) > 10, name
    assert _main_colour(img) == (0x33, 0x66, 0x99)
    assert all(abs(p[0] - 0x33) <= 6 and abs(p[2] - 0x99) <= 6 for p in ink)


def test_icons_recolour_from_the_tokens_and_follow_a_theme_change(qapp, theme) -> None:
    ic = icons.icon("lock", theme)  # made once
    light = _main_colour(ic.pixmap(24, 24).toImage())
    assert light == _rgb(LIGHT["text"])
    theme.apply(qapp, "dark")
    dark = _main_colour(ic.pixmap(24, 24).toImage())  # the same QIcon
    assert dark == _rgb(DARK["text"])
    ok = icons.icon("pass", theme, "success").pixmap(24, 24).toImage()
    assert _main_colour(ok) == _rgb(DARK["success"])
    sel = ic.pixmap(24, 24, QIcon.Mode.Selected).toImage()
    assert _main_colour(sel) == _rgb(DARK["on-primary"])
    off = ic.pixmap(24, 24, QIcon.Mode.Disabled).toImage()
    alphas = {QColor.fromRgba(off.pixel(x, y)).alpha() for x in range(24) for y in range(24)}
    assert 100 < max(alphas) < 200  # drawn, but faint


def test_icons_are_size_aware_and_sharp_at_every_size(theme) -> None:
    assert icons.stroke_width(16) == 1.5 and icons.stroke_width(24) == 2.0
    assert icons.stroke_width(32) > icons.stroke_width(24) > icons.stroke_width(16)
    ink16 = len(_ink(icons.pixmap("table", 16, QColor("#000000")).toImage()))
    ink32 = len(_ink(icons.pixmap("table", 32, QColor("#000000")).toImage()))
    assert ink32 > ink16 > 20
    big = icons.icon("search", theme).pixmap(48, 48)
    assert (big.width(), big.height()) == (48, 48)
    hi = icons.pixmap("search", 16, QColor("#000000"), 2.0)
    assert hi.width() == 32 and hi.devicePixelRatio() == 2.0
    with pytest.raises(KeyError):
        icons.icon("nope", theme)


def test_icon_button_sets_icon_name_and_tooltip_with_shortcut(theme, qtbot) -> None:
    b = QToolButton()
    qtbot.addWidget(b)
    icons.icon_button(b, "zoom-in", theme, "Zoom in", "Ctrl+=")
    assert not b.icon().isNull() and b.text() == ""
    assert b.accessibleName() == "Zoom in" and b.toolTip() == "Zoom in (Ctrl+=)"
    assert icons.tooltip_text("Fit") == "Fit"


def test_existing_icon_buttons_have_icons_and_tooltips_with_shortcuts(qtbot, tmp_path) -> None:
    w = make_window(tmp_path)
    qtbot.addWidget(w)
    expect = {
        w.zoom_in_btn: "Ctrl+=",
        w.zoom_out_btn: "Ctrl+-",
        w.fit_btn: "F",
        w.search_btn: "Ctrl+K",
    }
    for button, key in expect.items():
        assert not button.icon().isNull(), button.objectName()
        assert key in button.toolTip(), (button.objectName(), button.toolTip())
        assert button.accessibleName().strip()
    assert w.zoom_in_btn.text() == "" and w.zoom_out_btn.text() == ""  # no "+" / "−" text
    assert w.act_import.shortcut().toString() == "Ctrl+Shift+I"  # was the Palette's Import button
    assert "(C)" in w.tool_connect.toolTip() and w.tool_connect.accessibleName() == "Connect"
    assert w.tool_connect.menu() is w.menu_connect  # the type arrow (the Palette's Connect with)
    for dock in (w.dock_left, w.dock_right):
        close = dock.findChild(QAbstractButton, "qt_dockwidget_closebutton")
        assert close is not None and not close.icon().isNull()
        assert close.toolTip() == strings.DOCK_CLOSE and close.accessibleName()
    w.set_theme_mode("dark")  # a new style sheet must not reset the dock buttons
    close = w.dock_left.findChild(QAbstractButton, "qt_dockwidget_closebutton")
    assert close is not None and not close.icon().isNull() and close.toolTip()
    assert not w.act_undo.icon().isNull() and "Ctrl+Z" in w.act_undo.toolTip()


def test_problem_show_button_has_an_icon_and_a_tooltip(qtbot, tmp_path) -> None:
    from harness_design_studio.core import checks

    w = make_window(tmp_path)
    qtbot.addWidget(w)
    show_problems(w)
    finding = checks.Finding(
        id="r.U1", rule="r", severity="warning", object_id="U1", title="A problem", why="because"
    )
    card = w.problems._card(finding)
    shows = [b for b in card.findChildren(QPushButton) if b.text() == strings.SHOW]
    assert shows and not shows[0].icon().isNull() and shows[0].toolTip() == strings.SHOW_ON_DIAGRAM


# ---- SH-28 / SC-7: state chips ---------------------------------------------------------------


def test_every_state_has_its_own_icon_word_and_the_nothing_known_ones_a_pattern() -> None:
    assert {"pass", "fail", "pending", "not-checked", "locked", "released", "stale"} <= set(STATES)
    assert len({s.icon for s in STATES.values()}) == len(STATES)
    assert len({s.label for s in STATES.values()}) == len(STATES)
    for s in STATES.values():
        assert s.icon in icons.ICONS and s.token in LIGHT and s.token in DARK
        assert (s.pattern != "solid") == (s.key in ("pending", "not-checked")), s.key
    assert STATES["pending"].pattern == "dotted" and STATES["not-checked"].pattern == "hatched"


@pytest.mark.parametrize("tokens", [LIGHT, DARK], ids=["light", "dark"])
def test_chip_text_stays_readable_on_its_tint_and_pattern(tokens) -> None:
    """Solid chips: AA text contrast on the tint. Dotted and hatched chips: AA on the average of
    tint and pattern, and 3:1 even on a pixel of a hatch line (the worst case)."""

    def blend(a: str, b: str, alpha: float) -> str:
        mix = [round(x * (1 - alpha) + y * alpha) for x, y in zip(_rgb(a), _rgb(b), strict=True)]
        return "#{:02X}{:02X}{:02X}".format(*mix)

    def stacked(a1: float, a2: float) -> float:
        return 1 - (1 - a1) * (1 - a2)

    for spec in STATES.values():
        cover = PATTERN_COVERAGE.get(spec.pattern, 0.0)
        average = stacked(FILL_ALPHA, PATTERN_ALPHA * cover)
        worst = stacked(FILL_ALPHA, PATTERN_ALPHA) if cover else FILL_ALPHA
        for surface in ("bg", "surface", "surface-2"):
            fg = tokens[spec.token]
            assert contrast(fg, blend(tokens[surface], fg, average)) >= 4.5, (spec.key, surface)
            assert contrast(fg, blend(tokens[surface], fg, worst)) >= 3.0, (spec.key, surface)


def _chip_image(theme, state: str, text: str | None, grey: bool = False) -> QImage:
    img = QImage(150, 28, QImage.Format.Format_ARGB32)
    img.fill(QColor(theme.tokens["bg"]))
    p = QPainter(img)
    paint_chip(p, QRect(2, 2, 146, 24), state, theme, text=text, font=QFont("Sans", 9))  # type: ignore[arg-type]
    p.end()
    return img.convertToFormat(QImage.Format.Format_Grayscale8) if grey else img


@pytest.mark.parametrize("name", ["light", "dark"])
def test_state_chips_differ_without_colour(qapp, theme, name) -> None:
    """Same text, colours removed: pass, fail, pending, not checked and locked still differ."""
    theme.apply(qapp, name)
    states = ["pass", "fail", "pending", "not-checked", "locked", "stale", "warning"]
    images = {s: _chip_image(theme, s, "42", grey=True) for s in states}
    for a in states:
        for b in states:
            if a < b:
                assert images[a] != images[b], (a, b)
    blank = QImage(150, 28, QImage.Format.Format_ARGB32)
    blank.fill(QColor(theme.tokens["bg"]))
    assert all(_chip_image(theme, s, "42") != blank for s in states)  # never like an empty cell


def test_pending_and_not_checked_have_a_pattern_that_pass_and_fail_do_not(theme) -> None:
    """A dotted or hatched fill adds pixels beyond border, icon and text: compare a chip with no
    text, whose border and icon are alike in position."""
    solid = _chip_image(theme, "pass", "")
    dotted = _chip_image(theme, "pending", "")
    hatched = _chip_image(theme, "not-checked", "")

    def distinct_tones(img: QImage) -> int:
        return len({img.pixel(x, 8) for x in range(60, 140)})

    assert distinct_tones(solid) == 1  # an even tint
    assert distinct_tones(dotted) > 1 and distinct_tones(hatched) > 1


def test_state_chip_widget_has_an_accessible_name_and_follows_the_theme(qapp, theme, qtbot) -> None:
    chip = StateChip(theme, "locked", "Released in rev B")
    qtbot.addWidget(chip)
    assert chip.accessibleName() == "Locked: Released in rev B"
    assert chip.sizeHint().width() > 60 and chip.state() == "locked"
    chip.set_state("pending")
    assert chip.accessibleName() == "Pending" and chip.text() is None
    with pytest.raises(KeyError):
        chip.set_state("shiny")
    chip.show()
    light = chip.grab().toImage()
    theme.apply(qapp, "dark")
    assert chip.grab().toImage() != light


def test_state_delegate_paints_a_chip_and_leaves_other_cells_alone(theme, qtbot) -> None:
    model = wire_model(theme)
    view = QTableView()
    qtbot.addWidget(view)
    view.setModel(model)
    delegate = StateDelegate(theme, view)
    view.setItemDelegate(delegate)
    view.resize(900, 300)
    view.show()
    view.resizeColumnsToContents()
    pending = model.index(2, 4)
    plain = model.index(2, 1)
    assert delegate.state_of(pending) == "pending" and delegate.state_of(plain) is None

    def cell(index, width: int = 0) -> QImage:
        size = view.visualRect(index).size()
        img = QImage(width or size.width(), size.height(), QImage.Format.Format_ARGB32)
        img.fill(QColor(theme.tokens["bg"]))
        opt = QStyleOptionViewItem()
        opt.initFrom(view)
        opt.rect = QRect(0, 0, img.width(), img.height())
        opt.widget = view
        p = QPainter(img)
        delegate.paint(p, opt, index)
        p.end()
        return img

    blank = QImage(cell(pending).size(), QImage.Format.Format_ARGB32)
    blank.fill(QColor(theme.tokens["bg"]))
    assert cell(pending) != blank  # a pending value is never an empty cell
    # in a wide cell a chip of a number column sits at the right edge, a text column's at the left
    bg = QColor(theme.tokens["bg"]).rgb()

    def ink_span(img: QImage) -> tuple[int, int]:
        xs = [
            x for x in range(img.width()) if any(img.pixel(x, y) != bg for y in range(img.height()))
        ]
        return xs[0], xs[-1]

    wide = cell(pending, 300)
    assert ink_span(wide)[0] > 150 and ink_span(wide)[1] >= 290
    left = cell(model.index(1, 6), 300)  # "fail" in a text column
    assert ink_span(left)[0] < 12 and ink_span(left)[1] < 200
    assert delegate.sizeHint(QStyleOptionViewItem(), pending).width() > 40
    assert model.index(4, 4).data(STATE_ROLE) is None  # a plain value has no state


# ---- SC-21: shared tables --------------------------------------------------------------------


def test_model_reads_dict_and_tuple_rows_and_puts_the_unit_in_the_header(theme) -> None:
    cols = [Column(0, "Pin", mono=True), Column(1, "Length", unit="m", numeric=True)]
    m = DictTableModel(cols, [("J1.1", 2.5), ("J1.10", None)], theme)
    assert (m.rowCount(), m.columnCount()) == (2, 2)
    assert m.headerData(1, Qt.Orientation.Horizontal) == "Length (m)"
    assert m.index(0, 1).data() == "2.5" and m.index(1, 1).data() == ""
    assert m.index(0, 1).data(Qt.ItemDataRole.EditRole) == 2.5
    d = DictTableModel(WIRE_COLUMNS, WIRE_ROWS, theme)
    assert d.index(1, 0).data() == "W2" and d.index(0, 5).data() == "0.45"
    assert d.column_index("gauge") == 4
    with pytest.raises(KeyError):
        d.column_index("nope")


def test_numbers_are_right_aligned_with_tabular_figures_and_ids_are_mono(theme) -> None:
    m = wire_model(theme)
    right = int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    left = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    assert m.index(0, 5).data(Qt.ItemDataRole.TextAlignmentRole) == right
    assert m.index(0, 1).data(Qt.ItemDataRole.TextAlignmentRole) == left
    assert m.headerData(5, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole) == right
    num = m.index(0, 5).data(Qt.ItemDataRole.FontRole)
    assert num.featureValue(QFont.Tag("tnum")) == 1  # tabular figures
    assert m.index(0, 0).data(Qt.ItemDataRole.FontRole).family() == "JetBrains Mono"
    assert m.index(0, 1).data(Qt.ItemDataRole.FontRole) is None
    f = QFont("Inter")
    f.setPixelSize(13)
    f.setFeature(QFont.Tag("tnum"), 1)
    metrics = QFontMetrics(f)
    assert len({metrics.horizontalAdvance(c) for c in "0123456789"}) == 1


def test_state_and_tooltip_roles(theme) -> None:
    m = wire_model(theme)
    assert m.index(2, 4).data(STATE_ROLE) == "pending" and m.index(2, 4).data() == "pending"
    assert m.index(1, 6).data(STATE_ROLE) == "fail"
    assert m.index(1, 6).data(Qt.ItemDataRole.ToolTipRole) == "Longer than the segment allows"
    assert m.index(0, 6).data(Qt.ItemDataRole.ToolTipRole) == "Pass"  # default: the state's word
    assert m.index(4, 6).data(STATE_ROLE) is None
    assert "Pending" in m.index(2, 4).data(Qt.ItemDataRole.AccessibleTextRole)
    odd = DictTableModel([Column("a", "A", state=lambda r: "no-such-state")], [{"a": 1}], theme)
    assert odd.index(0, 0).data(STATE_ROLE) is None


def test_sorting_is_numeric_natural_and_puts_blanks_first(theme) -> None:
    m = wire_model(theme)
    proxy = TableProxy()
    proxy.setSourceModel(m)
    proxy.sort(0)  # wire IDs: W2 before W10
    assert [proxy.index(r, 0).data() for r in range(5)] == ["W2", "W3", "W4", "W10", "W11"]
    proxy.sort(5, Qt.SortOrder.AscendingOrder)  # length: blank first, then numbers
    assert [proxy.index(r, 0).data() for r in range(5)][0] == "W4"
    assert [proxy.index(r, 5).data() for r in range(1, 5)] == ["0.3", "0.45", "0.45", "1.2"]
    proxy.sort(5, Qt.SortOrder.DescendingOrder)
    assert proxy.index(0, 5).data() == "1.2"
    assert natural_key("J2") < natural_key("J10") < natural_key("j11")
    assert m.index(0, 5).data(SORT_ROLE) == 0.45 and m.index(3, 5).data(SORT_ROLE) is None


def test_proxy_filters_by_words_state_and_predicate(theme) -> None:
    m = wire_model(theme)
    proxy = TableProxy()
    proxy.setSourceModel(m)
    proxy.set_text("j2 tx")
    assert proxy.rowCount() == 2
    proxy.set_text("")
    proxy.set_states({"pending", "not-checked"})
    assert sorted(proxy.index(r, 0).data() for r in range(proxy.rowCount())) == ["W3"]
    proxy.set_states({"fail", "locked"})
    assert proxy.rowCount() == 2
    proxy.set_states(None)
    proxy.set_predicate(lambda row: str(cast(Mapping[str, Any], row)["from"]).startswith("J1"))
    assert proxy.rowCount() == 2
    proxy.set_text("rtn")
    assert proxy.rowCount() == 1
    proxy.set_predicate(None)
    proxy.set_text("")
    assert proxy.rowCount() == 5


def test_update_rows_keeps_selection_when_the_rows_stay(theme, qtbot) -> None:
    view = TableView(wire_model(theme), theme, name="Wires")
    qtbot.addWidget(view)
    view.selectRow(2)
    rows = [dict(r, signal=r["signal"] + "!") for r in WIRE_ROWS]
    assert view.source.update_rows(rows) is False
    assert view.selectionModel().selectedRows()[0].row() == 2
    assert view.source.index(0, 1).data() == "TX+!"
    assert view.source.update_rows(rows[:3]) is True and view.source.rowCount() == 3


def test_table_view_basics_header_stays_and_cells_select(theme, qtbot) -> None:
    rows = [{"id": f"W{i}", "signal": "x", "gauge": i} for i in range(300)]
    cols = [Column("id", "Wire", mono=True), Column("signal", "Signal"),
            Column("gauge", "Gauge", unit="AWG", numeric=True)]  # fmt: skip
    view = TableView(DictTableModel(cols, rows, theme), theme, name="Wire list")
    qtbot.addWidget(view)
    view.resize(500, 300)
    view.show()
    head = view.horizontalHeader()
    top = head.geometry().top()
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())
    assert head.isVisible() and head.geometry().top() == top  # sticky
    assert view.verticalHeader().isHidden()
    assert view.accessibleName() == "Wire list" and view.isSortingEnabled()
    assert view.selectionBehavior() == QTableView.SelectionBehavior.SelectItems
    assert isinstance(view.itemDelegate(), StateDelegate)
    assert head.sortIndicatorSection() == -1  # rows stay in the given order until a click
    assert view.proxy.index(0, 0).data() == "W0" and view.proxy.index(299, 0).data() == "W299"
    view.set_rows(rows[:10])
    assert view.model().rowCount() == 10


def test_table_code_never_uses_table_widgets() -> None:
    for name in ("tables.py", "states.py"):
        text = (GUI_DIR / name).read_text(encoding="utf-8")
        assert not re.search(r"QTableWidget\w*\(|import[^\n]*QTableWidget", text)


def _select(view: QTableView, r0: int, c0: int, r1: int, c1: int) -> None:
    from PySide6.QtCore import QItemSelection, QItemSelectionModel

    top, bottom = view.model().index(r0, c0), view.model().index(r1, c1)
    view.selectionModel().select(
        QItemSelection(top, bottom), QItemSelectionModel.SelectionFlag.Select
    )


def test_copy_tsv_copies_selected_cells_in_the_order_shown(theme, qtbot, qapp) -> None:
    view = TableView(wire_model(theme), theme, name="Wires")
    qtbot.addWidget(view)
    view.show()
    view.sortByColumn(0, Qt.SortOrder.AscendingOrder)  # W2, W3, W4, W10, W11
    _select(view, 0, 0, 1, 1)
    assert copy_tsv(view) == "W2\tTX-\nW3\t28V"
    assert qapp.clipboard().text() == "W2\tTX-\nW3\t28V"
    assert copy_tsv(view, headers=True, clipboard=False).splitlines()[0] == "Wire\tSignal"
    view.selectionModel().clear()
    _select(view, 0, 4, 1, 5)
    assert copy_tsv(view, headers=True).splitlines()[0] == "Gauge (AWG)\tLength (m)"
    view.selectionModel().clear()
    assert copy_tsv(view) == ""


def test_ctrl_c_copies_the_selection_and_ctrl_shift_c_adds_headers(theme, qtbot, qapp) -> None:
    view = TableView(wire_model(theme), theme, name="Wires")
    qtbot.addWidget(view)
    view.show()
    view.activateWindow()
    view.setFocus()
    qtbot.waitUntil(lambda: view.hasFocus())
    _select(view, 0, 0, 0, 2)
    qapp.clipboard().setText("before")
    QTest.keyClick(view, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert qapp.clipboard().text() == "W10\tTX+\tJ2.1"
    QTest.keyClick(
        view,
        Qt.Key.Key_C,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert qapp.clipboard().text().splitlines() == ["Wire\tSignal\tFrom", "W10\tTX+\tJ2.1"]


def test_copy_follows_moved_and_hidden_columns_and_cleans_tabs(theme, qtbot) -> None:
    rows = [{"a": "x\ty", "b": "line1\nline2", "c": "z"}]
    cols = [Column("a", "A"), Column("b", "B"), Column("c", "C")]
    view = TableView(DictTableModel(cols, rows, theme), theme, name="T")
    qtbot.addWidget(view)
    view.show()
    view.horizontalHeader().moveSection(2, 0)  # C, A, B
    _select(view, 0, 0, 0, 2)
    assert copy_tsv(view, clipboard=False) == "z\tx y\tline1 line2"
    view.setColumnHidden(1, True)  # B
    assert copy_tsv(view, clipboard=False) == "z\tx y"


def test_ragged_selection_leaves_gaps_empty(theme, qtbot) -> None:
    view = TableView(wire_model(theme), theme, name="Wires")
    qtbot.addWidget(view)
    view.show()
    view.sortByColumn(0, Qt.SortOrder.AscendingOrder)
    from PySide6.QtCore import QItemSelectionModel

    sm = view.selectionModel()
    sm.select(view.model().index(0, 0), QItemSelectionModel.SelectionFlag.Select)
    sm.select(view.model().index(1, 1), QItemSelectionModel.SelectionFlag.Select)
    assert copy_tsv(view, clipboard=False) == "W2\t\n\t28V"


def _wait_saved(qtbot, settings: QSettings, key: str) -> None:
    qtbot.waitUntil(lambda: settings.contains(f"tables/{key}/widths"), timeout=2000)


def test_column_widths_and_sort_order_are_saved_and_restored(theme, qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    v1 = TableView(wire_model(theme), theme, name="Wires", settings=settings, key="wires")
    qtbot.addWidget(v1)
    v1.show()
    QTest.qWait(20)
    assert not settings.contains("tables/wires/widths")  # sizing by the program saves nothing
    v1.horizontalHeader().resizeSection(1, 211)  # the person drags a column
    v1.sortByColumn(5, Qt.SortOrder.DescendingOrder)
    _wait_saved(qtbot, settings, "wires")
    v2 = TableView(wire_model(theme), theme, name="Wires", settings=settings, key="wires")
    qtbot.addWidget(v2)
    v2.show()
    assert v2.horizontalHeader().sectionSize(1) == 211
    assert v2.horizontalHeader().sortIndicatorSection() == 5
    assert v2.horizontalHeader().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder


def test_saved_widths_for_another_column_count_are_ignored(theme, qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    settings.setValue("tables/wires/widths", "10,20")
    view = TableView(wire_model(theme), theme, name="Wires", settings=settings, key="wires")
    qtbot.addWidget(view)
    assert view.horizontalHeader().sectionSize(0) > 20
    settings.setValue("tables/wires/widths", "a,b,c,d,e,f,g")
    view2 = TableView(wire_model(theme), theme, name="Wires", settings=settings, key="wires")
    qtbot.addWidget(view2)
    assert view2.horizontalHeader().sectionSize(0) > 20


def test_persist_widths_waits_for_a_model_that_fills_later(theme, qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "t.ini"), QSettings.Format.IniFormat)
    settings.setValue("tables/late/widths", "50,60,70,80,90,100,110")
    view = QTableView()
    qtbot.addWidget(view)
    model = DictTableModel([], [], theme)
    view.setModel(model)
    helper = persist_widths(view, settings, "late")
    assert not helper.restored
    model.beginResetModel()
    model.columns = list(WIRE_COLUMNS)
    model.endResetModel()
    assert helper.restored and view.horizontalHeader().sectionSize(2) == 70


@pytest.mark.perf
def test_big_tables_stay_fast(theme, qtbot) -> None:
    import time

    from tests.helpers import time_limit

    rows = [{"id": f"W{i}", "signal": "s", "gauge": i % 30, "state": "pending" if i % 7 == 0 else None}
            for i in range(5000)]  # fmt: skip
    cols = [Column("id", "Wire", mono=True), Column("signal", "Signal"),
            Column("gauge", "Gauge", numeric=True, state="state")]  # fmt: skip
    view = TableView(DictTableModel(cols, [], theme), theme, name="Big")
    qtbot.addWidget(view)
    view.show()
    t0 = time.perf_counter()
    view.set_rows(rows)
    view.sortByColumn(2, Qt.SortOrder.DescendingOrder)
    view.proxy.set_text("w49")
    assert time.perf_counter() - t0 < time_limit(2.0)


# ---- the host --------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["light", "dark"])
def test_host_renders_in_both_themes(qapp, theme, qtbot, name) -> None:
    theme.apply(qapp, name)
    host = UxHost(theme)
    qtbot.addWidget(host)
    host.resize(1100, 520)
    host.show()
    assert set(host.gallery) == set(icons.ICON_NAMES) and set(host.chips) == set(STATES)
    img = host.grab().toImage()
    assert img.width() == 1100
    assert {b.height() for b in host.buttons} == {theme.control_height()}
    unnamed = [
        w
        for w in host.findChildren(QAbstractButton)
        if w.isVisibleTo(host) and not w.accessibleName() and not w.text()
    ]
    assert unnamed == []
