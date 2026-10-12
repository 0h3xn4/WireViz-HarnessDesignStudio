"""Review, release and new-revision workflow.

A release needs a comment, a name, and a design that passes the gate: no verifier or rule
errors for the harness, harness plans current, every wire sized and measured, outputs that
were exported from the current design, and engineering values that a person has reviewed (no
configuration file marked as a placeholder) and parts that are approved (D-136). A release on
placeholders or with parts that are not approved is possible only with a written reason, which is
kept in the change log and the baseline (D-135). It writes a baseline (a frozen snapshot) and a change log
entry, and locks the harness (see `locks`). The only way to change it afterwards is a new
revision, which keeps the old baseline.
"""

import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from harness_design_studio.core import drc
from harness_design_studio.core.commands import Op, Put
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.generate.engine import generation_status
from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.model import Baseline, ChangeEntry, Harness, Project, evolve
from harness_design_studio.core.model.review import ChangeKind
from harness_design_studio.core.verify import verify_project

from .consistency import release_integrity
from .hashing import content_hash
from .snapshot import carried_interfaces, normalize, related_ids, snapshot_for

MIN_COMMENT = 10
MAX_COMMENT = 2000  # the baseline keeps the comment; its limit is in core/model/review.py
DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")  # ASCII digits only


def valid_date(text: str) -> bool:
    """A real calendar date written 2026-03-31 (not 2026-02-30, not full-width digits)."""
    if not DATE_RE.fullmatch(text):
        return False
    try:
        date.fromisoformat(text)
    except ValueError:
        return False
    return True


class ReleaseError(HarnessError):
    """The requested change-control step is not possible."""


@dataclass(frozen=True)
class Blocker:
    code: str
    message: str
    object_id: str | None = None
    about: str | None = None  # the input it is about: "by", "comment", "checker", "reason"


@dataclass
class ReleasePlan:
    ops: list[Op] = field(default_factory=list)
    blockers: list[Blocker] = field(default_factory=list)
    label: str = ""

    @property
    def ok(self) -> bool:
        return not self.blockers


def next_revision(rev: str) -> str:
    """A -> B ... Z -> AA -> AB (spreadsheet-style letters)."""
    if not re.fullmatch(r"[A-Z]+", rev):
        raise ReleaseError(
            f"Revision '{rev}' is not letters; rename it before starting a new revision."
        )
    chars = list(rev)
    k = len(chars) - 1
    while k >= 0:
        if chars[k] != "Z":
            chars[k] = chr(ord(chars[k]) + 1)
            return "".join(chars)
        chars[k] = "A"
        k -= 1
    return "A" + "".join(chars)


def _next_entry_id(project: Project) -> str:
    n = max((int(k[1:]) for k in project.changelog if re.fullmatch(r"C\d{4,}", k)), default=0)
    return f"C{n + 1:04d}"


def _entry(
    project: Project, h: Harness, kind: ChangeKind, by: str, when: str, comment: str
) -> ChangeEntry:
    return ChangeEntry(
        id=_next_entry_id(project),
        harness_id=h.id,
        revision=h.revision,
        kind=kind,
        by=by,
        when=when,
        comment=comment,
    )


def text_blockers(
    value: str | None, about: str, what: str, *, limit: int = 200, one_line: bool = True
) -> list[Blocker]:
    """A name, comment or reason must be plain text of a sensible length. Names are one line;
    comments may have line breaks (the reports show them as one line)."""
    if value is None:
        return []
    allowed = "" if one_line else "\n\t"  # what the data model accepts in a text
    bad = any(
        (unicodedata.category(c) in ("Cc", "Cs") and c not in allowed) or c in "\ufffe\uffff"
        for c in value
    )
    if bad:
        kind = "control characters" if not one_line else "control characters or line breaks"
        return [Blocker(f"{about}_invalid", f"{what} must not contain {kind}.", about=about)]
    if len(value.strip()) > limit:
        return [
            Blocker(
                f"{about}_long",
                f"{what} is longer than {limit} characters; shorten it.",
                about=about,
            )
        ]
    return []


