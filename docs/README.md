# Documentation index

This page lists every guide in the repository, grouped by what you want to do, with one line on each. This repository holds two tools: **Harness Design Studio** (documented in `harness/`) and its upstream, **WireViz** (documented in `docs/`, `tutorial/` and `examples/`).

- Not sure where to start? Read the [repository README](../README.md), then [Install](../harness/docs/INSTALL.md) and [Getting started](../harness/docs/GETTING_STARTED.md).
- Looking for something that was in the old `docs/README.md`? That file was the WireViz README. It is now part of the [repository README](../README.md#original-wireviz-readme), and an untouched copy is in [`upstream/README.upstream.md`](upstream/README.upstream.md).

## Contents

- [Getting started](#getting-started)
- [User guides](#user-guides)
- [Reference](#reference)
- [Examples](#examples)
- [Troubleshooting and help](#troubleshooting-and-help)
- [Developer docs](#developer-docs)
- [Project records](#project-records)
- [Upstream WireViz documentation](#upstream-wireviz-documentation)
- [This audit](#this-audit)

## Getting started

| Page | What it gives you |
| --- | --- |
| [Repository README](../README.md) | What the tool is, a quick start of eight commands, and the way to every other page |
| [Tool README](../harness/README.md) | The same for the `harness/` folder, with the status of the tool |
| [Install](../harness/docs/INSTALL.md) | Check your system, install the `.deb`, the `.tar.gz` or run from source, check that it works |
| [Getting started](../harness/docs/GETTING_STARTED.md) | A guided tour in 45 minutes with the real output of every command: example project, generate, read problems, export, fill in values, release |
| [Learning path](../harness/docs/LEARNING_PATH.md) | The whole route in nine steps, each with an example and a "done when" |
| [Concepts](../harness/docs/CONCEPTS.md) | The words and the mental model, in ten minutes |
| [Glossary](../harness/docs/GLOSSARY.md) | Every term and abbreviation used in these pages |

## User guides

| Page | What it gives you |
| --- | --- |
| [User manual](../harness/docs/user-manual/README.md) | One page per task: draw the design, generate harnesses, read and fix problems, fill in engineering values, import data, import KiCad pinouts, export outputs, set wire colours, release a harness, use Git and CI |
| [How-to index](../harness/docs/HOWTO.md) | The old list of recipes, now pointing at the user manual |
| [User guide](../harness/docs/guide/USER_GUIDE.md) | The guide that opens with **F1** in the app: screen, modes, menus, shortcuts |
| [Tips](../harness/docs/TIPS.md) | Shortcuts, power-user workflows, and what can and cannot be exchanged with other tools |
| [Cheat sheet](../harness/docs/CHEATSHEET.md) | One page: the loop, the data imports, release, shortcuts, the folder layout |

## Reference

| Page | What it says |
| --- | --- |
| [Command line](../harness/docs/CLI.md) | Every `harness` command and option (generated from the program) |
| [Design rules](../harness/docs/RULES.md) | Every rule: what, why, how to fix, severity (generated) |
| [Configuration](../harness/docs/CONFIG.md) | Every key of `config/*.json` |
| [Placeholders](../harness/docs/PLACEHOLDERS.md) | Which engineering values are still placeholders and who owns them |
| [Imports](../harness/docs/IMPORTS.md) | Importing interfaces, parts, lengths and engineering values |
| [KiCad](../harness/docs/KICAD.md) | Taking unit connector pinouts from a KiCad netlist |
| [Outputs](../harness/docs/OUTPUTS.md) | Every output file and its limits |
| [File format](../harness/docs/FILE_FORMAT.md) | The project folder format |
| [Templates](../harness/src/harness_design_studio/resources/examples/templates/README.md) | What each template file shipped with the tool is for |
| [Changelog (tool)](../harness/CHANGELOG.md) | What changed, release by release; the [root changelog](../CHANGELOG.md) explains how it relates to WireViz's |

## Examples

| Page | What it gives you |
| --- | --- |
| [Examples](../harness/docs/examples/README.md) | All five example projects: what each shows, how to create and run it, what you should see |
| [The flatsat tour](../harness/docs/FLATSAT_EXAMPLE.md) | A walk through the biggest example: a bench with ground equipment |
| [WireViz examples](../examples/readme.md) and [tutorial](../tutorial/readme.md) | These belong to WireViz, not to Harness Design Studio |

## Troubleshooting and help

| Page | What it gives you |
| --- | --- |
| [Troubleshooting](../harness/docs/TROUBLESHOOTING.md) | Real error messages, why they happen and how to fix them, grouped by when they happen |
| [FAQ](../harness/docs/FAQ.md) | Questions that are not errors |
| [Problem reporting](../harness/compliance/docs/PROBLEM_REPORTING.md) | How to report a problem with the tool |

## Developer docs

| Page | What it gives you |
| --- | --- |
| [Contributing](../CONTRIBUTING.md) | How to propose a change; the rule never to copy WireViz code into the tool |
| [Developer docs](../harness/docs/developer/README.md) | Setup and tests, architecture overview, keeping the documents correct, releasing, the tool scripts, refreshing the upstream README |
| [Architecture](../harness/docs/ARCHITECTURE.md) | Layers and the real source layout |
| [Decisions](../harness/docs/DECISIONS.md) | Every decision and why |
| [Security](../harness/docs/SECURITY.md) | The security review and what the tool does to protect files |
| [Release procedure](../harness/docs/RELEASE.md) | The checklist for releasing the tool (not the same as releasing a harness) |
| [Assistant instructions](../harness/CLAUDE.md) | Commands, layout and conventions, written for the AI assistant that builds the tool |

## Project records

These explain how the tool was specified and checked. You do not need them to use it.

| Page | What it is |
| --- | --- |
| [Specification](../harness/docs/SPEC.md), [Requirements](../harness/docs/REQUIREMENTS.md) | What the tool must do |
| [UX design record](../harness/docs/UX.md), [UX guidelines review](../harness/docs/UX_GUIDELINES_REVIEW.md) | How it should feel, and the owner's guidelines point by point |
| [Plan](../harness/docs/PLAN.md), [Milestone notes](../harness/docs/demos/README.md) | The milestone plan and the note from each milestone |
| [Open decisions](../harness/docs/OPEN_DECISIONS.md) | What still needs the owner |
| [October audit](../harness/docs/AUDIT.md) | The audit of 2026-10-07 |
| [Usability kit](../harness/docs/usability/README.md) | Test material for usability sessions (waived by the owner) |
| [Compliance records](../harness/compliance/README.md) | The ECSS/ESCC self-assessment, deviations and waivers, sign-off, risk register. It makes no claim of compliance. |

## Upstream WireViz documentation

These belong to [WireViz](https://github.com/wireviz/WireViz) and are kept as upstream wrote them.

| Page | What it is |
| --- | --- |
| [Original README](upstream/README.upstream.md) | Untouched copy (also embedded in the [repository README](../README.md#original-wireviz-readme)) |
| [Syntax](syntax.md) | The WireViz input file syntax |
| [Advanced image usage](advanced_image_usage.md) | Images in connectors and cables |
| [Build script](buildscript.md) | Rebuilding the examples and the tutorial |
| [Contributing](CONTRIBUTING.md) | How to contribute to WireViz |
| [Changelog](CHANGELOG.md) | WireViz's changelog |
| [Tutorial](../tutorial/readme.md), [Examples](../examples/readme.md) | Sample files and the example gallery |

## This audit

[DOCS_AUDIT.md](DOCS_AUDIT.md) records what was wrong with the documentation, what was changed, and what was left for the owner.

### Where is the page for …?

| You looked for | It is |
| --- | --- |
| `getting-started.md` | [`harness/docs/GETTING_STARTED.md`](../harness/docs/GETTING_STARTED.md) |
| `faq.md` | [`harness/docs/FAQ.md`](../harness/docs/FAQ.md) |
| `troubleshooting.md` | [`harness/docs/TROUBLESHOOTING.md`](../harness/docs/TROUBLESHOOTING.md) |
| `glossary.md` | [`harness/docs/GLOSSARY.md`](../harness/docs/GLOSSARY.md) |
| `tips.md` | [`harness/docs/TIPS.md`](../harness/docs/TIPS.md) |
| `user-manual/` | [`harness/docs/user-manual/`](../harness/docs/user-manual/README.md) |
| `examples/` | [`harness/docs/examples/`](../harness/docs/examples/README.md) |
| `developer/` | [`harness/docs/developer/`](../harness/docs/developer/README.md) |

The tool's pages use upper-case names (`FAQ.md`) in `harness/docs/` because that is the style they already had and because tests check those names.

Next: [Install](../harness/docs/INSTALL.md).
