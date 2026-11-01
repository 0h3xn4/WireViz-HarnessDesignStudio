# Transparency audit, appendix G: the GUI work screens

This page is appendix G of the [transparency audit](../transparency_audit.md): the row-level catalogue for the canvas, the Devices tab, the Inspector, the Why panel and the other screens an engineer works in. Each row names the file and line the reviewer opened. IDs read `GUI1-C<category>-<number>`; the categories and the tags `[SYS]`, `[ELEC]` and `[AIT]` are explained in section 1 of the audit. Paths beginning with `work/` are scratch projects the reviewer made while auditing; they are not in the repository. Nothing on this page was changed in the code: it is read-only.

## Contents

- [C1 - Hard-coded constants, defaults, rules (as the GUI layer carries or shows them)](#c1---hard-coded-constants-defaults-rules-as-the-gui-layer-carries-or-shows-them)
- [C2 - Hidden assumptions](#c2---hidden-assumptions)
- [C3 - Outputs shown without a derivation](#c3---outputs-shown-without-a-derivation)
- [C4 - Forced choices](#c4---forced-choices)
- [C5 - Inputs and outputs exchanged with files and other tools](#c5---inputs-and-outputs-exchanged-with-files-and-other-tools)
- [C6 - Customisation points that exist in these screens](#c6---customisation-points-that-exist-in-these-screens)
- [Per-screen matrix (units / source / role)](#per-screen-matrix-units--source--role)
- [Top findings](#top-findings)

**Scope.** Read fully: gui/controller.py (1-1747), why_panel.py (1-205), inspector.py (1-754), wire_editor.py (1-917), canvas_links.py (1-348), canvas_state.py (1-311), plan_table.py (1-119), lists_panel.py (1-609), interface_table.py (1-350), areas.py, harness_view.py (1-1471). Read in part: canvas.py (1-330, 880-960, 1126-1140, 1900-2160, 2326-2342, 3392-3402), canvas_badges.py (120-272), connector_editor.py (1-330), accessory_editor.py (1-130), devices_view.py (1-700, 828-845, 1170-1190), devices_pin_table.py (30-140, 396-470), devices_dialogs.py (1-140 plus greps), harness_edit_dialogs.py (1-140), link_dialog.py (1-120 plus greps), main_window.py (3131-3260, 3261-3410, 3457-3560, 3873-4040, 2611-2692), topbar.py (1-120 plus greps), workflow.py (1-80), preview.py (1-140), project_tree.py (1-130), roles.py, shell.py (355-453), tables.py/sheet.py/unit_table.py/rail.py/states.py/legend.py (greps only; mostly cosmetic). Core files opened to follow what the GUI shows: core/why.py, core/generate/explain.py, core/describe.py (1-300), core/edit.py (28-70, 186-330, 618-628), core/generate/lengths.py (1-140), core/generate/segmentation.py (60-165), core/configcheck.py (497-569), core/checks.py (190-204), core/io/layout.py (193-198), core/outputs/stamp.py (27-52), generation_status.py (23-48). Not read: main_window.py outside the ranges above (menus, tour, settings page), canvas.py 330-880 and 960-1900 (painting), panels.py beyond greps (PropertiesPanel), Next step page, dialogs.py.
Runtime observation: I generated the bundled "flatsat" example into my scratch folder (audit-transparency/gui1_tmp/p, outside the repo) and read the Why text of a wire (see GUI1-C3-001).

Persona tags: [SYS] systems engineer, [ELEC] electrical engineer (ampacity, derating, voltage drop, bundle, temperature, shield, EMC, ratings, pins), [AIT] assembly/integration/test (cut and strip lengths, contacts, crimp tools, terminations, labels, build sheets, tests, as-built).

## C1 - Hard-coded constants, defaults, rules (as the GUI layer carries or shows them)

Columns: id | file:line | value or rule | what it does / feeds | unit | visible? | editable? | R

| id | file:line | value or rule | does / feeds | unit | visible | editable | R |
|---|---|---|---|---|---|---|---|
| GUI1-C1-001 | core/edit.py:32-34,192-195 | `LANE_WIDTH=470.0`, `LANE_X0=10.0`, `UNIT_W=240.0`; lane = `int((x+UNIT_W/2-LANE_X0)//LANE_WIDTH)` clamped | A device's zone is the lane under its box centre. Feeds unit.zone, hence harness grouping (C1-002) [SYS][ELEC][AIT] | scene px | no (only the lane names) | none | R2 R3 |
| GUI1-C1-002 | core/edit.py:621-626; generate/segmentation.py:147-151 | `ops_move_unit`: dragging a box writes `unit.zone=zone_of_x(x)` in the same undo step | In mode per_zone_pair the zone pair is the harness bucket key and the label ("same pair of zones"). A cosmetic drag can regroup wires [SYS][ELEC][AIT] | - | toast "X is now in Y" (controller.py:899-901) | no; Zone field disabled (panels.py:445, strings.py:85) | R4 R7 R12 |
| GUI1-C1-003 | canvas.py:66,882-884; canvas.py:3398-3399 | `grid=10`, snap `round(x/GRID)*GRID`, `max(0.0, ...)` | Placement x,y are saved in the project and enter `model_hash` (io/layout.py:117-122,193-198), so a nudge changes the hash stamped on exports [SYS][AIT] | scene px | View > Snap | on/off (Alt bypass) | R9 |
| GUI1-C1-004 | canvas.py:2001,2013 | `LABEL_LIMIT = 30` links | With more than 30 links the V/A label shows only for selected, focused or hovered links [SYS][ELEC] | links | View > "labels" (hidden in Systems role, areas.py:58) | `show_all_labels` toggle | R2 |
| GUI1-C1-005 | canvas_state.py:33,265-268 | `MAX_COUNT=99` ("99+"); info-level and waived findings not counted on badges | Canvas badge counts understate when >99; info findings never reach the canvas [SYS][ELEC] | count | tooltip only | none | R12 |
| GUI1-C1-006 | core/describe.py:16-17,38-68 | `_num = f"{value:g}"` for V and A in canvas captions and link labels | Implicit rounding to 6 significant digits of entered voltage/current [ELEC] | V, A | canvas label | none | R5 |
| GUI1-C1-007 | harness_view.py:233-238; wire_editor.py:916-917 | `_length_text = f"{v:g}"`; gauge `str(v)` | Length (m) in wire table and Edit wire form rounded to 6 significant digits; the interface table instead shows exact `repr` (panels.py:153-161) [ELEC][AIT] | m | table header "Length (m)" | none | R5 |
| GUI1-C1-008 | harness_view.py:1195-1198 | `harness_sheets(snapshot, h, Stamp("preview","preview"), "A3")` | Drawing preview is always sheet A3 with a "preview" stamp; export writes A4 and A3 (core/outputs/build.py:108) [AIT] | mm (A3 420x297, core/outputs/canvas.py:17) | "preview" in title block | none | R4 R9 |
| GUI1-C1-009 | core/describe.py:124 | `VALUES_NEEDED = {"power": ("V","A"), "pyro": ("A",)}` | Only power and pyro links are asked for voltage/current ("V ?", "A ?", pending badge). Data, analog, RF links get none; no other attribute (shielding, EMC class) is ever requested [ELEC] | V, A | "V ?" on canvas; pending chip | none (code) | R3 R13 |
| GUI1-C1-010 | core/describe.py:71-110 | keyword list micro-d, mdm, d-sub, 38999, rj45, coax, sma, tnc matched in part description/number/ID | Decides connector family (drawing glyph, "family" text on card, canvas.py:309) from free text; first match wins; unknown = "generic" [ELEC][AIT] | - | card glyph | none | R3 |
| GUI1-C1-011 | core/describe.py:47-56 | gender = first `male`/`female` word in part description | Gender shown on cards and used by connector checks when the connector says "unspecified" [ELEC][AIT] | - | card, Devices tab | gender combo overrides (devices_view.py:1503-1511) | R7 |
| GUI1-C1-012 | core/describe.py:236-246,278-310 | `_NAME_WORDS`, `_SUBSYSTEM_WORDS` (wheel, battery, obc ...) pick the card picture | A picture implies a device kind the model does not have; cosmetic but looks like a classification [SYS] | - | card picture | none | R3 |
| GUI1-C1-013 | core/edit.py:50-52,43-44 | `guided_height = 70 + 14*max(0,links-2)`, `expert_height = 46 + 28*connectors` | Card height; no engineering meaning, but it is the only "size" on the canvas [SYS] | scene px | no | none | - |
| GUI1-C1-014 | canvas_links.py:44-48; canvas.py:1928-1929,261,264 | `OUT=36`, gaps `<40 -> 40`, slot `(h-44)/n`, right edge `+5` shift | Line routing offsets. Distances on the canvas are layout only, never cable lengths [SYS] | px | no | none | - |
| GUI1-C1-015 | copies.py:33 (via devices_view.py:405, devices_dialogs.py:142) | `MAX_DEVICES = 10` copies of one device incl. original | Spin box 1..10; IDs `ID`, `ID-R`, `ID-3` (controller.py:1044-1045) [SYS][AIT] | count | spin box limit only | none | R3 |
| GUI1-C1-016 | devices_dialogs.py:214 | `pins.setRange(1, 1000)` for a new connector part | Upper limit of pins per part [ELEC][AIT] | pins | spin box | none | R3 |
| GUI1-C1-017 | accessory_editor.py:125; strings.py:2374 | `quantity.setRange(1, 9999)` | Accessory quantity limits [AIT] | pcs | tooltip | none | R3 |
| GUI1-C1-018 | strings.py:2714 | Pin ID "letters, digits, _ - . (up to 16)" | Pin naming rule, enforced in core, stated only in a tooltip [ELEC][AIT] | chars | tooltip | none | R3 |
| GUI1-C1-019 | strings.py:2077-2087,2266-2275 | Gauge "a whole number", unit AWG only; length m; strip A/B mm | Fixed unit conventions in labels; no mm2, no feet, no conversion offered [ELEC][AIT] | AWG, m, mm | field labels | none | R5 |
| GUI1-C1-020 | wire_editor.py:585; strings.py:2086 | colour list `COLOURS` (core.wirecolours) "IEC 60757 names, or your own text" | Colour names and codes come from a built-in table, free text accepted without check [AIT] | - | combo | free text | R3 |
| GUI1-C1-021 | strings.py:2128-2134; 2704-2712; 2247; 2339-2345; link_dialog.py:61 | Fixed vocabularies: group kinds (twisted pair, shielded pair, quad, coax, overall shield), pin roles (power, return, ground, signal, shield, spare), termination (crimp, solder, not said), accessory kinds (sleeving, heat shrink, label, backshell, other) | Closed lists, no "other" for terminations (no ultrasonic, no splice, no screw) or group kinds [ELEC][AIT] | - | combos | none | R3 R13 |
| GUI1-C1-022 | devices_pin_table.py:48-50 | `EDITABLE = pin, signal, role, mode, contact_size, termination, function, contact_part` | Direction, class, interface, wire are derived and read-only [ELEC] | - | cell tooltips | fixed | R7 |
| GUI1-C1-023 | harness_view.py:1096,804 | `_is_spare`: no wire and no signal; spare pins hidden by default | Pin table starts without spare pins; count line says how many are hidden (harness_view.py:1081-1086) [ELEC][AIT] | pins | count label | "Show spare" toggle | R6 |
| GUI1-C1-024 | workflow.py:24,39-60; topbar.py:63-80 | Fixed 3-step flow `("generate","review","release")` | The "where am I" bar knows only Generate, Review (rule check), Release. No Import, Values, Export, Build-data step [SYS][ELEC][AIT] | - | top bar | none | R6 |
| GUI1-C1-025 | main_window.py:3250-3258; controller.py:238-239 | reviewer/author = `ui/user` setting, else Git name, else `getpass.getuser()`; date = `date.today()` | "who" and "when" of review/release are self-declared strings and the machine clock [SYS][ELEC][AIT] | - | change dialog field | field editable | R8 |
| GUI1-C1-026 | core/checks.py:196-204 | waiver justification 10..2000 chars, no control characters | Only override with a mandatory reason; applies to findings, not to values [SYS][ELEC] | chars | error text | fixed | R7 R12 |
| GUI1-C1-027 | why_panel.py:23 | `FIRST_LINES = 5` | Why shows 5 reasons, rest behind "Show all" (progressive disclosure, good) [all] | lines | button | none | R1 |
| GUI1-C1-028 | controller.py:59-60,274 | `DRC_DELAY_MS=1200`, `JOURNAL_DELAY_MS=1500`; findings sorted `(error,warning,info), id` | Rule check runs 1.2 s after the last edit; problems shown meanwhile are the last finished result (drc_current, 283-284) [all] | ms | "out of date" state | none | R12 |
| GUI1-C1-029 | lists_panel.py:97,100-125 | `BLANK_IS_PENDING` headers, "TBD*" prefix, "yes"/"approved" text matches | The list view classifies cells by matching display text and header names (fragile string contract with core/tables) [AIT] | - | chips | none | R5 R14 |
| GUI1-C1-030 | lists_panel.py:497-506 | export of "visible rows" (filtered and sorted) with stamp = tool version + model hash | "Export table" exports what the filter shows, not the full table; stamp has no timestamp, no user [AIT] | - | menu "Export table" | filter | R9 R10 |
| GUI1-C1-031 | accessory_editor.py:48-57,72 | accessory length `f"{a.length_mm:g}"`, "Position: nothing is computed from it" (strings.py:2369) | Position and length of sleeving/heat shrink are free text/number, not tied to wire lengths [AIT] | mm | form | free | R5 |
| GUI1-C1-032 | Cosmetic, grouped by file | canvas.py:58-96 `CanvasMetrics` (lod 0.45/0.5/0.8, zoom 0.02-3.0, minimap sizes, badge sizes); canvas_badges.py:22-25,178-180; harness_view.py:85-86; main_window.py:185-190; preview.py:49-57; rail.py:28-30; states.py:42-44 | pixel, zoom, timing and tint constants | px, ms | no | none | - |

## C2 - Hidden assumptions

| id | file:line | description | R |
|---|---|---|---|
| GUI1-C2-001 | edit.py:621-626, canvas.py:198-203 | Zone is not data entered but a side effect of where the box sits. Dropping a box 1 px over a lane boundary changes zone, thereby harness bundling and the "same pair of zones" text. Only an undoable toast tells. [SYS][ELEC][AIT] | R4 R7 |
| GUI1-C2-002 | controller.py:1311 | On every open `apply_ops(project, ops_autoplace(project))` silently adds Placement records outside the undo history; the project becomes different (and its model hash) before the user touched it. [SYS] | R8 R9 |
| GUI1-C2-003 | io/layout.py:117-122,193-198; stamp.py:27-28 | `model_hash` covers placements and zones, so layout moves change the hash stamped on every CSV/XLSX and top bar; whether the "outputs stale" chip fires on a pure move is unverified. [SYS][AIT] | R9 |
| GUI1-C2-004 | lengths.py:84-100 | A wire length is "its own length (hand-set, lock) else sum of routing segments"; `None` when a segment length is unknown or the segments form a loop. No slack, bend allowance, service loop, connector backshell offset or tolerance exists in the shown length. The tables never say which of the two cases applies. [ELEC][AIT] | R1 R4 |
| GUI1-C2-005 | wire_editor.py:61-64, strings.py:2276 | Strip lengths are applied to a wire "never lock": Generate keeps them, but nothing computes or suggests them from contact size/gauge; "Apply to all wires" overwrites per-wire values with one number. [AIT] | R7 R4 |
| GUI1-C2-006 | strings.py:2084-2087 | Gauge, type, colour or length edited in Edit wire (or Bulk, strings.py:2764) "lock" the wire against Generate. The lock is the override flag; no reason, no author, no date; the wire list only shows a "Locked" chip. [ELEC][AIT] | R7 R8 |
| GUI1-C2-007 | controller.py:1278; harness_view.py:1033 | Plan staleness is decided by comparing `input_hash` of the project plus plan ops with the record; the displayed hash is truncated: 8 chars in top bar (main_window.py:2567,2606) vs 12 in harness header (harness_view.py:1033). [all] | R9 |
| GUI1-C2-008 | harness_view.py:114-138 | State "Auto-filled" means "h.generated and not hand_set"; "pending" means gauge or length None. Gauge pending reason names only "values that wire sizing needs" (core/why.py:171-178), not the missing key unless the config check lists it. [ELEC] | R12 |
| GUI1-C2-009 | core/describe.py:130-139, canvas_state.py:270-285 | "Pending" on the canvas counts only missing V/A of power/pyro links; a design with zero entered currents shows pending chips, but a link whose current is entered as 0 or by mistake shows nothing. `parse_optional_float` accepts 0 and any positive number, no range (panels.py:164-176). [ELEC] | R5 R12 |
| GUI1-C2-010 | strings.py:483, interface_table.py:43,117,167-168 | Table column "Max current (A)" stores `max_current_a` and is the number the wire sizing uses (inferred from Why text, see C3-001); the table never says it is the sizing input, nor that it is steady-state or peak, nor at what temperature. [ELEC] | R1 R2 |
| GUI1-C2-011 | canvas_state.py:19-20 | `auto` = connector "the tool chose" = first free connector carrying the type (describe.py:341-343): a fixed first-fit rule behind a small badge. [SYS][AIT] | R4 R12 |
| GUI1-C2-012 | devices_view.py:1186-1188 | Pin "allocation" text is only two states: "fixed" if any pin is fixed, else "auto" (DV_ALLOC_*). The allocation rule (power and return grouped, pin order) is not described there; only per-pin reasons in Why. [ELEC][AIT] | R1 R4 |
| GUI1-C2-013 | devices_view.py:6-13 (doc) | Direction and class of a pin are derived from the interface type of its signal, "nothing is guessed"; empty with tooltip when unknown. Good, but the rule (name match of signal to type signal) is not shown. [ELEC] | R1 |
| GUI1-C2-014 | inspector.py:262-280 | Config file view lists "engineering values" with unit and a source string (`ev.source`: requirement ID/profile or "set in the project") only as a tooltip; value columns show `display unit`. Placeholder status is shown per file, not per value. [ELEC] | R2 R5 |
| GUI1-C2-015 | lists_panel.py:170-184 | `tables.clear_cache()` and rebuild from core builders on each refresh: the Lists tab is a second computation of what export writes, trusted to be equal; no check that the visible table equals the last exported file (OutputsFiles shows files separately). [AIT] | R9 R14 |
| GUI1-C2-016 | main_window.py:4028-4029 | Export includes drawings only if drawings were exported there before (`drawings_exported(folder)`): an implicit memory from files on disk. [AIT] | R4 R9 |
| GUI1-C2-017 | roles.py:10-18; main_window.py:3457-3475 | The role is a per-user QSettings value, default Electrical/AIT, never stored in the project and not stamped on exports. The same project shows different menus and areas for the same person at different times. [SYS][ELEC][AIT] | R6 R9 |
| GUI1-C2-018 | plan_table.py:7-8 | "The core cannot scope a generation to one harness": Generate always regenerates all unlocked harnesses; locked pins kept are counted, not listed per pin. [SYS][ELEC] | R4 R6 |

## C3 - Outputs shown without a derivation

| id | file:line | description | R |
|---|---|---|---|
| GUI1-C3-001 | core/why.py:57-78,150-154; generate/explain.py:15-26; observed on flatsat W001-001 | Why for a wire prints recorded sentences, for example "wire-sizing: ampacity: AWG 24 carries 1.08 A derated (factor 0.54) for 0.8 A" and "voltage drop: AWG 24 gives 0.458359 V over 2 conductor(s), limit 1 V". It does not show equation, resistivity, temperature, bundle count, length used (3.45 m), which config key supplied the 1 V limit, or the table row. Raw 6-digit numbers. [ELEC] | R1 R5 R12 |
| GUI1-C3-002 | why_panel.py:7-9,98-107 | "The panel adds nothing of its own": it is a viewer of strings recorded at last Generate (project.generation.provenance), so it can be older than the data on screen when the design is stale; no "inputs" or "intermediates" view. [ELEC][AIT] | R1 R6 |
| GUI1-C3-003 | why_panel.py:154-163 | Placeholder chip lists config files used ("Generated on placeholder values from: ...") but not which values or which results depend on them. [ELEC] | R2 R12 |
| GUI1-C3-004 | harness_view.py:233-250,279-280 | Wire table "Length (m)" and "Gauge (AWG)": computed numbers with no per-cell Explain; pending tooltips say "a routing segment on its path has no length" without naming the segment (strings.py:1277-1278). [ELEC][AIT] | R1 R12 |
| GUI1-C3-005 | harness_view.py:178-203 | Pin table gauge/colour/shield per pin copied from the wire; no contact, termination or strip length column on the harness side (they live on the Devices pin table and Edit wire form). Build data is spread over four screens. [AIT] | R6 |
| GUI1-C3-006 | lists_panel.py:51-59,170-184 | Mass, margin, BOM, tests, labels: read-only tables built in core; no click-through to the mass model, margin factor or test limits; the only explanation is the stale banner. Derivation not in the GUI. [ELEC][AIT] | R1 R6 |
| GUI1-C3-007 | canvas.py:894-895,923-925; describe.py:319-360 | "Why?" on the canvas explains only which connector the tool picked and the generation sentences of wires; nothing for the zone placed, the glyph, or label values. [SYS] | R1 |
| GUI1-C3-008 | canvas_links.py:340-345; core/links.py (unread) | Connection label "CAN, 2 wires" is derived from pin signals (`derived_interfaces`); rule not shown, no Why for a link (core/why.KINDS excludes "link", why.py:27). [SYS][ELEC] | R1 R12 |
| GUI1-C3-009 | inspector.py:203-218 | Part facts table shows approval chip and pins; no ratings (current, voltage, temperature, mating cycles) because the part model offers none in this view. [ELEC] | R2 |
| GUI1-C3-010 | devices_view.py:106-112 | Role column shows "(auto)" for the role taken from the signal name, but the rule (RTN/GND names) is only visible as tooltip text for two names (describe.py:20-31). [ELEC] | R1 |
| GUI1-C3-011 | topbar.py/main_window.py:2567,2606 | Status chip "Up to date" is computed from model hashes only (controller.py:1241-1246); no listing of which input changed since the last generate or export. [SYS][AIT] | R9 R14 |
| GUI1-C3-012 | harness_view.py:1237-1268 | Verify chip "OK" with rule counts; the independent verification summary appears in a tooltip (1286-1290); no drill into which checks ran. [ELEC] | R12 |
| GUI1-C3-013 | harness_view.py:1285-1290 | Computation times (`ms`) are shown in the verify tooltip, while the check content is not. [all] | R1 |
| GUI1-C3-014 | canvas_state.py:76-89 | Badge tooltip sentence: counts of problems/warnings/values; it does not name the rule or the object value. Clicking opens Problems filtered to the object (controller.py:1639). [all] | R12 |
| GUI1-C3-015 | lists_panel.py:497-506 | Labels list: label text is built in core; the Labels form (wire_editor.py:217-318) edits only the free-text override and does not preview the resulting label. [AIT] | R1 R6 |
| GUI1-C3-016 | harness_view.py:1033-1035 | Header "Generated from <12 chars of hash>": no way to see what that hash covered (list of inputs) from the GUI. [SYS][ELEC] | R9 R14 |

## C4 - Forced choices

| id | file:line | description | R |
|---|---|---|---|
| GUI1-C4-001 | canvas.py:198-203; panels.py:445; unit_table.py:41 | Zone cannot be set by field or table (Zone column not in `EDITABLE={1,4,7}`); only by dragging or by adding a zone (controller.py:1031). [SYS][ELEC] | R4 R7 |
| GUI1-C4-002 | plan_table.py:7-8; main_window.py:3131-3160 | Generate is all-harnesses only; preview dialog then apply; no per-harness regenerate. [SYS][ELEC][AIT] | R4 R6 |
| GUI1-C4-003 | harness_view.py:1195-1198 | Preview sheet fixed A3 and stamp "preview"; cannot compare A4 layout, cannot see final stamp before export. [AIT] | R4 |
| GUI1-C4-004 | strings.py:2128-2134,2247,2704-2712,2339-2345 | Closed lists for group kinds, terminations, pin roles, accessory kinds (see C1-021). [ELEC][AIT] | R3 R13 |
| GUI1-C4-005 | strings.py:2084 | Gauge is a whole AWG number only; no mm2, no half sizes, no "match the library wire". [ELEC] | R5 |
| GUI1-C4-006 | wire_editor.py:699-713 | Editing gauge, type, colour, length always sets the lock (`locked`) on that wire; there is no way to enter a value as a "preferred" without freezing it, except Strip A/B and note/label. [ELEC][AIT] | R7 |
| GUI1-C4-007 | harness_view.py:1102-1148 | Release only from draft/in review, revise only from released; Delete only draft. The reason is shown as tooltip; no override even with justification. [SYS][AIT] | R7 |
| GUI1-C4-008 | main_window.py:3261-3340 | Release dialog lets you accept placeholders and unapproved parts, each with a typed reason (accept_placeholders, accept_unapproved_parts), but not other blockers. This is the one place where a justified override exists. [SYS][ELEC] | R7 R8 |
| GUI1-C4-009 | connector_editor.py:1-17 (doc), strings.py:2323-2326 | A generated harness takes no new connectors; its pins and contacts "follow the device"; edits there make the connector "yours" (Connector.locked) and are kept. Contacts are set on the device pin, not on the cable side. [ELEC][AIT] | R4 R7 |
| GUI1-C4-010 | inspector.py:629-650 | The only part field editable in the Inspector is the crimp tool (free text); part category, manufacturer, current rating cannot be edited in the GUI (library files). [AIT] | R7 R13 |
| GUI1-C4-011 | canvas.py:107-109,219-231 | Connector side on a box (left/right) is forced by lane rule and link direction; cannot be set. Cosmetic, but the "right edge" implies nothing electrical. [SYS] | - |
| GUI1-C4-012 | areas.py:41-64 | Systems role hides Home, Drawings (Harness tab with Edit wire, Connectors, Accessories), Outputs (Lists) from the rail and about 45 menu entries, including engineering values (act-values), import of lengths/values, revisions, and wire colours. Still reachable from Ctrl+K. [SYS] | R6 |
| GUI1-C4-013 | main_window.py:3463-3475 | A new user without a hook is asked once for a role; closing the question gives Electrical/AIT silently. [all] | R6 |
| GUI1-C4-014 | link_dialog.py:61 | Pin roles in Link connectors are a fixed seven-item list with the propose-pairs rule from signal names. [ELEC] | R3 |
| GUI1-C4-015 | interface_table.py:46,142-144 | Redundancy chain restricted to nominal/redundant/none. [SYS] | R3 |
| GUI1-C4-016 | lists_panel.py:190-222 | Tables in Lists are read-only: no way to correct a derived value there; edits must go back to the Harness tab, the Devices tab or config. [AIT] | R6 R7 |

## C5 - Inputs and outputs exchanged with files and other tools

| id | file:line | description | R |
|---|---|---|---|
| GUI1-C5-001 | controller.py:1350-1372,1341,1424 | Open/save project folder `project.json` + files; `ProjectLock` lock file is written into the project folder on open (invisible to the user except an error when locked). [all] | R14 |
| GUI1-C5-002 | controller.py:1374-1404,1489-1571 | Recovery journal is written next to the project 1.5 s after every edit, with `base_fingerprint`; shown as "autosave" in status; a restore can contain older state than Git files (journal_base_changed). [all] | R8 R14 |
| GUI1-C5-003 | controller.py:1452-1462,1411-1415 | Disk change detection: `disk_fingerprint` compared on save (expected_fingerprint) and on request; "keep mine" memorises a fingerprint. Good source change detection for the project, but not for imported files (no link to the imported CSV). [all] | R14 |
| GUI1-C5-004 | devices_view.py:828-845,1470; main_window.py:1470 | "Pinout as exported": preview rows equal `system/box_pinouts.csv` rows; `export_to` writes CSV/XLSX with `stamp_of` = tool version + model hash. [ELEC][AIT] | R9 R10 |
| GUI1-C5-005 | lists_panel.py:497-514 | Any list to CSV or XLSX (visible rows, same stamp); no JSON. [AIT] | R10 |
| GUI1-C5-006 | tables.py:348-383; sheet.py:79-199; devices_pin_table.py:396-470 | Clipboard TSV: copy with headers, paste from Excel into interface, unit and pin tables (header names matched case-insensitive: `HEADER_WORDS`, devices_pin_table.py:415-421); silent skipping of unknown columns. [ELEC][AIT] | R14 |
| GUI1-C5-007 | canvas_badges.py:130-170 | FLIGHT/GROUND zone tags are in QSettings (`canvas/zone_tags`), not in the project, not exported, per user. Looks like a design fact. [SYS] | R2 R3 |
| GUI1-C5-008 | roles.py, main_window.py:3457-3475 | `ui/role`, `ui/user`, splitters, layout hashes in QSettings: user-local, outside project, not in exports. [all] | R9 |
| GUI1-C5-009 | main_window.py:3873-3910, 4022-4036 | Export dialog writes `outputs/` (DEFAULT_FOLDER, controller.py:39,1239); the "outputs state" compares model hashes (controller.py:1241-1246) and lists files in OutputsFiles. [all] | R9 R14 |
| GUI1-C5-010 | main_window.py:3913-3935 | Import wizard kinds: interfaces, parts, lengths, engineering values, KiCad netlist (project_tree.py:92-94). Imported files are not linked afterwards: no "source file" field, no re-import diff. [SYS][ELEC][AIT] | R14 |
| GUI1-C5-011 | main_window.py:2687 | Example projects copied to `Documents/Harness Design Studio`; implicit path. [all] | - |
| GUI1-C5-012 | main_window.py:1483-1550 (flow names) | Device library folder: save device to library, add from library (device_library); library folder chosen once, kept in settings. Not read in detail. [SYS][ELEC] | R13 R14 |
| GUI1-C5-013 | preview.py:1-8 | Drawing preview paints the same `Sheet` description that becomes SVG/PDF: what you see is what is exported (only the stamp text differs). Good. [AIT] | R9 |
| GUI1-C5-014 | drc_process.py (via controller.py:63-88) | The rule check runs in a separate helper process on a copy of the project; failure shows "drc-failed" finding (controller.py:286-295). [all] | R11 |

## C6 - Customisation points that exist in these screens

| id | file:line | description | R |
|---|---|---|---|
| GUI1-C6-001 | wire_editor.py:321-713 | Edit wire: gauge, type, colour, length, strip A/B, label, note on one or many wires, Apply as one undo step, "Reset to generated" (wire_editor.py:879-891). State text "Generated"/"Your values". [ELEC][AIT] | R7 |
| GUI1-C6-002 | harness_edit_dialogs.py:96-140 | Bulk wire edit by all, selected or one signal; "Only wires that have no value yet" option (strings.py:2772). [ELEC][AIT] | R7 |
| GUI1-C6-003 | devices_pin_table.py:48-110, devices_view.py:168-190 | Edit in place: pin, signal, role, mode (free/fixed/locked), contact size, termination, function, cable contact; locked by release with reason in tooltip (PinModel.why_not_editable). [ELEC][AIT] | R7 |
| GUI1-C6-004 | connector_editor.py (whole) | Cable connector part, gender, keying, name, pin signal/role/function/termination/contact size/contact part, add/rename/delete pins (hand-made harnesses). [ELEC][AIT] | R7 |
| GUI1-C6-005 | accessory_editor.py:78-130 | Accessories table and form (sleeving, heat shrink, label, backshell, other) with part, position text, length mm, quantity, note shown in build sheets. [AIT] | R13 |
| GUI1-C6-006 | inspector.py:629-650 | Crimp tool per contact part (free text, "shown in the build sheets"). [AIT] | R7 |
| GUI1-C6-007 | wire_editor.py:217-318 | Labels form: harness label and cable connector label text for `labels.csv`. [AIT] | R7 |
| GUI1-C6-008 | interface_table.py:42-46; unit_table.py:41 | Spreadsheet edit of name, chain, max current, requirement ID, with paste from Excel. [SYS][ELEC] | R14 |
| GUI1-C6-009 | controller.py:959-969; dialogs.py WaiverDialog | Waive a finding with justification (>=10 chars); waived findings listed separately (open_findings, 362-368). [SYS][ELEC] | R7 R12 |
| GUI1-C6-010 | main_window.py:3261-3410 | Review/release/new revision with name, checker, comment, placeholder and unapproved part acceptance reasons; history and changes dialogs (HistoryDialog, DiffDialog). This is the only change history the GUI offers; edits between releases are only undo steps. [SYS][ELEC][AIT] | R8 |
| GUI1-C6-011 | canvas.py:2021-2072; 2002-2003 | Filters by signal class, connector, bundle; View toggles for labels, connection ends, snap, legend. [SYS] | R2 |
| GUI1-C6-012 | devices_view.py:1178-1184,1543-1548 | "Suggest carries" proposes interface types a connector can carry; user accepts (explicit suggestion, not auto-apply). [ELEC] | R7 |
| GUI1-C6-013 | harness_view.py:94-99, tables.py:97 | Column headers carry units (AWG, m) via `Column.unit`; sort, filter, column widths saved per table. [all] | R5 |
| GUI1-C6-014 | inspector.py:75-109,195-201 | Banners say why a field is locked and offer "Start new revision" (reason via field_lock_reason). [all] | R7 R12 |

## Per-screen matrix (units / source / role)

Role: Systems engineer (SYS role) opens on the Next step page, with side panels closed, rail without Home/Drawings/Outputs, about 45 menu entries removed, problem notices and counts off (areas.py:39-64; main_window.py:3476-3500). Electrical / AIT role opens on the diagram (Model area, areas.py:38), shows everything and is the default for existing users and for an unanswered first-start question.

| Screen | Seen by | Less shown to | Units shown | Can see where a value came from | Overrides and flag |
|---|---|---|---|---|---|
| Diagram canvas (canvas.py, canvas_links.py) | both | SYS gets no zoom, align, snap, labels menus | V and A in label ("28 V · 5 A", describe.py:38-68), no lengths | tooltip "Why?" only for tool-chosen connectors | box position = zone (C1-002); no flag |
| Inspector (inspector.py) | both, but panels closed in SYS | SYS | config values with unit and source tooltip | source of config value (tooltip) | lock banner; crimp tool only |
| Why panel (why_panel.py) | both (SYS needs the panels button) | SYS | numbers inside recorded sentences, no unit conversion | recorded sentence only; no inputs | none; read-only |
| Interface and Unit tables | both (Go menu hidden in SYS) | SYS | "Max current (A)" in header; no V column | none | in-place edit, no flag |
| Devices tab (devices_view.py, devices_pin_table.py) | both (Model area) | - | contact size has no unit or standard; no ratings | direction/class tooltip; "Pinout as exported" preview | pin cell edit, mode fixed/locked/free, lock tooltip |
| Harness tab: wire and pin tables (harness_view.py) | ELEC/AIT rail; SYS only via Go | SYS (Drawings area hidden) | Gauge (AWG), Length (m); no strip, no mass | Why tab beside it (first tab) | Locked chip, state chip |
| Edit wire (wire_editor.py) | ELEC/AIT; SYS hidden | SYS | AWG, m, mm in labels | none beside the field | Apply locks; Reset button |
| Connectors tab (connector_editor.py) | ELEC/AIT | SYS | contact size free text, no unit | note "follows the device" | edit marks connector as locked |
| Accessories tab | ELEC/AIT | SYS | mm, pcs | none | form |
| Labels form | ELEC/AIT | SYS | text | none | text only |
| Lists (lists_panel.py) | ELEC/AIT (Outputs hidden in SYS) | SYS | units in builder headers (g, m) | none; rows come from core builders | read-only |
| Top bar and workflow (topbar.py, workflow.py) | both | SYS gets no counts | - | tooltips of the three steps | - |

Build data entry (strip A/B, contacts, crimp tool, accessories, labels) is spread over the Edit wire form, the Connectors tab, the Devices pin table, the Inspector (crimp tool), the Accessories tab and the Labels form: no single "build data" screen shows which of these are filled and which are pending for the build sheet.

## Top findings

1. GUI1-C1-002 / C2-001 - dragging a box on the canvas rewrites `unit.zone`, which decides harness grouping (per-zone-pair), with only a toast; the Zone field is read-only. Biggest hidden engineering input in the GUI layer. [SYS][ELEC][AIT]
2. GUI1-C3-001 - Why shows "ampacity: AWG 24 carries 1.08 A derated (factor 0.54) for 0.8 A" and "voltage drop ... 0.458359 V, limit 1 V" but no equation, temperature, bundle factor, resistivity, length used or config key. [ELEC]
3. GUI1-C2-006 / C4-006 - Editing gauge, type, colour or length locks the wire against Generate without reason, author or date; the only visible flag is a "Locked" chip. [ELEC][AIT]
4. GUI1-C2-004 / C3-004 - Shown wire length is "own length else sum of segments" with no slack, bend, service loop or tolerance, and the table does not say which case applies; pending tooltip does not name the missing segment. [ELEC][AIT]
5. GUI1-C1-009 / C2-010 - Only power (V and A) and pyro (A) links ever ask for electrical inputs; "Max current (A)" is the sizing input but is not labelled as such, and no data/RF link can carry EMC class, shielding or rating. [ELEC]
6. GUI1-C2-005 / C1-021 / C3-005 - Build data (strip A/B, contact size, termination, crimp tool, accessories, labels) is split over six places, units are fixed (mm, AWG), contact size is free text and terminations are a closed list of crimp/solder/not said. [AIT]
7. GUI1-C1-025 / C6-010 - Change history is only at review/release level; author is a typed name or OS login, date is the system clock; no who/when/old/new/why for individual value edits (only undo in session). [SYS][ELEC][AIT]
8. GUI1-C1-003 / C2-003 / C1-030 - Layout moves change the model hash stamped on every export, the stamp has no timestamp or user, and "Export table" exports only the filtered, sorted rows. [AIT][SYS]

Next: [the audit](../transparency_audit.md), [appendix F](editing-and-change-control.md), [appendix H](gui-dialogs-and-workflow.md)
