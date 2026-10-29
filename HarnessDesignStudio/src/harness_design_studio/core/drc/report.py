"""DRC report: open findings, waived findings with their justifications, and what was not
checked. Plain Markdown, deterministic (no dates; the model hash identifies the state)."""

from harness_design_studio.core.checks import Finding
from harness_design_studio.core.io.layout import model_hash
from harness_design_studio.core.model import Project

from . import run
from .rules import RULES

_SEV = {"error": "Error", "warning": "Warning", "info": "Not checked / note"}


def stale_waivers(project: Project, findings: list[Finding]) -> list[str]:
    """Waivers whose finding no longer exists (the problem was fixed, or the object removed)."""
    live = {f.id for f in findings}
    return sorted(w for w in project.waivers if w not in live)


def changed_waivers(findings: list[Finding]) -> list[Finding]:
    """Findings that have a waiver which no longer fits: the finding changed after it was waived."""
    return [f for f in findings if f.waiver_changed]


def render_markdown(project: Project, findings: list[Finding] | None = None) -> str:
    from harness_design_studio.core.checks import find as logical

    found = (
        findings
        if findings is not None
        else sorted(
            [*logical(project), *run(project)],
            key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f.severity], f.id),
        )
    )
    open_ = [f for f in found if f.waiver is None]
    waived = [f for f in found if f.waiver is not None]
    lines = [
        f"# Design rule check: {' '.join(project.meta.name.split())}",
        "",
        f"Model hash: `{model_hash(project)[:12]}`. Rules run: {len(RULES)}.",
        f"Open: {sum(f.severity == 'error' for f in open_)} error(s), "
        f"{sum(f.severity == 'warning' for f in open_)} warning(s), "
        f"{sum(f.severity == 'info' for f in open_)} note(s). Waived: {len(waived)}.",
    ]
    placeholders = sorted(n for n, c in project.config.items() if c.placeholder)
    if placeholders:
        lines += [
            "",
            f"Placeholder configuration in use: {', '.join(placeholders)}. Results that depend on it are marked as not checked.",
        ]
    for sev in ("error", "warning", "info"):
        group = [f for f in open_ if f.severity == sev]
        if not group:
            continue
        lines += [
            "",
            f"## {_SEV[sev]}s ({len(group)})"
            if sev != "info"
            else f"## {_SEV[sev]} ({len(group)})",
            "",
        ]
        for f in group:
            lines.append(f"- **{f.title}** (`{f.id}`)  ")
            lines.append(f"  {f.why_cited}")
    if waived:
        lines += ["", f"## Waived findings ({len(waived)})", ""]
        for f in waived:
            if f.waiver is not None:
                lines.append(f"- **{f.title}** (`{f.id}`): “{f.waiver.justification}”")
    changed = changed_waivers(found)
    if changed:
        lines += [
            "",
            "## Waivers that no longer fit",
            "",
            "These findings were waived, but the finding has changed since. They are open again; "
            "read them and waive them again if the reason still holds.",
            "",
        ]
        lines += [
            f"- **{f.title}** (`{f.id}`): was “{project.waivers[f.id].justification}”"
            for f in changed
        ]
    stale = stale_waivers(project, found)
    if stale:
        lines += [
            "",
            "## Waivers without a matching finding",
            "",
            "These waivers no longer apply; remove them when convenient.",
            "",
        ]
        lines += [f"- `{w}`: “{project.waivers[w].justification}”" for w in stale]
    return "\n".join(lines) + "\n"
