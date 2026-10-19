"""Recent projects: the list Home shows, kept in the program's settings (never in a project).

    entries = recent.load(settings)
    recent.remember(settings, RecentEntry(path="/work/flatsat", name="Flatsat", units=23, ...))

Each entry holds what a card on Home shows (name, folder, counts, how many harnesses are in each
state), so Home needs to read no project to draw it. The list is kept newest first, without
duplicates, at most `LIMIT` long. A damaged value in the settings reads as an empty list.
"""

import json
from dataclasses import asdict, dataclass
from typing import Any, Final, Protocol

KEY: Final = "home/recent"
LIMIT: Final = 8


class SettingsLike(Protocol):
    def value(self, key: str, default: Any = ...) -> Any: ...
    def setValue(self, key: str, value: Any) -> None: ...  # noqa: N802


@dataclass(frozen=True)
class RecentEntry:
    path: str
    name: str = ""
    units: int = 0
    interfaces: int = 0
    harnesses: int = 0
    draft: int = 0
    in_review: int = 0
    released: int = 0


def load(settings: SettingsLike) -> list[RecentEntry]:
    raw = settings.value(KEY, "")
    try:
        data = json.loads(str(raw)) if raw else []
    except ValueError:
        return []
    out: list[RecentEntry] = []
    if not isinstance(data, list):
        return out
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        try:
            out.append(
                RecentEntry(**{k: item[k] for k in RecentEntry.__dataclass_fields__ if k in item})
            )
        except TypeError:
            continue
    return out[:LIMIT]


def remember(settings: SettingsLike, entry: RecentEntry) -> bool:
    """Put `entry` first (replacing an older one for the same folder). Returns False, and writes
    nothing, when it is already first and unchanged."""
    current = load(settings)
    if current and current[0] == entry:
        return False
    rest = [e for e in current if e.path != entry.path]
    settings.setValue(KEY, json.dumps([asdict(e) for e in [entry, *rest][:LIMIT]]))
    return True


def forget(settings: SettingsLike, path: str) -> None:
    settings.setValue(KEY, json.dumps([asdict(e) for e in load(settings) if e.path != path]))
