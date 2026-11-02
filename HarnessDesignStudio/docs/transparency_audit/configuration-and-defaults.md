# Transparency audit, appendix A: configuration, model and defaults

This page is appendix A of the [transparency audit](../transparency_audit.md): the row-level catalogue for the configuration files, the data model, the starter library and the defaults a new project is written with. Each row names the file and line the reviewer opened. IDs read `CFG-C<category>-<number>`; the categories and the tags `[SYS]`, `[ELEC]` and `[AIT]` are explained in section 1 of the audit. Paths beginning with `work/` are scratch projects the reviewer made while auditing; they are not in the repository. Nothing on this page was changed in the code: it is read-only.

## Contents

- [C1 Hard-coded constants, defaults, margins, rules](#c1-hard-coded-constants-defaults-margins-rules)
- [C2 Hidden assumptions](#c2-hidden-assumptions)
- [C3 Outputs shown without derivation](#c3-outputs-shown-without-derivation)
- [C4 Forced single options](#c4-forced-single-options)
- [C5 Inputs and outputs](#c5-inputs-and-outputs)
- [C6 Customisation points that do exist](#c6-customisation-points-that-do-exist)
- [AIT view (what an AIT engineer can and cannot trace or change in this area)](#ait-view-what-an-ait-engineer-can-and-cannot-trace-or-change-in-this-area)
- [Top findings](#top-findings)

Scope: read in full core/model/*.py (base, config, generation, library, logical, physical, project, review, __init__), core/configcheck.py (716), standard_profiles.py (221), units.py, starter.py, templates.py, samples.py, counterparts.py, ids.py, wirecolours.py, first_connector.py, part_approval.py, docs/CONFIG.md (184); plus generate/naming.py (99), edit.py 100-192 and 440-520, generate/mass.py 30-60, generate/segmentation.py 78-150, generate/engine.py 920-960, vcs/roles.py 1-40, vcs/snapshot.py 8-20/100-110, describe.py 47-69, and the config JSON of a freshly created `blank` project (created under audit-transparency/cfgwork/, observed), a `typo` experiment project, resources/examples/templates/config-demo-values/*, flatsat/config/*. Persona tags: [SYS] systems, [ELEC] electrical, [AIT] assembly/integration/test. Downstream consumers (generate/sizing.py, drc/*, outputs/*) were not opened by me; "consumer unverified" means that. Section "AIT view" at the end answers what an AIT engineer can and cannot trace or change.

## C1 Hard-coded constants, defaults, margins, rules

### C1a. Values that live in config files (written into every new project)

All seven files are plain JSON, written with sorted keys (alphabetical, not logical order), no comments, no unit field, no source field, no rationale per key. Units exist only as key-name suffixes (_a, _m, _v, _c, _ohm_m, _mohm, _fraction) and in the GUI-only `FIELD_INFO` table (configcheck.py:464-492). The only per-file metadata is one boolean `placeholder`. `null` = not set (CONFIG.md:38).

| id | file:line | value / rule | what it does, output or decision fed | unit | visible? | editable? | R |
|---|---|---|---|---|---|---|---|
| CFG-C1-001 | model/config.py:25-26 | segmentation `"mode": "per_connector_pair"` (others: per_unit_pair, per_zone_pair) | How interfaces are grouped into harnesses (harness count, numbering, pin allocation). Shipped placeholder:true | none | segmentation.json, config dialog | yes; an unknown value is NOT rejected by the validator, generation silently falls back (C2-002) [SYS][AIT] | R2 R3 R4 |
| CFG-C1-002 | model/config.py:32-34 | segregation `forbid_nominal_with_redundant: true`, `forbid_pyro_with_other: true`, `category_pairs_to_separate: null` | Segregation rules. Two hard-wired booleans plus one pair list; no general rule table [SYS][ELEC] | bool | segregation.json | yes (bool validated, configcheck.py:207-210) | R3 R12 |
| CFG-C1-003 | model/config.py:41 | derating `contact_current_factor: null` | Fraction of contact rating usable; unset = check "not checked" [ELEC] | fraction | derating.json | yes; 0<x<=1 (configcheck.py:122-125) | R3 R5 |
| CFG-C1-004 | model/config.py:42 | `bundle_derating: null` | One scalar bundle factor for every bundle [ELEC] | fraction | derating.json | yes; 0<x<=1. Replaced by `bundle_factor_by_count` when set (CONFIG.md:168; consumer unverified) | R3 R4 |
| CFG-C1-005 | model/config.py:43 | `temperature_derating: null` | A typed scalar; NOT computed from `max_ambient_temperature_c` and a wire rating [ELEC] | fraction | derating.json | yes, 0<x<=1 | R1 R4 |
| CFG-C1-006 | model/config.py:44 | `max_ambient_temperature_c: null` | Only compared with part ratings in rule temperature-margin (CONFIG.md:86); does not feed `temperature_derating` [ELEC] | degC | derating.json | yes; only >-273.15 enforced (standard_profiles.py:198-202) | R4 |
| CFG-C1-007 | model/config.py:45 | `max_voltage_drop_v: null` | Allowed drop over a wire path (sizing, DRC) [ELEC] | V | derating.json | yes, must be >0 (configcheck.py:131-139), so 0 cannot disable | R3 |
| CFG-C1-008 | model/config.py:46 | `spare_pin_fraction: null` | Share of pins that must stay spare [ELEC][AIT] | fraction | derating.json | yes, 0<=x<1 (configcheck.py:126-129) | R3 |
| CFG-C1-009 | model/config.py:47 | `ampacity_a_by_awg: null` ({"20": amps}) | One ampacity table for the project, keyed by AWG only (no wire spec, insulation class, vacuum/air, temperature) [ELEC] | A | derating.json | yes; gauges 0..40, A>0, non-increasing with AWG number (configcheck.py:166-194) | R3 R4 |
| CFG-C1-010 | model/config.py:48 | `contact_rating_key: "contact_current_a"` (only non-null default in derating) | Names the `Part.ratings` key read as contact current rating [ELEC] | key name | derating.json | yes, any non-empty string (standard_profiles.py:203-205) | R2 R4 |
| CFG-C1-011 | model/config.py:55-62 | `wire_part_by_construction`: single, coax, twisted_pair -> EX-WIRE-SINGLE; twisted_shielded_pair, quad, twinax -> EX-WIRE-TWISTED-SHIELDED | Wire library part used for each generated wire; one part per construction, independent of gauge/category/voltage [SYS][ELEC][AIT] | part ID | generation.json; a bad part gives a "wire_part" warning (engine.py:934-946) | yes; not range-checked by configcheck | R3 R4 R7 |
| CFG-C1-012 | model/config.py:63 | `default_gauge_awg: null` | Gauge when none decided (consumer unverified) [ELEC] | AWG | generation.json | yes, int 0..40 (standard_profiles.py:195-197) | R3 |
| CFG-C1-013 | model/config.py:64 | `service_loop_m: null` | Extra length at each end; lengths "excluded while unset" (configcheck.py:44 used_by). One value for all wires, no cut tolerance key [AIT][ELEC] | m | generation.json | yes, >=0 | R3 R5 |
| CFG-C1-014 | model/config.py:65 | `conductor_resistivity_ohm_m: null` | Resistivity for voltage drop; no reference temperature or coefficient key [ELEC] | ohm m | generation.json | yes, >0 | R3 R4 |
| CFG-C1-015 | model/config.py:66 | `power_signal_gap_pins: null` ("0 used while unset", configcheck.py:51) | Empty pins between power and signal pins at allocation [ELEC][AIT] | pins | generation.json | yes, whole number >=0 | R3 |
| CFG-C1-016 | model/config.py:67 | `mass_margin_fraction: null` | Margin on harness mass: margin_g = total_g * fraction (mass.py:39-47) [SYS] | fraction | generation.json, outputs | yes, >=0, no upper limit | R3 R5 |
| CFG-C1-017 | model/config.py:68-70 | `test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v`: null | One global limit for every wire in the test tables (outputs/tables.py not opened) [AIT][ELEC] | ohm / Mohm / V | generation.json | yes, each >0; no per-wire/gauge/length limit | R3 R12 |
| CFG-C1-018 | model/config.py:71-72 | `shield_end_a/b: null` (backshell_360, pigtail, floating) | Global shield grounding concept for all shields; coax excepted (physical.py:17-19) [ELEC][AIT] | enum | generation.json | yes, 3 choices only (configcheck.py:22,146-148) | R4 R7 |
| CFG-C1-019 | model/config.py:79-82 | naming `harness "W{n:03d}"`, `box_connector "{unit}-J{n:02d}"`, `cable_connector "{harness}-P{n}"`, `wire "{harness}-{n:03d}"` (placeholder:false) | ID of every harness, cable connector, wire; the wire ID is the physical wire marker [AIT][SYS] | pattern | naming.json | harness, cable_connector, wire: yes. `box_connector` is dead: IDs hard-coded (edit.py:487, devices.py:321-323) | R2 R3 |
| CFG-C1-020 | model/config.py:86 | emc `classes: null`, `conflicting_class_pairs: null` | Class pairs that may not share a harness. `classes` is "kept for reference, no rule reads it" (CONFIG.md:108; not verified in code) [ELEC] | names | emc.json | yes; free text, not checked against interface-type emc_class (configcheck.py:93-100) | R3 R12 |
| CFG-C1-021 | model/config.py:92-103 | titleblock `fields`: all 10 fields in order | Title block content of drawings [AIT][SYS] | names | titleblock.json | yes; known names, no duplicates (configcheck.py:283-314). Code default for empty is another 6-field list (configcheck.py:280) | R3 R9 |
| CFG-C1-022 | model/config.py:7-9,20; project.py:76-77 | Seven fixed config names; any `placeholder:true` file flags results | A file is "placeholder" or "reviewed", nothing between; unknown names quarantined (loader.py:255) [SYS] | - | loader info line (loader.py:360-362) | flag editable (configcheck.py:708-716), no reviewer/date/reason | R2 R8 R9 |

### C1b. Keys read by code, absent from a new project's files

| id | file:line | value / rule | what it does | unit | visible? | editable? | R |
|---|---|---|---|---|---|---|---|
| CFG-C1-030 | generate/naming.py:9-16 | defaults `shield "{harness}-S{n}"`, `branch "{harness}-B{n}"`, `segment "{harness}-L{n}"` (+ the 3 above) | Used when key missing or template invalid; invisible in the shipped file [AIT] | pattern | CONFIG.md:117-119 only | yes, by adding the key | R2 R3 |
| CFG-C1-031 | counterparts.py:17-25 | `DEFAULT_COUNTERPARTS` tx/rx, txd/rxd, txp/rxp, txn/rxn, dout/din, mosi/miso, sdo/sdi | Which pins are paired as two ends of a line (link review, pairing proposal). sout/sin (used by the SpaceWire starter type, starter.py:136-138) is not in the table [SYS][ELEC] | words | CONFIG.md:128 | yes, `naming.signal_counterparts` replaces the whole table | R2 R3 R12 |
| CFG-C1-032 | configcheck.py:280 | `TITLEBLOCK_DEFAULT = (project, harness_id, title, revision, status, sheet)` | Used when `fields` is missing/empty/invalid [AIT] | names | no | via titleblock.json | R3 |
| CFG-C1-033 | vcs/roles.py:20-22 | `release_distinct_roles` unset = false; `FUTURE_DAYS = 1` | Four-eyes release off by default; a date up to 1 day ahead accepted [SYS][AIT] | bool / day | CONFIG.md:134-148 | flag by CLI; FUTURE_DAYS code only | R3 R8 |
| CFG-C1-034 | generate/segmentation.py:86,147 | `mode` defaults to per_connector_pair; `forbid_nominal_with_redundant` is true unless exactly `false` | Missing key means "keep chains apart" [SYS] | - | note only for unknown mode (segmentation.py:88-89) | via key | R2 R3 |
| CFG-C1-035 | generate/mass.py:39-47 | margin applied only when `mass_margin_fraction` is a number | Unset margin = no margin, no message at this point [SYS] | g | outputs (not opened) | via key | R1 R12 |

### C1c. Standard profiles (values hard-coded in code, applied only on request)

`standard_profiles.py` is the only place standard numbers live. Applied by `config DIR --apply-profile NAME` (CLI help seen). It fills only `null` keys, sets the whole file to `placeholder:true`, and cites a requirement ID per value (standard_profiles.py:1-12, 113-125).

| id | file:line | value / rule | what it does | unit | visible? | editable? | R |
|---|---|---|---|---|---|---|---|
| CFG-C1-040 | standard_profiles.py:45-46 | contact_current_factor 0.5 (ECSS-Q-ST-30-11_0140051, "Table 6-10 current 50 %") [ELEC] | Contact current derating | fraction | CLI output, form "source" (configcheck.py:534-541) | key overwritable | R3 R12 |
| CFG-C1-041 | standard_profiles.py:47-50 | connector_voltage_factor_withstand 0.25; _rated 0.75 ("whichever is lower") [ELEC] | Connector working voltage check | fraction | same | same | R3 |
| CFG-C1-042 | standard_profiles.py:51-52,55-56 | connector_temperature_margin_c 30; wire_temperature_margin_c 50 [ELEC] | Temperature margin rule | degC | same | same | R3 |
| CFG-C1-043 | standard_profiles.py:53,54 | rf_power_factor 0.75 (recorded, no rule); wire_voltage_factor 0.5 [ELEC] | RF power / wire voltage derating | fraction | same | same | R3 |
| CFG-C1-044 | standard_profiles.py:37-39 | `BUNDLE_K` {"1":1,"2":0.9,"3":0.81,"4":0.76,"5":0.71,"6":0.66,"7":0.62,"8":0.6,"9":0.59,"10":0.57,"15":0.49,"25":0.4,"50":0.29,"100":0.21,"200":0.15,"300":0.12} [ELEC] | Bundle K by wire count ("Table 6-41, full bundle"); counts between entries use the next listed count (CONFIG.md:168; consumer unverified) | factor | derating.json after profile | overwritable | R1 R3 |
| CFG-C1-045 | standard_profiles.py:41,59-60 | `PARTIAL_L` below_25 1.2, 25_to_50 1.1, above_50 1; "not applied automatically" [ELEC] | Recorded, never applied | factor | CONFIG.md:169 | n/a | R4 R12 |
| CFG-C1-046 | standard_profiles.py:61-62 | max_mating_cycles 50 [ELEC][AIT] | Mating cycle check | cycles | same | same | R3 |
| CFG-C1-047 | standard_profiles.py:63-64 | power_return_gap_pins 1 [ELEC] | Gap between power and return pins | pins | same | same | R3 |
| CFG-C1-048 | standard_profiles.py:67-70,218-220 | emc shield_bonding "both_ends_backshell"; same_class_one_bundle True. `shield_bonding` accepts only that one value [ELEC][AIT] | Shield bonding and bundle rules | enum / bool | same | single-choice enum | R4 |
| CFG-C1-049 | standard_profiles.py:74-81,129-142 | Validation constants: factors in (0,1]; K up to 1; L up to 2 (`upper: float = 2`); temperature margins >=0 [ELEC] | Out-of-range = error | - | error text | none | R12 |
| CFG-C1-050 | standard_profiles.py:43-72 | `PROFILES` = two profiles in a Python dict [SYS] | Adding a profile means editing code | - | `--apply-profile` help | none | R13 R3 |

### C1d. Model-level limits and domains (code only)

| id | file:line | value / rule | what it does | unit | visible? | editable? | R |
|---|---|---|---|---|---|---|---|
| CFG-C1-060 | model/base.py:104,107 | `MAX_LENGTH_M = 10_000.0`, `LengthM` ge 0 | A wire/segment length outside 0..10 000 m is set aside on load [AIT] | m | error on load | none | R3 R5 |
| CFG-C1-061 | model/base.py:105; library.py:29 | `MAX_PIN_COUNT = 1000`; pin_count 1..1000 [ELEC] | Part size limit | pins | error | none | R3 |
| CFG-C1-062 | model/base.py:108; physical.py:94-95,140 | `MAX_LENGTH_MM = 100_000.0` for strip and accessory lengths ("guard against a typing slip") [AIT] | No gauge/contact-based strip range exists | mm | error | none | R3 R12 |
| CFG-C1-063 | units.py:5; model/base.py:106 | `AWG_MIN, AWG_MAX = 0, 40`, integer only [ELEC] | Gauges outside 0..40 refused; no 1/0, 2/0, no mm2 sizing | AWG | error | none | R3 R5 |
| CFG-C1-064 | units.py:12,17,21 | `d = 0.127 mm * 92**((36-n)/39)`; `A = pi/4*d^2`; shown `AWG 20 (0.519 mm²)` with .3f [ELEC] | Solid-conductor geometry from the AWG definition; not a stranded nominal area (MIL-W-22759/EN 3475) | mm / mm2 | label shows mm2; formula only in docstring | none | R1 R5 |
| CFG-C1-065 | model/base.py:91-100; review.py:19-21 | Name max 200 chars, Text max 5000, no control/private-use chars; Justification min 10, max 2000 [SYS] | Waiver/release reason needs only 10 characters | chars | error | none | R3 R7 |
| CFG-C1-066 | ids.py:8-9,11-15; edit.py:173 | `ID_RE ^[A-Za-z][A-Za-z0-9_.\-]{0,63}$`; `PIN_RE ^[A-Za-z0-9][A-Za-z0-9_.\-]{0,15}$`; reserved con/prn/aux/nul/com1-9/lpt1-9; uniqueness by casefold [AIT] | Every ID incl. wire IDs (wire markers) must match; pin names max 16 chars, no spaces | chars | error text | none | R3 |
| CFG-C1-067 | model/project.py:16-17 | `SCHEMA_VERSION = 1`, `DEFAULT_ZONES = ("panel-A","panel-B")` [SYS] | Two default lanes in a new project | - | layout.json | zones editable | R3 |
| CFG-C1-068 | model/library.py:27-28,39 | Part `approval="pending"`, `unverified=False`, `conductors` 1..64 [SYS][AIT] | Conductors divides wire length in mass/BOM (mass.py:35-37) | count | parts list | yes | R2 R7 |
| CFG-C1-069 | model/library.py:46-47; generation.py:13 | LibraryInfo name "Project parts library", version "0"; `next_harness_number >= 1`, numbers never reused [SYS] | Library provenance defaults are placeholders | - | manifest.json | yes | R9 |
| CFG-C1-070 | physical.py:19,104-105 | `COAX_SHIELD_END = "backshell_360"`; ShieldGroup default `end_a = end_b = "floating"` [ELEC][AIT] | Coax shield bonded both ends regardless of project concept | enum | CONFIG.md:57 | coax: none | R4 R7 |
| CFG-C1-071 | physical.py:13,32,150-151 | Termination crimp/solder/unspecified, pin default `unspecified`; Harness `revision="A"`, `status="draft"` [AIT] | Closed 3-value termination list | enum | yes | closed list | R4 |
| CFG-C1-072 | physical.py:130-141 | Accessory: "Nothing is computed from it"; quantity 1..9999 [AIT] | Sleeving, heat-shrink, label, backshell lengths and counts are typed in, never derived | mm / count | accessories list | free entry | R1 R4 |
| CFG-C1-073 | wirecolours.py:8-27 | 12 IEC 60757 names/codes with screen hex, aliases gray->GY, purple->VT, `UNSET_COLOUR "#808080"` [AIT] | Colour name to code on drawings and build sheet | code | drawings | code only | R3 R13 |
| CFG-C1-074 | wirecolours.py:44-47 | Two known colours "a/b" -> "YE/GN" drawn grey; unknown colour -> `key[:6]` [AIT] | Unknown colour text is cut to 6 characters in the code shown, no warning | chars | no | none | R5 R12 |
| CFG-C1-075 | first_connector.py:22-23,37,48,50-51 | `_TAIL (-\d+)?(-[MF])?$`, `_LEAD ^(.*?)\s+\d+-pin\b`, sort label, family, pins, gender [SYS] | Part offered as "family, pins, gender" only if ID and description follow the text convention | text | choice list | none | R3 R4 |
| CFG-C1-076 | starter.py:98-103 | `mates_with` = part ID with trailing M/F swapped [SYS][AIT] | Counterpart relies on ID spelling; dropped if the other letter part is absent | text | parts list | per part | R4 |
| CFG-C1-077 | edit.py:112-125 | `_POWER` set; `_MICROD_BY_TYPES = {1:9, 2:15, 3:21, 4:25}`; 5+ types -> 31-pin; RF -> EX-SMA-F; Ethernet -> EX-RJ45-F [SYS][ELEC][AIT] | Device template picks the box connector part from the NUMBER of interface types carried, not pin demand, current or contact size | pins | only as part ID afterwards | part changeable later | R1 R4 |
| CFG-C1-078 | edit.py:32-33,208-209 | `LANE_WIDTH = 470.0`, `LANE_X0 = 10.0`, lane x = X0 + i*W + 20 [SYS] | Diagram placement; zone assigned from x (edit.py:469) | scene units | canvas | none | R3 |

### C1e. Starter library and interface types (starter.py)

All 28 parts and 17 interface types carry `unverified: true`, parts `approval: pending`, no manufacturer, part number, mass or rating (observed in library/*.json of the new project). They are marked as example only by the EX- prefix and "(example)" in descriptions.

| id | file:line | value / rule | what it does | unit | visible? | editable? | R |
|---|---|---|---|---|---|---|---|
| CFG-C1-090 | starter.py:14-92 | 24 connectors: D-sub 9/15, Micro-D 9/15/21/25/31, RJ45 8P8C, MDM 21, circular 19, SMA, TNC (M and F) [SYS][ELEC][AIT] | Connector menu for new devices; pin count creates pins "1".."N" (edit.py:481). No ratings, contact size/part or backshell | pins | parts list | per part | R2 R3 |
| CFG-C1-091 | starter.py:93-96,113 | Wire parts EX-WIRE-SINGLE, EX-WIRE-TWISTED-SHIELDED (`conductors=2`), EX-SLEEVE, EX-LABEL; no AWG, mass, temperature, voltage, spec [SYS][ELEC][AIT] | A wire part has no gauge; mass_per_m_g is one number per part for every AWG (mass.py:30-38) | g/m | parts list | yes, but C1-011 maps one part per construction | R1 R4 |
| CFG-C1-092 | starter.py:126-158 | 17 interface types with construction, shielding, directions, pair names, e.g. power_primary twisted_pair/none; rs422 twisted_shielded_pair/per_pair; can overall; pyro overall; rf_coax coax/none; ethernet only 4 signals [SYS][ELEC][AIT] | Encodes wires per interface, shield groups, wire part, mass; `unverified:true` but no source note | - | types list | yes | R2 R3 |
| CFG-C1-093 | starter.py:122,160-165 | `impedance_ohm`, `emc_class`, `default_gauge_awg` left None [ELEC] | Gauge and EMC class come from nowhere unless entered per type | - | types list | yes | R2 |
| CFG-C1-094 | samples.py:227-231,240,247,250,254; flatsat/config | sat15_full example numbers: ampacity 26..16 AWG = 1,2,3,5,7,10 A; bundle 0.6; temp 0.9; contact 0.5; drop 1.0 V; rho 1.7e-8; loop 0.1 m; shields backshell_360/floating; margin 0.1; continuity 1.0; isolation 100 Mohm/500 V; max_current 2.0 A power, 1.0 A thermal; 12 g/connector; 4 g/m; segment 1.0+0.25k m [SYS][ELEC][AIT] | Shipped as flatsat template (title says EXAMPLE). `config-demo-values/` differ: bundle 0.8, contact 0.75, loop 0.05, isolation 100 V, rho 1.72e-8, continuity 0.5 | mixed | README.md warning; project name | yes | R2 R3 |
| CFG-C1-095 | samples.py:156-206 | stress_project: 21 pins, 10 signals, 12 zones, per_zone_pair | Test fixture | - | no | no | - |

## C2 Hidden assumptions

| id | file:line | description (what is hidden and why it matters) | R |
|---|---|---|---|
| CFG-C2-001 | model/config.py:15; observed `typo` project | `values` is `dict[str, Any]`: an unknown key (`bundel_derating`) is accepted without message; a typo leaves the intended value `null`. [ELEC][SYS] | R3 R12 |
| CFG-C2-002 | segmentation.py:86-89; observed | `segmentation.mode = "per_banana"` passes `validate` and `drc`; generation then uses per_connector_pair with a note. configcheck.validate (103-163) has no check for `mode` or `wire_part_by_construction`. [SYS][AIT] | R4 R12 |
| CFG-C2-003 | generate/naming.py:28-34,68-86; observed | Invalid or non-distinct naming template (e.g. `wire: "X"`) is replaced by the default at generation; warning says only "naming template 'naming.wire' is not valid; the default was used", not why. Digit width >=3 refused (naming.py:72), distinctness tested for n=1..200 only. Wire markers change. [AIT][SYS] | R3 R12 |
| CFG-C2-004 | configcheck.py:122-125; CONFIG.md:86 | `temperature_derating` and `max_ambient_temperature_c` are independent. Nothing derives the factor from ambient and wire rating; the engineer computes it outside the tool. [ELEC] | R1 R4 |
| CFG-C2-005 | configcheck.py:166-194 | Ampacity is one table by AWG; conditions (air/vacuum, insulation temperature rating, conductor count) unstated. Validation forces non-increasing current with AWG number. [ELEC] | R4 R1 |
| CFG-C2-006 | model/config.py:65 | Resistivity is a single number; no key for reference temperature or coefficient. Demo 1.72e-8 vs example 1.7e-8. Consumer (sizing.voltage_drop_v) not opened. [ELEC] | R1 R2 |
| CFG-C2-007 | generate/engine.py:954 | `conductors = 2 if category in ("power","ground") else 1`: voltage-drop path of power/ground is assumed out and back, all else one conductor. Fixed in code. [ELEC] | R2 R4 |
| CFG-C2-008 | model/config.py:58-60; mass.py:35-37 | `quad` maps to a part with `conductors=2`, but a quad has 4 conductors; mass and BOM metres divide each wire length by 2, so 4 wires count as 2 cables per metre of route. Shipped in every new project. [SYS][AIT] | R1 R4 |
| CFG-C2-009 | mass.py:30-38 | Wire mass = part.mass_per_m_g * length / conductors, independent of gauge. [SYS][ELEC] | R1 R4 |
| CFG-C2-010 | units.py:9-17 | mm2 beside AWG computed as solid circular conductor; indicative for stranded wire. [ELEC] | R1 R5 |
| CFG-C2-011 | physical.py:17-19 | Coax shield always bonded both ends and exempt from `shield_end_a/b`; not overridable. [ELEC][AIT] | R4 R7 |
| CFG-C2-012 | configcheck.py:597 | Typed numbers: `"1,5"` -> 1.5 but also `"1,000"` -> 1.0 (thousand separator misread). A suffix equal to the field unit is stripped without conversion; other units (mV, cm, mm) fail with "not a number". [ELEC][AIT] | R5 |
| CFG-C2-013 | configcheck.py:206,216 | Ampacity CSV import: "," -> "." in amperes, header recognised only as first row when gauge is not an integer; unit assumed A. [ELEC] | R5 R14 |
| CFG-C2-014 | configcheck.py:534-541 | Displayed "source" is inferred by comparing the stored number with the profile value: a hand-typed 0.5 shows as ECSS; a profile value changed slightly shows "set in the project". No source field stored. [ELEC][SYS] | R3 R8 R9 |
| CFG-C2-015 | standard_profiles.py:113-125 | A profile fills only `null` keys and keeps different values; the whole file flips to `placeholder:true` even for unchanged keys; result mixes ECSS and hand values with no per-key tag. [ELEC][SYS] | R2 R8 |
| CFG-C2-016 | counterparts.py:30,52-72 | Pairing: first word of the name found in the table decides; a prefix may be missing on one side (line 71); words are letters only. SIN/SOUT, CANH/CANL not covered by default. [ELEC][SYS] | R4 R12 |
| CFG-C2-017 | edit.py:112-125 | Connector chosen from the count of interface types, see C1-077; 9..31 pins by lookup. [SYS][ELEC] | R1 R4 |
| CFG-C2-018 | starter.py:98-103; first_connector.py:37 | Mate and family are text conventions on the part ID (`-M`/`-F`, `-NN-`). [SYS][AIT] | R4 |
| CFG-C2-019 | describe.py:47-55 | Gender from the first word "male"/"female" in the part description, else unspecified; "male plug ... mates with female socket" gives male. [AIT][SYS] | R1 |
| CFG-C2-020 | project.py:76-77; configcheck.py:708-716 | `placeholder:false` with `null` values still counts as reviewed; flag change records neither who, when nor why. [SYS] | R7 R8 |
| CFG-C2-021 | library.py:43-45; observed project.json | "The tool never reads a clock into project data": no creation or save timestamp in project files (only `tool_version`). Provenance of when numbers were set is absent by design. [SYS] | R8 R9 |
| CFG-C2-022 | part_approval.py:19-40 | Approving sets `approval=approved` and `unverified=false` together; no approver, date, reason or datasheet reference stored. [AIT][SYS] | R7 R8 |
| CFG-C2-023 | physical.py:93-95 | Strip lengths are plain numbers per wire end, set by a person or CSV import; nothing here derives them from gauge, contact or crimp spec. [AIT] | R1 R7 |
| CFG-C2-024 | samples.py:225-231 | `sat15_full` writes example numbers into a placeholder project; the only label is the project name. [SYS][ELEC] | R2 R9 |

## C3 Outputs shown without derivation

| id | file:line | description | R |
|---|---|---|---|
| CFG-C3-001 | configcheck.py:534-541 | "source" in the engineering values form: requirement ID by value match, no equation or table cell for K, L or factors. [ELEC] | R1 |
| CFG-C3-002 | configcheck.py:34-71,231-273 | Hand-over report: "N of 17 set", MISSING lines with fixed `used_by` strings; no trace of which output used which value. [SYS][ELEC] | R1 R6 |
| CFG-C3-003 | model/generation.py:16-17 | `provenance` = "rule: reason" text lines per object; no inputs with units or intermediates in the model. [SYS][ELEC][AIT] | R1 |
| CFG-C3-004 | units.py:20-21 | `AWG 20 (0.519 mm²)` shown; formula not shown with the value. [ELEC] | R1 R5 |
| CFG-C3-005 | wirecolours.py:34-47 | Colour code ("BK", "YE/GN", or 6-character cut) shown without telling which of three branches produced it. [AIT] | R1 R12 |
| CFG-C3-006 | first_connector.py:40-52 | Connector choice list built by text parsing of ID and description; user cannot see why a part is or is not offered. [SYS] | R1 |
| CFG-C3-007 | edit.py:453-500 | New device arrives with J01.. connectors of tool-chosen parts and pins; the rule is not shown. [SYS][ELEC] | R1 R6 |
| CFG-C3-008 | counterparts.py:61-72 | Link review pairs TX with RX by table; the matched table row is not shown (consumer links.py not opened). [SYS][ELEC] | R1 R12 |
| CFG-C3-009 | standard_profiles.py:113-126 | Profile plan lists applied and kept values at command time; the file keeps no per-key note afterwards. [ELEC] | R8 R9 |

## C4 Forced single options

| id | file:line | description | R |
|---|---|---|---|
| CFG-C4-001 | logical.py:10-16 | Closed enumerations: Category (9), Construction (6), Shielding (3), Side, Direction, Flow. A new category or construction needs code. [SYS][ELEC] | R13 R4 |
| CFG-C4-002 | library.py:11-15,35 | PartCategory fixed: connector, contact, backshell, wire, sleeving, label. No splice, terminal, ferrule, heat-shrink or tool type; tool is free text `Part.tool`. [AIT][SYS] | R13 R4 |
| CFG-C4-003 | physical.py:11-16,127 | Closed lists: Gender, Role, Termination (crimp/solder/unspecified), HarnessStatus, ShieldKind, ShieldEnd, PinRole, AccessoryKind. No IDC, ultrasonic, weld, ring-terminal. [AIT][ELEC] | R13 R4 |
| CFG-C4-004 | units.py:5,8-12; base.py:106 | Wire size only AWG integers 0..40; no metric wires, no 1/0.., no half sizes. [ELEC] | R4 R5 |
| CFG-C4-005 | config.py:7-9; loader.py:255 | Seven config files only; no own rule or curve file; unknown names quarantined. [SYS] | R3 R13 |
| CFG-C4-006 | configcheck.py:22,146; physical.py:19 | Shield grounding is one global pair; no per-interface or per-category value; coax cannot follow it. [ELEC][AIT] | R4 R7 |
| CFG-C4-007 | model/config.py:55-62 | One wire part per construction for the project (not per gauge/category/voltage); a different part only by overriding a generated wire (physical.py:90). [SYS][ELEC][AIT] | R4 R7 |
| CFG-C4-008 | configcheck.py:122-139 | Validator forbids: factors >1 or <=0, max drop 0, spare fraction 1, ampacity rising for thinner wire, fractional pin gap, shield bonding other than both_ends_backshell. Domain assumptions, no "accept and flag" override. [ELEC] | R7 R12 |
| CFG-C4-009 | ids.py:8-9; base.py:91 | ID grammar (letter first, 64 chars, no spaces), pin grammar (16 chars) for all IDs; "A 1" or a customer wire number with spaces cannot be entered. [AIT] | R3 |
| CFG-C4-010 | review.py:19-21 | Waiver/release comment: at least 10 characters, free text, no reference field. [SYS] | R7 R8 |
| CFG-C4-011 | units.py; base.py:104-108 | SI throughout: m (wire/segment), mm (strip/accessory), g, degC, ohm m; no unit selector. [SYS] | R5 |
| CFG-C4-012 | templates.py:33-57 | New projects start from one of five bundled copies; a team cannot register its own template. [SYS] | R3 R13 |
| CFG-C4-013 | model/config.py:20-105 | Starting state of each config file (keys present, which null) defined in code; no user-chosen starting config. [SYS] | R3 |

## C5 Inputs and outputs

| id | file:line | description | R |
|---|---|---|---|
| CFG-C5-001 | templates.py:74-91; observed tree | New project writes project.json (name, description, schema_version, tool_version), config/*.json (7), library/*.json (7 incl. manifest.json), logical/interface_types.json, logical/layout.json, .gitattributes, .gitignore. Sorted keys, 2-space JSON, nulls written; no date, author or content hash. `.gitignore` is written outside templates.py. [SYS][AIT] | R9 R14 |
| CFG-C5-002 | templates.py:94-102 | `copy_import_templates` copies CSV, netlist, scripts, `config-demo-values/`, `ampacity-DEMO-ONLY.csv`. Demo numbers labelled in README only, JSON carries `placeholder:true`. [ELEC][AIT] | R9 |
| CFG-C5-003 | configcheck.py:197-228; cli/data.py:435-444 | `config --ampacity-csv` reads gauge,amperes and writes `ampacity_a_by_awg`; file name/hash not recorded; no table export. [ELEC] | R10 R14 |
| CFG-C5-004 | cli/data.py:455-469 (seen in grep); configcheck.py:336-420 | `config --counterparts`, `--distinct-roles`, `--apply-profile` write config keys. Profile name not stored. [SYS][ELEC] | R8 R9 |
| CFG-C5-005 | vcs/roles.py:6-8; CONFIG.md:146 | With distinct roles on and `--by` omitted, the name is read from Git `user.name` (gitname.py not opened). Implicit input to change records. [SYS][AIT] | R8 R14 |
| CFG-C5-006 | vcs/snapshot.py:10-18,106-110 | Release freezes derating, emc, segregation, titleblock and some generation keys into the baseline; segmentation and naming are not frozen. Config edits before a release leave no log entry. [SYS][ELEC] | R8 R9 |
| CFG-C5-007 | model/review.py:94-106 | Change log only records review/release/new_revision (id, harness, revision, by, when, comment); no old/new value; `by`/`when` typed text. [SYS][AIT] | R8 |
| CFG-C5-008 | loader.py:355-362 | A missing or unreadable config file is replaced by the built-in default with an INFO `config_defaulted`; not blocking. [SYS] | R12 R14 |
| CFG-C5-009 | model/base.py:29-43 | Newer optional fields are omitted from files while at default (byte-identical for old tools). A reader cannot see the full schema from a file. [SYS] | R14 |
| CFG-C5-010 | wirecolours.py:34-47 | Colour code on build sheet derives from the in-code table; unknown colour exports as a 6-character cut. [AIT] | R10 R14 |

## C6 Customisation points that do exist

| id | file:line | what it offers | R |
|---|---|---|---|
| CFG-C6-001 | model/config.py; CONFIG.md:20-36; gui/config_dialog.py:313-353 | Seven JSON files in `config/`, editable by hand or in the config dialog via `plan_set_value`; value re-validated, reason shown (configcheck.py:670-705), release lock checked. | R2 R3 |
| CFG-C6-002 | configcheck.py:464-492 | `FIELD_INFO` gives label and unit for 28 keys (fixed GUI list). Form text accepted: "0,5 V", "power + analog", "20: 5, 22: 3.5". | R5 |
| CFG-C6-003 | configcheck.py:33-71 | Hand-over checklist `config DIR` (17 required + 11 optional values), per-file `placeholder` flag, exit code 1 while missing. | R2 R6 |
| CFG-C6-004 | generate/naming.py; CONFIG.md:114-119 | Name patterns for harness, cable connector, wire, shield, branch, segment, checked for validity and distinctness. | R3 |
| CFG-C6-005 | counterparts.py:27-28,105-111 | `naming.signal_counterparts`: own word pairs, validated, `none`/`default` supported, via dialog or CLI. | R3 R4 |
| CFG-C6-006 | configcheck.py:276-314 | `titleblock.fields`: choose and order title block fields. | R3 R9 |
| CFG-C6-007 | standard_profiles.py:94-126 | Opt-in ECSS profiles with requirement IDs, only on unset keys, flagged placeholder. | R3 R12 |
| CFG-C6-008 | edit.py:975-992 | `generation.wire_colour_by_signal`: wire colour per signal name, free text; not in the shipped file. | R3 R4 |
| CFG-C6-009 | generate/engine.py:934 | `wire_part_by_construction` maps construction to any library wire part. | R4 R7 |
| CFG-C6-010 | model/library.py:33 | `Part.ratings` is a free dict of numeric values; the key read for contact current is configurable. | R2 R13 |
| CFG-C6-011 | model/physical.py:85-95 | Wire `locked`, `manual`, `strip_a_mm/strip_b_mm`, `gauge_awg`, `part_id`, `colour`, `length_m`, `label`, `note` can be set by a person and are kept on regeneration. | R7 |
| CFG-C6-012 | CLI help (schema, new) | JSON Schemas of project files can be written; five bundled templates. | R3 R11 |
| CFG-C6-013 | model/review.py:35-48 | Waivers with mandatory justification (>=10 chars), tied to a finding hash. | R7 R12 |
| CFG-C6-014 | part_approval.py:19-40 | A part is approved only by a person action; the tool never approves by itself. | R7 |

## AIT view (what an AIT engineer can and cannot trace or change in this area)

- Can change: wire, connector and harness labels (`label` fields), wire colour, strip length per end, contact and tool on a pin, accessories, naming patterns for harness/connector/wire IDs, test limits (one global value each), service loop (one global value).
- Cannot trace: why a strip length, contact or termination was chosen (typed or imported, nothing derived or sourced); why a wire has a given colour code (three-branch lookup, unknown colour cut to 6 characters); how a cut length is derived from `service_loop_m` and rounded (consumer not in this area); where a test limit comes from (global number, no reference).
- Cannot change: the termination list (crimp, solder, unspecified), part categories (no tool, splice, terminal, ferrule, heat-shrink part), one test limit for every wire regardless of gauge or length, the ID grammar (pins 16 characters, IDs 64); a failing naming template silently reverts to the default, so wire markers can change without a clear cause.
- Not recorded: who approved a part and when, who set a config value and why, which crimp tool setting was used as built (`tool` is free text on the contact part only).

## Top findings

1. CFG-C1-005 / CFG-C2-004 [ELEC]: `temperature_derating` is a typed scalar unrelated to `max_ambient_temperature_c` and to any wire rating; the key derating input has no model or derivation.
2. CFG-C2-005 / CFG-C1-009 / CFG-C1-044 [ELEC]: one ampacity table by AWG only (no wire spec, insulation, environment) with forced monotony; bundle factor is a scalar or an ECSS table with no derivation shown.
3. CFG-C2-008 / CFG-C2-009 / CFG-C1-091 [SYS][ELEC][AIT]: wire mass is per part not per gauge, and the shipped `quad` mapping uses a 2-conductor part so quad mass and BOM metres are doubled; one part per construction cannot follow gauge.
4. CFG-C2-001 / CFG-C2-002 / CFG-C2-003 [SYS][AIT]: unknown config keys, invalid `segmentation.mode` and invalid naming patterns are accepted or silently replaced; `validate` did not report a bundle_derating of 1.5 that `drc`, `generate` and `config` did (observed; CONFIG.md:42 says otherwise).
5. CFG-C1-022 / CFG-C2-020 / CFG-C2-021 / CFG-C5-007 [SYS]: review status is one boolean per file with no reviewer, date or reason; no timestamps in project data; change log covers review/release/revision only, not config edits.
6. CFG-C1-017 / CFG-C4-007 [AIT]: test limits are three global numbers; wire part, test limit and shield ends cannot vary per interface, gauge or length, so AIT cannot trace a limit to a requirement or tailor it.
7. CFG-C1-074 / CFG-C2-023 / CFG-C4-003 [AIT]: unknown wire colours are cut to 6 characters; strip length, termination and contact/tool are typed or imported with no derivation or source; termination list is fixed to crimp/solder/unspecified.
8. CFG-C1-077 / CFG-C1-092 [SYS][ELEC]: device templates choose a Micro-D size from the number of interface types, and starter interface types encode construction/shielding choices (Ethernet with 4 signals on an 8-pin RJ45, CAN overall shield) marked only `unverified`, with no source and no pin-demand logic.

Next: [the audit](../transparency_audit.md), [appendix B](generation.md)
