"""PyInstaller entry point for the console command `harness-design-studio` (alias `harness`)."""

from harness_design_studio.cli.main import main

if __name__ == "__main__":
    raise SystemExit(main())
