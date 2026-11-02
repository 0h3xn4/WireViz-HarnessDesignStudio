# Transparency audit, appendix H: the GUI dialogs and workflow

This page is appendix H of the [transparency audit](../transparency_audit.md): the row-level catalogue for the checks and problems panels, the export, import, settings and release screens, the roles and the workflow. Each row names the file and line the reviewer opened. IDs read `GUI2-C<category>-<number>`; the categories and the tags `[SYS]`, `[ELEC]` and `[AIT]` are explained in section 1 of the audit. Paths beginning with `work/` are scratch projects the reviewer made while auditing; they are not in the repository. Nothing on this page was changed in the code: it is read-only.

## Contents

- [C1 Hard-coded constants, defaults, thresholds, rules](#c1-hard-coded-constants-defaults-thresholds-rules)
- [C2 Hidden assumptions](#c2-hidden-assumptions)
- [C3 Outputs the user sees without seeing how they were derived](#c3-outputs-the-user-sees-without-seeing-how-they-were-derived)
- [C4 Forced choices, no override](#c4-forced-choices-no-override)
- [C5 Inputs and outputs exchanged with other tools or files (including implicit)](#c5-inputs-and-outputs-exchanged-with-other-tools-or-files-including-implicit)
- [C6 Customisation that exists](#c6-customisation-that-exists)
- [Persona lens: how each screen serves each role](#persona-lens-how-each-screen-serves-each-role)
- [Top findings](#top-findings)

Scope: Harness Design Studio 1.11.1, commit d42f0be. Paths are relative to `HarnessDesignStudio/src/harness_design_studio/`. Persona tags: [SYS] systems engineer, [ELEC] electrical engineer, [AIT] assembly/integration/test engineer, [ALL].
Read in full: gui/checks_panel.py (955), problems_panel.py (233), config_dialog.py (409), settings_page.py (425), export_dialog.py (1108), export_docs.py (190), outputs_files.py (426), import_wizard.py (968), import_kinds.py (590), next_step.py (291), workflow.py (98), roles.py (57), role_dialog.py (86), lock_tree.py (244), release_text.py (38), drc_process.py (175), recent.py (69), app.py (54), jobs.py (89), startup_help.py (109), new_project_dialog.py (290), next_page.py (302), panels.py (lines 1-190, 188-930 filtered), dialogs.py (lines 1-135, 211-909 filtered), releases_panel.py (732, filtered of layout calls), library_window.py (lines 1-80, 744-845 + greps), pages.py (1-120). Grep-only or skimmed: command_palette.py, empty_state.py, tour.py, background.py, notice.py, connector_picker.py (cosmetic constants only, no engineering content seen). gui/lockview.py does not exist (it is core/vcs/lockview.py). strings.py: about 1,000 lines read in ranges (checks, config, export, import, outputs, release, roles, next step, settings, waive, strip/contact/crimp texts). Also read for context: gui/areas.py 1-100, gui/main_window.py 3240-3345 and 3457-3640 (role handling, release flow, `_hide_menu_entries`), core/configcheck.py 20-130 and 440-620, core/imports.py 20-24, 210-252, core/generate/lengths.py 121-146, core/model/review.py 35-48, core/checks.py 19-35, core/wirecolours.py, core/copies.py:33, core/outputs/stamp.py, core/outputs/build.py 27-50. Behaviour observed once with the CLI (`new --template flatsat`, `drc`) in my scratch folder gui2-work.

---

## C1 Hard-coded constants, defaults, thresholds, rules

Columns: id | file:line | value or rule | what it does / which output or decision it feeds | unit | visible to user? (where) | editable? | R | persona

| id | file:line | value / rule | effect | unit | visible? | editable? | R | who |
|---|---|---|---|---|---|---|---|---|
| GUI2-C1-001 | strings.py:679; gui/dialogs.py:793-797 | `COMMENT_MIN = 10` | Review comment, release comment, placeholder-release reason and unapproved-part reason each need at least 10 characters after strip; length is the only quality test | characters | yes (hint "write at least 10 characters", strings.py:672) | none | R3,R7 | ALL |
| GUI2-C1-002 | gui/dialogs.py:124 | `if len(self.text.toPlainText().strip()) < 10` | Waiver justification minimum is a separate literal 10 (not COMMENT_MIN); text says "at least 10 characters" (strings.py:132). Two copies of the same rule | characters | yes (error text) | none | R3,R7 | ALL |
| GUI2-C1-003 | gui/panels.py:668,838,845 | `MAX_CARDS = 25`; findings of one rule+object+fix are collapsed into one card when count >= 3 (and only if not waivable) | Inspector Problems shows 25 cards max, then "N more"; grouped card lists first `GROUP_LIST = 8` (panels.py:670) | cards / findings | yes ("more problems" line) | none | R3,R12 | ALL |
| GUI2-C1-004 | gui/panels.py:669,728 | `UNCHECKED_RULE = "unchecked-config"` notes are exempt from the card limit | "Not checked" notes always shown; deliberate honesty rule | rule id | yes (heading "Not checked") | none | R12 | ALL |
| GUI2-C1-005 | gui/problems_panel.py:35,146-148 | `_ORDER = {error:0, warning:1, info:2}`; sort key (severity, rule, object_id) | Problems list order is fixed: errors first, then alphabetical by rule id and object id | order | partly (visible, not stated) | none (columns sortable by click, tables.py) | R3 | ALL |
| GUI2-C1-006 | gui/problems_panel.py:36-39 | Filters all/error/warning/links; `LINK_RULE_PREFIX = "link-"` | "Connections" filter works by rule-id prefix `link-`; a plug-in rule with that prefix would appear there | string | no | none | R13 | SYS |
| GUI2-C1-007 | gui/checks_panel.py:57-64 | `RANK = {fail:0, pending:1, not-checked:2, info:3, pass:4}` | Order in which results sort in the Checks table | order | no | none | R3 | ALL |
| GUI2-C1-008 | gui/checks_panel.py:82-87 | pass + `placeholder_files` -> label "Pass (placeholder values)" | A rule that passed on unreviewed numbers is still counted "passed" in the summary strip (`by_rule.summary`, checks_panel.py:841-849); only the label and a tooltip differ | label | yes (Result cell, strip tooltip `_placeholder_note` 882-885) | none | R7,R12 | ELEC |
| GUI2-C1-009 | gui/next_step.py:162-181 | `stage()`: add_device -> connect -> make_harness -> generate -> check -> fix -> build_sheets -> release -> done; "fix" only if `failed > 0` (errors only) | Fixed 6-step sequence. Warnings and unchecked rules never hold the page (next_step.py:22-23, 118-121); the page moves on to "Get the build sheets" with rules still not checked | step | partly (card says "1 warning is left. It does not stop you", strings.py:3024) | none | R6,R12 | SYS |
| GUI2-C1-010 | gui/workflow.py:51-98 | 3-step top bar Generate/Check/Release; Release "blocked" if stale, failed or not checked | A second, different workflow model (3 steps) next to next_step.py (6 steps); neither lists inputs/outputs of each step | state | yes (top bar chips) | none | R6 | ALL |
| GUI2-C1-011 | gui/releases_panel.py:549 | `wanted = {review:(draft), release:(draft,in_review), revise:(released)}` | Release can be done straight from draft (review is optional); the buttons enable by state only | state | partly (tooltip when disabled, 552-559) | none | R3,R7 | ALL |
| GUI2-C1-012 | gui/releases_panel.py:66-78 | `harness_state`: "revised" = draft that has any baseline | State chip rule | state | yes | none | R1 | ALL |
| GUI2-C1-013 | gui/controller.py:239 | `today = date.today().isoformat()` | Release/review/revision "when" = local calendar date, no time, no time zone | date | yes (Releases, change log) | none | R8,R9 | ALL |
| GUI2-C1-014 | gui/main_window.py:3252-3262 | name for "By": saved `ui/user`, else git `user.name` (only when `release_distinct_roles` on), else OS login `getpass.getuser()` | "Who" of a release is a pre-filled free-text field; identity not verified | text | yes (field, tooltip when from Git) | yes (typed) | R8 | ALL |
| GUI2-C1-015 | gui/export_dialog.py:12-18; export_docs.py:32-64 | Fixed document set per harness: build workbook, wire list, pinouts, BOM, mass/length, tests, labels, WireViz YAML, workbook, drawings A4 PDF, A3 PDF, A3 SVG; 14 system documents | Every export writes the full set; the only switch is "Include the PDF drawings" (D-169). Paper sizes A4/A3 and SVG A3-only are fixed (`drawing_svg` label "Drawing sheets, A3", export_docs.py:44; sheet_ref :177 "A3") | - | yes (tree) | drawings tick only | R3,R4,R10 | ALL |
| GUI2-C1-016 | gui/controller.py:1238-1239; core/outputs/build.py:27 | `DEFAULT_FOLDER = "outputs"` next to the project | Output location cannot be changed; the folder field is read-only (export_dialog.py:518) | path | yes (read-only field) | none ("Copy selection to folder" copies afterwards) | R9,R14 | ALL |
| GUI2-C1-017 | gui/export_dialog.py:128-130 | `OPENABLE_SUFFIXES` = .csv .xlsx .pdf .svg .md .json .yaml .txt .png | "Open" refuses any other file type (security); also requires the manifest to list the file | suffix | yes (notice) | none | R3 | ALL |
| GUI2-C1-018 | gui/export_dialog.py:90,139 | `MAX_DETAILS = 6`, `_DAMAGED_SHOWN = 5` | A failed independent check lists at most 6 problems ("and N more"); a damaged project lists 5 files | count | yes ("and N more") | none | R12 | ALL |
| GUI2-C1-019 | gui/export_dialog.py:105-111 | `human_size`: decimal kB/MB (1000), 1 decimal | File sizes in result list | B/kB/MB | yes | none | R5 | ALL |
| GUI2-C1-020 | core/outputs/stamp.py:20 (`model_hash[:12]`); gui/export_dialog.py:322,1022 | "Design <12 hex of model hash>" in the result header | The only provenance shown at export time is a 12-character truncation of the model hash; no tool version, no config summary, no timestamp | hex | yes ("{n} files written to {folder}. Design {hash}.") | none | R9 | ALL |
| GUI2-C1-021 | gui/outputs_files.py:314-315 | `strftime("%Y-%m-%d %H:%M")` of file mtime; `sha[:12]` shown | "Written" column is the file system mtime in local time (no zone, no seconds); SHA-256 shown truncated in the cell, full in tooltip | time, hex | yes | none | R9 | ALL |
| GUI2-C1-022 | gui/outputs_files.py:102-112 | State rule: manifest -> info; no hash -> Missing; not listed -> "Not in the export" (warning); hash differs -> "Changed since export" (fail); else Matches | Defines "export integrity" as byte equality with manifest; any hand edit of a CSV shows red | state | yes (OUT_REASON tooltip) | none | R9,R14 | AIT |
| GUI2-C1-023 | core/configcheck.py:33-54 | `NEEDS` = 17 required engineering values (ampacity table, bundle_derating, temperature_derating, contact_current_factor, max_voltage_drop_v, spare_pin_fraction, resistivity, shield ends A/B, service_loop_m, power_signal_gap_pins, mass_margin_fraction, 3 test limits, 2 pair lists) | Defines what counts as "pending value"; drives status-bar link, Checks "values pending", Next-step wait note | - | yes (Checks, config dialog) | list is in code only | R3,R13 | ELEC,AIT |
| GUI2-C1-024 | core/configcheck.py:57-70 | `OPTIONAL_NEEDS` = 11 further keys (max_ambient_temperature_c, connector/wire temperature margins, 3 voltage factors, max_mating_cycles, bundle_factor_by_count, power_return_gap_pins, shield_bonding, same_class_one_bundle) | Shown in the form only as "Only values still missing" unchecked; never counted as pending; their rules stay silent | - | partly (listed in dialog) | in code only | R3,R13 | ELEC |
| GUI2-C1-025 | core/configcheck.py:464-492 | `FIELD_INFO` units: A, V, ohm m, m, pins, ohm, Mohm, degC, cycles; no unit for bundle_derating, temperature_derating, contact_current_factor, spare_pin_fraction, mass_margin_fraction, all voltage factors | Dimensionless factors have no stated range/meaning in the form (0-1 vs percent unclear; mass_margin 0.1 = 10 %?) | unit missing | no | none | R5 | ELEC |
| GUI2-C1-026 | core/configcheck.py:597-599 | `_read_number` replaces "," by "." and strips a trailing unit text equal to the field unit | Typed "5,0 A" is accepted as 5.0; "5000 mA" is rejected; no unit conversion exists anywhere in the form | unit | no | none | R5 | ELEC |
| GUI2-C1-027 | core/configcheck.py:20 and 489 | `SHIELD_ENDS = (backshell_360, pigtail, floating)`; `emc.shield_bonding` choice list has one entry `both_ends_backshell` | Shield termination vocabulary and bonding option fixed in code | choice | yes (combo) | none | R4,R13 | ELEC |
| GUI2-C1-028 | gui/config_dialog.py:233-234 | `only_missing` ticked at start when any value is missing and no value was requested | Dialog opens showing only missing values; reviewed/default values hidden until unticked | bool | yes (checkbox) | yes (checkbox) | R2 | ELEC |
| GUI2-C1-029 | gui/config_dialog.py:256-266 | per-file "placeholder" flag is one bool for the whole file (`cfg.placeholder`), default True when the file is absent | "Reviewed" is a single tick for all values of a file; no reviewer, date or per-value status | bool | yes | yes (tick) | R7,R8 | ELEC |
| GUI2-C1-030 | gui/import_kinds.py:61-65,179; import_wizard.py:472 | `LENGTH_UNITS = {mm:0.001, cm:0.01, m:1.0}`; default `length_unit = "mm"` | Segment-length import assumes millimetres unless changed; result stored in metres (core/generate/lengths.py:127). No inch/foot | m | yes (combo, default mm) | yes (3 choices) | R5 | AIT,ELEC |
| GUI2-C1-031 | core/generate/lengths.py:121-139; gui/strings.py:864 (IMP_LENGTHS_NOTE) | Lengths columns read by position (harness, segment, length) with a mandatory heading row | A file with another column order is silently misread (if values are numeric where text expected the row is rejected, otherwise wrong) | - | yes (note under unit box) | no mapping (columns fixed) | R14 | AIT |
| GUI2-C1-032 | core/imports.py:232-252 | `guess_mapping`: header aliases, else "unknown fields default to the field's position" | Interface import pre-selects columns by name, then by column position; user can change in the wizard | - | yes (combos) | yes (combos) | R14 | SYS |
| GUI2-C1-033 | core/imports.py:20-24 | `MAX_ROWS 20000`, `MAX_BYTES 8 MiB`, `MAX_UNPACKED 64 MiB`, `MAX_SCANNED_ROWS 100000`, `MAX_COLUMNS 200` | Import size limits; refusal message names the limit only for rows | rows/bytes | partly (message) | none | R3 | ALL |
| GUI2-C1-034 | gui/import_wizard.py:61-62; import_kinds.py:60 | `LARGE_ROWS = 1500` (background read), `REPLAN_MS = 200`, `PREVIEW_ROWS = 20` | Preview shows the first 20 rows only; "Showing the first 20 of N" | rows | yes | none | R6 | ALL |
| GUI2-C1-035 | gui/import_wizard.py:475; import_kinds.py:181 | netlist reference prefix default `"J"` (`or "J"`) | Components starting with J are treated as connectors unless "Only these references" is given | string | yes (field prefilled) | yes | R14 | ELEC |
| GUI2-C1-036 | gui/import_kinds.py:462 | ampacity file: first row counts as a heading if its first cell is not an integer | Heading detection heuristic for the values import | - | no | none | R14 | ELEC |
| GUI2-C1-037 | gui/import_kinds.py:142-146 | `library_source()` = file name + first 12 hex of SHA-256 | Only the parts import records the origin of the data (in the library record); lengths, ampacity, interfaces, netlist, pinout imports record nothing (unverified for core planners) | hex | yes for parts ("Library source recorded", strings.py:IMP_PARTS_SOURCE) | none | R9,R14 | ALL |
| GUI2-C1-038 | gui/library_window.py:470; core/copies.py:33 | `MAX_DEVICES = 10` copies of one device kind incl. original | Library "Add to project" spin box range 1-10 | count | yes (spin limit) | none | R3 | SYS |
| GUI2-C1-039 | core/wirecolours.py:8-21 | 12 colours with IEC 60757 codes; unknown colour drawn grey `#808080` | Colour vocabulary of the wire-colour dialog and build sheets | code | yes (dialog) | none (free text kept grey) | R3,R13 | AIT |
| GUI2-C1-040 | gui/strings.py:2247,1593 | Termination choices fixed: unspecified, crimp, solder | AIT termination vocabulary cannot be extended | choice | yes | none | R13 | AIT |
| GUI2-C1-041 | gui/strings.py:2266-2275 | Strip length fields "Strip A (mm)" / "Strip B (mm)"; empty clears; no default | No default is invented (good); unit fixed mm; no tolerance, no per-gauge table | mm | yes | yes (values) | R5 | AIT |
| GUI2-C1-042 | gui/drc_process.py:26,25,168 | `CHECK_TIMEOUT_S = 180`; `PAUSE = 0.0005`; env `HARNESS_DRC_INPROCESS=1` | A rule check taking over 180 s kills the helper and silently reruns in the GUI thread | s | no | env var only | R3,R11 | ALL |
| GUI2-C1-043 | gui/recent.py:15-16 | `KEY = "home/recent"`, `LIMIT = 8` | Recent list is 8 projects | count | yes | none | R3 | ALL |
| GUI2-C1-044 | gui/new_project_dialog.py:40,91 | `MAX_NAME = 200` | Project name limit | chars | yes (error) | none | R3 | ALL |
| GUI2-C1-045 | core/templates.py (TEMPLATES) | "blank" = "starter parts and interface types, no devices" | A new project is not empty: starter parts and types are inserted; which values and whether they are example data is not itemised in the dialog | - | partly (one-line summary) | none | R2 | ALL |
| GUI2-C1-046 | gui/areas.py:41,48-65; gui/main_window.py:4633-4640 | `SYSTEMS_HIDDEN` areas and `SYSTEMS_HIDDEN_ACTIONS` (42 menu entries); problem notices default OFF for Systems, ON for Electrical | Role changes what is shown by default, including the pending-values link and counts | - | partly (Settings text) | role switch | R2,R6 | SYS |
| GUI2-C1-047 | gui/checks_panel.py:128-149; settings_page.py:42,148-157 | Column widths, `SCALES = (100,125,150,200)`, themes, tour step texts, palette 560x380 (command_palette.py:34-35), progress bar sizes | Cosmetic | px/% | yes | partly (scale) | - | ALL |

---

## C2 Hidden assumptions

| id | file:line | description | R | who |
|---|---|---|---|---|
| GUI2-C2-001 | gui/checks_panel.py:94-100,196-205; core/configcheck.py:33 | "Pass" means "no finding raised"; a rule whose inputs are unset is "pending/not checked", not failed. The "39 rules" total counts the rules the tool ships (flatsat run: Rules run 39); the table lists every rule, but not its method, threshold or the config keys it reads | R3,R12 | ALL |
| GUI2-C2-002 | gui/checks_panel.py:841-849 | Summary strip counts placeholder passes as "passed" (e.g. "20 passed"); only a tooltip says N of them used unreviewed numbers | R12 | ELEC |
| GUI2-C2-003 | gui/next_step.py:170-181 | The Next-step page treats "checked" as done once all error-severity rules passed or are unchecked; unchecked rules (waiting for derating values) are only mentioned as a note at the build-sheets step (`NEXT_SHEETS_WAIT`, strings.py:2460) | R6,R12 | SYS |
| GUI2-C2-004 | gui/next_step.py:171 | A project whose harnesses were all hand-made skips "Generate"; a project whose harness came from a link skips it too | R6 | SYS |
| GUI2-C2-005 | gui/config_dialog.py:6-7,342-369 | Setting a value stores it in config/<file>.json and clears nothing else; "placeholder" is a separate manual tick. Setting a value does not change the placeholder state, so a file can hold reviewed-looking numbers still flagged placeholder (and vice versa) | R7,R8 | ELEC |
| GUI2-C2-006 | strings.py:1040 (CONFIG_INTRO) | "The tool never supplies a number itself" is true for the 17 required values, but defaults exist elsewhere: `default_gauge_awg`, `wire_part_by_construction` (example parts), starter parts in "blank" (docs/CONFIG.md:94-96), "0 used while unset" for `power_signal_gap_pins` (configcheck.py:46 used_by text) | R2,R3 | ALL |
| GUI2-C2-007 | core/configcheck.py:46,45 | Unset values have silent fallbacks: "wire lengths (excluded while unset)" for service loop, "pin allocation (0 used while unset)" for pin gap. The form says "Needed for" but not what is assumed meanwhile | R2,R7 | ELEC,AIT |
| GUI2-C2-008 | gui/import_kinds.py:179; import_wizard.py:472 | Length import: unit assumed millimetres; the preview shows "123 mm" per row but never the resulting metres or whether existing lengths are overwritten | R5,R10 | AIT |
| GUI2-C2-009 | gui/import_kinds.py:445-490 | Ampacity import replaces the whole `ampacity_a_by_awg` table; the old table size is mentioned in a note but the diff old vs new per gauge is not shown. Gauge system (AWG) fixed in the column header | R1,R7 | ELEC |
| GUI2-C2-010 | gui/import_wizard.py:152-181; core/imports.py:232-252 | Column mapping is guessed by header alias then by position; unmapped source columns are dropped without a list of dropped columns (preview shows only mapped columns) | R14 | ALL |
| GUI2-C2-011 | gui/import_kinds.py:342-362 | Interface import rows are marked "connectors chosen for you and marked Auto until you confirm them" (`IMP_P_AUTO`): the tool chooses connectors/pins; the rule for choosing is in `why` records, not in the wizard | R1,R4 | ELEC |
| GUI2-C2-012 | gui/import_wizard.py:471; strings.py:IMP_PARTS_* | Approval words ("Approved when it says...") default to empty; a status in no list is a row error. No assumption (good), but the user must type vocabulary each time; it is not saved with the project | R14 | ALL |
| GUI2-C2-013 | gui/export_dialog.py:12-18 | "The independent check" is a second pass in the tool itself (`VerifyReport`); the dialog does not say what it compares, only "N problem(s)" and the first 6 messages | R1,R12 | ALL |
| GUI2-C2-014 | gui/export_dialog.py:1057-1100 | "Copy selection to folder" copies the ticked files without `manifest.json`; the copied deliverables lose their hash list and design hash | R9 | AIT |
| GUI2-C2-015 | gui/export_dialog.py:660-668 | Export refuses read-only, damaged (`recovered`), no folder, or no harnesses and no connections; refusal text cites the reason but there is no override for e.g. an unsaved/new project besides Save | R7 | ALL |
| GUI2-C2-016 | gui/outputs_files.py:7-9,80-99 | "Matches export" compares disk files with the manifest the export wrote, not with a re-derivation from the model; a wrong but untouched file still "matches" | R9 | AIT |
| GUI2-C2-017 | gui/releases_panel.py:415-436 | The "last commit" line comes from the Git repository around the project folder (author, subject, short hash); if the folder is not a repo the line is hidden. Release record "By" is not tied to it | R8,R9 | ALL |
| GUI2-C2-018 | gui/dialogs.py:101-130; core/model/review.py:35-48 | A waiver stores id, rule, object, justification, notes, finding_hash: no author, no date. Report says only "justification" | R8 | ALL |
| GUI2-C2-019 | gui/dialogs.py:73 (WaiverDialog), core/checks.py:27 | Waivable or not is decided per finding in core (`can_waive`); the GUI cannot make an error waivable or explain why one is not | R7,R12 | ALL |
| GUI2-C2-020 | gui/lock_tree.py:118-136 | Release lock tree prints each frozen config value via `format_value` (core/vcs/timeline); display rounding/format of that function not visible here (unverified); value order alphabetical | R1,R9 | ELEC |
| GUI2-C2-021 | docs/CONFIG.md:168 (read) vs gui/config_dialog.py | `bundle_factor_by_count`: "a bundle uses the next listed count" and `bundle_derating` is replaced by it: interpolation rule is in docs only, not in the form tooltip (hint is "like 1: 1.0, 10: 0.57") | R1,R4 | ELEC |
| GUI2-C2-022 | docs/CONFIG.md:169 | `partial_load_factor` is "recorded, not applied" and `rf_power_factor` "no rule yet"; neither is in the GUI at all | R2 | ELEC |
| GUI2-C2-023 | gui/recent.py:57-65; app.py:46-48 | Last project reopened automatically at start (`project/last`) | R6 | ALL |
| GUI2-C2-024 | gui/drc_process.py:163-175 | If the helper process fails the check silently runs in-process; results identical in principle, but a failure of the helper is invisible | R6 | ALL |
| GUI2-C2-025 | gui/roles.py:33-41; main_window.py:3464-3474 | A settings file with values but no role silently becomes Electrical / AIT; first run asks once. "AIT" and "Electrical" are one role, so AIT-only tasks (as-built, test limits, labels) have no distinct workspace | R2 | AIT |

---

## C3 Outputs the user sees without seeing how they were derived

| id | file:line | description | R | who |
|---|---|---|---|---|
| GUI2-C3-001 | gui/checks_panel.py:181-193; panels.py:882-935 (_card) | A finding shows `title` (sentence), `why` (explanation + "To fix it:"), requirement IDs. Actual value and limit appear only if the rule's author put them in the sentence. In the flatsat run the shown findings had no numbers (identical connectors, unapproved part "7 place(s)"). No structured actual/limit/margin column | R12,R1 | ELEC |
| GUI2-C3-002 | gui/checks_panel.py:128-149 | Rules table has ID, topic, severity, result, open, waived. No rule description, equation, threshold, config key used, or "how checked" column; only "Standard requirements: ..." tooltip (strings.py CHECKS_TIP_REQUIREMENTS) | R1,R12 | ELEC |
| GUI2-C3-003 | gui/checks_panel.py:383-435 | For a not-checked rule the panel shows the missing key, file, unit and "Supply value..." - good - but not which formula would use it or what value range is plausible | R1,R12 | ELEC |
| GUI2-C3-004 | gui/problems_panel.py:56-68 | Problems list: severity, rule id, object, message; the "why" is a tooltip only | R12 | ALL |
| GUI2-C3-005 | gui/panels.py:912-927 | Waive and Fix buttons: Fix applies a one-click change (`ctl.apply_fix`) whose effect is only described by `fix_label`; "Fix all (n)" tooltip lists a summary (`checks.fix_summary`) but not per-value changes | R7,R12 | ALL |
| GUI2-C3-006 | gui/panels.py:634-637 (_auto_tip) | "Auto" connector badge: tooltip gives the recorded reasons (`why.why_text`, 2 lines) - a real derivation view, but only for connectors and truncated to 2 items | R1 | ELEC |
| GUI2-C3-007 | strings.py WHY_* (1450-1465), core why records | A "Why" tab exists for unit, link, harness, wire, connector, pin ("What the tool recorded when it generated this"); it is a list of recorded sentences, no inputs/units/equation structure, and "Show all N" collapses long lists | R1 | ELEC |
| GUI2-C3-008 | gui/next_page.py:94-175 | Next step page: one title, one sentence, one button, six step lines with words done/next/to do/not possible. Per step: no list of inputs consumed or outputs produced, no counts | R6 | SYS |
| GUI2-C3-009 | gui/workflow.py:55-98 | Top-bar tooltips are single phrases ("not generated yet", "{n} rule(s) failed") | R6 | ALL |
| GUI2-C3-010 | gui/import_wizard.py:466-500 | Import preview/check pages show per-row result and reason, pending list, summary - good. Missing: resulting stored value after unit scaling, columns dropped, diff against existing data (only "Will add / update / keep" text) | R10,R14 | ALL |
| GUI2-C3-011 | gui/import_wizard.py:588-612 | Apply page shows a count and "one undo step called 'Import 12 rows'"; no list of object IDs created or changed | R8,R10 | ALL |
| GUI2-C3-012 | gui/export_dialog.py:322; export_docs.py:111-147 | Result list shows file, document, harness, size. File content, design hash only 12 chars; no per-file row counts, no config used, no tool version | R9,R10 | ALL |
| GUI2-C3-013 | gui/export_dialog.py:440-455 | Drawing preview is re-drawn from the model (`sheet_of`), "the same sheet the file holds" (strings EXP_PREVIEW_CAPTION) - not read from the written file | R9 | AIT |
| GUI2-C3-014 | export_docs.py:60 (`sys_provenance`, `sys_export`, `sys_drc_findings`) | Provenance JSON, project export JSON and findings CSV are written by the export, but the GUI never opens or summarises them; users learn of them only from the tree labels | R9,R10 | ALL |
| GUI2-C3-015 | gui/lock_tree.py:139-164 | Release dialog lists everything a release will freeze, including config files and their values and pending/placeholder status - strong transparency; it does not show the check results at release time | R9,R12 | ALL |
| GUI2-C3-016 | gui/releases_panel.py:105-136 | Diff table before/after in text per field (`r.before`, `r.after`); formatting of numbers is `core.vcs.timeline.format_value` (unverified) | R8 | ALL |
| GUI2-C3-017 | gui/dialogs.py:518-546 | Generate preview dialog: counts, findings list, "placeholders used" sentence; not the list of derived numbers (gauge, length, mass) | R1,R6 | ELEC |
| GUI2-C3-018 | gui/release_text.py:14-31 | Release blockers are rewritten by regex from CLI wording to screen wording; if the core sentence changes the rewrite silently stops (`plain_blocker` leaves it as it was) | R12 | ALL |
| GUI2-C3-019 | gui/panels.py:67-83 | `part_summary` one-line: description, maker, pins, approval, ratings `{k} {v:g}`: rating units not shown, `:g` formatting | R5 | ELEC |
| GUI2-C3-020 | gui/config_dialog.py:90-92,131 | The form says "Source: <requirement id> (profile X)" or "set in the project" (configcheck.py:_source) - a real provenance hint per value; no date, author, or previous value | R8 | ELEC |

---

## C4 Forced choices, no override

| id | file:line | description | R | who |
|---|---|---|---|---|
| GUI2-C4-001 | gui/export_dialog.py:12-18 | Export always writes the full set, deletes files not in the new set (`write_outputs`); cannot export one harness, one table, or a different format | R3,R10 | AIT |
| GUI2-C4-002 | gui/export_dialog.py:1010-1013 | A failed independent check blocks the whole export ("nothing is written"); no "export anyway with the flagged problems" path, no way to see the diff of the two computations | R7,R12 | ALL |
| GUI2-C4-003 | gui/export_dialog.py:518; controller.py:1238 | Output folder is fixed to `<project>/outputs` | R9,R14 | ALL |
| GUI2-C4-004 | export_docs.py:32-64 | Formats fixed per document (CSV for tables, XLSX workbook, PDF A4/A3, SVG A3); no JSON for wirelist/BOM/test tables; no unit or column choice | R10,R11 | ALL |
| GUI2-C4-005 | gui/dialogs.py:101-130 | A waiver is possible only on findings flagged `can_waive`; error-severity findings cannot be accepted with a reason, so they hold the Next-step page | R7 | ALL |
| GUI2-C4-006 | gui/checks_panel.py:128-149 | Rule severity, enabled/disabled, thresholds not editable from the Checks panel; no "downgrade with reason" | R2,R7 | ELEC |
| GUI2-C4-007 | gui/config_dialog.py (FIELD_INFO via configcheck.py:464-492) | Only 28 keys are editable in the GUI. Keys in config files but not in the form: `segmentation.mode`, `forbid_nominal_with_redundant`, `forbid_pyro_with_other`, `contact_rating_key`, `wire_part_by_construction`, `default_gauge_awg`, `emc.classes`, `naming.*` (id templates, `signal_counterparts`, `release_distinct_roles`), `titleblock.fields`, `partial_load_factor`, `rf_power_factor` (docs/CONFIG.md:68-181). Wire colours have their own dialog | R2,R3 | ELEC,SYS |
| GUI2-C4-008 | gui/config_dialog.py:394-409 | A change is committed with only an auto-label ("Set Bundle derating factor") and one undo step: no reason, author or date field; a value locked by a release is disabled with "Locked: ..." and needs a new revision | R7,R8 | ELEC |
| GUI2-C4-009 | gui/config_dialog.py:256-266 | Placeholder tick is per file; cannot mark one value reviewed and another not | R7 | ELEC |
| GUI2-C4-010 | gui/import_kinds.py:261,343,368,413,445,502,534; strings.py:IMP_CHECK_BLOCKS | For kinds with `partial=False` (parts, lengths, values, netlist, pinout) one bad row stops the whole import ("nothing is imported from a list with an error, as on the command line"); only interface import skips bad rows | R7 | ALL |
| GUI2-C4-011 | gui/import_wizard.py:152-181; import_kinds.py:78-104 | Six import kinds only. CLI `import-build-data` (strip lengths, pin contacts, accessories, crimp tools) has no wizard kind, so AIT build data cannot be imported from a file in the GUI (typed per wire/pin instead). `import-devices/-subsystem` go through the Library window | R10,R11 | AIT |
| GUI2-C4-012 | core/generate/lengths.py:121-139; import_kinds.py:61 | Length file: column order, heading row, units mm/cm/m only | R14 | AIT |
| GUI2-C4-013 | gui/import_kinds.py:66,445-490 | Values import accepts only an AWG-to-ampere table; the other 26 config values cannot be imported from a file | R3 | ELEC |
| GUI2-C4-014 | gui/roles.py:24-27; settings_page.py:49 | Two roles only; Electrical and AIT share one role, so an AIT user cannot hide design-only screens or get build-focused defaults; Systems cannot be partially extended | R2 | AIT |
| GUI2-C4-015 | gui/areas.py:48-65 | Systems role hides 42 menu entries incl. "Engineering values..." (`act-values`), all imports except parts and pinout, Revise, Changes, History, Expert/Guided toggle; only the palette or a role switch brings them back; list is code, not a setting | R2 | SYS |
| GUI2-C4-016 | gui/releases_panel.py:549-559; dialogs.py:784-801 | Release needs name + 10-character comment + (placeholder reason if any config file is placeholder) + (unapproved-part reason); the 10-character threshold and the set of required items are fixed | R7 | ALL |
| GUI2-C4-017 | gui/next_step.py:162-181 | Step sequence fixed; only the "or make a harness by hand" alternative at step 1 | R6 | SYS |
| GUI2-C4-018 | gui/library_window.py:470; core/copies.py:33 | At most 10 copies of a device per add | R3 | SYS |
| GUI2-C4-019 | gui/export_dialog.py:128-139 | "Open" limited to listed suffixes and manifest-listed files | R3 | ALL |
| GUI2-C4-020 | gui/settings_page.py:265-291 | Keyboard shortcuts table is read-only (no rebinding); not engineering-relevant | - | ALL |

---

## C5 Inputs and outputs exchanged with other tools or files (including implicit)

| id | file:line | description | R | who |
|---|---|---|---|---|
| GUI2-C5-001 | gui/app.py:14-18; settings_page.py:308 | `QSettings(IniFormat, UserScope, "HarnessDesigner", "HarnessDesigner")` user ini file, path shown in About ("Your settings are kept in ..."). Keys seen: `ui/theme`, `ui/scale`, `ui/mode`, `ui/snap`, `ui/labels`, `ui/connection_ends`, `ui/reduce_motion`, `ui/role`, `ui/user`, `ui/geometry`, `ui/state`, `<role>/ui/problem_notices`, `ui/minimap`, `ui/legend`, `project/last`, `home/recent`, `tour/done`, `export/open_after`, `library/folder|geometry|split`, `<table>/widths|sort` (main_window.py:4416-4739; tables.py:432-468) | R14 | ALL |
| GUI2-C5-002 | gui/recent.py:15-65; main_window.py:4270 | `home/recent` stores JSON of up to 8 projects (folder path, name, counts of devices, interfaces, harnesses by state) outside the project; `project/last` stores a folder path; both are per user, not per project | R14 | ALL |
| GUI2-C5-003 | gui/main_window.py:3324 | Name typed in a release dialog is remembered in `ui/user` and reused for later reviews/releases | R8 | ALL |
| GUI2-C5-004 | gui/main_window.py:3252-3262; core/vcs/roles.py:48-51 | Reads Git config `user.name` (when `release_distinct_roles` on) and the OS login via `getpass.getuser()` as release author | R8 | ALL |
| GUI2-C5-005 | gui/releases_panel.py:35-40,415-436 | Reads the Git repository around the project folder (`core.vcs.gitinfo.last_commit`): author, date, subject, short hash, branch; refreshed every 5 s | R14 | ALL |
| GUI2-C5-006 | gui/export_dialog.py:938-1022 | Export: writes `<project>/outputs/**` plus `manifest.json` (format_version, generator_version, model_hash, files with sha256; core/outputs/build.py:42-47); deletes files of an earlier export that are not in the new set (docstring lines 12-14); no timestamp inside manifest | R9 | ALL |
| GUI2-C5-007 | gui/export_dialog.py:1057-1100; outputs_files.py:381-413 | "Copy selection to folder": writes chosen files to an empty folder via `atomic_write_bytes`, without the manifest | R9,R14 | AIT |
| GUI2-C5-008 | gui/export_dialog.py:421-436; outputs_files.py:351-371 | Reveal/Open hand a file URL to `QDesktopServices.openUrl`, i.e. the system's default viewer for PDF/XLSX/CSV | R14 | ALL |
| GUI2-C5-009 | gui/outputs_files.py:78-99 | Reads and SHA-256 hashes every file under `outputs/` in a thread on show/Verify | R9 | ALL |
| GUI2-C5-010 | gui/import_wizard.py:66-68; import_kinds.py:149-165 | Import reads CSV/TSV/JSON/XLSX (first visible sheet; recorded as `source.sheet`) and KiCad .net/.xml; the file path is not stored in the project except parts (name + 12-hex SHA-256) | R14 | ALL |
| GUI2-C5-011 | gui/dialogs.py:275-330 | Interface import dialog also accepts pasted CSV text (no source file at all) | R14 | SYS |
| GUI2-C5-012 | gui/import_kinds.py:25-57 | Writes into the project through `ctl.run` (one undo step): `Put` ops for parts, `SetConfig` for ampacity, interface/pinout/netlist ops; no log of which file produced which objects | R8,R14 | ALL |
| GUI2-C5-013 | gui/library_window.py:288,520-560; core/library_folder.py:107-135 | Library folder (shared drive/Git checkout) path stored per user; the folder is scanned recursively for `*.json`, hidden folders skipped, non-library JSON "skipped without a word"; writes only on "Save selection to library" (`GYRO1.json`, `devices.json`) | R14 | SYS |
| GUI2-C5-014 | gui/drc_process.py:30-35,123-135,168 | Starts a child Python process `sys.executable -P -m harness_design_studio.core.drc.worker` (or `--drc-worker` in frozen builds) and talks pickled messages over its pipes; env `HARNESS_DRC_INPROCESS=1` disables it | R11 | ALL |
| GUI2-C5-015 | gui/controller.py:1357-1358 | Project lock file in the project folder while open (`ProjectLock`); read-only fallback if it cannot be created | R14 | ALL |
| GUI2-C5-016 | core/templates.py (read) | New project from an example writes a `.gitattributes` for teams using Git | R14 | ALL |
| GUI2-C5-017 | gui/dialogs.py:217-270; docs/CONFIG.md:102 | Wire-colours dialog writes `generation.json` `wire_colour_by_signal`, read by build workbook and drawings | R14 | AIT |
| GUI2-C5-018 | gui/startup_help.py:23-27 | Reads system libraries (libGL, libEGL, libxcb) via the loader at start | - | ALL |
| GUI2-C5-019 | gui/strings.py:198; checks finding text | User guide "section 11" and `docs/PLACEHOLDERS.md` are named as places to read what to fill in; the latter is a file in the repo, not obviously reachable from the packaged app | R2 | ELEC |
| GUI2-C5-020 | gui/export_dialog.py:615,753 | `export/open_after` ("Open the folder after the export") stored in user settings | R14 | ALL |

---

## C6 Customisation that exists

| id | file:line | what the user can change | R | who |
|---|---|---|---|---|
| GUI2-C6-001 | gui/config_dialog.py:171-409 | Form for 28 engineering values (17 required + 11 optional), grouped by config file, with unit label, kind-specific editor, immediate validation (`plan_set_value`), "Needed for" description, source line, locked state, placeholder flag per file, one undo step | R2,R3 | ELEC |
| GUI2-C6-002 | gui/checks_panel.py:383-435 | "Supply value..." from a not-checked rule opens the form at that value | R2,R12 | ELEC |
| GUI2-C6-003 | gui/checks_panel.py:678-704 | Checks filters (all/failed/not checked/pending/passed) and free-text search over id, topic, result, severity, requirements, missing key | R12 | ALL |
| GUI2-C6-004 | gui/dialogs.py:101-130; panels.py:898-910, 923-927 | Waive a finding with a justification (>= 10 chars); waived list shown in Problems; waiver auto-invalidates when the finding changes (`waiver_changed`, review.py:36-41) | R7,R12 | ALL |
| GUI2-C6-005 | gui/panels.py:912-927; checks_panel.py:858-880 | One-click Fix and "Fix all (n)" with tooltip summary, one undo step, skipped fixes named | R7 | ALL |
| GUI2-C6-006 | gui/next_page.py:129-175 | Approve part and Waive buttons on the Next-step problem card | R7 | SYS |
| GUI2-C6-007 | gui/import_wizard.py:184-330,355-420 | Column matching per field, approval/pending/rejected words, default category, length unit mm/cm/m, netlist prefix / refs / connector IDs / parts / signal map / pin-function option, pinout target device / subsystem / connector / default part / gender / replace | R14 | ALL |
| GUI2-C6-008 | gui/import_wizard.py:588-612 | Live preview of the first 20 rows and per-row reasons, "Only rows that need attention" filter, pending list, one undo step | R6,R12 | ALL |
| GUI2-C6-009 | gui/export_dialog.py:560-570,780-860 | "Include the PDF drawings" tick (remembered per folder via `drawings_exported`); harness x document tree ticks choose what the result list shows and what "Copy selection" copies; "Open the folder after export" | R10 | ALL |
| GUI2-C6-010 | gui/outputs_files.py:134-300 | Outputs list with document, format, size, written time, SHA-256, state vs manifest; Verify re-reads the folder | R9,R14 | AIT |
| GUI2-C6-011 | gui/dialogs.py:217-270 | Wire colour per signal from the IEC 60757 list | R3 | AIT |
| GUI2-C6-012 | strings.py:2266-2335 (WIRE_STRIP_*, CE_CONTACT_*, INS_PART_TOOL) | Strip lengths A/B per wire (and apply to all), cable contact per pin, crimp tool per contact part, termination (crimp/solder), accessories | R7 | AIT |
| GUI2-C6-013 | gui/releases_panel.py:146-373 | Timeline of reviews/releases/revisions, comparison of any two revisions or revision vs working design, mark changes on the diagram | R8 | ALL |
| GUI2-C6-014 | gui/dialogs.py:549-801; lock_tree.py | Release dialog: author, checker (required when `release_distinct_roles`), comment, placeholder reason, unapproved-part reason; tree of locked objects and values; New revision dialog shows what becomes editable | R7,R8 | ALL |
| GUI2-C6-015 | gui/settings_page.py:143-263 | Settings: theme, scale, reduce motion, role, Guided/Expert, snap, labels, connection ends, problem notices, library folder, link to engineering values. No engineering setting is stored in user settings | R2 | ALL |
| GUI2-C6-016 | gui/role_dialog.py; settings_page.py:49 | Role: Systems engineer (lean) or Electrical / AIT engineer (everything); switchable at any time, "never a permission, never stored in a project" (roles.py:3) | R2 | ALL |
| GUI2-C6-017 | gui/new_project_dialog.py:62-95 | Folder, name and one of five templates (blank, first-steps, minimal-satellite, small-satellite, flatsat) | R3 | ALL |
| GUI2-C6-018 | gui/library_window.py | Add devices/subsystems from a shared library, count 1-10, save selection to library | R13 | SYS |
| GUI2-C6-019 | cli (argparse list, observed) | Same operations by command line: `drc`, `export`, `verify`, `config`, `import-*`, `release`, `diff`, `log`; GUI wizard documents "planned by the planner the command line uses" (import_wizard.py:14) | R11 | ALL |
| GUI2-C6-020 | gui/command_palette.py (skimmed) | Ctrl+K palette still reaches actions hidden from menus in the Systems role (areas.py:44-46) | R2 | SYS |

---

## Persona lens: how each screen serves each role

| Screen | Systems engineer [SYS] | Electrical engineer [ELEC] | AIT engineer [AIT] |
|---|---|---|---|
| Settings page | Role/mode/notice switches and library folder; "Open the engineering values..." button exists (settings_page.py:222-229) though the menu entry is hidden for this role | Same page; no derating/engineering settings other than that button; no project-level assumptions list | Same; no build/tooling defaults (strip, crimp, paper size, label format) anywhere |
| Config dialog | Reachable via Checks "Supply value..." and Settings button; menu `act-values` hidden. Dimensionless factors and pair lists are what they will meet | Best served: unit, "needed for", source, locked state, placeholder flag; lacks equation, range, history, reason, bundle interpolation rule, ambient/derating chain | Only the three test limits (continuity ohm, isolation Mohm, isolation V) and service loop are theirs; no strip/cut tolerance, no tooling keys; cannot see which are the "limits printed in the test tables" until export |
| Checks / Problems | Reached by the rail (Checks stays in rail); status-bar pending link and counts hidden by default for this role (main_window.py:2676, 4651); Next-step card shows first problem with todo sentence | Rules table with ID, severity, requirement IDs, missing value deep link; no actual vs limit columns | Connector look-alike, unapproved part rules visible; no checks about strip/crimp/label; test limits not checked against anything |
| Export dialog | Next-step button "Export the build sheets" opens it; Outputs area hidden from rail (SYSTEMS_HIDDEN) so the integrity list (SHA-256) is reached only via palette | Gets document tree; no CSV of calculated intermediates; no provenance beyond 12-hex hash | Full tree incl. build workbook, tests, labels, WireViz; cannot export a subset; copies lose manifest; Outputs list with hashes is the "as-issued" record but not an as-built record |
| Import wizard | `act-import` (interfaces) and lengths/values/netlist entries hidden in menus; parts and pinout stay; library window for devices | Ampacity table import, netlist, pinout, parts | Lengths import (default mm); no strip/contact/crimp/accessories import (CLI only); pinout import |
| Release screens | Releases area in rail; revise/changes/history menu entries hidden | Release lock tree lists frozen config values and placeholder status | Release freezes wires/pins/config; no as-built/test-result record; date-only stamp |
| Workflow / Next step | Home screen for this role: 6 plain steps, one button, first problem card with Waive/Approve; no inputs/outputs per step | Page reachable but not first; no link back to it from the lower screens | Same page; "Get the build sheets" is step 5 and only tells that the workbook "has the cut list, the connector blocks and the test sheet" |

What Electrical / AIT gets versus Systems: every area (Home, Drawings, Outputs), all menu entries of `SYSTEMS_HIDDEN_ACTIONS` (imports of lengths/values/netlist/interfaces, Revise/Changes/History, engineering values, Expert/Guided, align tools), problem notices and counts on by default, panels open. What it loses: the Next-step page as first screen and its guidance, the Systems-only buttons on that page (Library, "Show everything"), and the plain-language problem card. The two roles share one shell; Electrical and AIT cannot be separated, and nothing in either role shows assumptions or step inputs/outputs.

---

## Top findings

1. **No structured "actual vs limit vs margin" or equation anywhere in Checks/Problems** (GUI2-C3-001, C3-002): a failed ampacity or voltage-drop rule shows only a sentence; engineers cannot defend the number from the screen. [ELEC] R1,R12
2. **No assumptions panel and no reason/author/date on any value change** (GUI2-C4-008, C2-006, C2-007, C4-007): config dialog edits 28 keys with only an undo label; docs/CONFIG.md documents further keys the form lacks; silent fallbacks when unset ("0 used while unset", "excluded while unset") are not listed. [ELEC] R2,R7,R8
3. **Dimensionless derating/margin factors have no unit or meaning in the form, no unit conversion** (GUI2-C1-025, C1-026): mass_margin_fraction, bundle/temperature/contact factors, voltage factors; "5000 mA" rejected, bundle interpolation rule only in docs. [ELEC] R5
4. **Placeholder passes counted as "passed"; Next step proceeds with unchecked rules; Systems role hides the pending-values link** (GUI2-C2-002, C2-003, C1-009, C1-046): a green strip can rest on unreviewed numbers. [ELEC,SYS] R6,R12
5. **Export is all-or-nothing, fixed folder/formats, no override of a failed independent check, provenance = 12-hex hash only; copies drop the manifest** (GUI2-C4-001, C4-002, C1-020, C2-014): users cannot see tool version, config or timestamp in the dialog. [ALL] R9,R10
6. **AIT build data cannot be imported in the GUI; length import assumes mm and reads columns by position; no source file/hash recorded except for parts** (GUI2-C4-011, C1-030, C1-031, C1-037). [AIT] R5,R14
7. **Waivers and release records carry no author/time; "when" is a local date, "by" a typed or OS-login name** (GUI2-C2-018, C1-013, C1-014, C1-002). [AIT,ELEC] R8
8. **Role design: Electrical and AIT are one role; the Systems role hides 42 menu entries (incl. engineering values and most imports) and by default turns problem notices off** (GUI2-C4-014, C4-015, C1-046); workflow exists as two models (3-step top bar and 6-step page) without inputs/outputs per step (GUI2-C1-010, C3-008). [SYS,AIT] R2,R6

Electrical-engineer items: 1, 2, 3, 4. AIT-engineer items: 5 (copies without manifest, no subset), 6, 7 (release as only record, no as-built).

Not covered or unverified: core/vcs/timeline.format_value rounding, core planners' own source recording for lengths/pinout/interfaces, content of `sys_provenance.json`, menu text of the full Help guide, and the actual-value text inside individual rules (other reviewers' areas).

Next: [the audit](../transparency_audit.md), [appendix G](gui-work-screens.md), [appendix I](requirements-and-trace-test.md)
