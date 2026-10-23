# Plan for version 1.7.0: the feedback of the test users on version 1.6.0

This page says what the test users said, what the tool does about each point today (checked in the code of version 1.6.0), what version 1.7.0 changes and in which order. It is a plan and a record, not a promise: each milestone was a pull request with tests, and what is not built is marked.

**Status (2026-10-22): published as version 1.7.0** (tag `v1.7.0` on commit `e5d8b1e`, release workflow run 39861016560, with the Linux and Windows packages; not signed off by the owner; the record is the section *Publication of 1.7.0* in [`../../compliance/SIGNOFF.md`](../../compliance/SIGNOFF.md)). The plan was written and the owner answered the four open questions (below). The build workbook (1.7.0 milestone 1, D-169) is built and merged (pull request 102). Milestone 2 (the build data, D-170) is built (model, editor fields, outputs, `import-build-data`, the documents) and merged (pull request 103); the design is below, and *As built* after it lists where the result differs from the words of the design. Stages S1 and S2 of the simple workspace (D-171) are built and merged (pull requests 104 and 105). The owner decided on 2026-10-22 that all of this ships as one release, version 1.7.0 (the number 1.8.0 will not be used for this work): version 1.7.0 carries the workbook, the build data and stages S1 and S2 of the simple workspace, and it is published. Stage S3 was discarded by the owner (2026-10-22); stage S4 and the measurement with the testers are not built: S4 remains open and would go in a later version, and no tester has repeated the tasks with 1.7.0, so nothing here says that the tool is easier to use. The words *today* and *version 1.6.0* in the sections below describe the tool before this release.

## What the test users said

1. They did not like the harness plan PDFs. They would rather have **a clearly structured, visually understandable and actionable spreadsheet** that can be used to **produce production-quality harnesses**.
2. The tool **felt overwhelming**: too much going on, too much information; they got confused quickly and did not know what to do.

We have no notes of what exactly they tried and where they stuck. The plan below is built from what the screens and files show; the testers are asked to confirm each stage (see *How we know it worked*).

## What the tool does today (version 1.6.0)

**The files.** Each harness gets a workbook `harnesses/W001/W001.xlsx` with the sheets *Wire list, Pinouts, BOM, Mass and length, Tests, Labels* (and *About*), and the same tables as CSV. It is a data dump, not a build document: no bold header, no frozen header row, no filter, no column width, no colour, no print setup. The wire list is in ID order, not in cut order; the pinouts are one list of all pins of all connectors (162 rows for harness W001 of the flatsat example); the test sheet has no column for a measured value, a result or an initial; there is no sheet that says what is still missing before the harness can be built. The PDF drawings are written for every harness, in A3 and A4, and are the first thing the export window shows.

**What a technician needs and the model does not hold.** Strip length per wire end; which contact or terminal goes on which pin and with which tool; sleeves, heat shrink and where a label goes. (The parts library already has the categories *contact*, *backshell*, *sleeving* and *label*; no pin, wire or harness refers to such a part.) A pin has a termination (crimp or solder) and a contact size, a wire has gauge, part, colour, length, label and note.

**The screen.** The first screen of a blank sample project holds about 60 controls and several kinds of jargon: seven areas on the rail; three tabs on the left and three on the right; a project tree with eight groups (units, interfaces, harnesses, parts, interface types, configuration with eight files, imports); eight diagram buttons; a legend and a minimap; six items in the status bar ("17 values pending · 17 rules not checked"). The modes *Guided* and *Expert* only change how much the diagram shows, not the screen around it. A new user is told nothing about the order of work.

## Decisions taken with the owner (2026-10-21)

| # | Question | Answer |
| --- | --- | --- |
| 1 | What happens to the PDFs? | **The workbook is the main output; the PDF drawings stay available but are off unless asked for** (`export --drawings`, a check box in the export window). Nothing is removed. |
| 2 | What must the build sheet carry beyond today's data? | All four: **strip length per wire end; contact or terminal part and crimp tool; sleeves, heat shrink and label position; a test sheet with measured values and sign-off.** |
| 3 | How is "too much" handled? | **A simple workspace is the default, Expert stays as today.** One next step at a time, plain words, everything else shown only when asked for. |
| 4 | Order | **The workbook first, then the simple workspace in stages, with the testers checking each.** (Since 2026-10-22 everything built ships as one release, version 1.7.0.) |

