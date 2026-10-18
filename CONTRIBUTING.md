# Contributing

This page tells you how to propose a change to this repository, which part of it to change, and the one rule you must not break.

## Contents

- [Two codebases in one repository](#two-codebases-in-one-repository)
- [The one hard rule](#the-one-hard-rule)
- [Set up and test](#set-up-and-test)
- [Propose a change](#propose-a-change)
- [Report a problem](#report-a-problem)
- [Change the documents](#change-the-documents)

## Two codebases in one repository

| Part | Folder | Contribution guide |
| --- | --- | --- |
| **Harness Design Studio**, a desktop tool for designing spacecraft harnesses | [`HarnessDesignStudio/`](HarnessDesignStudio/README.md) | This page |
| **WireViz**, the project this repository is forked from | `src/wireviz/`, `docs/`, `examples/`, `tutorial/` | WireViz's own guide, [`docs/CONTRIBUTING.md`](docs/CONTRIBUTING.md). Changes to WireViz itself belong in the [WireViz repository](https://github.com/wireviz/WireViz). |

If you are not sure which one you are changing, look at the folder. Almost all work in this repository is in `HarnessDesignStudio/`.

## The one hard rule

**Never copy, paste or import code from `src/wireviz` into `HarnessDesignStudio/`.** WireViz is released under the GPL-3.0; Harness Design Studio was written from scratch (a "clean-room" codebase) so that it does not inherit that licence. This is decision D-01 in [`HarnessDesignStudio/docs/DECISIONS.md`](HarnessDesignStudio/docs/DECISIONS.md). The same goes for ideas copied line by line from WireViz's code. WireViz is only an export target: the tool can write WireViz-style YAML.

## Set up and test

The tool runs on Ubuntu 24.04 or newer only. From a clone of this repository:

```
cd HarnessDesignStudio
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[gui,dev]"
pytest -n auto -m "not perf" && pytest -m perf   # in parallel, then the timing tests alone (plain `pytest` also works, only slower)
ruff format . && ruff check . && mypy
```

The Qt libraries, the coverage gate, golden files and what CI runs are explained in [`HarnessDesignStudio/docs/developer/setup-and-tests.md`](HarnessDesignStudio/docs/developer/setup-and-tests.md). The layers and the rules that keep them apart are in [`HarnessDesignStudio/docs/developer/architecture.md`](HarnessDesignStudio/docs/developer/architecture.md).

## Propose a change

1. Open an issue first if the change is more than a small fix, so that it can be discussed before you spend time on it. WireViz's guide asks for the same.
2. Work on a branch, not on `master`. Branch names in this repository describe the kind of change, for example `fix/…`, `docs/…`, `feature/…`.
3. Write the test first, and give every bug fix a test that fails without the fix. Tests, lint and types must pass; CI runs them on every pull request.
4. Follow the conventions in [`HarnessDesignStudio/CLAUDE.md`](HarnessDesignStudio/CLAUDE.md). It is written for the AI assistant that builds most of the tool, but it is also the shortest accurate list of the conventions: `core` never imports `gui` or the network; every model change goes through the command layer; output is deterministic; engineering values are never invented.
5. Record every new dependency (name, version, licence) in [`HarnessDesignStudio/docs/DECISIONS.md`](HarnessDesignStudio/docs/DECISIONS.md).
6. Write commit messages as one sentence that says what changed and why it matters. The history of this repository is the model.
7. Open a pull request into `master`. Say what changed, how you tested it, and what you left out. Do not merge your own pull request if you can ask the owner.

The owner of the repository decides what is merged. Releases are the owner's decision too ([`HarnessDesignStudio/docs/developer/release.md`](HarnessDesignStudio/docs/developer/release.md)).

## Report a problem

Open an issue on GitHub. The project treats every problem with the tool, a document or a test as a *software problem report*; the template and the way it is handled are in [`HarnessDesignStudio/compliance/docs/PROBLEM_REPORTING.md`](HarnessDesignStudio/compliance/docs/PROBLEM_REPORTING.md) and [`HarnessDesignStudio/compliance/templates/problem_report.md`](HarnessDesignStudio/compliance/templates/problem_report.md). Say which version you used (`harness-design-studio --version`; note that `master` and the released 0.1.0 print the same version), what you did, what you expected and what happened.

## Change the documents

Documents are part of the product: a test checks every link and runs the commands of the tutorial. Which files are generated, how to add a page and how to check the links: [`HarnessDesignStudio/docs/developer/docs-maintenance.md`](HarnessDesignStudio/docs/developer/docs-maintenance.md). The index of all documents is [`docs/README.md`](docs/README.md). The WireViz README embedded in the root [`README.md`](README.md) is refreshed with [`HarnessDesignStudio/docs/developer/upstream-sync.md`](HarnessDesignStudio/docs/developer/upstream-sync.md); do not edit it by hand.

Next: [`HarnessDesignStudio/docs/developer/README.md`](HarnessDesignStudio/docs/developer/README.md).
