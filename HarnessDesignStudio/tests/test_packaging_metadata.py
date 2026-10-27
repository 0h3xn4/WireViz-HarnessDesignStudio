"""E-F9: the package says which Python versions it supports, and the dev extra holds what CI uses."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _project() -> dict[str, object]:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]  # type: ignore[no-any-return]


def test_the_classifiers_name_python_3_14_only() -> None:
    classifiers = _project()["classifiers"]
    versions = [c for c in classifiers if c.startswith("Programming Language :: Python :: 3.")]  # type: ignore[attr-defined, union-attr]
    assert versions == ["Programming Language :: Python :: 3.14"]
    assert _project()["requires-python"] == ">=3.14"


def test_the_dev_extra_pins_pytest_timeout_like_the_other_tools() -> None:
    extras = _project()["optional-dependencies"]["dev"]  # type: ignore[index]
    pinned = [e for e in extras if e.startswith("pytest-timeout")]
    assert len(pinned) == 1 and pinned[0].startswith("pytest-timeout==")
    assert all("==" in e for e in extras)
