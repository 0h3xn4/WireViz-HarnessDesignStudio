# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""M4: the Releases tab names the last commit of the repository around the project folder."""

import shutil
from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.releases_panel import ReleasesPanel  # noqa: E402
from tests.test_accessibility import unnamed  # noqa: E402
from tests.test_gitinfo import git, repo  # noqa: E402
from tests.ux_rel import flatsat_controller, settings, themed  # noqa: E402


def make_panel(qtbot, ctl, tmp_path: Path) -> ReleasesPanel:
    panel = ReleasesPanel(ctl, themed(), settings=settings(tmp_path))
    qtbot.addWidget(panel)
    panel.resize(1100, 700)
    panel.show()
    return panel


def test_a_folder_that_is_not_a_repository_shows_no_line(qtbot, tmp_path: Path) -> None:
    themed()
    ctl = flatsat_controller(tmp_path)
    ctl.root = tmp_path
    panel = make_panel(qtbot, ctl, tmp_path)
    assert not panel.author.isVisible()


@pytest.mark.skipif(shutil.which("git") is None, reason="needs the git program")
def test_the_last_commit_is_named(qtbot, tmp_path: Path) -> None:
    themed()
    folder = tmp_path / "work"
    folder.mkdir()
    repo(folder, 2)
    ctl = flatsat_controller(tmp_path / "ctl")
    ctl.root = folder
    panel = make_panel(qtbot, ctl, tmp_path)
    assert panel.author.isVisible()
    text = panel.author.text()
    assert "Ada Lovelace" in text and "Change number 1" in text
    assert git(folder, "rev-parse", "HEAD")[:7] in text and "branch main" in text
    assert "example.org" not in text
    assert panel.author.accessibleName() == strings.REL_AUTHOR_NAME
    assert panel.author.toolTip() == strings.REL_AUTHOR_TIP
    assert unnamed(panel) == []
