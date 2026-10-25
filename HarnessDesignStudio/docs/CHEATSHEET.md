# Cheat sheet

One page. Every command is explained in [`CLI.md`](CLI.md); `harness-design-studio COMMAND --help` prints the same in a terminal. `harness` is a short alias of `harness-design-studio`.

## The loop

```
harness-design-studio new my-design --template first-steps  # start a project that has devices (harness-design-studio new --list shows the examples)
harness-design-studio generate my-design                    # make harnesses, connectors, pins, wires
harness-design-studio check my-design                       # validate, plus leftovers of Git merges and edits to released harnesses
harness-design-studio drc my-design                         # the full design rule check, as a report
harness-design-studio export my-design                      # build workbook per harness, wire lists, pinouts, BOM, test tables
harness-design-studio export my-design --drawings           # the same, and the PDF drawings of the harnesses
harness-design-studio verify my-design --outputs            # an independent check of the exported files
```

The build workbook, `outputs/harnesses/<ID>/<ID>_build.xlsx`, is the file to build a harness from; the PDF drawings are written only with `--drawings` (new in 1.7.0). Run the loop again after every change. Generating twice without a change changes nothing (the second run prints "0 added").

The command line cannot add devices or interfaces. The loop works on a project that already has them: an example such as `first-steps`, or your own design after you added the devices in the app (on the empty diagram, the button **Add a device** or **Add** in the project panel; or make a harness with no interface at all with **New harness…**, Ctrl+Shift+H). On a `blank` project `generate` finds 0 interfaces and `export` stops with ``error: there are no harnesses to export; run `harness-design-studio generate` first.``

## Bring in data

| You have | Command |
| --- | --- |
| the example import files, demo values and CI scripts | `harness-design-studio templates my-templates` (the folder must be new or empty) |
| interfaces in a table | app only: **File > Import > Import interfaces…** |
| a parts list (CSV, TSV, JSON or XLSX; also an InvenTree export) | `harness-design-studio import-parts DIR parts.csv --approved Approved` |
| segment lengths | `harness-design-studio import-lengths DIR lengths.csv --unit mm` |
| device connectors in KiCad | `harness-design-studio import-netlist DIR file.net --device RW1 --prefix J --connector J1=RW1-J01 --dry-run` |
| a device's pins from a table | `harness-design-studio import-pinout DIR gyro.csv --device GYRO1 --new-device "Gyro unit" --default-part MY-HD-9-F --dry-run` |
| a device's pinout as a file | `harness-design-studio export-pinout DIR --device GYRO1 -o gyro.xlsx` |
| a device from another project (a device library file) | `harness-design-studio import-devices DIR devices.json --list`, then `--device GYRO1 --dry-run` |
| a device to keep for other projects | `harness-design-studio export-devices DIR devices.json --device GYRO1` (or **Save to library…** in the Devices tab) |
| strip lengths, pin contacts, accessories or crimp tools (new in 1.7.0) | `harness-design-studio import-build-data DIR strip-lengths.csv --dry-run` (the kind is read from the headings; templates `strip-lengths.csv`, `pin-contacts.csv`, `accessories.csv`) |
| engineering values | edit `config/*.json`, see [`CONFIG.md`](CONFIG.md); `harness-design-studio config DIR` lists what is missing |

Add `--dry-run` to any import to see what it would do first. Other commands (`compare`, `schema`, `library`, `migrate`, and options such as `config --ampacity-csv`) are in [`CLI.md`](CLI.md).

## Edit what was generated (app, since 1.4.0)

In the **Drawings** area, select a harness and open the **Edit wire** tab beside *Why*: set the gauge, type, colour, length, strip lengths (**Strip A (mm)**, **Strip B (mm)**), label and note of the selected wires (gauge, type, colour and length lock the wire, so Generate keeps them; the rest it keeps anyway), **New wire** draws a wire between two pins, **Group** twists or shields selected wires, **Labels** names the harness and its cable connectors. In the **Devices** tab: a pin's *Function*, its *Cable contact* (press **Contact** to show the column), a connector's *Label*, **Save to library…** and **Add from library…**. The **Accessories** tab of the Harness view lists sleeving, heat shrink, labels and backshells. Details: [`user-manual/edit-a-wire.md`](user-manual/edit-a-wire.md), [`user-manual/define-a-device.md`](user-manual/define-a-device.md), [`user-manual/enter-the-build-data.md`](user-manual/enter-the-build-data.md) (strip lengths, contacts, crimp tools and accessories; new in 1.7.0).

## Release and change

