"""The areas of the window: what the navigation rail lists and which views each one holds.

No Qt here, so the mapping is tested without a display. An area is a place the person goes to
(`Next step`, `Home`, `Model`, `Checks` ...); the views it holds are the tabs of the main tab widget
(`diagram`, `devices`, `checks`, `harness`, `lists`, `releases`). Next step, Home and Settings are
pages of their own and hold no tab. The mapping of every old tab, menu and dialog is in
docs/ui/UI_OVERHAUL_PLAN.md (section 4).
"""

from dataclasses import dataclass
from typing import Final

from harness_design_studio.gui import strings


@dataclass(frozen=True)
class Area:
    key: str
    title: str
    icon: str  # a name of gui/icons.py
    tabs: tuple[str, ...]  # the main tabs it shows, in order; empty for a page of its own
    tip: str


AREAS: Final[tuple[Area, ...]] = (
    Area("next", strings.AREA_NEXT, "nav-next", (), strings.AREA_NEXT_TIP),
    Area("home", strings.AREA_HOME, "nav-home", (), strings.AREA_HOME_TIP),
    Area("model", strings.AREA_MODEL, "nav-model", ("diagram", "devices"), strings.AREA_MODEL_TIP),
    Area("checks", strings.AREA_CHECKS, "nav-checks", ("checks",), strings.AREA_CHECKS_TIP),
    Area("drawings", strings.AREA_DRAWINGS, "nav-drawings", ("harness",), strings.AREA_DRAWINGS_TIP),
    Area("outputs", strings.AREA_OUTPUTS, "nav-outputs", ("lists",), strings.AREA_OUTPUTS_TIP),
    Area("revisions", strings.AREA_REVISIONS, "nav-revisions", ("releases",), strings.AREA_REVISIONS_TIP),
    Area("settings", strings.AREA_SETTINGS, "nav-settings", (), strings.AREA_SETTINGS_TIP),
)  # fmt: skip
KEYS: Final[tuple[str, ...]] = tuple(a.key for a in AREAS)
PAGES: Final[tuple[str, ...]] = tuple(a.key for a in AREAS if not a.tabs)  # not backed by a tab
DEFAULT: Final[str] = "model"


def area(key: str) -> Area:
    for a in AREAS:
        if a.key == key:
            return a
    raise KeyError(key)


def area_of_tab(tab: str) -> str:
    """The area that holds a main tab."""
    for a in AREAS:
        if tab in a.tabs:
            return a.key
    raise KeyError(tab)


def tabs_of(key: str) -> tuple[str, ...]:
    return area(key).tabs