def _common(project: Project, hid: str, by: str, comment: str | None, when: str) -> list[Blocker]:
    out: list[Blocker] = []
    if hid not in project.harnesses:
        return [Blocker("no_harness", f"Harness {hid} does not exist.", hid)]
    if not by.strip():
        out.append(
            Blocker("no_name", "Enter your name; it is recorded in the change log.", about="by")
        )
    else:
        out.extend(text_blockers(by, "by", "The name"))
    if comment is not None:
        if len(comment.strip()) < MIN_COMMENT:
            out.append(
                Blocker(
                    "comment_short",
                    f"The comment needs at least {MIN_COMMENT} characters: say what changed or why.",
                    about="comment",
                )
            )
        out.extend(
            text_blockers(comment, "comment", "The comment", limit=MAX_COMMENT, one_line=False)
        )
    if not valid_date(when):
        out.append(Blocker("bad_date", "The date must look like 2026-03-31.", about="date"))
    return out


def placeholder_blockers(project: Project, accept_placeholders: str | None) -> list[Blocker]:
    """Configuration files still marked as placeholders block a release unless the person
    releasing gives a written reason (kept in the change log, see `placeholder_note`)."""
    names = project.placeholder_configs()
    if not names:
        return []
    listed = ", ".join(names)
    if accept_placeholders is None:
        return [
            Blocker(
                "placeholder_config",
                f"These configuration files are still placeholders: {listed}. Have an engineer "
                'review the values and set "placeholder" to false in each file '
                "(`harness config DIR` lists them). Or release on placeholders with a written "
                "reason (command line: --accept-placeholders REASON); the reason is kept in the "
                "change log.",
            )
        ]
    if len(accept_placeholders.strip()) < MIN_COMMENT:
        return [
            Blocker(
                "placeholder_reason_short",
                f"The reason for releasing on placeholders ({listed}) needs at least "
                f"{MIN_COMMENT} characters.",
            )
        ]
    return []


def placeholder_note(project: Project, by: str, accept_placeholders: str | None) -> str:
    """The sentence added to the comment of a release made on placeholders ('' otherwise)."""
    names = project.placeholder_configs()
    if not names or accept_placeholders is None:
        return ""
    return (
        f" [Released on placeholder configuration ({', '.join(names)}); "
        f"accepted by {by.strip()}: {accept_placeholders.strip()}]"
    )


def unapproved_parts(project: Project, h: Harness) -> list[str]:
    """Parts the harness uses that no one has approved: missing from the parts list, not
    approved, or example data nobody has verified."""
    used = {c.part_id for c in h.connectors} | {w.part_id for w in h.wires if w.part_id}
    out = []
    for pid in sorted(used):
        part = project.parts.get(pid)
        if part is None or part.approval != "approved" or part.unverified:
            out.append(pid)
    return out


def _listed(ids: list[str], limit: int = 5) -> str:
    more = f" and {len(ids) - limit} more" if len(ids) > limit else ""
    return ", ".join(ids[:limit]) + more


def part_blockers(project: Project, h: Harness, accept_unapproved: str | None) -> list[Blocker]:
    """Unapproved parts block a release unless the person releasing gives a written reason."""
    ids = unapproved_parts(project, h)
    if not ids:
        return []
    if accept_unapproved is None:
        return [
            Blocker(
                "parts_unapproved",
                f"{len(ids)} part(s) used by {h.id} are not approved (or are example data): "
                f"{_listed(ids)}. Approve them in the parts list, or release with a written "
                "reason (command line: --accept-unapproved-parts REASON); the reason is kept "
                "in the change log.",
                h.id,
            )
        ]
    if len(accept_unapproved.strip()) < MIN_COMMENT:
        return [
            Blocker(
                "parts_reason_short",
                f"The reason for releasing with parts that are not approved needs at least "
                f"{MIN_COMMENT} characters.",
                h.id,
            )
        ]
    return []


def part_note(project: Project, h: Harness, by: str, accept_unapproved: str | None) -> str:
    """The sentence added to the comment of a release made with unapproved parts ('' otherwise)."""
    ids = unapproved_parts(project, h)
    if not ids or accept_unapproved is None:
        return ""
    return (
        f" [Released with parts that are not approved ({_listed(ids)}); "
        f"accepted by {by.strip()}: {accept_unapproved.strip()}]"
    )


