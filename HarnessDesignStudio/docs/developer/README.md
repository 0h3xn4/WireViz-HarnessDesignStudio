# Developer documentation

This page is the map of the documents for people who work on the code or the documents of Harness Design Studio.

## Start here

1. Read [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) at the repository root: which codebase to work in, and the one hard rule (never copy WireViz code into the tool).
2. [Set up a development environment and run the tests](setup-and-tests.md).
3. [Architecture overview](architecture.md): the layers and the rules that keep them apart.

## All developer pages

| Page | What it is for |
| --- | --- |
| [`setup-and-tests.md`](setup-and-tests.md) | Set up the environment, run the tests, the style and type checks, golden files, what CI runs |
| [`architecture.md`](architecture.md) | A short overview for a new contributor, with links to the full [architecture](../ARCHITECTURE.md), the [decisions](../DECISIONS.md) and the [security review](../SECURITY.md) |
| [`docs-maintenance.md`](docs-maintenance.md) | Which documents are generated, how to regenerate them, how to add a page, how to check the links |
| [`release.md`](release.md) | How to cut a release of the tool, in plain words |
| [`tools.md`](tools.md) | Every script in `HarnessDesignStudio/tools/` (including the screenshot, timing and output-hash scripts of the UI overhaul) |
| [`upstream-sync.md`](upstream-sync.md) | How to refresh the copy of the WireViz README after WireViz changes it |

## Other documents you will need

| Page | What it is for |
| --- | --- |
| [`../../CLAUDE.md`](../../CLAUDE.md) | Commands, layout and conventions, written for the AI assistant that builds the tool. Accurate and detailed; read it for the conventions per area of the code. |
| [`CLAUDE_HISTORY.md`](CLAUDE_HISTORY.md) | The status paragraph that used to stand in `CLAUDE.md`, moved here word for word |
| [`../DECISIONS.md`](../DECISIONS.md) | Every decision (D-01, D-02 ...) with its reason. New dependencies are recorded here with their licence. |
| [`../DESIGN.md`](../DESIGN.md) | The design system of the editor: tokens (`gui/theme/tokens.py`), type, themes, icons, state chips, tables, the window and its areas, shortcuts |
| [`../ui/UI_OVERHAUL_PLAN.md`](../ui/UI_OVERHAUL_PLAN.md), [`../ui/BEFORE_AFTER.md`](../ui/BEFORE_AFTER.md), [`../ui/PERF_BASELINE.md`](../ui/PERF_BASELINE.md) | The UI overhaul of version 1.3.0: the plan with the mapping of every old tab, menu and dialog to its new place, the before and after pictures, the timings |
| [`../SECURITY.md`](../SECURITY.md) | What the tool does to protect files and what was reviewed |
| [`../RELEASE.md`](../RELEASE.md) | The release checklist, step by step |
| [`../FILE_FORMAT.md`](../FILE_FORMAT.md) | The project folder format |
| [`../../compliance/docs/PROBLEM_REPORTING.md`](../../compliance/docs/PROBLEM_REPORTING.md) | How problems are reported and tracked |
| [`../../../docs/README.md`](../../../docs/README.md) | The index of all documents |

Next: [`setup-and-tests.md`](setup-and-tests.md).
