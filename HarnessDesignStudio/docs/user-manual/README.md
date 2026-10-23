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
| be told what to do next, one step at a time | [Use the simple workspace](use-the-simple-workspace.md) |
| start a project and draw units and links | [Draw the design](draw-the-design.md) |
| add a backup chain, or put units in other lanes | [Redundancy and zones](redundancy-and-zones.md) |
| have the tool make connectors, pins and wires | [Generate harnesses](generate-harnesses.md) |
| understand an error or a warning, or waive one | [Read and fix problems](read-and-fix-problems.md) |
| enter derating factors, wire current ratings and test limits | [Fill in the engineering values](fill-in-engineering-values.md) |
| change a wire, draw a wire of my own, put two wires on one pin, or twist wires | [Edit a wire](edit-a-wire.md) |
| make a harness from nothing, with no interfaces: its connectors, pins and wires | [Build a harness by hand](build-a-harness-by-hand.md) |
| enter the strip lengths, the contact on each pin and its crimp tool, and the sleeving, heat shrink and labels of a harness | [Enter the build data](enter-the-build-data.md) |
| load my interface table, approved parts list, segment lengths or build data | [Import data](import-data.md) |
| define a device of my own down to each pin, or load its pinout from a spreadsheet | [Define a device](define-a-device.md) |
| take a unit's pinout from KiCad | [Import KiCad pinouts](import-kicad-pinouts.md) |
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

1. [Use the simple workspace](use-the-simple-workspace.md): the Next step page, one thing to do at a time; fewer things on screen; Simple or Full. Since 1.7.0.
2. [Draw the design](draw-the-design.md): start a project; add units; connect them; guided and expert mode; save.
3. [Redundancy and zones](redundancy-and-zones.md): the redundant copy of a unit; links between the chains; lanes.
4. [Generate harnesses](generate-harnesses.md): preview, apply and undo; the independent check; the Harness tab and its "Why" pane; how links are grouped.
5. [Read and fix problems](read-and-fix-problems.md): errors, warnings and notes; fixes; waivers; `harness-design-studio drc`.
6. [Fill in the engineering values](fill-in-engineering-values.md): `harness-design-studio config`; the file shape; the gauge table; demo values; profiles.
7. [Import data](import-data.md): the import wizard (interfaces only in the app), approved parts, segment lengths, build data (`import-build-data`).
8. [Import KiCad pinouts](import-kicad-pinouts.md): `harness-design-studio import-netlist` and fixed pins.
9. [Define a device](define-a-device.md): the Devices tab, pins and signals, `import-pinout` and `export-pinout`.
10. [Edit a wire](edit-a-wire.md): the *Edit wire* tab, wires you draw, several wires on one pin, twisting, labels, pin function. Since 1.4.0.
11. [Set wire colours](set-wire-colours.md): *Edit > Wire colours...* and the file setting. Since 1.0.0 (not in the 0.1.0 packages).
12. [Build a harness by hand](build-a-harness-by-hand.md): *New harness*, the *Connectors* tab, pin function and termination, wires between the new connectors. Since 1.5.0.
13. [Enter the build data](enter-the-build-data.md): strip lengths, the contact on each pin and its crimp tool, accessories; in the app and with `harness-design-studio import-build-data`; what the build workbook then shows. Since 1.7.0.
14. [Export the outputs](export-the-outputs.md): the build workbook sheet by sheet and how to build from it, the optional PDF drawings, what each file is for; checking that it is current.
15. [Naming and title block](naming-and-title-block.md): name patterns and title block fields.
16. [Release a harness](release-a-harness.md): review, release, the gates, the change log.
17. [Change a released harness](change-a-released-harness.md): new revision, `diff`, `log`, `compare`.
18. [Use Git and CI](use-git-and-ci.md): Git habits, `harness-design-studio check`, a build script, a workflow.

## How to read the pages