def release_blockers(
    project: Project,
    hid: str,
    *,
    by: str,
    comment: str,
    when: str,
    outputs_folder: Path | None,
    accept_placeholders: str | None = None,
    accept_unapproved_parts: str | None = None,
    checker: str | None = None,
) -> list[Blocker]:
    out = _common(project, hid, by, comment, when)
    h = project.harnesses.get(hid)
    if h is None:
        return out
    out.extend(placeholder_blockers(project, accept_placeholders))
    out.extend(part_blockers(project, h, accept_unapproved_parts))
    notes = placeholder_note(project, by, accept_placeholders) + part_note(
        project, h, by, accept_unapproved_parts
    )
    out.extend(text_blockers(accept_placeholders, "reason", "The reason for releasing on placeholders", limit=MAX_COMMENT, one_line=False))  # fmt: skip
    out.extend(text_blockers(accept_unapproved_parts, "reason", "The reason for releasing with parts that are not approved", limit=MAX_COMMENT, one_line=False))  # fmt: skip
    out.extend(text_blockers(checker, "checker", "The checker's name"))
    if len(comment.strip() + notes) > MAX_COMMENT and not any(
        b.code == "comment_long" for b in out
    ):
        out.append(
            Blocker(
                "comment_long",
                f"The comment (with the reason for releasing on placeholders) is longer than "
                f"{MAX_COMMENT} characters; shorten it.",
                about="comment",
            )
        )
    if h.status == "released":
        out.append(
            Blocker(
                "already_released",
                f"{hid} is already released (revision {h.revision}). Start a new revision to change it.",
                hid,
            )
        )
    if not h.wires:
        out.append(Blocker("no_wires", f"{hid} has no wires.", hid))
    if h.generated and generation_status(project) == "stale":
        out.append(
            Blocker(
                "generation_stale",
                "The harness plans are out of date. Generate harnesses again first.",
                hid,
            )
        )
    related = related_ids(project, h)
    for issue in verify_project(project).errors:
        if issue.object_id is None or issue.object_id in related:
            out.append(Blocker("verify_error", f"Verifier: {issue.message}", issue.object_id))
    carried = carried_interfaces(h)
    for f in drc.run(project):
        if f.severity != "error" or f.waiver is not None:
            continue
        where = drc.locate(project, f.object_id)
        mine = (
            f.object_id in related
            or where == ("harness", hid)
            or (where is not None and where[0] == "interface" and where[1] in carried)
            or f.rule == "config-invalid"  # a wrong engineering value affects every harness
        )
        if mine:
            out.append(Blocker("rule_error", f.title, f.object_id))
    undecided = [w.id for w in h.wires if w.gauge_awg is None]
    if undecided:
        out.append(
            Blocker(
                "gauge_pending",
                f"{len(undecided)} wire(s) have no gauge decided (first: {undecided[0]}). Fill in the derating values (the file config/derating.json; `harness config DIR` lists what is missing) or set the gauge by hand.",
                undecided[0],
            )
        )
    no_length = [w.id for w in h.wires if wire_length(h, w) is None]
    if no_length:
        out.append(
            Blocker(
                "length_unknown",
                f"{len(no_length)} wire(s) have no length (first: {no_length[0]}). Enter the routing segment lengths (`harness import-lengths DIR FILE` loads them from a table).",
                no_length[0],
            )
        )
    out.extend(outputs_blockers(project, outputs_folder, hid))
    existing = f"{hid}.{h.revision}"
    if existing in project.baselines:
        out.append(
            Blocker(
                "baseline_exists",
                f"Revision {h.revision} of {hid} already has a baseline; start a new revision.",
                hid,
            )
        )
    return out


def _linked_or_read_only(folder: Path) -> str:
    """Why the outputs cannot be written again after the release (the status in the title blocks
    is stamped by a second export), or '' if they can. Checked before anything is committed."""
    if folder.is_symlink() or any(
        (Path(root) / d).is_symlink() for root, dirs, _ in os.walk(folder) for d in dirs
    ):
        return (
            "The outputs folder (or a folder in it) is a link, so the released status could not "
            "be written into the outputs. Replace the link with a real folder and export again."
        )
    if folder.is_dir() and not os.access(folder, os.W_OK | os.X_OK):
        return (
            "The outputs folder cannot be written, so the released status could not be stamped "
            "into the outputs. Make it writable and export again."
        )
    return ""


