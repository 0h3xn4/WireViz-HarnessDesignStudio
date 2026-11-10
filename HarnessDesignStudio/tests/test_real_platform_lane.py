# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-26. The layout tests do not rely on Qt's offscreen platform alone: a second workflow,
`harness-real-platform.yml`, runs them on Qt's real `xcb` platform under a virtual X display
(`xvfb`) on Ubuntu and on Qt's real `windows` platform on GitHub's Windows runner.

Here: what the lane must keep (the platform it asks for is the platform the tests get, the tests it
runs are the layout tests, it is a job of its own that no required check waits for), and that the
report it prints before the tests works on any platform.
"""

import os
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtWidgets import QApplication  # noqa: E402

from tests import real_platform_report  # noqa: E402

WORKFLOW = (
    Path(__file__).resolve().parents[2] / ".github" / "workflows" / "harness-real-platform.yml"
)
LAYOUT_TESTS = (
    "tests/test_ui_layout_sweep.py",
    "tests/test_ui_dialog_layout.py",
    "tests/test_ui_four_actions.py",
)


def test_the_lane_gets_the_platform_it_asked_for(qapp) -> None:
    """In the lane `HARNESS_REAL_PLATFORM` names the platform (`xcb`, `windows`); a run that
    quietly fell back to offscreen would pass every layout test and prove nothing."""
    asked = os.environ.get("HARNESS_REAL_PLATFORM")
    if not asked:
        pytest.skip("not the real-platform lane (HARNESS_REAL_PLATFORM is not set)")
    app = QApplication.instance()
    assert app is not None and app.platformName() == asked
    screen = app.primaryScreen()
    assert screen is not None and screen.geometry().width() >= 1024  # (a screen a window fits on)


def test_the_report_names_the_platform_the_screen_and_the_fonts(qapp) -> None:
    lines = real_platform_report.report()
    text = "\n".join(lines)
    app = QApplication.instance()
    assert app is not None
    assert f"qt platform: {app.platformName()}" in text
    assert "screen " in text and "dpi" in text
    assert "bundled families loaded:" in text and "Inter" in text and "JetBrains Mono" in text
    assert "fingerprint of those widths:" in text
    assert "characters above ASCII used in gui/strings.py" in text


def test_the_report_reads_the_characters_the_texts_use() -> None:
    chars = real_platform_report.used_characters()
    assert "…" in chars and all(ord(c) > 126 for c in chars)


def lane() -> str:
    if not WORKFLOW.is_file():
        pytest.skip("the repository root is not here")
    return WORKFLOW.read_text(encoding="utf-8")


def test_the_workflow_runs_the_layout_tests_on_both_real_platforms() -> None:
    text = lane()
    assert "QT_QPA_PLATFORM: xcb" in text and "QT_QPA_PLATFORM: windows" in text
    assert "HARNESS_REAL_PLATFORM: xcb" in text and "HARNESS_REAL_PLATFORM: windows" in text
    assert "xvfb-run" in text and "runs-on: ubuntu-24.04" in text and "windows-latest" in text
    # the Qt libraries are the ones the release workflow installs (plus the virtual display)
    release = (WORKFLOW.parent / "release.yml").read_text(encoding="utf-8")
    libs = next(ln for ln in release.splitlines() if "libxcb-xinerama0" in ln)
    assert libs.split("install -y")[1].strip() in text
    assert "xvfb" in text.split("install -y")[1]
    for test in LAYOUT_TESTS:
        assert test in text, test
    assert "python -m tests.real_platform_report" in text


def test_the_lane_is_its_own_workflow_and_not_a_required_gate_yet() -> None:
    """A separate workflow with names of its own, so branch protection can name it later and the
    existing checks (`harness-design-studio CI` and `platforms`) are neither slower nor changed.
    It does not wait for them (no `needs` on another workflow's job exists across workflows)."""
    text = lane()
    assert text.startswith("name: harness-design-studio real platform\n")
    assert "needs:" not in text
    # every job has a time limit that keeps the lane under about 20 minutes of work
    assert text.count("timeout-minutes:") >= text.count("runs-on:") >= 2
    assert "cancel-in-progress" in text  # a newer push replaces the run in progress
