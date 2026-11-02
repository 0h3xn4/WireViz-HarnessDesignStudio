# Transparency audit, appendix C: rules and warnings

This page is appendix C of the [transparency audit](../transparency_audit.md): the row-level catalogue for the 39 design rules, their thresholds, their finding texts and the waiver mechanism. Each row names the file and line the reviewer opened. IDs read `DRC-C<category>-<number>`; the categories and the tags `[SYS]`, `[ELEC]` and `[AIT]` are explained in section 1 of the audit. Paths beginning with `work/` are scratch projects the reviewer made while auditing; they are not in the repository. Nothing on this page was changed in the code: it is read-only.

## Contents

- [C1 Hard-coded constants, defaults, thresholds, rules](#c1-hard-coded-constants-defaults-thresholds-rules)
- [C2 Hidden assumptions (simplified models, reference systems, implicit rounding, fixed sequences)](#c2-hidden-assumptions-simplified-models-reference-systems-implicit-rounding-fixed-sequences)
- [C3 Outputs shown without their derivation](#c3-outputs-shown-without-their-derivation)
- [C4 Forced single options](#c4-forced-single-options)
- [C5 Inputs and outputs exchanged with other tools or files](#c5-inputs-and-outputs-exchanged-with-other-tools-or-files)
- [C6 Customisation points that DO exist](#c6-customisation-points-that-do-exist)
- [Rules (39 rules plus the dynamic verify-mismatch and 4 logical rules of checks.py)](#rules-39-rules-plus-the-dynamic-verify-mismatch-and-4-logical-rules-of-checkspy)
- [Top findings](#top-findings)

**Scope.** Read in full: core/drc/__init__.py (135), base.py (66), rules.py (842), standard_rules.py (481), by_rule.py (352), report.py (95), worker.py (125); core/checks.py (332), why.py (249), describe.py (384), integrity.py (722), verify.py (400), usedby.py (151), generation_status.py (80). Read for context (partly): core/generate/sizing.py 1-172, core/generate/explain.py (50), core/generate/lengths.py 30-100, core/configcheck.py 20-200 and 450-500, core/standard_profiles.py 1-205, core/model/config.py 25-110, core/model/review.py 19-50, core/model/library.py 15-40, core/units.py 1-21, core/links.py 867-964, core/vcs/release.py 325-470, core/generate/engine.py 925-965, core/outputs/build.py 85-98, cli/main.py 175-260, gui/drc_process.py (175), gui/controller.py 55-100/225-380/940-985/1570-1615, gui/checks_panel.py 1-700, gui/panels.py 800-960, gui/problems_panel.py 30-130. Not read: remaining gui/checks_panel.py (700-955), gui/why_panel.py, core/edit.py (waiver deletion, grep only), compliance/ (requirement text), outputs/verify.py (grep only).

Personas: [SYS] systems engineer, [ELEC] electrical engineer, [AIT] assembly/integration/test engineer.

**How the Checks panel gets its data (answer to the special question).** Edit -> `EditorController._schedule_drc` (1200 ms pause, gui/controller.py:57,303) -> `DrcWorker` QThread (controller.py:63) -> `drc_process.run_check` (gui/drc_process.py:163) -> helper subprocess `python -P -m harness_design_studio.core.drc.worker` (drc_process.py:34), project pickled over pipes in chunks (worker.py:62-80) -> child runs `drc.run(project)` (worker.py:109) -> findings pickled back (1000 per message) -> `controller._drc_raw` -> `controller.findings()` merges `checks.find` (logical rules, in-process) + `drc.apply_waivers` + a synthetic `drc-failed` error (controller.py:268-290) -> `by_rule.run_by_rule` groups findings into pass / fail / not_checked / pending per rule (controller.py:1585-1593) -> `ChecksPanel`/`RuleDetails` (checks_panel.py). Fallbacks: in-thread run if helper dies or after 180 s (drc_process.py:26,172-175), env `HARNESS_DRC_INPROCESS=1` (drc_process.py:27). The Checks panel object table shows only `Finding.title` and the waiver text (checks_panel.py:166-177); the rule's `why`/`how`, requirement text and the threshold in force are NOT shown there (they are in the Problems tooltip/cards, problems_panel.py:65, panels.py:897).

**What the independent verifier (core/verify.py) re-computes.** From the logical layer only (verify.py:1-10): for each interface with a known type, two endpoints and connectors, the set of required end-to-end connections (`expected_connections`, verify.py:75-89: k-th `out` to k-th `in` crosswise, `passive`/`bidir` and leftover directional signals pass straight through); the (end, signal) pair each wire really joins, read from the box-connector pinout (`_wire_connection`, 153-221); missing / duplicated / extra connections; wire label vs signals ("A/B" or "B/A", 224-226); same-pin wires; wire end connector/pin existence; mating box existence (generated harnesses); pin reuse on cable and box side; harness `interfaces` list vs wires (143-149); shield group presence per interface type (229-252); link pairs vs wires (264-323); orphan interface refs (warning); stale outputs via `generation_status` (391-399). It does NOT check gauge, colour, part, length, mass, any derating or any numeric value (docstring line 8). Only its errors reach the DRC, as non-waivable `verify-mismatch`; its warnings (`pin_shared`, `wire_orphan`) are dropped there (drc/__init__.py:64-65).

---

## C1 Hard-coded constants, defaults, thresholds, rules

Format: id | file:line | value or rule | what it does / feeds | unit | visible? | editable? | R | persona

| id | file:line | value / rule | what it does, which output or decision it feeds | unit | visible to user? | editable? | R | who |
|---|---|---|---|---|---|---|---|---|
| DRC-C1-001 | core/drc/base.py:30,35 | `waivable=None -> severity == "warning"` | Only warnings can be waived. No rule sets `waivable` explicitly (grep + read). Every error and info is un-waivable | bool | Waive button appears only for warnings (panels.py:922); no explanation why errors cannot be waived | none (code) | R7,R12,R2 | SYS,ELEC,AIT |
| DRC-C1-002 | core/drc/rules.py:756-842, standard_rules.py:436-481 | `RULES` tuple, 39 rules, fixed severity per rule | Severity (error/warning/info) of each rule is hard-wired; drives release gate (release.py:379-394), Fix-all, to-do counts | enum | Severity column in Checks (checks_panel.py:129) | none | R3,R4,R7,R13 | SYS,ELEC,AIT |
| DRC-C1-003 | core/generate/sizing.py:21-29 | `REL_TOL = 1e-9`; `exceeds()` = over by more than 1e-9 relative | Single comparison for every limit rule (contact, wire, drop, spare, voltage, temperature, bundle). A value 1e-9 over its limit passes | relative | no | none | R1,R5 | ELEC |
| DRC-C1-004 | core/drc/rules.py:385 | `n = 2 if itype.category in ("power","ground") else 1` | Voltage-drop path assumes a return conductor of equal gauge and length for power/ground, one conductor for everything else. Duplicated in generator (engine.py:954) | count | no (title shows only the drop) | none | R2,R4,R1 | ELEC |
| DRC-C1-005 | core/drc/rules.py:380 | `0 <= w.gauge_awg <= 40` | A gauge outside 0..40 yields a finding "not a wire size" instead of a drop calc; same 0..40 in ampacity_table (sizing.py:57), units.py:5 | AWG | title states 0 to 40 | none | R3 | ELEC |
| DRC-C1-006 | core/generate/sizing.py:40, core/units.py:12-17 | `drop = I*rho*L/(A*1e-6)*n`; `A = pi/4*d^2`, `d = 0.127*92^((36-n)/39)` | Voltage-drop model behind rule voltage-drop: DC, circular solid conductor, no stranding factor, no temperature coefficient, no contact/splice resistance | V; ohm m; m; mm2 | no formula shown (title gives only result and limit) | rho, limit via config; formula none | R1,R4,R5 | ELEC |
| DRC-C1-007 | core/drc/rules.py:402 | `f"...fewer than the required {fraction:.0%}"` | spare-pins-low prints required share rounded to whole percent (0.125 prints 12%) and never prints the required pin count. Verified: `f"{0.125:.0%}"` = '12%' | % | in title | rounding none | R5,R12 | ELEC,AIT |
| DRC-C1-008 | core/drc/rules.py:337,362; standard_rules.py:79,99,153,215 | `{x:g}` formatting in finding titles (6 significant digits) | Limits, currents, voltages printed with `:g`: 12345678.9 prints 1.23457e+07; implicit rounding of what the engineer compares | various | in title | none | R5,R12 | ELEC |
| DRC-C1-009 | core/drc/rules.py:388 | `f"drops {drop:.3g} V, more than the {limit:g} V limit"` | Drop printed to 3 significant digits, limit to 6: a drop of 0.5004 V vs limit 0.5 V reads "drops 0.5 V, more than the 0.5 V limit" (verified `f"{0.5004:.3g}"`='0.5') | V | in title | none | R12,R5 | ELEC |
| DRC-C1-010 | core/drc/rules.py:299 | `contact_rating_key` default `"contact_current_a"` | Name of the Part.ratings entry used as contact current rating. Key is free text; unit only implied by the suffix `_a` | A (implied) | config file only; not in FIELD_INFO (configcheck.py:464-490) so not in the Supply dialog | `config/derating.json: contact_rating_key` | R3,R5 | ELEC |
| DRC-C1-011 | core/drc/rules.py:320-338 | contact check compares `i.max_current_a` of the WHOLE interface against ONE contact rating x `contact_current_factor` | Assumes all interface current flows through one contact; parallel pins are not credited; no per-pin current | A | title shows current, derated limit | factor via config | R2,R4 | ELEC |
| DRC-C1-012 | core/generate/sizing.py:77-100 | `limit = table[awg] * (bundle * temperature)` | Single formula behind current-over-wire and bundle-current. Factor order fixed; no AC/pulse/altitude/insulation-temperature terms | A | title shows result only for current-over-wire; K and temperature factor only in bundle-current title (standard_rules.py:357-362) | table and factors via config | R1,R4 | ELEC |
| DRC-C1-013 | core/drc/rules.py:353; standard_rules.py:331-332,345 | bundle size = `len(h.wires)` (all wires of the harness) | Bundle K uses the count of every wire in the harness, including signal and unloaded wires; `bundle_wire_count` is a one-liner, no user choice | count | bundle-current title says "bundle of N wires (H)" | none | R2,R4,R7 | ELEC |
| DRC-C1-014 | core/generate/sizing.py:62-74 | `bundle_k`: first listed count >= n; None above the largest | K is read at the next higher listed count (no interpolation); above the table the check is skipped | wires | note in unchecked-config (rules.py:576-579) | table via config | R1,R4 | ELEC |
| DRC-C1-015 | core/drc/standard_rules.py:318 | partial-load factor L "not applied ... conservative (L = 1)" | Table 6-42 L (config key `partial_load_factor`, standard_profiles.py:46) is stored but never used by any rule | factor | note text in unchecked-config | key stored, no effect | R1,R4 | ELEC |
| DRC-C1-016 | core/drc/standard_rules.py:50-66 | `min(f1*dwv, f2*rated)` | Connector working-voltage limit is the lower of 25 % of withstand and 75 % of rated (from profile); "whichever is lower" fixed in code | V | title shows final limit only, not which branch | factors via config | R1,R2 | ELEC |
| DRC-C1-017 | core/drc/standard_rules.py:25-31,45-47,90 | Part.ratings key names `rated_voltage_v`, `dielectric_withstand_v`, `max_temp_c`, `mating_cycles`, `shield_insulated`, `conductive_finish` | Fixed key vocabulary for part ratings; unit only in the suffix; flags use 1/0 and the rule fires only when value == 0 (standard_rules.py:405) | V, degC, count, flag | docstring only; no UI list found in my files | key names none | R3,R5 | ELEC |
| DRC-C1-018 | core/drc/standard_rules.py:119-141 | `exceeds(ambient, top - margin)` | Temperature check = ambient vs part max minus margin; no self-heating. Title says "before any self-heating of the conductor" | degC | in title | ambient/margins via config | R4,R1 | ELEC |
| DRC-C1-019 | core/drc/standard_rules.py:150 | `rated < limit` (strict) | Mating cycles: part rating below programme limit. A rating equal to the limit passes; no tracking of actual mate count (note at 254) | cycles | in title | limit via config | R2 | AIT,ELEC |
| DRC-C1-020 | core/drc/standard_rules.py:163-164 | `manufacturer.strip().casefold()` equality | connector-manufacturer: string equality of the Part.manufacturer text; "TE" vs "TE Connectivity" is a finding | text | in title | none | R7 | AIT |
| DRC-C1-021 | core/drc/standard_rules.py:184-191, 207-216 | gap must be `1 <= gap <= 1000`; pins checked in list order; window `k+2+gap` | power-return-adjacent assumes `conn.pins` list order = physical contact order; any two different power/ground signals (also two rails, not only power vs return) count; unassigned = no interface and no signal | pins | in title (free count vs required) | `generation.power_return_gap_pins` | R2,R4 | ELEC,AIT |
| DRC-C1-022 | core/drc/rules.py:430, standard_rules.py:372-378 | shield kinds exempt: `twisted_pair, coax` (wrong-end) vs `twisted_pair` only (unterminated, bonding) | Inconsistent exemptions: coax is exempt from shield-wrong-end ("bonded at both ends") but is still tested by shield-bonding, which requires backshell_360 both ends | enum | comment in code only | none | R2,R4 | ELEC |
| DRC-C1-023 | core/drc/rules.py:409-420, 423-436 | one project-wide grounding concept: `generation.shield_end_a/_b` | Every shield in every harness is judged against the same A/B pair; the rules read the shield ends from `h.shields`, no per-harness or per-signal-type concept | enum | in title ("grounding concept says X/Y") | config (global only) | R4,R2 | ELEC,SYS |
| DRC-C1-024 | core/drc/standard_rules.py:374 | exact match `("backshell_360","backshell_360")`; only `emc.shield_bonding == "both_ends_backshell"` accepted (rules.py gate by_rule.py:185) | Only one bonding method exists; `FIELD_INFO` choices = one value (configcheck.py:490) | enum | in title | no alternative | R4,R13 | ELEC,AIT |
| DRC-C1-025 | core/drc/standard_rules.py:390 | overshield kinds `overall_shield, twisted_pair` skipped when collecting parts needing an insulated sheath | Decides which wire parts must have `shield_insulated` | enum | comment only | none | R2 | ELEC |
| DRC-C1-026 | core/drc/base.py:63-66; rules.py:451,467 | `flag()` : unset/None means True | Segregation checks `forbid_nominal_with_redundant`, `forbid_pyro_with_other` are ON unless set to false; shipped default True (model/config.py segregation block) | bool | in config file; not in FIELD_INFO | config (false) | R3,R2 | SYS,ELEC |
| DRC-C1-027 | core/drc/rules.py:454,462,478 | redundancy values `"nominal"` and `"redundant"`, category `"pyro"` | Hard-coded vocabulary in chains-mixed / pyro-mixed; both rules check harness AND connector level; errors, unwaivable | enum | in title | none | R4,R13 | SYS |
| DRC-C1-028 | core/drc/rules.py:178-188 | mate-mismatch: gender equal, mating part, `len(pins)` equal, `keying` equal (string) | A cable connector with fewer pins or different keying text than the box is an error | text/count | in title ("both are male; 7 pins against 9; keying differs") | none | R7,R12 | SYS,AIT |
| DRC-C1-029 | core/drc/rules.py:198 | look-alike group key `(unit, part_id, keying, gender, len(pins))`, only connectors named by an interface endpoint | Defines "identical connector"; always on | key | in title | none (waive only) | R3 | AIT |
| DRC-C1-030 | core/drc/rules.py:204 | `ids[:3]`, " and N more" | Names at most 3 connectors in look-alike title | count | title | none | R12 | AIT |
| DRC-C1-031 | core/drc/rules.py:226-227 | approval states: `approved`, `not_approved`->"rejected", other -> "not approved yet"; `part.unverified` counts as unapproved | Maps part approval to finding text; ties to release gate `unapproved_parts` | enum | title | none | R8 | AIT,SYS |
| DRC-C1-032 | core/drc/rules.py:68; drc/__init__.py:68 | `sha256(message)[:6]` appended to finding IDs of model-inconsistent / verify-mismatch | IDs of these findings change whenever the message wording changes (new release, different value) | hex6 | ID shown in Checks/Problems | none | R8 | SYS |
| DRC-C1-033 | core/checks.py:49-51,71-75 | `safe_id`: keep `[A-Za-z0-9_.-]`, else `_` + 8 hex; IDs > 64 chars cut to 52 + `.` + 8 hex | Finding/waiver IDs for odd object names (signals like TX+) are hash-suffixed and not readable | chars | shown | none | R8,R14 | SYS |
| DRC-C1-034 | core/checks.py:57 | `finding_hash = sha256(rule + "\n" + title)[:12]` | Waiver stays valid only while rule+title text is identical. Because titles embed the numbers, changing a limit voids the waiver (good) but so does a wording change in a new tool version | hex12 | "Waiver no longer fits" label (checks_panel.py:177) | none | R7,R8 | SYS,ELEC |
| DRC-C1-035 | core/model/review.py:19-21 | `Justification` min 10, max 2000 chars, no control chars | Only validation of a waiver reason; no author, no date, no scope, no expiry field in `Waiver` (review.py:35-48) | chars | message at waive (strings.py:132) | none | R8,R7 | SYS |
| DRC-C1-036 | core/drc/__init__.py:14,26; checks.py:140 | sort order: error, warning, info, then by ID (string order) | Order of every list, report, CSV and to-do; ID string sort (not natural) | - | implicit | none | R6 | SYS |
| DRC-C1-037 | core/drc/__init__.py:64-65 | `if issue.severity != "error": continue` | Verifier warnings (`pin_shared` for hand-drawn wires, `wire_orphan`) never appear in Checks | enum | no | none | R12,R6 | SYS,AIT |
| DRC-C1-038 | core/drc/__init__.py:76 | `can_waive=False`, fix label "Regenerate harnesses" except `link_wire_mismatch` | verify-mismatch always un-waivable, one-click fix = regenerate everything (fix_ops 84-93) | - | button label | none | R7 | SYS |
| DRC-C1-039 | core/drc/report.py:11,41 | `"Rules run: {len(RULES)}"` | Report says all 39 rules ran even when most are pending/unchecked | count | CLI `drc` and report | none | R12,R9 | SYS |
| DRC-C1-040 | core/drc/report.py:2,40-41 | model hash `[:12]`, no date, no tool version, no config values | Report provenance is only a 12-hex model hash | hex12 | report header | none | R9 | SYS |
| DRC-C1-041 | gui/controller.py:57,188; gui/drc_process.py:25-26 | `DRC_DELAY_MS=1200`, `MANY_FINDINGS=1000`, `PAUSE=0.0005`, `CHECK_TIMEOUT_S=180` | A check running > 180 s is killed and rerun in-thread; results shown can be up to 1.2 s + run time old (flagged by "stale" label, checks_panel.py:~560) | ms, s | stale label only | constructor args / env only | R6 | SYS |
| DRC-C1-042 | core/drc/worker.py:23,66 | `MAX_MESSAGE = 1<<31`, `FINDING_CHUNK = 1000`, `os.nice(5)` | Transport limits of the helper process; cosmetic for results | bytes | no | none | - | SYS |
| DRC-C1-043 | core/why.py:241; core/verify.py:250; core/integrity.py:237; core/links.py:953 | `limit=3` reasons; `missing[:3]`; `shared[:6]`; `powered[:4]` | Messages truncate lists silently ("and others", "...") so the engineer cannot see all affected IDs | count | partly | none | R12,R10 | SYS,AIT |
| DRC-C1-044 | core/describe.py:124 | `VALUES_NEEDED = {"power": ("V","A"), "pyro": ("A",)}` | Which interface categories prompt for voltage/current (the inputs of the ampacity/drop/voltage checks). Other categories (analog, RF, data) never prompt, so their checks run on nothing | enum | link label "V ?" | none | R4,R13 | ELEC |
| DRC-C1-045 | core/describe.py:20-30,90-102,236-254 | keyword tables: RTN/GND meaning; connector family by words (micro-d, 38999, sma...), unit glyph by name words | Heuristic text matching (e.g. "power" in a unit name -> power glyph); family/gender guessed from part description (`part_gender` regex, 47-55); display only, but feeds what the user thinks a connector is | text | display | none | R3,R2 | AIT,SYS |
| DRC-C1-046 | core/describe.py:384 | `harness.revision != "A"` -> "revised" | First revision letter fixed as "A" | text | state chip | none | R3 | SYS |
| DRC-C1-047 | core/checks.py:98-141 (cross-strap, no-connector, unconfirmed, isolated) | severity warning/info/info/info fixed; cross-strap waivable (True), others not | Logical rules; "unconfirmed" excluded from Fix-all (checks.py:270) | enum | Problems | none | R7 | SYS |
| DRC-C1-048 | core/configcheck.py:119-150; standard_profiles.py:155-205 | validity ranges: factors `0<x<=1`; spare fraction `0<=x<1`; gauge 0..40; gap whole >=0; mating cycles int >=1; K table non-increasing; ampacity non-decreasing toward bigger wire | `config-invalid` error blocks release for every harness (release.py:390). Range limits are code | various | message text | none | R3,R12 | ELEC |
| DRC-C1-049 | core/standard_profiles.py:36-77 | profile `ecss-q-st-30-11c`: contact 0.5, conn V 0.25/0.75, conn T margin 30, RF 0.75, wire V 0.5, wire T margin 50, K table, L table, mating 50, gap 1; `ecss-e-st-20-07c`: both_ends_backshell, same-class true | Defaults a project gets from a profile; only fills unset values; marks files placeholder | per key | recorded as requirement ID in profile; applied values visible in config files | edit values after apply | R3,R2 | ELEC,SYS |
| DRC-C1-050 | core/model/config.py (derating/generation blocks, read lines 25-110) | shipped defaults: every electrical value `None` (placeholder=True); `wire_part_by_construction` maps to EX-WIRE-*; naming patterns | New project is "pending" on most rules; no engineering number shipped | - | Checks "pending" | config | R3 | SYS,ELEC |
| DRC-C1-051 | core/drc/rules.py:664-669 | EMC rules need `emc_class` on interface types; else "No interface type has an EMC class yet" | EMC separation rules do nothing without data | - | note | data | R12 | SYS,ELEC |
| DRC-C1-052 | core/drc/standard_rules.py:309-313 | `rf_power_factor` has a profile value but no rule; rule `multipactor` only an info note | 75 % RF factor and 6 dB margin are stored/not evaluated; key absent from NEEDS/FIELD_INFO | factor | note text | stored, no effect | R1,R4 | ELEC |

## C2 Hidden assumptions (simplified models, reference systems, implicit rounding, fixed sequences)

| id | file:line | assumption | why it matters | R | who |
|---|---|---|---|---|---|
| DRC-C2-001 | rules.py:341-363 | One `max_current_a` per interface is applied to every wire carrying it, as steady DC; no duty cycle, peak, per-wire split | A multi-wire interface or paralleled pins gets full current on each wire | R2,R4 | ELEC |
| DRC-C2-002 | rules.py:385, sizing.py:40 | Return conductor same gauge and length as the outgoing conductor | Unequal return, shared returns or chassis return give wrong drop | R2,R4 | ELEC |
| DRC-C2-003 | sizing.py:40; units.py:15-17 | Resistivity is one constant (any temperature), conductor solid circular, no contact resistance | Drop under-estimated for stranded/hot wire; rho temperature is not stated anywhere | R1,R5 | ELEC |
| DRC-C2-004 | standard_rules.py:331-345 | Bundle = all wires of one harness; ISW from user table x K x temperature factor; L=1 | Over- or under-conservative per real bundle layout; no routing geometry (acknowledged note 291) | R4,R7 | ELEC |
| DRC-C2-005 | standard_rules.py:119-141 | Temperature margin vs ambient only; no I2R heating, no bundle heat | Thermal margin is not a wire temperature; note "thermal-analysis" admits it (281-284) | R1 | ELEC |
| DRC-C2-006 | standard_rules.py:194-216 | Pin list order = physical contact adjacency | Wrong for connectors whose insert layout is not sequential (Micro-D staggered rows, circular) | R2 | ELEC,AIT |
| DRC-C2-007 | rules.py:398 | A "spare" pin = no interface and no signal; counted on box connectors with at least one allocated pin | Pins reserved/shorted/unpopulated are not recognised; pin-count tolerance fixed | R2 | AIT,ELEC |
| DRC-C2-008 | rules.py:423-436 | One global shield grounding concept A/B | Single-point vs multi-point grounding per signal type cannot be expressed | R4 | ELEC |
| DRC-C2-009 | verify.py:53-58,81-89 | Out/in signals are paired by list position (k-th out with k-th in) | A type whose signal order is not paired this way yields false "missing/extra" or hides swaps | R4 | SYS |
| DRC-C2-010 | rules.py:238-261 | Types with only `out` or only `in` are never judged for direction; passthrough exemption copied from verifier | One-directional types (analog, discrete, pyro, LVDS) cannot trigger direction-conflict | R4 | SYS,ELEC |
| DRC-C2-011 | rules.py:211-232 | Part use counted by IDs on connectors and wires only; accessories, contacts not covered | Unapproved contact part (Pin.contact_part) or accessory is not flagged by part-unapproved (integrity only checks existence, integrity.py:54-60) | R14 | AIT |
| DRC-C2-012 | rules.py:127-137 | A pin is "floating" only if it has a signal and no wire; unused pins without signal are ignored | Fine for naming; no unpopulated-contact / blanking-plug logic (AIT) | R6 | AIT |
| DRC-C2-013 | rules.py:140-152 | Shared pin = more than one wire id on the same (connector, pin) in a harness; spliced pins are not distinguished from crimped pairs | Warning text assumes two wires in one contact need a crimp holding both; no contact-size/crimp-range check exists anywhere in the 39 rules | R2 | AIT |
| DRC-C2-014 | rules.py:557-590; release.py:395-413 | Missing wire length / gauge is a release blocker (`length_unknown`, `gauge_pending`), but a Checks row exists only when an interface current exists | Cut-list gaps are invisible in Checks until release; build-data gaps not a DRC rule | R6,R12 | AIT |
| DRC-C2-015 | by_rule.py:167-192 | GATES duplicate the first lines of each rule ("exactly as the rule's own first lines test them") | Pass/pending status is computed separately from the rule; they can drift. Rule logic and status logic are two code paths | R1,R6 | SYS |
| DRC-C2-016 | by_rule.py:310-322 | "pass" = rule ran, no open finding, no pending, no note; waived findings are not counted as open | A rule whose only finding is waived shows pass-like state (count 0, waived n) | R7 | SYS |
| DRC-C2-017 | checks.py:63-68 | Waiver applies when `finding_hash` missing (older/manual waivers) with no check at all | Hand-written or pre-1.11 waivers silently keep covering a changed finding | R7,R8 | SYS |
| DRC-C2-018 | generation_status.py:13-20,23-73 | `input_hash` excludes generated pins/wires, release status and `release_distinct_roles`, includes config, parts, units, interfaces, locked wires, segment lengths | "Outputs outdated" depends on this fixed list; inputs outside that list (for example a hand-set length on an unlocked wire, unverified) would not mark outputs outdated | R9,R14 | SYS |
| DRC-C2-019 | why.py:3-6,51-52 | "Why" text is the provenance recorded at generation time, not recomputed | After a config change without regenerating, the explanation shows the old reasoning and numbers; stale outputs is the only cue | R1,R14 | SYS,ELEC |
| DRC-C2-020 | rules.py:672-753 | Unit/rating ambiguity: `max_current_a`, `voltage_v` have no AC/DC, rms/peak, continuous/peak qualifier (model/logical.py:63-64) | Contact/wire/voltage limits are applied to whatever number was entered | R5 | ELEC |
| DRC-C2-021 | integrity.py:35-45,48-429 | Orphan data in generated harnesses is downgraded from error to warning ("plans outdated") | An error becomes a warning depending on the `generated` flag; engineer does not see the rule | R12 | SYS |

## C3 Outputs shown without their derivation

| id | file:line | what the user sees | what is missing | R | who |
|---|---|---|---|---|---|
| DRC-C3-001 | rules.py:362 | "Wire W1-003 (AWG 24) carries 5 A but allows 3.2 A after derating" | Table ampacity, bundle K, temperature factor, bundle count not shown (bundle-current does show them, standard_rules.py:362) | R1,R12 | ELEC |
| DRC-C3-002 | rules.py:388 | "drops 0.5 V, more than the 0.5 V limit" | Current, length, gauge, area, rho, n conductors absent; 3 vs 6 digit rounding | R1,R12 | ELEC |
| DRC-C3-003 | rules.py:337 | "carries 10 A but contacts of J1 allow 5 A after derating" | Part rating, rating key, factor absent | R1,R12 | ELEC |
| DRC-C3-004 | standard_rules.py:79 | "allows 12 V after derating" | Which of the two factors/ratings set the limit not stated | R1 | ELEC |
| DRC-C3-005 | rules.py:402 | "has 1 spare pin(s) of 9, fewer than the required 12%" | Required number of spare pins and exact fraction missing; counts only unassigned pins | R12,R5 | ELEC,AIT |
| DRC-C3-006 | checks_panel.py:166-177 | Checks details table: object, title, severity, waiver text | `why`, `how`, requirement text, threshold in force and its config key are not shown here | R12,R2 | SYS,ELEC,AIT |
| DRC-C3-007 | panels.py:897-906 | Card shows `f.why`, requirement ID string | Requirement IDs (e.g. ECSS-Q-ST-30-11_0140051) are not resolved to clause number or text inside the tool; text lives in compliance/ outside src (unverified in package) | R1,R12 | ELEC |
| DRC-C3-008 | base.py:48 | `why = rule.why + " To fix it: " + rule.how` | Same sentence for every object of a rule; no actual values; no "how to waive" and no "how to retune the limit" | R12 | SYS,ELEC,AIT |
| DRC-C3-009 | by_rule.py:309-335 | State chip pass/fail/not checked/pending with "passed on placeholder values" note | Which numeric values the pass used is not listed (only file names, checks_panel.py rule_state) | R2,R12 | ELEC |
| DRC-C3-010 | report.py:25-95 | Markdown report: title + generic why + waiver text | No limits table, no config snapshot, no rule version; CLI `drc` prints it, no JSON | R9,R10 | SYS |
| DRC-C3-011 | verify.py:370-384 | "SIG+ (end 1) to SIG- (end 2) has no wire" | The derivation of the expected pairing (positional out/in pairing) is not shown | R1 | SYS |
| DRC-C3-012 | drc/__init__.py:54-79 | verify-mismatch finding titled by verifier message | Rule is called "Independent verification"; no list of what was re-derived | R1,R6 | SYS |
| DRC-C3-013 | why.py:100-150 | Reasons are strings "rule: sentence" parsed by regex (24) | No structured equation / inputs / units; `Reason` carries rule, text, where only | R1 | SYS,ELEC |
| DRC-C3-014 | standard_rules.py:315-319; 255-292 | Info notes "not checked" with clause numbers inside free text | Good disclosure, but not linked to a rule's status row beyond NOTES dict (by_rule.py:199-232) | R12 | SYS |
| DRC-C3-015 | describe.py:317-373 | `why_lines`: "chosen for you, the first free connector" | Selection criterion stated, alternatives rejected not listed | R4,R1 | SYS,AIT |
| DRC-C3-016 | checks.py:208-249 | To-do: "N warnings to fix or waive" | No breakdown by rule in the sentence | R6 | SYS |

## C4 Forced single options

| id | file:line | what is forced | R | who |
|---|---|---|---|---|
| DRC-C4-001 | base.py:30-35 | Errors cannot be waived. Engineer who has analysis showing an overload is acceptable (e.g. current-over-wire, voltage-drop, mate-mismatch) must change the global limit or the data; there is no per-finding accepted deviation. Release gate blocks on every unwaived error (release.py:379-394) | R7,R12 | ELEC,AIT,SYS |
| DRC-C4-002 | rules.py:756-842 | No rule can be switched off, only gated by config; structural/always-on rules (duplicate-id, wire-dangling, pin-shared, pin-floating, connector-lookalike, part-unapproved, mate-mismatch, direction-conflict) have no switch | R3,R7 | SYS |
| DRC-C4-003 | rules.py:756 | Rule list is a code tuple; no registry, no plugin or user-defined rules, no custom message templates | R13 | SYS |
| DRC-C4-004 | rules.py:385 | Return-path factor 2 for power/ground not selectable (no config key) | R4 | ELEC |
| DRC-C4-005 | rules.py:353, standard_rules.py:331 | Bundle size definition (all wires of harness) fixed; no per-bundle or per-segment definition | R4,R7 | ELEC |
| DRC-C4-006 | rules.py:423-436 | One shield grounding concept for the whole project | R4 | ELEC |
| DRC-C4-007 | standard_rules.py:374 | Shield bonding offers one method only | R4 | ELEC,AIT |
| DRC-C4-008 | standard_rules.py:50-66 | Connector voltage rule takes the lower of two factors; no way to use only one when both set (unset one to skip) | R4 | ELEC |
| DRC-C4-009 | rules.py:320-338 | Limits are project-global: no per-part, per-harness, per-zone, per-interface override of factors, ambient, drop limit | R7 | ELEC |
| DRC-C4-010 | drc/__init__.py:84-93 | Only fix for signal-unassigned / verify-mismatch is regenerate all; refused for hand-drawn or released harness | R7 | SYS,AIT |
| DRC-C4-011 | checks.py:268-278 | "Fix all" never confirms tool-chosen connectors | R7 | SYS |
| DRC-C4-012 | rules.py:178-188 | mate-mismatch: pin count and keying must be equal; no accepted mismatch (partially populated, adapter) | R7 | AIT |
| DRC-C4-013 | drc/__init__.py:76; checks.py:60-68 | verify-mismatch and released-modified (error) cannot be waived; released-modified requires baseline match | R7 | AIT,SYS |
| DRC-C4-014 | gui/controller.py:268-290 | Checks run automatically 1.2 s after edit; "Check now" and Cancel exist, but delay/timeouts are not user settings | R6 | SYS |
| DRC-C4-015 | checks.py:190-205 | Waiver is per finding ID only; no waive-by-rule / by-object-class, no expiry, no approver | R7,R8 | SYS |

## C5 Inputs and outputs exchanged with other tools or files

| id | file:line | item | direction | visibility | R | who |
|---|---|---|---|---|---|---|
| DRC-C5-001 | rules.py:299,366-369, 591-596; standard_rules.py:52,84,121-128 | Reads `config/derating.json`, `generation.json`, `segregation.json`, `emc.json` (project folder JSON) | in | file names in "Supply value" rows (by_rule.py:51) and error messages | R3,R14 | ELEC,SYS |
| DRC-C5-002 | standard_rules.py:45-47 | Reads `Part.ratings` (parts library JSON) keys listed in C1-017 | in | in "no rating" notes | R14 | ELEC |
| DRC-C5-003 | rules.py:324-327,376 | Reads interface `max_current_a`, `voltage_v` (project JSON); lengths from `wire.length_m` or segments (`lengths.wire_length`, imported lengths via CLI `import-lengths`, release.py:405) | in | partial | R14 | ELEC,AIT |
| DRC-C5-004 | outputs/build.py:85-98 | Exported DRC findings table columns: id, rule, severity, object, title, waived, justification, requirement | out (CSV/sheet in outputs) | in export | R10,R9 | SYS |
| DRC-C5-005 | outputs/verify.py:893-904 (grep only) | Output verifier recomputes the DRC findings table and compares; mismatch is an error | in/out | message only | R9 | SYS |
| DRC-C5-006 | cli/main.py:182-193 | CLI `drc`: Markdown to stdout; exit 1 if any open error. No JSON, no rule status table, no thresholds | out | CLI | R10,R11 | SYS |
| DRC-C5-007 | cli/main.py:196-224 | CLI `verify [--outputs]` prints issues incl. warnings; exit 0/1 | out | CLI | R11 | SYS |
| DRC-C5-008 | worker.py:1-20; gui/drc_process.py:34 | Whole project pickled to a helper process via stdin/stdout pipes; no network, no file | internal, invisible | docstring | R9 | SYS |
| DRC-C5-009 | standard_profiles.py:1-30 | Requirement IDs (ECSS-Q-ST-30-11_xxxxxx) refer to `compliance/requirements` outside `src` | in (reference) | IDs shown as text | R1,R14 | ELEC |
| DRC-C5-010 | core/vcs/release.py:379-394 | Release gate re-runs `drc.run` and `verify_project`; unwaived errors and config-invalid block | internal | blocker list | R7 | SYS,AIT |
| DRC-C5-011 | generation_status.py:23-73 | `project.generation.input_hash` (sha256 hex of canonical JSON of listed inputs) stored in project | in/out | hidden | R9,R14 | SYS |
| DRC-C5-012 | why.py:51 | `project.generation.provenance` (dict of recorded reason strings) stored in project, read for Why panel | in | Why panel | R1 | SYS |
| DRC-C5-013 | report.py:36-46 | Waivers stored in `waivers.json` (schemas.py:75); report lists justifications | out | report | R8,R14 | SYS |

## C6 Customisation points that DO exist

| id | file:line | customisation | strength / limit | R | who |
|---|---|---|---|---|---|
| DRC-C6-001 | configcheck.py:33-67; by_rule.py:168-192 | Supply value dialog per missing key (file, key, unit) from the Checks panel; JSON config editable | Visible unit and label for ~28 keys; keys outside FIELD_INFO (contact_rating_key, rf_power_factor, partial_load_factor, default_gauge_awg, forbid_*) are file-only | R3,R2 | ELEC |
| DRC-C6-002 | standard_profiles.py:36-77, 83-120 | Apply ECSS profile: fills only unset values, marks files as placeholder, records requirement IDs | Good: nothing applied silently, kept values listed | R3,R2 | ELEC,SYS |
| DRC-C6-003 | rules.py:451,467 | `forbid_nominal_with_redundant`, `forbid_pyro_with_other` switch off two error rules | The only rule switches that exist | R3,R7 | SYS |
| DRC-C6-004 | rules.py:495-541 | `category_pairs_to_separate`, `conflicting_class_pairs` user lists | Free pairs; severity warning fixed | R3,R4 | SYS,ELEC |
| DRC-C6-005 | checks.py:190-205; base.py | Waivers with mandatory justification; invalidated when title changes | Only warnings; no author/date | R7,R8 | SYS,ELEC |
| DRC-C6-006 | by_rule.py:1-30,255-336 | Four-state result per rule with named missing values, notes, placeholder annotation | Strong transparency of "what was not checked" | R12,R6 | SYS,ELEC |
| DRC-C6-007 | checks_panel.py:70-80 | Filter by state, text search, click-through to object | no rule parameter editing in-panel except missing values | R6 | SYS |
| DRC-C6-008 | gui/drc_process.py:27 | `HARNESS_DRC_INPROCESS=1` runs rules in-thread | debug only | R11 | SYS |
| DRC-C6-009 | rules.py:298-302 | `contact_rating_key` selects which part rating is the contact limit | Only way to choose a different rating (e.g. contact_current_a_size20) globally | R4 | ELEC |
| DRC-C6-010 | standard_rules.py:322-328; sizing.py:62-74 | `bundle_factor_by_count` user table; replaces single factor | Edit points as a table; interpolation not available | R3,R4 | ELEC |
| DRC-C6-011 | core/links.py:958-964 | Link review rules (4 DRC rules) check pairings the engineer defined; roles can be set to Spare/Return to resolve | Resolve-by-data, not waive (warnings are waivable) | R12 | ELEC,AIT |
| DRC-C6-012 | configcheck.py:231 (`report`), CLI `config DIR` | Listing of missing/invalid values | Text only | R6,R10 | SYS |

---

## Rules (39 rules plus the dynamic verify-mismatch and 4 logical rules of checks.py)

Columns: id | file:line | threshold(s) and source | severity (fixed/configurable) | R12 text quality: states rule? / actual vs limit with units? / why? / fix? / override? | standard clause cited? (`sources` IDs only) | simplified model | personas

Legend for severity: "fixed" = hard-coded in the `Rule`; waivable only if warning (base.py:35). "Switch" = how it can be disabled.

| # | id | file:line | thresholds and source | severity | R12 text quality | standard cited | model | who |
|---|---|---|---|---|---|---|---|---|
| 1 | duplicate-id | rules.py:757 (check 57-70) | none; counts IDs of connectors, wires, pins | error, fixed, not waivable | rule yes; actual (count) yes; limit n/a; why generic; fix "rename"; no override | no | no | SYS |
| 2 | wire-dangling | rules.py:760 (73-92) | none | error, fixed | rule yes; names connector/pin; why/fix generic; no override | no | no | SYS,AIT |
| 3 | model-inconsistent | rules.py:763 (155-162) | passes through integrity issues that are not errors (integrity.py) | warning, fixed, waivable | text = integrity message; why generic ("later outputs may be wrong"); fix generic; waive yes | no | no | SYS |
| 4 | segment-loop | rules.py:766 (95-103) | tree rule for segments | error, fixed | rule yes (explains length undefined); fix generic; no override | no | no | SYS,AIT |
| 5 | signal-unassigned | rules.py:769 (106-124) | none | warning, fixed | signal+connector named; fix = Regenerate one-click; waive yes | no | no | SYS,ELEC |
| 6 | pin-floating | rules.py:772 (127-137) | pin with signal and no wire | warning, fixed | yes pin/signal; fix generic; waive yes | no | no | AIT |
| 7 | pin-shared | rules.py:775 (140-152) | >1 wire on a pin | warning, fixed | lists wire IDs and count; why crimp; fix and waive named in how text | no | no | AIT,ELEC |
| 8 | mate-mismatch | rules.py:779 (168-190) | gender, mating part, pin count, keying equality (hard-coded) | error, fixed, not waivable | lists each mismatch with values; why damage; fix generic; no override | ECSS-Q-ST-30-11_0140054 | no | AIT,SYS |
| 9 | direction-conflict | rules.py:782 (238-261) | out/out or in/in | error, fixed | states conflict class; no signal names/directions of ends; no override | no | positional pairing (verify.py:53) | SYS,ELEC |
| 10 | current-over-contact | rules.py:785 (320-338) | `derating.contact_current_factor` x part rating `contact_current_a` (key `contact_rating_key`) | error, fixed; rule runs only if factor set | actual and derated limit with A; not the raw rating, factor or key; fix generic; no override | ECSS-Q-ST-30-11_0140050 | whole-interface current vs one contact | ELEC |
| 11 | current-over-wire | rules.py:788 (349-363) | ampacity table x bundle (K by count or single factor) x temperature factor, `derating.*` | error, fixed | actual, limit, gauge, A; factors not shown; fix "larger gauge"; no override | ECSS-Q-ST-30-11_0140217 | steady current, bundle = all wires | ELEC |
| 12 | voltage-drop | rules.py:790 (366-388) | `derating.max_voltage_drop_v`; `generation.conductor_resistivity_ohm_m`; n=2 power/ground | error, fixed | actual (3 sig. digits) and limit (V); no length/gauge/current; fix "larger gauge or shorten"; no override | none | DC, round trip, solid circular | ELEC |
| 13 | spare-pins-low | rules.py:793 (391-403) | `derating.spare_pin_fraction` | warning, fixed | spare vs total and rounded % ; required pins not shown; fix "bigger connector"; waive yes | none | pin without interface/signal | ELEC,AIT |
| 14 | shield-unterminated | rules.py:796 (409-420) | gate: either `shield_end_a/_b` set | warning, fixed | states shield, harness; fix generic; waive yes | none | | ELEC,AIT |
| 15 | shield-wrong-end | rules.py:799 (423-436) | `generation.shield_end_a/_b` global concept | warning, fixed | states actual vs concept (both values); waive yes | ECSS-E-ST-20-07_0080041, _0080042 | one global concept | ELEC,AIT |
| 16 | chains-mixed | rules.py:802 (450-463) | switch `segregation.forbid_nominal_with_redundant` (default on) | error, fixed; switchable | states harness/connector; no list of offending interfaces | none | | SYS |
| 17 | pyro-mixed | rules.py:805 (466-492) | switch `forbid_pyro_with_other` | error, fixed; switchable | same | none | | SYS,ELEC |
| 18 | category-mixed | rules.py:808 (505-518) | `segregation.category_pairs_to_separate` | warning, fixed | names pair and harness; fix generic | ECSS-E-ST-20-07_0080034 | category from type | SYS,ELEC |
| 19 | emc-mixed | rules.py:811 (531-541) | `emc.conflicting_class_pairs` | warning, fixed | names classes and harness | ECSS-E-ST-20-07_0080034 | | SYS,ELEC |
| 20 | connector-lookalike | rules.py:814 (193-208) | key (unit, part, keying, gender, pins) | warning, fixed, always on | lists up to 3 IDs; why; fix named | ECSS-Q-ST-30-11_0140054 | | AIT |
| 21 | part-unapproved | rules.py:817 (211-232) | part `approval`, `unverified` | warning, fixed | part, state, number of uses; fix named; waive yes (also release override reason) | ESCC3901-4.4 | | AIT,SYS |
| 22 | connector-voltage | standard_rules.py:437 (69-80) | `connector_voltage_factor_withstand` x `dielectric_withstand_v`, `connector_voltage_factor_rated` x `rated_voltage_v`; lower wins | error, fixed | actual and limit in V; not which factor; fix generic | ECSS-Q-ST-30-11_0140051, _0140058 | | ELEC |
| 23 | wire-voltage | standard_rules.py:441 (83-100) | `wire_voltage_factor` x `rated_voltage_v` | error, fixed | actual and limit; factor not shown | ECSS-Q-ST-30-11_0140213 | | ELEC |
| 24 | temperature-margin | standard_rules.py:445 (119-141) | `max_ambient_temperature_c`, `connector_temperature_margin_c`, `wire_temperature_margin_c`, part `max_temp_c` | error, fixed | best text of all: ambient, limit, max, margin, in degC, notes no self-heating; fix generic; no override | ECSS-Q-ST-30-11_0140051, _0140213 | ambient only | ELEC |
| 25 | mating-cycles | standard_rules.py:449 (144-154) | `derating.max_mating_cycles` vs part `mating_cycles` | warning, fixed | rated vs limit (cycles); no actual usage; note says count is a human record | ECSS-Q-ST-30-11_0140056, _0140061 | rating vs programme limit | AIT,ELEC |
| 26 | connector-manufacturer | standard_rules.py:453 (157-169) | manufacturer string equality | warning, fixed | both manufacturers shown | ECSS-Q-ST-30-11_0140055 | text equality | AIT |
| 27 | wire-specification | standard_rules.py:457 (172-179) | approved wire part with empty `specification` | warning, fixed | part named | ESCC3901-4.4 | | AIT,SYS |
| 28 | shield-bonding | standard_rules.py:461 (366-378) | `emc.shield_bonding == both_ends_backshell` | warning, fixed | actual ends shown, requirement stated | ECSS-E-ST-20-07_0080041, _0080042 | | ELEC,AIT |
| 29 | shield-parts | standard_rules.py:465 (398-411) | rating `conductive_finish` / `shield_insulated` == 0 | warning, fixed | part, harness, finding | ECSS-E-ST-20-07_0080039, _0080040 | | ELEC,AIT |
| 30 | emc-class-split | standard_rules.py:469 (414-433) | `emc.same_class_one_bundle` true | warning, fixed | class, units, bundles | ECSS-E-ST-20-07_0080035 | two-endpoint interfaces only | SYS,ELEC |
| 31 | power-return-adjacent | standard_rules.py:473 (182-216) | `generation.power_return_gap_pins` 1..1000 | warning, fixed | free vs required contacts shown; fix says regenerate | ECSS-Q-ST-30-11_0140052 | list order = adjacency | ELEC,AIT |
| 32 | bundle-current | standard_rules.py:477 (335-363) | ampacity x K(count) x temperature factor (1 if unset) | error, fixed | best of the current rules: single-wire A, K, temp factor, limit, count | ECSS-Q-ST-30-11_0140217, _0140218 | L=1, all wires | ELEC |
| 33 | link-unpaired | rules.py:821 (link_pin_unpaired, links.py:939) | none | warning, fixed | pin, signal, link; fix says set Spare | none | | ELEC,AIT |
| 34 | link-direction | rules.py:824 (links.py:917-923) | direction conflict | error, fixed | both signals and directions | none | | ELEC,SYS |
| 35 | link-signal-mismatch | rules.py:827 (links.py:911-916) | `name_relation` table | warning, fixed | both names | none | name table | SYS |
| 36 | link-power-return | rules.py:830 (links.py:947-954) | power pairs with no return pair; shows first 4 | warning, fixed | names pins | none | | ELEC |
| 37 | config-invalid | rules.py:833 (544-546) | ranges in C1-048 | error, fixed; blocks all releases | states key and range | none | | ELEC,SYS |
| 38 | released-modified | rules.py:836 (549-551) | release_integrity (vcs/consistency, not read) | error, fixed | unverified | none | | AIT,SYS |
| 39 | unchecked-config | rules.py:839 (672-753) | notes about missing data | info, fixed, not waivable | each note names the missing value; no clause for most | clause numbers in free text only | | SYS,ELEC |
| + | verify-mismatch | drc/__init__.py:54-79 | verifier errors | error, not waivable | verifier message; fix "Regenerate" | none | | SYS,AIT |
| + | cross-strap / no-connector / unconfirmed / isolated | checks.py:87-141 | none | warning (waivable) / info | actual objects named | none | | SYS |

### R12 for rules electrical and AIT engineers meet (can they see the numbers and decide to fix or waive?)

- **Wire sizing (current-over-wire, bundle-current, voltage-drop):** current-over-wire shows current, gauge and derated limit but not the factors; bundle-current shows K and temperature factor; voltage-drop shows only drop and limit. All three are errors: the engineer cannot waive, only change a global factor or the data. Not enough to defend a deviation.
- **Contact ratings (current-over-contact, connector-voltage):** shows interface value and derated limit, not the raw rating or factor. Error, no waiver.
- **Mating cycles:** rated vs programme limit shown; actual use is outside the tool (note at standard_rules.py:254). Waivable.
- **Shield termination / grounding / bonding:** actual ends and concept shown; waivable; but one global concept (see C4-006).
- **Build-data gaps (length, gauge):** release blockers only (release.py:395-413), no Checks row unless a current exists (C2-014). No rule for strip/cut length, contact crimp range, labels, tooling.

---

## Top findings

1. **DRC-C4-001 / DRC-C1-001** – Every error rule is un-waivable and gates release; severity is hard-wired (DRC-C1-002). An engineer with a justified deviation on wire current, voltage drop, contact current or mating has no recorded-acceptance path. [ELEC, AIT, SYS]
2. **DRC-C3-001 / C3-002 / C3-003 / C3-006** – Finding text shows result and limit but not the derivation (base ampacity, K, temperature factor, rating, factor, rho, length, n). The Checks panel shows only the title; why/how/clause are elsewhere. [ELEC]
3. **DRC-C1-004 / C2-002 / C2-003** – Voltage drop assumes DC, solid circular conductor, equal return path (n=2 for power/ground), no temperature or contact resistance; hard-coded and duplicated in the generator. [ELEC]
4. **DRC-C1-013 / C2-004** – Bundle factor counts every wire in a harness (including signal and unloaded wires); L fixed to 1; no per-bundle definition or override. [ELEC]
5. **DRC-C1-008 / C1-009 / C1-007** – Silent rounding in finding text (`:g`, `:.3g`, `:.0%`): a failing drop can print as equal to its limit; spare-pin fraction rounded, required pin count never given. [ELEC, AIT]
6. **DRC-C2-014 / C2-006 / C2-013** – AIT: missing lengths/gauges only surface at the release gate; pin adjacency assumes list order = physical layout; no check of contact crimp range, strip length or tooling in any of the 39 rules; mating-cycle count is not tracked. [AIT]
7. **DRC-C1-034 / C1-035 / C2-017** – Waivers have no author, date, scope or expiry; validity is a 12-hex hash of rule+title, so wording changes in a new tool version void them and pre-1.11 waivers without hash are never checked. [SYS]
8. **DRC-C4-003 / DRC-C2-015 / DRC-C3-010** – Rules are a code tuple (no registry/plugins) and rule status (GATES) is a second copy of rule logic; report says "Rules run: 39" regardless of pending state, with no tool version, config values or date. [SYS]

Next: [the audit](../transparency_audit.md), [appendix B](generation.md), [appendix D](outputs.md)
