# mypy: disable-error-code="no-untyped-def,no-untyped-call,arg-type,operator,var-annotated"
"""1.7.0 S1 (D-171): the one next step of the simple workspace, over every combination of facts.
No Qt, no display."""

import itertools
from dataclasses import replace

from harness_design_studio.gui import next_step as ns
from harness_design_studio.gui import strings
from harness_design_studio.gui.next_step import NextInputs, next_step

BANNED = (
    "interface type",
    "interface",
    "configuration",
    "placeholder",
    "model hash",
    "values pending",
    "drc",
    "rule",
    "generation",
)

# a project at the point where only the release is left
RELEASABLE = NextInputs(
    units=3, interfaces=2, harnesses=2, hand_made_harnesses=0, generation="current",
    checked=True, outputs="current", released=0,
)  # fmt: skip


def key(**kw: object) -> str:
    return next_step(NextInputs(**kw)).key  # type: ignore[arg-type]


def states(n: ns.Next) -> list[str]:
    return [s.state for s in n.steps]


def test_each_rule_in_the_order_of_the_work() -> None:
    assert key() == "add_device"
    assert key(units=1) == "connect"
    assert key(units=2, interfaces=1) == "generate"
    assert key(units=2, interfaces=1, harnesses=1, generation="current") == "check"
    assert key(units=2, interfaces=1, harnesses=1, generation="current", checked=True) == "build_sheets"  # fmt: skip
    f = replace(RELEASABLE)
    assert next_step(f).key == "release"
    assert next_step(replace(f, released=2)).key == "done"
    assert next_step(replace(f, failed=3)).key == "fix"


def test_a_job_that_runs_comes_before_everything() -> None:
    for f in (NextInputs(), RELEASABLE, replace(RELEASABLE, read_only=True)):
        n = next_step(replace(f, running="generate"))
        assert n.key == "busy" and n.title == "Working…" and n.button == ""


def test_a_read_only_project_offers_no_edit() -> None:
    for f in (NextInputs(), RELEASABLE, replace(RELEASABLE, failed=1)):
        n = next_step(replace(f, read_only=True))
        assert n.key == "read_only" and n.button == "" and n.alternative == ""
        assert "newer version" in n.why or "another window" in n.why
        assert "blocked" in states(n) and "next" not in states(n)
    # what was reached is still shown as done
    done = states(next_step(replace(RELEASABLE, read_only=True)))
    assert done[:5] == ["done"] * 5 and done[5] == "blocked"


def test_the_first_step_offers_a_harness_by_hand() -> None:
    n = next_step(NextInputs())
    assert (n.title, n.button) == ("Start with a device", "Add a device")
    assert n.alternative == "or make a harness by hand"
    assert n.alternative_key == "new_harness" and n.alternative_button == "New harness…"
    assert next_step(NextInputs(units=1)).alternative == ""


def test_a_harness_made_by_hand_skips_connecting_and_generating() -> None:
    by_hand = NextInputs(harnesses=1, hand_made_harnesses=1)
    assert next_step(by_hand).key == "check"
    assert states(next_step(by_hand)) == ["done", "done", "done", "next", "todo", "todo"]
    # whatever the state of the generation record is
    for generation in ("none", "current", "stale"):
        assert key(harnesses=2, hand_made_harnesses=2, generation=generation) == "check"
    # one harness that Generate made brings the step back
    assert key(units=2, interfaces=1, harnesses=2, hand_made_harnesses=1) == "generate"
    assert key(harnesses=2, hand_made_harnesses=1, generation="current") == "check"


def test_stale_plans_say_so() -> None:
    f = NextInputs(units=2, interfaces=1, harnesses=2, generation="stale", checked=True)
    n = next_step(f)
    assert n.key == "generate" and "out of date" in n.why
    assert n.button == "Generate the harnesses" and n.title != next_step(replace(f, generation="none")).title  # fmt: skip


