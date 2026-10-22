"""The one next step the simple workspace shows (decision D-171, stage S1).

No Qt here, so every combination is tested without a display. `next_step(facts)` takes the facts
of the project (`NextInputs`) and returns what to do now (`Next`): a short title, one plain
sentence, the text of the one button, and the six steps of the work with where the person is:

    1 Add your devices   2 Connect them   3 Generate the harnesses
    4 Check the design   5 Get the build sheets   6 Review and release

Each step line is `done`, `next`, `todo` or `blocked` (`blocked` only for a read-only project).
The rules run in this order, the first that fits wins:

    busy         a job runs                                   no button
    read_only    the project cannot be changed                no button
    add_device   no devices and no harness                    (or: make a harness by hand)
    connect      no connection and no harness
    generate     no harness, or no plans, or plans out of date (a project whose harnesses were all
                 made by hand skips this step)
    check        the design was not checked
    fix          checks failed
    build_sheets the files are not up to date
    release      a harness is not released
    done         everything is released

The words are plain on purpose: this stage exists because testers found the tool confusing. The
window maps each key to an existing flow (`gui/next_page.py` only shows and calls back).

The workspace setting (Simple or Full) is here too: `default_workspace` says which one a settings
file gets when the person never chose, and `workspace_key` the settings key under which the layout of
a workspace is remembered (stage S2: Full keeps the keys it always had, Simple has keys of its own).
"""

from dataclasses import dataclass
from typing import Final, Literal

from harness_design_studio.gui import strings

StepState = Literal["done", "next", "todo", "blocked"]
WORKSPACES: Final = ("simple", "full")
FIRST_RUN_WORKSPACE: Final = "simple"  # a settings file with no stored values at all (tests set it)
KEYS: Final = (
    "busy",
    "read_only",
    "add_device",
    "connect",
    "generate",
    "check",
    "fix",
    "build_sheets",
    "release",
    "done",
)
STEP_LABELS: Final = (
    strings.NEXT_STEP_ADD,
    strings.NEXT_STEP_CONNECT,
    strings.NEXT_STEP_GENERATE,
    strings.NEXT_STEP_CHECK,
    strings.NEXT_STEP_SHEETS,
    strings.NEXT_STEP_RELEASE,
)
# the index of the step each key is about (6: every step is done)
_STEP_OF: Final = {
    "add_device": 0,
    "connect": 1,
    "generate": 2,
    "check": 3,
    "fix": 3,
    "build_sheets": 4,
    "release": 5,
    "done": 6,
}


@dataclass(frozen=True)
class NextInputs:
    units: int = 0
    interfaces: int = 0
    harnesses: int = 0
    hand_made_harnesses: int = 0  # harnesses a person made (generated=False)
    generation: str = "none"  # none | current | stale
    running: str | None = None  # a job runs: generate | export | arrange
    checked: bool = False  # a rule check result is current
    failed: int = 0  # rules that failed
    unchecked: int = 0  # rules not checked or waiting for a value
    outputs: str = "none"  # none | unsaved | current | stale | modified | unreadable
    in_review: int = 0
    released: int = 0
    read_only: bool = False
    has_folder: bool = True  # the project lives in a folder (the sample does not)


@dataclass(frozen=True)
class StepLine:
    label: str
    state: StepState


@dataclass(frozen=True)
class Next:
    key: str
    title: str
    why: str  # one plain sentence
    button: str  # the text of the one primary action ("" when there is none)
    steps: tuple[StepLine, ...]
    note: str = ""  # an extra plain sentence under the reason ("" when there is none)
    alternative: str = ""  # "or make a harness by hand"
    alternative_key: str = ""
    alternative_button: str = ""

    @property
    def texts(self) -> tuple[str, ...]:
        """Every text of this result (the tests look for words that must not appear)."""
        return (
            self.title,
            self.why,
            self.button,
            self.note,
            self.alternative,
            self.alternative_button,
            *(s.label for s in self.steps),
        )


def default_workspace(has_stored_values: bool) -> str:
    """Simple for a settings file that holds nothing yet; Full for one that does (people who
    already use the editor keep what they have and can switch in the View menu)."""
    return "full" if has_stored_values else FIRST_RUN_WORKSPACE


def clean_workspace(value: object, fallback: str) -> str:
    """A stored value as one of `WORKSPACES` (a hand-edited file may say anything)."""
    text = str(value)
    return text if text in WORKSPACES else fallback


