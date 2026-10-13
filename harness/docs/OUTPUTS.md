# Outputs

`harness export DIR` (or **Export outputs** in the Harness plans tab) writes everything below into `DIR/outputs/`. The files are produced from the model only: the same model gives the same bytes. Nothing in them is typed in by hand; edit the model and export again.

```
outputs/
  manifest.json                    format, generator version, model hash, placeholder config, sha256 and size of every file
  harnesses/<ID>/
    drawing_A3_s<n>.svg            harness drawing, one SVG per A3 sheet
    drawing_A3.pdf, drawing_A4.pdf vector PDF, multi-sheet, same content
    wirelist.csv  pinouts.csv  bom.csv  mass_length.csv  tests.csv  labels.csv
    wireviz.yaml                   WireViz-style input (best effort, see below)
    <ID>.xlsx                      all tables of the harness as sheets
  system/
    block_diagram.svg|pdf          units in zone lanes, interfaces coloured by category
    harness_overview.svg|pdf       harnesses between units, solid = nominal, dashed = redundant
    bom.csv  mass_length.csv  mating_matrix.csv  traceability.csv  box_pinouts.csv
    changelog.csv  revision_report.md   change log and per-harness history with differences between revisions
    drc_findings.csv  drc_report.md
    export.json                    the whole model in one documented JSON file
    provenance.json                which tool version, library and configuration made the outputs (see Provenance)
    system.xlsx                    BOM, mass and length, matrices, box pinouts, DRC findings
```

## Stamps
Every file carries `harness-design-studio <version> model <first 12 hex of the model hash>`: CSV and YAML as a first comment line (`# ...`), SVG in `<desc>`, PDF in the Subject, Markdown as the first line, XLSX on the About sheet, JSON as `model_hash`. CSV readers must skip lines that start with `# `. Cells that start with `= + - @`, a tab or a carriage return and are not plain numbers are written with a leading `'` so spreadsheet programs do not run them as formulas (`+5V` is written `'+5V`, `-12` stays `-12`). The guard can be undone exactly: a cell that already starts with `'` followed by such a character gets one more `'`, and a reader removes exactly one. The XLSX files hold the text as it is (no `'`), stored as text, and are written without lxml (`OPENPYXL_LXML` is forced off before openpyxl is imported), so they are identical with or without lxml installed.

## Stale detection
`manifest.json` stores the model hash. The editor compares it with the current model (quick check) and shows "up to date", "out of date" or "not exported". `harness verify DIR --outputs` also hashes every file (detects edited or missing files) and re-checks content against the design.

## Verifier v2 (`core/outputs/verify.py`)
Re-reads the finished files and compares them with the model without using the builders: wire list against wires (missing, duplicated, extra, different ends, gauge or length), pinouts, BOM quantities and wire lengths, one continuity test per wire and one isolation test per wire and shield, every cell of the pinouts, box pinouts, BOM (category, approval, wires without length, used in), tests (limits, test voltage, wires), labels, mass and length (missing data, totals), mating matrix, traceability and DRC findings, the values in the WireViz files (pins, gauge, colour, length, connections), all sheets of the XLSX files against the CSV files, the drawing text (every pin number and signal of the SVG, wire and connector IDs, sheet numbers; the PDFs against the SVGs), JSON export, provenance values, diagram contents, stamps and manifest. A warning (not an error) names the characters a PDF cannot show (below). `harness export` and the editor refuse to write outputs that fail it.

## Drawing
A wiring diagram: the connectors are tables on the left and the right (name, part, gender in words, pin count, the mating box connector, and for every used pin its number and signal), the wires run between them as curves in their wire colour, and between the connectors each cable (the wires of one connector pair) has a block that lists its wires (ID and IEC 60757 colour code) with the number of wires, gauge ("pending" when undecided) and length. Wires whose colour is not set are grey; a two-colour wire written `yellow/green` (or `green-yellow`) shows both codes (`YE/GN`) and is drawn grey; the colour comes from the wire (set by hand) or from the optional `wire_colour_by_signal` entry of `generation.json`, and the tool defines none. Wires are drawn on a dark outline and carry their colour code as text, so a greyscale print loses nothing. Shields are drawn as sleeves: the wires of a shield sit together in the cable block under a grey jacket that carries the shield's ID and kind and shows how each end is terminated (a solid bar for a 360 degree backshell connection, a lead for a pigtail, a cross for a floating end). Routing segments, spare pins and notes follow beneath, and the shields are also listed there. A title block closes every sheet (project, harness, title, revision, status, sheet n / N, stamp). Long harnesses continue on further sheets; a cable block that continues is marked "(continued)". The first sheet starts with a routing sketch (connectors and branch points as boxes, segments with lengths; schematic, not to scale; omitted above 14 nodes). Limits: the drawing is a wire-by-wire diagram plus this sketch, not a geometric layout of the branches. Author, checker, approver and date come from the harness (set by review and release, see change control); they show "-" until then. The title block field list comes from `config/titleblock.json` (placeholder, D-15): field names must be known (`project`, `harness_id`, `title`, `revision`, `date`, `author`, `checker`, `approver`, `sheet`, `status`), each at most once and written as text; anything else is a configuration error and the default fields are drawn. Any field may be left out, `sheet` too (the output check then does not look for the sheet number). A shield's end A is the start of its wire with the lowest ID in the whole harness, so the ends do not change sides between sheets. Pin IDs longer than about 12 characters are drawn smaller (down to 1.4 mm) and the pin column of that connector grows, so a pin ID is never cut. In the SVG every pin number and pin signal text carries a `data-ref` attribute (`pin/<connector>/<pin>`, `sig/<connector>/<pin>`) for the output check. PDF text is Windows-1252: characters outside it (for example the ohm sign or Greek letters) appear as `?` in the PDF while the SVG shows them; the export check lists them as a warning (`out_pdf_chars`). The harness overview draws one line for every pair of units that a harness joins.