def test_failed_checks_are_counted_in_the_sentence() -> None:
    f = replace(RELEASABLE, failed=1)
    assert next_step(f).why.startswith("1 check failed")
    n = next_step(replace(f, failed=4))
    assert n.title == "Fix what is marked" and n.why.startswith("4 checks failed")
    assert n.button == "Show the problems"
    # a failed count means nothing before the check has run
    assert next_step(replace(f, checked=False)).key == "check"


def test_build_sheets_do_not_wait_for_values_that_are_missing() -> None:
    f = replace(RELEASABLE, outputs="none", unchecked=0)
    n = next_step(f)
    assert n.key == "build_sheets" and n.title == "Get the build sheets"
    assert n.button == "Export the build sheets" and n.note == ""
    assert "cut list" in n.why and "connector blocks" in n.why and "test sheet" in n.why
    waiting = next_step(replace(f, unchecked=5))
    assert waiting.key == "build_sheets" and waiting.button == n.button
    assert "engineering values" in waiting.note and "will say so" in waiting.note
    assert next_step(replace(f, has_folder=False)).note == strings.NEXT_SHEETS_FOLDER
    for outputs in ("none", "unsaved", "stale", "modified", "unreadable"):
        assert key(**{**RELEASABLE.__dict__, "outputs": outputs}) == "build_sheets"
    assert key(**RELEASABLE.__dict__) == "release"


def test_release_and_done_buttons() -> None:
    n = next_step(RELEASABLE)
    assert (n.title, n.button) == ("Review and release", "Go to Releases")
    n = next_step(replace(RELEASABLE, released=2))
    assert (n.title, n.button) == ("Everything is released", "Open the Outputs")
    # a harness that is still in review is not released
    assert key(**{**RELEASABLE.__dict__, "released": 1, "in_review": 1}) == "release"


def test_the_steps_follow_the_key() -> None:
    expect = {
        "add_device": ["next", "todo", "todo", "todo", "todo", "todo"],
        "connect": ["done", "next", "todo", "todo", "todo", "todo"],
        "make_harness": ["done", "done", "next", "todo", "todo", "todo"],
        "generate": ["done", "done", "next", "todo", "todo", "todo"],
        "check": ["done", "done", "done", "next", "todo", "todo"],
        "fix": ["done", "done", "done", "next", "todo", "todo"],
        "build_sheets": ["done", "done", "done", "done", "next", "todo"],
        "release": ["done", "done", "done", "done", "done", "next"],
        "done": ["done"] * 6,
    }
    cases = {
        "add_device": NextInputs(),
        "connect": NextInputs(units=2),
        "make_harness": NextInputs(units=2, links=1),
        "generate": NextInputs(units=2, interfaces=1),
        "check": replace(RELEASABLE, checked=False),
        "fix": replace(RELEASABLE, failed=2),
        "build_sheets": replace(RELEASABLE, outputs="stale"),
        "release": RELEASABLE,
        "done": replace(RELEASABLE, released=2),
    }
    for k, f in cases.items():
        n = next_step(f)
        assert n.key == k
        assert states(n) == expect[k], k
        assert len(n.steps) == 6
    labels = [s.label for s in next_step(NextInputs()).steps]
    assert labels == [
        "Add your devices",
        "Connect them",
        "Generate the harnesses",
        "Check the design",
        "Get the build sheets",
        "Review and release",
    ]


def test_a_running_job_keeps_the_steps_of_the_work() -> None:
    busy = next_step(replace(RELEASABLE, running="export", outputs="stale"))
    assert busy.key == "busy"
    assert states(busy) == ["done", "done", "done", "done", "next", "todo"]


def test_only_a_read_only_project_has_blocked_steps() -> None:
    for f in _all_facts():
        n = next_step(f)
        if "blocked" in states(n):
            assert n.key == "read_only", f
        if n.key == "read_only" and ns.stage(f) != "done":
            assert "blocked" in states(n), f


def test_there_is_exactly_one_next_step_unless_all_is_done() -> None:
    for f in _all_facts():
        n = next_step(f)
        if n.key == "read_only":
            continue
        count = states(n).count("next")
        all_done = states(n) == ["done"] * 6  # (also while a job runs on a finished project)
        assert count == (0 if all_done else 1), (f, n.key)
        # earlier steps are done, later steps to do: never a gap
        order = {"done": 0, "next": 1, "todo": 2}
        seq = [order[s] for s in states(n)]
        assert seq == sorted(seq), (f, n.key)


