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
from harness_design_studio.gui.roles import AIT, ELECTRICAL, ROLES, SYSTEMS


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
    Area("asbuilt", strings.AREA_ASBUILT, "nav-asbuilt", (), strings.AREA_ASBUILT_TIP),
    Area("revisions", strings.AREA_REVISIONS, "nav-revisions", ("releases",), strings.AREA_REVISIONS_TIP),
    Area("settings", strings.AREA_SETTINGS, "nav-settings", (), strings.AREA_SETTINGS_TIP),
)  # fmt: skip
KEYS: Final[tuple[str, ...]] = tuple(a.key for a in AREAS)
PAGES: Final[tuple[str, ...]] = tuple(a.key for a in AREAS if not a.tabs)  # not backed by a tab
DEFAULT: Final[str] = "model"
# What the rail lists for each role (S9). A role is a view, never a permission: the area stays in
# the View and Go menus, the command palette and the buttons of the Next step page, and the rail lists
# the one that is open. The Systems engineer role has Next step instead of Home and leaves out the
# detail areas (the drawings, the outputs and the as-built records); the Electrical engineer role
# lists every area but the as-built records; the AIT role leaves out the Model (the diagram and the
# devices), which is where the design is edited.
SYSTEMS_HIDDEN: Final[tuple[str, ...]] = ("home", "drawings", "outputs", "asbuilt")
HIDDEN_AREAS: Final[dict[str, tuple[str, ...]]] = {
    SYSTEMS: SYSTEMS_HIDDEN,
    ELECTRICAL: ("asbuilt",),
    AIT: ("model",),
}
# Quick mode (a view setting on top of any role, `ui/quick`) lists three areas whatever the role: the
# Model (the diagram and the devices), Home (the way to a new or recent project) and Settings. The
# areas of due diligence (Next step, Checks, Drawings, Outputs, Revisions, As-built) are left out of
# the rail like a role leaves some out: they stay in the View and Go menus and the command palette,
# and the rail lists the one that is open.
QUICK_LISTED: Final[tuple[str, ...]] = ("home", "model", "settings")


# The menu entries the Systems engineer role does not list (Release 1.9, W1). The names are the
# object names of the actions; "menu:" names a submenu by its title. They are only hidden: every
# one stays in the command palette (Ctrl+K) and keeps its shortcut, and the Electrical / AIT
# engineer role lists all of them. A role is a view of the program, never a permission.
SYSTEMS_HIDDEN_ACTIONS: Final[tuple[str, ...]] = (
    # File > Import: the lists of wires, lengths and values, and the interface-first import
    "act-import", "act-import-lengths", "act-import-values", "act-import-netlist",
    # Edit: the diagram tools, the harness and wire tools, the interface-first way
    "act-select-all", "act-duplicate", "act-redundant", "act-new-interface",
    "act-add-zone", "act-new-harness", "act-bulk-wires", "act-wire-colours",
    "act-align-left", "act-align-hcenter", "act-align-right", "act-align-top",
    "act-align-vmiddle", "act-align-bottom", "act-distribute-horizontal",
    "act-distribute-vertical", "menu:align", "menu:distribute", "menu:connect-with-type",
    # View: the diagram's drawing options
    "act-guided", "act-expert", "act-minimap", "act-legend", "act-snap", "act-labels",
    "act-connection-ends", "act-zoom-100", "act-zoom-selection", "act-arrange",
    # Design: revisions of a harness and the engineering values
    "act-revise", "act-changes", "act-history", "act-delete-harness", "act-values",
    # Go: the detail views and the two lists the side panels hold
    "act-go-harness", "act-go-lists", "act-go-interfaces", "act-go-units",
)  # fmt: skip


# The as-built entries: the page, the import of a filled-in sheet and the sheet to fill in. Only the
# AIT role lists them in the menus; the command palette runs them in every role.
ASBUILT_ACTIONS: Final[tuple[str, ...]] = ("act-go-asbuilt", "act-import-asbuilt", "act-export-asbuilt")  # fmt: skip
# What the AIT role does not list: the editing of the diagram (the tools, the alignment, the
# drawing options of the View menu), the way back to the diagram and the two lists beside it.
AIT_HIDDEN_ACTIONS: Final[tuple[str, ...]] = (
    "act-select-all", "act-duplicate", "act-redundant", "act-new-interface", "act-add-zone",
    "act-align-left", "act-align-hcenter", "act-align-right", "act-align-top",
    "act-align-vmiddle", "act-align-bottom", "act-distribute-horizontal",
    "act-distribute-vertical", "menu:align", "menu:distribute", "menu:connect-with-type",
    "act-guided", "act-expert", "act-minimap", "act-legend", "act-snap", "act-labels",
    "act-connection-ends", "act-zoom-100", "act-zoom-selection", "act-arrange",
    "act-go-diagram", "act-go-devices", "act-go-interfaces", "act-go-units",
)  # fmt: skip
HIDDEN_ACTIONS: Final[dict[str, tuple[str, ...]]] = {
    SYSTEMS: (*SYSTEMS_HIDDEN_ACTIONS, *ASBUILT_ACTIONS),
    ELECTRICAL: ASBUILT_ACTIONS,
    AIT: AIT_HIDDEN_ACTIONS,
}


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


def hidden_actions_in(role: str) -> tuple[str, ...]:
    """The menu entries a role does not list (see `HIDDEN_ACTIONS`)."""
    return HIDDEN_ACTIONS.get(role, ())


def hidden_in(role: str, quick: bool = False) -> tuple[str, ...]:
    """The areas the rail does not list for a role (with Quick mode on: for any role, every area
    but `QUICK_LISTED`). They still exist: the View and Go menus, their keys, the buttons of the
    Next step page and the command palette reach them, and the rail lists the one that is open."""
    if quick:
        return tuple(a.key for a in AREAS if a.key not in QUICK_LISTED)
    return HIDDEN_AREAS.get(role, ())


def listed_areas(role: str) -> tuple[str, ...]:
    """The areas the rail lists for a role, in order."""
    gone = hidden_in(role)
    return tuple(a.key for a in AREAS if a.key not in gone)


def unlisted_everywhere() -> tuple[str, ...]:
    """The areas that no role lists (a test keeps this empty: every page is on the rail of at
    least one role)."""
    return tuple(a.key for a in AREAS if all(a.key in hidden_in(r) for r in ROLES))
