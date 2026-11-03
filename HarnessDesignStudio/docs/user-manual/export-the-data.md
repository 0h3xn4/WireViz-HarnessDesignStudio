# Export the data

This page shows how to write every intermediate and final result of a design as files a spreadsheet or a script can read, and how a colleague can check a number from those files alone, without the tool and without your project. Use it for a review, for a trade study, or when someone asks *show me how you got that gauge*.

## Contents

- [Before you start](#before-you-start)
- [1. Write the data](#1-write-the-data)
- [2. Read the files in a spreadsheet](#2-read-the-files-in-a-spreadsheet)
- [3. Read the files in a script](#3-read-the-files-in-a-script)
- [4. Reproduce a number from the files](#4-reproduce-a-number-from-the-files)
- [5. Record who ran it and when](#5-record-who-ran-it-and-when)
- [6. Read a file back into the tool](#6-read-a-file-back-into-the-tool)
- [Common mistakes](#common-mistakes)

## Before you start

- You have a project that is generated: `harness-design-studio new wheel-link --template first-steps`, then `harness-design-studio generate wheel-link`. The packaged examples hold example values, not engineering data; with no derating table the sizing columns are empty and say what is missing.
- The outputs of `export` (the build workbook, the wire lists, the drawings) are what you build from. The data files are what you check with: they hold the numbers *behind* the outputs, one row per wire, per rule, per part, in a form that has no layout.
- Nothing here changes a number or the project. The command reads the design and writes files to the folder you name.

## 1. Write the data

```
harness-design-studio export-data wheel-link --out wheel-link-data
```

```
34 data files written to wheel-link-data (model <hash>).
```

The folder gets a pair of files, `NAME.json` and `NAME.csv`, for each result, and three files of their own:

| Result | What one row is |
| --- | --- |
| `wire_sizing` | a wire: its current, gauge, cross-section in mm², base ampacity, bundle size and factor K, temperature factor, derated limit, length, resistivity, conductors counted, voltage drop, the largest drop allowed, both margins and verdicts, and what is missing |
| `lengths` | a wire: its length and where it comes from (the path through the segments, the service loops, a length stored on the wire) |
| `segment_lengths` | a routing segment that has a length (the input the wire lengths come from) |
| `segmentation_groups`, `segmentation_interfaces` | a group of interfaces that share a harness; an interface and the group, class, chain, devices and zones that decided it |
| `pin_allocation` | a pin of a device connector or of a cable connector: signal, interface, wires, spare |
| `rule_results` | a limit a design rule compares a number with: actual, limit, margin, unit, verdict |
| `findings` | a finding of the design rule check, waived ones included, with actual, limit and margin when its rule has them |
| `readiness` | a check of *Ready to build* of a harness: how many items are open, which, whether it blocks |
| `mass`, `mass_wires` | a harness; a wire |
| `bom`, `bom_contributions` | a line of the bill of materials; every connector, contact, wire and accessory that adds to it |
| `test_limits` | a test of the test sheet, with its limit and test voltage |
| `parts` | a part of the library: masses, conductors, approval, ratings |
| `settings` | a setting in force: its value, unit and origin (the project, the tool's own default, or not set) |

| File | What it is |
| --- | --- |
| `configuration.json` | the files `config/*.json` as the tool used them, each with its placeholder flag |
| `provenance.json` | the tool version, the model hash, the library, the files imported (when the project records them), and the SHA-256 of every other file of the folder |
| `run_record.json` | only with `--run-record`: [section 5](#5-record-who-ran-it-and-when) |

Every JSON file starts with `format` (1), the table name, `tool_version`, `model_hash`, then `columns` (key, name, unit, header, what the column holds) and `rows`, one row to a line. The CSV file has the same rows; its first line is the headings with the unit in each, `Current (A)`, `Cross-section (mm²)`, `Resistivity (Ω·m)`. A number is written with 12 significant digits, so a sum carries no floating point noise. A value that is not set is an empty cell (`null` in the JSON), never a zero.

**The same design gives the same bytes.** No file holds a time, a user name or a path, so you can write the folder twice, keep it in Git and see in a diff exactly what a change of the design, of a configuration value or of the tool did. The gauge is the plain AWG number, as in every written file of the tool; its cross-section is the column `area_mm2`.

With `--json` the command prints the list of files instead of the line of text. From Python: `api.export_data(folder, out)`.

## 2. Read the files in a spreadsheet

Open `wire_sizing.csv` as UTF-8 text (the headings hold `²` and `Ω`). In Excel use **Data > From Text/CSV** and choose *65001: Unicode (UTF-8)*; in LibreOffice choose *Unicode (UTF-8)* in the import dialog. Then:

- Filter *Current verdict* or *Drop verdict* on `fail` to see every wire over its limit, and *Missing* to see what the project has not set.
- Sort *Voltage drop (V)* to find the worst wire; *Drop margin (V)* is the room left.
- Add your own column, for example `=Current/Derated current limit` for the load of each gauge; the inputs are all in the row.
- `rule_results.csv` filtered on *Rule* `current-over-wire` gives actual, limit and margin for every wire whether or not it failed.
- `bom_contributions.csv` as a pivot table, summed by *Part* and *Unit*, is the bill of materials `bom.csv` shows.

## 3. Read the files in a script

The JSON files hold typed rows, so a few lines of Python suffice and need no part of the tool:

```
import json
doc = json.load(open("wheel-link-data/wire_sizing.json", encoding="utf-8"))
worst = max((r for r in doc["rows"] if r["voltage_drop_v"] is not None), key=lambda r: r["voltage_drop_v"])
print(worst["wire"], worst["voltage_drop_v"], "V of", worst["max_voltage_drop_v"], "V")
```

Each column has a `key` (the name in the rows), the `name` and `unit` and a `header` that is the heading in the CSV file. A table that has no rows has `"rows": []`.

## 4. Reproduce a number from the files

A colleague who has only the folder can work the sizing out again. The script [`docs/examples/open-data/reproduce.py`](../examples/open-data/reproduce.py) does it: it imports only `csv`, `json`, `math`, `sys` and `pathlib`, reads the CSV files and `configuration.json`, and recomputes from the equations of [wire sizing](../models/wire-sizing.md):

```
python docs/examples/open-data/reproduce.py wheel-link-data
```

```
wires 103, areas 40, limits 40, gauges 40, drops 40, skipped 63, bom_lines 8
Every recomputed number agrees with the files to 9 decimals.
```

(The numbers are those of the `flatsat` example; `skipped` counts the wires that have no gauge yet.) It recomputes the cross-section of each gauge, the derated current limit (base ampacity × bundle factor K × temperature factor, with K looked up for the bundle size) and its verdict, whether the gauge is at least as large as the current needs, the voltage drop of each wire and its verdict, and the metres of every line of the bill of materials from its contributions. It prints what differs and ends with exit code 1 when something does. A test runs it on every packaged example.

By hand, for wire `W001-001` of the `flatsat` example, from one row of `wire_sizing.csv`:

| From the row | Value |
| --- | --- |
| Current, gauge, cross-section | 0.8 A, AWG 24, 0.204730 mm² (0.127 mm × 92^((36 − 24)/39) is the diameter; π/4 × d² the area) |
| Base ampacity of the gauge, K, temperature factor | 2.0 A, 0.6 (18 wires in the bundle), 0.9 |
| Derated limit | 2.0 × 0.6 × 0.9 = **1.08 A**; the wire carries 0.8 A, margin 0.28 A, verdict pass |
| Length, resistivity, conductors counted | 3.45 m, 1.7e-08 Ω·m, 2 (the way out and back) |
| Voltage drop | 0.8 × 1.7e-08 × 3.45 / (0.204730e-06) × 2 = **0.458359 V**; limit 1.0 V, margin 0.541641 V |

`harness-design-studio explain wheel-link W001-001` prints the same steps with the source of every input.

## 5. Record who ran it and when

The files above carry no time and no name, on purpose: that is what makes them comparable. A reviewer still wants to know when a set of files was made and by whom. That goes in a file of its own, **written only when you ask**, beside the files and never inside one:

```
harness-design-studio export-data wheel-link --out wheel-link-data --run-record --author "A. Engineer"
harness-design-studio export wheel-link --run-record
harness-design-studio generate wheel-link --run-record
```

`run_record.json` holds `time_utc` (to the second), `operator`, `tool_version`, `platform`, `python`, the `model_hash` of the design and `extensions` (the plug-ins in force: empty until the tool has any). It has no path. `--author` is the name; without it the tool takes the environment variable `HARNESS_AUTHOR`, then the `user.name` Git has for the project, then the user name of the system, then `unknown`. For `export` and `generate` the record is written into the `outputs` folder of the project (or the folder of `--out`); it is not listed in `manifest.json`, `verify --outputs` does not call it an unlisted file, and it is in no hash: the outputs are byte for byte the same with and without it. Run `export-data` again without `--run-record` and an old record stays where it was; its `model_hash` tells you whether it still belongs to the files.

## 6. Read a file back into the tool

Two of the files are inputs the importers know, so an export can be read again:

| File | Read by | Command |
| --- | --- | --- |
| `segment_lengths.csv` | `import-lengths` (harness, segment, length, in this order) | `harness-design-studio import-lengths DIR wheel-link-data/segment_lengths.csv --unit m` |
| `parts.csv` | `import-parts` | `harness-design-studio import-parts DIR wheel-link-data/parts.csv --approved approved --pending pending --rejected not_approved` |

`segment_lengths.csv` lists only the segments that have a length, because `import-lengths` stops on a row without one. The other files are results, not inputs: the tool does not read them. A device pinout is written and read back with `export-pinout` and `import-pinout`. [Importing outside data](../IMPORTS.md#which-export-is-read-by-which-importer) lists every pair.

## Common mistakes

- **Expecting a time or a name in the data files.** There is none, on purpose. Use `--run-record`.
- **Expecting the gauge to carry its area in the file.** The gauge column is the plain number, as in every file the tool writes. The area is its own column (`area_mm2`, `Cross-section (mm²)`).
- **Comparing a recomputed number with the CSV to the last digit.** The files hold 12 significant digits and the comparison is to 9 decimals.
- **Reading an empty cell as zero.** An empty cell is a value that is not set; `Missing` says which.
- **Opening the CSV with the wrong encoding.** The headings hold `²` and `Ω`: choose UTF-8.
- **Treating a folder written for another version of the design as current.** Compare `model_hash` in `provenance.json` with the hash `export` prints.

Next: [see what the tool assumes](see-what-the-tool-assumes.md), [script the tool](script-the-tool.md), [the models](../models/README.md), [export the outputs](export-the-outputs.md)
