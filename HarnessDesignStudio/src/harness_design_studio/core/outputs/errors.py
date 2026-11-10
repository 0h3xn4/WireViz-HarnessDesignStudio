# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Errors of the output builder, in plain language."""

from harness_design_studio.core.errors import HarnessError


class OutputsError(HarnessError):
    """An output file could not be built; nothing was written."""
