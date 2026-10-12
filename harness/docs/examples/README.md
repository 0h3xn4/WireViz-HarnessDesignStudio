# Examples

This page describes the five example projects and the 15 template files that ship with Harness Design Studio, with the real output of each, so that you can pick one and know what to expect.

## Contents

- [At a glance](#at-a-glance)
- [Which build do you have?](#which-build-do-you-have)
- [blank](#blank)
- [first-steps](#first-steps)
- [minimal-satellite](#minimal-satellite)
- [small-satellite](#small-satellite)
- [flatsat](#flatsat)
- [Does every example run?](#does-every-example-run)
- [The 15 template files](#the-15-template-files)
- [WireViz examples in this repository](#wireviz-examples-in-this-repository)

Every command below was run with the tool (version `0.1.0`, built from `master`) in an empty folder, one project per example, and the output is pasted as printed. The names `my-blank`, `my-first-steps` and so on are the folder names used in the commands; use your own.

## At a glance

| Example | Units | Interfaces | Starts generated? | What it is for | In the 0.1.0 packages? |
| --- | --- | --- | --- | --- | --- |
| [`blank`](#blank) | 0 | 0 | no | your own design from nothing | yes |
| [`first-steps`](#first-steps) | 3 | 2 | no | the tutorial; a first harness in minutes | yes |
| [`minimal-satellite`](#minimal-satellite) | 7 | 11 | no | a small, realistic spacecraft to copy and adapt | **no, newer builds only** |
| [`small-satellite`](#small-satellite) | 14 | 24 | no | redundancy (main and backup chains) and a larger diagram | yes |
| [`flatsat`](#flatsat) | 23 | 44 | yes (8 harnesses) | a whole bench setup with ground equipment | **no, newer builds only** |

If a word here is new to you, see [`GLOSSARY.md`](../GLOSSARY.md). Every example uses the tool's **example parts** (their part numbers start with `EX-`), and every configuration file except `naming.json` is still marked `"placeholder": true`. None of the examples is engineering data, and none is a statement that anything complies with a standard.

## Which build do you have?

`harness --version` prints `0.1.0` for the released packages **and** for the current development source, so the version number cannot tell them apart. Ask the tool which examples it has:

```
harness new --list
```

A **newer build** (from `master`) lists five:

```
blank              An empty project: starter parts and interface types, no units.
first-steps        Three units, a power link and an RS-422 link. Nothing is generated yet: start here.
minimal-satellite  Seven units, nominal only: power, computer, radio, wheel and sun sensor. Adapt it.
small-satellite    14 units with nominal and redundant chains. Generate it to see a realistic system.
flatsat            A complete bench: 23 flight and ground units, generated, with example numbers.
```

The **released 0.1.0 packages** (the `.deb` and the `.tar.gz`) list three. This is what the source of the `v0.1.0` tag printed:

```
blank            An empty project: starter parts and interface types, no units.
first-steps      Three units, a power link and an RS-422 link. Nothing is generated yet: start here.
small-satellite  14 units with nominal and redundant chains. Generate it to see a realistic system.
```

`minimal-satellite`, `flatsat` and the template `design-worksheet.md` are on `master` but not in the 0.1.0 packages ([`CHANGELOG.md`](../../CHANGELOG.md) of the tool, section *Unreleased*). Asking for them from a 0.1.0 package gives `error: Unknown template 'minimal-satellite'. Choose one of: blank, first-steps, small-satellite.` ([`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md#creating-a-project)). The counts quoted on this page are the same on both builds for `blank`, `first-steps` and `small-satellite`; the *model hash* of `first-steps` and `small-satellite` differs between the builds (the example files were rebuilt), so a hash quoted here will not match a 0.1.0 package. The drawings also differ: the wiring-diagram drawing with wire colours is newer than 0.1.0. To get a newer build, see way C in [`INSTALL.md`](../INSTALL.md).

The same five commands work on every example: `new`, `validate`, `generate`, `drc`, `export`, and `verify --outputs`. The project's model hash and the Open line of `drc` below are printed **after** `generate`; before that the hash differs (it covers the generated harnesses too). A project created with `--name` has a different hash for the same design, because the name is part of the design.

## blank

**What it shows:** an empty project: the starter parts library (example connectors, contacts, wires), the 17 interface types, the seven configuration files (six of them placeholders), two lanes called `panel-A` and `panel-B`, and no units. It is where your own design starts. The command line cannot add units or interfaces; open the project in the app and add them (Part 10 of [`GETTING_STARTED.md`](../GETTING_STARTED.md)).

```
harness new my-blank --template blank
```

```
Project 'My project' created in my-blank (0 units, 0 interfaces).
Next: harness validate my-blank   or open it in the app (File > Open project).
```

```
harness generate my-blank
harness drc my-blank
```

```
0 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
0 interfaces and 0 wires checked: 0 error(s)
# Design rule check: My project

Model hash: `83e9a4b5c394`. Rules run: 33.
Open: 0 error(s), 0 warning(s), 0 note(s). Waived: 0.
```

`harness validate my-blank` ends with `0 units, 0 interfaces, 0 connectors, 0 harnesses: 0 error(s), 0 warning(s).` Exporting an empty project is not possible and says so (exit code 1): `error: there are no harnesses to export; run `harness generate` first.` Next, in the app: **File > Open project...**.

## first-steps

**What it shows:** three units (`RW1` a reaction wheel, `OBC1` the on-board computer, `PCDU1` a power unit) and two interfaces: a primary-power link from `PCDU1` to `RW1`, and an RS-422 data link from `OBC1` to `RW1`. Nothing is generated yet. This is the project of the tutorial: you generate two harnesses (`W001` for the data link, `W002` for the power link), read the problems, fill in the gaps and release one. Start here.

```
harness new my-first-steps --template first-steps
```

```
Project 'First steps: reaction wheel link' created in my-first-steps (3 units, 2 interfaces).
Next: harness validate my-first-steps   or open it in the app (File > Open project).
```

```
harness validate my-first-steps
harness generate my-first-steps
harness drc my-first-steps
```

```
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
3 units, 2 interfaces, 9 connectors, 0 harnesses: 0 error(s), 0 warning(s).
2 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
# Design rule check: First steps: reaction wheel link

Model hash: `91531b45fd2c`. Rules run: 33.
Open: 0 error(s), 10 warning(s), 8 note(s). Waived: 0.
```

```
harness export my-first-steps
```

```
38 files written to my-first-steps/outputs (model 91531b45fd2c).
```

All ten warnings say that an example part is used and nobody has approved it. The notes say which checks did not run because their numbers are missing, and which choices nobody has confirmed yet. That is the tool being honest, not a failure. **Next:** the walk-through in [`GETTING_STARTED.md`](../GETTING_STARTED.md) (about 45 minutes) or the nine steps of [`LEARNING_PATH.md`](../LEARNING_PATH.md). The tutorial quotes a different hash because it creates the project with `--name "Wheel link"`.

## minimal-satellite

**What it shows:** a small spacecraft with no redundancy, between `first-steps` and `small-satellite`: seven units (`SA1` solar array, `BAT1` battery, `PCDU1` power distribution unit, `OBC1` computer, `TRX1` transceiver, `RW1` reaction wheel, `SS1` sun sensor) and 11 interfaces, in two lanes `panel-A` and `panel-B`. A good starting point to copy, then rename, add and remove units to describe your own spacecraft. **Newer builds only; not in the 0.1.0 packages.**

```
harness new my-minimal-satellite --template minimal-satellite
```

```
Project 'Minimal satellite' created in my-minimal-satellite (7 units, 11 interfaces).
Next: harness validate my-minimal-satellite   or open it in the app (File > Open project).
```

```
harness generate my-minimal-satellite
harness drc my-minimal-satellite
```

```
11 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
11 interfaces and 24 wires checked: 0 error(s)
# Design rule check: Minimal satellite

Model hash: `b236e927941b`. Rules run: 33.
Open: 0 error(s), 15 warning(s), 17 note(s). Waived: 0.
```

`harness validate` first reports `7 units, 11 interfaces, 37 connectors, 0 harnesses: 0 error(s), 0 warning(s).` and `harness export` then writes `137 files written to my-minimal-satellite/outputs (model b236e927941b).` **Next:** open it in the app, look at the diagram, and compare it with your own spacecraft. The template `design-worksheet.md` (also newer builds only) helps you plan the units and interfaces of your own on paper first.

## small-satellite

**What it shows:** 14 units and 24 interfaces with **nominal and redundant chains**: a redundant computer (`OBC1-R`) and power unit (`PCDU1-R`) next to the main ones, a battery, solar array, transceiver, payload, star tracker, two reaction wheels, sun sensor, magnetorquer and a heater panel, in three lanes (`bus`, `aocs`, `payload`). The tool keeps the two chains in separate connectors and harnesses and warns if something connects them. It is the example to read when you want to see a realistic diagram and how redundancy looks. A trial of this example is recorded in [`TRIAL_small_satellite.md`](../demos/TRIAL_small_satellite.md).

```
harness new my-small-satellite --template small-satellite
```

```
Project 'Small satellite (reference)' created in my-small-satellite (14 units, 24 interfaces).
Next: harness validate my-small-satellite   or open it in the app (File > Open project).
```

```
harness generate my-small-satellite
harness drc my-small-satellite
```

```
24 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
24 interfaces and 54 wires checked: 0 error(s)
# Design rule check: Small satellite (reference)

Model hash: `02ebf01ed3a9`. Rules run: 33.
Open: 0 error(s), 20 warning(s), 28 note(s). Waived: 0.
```

`harness validate` first reports `14 units, 24 interfaces, 75 connectors, 0 harnesses: 0 error(s), 0 warning(s).` and `harness export` writes `280 files written to my-small-satellite/outputs (model 02ebf01ed3a9).` With the default grouping it makes 24 harnesses; [`TIPS.md`](../TIPS.md#choose-how-interfaces-are-grouped-into-harnesses) shows what the other two grouping modes give (23 and 5). **Next:** in the app, select a unit and use **Create redundant copy** on it, or read the Problems tab.

## flatsat

**What it shows:** a complete bench setup, the biggest example. 23 units (flight units and the ground equipment that drives them: a checkout system, a ground power supply and RF test equipment), 44 interfaces, four lanes (`egse`, `bus`, `aocs`, `payload`), eight harnesses and 103 wires, grouped by pair of lanes (`per_zone_pair`). Unlike the others it **ships already generated**, with example numbers filled in, so that every output has content from the first minute; the numbers and parts are for learning only. **Newer builds only; not in the 0.1.0 packages.** A guided tour with exercises is in [`FLATSAT_EXAMPLE.md`](../FLATSAT_EXAMPLE.md).

```
harness new my-flatsat --template flatsat
```

```
Project 'Flatsat (EXAMPLE numbers, not engineering data)' created in my-flatsat (23 units, 44 interfaces).
Next: harness validate my-flatsat   or open it in the app (File > Open project).
```

```
harness validate my-flatsat
harness generate my-flatsat
harness drc my-flatsat
```

```
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
23 units, 44 interfaces, 197 connectors, 8 harnesses: 0 error(s), 0 warning(s).
0 added, 0 changed, 8 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
44 interfaces and 103 wires checked: 0 error(s)
# Design rule check: Flatsat (EXAMPLE numbers, not engineering data)

Model hash: `25294117de0d`. Rules run: 33.
Open: 0 error(s), 28 warning(s), 47 note(s). Waived: 0.
```

`harness export my-flatsat` writes `111 files written to my-flatsat/outputs (model 25294117de0d).` The figures in [`FLATSAT_EXAMPLE.md`](../FLATSAT_EXAMPLE.md) (23 units, 44 interfaces, 8 harnesses, 103 wires, and per harness 18, 26, 2, 22, 7, 16, 8 and 4 wires; 329.6 m of wire and 2.6 kg in `outputs/system/mass_length.csv`) agree with the files this run produced. `generate` reports `8 unchanged` because nothing needs to be made. **Next:** open it in the app and click `PDU2`: only its links stay in colour.

## Does every example run?

Every example was run through `new`, `validate`, `generate` (where it is not already generated), `drc`, `export` and `verify --outputs`, one after the other, with the tool as built from `master`. All steps ended with exit code 0 and `0 error(s)`, except one that is expected: `blank` has no harnesses, so `export` and `verify --outputs` refuse (exit code 1, see above). `blank`, `first-steps` and `small-satellite` were also run (`new`, `generate`, `drc`, `export`, `verify --outputs`) from the source of the `v0.1.0` tag and ended the same way (counts as above; the hashes of the last two differ).

| Example | `validate` | `generate` | `drc` | `export` | `verify --outputs` |
| --- | --- | --- | --- | --- | --- |
| `blank` | 0 errors | 0 harnesses | 0, 0, 0 | refused, nothing to export | refused, no outputs |
| `first-steps` | 0 errors | 2 added, 6 wires | 0 errors, 10 warnings, 8 notes | 38 files | 0 errors |
| `minimal-satellite` | 0 errors | 11 added, 24 wires | 0 errors, 15 warnings, 17 notes | 137 files | 0 errors |
| `small-satellite` | 0 errors | 24 added, 54 wires | 0 errors, 20 warnings, 28 notes | 280 files | 0 errors |
| `flatsat` | 0 errors | 8 unchanged, 103 wires | 0 errors, 28 warnings, 47 notes | 111 files | 0 errors |

## The 15 template files

`harness templates my-templates` copies the import templates, scripts and checklists to a folder that must not exist yet:

```
harness templates my-templates
```

```
15 files written to my-templates. Start with my-templates/README.md.
```

The files are written for the `first-steps` example, so you can try each one before using your own data. The full description of each is in the [templates README](../../src/harness_design_studio/resources/examples/templates/README.md) (which is also `my-templates/README.md`); this is the list, with the build that has it. The columns of the CSV files are in [`IMPORTS.md`](../IMPORTS.md).

| # | File | In short | Used with | 0.1.0 packages |
| --- | --- | --- | --- | --- |
| 1 | `README.md` | what the other files are | read it first | yes |
| 2 | `interfaces.csv` | two example interface rows | app: **File > Import interfaces...** | yes |
| 3 | `approved-parts.csv` | five example part rows: three `Approved`, one `Review`, one `Rejected` | `harness import-parts` | yes |
| 4 | `segment-lengths.csv` | two example segment lengths (millimetres) | `harness import-lengths` | yes |
| 5 | `wheel-connectors.net` | a KiCad netlist for the connectors of `RW1` | `harness import-netlist` | yes |
| 6 | `signal-map.csv` | renames KiCad net names to signal names | `--signal-map` of `import-netlist` | yes |
| 7 | `ampacity-DEMO-ONLY.csv` | learning only: current by wire gauge | `harness config --ampacity-csv` | yes |
| 8 | `config-demo-values/derating.json` | learning only: demo values for `derating.json` | copy over `config/derating.json` of a practice project | yes |
| 9 | `config-demo-values/emc.json` | learning only: demo values for `emc.json` | copy over `config/emc.json` | yes |
| 10 | `config-demo-values/generation.json` | learning only: demo values for `generation.json` | copy over `config/generation.json` | yes |
| 11 | `config-demo-values/segregation.json` | learning only: demo values for `segregation.json` | copy over `config/segregation.json` | yes |
| 12 | `ci/build.sh` | checks, generates, verifies and exports a project; stops at the first problem | `sh ci/build.sh DIR` | yes |
| 13 | `ci/github-actions.yml` | the same as a GitHub Actions workflow | copy to `.github/workflows/` | yes |
| 14 | `design-review-checklist.md` | things to look at before a harness is released | copy next to your design | yes |
| 15 | `design-worksheet.md` | plan units, interfaces and missing data on paper | print or copy it | **no, newer builds only** |

On the 0.1.0 packages the command writes 14 files (no `design-worksheet.md`). The demo values and `ampacity-DEMO-ONLY.csv` are **not from any standard and not engineering data**; the files stay marked as placeholders. See [`PLACEHOLDERS.md`](../PLACEHOLDERS.md).

## WireViz examples in this repository

This repository is a fork of WireViz, a separate program for drawing cable and wiring harness documentation from a text file. Harness Design Studio sits inside it as a separate, clean-room codebase. The WireViz example gallery and the WireViz tutorial that are also in this repository belong to **WireViz, not to Harness Design Studio**: they use WireViz's own YAML files and commands, not the commands on this page.

- [WireViz example gallery](../../../examples/readme.md)
- [WireViz tutorial](../../../tutorial/readme.md)

The only link between the two is a file: Harness Design Studio writes a `wireviz.yaml` per harness in a WireViz-like structure, as a convenience export that has not been validated against the WireViz program ([`OUTPUTS.md`](../OUTPUTS.md)).

Next: [`GETTING_STARTED.md`](../GETTING_STARTED.md), [`LEARNING_PATH.md`](../LEARNING_PATH.md)
