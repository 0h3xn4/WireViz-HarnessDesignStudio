"""Naming schemes from the `naming` configuration. Invalid templates fall back to the defaults."""

import re
from dataclasses import dataclass, field

from harness_design_studio.core.ids import check_id
from harness_design_studio.core.model import Project

DEFAULTS = {
    "harness": "W{n:03d}",
    "cable_connector": "{harness}-P{n}",
    "wire": "{harness}-{n:03d}",
    "shield": "{harness}-S{n}",
    "branch": "{harness}-B{n}",
    "segment": "{harness}-L{n}",
}


@dataclass
class Namer:
    templates: dict[str, str]
    warnings: list[str] = field(default_factory=list)

    def _fmt(self, kind: str, **kw: object) -> str:
        template = self.templates.get(kind, DEFAULTS[kind])
        try:
            name = template.format(**kw)
        except Exception:  # a template can fail in many ways (attributes, subscripts, formats)
            name = ""
        if not _valid_id(name):
            if kind in self.templates and f"naming.{kind}" not in self.warnings:
                self.warnings.append(f"naming.{kind}")
            name = DEFAULTS[kind].format(**kw)
        return name

    def use_default(self, kind: str) -> None:
        """Give up on a template that ran out of free names; the default pattern is used from now."""
        if self.templates.pop(kind, None) is not None and f"naming.{kind}" not in self.warnings:
            self.warnings.append(f"naming.{kind}")

    def harness(self, n: int) -> str:
        return self._fmt("harness", n=n)

    def cable_connector(self, harness: str, n: int) -> str:
        return self._fmt("cable_connector", harness=harness, n=n)

    def wire(self, harness: str, n: int) -> str:
        return self._fmt("wire", harness=harness, n=n)

    def shield(self, harness: str, n: int) -> str:
        return self._fmt("shield", harness=harness, n=n)

    def branch(self, harness: str, n: int) -> str:
        return self._fmt("branch", harness=harness, n=n)

    def segment(self, harness: str, n: int) -> str:
        return self._fmt("segment", harness=harness, n=n)


def _valid_id(name: str) -> bool:
    try:
        check_id(name)
    except ValueError:
        return False
    return True


def _distinct(kind: str, template: str) -> bool:
    """A template must give a valid, different name for every harness and every number, or IDs
    collide (and a template without a number would make generation search for a free name
    forever). Numbers up to 200 are tried; the engine bounds its search for the rest."""
    if re.search(r"\{[^{}]*\d{3,}[^{}]*\}", template):  # a width of hundreds would eat memory
        return False
    if kind == "harness":
        samples: list[dict[str, object]] = [{"n": n} for n in range(1, 201)]
    else:
        samples = [{"harness": h, "n": n} for h in ("H1", "H2") for n in range(1, 201)]
    try:
        names = {template.format(**kw) for kw in samples}
    except Exception:
        return False
    if not (len(names) == len(samples) and all(_valid_id(x) for x in names)):
        return False
    if kind == "harness":  # the default names built on a harness ID (the fallback) must fit too
        return all(_valid_id(f"{x}-S9999") for x in names)
    return True


def namer_for(project: Project) -> Namer:
    cfg = project.config.get("naming")
    values = cfg.values if cfg is not None else {}
    templates = {k: v for k, v in values.items() if isinstance(v, str)}
    namer = Namer({})
    for kind, template in templates.items():
        if kind in DEFAULTS and not _distinct(kind, template):
            namer.warnings.append(f"naming.{kind}")  # reported; the default is used instead
        else:
            namer.templates[kind] = template
    return namer