def outputs_blockers(
    project: Project, folder: Path | None, hid: str | None = None
) -> list[Blocker]:
    from harness_design_studio.core.outputs.build import (
        damaged_files,
        exported_harnesses,
        outputs_content_state,
    )

    if folder is None:
        return [
            Blocker(
                "outputs_unsaved",
                "Save the project to a folder and export the outputs before releasing.",
            )
        ]
    linked = _linked_or_read_only(folder)
    if linked:
        return [Blocker("outputs_linked", linked)]
    state = outputs_content_state(project, folder)
    if state == "none":
        return [
            Blocker(
                "outputs_missing",
                "Outputs have not been exported yet. Export them, review them, then release.",
            )
        ]
    if state != "current":
        return [
            Blocker(
                "outputs_stale",
                "The outputs are out of date (the design changed after the export). Export again.",
            )
        ]
    # the manifest alone proves nothing: the files it lists must still be there and unchanged
    damaged = damaged_files(folder)
    if damaged:
        return [
            Blocker(
                "outputs_modified",
                f"{len(damaged)} output file(s) were changed or removed after the export (first: {damaged[0]}). Export again.",
            )
        ]
    if hid is not None and hid not in (exported_harnesses(folder) or set()):
        return [
            Blocker(
                "outputs_missing",
                f"The exported outputs do not include {hid}. Export all outputs, then release.",
                hid,
            )
        ]
    return []


def plan_release(
    project: Project,
    hid: str,
    *,
    by: str,
    checker: str | None,
    comment: str,
    when: str,
    outputs_folder: Path | None,
    accept_placeholders: str | None = None,
    accept_unapproved_parts: str | None = None,
) -> ReleasePlan:
    blockers = release_blockers(
        project, hid, by=by, comment=comment, when=when, outputs_folder=outputs_folder,
        accept_placeholders=accept_placeholders, accept_unapproved_parts=accept_unapproved_parts,
        checker=checker,
    )  # fmt: skip
    plan = ReleasePlan(blockers=blockers, label=f"Release {hid}")
    if blockers:
        return plan
    h = project.harnesses[hid]
    released = normalize(
        evolve(
            h,
            status="released",
            author=h.author or by.strip(),
            checker=(checker or "").strip() or None,
            approver=by.strip(),
            released_on=when,
        )
    )
    snapshot = snapshot_for(project, released)
    full_comment = (
        comment.strip()
        + placeholder_note(project, by, accept_placeholders)
        + part_note(project, h, by, accept_unapproved_parts)
    )
    entry = _entry(project, released, "release", by.strip(), when, full_comment)
    baseline = Baseline(
        id=f"{hid}.{h.revision}", harness_id=hid, revision=h.revision, released_on=when, by=by.strip(),
        comment=full_comment, content_hash=content_hash(project), snapshot=snapshot,
    )  # fmt: skip
    plan.ops = [Put("harnesses", released), Put("baselines", baseline), Put("changelog", entry)]
    plan.label = f"Release {hid} revision {h.revision}"
    return plan


def plan_new_revision(
    project: Project, hid: str, *, by: str, comment: str, when: str
) -> ReleasePlan:
    blockers = _common(project, hid, by, comment, when)
    h = project.harnesses.get(hid)
    if h is not None and h.status != "released":
        blockers.append(
            Blocker("not_released", f"{hid} is not released, so it can be edited directly.", hid)
        )
    plan = ReleasePlan(blockers=blockers, label=f"New revision of {hid}")
    if blockers or h is None:
        return plan
    new = evolve(
        h,
        revision=next_revision(h.revision),
        status="draft",
        checker=None,
        approver=None,
        released_on=None,
    )
    entry = _entry(project, new, "new_revision", by.strip(), when, comment.strip())
    plan.ops = [Put("harnesses", new), Put("changelog", entry)]
    plan.label = f"New revision {new.revision} of {hid}"
    return plan


def plan_submit_review(project: Project, hid: str, *, by: str, when: str) -> ReleasePlan:
    blockers = _common(project, hid, by, None, when)
    h = project.harnesses.get(hid)
    if h is not None and h.status != "draft":
        blockers.append(
            Blocker(
                "not_draft",
                f"{hid} is {h.status.replace('_', ' ')}; only drafts can be submitted for review.",
                hid,
            )
        )
    if h is not None and not h.wires:
        blockers.append(Blocker("no_wires", f"{hid} has no wires.", hid))
    plan = ReleasePlan(blockers=blockers, label=f"Submit {hid} for review")
    if blockers or h is None:
        return plan
    new = evolve(h, status="in_review", author=by.strip())
    plan.ops = [
        Put("harnesses", new),
        Put("changelog", _entry(project, new, "review", by.strip(), when, "")),
    ]
    return plan


__all__ = [
    "Blocker",
    "ReleaseError",
    "ReleasePlan",
    "next_revision",
    "plan_new_revision",
    "part_blockers",
    "part_note",
    "placeholder_blockers",
    "placeholder_note",
    "plan_release",
    "plan_submit_review",
    "release_blockers",
    "release_integrity",
    "unapproved_parts",
]
