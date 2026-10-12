"""Change log table and the revision report (history plus differences between baselines)."""

from harness_design_studio.core.model import Baseline, Harness, Project

from .diff import Diff, diff_snapshots, render_markdown
from .snapshot import snapshot_for

LOG_HEADER = ["Entry", "Harness", "Revision", "Event", "By", "Date", "Comment"]
EVENTS = {
    "review": "submitted for review",
    "release": "released",
    "new_revision": "new revision started",
}


def one_line(text: str) -> str:
    """A comment with its line breaks and runs of spaces collapsed, so that it cannot look like a
    separate entry in a table or in the report."""
    return " ".join(text.split())


def changelog_rows(project: Project, harness_id: str | None = None) -> list[list[str]]:
    rows = [LOG_HEADER]
    for e in sorted(project.changelog.values(), key=lambda x: x.id):
        if harness_id is None or e.harness_id == harness_id:
            rows.append(
                [
                    e.id,
                    e.harness_id,
                    e.revision,
                    EVENTS[e.kind],
                    one_line(e.by),
                    e.when,
                    one_line(e.comment),
                ]
            )
    return rows


def baselines_of(project: Project, hid: str) -> list[Baseline]:
    return sorted(
        (b for b in project.baselines.values() if b.harness_id == hid),
        key=lambda b: (len(b.revision), b.revision),
    )


def working_diff(project: Project, h: Harness, base: Baseline) -> Diff:
    return diff_snapshots(base.snapshot, snapshot_for(project, h))


def revision_report(project: Project, stamp_line: str) -> str:
    lines = [
        f"<!-- {stamp_line} -->",
        f"# Revision report: {' '.join(project.meta.name.split())}",
        "",
    ]
    hids = sorted(
        {b.harness_id for b in project.baselines.values()}
        | {e.harness_id for e in project.changelog.values()}
    )
    if not hids:
        return "\n".join([*lines, "No harness has been put into review or released yet.", ""])
    for hid in hids:
        h = project.harnesses.get(hid)
        state = (
            f"revision {h.revision}, {h.status.replace('_', ' ')}"
            if h
            else "no longer in the design"
        )
        lines += [f"## {hid} ({state})", ""]
        if h is not None and (h.approver or h.checker or h.author):
            lines.append(
                f"Author {h.author or '-'}, checker {h.checker or '-'}, approver {h.approver or '-'}, released {h.released_on or '-'}."
            )
            lines.append("")
        for e in sorted(
            (e for e in project.changelog.values() if e.harness_id == hid), key=lambda x: x.id
        ):
            tail = f": {one_line(e.comment)}" if e.comment else ""
            lines.append(
                f"- {e.when}, {one_line(e.by)}: revision {e.revision} {EVENTS[e.kind]}{tail} (`{e.id}`)"
            )
        bases = baselines_of(project, hid)
        for a, b in zip(bases, bases[1:], strict=False):
            diff = diff_snapshots(a.snapshot, b.snapshot)
            lines += [
                "",
                render_markdown(f"{hid}: revision {a.revision} to {b.revision}", diff)
                .replace("# ", "### ", 1)
                .rstrip(),
            ]
        if bases and h is not None:
            diff = working_diff(project, h, bases[-1])
            if not diff.empty:
                lines += [
                    "",
                    render_markdown(
                        f"{hid}: working design against revision {bases[-1].revision}", diff
                    )
                    .replace("# ", "### ", 1)
                    .rstrip(),
                ]
        lines.append("")
    return "\n".join(lines)
