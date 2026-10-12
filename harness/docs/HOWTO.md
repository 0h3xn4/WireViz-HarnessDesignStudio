# How to: the whole app, task by task

This page is a short index: each recipe that used to be here now has its own page in the [user manual](user-manual/README.md), with the commands and the output you should see.

**New to the tool?** Do [`GETTING_STARTED.md`](GETTING_STARTED.md) first (45 minutes, with real output) and read [`CONCEPTS.md`](CONCEPTS.md) for the words. Every command and option is in [`CLI.md`](CLI.md). Problems are in [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) and [`FAQ.md`](FAQ.md). The example files used in the manual come from `harness templates FOLDER`.

**Former section numbers.** This file used to hold 17 numbered recipes, and other documents may still say "HOWTO section 15". The headings below keep those numbers. Each heading now has one line and a link.

## 1. Install

Moved to [`INSTALL.md`](INSTALL.md): the `.deb`, the `.tar.gz`, a source install, checks and install problems.

## 2. Start a project

[Draw the design](user-manual/draw-the-design.md#1-start-a-project): `harness new`, **File > New project…**, **File > New project from an example…**.

## 3. Add units and interfaces

[Draw the design](user-manual/draw-the-design.md#2-add-units) (adding a unit opens no window; the ID and the name are given automatically) and [Redundancy and zones](user-manual/redundancy-and-zones.md).

## 4. Import interfaces from a spreadsheet

[Import data](user-manual/import-data.md#interfaces-from-a-table-app-only). This works in the app only.

## 5. Take connector pinouts from KiCad

[Import KiCad pinouts](user-manual/import-kicad-pinouts.md).

## 6. Read and fix problems

[Read and fix problems](user-manual/read-and-fix-problems.md).

## 7. Generate harnesses

[Generate harnesses](user-manual/generate-harnesses.md).

## 8. Understand why a wire is the way it is

[Generate harnesses, the "Why" tab](user-manual/generate-harnesses.md#3-read-why-a-wire-is-the-way-it-is).

## 9. Fill in the engineering values

[Fill in the engineering values](user-manual/fill-in-engineering-values.md). The files have a wrapper: the numbers go inside `values` ([the shape of a config file](user-manual/fill-in-engineering-values.md#the-shape-of-a-config-file)).

## 10. Import the approved parts list

[Import data, approved parts list](user-manual/import-data.md#approved-parts-list).

## 11. Import segment lengths

[Import data, segment lengths](user-manual/import-data.md#segment-lengths).

## 12. Export outputs

[Export the outputs](user-manual/export-the-outputs.md).

## 13. Review and release a harness

[Release a harness](user-manual/release-a-harness.md). A release is blocked until the configuration files are reviewed and the parts approved, unless you give a written reason (`--accept-placeholders REASON`, `--accept-unapproved-parts REASON`).

## 14. Change a released harness

[Change a released harness](user-manual/change-a-released-harness.md).

## 15. Use Git with a project

[Use Git and CI, part 1 to 3](user-manual/use-git-and-ci.md#1-put-a-project-in-git).

## 16. Run in a script or CI

[Use Git and CI, parts 4 and 5](user-manual/use-git-and-ci.md#4-run-it-in-a-script).

## 17. When something goes wrong

[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) and [`FAQ.md`](FAQ.md).

## Recipes that did not exist before

- [Set wire colours](user-manual/set-wire-colours.md). This is newer than the 0.1.0 packages.
- [Naming and title block](user-manual/naming-and-title-block.md).
- [Redundancy and zones](user-manual/redundancy-and-zones.md).

Keyboard: **Ctrl+K** command palette, **Ctrl+Z** and **Ctrl+Y** undo and redo, **Ctrl+S** save, **Ctrl+=**, **Ctrl+-** and **Ctrl+0** zoom, **F1** the user guide. The full list is in the [user guide](guide/USER_GUIDE.md).

Next: [user manual](user-manual/README.md), [`GETTING_STARTED.md`](GETTING_STARTED.md)