def workspace_key(key: str, workspace: str) -> str:
    """The settings key for a part of the layout that is remembered per workspace. Full keeps the
    key as it is (people who already use the editor lose nothing); Simple gets a key of its own
    next to it: `ui/state` becomes `ui/simple/state`, `layout/ab12/area` `layout/ab12/simple/area`."""
    if workspace != "simple":
        return key
    head, _, tail = key.rpartition("/")
    return f"{head}/simple/{tail}" if head else f"simple/{tail}"


def stage(f: NextInputs) -> str:
    """The key of the first step that is not done, whatever runs and whatever may be edited."""
    if f.units == 0 and f.harnesses == 0:
        return "add_device"
    if f.interfaces == 0 and f.harnesses == 0:
        return "connect"
    by_hand = f.harnesses > 0 and f.hand_made_harnesses == f.harnesses
    if not by_hand and (f.harnesses == 0 or f.generation in ("none", "stale")):
        return "generate"
    if not f.checked:
        return "check"
    if f.failed > 0:
        return "fix"
    if f.outputs != "current":
        return "build_sheets"
    if f.released < f.harnesses:
        return "release"
    return "done"


def _steps(index: int, *, blocked: bool = False) -> tuple[StepLine, ...]:
    lines = []
    for i, label in enumerate(STEP_LABELS):
        state: StepState
        if i < index:
            state = "done"
        elif blocked:
            state = "blocked"
        else:
            state = "next" if i == index else "todo"
        lines.append(StepLine(label, state))
    return tuple(lines)


def next_step(f: NextInputs) -> Next:
    key = stage(f)
    index = _STEP_OF[key]
    if f.running:
        return Next("busy", strings.NEXT_BUSY_TITLE, strings.NEXT_BUSY_WHY, "", _steps(index))
    if f.read_only:
        return Next(
            "read_only",
            strings.NEXT_READ_ONLY_TITLE,
            strings.NEXT_READ_ONLY_WHY,
            "",
            _steps(index, blocked=True),
        )
    steps = _steps(index)
    if key == "add_device":
        return Next(
            key,
            strings.NEXT_ADD_TITLE,
            strings.NEXT_ADD_WHY,
            strings.NEXT_ADD_BUTTON,
            steps,
            alternative=strings.NEXT_ADD_ALTERNATIVE,
            alternative_key="new_harness",
            alternative_button=strings.NEXT_ADD_ALTERNATIVE_BUTTON,
        )
    if key == "connect":
        return Next(
            key,
            strings.NEXT_CONNECT_TITLE,
            strings.NEXT_CONNECT_WHY,
            strings.NEXT_CONNECT_BUTTON,
            steps,
        )
    if key == "generate":
        if f.generation == "stale" and f.harnesses > 0:
            title, why = strings.NEXT_GENERATE_AGAIN_TITLE, strings.NEXT_GENERATE_AGAIN_WHY
        else:
            title, why = strings.NEXT_GENERATE_TITLE, strings.NEXT_GENERATE_WHY
        return Next(key, title, why, strings.NEXT_GENERATE_BUTTON, steps)
    if key == "check":
        return Next(
            key, strings.NEXT_CHECK_TITLE, strings.NEXT_CHECK_WHY, strings.NEXT_CHECK_BUTTON, steps
        )
    if key == "fix":
        why = (
            strings.NEXT_FIX_WHY_ONE
            if f.failed == 1
            else strings.NEXT_FIX_WHY_MANY.format(f.failed)
        )
        return Next(key, strings.NEXT_FIX_TITLE, why, strings.NEXT_FIX_BUTTON, steps)
    if key == "build_sheets":
        notes = []
        if f.unchecked > 0:
            notes.append(strings.NEXT_SHEETS_WAIT)
        if not f.has_folder:
            notes.append(strings.NEXT_SHEETS_FOLDER)
        return Next(
            key,
            strings.NEXT_SHEETS_TITLE,
            strings.NEXT_SHEETS_WHY,
            strings.NEXT_SHEETS_BUTTON,
            steps,
            note=" ".join(notes),
        )
    if key == "release":
        return Next(
            key,
            strings.NEXT_RELEASE_TITLE,
            strings.NEXT_RELEASE_WHY,
            strings.NEXT_RELEASE_BUTTON,
            steps,
        )
    return Next(
        "done", strings.NEXT_DONE_TITLE, strings.NEXT_DONE_WHY, strings.NEXT_DONE_BUTTON, steps
    )
