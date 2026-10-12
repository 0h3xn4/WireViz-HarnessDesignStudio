"""DRC building blocks: a rule states what is wrong, why it matters and how to fix it; its check
yields `Hit`s (one per offending object). Findings reuse `checks.Finding` so the Problems panel,
waivers and to-do list treat logical and design rule findings the same way."""

from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from harness_design_studio.core.checks import Finding, finding_id
from harness_design_studio.core.issues import Severity
from harness_design_studio.core.model import Project


@dataclass(frozen=True)
class Hit:
    object_id: str
    title: str  # plain-language statement of this one problem
    fix_label: str | None = None  # set only when `drc.fix_ops` can really fix it
    key: str | None = None  # tells apart several problems of one object (the finding ID uses it)


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    topic: str  # short plain-language name, shown in the report
    why: str
    how: str  # how to fix it by hand
    check: Callable[[Project], Iterator[Hit]]
    waivable: bool | None = None  # default: warnings can be waived, errors and info cannot
    sources: tuple[str, ...] = ()  # IDs of the standard requirements this rule serves (compliance/)

    @property
    def can_waive(self) -> bool:
        return self.severity == "warning" if self.waivable is None else self.waivable

    def run(self, project: Project) -> list[Finding]:
        out: list[Finding] = []
        used: Counter[str] = Counter()
        for h in self.check(project):
            fid = finding_id(self.id, h.key or h.object_id)
            used[fid] += 1
            if used[fid] > 1:  # safety net: a waiver must never cover two different problems
                fid = finding_id(self.id, f"{h.key or h.object_id}#{used[fid]}")
            out.append(
                Finding(
                    fid, self.id, self.severity, h.object_id,
                    h.title, f"{self.why} To fix it: {self.how}", h.fix_label, self.can_waive, None, self.sources,
                )
            )  # fmt: skip
        return out


def cfg(project: Project, name: str) -> dict[str, object]:
    c = project.config.get(name)
    return dict(c.values) if c is not None else {}


def number(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def flag(values: dict[str, object], key: str) -> bool:
    """A yes/no setting that defaults to yes; an explicit null must not silently switch it off."""
    value = values.get(key)
    return True if value is None else bool(value)
