# User manual

This manual has one page for each job you do with Harness Design Studio, written as "How do I ...", with commands you can copy and the output you should see.

## Contents

- [Which page do I need?](#which-page-do-i-need)
- [The pages](#the-pages)
- [How to read the pages](#how-to-read-the-pages)
- [If you are new](#if-you-are-new)

## Which page do I need?

| I want to ... | Read |
| --- | --- |
| install the tool | [`INSTALL.md`](../INSTALL.md) |
| be told what to do next, one step at a time | [Choose your role](choose-your-role.md) |
| start a project and draw devices and links | [Draw the design](draw-the-design.md) |
| join a connector of one device to a connector of another, pin by pin, from the names on the pins, and check the result | [Connect two connectors](connect-two-connectors.md) |
| add a backup chain, or put devices in other lanes | [Redundancy and zones](redundancy-and-zones.md) |
| have the tool make connectors, pins and wires | [Generate harnesses](generate-harnesses.md) |
| understand an error or a warning, or waive one | [Read and fix problems](read-and-fix-problems.md) |
| enter derating factors, wire current ratings and test limits | [Fill in the engineering values](fill-in-engineering-values.md) |
| change a wire, draw a wire of my own, put two wires on one pin, or twist wires | [Edit a wire](edit-a-wire.md) |
| make a harness from nothing, with no interfaces: its connectors, pins and wires | [Build a harness by hand](build-a-harness-by-hand.md) |
| enter the strip lengths, the contact on each pin and its crimp tool, and the sleeving, heat shrink and labels of a harness | [Enter the build data](enter-the-build-data.md) |
| load my interface table, approved parts list, segment lengths or build data | [Import data](import-data.md) |
| define a device of my own down to each pin, or load its pinout from a spreadsheet | [Define a device](define-a-device.md) |
| keep devices and subsystems in a folder my team shares, add them to a project, or say how many of a device there are | [Use the library](use-the-library.md) |
| take a device's pinout from KiCad | [Import KiCad pinouts](import-kicad-pinouts.md) |
| write the build workbook to build a harness from, the wire lists and the test tables (and, if you want them, the PDF drawings) | [Export the outputs](export-the-outputs.md) |
| give the wires colours | [Set wire colours](set-wire-colours.md) |
| change harness, connector and wire IDs, or the title block fields | [Naming and title block](naming-and-title-block.md) |
| freeze a harness with a name, a comment and a record | [Release a harness](release-a-harness.md) |
| change a harness that is already released | [Change a released harness](change-a-released-harness.md) |
| keep a project in Git, check it after a merge, or run it in CI | [Use Git and CI](use-git-and-ci.md) |
| fix something that does not work | [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md), then [`FAQ.md`](../FAQ.md) |
| look up a command or an option | [`CLI.md`](../CLI.md) |
| look up a word | [`GLOSSARY.md`](../GLOSSARY.md) |

## The pages

The numbers follow the order of the work. The first page is the one the editor shows when you open a project for the first time.

1. [Choose your role](choose-your-role.md): Systems engineer or Electrical / AIT engineer, and what each shows first; the Next step page, one thing to do at a time. The Next step page is from 1.7.0, the roles after it.
2. [Draw the design](draw-the-design.md): start a project; add devices; connect them; guided and expert mode; save.
3. [Redundancy and zones](redundancy-and-zones.md): the redundant copy of a device; links between the chains; lanes.
4. [Generate harnesses](generate-harnesses.md): preview, apply and undo; the independent check; the Harness tab and its "Why" pane; how links are grouped.
5. [Read and fix problems](read-and-fix-problems.md): errors, warnings and notes; fixes; waivers; `harness-design-studio drc`.
6. [Fill in the engineering values](fill-in-engineering-values.md): `harness-design-studio config`; the file shape; the gauge table; demo values; profiles.
7. [Import data](import-data.md): the import wizard (interfaces only in the app), approved parts, segment lengths, build data (`import-build-data`).
8. [Import KiCad pinouts](import-kicad-pinouts.md): `harness-design-studio import-netlist` and fixed pins.
9. [Define a device](define-a-device.md): the Devices tab, pins and signals, `import-pinout` and `export-pinout`.
10. [Connect two connectors](connect-two-connectors.md): the window *Link connectors*, pairs proposed by signal name, roles (power, return, ground), *Check my connections*, *Create harness*. New in 1.8.0.
11. [Edit a wire](edit-a-wire.md): the *Edit wire* tab, wires you draw, several wires on one pin, twisting, labels, pin function. Since 1.4.0.
12. [Set wire colours](set-wire-colours.md): *Edit > Wire colours...* and the file setting. Since 1.0.0 (not in the 0.1.0 packages).
13. [Build a harness by hand](build-a-harness-by-hand.md): *New harness*, the *Connectors* tab, pin function and termination, wires between the new connectors. Since 1.5.0.
14. [Enter the build data](enter-the-build-data.md): strip lengths, the contact on each pin and its crimp tool, accessories; in the app and with `harness-design-studio import-build-data`; what the build workbook then shows. Since 1.7.0.
15. [Export the outputs](export-the-outputs.md): the build workbook sheet by sheet and how to build from it, the optional PDF drawings, what each file is for; checking that it is current.
16. [Naming and title block](naming-and-title-block.md): name patterns and title block fields.
17. [Release a harness](release-a-harness.md): review, release, the gates, the change log.
18. [Change a released harness](change-a-released-harness.md): new revision, `diff`, `log`, `compare`.
19. [Use Git and CI](use-git-and-ci.md): Git habits, `harness-design-studio check`, a build script, a workflow.
20. [Use the library](use-the-library.md): the library folder a team shares, the library window, devices and subsystems, a number of the same device, `export-subsystem` and `import-subsystem`. New in 1.8.0.

## How to read the pages

- **Commands** use a practice project called `wheel-link`, made with `harness-design-studio new wheel-link --template first-steps`. Put your own folder where you see `wheel-link` or `DIR`. Output blocks are real output of the tool. Numbers such as the model hash (`55f35af414c5`) depend on the project and the tool version; yours can differ.
- **Command names.** The command line tool is `harness-design-studio`; `harness` is a short alias that runs the same program, so older scripts keep working. The app is `harness-design-studio-gui` (alias `harness-gui`) when started from a terminal.
- **App steps** (menus, buttons, tabs) use the names that version 1.8.1 of the program shows. They were checked against the program's texts (`gui/strings.py`) and against the menus and buttons of the window started without a screen, in both roles. Nobody watched the steps on a screen, so pages with app steps say "GUI, not run" where it matters.
- **Where things are in the window.** The rail on the left opens an area: **Next step**, **Home**, **Model** (the **Diagram** and **Devices** tabs), **Checks**, **Drawings** (the **Harness** tab), **Outputs** (the **Lists** tab), **Revisions** (the **Releases** tab) and, at the bottom, **Settings**. The pages name the tab, as the **Go** menu does (Ctrl+1 to Ctrl+6; Ctrl+7 is Home, Ctrl+, is Settings). The user guide, section 4, describes the window.
- **Two roles and two modes.** These are separate choices. The **role** (**Systems engineer** or **Electrical / AIT engineer**, in the **View** menu under **Role** and under **Settings > Editing**) decides how much is on screen and where a project opens; it replaces the *Simple* and *Full* workspaces of 1.7.0. As a **Systems engineer** a project opens on the Next step page, the project tree, the inspector and the Problems panel start closed, and the rail lists Next step, Model, Checks, Revisions and Settings only (**Home**, **Drawings** and **Outputs** are still in the **Go** menu, on their keys and in the command palette, Ctrl+K). As an **Electrical / AIT engineer** a project opens where it opened before and every area and panel is there. A first start, a settings file with nothing stored yet, asks *Who are you working as?*; a settings file that already holds values gets **Electrical / AIT engineer** without a question. The **mode** (**Guided** or **Expert**, in the top bar) decides only how much of a device and a link the diagram shows. Every page works in both roles; where a step needs a panel that the Systems engineer role has closed, the page says so: press **Show panels** in the top bar. To reach the Model area from the Next step page, press **Model** in the rail or Ctrl+1.
- **New in 1.8.0.** Connections between connectors, pin by pin, with the pairs proposed from the signal names ([Connect two connectors](connect-two-connectors.md)), the library window and the number of devices ([Use the library](use-the-library.md)), and the word *device* on screen and in these pages. Pages that use them say so.
- **Since 1.7.0.** The build workbook `<ID>_build.xlsx`, the build data in it (strip lengths, contacts, crimp tools, accessories, [Enter the build data](enter-the-build-data.md)) and the option `--drawings`: `export` no longer writes the harness PDF drawings unless you ask for them (the check box **Include the PDF drawings** in the Export window). Pages that use them say so. See [Export the outputs](export-the-outputs.md). The Next step page and fewer things on screen ([Choose your role](choose-your-role.md); the simple workspace of 1.7.0, which the roles replaced after it) are from 1.7.0 too.
- **Since 1.0.0.** Some things are not in the 0.1.0 packages: the examples `minimal-satellite` and `flatsat`, the wiring-diagram drawing with wire colours, *Edit > Wire colours...* and `design-worksheet.md`. They are not in the 0.1.0 `.deb` and `.tar.gz`. `harness-design-studio new --list` shows three examples on 0.1.0 and five on 1.0.0. The [changelog](../../CHANGELOG.md) lists what is new. Pages that use these say so.
- **No claim of compliance.** The tool was created mainly by an AI and has not been reviewed independently. Results rest on placeholders and example parts until you supply your own values. See [the status](../../README.md#status).

## If you are new

Do the 45-minute tutorial first: [`GETTING_STARTED.md`](../GETTING_STARTED.md). The route from beginner to release is in [`LEARNING_PATH.md`](../LEARNING_PATH.md). The words are in [`CONCEPTS.md`](../CONCEPTS.md) and the [glossary](../GLOSSARY.md). The app also has a built-in user guide (**F1**), the same text as [`guide/USER_GUIDE.md`](../guide/USER_GUIDE.md).

Next: [Choose your role](choose-your-role.md), [Draw the design](draw-the-design.md), [Generate harnesses](generate-harnesses.md)
