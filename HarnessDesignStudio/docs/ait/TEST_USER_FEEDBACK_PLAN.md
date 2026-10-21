# Plan for versions 1.7.0 and 1.8.0: the feedback of the test users on version 1.6.0

This page says what the test users said, what the tool does about each point today (checked in the code of version 1.6.0), what the next versions change and in which order. It is a plan and a record, not a promise: each milestone is a pull request with tests, and what is not built yet is marked.

**Status (2026-10-21).** The plan is written and the owner has answered the four open questions (below). Nothing is built yet.

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
| 4 | Order | **The workbook first (1.7.0), then the simple workspace in stages (1.8.0), with the testers checking each.** |

These become decisions D-169 (workbook and optional PDFs), D-170 (build data fields) and D-171 (simple workspace) in [`../DECISIONS.md`](../DECISIONS.md) as each is built.

## Rules for every milestone

1. **Old projects open and behave as before.** Every new field is optional and is **not written** while it has its default value (`SparseEntity`, `OMIT_WHEN_DEFAULT`), so a project that does not use it keeps byte-identical files, the same model hash and the same outputs. The proof is `python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_1.2.0.json` (run with the drawings on, as the reference was made).
2. **New columns and sheets exist only when used** where they depend on a new field; the build workbook itself is a new file and changes no existing one.
3. **The file format stays at schema version 1.**
4. **Generation never destroys a person's choice**: strip lengths, contact parts and accessories a person entered are kept when the harnesses are generated again, and what cannot be kept is reported, as for locked wires.
5. **Released harnesses stay locked**; every edit goes through `History.execute` and `check_locks`.
6. **No engineering value is invented.** The tool sets no strip length, no contact and no tool of its own; an empty cell stays empty and is shown as *to fill in*, never as a default.
7. **Deterministic**: the same model gives the same bytes (no dates, sorted rows, a fixed zip), and the independent verifier (`core/outputs/verify.py`) learns every new file.
8. **UI changes leave every written file alone** (this applies to 1.8.0 and to the screens of 1.7.0).

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
  The old `W001.xlsx` and the CSV files stay as they are (they are the data, and scripts may read them). **The PDF drawings become optional**: `build_outputs(..., drawings=False)` by default, `harness-design-studio export DIR --drawings` and a check box *Include the PDF drawings* in the export window turn them on. This changes the default file set of `export`, so it is in the changelog, and `tools/output_hashes.py` and the goldens run with the drawings on.
  After M1 a **sample workbook of the flatsat example goes to the test users** before the model changes of M2 are made, so they can say what is missing or wrong.
- **M2, the build data a technician needs** (decision D-170). Optional fields:
  - `Wire.strip_a_mm`, `Wire.strip_b_mm`: strip length at each end (`LengthMm`, a person's value).
  - `Pin.contact_part`: the part (category *contact*) used on that pin; `Part.tool`: the crimp tool or setting named for a contact part (free text, a person's).
  - `Harness.accessories`: a list of `Accessory` (ID, kind *sleeving*, *heat_shrink*, *label*, *backshell* or *other*, a part, what it applies to (a connector, a wire or the harness), a position in words, a length, a quantity, a note). This covers sleeves, heat shrink, backshells and where a label goes.
  - Edit plans in `core/wires.py` and a new `core/build_data.py` (set strip length for one wire, a selection or the whole harness; set a contact for a pin, a connector or all pins of one part; add and remove an accessory), the *Edit wire* and *Connectors* tabs get the fields, the pinout import and the wire import read the new columns, `harness-design-studio` gets matching options, and the workbook shows the columns and the accessory list only when used (the *Start here* sheet lists what is still empty).
  - Generation keeps a person's values (rule 4).
- **Release 1.7.0**: version, changelog, highlights, regenerated examples and goldens, documents (user manual page *Build sheets*, the output reference, the file format, the glossary, the guide), screenshots, the output proof.

### 1.8.0, the simple workspace (decision D-171)

Built in stages, each one checked by the testers before the next:

- **S1, one next step.** On opening a project the window shows a single page *What to do next* instead of the full workbench: the next step in plain words with one primary button (*Add a device*, *Connect them*, *Generate the harnesses*, *Fix what is marked*, *Get the build sheets*), the steps done before it, and a link *Show everything* (Expert). The steps follow the facts of the project (`gui/workflow.py` already derives the Generate, Check and Release steps).
- **S2, fewer things on screen.** In the simple workspace the rail has four areas (Design, Check, Build, Revisions); the project tree, the inspector, the legend, the minimap, the status-bar counts and the diagram tool bar are closed until asked for; one panel opens at a time.
- **S3, plain words.** A word list replaces jargon on the simple screens: *interface types*, *configuration*, *values pending*, *rules not checked*, *Placeholder*, *model hash* get a plain wording or move behind a *Details* link; every message says what to do next.
- **S4, the first project.** A blank project asks for one thing at a time (the name, the first device, its connectors), instead of the empty diagram.

The mode setting already exists (*Guided*, *Expert*); the simple workspace is a third state that becomes the default for a new settings file; people who already chose Expert keep it.

## How we know it worked

- After M1 the testers get the sample workbook and a task: *build harness W003 from this file alone*. We record what they ask for that is not there.
- After each stage of 1.8.0 the usability kit ([`../usability/`](../usability/README.md): tasks, SUS questionnaire, `tools/usability_setup.py`, `tools/usability_summary.py`) is run with the same tasks as before the change, and the SUS score and the time to the first generated harness are compared. Nothing in this plan claims that the tool is easier to use until that result exists.

## What is not planned

- A live connection to a parts database (the tool stays offline).
- Formulas, macros or charts in the workbook.
- Removing the PDF drawings or the CSV files.
- Any engineering default for strip lengths, contacts or tools.

Next: [`AIT_FEEDBACK_PLAN.md`](AIT_FEEDBACK_PLAN.md) (the plan of 1.4.0), [`../usability/README.md`](../usability/README.md).
