# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Python plug-ins: finding them, saying what they are, and loading the ones that may be loaded.

Two places are searched, and nothing is executed to search them:

* the folder `<project>/extensions/plugins/` (one `.py` file for each plug-in), and
* installed packages that declare an entry point in the group `harness_design_studio.plugins`
  (the entry point names the plug-in's module).

For each, the tool computes the SHA-256 of the code and reads the declaration `PLUGIN = {...}` from
the source text with `ast.literal_eval` (no code runs). A plug-in is **imported** only if all of this
holds, checked here and nowhere else:

1. the project lists its name in `extensions/enabled.json`;
2. the user trusted that exact code (name and hash) in the trust store of the user's settings
   folder (`trust.py`); and
3. its declaration is valid and names the API version this tool has; and
4. Python plug-ins are not switched off on this computer (`policy.py`: the machine-wide policy file
   or the environment variable `HARNESS_DESIGN_STUDIO_NO_PLUGINS`). This is asked here and again in
   `load`, the one place that imports a plug-in.

Anything else is listed with the reason it was not loaded. The file that is hashed is the file that
runs: the loader below is handed the bytes that were hashed, so a change between the check and the
import cannot run other code, and no cached bytecode is ever used for a plug-in.

A trusted plug-in runs with the rights of the person who trusted it. This module is a gate, not a
sandbox.
"""

import ast
import hashlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import importlib.util
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

from . import policy, trust
from .pluginapi import PluginApi
from .registry import PLUGIN_API_VERSION, PLUGIN_KINDS, Item, Registry, RegistryError

ENTRY_POINT_GROUP = "harness_design_studio.plugins"
PLUGIN_DIR = "extensions/plugins"
MAX_SOURCE_BYTES = 2 * 1024 * 1024

PROJECT = "project"
INSTALLED = "entry-point"

# the states of a plug-in, in the words of the listing
LOADED = "loaded"
DISABLED = "disabled"  # the project does not enable it
UNTRUSTED = "untrusted"  # enabled, but the user has not trusted this code
FAILED = "failed"  # enabled and trusted, but it could not be loaded
INVALID = "invalid"  # no usable declaration: it cannot be trusted or loaded
BLOCKED = "blocked"  # Python plug-ins are switched off on this computer (policy.py)


@dataclass(frozen=True)
class Candidate:
    """A plug-in as found on disk, before anything is run."""

    name: str
    version: str
    kinds: tuple[str, ...]
    api: int
    source: str  # PROJECT or INSTALLED
    where: str  # "extensions/plugins/x.py" or "package-name 1.2"
    sha256: str
    lines: int
    description: str = ""
    problem: str = ""  # why it is not usable ("" when it is)
    locator: str = ""  # for INSTALLED: "dist-name|entry-point-name"; for PROJECT: the file name

    @property
    def usable(self) -> bool:
        return not self.problem


@dataclass(frozen=True)
class PluginInfo:
    """A candidate with what the project and the user say about it."""

    name: str
    version: str
    kinds: tuple[str, ...]
    source: str
    where: str
    sha256: str
    lines: int
    description: str
    enabled: bool
    trusted: bool
    state: str
    message: str = ""
    api: int = PLUGIN_API_VERSION
    locator: str = ""


# ---- reading what a plug-in is without running it ----------------------------------------------------


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def declaration(source: str) -> tuple[dict[str, object] | None, str]:
    """The literal `PLUGIN = {...}` of a module's source and the reason it is not usable. The source
    is parsed, never executed."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError) as exc:
        return None, f"the source cannot be read as Python ({type(exc).__name__})"
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "PLUGIN" for t in node.targets
        ):
            try:
                value = ast.literal_eval(node.value)
            except ValueError, SyntaxError, TypeError, MemoryError, RecursionError:
                return (
                    None,
                    "PLUGIN must be a literal (a dict of text, numbers and lists), not a computed value",
                )
            if not isinstance(value, dict):
                return None, "PLUGIN must be a dict"
            return value, ""
    return None, "the module has no PLUGIN declaration"


_NAME = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")


