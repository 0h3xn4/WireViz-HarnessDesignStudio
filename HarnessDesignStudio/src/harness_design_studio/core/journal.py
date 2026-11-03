"""The change journal of a project: who changed what, when, from what to what and why (S4, D-191,
requirement R8).

A project has a journal if and only if it has the file `journal.json`. It is made by
`harness-design-studio journal DIR --start` and by `new` and the editor's New project; a project
that has none is opened and saved byte for byte as before.

How it is kept. Nobody writes to the journal while editing. When the project is **saved**, the files
of the design that changed are compared with what was on disk (`rows_for_save`), and one entry is
added for each field that changed. So every way of changing a project (the editor, the command line,
a script that calls `save_project`) is recorded the same way, and only files whose bytes changed are
read, so saving stays as fast as before. Generation is one entry for each harness it changed (the
number of wires added, changed and removed and the model hash before and after), not one for each
field.

Where the reason is. The model holds the reason for an override (`Wire.overrides`), a waiver and a
release; the journal adds who and when. The design files hold no name and no time, and
`journal.json` is left out of the model hash and of every written output, so the same design still
gives the same bytes. The clock and the author are read in `now()` and `author()` only, which tests
replace.
"""

import contextlib
import hashlib
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from harness_design_studio import __version__
from harness_design_studio.core.model import (
    Journal,
    JournalEntry,
    JournalError,
    Project,
)
from harness_design_studio.core.model.journal import KINDS

from .io import canonical

JOURNAL_FILE = "journal.json"
GENERATION_FILE = "generated/generation.json"
IMPORT_RECORDS_FILE = "imports/records.json"
UNKNOWN_AUTHOR = "unknown"
MAX_SHORT = 200  # a value longer than this is cut in the journal (the design file holds it whole)
BULK = 25  # more objects than this created or removed in one save are one entry
MAX_FIELDS_PER_OBJECT = 25  # more fields of one object than this changed in one save: one entry

__all__ = [
    "KINDS",
    "Journal",
    "JournalEntry",
    "JournalError",
    "author",
    "entries_for",
    "extended",
    "files_hash",
    "history",
    "now",
    "render",
    "rows_for_save",
    "set_author",
    "start",
    "to_dicts",
]

Row = dict[str, Any]

# ---- the clock and the author: the only places they are read, replaced by tests -----------------


def now() -> str:
    """The time of an entry: UTC, to the second (`2026-11-03T14:05:09Z`)."""
    from datetime import UTC, datetime

    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


_AUTHOR: str | None = None


def set_author(name: str | None) -> None:
    """Name the author for this run (the `--author` option of the command line); None undoes it."""
    global _AUTHOR
    _AUTHOR = _clean_name(name) if name else None


def _clean_name(name: str | None) -> str | None:
    if name is None:
        return None
    text = " ".join(name.split())[:200]
    return text if text and all(ord(c) >= 32 and ord(c) != 127 for c in text) else None


def author() -> str:
    """Who is working: `--author`, else the environment variable HARNESS_AUTHOR, else the name Git
    has for this person, else the user of the computer, else `unknown`."""
    if _AUTHOR:
        return _AUTHOR
    named = _clean_name(os.environ.get("HARNESS_AUTHOR"))
    if named:
        return named
    from .vcs.gitname import configured_name

    with contextlib.suppress(Exception):
        named = _clean_name(configured_name(Path.cwd()))
        if named:
            return named
    for var in ("USER", "USERNAME"):
        named = _clean_name(os.environ.get(var))
        if named:
            return named
    return UNKNOWN_AUTHOR


# ---- adding entries ---------------------------------------------------------------------------


def short(value: Any) -> Any:
    """`value` as it goes into an entry: a small value as it is, a big one cut."""
    if value is None or isinstance(value, bool | int):
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else str(value)
    if isinstance(value, str):
        return value if len(value) <= MAX_SHORT else value[: MAX_SHORT - 3] + "..."
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return value if len(text) <= MAX_SHORT else text[: MAX_SHORT - 3] + "..."


