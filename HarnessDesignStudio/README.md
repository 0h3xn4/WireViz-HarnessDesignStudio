# Harness Design Studio

An offline desktop tool for designing the electrical harnesses of a spacecraft.

> **Created mainly by an AI.** Harness Design Studio was written mainly by Claude, Anthropic's AI assistant, used through Claude Code; the repository owner set the requirements and approved the decisions and releases. No other person has reviewed it independently (waived by the owner, see [`compliance/DEVIATIONS.md`](compliance/DEVIATIONS.md)), and no compliance with any standard is claimed. Check its results before relying on them.
>
> **Based in the WireViz repository.** This repository is a fork of [WireViz](https://github.com/wireviz/WireViz). Harness Design Studio is a separate, clean-room codebase inside it: no WireViz code is copied or imported (D-01 in [`docs/DECISIONS.md`](docs/DECISIONS.md)), and WireViz is an export target (WireViz-style YAML, best effort). The original WireViz documentation is in the [repository README](../README.md#original-wireviz-readme); [`../docs/README.md`](../docs/README.md) is the index of all documents.

You describe the **units** (computer, power unit, reaction wheel ...) and the **interfaces** between them. The tool generates the harnesses (connectors, pins, wires), checks them, writes the drawings and lists, and keeps a change-controlled record of every release. A harness is the bundle of wires and connectors that joins the units; words you do not know are in the [glossary](docs/GLOSSARY.md).

```
 you draw                      the tool makes                  the tool writes
 units + interfaces   ──►      harnesses: connectors,   ──►    drawings, wire lists, pinouts,
                               pins, wires, with a             BOM, test tables, labels,
                               reason for each choice          block diagram, change log
```

- **Your design is the source of truth.** Harnesses, drawings and lists are generated from it and can be regenerated at any time.
- **Offline.** It never uses the network (a test enforces this).
- **Reproducible.** The same design always produces byte-identical files, so Git diffs show real changes only.
- **Starts from the usual standards.** RS-422, RS-485 and CAN for communication, Micro-D (9 to 31 pin) for power and data, Ethernet as the alternative for high data rates, SMA for RF (what each one is: [glossary](docs/GLOSSARY.md)). Other types and connectors can be added.
- **Honest about what it does not know.** Engineering values (derating, ampacity, EMC rules, approved parts; see the [glossary](docs/GLOSSARY.md)) are never invented. Until you supply them, results say *pending* or *not checked*.

Runs on **Ubuntu 24.04 or newer**; packages for **Windows 10 and 11** and **macOS 13 or newer** are built from version 1.2.0 on ([`docs/INSTALL.md`](docs/INSTALL.md), decision D-149). The latest published release is version `1.3.0` (the new user interface; see [Status](#status)).

## Try it in five minutes

1. **Install** (details in [`docs/INSTALL.md`](docs/INSTALL.md)):

   ```
   sudo apt install ./harness-design-studio_<version>_amd64.deb
   harness-design-studio --version
   ```

2. **Make a practice project** from the built-in example and let the tool work on it:

   ```
   harness-design-studio new wheel-link --template first-steps
   harness-design-studio generate wheel-link
   harness-design-studio drc wheel-link
   harness-design-studio export wheel-link
   ```

   (`harness` still works as a short name for `harness-design-studio`.)

3. **Look at the result**: drawings and lists are in `wheel-link/outputs/`. Open the project in the app (**Harness Design Studio** in the application menu, then **File > Open project…**) to see the diagram, the *Checks* tab and, in the *Harness* tab, the *Why* explanation of every wire.

That is the whole idea. [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) walks through it step by step with the real output of every command.

## Documentation

| You are | Start with |
| --- | --- |
| **new to the tool** | [`docs/LEARNING_PATH.md`](docs/LEARNING_PATH.md): the route in nine steps. Or directly [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md): your first harness in 45 minutes, then [`docs/CONCEPTS.md`](docs/CONCEPTS.md): how the tool thinks, in ten minutes. |
| **installing it** | [`docs/INSTALL.md`](docs/INSTALL.md) |
| **doing a task** (draw, generate, import, KiCad, export, colours, release, Git, CI) | [`docs/user-manual/`](docs/user-manual/README.md): one page per task |
| **looking something up** | [`docs/CLI.md`](docs/CLI.md) (every command), [`docs/guide/USER_GUIDE.md`](docs/guide/USER_GUIDE.md) (the **user guide**, also in the app: **F1**), the one-page [`docs/CHEATSHEET.md`](docs/CHEATSHEET.md), [`docs/TIPS.md`](docs/TIPS.md), the [glossary](docs/GLOSSARY.md) |
| **stuck** | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) (error messages and fixes), [`docs/FAQ.md`](docs/FAQ.md) (questions) |
| **wanting to see what changed** | [`CHANGELOG.md`](CHANGELOG.md) |
| **an engineer supplying values** | [`docs/CONFIG.md`](docs/CONFIG.md), [`docs/PLACEHOLDERS.md`](docs/PLACEHOLDERS.md), [`docs/IMPORTS.md`](docs/IMPORTS.md) |
| **a reviewer or releaser** | [`docs/RULES.md`](docs/RULES.md), [`docs/OUTPUTS.md`](docs/OUTPUTS.md), the review checklist in the templates |
| **a developer** | [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`docs/developer/`](docs/developer/README.md), [`CLAUDE.md`](CLAUDE.md), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/DECISIONS.md`](docs/DECISIONS.md), [`docs/SECURITY.md`](docs/SECURITY.md) |

[`../docs/README.md`](../docs/README.md) is the index of every document in the repository; [`docs/README.md`](docs/README.md) is the index of this tool's documents.

## Examples and templates

`harness-design-studio new --list` shows the example projects shipped with the tool. All five, with what to run and what you should see, are on the [examples page](docs/examples/README.md). `minimal-satellite`, `flatsat` and the `design-worksheet.md` template are new in 1.0.0; the 0.1.0 packages have `blank`, `first-steps` and `small-satellite` only.

| Example | What it is |
| --- | --- |
| `blank` | An empty project with the starter parts and interface types. Start a real design here. |
| `first-steps` | Three units, a power link and an RS-422 link. Nothing generated yet. Start here. |
| `minimal-satellite` | Seven units, nominal only: solar array, battery, power unit, computer, radio, wheel and sun sensor. A small but realistic starting point. |
| `small-satellite` | 14 units with redundant chains. Generate it to see a realistic system. |
| `flatsat` | A complete bench: 23 flight and ground units, generated, with example numbers. Read [`docs/FLATSAT_EXAMPLE.md`](docs/FLATSAT_EXAMPLE.md) for a tour. |

`harness-design-studio templates my-templates` copies templates for your own data: CSV files for interfaces, approved parts and segment lengths, a KiCad netlist, a CI script, a GitHub Actions workflow, a **design worksheet** to plan a design on paper, a design review checklist and *demo* engineering values for learning (not engineering data). What each file is for: [`src/harness_design_studio/resources/examples/templates/README.md`](src/harness_design_studio/resources/examples/templates/README.md).

## What is in a project

A project is a folder of small JSON files (`project.json`, `config/`, `library/`, `logical/`, `physical/`, ...). Put it in Git. Outputs go to `outputs/` and are always safe to delete and regenerate. Format: [`docs/FILE_FORMAT.md`](docs/FILE_FORMAT.md).

## Status

Version `1.3.0` (the new user interface, decisions D-150 to D-159) was published on 2026-10-20 as the tag `v1.3.0` on commit `e7cf531`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip`, the two macOS disk images and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner either. Version `1.2.0` (packages for Windows and macOS, decision D-149) was published on 2026-10-19 as the tag `v1.2.0` on commit `1cdd6a7`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip`, the two macOS disk images and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner either. Version `1.1.0` was published on 2026-10-18 as the tag `v1.1.0` on commit `f998cd9`; the `.deb`, the `.tar.gz` and `SHA256SUMS` are on the GitHub release page. It has not been signed off by the owner (`docs/RELEASE.md` step 14); `compliance/SIGNOFF.md` records the release decision for 1.0.0 and, after the fact, the publication of 1.1.0, 1.2.0 and 1.3.0 (their checksums are in `compliance/evidence/`); it records no owner sign-off for them. Version `1.0.0`, released on the owner's instruction on 2026-10-12 ([`compliance/SIGNOFF.md`](compliance/SIGNOFF.md); all the records are indexed in [`compliance/README.md`](compliance/README.md)). It was published on 2026-10-12 as the tag `v1.0.0` on commit `0c6a96a`; the `.deb`, the `.tar.gz` and `SHA256SUMS` are on the GitHub release page. Documents changed after that commit are on `master` but are not inside those packages. It is not a statement of compliance with any standard. On 2026-10-12 the assistant recorded defaults for the four open engineering decisions under the owner's delegation, which the owner can change later ([`docs/DECISIONS.md`](docs/DECISIONS.md) D-142 to D-145): the harness boundary rule (D-10) and the title block (D-15) are the documented defaults the tool implements; the tool ships no derating or EMC values (D-11) and no approved parts list (D-12), so each project supplies them and until then results rest on placeholders and example parts. The licence of `HarnessDesignStudio/` stays the placeholder `LicenseRef-Proprietary` (D-02, D-143). Not done and waived by the owner: independent review, usability sessions, a screen-reader pass and a clean-machine installation test; the packages are not signed ([`compliance/DEVIATIONS.md`](compliance/DEVIATIONS.md)). See [`docs/OPEN_DECISIONS.md`](docs/OPEN_DECISIONS.md) (the options as they were) and [`docs/RELEASE.md`](docs/RELEASE.md). Until the engineering values exist, results say so. The [changelog](CHANGELOG.md) lists what is new since 0.1.0.

## For developers

Clean-room project: never copy code from `../src/wireviz` (GPL-3.0). Start with [`../CONTRIBUTING.md`](../CONTRIBUTING.md) and [`docs/developer/`](docs/developer/README.md), then [`CLAUDE.md`](CLAUDE.md) (commands, layout, conventions), [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md), [`docs/DECISIONS.md`](docs/DECISIONS.md) and [`docs/SECURITY.md`](docs/SECURITY.md). Release procedure: [`docs/RELEASE.md`](docs/RELEASE.md).

```
python3 -m venv .venv && . .venv/bin/activate && pip install -e ".[gui,dev]"
pytest --cov      # tests; the 90% core coverage gate applies with --cov
pytest -n auto -m "not perf" && pytest -m perf   # the same in parallel (pytest-xdist), timing tests last and alone
ruff format . && ruff check . && mypy
python -m tools.release_check --quick
```

Next: [`docs/INSTALL.md`](docs/INSTALL.md), [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md).