def candidate_from_source(
    data: bytes,
    *,
    source: str,
    where: str,
    locator: str,
    fallback_name: str = "",
    fallback_version: str = "",
) -> Candidate:
    """What a plug-in file says it is."""
    sha = sha256_bytes(data)
    lines = data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)
    problem = ""
    decl: dict[str, object] | None = None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
        problem = "the source is not UTF-8 text"
    if not problem and len(data) > MAX_SOURCE_BYTES:
        problem = f"the source is larger than {MAX_SOURCE_BYTES // 2**20} MB"
    if not problem:
        decl, problem = declaration(text)
    name = fallback_name
    version = fallback_version
    kinds: tuple[str, ...] = ()
    api = 0
    description = ""
    if decl is not None and not problem:
        name = str(decl.get("name", ""))
        version = str(decl.get("version", ""))
        raw_kinds = decl.get("kinds")
        api_raw = decl.get("api")
        description = str(decl.get("description", ""))
        if not _NAME.match(name):
            problem = "PLUGIN['name'] must be lower-case letters, digits, '-' and '_' (at most 48)"
        elif not version.strip():
            problem = "PLUGIN['version'] is missing"
        elif not (
            isinstance(raw_kinds, list)
            and raw_kinds
            and all(isinstance(k, str) and k in PLUGIN_KINDS for k in raw_kinds)
        ):
            problem = f"PLUGIN['kinds'] must be a list of {', '.join(PLUGIN_KINDS)}"
        elif not isinstance(api_raw, int) or isinstance(api_raw, bool):
            problem = "PLUGIN['api'] (the plug-in API version) is missing"
        elif api_raw != PLUGIN_API_VERSION:
            problem = f"the plug-in is written for API version {api_raw}; this tool has {PLUGIN_API_VERSION}"
        if isinstance(raw_kinds, list):
            kinds = tuple(str(k) for k in raw_kinds)
        api = api_raw if isinstance(api_raw, int) and not isinstance(api_raw, bool) else 0
    return Candidate(
        name or fallback_name, version, kinds, api, source, where, sha, lines, description,
        problem, locator,
    )  # fmt: skip


def project_candidates(root: Path) -> list[Candidate]:
    """The `.py` files of `<project>/extensions/plugins/`, sorted by name. Links are not followed."""
    folder = root / PLUGIN_DIR
    out: list[Candidate] = []
    if not folder.is_dir():
        return out
    for path in sorted(folder.glob("*.py"), key=lambda p: p.name):
        rel = f"{PLUGIN_DIR}/{path.name}"
        if path.is_symlink() or not path.is_file():
            out.append(
                Candidate(
                    path.stem,
                    "",
                    (),
                    0,
                    PROJECT,
                    rel,
                    "",
                    0,
                    problem="a link is not followed: plug-ins must be real files in the project",
                    locator=path.name,
                )
            )
            continue
        try:
            data = path.read_bytes()
        except OSError as exc:
            out.append(
                Candidate(
                    path.stem,
                    "",
                    (),
                    0,
                    PROJECT,
                    rel,
                    "",
                    0,
                    problem=f"the file could not be read ({exc.strerror})",
                    locator=path.name,
                )
            )
            continue
        out.append(
            candidate_from_source(
                data, source=PROJECT, where=rel, locator=path.name, fallback_name=path.stem
            )
        )
    return out


def _dist_sources(dist: importlib.metadata.Distribution) -> list[tuple[str, bytes]]:
    """(path inside the distribution, bytes) of its Python files, sorted by path."""
    rows: list[tuple[str, bytes]] = []
    for f in dist.files or []:
        if f.suffix != ".py":
            continue
        try:
            rows.append((f.as_posix(), Path(str(dist.locate_file(f))).read_bytes()))
        except OSError:
            continue
    return sorted(rows)


def distribution_hash(rows: list[tuple[str, bytes]]) -> str:
    """One hash of a distribution's Python files: their paths and the hash of each, in path order."""
    h = hashlib.sha256()
    for rel, data in rows:
        h.update(rel.encode() + b"\0" + sha256_bytes(data).encode() + b"\n")
    return h.hexdigest()


