# Transparency audit, appendix D: written outputs

This page is appendix D of the [transparency audit](../transparency_audit.md): the row-level catalogue for the tables, the build workbook, the labels, the test sheet and the provenance the tool writes. Each row names the file and line the reviewer opened. IDs read `OUT-C<category>-<number>`; the categories and the tags `[SYS]`, `[ELEC]` and `[AIT]` are explained in section 1 of the audit. Paths beginning with `work/` are scratch projects the reviewer made while auditing; they are not in the repository. Nothing on this page was changed in the code: it is read-only.

## Contents

- [C1 Hard-coded constants, defaults, margins, thresholds, rules](#c1-hard-coded-constants-defaults-margins-thresholds-rules)
- [C2 Hidden assumptions](#c2-hidden-assumptions)
- [C3 Outputs shown without a visible derivation](#c3-outputs-shown-without-a-visible-derivation)
- [C4 Forced choices (no alternative selectable)](#c4-forced-choices-no-alternative-selectable)
- [C5 Inputs and outputs exchanged with other tools or files (explicit and implicit)](#c5-inputs-and-outputs-exchanged-with-other-tools-or-files-explicit-and-implicit)
- [C6 Customisation points that DO exist](#c6-customisation-points-that-do-exist)
- [AIT lens: the AIT engineer's working outputs](#ait-lens-the-ait-engineers-working-outputs)
- [Electrical lens: outputs](#electrical-lens-outputs)
- [Top findings](#top-findings)

**Scope.** Read in full: core/outputs/build.py (365), buildsheet.py (722), canvas.py (263), connections.py (144), drawing.py (788), errors.py (7), exports.py (173), provenance.py (58), stamp.py (69), system.py (212), tables.py (542), verify.py (1916), xlsx_env.py (31); core/build_data.py (371), core/build_data_import.py (359). Read for context (partial): generate/lengths.py, generate/mass.py, io/layout.py (model_hash), vcs/hashing.py, vcs/report.py (changelog_rows), configcheck.py (titleblock_fields), wirecolours.py (resolve), drc/report.py (render_markdown head), engine.py 650-690. Not read: links.py (`derived_interfaces`, `effective_role`), imports.py, drc rules. Observed with the CLI on a scratch copy of the small-satellite example (new, generate, export; 232 files).

Persona tags: [SYS] systems engineer, [ELEC] electrical engineer, [AIT] assembly/integration/test engineer.

Short answer on the special questions:
- **Stamp** = `harness-design-studio <version> model <12 hex of SHA-256 of the serialised model>` (stamp.py:22-25). No timestamp, no user, no configuration values, no input-file hash. It is on CSV line 1, YAML line 1, MD line 1, SVG `<desc>`, PDF /Subject, xlsx About sheet and print footer, and in the `model_hash` key of the JSON files.
- **provenance.json** (provenance.py:25-58) = tool version, full model hash, project name, library name/version/source/date/part counts by approval, for each config file only `placeholder` flag and a 16-hex truncated hash of its values, and design counts. No config values, no timestamp, no operator, no list of imported files. manifest.json adds `content_hash`, `placeholder_config` and per-file SHA-256 (build.py:39-52).
- **Verifier** (verify.py) re-reads the written bytes and re-derives each cell from the model by a second implementation of the same rules (it does not import the table builders). It proves the files are consistent with the model and the documented rules. It does not test any engineering rule, and it copies the same constants/assumptions (e.g. `length / conductors`, `total * margin`). Some cells (connection Type/Interface, Carries) are only checked for plausibility and then "taken as written" (verify.py:1240-1244, 1376-1378, 1404-1406).
- **Overrides**: no exported value is marked as overridden or manually edited. Only `Locked` (wirelist col 13), `(example data)` on unverified parts, `TBD (placeholder)` and the placeholder lines are flags.

---

## C1 Hard-coded constants, defaults, margins, thresholds, rules

Columns: id | file:line | value or rule | what it does / feeds | unit | visible to user (where) | editable (key/UI) | R | persona

| id | file:line | value / rule | effect | unit | visible? | editable? | R | persona |
|---|---|---|---|---|---|---|---|---|
| OUT-C1-001 | tables.py:25-26 | `PENDING = "pending"`, `TBD = "TBD (placeholder)"` | Text written where a gauge or a test limit is unset | text | yes, in cells | none | R3,R12 | SYS ELEC AIT |
| OUT-C1-002 | tables.py:34-44 | `round(v, 9)`, shortest repr, no exponent, `.0` stripped | Every number in CSV/XLSX/YAML (length, mass, strip, metres) | as column | no (docs only) | none | R5 | SYS ELEC AIT |
| OUT-C1-003 | tables.py:29-31 | `f"{v:.6g}"` 6 significant digits | Lengths/segment lengths printed on drawings; differs from CSV precision | m | no | none | R5 | SYS AIT |
| OUT-C1-004 | tables.py:116-118 | Wire list header incl. `"AWG"`, `"Length (m)"`; EMC/Requirement/Label+Note/Strip columns appear only if the project uses them | Fixes gauge system (AWG only) and length unit (m); column set varies by project | AWG, m | headers yes | none | R3,R5 | ELEC AIT |
| OUT-C1-005 | tables.py:125 | gauge unset -> `"pending"` | Wire list AWG cell | AWG | yes | gauge per wire | R7 | ELEC AIT |
| OUT-C1-006 | tables.py:184 | Spare = `"no" if wires or p.interface_id or p.signal else "yes"` | Pinout "Spare" column definition | flag | no | none | R1 | ELEC AIT |
| OUT-C1-007 | tables.py:296-301 | One contact per pin that has a contact part AND a wire; connectors counted 1 per cable connector | BOM `ea` quantities; no spares/overage | ea | no | none | R1,R3 | AIT |
| OUT-C1-008 | tables.py:311 | `metres[pid] += length / part.conductors` (1 if part unknown) | BOM metres of wire parts; multi-conductor part counts cable metres | m | partly (docstring, D-188) | `Part.conductors` | R1,R5 | AIT SYS |
| OUT-C1-009 | tables.py:319 | `length_mm * quantity / 1000` | BOM metres for sleeving/heat shrink accessories | m | no | accessory fields | R1,R5 | AIT |
| OUT-C1-010 | tables.py:303,329 | `"(no part)"`; `"missing from parts list"`; `+ " (example data)"` if `unverified` | BOM line identity and Approval text | text | yes | part library | R7,R12 | SYS AIT |
| OUT-C1-011 | tables.py:323 | BOM lines sorted by (part, unit) `ea` before `m` | Order of BOM rows | - | no | none | R3 | AIT |
| OUT-C1-012 | tables.py:366-372; mass.py:37 | wire mass = `mass_per_m_g * length / conductors`; connector mass = `mass_g` per cable connector; contacts, backshells, sleeving, accessories, shields NOT included | Mass columns of mass_length.csv; header says "wires and cable connectors" | g | header only | part mass fields | R1 | SYS |
| OUT-C1-013 | mass.py:41-46; tables.py:380 | `margin_g = total_g * mass_margin_fraction` (config `generation.mass_margin_fraction`); system margin = sum of harness margins, blank if any blank | Margin and "Mass with margin" | g, fraction | placeholder status only | config generation.json key | R3,R4 | SYS |
| OUT-C1-014 | tables.py:370; mass.py:19 | Mass is written as `0` (not blank) when nothing is known; `Complete=no` | Total mass cell for incomplete data | g | Complete + Missing data columns | none | R12 | SYS |
| OUT-C1-015 | tables.py:395-403 | Limit text `f"{v:g} ohm max"`, `"Mohm min"`, `"V"` from config keys `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v`; else TBD | Test-table Limit and Test voltage; one global value for all wires | ohm, Mohm, V | yes (tests.csv, Tests sheet) | config generation.json | R3,R5 | AIT ELEC |
| OUT-C1-016 | tables.py:406-414 | Tests generated: 1 continuity per wire, 1 isolation per wire vs "all other wires and shields", 1 per shield vs "all wires"; IDs `T{n:03d}`; Expected `"continuous"`/`"isolated"` | The whole test plan; no method, current, dwell, instrument | text | yes | none | R4,R7 | AIT |
| OUT-C1-017 | tables.py:419-435 | Labels: 1 harness label (if set), 1 per connector, 2 per wire (`-A`, `-B`); Quantity always `"1"`; text `"<id> <label or signal> to <far end>"`; ` [EMC x]` suffix | Label print list | text, ea | yes | label/signal text fields only | R3 | AIT ELEC |
| OUT-C1-018 | tables.py:55-59 | EMC class = `emc_class` of the interface type of the wire's interface | Wire list EMC column, label suffix | class | yes | interface type data | R1 | ELEC AIT |
| OUT-C1-019 | tables.py:514-542 | "Routed" = `yes` if >=1 wire carries the interface | Traceability matrix | flag | yes | none | R1,R12 | SYS |
| OUT-C1-020 | buildsheet.py:255-266 | Cut order key: gauge known first, AWG ascending (thick first), colour name lower-case alphabetical (`"~"` if none), length known first, length ascending, wire ID | Cut-list order | - | no | none | R3,R4 | AIT |
| OUT-C1-021 | buildsheet.py:297-332 | 8 readiness checks; blocking = length, gauge, colour, part; non-blocking = termination, strip lengths, contact part, approval | "Start here" table, status OK/TO FIX/NOTE | count | yes (sheet) | none | R3,R12 | AIT SYS |
| OUT-C1-022 | buildsheet.py:358-359; verify.py:1758 | `ready = "yes" if blocking == 0`; blocking = first four checks only; DRC errors, review/release status, test limits, strip lengths not considered | "Ready to build" answer | yes/no | yes, text under it | none | R1,R12 | AIT SYS |
| OUT-C1-023 | buildsheet.py:338-343 | `"yes (values rest on placeholder configuration: ...)"` | Ready answer qualifier | text | yes | config `placeholder` flag | R12 | AIT ELEC |
| OUT-C1-024 | buildsheet.py:55-58 | `"to fill in"`, `"TO FIX"`, `"NOTE"`, `"OK"` | Missing-value markers in build workbook (amber) | text | yes | none | R7 | AIT |
| OUT-C1-025 | buildsheet.py:412-414 | Sign-off steps fixed: Cut and stripped, Terminated, Assembled and labelled, Tested, Released for delivery | Hand sign-off block (Step/Name/Date/Signature) | - | yes | none | R8 | AIT |
| OUT-C1-026 | buildsheet.py:664 | Test result list `"Pass,Fail"`; "Measured" is free text | Tests sheet entry | - | yes | none | R7,R12 | AIT |
| OUT-C1-027 | buildsheet.py:424-426,443,464 | `round(v, 9) + 0.0`; cut total = plain sum of all lengths | Cut list numbers and total (full length per conductor row) | m, mm | yes | none | R5 | AIT |
| OUT-C1-028 | buildsheet.py:544 | Page break when a connector block would pass 42 rows | Connector sheet printing | rows | no | none | - | AIT |
| OUT-C1-029 | buildsheet.py:60-63,218-221 | Layout colours, A4 landscape, margins 0.4/0.6/0.8 in, widths cap 46 (cosmetic, grouped) | Workbook look/print | - | no | none | - | AIT |
| OUT-C1-030 | buildsheet.py:45,53 | `HARNESS_TARGET = "(harness)"`; check header texts | Accessory with no target | text | yes | none | - | AIT |
| OUT-C1-031 | exports.py:42-43,48 | YAML `gauge: "<n> AWG"`, `length: <number>` without a unit | WireViz export; unit of length implied | AWG, m? (unverified in WireViz) | no | none | R5,R14 | SYS AIT |
| OUT-C1-032 | exports.py:101-102,128-130,166-171 | Workbook created/modified pinned to 2000-01-01; zip entries 1980-01-01; creator `harness-design-studio` | File properties show a false date | date | yes in file properties | none | R9 | SYS |
| OUT-C1-033 | exports.py:137; stamp.py:34-46 | Cells starting `= + - @ TAB CR` get leading `'` in CSV, text type in XLSX | CSV text differs from model text; plain numbers exempt | text | no | none | R10,R14 | SYS AIT |
| OUT-C1-034 | exports.py:19-20; build.py:25-26; provenance.py:16-17 | `JSON_VERSION=1`, manifest `FORMAT_VERSION=1`, provenance `FORMAT_VERSION=1` | Schema versions of export.json/manifest/provenance | - | in files | none | R9,R14 | SYS |
| OUT-C1-035 | stamp.py:20-25 | `short = model_hash[:12]`; line = `harness-design-studio <ver> model <12 hex>` | Stamp on every file | hash | yes | none | R9 | SYS ELEC AIT |
| OUT-C1-036 | provenance.py:20-22 | Config values hashed `sha256(json)[:16]` | `settings.<name>.values_sha256_16` | hash | yes | none | R9 | SYS ELEC |
| OUT-C1-037 | build.py:108,60-64 | Drawing sizes default `("A4","A3")`; SVG only for A3 (`drawing_A3_sN.svg`) | Which drawings are written | - | CLI `--drawings` only | function arg | R3 | AIT SYS |
| OUT-C1-038 | build.py:27,122-125,149,172 | Output folder `outputs`; harnesses by ID order; accessories file only if accessories; connections files only if links | Output set structure | - | docs | none | R3 | SYS |
| OUT-C1-039 | canvas.py:16-17 | `CHAR_EM=0.6` (Courier), `SHEETS = A4 297x210, A3 420x297` mm | Text width and sheet sizes of all drawings | mm | no | none | R3 | SYS AIT |
| OUT-C1-040 | canvas.py:24-27,172 | `fit()` truncates with `~`; PDF text encoded `cp1252, "replace"` (other chars become `?`) | Long signals/labels cut on drawings; non-Latin text lost in PDF | chars | verify warning only | none | R12 | AIT SYS |
| OUT-C1-041 | drawing.py:34,41-43,680 | `SKETCH_MAX_NODES = 14`; routing sketch omitted if more nodes or taller than half the page | Routing sketch (with segment lengths) disappears silently | nodes | no | none | R4,R12 | AIT SYS |
| OUT-C1-042 | drawing.py:643,41 | Title block `date` = `h.released_on or "-"` (not export date); fields from `titleblock.fields` else default `project, harness_id, title, revision, status, sheet` (configcheck.py:280,437) | Drawing title block | date | yes | config titleblock.json | R3,R9 | SYS AIT |
| OUT-C1-043 | drawing.py:317-325 | Cable block summary: `AWG mixed`, `lengths vary`, `length n/a`, `AWG ?`->`pending` | Cable block text | AWG, m | yes | none | R12 | AIT ELEC |
| OUT-C1-044 | drawing.py:354-356,385-392 | Shield end A = end of the shield's wire with lowest ID, side chosen by that wire's from-connector | Which shield end is drawn left/right (end_a/end_b) | - | no | none | R1 | ELEC AIT |
| OUT-C1-045 | drawing.py:121-135,586-588 | Connector side (left/right) by propagation from the first sorted pair; a wire's From end may be drawn on the right | Layout of every drawing | - | no | none | R6 | AIT |
| OUT-C1-046 | drawing.py:27-30,72-87 | Layout constants MARGIN 8, TB 190x42, CONN_W 58, BOX_W 96, ROW 4.2, MAX_WIRE_RUN 45, text sizes (cosmetic, grouped) | Drawing geometry | mm | no | none | - | AIT |
| OUT-C1-047 | drawing.py:280-282 | `textwrap.wrap(..., 150)` of the notes/extras lines | Notes under drawing wrapped at 150 chars | chars | no | none | - | AIT |
| OUT-C1-048 | system.py:14-27,61 | `CATEGORY_STYLE` colours/dashes, redundant dash (2.5,1.5), BOX_W 44, LANE_W 70 (cosmetic, grouped) | System diagrams | - | legend | none | - | SYS |
| OUT-C1-049 | system.py:137-141 | Edge style of a connection = category of the interface type with most pairs; no type -> "other" | Block diagram line style | - | no | none | R1 | SYS |
| OUT-C1-050 | system.py:184-202 | Harness overview: a harness draws a line between every pair of its units; redundant if any wire's interface is redundant | Overview diagram | - | no | none | R1 | SYS |
| OUT-C1-051 | connections.py:30-37 | Fixed connection list columns | connections.csv/xlsx | - | yes | none | R3 | SYS ELEC |
| OUT-C1-052 | verify.py:1300-1305 (verifier copy of role rule) | Pin role: given role, else signal `RTN`->return, `GND`->ground, else interface category power/ground, else `signal` | "From/To role" in connection list (builder rule lives in links.py, not read) | text | role column | `Pin.role` per pin | R1,R4 | ELEC SYS |
| OUT-C1-053 | verify.py:353-357,242 | Verifier tolerance 1e-5 relative, 1e-9 absolute | What counts as "equal" | - | no | none | R3 | SYS |
| OUT-C1-054 | build_data.py:39; model/base.py:108 (line seen via grep) | `MAX_QUANTITY = 9999`; `MAX_LENGTH_MM = 100000` (accessory length, strip) | Input guard on build data | ea, mm | error text | none | R3 | AIT |
| OUT-C1-055 | build_data.py:104-123 | Strip/length accepts `,` as decimal, range 0..100000 mm; "not a design limit" | Strip length entry | mm | error text | none | R5 | AIT |
| OUT-C1-056 | build_data.py:270-276 | Accessory IDs `ACC-001...` first free | Accessory ID scheme | - | yes | ID editable | - | AIT |
| OUT-C1-057 | build_data_import.py:171,176-181 | If any row is refused, no ops at all (all-or-nothing); empty cell never clears | Import behaviour | - | row messages | none | R7,R14 | AIT |
| OUT-C1-058 | build_data_import.py:35-64,71 | Heading aliases (`stripa`, `qty`, `crimptool`...); first kind whose needs are met wins (order strips, contacts, accessories, tools) | Which kind a table is detected as | - | error text lists expected headings | none | R14 | AIT |
| OUT-C1-059 | build_data_import.py:300 | Accessory kind normalised `casefold`, spaces/hyphens -> `_`; quantity default 1 (line 307) | Silent default fill on import | - | no | none | R7 | AIT |
| OUT-C1-060 | lengths.py:37-51,86-100 | Wire length = own `length_m`, else sum of segments on the unique tree path; second route -> None; no service loop, strip or cut allowance added here | Every "Length (m)" in all outputs | m | no | segment/wire lengths | R1,R4 | AIT ELEC |
| OUT-C1-061 | lengths.py:118,163-164 | `MAX_LENGTH_M = 10_000`; segment-length import rejects larger | Input guard | m | error text | none | R3 | AIT |
| OUT-C1-062 | lengths.py:77 | Path cache limit 512 | Performance only | - | no | none | - | - |

62 rows.

---

## C2 Hidden assumptions

| id | file:line | assumption (what is implicit and why it matters) | R | persona |
|---|---|---|---|---|
| OUT-C2-001 | tables.py:126; lengths.py:86-100 | "Length (m)" does not say whether it includes service loop, strip length, cut allowance or routing slack. The service loop (config `service_loop_m`) is applied at generation (engine.py:661-662, not in outputs) and the result is stored as the wire's `length_m`; the output cannot tell a generated, imported, hand-typed or segment-derived length apart. | R1,R5,R7 | AIT ELEC |
| OUT-C2-002 | lengths.py:37-51 | A wire whose path has two possible routes gets no length (blank / "to fill in") with no reason in the output; only the DRC rule `segment-loop` explains. | R12 | AIT |
| OUT-C2-003 | tables.py:311; buildsheet.py:437-443 | Cut list shows each conductor wire at full length L; BOM divides by `conductors` (cable metres). For a 2-conductor part the cut list shows 2 rows x L while the BOM shows L. Nowhere stated in the cell or header; the cut total (buildsheet.py:464) sums all rows. | R1,R5 | AIT |
| OUT-C2-004 | tables.py:296-301 | BOM has no wire waste, no connector/contact spares, no cut allowance; metres are net harness length. Unknown-length wires are left out of metres and only counted in "Wires without length". | R3,R4 | AIT |
| OUT-C2-005 | mass.py:30-37 | Mass = cable connectors + wires only; excludes contacts, backshells, sleeving, accessories, labels, shield braids. Header says so, but system totals read as harness mass. | R1 | SYS |
| OUT-C2-006 | tables.py:370; tables.py:385 | Unknown parts add nothing to mass; the number shown (e.g. `0`) looks like a value; "Complete=no" is the only hint. | R12 | SYS |
| OUT-C2-007 | mass.py:46 | One global fractional margin on the sum; no per-item or per-category margin. | R3,R4 | SYS |
| OUT-C2-008 | tables.py:406-414 | Test plan is generated by fixed logic: every wire tested continuity point-to-point and isolated from "all other wires and shields", regardless of voltage class, shielding, harness type. One limit for all wires. No test method (2/4-wire), current, dwell, temperature, instrument, calibration. | R4,R7 | AIT ELEC |
| OUT-C2-009 | tables.py:401-403,411 | Isolation test voltage is a single value in V (any polarity/ramp/hold implied); continuity limit in ohm for any gauge/length (no length-dependent expectation). | R4,R12 | ELEC AIT |
| OUT-C2-010 | tables.py:419-435 | Labels: one label per connector independent of gender/size; two per wire (one per end) in the same format; no label material, size, marker length, print order; `Quantity` always 1. | R3 | AIT |
| OUT-C2-011 | buildsheet.py:358; verify.py:1758 | "Ready to build = yes" ignores DRC errors, release/review status, approval, strip lengths, terminations, contacts and test limits (placeholder qualifier only). An engineer can read "yes" as design-approved. | R12 | AIT SYS |
| OUT-C2-012 | buildsheet.py:255-266 | Cut order assumes AWG (smaller number = thicker) and that colour-then-length grouping is what the shop wants; part/cable type does not group. | R3,R4 | AIT |
| OUT-C2-013 | tables.py:116-121; buildsheet.py:36 | AWG is the only gauge system and metres/millimetres the only length units; no mm2 or inch. | R5 | ELEC AIT |
| OUT-C2-014 | tables.py:34-44 vs 29-31 | CSV/XLSX numbers keep 9 decimals (precision overstated, e.g. 12.345678912 g); drawings show 6 significant digits. Same wire shows different lengths in the drawing and the list. | R5 | SYS AIT |
| OUT-C2-015 | stamp.py:20-25; exports.py:102 | No timestamp anywhere by design ("equal design, equal bytes"); an engineer cannot tell when or by whom an output was made; workbook properties show 2000-01-01. | R8,R9 | SYS AIT |
| OUT-C2-016 | provenance.py:25-58 | Provenance does not contain the configuration values (limits, margin, resistivity, derating), only a hash that cannot be read back; nor input files, import sources or operator. | R9,R3 | ELEC SYS |
| OUT-C2-017 | verify.py:1-4, 1240-1244 | The "independent" verifier is a second implementation of the same documented rules; it detects builder bugs and tampering, not wrong rules/constants. Type/Interface/Carries cells are accepted if plausible. | R1,R12 | SYS |
| OUT-C2-018 | drawing.py:121-135 | Layout puts connectors left/right by algorithm; "From" may be on the right; reading direction of a wire is not the same as From/To of the list. | R6 | AIT |
| OUT-C2-019 | drawing.py:643 | Title block DATE is the release date (or `-`), not the drawing/export date; a draft drawing has no date. | R9 | AIT SYS |
| OUT-C2-020 | canvas.py:24-27 | Signals/labels longer than the column are cut with `~` on the drawing, IDs are shrunk instead; the verifier tolerates the cut signal (verify.py:631). | R12 | AIT |
| OUT-C2-021 | drawing.py:317-325 | Cable block shows "AWG mixed"/"lengths vary" without listing them (listed only per row when `mixed`). | R12 | ELEC AIT |
| OUT-C2-022 | tables.py:184 | A pin with a signal/interface but no wire is "not spare" but has no wire; AIT sees "(no wire)" vs "(spare)" in the build sheet (buildsheet.py:491) – two definitions of the same state. | R1 | AIT ELEC |
| OUT-C2-023 | build_data.py:14-15 | Strip lengths, contacts and crimp tools are never computed or validated (no check that a contact fits a pin or gauge, no default strip per contact). | R4,R12 | AIT ELEC |
| OUT-C2-024 | build_data_import.py:288 etc. | Strip/contact import: an empty cell leaves the old value (cannot clear by import); a "tool" per contact must be the same in all rows. | R7 | AIT |
| OUT-C2-025 | system.py:137-141,192 | Diagram semantics: majority category per connection; overview draws a full mesh of all unit pairs of a harness, which implies connections that may not exist. | R1 | SYS |
| OUT-C2-026 | buildsheet.py:9 | Build workbook has no formulas; totals/counts are values; an AIT engineer cannot recompute or adjust (e.g. add allowance) inside the sheet. | R1,R7 | AIT |
| OUT-C2-027 | verify.py:1300-1305 | Pin role rule keys on the literal signal names `RTN` and `GND` (case-insensitive). | R3 | ELEC |
| OUT-C2-028 | build.py:335; build.py:280-286 | "Stale" is judged by model hash (any change, incl. unrelated), and release gate by content hash; the user is told stale/current but not which change caused it. | R8 | SYS |

28 rows.

---

## C3 Outputs shown without a visible derivation

| id | file:line | what is shown and why it cannot be traced | R | persona |
|---|---|---|---|---|
| OUT-C3-001 | tables.py:126 | `Length (m)` per wire: no source (own/segment sum/import), no path, no allowances. | R1 | AIT ELEC |
| OUT-C3-002 | tables.py:330 | BOM `Quantity` in m: no per-wire contribution list, no conductors division shown; `Wires without length` is a count, not a list. | R1,R10 | AIT |
| OUT-C3-003 | tables.py:366-372 | Mass, Margin, Mass with margin: no per-part breakdown, no margin fraction value in the file; Missing data gives names only. | R1,R10 | SYS |
| OUT-C3-004 | tables.py:395-403 | Test `Limit` and `Test voltage`: the config key/file and its status are not named; only `TBD (placeholder)` or the number. | R3,R12 | AIT ELEC |
| OUT-C3-005 | buildsheet.py:315-331 | "Start here" counts (e.g. 7 wires without strip) give no list of which wires/pins; AIT must filter the Cut list by the amber cells. | R6,R12 | AIT |
| OUT-C3-006 | buildsheet.py:359-368 | "Ready to build": text only says "nothing marked TO FIX is open"; the four blocking checks are not named as the definition. | R1,R12 | AIT |
| OUT-C3-007 | buildsheet.py:435 | Cut list order: no column or note says why a wire is at a position (gauge, colour, length key). | R1 | AIT |
| OUT-C3-008 | buildsheet.py:461-466 | Cut list total row: unit not in cell, includes conductor rows at full length. | R1,R5 | AIT |
| OUT-C3-009 | tables.py:59 | EMC class in wire list/label: no pointer to the interface type or the config `emc` file; blank when classes undefined. | R1 | ELEC AIT |
| OUT-C3-010 | tables.py:513-541 | Traceability `Type` of a connection and `Carries`: derived in links.py (not read) and shown without the pair-matching rule. | R1 | SYS |
| OUT-C3-011 | connections.py:87-93 | "From/To role" and "Interface" per pair: derived roles (RTN/GND/category rule) not explained in the file. | R1 | ELEC SYS |
| OUT-C3-012 | build.py:77-102 | Findings table: columns Finding, Rule, Severity, Object, Statement, Waived, Justification, Requirement. No actual value, limit, why it matters or how to resolve. Order: severity then ID. | R12 | SYS ELEC |
| OUT-C3-013 | build.py:177 | `drc_report.md`: counts and statements; "results that depend on [placeholders] are marked as not checked" without listing which rules. | R12 | ELEC SYS |
| OUT-C3-014 | drawing.py:312-327 | Cable summary and per-wire label (`AWG`, `m`) on the drawing: rounding 6 digits, source not shown. | R1,R5 | AIT |
| OUT-C3-015 | drawing.py:586-614 | Wire geometry on drawings is schematic; the drawing length of a wire has no relation to its Length value (not stated on the sheet except the sketch "not to scale"). | R1 | AIT |
| OUT-C3-016 | provenance.py:46-49 | `values_sha256_16` per config: cannot be reversed to values or compared to a file without the same algorithm; no per-key change info. | R9,R3 | ELEC SYS |
| OUT-C3-017 | build.py:42-47 | Manifest `content_hash` vs `model_hash`: two hashes, meaning explained only in code comments. | R9 | SYS |
| OUT-C3-018 | tables.py:329 | `Approval` text e.g. `pending (example data)`: no pointer to who approved or when. | R8 | AIT SYS |
| OUT-C3-019 | tables.py:331 | `Used in` list of harness IDs per part: no wire/connector references. | R1 | AIT |
| OUT-C3-020 | exports.py:114,142-144 | xlsx About sheet is 2 rows (stamp, hash): no settings, no limits, no status of placeholders. | R9 | AIT SYS |
| OUT-C3-021 | build.py:179 | `revision_report.md` and `changelog.csv`: who/when/comment recorded (vcs/report.py:22-37, `By`,`Date`,`Comment` columns), but no old/new values of edits and changes are only at release/review/new revision granularity. | R8 | SYS AIT |
| OUT-C3-022 | build.py:105-188 | Progress/inspection of intermediates: the build is one call; the user sees no per-step intermediate (wire list -> BOM -> mass) and cannot inspect it before files are written. | R6 | SYS |

22 rows.

---

## C4 Forced choices (no alternative selectable)

| id | file:line | what is forced | R | persona |
|---|---|---|---|---|
| OUT-C4-001 | tables.py:116; buildsheet.py:36 | Gauge system AWG and length unit m (wires) / mm (strip, accessories); no unit selection or conversion. | R5 | ELEC AIT |
| OUT-C4-002 | tables.py:406-414 | Test table logic fixed: no custom test types, per-class limits, test method, extra columns, test order. | R4,R13 | AIT ELEC |
| OUT-C4-003 | tables.py:419-435 | Label format and quantity fixed (2 per wire, 1 per connector); no label template, material or size. | R3,R4 | AIT |
| OUT-C4-004 | buildsheet.py:31-53 | Build workbook sheet names, column sets and sign-off steps fixed; cannot add company fields (serial number, lot, tool ID, operator, drawing number). | R3,R13 | AIT |
| OUT-C4-005 | buildsheet.py:255-266 | Cut order fixed. | R4 | AIT |
| OUT-C4-006 | buildsheet.py:297-332,358 | Which checks block "Ready to build" is fixed; no way to make strip lengths or contacts blocking, or DRC errors blocking. | R3,R7 | AIT SYS |
| OUT-C4-007 | build.py:118-187 | The list of output files is hard-wired; no registry for own tables, models or exports. | R13 | SYS |
| OUT-C4-008 | build.py:108; canvas.py:17 | Drawing sheets only A4/A3; font Courier only; PDF/SVG layout fixed; PDF cp1252. | R3 | AIT |
| OUT-C4-009 | stamp.py:54-61; build.py:135-140 | CSV always comma, LF, first line `# stamp` comment (a `delimiter` parameter exists but is never used by build_outputs); plain readers show the comment as data. | R10,R14 | SYS |
| OUT-C4-010 | stamp.py:38-46 | Formula-like text altered with a leading apostrophe in CSV; cannot be turned off. | R14 | SYS |
| OUT-C4-011 | exports.py:154; build.py:153 | WireViz YAML structure fixed: each wire is a one-conductor cable; no cable bundles/twisted pairs; not validated against WireViz (exports.py:28-29). | R14 | SYS |
| OUT-C4-012 | stamp.py/exports.py:102 | No timestamp option; deterministic bytes are forced. | R9 | SYS AIT |
| OUT-C4-013 | build_data_import.py:171 | Import all-or-nothing: one bad row blocks the table. | R7 | AIT |
| OUT-C4-014 | build_data.py:38 | Accessory kinds limited to the model's `AccessoryKind` set. | R13 | AIT |
| OUT-C4-015 | tables.py:62-89 | Optional columns appear only if the project uses them; the user cannot force a stable column set across projects (affects scripts). | R14 | SYS |
| OUT-C4-016 | mass.py:46 | One global mass margin fraction; no per-part margin. | R4 | SYS |

16 rows.

---

## C5 Inputs and outputs exchanged with other tools or files (explicit and implicit)

| id | file:line | description | R | persona |
|---|---|---|---|---|
| OUT-C5-001 | build.py:132-188 | Written per harness: wirelist, pinouts, bom, mass_length, tests, labels (CSV), accessories.csv (only if any), wireviz.yaml, `<H>.xlsx`, `<H>_build.xlsx`, drawings (optional): total 232 files for 24 harnesses in the example. | R10 | SYS AIT |
| OUT-C5-002 | build.py:167-187 | System: bom, mass_length, mating_matrix, traceability, box_pinouts, connections (csv, xlsx; only with links), drc_findings.csv, drc_report.md, changelog.csv, revision_report.md, export.json, provenance.json, system.xlsx, block_diagram/harness_overview svg+pdf. | R10 | SYS |
| OUT-C5-003 | build.py:39-52 | manifest.json: generator_version, model_hash, content_hash, placeholder_config, files with sha256 and bytes. Written last, outside the file list. | R9,R14 | SYS |
| OUT-C5-004 | exports.py:79-99 | export.json holds: project name/description, placeholder config NAMES, units, interface_types, interfaces, box_connectors, harnesses (all fields incl. wires, strip, segments, shields, accessories), parts, links. NOT in it: config values/limits, derived lengths, mass, BOM, tests, DRC findings/waivers, changelog, baselines, library_info, zones. | R9,R10,R14 | SYS ELEC AIT |
| OUT-C5-005 | exports.py:27-54 | WireViz YAML: connectors (pincount, pinlabels, type), cables (gauge, colour, length without unit), connections; wire signal/interface/strip/termination/contact not exported. | R14 | SYS |
| OUT-C5-006 | provenance.py:25-58 | provenance.json lists library name/version/source/date; no list of imported files (parts, netlist, lengths, build data) or their hashes. | R9,R14 | SYS |
| OUT-C5-007 | build_data_import.py:1-20 | Build-data import accepts CSV/TSV/JSON/XLSX via `imports.read_table_sheet` (not read). The model keeps no record of source file, sheet, row or hash; the only trace is the change history of the edit. | R14,R8 | AIT |
| OUT-C5-008 | lengths.py:131-170 | Segment-length import (CSV from CAD) columns by position (harness, segment, length), `scale` argument; units of the file are chosen by the caller; source file not recorded. | R14,R5 | AIT |
| OUT-C5-009 | build.py:196-234 | `write_outputs` reads the previous manifest and DELETES files listed there that are no longer in the set (and removes empty folders); refuses links. Implicit deletion; user sees only "N files written". | R6 | SYS |
| OUT-C5-010 | build.py:327-352 | `outputs_status` compares manifest model hash with the current model (quick) or file hashes (deep): "none/stale/modified/current". Change detection of outputs vs design exists; none for imported source files. | R14 | SYS |
| OUT-C5-011 | verify.py:46-52, 99-113 | `verify_outputs` reads the whole output folder (and ignores `*.tmp`); runs automatically after CLI export; findings codes `out_*`. | R11,R12 | SYS |
| OUT-C5-012 | xlsx_env.py:11 | Sets process environment `OPENPYXL_LXML=False` at import so bytes are reproducible. Implicit global side effect. | R11 | SYS |
| OUT-C5-013 | exports.py:113-151; buildsheet.py:685-701 | XLSX built with openpyxl write-only; no formulas; data validation lists (`x`, `Pass,Fail`) and conditional formats inside the AIT sheets. | R10 | AIT |
| OUT-C5-014 | buildsheet.py:346-421 | The AIT workbook is filled in by hand and is NOT read back: results, ticks, initials and dates typed into `_build.xlsx` are never imported; re-export overwrites the file (build.py:155,226-227). | R8,R10,R14 | AIT |
| OUT-C5-015 | drawing.py:100-107; canvas.py:102 | In-memory `Sheet.marks` (drawing-to-object links) are never written to SVG/PDF; only `data-ref` on pin and signal texts in SVG. | R10,R14 | SYS |
| OUT-C5-016 | stamp.py:64-69 | `parse_csv` skips only the first line if it starts with `# `; external readers must do the same. | R14 | SYS |
| OUT-C5-017 | build.py:72-102 | drc_findings.csv holds Rule/Severity/Object/Statement/Waived/Justification/Requirement; no actual or limit value columns. | R12,R10 | SYS ELEC |
| OUT-C5-018 | tables.py:127 | Only flag about manual state in the wire list is `Locked` (kept against regeneration); no column for manual length/gauge/colour override. | R7 | SYS ELEC AIT |
| OUT-C5-019 | build.py:154-155; buildsheet.py:25 | Same data in several forms (CSV, `<H>.xlsx`, `_build.xlsx`, system.xlsx); the verifier checks they agree (verify.py:1495,1911). | R10 | SYS |
| OUT-C5-020 | cli export | Observed: `export` fails with "there are no harnesses to export" before `generate`; writes to `<project>/outputs`, verifies after writing. | R11 | SYS |

20 rows.

R10 gap list (intermediates in memory, not exported): per-wire derived length and the segment path; per-part mass contribution; BOM per-wire contributions; readiness check item lists; cut-order key; derived interface/pair types and roles (links.py); drawing placement (sides, pagination, `Sheet.marks`); configuration values used; margin fraction applied; verifier's recomputed values.

---

## C6 Customisation points that DO exist

| id | file:line | what the engineer can change | R | persona |
|---|---|---|---|---|
| OUT-C6-001 | tables.py:395-403 | Test limits and voltage via config `generation.json` keys `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v` (JSON in `config/`, human-readable). | R3 | AIT ELEC |
| OUT-C6-002 | mass.py:41 | `mass_margin_fraction` in `generation.json`. | R3 | SYS |
| OUT-C6-003 | configcheck.py:437 | Title block field list in `titleblock.json`. | R3 | SYS AIT |
| OUT-C6-004 | build_data.py (plan_set_strip, plan_set_contacts, plan_set_accessory, plan_set_part_tool) | Strip lengths per end, contact part per pin, accessories, crimp tool per contact; undoable via `Op`s; released harness refuses edits (build_data.py:63-71). | R7 | AIT |
| OUT-C6-005 | build_data_import.py:147 | Import of the same four build-data kinds from tables with row-by-row result messages; CLI `import-build-data`. | R14 | AIT |
| OUT-C6-006 | tables.py:78-80,101 | Wire `label`, `note`, connector `label`, harness `label` text feed labels, cut list and wire list. | R7 | AIT |
| OUT-C6-007 | build.py:105-113 | `build_outputs(sizes=, drawings=, harness_ids=, cancel=, progress=)` and `write_outputs`, `outputs_status`, `damaged_files`, `verify_outputs`: a scriptable Python core (docstrings only; no external API document read). | R11 | SYS |
| OUT-C6-008 | build.py:271-277; CLI `--drawings` | Drawings optional (default off in CLI). | R3 | AIT |
| OUT-C6-009 | build.py:97-98 | Waivers with justification appear in drc_findings.csv (`Waived`,`Justification`). | R8,R12 | SYS ELEC |
| OUT-C6-010 | build.py:49-52, 289-306 | Manifest with SHA-256 per file; `damaged_files` detects edited outputs. | R9 | SYS |
| OUT-C6-011 | tables.py:329; buildsheet.py:343,389-391 | Placeholder and unverified flags carried to Parts, "Start here" and manifest. | R12 | ALL |
| OUT-C6-012 | wirecolours.resolve (wirecolours.py:34-47) | Colour names/IEC 60757 codes resolved from a table; unknown names kept, drawn grey. Table is code, not config. | R3 | AIT |
| OUT-C6-013 | stamp.py:54 | `csv_bytes(delimiter=)` exists (not used by build). | R14 | SYS |
| OUT-C6-014 | exports.py:79-99 | export.json documents the whole model (all fields) and is deterministic; easiest machine-readable hand-off. | R14 | SYS |

14 rows. No plugin/registry mechanism for outputs, tables, test types, labels or models was found (R13).

---

## AIT lens: the AIT engineer's working outputs

Persona [AIT]. All of these are in `<H>_build.xlsx` (buildsheet.py) unless stated. "Source" = can the AIT engineer follow the value back to its origin; "Edit" = can the value be changed in the sheet or only in the design.

| output | numbers / text an AIT engineer sees | traceable to source? | edit / override? | missing for as-built records and test limits |
|---|---|---|---|---|
| **Start here** (buildsheet.py:346-421) | "Ready to build" yes/no; 8 check counts with status OK/TO FIX/NOTE; harness revision/status/stamp; author, checker, approver, "Released on" (or "not set"); placeholder file names; 5 sign-off rows | Counts have no item lists (buildsheet.py:315-331). Ready definition (4 blocking checks) not stated. Placeholder files are named (`config/<n>.json`). Author/approver/date from the design record. | Not editable in sheet (no formulas, values). Edit design then re-export. | No export date/time, no export user, no configuration values, no job/serial/lot/work-order field; "Ready" ignores DRC findings and test limits. No as-built revision field separate from design revision. |
| **Cut list** (buildsheet.py:429-471) | Per wire: colour (name + IEC code, colour fill), AWG, part, **Length (m)**, **Strip A / B (mm)**, from, to, signal or label, shield group, note; total row; "Cut (x)" tick; sort by gauge, colour, length | Length: no source (own value / segment sum / import / generated incl. service loop) and no allowance shown (OUT-C2-001). Strip: person-entered (build_data), no default or datasheet link. Colour: wire attribute. Order key hidden (OUT-C1-020). Cable vs conductor lengths (OUT-C2-003). | Tick only. Values only in design (Edit wire tab / import); no per-sheet override, no "actual cut length" column. | No actual cut length / measured length, no cut allowance, no spool/lot/heat code, no wire-part batch, no tolerance on length (+/- mm), no strip tolerance. `to fill in` amber cells are the only flag. |
| **Connectors** (buildsheet.py:474-565) | Per connector block: ID, part, gender, "mates with ..." or "not plugged into a unit", label; per pin: signal, function, wire IDs, colour, AWG, goes-to, termination (crimp/solder or `to fill in`), contact size, contact part, tool (from the contact part), 3 tick columns (Terminated/Inserted/Checked) | Contact/tool are person-entered library/pin fields; "Contact size" free field `p.contact_size`; no link to a crimp spec, pull-test value or insertion depth. Goes-to derived from wires. | Ticks only. Pins with 2+ wires show joined text. | No crimp height/force/pull-test limits, no tool calibration ID, no operator/date per pin, no solder spec/inspection class, no torque for backshell. |
| **Parts** (buildsheet.py:568-591; tables.py:284-333) | Part, category, manufacturer, part number, description, approval (colour), Quantity + Unit, Wires without length, Used in | BOM quantities derivable only by re-counting (OUT-C3-002); metres = net length / conductors, no waste or spares. | Not editable; no "issued quantity" column. | No lot/date code, no issued/returned quantity, no stock location, no substitution record; approval shows state not approver/date. |
| **Accessories** (buildsheet.py:594-624) | Done tick, ID, kind, part, target (`(harness)` default), position (free text), length (mm), quantity, note | Person-entered; position is words only ("50 mm from P1 end"), no computed position. | Ticks only. | No applied length, no heat-shrink recovered size/temperature, no installed position tolerance. |
| **Labels** (buildsheet.py:627-642; tables.py:419-435) | Done tick, label ID (`W-A`/`W-B`), kind, text, quantity (1) | Text built from wire label/signal and far-end pin + `[EMC x]` tag; format fixed. Which label ID is on which end of the cable not stated beyond "to <far end>". | Ticks only. | No label size/material/print template, no print order, no spare labels, no check-after-print field. |
| **Tests** (buildsheet.py:645-675; tables.py:400-415) | Test ID `T001...`, type, from, to, expected (`continuous`/`isolated`), **Limit** (`0.1 ohm max` / `100 Mohm min` style or `TBD (placeholder)`), test voltage (isolation only), wire; empty Measured, Result (Pass/Fail list), Initials, Date | Limit text comes from config keys but the sheet names neither the key nor the file; global limit for all wires; `TBD (placeholder)` appears as a limit with no instruction. Method implicit. | Result/Measured/Initials/Date are free cells; limit not editable in sheet (config). Result is not checked against Limit (no formula). | No numeric Measured unit (cell header "Measured" has no unit), no instrument ID / calibration due date, no test voltage tolerance/hold time, no temperature/humidity, no test-pair for shield isolation beyond "all wires", no overall pass/fail and no link of results back to the tool (OUT-C5-014). |
| **Sign-off block** (buildsheet.py:410-415) | 5 fixed steps with Name / Date / Signature | Static text. | Hand-fill only. | No inspection/QA stamp, no discrepancy/NCR reference, no as-built deviation list, no document number; results never re-imported. |
| **About sheet** (buildsheet.py:678-682) | `Generated by` stamp line and `Model hash` | Hash links to the model; tool version in the stamp. | No. | No timestamp; footer on each sheet shows the stamp line only (buildsheet.py:224-226). |
| **Drawing (optional PDF/SVG)** (drawing.py) | Connectors with pins/signals, cable block per connector pair, wire ID + IEC code, AWG/length if mixed, shield sleeves, routing sketch, notes, spare pins, title block | Wire lengths 6 significant digits; schematic only; sketch dropped over 14 nodes; signals cut with `~`; date field = release date. | No. | No dimensional/branch-length drawing for the board, no tolerance, no break-out lengths. |

AIT summary: the sheet is a good, honest to-do list ("to fill in" never invents values) but every number is a bare value without derivation; strip length and contact data are fully manual; there is no place in the output for as-built (actual) values, tolerances, lot/serial, tooling calibration, or test measurement units, and what is typed into the workbook is never brought back into the tool.

## Electrical lens: outputs

- No ampacity, derating, voltage drop, bundle factor, temperature or resistivity appears anywhere in the outputs I read; `conductor_resistivity_ohm_m` is a config key (generation.json) but no output file uses it (grep of outputs found none; DRC rules may). Output files therefore show no numeric margin against any electrical limit; the findings table carries only statements (build.py:77-102).
- Shield end A/B (drawing.py:354-392) and EMC class (tables.py:55-59, label suffix) are shown but with the hidden conventions in OUT-C1-018 and OUT-C1-044.
- Test limits (continuity ohm, isolation Mohm, voltage V) are global, unit-tagged text, placeholder in the example (observed tests.csv: `Limit = TBD (placeholder)`).
- Pin role rule (RTN/GND by literal name) in connection list is hard-coded (OUT-C1-052).
- Connector ratings (`Part.ratings`) are exported to export.json only, not shown in any CSV/XLSX.

---

## Top findings

1. **OUT-C2-001 / OUT-C1-060** [AIT ELEC SYS]: every "Length (m)" (wire list, cut list, BOM metres, mass, YAML) has no stated basis: own value vs segment sum vs service loop vs strip/cut allowance; two-route paths silently give "no length".
2. **OUT-C2-016 / OUT-C1-036** [SYS ELEC]: provenance records only a 16-hex hash of each config file; limits, margin, resistivity and other values used are not recorded in any output, and there is no timestamp, operator or imported-file list (R9).
3. **OUT-C1-022 / OUT-C4-006** [AIT SYS]: "Ready to build" is decided by 4 fixed checks and ignores DRC errors, release status, strip lengths, terminations and test limits; the definition is not shown on the sheet.
4. **OUT-C1-016 / OUT-C1-015 / OUT-C4-002** [AIT ELEC]: the test plan and its limits are fixed logic with one global limit; limits show as `TBD (placeholder)` while the sheet can still read "Ready to build: yes (...placeholder...)"; no method, instrument, tolerance or unit on "Measured".
5. **OUT-C5-014 / AIT lens** [AIT]: the build workbook is write-only: ticks, measured values, initials and dates typed in are never read back, re-export overwrites them, and there is no as-built/serial/lot/actual-length field.
6. **OUT-C2-003 / OUT-C1-008** [AIT SYS]: cut list lists each conductor at full length while BOM divides by `conductors`; unmarked difference between cable metres and wire rows.
7. **OUT-C5-018 / OUT-C3-021** [ALL]: no exported value is flagged as overridden or manually set (only `Locked`); manual vs generated length, gauge or strip are indistinguishable, and the change log has no old/new values.
8. **OUT-C2-017 / OUT-C3-012** [SYS ELEC]: the "independent" verifier re-implements the same rules and tolerates "as written" cells; findings exports carry no actual/limit/how-to-fix, so electrical pass/fail margins are not visible or defensible from the outputs (R12).
9. **OUT-C1-012 / OUT-C2-005** [SYS ELEC]: mass covers only cable connectors and wires with one global margin; contacts, backshells, sleeving and accessories are excluded, and unknown data yields `0` with only a `Complete=no` hint.
10. **OUT-C5-004 / OUT-C4-007** [SYS]: export.json omits config values, derived lengths, mass, BOM and findings; the output list is hard-wired (no registry), so a user cannot add tables, test types or label formats (R10, R13).

Next: [the audit](../transparency_audit.md), [appendix C](rules-and-warnings.md), [appendix E](interchange-and-cli.md)
