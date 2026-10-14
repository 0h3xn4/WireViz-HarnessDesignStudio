"""Bundled resources (the offline user guide, example projects and templates, fonts)."""

import sys
from pathlib import Path


def guide_path() -> Path | None:
    """The bundled user guide (HTML), also inside a PyInstaller build; None if it is missing."""
    roots = [Path(__file__).parent]
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        roots.insert(0, Path(frozen) / "harness_design_studio" / "resources")
    for root in roots:
        candidate = root / "guide" / "index.html"
        if candidate.is_file():
            return candidate
    return None


def examples_path() -> Path | None:
    """The bundled example projects and templates, also inside a PyInstaller build."""
    roots = [Path(__file__).parent]
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        roots.insert(0, Path(frozen) / "harness_design_studio" / "resources")
    for root in roots:
        candidate = root / "examples"
        if (candidate / "projects").is_dir():
            return candidate
    return None


def fonts_path() -> Path | None:
    """The bundled IBM Plex fonts (WOFF2, SIL OFL), also inside a PyInstaller build."""
    roots = [Path(__file__).parent]
    frozen = getattr(sys, "_MEIPASS", None)
    if frozen:
        roots.insert(0, Path(frozen) / "harness_design_studio" / "resources")
    for root in roots:
        candidate = root / "fonts"
        if candidate.is_dir() and any(candidate.glob("*.woff2")):
            return candidate
    return None
