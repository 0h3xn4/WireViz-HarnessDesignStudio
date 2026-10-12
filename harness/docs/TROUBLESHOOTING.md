# Troubleshooting

This page lists the error messages you are most likely to meet, with the exact text, why it happens and how to fix it, in the order you meet them.

## Contents

- [How this page was made](#how-this-page-was-made)
- [Exit codes: what 0, 1 and 2 mean](#exit-codes-what-0-1-and-2-mean)
- [Installing](#installing)
- [Starting](#starting)
- [Creating a project](#creating-a-project)
- [Generating](#generating)
- [Checking](#checking)
- [Importing](#importing)
- [Exporting](#exporting)
- [Releasing](#releasing)
- [Where do my files go, and how do I start over?](#where-do-my-files-go-and-how-do-i-start-over)

## How this page was made

Every message below was produced on purpose with the tool (version `0.1.0`, installed into a clean Python virtual environment on Ubuntu 24.04) and pasted as the tool printed it. Project folder names such as `demo` are the ones used in the commands. Some things were **not** run, and the page says so where they appear: the `.deb` and `.tar.gz` installs and the packaged `--selftest` (text quoted from [`INSTALL.md`](INSTALL.md)), and anything that needs the app window (text quoted from the program's own message list). Messages about the examples of the released 0.1.0 packages were produced from the source of the `v0.1.0` tag.

Questions that are not errors ("which example should I start with?", "does it use the internet?") are answered in [`FAQ.md`](FAQ.md). Words you do not know are explained in [`GLOSSARY.md`](GLOSSARY.md).

## Exit codes: what 0, 1 and 2 mean

Every `harness` command ends with a number you can read with `echo $?`. Scripts and CI use it. The full table is in [`CLI.md`](CLI.md).

| Code | Meaning | Example you can try |
| --- | --- | --- |
| 0 | It worked. Warnings are allowed. | `harness validate demo` |
| 1 | The project has errors, or a step is **blocked** (a release, an import with bad rows, an export with nothing to export). Your command was understood; the design or the data is the problem. | `harness export demo` before `harness generate demo` |
| 2 | **Usage error**: a wrong word, a missing argument, a folder that is not a project, a file that cannot be read. Your command was not understood or its input does not exist. | `harness generate notproj` |

```
harness validate demo
echo $?
```

```
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
3 units, 2 interfaces, 9 connectors, 0 harnesses: 0 error(s), 0 warning(s).
0
```

Two commands use 1 in a way that can surprise you: `harness drc` ends with 1 when there is an open **error** (warnings still give 0), and `harness config` ends with 1 while any engineering value is still missing, which is normal for a new project.

## Installing

### `harness: command not found`

```
bash: line 1: harness: command not found
```

(In a terminal you type into, the `line 1:` part is missing.) The shell cannot find the `harness` program. Why, by the way you installed:

- **`.tar.gz` install (way B of [`INSTALL.md`](INSTALL.md)):** `~/.local/bin` is not on your `PATH`. Fix it once with `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc` and then `. ~/.bashrc` (or log out and in).
- **Run from source or pip into a virtual environment (way C):** the environment is not active in this terminal. Run `. .venv/bin/activate` in the folder where you made it.
- **Nothing installed yet:** start at [`INSTALL.md`](INSTALL.md).

Check with `harness --version`; it prints `harness 0.1.0` (or a newer number).

### I am on Windows or macOS

The tool runs on **Ubuntu 24.04 or newer, 64-bit x86**, and nothing else. Windows, macOS, other Linux distributions and Ubuntu 22.04 and older are not supported (decision D-127). Check your system with `lsb_release -rs` (must print 24.04 or higher). See [`INSTALL.md`](INSTALL.md).

### `E: Unable to locate package ./harness-design-studio_...` or `dpkg: dependency problems`

Not run for this page; quoted from [`INSTALL.md`](INSTALL.md). Run `sudo apt install ./harness-design-studio_<version>_amd64.deb` in the folder that holds the file and keep the `./` in front of the name. For `dpkg: dependency problems`, run `sudo apt install -f`; it installs the missing system libraries from your normal Ubuntu sources.

### `install.sh` says there is nothing to install

Not run for this page. You ran `install.sh` from the source tree. Run it from the unpacked `.tar.gz` folder. See [`INSTALL.md`](INSTALL.md).

## Starting

### Qt cannot load the "xcb" platform plugin

This is what the app printed on a machine without the Qt system libraries and without a screen:

```
qt.qpa.plugin: From 6.5.0, xcb-cursor0 or libxcb-cursor0 is needed to load the Qt xcb platform plugin.
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.
```

The command ended with exit code 134 (aborted). Why: a system library that Qt needs is missing, or there is no screen to draw on. A normal Ubuntu desktop has these libraries; a container or a server image does not. Fix, from [`INSTALL.md`](INSTALL.md):

```
sudo apt install libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0
```

Messages that mention `libEGL` or `libxkbcommon` have the same fix. If you are connected over SSH, the app has no screen: use the `harness` command line over SSH, or start the app on the machine itself. The `harness` command line never needs these libraries.

### `harness-gui --selftest` does not print `selftest ok`; it opens the app

`--selftest` belongs to the **packaged** program `harness-design-studio` (the `.deb` and `.tar.gz` installs). The `harness-gui` command of a source or pip install does not know the word and starts the app. Run offscreen (`QT_QPA_PLATFORM=offscreen harness-gui --selftest`) it printed

```
This plugin does not support propagateSizeHints()
```

and then kept running until it was stopped after 15 seconds. To check a source install use `harness --version` and, for developers, `pytest`. To check a packaged install use `harness-design-studio --selftest`, which is expected to print `selftest ok` (not run for this page).

### The window is blank, tiny, or closes at once

Run `harness-design-studio --selftest` in a terminal (packaged install) and read the message; if it names `xcb`, `libEGL` or `libxkbcommon`, install the libraries above. If the window is tiny or the text too small, use **View > UI scale**. The settings file is `~/.config/HarnessDesigner/HarnessDesigner.ini`; delete it to reset the scale, theme and last project (it holds no design data).

### A banner says "Read-only: this project was saved by a newer version of the tool, or is open in another window"

The app's own wording:

```
Read-only: this project was saved by a newer version of the tool, or is open in another window. You cannot change it here.
```

Nothing was changed. Two causes:

1. **The project was saved by a newer tool.** On the command line the same project gives a warning on `validate` and refuses to change anything. This is what a project marked as format 99 printed (made by editing `project.json` for the test):

   ```
   harness validate newer
   ```

   ```
   INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
   WARNING newer_version: This project was saved by a newer version of the tool (format 99; this tool understands up to 1). It is opened read-only. [project.json]
   3 units, 2 interfaces, 9 connectors, 0 harnesses: 0 error(s), 1 warning(s).
   ```

   ```
   harness generate newer
   ```

   ```
   error: this project is read-only (saved by a newer tool version).
   ```

   The exit code is 2. `harness migrate newer` gives the same error. **Fix:** install the newer tool (see [`INSTALL.md`](INSTALL.md)); `harness validate` can still read the project with this one. Do not edit `project.json` by hand to make the warning go away.
2. **It is open in another window.** See the next entry.

### "Project already open" / "This project is already open in another instance of the tool"

The app's dialog says: *This project is already open in another window or session. Close it there first, or open this copy read-only.* with the button **Open read-only**. On the command line, with a lock file of a running session in the project folder:

```
harness generate lk
```

```
error: This project is already open in another instance of the tool. Close it there first, or open this copy read-only.
```

The exit code is 1. Commands that only read (such as `harness validate lk`) still work. **Why:** the app and every command that changes a project take the same lock (`.harness.lock` in the project folder), so they never write at once. **Fix:** close the other window or wait for the other command to end. A lock left behind by a crashed session on the same machine is taken over automatically. A lock written by another computer (a shared drive) cannot be checked, so it is treated as alive; if you are certain nobody has the project open, delete the `.harness.lock` file in the project folder.

### "This project has problems" (the recovery view)

The app's wording for the banner:

```
Parts of this project could not be loaded. Everything else was loaded. The original folder is protected.
```

and in the window: *Some parts could not be loaded. Everything else was loaded. The original folder is protected: it cannot be overwritten.* One or more files are damaged. The app shows what it could read. **Fix:** press **Save salvaged copy…** to write a clean copy to a new folder (the parts that could not be loaded are kept word for word in `quarantine.json` and `quarantine/files/` beside it, so nothing is lost), and repair or restore the original from Git. On the command line the same damage looks like this (a unit file cut off in the middle, made for the test):

```
harness validate dmg
```

```
ERROR   invalid_json: The file is not valid JSON at line 2, column 11: Expecting value. [logical/units/aocs.json]
ERROR   unknown_unit: Box connector 'RW1-J01' does not belong to an existing unit.
ERROR   unknown_unit: Box connector 'RW1-J02' does not belong to an existing unit.
ERROR   unknown_unit: Interface 'IF-001' refers to unit 'RW1', which does not exist.
ERROR   unknown_unit: Interface 'IF-002' refers to unit 'RW1', which does not exist.
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
WARNING orphan_placement: A diagram position exists for 'RW1', which is not a unit.
2 units, 2 interfaces, 9 connectors, 0 harnesses: 5 error(s), 1 warning(s).
```

Read the **first** error: it names the file and the line and column. The other errors follow from it (the wheel is missing, so everything that mentions it is wrong). The message never prints the content of the file, because it may be confidential. Fix the file (a JSON-aware editor shows the position; `git diff` shows what changed) and run `harness validate` again. `harness generate` on a project with errors changes nothing; after two `warning: [interface_skipped]` lines it ends with (exit code 1):

```
2 interfaces and 0 wires checked: 6 error(s)
Not saved: fix the errors above first.
```

### "Unsaved changes found" at start

```
The last session ended before its changes were saved. Restore them?
```

The app keeps an autosave (`.harness-recovery/` in the project folder). Press **Restore** to bring your last edits back.

## Creating a project

### `error: Unknown template 'satellite'. Choose one of: ...`

```
harness new x1 --template satellite
```

```
error: Unknown template 'satellite'. Choose one of: blank, first-steps, minimal-satellite, small-satellite, flatsat.
```

Exit code 2. The name after `--template` must be exactly one of the five names. `harness new --list` prints them with a one-line description. See [`examples/README.md`](examples/README.md).

### The same error for `minimal-satellite` or `flatsat`, on the released 0.1.0 packages

The examples `minimal-satellite` and `flatsat`, and the template `design-worksheet.md`, were added **after** the 0.1.0 release (see [`../CHANGELOG.md`](../CHANGELOG.md), section *Unreleased*). A tool installed from the 0.1.0 `.deb` or `.tar.gz` has only three examples. This is what the source of the `v0.1.0` tag prints:

```
harness new --list
```

```
blank            An empty project: starter parts and interface types, no units.
first-steps      Three units, a power link and an RS-422 link. Nothing is generated yet: start here.
small-satellite  14 units with nominal and redundant chains. Generate it to see a realistic system.
```

```
harness new old1 --template minimal-satellite
```

```
error: Unknown template 'minimal-satellite'. Choose one of: blank, first-steps, small-satellite.
```

**Fix:** use `first-steps` or `small-satellite`, or install a newer build (way C of [`INSTALL.md`](INSTALL.md) builds the latest source). `harness templates DIR` also writes 14 files instead of 15 on 0.1.0 (no `design-worksheet.md`).

### `error: demo already exists and is not an empty folder; choose a new one.`

```
harness new demo --template first-steps
```

```
error: demo already exists and is not an empty folder; choose a new one.
```

Exit code 2. `harness new` never overwrites anything. Choose a folder name that does not exist yet, or an existing folder that is empty. To throw the old project away and start again, see [the last section](#where-do-my-files-go-and-how-do-i-start-over).

### `error: give the folder for the new project (or use --list).`

You ran `harness new` with no folder name. Give one: `harness new my-design --template first-steps`.

## Generating

### `error: 'notproj' is not a harness project folder (no project.json).`

```
harness generate notproj
```

```
error: 'notproj' is not a harness project folder (no project.json).
```

Exit code 2. The folder exists but is not a project: a project folder always has a `project.json` at its top. Why it happens: you are in the wrong folder (go one level in or out), you typed the wrong name, or you pointed at a folder **inside** the project (`demo/outputs`). `ls demo/project.json` should find the file. Every command that takes a project (`validate`, `check`, `generate`, `drc`, `export`, `verify`, `config`, ...) gives this message. If the folder does not exist at all you get `error: 'does-not-exist' is not a folder.`

### Generating a blank project makes nothing

```
harness new demo-blank --template blank
harness generate demo-blank
```

```
0 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
0 interfaces and 0 wires checked: 0 error(s)
```

Not an error: the blank project has no units and no interfaces, and the command line cannot add them. Add units and interfaces in the app (see Part 10 of [`GETTING_STARTED.md`](GETTING_STARTED.md)), or start from `first-steps`.

### `Not saved: fix the errors above first.` with `[contact_overload]` or `[wire_sizing]`

Seen after setting the maximum current of the power link *Feed of the AOCS distribution unit* (`IF-009`) of the `flatsat` example to 8 A in its project file:

```
error: [contact_overload] W002-001: 8 A exceeds the derated contact rating of PCDU1-J09.
error: [contact_overload] W002-001: 8 A exceeds the derated contact rating of PDU2-J01.
error: [contact_overload] W002-002: 8 A exceeds the derated contact rating of PCDU1-J09.
error: [contact_overload] W002-002: 8 A exceeds the derated contact rating of PDU2-J01.
error: [wire_sizing] W002-001: no listed gauge carries 8 A after derating (factor 0.54).
error: [wire_sizing] W002-002: no listed gauge carries 8 A after derating (factor 0.54).
0 added, 1 changed, 7 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
44 interfaces and 103 wires checked: 0 error(s)
Not saved: fix the errors above first.
```

Exit code 1. **Why:** the current is more than the connector contact (or the largest wire in your ampacity table) can carry after derating. The line `44 interfaces and 103 wires checked: 0 error(s)` is the same independent check that `harness verify` prints; the errors that stopped the save are the `error:` lines above it. Nothing was written. **Fix:** lower the current, or choose a connector or wire that can carry it. If you think the derating values are wrong, ask the engineer who owns them (`harness config DIR` lists them); do not lower them just to make the error go away. Run `harness generate` again.

### A wire gauge says `pending`

Not an error. A gauge stays *pending* until the interface has a **Max current (A)**, the ampacity and derating values exist, and the segment lengths are known. `harness config DIR` lists what is missing and why it matters. See [`CONFIG.md`](CONFIG.md) and [`PLACEHOLDERS.md`](PLACEHOLDERS.md).

## Checking

### `ERROR quarantined: ... Extra inputs are not permitted` (a setting in the wrong place)

The configuration files in `config/` do **not** have the settings at the top level. Every file has the shape `{"name": ..., "placeholder": ..., "values": {...}}`, and the settings go **inside `values`**. This is a new project's `config/derating.json`:

```
{
  "name": "derating",
  "placeholder": true,
  "values": {
    "ampacity_a_by_awg": null,
    "bundle_derating": null,
    "contact_current_factor": null,
    "contact_rating_key": "contact_current_a",
    "max_ambient_temperature_c": null,
    "max_voltage_drop_v": null,
    "spare_pin_fraction": null,
    "temperature_derating": null
  }
}
```

If you add `"bundle_derating": 0.8` next to `"values"` (a typical mistake, because the key tables in [`CONFIG.md`](CONFIG.md) list the keys without showing the wrapper), the file is refused and the built-in placeholder is used instead:

```
harness validate q
```

```
ERROR   quarantined: A configuration could not be loaded and was set aside: bundle_derating: Extra inputs are not permitted [config/derating.json]
INFO    config_defaulted: Configuration 'derating' is missing or unreadable; the built-in placeholder is used. [config/derating.json]
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
3 units, 2 interfaces, 9 connectors, 0 harnesses: 1 error(s), 0 warning(s).
```

Exit code 1. **Fix:** move the key into `"values"`:

```
{
  "name": "derating",
  "placeholder": true,
  "values": {
    "ampacity_a_by_awg": null,
    "bundle_derating": 0.8,
    "contact_current_factor": null,
    "contact_rating_key": "contact_current_a",
    "max_ambient_temperature_c": null,
    "max_voltage_drop_v": null,
    "spare_pin_fraction": null,
    "temperature_derating": null
  }
}
```

Then `harness validate` is clean again and `harness config DIR` counts the value as set (it said `Engineering values: 1 of 17 set.` after this change). A misspelled key **inside** `values` is not reported: `harness validate` stays quiet and the key is ignored, so `harness config DIR` still lists the correct key as `MISSING`. Run `harness config DIR` after every edit of a configuration file and check that the count of set values went up. Set `"placeholder": false` only after an engineer has reviewed the whole file. To get a file back to its starting state, copy it from a fresh project: `harness new fresh --template blank`, then copy `fresh/config/derating.json` over yours.

### `ERROR merge_conflict: The file contains unresolved Git merge conflict markers.`

```
harness check mc
```

```
ERROR   merge_conflict: The file contains unresolved Git merge conflict markers. Resolve the conflict first. [logical/interfaces/power.json]
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
3 units, 1 interfaces, 9 connectors, 0 harnesses: 1 error(s), 0 warning(s).
```

A Git merge left `<<<<<<<`, `=======` and `>>>>>>>` lines in a project file. Open the file named in brackets, decide which side to keep, delete the three marker lines, and run `harness check` again. Use `check` rather than `validate` after a merge: `check` also finds these markers and released harnesses that were edited.

### `harness drc` ends with exit code 1

An open **error** of the design rule check. The summary line says how many:

```
Open: 5 error(s), 28 warning(s), 47 note(s). Waived: 0.
```

Errors cannot be waived; fix them. Read the `## Errors` section of the report (`harness drc DIR`), where each finding says why it matters and how to fix it. Warnings can be fixed or waived with a written reason in the app. The rules are explained in [`RULES.md`](RULES.md).

### `harness verify DIR` or `--outputs` prints `[outputs_outdated]`, `[out_stale]`, `[out_stamp]` or `[out_modified]`

You changed the design (here: renamed a unit in a project that was already generated and exported) or edited an exported file:

```
harness verify so --outputs
```

```
error: [outputs_outdated] The model changed after the harness plans were generated. Generate again before releasing.
error: [out_stale] The outputs were made from an older version of the design.
error: [out_stamp] harnesses/W001/W001.xlsx does not carry the current generator and model stamp.
...
```

(many `out_stamp` lines follow, one per file.) And after appending a line to `system/bom.csv` by hand:

```
error: [out_modified] system/bom.csv was changed after it was exported.
```

Exit code 1. **Fix:** never edit files in `outputs/`; they are made from the design and are safe to delete. Run `harness generate DIR`, then `harness export DIR`, then `harness verify DIR --outputs`.

## Importing

All imports preview first. With `--dry-run` nothing is changed; without it, **nothing is written if any row has a problem**. The exit code is 1 when a row has a problem. Fix the file and run again. The columns and their alternative names are in [`IMPORTS.md`](IMPORTS.md); starting files are in `harness templates DIR`.

### `import-lengths`: `row N: ERROR ...`

Take this file, `bad-lengths.csv` (made for the test, on the project `imp` made from `first-steps` and generated):

```
harness,segment,length
W001,W001-L1,850
W001,W001-L9,900
W007,W007-L1,abc
W002,W002-L1,-5
```

```
harness import-lengths imp bad-lengths.csv --dry-run
```

```
row 2: OK
row 3: ERROR Harness 'W001' has no segment 'W001-L9'
row 4: ERROR Harness 'W007' does not exist
row 5: ERROR '-5' is not a length (digits with a decimal point or comma)
1 length(s) ready, 3 row(s) with problems.
Nothing was changed.
```

Row numbers count the header as row 1. A row with two problems shows only the first one (row 4 has a missing harness and a length `abc`; with the harness right, `abc` is reported as `'abc' is not a length (digits with a decimal point or comma)`). Use the harness and segment IDs from your project (the drawing and `wirelist.csv` show them; segments are called `W001-L1` and so on). A length must be digits, with a decimal point or comma, no minus sign. The default unit is millimetres; add `--unit m` or `--unit cm`. If **every** row fails on the harness name, the columns are in the wrong order:

```
row 2: ERROR Harness 'W001-L1' does not exist
0 length(s) ready, 1 row(s) with problems.
Every row failed on the harness name. The columns are read by position: harness, segment, length. The headings of the file read: segment, length, harness. If they are in another order, reorder the columns and try again.
Nothing was changed.
```

Unlike the other imports, this one reads the columns **by position**: first the harness, then the segment, then the length. After a successful import run `harness generate DIR` so the wire lengths follow. A file that does not exist gives `error: The file could not be read (No such file or directory).` (exit code 2).

### `import-parts`: `Approval status 'Approved' is not in your approved, pending or rejected lists; say what it means`

```
harness import-parts imp approved-parts.csv --dry-run
```

```
row 2: ERROR Approval status 'Approved' is not in your approved, pending or rejected lists; say what it means
...
0 part(s) ready, 5 row(s) with problems.
Nothing was changed.
```

The tool never decides what "approved" means in **your** file. Tell it which values mean what: `--approved Approved --pending Review --rejected Rejected` (repeat an option for several values). With them the same file reads `5 part(s) ready, 0 row(s) with problems.` Other messages of this command:

```
row 3: ERROR Category 'widget' is not one of connector, contact, backshell, wire, sleeving, label
row 5: ERROR The row has no part ID or part number
```

Give every row a `category` column value from that list (or one `--category` for the whole file), and a part number.

### `import-netlist`: `The file is not a KiCad netlist`

```
harness import-netlist imp bad.kicad_sch --unit RW1
```

```
error: The file is not a KiCad netlist (no (export ...) at the top).
```

Exit code 2. The tool reads the **netlist** that KiCad exports (File, Export, Netlist), not the schematic file `.kicad_sch`. See [`KICAD.md`](KICAD.md). Other messages:

```
-: ERROR Unit 'RW9' does not exist
```

The `--unit` must be a unit of the project (check the ID in the app or in `logical/units/`).

```
J1: ERROR Connector RW1-J77 has no library part: set the field HarnessPart or use --part J1=PART
```

`--connector J1=RW1-J77` named a connector that does not exist yet, so the tool would create it but does not know which part to use. Either fix the ID (`RW1-J01` exists), or add `--part J1=EX-MICROD-9-F`, after which the line reads `J1: OK added RW1-J77 (2 signal pin(s))`. And `J9: ERROR 'J9' is not in the netlist` means `--ref J9` names a part that is not in the file.

### Interfaces: a row cannot be placed

Importing interfaces (**File > Import interfaces...**, CSV or XLSX) is done in the app only; there is no `harness` command for it. The preview lists each row; a row that cannot be placed says why (a unit that does not exist, no free connector on a unit that can carry the type) and nothing is applied. See [`IMPORTS.md`](IMPORTS.md). The messages were not run for this page because they need the app window.

## Exporting

### There are no harnesses to export

```
harness export demo
```

```
error: there are no harnesses to export; run `harness generate` first.
```

Exit code 1. Outputs are written per harness, and none exists yet. Run `harness generate demo`, then `harness export demo`. (With the `blank` project it stays this way until you add units and interfaces in the app.)

### No outputs folder

```
harness verify demo --outputs
```

```
error: no outputs folder; run `harness export` first.
```

Exit code 1. `--outputs` checks the files in `demo/outputs`; there are none yet.

### Which file is what?

See [`OUTPUTS.md`](OUTPUTS.md) for the list of files. A project of the `first-steps` example writes `38 files written to demo-first-steps/outputs (model 91531b45fd2c).`

## Releasing

A release is refused (exit code 1) until every check passes. Each reason is printed on a line `blocked: [code] words`. Read all lines: fix them one by one. This is what a first try on the `first-steps` example prints:

```
harness release rel W001 --by "Ada" --comment "short"
```

```
blocked: [comment_short] The comment needs at least 10 characters: say what changed or why.
blocked: [placeholder_config] These configuration files are still placeholders: derating, emc, generation, segmentation, segregation, titleblock. Have an engineer review the values and set "placeholder" to false in each file (`harness config DIR` lists them). Or release on placeholders with a written reason; the reason is kept in the change log.
blocked: [parts_unapproved] 3 part(s) used by W001 are not approved (or are example data): EX-MICROD-21-M, EX-MICROD-25-M, EX-WIRE-TWISTED-SHIELDED. Approve them in the parts list, or release with a written reason; the reason is kept in the change log.
blocked: [gauge_pending] 4 wire(s) have no gauge decided (first: W001-001). Fill in the derating values (the file config/derating.json; `harness config DIR` lists what is missing) or set the gauge by hand.
blocked: [length_unknown] 4 wire(s) have no length (first: W001-001). Enter the routing segment lengths (`harness import-lengths DIR FILE` loads them from a table).
blocked: [outputs_missing] Outputs have not been exported yet. Export them, review them, then release.
```

| Code | Why | Fix |
| --- | --- | --- |
| `comment_short` | `--comment` has fewer than 10 characters. | Say what changed or why, in at least 10 characters. |
| `placeholder_config` | A configuration file is still marked `"placeholder": true`: nobody has reviewed the engineering values. | Have an engineer review the files and set `"placeholder": false` in each; or release anyway with `--accept-placeholders "reason"`. The reason is kept in the change log and the baseline. |
| `parts_unapproved` | The harness uses a part that is not on the approved list, or is example data. | Approve the parts (`harness import-parts`, see [`IMPORTS.md`](IMPORTS.md)); or release with `--accept-unapproved-parts "reason"`. |
| `gauge_pending` | A wire has no gauge. | Enter the derating and ampacity values (`harness config DIR`), the interface currents, and generate again. |
| `length_unknown` | A wire has no length. | `harness import-lengths DIR FILE`, then `harness generate DIR`. |
| `outputs_missing` | You have not exported yet. | `harness export DIR`. (`outputs_stale` and `outputs_modified` mean the outputs no longer match the design; export again.) |

The two reasons for placeholders and unapproved parts need at least 10 characters too:

```
blocked: [placeholder_reason_short] The reason for releasing on placeholders (derating, emc, generation, segmentation, segregation, titleblock) needs at least 10 characters.
blocked: [parts_reason_short] The reason for releasing with parts that are not approved needs at least 10 characters.
```

A release that rests on placeholders or example parts teaches the flow and nothing more: the change log records that it did. Practise only in a practice project; the full walk-through is Part 9 of [`GETTING_STARTED.md`](GETTING_STARTED.md). This is what a successful practice release on the `flatsat` example printed, and the change log that follows:

```
Release W003 revision A: done.
Outputs re-exported with the released status (111 files).
```

Other release messages:

```
blocked: [no_harness] Harness W999 does not exist.
```

(exit code 2: wrong harness ID; the IDs are in the Harness plans tab and the `outputs/` folder names.)

```
blocked: [not_released] W003 is not released, so it can be edited directly.
```

(exit code 1: you asked `harness revise` for a harness that is not released; revisions are only for released harnesses.)

### `harness diff ... --from A --to B`: `error: W003 has no baseline for revision B.`

After `harness release` (revision A) and `harness revise` (revision B), this fails:

```
harness diff fs W003 --from A --to B
```

```
error: W003 has no baseline for revision B.
```

Exit code 2. A baseline (the frozen snapshot that `diff` compares) is written **when a revision is released**. Revision B is only a draft until you release it, so it has no baseline. What works: compare revision A with the working design (this is the default; leave out `--to`):

```
harness diff fs W003 --from A
```

```
# W003: working design against revision A

Comparing before with after: 0 added, 0 removed, 1 changed.

## Changed (1)

- Harness `W003`
  - approver: Ada -> (none)
  - released_on: 2026-10-10 -> (none)
  - revision: A -> B
  - status: released -> draft
```

For a harness that was never released: `error: W001 has no baseline yet; release it first.` (exit code 2). `harness log DIR` prints the history, including the reasons given for releasing on placeholders and example parts.

## Where do my files go, and how do I start over?

**A project is a folder.** `harness new demo --template first-steps` creates the folder `demo` **inside the folder you are in** (a path like `~/projects/demo` creates it there). Nothing is kept anywhere else. This is what you get:

```
demo/
  project.json            name and the tool version that last saved it
  config/                 seven rule files (derating.json, generation.json, ...)
  library/                the parts list
  logical/                units, interface types, interfaces, diagram layout
  physical/               connectors (and, after generating, harnesses/)
  generated/              the record of the last generation (after generating)
  outputs/                drawings, tables, exports (after harness export)
  baselines/, changelog.json   written when you release
  waivers.json            written when you waive a finding
  .gitignore              written once; lists files that Git should ignore
```

The files are plain text (JSON), so a project folder can be copied, zipped, e-mailed or kept in Git. The format is in [`FILE_FORMAT.md`](FILE_FORMAT.md).

| What | Where |
| --- | --- |
| Your design | the project folder you named |
| Drawings, wire lists, BOM, exports | `<project>/outputs/` (made by `harness export`; safe to delete and make again) |
| Autosave of the app | `<project>/.harness-recovery/` (offered for restore after a crash; ignored by Git) |
| App settings (theme, scale, last project) | `~/.config/HarnessDesigner/HarnessDesigner.ini` (no design data) |
| Lock file while a project is open | `<project>/.harness.lock` (removed when closed) |
| Copies of the import templates | the folder you gave to `harness templates` |

**To start over:**

- *Throw away the whole project and begin again:* delete the folder and create it again. This removes **everything** in it, including edits you made.

  ```
  rm -r demo
  harness new demo --template first-steps
  ```

- *Make the generated harnesses and outputs fresh:* `harness generate demo` is safe to repeat (generating twice gives the same result); `rm -r demo/outputs` and `harness export demo` rebuild the outputs.
- *Put one configuration file back to its starting state:* copy it from a fresh project (`harness new fresh --template blank`, then copy `fresh/config/derating.json` over yours).
- *Reset the app's look and scale:* delete `~/.config/HarnessDesigner/HarnessDesigner.ini`.
- *Undo a mistake in the app:* **Ctrl+Z**. A released harness is locked; start a new revision with `harness revise` instead of editing it.
- *Two copies to try different ideas:* copy the folder (`cp -r demo demo-try`); `harness compare demo demo-try` shows the differences.

Still stuck? Run `harness validate DIR` and `harness drc DIR` and read the messages: each says what is wrong and how to fix it. Check the output first before you send it to anyone if the project is confidential: the messages name units, interfaces and parts. More answers: [`FAQ.md`](FAQ.md).

Next: [`FAQ.md`](FAQ.md), [`GLOSSARY.md`](GLOSSARY.md)
