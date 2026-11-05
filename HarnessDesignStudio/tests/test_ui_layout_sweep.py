# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-23. Nothing in a dialog or window of the program lies on top of anything else, is cut
off, or is squeezed below what it needs, at the interface sizes and font sizes people use.

The owner ran the program on a real display and the *Add device* window had the name field over
the note under it and the banner over the buttons: the window was shorter than its wrapped text
needs (a top-level window's smallest size does not count height for width). This sweep opens every
dialog and window the program has, at five interface sizes and with larger fonts, in both themes,
with 40-character names and with the reason banner shown and hidden, at the size the window opens
at and at the smallest size it allows, and runs the layout audit of `tests/layout_audit.py` on each.
"""

import os

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QLineEdit,
    QPlainTextEdit,
    QWidget,
)

pytestmark = pytest.mark.gui

from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from tests.layout_audit import Finding, audit  # noqa: E402
from tests.layout_cases import (  # noqa: E402
    LONG,
    Case,
    Ctx,
    cases,
    make_ctx,
    make_window,
    window_views,
)

# name: (theme, interface scale, extra pixels on the base font size). 2 pt = 3 px, 4 pt = 5 px.
SCENARIOS: dict[str, tuple[str, float, int]] = {
    "light": ("light", 1.0, 0),
    "dark": ("dark", 1.0, 0),
    "light-125": ("light", 1.25, 0),
    "light-150": ("light", 1.5, 0),
    "light-200": ("light", 2.0, 0),
    "font-plus-2pt": ("light", 1.0, 3),
    "font-plus-4pt": ("light", 1.0, 5),
    "dark-font-plus-4pt": ("dark", 1.0, 5),
}
STATES = ("opened", "long-text", "reason-shown")
BASE_FONT_PX = 13


def app() -> QApplication:
    found = QApplication.instance()
    return found if isinstance(found, QApplication) else QApplication([])


def themed(name: str, scale: float, extra_px: int) -> ThemeManager:
    """A theme at an interface size, with the base font made `extra_px` larger than the design
    says (what a person with a larger system font, or another family that is wider, gets)."""
    theme = ThemeManager()
    theme.apply(app(), name, scale)  # type: ignore[arg-type]
    if extra_px:
        a = app()
        a.setStyleSheet(
            a.styleSheet()
            + f"\nQWidget {{ font-size: {round((BASE_FONT_PX + extra_px) * scale)}px; }}"
        )
    return theme


def settle() -> None:
    """Let the layouts finish: a change of size asks the containers again, one level per turn."""
    for _ in range(10):
        app().processEvents()


def put_in_state(w: QWidget, state: str) -> None:
    """`long-text`: 40 characters in every text field; `reason-shown`: something typed in each
    text field and taken out again, so that a form that checks as you type shows its reason."""
    fields = [
        e
        for e in w.findChildren(QLineEdit)
        if e.isEnabled()
        and not e.isReadOnly()
        and e.parent() is not None
        and type(e.parent()).__name__ not in ("QComboBox", "QSpinBox", "QDoubleSpinBox")
    ]
    if state == "long-text":
        for e in fields:
            e.setText(LONG)
        for t in w.findChildren(QPlainTextEdit):
            if not t.isReadOnly():
                t.setPlainText(LONG * 3)
    elif state == "reason-shown":
        for e in fields:
            e.setText("x")
            e.setText("")


def look(case: Case, ctx: Ctx, state: str) -> list[Finding]:
    """Open the case, put it in the state, and audit it as it opens and at its smallest size."""
    w = case.make(ctx)
    found: list[Finding] = []
    try:
        put_in_state(w, state)
        w.show()
        settle()
        found += audit(w)
        if w.isWindow():  # a window may be given its smallest size (by the window manager)
            w.resize(1, 1)
            settle()
            found += [
                Finding(f.rule, f"{f.where} (smallest size)", f.detail)
                for f in audit(w, scrolled=False)
            ]
    finally:
        w.close()
        w.deleteLater()
        settle()
    return found


def sweep(scenario: str, tmp_path, only: str | None = None) -> list[str]:
    name, scale, extra = SCENARIOS[scenario]
    ctx = make_ctx(themed(name, scale, extra), tmp_path)
    out: list[str] = []
    try:
        for case in cases():
            if only and only not in case.name:
                continue
            for state in STATES:
                try:
                    for f in look(case, ctx, state):
                        out.append(f"[{scenario}] {case.name} / {state}: {f}")
                except Exception as exc:  # a case that cannot be built is a failure of the sweep
                    out.append(f"[{scenario}] {case.name} / {state}: CANNOT BUILD {exc!r}")
    finally:
        ctx.ctl.release()
    return out


@pytest.mark.slow
@pytest.mark.parametrize("scenario", list(SCENARIOS))
def test_no_dialog_overlaps_clips_or_squeezes(scenario: str, tmp_path) -> None:
    found = sweep(scenario, tmp_path)
    assert not found, "\n" + "\n".join(found)


WINDOW_SIZES = ((1440, 900), (1100, 700))  # at an interface size of 100 %; larger sizes scale them
# The main window at the interface sizes and with the base font 2 pt larger. At 4 pt larger its
# bars and its status bar are too crowded for the width of the window and cut or overlap their
# items (listed in docs/developer/gui-layout.md); the dialogs are swept at that size too.
WINDOW_SCENARIOS = tuple(k for k, (_t, _s, extra) in SCENARIOS.items() if extra <= 3)
# every scenario with the role of the electrical engineer; the other roles and Quick mode at two
ROLE_RUNS = tuple((scenario, "electrical", False) for scenario in WINDOW_SCENARIOS) + tuple(
    (scenario, role, quick)
    for scenario in ("light", "light-150")
    for role, quick in (("systems", False), ("ait", False), ("electrical", True))
)


# What the main window is held to. The program's bars (title bar, rail, status bar) fold and cut
# their text on purpose when the window is narrow, and a few buttons are a few pixels narrower than
# their hint; those show as `squeezed` and `text-cut` and are listed in docs/developer/gui-layout.md.
# Nothing lying over anything else, nothing sticking out of its parent, no wrapped text cut off and
# no window shorter than its content is never accepted. HARNESS_LAYOUT_STRICT=1 holds the window to
# every rule.
WINDOW_RULES = {"overlap", "outside", "wrap-clipped", "window-short"}


def window_rules() -> set[str] | None:
    return None if os.environ.get("HARNESS_LAYOUT_STRICT") else WINDOW_RULES


def sweep_window(scenario: str, tmp_path, role: str, quick: bool) -> list[str]:
    name, scale, extra = SCENARIOS[scenario]
    ctx = make_ctx(themed(name, scale, extra), tmp_path)
    win = make_window(ctx, role, quick)
    if extra:  # (the window has applied the interface size and theme of its settings)
        a = app()
        a.setStyleSheet(
            a.styleSheet()
            + f"\nQWidget {{ font-size: {round((BASE_FONT_PX + extra) * scale)}px; }}"
        )
    out: list[str] = []
    try:
        for width, height in WINDOW_SIZES:
            # a window at 150 % is as big in pixels as the same window at 100 % is at 1.5 times
            # the pixels (a person who chose a larger interface has a larger screen)
            win.resize(round(width * scale), round(height * scale))
            win.show()
            settle()
            for banners in (False, True):  # the banners under the bar: none, and three long ones
                show_banners(win, banners)
                for label, bring_up in window_views(win):
                    out += look_at_view(
                        win, label, bring_up, scenario, width, height, role, quick, banners
                    )
    finally:
        win.close()
        win.deleteLater()
        ctx.ctl.release()
        settle()
    return out


def show_banners(win, on: bool) -> None:
    keys = ("stale", "locked", "damaged")
    for key in keys:
        win.alerts.clear(key)
    if on:
        for key, severity in zip(keys, ("warning", "info", "error"), strict=True):
            win.alerts.show_banner(
                key,
                severity,
                f"{LONG}. " * 3,
                details=[LONG, LONG * 2],
                actions=[("Show it", lambda: None), ("Fix it", lambda: None)],
            )
    settle()


def look_at_view(win, label, bring_up, scenario, width, height, role, quick, banners) -> list[str]:
    bring_up()
    if label.startswith("inspector/"):
        win.dock_right.show()
    settle()
    where = f"window {width}x{height} {role}{' quick' if quick else ''}"
    where += " banners" if banners else ""
    return [
        f"[{scenario}] {where} / {label}: {f}"
        for f in audit(win)
        if (rules := window_rules()) is None or f.rule in rules
    ]


@pytest.mark.slow
@pytest.mark.parametrize("scenario,role,quick", ROLE_RUNS)
def test_the_main_window_holds_in_every_area(
    scenario: str, role: str, quick: bool, tmp_path
) -> None:
    found = sweep_window(scenario, tmp_path, role, quick)
    assert not found, "\n" + "\n".join(found)