def installed_candidates(search_path: list[str] | None = None) -> list[Candidate]:
    """Plug-ins of installed packages (entry point group `harness_design_studio.plugins`)."""
    out: list[Candidate] = []
    try:
        eps = (
            importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
            if search_path is None
            else [
                ep
                for d in importlib.metadata.distributions(path=search_path)
                for ep in d.entry_points
                if ep.group == ENTRY_POINT_GROUP
            ]
        )
    except Exception:  # a damaged installation must not stop the tool
        return out
    seen: set[tuple[str, str]] = set()
    for ep in sorted(eps, key=lambda e: (e.name, e.value)):
        dist = getattr(ep, "dist", None)
        dist_name = dist.metadata["Name"] if dist is not None else ""
        if (dist_name, ep.name) in seen:
            continue
        seen.add((dist_name, ep.name))
        where = f"{dist_name} {dist.version}" if dist is not None else ep.value
        locator = f"{dist_name}|{ep.name}"
        if dist is None:
            out.append(
                Candidate(
                    ep.name,
                    "",
                    (),
                    0,
                    INSTALLED,
                    where,
                    "",
                    0,
                    problem="the package that declares it cannot be found",
                    locator=locator,
                )
            )
            continue
        rows = _dist_sources(dist)
        if not rows:
            out.append(
                Candidate(
                    ep.name,
                    dist.version,
                    (),
                    0,
                    INSTALLED,
                    where,
                    "",
                    0,
                    problem="the package lists no Python files the tool can read, so no hash of its code can be made",
                    locator=locator,
                )
            )
            continue
        module = ep.value.split(":")[0].strip()
        rel = module.replace(".", "/")
        main = next((d for p, d in rows if p in (f"{rel}.py", f"{rel}/__init__.py")), None)
        sha = distribution_hash(rows)
        lines = sum(d.count(b"\n") for _p, d in rows)
        if main is None:
            out.append(
                Candidate(
                    ep.name,
                    dist.version,
                    (),
                    0,
                    INSTALLED,
                    where,
                    sha,
                    lines,
                    problem=f"the module {module} is not among the package's files",
                    locator=locator,
                )
            )
            continue
        cand = candidate_from_source(
            main,
            source=INSTALLED,
            where=where,
            locator=locator,
            fallback_name=ep.name,
            fallback_version=dist.version,
        )
        problem = cand.problem
        if not problem and cand.name != ep.name:
            problem = f"PLUGIN['name'] ({cand.name}) is not the name of the entry point ({ep.name})"
        out.append(
            Candidate(
                cand.name,
                cand.version,
                cand.kinds,
                cand.api,
                INSTALLED,
                where,
                sha,
                lines,
                cand.description,
                problem,
                locator,
            )
        )
    return out


# ---- the gate ---------------------------------------------------------------------------------------


def info_for(c: Candidate, enabled: set[str]) -> PluginInfo:
    """The state of a candidate: loaded states are filled in by `load`."""
    is_enabled = c.name in enabled
    trusted = bool(c.sha256) and trust.is_trusted(c.name, c.sha256)
    blocked = policy.plugins_blocked()
    if not c.usable:
        state, message = INVALID, c.problem
    elif blocked:
        state, message = BLOCKED, blocked
    elif not is_enabled:
        state, message = DISABLED, "the project does not enable it"
    elif not trusted:
        state = UNTRUSTED
        message = (
            "enabled by the project, but this code is not trusted on this computer; "
            f"it was not loaded (harness-design-studio trust DIR {c.name})"
        )
    else:
        state, message = "ready", ""
    return PluginInfo(
        c.name, c.version, c.kinds, c.source, c.where, c.sha256, c.lines, c.description,
        is_enabled, trusted, state, message, c.api, c.locator,
    )  # fmt: skip


@dataclass
class Loaded:
    name: str
    sha256: str
    items: list[Item] = field(default_factory=list)
    problem: str = ""


_LOADED: dict[tuple[str, str], Loaded] = {}  # (name, sha256) -> what the plug-in registered


class _VerifiedLoader(importlib.abc.SourceLoader):
    """Runs exactly the bytes that were hashed. It has no bytecode cache: a `__pycache__` file that
    came with a cloned project is never used."""

    def __init__(self, fullname: str, path: str, data: bytes) -> None:
        self._fullname, self._path, self._data = fullname, path, data

    def get_filename(self, fullname: str) -> str:
        return self._path

    def get_data(self, path: str) -> bytes:
        return self._data


