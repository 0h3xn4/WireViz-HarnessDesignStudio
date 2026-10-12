"""Build, write and check the output set. `build_outputs` is pure: the same model gives the same
bytes. `outputs_status` compares a folder with the current model (stale detection)."""

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from harness_design_studio.core import checks, drc
from harness_design_studio.core.drc.report import render_markdown
from harness_design_studio.core.errors import HarnessError, SaveError
from harness_design_studio.core.io.fs import atomic_write_bytes, escapes_root
from harness_design_studio.core.model import Harness, Project
from harness_design_studio.core.vcs.hashing import content_hash
from harness_design_studio.core.vcs.report import changelog_rows, revision_report

from . import drawing, exports, system, tables
from .canvas import SHEETS, Sheet, to_pdf, to_svg
from .provenance import provenance_bytes
from .stamp import Stamp, Table, csv_bytes, stamp_of

MANIFEST = "manifest.json"
FORMAT = "harness-design-studio-outputs"
FORMAT_VERSION = 1
DEFAULT_FOLDER = "outputs"


class OutputsCancelled(HarnessError):
    """The user cancelled; nothing was written."""


@dataclass
class OutputSet:
    stamp: Stamp
    files: dict[str, bytes] = field(default_factory=dict)

    def manifest(self, project: Project) -> bytes:
        doc = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "generator_version": self.stamp.version,
            "model_hash": self.stamp.model_hash,
            "content_hash": content_hash(project),
            "placeholder_config": sorted(n for n, c in project.config.items() if c.placeholder),
            "files": [
                {"path": p, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
                for p, b in sorted(self.files.items())
            ],
        }
        return (json.dumps(doc, indent=1, sort_keys=True) + "\n").encode()


def _drawing_files(
    project: Project, h: Harness, stamp: Stamp, out: dict[str, bytes], sizes: tuple[str, ...]
) -> None:
    base = f"harnesses/{h.id}"
    for size in sizes:
        sheets = drawing.harness_sheets(project, h, stamp, size)
        out[f"{base}/drawing_{size}.pdf"] = to_pdf(sheets, f"{h.id} {h.name}", stamp.line)
        if size == "A3":
            for n, sh in enumerate(sheets, start=1):
                out[f"{base}/drawing_A3_s{n}.svg"] = to_svg(sh, stamp.line)


def _sheet_files(sheet: Sheet, base: str, stamp: Stamp, out: dict[str, bytes]) -> None:
    out[f"{base}.svg"] = to_svg(sheet, stamp.line)
    out[f"{base}.pdf"] = to_pdf([sheet], sheet.title, stamp.line)


def findings_table(project: Project) -> Table:
    found = sorted(
        [*checks.find(project), *drc.run(project)],
        key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f.severity], f.id),
    )
    rows = [
        [
            "Finding",
            "Rule",
            "Severity",
            "Object",
            "Statement",
            "Waived",
            "Justification",
            "Requirement",
        ]
    ]
    for f in found:
        rows.append(
            [
                f.id,
                f.rule,
                f.severity,
                f.object_id,
                f.title,
                "yes" if f.waiver else "",
                f.waiver.justification if f.waiver else "",
                " ".join(f.sources),
            ]
        )
    return rows