These become decisions D-169 (workbook and optional PDFs), D-170 (build data fields) and D-171 (simple workspace) in [`../DECISIONS.md`](../DECISIONS.md) as each is built.

## Rules for every milestone

1. **Old projects open and behave as before.** Every new field is optional and is **not written** while it has its default value (`SparseEntity`, `OMIT_WHEN_DEFAULT`), so a project that does not use it keeps byte-identical files, the same model hash and the same outputs. The proof is `python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_1.2.0.json` (run with the drawings on, as the reference was made).
2. **New columns and sheets exist only when used** where they depend on a new field; the build workbook itself is a new file and changes no existing one.
3. **The file format stays at schema version 1.**
4. **Generation never destroys a person's choice**: strip lengths, contact parts and accessories a person entered are kept when the harnesses are generated again, and what cannot be kept is reported, as for locked wires.
5. **Released harnesses stay locked**; every edit goes through `History.execute` and `check_locks`.
6. **No engineering value is invented.** The tool sets no strip length, no contact and no tool of its own; an empty cell stays empty and is shown as *to fill in*, never as a default.
7. **Deterministic**: the same model gives the same bytes (no dates, sorted rows, a fixed zip), and the independent verifier (`core/outputs/verify.py`) learns every new file.
8. **UI changes leave every written file alone** (this applies to the simple workspace and to the screens of the workbook and the build data).

## Milestones

### 1.7.0, the build workbook

- **M1, the workbook from today's data.** A new file per harness, `harnesses/W001/W001_build.xlsx`, written with a real layout (a normal openpyxl workbook with styles; the bytes stay deterministic). Sheets, in the order a person works:
  1. **Start here**: harness, revision, status, the stamp; **what is ready and what is missing** (wires without length or gauge, pins without contact, unapproved parts), each with a count and a red or green mark; how to read the other sheets; the sign-off lines.
  2. **Cut list**: one row per wire, sorted by gauge, colour and length so that the same wire is cut together; wire ID, colour shown as a colour fill (with the colour name beside it, never alone), gauge, part, length, both ends (connector and pin), label text, and a column to tick when cut.
  3. **Connectors**: one block per connector with a heading (ID, part, mates with), then its pins in a grid: pin, signal, function, wire, termination, contact; spare pins greyed out; a tick column per step (terminate, insert, check).
  4. **Parts**: the bill of materials with quantity, unit, approval state (not approved is marked), and the same wires without length counted.
  5. **Labels**: the label text, what it labels and how many.
  6. **Test sheet**: continuity and insulation tests with expected value, limit, and empty columns for the measured value, pass/fail, initials and date.
  7. **About**: generator and model hash (as today).
  
  Every sheet has a bold header row that stays on screen, filters, sensible column widths, a print area and page setup for A4 landscape with the harness and sheet name in the footer, and conditional formatting for empty required cells. Formulas are not used: all values are computed by the program (the existing rule that text from a project is never stored as a formula stays).
  The old `W001.xlsx` and the CSV files stay as they are (they are the data, and scripts may read them). **The PDF drawings become optional**: `build_outputs(..., drawings=False)` by default, `harness-design-studio export DIR --drawings` and a check box *Include the PDF drawings* in the export window turn them on. This changes the default file set of `export`, so it is in the changelog, and `tools/output_hashes.py` and the goldens run with the drawings on. *As built:* the library function `build_outputs` keeps `drawings=True` as its default; `harness-design-studio export` and the Export window pass `drawings=False` unless `--drawings` or the check box is chosen, and an export without them into a folder that had the drawings removes them and says so.
  After M1 a **sample workbook of the flatsat example goes to the test users** before the model changes of M2 are made, so they can say what is missing or wrong.
