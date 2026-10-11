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
| [`tools.md`](tools.md) | Every script in `harness/tools/` |
| [`upstream-sync.md`](upstream-sync.md) | How to refresh the copy of the WireViz README after WireViz changes it |

## Other documents you will need

| Page | What it is for |
| --- | --- |
| [`../../CLAUDE.md`](../../CLAUDE.md) | Commands, layout and conventions, written for the AI assistant that builds the tool. Accurate and detailed; read it for the conventions per area of the code. |
| [`../DECISIONS.md`](../DECISIONS.md) | Every decision (D-01, D-02 ...) with its reason. New dependencies are recorded here with their licence. |
| [`../SECURITY.md`](../SECURITY.md) | What the tool does to protect files and what was reviewed |
| [`../RELEASE.md`](../RELEASE.md) | The release checklist, step by step |
| [`../FILE_FORMAT.md`](../FILE_FORMAT.md) | The project folder format |
| [`../../compliance/docs/PROBLEM_REPORTING.md`](../../compliance/docs/PROBLEM_REPORTING.md) | How problems are reported and tracked |
| [`../../../docs/README.md`](../../../docs/README.md) | The index of all documents |

Next: [`setup-and-tests.md`](setup-and-tests.md).