## Tables
Numbers in the tables and in the YAML keep all their digits (the shortest text that reads back as the same value, no exponent; totals are rounded to 9 decimals so sums show no floating point noise). Only the text on the drawings is rounded (6 significant digits). Rows that share a key are in ID order whatever order the harnesses were created in (wire IDs in the pinouts are sorted, mating rows are ordered by connector and harness), so equal designs give equal bytes. A long ID is drawn in a smaller font instead of being cut (down to 1.4 mm for the 64 characters the model allows).

- `wirelist.csv`: Wire, Signal, Interface, From connector/pin, To connector/pin, AWG ("pending" when undecided), Part, Colour, Length (m), Shield group, Locked.
- `pinouts.csv` / `box_pinouts.csv`: every pin of every cable / box connector, wires attached, spare flag.
- `bom.csv`: connector parts by count, wire parts by metres known (plus the number of wires without length), approval status.
- `mass_length.csv`: known wire length, mass of wires and cable connectors, margin, whether the data is complete, what is missing. Totals count only what is known and say so. Backshells, shielding, sleeving and tie-downs are not in the mass (the tool has no mass data for them); "Complete" refers to the wires and cable connectors only.
- `tests.csv`: continuity per wire, isolation per wire (against all others and shields) and per shield. Limits come from `generation.test_*` and read "TBD (placeholder)" until set.
- `labels.csv`: one label per connector, two per wire (one per end).
- `mating_matrix.csv`, `traceability.csv`: box connector to cable connector; interface to harness and wires.

## WireViz YAML
Each wire is written as its own one-conductor cable, with `connectors`, `cables` and `connections` in the structure WireViz reads. It is written from the model by this tool and has not been validated against the WireViz program (outside this clean-room project). Treat it as a convenience export.

## JSON export (`system/export.json`)
```
{ "format": "harness-design-studio-export", "format_version": 1,
  "generator": {"name", "version"}, "model_hash": "<64 hex>",
  "project": {"name", "description"}, "placeholder_config": [names],
  "units": [...], "interface_types": [...], "interfaces": [...],
  "box_connectors": [...], "harnesses": [...], "parts": [...] }
```
Each list holds the model objects exactly as in the project files (sorted by ID); fields are described in `FILE_FORMAT.md`. `format_version` changes only for incompatible changes.

## Print
Dark colours and dash patterns carry every distinction (category, nominal/redundant), so greyscale prints stay readable. Tests check contrast against white (at least 3:1) for the system diagrams. Harness drawings draw wire colours on a dark outline and write every colour as a code (REQ-OUT-03).

## Change control in the outputs
`system/changelog.csv` lists every change log entry. `system/revision_report.md` gives, per harness, the history and the differences between consecutive baselines and between the working design and the latest baseline. The manifest also stores `content_hash` (model hash without release bookkeeping) which the release gate compares; see DECISIONS D-104.

## EMC class on wires and labels

When at least one interface type has an EMC class, the wire list gets a last column `EMC class` and the wire labels end with `[EMC <class>]`, so personnel can see the category of every wire (ECSS-E-ST-20-07C 4.2.13.1 d). Projects without EMC classes get byte-identical files. The output verifier checks the column against the design.

## Provenance

`system/provenance.json` states which tool version and which design made the outputs: the model hash, the project name, the parts library (name, version, number of parts by approval status), every configuration file with its placeholder flag and a short hash of its values, and the counts of units, interfaces, harnesses and wires. There are no dates and no paths, so equal designs give equal bytes. The output verifier checks the placeholder flags and counts against the design. The WireViz-style YAML files are an export format only; WireViz is not used to make any output.

## Requirement IDs on findings

`system/drc_findings.csv` ends with a column `Requirement`: the IDs of the standard requirements the rule serves (empty when the rule serves none). The Problems panel shows the same IDs under the explanation of a finding, and the design rule report prints them after it. The IDs are those of `compliance/requirements` in the tool's repository (`docs/RULES.md` lists them per rule).

Next: [export the outputs (user manual)](user-manual/export-the-outputs.md), [`FILE_FORMAT.md`](FILE_FORMAT.md).
