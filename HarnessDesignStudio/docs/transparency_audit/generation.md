# Transparency audit, appendix B: generation

This page is appendix B of the [transparency audit](../transparency_audit.md): the row-level catalogue for how wires are sized, measured, grouped and placed on pins, and what can be overridden. Each row names the file and line the reviewer opened. IDs read `GEN-C<category>-<number>`; the categories and the tags `[SYS]`, `[ELEC]` and `[AIT]` are explained in section 1 of the audit. Paths beginning with `work/` are scratch projects the reviewer made while auditing; they are not in the repository. Nothing on this page was changed in the code: it is read-only.

## Contents

- [C1. Hard-coded constants, defaults, margins, thresholds, rules](#c1-hard-coded-constants-defaults-margins-thresholds-rules)
- [C2. Hidden assumptions](#c2-hidden-assumptions)
- [C3. Outputs shown without derivation](#c3-outputs-shown-without-derivation)
- [C4. Forced choices (cannot be changed)](#c4-forced-choices-cannot-be-changed)
- [C5. Inputs and outputs exchanged with other tools or files](#c5-inputs-and-outputs-exchanged-with-other-tools-or-files)
- [C6. Customisation points that exist](#c6-customisation-points-that-exist)
- [Override and regeneration summary](#override-and-regeneration-summary)
- [Top findings](#top-findings)

**Scope.** Read in full: `core/generate/engine.py` (1-1095), `explain.py` (1-50), `lengths.py` (1-202), `mass.py` (1-47), `naming.py` (1-99), `pins.py` (1-225), `segmentation.py` (1-184), `sizing.py` (1-172), `wiring.py` (1-50); `core/wires.py` (1-780), `core/routing.py` (1-327), `core/pairing.py` (1-164), `core/manual_harness.py` (1-279). Context read (partial): `core/units.py` 1-21, `core/generation_status.py` 1-80, `core/standard_profiles.py` 1-110, `core/configcheck.py` 120-160, `core/model/physical.py` (Wire, ShieldGroup, Segment), `core/model/library.py` 15-50, blank and demo `config/*.json`. No code was run; behaviour is read from source.

Persona tags: [SYS] systems engineer, [ELEC] electrical engineer (ampacity, derating, voltage drop, bundle, shield, connector ratings, pin allocation), [AIT] assembly/integration/test (cut and strip lengths, contacts/tools, terminations, labels, build sheets, test tables, as-built). Config key names are those of `config/generation.json` ("gen.") and `config/derating.json` ("der.").

Overall picture: the generator is deterministic and mostly config-driven ("the tool never guesses", sizing.py:3-4), unset values stay `null` and leave the gauge undecided. But the decision logic itself (gauge search, multiplication of factors, 2-conductor voltage drop, length formula, first-fit pin placement, shield grouping) is fixed in code, and the only trace is a handful of free-text lines recorded at generation time.

---

## C1. Hard-coded constants, defaults, margins, thresholds, rules

| id | file:line | value or rule | what it does / feeds | unit | visible to user? | editable? | persona | R |
|---|---|---|---|---|---|---|---|---|
| GEN-C1-001 | sizing.py:21,29 | `REL_TOL = 1e-9`; `value - limit > REL_TOL*max(abs(value),abs(limit))` | Tolerance for "exceeds"; a current or drop within 1e-9 relative of its limit passes. Shared by sizing and DRC | relative | no (docstring only) | none | [ELEC] | R2 R3 |
| GEN-C1-002 | sizing.py:32-34 | `base * (bundle * temperature)` | Derated ampacity = table value x bundle K x temperature factor. Purely multiplicative; no insulation, altitude, vacuum, partial-load (L) term | A | partly: note shows the product "factor" only (sizing.py:145) | none (formula); factors via der.* | [ELEC] | R1 R4 |
| GEN-C1-003 | sizing.py:57 | `if not 0 <= gauge <= 40: return None` | Any ampacity-table key outside AWG 0..40 voids the whole table, so gauge becomes "pending" with no reason naming the bad key | AWG | no | none | [ELEC] | R12 |
| GEN-C1-004 | sizing.py:62-74 | `bundle_k`: first listed count >= n; None if n is above the largest listed | K for the bundle. Counts above the table (ECSS profile ends at 300) leave gauge pending; text says "next listed count", never interpolates | wires | note "bundle factor K ... (Table 6-41)" | der.bundle_factor_by_count | [ELEC] | R4 R12 |
| GEN-C1-005 | sizing.py:126 | `"bundle factor K ... (Table 6-41)"` | Source label is hard-coded text; printed even when the user's table is not ECSS. Wrong/misleading provenance if table differs | n/a | yes (explain line) | none | [ELEC] | R1 R9 |
| GEN-C1-006 | sizing.py:94-95,121-125 | `by_count` table, when present and `bundle_wires` known, REPLACES `bundle_derating` silently | Two sources for one factor; the single factor is ignored whenever the table exists | factor | no (not stated in the note unless table gave K) | der.* (both keys) | [ELEC] | R2 R4 |
| GEN-C1-007 | sizing.py:136-143 | `candidates = sorted(table, reverse=True)`; first gauge passing ampacity wins | Selection rule: smallest conductor (highest AWG) whose derated ampacity >= current. No minimum gauge, no mechanical/handling minimum, no contact crimp range check | AWG | note shows chosen gauge only; rejected ones not listed | none | [ELEC][AIT] | R4 R7 |
| GEN-C1-008 | sizing.py:37-40 | `I * rho * L / (area_mm2*1e-6) * conductors` | Voltage drop (DC, resistive only). No temperature coefficient of rho, no contact/connector resistance, no stranding lay factor | V | note shows result V, limit V, conductor count; not rho, L, area | none (formula) | [ELEC] | R1 R4 |
| GEN-C1-009 | units.py:15-21 | `d = 0.127 mm * 92**((36-n)/39)`; `area = pi/4*d^2` | Conductor area for the voltage-drop calc: nominal solid circular area of the AWG, not the stranded cable's actual area/resistance from the wire spec | mm2 | AWG shown as "AWG n (x.xxx mm2)" in UI strings | none | [ELEC] | R4 R5 |
| GEN-C1-010 | sizing.py:156-163 | `for cand in sorted(a for a in table if a <= awg)` | Voltage-drop pass only goes UP in size (lower AWG number) from the ampacity result, using the first that passes; error if none. Limit is absolute volts, not a % of supply | AWG, V | partly (note on pass; error text on fail) | der.max_voltage_drop_v | [ELEC] | R4 R12 |
| GEN-C1-011 | engine.py:954 | `conductors = 2 if category in ("power","ground") else 1` | Drop doubled for power and ground categories (assumes return of equal length and gauge, both wires sized with the same 2x). Other categories get 1x | count | note says "over N conductor(s)" only | none | [ELEC] | R1 R4 R7 |
| GEN-C1-012 | engine.py:667 | `bundle_wires = sum(len(links_of(...)[0]) for i in ifaces)` | Bundle size for K = number of generated wires of the whole harness, ignores branch/segment split, manual wires, and which wires actually carry current (fully loaded assumed) | wires | note "for N wires" only when table used | none | [ELEC] | R1 R4 |
| GEN-C1-013 | engine.py:691-692 | `length = path_length(...)`; `length += 2 * loop` | Generated wire length = sum of segment lengths + 2 x service loop (one per end). No slack, bend radius, tolerance, twist take-up, backshell length | m | no (only a note when loop is unset, engine.py:663) | gen.service_loop_m | [ELEC][AIT] | R1 R2 R5 |
| GEN-C1-014 | engine.py:661-666 | `loop` None -> lengths "exclude service loops" | Unset loop = 0, announced only in provenance for the harness | m | explain (harness) only | gen.service_loop_m | [AIT] | R2 R12 |
| GEN-C1-015 | engine.py:431-434 | `gap = int(_num(gen.get("power_signal_gap_pins")) or 0)` | Unset -> 0 pins between the power block and the first signal; provenance rule line "placeholder (0 used)" | pins | provenance "rules" key | gen.power_signal_gap_pins | [ELEC] | R2 R12 |
| GEN-C1-016 | engine.py:435 | `ret_gap = int(_num(gen.get("power_return_gap_pins")) or 0)` | Unset -> 0 unassigned pins between power and return. Unlike the signal gap, NO placeholder note is recorded here | pins | no (only configcheck.py:66, outside GEN) | gen.power_return_gap_pins | [ELEC] | R2 R12 |
| GEN-C1-017 | engine.py:170,172 | `_whole(..., 0)`; `_whole(default_gauge_awg, 0, 40)` | Range validation of two config keys (invalid -> error, key dropped) | pins, AWG | error finding | n/a | [ELEC] | R12 |
| GEN-C1-018 | engine.py:972-984 | no current -> interface type `default_gauge_awg`, else `gen.default_gauge_awg` | Gauge fill when no `max_current_a`. Only when current is None; a provisional or pending sizing never falls back | AWG | explain line "default gauge AWG n from the configuration" | InterfaceType.default_gauge_awg, gen.default_gauge_awg | [ELEC][AIT] | R2 R7 |
| GEN-C1-019 | engine.py:985-990 | `wire_colour_by_signal`; key = full label, else each half of "TX+/RX+" | Wire colour = config lookup by signal name; none if not listed. Set only on newly built, unlocked wires | text | no explain line for colour | gen.wire_colour_by_signal | [AIT] | R2 R3 |
| GEN-C1-020 | engine.py:933-948 | `wire_part_by_construction[construction]` must be a wire part, else None + warning | Selects the wire part (type) per construction (single, coax, twisted_pair, quad ...); drives mass, BOM, `conductors` | part id | warning only if missing; no note when set | gen.wire_part_by_construction | [ELEC][AIT] | R3 R4 |
| GEN-C1-021 | engine.py:995-1017 | `current > rating * factor` with `rating = part.ratings[contact_rating_key]` (default key "contact_current_a") | Contact overload ERROR. Uses interface max current vs the rating of the box connector part; ignores wire gauge, contact size, number of contacts. Skipped silently (provenance note) if rating or factor unset; not run for locked wires | A | error text lacks rating, factor, limit values | der.contact_current_factor, der.contact_rating_key, Part.ratings | [ELEC][AIT] | R12 R1 |
| GEN-C1-022 | engine.py:1029-1036 | valid ends `{"backshell_360","pigtail","floating"}`; unset/invalid -> `"floating"` | Shield termination for generated groups. Unset gives floating (a provenance note says "placeholder") | enum | explain (harness) | gen.shield_end_a/b | [ELEC][AIT] | R2 R12 |
| GEN-C1-023 | engine.py:1050-1051; physical.py:19 | `COAX_SHIELD_END = "backshell_360"` | Coax outer conductor forced to 360 deg backshell both ends regardless of grounding concept | enum | no | none | [ELEC][AIT] | R3 R4 |
| GEN-C1-024 | engine.py:1056-1083 | construction->group rule: single none; coax one group per wire; quad one group of all wires; else group by signal `pair` (power/ground category: pair "power"); kind `shielded_pair` iff `shielding=="per_pair"` else `twisted_pair`; `overall` adds one more group of all wires | Decides which wires are twisted/shielded/coax. Power interface wires are always one "twisted pair" group even if >2 signals; a wire can be in a pair group AND the overall group | kind | no provenance line per group | via InterfaceType (construction, shielding, signal.pair) | [ELEC][AIT] | R1 R4 R7 |
| GEN-C1-025 | wiring.py:29-50; engine.py:668-677 | out[k] pairs with in[k] by position; extras to same-named; passive/bidir same name; link drives from "X" | Which signal connects to which (TX+/RX+) is by list order of the type's signals; direction label "X drives" | n/a | provenance wiring line | via InterfaceType signal order | [ELEC][AIT] | R1 R7 |
| GEN-C1-026 | segmentation.py:86-87,32 | `mode = ... get("mode","per_connector_pair")`; unknown -> per_connector_pair + note | Default harness granularity (D-10). Only 3 modes | enum | explain (harness) and config | segmentation.mode | [SYS] | R4 R13 |
| GEN-C1-027 | segmentation.py:65,147 | pyro isolated when `forbid_pyro_with_other in (None, True)`; chains kept apart unless `forbid_nominal_with_redundant is False` | Missing key = rule ON. Segregation defaults are "on if absent" | bool | no | segregation.* | [SYS][ELEC] | R2 R3 |
| GEN-C1-028 | segmentation.py:46-58 | greedy colouring of `category_pairs_to_separate`, class names "main"/"cat-A+B" | Which categories can share a harness; greedy, sorted-name order, not optimal | n/a | harness label suffix "(cat-...)" | segregation.category_pairs_to_separate | [SYS][ELEC] | R1 R4 |
| GEN-C1-029 | segmentation.py:152-155 | key `cp|chain|ca|cb` has no class; classes only trigger a note | In per_connector_pair (the default) segregation classes (pyro, power vs signal) are NOT applied; mixed classes only warn | n/a | warning "mixes interface classes" | none | [SYS][ELEC] | R12 |
| GEN-C1-030 | segmentation.py:148 | `chain = i.redundancy` ("nominal"/"redundant"/"none") | "none" and "nominal" are different keys, so two interfaces on same connectors split into separate harnesses | enum | label "(redundant)" only | segregation.forbid_nominal_with_redundant | [SYS] | R1 |
| GEN-C1-031 | segmentation.py:109-119 | `len(endpoints) > 2` skipped "not generated yet"; != 2 skipped | Hard limit: exactly two ends per interface | count | warning | none | [SYS] | R13 |
| GEN-C1-032 | segmentation.py:70-80 | X/Y end = alphabetically lower connector ID (or unit ID, or zone order) | Which end is "X"; drives cable connector numbering (P1 for X), "drives" wording, ID order | n/a | no | none | [SYS][AIT] | R1 |
| GEN-C1-033 | pins.py:13,124-126 | `CATEGORY_RANK = {"power":0,"ground":1}`, others 2; sort by (rank, interface id) | Placement order on a connector: power first, then ground, then everything else alphabetical by interface ID | n/a | docstring only | none | [ELEC][AIT] | R3 R4 |
| GEN-C1-034 | pins.py:87-101 | `groups_of`: power/ground = one block of all signals; `pair` signals adjacent; others single | Which signals must sit together | n/a | provenance "pair X on adjacent pins" | via InterfaceType.signals[].pair | [ELEC] | R1 |
| GEN-C1-035 | pins.py:120-129,161-167 | pins in `connector.pins` list order; `min_start = power_end + 1 + gap`; first-fit lowest free block | "Adjacent" = consecutive in the part's pin list, not physical layout. First free block wins; no preference for pin type, contact size, shielding | index | reason line says "adjacent pins", not which index/why | gen.power_signal_gap_pins; lock pins | [ELEC][AIT] | R1 R4 R7 |
| GEN-C1-036 | pins.py:147-148,175-176 | `stride = 1 + return_gap` for power groups with k>1 | Spacing power/return by unassigned contacts (ECSS-Q-ST-30-11C 6.11.3 a, cited in docstring only); falls back to unspaced with a warning | pins | warning pin_adjacency | gen.power_return_gap_pins | [ELEC] | R12 |
| GEN-C1-037 | pins.py:181-190 | fallback `free[:k]` non-adjacent pins | If no adjacent block, takes first free pins; flagged warning + provenance "no adjacent block was free" | pins | yes | none | [ELEC] | R12 |
| GEN-C1-038 | pins.py:47-60 | fixed pinout: first free pin whose `signal` equals the type signal name, previous pin kept if free | Pin match by exact name; unnamed pins never offered | n/a | provenance | Pin.fixed/signal | [ELEC][AIT] | R7 |
| GEN-C1-039 | engine.py:450-456 | pin with `signal` but no `interface_id` is treated as locked | Typed-in pin assignment implicitly locks without the user pressing lock | bool | partly (kept_locks in report) | Pin.locked | [ELEC] | R7 R12 |
| GEN-C1-040 | engine.py:586-598 | mating part = `part.mates_with` else same part; gender = opposite of box (or part gender); pins copied from box | Cable connector part, gender, keying, pin list. Fallback to same part only warns | n/a | provenance "mating:" line, warning | Part.mates_with; edit + `Connector.locked` | [AIT] | R1 R7 |
| GEN-C1-041 | engine.py:617-639 | topology: 1 trunk segment X-node to Y-node; if >1 connector at an end, one branch point and one star segment per connector | Fixed routing model (no real geometry); segments get length only if previously entered | m | segment table | segment lengths | [SYS][AIT] | R4 R6 |
| GEN-C1-042 | naming.py:9-16 | defaults `W{n:03d}`, `{harness}-P{n}`, `{harness}-{n:03d}`, `{harness}-S{n}`, `{harness}-B{n}`, `{harness}-L{n}` | ID scheme for harness, connectors, wires (numbered 001..), shields, branches, segments. Wire number = first free in iteration order (interface id, link order) | n/a | naming.json (only 4 keys in blank config) | naming.* | [AIT][SYS] | R3 |
| GEN-C1-043 | naming.py:68-86 | template tested on n=1..200 and 2 harnesses; width of 3+ digits rejected | Template acceptance rule; failing template silently replaced by default (warning at end) | n/a | warning "naming template ... not valid" | naming.* | [AIT] | R12 |
| GEN-C1-044 | engine.py:644,743,764 | IDs sorted as text | Lists (wires, segments) are in text order, so `L10` sorts before `L2`; exports inherit the order | n/a | comment engine.py:640-643 | none | [AIT] | R6 |
| GEN-C1-045 | engine.py:715-722 | on regeneration only `label`, `note`, `strip_a_mm`, `strip_b_mm` of an unlocked previous wire are kept | Strip lengths are never calculated; kept only if the wire is matched by key (interface, signal, source box) | mm | no | user entry per wire | [AIT] | R7 R8 |
| GEN-C1-046 | engine.py:697-710 | locked wire: `evolve(prev_w, pins/connectors/signal/interface only)` | Locked wire keeps gauge, part, colour AND length (even if only gauge was edited). Not re-sized, not contact-checked | n/a | provenance "override" line | via wires.py edit | [ELEC][AIT] | R7 R12 |
| GEN-C1-047 | engine.py:772-781 | in_review harness changed -> status draft, checker cleared | Workflow rule applied silently except an info finding | enum | info finding | none | [SYS] | R8 |
| GEN-C1-048 | engine.py:239,925-930 | `next_n` from `prev.next_harness_number` (>=1), never reused | Harness numbers monotonic; gaps stay | n | generation record | none | [SYS] | R3 |
| GEN-C1-049 | lengths.py:117-118 | `_NUMBER = [0-9]+([.,][0-9]+)?`; `MAX_LENGTH_M = 10_000.0` | Segment length import: no sign/exponent, comma accepted, > 10 000 m rejected (model bound also in model/base.py:104-109 as seen in grep context) | m | error text | none | [AIT] | R5 R12 |
| GEN-C1-050 | lengths.py:127-130,159 | `scale` (1.0; 0.001 for mm), `round(x*scale, 9)`; first row must be a heading; columns 0,1,2 by position | Unit conversion is an argument, not a column in the file; 9-decimal rounding | m | hint on failure | scale arg | [AIT] | R5 R14 |
| GEN-C1-051 | lengths.py:37-52 | `path_length`: BFS fewest hops; None if a second route exists or any segment length None | Single path rule; loops give "no length" | m | DRC `segment-loop` | none | [AIT] | R12 |
| GEN-C1-052 | lengths.py:86-99 | `wire_length`: wire's own `length_m` else sum of segments (cache 512) | Generated wires get `length_m` stored at generation, so later segment edits do NOT change them until regenerated; manual wires with no length use segments WITHOUT the service loop | m | no | wire edit | [AIT] | R6 R12 |
| GEN-C1-053 | mass.py:24-37 | connectors: `part.mass_g` of cable connectors; wires: `mass_per_m_g * length / part.conductors` | Pair rule: each conductor counts mass_per_m x length / conductors of the part (2 for a twisted pair part). Excludes contacts, backshells, accessories, splices, solder, labels, shield terminations | g | MassReport has totals and missing list only | Part.mass_g, mass_per_m_g, conductors | [SYS][AIT] | R1 R10 |
| GEN-C1-054 | mass.py:40-46 | margin = total x `mass_margin_fraction` (if numeric) | Mass margin from generation config only; None while placeholder | fraction | yes | gen.mass_margin_fraction | [SYS] | R2 |
| GEN-C1-055 | wires.py:34,41,651 | `EDITABLE`, `LOCKING = {gauge_awg, part_id, colour, length_m}`, `BULK_FIELDS` | Any edit of those four locks the whole wire (all four fields). Clear is refused: only Reset | n/a | docstring | none | [ELEC][AIT] | R7 |
| GEN-C1-056 | wires.py:411-417 | `GROUP_KINDS`: twisted_pair (2,2), shielded_pair (2,2), quad (4,4), coax (1,1), overall_shield (2,None) | Wire-count limits per group kind (manual groups only; generated power group can exceed 2) | wires | error text | none | [ELEC] | R3 R13 |
| GEN-C1-057 | wires.py:444-447,489-490 | manual group ends from gen.shield_end_a/b; unset/invalid -> "floating" without note here | Same fallback as generation but no provenance | enum | rule `shield-unterminated` (outside GEN) | gen.shield_end_* | [ELEC][AIT] | R2 R12 |
| GEN-C1-058 | wires.py:759-760 | label length 1..200, no control chars | Label text limit | chars | error text | none | [AIT] | R5 |
| GEN-C1-059 | manual_harness.py:37,154 | `ROLES` cable/inline/feedthrough/test; limit = `part.pin_count or MAX_PIN_COUNT` (1000 per model/base.py:105 in grep) | Manual connector role set; pins default `1..N` numeric | pins | error text | none | [AIT] | R13 |
| GEN-C1-060 | pairing.py:19-21,97-102 | tab, then `;`/`,`, then whitespace splitting; `casefold` matching; "pin 1 to pin 1" by identical ID | Proposal logic for pin pairing (propose only, person accepts) | n/a | proposal notes | none | [ELEC][AIT] | R4 |
| GEN-C1-061 | routing.py:83-88 | `TRACK_MARGIN 14, TRACK_STEP 16, SPINE_BASE 18, SPINE_STEP 12, CORRIDOR_PAD 12, MAX_ORDERED 40`, `top-6<y<bottom+6` | Diagram drawing geometry only. NOT harness routing and feeds no length or engineering number. Cosmetic group row | px | no | none | [SYS] | - |

---

## C2. Hidden assumptions

| id | file:line | description | persona | R |
|---|---|---|---|---|
| GEN-C2-001 | sizing.py:47-59, engine.py:954 | One project-wide ampacity table by AWG alone (A per gauge). Tool does not know insulation, conductor type, temperature rating, vacuum or single-wire vs bundle basis of the table; whether table values are already derated is the engineer's burden. | [ELEC] | R2 R4 |
| GEN-C2-002 | sizing.py:119,135 | Temperature is one user-computed factor. `max_ambient_temperature_c` is NOT used in sizing (only by DRC rules, standard_rules.py:121); the tool never derives the factor from ambient and wire rating. | [ELEC] | R2 R4 |
| GEN-C2-003 | engine.py:667 | Bundle count assumes the whole harness is one bundle and all wires fully loaded; branch segments with fewer wires, partial-load factor L (standard_profiles.py:46, "not applied automatically") and manual wires are ignored. | [ELEC] | R4 R12 |
| GEN-C2-004 | engine.py:955-961 | Every wire of an interface is sized for the same `max_current_a` (PWR and RTN equal; signal wires of a mixed type get the same value). DC only; no peak/RMS/duty. `voltage_v` is not used. | [ELEC] | R2 R5 |
| GEN-C2-005 | sizing.py:37-40, engine.py:954 | Voltage drop: DC, wire only, resistivity at the stated value (no temperature), nominal solid area; no contact or connector drop; return conductor equal length and gauge; evaluated against absolute volts regardless of supply voltage. | [ELEC] | R1 R4 |
| GEN-C2-006 | sizing.py:169-171 | Gauge is only set when ampacity, resistivity, max drop AND wire length are all known. Length exists only after segment lengths are entered and generation is re-run, so the first run leaves current-carrying wires without gauge (order of work is implicit). | [SYS][ELEC] | R6 |
| GEN-C2-007 | engine.py:690-692 | One length serves as electrical length, mass length, BOM and (downstream) cut length: segment sum + 2 x loop. No cut tolerance, strip allowance, twist take-up, slack or rounding rule. The tool does not call it a cut length. | [AIT][ELEC] | R1 R5 |
| GEN-C2-008 | engine.py:641-644, lengths.py:37 | Routing is a tree of nodes; length of a wire is the unique path between its two cable connectors; route is the same for all wires between the same connectors (no wire-specific detours, no pass-through of other branches). | [AIT] | R4 |
| GEN-C2-009 | engine.py:693 | Wire `length_m` is stored as data at generation (same field a person edits). A stored generated length is indistinguishable from an entered one unless `locked`; later segment edits leave it stale until regeneration. | [AIT][SYS] | R7 R12 |
| GEN-C2-010 | engine.py:1068-1079 | Power/ground interfaces are assumed twisted ("power" pair); pairs are grouped per source connector; signal pairs rely on `signal.pair` labels. Twisting, lay length, and shield coverage are not modelled. | [ELEC] | R4 |
| GEN-C2-011 | pins.py:120, 161 | "Adjacent pins" means consecutive entries in the connector's pin list; pin order in the library defines physical adjacency. Power-first policy and gap are the only EMC/segregation logic on pins. | [ELEC][AIT] | R4 |
| GEN-C2-012 | engine.py:598, pins.py (Request) | Generation does not compare wire gauge with pin contact size or crimp range; contact size is copied from the device pin, `contact_part` copied too. No tool/crimp setting is derived. | [AIT][ELEC] | R12 |
| GEN-C2-013 | engine.py:586-596 | If a device connector has no declared mating part, the cable end uses the same part number (warning only). Gender derived from part definition if the box gender is unspecified. | [AIT] | R12 |
| GEN-C2-014 | wiring.py:1-7 | "Matching is by position among the type's outs and ins": reordering signals in the interface type silently rewires TX/RX. | [ELEC][AIT] | R7 R12 |
| GEN-C2-015 | segmentation.py:152-162 | Default per_connector_pair: one harness per pair of device connectors; segregation (pyro, power vs signal classes) is ignored in this mode (note only). Redundancy "none" differs from "nominal". | [SYS][ELEC] | R4 R12 |
| GEN-C2-016 | sizing.py:141,145,161, engine.py:1015 | Numbers in notes are printed with `:g` (6 significant digits); this is the displayed rounding, internal values are full precision. No unit is printed after lengths or factors in several notes. | [ELEC] | R5 |
| GEN-C2-017 | engine.py:640-644, 743 | Wire and segment lists are sorted as text IDs (L1, L10, L2). Anything downstream that follows this order (wire list, labels, build sheet) inherits it; custom templates without zero padding give non-numeric order. | [AIT] | R6 |
| GEN-C2-018 | mass.py:22-37 | Mass counts only cable connectors, wires and the config margin. Contacts, backshells, accessories (sleeving, heat shrink), shields, splices, solder and labels are not included, and a wire without `part_id` is "missing". | [SYS][AIT] | R1 |
| GEN-C2-019 | generation_status.py:41-50 (input_hash) | "Up to date" means the hash of inputs matches; explanation text in `provenance` is not re-checked against the project when displayed (explain.py:15-29), so an explain line can describe an older state. | [SYS] | R1 R9 |
| GEN-C2-020 | engine.py:819-823, 850-897 | Wire key `interface|signal|source box` (when `/` in signal) decides identity across regeneration; renaming a signal or reorienting an interface loses locked wires/labels/strip lengths (warning `locked_data_lost`). | [AIT][SYS] | R8 R12 |

---

## C3. Outputs shown without derivation

| id | file:line | description | persona | R |
|---|---|---|---|---|
| GEN-C3-001 | explain.py:1-50 | "Explain" is a lookup of free-text lines logged at generation (`project.generation.provenance`), not a recomputation. No equation, no inputs with units, no source reference except the hard-coded "Table 6-41" text. | [SYS][ELEC] | R1 |
| GEN-C3-002 | sizing.py:144-146 | Ampacity note gives chosen AWG, derated limit and combined factor; not base table ampacity, bundle K, temperature factor separately (only K when table used), not the rejected larger-AWG candidates or why. | [ELEC] | R1 R12 |
| GEN-C3-003 | sizing.py:160-163 | Voltage-drop note gives drop and limit, not rho, length used, area, or whether the gauge changed from the ampacity result. | [ELEC] | R1 |
| GEN-C3-004 | engine.py:690-692 | No provenance line for wire length: path segments, segment lengths and 2 x loop are not listed. The length column of the wire list cannot be traced to its terms. | [AIT][ELEC] | R1 |
| GEN-C3-005 | engine.py:1056-1083 | No provenance for shield/twist groups (`_shields` records only the harness-level "placeholder" note); why a wire is in group S2 is not explainable. | [ELEC][AIT] | R1 |
| GEN-C3-006 | engine.py:933-948,985-990 | Wire part and colour choice leave no explain line (only a warning when part is missing). | [AIT] | R1 |
| GEN-C3-007 | pins.py:206-208 | Pin reason says "(pair X on adjacent pins)" or "single signal"; it does not say first-fit, the gap in force, why that block and not another. | [ELEC][AIT] | R1 |
| GEN-C3-008 | engine.py:1012-1016 | `contact_overload` error: "{wire}: {I} A exceeds the derated contact rating of {connector}" without rating, factor, limit or key used. | [ELEC][AIT] | R12 |
| GEN-C3-009 | engine.py:1007-1010 | Contact check skipped when rating/factor unset is only a provenance line, not a finding; a passing design looks checked. | [ELEC] | R12 |
| GEN-C3-010 | mass.py:10-47 | `MassReport` returns only totals and missing items; per-wire/per-connector contributions, the pair divisor and the margin base are not itemised. | [SYS][AIT] | R1 R10 |
| GEN-C3-011 | engine.py:707-710 | Locked-wire override note says the wire was kept; does not show the generated value that was replaced, who/when/why, or whether the locked gauge still passes. | [ELEC][AIT] | R7 R8 |
| GEN-C3-012 | engine.py:758-761 | Segmentation note says "share a harness because same pair of ..."; does not quote the active mode, segregation keys or why other interfaces were excluded. | [SYS] | R1 |
| GEN-C3-013 | engine.py:360-367, 243-249 | Plan report lists added/changed/unchanged counts; the diff of a changed harness (which wire got which new gauge/pin and why) is not shown by the plan. | [SYS] | R6 R8 |
| GEN-C3-014 | engine.py:972-984 | Default-gauge fill is explained but the wire stays unflagged as "not sized"; downstream it is indistinguishable from a sized gauge except through provenance. | [ELEC][AIT] | R7 |
| GEN-C3-015 | explain.py:6-12 | `_without_driver` rewrites provenance text at display time; displayed text differs from stored text. | [SYS] | R1 |

AIT view of what the generator feeds: wire list/build sheet (gauge, part, colour, length, label), labels (signal or `label`), strip lengths (entered only), contacts/tool (copied `contact_part`, `Part.tool` entered), terminations (pin `termination` copied from the device pin). An AIT engineer can read the result and the few explain lines but cannot trace length terms, shield group membership, colour or part selection, nor see a computed cut/strip length.

---

## C4. Forced choices (cannot be changed)

| id | file:line | description | persona | R |
|---|---|---|---|---|
| GEN-C4-001 | sizing.py:136-143 | Gauge selection algorithm is fixed: smallest gauge meeting ampacity, then upsize for drop. No alternative method (margin factor, minimum gauge, per-category rule, mechanical minimum). | [ELEC] | R4 |
| GEN-C4-002 | sizing.py:34 | Derating formula fixed as base x bundle x temperature; no extra factors (altitude, vacuum, partial-load L, insulation class). Only one ampacity table per project (not per wire part). | [ELEC] | R4 R13 |
| GEN-C4-003 | engine.py:954 | Conductor count for drop is 2 for categories power and ground, 1 otherwise; no per-interface return length/ground structure choice. | [ELEC] | R4 R7 |
| GEN-C4-004 | engine.py:691-692 | Service loop is the same 2 x value for every wire, end and harness; no per-harness, per-connector or per-wire allowance (except locking a length). | [AIT] | R3 R7 |
| GEN-C4-005 | engine.py:617-639 | Harness topology (trunk + one branch per side with several connectors) is fixed; segments of a generated harness are rebuilt each run, user-added segments would be lost (old lengths kept only per same node pair, engine.py:617). Unverified for the GUI path. | [SYS][AIT] | R4 R6 |
| GEN-C4-006 | engine.py:567-599 | Cable connector set, part, gender, pins are derived; user override only via the edited-connector flag (engine.py:609-615), not by pre-selection. | [AIT] | R7 |
| GEN-C4-007 | pins.py:120-225 | Placement strategy is fixed (power first, first-fit, alphabetical by interface). User can only lock a pin or fix a pinout; cannot set an order or a rule such as "keep shielded pairs apart". | [ELEC] | R4 R13 |
| GEN-C4-008 | engine.py:1056-1083, wires.py:511-516 | Generated shield/twist groups follow the interface type and cannot be edited, ungrouped or re-ended per group ("comes from the construction of the interface type"). Only manual groups editable. | [ELEC][AIT] | R7 |
| GEN-C4-009 | engine.py:1050 | Coax shield termination cannot be set. | [ELEC] | R4 |
| GEN-C4-010 | wires.py:41,697-710 | Locking is all-or-nothing: editing gauge alone also freezes part, colour and length of that wire; a locked wire is not re-sized, not contact-checked and its length does not follow segment edits. | [ELEC][AIT] | R7 |
| GEN-C4-011 | wires.py:99-103 | A locked field cannot be cleared on one wire (only Reset, which discards all overrides). | [ELEC][AIT] | R7 |
| GEN-C4-012 | wires.py:168-172, 381-387 | Pins of a generated wire cannot be changed and a generated wire cannot be deleted; the person must change the design. | [AIT] | R7 |
| GEN-C4-013 | manual_harness.py:70-74 | A generated harness refuses an added connector; mixing hand-built and generated content within one harness is not possible. | [AIT] | R7 |
| GEN-C4-014 | segmentation.py:8,109 | Only three segmentation modes and two-ended interfaces; multi-drop is "not generated yet". | [SYS] | R4 R13 |
| GEN-C4-015 | engine.py:1081-1082 | Overall shield always ends as the global shield_end_a/b; no per-harness or per-group-type setting. | [ELEC] | R3 |
| GEN-C4-016 | wires.py:34-41 | Strip lengths: per wire entered only (kept in engine.py:715-722); no rule-based default per gauge/contact, no bulk entry via wire edit (`BULK_FIELDS` excludes them). | [AIT] | R3 R7 |
| GEN-C4-017 | engine.py:985-990 | Colour assignment only by signal name; no colour by category/gauge/pair scheme. | [AIT] | R3 R4 |
| GEN-C4-018 | model/base.py:104-109, units.py:7 | Lengths <= 10 000 m, strips <= 100 000 mm, AWG 0..40 (limits seen in grep context and units.py). | [AIT] | R3 |
| GEN-C4-019 | naming.py:68-86 | Template language is Python `str.format` with only `{n}` and `{harness}` placeholders; width >= 3 digits rejected, 200-sample test. | [AIT] | R3 |
| GEN-C4-020 | lengths.py:37-52 | A loop in the segment graph gives no length at all; no rule to pick one route. | [AIT] | R4 |

---

## C5. Inputs and outputs exchanged with other tools or files

| id | file:line | description | persona | R |
|---|---|---|---|---|
| GEN-C5-001 | engine.py:139-141,153-195 | Reads config files `generation`, `derating` (plus `segmentation`, `segregation`, `naming` in segmentation.py:41 / naming.py:89). Invalid values become findings and are silently treated as unset. | [SYS][ELEC] | R3 R14 |
| GEN-C5-002 | engine.py:424-433, 585, 933-939 | Reads library parts (`mates_with`, `mass_g`, `mass_per_m_g`, `conductors`, `ratings`, `category`) and interface types (signals, pair, construction, shielding, default_gauge_awg). Values originate from imported library files; no link or hash shown in GEN. | [SYS][ELEC][AIT] | R14 |
| GEN-C5-003 | engine.py:347-353 | Writes `GenerationRecord`: `input_hash`, `generator_version` (`__version__`), `next_harness_number`, `placeholders_used`, provenance map. No timestamp (by design, engine.py:5-6) and no user/reason. | [SYS] | R8 R9 |
| GEN-C5-004 | generation_status.py:21-50 | `input_hash` covers units, interfaces, types, parts, zones, config, box connectors, locked wires, segment lengths of generated harnesses, manual interface ids. Unlocked wire labels, notes and strip lengths are excluded. | [SYS] | R9 R14 |
| GEN-C5-005 | lengths.py:121-187 | CSV import of segment lengths (harness, segment, length) read by column position; unit via `scale` argument. The source file name, hash and unit are not stored with the lengths. Result: `Put harnesses` with new `length_m`. | [AIT] | R5 R14 |
| GEN-C5-006 | pairing.py:105-164 | Pasted table (tab/comma/semicolon/space) for pin pairs; proposal only, nothing stored about origin. | [AIT][ELEC] | R14 |
| GEN-C5-007 | mass.py:22-47 | Reads parts and config for mass; no export file in GEN (mass appears in outputs elsewhere). | [SYS] | R10 |
| GEN-C5-008 | wires.py (all) | No file I/O; edits are `Op`s executed by History. Change log (who/when/reason) is not written here. | [SYS] | R8 |
| GEN-C5-009 | manual_harness.py, wires.py:241-250 | New IDs from `naming` config and used IDs across the whole project; the project's pin and part libraries are read. | [AIT] | R14 |
| GEN-C5-010 | engine.py:1089-1095 | `generate_project` is the only scripting entry in GEN (`plan_generation` pure, `apply_ops`). Other functions are plain Python functions without a documented API. | [SYS] | R11 |

---

## C6. Customisation points that exist

- Config (`generation.json`): `conductor_resistivity_ohm_m`, `service_loop_m`, `default_gauge_awg`, `mass_margin_fraction`, `power_signal_gap_pins`, `power_return_gap_pins`, `shield_end_a/b`, `wire_part_by_construction`, `wire_colour_by_signal`.
- Config (`derating.json`): `ampacity_a_by_awg`, `bundle_derating`, `bundle_factor_by_count`, `temperature_derating`, `max_voltage_drop_v`, `contact_current_factor`, `contact_rating_key`.
- Config: `segmentation.mode` (3 modes), `segregation.category_pairs_to_separate / forbid_pyro_with_other / forbid_nominal_with_redundant`, `naming.*` templates (6 kinds).
- Optional ECSS value profile (standard_profiles.py:1-110) fills only unset values and marks the file placeholder; every value carries a requirement ID.
- Interface level: `max_current_a`, `redundancy`, interface-type `default_gauge_awg`, signal order/`pair`/direction, `construction`, `shielding`.
- Pin level: lock, fixed pinout, typed-in signal (engine.py:445-456).
- Wire level (wires.py): edit gauge, part, colour, length (locks); label, note; strip lengths kept; reset; bulk edit of gauge/part/colour/length by harness, signal or selection; manual wires with free ends; manual twist/shield/coax groups with own ends; edited cable connectors; manual harnesses (manual_harness.py).
- Segment lengths: entered per segment or CSV import.
- Part level: `conductors`, `mass_g`, `mass_per_m_g`, `ratings`, `mates_with`, `tool`.
- Preview: `plan_generation` never changes the project and reports kept/added/changed/removed, locked pins kept, and warnings (e.g. `locked_data_lost`).
- Placeholder discipline: unset values leave gauge undecided with the missing keys named (sizing.py:3-4,128-134,170).

---

## Override and regeneration summary

- Overrides that survive regeneration: locked pins/wires (all four wire fields together), labels, notes, strip lengths (while wire matched by key), edited cable connectors, manual wires/groups/harnesses, segment lengths on same node pair.
- Overrides that do NOT exist: gauge/colour/part without locking; per-field override; generated shield groups; generated wire deletion.
- Flagging: locked wire carries an "override" provenance line; plan report lists `kept_locks` for pins only. There is no justification text, author or date on an override (R7, R8 unmet in GEN).
- A locked wire is exempt from sizing and the contact check at generation time; DRC rules elsewhere may still check (unverified).
- Anything typed on an unlocked wire other than label/note/strip is overwritten on the next run.

## Top findings

1. GEN-C3-001 / GEN-C3-004: "Explain" is a replay of stored text lines; wire length, shield groups, colour and part have no derivation at all, and gauge shows only the combined factor, not base ampacity, K and temperature factor.
2. GEN-C1-011 / GEN-C1-012 / GEN-C2-003 [ELEC]: bundle K uses the whole-harness wire count (fully loaded) and voltage drop is doubled for power/ground categories, both hard-coded; ambient temperature never feeds the temperature factor (GEN-C2-002).
3. GEN-C1-002 / GEN-C1-007 / GEN-C4-001 [ELEC]: gauge = smallest AWG passing ampacity x K x temperature, then upsized for absolute-volt drop; no method choice, no minimum gauge, no crimp-range or contact-size check (GEN-C2-012).
4. GEN-C1-021 / GEN-C3-008 [ELEC][AIT]: contact overload ignores wire gauge and contact size, is skipped silently for unset rating/factor and for locked wires, and its error shows no rating or factor.
5. GEN-C1-013 / GEN-C2-007 / GEN-C2-009 [AIT]: wire length is segment sum + 2 x one loop value, stored as data (stale after segment edits, indistinguishable from an entered length), with no cut tolerance, strip allowance or twist take-up; not traceable (GEN-C3-004).
6. GEN-C1-046 / GEN-C4-010 / GEN-C4-011 [ELEC][AIT]: any gauge/part/colour/length edit locks all four fields; locked wires are not re-sized or re-checked, keep stale lengths, and carry no reason, author or date.
7. GEN-C1-024 / GEN-C4-008 [ELEC][AIT]: shield, twist and coax groups are decided by hard-coded construction logic (power always a "twisted pair", coax always 360 deg, a wire can sit in a pair group and an overall group), with no provenance and no per-group override.
8. GEN-C1-035 / GEN-C1-016 / GEN-C1-029 [ELEC]: pin placement is first-fit in the part's pin-list order with adjacency = list neighbours; the power-return gap defaults silently to 0 with no note, and in the default per_connector_pair mode segregation classes are not applied.
(AIT-specific: strip lengths are never computed, only kept per wire GEN-C1-045/C4-016; labels, build-sheet order and wire IDs follow text sort and the naming template GEN-C1-042/044.)

Next: [the audit](../transparency_audit.md), [appendix A](configuration-and-defaults.md), [appendix C](rules-and-warnings.md)
