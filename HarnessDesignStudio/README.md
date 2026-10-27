# Harness Design Studio

## In five minutes

Harness Design Studio is an offline desktop tool for the electrical harnesses of a spacecraft, made for systems engineers and for electrical / AIT engineers. You describe the devices and the interfaces between them; it generates the harnesses, checks them and writes the build workbook and lists. Try it on a practice project (these are the commands of Parts 1 to 3 and 6 of [`GETTING_STARTED.md`](docs/GETTING_STARTED.md)):

    harness-design-studio new wheel-link --template first-steps
    harness-design-studio validate wheel-link
    harness-design-studio generate wheel-link
    harness-design-studio verify wheel-link
    harness-design-studio export wheel-link

The files are in `wheel-link/outputs/`. The full 45-minute tutorial is [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md). **Honest limits:** the tool was written mainly by an AI and no other person has reviewed it independently, no engineering values are supplied until your project enters them (results say *pending* or *not checked*), and the owner has not signed any release off (see the notes below).

An offline desktop tool for designing the electrical harnesses of a spacecraft.

> **Created mainly by an AI.** Harness Design Studio was written mainly by Claude, Anthropic's AI assistant, used through Claude Code; the repository owner set the requirements and approved the decisions and releases. No other person has reviewed it independently (waived by the owner, see [`compliance/DEVIATIONS.md`](compliance/DEVIATIONS.md)), and no compliance with any standard is claimed. Check its results before relying on them.
>
> **Based in the WireViz repository.** This repository is a fork of [WireViz](https://github.com/wireviz/WireViz). Harness Design Studio is a separate, clean-room codebase inside it: no WireViz code is copied or imported (D-01 in [`docs/DECISIONS.md`](docs/DECISIONS.md)), and WireViz is an export target (WireViz-style YAML, best effort). The original WireViz documentation is in the [repository README](../README.md#original-wireviz-readme); [`../docs/README.md`](../docs/README.md) is the index of all documents.

You describe the **devices** (computer, power unit, reaction wheel ...) and the **interfaces** between them. The tool generates the harnesses (connectors, pins, wires), checks them, writes a build workbook and lists for every harness (and the PDF drawings, if you ask for them), and keeps a change-controlled record of every release. A harness is the bundle of wires and connectors that joins the devices; words you do not know are in the [glossary](docs/GLOSSARY.md).

```
 you draw                      the tool makes                  the tool writes
 devices + interfaces ──►      harnesses: connectors,   ──►    build workbook, wire lists,
                               pins, wires, with a             pinouts, BOM, test tables,
                               reason for each choice          labels, block diagram, change log
```

- **Your design is the source of truth.** Harnesses, drawings and lists are generated from it and can be regenerated at any time.
- **You can still edit what it makes.** Set the gauge, type, colour or length of a single wire, draw a wire yourself, put several wires on one pin, twist or shield wires together, give pins a function and connectors and harnesses a label; Generate keeps all of it ([`docs/user-manual/edit-a-wire.md`](docs/user-manual/edit-a-wire.md)). A device you defined down to each pin can be saved to a device library file and added to another project.
- **You can start with less on screen.** Since 1.7.0 a **Next step** page names one thing to do at a time, with one button, and the project tree, the inspector and the Problems panel start closed. New in 1.8.0 this is the **Systems engineer** role: a first start asks *Who are you working as?* and the answer, **Systems engineer** or **Electrical / AIT engineer** (every area and panel), decides what the window shows first; **View > Role** changes it at once, and it is a view, never a permission ([`docs/user-manual/choose-your-role.md`](docs/user-manual/choose-your-role.md)).
- **You can start from nothing.** A blank project shows an **Add a device** button for its first device (1.6.0). **New harness…** (1.5.0) makes a harness with no interface behind it; you add its connectors in the Connectors tab and draw its wires in Edit wire, and Generate leaves it as it is ([`docs/user-manual/build-a-harness-by-hand.md`](docs/user-manual/build-a-harness-by-hand.md)).
- **You can start from your pinout.** New in 1.8.0: join two connectors pin by pin; the program proposes the pairs from the signal names on the pins, you confirm them, **Check my connections** reviews them, and **Create harness** makes a harness only when you press it ([how](docs/user-manual/connect-two-connectors.md)).
- **You can share devices and subsystems.** New in 1.8.0: a **library folder** on a shared drive or in a Git repository holds device files and subsystem files (devices with the connections between them); **File > Library…** opens a window of its own to search it, preview an entry and add it to the project in one undo step, and **Number of these devices** says how many of a device there are. The program stays offline and writes into the folder only when you press **Save to library** ([how](docs/user-manual/use-the-library.md)).
- **Offline.** It never uses the network (a test enforces this).
- **Reproducible.** The same design always produces byte-identical files, so Git diffs show real changes only.
- **Starts from the usual standards.** RS-422, RS-485 and CAN for communication, Micro-D (9 to 31 pin) for power and data, Ethernet as the alternative for high data rates, SMA for RF (what each one is: [glossary](docs/GLOSSARY.md)). Other types and connectors can be added.
- **Honest about what it does not know.** Engineering values (derating, ampacity, EMC rules, approved parts; see the [glossary](docs/GLOSSARY.md)) are never invented. Until you supply them, results say *pending* or *not checked*.

Runs on **Ubuntu 24.04 or newer**; packages for **Windows 10 and 11** are built from version 1.2.0 on ([`docs/INSTALL.md`](docs/INSTALL.md), decision D-149); macOS is not supported (D-168). The latest published release is version `1.8.0`, published on 2026-10-26 (connections between connectors, pin by pin, with the pinout first; editing a connector, a group and all wires; a library folder that a team shares, with subsystems and a number of the same device; two roles, Systems engineer and Electrical / AIT engineer; decisions D-172 to D-176; see [Status](#status)); version `1.7.0` (a build workbook for every harness, the build data a technician needs, a simple workspace) was published on 2026-10-22.

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

3. **Look at the result**: the build workbook of each harness (`harnesses/W001/W001_build.xlsx`, an Excel file to build the harness from) and the lists are in `wheel-link/outputs/`; the PDF drawings are written only with `harness-design-studio export wheel-link --drawings` (the build workbook and this option are new in 1.7.0). Open the project in the app (**Harness Design Studio** in the application menu, then **File > Open project…**): as a Systems engineer it opens on the *Next step* page, which names what to do next, and as an Electrical / AIT engineer it opens on the diagram (the first start asks which you are; **View > Role** changes it). The diagram is in the *Model* area, the checks in *Checks* and, in the *Drawings* area of the Electrical / AIT engineer, the *Why* explanation of every wire.

That is the whole idea. [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) walks through it step by step with the real output of every command.

## Documentation

| You are | Start with |
| --- | --- |
| **new to the tool** | [`docs/LEARNING_PATH.md`](docs/LEARNING_PATH.md): the route in nine steps. Or directly [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md): your first harness in 45 minutes, then [`docs/CONCEPTS.md`](docs/CONCEPTS.md): how the tool thinks, in ten minutes. |
| **installing it** | [`docs/INSTALL.md`](docs/INSTALL.md) |
| **doing a task** (draw, generate, edit a wire, build a harness by hand, import, KiCad, devices, export, colours, release, Git, CI) | [`docs/user-manual/`](docs/user-manual/README.md): one page per task |
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
| `first-steps` | Three devices, a power link and an RS-422 link. Nothing generated yet. Start here. |
| `minimal-satellite` | Seven devices, nominal only: solar array, battery, power unit, computer, radio, wheel and sun sensor. A small but realistic starting point. |
| `small-satellite` | 14 devices with redundant chains. Generate it to see a realistic system. |
| `flatsat` | A complete bench: 23 flight and ground devices, generated, with example numbers. Read [`docs/FLATSAT_EXAMPLE.md`](docs/FLATSAT_EXAMPLE.md) for a tour. |

`harness-design-studio templates my-templates` copies templates for your own data: CSV files for interfaces, approved parts and segment lengths, example rows for the build data (strip lengths, pin contacts, accessories; new in 1.7.0), a KiCad netlist, a CI script, a GitHub Actions workflow, a **design worksheet** to plan a design on paper, a design review checklist and *demo* engineering values for learning (not engineering data). What each file is for: [`src/harness_design_studio/resources/examples/templates/README.md`](src/harness_design_studio/resources/examples/templates/README.md).

## What is in a project

A project is a folder of small JSON files (`project.json`, `config/`, `library/`, `logical/`, `physical/`, ...). Put it in Git. Outputs go to `outputs/` and are always safe to delete and regenerate. Format: [`docs/FILE_FORMAT.md`](docs/FILE_FORMAT.md).

## Status

Version `1.8.0` (decisions D-172 to D-176; the workshop feedback of 2026-10-23: connections between connectors pin by pin with the pinout first, editing a connector, a group and all wires, a library folder that a team shares with subsystems and a number of the same device, two roles) is the latest published release. It was published on 2026-10-26 as the tag `v1.8.0` on commit `1f7431e`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip` and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner. See [`docs/releases/1.8.0.md`](docs/releases/1.8.0.md) and the [changelog](CHANGELOG.md).

Version `1.7.0` (decisions D-169, D-170 and D-171) was published on 2026-10-22 as the tag `v1.7.0` on commit `e5d8b1e`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip` and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner. It has two parts. First, every harness gets a build workbook, `harnesses/<ID>/<ID>_build.xlsx`, which also shows the build data a technician needs when you enter it: the strip length at each end of a wire, the contact on each pin and its crimp tool, and the sleeving, heat shrink, labels and backshells of the harness (fields in the app and `harness-design-studio import-build-data`; see [`docs/user-manual/enter-the-build-data.md`](docs/user-manual/enter-the-build-data.md)). The PDF drawings of the harnesses are written only with `harness-design-studio export DIR --drawings` (in the app: the check box **Include the PDF drawings**). Second, a **simple workspace**: a *Next step* page that names one thing to do at a time, and fewer things on screen (stages S1 and S2; the setting *Simple* or *Full* in the View menu and *Workspace* in Settings; a first run opens in Simple, anyone who already has settings keeps Full). In 1.8.0 these two workspaces became the roles *Systems engineer* and *Electrical / AIT engineer* (decision D-176; see [`docs/user-manual/choose-your-role.md`](docs/user-manual/choose-your-role.md)). Not built: a first-project stage (S4) and the measurement with the testers, so nothing here claims that the tool is easier to use; the plain-words stage (S3) was discarded by the owner. See the [changelog](CHANGELOG.md).

macOS support was removed on 2026-10-21 (decision D-168): the tool runs on Ubuntu 24.04 and newer and Windows 10 and 11; the releases 1.2.0 to 1.5.0 still carry their two macOS disk images on GitHub, which are not maintained or tested any more. Version `1.6.0` (no macOS, an Add a device button and corrected texts on the start screen of a blank project; decision D-168) was published on 2026-10-21 as the tag `v1.6.0` on commit `21f4716`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip` and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner either. Version `1.5.0` (a harness made by hand with no interface, a plain message when a Linux machine lacks a system library, packages checked without any Python on the machine; decisions D-166 and D-167) was published on 2026-10-21 as the tag `v1.5.0` on commit `4365368`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip`, the two macOS disk images and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner either. Version `1.4.0` (wire editing, hand-drawn wires, a function on every pin, labels, the last commit, a device library; decisions D-160 to D-165) was published on 2026-10-20 as the tag `v1.4.0` on commit `1427aad`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip`, the two macOS disk images and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner either. Version `1.3.0` (the new user interface, decisions D-150 to D-159) was published on 2026-10-20 as the tag `v1.3.0` on commit `e7cf531`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip`, the two macOS disk images and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner either. Version `1.2.0` (packages for Windows and macOS, decision D-149) was published on 2026-10-19 as the tag `v1.2.0` on commit `1cdd6a7`; the `.deb`, the `.tar.gz`, the Windows setup program and `.zip`, the two macOS disk images and `SHA256SUMS` are on the GitHub release page, and the packages are not signed. It has not been signed off by the owner either. Version `1.1.0` was published on 2026-10-18 as the tag `v1.1.0` on commit `f998cd9`; the `.deb`, the `.tar.gz` and `SHA256SUMS` are on the GitHub release page. It has not been signed off by the owner (`docs/RELEASE.md` step 14); `compliance/SIGNOFF.md` records the release decision for 1.0.0 and, after the fact, the publication of 1.1.0, 1.2.0, 1.3.0, 1.4.0, 1.5.0, 1.6.0 and 1.7.0 (their checksums are in `compliance/evidence/`); it records no owner sign-off for them. Version `1.0.0`, released on the owner's instruction on 2026-10-12 ([`compliance/SIGNOFF.md`](compliance/SIGNOFF.md); all the records are indexed in [`compliance/README.md`](compliance/README.md)). It was published on 2026-10-12 as the tag `v1.0.0` on commit `0c6a96a`; the `.deb`, the `.tar.gz` and `SHA256SUMS` are on the GitHub release page. Documents changed after that commit are on `master` but are not inside those packages. It is not a statement of compliance with any standard. On 2026-10-12 the assistant recorded defaults for the four open engineering decisions under the owner's delegation, which the owner can change later ([`docs/DECISIONS.md`](docs/DECISIONS.md) D-142 to D-145): the harness boundary rule (D-10) and the title block (D-15) are the documented defaults the tool implements; the tool ships no derating or EMC values (D-11) and no approved parts list (D-12), so each project supplies them and until then results rest on placeholders and example parts. The licence of `HarnessDesignStudio/` stays the placeholder `LicenseRef-Proprietary` (D-02, D-143). Not done and waived by the owner: independent review, usability sessions, a screen-reader pass and a clean-machine installation test; the packages are not signed ([`compliance/DEVIATIONS.md`](compliance/DEVIATIONS.md)). See [`docs/OPEN_DECISIONS.md`](docs/OPEN_DECISIONS.md) (the options as they were) and [`docs/RELEASE.md`](docs/RELEASE.md). Until the engineering values exist, results say so. The [changelog](CHANGELOG.md) lists what is new since 0.1.0.

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