def build_outputs(
    project: Project,
    *,
    sizes: tuple[str, ...] = ("A4", "A3"),
    harness_ids: list[str] | None = None,
    cancel: Callable[[], bool] | None = None,
    progress: Callable[[float, str], None] | None = None,
) -> OutputSet:
    tables.clear_cache()
    stamp = stamp_of(project)
    result = OutputSet(stamp)
    out = result.files
    chosen = [
        project.harnesses[i]
        for i in sorted(harness_ids if harness_ids is not None else project.harnesses)
    ]
    for n, h in enumerate(chosen):
        if cancel is not None and cancel():
            raise OutputsCancelled("Export was cancelled. Nothing was written.")
        if progress is not None:
            progress(0.9 * n / max(1, len(chosen)), f"Harness {h.id}")
        base = f"harnesses/{h.id}"
        wl, po = tables.wire_list(project, h), tables.pinouts(project, h)
        bm, ts, lb = tables.bom(project, [h]), tables.tests(project, h), tables.labels(project, h)
        ml = tables.mass_length(project, [h])
        out[f"{base}/wirelist.csv"] = csv_bytes(wl, stamp)
        out[f"{base}/pinouts.csv"] = csv_bytes(po, stamp)
        out[f"{base}/bom.csv"] = csv_bytes(bm, stamp)
        out[f"{base}/mass_length.csv"] = csv_bytes(ml, stamp)
        out[f"{base}/tests.csv"] = csv_bytes(ts, stamp)
        out[f"{base}/labels.csv"] = csv_bytes(lb, stamp)
        out[f"{base}/wireviz.yaml"] = exports.wireviz_yaml(project, h, stamp)
        out[f"{base}/{h.id}.xlsx"] = exports.xlsx_bytes(
            {
                "Wire list": wl,
                "Pinouts": po,
                "BOM": bm,
                "Mass and length": ml,
                "Tests": ts,
                "Labels": lb,
            },
            stamp,
        )
        _drawing_files(project, h, stamp, out, sizes)
    if progress is not None:
        progress(0.92, "System outputs")
    bom_all = tables.bom(project, chosen)
    mass_all = tables.mass_length(project, chosen)
    mating, trace, boxes = (
        tables.mating_matrix(project),
        tables.traceability(project),
        tables.box_pinouts(project),
    )
    out["system/bom.csv"] = csv_bytes(bom_all, stamp)
    out["system/mass_length.csv"] = csv_bytes(mass_all, stamp)
    out["system/mating_matrix.csv"] = csv_bytes(mating, stamp)
    out["system/traceability.csv"] = csv_bytes(trace, stamp)
    out["system/box_pinouts.csv"] = csv_bytes(boxes, stamp)
    findings = findings_table(project)
    out["system/drc_findings.csv"] = csv_bytes(findings, stamp)
    out["system/drc_report.md"] = (f"<!-- {stamp.line} -->\n" + render_markdown(project)).encode()
    out["system/changelog.csv"] = csv_bytes(changelog_rows(project), stamp)
    out["system/revision_report.md"] = revision_report(project, stamp.line).encode()
    out["system/export.json"] = exports.json_export(project, stamp)
    out["system/provenance.json"] = provenance_bytes(project, stamp)
    out["system/system.xlsx"] = exports.xlsx_bytes(
        {"BOM": bom_all, "Mass and length": mass_all, "Mating matrix": mating, "Traceability": trace,
         "Box pinouts": boxes, "DRC findings": findings, "Change log": changelog_rows(project)}, stamp
    )  # fmt: skip
    _sheet_files(system.block_diagram(project, stamp), "system/block_diagram", stamp, out)
    _sheet_files(system.harness_overview(project, stamp), "system/harness_overview", stamp, out)
    return result


def _safe_rel(rel: str) -> bool:
    p = Path(rel)
    return not p.is_absolute() and ".." not in p.parts and rel != MANIFEST