def _module_name(name: str) -> str:
    return "hds_plugin_" + re.sub(r"[^a-z0-9_]", "_", name)


def _import_project(c: Candidate, root: Path) -> ModuleType:
    path = root / PLUGIN_DIR / c.locator
    data = path.read_bytes()
    if sha256_bytes(data) != c.sha256:
        raise RegistryError("the file changed after it was checked; it was not loaded")
    modname = _module_name(c.name)
    loader = _VerifiedLoader(modname, str(path), data)
    spec = importlib.util.spec_from_loader(modname, loader, origin=str(path))
    if spec is None:
        raise RegistryError("the file cannot be loaded as a module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[modname] = module
    try:
        loader.exec_module(module)
    except BaseException:
        sys.modules.pop(modname, None)
        raise
    return module


def _dist_name(ep: importlib.metadata.EntryPoint) -> str:
    dist = getattr(ep, "dist", None)
    return str(dist.metadata["Name"]) if dist is not None else ""


def _import_installed(c: Candidate, search_path: list[str] | None) -> ModuleType:
    dist_name, _, ep_name = c.locator.partition("|")
    candidates = [
        ep
        for ep in (
            importlib.metadata.entry_points(group=ENTRY_POINT_GROUP)
            if search_path is None
            else [
                e
                for d in importlib.metadata.distributions(path=search_path)
                for e in d.entry_points
                if e.group == ENTRY_POINT_GROUP
            ]
        )
        if ep.name == ep_name and _dist_name(ep) == dist_name
    ]
    if not candidates:
        raise RegistryError("the entry point is gone")
    dist = candidates[0].dist
    if dist is None or distribution_hash(_dist_sources(dist)) != c.sha256:
        raise RegistryError("the package changed after it was checked; it was not loaded")
    module = candidates[0].load()
    if not isinstance(module, ModuleType):
        raise RegistryError("the entry point must name a module")
    return module


def load(c: Candidate, root: Path | None, search_path: list[str] | None = None) -> Loaded:
    """Import a plug-in that passed the gate and let it register. Never raises: the result says what
    went wrong. The caller must have checked enabled and trusted. While Python plug-ins are switched
    off on this computer nothing is imported, and nothing loaded earlier in this process is handed
    out."""
    blocked = policy.plugins_blocked()
    if blocked:
        return Loaded(c.name, c.sha256, [], blocked)
    key = (c.name, c.sha256)
    if key in _LOADED:
        return _LOADED[key]
    result = Loaded(c.name, c.sha256)
    try:
        module = (
            _import_project(c, root)
            if c.source == PROJECT and root is not None
            else _import_installed(c, search_path)
        )
        decl = getattr(module, "PLUGIN", None)
        register = getattr(module, "register", None)
        if (
            not isinstance(decl, dict)
            or decl.get("name") != c.name
            or decl.get("version") != c.version
        ):
            raise RegistryError(
                "PLUGIN in the running module is not the one that was read from its source"
            )
        if not callable(register):
            raise RegistryError("the module has no register(api) function")
        staging = Registry()
        register(PluginApi(c.name, c.version, c.sha256, staging))
        allowed = set(c.kinds)
        for item in staging.items():
            if item.kind not in allowed:
                raise RegistryError(
                    f"it registered a {item.kind} ('{item.name}') but declares only {', '.join(c.kinds)}"
                )
            result.items.append(item)
        if not result.items:
            raise RegistryError("it registered nothing")
    except BaseException as exc:  # a plug-in may raise anything; none of it may stop the tool
        if isinstance(exc, KeyboardInterrupt | SystemExit):
            raise
        result.items = []
        result.problem = (
            f"{type(exc).__name__}: {str(exc)[:300]}"
            if not isinstance(exc, RegistryError)
            else str(exc)
        )
    _LOADED[key] = result
    return result


def forget_loaded() -> None:
    """Drop what was loaded (tests; `Reload` in the editor)."""
    _LOADED.clear()