def _row(
    kind: str, obj: str, field: str = "", old: Any = None, new: Any = None, reason: str = ""
) -> Row:
    return {
        "kind": kind,
        "object": obj[:200] or "project",
        "field": field[:200],
        "old": short(old),
        "new": short(new),
        "reason": reason[:5000],
    }


def extended(journal: Journal, rows: Iterable[Row]) -> Journal:
    """`journal` with `rows` added, all with the same time, author and tool version."""
    rows = list(rows)
    if not rows:
        return journal
    when, who = now(), author()
    return journal.appended(
        {**r, "when": when, "author": who, "tool_version": __version__} for r in rows
    )


def start(project: Project, reason: str = "") -> bool:
    """Give the project a journal (it records its start). False when it has one already."""
    if project.journal is not None:
        return False
    first = _row(
        "start", "project", "journal", None, "started", reason or "The journal was started."
    )
    project.journal = extended(Journal(), [first])
    return True


# ---- reading ----------------------------------------------------------------------------------


def to_dicts(entries: Iterable[JournalEntry]) -> list[dict[str, Any]]:
    return [e.model_dump(mode="json") for e in entries]


def _matches(entry_object: str, wanted: str) -> bool:
    bare = entry_object.split(":", 1)[-1]
    return wanted in (entry_object, bare) or bare.startswith(wanted + ".")


def entries_for(
    project: Project, object_id: str | None = None, since: int = 0
) -> list[JournalEntry]:
    """The entries about `object_id` (`W001-001` or `wire:W001-001`; a configuration file also
    selects its keys), numbered above `since`, oldest first."""
    if project.journal is None:
        return []
    return [
        e
        for e in project.journal
        if e.seq > since and (object_id is None or _matches(e.object, object_id))
    ]


def history(project: Project, object_id: str | None = None, since: int = 0) -> list[dict[str, Any]]:
    return to_dicts(entries_for(project, object_id, since))