- **M2, the build data a technician needs** (decision D-170). Optional fields:
  - `Wire.strip_a_mm`, `Wire.strip_b_mm`: strip length at each end (`LengthMm`, a person's value).
  - `Pin.contact_part`: the part (category *contact*) used on that pin; `Part.tool`: the crimp tool or setting named for a contact part (free text, a person's).
  - `Harness.accessories`: a list of `Accessory` (ID, kind *sleeving*, *heat_shrink*, *label*, *backshell* or *other*, a part, what it applies to (a connector, a wire or the harness), a position in words, a length, a quantity, a note). This covers sleeves, heat shrink, backshells and where a label goes.
  - Edit plans in `core/wires.py` and a new `core/build_data.py` (set strip length for one wire, a selection or the whole harness; set a contact for a pin, a connector or all pins of one part; add and remove an accessory), the *Edit wire* and *Connectors* tabs get the fields, the pinout import and the wire import read the new columns, `harness-design-studio` gets matching options, and the workbook shows the columns and the accessory list only when used (the *Start here* sheet lists what is still empty).
  - Generation keeps a person's values (rule 4).
- **Release 1.7.0**: version, changelog, highlights, regenerated examples and goldens, documents (user manual page *Build sheets*, the output reference, the file format, the glossary, the guide), screenshots, the output proof.

#### The design of milestone 2 (decision D-170)

Model (all optional and sparse: not written while empty, so a project that does not use them keeps byte-identical files and outputs; `core/model/physical.py`, `library.py`):

| Field | Meaning |
| --- | --- |
| `Wire.strip_a_mm`, `Wire.strip_b_mm` | insulation stripped at the From end and the To end, in mm (a person's value; 0 to 100,000 as a guard against a typing slip, not a design limit) |
| `Pin.contact_part` | the library part (category *contact*) the **cable side** uses on this pin. Like `termination` and `function` it is set on the **unit's pin** (Devices tab) and copied to the cable connector's pin by Generate; on a harness made by hand it is set on the cable connector's own pin |
| `Part.tool` | the crimp tool or its setting for a contact part (free text, a person's) |
| `Harness.accessories` | a list of `Accessory`: `id`, `kind` (*sleeving*, *heat_shrink*, *label*, *backshell*, *other*), `part_id` (a library part or none), `target` (a connector or a wire of the harness, or none for the harness), `position` (in words: "50 mm from the P1 end"), `length_mm` (one piece), `quantity` (1 to 9999), `note` |

Rules: an accessory whose target is not a connector or a wire of its harness is an integrity error (`dangling_accessory`). Generation keeps what a person entered: strip lengths of a wire it carries over (like label and note), accessories whose target still exists (and reports the ones it cannot keep), and copies `contact_part` from the unit's pin to the cable pin. A released harness is locked, accessories included (`vcs/lockview.py`, `vcs/diff.py`). Nothing is computed from these values: the tool does not check that a contact fits a pin or that a strip length is sensible.

Where the values show:

- **Tables, only when used** (so existing projects keep byte-identical tables): `wirelist.csv` gets the columns *Strip A (mm)* and *Strip B (mm)* when any wire has one; `pinouts.csv` and `box_pinouts.csv` get *Contact* when any pin has one; a new `accessories.csv` per harness when it has accessories; `bom.csv` counts the contact parts used on pins (each pin in use, one each, unit *ea*) and the accessory parts (the quantity, unit *ea*; or, when a length is given, the length times the quantity in metres, unit *m*).
- **The build workbook always shows them** (it is a new file, and an empty cell is a to-do): *Cut list* gets *Strip A (mm)* and *Strip B (mm)*; *Connectors* gets *Contact* and *Tool*; a new sheet **Accessories** between *Parts* and *Labels* (*none entered* when there are none); *Start here* gets the notes *Wires without strip lengths* and *Pins in use without a contact*.
- The independent verifier checks every new column, sheet and BOM line.

Ways to enter them: the *Edit wire* tab (strip lengths, one wire or a selection, and *All wires of this harness*), the Devices tab pin table (a *Cable contact* column and the *Fill…* bulk action) and the *Connectors* tab of a harness made by hand, a new *Accessories* tab beside them (a table with add, change, delete), the part card for *Tool*; on the command line `harness-design-studio import-build-data DIR FILE` (a CSV, TSV, JSON or XLSX table read by its column headings: *Wire* with *Strip A (mm)* and *Strip B (mm)*; or *Connector*, *Pin* and *Contact* (and *Tool* for the part); or *Harness*, *Kind*, *Part*, *Target*, *Position*, *Length (mm)*, *Quantity*, *Note*), with templates in `resources/examples/templates/`.

**As built.** The bulk action in the Devices tab is the button and context-menu entry **Cable contact…** (the column is hidden until the **Contact** toggle is on). The crimp tool is set on the part page of the Inspector (click a part of the category contact in the project tree; **Crimp tool**, **Set tool**). The notes of *Start here* are *Wires without strip lengths* (a wire that lacks either end) and *Pins in use without a contact part*; the sheet with none says `No accessories entered.` The pin contact can also be named by `import-pinout` (column *Cable contact*), and `import-build-data` refuses the contact of a pin of a generated harness. The workbook has eight sheets. User manual: [`../user-manual/enter-the-build-data.md`](../user-manual/enter-the-build-data.md).

### Stages S1 and S2 of the simple workspace, in 1.7.0 (decision D-171)

Built in stages, each one meant to be checked by the testers before the next. Stages S1 and S2 are in version 1.7.0; S4 remains open and would go in a later version:

- **S1, one next step.** On opening a project the window shows a single page *What to do next* instead of the full workbench: the next step in plain words with one primary button (*Add a device*, *Connect them*, *Generate the harnesses*, *Fix what is marked*, *Get the build sheets*), the steps done before it, and a link *Show everything* (Expert). The steps follow the facts of the project (`gui/workflow.py` already derives the Generate, Check and Release steps).
  **S1 as built.** A rail area **Next step** (first in the rail; a page of its own like Home) shows the heading *What to do next*, one card (the title, one sentence, the one primary button, and for an empty project the alternative *or make a harness by hand* with *New harness…*), the six steps with an icon and a word (*done*, *next*, *to do*, *not possible*), and the link *Show everything*. The texts are in the user manual page [Use the simple workspace](../user-manual/use-the-simple-workspace.md). The rules are a pure function (`gui/next_step.py`) of: devices, connections, harnesses (and how many were made by hand), whether the plans are current, a running job, whether the design was checked and how many checks failed, whether the files are up to date, how many harnesses are released and whether the project is read-only. The setting *Workspace: Simple or Full* is stored as `ui/workspace`; a settings file with no stored value gets Simple, a file that holds values keeps Full. The first-run tour still runs over the Next step page; its steps for hidden targets are skipped (S3, which would have reworded it, is discarded). No file, rule, command or output changed.
- **S2, fewer things on screen (built).** In the simple workspace the rail has four areas (Design, Check, Build, Revisions); the project tree, the inspector, the legend, the minimap, the status-bar counts and the diagram tool bar are closed until asked for; one panel opens at a time.
  **S2 as built.** The words of the plan differ in two points, on purpose: the rail keeps its seven areas (Home is the one left out, Next step does its job) instead of being cut to four, because the Drawings area is where a harness is edited; and the tree and the inspector open and close together with one switch (*Show panels*) instead of one panel at a time. Details: Simple starts with the tree, the Interfaces tab, the inspector and the Problems panel closed, the minimap and legend off, the status bar reduced, the diagram tool row reduced to *Select*, *Connect*, *Add device* and **More**. The layout memory is per workspace, so the Full layout is never overwritten. Open point from the build: a click or double-click on a unit or link does not open the inspector in Simple (it shows a toast with *Show panels* once per window); opening it on a click would be one line, and was held back because it would reopen the panel on the first click.
- **S3, plain words (discarded).** The owner decided on 2026-10-22 that stage S3 is discarded completely: it is not built and not planned, and no word list replaces any wording. What follows is kept as the record of what was proposed. A word list would have replaced jargon on the simple screens: *interface types*, *configuration*, *values pending*, *rules not checked*, *Placeholder*, *model hash* get a plain wording or move behind a *Details* link; every message says what to do next.
- **S4, the first project.** A blank project asks for one thing at a time (the name, the first device, its connectors), instead of the empty diagram.

The mode setting already exists (*Guided*, *Expert*; it only changes how much the diagram shows); the workspace setting (*Simple*, *Full*) is separate from it, and Simple becomes the default for a new settings file; people who already use the editor keep Full.

## How we know it worked

- After M1 the testers get the sample workbook and a task: *build harness W003 from this file alone*. We record what they ask for that is not there.
- After each stage of the simple workspace the usability kit ([`../usability/`](../usability/README.md): tasks, SUS questionnaire, `tools/usability_setup.py`, `tools/usability_summary.py`) is run with the same tasks as before the change, and the SUS score and the time to the first generated harness are compared. Nothing in this plan claims that the tool is easier to use until that result exists.

## What is not planned

- A live connection to a parts database (the tool stays offline).
- Formulas, macros or charts in the workbook.
- Removing the PDF drawings or the CSV files.
- Any engineering default for strip lengths, contacts or tools.

Next: [`AIT_FEEDBACK_PLAN.md`](AIT_FEEDBACK_PLAN.md) (the plan of 1.4.0), [`../usability/README.md`](../usability/README.md).
