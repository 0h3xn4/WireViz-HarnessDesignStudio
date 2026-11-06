# How to: the whole app, task by task

This page is a short index: each recipe that used to be here now has its own page in the [user manual](user-manual/README.md), with the commands and the output you should see.

**New to the tool?** Do [`GETTING_STARTED.md`](GETTING_STARTED.md) first (45 minutes, with real output) and read [`CONCEPTS.md`](CONCEPTS.md) for the words. Every command and option is in [`CLI.md`](CLI.md). Problems are in [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) and [`FAQ.md`](FAQ.md). The example files used in the manual come from `harness-design-studio templates FOLDER`.

**Former section numbers.** This file used to hold 17 numbered recipes, and other documents may still say "HOWTO section 15". The headings below keep those numbers. Each heading now has one line and a link.

## 1. Install

Moved to [`INSTALL.md`](INSTALL.md): the `.deb`, the `.tar.gz`, a source install, checks and install problems.

## 2. Start a project

[Draw the design](user-manual/draw-the-design.md#1-start-a-project): `harness-design-studio new`, **File > New project…**, **File > New project from an example…**.

## 3. Add devices and interfaces

[Draw the design](user-manual/draw-the-design.md#2-add-devices) (a kind from **Edit > Add device** is added at once with an ID and name of its own; **Device…**, Ctrl+Shift+N, and the button **Add a device** of an empty diagram ask for the name first and suggest the ID, and add a device with connectors of your own to define) and [Redundancy and zones](user-manual/redundancy-and-zones.md). To join a connector of one device to a connector of another from the names on the pins, with no interface type, see [Connect two connectors](user-manual/connect-two-connectors.md) (new in 1.8.0).

## 4. Import interfaces from a spreadsheet

[Import data](user-manual/import-data.md#interfaces-from-a-table-app-only). This works in the app only: **File > Import > Import interfaces…** (Ctrl+Shift+I) opens the import wizard.

## 5. Take connector pinouts from KiCad

[Import KiCad pinouts](user-manual/import-kicad-pinouts.md). A device of your own, pin by pin, or from a spreadsheet: [Define a device](user-manual/define-a-device.md).

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

[Export the outputs](user-manual/export-the-outputs.md): the build workbook of each harness (the file to build from) and the lists; add `--drawings` for the PDF drawings (new in 1.7.0). Only the block diagram, as SVG, PDF and PNG for a slide: **File > Export diagram…** (new in 1.14.0). Every result as JSON and CSV: `export-data`, or the box **Include the open data** in the Export window ([Export the data](user-manual/export-the-data.md)).

## 13. Review and release a harness

[Release a harness](user-manual/release-a-harness.md). A release is blocked until the configuration files are reviewed and the parts approved, unless you give a written reason (`--accept-placeholders REASON`, `--accept-unapproved-parts REASON`; and `--accept-asbuilt REASON` in a project that asks for as-built records before a release).

## 14. Change a released harness

[Change a released harness](user-manual/change-a-released-harness.md).

## 15. Use Git with a project

[Use Git and CI, part 1 to 3](user-manual/use-git-and-ci.md#1-put-a-project-in-git).

## 16. Run in a script or CI

[Use Git and CI, parts 4 and 5](user-manual/use-git-and-ci.md#4-run-it-in-a-script).

## 17. When something goes wrong

[`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) and [`FAQ.md`](FAQ.md).

## Recipes that did not exist before

- [Set wire colours](user-manual/set-wire-colours.md). It is not in the 0.1.0 packages.
- [Naming and title block](user-manual/naming-and-title-block.md).
- [Edit a wire](user-manual/edit-a-wire.md) (since 1.4.0) and [Build a harness by hand](user-manual/build-a-harness-by-hand.md), a harness with no interface behind it (since 1.5.0).
- [Redundancy and zones](user-manual/redundancy-and-zones.md).
- [Enter the build data](user-manual/enter-the-build-data.md): strip lengths, contacts, crimp tools and accessories, in the app and from a file (new in 1.7.0).
- [Use the library](user-manual/use-the-library.md): a folder your team shares with devices and subsystems, and a number of the same device (new in 1.8.0).
- [Choose your role](user-manual/choose-your-role.md): Systems engineer, Electrical engineer or AIT engineer, the **Role** button, **Quick mode** and the Next step page (the Next step page is from 1.7.0, the roles from 1.8.0, the third role from 1.12.0, Quick mode from 1.14.0).
- [Make a block diagram in five minutes](user-manual/quick-diagram.md): Quick mode, a picture of a set-up as SVG, PDF and PNG with no checks and no paperwork (new in 1.14.0).
- [Telling devices apart](user-manual/telling-devices-apart.md): the picture, colour and shape of each kind of device, and the **Kind** you can set by hand (new in 1.16.0).
- [See what the tool assumes](user-manual/see-what-the-tool-assumes.md), [Override a value and keep a history](user-manual/override-and-keep-a-history.md), [Record what was built](user-manual/record-what-was-built.md), [Export the data](user-manual/export-the-data.md) and [Follow the workflow](user-manual/follow-the-workflow.md): the transparency work of 1.12.0.

Keyboard: **Ctrl+K** command palette, **Ctrl+Z** and **Ctrl+Y** undo and redo, **Ctrl+S** save, **Ctrl+=** and **Ctrl+-** zoom, **F** fit, **Ctrl+0** 100 %, **Ctrl+G** generate, **Ctrl+E** export, **Ctrl+Shift+N** add a device, **Ctrl+Shift+H** new harness, **F1** the user guide. The full list is in the [user guide](guide/USER_GUIDE.md) and, in the app, under **Settings > Keyboard shortcuts**.

Next: [user manual](user-manual/README.md), [`GETTING_STARTED.md`](GETTING_STARTED.md)