- **Commands** use a practice project called `wheel-link`, made with `harness-design-studio new wheel-link --template first-steps`. Put your own folder where you see `wheel-link` or `DIR`. Output blocks are real output of the tool. Numbers such as the model hash (`5e6bcbd63d91`) depend on the project and the tool version; yours can differ.
- **Command names.** The command line tool is `harness-design-studio`; `harness` is a short alias that runs the same program, so older scripts keep working. The app is `harness-design-studio-gui` (alias `harness-gui`) when started from a terminal.
- **App steps** (menus, buttons, tabs) use the names that version 1.7.0 of the program shows. They were checked against the program's texts (`gui/strings.py`) and against the menus and buttons of the window started without a screen, in both workspaces. Nobody watched the steps on a screen, so pages with app steps say "GUI, not run" where it matters.
- **Where things are in the window.** The rail on the left opens an area: **Next step**, **Home**, **Model** (the **Diagram** and **Devices** tabs), **Checks**, **Drawings** (the **Harness** tab), **Outputs** (the **Lists** tab), **Revisions** (the **Releases** tab) and, at the bottom, **Settings**. The pages name the tab, as the **Go** menu does (Ctrl+1 to Ctrl+6; Ctrl+7 is Home, Ctrl+, is Settings). The user guide, section 4, describes the window.
- **Two workspaces and two modes.** These are separate choices. The **workspace** (**Simple** or **Full**, in the **View** menu and under **Settings > Editing**) decides how much is on screen and where a project opens. In **Simple** a project opens on the Next step page, the project tree, the inspector and the Problems panel start closed, and **Home** is not in the rail (it is still in the **Go** menu, on Ctrl+7). In **Full** a project opens where it opened before and every panel is there. A first run, a settings file with nothing stored yet, gets **Simple**; a settings file that already holds values keeps **Full**. The **mode** (**Guided** or **Expert**, in the top bar) decides only how much of a unit and a link the diagram shows. Every page works in both workspaces; where a step needs a panel that Simple has closed, the page says so: press **Show panels** in the top bar. To reach the Model area from the Next step page, press **Model** in the rail or Ctrl+1.
- **Since 1.7.0.** The build workbook `<ID>_build.xlsx`, the build data in it (strip lengths, contacts, crimp tools, accessories, [Enter the build data](enter-the-build-data.md)) and the option `--drawings`: `export` no longer writes the harness PDF drawings unless you ask for them (the check box **Include the PDF drawings** in the Export window). Pages that use them say so. See [Export the outputs](export-the-outputs.md). The simple workspace ([Use the simple workspace](use-the-simple-workspace.md): the Next step page and fewer things on screen) is from 1.7.0 too.
- **Since 1.0.0.** Some things are not in the 0.1.0 packages: the examples `minimal-satellite` and `flatsat`, the wiring-diagram drawing with wire colours, *Edit > Wire colours...* and `design-worksheet.md`. They are not in the 0.1.0 `.deb` and `.tar.gz`. `harness-design-studio new --list` shows three examples on 0.1.0 and five on 1.0.0. The [changelog](../../CHANGELOG.md) lists what is new. Pages that use these say so.
- **No claim of compliance.** The tool was created mainly by an AI and has not been reviewed independently. Results rest on placeholders and example parts until you supply your own values. See [the status](../../README.md#status).

## If you are new

Do the 45-minute tutorial first: [`GETTING_STARTED.md`](../GETTING_STARTED.md). The route from beginner to release is in [`LEARNING_PATH.md`](../LEARNING_PATH.md). The words are in [`CONCEPTS.md`](../CONCEPTS.md) and the [glossary](../GLOSSARY.md). The app also has a built-in user guide (**F1**), the same text as [`guide/USER_GUIDE.md`](../guide/USER_GUIDE.md).

Next: [Use the simple workspace](use-the-simple-workspace.md), [Draw the design](draw-the-design.md), [Generate harnesses](generate-harnesses.md)
