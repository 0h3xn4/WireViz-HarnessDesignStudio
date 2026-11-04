"""`--json`: the result of a command as one JSON document on the standard output.

A command that has a result in data form takes `--json`. With it the usual text lines are not
printed; one JSON document is, with the same exit code as without it. Messages about a command that
could not run at all (a project that cannot be read, a wrong option) still go to the standard error
as text, and then nothing is printed to the standard output. The document is deterministic: it has
no time, no user name and no absolute path, lists are in a fixed order, and the same design gives
the same bytes. `SHAPES` says what each command's document holds; `docs/CLI.md` is made from it.
"""

import argparse
import json
from typing import Any

# command -> the keys of the document the command prints with --json (in this order). A test runs
# every command with --json and compares.
SHAPES: dict[str, tuple[str, ...]] = {
    "new": ("ok", "name", "template", "devices", "interfaces"),
    "new --list": ("ok", "templates"),
    "templates": ("ok", "count", "files"),
    "schema": ("ok", "count", "files"),
    "validate": (
        "ok", "devices", "interfaces", "connectors", "harnesses", "errors", "warnings", "issues",
    ),
    "check": (
        "ok", "devices", "interfaces", "connectors", "harnesses", "errors", "warnings", "issues",
    ),
    "drc": (
        "ok", "model_hash", "rules_run", "open_errors", "open_warnings", "open_notes", "waived",
        "placeholder_config", "findings",
    ),
    "verify": ("ok", "interfaces_checked", "wires_checked", "stale", "issues"),
    "settings": ("settings", "definitions", "assumptions"),  # no "ok": printed as before
    "settings --annotate": ("ok", "action", "files", "unchanged", "changed"),
    "explain --all": ("ok", "count", "without_value", "files"),  # with OBJECT: a list
    "export-data": ("ok", "count", "model_hash", "files", "run_record"),
    "generate": (
        "ok", "saved", "added", "changed", "unchanged", "removed", "frozen", "kept_locks",
        "findings", "interfaces_checked", "wires_checked", "verify_issues",
    ),
    "export": (
        "ok", "written", "blocked", "model_hash", "drawings_removed", "file_count", "files",
        "issues",
    ),
    "merge-fix": ("ok", "result", "conflicts", "problem", "generate", "check"),
    "config": (
        "ok", "set_count", "total", "values", "problems", "placeholder_files",
        "waiting_for_decision", "counterpart_pairs", "release_distinct_roles", "comment_warnings",
        "changes",
    ),
    "library": ("ok", "name", "version", "source", "date", "changed"),
    "import-parts": ("ok", "dry_run", "changed", "ready", "problems", "rows", "library", "import"),
    "import-lengths": ("ok", "dry_run", "changed", "ready", "problems", "hint", "rows", "import"),
    "import-build-data": ("ok", "dry_run", "changed", "kind", "counts", "rows", "import"),
    "import-netlist": (
        "ok", "dry_run", "changed", "rows", "warnings", "unmatched_signals", "import",
    ),
    "import-pinout": (
        "ok", "dry_run", "changed", "connectors", "pins", "rows", "warnings", "unmatched_signals",
        "import",
    ),
    "import-devices": ("ok", "dry_run", "changed", "rows", "notes", "import"),
    "import-devices --list": ("ok", "devices"),
    "import-subsystem": (
        "ok", "dry_run", "changed", "name", "connections", "rows", "notes", "import",
    ),
    "imports": ("ok", "records_file", "count", "sources_changed", "imports"),
    "import-subsystem --show": (
        "ok", "name", "description", "devices", "connectors", "connections", "device_list",
    ),
    "export-pinout": ("ok", "device", "pin_rows", "columns", "rows", "written"),
    "export-devices": ("ok", "devices", "connectors", "notes"),
    "export-subsystem": ("ok", "name", "devices", "connectors", "connections"),
    "review": ("ok", "action", "by", "blockers", "outputs"),
    "release": ("ok", "action", "by", "blockers", "outputs"),
    "revise": ("ok", "action", "by", "blockers", "outputs"),
    "diff": ("ok", "harness", "from", "to", "added", "removed", "changed", "changes"),
    "compare": ("ok", "added", "removed", "changed", "changes", "not_compared"),
    "log": ("ok", "harness", "entries"),
    "migrate": ("ok", "migrated"),
    "journal": ("ok", "has_journal", "count", "entries"),
    "journal --start": ("ok", "started", "file"),
    "override": ("ok", "wire", "action", "changed", "overrides", "derivation"),
    "deviation": ("ok", "action", "finding", "count", "deviations"),
    "workflow": ("ok", "steps"),
    "asbuilt": (
        "ok", "records", "complete", "missing", "out_of_limit", "within_limit", "not_compared",
        "differs_from_design", "stale_records", "harnesses", "lines",
    ),
    "import-asbuilt": ("ok", "dry_run", "changed", "counts", "rows", "import"),
    "export-asbuilt": ("ok", "rows", "columns", "written"),
    "extensions": (
        "ok", "has_folder", "enabled_declarative", "enabled_plugins", "files", "plugins", "items",
        "issues",
    ),
    "trust": ("ok", "action", "name", "version", "sha256", "lines", "where", "trusted", "changed"),
    "import-plugin": ("ok", "dry_run", "changed", "importer", "rows", "notes"),
}  # fmt: skip

JSON_HELP = (
    "print the result as one JSON document instead of text (same exit code; "
    "no time, user name or absolute path in it)"
)


def add_json_flag(parser: argparse.ArgumentParser) -> None:
    """The `--json` option, worded the same for every command."""
    parser.add_argument("--json", action="store_true", help=JSON_HELP)


def dumps(doc: dict[str, Any]) -> str:
    """The text of a document: indented, in the order the command built it, UTF-8 as it is."""
    return json.dumps(doc, indent=2, ensure_ascii=False)


class Report:
    """Where a command puts its result: text lines on the standard output (the default), or, with
    `--json`, the keys of one document. `say` prints in the first case and is silent in the second,
    so a command writes its text once and its data once, and neither can change the other."""

    def __init__(self, as_json: bool = False) -> None:
        self.as_json = as_json
        self.doc: dict[str, Any] = {}

    def say(self, text: str = "", **kwargs: Any) -> None:
        if not self.as_json:
            print(text, **kwargs)

    def put(self, **keys: Any) -> None:
        """Add keys to the document (ignored, not even built, in text mode by the callers' `if`)."""
        self.doc.update(keys)

    def result(self, code: int) -> dict[str, Any]:
        """The document with `ok` first: true when the exit code is 0."""
        return {"ok": code == 0, **{k: v for k, v in self.doc.items() if k != "ok"}}

    def finish(self, code: int) -> int:
        """Print the document when the command made one; the exit code is the command's own."""
        if self.as_json and self.doc:
            print(dumps(self.result(code)))
        return code