def _show(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def render_entry(e: JournalEntry) -> str:
    what = f"{e.object} {e.field}".strip()
    change = ""
    if e.old is not None or e.new is not None:
        change = f": {_show(e.old)} -> {_show(e.new)}"
    why = f" (reason: {e.reason})" if e.reason else ""
    return f"#{e.seq} {e.when} {e.author} [{e.kind}] {what}{change}{why}"


def render(entries: Iterable[JournalEntry]) -> str:
    """The entries as text for a person, one to a line, oldest first."""
    return "\n".join(render_entry(e) for e in entries)


# ---- what changed: comparing the files of a save with the files on disk -------------------------


def _blank_tool_version(project_json: bytes) -> bytes:
    try:
        data = json.loads(project_json)
        data["tool_version"] = ""
        return canonical.dumps(data)
    except ValueError, TypeError:
        return project_json


def files_hash(files: Mapping[str, bytes]) -> str:
    """The model hash of a set of project files (`layout.model_hash` of the project they came
    from): independent of the tool version and of the journal."""
    digest = hashlib.sha256()
    for rel, data in sorted(files.items()):
        if rel in (JOURNAL_FILE, IMPORT_RECORDS_FILE):
            continue
        if rel == "project.json":
            data = _blank_tool_version(data)
        digest.update(rel.encode("utf-8") + b"\0" + data + b"\0")
    return digest.hexdigest()


def _parse(data: bytes | None) -> Any:
    if data is None:
        return None
    try:
        return json.loads(data)
    except ValueError:
        return None


_LISTS = {  # file name pattern -> (collection, key of the list, object prefix)
    "waivers.json": ("waiver", "waivers"),
    "changelog.json": ("changelog", "changelog"),
    "logical/links.json": ("link", "links"),
    "logical/interface_types.json": ("interface_type", "interface_types"),
    IMPORT_RECORDS_FILE: ("import", "imports"),
}
_FOLDERS = (  # folder -> (collection, key of the list)
    ("library/", "part", "parts"),
    ("logical/units/", "device", "units"),
    ("logical/interfaces/", "interface", "interfaces"),
    ("physical/connectors/", "connector", "connectors"),
)
_HARNESS_LISTS = (  # list of a harness -> object prefix of its items
    ("connectors", "connector"),
    ("wires", "wire"),
    ("splices", "splice"),
    ("shields", "shield"),
    ("branch_points", "branch_point"),
    ("segments", "segment"),
    ("accessories", "accessory"),
)
_NOT_DESIGN = frozenset({"id"})


def _collect(rel: str, data: Any, bucket: dict[str, dict[str, Any]]) -> None:
    """File `data` under its collection, by the ID of each object."""
    if data is None:
        return
    if rel == "project.json":
        bucket.setdefault("project", {})["project"] = data
    elif rel == "library/manifest.json":
        bucket.setdefault("library", {})["library"] = data
    elif rel.startswith("config/"):
        bucket.setdefault("config", {})[rel.removeprefix("config/").removesuffix(".json")] = data
    elif rel.startswith("physical/harnesses/"):
        if isinstance(data, dict) and isinstance(data.get("id"), str):
            bucket.setdefault("harness", {})[data["id"]] = data
    else:
        found = _LISTS.get(rel)
        if found is None:
            found = next(((c, k) for f, c, k in _FOLDERS if rel.startswith(f)), None)
        if found is None or not isinstance(data, dict):
            return  # layout, baselines, the generation record: not entries of their own
        coll, key = found
        for obj in data.get(key, []) if isinstance(data.get(key), list) else []:
            if isinstance(obj, dict) and isinstance(obj.get("id"), str):
                bucket.setdefault(coll, {})[obj["id"]] = obj


def _leaves(path: str, old: Any, new: Any, out: list[tuple[str, Any, Any]]) -> None:
    """Every leaf that differs between `old` and `new`, as (path, old value, new value). Objects go
    key by key, lists of objects with an `id` item by item; anything else is compared whole."""
    if old == new:
        return
    if isinstance(old, dict) and isinstance(new, dict):
        for k in sorted(set(old) | set(new)):
            if k in _NOT_DESIGN and path == "":
                continue
            _leaves(f"{path}.{k}" if path else k, old.get(k), new.get(k), out)
        return
    if _is_id_list(old) and _is_id_list(new):
        a, b = {x["id"]: x for x in old}, {x["id"]: x for x in new}
        for i in sorted(set(a) | set(b)):
            _leaves(f"{path}[{i}]", a.get(i), b.get(i), out)
        return
    out.append((path, old, new))


def _is_id_list(v: Any) -> bool:
    return (
        isinstance(v, list)
        and bool(v)
        and all(isinstance(x, dict) and isinstance(x.get("id"), str) for x in v)
    )


def _object_rows(kind: str, obj: str, old: Any, new: Any, *, bulk_ok: bool = True) -> list[Row]:
    """The rows for one object that was created, removed or changed field by field."""
    if old is None:
        return [_row(kind, obj, "(created)", None, new)]
    if new is None:
        return [_row(kind, obj, "(removed)", old, None)]
    leaves: list[tuple[str, Any, Any]] = []
    _leaves("", old, new, leaves)
    if len(leaves) > MAX_FIELDS_PER_OBJECT:
        return [_row(kind, obj, "(changed)", None, f"{len(leaves)} fields changed")]
    return [_row(kind, obj, p, o, n) for p, o, n in leaves]


def _count_diff(old: list[dict[str, Any]], new: list[dict[str, Any]]) -> tuple[int, int, int]:
    a, b = {x.get("id"): x for x in old}, {x.get("id"): x for x in new}
    return (
        len(set(b) - set(a)),
        sum(1 for i in set(a) & set(b) if a[i] != b[i]),
        len(set(a) - set(b)),
    )


def _override_rows(wid: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[Row]:
    """Overrides set, changed or cleared on a wire: the field, the value before and after and the
    reason the model holds."""
    before = (old or {}).get("overrides") or {}
    after = (new or {}).get("overrides") or {}
    rows: list[Row] = []
    for f in sorted(set(before) | set(after)):
        o = (old or {}).get(f)
        n = (new or {}).get(f)
        if f in after:
            if f not in before or before[f] != after[f] or o != n:
                rows.append(_row("override", f"wire:{wid}", f, o, n, after[f]))
        else:
            rows.append(_row("override", f"wire:{wid}", f, o, n, "The override was cleared."))
    return rows


def _wire_rows(wid: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[Row]:
    rows = _override_rows(wid, old, new)
    if old is None or new is None:
        return [*_object_rows("edit", f"wire:{wid}", old, new), *rows]
    covered = {r["field"] for r in rows}
    leaves: list[tuple[str, Any, Any]] = []
    _leaves("", old, new, leaves)
    keep = [
        (p, o, n)
        for p, o, n in leaves
        if not (p == "overrides" or p.startswith("overrides.") or p in covered)
        and not (p == "locked" and rows)
    ]
    if len(keep) > MAX_FIELDS_PER_OBJECT:
        keep = [("(changed)", None, f"{len(keep)} fields changed")]
    return [*(_row("edit", f"wire:{wid}", p, o, n) for p, o, n in keep), *rows]


def _harness_rows(
    hid: str,
    old: dict[str, Any] | None,
    new: dict[str, Any] | None,
    *,
    generation: bool,
    hashes: tuple[str, str] | None,
) -> list[Row]:
    generated = bool((new or old or {}).get("generated"))
    if generation and generated:
        return _generated_harness_rows(hid, old, new, hashes)
    if old is None or new is None:
        return [
            _row("edit", f"harness:{hid}", "(created)" if old is None else "(removed)", old, new)
        ]
    rows: list[Row] = []
    scalars: list[tuple[str, Any, Any]] = []
    _leaves("", {k: v for k, v in old.items() if k not in dict(_HARNESS_LISTS)},
            {k: v for k, v in new.items() if k not in dict(_HARNESS_LISTS)}, scalars)  # fmt: skip
    for p, o, n in scalars:
        kind = (
            "release"
            if p in ("status", "revision", "released_on", "checker", "approver", "author")
            else "edit"
        )
        rows.append(_row(kind, f"harness:{hid}", p, o, n))
    for key, prefix in _HARNESS_LISTS:
        a = {x["id"]: x for x in old.get(key, [])}
        b = {x["id"]: x for x in new.get(key, [])}
        for i in sorted(set(a) | set(b)):
            if a.get(i) == b.get(i):
                continue
            if key == "wires":
                rows.extend(_wire_rows(i, a.get(i), b.get(i)))
            else:
                rows.extend(_object_rows("edit", f"{prefix}:{i}", a.get(i), b.get(i)))
    return rows


def _generated_harness_rows(
    hid: str, old: dict[str, Any] | None, new: dict[str, Any] | None, hashes: tuple[str, str] | None
) -> list[Row]:
    """A generated harness in a save that holds a generation: one entry for the whole harness, and
    the overrides (they are a person's, generation only keeps them)."""
    ow, nw = (old or {}).get("wires", []), (new or {}).get("wires", [])
    added, changed, removed = _count_diff(ow, nw)
    others = sum(
        sum(_count_diff((old or {}).get(k, []), (new or {}).get(k, [])))
        for k, _p in _HARNESS_LISTS
        if k != "wires"
    )
    rows: list[Row] = []
    if added or changed or removed or others or old is None or new is None:
        before = hashes[0] if hashes and old is not None else None
        after = hashes[1] if hashes and new is not None else None
        rows.append(
            _row(
                "generate",
                f"harness:{hid}",
                "generate",
                {"model_hash": before[:12]} if before else None,
                {
                    "wires_added": added,
                    "wires_changed": changed,
                    "wires_removed": removed,
                    "other_changes": others,
                    "model_hash": after[:12] if after else None,
                },
            )
        )
    a, b = {x["id"]: x for x in ow}, {x["id"]: x for x in nw}
    for i in sorted(set(a) | set(b)):
        rows.extend(_override_rows(i, a.get(i), b.get(i)))
    if old is not None and new is not None:
        for p in ("status", "released_on", "checker", "approver"):
            if old.get(p) != new.get(p):
                rows.append(_row("release", f"harness:{hid}", p, old.get(p), new.get(p)))
    return rows


def _waiver_kind(rule: str) -> str:
    from .drc.rules import RULES

    return "deviation" if any(r.id == rule and r.can_deviate for r in RULES) else "waiver"


def _waiver_rows(fid: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[Row]:
    obj = f"waiver:{fid}"
    if new is not None and old is None:
        kind = _waiver_kind(str(new.get("rule", "")))
        return [
            _row(kind, obj, "(added)", None, new.get("rule"), str(new.get("justification", "")))
        ]
    if old is not None and new is None:
        kind = _waiver_kind(str(old.get("rule", "")))
        return [
            _row(kind, obj, "(removed)", old.get("rule"), None, str(old.get("justification", "")))
        ]
    if old is None or new is None:
        return []
    kind = _waiver_kind(str(new.get("rule", "")))
    rows: list[Row] = []
    if old.get("justification") != new.get("justification"):
        now_text = new.get("justification")
        rows.append(
            _row(
                kind, obj, "justification", old.get("justification"), now_text, str(now_text or "")
            )
        )
    for p in ("finding_hash", "notes"):
        if old.get(p) != new.get(p):
            rows.append(_row(kind, obj, p, old.get(p), new.get(p)))
    return rows


def _import_summary(rec: dict[str, Any] | None) -> dict[str, Any] | None:
    if rec is None:
        return None
    return {
        "source": rec.get("source_name"),
        "sha256": str(rec.get("sha256", ""))[:12],
        "rows_read": rec.get("rows_read"),
        "dropped": rec.get("dropped_count", 0),
        "converted": rec.get("converted_count", 0),
    }


def _import_rows(rid: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[Row]:
    """An import record added, replaced (the same source imported again) or removed: one entry
    that says what was read, from which file (by its hash) and how much was dropped or converted."""
    what = "(recorded)" if old is None else "(removed)" if new is None else "(read again)"
    return [_row("import", f"import:{rid}", what, _import_summary(old), _import_summary(new))]


def _config_rows(name: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[Row]:
    if old is None or new is None:
        what = "(created)" if old is None else "(removed)"
        before = old.get("values") if old else None
        after = new.get("values") if new else None
        return [_row("config", f"config:{name}", what, before, after)]
    rows = []
    if old.get("placeholder") != new.get("placeholder"):
        o, n = old.get("placeholder"), new.get("placeholder")
        rows.append(_row("config", f"config:{name}", "placeholder", o, n))
    ov, nv = old.get("values") or {}, new.get("values") or {}
    for k in sorted(set(ov) | set(nv)):
        if ov.get(k) != nv.get(k) or (k in ov) != (k in nv):
            rows.append(_row("config", f"config:{name}.{k}", "value", ov.get(k), nv.get(k)))
    return rows


def _changelog_rows(cid: str, old: dict[str, Any] | None, new: dict[str, Any] | None) -> list[Row]:
    if new is None or old is not None:
        return []  # entries of the change log are written once
    return [
        _row(
            "release",
            f"harness:{new.get('harness_id')}",
            str(new.get("kind", "")),
            None,
            {"revision": new.get("revision"), "by": new.get("by"), "date": new.get("when")},
            str(new.get("comment", "")),
        )
    ]


def rows_for_save(
    project: Project, old: Mapping[str, bytes], new: Mapping[str, bytes]
) -> list[Row]:
    """The rows to add to the journal for a save that replaces the files `old` (what is on disk,
    by file name) by `new`. Only the files whose bytes differ are read."""
    changed = sorted(
        rel for rel in set(old) | set(new) if rel != JOURNAL_FILE and old.get(rel) != new.get(rel)
    )
    if not changed:
        return []
    before: dict[str, dict[str, Any]] = {}
    after: dict[str, dict[str, Any]] = {}
    for rel in changed:
        _collect(rel, _parse(old.get(rel)), before)
        _collect(rel, _parse(new.get(rel)), after)
    generation = GENERATION_FILE in changed
    rows: list[Row] = []
    hashes: tuple[str, str] | None = None
    if generation and (before.get("harness") or after.get("harness")):
        hashes = (files_hash(old), files_hash(new))
    allocation = {"connector": 0, "interface": 0}
    for coll in ("project", "library", "config", "part", "device", "interface", "interface_type",
                 "link", "connector", "waiver", "changelog", "harness", "import"):  # fmt: skip
        a, b = before.get(coll, {}), after.get(coll, {})
        ids = sorted(i for i in set(a) | set(b) if a.get(i) != b.get(i))
        if not ids:
            continue
        made = [i for i in ids if i not in a]
        gone = [i for i in ids if i not in b]
        if coll in ("part", "device", "interface", "connector", "link") and (
            len(made) > BULK or len(gone) > BULK
        ):
            if len(made) > BULK:
                rows.append(_row("import", f"{coll}:*", "(created)", None, f"{len(made)} objects"))
                ids = [i for i in ids if i not in made]
            if len(gone) > BULK:
                rows.append(_row("edit", f"{coll}:*", "(removed)", f"{len(gone)} objects", None))
                ids = [i for i in ids if i not in gone]
        for i in ids:
            o, n = a.get(i), b.get(i)
            if coll == "project":
                skip = {"tool_version", "schema_version"}
                rows.extend(
                    _row("edit", "project", p, ov, nv) for p, ov, nv in _top_leaves(o, n, skip)
                )
            elif coll == "library":
                rows.extend(
                    _row("edit", "library", p, ov, nv) for p, ov, nv in _top_leaves(o, n, set())
                )
            elif coll == "config":
                rows.extend(_config_rows(i, o, n))
            elif coll == "waiver":
                rows.extend(_waiver_rows(i, o, n))
            elif coll == "changelog":
                rows.extend(_changelog_rows(i, o, n))
            elif coll == "import":
                rows.extend(_import_rows(i, o, n))
            elif coll == "harness":
                rows.extend(_harness_rows(i, o, n, generation=generation, hashes=hashes))
            elif coll == "part":
                for r in _object_rows("edit", f"part:{i}", o, n):
                    if r["field"] == "approval":
                        r["kind"] = "approval"
                    rows.append(r)
            elif generation and coll in allocation and o is not None and n is not None:
                rest = _allocation_rows(coll, i, o, n, allocation)
                rows.extend(rest)
            else:
                rows.extend(_object_rows("edit", f"{coll}:{i}", o, n))
    if any(allocation.values()):
        counts = {f"{k}s_changed": v for k, v in allocation.items() if v}
        rows.append(_row("generate", "project", "allocation", None, counts))
    return rows


def _top_leaves(old: Any, new: Any, skip: set[str]) -> list[tuple[str, Any, Any]]:
    out: list[tuple[str, Any, Any]] = []
    _leaves("", old or {}, new or {}, out)
    return [x for x in out if x[0].split(".")[0] not in skip]


def _allocation_rows(
    coll: str, oid: str, old: dict[str, Any], new: dict[str, Any], count: dict[str, int]
) -> list[Row]:
    """A save that holds a generation: what generation allocated on a box connector (a pin's
    signal and interface) or chose for an interface (its connectors) is counted, not listed; any
    other field a person changed is listed."""
    leaves: list[tuple[str, Any, Any]] = []
    _leaves("", old, new, leaves)
    mine = [
        x
        for x in leaves
        if not (
            (
                coll == "connector"
                and x[0].startswith("pins[")
                and x[0].endswith((".signal", ".interface_id"))
            )
            or (coll == "interface" and x[0].startswith("endpoints"))
        )
    ]
    if len(mine) != len(leaves):
        count[coll] += 1
    if len(mine) > MAX_FIELDS_PER_OBJECT:
        return [_row("edit", f"{coll}:{oid}", "(changed)", None, f"{len(mine)} fields changed")]
    return [_row("edit", f"{coll}:{oid}", p, o, n) for p, o, n in mine]


def waiver_record(project: Project, waiver_id: str) -> JournalEntry | None:
    """The entry that says who accepted the finding `waiver_id` and when (the latest time the waiver
    was added or its justification changed); None when there is no journal or no such entry."""
    if project.journal is None:
        return None
    found = None
    for e in project.journal:
        if e.object == f"waiver:{waiver_id}" and e.kind in ("waiver", "deviation"):
            if e.field in ("(added)", "justification"):
                found = e
            elif e.field == "(removed)":
                found = None
    return found


def who_and_when(project: Project, waiver_id: str) -> str:
    """`by NAME on DATE` for a waiver or deviation, or '' when the journal does not know."""
    e = waiver_record(project, waiver_id)
    return f"by {e.author} on {e.when[:10]}" if e is not None else ""
