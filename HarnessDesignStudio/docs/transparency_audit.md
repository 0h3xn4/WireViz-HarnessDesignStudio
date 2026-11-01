# Transparency audit (Phase 0)

This page is the Phase 0 audit of Harness Design Studio 1.11.1 against the request to make the tool transparent, traceable and customisable. It changes no code. It lists what the tool hides, hard-codes and forces today, how far a real number can be traced, what already exists to build on, and a proposed order of work. **Nothing is implemented. The next step waits for your review.**

## Contents

- [1. What this audit is](#1-what-this-audit-is)
- [2. The people it is for](#2-the-people-it-is-for)
- [3. The short version](#3-the-short-version)
- [4. What already works and should be kept](#4-what-already-works-and-should-be-kept)
- [5. Findings by principle](#5-findings-by-principle)
- [6. The 14 requirements: where the tool stands](#6-the-14-requirements-where-the-tool-stands)
- [7. The definition of done, tested today](#7-the-definition-of-done-tested-today)
- [8. The trace test: 16 real numbers](#8-the-trace-test-16-real-numbers)
- [9. Defects and inconsistencies found](#9-defects-and-inconsistencies-found)
- [10. The catalogue (appendices)](#10-the-catalogue-appendices)
- [11. Proposed implementation plan](#11-proposed-implementation-plan)
- [12. Decisions needed from you](#12-decisions-needed-from-you)
- [13. What this audit did not cover](#13-what-this-audit-did-not-cover)

## 1. What this audit is

**Method.** Nine reviewers read the source in disjoint areas and wrote down what they found, each row with the file and line they opened: configuration and defaults, generation, design rules and warnings, written outputs, imports and the command line, editing and change control, and the two halves of the GUI. A ninth reviewer tested your 14 requirements against the running tool. It generated the `first-steps`, `flatsat`, `small-satellite` and `minimal-satellite` examples and traced 16 real numbers from the exported files back to their inputs, recomputing the numeric ones outside the tool.

**What I checked myself.** Before this page was written I opened the code for the claims that matter most and ran the one behaviour that looked like a defect. Those are marked *(checked)* below. The other findings are as the reviewers reported them, from reading the code; where a reviewer could not confirm something it is marked *unverified* in the appendix.

**Version.** Everything refers to commit `d42f0be` (version 1.11.1). File and line numbers move as the code changes.

**What it is not.** It is not a design for the solution and it is not a judgement of the tool's numbers. Where the tool does something conservative or simplified (a bundle factor from the whole harness, a doubled voltage drop) the audit says that it is hidden or fixed, not that it is wrong. The few places where behaviour looks inconsistent are listed separately in [section 9](#9-defects-and-inconsistencies-found).

**Reading the IDs.** A row such as `GEN-C1-046` is area `GEN`, category `C1`, number 46, in the appendix for that area. The categories follow your request: C1 hard-coded constants, defaults, margins, thresholds and rules; C2 hidden assumptions; C3 outputs shown without their derivation; C4 places where the user is forced into one option; C5 input and output exchanged with other tools or files, including implicit ones; C6 customisation that exists today. The tags `[SYS]`, `[ELEC]` and `[AIT]` say who is hit hardest: the systems engineer, the electrical engineer, or the AIT (assembly, integration and test) engineer.

## 2. The people it is for

The tool has two roles today: **Systems engineer** and **Electrical / AIT engineer**. The audit looks at three kinds of user, because they ask different questions of the same number.

| User | What they must be able to defend | Typical numbers |
| --- | --- | --- |
| Systems engineer `[SYS]` | That the harness architecture follows the requirements and the interfaces | Which interface is in which harness, which connector, mass and length totals, release state |
| Electrical engineer `[ELEC]` | That every wire and contact carries its current and meets drop, shielding and EMC rules | Gauge, derating and bundle factor, voltage drop, contact current, shield termination, EMC class |
| AIT engineer `[AIT]` | That the harness can be built and tested exactly as the sheets say | Cut length, strip length, contact and crimp tool, label text, test limits, "Ready to build" |

The two roles of the program do not match this split: the electrical and AIT engineer share one role, and the Systems role hides 42 menu entries, among them the engineering values and most imports (GUI2-C4-014, GUI2-C1-046). Whether that is right is a question for the plan, not a finding.

## 3. The short version

1. **The tool already records numbers, but not equations.** The Why tab and the findings say "AWG 24 carries 1.08 A derated (factor 0.54) for 0.8 A" and "voltage drop 0.458359 V, limit 1 V". None of them shows the equation, the temperature, the bundle factor, the resistivity, the length used or the configuration key behind the number. In the trace test the reviewer's estimates for the sixteen numbers ran from 3 to 25 minutes, never under a minute, and the numeric ones could be reproduced only by reading the configuration files or the code (section 8).
2. **Several outputs have no derivation at all.** Wire length, mass, the bill of materials, colour, shield ends, labels, test limits, the "Ready to build" status and the choice of a connector have no Why line (GEN-C3-001, OUT-C2-001, REQ).
3. **A lot is hard-coded.** The audit lists 429 constants, defaults and rules. Many are in code and not in any configuration file: the two-conductor round trip of the voltage drop, the bundle factor counting every wire of the harness, two service loops added to every length, first-fit pin placement, the four checks behind "Ready to build", the label and test formats (*checked* for the service loop, section 5).
4. **The configuration files are plain JSON with no comments, units or sources.** Seven files per project; units only as key-name suffixes; one yes/no per file for "reviewed". Invalid values are caught by some commands and not by others (*checked*, section 9).
5. **Overrides exist but are blunt and unrecorded.** Editing a wire's length, colour, gauge or part sets a single lock that freezes all four. A locked wire is not resized or rechecked and carries no reason, author or date (EDIT-C1-046, GEN-C1-046).
6. **There is no change history for edits.** Only review, release and new-revision are logged; `by` is a typed name and `when` a date without time. Waivers, part approvals and configuration edits record neither author nor date. Undo is in memory (EDIT, GUI1, GUI2).
7. **Errors cannot be waived, and a waiver is tied to the finding text.** There is no recorded-deviation path for a justified exception on wire current, voltage drop, contact current or mating (DRC-C4-001, *checked*).
8. **Exports carry a hash of the configuration, not the configuration.** The tool version and model hash are in every file; the values behind derating, resistivity, margins and test limits are not (`export.json` has no configuration at all). A colleague cannot reproduce a result from the exported files alone (OUT-C2-016, IO-C2-017).
9. **Imports leave no trace of their source.** Only the parts import remembers a file name. No import records a hash or detects that its source changed. Units on import are fixed (millimetres, grams) and some conversions are silent (IO, GUI2). The tool's own CSV exports cannot be read back by three of its importers.
10. **The core is scriptable but undocumented, and not extensible.** The calculation code has no Qt and can be called from Python, but there is no documented API, no JSON output and no way to explain a number from the command line. The rules are a code tuple; nothing can be added without editing the core (REQ, DRC-C4-003).
11. **One hidden engineering input sits in the GUI layer.** Dragging a device box on the canvas rewrites the device's zone when the box lands in another zone, and the zone decides how interfaces are grouped into harnesses in the per-zone-pair mode. The user sees a toast; the Zone field is read-only (GUI1-C1-002, *checked*).
12. **The AIT side is the least traceable.** Cut length has no stated basis, strip lengths, contacts and tools are typed in and never derived or checked, the build workbook is write-only (results typed into it are never read back) and has no fields for as-built data, serial or lot numbers (OUT, GEN, GUI1).

Of your 14 requirements, none is fully met, 13 are partly met and one (a plugin or registry pattern, R13) is missing. The definition of done fails on tracing a number in under a minute and is partly met on the other three tests (section 7).

## 4. What already works and should be kept

A plan should build on these, not replace them.

- **The Why mechanism records real numbers** with units, stored in `generated/generation.json` and shown in the Why tab for a unit, interface, harness, wire, connector or pin (`core/generate/explain.py`, `core/why.py`, `gui/why_panel.py`). It is the natural base for an Explain view.
- **Findings state the result and the limit.** "Wire W001-001 (AWG 24) carries 0.8 A but allows 0.54 A after derating" (R12 partly met). Every rule has a fixed *why*, *how*, severity and requirement IDs (`core/drc/base.py`, `docs/RULES.md`).
- **"Pending", "not checked" and "to fill in" instead of silent defaults.** A missing value is named by its configuration key and travels into "Ready to build" and into the check report. The `first-steps` trace was the best-explained case.
- **Configuration is already outside the code for the main engineering values.** Seven JSON files per project, validated against ranges, with a form (the Engineering values dialog: unit, hint, what it is for, where it is used, placeholder switch), a `config` command, ECSS profiles and a `schema` command that writes JSON Schemas. They are shared through Git.
- **Provenance exists.** Every CSV has a stamp line with tool version and model hash; `provenance.json` lists the configuration hashes, library and counts; `manifest.json` lists a SHA-256 for every file; `generation.json` keeps the input hash and generator version. The missing timestamp is deliberate (determinism, `core/outputs/provenance.py`).
- **The tool is deterministic.** The same design gives byte-identical files. This is a strength a transparency feature must not break (see decision 1 in section 12).
- **The independent output verifier** re-implements the written tables, so a coding error in a writer shows up.
- **Overrides are kept at regeneration** and noted with an `override:` line; a hand edit is rechecked by the design rules.
- **A documented command line** of 29 commands with exit codes, and a core without Qt.

## 5. Findings by principle

### 5.1 Glass box, not black box (R1, R5, R12)

- **Equations and constants are not visible to a user.** The voltage-drop equation `I·ρ·L/A·n`, the AWG-to-area formula and the combination of bundle and temperature factors appear in no document or GUI text. They exist only in `core/generate/sizing.py:39-40`, `core/units.py:8-17` and the rule code (REQ trace rows 1 and 2; GEN-C3-001; DRC-C3-001). `[ELEC]`
- **The gauge note shows only the combined factor**, not base ampacity, bundle factor and temperature factor. The citation "Table 6-41" is written even when the user supplied their own bundle table (GEN-C3-004; section 9). `[ELEC]`
- **Finding statements round silently.** `:g`, `:.3g` and `:.0%` formats mean a failing drop can print equal to its limit, and a spare-pin fraction is rounded without the required count (DRC-C1-008, C1-009). `[ELEC]`
- **The Checks and Problems panels show a sentence plus requirement IDs.** No structured actual value, limit, margin or equation; the clause IDs are never resolved to a clause title (GUI2-C3-001, C3-002; DRC-C3-006). In the flatsat command-line run the findings carried no numbers at all. `[ELEC]`
- **Wire length has no stated basis.** Every "Length (m)" is either an entered value, the sum of the harness segments, or that sum plus two service loops; the table does not say which. A wire with two possible routes silently gets no length. The cut list shows each conductor at full length while the BOM divides by the conductor count (OUT-C2-001, OUT-C2-003, GUI1-C2-004). `[AIT]`
- **Units are mostly written, with exceptions.** Headers carry units and configuration keys carry unit suffixes. AWG is shown without mm² although the specification asks for both; `format_awg` exists and is never called. Why lines show dimensionless factors ("factor 0.54") unlabelled (REQ R5; section 9). `[ELEC]`

### 5.2 Nothing hidden, nothing hard-coded (R2, R3, R4)

- **Hard-coded engineering assumptions, with no assumptions panel.** The two-conductor round trip, a bundle factor that counts every wire of the harness (including unloaded and signal wires) with L fixed at 1, a temperature factor that is one typed number unrelated to the ambient temperature or to any wire rating, one ampacity table by AWG only, gauge chosen as the smallest AWG that passes and then upsized for drop, first-fit pin placement in pin-list order, adjacency assumed equal to list neighbours. (GEN-C1-011, C1-012, C2-002; CFG-C1-005, C2-004, C2-005; DRC-C1-004, C1-013). `[ELEC]`
- **The voltage drop** assumes DC, a solid conductor, an equal-gauge return and no temperature or contact resistance. It is hard-coded in the rule and duplicated in the generator, and the limit is absolute volts (DRC-C1-004, GEN-C1-012). `[ELEC]`
- **Service loop and lengths.** *(checked)* A wire's length is the harness path length plus `2 × service_loop_m`; an unset loop is a placeholder of 0 with only a generation note (`core/generate/engine.py:661-692`). There is no cut tolerance, strip allowance or twist take-up (GEN-C1-013). `[AIT]`
- **Mass** is per library part, not per gauge, so one part per construction cannot follow gauge; contacts, backshells, sleeving and accessories are excluded; unknown data gives `0` with only a `Complete: no` hint (CFG-C2-008, OUT-C1-012). `[SYS][ELEC]`
- **"Ready to build"** is decided by four fixed checks and ignores DRC errors, release state, strip lengths, terminations and test limits; the definition is not shown on the sheet (OUT-C1-022, OUT-C4-006). `[AIT]`
- **Test limits** are three global numbers (continuity, isolation, test voltage), with no link to length, gauge or a source standard, and show as "TBD (placeholder)" until set (CFG-C1-017, OUT-C1-015/016). `[AIT]`
- **Configuration files** have no comments, no per-key units or sources, sorted rather than logical key order, and review state as one boolean per file (CFG-C1-022, C2-020). The Engineering values dialog has 28 keys; some keys in `docs/CONFIG.md` are not in the form; dimensionless factors have no unit or range in the form (GUI2-C1-025, C2-007).
- **Model choices are almost never selectable.** The only real choice of method is the segmentation mode (three values), and the Why text mentions it only as a consequence, not as "Method: per_zone_pair". There is no alternative for wire sizing, the voltage-drop model, the mass model, pin allocation, the length model or the derating method (REQ R4).
- **Build data is free text or closed lists.** Contact size is free text; termination is a closed list (crimp, solder, unspecified); unknown wire colours are cut to six characters; strip lengths, contacts and crimp tools are typed or imported and never derived or checked (CFG-C4-003, GUI1-C2-005, EDIT-C1-047). `[AIT]`

### 5.3 The engineer stays in control (R7, R8)

- **One lock for four values.** Editing a wire's gauge, part, colour or length sets `Wire.locked`; derating is then never recomputed for that wire, and the DRC skips the contact-overload check for locked wires. The only flags are a "Locked" column and chip, with no reason, author or date. In the output files a manual and a generated length cannot be told apart (GEN-C1-046, EDIT-C1-046, OUT-C5-018). `[ELEC][AIT]`
- **No change history for edits.** *(checked)* Only review, release and new-revision are logged. A design edit has no who, when, old value, new value or reason; waivers and part approvals have no author or date; configuration edits are not logged; undo is in memory, label-only, 200 steps (EDIT-C1-013, C2-022; CFG-C2-021).
- **A release freezes only some of the configuration.** `service_loop_m` (added twice to every length), `default_gauge_awg` and `wire_part_by_construction` are not frozen or recorded, so a released length list cannot be reproduced from its baseline. `Baseline.content_hash` is written and shown in a diff but not compared anywhere *(checked)*, and the release gate ignores approval of contacts and accessories, strip lengths, contact assignment and test limits (EDIT-C1-017, C1-022, C1-009, C1-010). `[ELEC][AIT]`
- **Errors cannot be waived.** *(checked)* `waivable` defaults to warnings only and no rule sets it. Severity is hard-wired; an error blocks a release; a released harness, its baseline and its log are immutable, so a typo can only be fixed in a new revision (DRC-C4-001, EDIT-C4-001/002).
- **A waiver is a 12-character hash of the rule and the finding title** (since 1.11.0), with no author, date, scope or expiry. A new tool version that rewords a finding voids it (DRC-C1-034, C1-035). `[SYS]`
- **Inferences are silent.** Pin direction and role are inferred from signal names and interface types; the pin table shows a note but not the derivation; a mistyped name counts as a plain signal (EDIT-C2-007). The device templates choose a Micro-D size from the number of interface types, and starter interface types encode construction choices marked only "unverified" (CFG-C1-077, C1-092). `[ELEC]`
- **A drag changes the model.** *(checked)* Moving a device box can rewrite its zone and so the harness grouping (GUI1-C1-002). It also changes the model hash stamped on every export (GUI1-C1-003). `[SYS][ELEC][AIT]`

### 5.4 Progressive disclosure and workflow (R6)

- **The workflow exists twice** (a three-step top bar and a six-step page) and neither says what each step consumes and produces (GUI2-C1-010, C3-008).
- **The "Passed" count includes rules that passed on placeholder values**, the Next step page moves on with unchecked rules, and the Systems role hides the pending-values link, so a green strip can rest on unreviewed numbers (GUI2-C2-002, C2-003). `[ELEC][SYS]`
- **Intermediate results of generation are not inspectable or editable** except through files: per-wire sizing candidates, segmentation groups, skipped interfaces, the voltage drop per wire (REQ R6, R10).
- **Build data is spread over six places** in the GUI, and `import-build-data` (strip lengths, contacts, crimp tools) exists only on the command line (GUI1-C2-005, GUI2-C4-011). `[AIT]`

### 5.5 Data exchange, provenance, openness (R9, R10, R11, R13, R14)

- **Provenance has no timestamp, operator, configuration values or imported-file list**; the configuration appears only as a 16-hex hash per file; workbook dates are pinned to 2000-01-01 (OUT-C2-016, IO-C2-017/018). The export dialog shows a 12-character design hash only (GUI2-C1-020).
- **Open data is partial.** 88 files per flatsat export, but not the sizing candidates, segmentation groups, DRC by-rule results with actual and limit, the readiness checks, the Why reasons, the configuration values, derived lengths, mass, BOM or findings as JSON (OUT-C5-004, REQ R10).
- **Exports are altered for other tools and cannot be re-imported.** CSVs start with a `#` stamp line and prefix `+`, `-`, `=` and `@` cells with an apostrophe; the lengths, build-data and parts readers do not skip the stamp line (IO-C1-057, IO-C2-021/022; the pinout reader does).
- **Imports drop and assume.** The parts import has no field for contact current or voltage and drops unmapped columns without a warning. KiCad import discards pin type, source and footprint and merges same-named nets from different sheets. Strip and accessory lengths are always millimetres, mass is assumed in grams, a comma becomes a decimal point ("1,234" is read as 1.234), and `import-lengths` reads columns by position with a millimetre default and does not echo the resulting metres (IO-C1-012, C1-037/038, C2-005/006; REQ B7). `[ELEC][AIT]`
- **The ampacity table loader stores no conditions, source or date** (IO-C1-041).
- **No import detects that its source changed** (R14): no file name, time or hash for pinouts, lengths, strips, contacts, netlists or devices (IO-C5, IO-C4-010).
- **Scripting.** No JSON output, no output-folder option and no documented Python API; no command explains a number (IO-C4-001/002, REQ R11).
- **Extensibility.** The rules are a code tuple (`core/drc/rules.py`), the rule status table duplicates rule logic, the output list is hard-wired, there are no entry points; only data (parts, interface types, wire part by construction) is user-extensible (DRC-C4-003, OUT-C4-007, REQ R13).

## 6. The 14 requirements: where the tool stands

| Req | Status | What exists | Main gap | Gap larger for |
| --- | --- | --- | --- | --- |
| R1 Explain view | partial | Why tab for unit, interface, harness, wire, connector, pin; stored lines with numbers | No equation, constants or source; none for length, mass, BOM, colour, shield ends, labels, test limits, readiness, connector choice, the derivation of a rule limit; no command-line explain | `[ELEC]` |
| R2 Assumptions panel | partial | Engineering values dialog and `config` command for configuration values | Only values in config files; hard-coded model choices are not listed; no "assumptions active in this analysis"; fallbacks used when a value is unset are not listed | `[ELEC]` |
| R3 Externalised configuration | partial | Seven JSON files per project, ranges validated, ECSS profiles, JSON Schemas, shared by Git | No comments, units or sources in the files; model constants still in code | `[ELEC][AIT]` |
| R4 Selectable models | partial | Segmentation mode; single factor or bundle table; shield concept; naming patterns | No alternatives for sizing, drop, mass, length, pin allocation, readiness; the active choice is not shown | `[ELEC]` |
| R5 Units everywhere | partial | Unit in CSV headers, keys and rule sentences | No mm² beside AWG; dimensionless factors unlabelled; import units fixed and partly silent; `export.json` has fields without units | `[ELEC][AIT]` |
| R6 Workflow visibility | partial | Top bar, Next step page, outputs list, stale detection, "Used in" | No consumes/produces per step; intermediates not inspectable or editable | `[AIT]` |
| R7 Overrides | partial | Wire, pin and connector locks kept at regeneration; DRC rechecks; waivers need a reason | One lock for four values; no reason, author or date; not flagged in exports; errors cannot be waived | `[ELEC][AIT]` |
| R8 Change history | partial | Change log for review, release and revision; baselines; Git | Nothing for edits, configuration or overrides between releases; no old/new; no time of day | `[SYS]` |
| R9 Provenance | partial | Stamp line, `provenance.json`, `manifest.json`, `input_hash` | No timestamp (deliberate), no configuration values, no operator, no imports; `export.json` has no configuration | `[ELEC]` |
| R10 Open data | partial | 88 files per export, `export.json` of the model | Intermediates, configuration, derived lengths, mass, BOM and findings not in JSON | `[ELEC]` |
| R11 Scriptable | partial | 29 documented commands; core without Qt | No documented Python API, no JSON output, no explain command | `[SYS]` |
| R12 Explainable warnings | partial | why, how, severity, requirement IDs; actual and limit in the text | One fixed sentence per rule; no derivation, no configuration key, no override path | `[ELEC]` |
| R13 Extensibility | missing | Data extensibility (parts, interface types) | No registry or entry points for rules, models, outputs, importers | `[ELEC]` |
| R14 Visible data links | partial | Pin-to-pin links; library source typed by hand; stale-generation flag | No source, time or hash for imports; no source-changed flag | all |

## 7. The definition of done, tested today

| Test | Verdict | Systems | Electrical | AIT |
| --- | --- | --- | --- | --- |
| (a) Trace any number to its inputs and logic in under a minute | **Fails** | "Which harness and why" takes about 8 minutes; connector and pin choice stop at the code | Gauge and drop need configuration and code: 12 to 25 minutes | Cut length, BOM metres and labels are not traced at all; "Ready to build" and the test-limit source take 4 to 5 minutes |
| (b) Change any assumption, constant, margin or rule without editing code | Partly | Segmentation mode, naming, EMC pairs, grounding concept: yes. Connector and pin strategy, method choice: no | Ampacity, derating, resistivity, drop limit, service loop: yes. The round trip, the bundle-size definition, the factor lookup: no | Test limits, strip lengths, contacts: yes. Label format, cut order, the blocking set of "Ready to build", cut allowance: no |
| (c) Reproduce a colleague's result from an exported file | Partly | Only with the whole project folder (model hash, `verify --outputs`); the export alone cannot be loaded | Same; the colleague's ampacity table is unknowable from the export (a 16-hex hash only) | The workbook holds what a builder needs and shows version and hash; it cannot be checked against the design |
| (d) Explain the result in a design review without "the tool computed it" | Partly | Segmentation and standard-based rules: yes (requirement IDs, clauses) | Gauge: only after reading the code ("why 0.6?" is only the user's own number) | Cut length: "because the tool sums the segments and adds a loop" is the best answer today |

The gap differs by persona. Test (a) is worst for electrical engineers because the equations are in code only; (b) is worst for AIT engineers because the output layout and the readiness logic are not configurable; (c) is worst for electrical engineers because the values behind derating are not in the export; (d) is best for systems engineers because the rules are requirement-driven.

## 8. The trace test: 16 real numbers

The reviewer traced each number using only what a user has (GUI texts, output files, documents, the command line, the configuration files) and recomputed the numeric ones outside the tool. **All numeric results matched.** The trail is reproducible but not visible.

| # | User | Number or decision | How far | Where it ends | Minutes |
| --- | --- | --- | --- | --- | --- |
| 1 | `[ELEC]` | Gauge AWG 24 and the derating factor 0.54 of wire `W001-001` | Part | Factor found only by reading `config/derating.json` (0.6 × 0.9); no document gives the rule | 12 (GUI) or 20 (files only) |
| 2 | `[ELEC]` | Voltage drop 0.458359 V | Part | `I·ρ·L/A·n` and the AWG area formula are in code only; "2 conductors" is a hard-coded round trip | 25 |
| 3 | `[AIT]` | Cut length 3.45 m | Part | Equals segments 3.25 m plus 2 × 0.1 m loop; nothing in a Why line or a document links them | 20 |
| 4 | `[SYS][AIT]` | BOM metres 165.2 and 82.2 | Part | Reproducible only by summing the wire lists yourself; no pointer from a BOM line to wires | 15 |
| 5 | `[SYS]` | Mass 2045.6 g, 2250.16 g with margin | Full | Recomputed from library masses and the 10 % margin; the library values are example data | 15 |
| 6 | `[SYS]` | Why interfaces IF-010 to IF-018 share harness W001 | Full for "which and why" | The Why line does not name the mode or the zones | 8 |
| 7 | `[SYS][ELEC]` | Why PWR is on pin 1 and RTN on pin 2 | Part | Says why grouped, not why pin 1 (first free block) | 10 |
| 8 | `[SYS]` | Why connector `PDU2-J02` was chosen | Stops | No reason is recorded for the choice, only that it is unconfirmed | 10 |
| 9 | `[ELEC]` | A current finding "carries 0.8 A but allows 0.54 A" | Part | 0.54 only from configuration; the clause text is in a separate file | 8 |
| 10 | `[ELEC]` | EMC class and the mixed-class finding | Full | Nothing hidden: all classes are unset in the example | 5 |
| 11 | `[ELEC]` | Shield termination of `W001-S1` | Part | No Why line for a shield group; values from the grounding concept | 10 |
| 12 | `[AIT]` | Strip length, contact and crimp tool | Not computed | By design typed in; the contact library in the example is empty | 3 |
| 13 | `[AIT]` | Label text of a wire | Part | Format only in code, not configurable, not described | 8 |
| 14 | `[AIT]` | Test limits 1 Ω, 100 MΩ, 500 V | Full for source, stops at reason | One flat limit; no link to length or gauge, no source standard | 4 |
| 15 | `[AIT][SYS]` | "Ready to build" | Full by logic | Rule list only in code and one sentence of the output reference | 5 |
| 16 | `[SYS]` | Gauge "pending" and mass 0 in `first-steps` | Full | Best-explained case: missing values named by configuration key | 3 |

Three numbers were fully traceable, eleven reproducible only through configuration or code, and two stopped at a choice made in code. The reviewer's estimates (an experienced engineer who did not build the tool, using only what a user has) run from 3 to 25 minutes; only the two cases where the tool names the missing value (#16) or the configuration key (#12, #14) were quick, and no number was traced in under a minute.

## 9. Defects and inconsistencies found

Nothing here changes a number silently in the shipped examples. None has been fixed: Phase 0 is read-only. Under your constraint, a fix that changes a result will be recorded in `docs/changes.md` with before and after values, and only after you agree.

| # | Observation | Verified | Impact |
| --- | --- | --- | --- |
| D1 | **`validate` accepts an invalid configuration value that `generate`, `drc` and `config` reject.** With `bundle_derating` set to 1.5 in `config/derating.json`, `validate` prints "0 error(s)" and exits 0; `generate` stops with `config_invalid: bundle_derating must be a number above 0 and at most 1`; `config` shows it INVALID; `drc` exits 1. `docs/CONFIG.md` says `validate` uses the same checks. | Reproduced by the lead | A user who validates first is told the project is clean (`[ELEC]`) |
| D2 | AWG is never shown with mm² although `docs/SPEC.md` says it should be; `format_awg` exists and only a test calls it | Reviewer, code | Low; requirement R5 |
| D3 | Gauge and wire part are decoupled: AWG 16 and AWG 26 wires both become `EX-WIRE-SINGLE` with one BOM line and one mass per metre, so a procurement list cannot be built by gauge | Reviewer, outputs | Medium (`[SYS][AIT]`) |
| D4 | The sizing note always cites "Table 6-41", also when the user supplied their own bundle table | Reviewer, `core/generate/sizing.py:126` | Low |
| D5 | A "shield group" is created for unshielded twisted power pairs and shown in the wire list as if it were shielded | Reviewer | Low, presentation |
| D6 | "Ready to build: yes" while every wire lacks a strip length and 36 pins lack a termination or contact (documented as a note only) | Reviewer | Medium, policy (`[AIT]`) |
| D7 | The voltage drop of a power pair assumes the return has the same gauge and length (n=2); a return of another gauge would give a wrong round trip | Reviewer, code | Low, not reachable in generated examples |
| D8 | `import-lengths` converts silently: a bare `5.0` became 0.005 m with "row 2: OK"; the unit default is millimetres, documented, but the metres are not echoed | Reviewer, run | Medium, a unit trap (`[AIT]`) |
| D9 | With the ECSS profile, generation aborts when one wire has no gauge that carries its current, instead of leaving it pending; and the flat bundle factor comes from all wires of the harness (26 to 50 wires gave K 0.29) | Reviewer, run | Medium, restrictive |
| D10 | Text in numeric columns (`pending` in AWG, `0` for unknown mass, `0 m` for unknown BOM length) | Reviewer | Low |
| D11 | A hand-set gauge outside the ampacity table (28 AWG) is checked for voltage drop but skips the current check with only an info note, so it can pass | Reviewer, run | Low (`[ELEC]`) |
| D12 | `placeholders_used` lists all six placeholder files for every object | Reviewer | Low |
| D13 | The shipped `quad` maps to a two-conductor part, so a quad counts two pairs in BOM and mass (documented in D-188 as a known limit) | Known | Assumption to expose, not a new defect |

## 10. The catalogue (appendices)

The full row-level catalogue, with the file and line of every finding, is in nine appendix pages. 1,112 rows in the eight code areas.

| Appendix | Area | C1 | C2 | C3 | C4 | C5 | C6 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [A. Configuration and defaults](transparency_audit/configuration-and-defaults.md) | model, config, starter data | 64 | 24 | 9 | 13 | 10 | 14 |
| [B. Generation](transparency_audit/generation.md) | sizing, lengths, mass, segmentation, pins | 61 | 20 | 15 | 20 | 10 | list |
| [C. Rules and warnings](transparency_audit/rules-and-warnings.md) | the 39 design rules, checks, waivers | 52 | 21 | 16 | 15 | 13 | 12 |
| [D. Written outputs](transparency_audit/outputs.md) | tables, build workbook, labels, provenance | 62 | 28 | 22 | 16 | 20 | 14 |
| [E. Interchange and command line](transparency_audit/interchange-and-cli.md) | imports, exports, file formats, commands | 64 | 33 | 14 | 21 | 23 | 16 |
| [F. Editing and change control](transparency_audit/editing-and-change-control.md) | overrides, history, release | 47 | 22 | 13 | 16 | 10 | 20 |
| [G. GUI: work screens](transparency_audit/gui-work-screens.md) | canvas, Devices, Inspector, Why | 32 | 18 | 16 | 16 | 14 | 14 |
| [H. GUI: dialogs and workflow](transparency_audit/gui-dialogs-and-workflow.md) | checks, export, import, settings, roles | 47 | 25 | 20 | 20 | 20 | 20 |
| [I. Requirements and trace test](transparency_audit/requirements-and-trace-test.md) | R1 to R14, the 16 traces, documents, defects | | | | | | |

Rows tagged `[ELEC]` or `[AIT]` in these pages are the ones that matter to electrical and AIT engineers. Paths that begin with `work/` in the appendices are scratch projects the reviewers made while auditing; they are not in the repository, and the commands that make them are named beside them.

## 11. Proposed implementation plan

This is a proposal for your review, not a commitment. It is ordered by value and by risk.

**Rules for every step** (from your constraints and from the tool's own rules):

- **Regression first.** Before a refactor, add tests that capture today's numbers: gauge, derating, drop, length, mass, BOM, test limits, readiness, labels and findings, on all shipped examples *and* on variants (a hand override, a locked wire, the ECSS profile, a placeholder-free configuration). The existing output-hash baseline covers the shipped examples only.
- **Numbers do not change** unless a defect is found. A defect is recorded in `docs/changes.md` with before and after values and fixed only with your agreement, one at a time.
- **Written files stay byte-identical** for a project that does not use a new feature (new fields are sparse and optional, as in 1.8 to 1.11). Where a step must change written files on purpose (provenance, JSON export), the baseline is renewed deliberately, with a documented reason, as before.
- **One feature area at a time**, working software and passing tests after each step, one release per step or two, each prepared and published the way 1.11.0 and 1.11.1 were.
- **The default screen stays clean.** Transparency is one click away: an Explain button, an Assumptions page, a flag you can open.
- **Model documentation in `docs/models/`**, aimed at engineers, written with each step and tied to a test so that no registered model or rule is left undocumented.

| Step | Work | Covers | Size | Risk | Depends on |
| --- | --- | --- | --- | --- | --- |
| **WP0** | **Safety net.** Number-capturing regression tests; `docs/changes.md`; fix D1 (`validate` runs the configuration check) and D4 (citation) with your approval; decide D2 and D8 | Constraints | S | Low | none |
| **WP1** | **Derivations.** A structured derivation record (quantity, value, unit, equation, inputs with units and source, intermediates, assumptions used, reference). Start with wire sizing (ampacity, bundle and temperature factors, drop) and the DRC limits so a finding carries actual, limit, margin and the equation; then length, mass, BOM, readiness, test limits, labels. Shown in an Explain view (Why tab, one click) and a command-line `explain`; stored in JSON; text outputs unchanged at first | R1, R12, R5 | L | Medium | WP0 |
| **WP2** | **Constants and assumptions registry.** One named, documented registry of every model constant now in code (round trip, service loop count, K rule, first-fit order, readiness checks, label and test formats, rounding), each with value, unit, description, source and default equal to today's number; moved into the configuration; an Assumptions page that lists what is active in the current analysis, including fallbacks used for unset values | R2, R3 | L | Medium | WP0, WP1 |
| **WP3** | **Selectable models.** Alternatives behind selectors whose default is today's behaviour: bundle-factor definition (whole harness, per bundle, loaded wires), voltage-drop model, length model (service loop, cut and strip allowance, twist take-up), mass model, pin allocation strategy, readiness policy. The active choice is recorded and displayed | R4 | L | Medium to high | WP2 |
| **WP4** | **Overrides and history.** Per-field overrides (field, value, reason, author, time) instead of one lock; flagged in every view and export; re-validate and explain consequences; an append-only change journal for inputs, configuration and overrides (who, when, old, new, reason); freeze every generation key at release; author and date on waivers and approvals; a recorded-deviation path for errors if you decide so | R7, R8 | L | High (file format) | WP0, WP2 |
| **WP5** | **Provenance and open data.** Provenance that carries the configuration values, tool version, operator and imported-file list; JSON and CSV for every intermediate and final result (sizing table, segmentation groups, rule results with actual and limit, readiness checks, derived lengths, mass, BOM, findings); exports the tool can read back; a timestamp handled without breaking determinism (decision 1) | R9, R10 | M | Medium (renews the baseline) | WP1, WP2 |
| **WP6** | **Data links.** An import record (source file, hash, time, rows read and dropped, unit assumed, values converted) kept in the project; a "source changed" flag; the parts import gets ratings; KiCad import keeps pin type and source; explicit units on import and an echo of converted values | R14, R5 | M | Medium | WP0 |
| **WP7** | **Scriptable core.** A documented, stable Python API over the existing core (load, generate, check, explain, export), `--json` and an output folder on the commands, worked examples for batches and trade studies | R11 | M | Low | WP1 |
| **WP8** | **Extensibility.** A registry for rules, models, output tables and importers with discovery by Python entry points and an opt-in project plug-in folder; every plug-in's name and version recorded in provenance | R13 | L | High (code loading) | WP2, WP3, WP7, decision 5 |
| **WP9** | **Models documentation.** `docs/models/` for every model, rule and assumption, seeded from `RULES.md`, `CONFIG.md` and the derivation records | Constraint | M | Low | grows with WP1 to WP3 |
| **WP10** | **Workflow and the two roles.** What each step consumes and produces; inspect and edit intermediates; as-built, serial, lot and result capture for AIT (the workbook is write-only today); whether Electrical and AIT stay one role | R6 | M to L | Medium | WP1, WP4, decision 6 |

**Proposed order of delivery.** WP0, then WP1 for sizing and DRC (the largest gain for electrical engineers and the base for everything else), then WP5 and WP2 in parallel with WP9, then WP4, WP6, WP7, WP3, WP10, and WP8 last, because it depends on stable interfaces. A first release could carry WP0, the sizing part of WP1 and the first part of WP5; none of it changes a number.

**Quick wins that need no design decision:** D1, D4, an echo of converted metres on `import-lengths`, mm² beside AWG (once you decide D2), a skip of the `#` stamp line in the three readers, a warning for dropped import columns, and showing the method and zones in the segmentation Why line.

## 12. Decisions needed from you

These decide the shape of Phase 1. I have marked what I would recommend.

1. **Determinism and the timestamp (R9).** The tool promises byte-identical files from the same design. A timestamp breaks that. Options: (a) put the timestamp and operator in a separate run record that is outside the hash and the baseline; (b) make them opt-in; (c) do not record them. *I recommend (a).*
2. **Format of the configuration files (R3).** JSON cannot carry comments. Options: keep JSON and add `description`, `unit` and `source` fields per key (no new dependency, already validated by schemas); move to YAML with comments (a new dependency, a migration); allow commented JSON. *I recommend keeping JSON with per-key metadata.*
3. **Errors and deviations (R7).** Today an error cannot be waived and blocks a release. Should an error be able to carry a recorded deviation (reason, author, date, approval, expiry) that keeps it visible but lets a release proceed? Which rules, if any, must stay absolute? *I recommend yes for the electrical rules, with the deviation shown on every output.*
4. **Defaults that look conservative or simplified.** Keep today's behaviour as the default and make it visible and selectable (my recommendation), or change any default? Changing a default changes numbers and needs your approval case by case.
5. **Plug-ins and executing code (R13).** The tool is internal and offline. May a project load user Python code (entry points and a project plug-in folder, with a clear trust prompt)? Or should extension be data-only (declarative rules and tables) first? *I recommend declarative rules first and Python entry points second, both opt-in.*
6. **The audiences and roles (R6).** Should Electrical and AIT become two roles? Is capturing as-built data, serial and lot numbers and measured test results back into the tool in scope, or does the workbook stay a print-and-sign document?
7. **File format changes.** Steps WP4 to WP6 add fields and files. Are you content with a schema-version bump and migration where needed, keeping projects that do not use a feature byte-identical, as in 1.8 to 1.11?
8. **Release cadence.** One release per work package, or fewer, larger ones?
9. **Standards references (R1).** The explanations can cite a standard and clause by ID and title, but the tool cannot ship the standard's text. Is citing IDs and titles enough, with the text left to the reader's own copy?
10. **Priority.** Is the order in section 11 right for your teams? Which numbers do the electrical and AIT engineers complain about first?

## 13. What this audit did not cover

- Code was read, not exercised, except for the hands-on trace test and a few runs. Parts of the GUI layer (painting code in the canvas, the Properties panel, some dialogs, the tour and the command palette) were skimmed or only searched. Rows say *unverified* where a reviewer could not confirm.
- The reviewers did not open every rule's internals or the compliance requirement texts, and did not run the application on a display. Nobody has watched the GUI on a real display; GUI findings come from the code and from the strings the program shows.
- Behaviour that depends on the user's operating system, Git setup or the Qt version was not tested.
- The audit does not rank the findings by how often a team would meet them: that is for you and your engineers.
- Some line numbers will drift as the code changes.

Next: [the catalogue, appendix A](transparency_audit/configuration-and-defaults.md), [the requirements and the trace test, appendix I](transparency_audit/requirements-and-trace-test.md), [the decisions already taken](DECISIONS.md)
