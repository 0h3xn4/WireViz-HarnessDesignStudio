# Tips

This page collects shortcuts and habits that save time once you have finished [`GETTING_STARTED.md`](GETTING_STARTED.md), and says plainly how the tool exchanges data with other programs.

## Contents

- [Keyboard shortcuts](#keyboard-shortcuts)
- [The command palette (Ctrl+K)](#the-command-palette-ctrlk)
- [Reading a busy diagram](#reading-a-busy-diagram)
- [Keep a project in Git](#keep-a-project-in-git)
- [Run the checks in a script or CI](#run-the-checks-in-a-script-or-ci)
- [Compare two versions of a design](#compare-two-versions-of-a-design)
- [Engineering values: config, profiles and the ampacity table](#engineering-values-config-profiles-and-the-ampacity-table)
- [Choose how interfaces are grouped into harnesses](#choose-how-interfaces-are-grouped-into-harnesses)
- [Wire colours](#wire-colours)
- [Waivers](#waivers)
- [Small habits](#small-habits)
- [Working with other tools](#working-with-other-tools)

Every command on this page was run with the tool (version `0.1.0`, built from `master`) before it was written down. Some of the options need the newer examples; the page says so where it matters (see [`examples/README.md`](examples/README.md) for which build has what).

## Keyboard shortcuts

These are the shortcuts the app defines (read from the program's source, `gui/main_window.py` and `gui/canvas.py`). Menus show the same keys.

| Keys | What it does |
| --- | --- |
| Ctrl+N | New project... |
| Ctrl+O | Open project... |
| Ctrl+S | Save |
| Ctrl+Shift+S | Save as... |
| Ctrl+Shift+I | Import interfaces... (a CSV or XLSX table) |
| Ctrl+Q | Quit |
| Ctrl+Z | Undo |
| Ctrl+Y or Ctrl+Shift+Z | Redo |
| Delete | Delete the selected item (it first shows what else goes with it) |
| C | Start the Connect tool; then click the two units to add an interface |
| Esc | Back to the Select tool; also clears the selection and ends the focus on a unit or link |
| Ctrl+= and Ctrl+- | Zoom in and out |
| Ctrl+0 | Fit the whole diagram in the window |
| Ctrl+K | Search and commands (the command palette, next section) |
| F1 | The user guide |
| Tab | Move between units and links with the keyboard (Undo and Redo in the toolbar are reachable the same way) |
| Enter or Space | Select the unit or link that has the keyboard focus (with the Connect tool active, a unit with the focus is picked) |
| Shift+arrow keys | Move the focused unit by one grid step (10 diagram units), in the Select tool, when the project is not read-only |

Everything else is in the menus: **View > Arrange diagram** tidies the units (they stay in their lanes; Undo restores the old positions), **View > UI scale** offers 100, 125, 150 and 200 %, and **View > Dark theme**, **Show overview map** and **Show all link labels** switch those on and off. Switching between **Guided** and **Expert** mode never changes data.

## The command palette (Ctrl+K)

Press **Ctrl+K**, type a few letters, press **Enter**. The list is one searchable collection of:

- every menu action that is enabled, with its shortcut written beside it;
- **Add unit: ...** for each kind of unit;
- **Connect with ...** for each interface type (17 ship with the tool);
- **Go to unit** `OBC1 (Computer 1)` for every unit, and **Go to interface** `IF-002 (...)` for every interface.

Type several words and every word must match, in any order (`go rw1` finds *Go to unit RW1*). **Up** and **Down** move through the list and the list shows at most 14 lines at a time; keep typing to narrow it. It is the quickest way to jump to one object in a project with dozens of units.

## Reading a busy diagram

- **Click a unit or a link**: its links stay in colour and everything else fades. Click the empty background or press **Esc** to see everything again.
- **Show** in the toolbar fades everything except one *signal class*, one *connector* or one *bundle (harness)*: choose **All interfaces**, **By signal class**, **By connector** or **By bundle (harness)**, then the value. It changes the picture only, never the project.
- **Interface table** and **Outline** tabs list every interface and every unit as text. They are the screen-reader friendly views, and also the fastest way to find one row in a large design.
- A voltage or current shows next to a link only when it was entered; **View > Show all link labels** shows them all.

## Keep a project in Git

A project is a folder of small, plain JSON files in a fixed format (sorted keys, two-space indent, lists sorted by ID), so a Git diff shows real changes only. Commit the whole folder. `harness new` writes a `.gitignore` that already leaves out lock files, backups and the app's autosave. `outputs/` can be committed or ignored; it is always safe to delete and make again. The format is in [`FILE_FORMAT.md`](FILE_FORMAT.md).

After a merge or a pull, run:

```
harness check my-design
```

`check` is `validate` plus a search for leftover merge-conflict markers and for released harnesses that were edited. It ends with exit code 1 when it finds a problem (see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md#checking)).

If you edit project files by hand, let your editor check them. The command writes one JSON Schema for each kind of file and a settings snippet:

```
harness schema my-design/schemas
```

```
14 schemas written to my-design/schemas. In VS Code, copy the "json.schemas" entry of my-design/schemas/editor-settings.json into the .vscode/settings.json of the project (the schemas folder must sit inside the project folder as schemas/).
```

The folder must not exist yet or must be empty.

## Run the checks in a script or CI

`harness templates my-templates` copies, among others, `ci/build.sh` and `ci/github-actions.yml`. The script stops at the first problem:

```
harness templates my-templates
harness new cib --template first-steps
sh my-templates/ci/build.sh cib
```

```
15 files written to my-templates. Start with my-templates/README.md.
Project 'First steps: reaction wheel link' created in cib (3 units, 2 interfaces).
Next: harness validate cib   or open it in the app (File > Open project).
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
3 units, 2 interfaces, 9 connectors, 0 harnesses: 0 error(s), 0 warning(s).
2 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
2 interfaces and 6 wires checked: 0 error(s)
38 files written to cib/outputs (model 91531b45fd2c).
2 interfaces and 6 wires checked: 0 error(s)
build ok: cib/outputs
```

What it runs: `check`, `generate`, `verify`, `drc` (it stops with the report if there is an open error), `export` and `verify --outputs`. `ci/github-actions.yml` is the same list as a GitHub Actions workflow for a design repository; it installs the `.deb` from a `tools/` folder and expects the project in a folder called `design`. Edit both files for your own repository before you use them. The exit codes that make this work are 0 (ok), 1 (errors or blocked) and 2 (usage error), see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md#exit-codes-what-0-1-and-2-mean).

A report you can attach to a review: `harness drc my-design > drc-report.md`.

## Compare two versions of a design

`harness compare OLD NEW` compares two project folders object by object. Use it for two Git checkouts, or for "before" and "after" copies:

```
cp -r my-design my-design-try
harness compare my-design my-design-try
```

```
# Project comparison

Comparing my-design with my-design-try: 0 added, 0 removed, 0 changed.

No differences.
```

For a harness you have released, `harness diff DIR W001` shows what changed since its baseline, and `harness log DIR` prints the change log. `--from A --to B` works between two **released** revisions (see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md#releasing) for the error you get otherwise).

## Engineering values: config, profiles and the ampacity table

`harness config DIR` is the hand-over checklist: which engineering values are still missing, what depends on each, and which values that are set are invalid. It ends with exit code 1 while anything is missing, so it can also be a gate in a script. Its first line counts the values that are set; a new project says `Engineering values: 0 of 17 set.`

Two shortcuts fill values in:

- **A current-by-gauge table from a file:** `harness config DIR --ampacity-csv FILE` (two columns, `gauge,amperes`; the file `ampacity-DEMO-ONLY.csv` in the templates is a learning example). It is checked before anything is written: `Loaded 6 gauges into config/derating.json. Review it, then set "placeholder": false when the file is complete.`
- **Values from a named profile:** `harness config DIR --apply-profile ecss-q-st-30-11c` (or `ecss-e-st-20-07c`) fills the values that are still empty, keeps every value you set, and prints which requirement of the supplied standard each value comes from. The files stay `"placeholder": true` until an engineer has reviewed them. This is a convenience for filling in numbers from a standard that you were given; it is not a statement that a design complies with it. See [`CONFIG.md`](CONFIG.md).

Remember that the settings live **inside** `"values": {...}` in each file; a key beside it is refused (see [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md#checking)), and a misspelled key inside it is silently ignored, so run `harness config DIR` after every edit and check that the count went up.

## Choose how interfaces are grouped into harnesses

`config/segmentation.json` has one setting, `"mode"`. It decides what one harness (one drawing, one cable bundle) contains. The same `small-satellite` example (14 units, 24 interfaces) gave:

| `"mode"` | One harness per... | Harnesses |
| --- | --- | --- |
| `per_connector_pair` (default) | pair of unit connectors | 24 |
| `per_unit_pair` | pair of units | 23 |
| `per_zone_pair` | pair of zones (lanes of the diagram) | 5 |

Edit the file (`"mode": "per_zone_pair"` inside `"values"`), run `harness generate DIR`, and the report says `5 added, 0 changed, 0 unchanged, 24 removed`. Released harnesses are never touched. Which rule your company wants is an open decision of the owner (D-10, see [`OPEN_DECISIONS.md`](OPEN_DECISIONS.md)); the default is a placeholder. The `flatsat` example ships with `per_zone_pair`.

## Wire colours

The tool defines no wire colours. A wire has a colour only if you set one: by hand on the wire, in the app with **Edit > Wire colours...** (one colour per signal name such as `PWR`, `RTN`, `CANH`; one undo step), or in `config/generation.json` under `"values"`:

```
"wire_colour_by_signal": {"PWR": "red", "RTN": "black"}
```

After `harness generate`, the wire list has the colours and the drawings draw them (with the IEC 60757 code as text, so a black-and-white print loses nothing). Unset wires stay grey. Running this on `small-satellite` and comparing the two folders with `harness compare` listed the changed configuration and 23 wires whose `colour` went from `(none)` to `red` or `black` (`Comparing sa with sb: 0 added, 0 removed, 24 changed.`). This needs the newer build; see [`OUTPUTS.md`](OUTPUTS.md).

## Waivers

A warning of the design rule check can be fixed or **waived**: in the app, press **Waive...** on the finding in the **Problems** tab and write a reason of at least 10 characters. Errors cannot be waived. The waiver is stored in `waivers.json` at the top of the project folder, which is plain text and therefore shows up in Git review like any other change. This is the shape of the file for one waiver:

```
{
  "waivers": [
    {
      "id": "part-unapproved.EX-MICROD-15-F",
      "justification": "Example part, practice project only",
      "notes": "",
      "object_id": "EX-MICROD-15-F",
      "rule": "part-unapproved"
    }
  ]
}
```

`harness drc` then counts it (`Open: 0 error(s), 9 warning(s), 8 note(s). Waived: 1.`) and lists it in a section *Waived findings*, with the reason, so a reviewer still sees it. The id is `<rule>.<object>`. (The app writes this file; the copy above was typed by hand to see what `harness drc` does with it.) Do not confuse this with *waived by the owner* in the compliance documents; the words differ in meaning (see [`GLOSSARY.md`](GLOSSARY.md#words-that-mean-two-things-here)).

## Small habits

- **Preview imports:** every `import-*` command accepts `--dry-run`; it shows each row and changes nothing. See [`IMPORTS.md`](IMPORTS.md).
- **Undo is cheap:** an import is applied as one undo step in the app, however many rows it has.
- **Look at the Why tab:** select a wire and read *Why is it like this?* before you override a choice.
- **Lock what you decided:** a wire or pin you set by hand and lock is kept by every later generation.
- **Verify before you send:** `harness verify DIR --outputs` re-reads the exported files and compares them with the design; the 12-character model hash in every file tells you which design printed it.
- **Plan on paper first** with `design-worksheet.md` from the templates (on `master`, not in the 0.1.0 packages).

## Working with other tools

**This repository contains no integration with SpaceMissionStudio, Requirements Studio, Budget Studio, AIT Logbook or ICD Studio.** The whole repository was searched, case-insensitively and with or without spaces, for all five names: the only file that contains them is the audit record [`../../docs/DOCS_AUDIT.md`](../../docs/DOCS_AUDIT.md), which says the same thing. There is no code, no format, no command and no setting for any of them. The tool also makes no network connection (a test checks it), so nothing could talk to another program behind your back.

What does exist is **files**. The tool reads a few file formats in and writes several out. Anything you want to connect to another program has to go through these files, by hand or by a script you write.

### What the tool reads

| What | File type | Exact columns or fields | How |
| --- | --- | --- | --- |
| Interfaces between units | CSV or XLSX (first sheet) | `id`, `type`, `from`, `to`, `redundancy` (the last is optional). Headers are matched by name; `from` is also read from `from unit`, `source` or `a`; `to` from `to unit`, `destination`, `target` or `b`; the type from `interface type`, `kind` or `protocol`. The units must already exist; `type` is the name or ID of an interface type. | App only: **File > Import interfaces...** (no `harness` command). Starting file: `interfaces.csv` |
| Approved parts list | CSV or XLSX | Matched by header: part ID or part number, manufacturer, description, category, specification, approval status, pin count, mass (g), mass per metre (g/m), mating part. The template has `part number,manufacturer,description,category,pin count,approval status`. You say what the approval values mean with `--approved`, `--pending` and `--rejected`. | `harness import-parts DIR FILE ...` |
| Segment lengths | CSV or XLSX | `harness,segment,length`, read **by position** (this order); default unit millimetres; `--unit` can be `mm`, `cm` or `m`. | `harness import-lengths DIR FILE` |
| Unit connector pinouts | KiCad netlist (`.net`, S-expression or XML) | Components whose reference starts with the prefix (default `J`); the symbol fields `HarnessConnector` (connector ID) and `HarnessPart` (part); net names become signal names, optionally renamed with a signal map with the columns `net,signal`. | `harness import-netlist DIR FILE --unit UNIT ...` ([`KICAD.md`](KICAD.md)) |
| Current by wire gauge | CSV | `gauge,amperes` (header optional) | `harness config DIR --ampacity-csv FILE` |
| Other engineering values | the JSON files in `config/` | see [`CONFIG.md`](CONFIG.md) | edit by hand, check with `harness config DIR` |

Units themselves cannot be imported from a table; you add them in the app. The details of every column are in [`IMPORTS.md`](IMPORTS.md).

### What the tool writes

`harness export DIR` writes everything into `DIR/outputs/`. For the `first-steps` example it writes 38 files; these are the names (per harness, `W001` and `W002` here):

```
outputs/manifest.json
outputs/harnesses/W001/  W001.xlsx  bom.csv  drawing_A3.pdf  drawing_A3_s1.svg  drawing_A4.pdf
                         labels.csv  mass_length.csv  pinouts.csv  tests.csv  wirelist.csv  wireviz.yaml
outputs/system/  block_diagram.pdf  block_diagram.svg  bom.csv  box_pinouts.csv  changelog.csv
                 drc_findings.csv  drc_report.md  export.json  harness_overview.pdf  harness_overview.svg
                 mass_length.csv  mating_matrix.csv  provenance.json  revision_report.md
                 system.xlsx  traceability.csv
```

| Format | Files | Header (first row after the `# ...` stamp line) |
| --- | --- | --- |
| CSV | `wirelist.csv` | `Wire,Signal,Interface,From connector,From pin,To connector,To pin,AWG,Part,Colour,Length (m),Shield group,Locked` |
| CSV | `pinouts.csv`, `system/box_pinouts.csv` | `Connector,Role,Mates with,Part,Pin,Signal,Interface,Wires,Spare` |
| CSV | `bom.csv` (per harness and `system/`) | `Part,Category,Manufacturer,Part number,Description,Approval,Quantity,Unit,Wires without length,Used in` |
| CSV | `mass_length.csv` (per harness and `system/`) | `Harness,Wires,Connectors,Wire length known (m),Wires without length,Mass of known parts (g),Margin (g),Mass with margin (g),Complete,Missing data` |
| CSV | `tests.csv` | `Test,Type,From,To,Expected,Limit,Test voltage,Wire` |
| CSV | `labels.csv` | `Label,Kind,Text,Quantity` |
| CSV | `system/mating_matrix.csv` | `Box connector,Unit,Part,Gender,Cable connector,Cable part,Cable gender,Harness` |
| CSV | `system/traceability.csv` | `Interface,Name,Type,From,To,Harnesses,Wires,Routed` |
| CSV | `system/drc_findings.csv` | `Finding,Rule,Severity,Object,Statement,Waived,Justification,Requirement` |
| CSV | `system/changelog.csv` | `Entry,Harness,Revision,Event,By,Date,Comment` |
| XLSX | `<ID>.xlsx` per harness, `system/system.xlsx` | all tables as sheets |
| JSON | `system/export.json` | the whole model in one file: `box_connectors`, `format`, `format_version`, `generator`, `harnesses`, `interface_types`, `interfaces`, `model_hash`, `parts`, `placeholder_config`, `project`, `units` |
| JSON | `manifest.json`, `system/provenance.json` | the list of files with checksums; which tool version and design made them |
| SVG and PDF | `drawing_A3_s<n>.svg` (A3 sheets), `drawing_A3.pdf`, `drawing_A4.pdf`, `system/block_diagram.*`, `system/harness_overview.*` | drawings |
| YAML | `wireviz.yaml` per harness | "WireViz-style" input: `metadata`, `connectors`, `cables`, `connections`. Written by this tool; **not validated against the WireViz program**. |
| Markdown | `system/drc_report.md`, `system/revision_report.md` | reports |

Every CSV starts with a comment line (`# harness-design-studio 0.1.0 model <hash>`) that a reader must skip. Details and limits: [`OUTPUTS.md`](OUTPUTS.md). The interface Properties panel of the app has a field *Requirement ID (for traceability)*; its value is part of the interface in `system/export.json`.

### Ideas, not features

Each sentence below is an **idea, not a feature: not built, not tested**. It names which of the files above could carry data to or from one of your other tools, *if* that tool can read or write that kind of file. Nothing here has been tried, and nothing in this repository knows the formats of those tools.

- **SpaceMissionStudio** - idea, not a feature (not built, not tested): a list of units and links could be turned into `interfaces.csv` (`id,type,from,to,redundancy`) and imported with **File > Import interfaces...**, after the units have been added by hand in the app.
- **Requirements Studio** - idea, not a feature (not built, not tested): `system/traceability.csv` (interface to harness to wires) and the `Requirement ID` of each interface in `system/export.json` could be read by a script and compared with a requirement list; note that the `Requirement` column of `drc_findings.csv` holds the IDs of the standard requirements a rule serves, not your programme's requirements.
- **Budget Studio** - idea, not a feature (not built, not tested): `system/mass_length.csv` (known wire length, mass with margin, and whether the data is `Complete`) could feed a mass or harness-length budget; its totals count only what is known, and in the `flatsat` example they include ground-equipment harnesses.
- **AIT Logbook** - idea, not a feature (not built, not tested): `tests.csv` (one continuity test per wire, isolation tests, limits that read `TBD (placeholder)` until set) and `labels.csv` could be used as the list of what to test and what to label; the tool has no way to read test results back.
- **ICD Studio** - idea, not a feature (not built, not tested): `system/box_pinouts.csv`, `pinouts.csv` and `wirelist.csv` (connector, pin, signal, interface, wire) are pin-level tables that could be an input to an interface document, and `interfaces.csv` is the format the other way; the tool does not read or write an interface control document itself.

If you decide that one of these exchanges is worth building, say so in an issue; until then this page describes files and nothing else.

Next: [`CHEATSHEET.md`](CHEATSHEET.md), [`user-manual/README.md`](user-manual/README.md)
