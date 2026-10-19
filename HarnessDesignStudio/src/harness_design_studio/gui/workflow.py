"""The workflow the top bar shows: Generate, then Review (the design rule check), then Release.

No Qt here, so every combination is tested without a display. `workflow(inputs)` returns the three
steps with a state and a short detail:

    todo       the step is next or not done yet
    attention  it was done and something needs you (plans out of date, rules failed)
    done       finished
    running    a job of this step runs now
    blocked    an earlier step has to happen first (or the project is read-only)

The states say the same as the status chip and the banners (they are computed from the same facts:
`ShellStatus`), but in one line and in the order the work goes.
"""

from dataclasses import dataclass
from typing import Final, Literal

from harness_design_studio.gui import strings

State = Literal["todo", "attention", "done", "running", "blocked"]
KEYS: Final = ("generate", "review", "release")


@dataclass(frozen=True)
class WorkflowInputs:
    generation: str = "none"  # none | current | stale
    running: str | None = None  # generate | export | arrange while a job runs
    checking: bool = False  # the rule check runs
    checked: bool = False  # a check result is current
    failed: int = 0  # rules that failed
    unchecked: int = 0  # rules that could not be checked or wait for a value
    harnesses: int = 0
    in_review: int = 0
    released: int = 0
    read_only: bool = False


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    state: State
    detail: str

    @property
    def tooltip(self) -> str:
        return f"{self.label}: {self.detail}"


def workflow(i: WorkflowInputs) -> tuple[Step, Step, Step]:
    return (_generate(i), _review(i), _release(i))


def _generate(i: WorkflowInputs) -> Step:
    label = strings.STEP_GENERATE
    if i.running == "generate":
        return Step("generate", label, "running", strings.STEP_GENERATE_RUNNING)
    if i.read_only:
        state: State = "done" if i.generation == "current" else "blocked"
        return Step("generate", label, state, strings.STEP_READ_ONLY)
    if i.generation == "current":
        return Step("generate", label, "done", strings.STEP_GENERATE_DONE)
    if i.generation == "stale":
        return Step("generate", label, "attention", strings.STEP_GENERATE_STALE)
    return Step("generate", label, "todo", strings.STEP_GENERATE_TODO)


def _review(i: WorkflowInputs) -> Step:
    label = strings.STEP_REVIEW
    if i.checking:
        return Step("review", label, "running", strings.STEP_REVIEW_RUNNING)
    if i.generation == "none":
        return Step("review", label, "blocked", strings.STEP_GENERATE_FIRST)
    if not i.checked:
        return Step("review", label, "todo", strings.STEP_REVIEW_TODO)
    if i.failed:
        return Step("review", label, "attention", strings.STEP_REVIEW_FAILED.format(i.failed))
    detail = strings.STEP_REVIEW_PASSED
    if i.unchecked:
        detail += " " + strings.STEP_REVIEW_UNCHECKED.format(i.unchecked)
    if i.in_review:
        detail += " " + strings.STEP_IN_REVIEW.format(i.in_review)
    return Step("review", label, "done", detail)


def _release(i: WorkflowInputs) -> Step:
    label = strings.STEP_RELEASE
    if i.harnesses and i.released == i.harnesses:
        return Step("release", label, "done", strings.STEP_RELEASE_ALL.format(i.released))
    detail = strings.STEP_RELEASE_COUNT.format(i.released, i.harnesses)
    if i.read_only or i.harnesses == 0 or i.generation == "none":
        return Step(
            "release", label, "blocked", detail if i.harnesses else strings.STEP_GENERATE_FIRST
        )
    if i.generation == "stale" or i.failed or not i.checked:
        return Step("release", label, "blocked", strings.STEP_REVIEW_FIRST + " " + detail)
    return Step("release", label, "todo", detail)
