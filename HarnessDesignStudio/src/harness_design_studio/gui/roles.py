"""The two roles of the editor (decision D-176, workshop milestone M5). No Qt here.

A role is a view of the tool, never a permission and never stored in a project:

    systems     Systems engineer: thinks in devices, connections between devices, subsystems, the
                library, checks and the Next step page. The lean layout (the Simple workspace of
                1.7.0): side panels closed, the Next step page first, a rail without the detail areas
                (Home, Drawings, Outputs), problem notices off until asked for.
    electrical  Electrical / AIT engineer: thinks in connectors, pinouts, harnesses, wires, build
                sheets and tests. Sees everything the tool offers (the Full workspace of 1.7.0).

The roles replace the Simple / Full choice of 1.7.0. The code keeps two things from it so that nobody
loses a saved layout: `systems` is stored under the keys `simple` had (`ui/simple/state`,
`layout/<hash>/simple/area`) and `electrical` under the keys `full` had (the plain ones). The stored
value of the role is `ui/role`; `ui/workspace` (1.7.0) is read once, to carry a person's choice over.

`FIRST_RUN_ROLE` is the hook for tests and CI: when it names a role, a settings file with no stored
values gets that role without a question. In the real program it is None, and the window asks once
("Who are you working as?").
"""

from typing import Final

SYSTEMS: Final = "systems"
ELECTRICAL: Final = "electrical"
ROLES: Final = (SYSTEMS, ELECTRICAL)
FIRST_RUN_ROLE: str | None = None  # a settings file with no stored values at all (tests set it)

# the 1.7.0 workspace a stored `ui/workspace` named, and the role it becomes
_FROM_WORKSPACE: Final = {"simple": SYSTEMS, "full": ELECTRICAL}


def default_role(has_stored_values: bool, old_workspace: object = None) -> str | None:
    """The role a settings file gets when it holds no role.

    A file that has values is an existing user: the choice of 1.7.0 (`ui/workspace`) carries over
    (Simple becomes Systems engineer), and anybody else becomes Electrical / AIT engineer, silently.
    A file with nothing stored gets `FIRST_RUN_ROLE`; None means the window must ask."""
    if has_stored_values:
        return _FROM_WORKSPACE.get(str(old_workspace), ELECTRICAL)
    return FIRST_RUN_ROLE if FIRST_RUN_ROLE in ROLES else None


def clean_role(value: object, fallback: str) -> str:
    """A stored value as one of `ROLES` (a hand-edited file may say anything)."""
    text = str(value)
    return text if text in ROLES else fallback


def role_key(key: str, role: str) -> str:
    """The settings key for a part of the layout that is remembered per role. Electrical keeps the
    key as it is (people who already use the editor lose nothing); Systems gets a key of its own
    next to it: `ui/state` becomes `ui/simple/state`, `layout/ab12/area` `layout/ab12/simple/area`."""
    if role != SYSTEMS:
        return key
    head, _, tail = key.rpartition("/")
    return f"{head}/simple/{tail}" if head else f"simple/{tail}"
