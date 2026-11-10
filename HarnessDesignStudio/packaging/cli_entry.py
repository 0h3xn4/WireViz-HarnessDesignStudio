# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""PyInstaller entry point for the console command `harness-design-studio` (alias `harness`)."""

from harness_design_studio.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
