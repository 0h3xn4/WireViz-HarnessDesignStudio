"""UI overhaul M3: the workflow steps (Generate, Check, Release) over every combination of facts."""

import itertools

from harness_design_studio.gui.workflow import KEYS, WorkflowInputs, workflow


def states(**kw: object) -> tuple[str, str, str]:
    g, r, rel = workflow(WorkflowInputs(**kw))  # type: ignore[arg-type]
    return g.state, r.state, rel.state


def test_nothing_done_yet() -> None:
    assert states() == ("todo", "blocked", "blocked")


def test_a_full_journey_in_order() -> None:
    assert states(generation="current") == ("done", "todo", "blocked")
    assert states(generation="current", harnesses=3) == ("done", "todo", "blocked")
    assert states(generation="current", harnesses=3, checked=True) == ("done", "done", "todo")
    assert states(generation="current", harnesses=3, checked=True, released=2) == (
        "done",
        "done",
        "todo",
    )
    assert states(generation="current", harnesses=3, checked=True, released=3) == (
        "done",
        "done",
        "done",
    )


def test_attention_and_running_states() -> None:
    assert states(generation="stale", harnesses=3, checked=True)[0] == "attention"
    assert states(generation="current", harnesses=3, checked=True, failed=2) == (
        "done",
        "attention",
        "blocked",
    )
    assert states(generation="current", checking=True)[1] == "running"
    assert states(generation="current", running="generate")[0] == "running"
    # a stale design cannot be released even when every rule passed on the old plans
    assert states(generation="stale", harnesses=3, checked=True)[2] == "blocked"


def test_a_read_only_project_blocks_what_changes_it() -> None:
    assert states(generation="current", harnesses=2, checked=True, read_only=True) == (
        "done",
        "done",
        "blocked",
    )
    assert states(generation="none", read_only=True)[0] == "blocked"


def test_every_combination_gives_three_named_steps_with_a_detail() -> None:
    for gen, run, chk, checked, failed, har, rel, ro in itertools.product(
        ("none", "current", "stale"), (None, "generate", "export"), (False, True), (False, True),
        (0, 2), (0, 3), (0, 3), (False, True),
    ):  # fmt: skip
        if rel > har:
            continue
        steps = workflow(WorkflowInputs(gen, run, chk, checked, failed, 1, har, 0, rel, ro))
        assert tuple(s.key for s in steps) == KEYS
        for s in steps:
            assert (
                s.label
                and s.detail
                and s.state in ("todo", "attention", "done", "running", "blocked")
            )
            assert s.tooltip.startswith(s.label)
        # (released harnesses count as released even if the generation record is gone)
        assert not (steps[2].state == "todo" and (gen != "current" or failed or not checked))
