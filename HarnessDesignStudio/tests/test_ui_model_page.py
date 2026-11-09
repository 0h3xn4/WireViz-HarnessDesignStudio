# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""REQ-GUI-10. The Explain window and the Why tab name the page of the documentation that describes
the model behind a derivation: a quiet line "Model page: docs/models/wire-sizing.md", as text (nothing
is opened, no network)."""

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from harness_design_studio.core import templates  # noqa: E402
from harness_design_studio.core.derive import (  # noqa: E402
    EXPLAINABLE_RULES,
    Derivation,
    explain_finding,
    explain_object,
    render,
)
from harness_design_studio.core.derive_kinds import KINDS, page_of_rule  # noqa: E402
from harness_design_studio.core.io.loader import load_project  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.controller import EditorController  # noqa: E402
from harness_design_studio.gui.explain_dialog import (  # noqa: E402
    ExplainDialog,
    model_page_line,
    render_with_page,
)
from harness_design_studio.gui.theme import ThemeManager  # noqa: E402
from harness_design_studio.gui.why_panel import WhyPanel  # noqa: E402

MODELS = Path(__file__).resolve().parents[1] / "docs" / "models"


@pytest.fixture
def theme(qapp):
    th = ThemeManager()
    th.apply(qapp, "light", 1.0)
    yield th
    ThemeManager().apply(qapp, "light", 1.0)


@pytest.fixture
def ctl(qapp, tmp_path: Path) -> Iterator[EditorController]:
    c = EditorController(journal_delay_ms=10_000, drc_delay_ms=600_000)
    templates.create_project(tmp_path / "flat", "flatsat")
    c._install(load_project(tmp_path / "flat").project, None, None)
    yield c
    c.release()


def derivation(kind: str) -> Derivation:
    return Derivation(
        id=kind, subject="Wire W001-001", quantity="x", value=1.0, unit="", equation="a"
    )


def test_every_kind_of_derivation_names_a_page_that_exists() -> None:
    assert len(KINDS) >= 20
    for kind, (page, _what) in KINDS.items():
        line = model_page_line(derivation(kind))
        assert line == f"Model page: docs/models/{page}" == strings.EXPLAIN_MODEL_PAGE.format(page)
        assert (MODELS / page).is_file(), kind


def test_a_kind_the_tool_does_not_list_has_no_line_and_no_error() -> None:
    assert model_page_line(derivation("rule-of-an-extension")) == ""
    d = derivation("rule-of-an-extension")
    assert render_with_page(d) == render(d)


def test_the_explain_window_ends_each_calculation_with_its_model_page(ctl, theme, qtbot) -> None:
    wire = ctl.project.harnesses["W001"].wires[0].id
    found = explain_finding(ctl.project, "current-over-wire", str(wire))
    assert found
    dlg = ExplainDialog(None, theme, found)
    qtbot.addWidget(dlg)
    text = dlg.text.toPlainText()
    assert text.endswith("\nModel page: docs/models/wire-sizing.md")
    assert text == "\n\n".join(
        render(d) + "\nModel page: docs/models/wire-sizing.md" for d in found
    )
    assert dlg.text.isReadOnly()  # (selectable text: nothing to click)
    assert "http" not in text and "://" not in text
    both = ExplainDialog(
        None, theme, found + explain_finding(ctl.project, "voltage-drop", str(wire))
    )
    qtbot.addWidget(both)
    assert both.text.toPlainText().count("Model page: docs/models/wire-sizing.md") >= 2
    nothing = ExplainDialog(None, theme, [])
    qtbot.addWidget(nothing)
    assert nothing.text.toPlainText() == strings.EXPLAIN_NOTHING  # (no line without a calculation)


def test_every_rule_of_the_tool_opens_an_explanation_that_names_its_page() -> None:
    for rule in sorted(EXPLAINABLE_RULES):
        page = page_of_rule(rule)
        assert (MODELS / page).is_file(), rule


def make(ctl, theme, qtbot) -> WhyPanel:
    panel = WhyPanel(ctl, theme)
    qtbot.addWidget(panel)
    panel.resize(380, 700)
    panel.show()
    QApplication.processEvents()
    return panel


def notes(panel: WhyPanel) -> list[QLabel]:
    return [lab for lab in panel.findChildren(QLabel) if lab.objectName() == "why-model-page"]


def test_the_why_tab_shows_the_page_under_the_calculation_only_when_it_is_open(
    ctl, theme, qtbot
) -> None:
    wid = str(ctl.project.harnesses["W001"].wires[0].id)
    panel = make(ctl, theme, qtbot)
    panel.show_object("wire", wid)
    assert notes(panel) == []  # (closed: the panel stays short)
    assert panel.explain_button is not None
    panel.explain_button.click()
    QApplication.processEvents()
    shown = notes(panel)
    derivations = explain_object(ctl.project, wid)
    assert [n.text() for n in shown] == [model_page_line(d) for d in derivations]
    assert all(n.text().startswith("Model page: docs/models/") for n in shown)
    assert all(n.text().endswith(".md") for n in shown)
    for n in shown:
        assert n.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
        assert not n.openExternalLinks() and "<a " not in n.text()
        assert n.property("muted") is True  # (a quiet line, not a heading)
    # the text of the calculation itself is as the command prints it
    assert [t.text() for t in panel.explain_texts] == [render(d) for d in derivations]
    panel.explain_button.click()
    assert notes(panel) == []
