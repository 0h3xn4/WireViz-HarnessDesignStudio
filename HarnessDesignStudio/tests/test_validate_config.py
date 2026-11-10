# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""`validate` runs the same check of the values in `config/*.json` as `generate`, `drc` and `config`
(D-191). Before, a project whose `bundle_derating` was 1.5 passed `validate` with "0 error(s)" while
`generate` stopped with `config_invalid` (found by the transparency audit; `docs/CONFIG.md` says they
use the same checks)."""

from pathlib import Path

import pytest

from harness_design_studio.cli.main import main
from harness_design_studio.core import configcheck, templates
from harness_design_studio.core.io.saver import save_project
from harness_design_studio.core.model import ConfigFile, Project


def project_with(tmp_path: Path, **derating: object) -> Path:
    path = tmp_path / "p"
    project: Project = templates.create_project(path, "first-steps")
    base = project.config["derating"]
    project.config["derating"] = ConfigFile(
        name="derating", placeholder=False, values={**base.values, **derating}
    )
    save_project(project, path)
    return path


@pytest.mark.parametrize(
    "values",
    [
        {"bundle_derating": 1.5},
        {"bundle_derating": 0},
        {"temperature_derating": 2},
        {"ampacity_a_by_awg": {"20": 1.0, "24": 5.0}},  # a thinner wire must not carry more
    ],
)
def test_validate_reports_a_config_value_that_generate_and_config_refuse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], values: dict[str, object]
) -> None:
    path = project_with(tmp_path, **values)
    assert main(["validate", str(path)]) == 1
    out = capsys.readouterr().out
    assert "config_invalid" in out and "1 error(s)" in out
    assert main(["generate", str(path)]) == 1  # the same refusal as before
    assert "config_invalid" in capsys.readouterr().out
    assert main(["config", str(path)]) == 1


def test_validate_names_the_file_and_the_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = project_with(tmp_path, bundle_derating=1.5)
    main(["validate", str(path)])
    assert (
        "config/derating.json: bundle_derating must be a number above 0 and at most 1"
        in capsys.readouterr().out
    )


def test_validate_stays_clean_for_a_project_whose_values_are_fine(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = project_with(tmp_path, bundle_derating=0.6, temperature_derating=0.9)
    assert main(["validate", str(path)]) == 0
    assert "0 error(s)" in capsys.readouterr().out
    project = templates.create_project(tmp_path / "flat", "flatsat")
    assert configcheck.validate(project) == []
    assert main(["validate", str(tmp_path / "flat")]) == 0
