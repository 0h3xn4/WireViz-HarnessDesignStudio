"""What a project's `extensions/` folder is and does: finding it, checking it, and running it.

`discover(root)` is called by the loader when a project is opened (nothing happens for a project
without an `extensions/` folder: `project.extensions` stays None and no extension code is reached).
It reads, in this order and without running any plug-in that is not enabled and trusted:

1. `extensions/enabled.json`: which files and which plug-ins the project uses;
2. the Python plug-ins (the project's and the installed ones): what they are and whether they may be
   loaded; the ones that may are loaded now, because their fields can be read by the files below;
3. the declarative files `extensions/*.json`: checked and, if enabled and without a problem, kept.

The result (`ProjectExtensions`) is plain data that can be pickled (the rule check runs in a helper
process); `runtime(project)` turns it, in whichever process asks, into the objects that run: the
rules, the tables and the registry.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harness_design_studio.core.checks import Finding
from harness_design_studio.core.derive import Derivation, Input
from harness_design_studio.core.drc.base import Hit, Rule
from harness_design_studio.core.model import Project

from . import builtins, trust
from . import plugins as plugins_mod
from .declarative import DeclRule, ExtFile, ExtIssue, build_table, read_file
from .fields import BUILTIN_FIELDS, FieldDef
from .jsonpos import JsonSyntaxError, Located
from .jsonpos import loads as load_located
from .pluginapi import PluginImporter, PluginRule, PluginTable
from .registry import (
    DECLARATIVE,
    FIELD,
    LOOKUP,
    PLUGIN,
    REGISTRY,
    RULE,
    TABLE,
    Item,
    Registry,
    RegistryError,
)
from .schema import ENABLED, ENABLED_FORMAT, check, show_path

FOLDER = "extensions"
ENABLED_FILE = "enabled.json"
MAX_FILE_BYTES = 1024 * 1024
PROBLEM_RULE = "x-extension-problem"
TABLE_FOLDER = "system/extensions"

type Table = list[list[str]]


@dataclass(frozen=True)
class FileInfo:
    rel: str
    file: str  # the file name, as enabled.json lists it
    name: str
    version: str
    sha256: str
    enabled: bool
    status: str  # "applied" | "disabled" | "broken" | "unreadable"
    rules: int = 0
    tables: int = 0
    lookups: int = 0


@dataclass(frozen=True)
class ProjectExtensions:
    root: str  # where the project was read (in memory only; never written to project data)
    files: tuple[FileInfo, ...] = ()
    parsed: tuple[ExtFile, ...] = ()  # every file that is valid, enabled or not
    plugins: tuple[plugins_mod.PluginInfo, ...] = ()
    issues: tuple[ExtIssue, ...] = ()
    enabled_files: tuple[str, ...] = ()
    enabled_plugins: tuple[str, ...] = ()
    search_path: tuple[str, ...] | None = None  # only tests give one

    @property
    def applied(self) -> tuple[ExtFile, ...]:
        names = {f.rel for f in self.files if f.status == "applied"}
        return tuple(p for p in self.parsed if p.rel in names)

    @property
    def fingerprint(self) -> str:
        h = hashlib.sha256()
        for f in self.files:
            h.update(f"{f.rel}|{f.sha256}|{f.status}\n".encode())
        for p in self.plugins:
            h.update(f"{p.name}|{p.sha256}|{p.state}|{p.trusted}\n".encode())
        h.update(self.root.encode())
        return h.hexdigest()


def _read_limited(path: Path) -> tuple[bytes | None, str]:
    if path.is_symlink() or not path.is_file():
        return None, "a link is not followed: extension files must be real files in the project"
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return None, f"the file is larger than {MAX_FILE_BYTES // 1024} KB"
        return path.read_bytes(), ""
    except OSError as exc:
        return None, f"the file could not be read ({exc.strerror})"


def read_enabled(root: Path) -> tuple[list[str], list[str], list[ExtIssue], bool]:
    """(declarative files, plug-in names, problems, whether the file exists) of enabled.json."""
    rel = f"{FOLDER}/{ENABLED_FILE}"
    path = root / FOLDER / ENABLED_FILE
    if not path.exists():
        return [], [], [], False
    data, why = _read_limited(path)
    if data is None:
        return [], [], [ExtIssue("error", rel, 1, "", why)], True
    try:
        doc: Located = load_located(data.decode("utf-8"))
    except UnicodeDecodeError:
        return [], [], [ExtIssue("error", rel, 1, "", "the file is not UTF-8 text")], True
    except JsonSyntaxError as exc:
        return (
            [],
            [],
            [
                ExtIssue(
                    "error",
                    rel,
                    exc.line,
                    "",
                    f"not valid JSON at column {exc.column}: {exc.message}",
                )
            ],
            True,
        )
    problems = [
        ExtIssue("error", rel, doc.line_of(p.path) or 1, show_path(p.path), p.message)
        for p in check(ENABLED, doc.value)
    ]
    if problems:
        return [], [], problems, True
    value = doc.value
    if not isinstance(value, dict):  # (the shape check has refused anything else)
        return [], [], problems, True
    return list(value.get("declarative", [])), list(value.get("plugins", [])), [], True


def write_enabled(root: Path, declarative: list[str], plugin_names: list[str]) -> None:
    """Write enabled.json in the tool's own form (sorted, one name to a line). The only file of the
    extensions folder the tool ever writes."""
    import json

    doc = {
        "format": ENABLED_FORMAT,
        "format_version": 1,
        "declarative": sorted(set(declarative)),
        "plugins": sorted(set(plugin_names)),
    }
    folder = root / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    (folder / ENABLED_FILE).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")


def discover(root: Path, search_path: list[str] | None = None) -> ProjectExtensions | None:
    """The extensions of the project in `root`, or None when it has no `extensions/` folder."""
    folder = root / FOLDER
    if folder.is_symlink() or not folder.is_dir():
        return None
    builtins.install()
    enabled_files, enabled_plugins, issues, _present = read_enabled(root)
    issues = list(issues)
    # -- plug-ins first: the declarative files may read their fields
    candidates = plugins_mod.project_candidates(root) + plugins_mod.installed_candidates(
        search_path
    )
    infos: list[plugins_mod.PluginInfo] = []
    plugin_fields: list[FieldDef] = []
    for c in candidates:
        info = plugins_mod.info_for(c, set(enabled_plugins))
        if info.state == "ready":
            done = plugins_mod.load(c, root, search_path)
            clash = next((i for i in done.items if REGISTRY.get(i.kind, i.name) is not None), None)
            if clash is not None and not done.problem:
                done = plugins_mod.Loaded(
                    done.name,
                    done.sha256,
                    [],
                    f"the {clash.kind} '{clash.name}' is already provided by the tool",
                )
                plugins_mod._LOADED[(c.name, c.sha256)] = done
            if done.problem:
                info = _with(info, state=plugins_mod.FAILED, message=done.problem)
                issues.append(
                    ExtIssue(
                        "warning",
                        c.where,
                        1,
                        "",
                        f"plug-in {c.name} could not be loaded: {done.problem}",
                    )
                )
            else:
                info = _with(info, state=plugins_mod.LOADED)
                plugin_fields += [
                    i.obj for i in done.items if i.kind == FIELD and isinstance(i.obj, FieldDef)
                ]
        infos.append(info)
    known = {i.name for i in infos}
    for name in enabled_plugins:
        if name not in known:
            issues.append(
                ExtIssue(
                    "warning",
                    f"{FOLDER}/{ENABLED_FILE}",
                    1,
                    "plugins",
                    f"the plug-in '{name}' is enabled but no such plug-in is installed or in {plugins_mod.PLUGIN_DIR}",
                )
            )
    defs: list[FieldDef] = [*BUILTIN_FIELDS, *plugin_fields]
    # -- declarative files
    files: list[FileInfo] = []
    parsed: list[ExtFile] = []
    on_disk = sorted(p for p in folder.glob("*.json") if p.name != ENABLED_FILE)
    present = {p.name for p in on_disk}
    for p in on_disk:
        rel = f"{FOLDER}/{p.name}"
        data, why = _read_limited(p)
        enabled = p.name in enabled_files
        if data is None:
            files.append(FileInfo(rel, p.name, p.stem, "", "", enabled, "unreadable"))
            if enabled:
                issues.append(ExtIssue("error", rel, 1, "", why))
            continue
        sha = hashlib.sha256(data).hexdigest()
        spec, found = read_file(rel, data, sha, defs)
        if spec is None:
            files.append(
                FileInfo(rel, p.name, p.stem, "", sha, enabled, "broken" if enabled else "disabled")
            )
            if enabled:
                issues.extend(found)
            continue
        parsed.append(spec)
        files.append(
            FileInfo(rel, p.name, spec.name, spec.version, sha, enabled, "applied" if enabled else "disabled",
                     len(spec.rules), len(spec.tables), len(spec.lookups))
        )  # fmt: skip
    for name in enabled_files:
        if name not in present:
            issues.append(
                ExtIssue(
                    "error",
                    f"{FOLDER}/{ENABLED_FILE}",
                    1,
                    "declarative",
                    f"'{name}' is enabled but {FOLDER}/{name} does not exist",
                )
            )
    ext = ProjectExtensions(
        str(root), tuple(files), tuple(parsed), tuple(infos), tuple(issues),
        tuple(enabled_files), tuple(enabled_plugins),
        None if search_path is None else tuple(search_path),
    )  # fmt: skip
    return _without_clashes(ext)


def _with(info: plugins_mod.PluginInfo, **changes: object) -> plugins_mod.PluginInfo:
    from dataclasses import replace

    return replace(info, **changes)  # type: ignore[arg-type]


def _without_clashes(ext: ProjectExtensions) -> ProjectExtensions:
    """A rule id or table name that two enabled sources both claim goes to the first (declarative
    files in name order, then plug-ins); the second is reported and not applied."""
    from dataclasses import replace

    taken: dict[tuple[str, str], str] = {(i.kind, i.name): "the tool" for i in REGISTRY.items()}
    for info in ext.plugins:
        if info.state != plugins_mod.LOADED:
            continue
        done = plugins_mod._LOADED.get((info.name, info.sha256))
        for item in done.items if done else []:
            taken.setdefault((item.kind, item.name), info.where)
    issues = list(ext.issues)
    files = list(ext.files)
    for n, f in enumerate(files):
        if f.status != "applied":
            continue
        spec = next(p for p in ext.parsed if p.rel == f.rel)
        names = [(RULE, r.id) for r in spec.rules] + [(TABLE, t.name) for t in spec.tables]
        clash = [(k, nm, taken[(k, nm)]) for k, nm in names if (k, nm) in taken]
        if clash:
            k, nm, where = clash[0]
            issues.append(
                ExtIssue(
                    "error",
                    f.rel,
                    1,
                    "",
                    f"the {k} '{nm}' is already provided by {where}; this file is not applied",
                )
            )
            files[n] = replace(f, status="broken")
            continue
        for k, nm in names:
            taken[(k, nm)] = f.rel
    return replace(ext, files=tuple(files), issues=tuple(issues))


def attach(project: Project, root: Path, search_path: list[str] | None = None) -> None:
    """Set `project.extensions` from the folder it was read from."""
    project.extensions = discover(root, search_path)


def refresh(project: Project) -> None:
    """Read the extensions folder again (after the person changed a file, trusted a plug-in or
    changed enabled.json)."""
    ext = project.extensions
    if ext is not None:
        plugins_mod.forget_loaded()
        _RUNTIMES.clear()
        project.extensions = discover(
            Path(ext.root), None if ext.search_path is None else list(ext.search_path)
        )


# ---- running --------------------------------------------------------------------------------------------


@dataclass
class Runtime:
    registry: Registry
    decl_rules: dict[str, DeclRule] = field(default_factory=dict)
    plugin_rules: dict[str, PluginRule] = field(default_factory=dict)
    rules: list[Rule] = field(default_factory=list)  # in the order they run
    tables: list[tuple[str, Callable[[Project], tuple[Table, list[str]]]]] = field(
        default_factory=list
    )
    importers: dict[str, PluginImporter] = field(default_factory=dict)
    defs: dict[str, FieldDef] = field(default_factory=dict)


_RUNTIMES: dict[str, Runtime] = {}


def _plugin_candidate(info: plugins_mod.PluginInfo) -> plugins_mod.Candidate:
    return plugins_mod.Candidate(
        info.name, info.version, info.kinds, info.api, info.source, info.where, info.sha256,
        info.lines, info.description, "", info.locator,
    )  # fmt: skip


def runtime(project: Project) -> Runtime | None:
    """The objects that run for a project; None for a project without an extensions folder."""
    ext: ProjectExtensions | None = project.extensions
    if ext is None:
        return None
    builtins.install()
    key = ext.fingerprint
    if any(p.state == plugins_mod.LOADED for p in ext.plugins):
        # trust may have been taken back since the project was read (by another process): a cached
        # runtime is used only while the same plug-ins are still trusted
        key += "|" + ",".join(
            sorted(
                p.name
                for p in ext.plugins
                if p.state == plugins_mod.LOADED
                and p.enabled
                and trust.is_trusted(p.name, p.sha256)
            )
        )
    hit = _RUNTIMES.get(key)
    if hit is not None:
        return hit
    items: list[Item] = []
    defs: dict[str, FieldDef] = {d.id: d for d in BUILTIN_FIELDS}
    rt = Runtime(REGISTRY.layered(), defs=defs)
    for info in ext.plugins:
        # trust is asked again here: the process may be another one, and trust may have been taken back
        if not (
            info.enabled
            and info.state == plugins_mod.LOADED
            and trust.is_trusted(info.name, info.sha256)
        ):
            continue
        done = plugins_mod.load(
            _plugin_candidate(info),
            Path(ext.root),
            None if ext.search_path is None else list(ext.search_path),
        )
        if done.problem:
            continue
        items += done.items
    for item in items:
        if item.kind == FIELD and isinstance(item.obj, FieldDef):
            defs[item.name] = item.obj
    decl_items: list[Item] = []
    for spec in ext.applied:
        for r in spec.rules:
            d = DeclRule(r, spec, defs)
            rt.decl_rules[r.id] = d
            decl_items.append(
                Item(RULE, r.id, spec.version, DECLARATIVE, spec.rel, spec.sha256, r.title, d)
            )
        for t in spec.tables:
            decl_items.append(
                Item(TABLE, t.name, spec.version, DECLARATIVE, spec.rel, spec.sha256, t.title, t)
            )
            rt.tables.append((t.name, _declarative_table(t, spec, defs)))
        for lk in spec.lookups:
            decl_items.append(
                Item(
                    LOOKUP,
                    f"{spec.name}/{lk.name}",
                    spec.version,
                    DECLARATIVE,
                    spec.rel,
                    spec.sha256,
                    lk.description or lk.key,
                    lk,
                )
            )
    for item in [*decl_items, *items]:
        try:
            rt.registry.register(item)
        except RegistryError:
            continue  # a clash was reported by discover; the first one stays
        if item.kind == RULE and isinstance(item.obj, PluginRule):
            rt.plugin_rules[item.name] = item.obj
        elif item.kind == TABLE and isinstance(item.obj, PluginTable):
            rt.tables.append((item.name, _plugin_table(item.obj)))
        elif item.kind == "importer" and isinstance(item.obj, PluginImporter):
            rt.importers[item.name] = item.obj
    rt.tables.sort(key=lambda t: t[0])
    rt.rules = [d.rule() for _id, d in sorted(rt.decl_rules.items())] + [
        pr.rule for _id, pr in sorted(rt.plugin_rules.items())
    ]
    if len(_RUNTIMES) > 16:
        _RUNTIMES.clear()
    _RUNTIMES[key] = rt
    return rt


def _declarative_table(t, spec: ExtFile, defs: dict[str, FieldDef]):  # type: ignore[no-untyped-def]
    return lambda project: build_table(project, t, spec, defs)


def _plugin_table(t: PluginTable):  # type: ignore[no-untyped-def]
    def build(project: Project) -> tuple[Table, list[str]]:
        try:
            rows = t.build(project)
            return [[str(c) for c in row] for row in rows], []
        except Exception as exc:  # a plug-in's table must not stop an export
            return [["error"]], [f"table {t.name}: {type(exc).__name__}: {str(exc)[:200]}"]

    return build


# ---- the rules of a project ------------------------------------------------------------------------------


def rules_for(project: Project) -> list[Rule]:
    """The extension rules to run for a project: declarative first (by ID), then plug-in rules. A
    plug-in rule that raises is turned into one finding that says so (see `problem_rule`)."""
    rt = runtime(project)
    return list(rt.rules) if rt is not None else []


def run_extension_rules(project: Project) -> list[Finding]:
    """The findings of every extension rule and of the rule that reports what could not be applied.
    A plug-in rule that raises gives a finding of the problem rule; it never stops the check."""
    rt = runtime(project)
    ext: ProjectExtensions | None = project.extensions
    if rt is None or ext is None:
        return []
    found: list[Finding] = []
    failed: list[str] = []
    for rule in rt.rules:
        try:
            found += rule.run(project)
        except Exception as exc:
            failed.append(f"{rule.id}: {type(exc).__name__}: {str(exc)[:200]}")
    found += problem_rule(project, failed).run(project)
    return found


def problems(project: Project, failed: list[str] | None = None) -> list[tuple[str, str]]:
    """(object, statement) for everything the project enabled that is not applied."""
    ext: ProjectExtensions | None = project.extensions
    out: list[tuple[str, str]] = []
    if ext is None:
        return out
    by_file: dict[str, list[ExtIssue]] = {}
    for i in ext.issues:
        by_file.setdefault(i.file, []).append(i)
    for f in ext.files:
        if f.enabled and f.status in ("broken", "unreadable"):
            first = by_file.get(f.rel, [None])[0]
            more = len(by_file.get(f.rel, [])) - 1
            text = first.render() if first else "it could not be read"
            out.append(
                (
                    f.file,
                    f"The extension file {f.rel} is enabled but was not applied: {text}"
                    + (f" (and {more} more)" if more > 0 else ""),
                )
            )
    for p in ext.plugins:
        if p.enabled and p.state not in (plugins_mod.LOADED,):
            out.append(
                (
                    p.name,
                    f"The plug-in {p.name} is enabled but was not loaded: {p.message or p.state}",
                )
            )
    for i in ext.issues:
        if i.file == f"{FOLDER}/{ENABLED_FILE}":
            out.append(
                (ENABLED_FILE, f"{FOLDER}/{ENABLED_FILE} is not applied as written: {i.render()}")
            )
    for text in failed or []:
        out.append(
            (
                text.split(":")[0],
                f"An extension rule stopped with an error and was not applied: {text}",
            )
        )
    return sorted(set(out))


def problem_rule(project: Project, failed: list[str] | None = None) -> Rule:
    def check(p: Project) -> object:
        for obj, text in problems(p, failed):
            yield Hit(obj, text)

    return Rule(
        PROBLEM_RULE, "warning", "Extensions not applied",
        "An extension that the project enabled did not run, so the checks and tables it adds are missing from this report: silence would look like a pass.",
        "Open Help > Extensions (or run `harness-design-studio extensions DIR`) and correct the file, trust the plug-in, or take it out of extensions/enabled.json.",
        check,  # type: ignore[arg-type]
    )  # fmt: skip


def rule_notes(project: Project) -> dict[str, list[str]]:
    """What each declarative rule could not look at (objects with a value that is not known)."""
    rt = runtime(project)
    if rt is None:
        return {}
    out: dict[str, list[str]] = {}
    for rid, d in rt.decl_rules.items():
        notes = d.notes(project)
        if notes:
            out[rid] = notes
    return out


def is_extension_rule(project: Project, rule_id: str) -> bool:
    if rule_id == PROBLEM_RULE:
        return project.extensions is not None
    rt = runtime(project)
    return rt is not None and (rule_id in rt.decl_rules or rule_id in rt.plugin_rules)


def rule_source(project: Project, rule_id: str) -> Item | None:
    rt = runtime(project)
    return rt.registry.get(RULE, rule_id) if rt is not None else None


def explain(
    project: Project, rule_id: str, object_id: str, findings: list[Finding] | None = None
) -> list[Derivation]:
    """The derivation(s) behind an extension rule for one object (S1 form)."""
    rt = runtime(project)
    if rt is None:
        return []
    if rule_id in rt.decl_rules:
        d = rt.decl_rules[rule_id].derivation(project, object_id)
        return [d] if d is not None else []
    statements = [
        f.title
        for f in (findings if findings is not None else run_extension_rules(project))
        if f.rule == rule_id and f.object_id == object_id
    ]
    if rule_id in rt.plugin_rules:
        pr = rt.plugin_rules[rule_id]
        item = rt.registry.get(RULE, rule_id)
        extra = ""
        if pr.explain is not None:
            try:
                extra = pr.explain(project, object_id)
            except Exception as exc:
                extra = f"(the plug-in's explanation stopped with {type(exc).__name__})"
        inputs = [
            Input(
                "Statement of the finding" if k == 0 else f"Statement of the finding ({k + 1})",
                t,
                "",
                f"rule {rule_id}, object {object_id}",
            )
            for k, t in enumerate(statements)
        ]
        if extra:
            inputs.append(Input("The plug-in says", extra, "", f"plug-in {pr.plugin}"))
        ref = (
            f"Plug-in rule {rule_id} from plug-in {pr.plugin} (version {item.version if item else ''}, sha256 {(item.sha256 if item else '')[:12]}); "
            f"it is not part of the tool. Why it matters: {pr.rule.why} To fix it: {pr.rule.how}"
        )
        return [
            Derivation(
                "rule-check",
                f"Rule {rule_id} for {object_id}",
                pr.rule.topic,
                None,
                "",
                "this rule is a yes/no check: it compares "
                + pr.compares.removeprefix("it compares "),
                tuple(inputs),
                (),
                None,
                (),
                ref,
                text=statements[0] if statements else "no finding for this object today",
            )  # fmt: skip
        ]
    if rule_id == PROBLEM_RULE:
        listed = problems(project)
        inputs = [
            Input(
                "Not applied" if k == 0 else f"Not applied ({k + 1})",
                t,
                "",
                f"{FOLDER}/{ENABLED_FILE}",
            )
            for k, (_o, t) in enumerate(listed)
        ]
        return [
            Derivation(
                "rule-check",
                f"Rule {rule_id} for {object_id}",
                "Extensions not applied",
                None,
                "",
                "this rule is a yes/no check: it compares the extension files and plug-ins the project enables with what the tool could apply",
                tuple(inputs),
                (),
                None,
                (),
                "An extension that is enabled but not applied leaves its checks out of the report.",
                text=statements[0] if statements else "everything the project enables is applied",
            )  # fmt: skip
        ]
    return []


# ---- tables ---------------------------------------------------------------------------------------------


def tables_for(project: Project) -> tuple[list[tuple[str, Table]], list[str]]:
    """(name, rows) of every extension table, and the problems met while making them."""
    rt = runtime(project)
    if rt is None:
        return [], []
    out: list[tuple[str, Table]] = []
    notes: list[str] = []
    for name, build in rt.tables:
        rows, problems_ = build(project)
        out.append((name, rows))
        notes += [f"{name}: {p}" for p in problems_]
    return out, notes


def table_files(
    project: Project, stamp: object, csv_bytes: Callable[[Table, object], bytes]
) -> dict[str, bytes]:
    """The files `export` adds for the extension tables: `system/extensions/<name>.csv`."""
    tables, _notes = tables_for(project)
    return {f"{TABLE_FOLDER}/{name}.csv": csv_bytes(rows, stamp) for name, rows in tables}


def provenance(project: Project) -> list[dict[str, object]]:
    """What the extensions of the project are, for the provenance file and the run record: every
    enabled declarative file (name, version, hash) and every loaded plug-in (name, version, hash),
    in a fixed order. Empty for a project without enabled extensions."""
    ext: ProjectExtensions | None = project.extensions
    if ext is None:
        return []
    rows: list[dict[str, object]] = []
    for f in ext.files:
        if f.status == "applied":
            rows.append(
                {
                    "name": f.name,
                    "version": f.version,
                    "kind": "declarative",
                    "file": f.rel,
                    "sha256": f.sha256,
                }
            )
    for p in ext.plugins:
        if p.state == plugins_mod.LOADED:
            rows.append(
                {
                    "name": p.name,
                    "version": p.version,
                    "kind": "plugin",
                    "file": p.where,
                    "sha256": p.sha256,
                }
            )
    return sorted(rows, key=lambda r: (str(r["kind"]), str(r["name"])))


def loaded(project: Project | None = None) -> list[tuple[str, str, str, str]]:
    """(name, version, kind, sha256) of the extensions in force: for a project, its enabled
    declarative files and its loaded plug-ins; without one, every plug-in loaded in this process.
    The run record keeps this list (S5)."""
    if project is not None:
        return [
            (str(r["name"]), str(r["version"]), str(r["kind"]), str(r["sha256"]))
            for r in provenance(project)
        ]
    return sorted(
        (name, "", PLUGIN, sha)
        for (name, sha), done in plugins_mod._LOADED.items()
        if not done.problem
    )


# ---- the listing (the `extensions` command, the Help page, `api.list_extensions`) -------------------------


def listing(project: Project) -> dict[str, Any]:
    """Everything registered for a project and where it stands, as plain data in a fixed order:
    the built-in items and the extension items of the project together (`items`), the declarative
    files (`files`), the Python plug-ins (`plugins`) and the problems met (`issues`). No time and no
    absolute path."""
    builtins.install()
    ext: ProjectExtensions | None = project.extensions
    rt = runtime(project)
    registry = rt.registry if rt is not None else REGISTRY
    items: list[dict[str, Any]] = []
    trusted_by_plugin = {p.name: p.trusted for p in ext.plugins} if ext is not None else {}
    for item in registry.items():
        row = item.to_dict()
        row["enabled"] = True
        row["trusted"] = (
            trusted_by_plugin.get(item.origin, False)
            if item.source == PLUGIN
            else (True if item.source == "built-in" else None)
        )
        items.append(row)
    if ext is not None:  # what the files offer that the project does not use (yet)
        off = {f.rel for f in ext.files if f.status == "disabled"}
        for spec in ext.parsed:
            if spec.rel not in off:
                continue
            for r in spec.rules:
                items.append(
                    {
                        "kind": RULE,
                        "name": r.id,
                        "version": spec.version,
                        "source": DECLARATIVE,
                        "origin": spec.rel,
                        "sha256": spec.sha256,
                        "doc": r.title,
                        "enabled": False,
                        "trusted": None,
                    }
                )
            for t in spec.tables:
                items.append(
                    {
                        "kind": TABLE,
                        "name": t.name,
                        "version": spec.version,
                        "source": DECLARATIVE,
                        "origin": spec.rel,
                        "sha256": spec.sha256,
                        "doc": t.title,
                        "enabled": False,
                        "trusted": None,
                    }
                )
    return {
        "has_folder": ext is not None,
        "enabled_declarative": list(ext.enabled_files) if ext else [],
        "enabled_plugins": list(ext.enabled_plugins) if ext else [],
        "files": [
            {
                "file": f.rel,
                "name": f.name,
                "version": f.version,
                "sha256": f.sha256,
                "enabled": f.enabled,
                "status": f.status,
                "rules": f.rules,
                "tables": f.tables,
                "lookups": f.lookups,
            }
            for f in (ext.files if ext else ())
        ],
        "plugins": [
            {
                "name": p.name,
                "version": p.version,
                "kinds": list(p.kinds),
                "source": p.source,
                "where": p.where,
                "sha256": p.sha256,
                "lines": p.lines,
                "enabled": p.enabled,
                "trusted": p.trusted,
                "state": p.state,
                "message": p.message,
            }
            for p in (ext.plugins if ext else ())
        ],
        "items": items,
        "issues": [i.to_dict() for i in (ext.issues if ext else ())],
    }


def rules_markdown(project: Project) -> str:
    """The rules of the project's extensions as a Markdown page, in the form of `docs/RULES.md`: one
    row for each rule with its severity, what it applies to, the condition (a data file) or what it
    compares (a plug-in), why, how to fix, the requirement IDs and where it comes from. Empty rows
    when the project enables no extension rule."""
    rt = runtime(project)
    lines = [
        "# Rules of the extensions",
        "",
        "These rules are not part of the tool. They come from the extensions this project enables,"
        " each with the file or plug-in, its version and its SHA-256.",
        "",
        "| Rule | Severity | Applies to | Condition or comparison | Why it matters | How to fix | Requirements | Source |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if rt is None:
        return "\n".join(lines) + "\n"
    from . import expr

    def cell(text: str) -> str:
        return text.replace("|", "\\|").replace("\n", " ")

    for rule in rt.rules:
        item = rt.registry.get(RULE, rule.id)
        cited = ", ".join(f"`{x}`" for x in rule.sources) or "none"
        waive = "waivable" if rule.can_waive else "not waivable"
        src = f"{item.origin}, version {item.version}, sha256 `{item.sha256[:12]}`" if item else ""
        if rule.id in rt.decl_rules:
            spec = rt.decl_rules[rule.id].spec
            what = (
                "`"
                + expr.render(spec.condition)
                + "`"
                + (f", where `{expr.render(spec.when)}`" if spec.when else "")
            )
            applies = spec.applies_to
        else:
            what = "(code) " + rt.plugin_rules[rule.id].compares
            applies = "see the plug-in"
        lines.append(
            f"| `{rule.id}` | {rule.severity} ({waive}) | {applies} | {cell(what)} | {cell(rule.why)} | {cell(rule.how)} | {cited} | {cell(src)} |"
        )
    return "\n".join(lines) + "\n"