```
harness-design-studio review  DIR W001 --by "Name"                                  # submit for review
harness-design-studio release DIR W001 --by "Name" --comment "why, 10+ characters"  # baseline, change log entry, lock
harness-design-studio revise  DIR W001 --by "Name" --comment "why, 10+ characters"  # open a new revision of a released harness
harness-design-studio diff    DIR W001                                              # what changed against the baseline
harness-design-studio log     DIR                                                   # the change log
```

The comment must have at least 10 characters. A release is blocked while checks fail, while a configuration file is a placeholder, or while the harness uses parts that are not approved. You can release anyway with `--accept-placeholders REASON` and `--accept-unapproved-parts REASON`; the reason is kept in the change log.

## Exit codes

`0` success (warnings allowed), `1` the project has errors or a step is blocked, `2` usage error or an unreadable project (also a project with damaged files), `130` interrupted with Ctrl-C.

## In the app

The window: a rail on the left (Next step, Home, Model, Checks, Drawings, Outputs, Revisions, Settings), a top bar (the steps **Generate**, **Check**, **Release…**, then **Export…** and a status chip), the tabs of the area you are in (Diagram and Devices under Model), the project tree on the left, the Inspector, Why and Problems on the right, and a Problems panel at the bottom (Ctrl+Shift+M). That is the **Full** workspace. A first run starts in the **Simple** workspace (since 1.7.0): it opens on the **Next step** page (one thing to do, one button), the tree, the Inspector and the Problems panel are closed, and the rail has no Home. **View > Full** or **Show everything** gives the full window, **View > Simple** goes back, **Show panels** (top bar) opens the tree and the Inspector. **Settings** holds the theme, the interface size, Reduce motion, the list of all keys, About and the licences.

| Keys | Action |
| --- | --- |
| Ctrl+N, Ctrl+O | new project, open project |
| Ctrl+S, Ctrl+Shift+S | save, save as |
| Ctrl+Shift+I | import interfaces (a table) |
| Ctrl+G, F5, Ctrl+E | generate harnesses, run the checks, export |
| Ctrl+I | new interface |
| Ctrl+1 to Ctrl+6 | the tabs: Diagram, Harness, Lists, Checks, Releases, Devices |
| Ctrl+7, Ctrl+, | Home (also in Simple, where the rail does not list it), Settings |
| Ctrl+Shift+M | show or hide the Problems panel |
| Ctrl+Shift+H | new harness by hand (Drawings area: then add its connectors in the Connectors tab) |
| Ctrl+Shift+N | add a device (Devices tab: F2 or Enter edits a cell, Insert adds a pin, Shift+Delete deletes pins, Ctrl+L fills from an interface type, Ctrl+Enter assigns to an interface) |
| Ctrl+Shift+T | the Interface table |
| Ctrl+Shift+J | the Device list |
| F6, Shift+F6 | next and previous panel |
| Ctrl+Q | quit |
| Ctrl+K | Search and commands (the command palette): type a command or an ID |
| Enter or F2, Esc, Ctrl+V in a table | edit a cell, keep the old text, paste a block of cells from a spreadsheet |
| Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z | undo, redo |
| Ctrl+=, Ctrl+-, Ctrl+0 | zoom in, out, 100 % |
| F, Shift+F | fit everything, zoom to the selection |
| Ctrl+A, Ctrl+D, Ctrl+F | select all, duplicate, find (in the diagram) |
| C, Esc | start the Connect tool, back to Select (Esc also clears the selection) |
| Tab, Enter or Space | move between devices and links, select |
| Shift+arrows | move the selected device |
| Delete | delete the selected item (after showing what it affects) |
| F1 | the user guide |

## What is where

```
my-design/
  project.json        name and description
  config/             engineering values (rules you or your programme supply)
  library/            parts and interface types
  logical/            units (the devices) and interfaces (what you draw)
  physical/           connectors and harnesses (what the tool generates)
  generated/          how the last generation was made (for explanations)
  outputs/            build workbooks and lists (safe to delete and regenerate)
  changelog.json      release history
  baselines/          the frozen copy of each released harness (written at release)
```

Put the folder in Git. Everything except `outputs/` is meant to be reviewed as text.

## Words you will meet

| Word | Meaning |
| --- | --- |
| device | a box: computer, power unit, wheel, sensor |
| interface | a connection need between two devices: power, RS-422, CAN, ... |
| harness | a bundle of wires with connectors that carries interfaces |
| *pending* | a value is missing; nothing was invented |
| *not checked* | a rule could not run because its numbers are not supplied |
| placeholder | a configuration file nobody has reviewed yet |
| baseline | the frozen copy stored at release |
| accessory | sleeving, heat shrink, a label or a backshell on a harness (1.7.0) |

More: [`CONCEPTS.md`](CONCEPTS.md) and the glossary in the user guide.

Next: [user manual](user-manual/README.md), [`CLI.md`](CLI.md), [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md).
