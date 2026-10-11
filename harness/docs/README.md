# Documentation map of Harness Design Studio

This page lists the documents of the tool, grouped by what you want to do. The index of the whole repository (including the WireViz documents) is [`../../docs/README.md`](../../docs/README.md).

## Contents

- [Getting started](#getting-started)
- [Do a task](#do-a-task)
- [Look something up](#look-something-up)
- [Examples and templates](#examples-and-templates)
- [Stuck](#stuck)
- [For developers](#for-developers)
- [Project records](#project-records)

## Getting started

| Document | For | What it gives you |
| --- | --- | --- |
| [`INSTALL.md`](INSTALL.md) | everyone | Install on Ubuntu, check it works, uninstall, build from source |
| [`GETTING_STARTED.md`](GETTING_STARTED.md) | newcomers | A guided tour with real output: example project, generate, read problems, export, fill in values, release |
| [`LEARNING_PATH.md`](LEARNING_PATH.md) | newcomers | The whole route in nine steps, with the example or template for each and how you know you are done |
| [`CONCEPTS.md`](CONCEPTS.md) | newcomers | The words and the mental model, in ten minutes |
| [`GLOSSARY.md`](GLOSSARY.md) | everyone | Every term and abbreviation, in plain words |

## Do a task

| Document | What it gives you |
| --- | --- |
| [`user-manual/`](user-manual/README.md) | One page per task: draw the design, generate harnesses, read and fix problems, fill in engineering values, import data, import KiCad pinouts, export the outputs, set wire colours, release a harness, use Git and CI |
| [`HOWTO.md`](HOWTO.md) | The index of the old recipes, pointing at the user manual |
| [`TIPS.md`](TIPS.md) | Shortcuts, power-user workflows, and exchanging data with other tools |
| [`CHEATSHEET.md`](CHEATSHEET.md) | One page: the loop, the data imports, release, shortcuts, the folder layout, the words |

## Look something up

| Document | What it says |
| --- | --- |
| [`guide/USER_GUIDE.md`](guide/USER_GUIDE.md) | The user guide that opens with **F1** in the app: screen, modes, menus, shortcuts |
| [`CLI.md`](CLI.md) | Every `harness` command and option (generated from the program) |
| [`RULES.md`](RULES.md) | Every design rule: what, why, how to fix, severity (generated) |
| [`CONFIG.md`](CONFIG.md) | Every key of `config/*.json` |
| [`PLACEHOLDERS.md`](PLACEHOLDERS.md) | Which engineering values are still placeholders, who owns them |
| [`IMPORTS.md`](IMPORTS.md) | Importing interfaces, parts, lengths, engineering values |
| [`KICAD.md`](KICAD.md) | Taking unit connector pinouts from a KiCad netlist |
| [`OUTPUTS.md`](OUTPUTS.md) | Every output file and its limits |
| [`FILE_FORMAT.md`](FILE_FORMAT.md) | The project folder format |
| [`../CHANGELOG.md`](../CHANGELOG.md) | What changed, release by release |

## Examples and templates

| Document | What it gives you |
| --- | --- |
| [`examples/README.md`](examples/README.md) | The five example projects and the template files: what each is, how to run it, what you should see |
| [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md) | A tour of the biggest example, a flatsat with ground equipment |
| [`templates/README.md`](../src/harness_design_studio/resources/examples/templates/README.md) | What each file written by `harness templates FOLDER` is for |

`harness new --list` shows the example projects and `harness templates FOLDER` copies the import templates, demo values, CI scripts and the review checklist. Screenshots of the app are in [`ux/qt/`](ux/qt/).

## Stuck

| Document | What it gives you |
| --- | --- |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | Real error messages and their fixes, by the step where they happen |
| [`FAQ.md`](FAQ.md) | Questions that are not errors |

## For developers

[`../../CONTRIBUTING.md`](../../CONTRIBUTING.md), [`developer/`](developer/README.md) (setup and tests, keeping the documents correct, releasing, refreshing the upstream README), [`../CLAUDE.md`](../CLAUDE.md) (commands, layout and conventions, written for the AI assistant), [`ARCHITECTURE.md`](ARCHITECTURE.md), [`DECISIONS.md`](DECISIONS.md), [`SECURITY.md`](SECURITY.md), [`RELEASE.md`](RELEASE.md) (the checklist for releasing the tool, not a harness).

Some files are **generated** and a test fails when they are stale: `RULES.md` (`python -m tools.gen_rule_docs`), `CLI.md` (`python -m tools.gen_cli_docs`), the HTML of the user guide (`python -m tools.build_guide`), and the example projects (`python -m tools.build_examples`). More in [`developer/docs-maintenance.md`](developer/docs-maintenance.md).

## Project records

These explain how the tool was specified and checked; you do not need them to use it.

| Document | What it says |
| --- | --- |
| [`SPEC.md`](SPEC.md), [`REQUIREMENTS.md`](REQUIREMENTS.md), [`UX.md`](UX.md) | What the tool must do and how it should feel |
| [`UX_GUIDELINES_REVIEW.md`](UX_GUIDELINES_REVIEW.md) | The owner's UX/UI guidelines, point by point: done, new, not applicable, open |
| [`DECISIONS.md`](DECISIONS.md), [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md) | What was decided, and what still needs an owner |
| [`PLAN.md`](PLAN.md), [`demos/`](demos/README.md) | The plan and the note from each milestone |
| [`AUDIT.md`](AUDIT.md) | The October audit |
| [`../compliance/README.md`](../compliance/README.md) | The ECSS/ESCC self-assessment: matrix, gaps, deviations, sign-off, open actions, risks. No claim of compliance. |
| [`usability/`](usability/README.md) | The usability test kit |
| [`../../docs/DOCS_AUDIT.md`](../../docs/DOCS_AUDIT.md) | The audit of these documents |

Next: [`INSTALL.md`](INSTALL.md).