def _all_facts():  # type: ignore[no-untyped-def]
    for (units, interfaces, links, harnesses, hand, generation, running, checked, failed,
         unchecked, outputs, released, read_only, has_folder) in itertools.product(
        (0, 2), (0, 1), (0, 1), (0, 2), (0, 1, 2), ("none", "current", "stale"), (None, "generate"),
        (False, True), (0, 2), (0, 3), ("none", "current", "stale"), (0, 1, 2), (False, True),
        (False, True),
    ):  # fmt: skip
        if hand > harnesses or released > harnesses:
            continue
        yield NextInputs(
            units=units, interfaces=interfaces, links=links, harnesses=harnesses,
            hand_made_harnesses=hand,
            generation=generation, running=running, checked=checked, failed=failed,
            unchecked=unchecked, outputs=outputs, released=released, read_only=read_only,
            has_folder=has_folder,
        )  # fmt: skip


def test_every_combination_gives_a_known_key_with_plain_words() -> None:
    seen = set()
    for f in _all_facts():
        n = next_step(f)
        assert n.key in ns.KEYS
        seen.add(n.key)
        assert n.title.strip() and n.why.strip()
        for text in n.texts:
            low = text.lower()
            for word in BANNED:
                assert word not in low, (word, text)
    assert seen == set(ns.KEYS)


def test_no_text_of_the_page_holds_a_word_that_confuses() -> None:
    texts = [v for k, v in vars(strings).items() if k.startswith("NEXT_") and isinstance(v, str)]
    texts += list(strings.NEXT_BUTTON_TIPS.values())
    assert len(texts) > 40
    for text in texts:
        low = text.lower()
        for word in ("interface type", "configuration", "placeholder", "model hash", "values pending"):  # fmt: skip
            assert word not in low, text


def test_every_key_with_an_action_has_a_button_and_a_tip() -> None:
    for k in ns.KEYS:
        if k in ("busy", "read_only"):
            continue
        assert k in strings.NEXT_BUTTON_TIPS, k
    assert "new_harness" in strings.NEXT_BUTTON_TIPS
    buttons = {}
    for f in _all_facts():
        n = next_step(f)
        buttons.setdefault(n.key, set()).add(n.button)
    for k, names in buttons.items():
        if k in ("busy", "read_only"):
            assert names == {""}, k
        else:
            assert len(names) == 1 and "" not in names, k


def test_the_sentences_are_short_and_plain() -> None:
    for f in _all_facts():
        n = next_step(f)
        for sentence in (n.why, n.note):
            if sentence:
                assert sentence[-1] == "." or sentence[-1] == "…" or n.key == "busy", sentence
                assert len(sentence.split()) <= 20, sentence


def test_the_exact_texts() -> None:
    """The words of the manual: a change here is a change of the documentation."""
    f = NextInputs(units=2, interfaces=1)
    assert (next_step(f).title, next_step(f).why) == (
        "Generate the harnesses",
        "The program makes the harnesses from your connections.",
    )
    assert next_step(NextInputs(units=2)).button == "Connect two devices"
    assert next_step(replace(RELEASABLE, checked=False)).button == "Check the design"


def test_the_workspace_default_depends_on_what_the_settings_file_holds(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(
        ns, "FIRST_RUN_WORKSPACE", "simple"
    )  # (conftest sets Full for the other tests)
    assert ns.default_workspace(False) == ns.FIRST_RUN_WORKSPACE == "simple"
    assert ns.default_workspace(True) == "full"
    assert ns.clean_workspace("simple", "full") == "simple"
    assert ns.clean_workspace("full", "simple") == "full"
    assert ns.clean_workspace("pink", "full") == "full"
    assert ns.clean_workspace(None, "simple") == "simple"
    assert ns.WORKSPACES == ("simple", "full")
