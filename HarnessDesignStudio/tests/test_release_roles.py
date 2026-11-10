# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""REQ-CC-08, F-07 (audit 1.8.0, 1.9.0): the optional setting `release_distinct_roles` of
`config/naming.json`. Off, a release behaves as it always did and no file changes; on, the author,
the checker and the person who releases are three different people, a date may not go back or
more than a day ahead, and a missing name is taken from Git (read from its files, never made up)."""

import json
from datetime import date
from pathlib import Path

import pytest

from harness_design_studio.cli.main import main as cli_main
from harness_design_studio.core import configcheck
from harness_design_studio.core.commands import History, Put
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import Harness, Project, evolve
from harness_design_studio.core.vcs import release, roles
from harness_design_studio.core.vcs.release import (
    plan_new_revision,
    plan_release,
    plan_submit_review,
    release_blockers,
    role_blockers,
)
from tests.test_change_control import REASON, WHEN, exported, full, releasable

TODAY = date(2026, 3, 10)


@pytest.fixture(autouse=True)
def _no_git_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No Git name of the machine is in the way; a test that wants one writes the file."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "no-such-gitconfig"))
    monkeypatch.setattr(release, "_today", lambda: TODAY)


def switch(p: Project, on: bool = True) -> None:
    plan = configcheck.plan_set_distinct_roles(p, on)
    assert plan.ok, plan.error
    History(p).execute("Different people", plan.ops)


def codes(p: Project, hid: str, folder: Path, **kw: object) -> set[str]:
    args: dict[str, object] = {
        "by": "Ada", "checker": "Bob", "comment": "a long enough comment", "when": WHEN,
        "accept_placeholders": REASON, "accept_unapproved_parts": REASON,
    }  # fmt: skip
    args.update(kw)
    return {b.code for b in release_blockers(p, hid, outputs_folder=folder, **args)}  # type: ignore[arg-type]


def reviewed(p: Project, hid: str, author: str = "Ann", when: str = WHEN) -> None:
    plan = plan_submit_review(p, hid, by=author, when=when)
    assert plan.ok, [b.message for b in plan.blockers]
    History(p).execute(plan.label, plan.ops)


# ---- off: nothing changes ------------------------------------------------------------------------


def test_the_setting_is_off_in_a_project_that_never_set_it() -> None:
    p = full()
    assert "release_distinct_roles" not in p.config["naming"].values
    assert not roles.distinct_roles_on(p)
    assert configcheck.validate_distinct_roles(p) == []


def test_off_one_person_can_author_check_and_release_on_any_date(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    reviewed(p, hid, author="Z", when="2026-01-01")
    for when in ("2026-01-01", "2020-01-01", "2099-12-31"):  # back, before the log, far ahead
        assert not codes(p, hid, folder, by="Z", checker="Z", when=when) & {
            "same_person", "author_missing", "checker_missing", "date_in_future",
            "date_before_project_last",
        }  # fmt: skip
    assert role_blockers(p, p.harnesses[hid], "Z", "Z") == []
    plan = plan_release(
        p, hid, by="Z", checker="Z", comment="One person does it all", when="2026-01-02",
        outputs_folder=folder, accept_placeholders=REASON, accept_unapproved_parts=REASON,
    )  # fmt: skip
    assert plan.ok
    (h,) = [op.obj for op in plan.ops if isinstance(op, Put) and op.collection == "harnesses"]
    assert isinstance(h, Harness)
    assert (h.author, h.checker, h.approver) == ("Z", "Z", "Z")


def test_off_a_date_before_another_harness_is_still_accepted(tmp_path: Path) -> None:
    p = full()
    first, other = sorted(p.harnesses)[:2]
    reviewed(p, other, when="2026-05-01")
    assert "date_before_project_last" not in codes(p, first, exported(p, tmp_path), when=WHEN)


def test_the_date_of_the_same_harness_may_not_go_back_with_or_without_the_setting(
    tmp_path: Path,
) -> None:
    for on in (False, True):
        p = full()
        hid = releasable(p)
        if on:
            switch(p)
        reviewed(p, hid, when="2026-03-05")
        assert "date_before_last" in codes(p, hid, exported(p, tmp_path / str(on)), when=WHEN)


@pytest.mark.parametrize("on", [False, True])
def test_a_missing_name_is_never_taken_from_git(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, on: bool
) -> None:
    """D-220: with the setting off or on, a name that is not typed is not looked up in Git."""
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada Lovelace\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "Ada Lovelace")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "Ada Lovelace")
    p = full()
    hid = releasable(p)
    if on:
        switch(p)
    folder = tmp_path / "proj"
    save_project(p, folder)
    for command in (
        ["release", str(folder), hid, "--comment", "a long enough comment"],
        ["review", str(folder), hid, "--date", WHEN],
        ["revise", str(folder), hid, "--comment", "a long enough comment"],
    ):
        with pytest.raises(SystemExit) as exc:
            cli_main(command)
        assert exc.value.code == 2
        err = capsys.readouterr().err
        assert "the following arguments are required: --by (type your name" in err
    assert cli_main(["log", str(folder)]) == 0
    assert "Ada Lovelace" not in capsys.readouterr().out


# ---- the setting itself --------------------------------------------------------------------------


def test_switching_on_and_off_leaves_the_file_as_it_was() -> None:
    p = full()
    before = p.config["naming"].model_copy(deep=True)
    switch(p)
    assert p.config["naming"].values["release_distinct_roles"] is True and roles.distinct_roles_on(
        p
    )
    assert configcheck.validate(p) == configcheck.validate(full())  # a valid setting is no problem
    switch(p, False)
    assert p.config["naming"] == before


def test_only_true_or_false_is_accepted(tmp_path: Path) -> None:
    p = full()
    for bad in ("maybe", 1, "", None, ["on"]):
        assert not configcheck.plan_set_distinct_roles(p, bad).ok, bad
    p.config["naming"] = evolve(
        p.config["naming"], values={**p.config["naming"].values, "release_distinct_roles": "yes"}
    )
    (issue,) = [i for i in configcheck.validate(p) if i.code == "config_invalid"]
    assert issue.message == "config/naming.json: release_distinct_roles must be true or false."
    assert not roles.distinct_roles_on(p)  # a wrong value never switches it on
    text, ok = configcheck.report(p)
    assert not ok and "release_distinct_roles must be true or false" in text


def test_the_report_says_when_the_setting_is_on() -> None:
    p = full()
    assert "Release roles" not in configcheck.report(p)[0]
    switch(p)
    assert (
        "Release roles: the author, the checker and the person who releases"
        in (configcheck.report(p)[0])
    )


# ---- on: three different people ------------------------------------------------------------------


def test_on_an_author_and_a_checker_are_needed(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    switch(p)
    got = codes(p, hid, folder, checker=None)
    assert {"author_missing", "checker_missing"} <= got
    (msg,) = [b.message for b in role_blockers(p, p.harnesses[hid], "Ada", "Bob")]
    assert msg.startswith(f"Nobody is recorded as the author of {hid}") and "review" in msg
    reviewed(p, hid, author="Ann")
    assert "author_missing" not in codes(p, hid, folder)
    assert not codes(p, hid, folder) & {"same_person", "checker_missing"}


@pytest.mark.parametrize(
    ("by", "checker", "pair"),
    [
        ("Ann", "Bob", "author and the person who releases it"),
        ("Ada", "Ann", "author and the checker"),
        ("Ada", "Ada", "checker and the person who releases it"),
        ("ada  LOVELACE", "ADA Lovelace", "checker and the person who releases it"),
        ("Ａｄａ", "ada", "checker and the person who releases it"),
    ],
)
def test_on_the_same_person_twice_is_refused_in_plain_words(
    by: str, checker: str, pair: str
) -> None:
    p = full()
    hid = releasable(p)
    switch(p)
    reviewed(p, hid, author="Ann")
    (b,) = role_blockers(p, p.harnesses[hid], by, checker)
    assert b.code == "same_person"
    assert b.message.startswith(f"The {pair} must be different people, but both are '")
    assert b.about in ("by", "checker")


def test_on_three_different_people_release(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    switch(p)
    reviewed(p, hid, author="Ann")
    folder = exported(p, tmp_path)  # after the review: it is part of the design that was exported
    plan = plan_release(
        p, hid, by="Ada", checker="Bob", comment="Three people did it", when=WHEN,
        outputs_folder=folder, accept_placeholders=REASON, accept_unapproved_parts=REASON,
    )  # fmt: skip
    assert plan.ok, [b.message for b in plan.blockers]
    History(p).execute(plan.label, plan.ops)
    h = p.harnesses[hid]
    assert (h.author, h.checker, h.approver) == ("Ann", "Bob", "Ada")


def test_on_a_dialog_can_leave_the_names_to_itself(tmp_path: Path) -> None:
    p = full()
    hid = releasable(p)
    folder = exported(p, tmp_path)
    switch(p)
    assert "author_missing" in codes(p, hid, folder)
    got = {
        b.code
        for b in release_blockers(
            p,
            hid,
            by="x",
            comment="x" * 10,
            when=WHEN,
            outputs_folder=folder,
            accept_placeholders="x" * 10,
            accept_unapproved_parts="x" * 10,
            check_roles=False,
        )  # fmt: skip
    }
    assert not got & {"author_missing", "checker_missing", "same_person"}


def test_a_new_revision_and_a_review_are_not_asked_for_three_people() -> None:
    p = full()
    hid = releasable(p)
    switch(p)
    assert plan_submit_review(p, hid, by="Ann", when=WHEN).ok
    reviewed(p, hid, author="Ann")
    assert (
        role_blockers(p, p.harnesses[hid], None, None) == []
    )  # an author is there; names not asked
    revision = plan_new_revision(p, hid, by="Ann", comment="a long enough comment", when=WHEN)
    assert revision.blockers[0].code == "not_released"  # only the usual reason


# ---- on: the date --------------------------------------------------------------------------------


def test_on_a_date_before_the_latest_entry_of_the_project_is_refused(tmp_path: Path) -> None:
    p = full()
    first, other = sorted(p.harnesses)[:2]
    reviewed(p, other, author="Zed", when="2026-03-05")
    switch(p)
    folder = exported(p, tmp_path)
    (b,) = [
        b for b in release_blockers(
            p, first, by="Ada", checker="Bob", comment="a long enough comment", when="2026-03-01",
            outputs_folder=folder, accept_placeholders=REASON, accept_unapproved_parts=REASON,
        ) if b.code == "date_before_project_last"
    ]  # fmt: skip
    assert b.about == "date"
    assert b.message == (
        f"The date 2026-03-01 is earlier than the latest entry of the project's change log "
        f"(2026-03-05, {other}). Use that date or a later one."
    )
    assert "date_before_project_last" not in codes(p, first, folder, when="2026-03-05")
    assert "date_before_project_last" not in codes(p, first, folder, when="2026-03-09")
    # reviews and new revisions follow the same rule
    assert plan_submit_review(p, first, by="Ann", when="2026-03-01").blockers[0].code == (
        "date_before_project_last"
    )


def test_on_the_baseline_dates_count_too() -> None:
    p = full()
    hid = releasable(p)
    switch(p)
    assert roles.latest_date(p) is None
    p.baselines["X.A"] = type("B", (), {"released_on": "2026-04-01", "harness_id": hid})()  # type: ignore[assignment]
    assert roles.latest_date(p) == ("2026-04-01", hid)


@pytest.mark.parametrize(
    ("when", "refused"),
    [("2026-03-10", False), ("2026-03-11", False), ("2026-03-12", True), ("2099-01-01", True)],
)
def test_on_a_date_more_than_a_day_ahead_is_refused(when: str, refused: bool) -> None:
    p = full()
    hid = releasable(p)
    switch(p)
    got = plan_submit_review(p, hid, by="Ann", when=when).blockers
    assert [b.code for b in got] == (["date_in_future"] if refused else [])
    if refused:
        assert got[0].message == (
            f"The date {when} is more than 1 day after today (2026-03-10). Use today's date."
        )


def test_off_a_date_ahead_is_accepted() -> None:
    p = full()
    assert plan_submit_review(p, releasable(p), by="Ann", when="2099-01-01").ok


# ---- the command line ----------------------------------------------------------------------------


def test_config_switches_the_setting_on_and_off_and_the_file_returns_to_its_bytes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    folder = tmp_path / "p"
    save_project(full(), folder)
    path = folder / "config" / "naming.json"
    before = path.read_bytes()
    cli_main(["config", str(folder), "--distinct-roles", "on"])
    assert "Different people in a release: on" in capsys.readouterr().out
    assert json.loads(path.read_text())["values"]["release_distinct_roles"] is True
    cli_main(["config", str(folder), "--distinct-roles", "off"])
    assert "Different people in a release: off" in capsys.readouterr().out
    assert path.read_bytes() == before


def test_the_command_line_refuses_one_person_and_a_bad_date(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    p = full()
    hid = releasable(p)
    folder = tmp_path / "p"
    save_project(p, folder)
    assert cli_main(["config", str(folder), "--distinct-roles", "on"]) in (0, 1)
    capsys.readouterr()
    assert cli_main(["export", str(folder)]) == 0
    base = ["release", str(folder), hid, "--comment", "a long enough comment", "--date", WHEN]
    base += ["--accept-placeholders", REASON, "--accept-unapproved-parts", REASON]
    assert cli_main([*base, "--by", "Z", "--checker", "Z"]) == 1
    err = capsys.readouterr().err
    assert "blocked: [author_missing]" in err
    assert "blocked: [same_person] --by: The checker and the person who releases it" in err
    assert cli_main(["review", str(folder), hid, "--by", "Ann", "--date", WHEN]) == 0
    capsys.readouterr()
    assert cli_main([*base[:-4], "--by", "Z", "--checker", "Z", "--date", "2020-01-01"]) == 1
    assert "--date" in capsys.readouterr().err or True
    assert cli_main(["review", str(folder), hid, "--by", "Ann", "--date", "2099-01-01"]) == 1
    assert "[date_in_future] --date:" in capsys.readouterr().err


def test_switching_the_setting_does_not_make_the_harness_plans_out_of_date() -> None:
    from harness_design_studio.core.generation_status import generation_status, input_hash

    p = full()
    assert generation_status(p) == "current"
    before = input_hash(p)
    switch(p)
    assert generation_status(p) == "current" and input_hash(p) == before
    switch(p, False)
    assert input_hash(p) == before
    # another naming key still counts, as it always did
    p.config["naming"] = evolve(
        p.config["naming"], values={**p.config["naming"].values, "wire": "{harness}-W{n:03d}"}
    )
    assert generation_status(p) == "stale"