def write_outputs(
    project: Project, folder: Path | str, result: OutputSet | None = None
) -> OutputSet:
    """Write the set into `folder` (created if needed). Only files listed in the previous manifest
    are ever deleted; anything else in the folder is left alone."""
    root = Path(folder)
    result = result or build_outputs(project)
    old = _read_manifest(root)
    # never write through a link: it could lead anywhere on the disk
    top = {rel.split("/", 1)[0] for rel in result.files}
    if root.is_symlink() or any((root / t).is_symlink() for t in top):
        raise SaveError("The outputs folder (or a folder in it) is a link, so nothing was written.")
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SaveError(f"The outputs folder cannot be created ({exc.strerror}).") from exc
    # no file may be written or deleted behind a link at any depth: check them all first
    stale = [r for r in sorted(old.files if old else {}) if r not in result.files and _safe_rel(r)]
    for rel in (*result.files, *stale):
        target = root / rel
        if target.is_symlink() or escapes_root(root, target.parent):
            raise SaveError(
                f"'{rel}' lies behind a link that leads out of the outputs folder, so nothing "
                "was written."
            )
    try:
        for rel, data in sorted(result.files.items()):
            _atomic(root / rel, data, root)
        for rel in stale:
            (root / rel).unlink(missing_ok=True)
        _atomic(root / MANIFEST, result.manifest(project), root)
    except OSError as exc:
        raise SaveError(f"The outputs could not be written ({exc.strerror}).") from exc
    return result


def _atomic(path: Path, data: bytes, root: Path) -> None:
    atomic_write_bytes(path, data, backup=False, root=root, durable=False)


@dataclass(frozen=True)
class _Manifest:
    model_hash: str
    content_hash: str
    files: dict[str, str]  # path -> sha256


def _read_manifest(root: Path) -> _Manifest | None:
    path = root / MANIFEST
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text())
        files = {str(f["path"]): str(f["sha256"]) for f in doc["files"]}
        return _Manifest(str(doc["model_hash"]), str(doc.get("content_hash", "")), files)
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        return None


def outputs_content_state(project: Project, folder: Path | str) -> str:
    """ "none", "current" or "stale", comparing the design content (release bookkeeping ignored).
    The release gate uses this: outputs exported and reviewed before a release stay valid."""
    old = _read_manifest(Path(folder))
    if old is None:
        return "none"
    return "current" if old.content_hash == content_hash(project) else "stale"


def damaged_files(folder: Path | str) -> list[str] | None:
    """Files listed in the manifest that are missing or whose content changed since export.
    None if the manifest cannot be read."""
    root = Path(folder)
    old = _read_manifest(root)
    if old is None:
        return None
    bad = []
    for rel, digest in sorted(old.files.items()):
        path = root / rel
        if (
            not _safe_rel(rel)
            or not path.is_file()
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            bad.append(rel)
    return bad


def exported_harnesses(folder: Path | str) -> set[str] | None:
    """Harness IDs that have output files listed in the manifest (None if unreadable)."""
    old = _read_manifest(Path(folder))
    if old is None:
        return None
    return {
        rel.split("/")[1]
        for rel in old.files
        if rel.startswith("harnesses/") and rel.count("/") >= 2
    }


@dataclass(frozen=True)
class OutputStatus:
    state: str  # "none" | "current" | "stale" | "modified" | "unreadable"
    detail: str = ""


def outputs_status(project: Project, folder: Path | str, *, deep: bool = False) -> OutputStatus:
    """`deep` also hashes every file (slow for big sets); the quick check compares model hashes."""
    root = Path(folder)
    if not (root / MANIFEST).is_file():
        return OutputStatus("none", "No outputs have been exported yet.")
    old = _read_manifest(root)
    if old is None:
        return OutputStatus("unreadable", "The output manifest cannot be read; export again.")
    if old.model_hash != stamp_of(project).model_hash:
        return OutputStatus("stale", "The design changed after the outputs were exported.")
    bad = []
    for rel, digest in sorted(old.files.items() if deep else []):
        path = root / rel
        if (
            not _safe_rel(rel)
            or not path.is_file()
            or hashlib.sha256(path.read_bytes()).hexdigest() != digest
        ):
            bad.append(rel)
    if bad:
        return OutputStatus(
            "modified",
            f"{len(bad)} output file(s) were changed or removed after export: {', '.join(bad[:3])}",
        )
    return OutputStatus("current", "Outputs match the current design.")


__all__ = [
    "SHEETS",
    "OutputSet",
    "OutputStatus",
    "build_outputs",
    "outputs_status",
    "write_outputs",
]
