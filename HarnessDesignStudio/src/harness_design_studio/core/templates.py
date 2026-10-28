"""Starting points shipped with the tool: example projects and import templates.

`create_project` makes a new project folder from an example (so a beginner can start from
something that works) with a `.gitattributes` for teams that use Git; `copy_import_templates`
copies the CSV, netlist and script templates.
Both only read the bundled files and write where the caller says; nothing is overwritten.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.io.loader import load_project
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.mergefix import write_gitattributes
from harness_design_studio.core.model import Project, evolve
from harness_design_studio.resources import examples_path


class TemplateError(HarnessError):
    """A template cannot be used (unknown name, folder not empty, files missing)."""


@dataclass(frozen=True)
class TemplateInfo:
    name: str
    title: str
    summary: str


# Names and one-line descriptions; the folders are built by tools/build_examples.py.
TEMPLATES = (
    TemplateInfo(
        "blank", "My project", "An empty project: starter parts and interface types, no devices."
    ),
    TemplateInfo(
        "first-steps",
        "First steps: reaction wheel link",
        "Three devices, a power link and an RS-422 link. Nothing is generated yet: start here.",
    ),
    TemplateInfo(
        "minimal-satellite",
        "Minimal satellite",
        "Seven devices, nominal only: power, computer, radio, wheel and sun sensor. Adapt it.",
    ),
    TemplateInfo(
        "small-satellite",
        "Small satellite (reference)",
        "14 devices with nominal and redundant chains. Generate it to see a realistic system.",
    ),
    TemplateInfo(
        "flatsat",
        "Flatsat (EXAMPLE numbers, not engineering data)",
        "A complete bench: 23 flight and ground devices, generated, with example numbers.",
    ),
)


def _usable(dest: Path) -> bool:
    """A folder that does not exist yet, or exists and is empty."""
    if dest.is_symlink():  # a link (also a dangling one) is never written through
        return False
    return not dest.exists() or (dest.is_dir() and not any(dest.iterdir()))


def _root() -> Path:
    root = examples_path()
    if root is None:
        raise TemplateError("The bundled examples are missing from this installation.")
    return root


def create_project(dest: Path, template: str, name: str | None = None) -> Project:
    """Write a new project to `dest` (a missing or empty folder) from the named example."""
    known = {t.name: t for t in TEMPLATES}
    if template not in known:
        raise TemplateError(f"Unknown template '{template}'. Choose one of: {', '.join(known)}.")
    if not _usable(dest):
        raise TemplateError(f"{dest} already exists and is not an empty folder; choose a new one.")
    if name is not None and not name.strip():
        raise TemplateError("The project name must not be empty.")
    loaded = load_project(_root() / "projects" / template)
    if loaded.has_errors:
        raise TemplateError(f"The bundled example '{template}' is damaged.")
    project = loaded.project
    if name is not None:
        project.meta = evolve(project.meta, name=name.strip())
    save_project(project, dest)
    write_gitattributes(dest)  # so that two people who both press Generate can merge (merge-fix)
    return project


def copy_import_templates(dest: Path) -> list[Path]:
    """Copy the import templates into `dest` (a new or empty folder); returns the files made."""
    if not _usable(dest):
        raise TemplateError(f"{dest} already exists and is not an empty folder; choose a new one.")
    source = _root() / "templates"
    if not source.is_dir():
        raise TemplateError("The bundled templates are missing from this installation.")
    shutil.copytree(source, dest, dirs_exist_ok=True)
    return sorted(p for p in dest.rglob("*") if p.is_file())
