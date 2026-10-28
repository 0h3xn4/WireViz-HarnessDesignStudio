"""Different people in a release, an optional setting of the project (1.9.0, audit F-07).

Off by default and then nothing here changes anything: one name can still author, check and
release a harness. The project switches it on with `release_distinct_roles` in
`config/naming.json` (`harness-design-studio config DIR --distinct-roles on`). While it is on:

- the author (who put the harness into review), the person who checked it and the person who
  releases it must be three different people, and the author and the checker must be named;
- the date of a review, release or new revision may not be earlier than the latest entry of the
  change log or the latest baseline of the whole project, and not more than one day after today
  (one day because the clocks of two places differ); the rule that a date may not be earlier than
  the last entry of the same harness holds with or without the setting;
- a name that is left out is taken from Git (`gitname.py`) when Git has one; it is never made up.

`naming.json` is not frozen by a release (`snapshot.FROZEN_CONFIG_FILES`), so the setting can be
switched on at any time. It never changes a harness that is released already. No Qt, no model change.
"""

import unicodedata
from datetime import date, timedelta
from pathlib import Path

from harness_design_studio.core.model import Project

from .gitname import configured_name

CONFIG_FILE = "naming"
CONFIG_KEY = "release_distinct_roles"
FUTURE_DAYS = 1  # a date up to one day after today is accepted


def distinct_roles_on(project: Project) -> bool:
    """Is the setting switched on? Only the value true switches it on; a value that is not true
    or false is an error of the configuration check, and the setting stays off."""
    config = project.config.get(CONFIG_FILE)
    return config is not None and config.values.get(CONFIG_KEY) is True


def person_key(name: str) -> str:
    """Two spellings of one name compare equal: letter case, width and spacing do not matter."""
    return " ".join(unicodedata.normalize("NFKC", name).casefold().split())


def same_person(a: str | None, b: str | None) -> bool:
    return bool(a and b and person_key(a) and person_key(a) == person_key(b))


def default_name(project: Project, start: Path | None) -> str | None:
    """The name to use when none was typed: the Git `user.name` when the setting is on and Git
    has one, else None (today's behaviour: the person must type a name)."""
    return configured_name(start) if distinct_roles_on(project) else None


def latest_date(project: Project) -> tuple[str, str] | None:
    """The latest date written in the change log or in a baseline of any harness of the project,
    with the harness it belongs to; None when there is none."""
    from .release import valid_date

    dated = [(e.when, e.harness_id) for e in project.changelog.values()]
    dated += [(b.released_on, b.harness_id) for b in project.baselines.values()]
    good = [x for x in dated if valid_date(x[0])]
    return max(good) if good else None


def date_problem(project: Project, when: str, today: date) -> tuple[str, str] | None:
    """(code, plain sentence) when `when` (a valid date) is refused by the setting, else None."""
    if not distinct_roles_on(project):
        return None
    last = latest_date(project)
    if last is not None and when < last[0]:
        return (
            "date_before_project_last",
            f"The date {when} is earlier than the latest entry of the project's change log "
            f"({last[0]}, {last[1]}). Use that date or a later one.",
        )
    if date.fromisoformat(when) > today + timedelta(days=FUTURE_DAYS):
        return (
            "date_in_future",
            f"The date {when} is more than {FUTURE_DAYS} day after today ({today.isoformat()}). "
            "Use today's date.",
        )
    return None
