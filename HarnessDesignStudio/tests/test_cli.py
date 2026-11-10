# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
import pytest

from harness_design_studio import __version__
from harness_design_studio.cli.main import main


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--version"]) == 0
    assert __version__ in capsys.readouterr().out


def test_no_args_prints_help_and_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 2
    assert "usage" in capsys.readouterr().err.lower()


def test_unknown_option_is_clean_error(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--bogus"]) == 2
    assert "usage" in capsys.readouterr().err.lower()
