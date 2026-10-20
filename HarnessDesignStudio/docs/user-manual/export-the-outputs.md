# Export the outputs

This page shows how to write the drawings and lists of a design (wire lists, pinouts, parts list, test tables, labels, block diagram) into the project's `outputs` folder, and how to check that they are current.

## Contents

- [Before you start](#before-you-start)
- [1. Export](#1-export)
- [2. What you get](#2-what-you-get)
- [3. Read a file](#3-read-a-file)
- [4. Check that the outputs are current](#4-check-that-the-outputs-are-current)
- [Common mistakes](#common-mistakes)

## Before you start

- You have a generated project ([generate harnesses](generate-harnesses.md)). Export needs at least one harness.
- Everything in `outputs/` is made from the design alone. Nothing in it is typed by hand and nothing needs editing. Change the design, export again. The `outputs` folder is always safe to delete and make again.
- Placeholder values show in the outputs: gauges say `pending` and test limits say `TBD (placeholder)` until the values exist ([fill in the engineering values](fill-in-engineering-values.md)).

## 1. Export

**In the app** (GUI, not run): press **Export…** in the top bar (or **File > Export…**, Ctrl+E). The **Export outputs** window opens. It shows the output folder, a tree of harnesses and documents, and the button **Export**. The project must be saved to a folder first (the window says so and offers **Save project…**). When it is done the window lists the files written ("38 files written to …") and the app says "38 files written to the outputs folder (design 63eb9fef79dc)." (your numbers will differ). In the list, **Open** opens the selected file, **Reveal in folder** shows it in the file manager, and selecting a drawing shows a picture of it. The export always writes the whole set. The ticks in the tree choose which files the list shows and which ones **Copy selection to folder…** copies.

**On the command line**:

```
harness-design-studio export wheel-link
```

```
38 files written to wheel-link/outputs (model 63eb9fef79dc).
```

The files are checked independently before they are written. If that check fails, nothing is written and the window shows a notice, "The independent check found n problem(s) in the outputs, so nothing was written", with the first problems, until the next export succeeds. The check compares every cell of the pinouts, BOM, test tables, labels, mass table, mating matrix, traceability, box pinouts and design rule findings with the design, the values in the YAML files, the pins and signals in the drawings, the texts of the PDFs, the sheets of the Excel workbooks and the provenance values. A workbook that cannot be built (for example because the temporary folder is full) gives a message that says why. Export is refused, in the app and on the command line, for a project that is read-only or has damaged files ("This project is read-only, so nothing was exported. Save a copy to a new folder first."); an export or generation that was started before you edited the project is dropped ("The project was edited while this ran, so the result was dropped. Please try again.").

## 2. What you get

This is the list for the practice project. The export counts 38 files; with `manifest.json` there are 39:

```
wheel-link/outputs/
  manifest.json                  tool version, model hash, a checksum of every file
  harnesses/W001/
    drawing_A3.pdf  drawing_A4.pdf  drawing_A3_s1.svg   the harness drawing
    wirelist.csv  pinouts.csv  bom.csv  mass_length.csv  tests.csv  labels.csv
    wireviz.yaml                 a WireViz-style description (best effort)
    W001.xlsx                    all tables of the harness as an Excel workbook
  harnesses/W002/ ...            the same for each further harness
  system/
    block_diagram.pdf  block_diagram.svg      the units and their links
    harness_overview.pdf  harness_overview.svg
    bom.csv  mass_length.csv  box_pinouts.csv  mating_matrix.csv  traceability.csv
    drc_report.md  drc_findings.csv  changelog.csv  revision_report.md
    export.json  provenance.json  system.xlsx
```

| File | What it is for |
| --- | --- |
| `wirelist.csv` | Every wire: signal, interface, connectors, pins, gauge, part, colour, length. |
| `pinouts.csv`, `box_pinouts.csv` | Every pin of every cable connector, and of every connector on a unit, with the wire on it and whether it is spare. |
| `bom.csv` | The bill of materials ([BOM](../GLOSSARY.md)): parts and quantities, with approval status. |
| `mass_length.csv` | Wire length and mass, and what is still unknown. Totals count only what is known. |
| `tests.csv` | A continuity test for each wire and an isolation test for each wire and shield. |
| `labels.csv` | One label for each connector and two for each wire. |
| `mating_matrix.csv` | Which cable connector mates with which unit connector, with the gender of each. |
| `traceability.csv` | Which interface is carried by which wires. |
| `drc_report.md` | The same report as `harness-design-studio drc`. |
| `changelog.csv`, `revision_report.md` | The change log and the history of each harness ([release a harness](release-a-harness.md)). |
| `export.json` | The whole model in one JSON file, for other tools. |
| `provenance.json` | Which tool version and which design made the outputs, the library, and every config file with its placeholder flag. |

Only the A3 drawing is also written as SVG; the A4 drawing is a PDF only. Full list and limits: [`OUTPUTS.md`](../OUTPUTS.md).

## 3. Read a file

Every file carries the tool version and a **model hash** (a short fingerprint of the design): CSV and YAML files start with a comment line, for example

```
# harness-design-studio 1.3.0 model 63eb9fef79dc
```

A program that reads the CSV must skip lines that start with `# `. A printed sheet can be traced to the exact design it came from by that hash.

The first rows of `harnesses/W002/pinouts.csv`:

```
Connector,Role,Mates with,Part,Pin,Signal,Interface,Wires,Spare
W002-P1,cable,PCDU1-J01,EX-MICROD-9-M,1,,,W002-001,no
W002-P1,cable,PCDU1-J01,EX-MICROD-9-M,2,,,W002-002,no
W002-P1,cable,PCDU1-J01,EX-MICROD-9-M,3,,,,yes
```

The drawing is a wiring diagram. The connectors are tables left and right, with every used pin and its signal. The wires run between them. In between, each cable has a block that lists its wires with the number of wires, the gauge ("pending" when undecided) and the length. A title block closes the sheet. Wire colours are drawn only if you set them ([set wire colours](set-wire-colours.md)); unset wires are grey. The wiring-diagram drawing is not in the 0.1.0 packages (see the [changelog](../../CHANGELOG.md)); the 0.1.0 drawing is the older wire-by-wire sheet.

The title block shows the author, checker, approver and date as "-" until the harness has been reviewed and released. Its fields come from `config/titleblock.json` ([naming and title block](naming-and-title-block.md)); `sheet` may be left out. A pin ID is drawn whole (smaller, or in a wider pin column), a connector or wire ID of up to 64 characters is drawn in a smaller font instead of being cut, and a shield keeps its end A on every sheet. The harness overview draws every pair of units that a harness joins.

Numbers in the tables and the YAML keep all their digits (a length of 1234.567 mm is written as it is); only the text on the drawings is rounded. A CSV cell that starts with `=`, `+`, `-` or `@` and is not a plain number is written with a leading `'` so a spreadsheet program does not run it as a formula (`+5V` appears as `'+5V`; `-12` stays `-12`); the guard can be undone exactly, so such a signal exports and verifies. The Excel files are written without lxml, so the same design gives identical bytes on every machine.

## 4. Check that the outputs are current

The status chip in the top bar and the header of the **Harness** tab show the state (*Up to date*, *Outputs out of date*, *Not exported*, *Outputs changed*); a banner under the top bar offers **Export…** when the files are out of date. The **Harness plans** tab of the bottom panel spells it out: "Outputs: up to date with the design.", "Outputs: out of date, the design changed after the last export.", "Outputs: not exported yet.", "Outputs: files were changed after export." On the command line:

```
harness-design-studio verify wheel-link --outputs
```

```
2 interfaces and 6 wires checked: 0 error(s)
```

After you change the design without exporting again, the same command fails (exit code 1). The first lines are:

```
error: [outputs_outdated] The model changed after the harness plans were generated. Generate again before releasing.
error: [out_stale] The outputs were made from an older version of the design.
```

It also finds files that were edited or deleted after the export (`[out_modified]`). Fix: `harness-design-studio generate wheel-link` and `harness-design-studio export wheel-link`.

## Common mistakes

- **"error: there are no harnesses to export; run `harness-design-studio generate` first."** Generate first.
- **Editing a file in `outputs/`.** The next export overwrites it, and `harness-design-studio verify --outputs` reports it as changed. Change the design instead.
- **Committing `outputs/` by accident.** The `.gitignore` the tool writes covers lock, backup and temporary files, not `outputs/`. Add `outputs/` yourself if you do not want it in Git ([use Git and CI](use-git-and-ci.md)).
- **Opening the CSV in a spreadsheet shows a first line starting with `#`.** That is the stamp. It is meant to be there.
- **`warning: [out_pdf_chars] These characters cannot be shown in the PDF ...`** A name or note holds characters outside the Windows-1252 set (for example Ω or Greek letters). The PDF prints `?`; the SVG, the CSV files and the workbook keep them. The warning names every character, and the files are written ([troubleshooting](../TROUBLESHOOTING.md)).

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

Next: [release a harness](release-a-harness.md), [set wire colours](set-wire-colours.md)
