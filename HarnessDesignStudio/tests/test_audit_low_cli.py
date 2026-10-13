"""Low findings of the audit in change control, the command line and the importers (E-15, E-17,
K-11, K-17)."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import edit, templates
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.model import ChangeEntry, Project, evolve
from harness_design_studio.core.samples import sat15_full
from harness_design_studio.core.templates import TemplateError
from harness_design_studio.core.vcs.release import plan_new_revision, plan_submit_review

ROOT = Path(__file__).resolve().parents[1]
_BASE: Project | None = None


def _project() -> Project:
    global _BASE
    if _BASE is None:
        _BASE = sat15_full()
    return edit.clone_with(_BASE, [])


def _draft(p: Project) -> str:
    return next(h.id for h in sorted(p.harnesses.values(), key=lambda x: x.id) if h.wires)


def _with_entry(p: Project, hid: str, when: str) -> None:
    h = p.harnesses[hid]
    p.changelog["C0001"] = ChangeEntry(
        id="C0001", harness_id=hid, revision=h.revision, kind="review", by="Ada", when=when
    )


# ---- E-15: a step cannot be dated before the step it follows -----------------------------------


def test_a_review_dated_before_the_last_entry_of_the_harness_is_refused() -> None:
    p = _project()
    hid = _draft(p)
    _with_entry(p, hid, "2026-05-01")
    plan = plan_submit_review(p, hid, by="Ada", when="2026-04-30")
    assert [b.code for b in plan.blockers] == ["date_before_last"]
    assert plan.blockers[0].about == "date" and "2026-05-01" in plan.blockers[0].message


def test_the_same_day_or_a_later_day_is_accepted() -> None:
    p = _project()
    hid = _draft(p)
    _with_entry(p, hid, "2026-05-01")
    assert not plan_submit_review(p, hid, by="Ada", when="2026-05-01").blockers
    assert not plan_submit_review(p, hid, by="Ada", when="2026-05-02").blockers


def test_the_entries_of_other_harnesses_do_not_count() -> None:
    p = _project()
    hid = _draft(p)
    other = next(h for h in p.harnesses if h != hid)
    _with_entry(p, other, "2027-01-01")
    assert not plan_submit_review(p, hid, by="Ada", when="2026-04-30").blockers


def test_a_new_revision_dated_before_the_release_is_refused() -> None:
    p = _project()
    hid = _draft(p)
    _with_entry(p, hid, "2026-05-01")
    p.harnesses[hid] = evolve(p.harnesses[hid], status="released")
    plan = plan_new_revision(p, hid, by="Ada", comment="Rework for the build", when="2026-01-01")
    assert "date_before_last" in {b.code for b in plan.blockers}


def test_an_empty_date_is_a_mistake_not_today(capsys: pytest.CaptureFixture[str]) -> None:
    p = _project()
    hid = _draft(p)
    assert {b.code for b in plan_submit_review(p, hid, by="Ada", when="").blockers} == {"bad_date"}


# ---- E-17: project names and targets ----------------------------------------------------------


@pytest.mark.parametrize("name", ["", "  "])
def test_a_blank_project_name_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], name: str
) -> None:
    rc = cli_main(["new", str(tmp_path / "p"), "--name", name])
    cap = capsys.readouterr()
    assert rc == 2 and "name" in cap.err and not (tmp_path / "p").exists()


def test_a_project_name_is_stored_without_surrounding_spaces(tmp_path: Path) -> None:
    assert cli_main(["new", str(tmp_path / "p"), "--name", "  My design "]) == 0
    assert load_project(tmp_path / "p").project.meta.name == "My design"


def test_a_link_is_not_a_place_for_a_new_project(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "dangling").symlink_to(tmp_path / "nowhere")
    (tmp_path / "empty").mkdir()
    (tmp_path / "to-empty").symlink_to(tmp_path / "empty", target_is_directory=True)
    for name in ("dangling", "to-empty"):
        with pytest.raises(TemplateError, match="not an empty folder"):
            templates.create_project(tmp_path / name, "blank")
    assert not any((tmp_path / "empty").iterdir())


def test_the_exit_code_table_names_what_else_returns_1() -> None:
    text = (ROOT / "docs" / "CLI.md").read_text(encoding="utf-8")
    row = next(line for line in text.splitlines() if line.startswith("| 1 |"))
    assert "import" in row and "config" in row


# ---- K-11: the segment-length columns are read by position -------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        ROOT / "docs" / "IMPORTS.md",
        ROOT
        / "src"
        / "harness_design_studio"
        / "resources"
        / "examples"
        / "templates"
        / "README.md",
    ],
)
def test_the_docs_say_that_import_lengths_reads_columns_by_position(path: Path) -> None:
    text = " ".join(path.read_text(encoding="utf-8").split())
    assert "by position" in text


def test_the_help_of_import_lengths_says_columns_are_by_position(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli_main(["import-lengths", "--help"]) == 0
    assert "by position" in " ".join(capsys.readouterr().out.split())


# ---- K-17: the helper file of the lock is documented -------------------------------------------


def test_the_lock_helper_file_is_documented() -> None:
    for name in ("FILE_FORMAT.md", "TROUBLESHOOTING.md"):
        assert ".harness.lock.takeover" in (ROOT / "docs" / name).read_text(encoding="utf-8")
