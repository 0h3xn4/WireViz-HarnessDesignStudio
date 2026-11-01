# Transparency audit, appendix F: editing and change control

This page is appendix F of the [transparency audit](../transparency_audit.md): the row-level catalogue for overrides, locks, change history, baselines and releases. Each row names the file and line the reviewer opened. IDs read `EDIT-C<category>-<number>`; the categories and the tags `[SYS]`, `[ELEC]` and `[AIT]` are explained in section 1 of the audit. Paths beginning with `work/` are scratch projects the reviewer made while auditing; they are not in the repository. Nothing on this page was changed in the code: it is read-only.

## Contents

- [C1. Hard-coded constants, defaults, rules](#c1-hard-coded-constants-defaults-rules)
- [C2. Hidden assumptions](#c2-hidden-assumptions)
- [C3. Outputs the user sees without seeing how they were derived](#c3-outputs-the-user-sees-without-seeing-how-they-were-derived)
- [C4. Forced options (cannot be changed)](#c4-forced-options-cannot-be-changed)
- [C5. Inputs and outputs exchanged with other tools or files](#c5-inputs-and-outputs-exchanged-with-other-tools-or-files)
- [C6. Customisation points that DO exist (what the engineer can change)](#c6-customisation-points-that-do-exist-what-the-engineer-can-change)
- [Change history (R8) and overrides (R7): answers to the special questions](#change-history-r8-and-overrides-r7-answers-to-the-special-questions)
- [Top findings](#top-findings)

**Scope.** Read in full (all lines): core/vcs/{consistency 118, diff 237, gitindex 95, gitinfo 315, gitname 122, hashing 38, locks 207, lockview 276, release 610, report 104, roles 82, snapshot 172, timeline 166}.py; core/{commands 274, recovery 140, mergefix 168, devices 2059, edit 1187, links 992, connector_edit 313, copies 108}.py. Also read for context (not my files, partial): core/wires.py 1-200, core/build_data.py 1-30, core/counterparts.py 1-111, core/ids.py, core/model/review.py 1-106, core/model/physical.py 11-100, core/generate/engine.py 600-720, core/model/config.py 50-90. Nothing was run. Persona tags: [SYS] systems, [ELEC] electrical, [AIT] assembly/integration/test.
Short names: Fig = line of the file named in the row; "log" = project change log (ChangeEntry).

## C1. Hard-coded constants, defaults, rules

Row: id | file:line | value or rule | what it does / feeds | unit | visible? | editable? | R | persona

| id | file:line | value/rule | effect | unit | visible | editable | R | persona |
|---|---|---|---|---|---|---|---|---|
| EDIT-C1-001 | vcs/release.py:34 | `MIN_COMMENT = 10` | Min length of release/revision comment and of accept-placeholder / accept-unapproved-parts reasons (lines 151, 243, 298); any 10 characters pass | chars | message only after failing | none | R7 R8 R12 | SYS ELEC AIT |
| EDIT-C1-002 | vcs/release.py:35, 115, model/review.py:19 | `MAX_COMMENT = 2000`; names/text `limit=200`; Justification 10..2000 | Upper bounds of comment, names, waiver justification | chars | on failure | none | R8 | SYS |
| EDIT-C1-003 | vcs/release.py:36-47 | `DATE_RE [0-9]{4}-[0-9]{2}-[0-9]{2}` | Release/review date is a typed ISO date; no time of day, no timezone, not read from a clock (library.py:44 says tool never reads a clock into project data) | date | field | none | R8 R9 | SYS AIT |
| EDIT-C1-004 | vcs/release.py:78-92 | `next_revision`: A..Z, AA, AB; letters only | Revision scheme fixed; a revision not made of capital letters blocks "new revision" (80-83) | - | on failure | none | R3 R8 | SYS |
| EDIT-C1-005 | vcs/release.py:95-97 | `f"C{n+1:04d}"` | Change-log entry ID C0001..; max(n)+1 | - | log table | none | R8 | SYS |
| EDIT-C1-006 | vcs/release.py:165-174 | date may not be earlier than latest log entry of the same harness | Always-on chronology rule | date | blocker text | none | R12 | SYS |
| EDIT-C1-007 | vcs/roles.py:183-185, 189-192 | `release_distinct_roles` default off; `FUTURE_DAYS = 1` | When on: author/checker/releaser must differ, date >= project latest entry, <= today+1 day. Off = one person can author, check and release | days | naming.json (documented) | naming.json key; FUTURE_DAYS none | R2 R3 R8 | SYS |
| EDIT-C1-008 | vcs/roles.py:195-197 | `person_key`: NFKC + casefold + whitespace collapse | Defines "same person"; "J. Smith" and "John Smith" are different people | - | none | none | R8 | SYS |
| EDIT-C1-009 | vcs/release.py:265-274 | unapproved part = missing OR `approval != "approved"` OR `unverified`; checked only for connector parts and wire parts | Release gate for parts. Contact parts, accessory parts and counterpart parts (snapshot.py:321-331 freezes them) are NOT approval-gated | - | blocker text | override with reason (R7 ok) | R7 R12 | ELEC AIT |
| EDIT-C1-010 | vcs/release.py:367-411 | release gate: has wires; generation not stale; every wire has `gauge_awg`; every wire has a length; outputs current | Fixed list of release conditions. Strip length, contacts, crimp tool, labels, accessories and test limits are NOT gate items | - | blocker texts | none (only 2 of the gates can be overridden) | R3 R4 R12 | ELEC AIT |
| EDIT-C1-011 | vcs/release.py:378-392 | only verifier errors and DRC errors with `waiver is None` that relate to this harness (or `config-invalid`) block | Warnings never block a release; waived errors pass | - | blocker texts | waiver (justification >=10 chars) | R7 R12 | SYS ELEC |
| EDIT-C1-012 | vcs/release.py:225-262 | placeholder config files block release unless a reason (>=10 chars) is given | Release on unreviewed derating/EMC/etc. values possible with a typed reason, appended to comment (260-262) | - | blocker text + comment | reason text | R7 R8 | ELEC |
| EDIT-C1-013 | vcs/release.py:519-524 | `author=h.author or by`; `checker=checker or None`; `approver=by` | Role bookkeeping at release; with the roles setting off the checker is optional and the author may be the releaser | - | report.py:444-448 | none | R8 | SYS |
| EDIT-C1-014 | vcs/release.py:556-563 | new revision keeps author; clears checker/approver/released_on | Next revision inherits the author silently | - | none | none | R8 | SYS |
| EDIT-C1-015 | vcs/release.py:586 | `status="in_review", author=by` | Submitting for review overwrites author each time; review entry has empty comment (589) | - | log | none | R8 | SYS |
| EDIT-C1-016 | vcs/snapshot.py:248 | `FROZEN_CONFIG_FILES = ("derating","emc","segregation","titleblock")` | Config frozen by a release; edits blocked while any harness is released (locks.py:131-140). Not frozen: `segmentation`, `naming` (incl. `signal_counterparts`) | - | lockview.py `config_key_locked` | none | R3 R8 | ELEC |
| EDIT-C1-017 | vcs/snapshot.py:249-258 | `FROZEN_GENERATION_KEYS` = resistivity, mass margin, `power_return_gap_pins`, shield ends A/B, continuity max, isolation min, isolation voltage | Only these generation keys are frozen/recorded in a baseline. NOT frozen: `service_loop_m` (adds 2x loop to every length, engine.py:661-667), `default_gauge_awg`, `wire_part_by_construction`, `power_signal_gap_pins` | ohm.m, -, V, ohm, Mohm | baseline snapshot | none | R3 R9 | ELEC AIT |
| EDIT-C1-018 | vcs/snapshot.py:340-342 | `placeholder` flag excluded from the frozen values | Changing placeholder true to false is not a frozen change, not logged | - | none | none | R8 | ELEC |
| EDIT-C1-019 | vcs/locks.py:27-30 | `COSMETIC_*` fields editable after release: interface name/notes/requirement_id; unit name/notes/zone; part notes; type name/notes | Everything else on those objects is locked. Zone, interface requirement_id and notes change with no log entry | - | lockview.py:395-408 | none | R7 R8 | SYS |
| EDIT-C1-020 | vcs/lockview.py:283, locks.py:193-203 | box connector frozen fields = part_id, gender, keying (+pins used); label, name, carries, notes stay editable | Name/label changes of a released box connector are silent | - | lockview | none | R8 | SYS AIT |
| EDIT-C1-021 | vcs/hashing.py:132-156 | `content_hash` = `model_hash` after deleting baselines, change log and release bookkeeping | Hash stored in each baseline and output manifest (outputs/build.py:45,286). Covers everything else serialized (incl. non-frozen config, placements; placements: unverified) | sha256 | manifest | none | R9 R14 | SYS |
| EDIT-C1-022 | vcs/release.py:537, consistency.py:39-56 | `Baseline.content_hash` stored but never compared on load; integrity compares snapshot objects, not the hash | The recorded hash is informational; tamper detection relies on field comparison of the snapshot | - | baseline file | none | R9 | SYS |
| EDIT-C1-023 | commands.py:165 | `MAX_UNDO_STEPS = 200` | Undo depth; oldest dropped (219) | steps | none | none | R8 | SYS |
| EDIT-C1-024 | commands.py:209-217 | edit cancelled if it adds any integrity error of a new (code, object) pair, or one more of the same | Rule deciding which edits are allowed; messages only after the fact | - | dialog text | none | R12 | SYS |
| EDIT-C1-025 | devices.py:51-64, 66-73 | pin mode free/fixed/locked ("locked wins over fixed", 158); roles power/return/ground/signal/shield/spare; direction words map ("passive"->"", "both"->bidir, ...) | Fixed vocabularies; "passive"/"n/a" collapse to "not set" | - | UI choices | none | R4 R13 | ELEC AIT |
| EDIT-C1-026 | devices.py:145, ids.py:9 | pin name `^[A-Za-z0-9][A-Za-z0-9_.\-]{0,15}$` ; ID `^[A-Za-z][A-Za-z0-9_.\-]{0,63}$`, Windows reserved names | Pin ID max 16 chars, no spaces/slash: connector pin names such as "A+" or "1/2" are refused | chars | error message | none | R3 | ELEC AIT |
| EDIT-C1-027 | devices.py:167-170, model/base.py:105 | `MAX_PIN_COUNT = 1000`; limit = part.pin_count if set | Max pins per connector; also max for part pin_count (1722) | pins | error | none | R3 | ELEC |
| EDIT-C1-028 | copies.py:346 | `MAX_DEVICES = 10` | Max number of one device incl. original; copies fixed as `ID-R`, `ID-3`.. (349-351) | count | error | none | R3 | SYS |
| EDIT-C1-029 | edit.py:112-125 | `_box_part`: SMA for rf_coax, RJ45 for ethernet, Micro-D 9 for power types, else Micro-D by number of types {1:9,2:15,3:21,4:25} else 31 | Silent choice of connector part for template units; parts are example (EX-*) | pins | none | none (TEMPLATES dict in code) | R3 R13 | ELEC AIT |
| EDIT-C1-030 | edit.py:136-154 | 14 device templates: prefixes OBC, PCDU, RW, ST..., subsystems, connector counts, carried types | Hard-coded template catalogue (e.g. "computer_xl" 11 x 6-type connectors) | - | template picker | none | R13 | SYS |
| EDIT-C1-031 | edit.py:178-183, 170-175, links.py:478-483, devices.py:314-323 | ID schemes `IF-%03d`, `<prefix>%d`, `L%d`, `<unit>-J%02d` / name `J%02d`; `DEV%d`; suggest_device_id: first word, digits stripped, 8 chars upper (1457) | ID/naming sequences for interfaces, units, links, box connectors (not the config `naming` templates used for harness/wire IDs, config.py:78-84) | - | IDs visible | harness/wire/cable-conn via naming.json only | R3 | SYS AIT |
| EDIT-C1-032 | edit.py:32-39, 244 | LANE_WIDTH 470, UNIT_W 240, SLOT_STEP 70, UNIT_GAP 24, MAX_DIAGRAM_HEIGHT 200000, MAX_SWEEPS 30, `_half` rounding to 0.5 | Cosmetic diagram layout (grouped) | scene units | diagram | none | - | SYS |
| EDIT-C1-033 | edit.py:729 | `redundancy = "none" if side == "none" else side` | New interface redundancy inherited silently from the from-unit's chain | - | interface field | edit afterwards | R7 | SYS |
| EDIT-C1-034 | devices.py:1439-1445, 1522, 1497 | default subsystem = most common one else "general"; new device side "nominal"; name falls back to "Device N" | Silent defaults for new device | - | shown in table | edit | R2 | SYS |
| EDIT-C1-035 | devices.py:1736-1770, 1946-1954 | part `approval="pending"`, `unverified=True` for parts and interface types the editor makes (1953); tool never approves | Good: new library data starts unapproved | - | part list | approval by hand-editing file only (unverified: no UI) | R7 | ELEC AIT |
| EDIT-C1-036 | devices.py:1727-1733, 1773-1790 | description `"{n}-pin connector, {gender}"`; mate ID rule `X-F`<->`X-M`; `_swap_gender` regex | Gender of connector read from free-text description (`part_gender`) | - | description | edit | R4 | ELEC AIT |
| EDIT-C1-037 | links.py:44-50, counterparts.py:17-25 | default counterpart words tx/rx, txd/rxd, txp/rxp, txn/rxn, dout/din, mosi/miso, sdo/sdi | Decides which pins a proposed link pairs and which pairings are warned; config can replace (`signal_counterparts`) | - | naming.json | naming.json | R3 R13 | ELEC AIT |
| EDIT-C1-038 | links.py:168-179 | `effective_role`: "RTN"->return, "GND"->ground, category power->power, other->signal, none->"" | Role of a pin derived from the signal name when `Pin.role` empty; used by link review "power without return", "unpaired" | - | link findings text only | per-pin role override | R1 R7 | ELEC |
| EDIT-C1-039 | links.py:606, 953 | review shows first 4 pairs (`powered[:4]`); links.py:606 `[:200]` wire signal truncated | Display truncation / signal "A/B" joined and cut at 200 chars (606) | chars | message | none | R5 | AIT |
| EDIT-C1-040 | links.py:634-639 | harness name from link: `link.name or "<unitA> to <unitB>"`, uniqueness suffix `(Lx)` / `(Lx-n)` | Name of harness made from a link | - | harness list | rename | R7 | AIT |
| EDIT-C1-041 | devices.py:1275-1363 | inline checks CD-K1..K8 (severity fixed: e.g. pins_missing info, gender_unspecified warning, signal_on_two_pins warning) | Hard-coded severities and wording; "not design rules" | - | under pin table | none | R3 R12 | ELEC AIT |
| EDIT-C1-042 | vcs/gitinfo.py:121-123, gitname.py:500, gitindex.py:19, mergefix.py:464 | `MAX_OBJECT 1 MiB`, `MAX_DELTA_DEPTH 64`, `MAX_UP 12` parent folders, `MAX_CONFIG 64 KiB`, `MAX_INDEX 256 MiB`, `MAX_FILE 64 MiB` | Read limits when reading .git by hand; failure = "not known" | bytes | none | none | R14 | SYS |
| EDIT-C1-043 | vcs/gitinfo.py:108-110, 403-409 | last commit of whole repository (not of the project), author name only, subject cut at 200 | "Who made the last change" display can name someone who did not touch the project; uncommitted edits not seen | - | window text | none | R8 | SYS |
| EDIT-C1-044 | vcs/timeline.py:289-308 | diff display: values cut at 80 chars (`text[:77]+"..."`); units appended by suffix map `_UNITS` (m, V, A, g, degC, mm2); `mm` and `ohm` missing | Values in diff views are truncated; unit label from field-name suffix only (`strip_a_mm`, `*_ohm` get none) | chars | diff view | none | R5 | ELEC AIT |
| EDIT-C1-045 | vcs/diff.py:186-197 | `KIND_NAMES` vs `SCREEN_KIND_NAMES` (unit -> Device) | Files written to disk keep "Unit" wording, screen says "Device" | - | both | none | R14 | SYS |
| EDIT-C1-046 | wires.py:34-44 (context) | `LOCKING = {gauge_awg, part_id, colour, length_m}` set one `Wire.locked` flag | Editing ANY of these locks all four: setting only a length freezes gauge/type/colour too (engine.py:697-709), so derating is no longer re-evaluated | - | log note "override:" (engine.py:709); output column "yes" (outputs/tables.py:127) | Reset (wires.py:193) | R7 R12 | ELEC AIT |
| EDIT-C1-047 | build_data.py:10-18 (context) | strip length, contact, tool, accessories "entered; nothing computed or checked" | No default strip length, no sanity check (no contact-fits-pin, no range) | mm | wire editor | by hand | R7 R12 | AIT |

## C2. Hidden assumptions

| id | file:line | assumption (why it matters) | R | persona |
|---|---|---|---|---|
| EDIT-C2-001 | vcs/locks.py:25-30, 33-70 | "Design" vs "cosmetic" split is defined in code per object type; an engineer cannot tell which fields are frozen except by trying (or lockview.cosmetic_fields) | R2 R3 | SYS |
| EDIT-C2-002 | vcs/snapshot.py:248-258 | Release freezes only some config; `service_loop_m` and the default gauge are outside it, so a released length list cannot be reproduced from the recorded config alone | R9 | ELEC AIT |
| EDIT-C2-003 | vcs/snapshot.py:279-290, 298-310 | A wire's "used pin" on a box connector is derived by pin ID equality between cable pin and box pin (`same ID`, line 281-283); renaming conventions would break it silently | R6 | ELEC AIT |
| EDIT-C2-004 | vcs/consistency.py:59-87 | A baseline made before `parts`, `interface_types`, `config`, `links` were recorded (`None`) is not compared at all; older releases are weaker-protected | R9 | SYS |
| EDIT-C2-005 | vcs/report.py:416; timeline.py | Revision order = `(len, string)` of letters; works for A..Z, AA, but depends on `next_revision` only | R8 | SYS |
| EDIT-C2-006 | vcs/hashing.py:132-156 | Hash ignores author/checker/approver, so changing who approved after the fact is invisible to the output "current" test (but release_integrity flags harness change via `normalize` compare) | R8 R9 | SYS |
| EDIT-C2-007 | devices.py:1097-1140 | Direction/category "derived, never guessed": from interface type of the pin's interface, else from signal NAME matched to all (or carried) types; ambiguity -> blank. Name-based inference with silent narrowing by `connector.carries` (1130-1131) | R1 R4 | ELEC |
| EDIT-C2-008 | links.py:119-140 | Link direction: Pin.direction wins; else derived direction is dropped to "" for signals of one-directional types, and for signals with no partner (`direction_judged`, `passthrough_signals` from verify.py). Directional conflicts therefore not seen on many pins | R1 R12 | ELEC |
| EDIT-C2-009 | links.py:168-179 | Role "power" requires an interface type of category power; any other named signal is "signal"; a pin with unknown signal name (typo) is "signal" and never triggers power rules | R1 R12 | ELEC |
| EDIT-C2-010 | links.py:312-414 | Pairing proposal is by name only; first match in natural reading order wins, counterparts before equals; same-side equal names (TX-TX) are never paired; `_pair_side` is skipped when both pins have a direction | R1 R4 | ELEC AIT |
| EDIT-C2-011 | links.py:736-795 | "What a link carries" is guessed: type that explains most pairs; ties go to fewer signals then first ID; RS-422 and Ethernet look the same (documented in docstring 721-724) | R1 R4 | SYS ELEC |
| EDIT-C2-012 | links.py:816-834 | "Power loop" exemption: a power type with 2+ signals and no RTN/GND (e.g. heater HTR+/HTR-) is assumed to carry its own return | R1 | ELEC |
| EDIT-C2-013 | links.py:600-607 | Wire signal from two pins: both same -> that name; differ -> "A/B" (cut at 200); one missing -> the other. Becomes label/signal text on build output | R1 | AIT |
| EDIT-C2-014 | edit.py:1114-1134, 813-843 | Copy of a device (duplicate or redundant twin): pins lose interface allocation and signal unless locked/fixed; connector IDs = `<newid>-<suffix of old>`; zone of twin = NEXT lane (`(lane+1) % len(zones)`, 818); name suffix "(redundant)" | R1 R6 | SYS |
| EDIT-C2-015 | edit.py:769-803 | Mirrored interfaces of a twin: skipped silently into `skipped` list when no free connector; ID `<iface>-<suffix>` | R6 R12 | SYS |
| EDIT-C2-016 | edit.py:703-710, 379-383 | Guided mode picks `free[0]` connector (sorted by ID) and marks the end `auto=True`; confirm only by `ops_confirm_interface` | R4 R7 | SYS ELEC |
| EDIT-C2-017 | devices.py:167-170, 372-374 | Part pin count is the cap; a part with no `pin_count` caps at 1000 and creates no pins by default (373) | R2 | ELEC AIT |
| EDIT-C2-018 | devices.py:253-264, 267-278 | "Generated draft harness only becomes out of date": editing/deleting a pin does NOT block, but silently makes the draft wiring stale; only hand-made or released harnesses block | R6 R12 | SYS ELEC |
| EDIT-C2-019 | mergefix.py:451-462, 504-537 | After a git merge the `generation.json` conflict is resolved by keeping OUR side blindly; the hash of "their" design is dropped, a Generate is needed to re-sync | R8 R14 | SYS |
| EDIT-C2-020 | recovery.py:306-353 | Autosave journal is the whole project as JSON text, one file, inside the project folder; recovery restores the latest state, with no list of what changed | R8 R14 | SYS |
| EDIT-C2-021 | vcs/roles.py:204-207 | Name defaults from `git config user.name` only when roles setting is on; not an authenticated identity; first-line only, includes ignored | R8 | SYS |
| EDIT-C2-022 | commands.py:246-252 | After the project is saved, a release can no longer be undone (RELEASE_SAVED); before saving it can, with no record | R8 | SYS |

## C3. Outputs the user sees without seeing how they were derived

| id | file:line | what is shown / not explained | R | persona |
|---|---|---|---|---|
| EDIT-C3-001 | devices.py:1182-1227 (`pin_rows`) | Direction, category and note per pin are derived; the note says "From <type>" or why blank, which is a partial trace. Which signal-name match and which narrowing step was used is not itemised | R1 | ELEC |
| EDIT-C3-002 | links.py:153-179 | Effective role of a pin shown/used in link findings, but the Devices pin table role shows only the stored role (empty = "taken from the signal name"); no column that shows the derived role (unverified for GUI) | R1 R7 | ELEC |
| EDIT-C3-003 | links.py:736-795 | Derived interface label "CAN, 2 wires" / "RS-422 or Ethernet" without the matching score | R1 | SYS ELEC |
| EDIT-C3-004 | links.py:853-955 | Link review messages carry rule, pins and fix, but not a rule ID or a limit; no way to waive or override a single link finding (no waiver path for LinkFinding: unverified outside this file) | R12 | ELEC AIT |
| EDIT-C3-005 | devices.py:1275-1363 | CD-K checks: check ID, message; no "why it matters", no override | R12 | ELEC AIT |
| EDIT-C3-006 | vcs/release.py:321-422 | Release blockers: each says what, but gauge_pending message does not name the missing derating inputs themselves and length_unknown does not list wires (only first) | R12 | ELEC AIT |
| EDIT-C3-007 | vcs/consistency.py:39-56 | "was changed after its release ... no longer matches its baseline" names the category (interface, device, box connector, part, type, link, config) but not the field and value; the diff is a separate view (timeline.compare_revisions) | R8 R12 | SYS |
| EDIT-C3-008 | vcs/locks.py:204-207 | Lock refusal sentence names the harness and revision; it does not name which field was refused | R12 | SYS |
| EDIT-C3-009 | commands.py:209-217 | Cancelled edit lists new integrity errors but not the full rule or the pre-existing ones | R12 | SYS |
| EDIT-C3-010 | vcs/release.py:254-318 | Release notes for placeholder / unapproved parts are appended to a free-text comment; the list of placeholder files is shown but not their values | R9 | ELEC |
| EDIT-C3-011 | vcs/diff.py:98-110, timeline.py | Diff shows before/after of stored fields only; derived consequences (gauge, voltage drop, mass) are not diffed; wires diff only if changed in the snapshot | R8 | ELEC AIT |
| EDIT-C3-012 | copies.py:385-421 | "N of these devices" count is derived from IDs ending -R, -3.. ; a hand-made `-R` unit counts | R1 | SYS |
| EDIT-C3-013 | mergefix.py:559-582 | merge-fix reports files in conflict, but not what Generate had decided on each side | R8 | SYS |

## C4. Forced options (cannot be changed)

| id | file:line | forced choice | R | persona |
|---|---|---|---|---|
| EDIT-C4-001 | vcs/locks.py:145-147 | A released harness can only be replaced by its next revision with identical content; no unlock, no override, even to correct a typo in a note on a wire | R7 | ELEC AIT |
| EDIT-C4-002 | vcs/locks.py:80-94 | Baselines and change-log entries cannot be edited or deleted, even by the author, e.g. to fix a wrong name or reason; a wrong release comment stays forever | R7 R8 | SYS |
| EDIT-C4-003 | commands.py:57, 246-252 | Saved release cannot be undone | R7 | SYS |
| EDIT-C4-004 | vcs/release.py:128-137, 34 | Comment and reason are mandatory (>=10 chars) but free text only; there is no reason on any non-release edit, and no category list for reasons | R8 | SYS |
| EDIT-C4-005 | vcs/release.py:367-411 | A release needs a gauge and a length on every wire: no way to release with "gauge/length not required" (e.g. test harness, bonding strap) without inventing a value | R7 | ELEC AIT |
| EDIT-C4-006 | vcs/release.py:34-47 | Date must be typed; cannot be omitted; with roles on it must be inside a fixed window (-,+1 day) | R8 | SYS |
| EDIT-C4-007 | links.py:493-496, 498-518 | A link cannot be changed once its harness is released; a pin owned by an interface cannot be paired in a link; a device connector takes ONE plug and one interface (devices.py:1598, edit.py:426) | R7 | ELEC AIT |
| EDIT-C4-008 | devices.py:1573-1576 | "One interface per connector in the editor": a connector shared by two interfaces (e.g. redundant bus stub, power + signal in one D-sub) cannot be allocated by hand | R4 | ELEC |
| EDIT-C4-009 | connector_edit.py:56-63, 125-127, 194-196 | On a Generate-made harness the cable connector's name, pin IDs, pin count and contact cannot be edited; the only route is to change the device, or to give up and make a hand-made harness | R7 | ELEC AIT |
| EDIT-C4-010 | edit.py:960-963, 939-955 | Interface and unit edits allow a fixed field list (`allowed`); e.g. interface `type_id`, endpoints and a unit's subsystem/zone have to be changed elsewhere | R7 | SYS |
| EDIT-C4-011 | copies.py:346-351, 400-403 | Max 10 devices; copy count can only go up; fixed ID suffix scheme | R3 | SYS |
| EDIT-C4-012 | edit.py:136-154 | Template catalogue fixed in code; user templates not possible (no registry) | R13 | SYS |
| EDIT-C4-013 | devices.py:1747-1748 | Part approval can't be set by the tool at all (no approve action in these planners) | R7 R8 | ELEC AIT |
| EDIT-C4-014 | commands.py:29-41, 134-146 | Only 11 fixed collections can be put/deleted; a plugin item type is not possible | R13 | SYS |
| EDIT-C4-015 | snapshot.py:248-258 | The frozen config set is not selectable per project | R3 | ELEC |
| EDIT-C4-016 | wires.py:90-100 (context) | One `locked` flag for four attributes (gauge, type, colour, length); cannot lock only the length | R7 | ELEC AIT |

## C5. Inputs and outputs exchanged with other tools or files

| id | file:line | exchange | R | persona |
|---|---|---|---|---|
| EDIT-C5-001 | recovery.py:295-307 | Writes `<project>/.harness-recovery/session.json` (whole project) automatically; invisible to the user until a crash; deleted by `clear_journal` | R14 | SYS |
| EDIT-C5-002 | recovery.py:386-399 | Reads `session.json` and `base_fingerprint` on opening to offer restore | R14 | SYS |
| EDIT-C5-003 | mergefix.py:452-476 | Writes `.gitattributes` into a new project (`generated/generation.json merge=binary`) without a prompt; `merge-fix` rewrites `generated/generation.json` (take_our_side, 539-561) | R14 | SYS |
| EDIT-C5-004 | vcs/gitinfo.py:96-120, gitindex.py:28-47 | Reads `.git/HEAD`, refs, packed-refs, objects, packs, `.git/index` of the repository found by walking up to 12 parents; never runs git | R14 | SYS |
| EDIT-C5-005 | vcs/gitname.py:516-537 | Reads `$GIT_CONFIG_GLOBAL`, `$XDG_CONFIG_HOME/git/config`, `~/.gitconfig`, repo `config` to fill the signing name (only with roles on); environment dependence | R9 | SYS |
| EDIT-C5-006 | vcs/release.py:425-494 | Reads outputs folder and its manifest (`damaged_files`, `exported_harnesses`, `outputs_content_state`); refuses to release if folder is a symlink or read-only (428-440) | R9 R14 | AIT |
| EDIT-C5-007 | vcs/report.py:424-477 | Revision report markdown with `<!-- stamp_line -->`; stamp content not defined here | R9 | SYS |
| EDIT-C5-008 | devices.py:1245-1249 | `pinout_table` = rows of `system/box_pinouts.csv`; paste/import of pin rows via `ROW_COLUMNS` (884-886) and `rows_from_grid`; direction is not a paste column (1659) | R10 R14 | ELEC AIT |
| EDIT-C5-009 | links.py:610-668 | `plan_create_harness` creates harness, connectors and wires from a link; lengths, gauge, colour left pending | R6 | ELEC AIT |
| EDIT-C5-010 | edit.py:976-995 | Wire colours per signal written into `config/generation.json` (`wire_colour_by_signal`) | R3 | AIT |

## C6. Customisation points that DO exist (what the engineer can change)

| id | file:line | customisation | R | persona |
|---|---|---|---|---|
| EDIT-C6-001 | vcs/roles.py:183-192 | `release_distinct_roles` in naming.json switches on author/checker/releaser separation | R3 R8 | SYS |
| EDIT-C6-002 | vcs/release.py:225-318 | Release on placeholders or on unapproved parts with a written, logged reason (flagged in comment text) | R7 | ELEC |
| EDIT-C6-003 | vcs/lockview.py, locks.py | Lock reason sentences available per object/field (lock_reason, field_lock_reason) so the UI can disable fields with the reason | R12 | SYS |
| EDIT-C6-004 | vcs/timeline.py:269-283, report.py:420-421 | Compare any two revisions, or a revision and the working design; field-level before/after | R8 | SYS ELEC AIT |
| EDIT-C6-005 | vcs/timeline.py:249-266, report.py:381-410 | Change log table and timeline (id, harness, revision, kind, by, date, comment) | R8 | SYS |
| EDIT-C6-006 | devices.py:156-164, 643-659 | Per-pin: signal, contact size, termination (crimp/solder/unspecified), function, contact part, role, direction, mode free/fixed/locked | R7 | ELEC AIT |
| EDIT-C6-007 | devices.py:1566-1634 | Assign an interface to specific pins by hand (pins become locked); Generate never moves them (engine.py:441-525) | R7 | ELEC |
| EDIT-C6-008 | devices.py:1036-1083, 134-141 | Create parts/interface types by hand (unverified, pending) | R13 | ELEC AIT |
| EDIT-C6-009 | devices.py:393-426, 462-526 | Edit connector part/gender/keying with preview of pin changes (`plan_change_part`) | R1 | ELEC AIT |
| EDIT-C6-010 | connector_edit.py:95-191, 281-296 | Edit a cable connector (part, gender, keying, pin signal/role/function/termination/contact size) on a generated harness: marks `Connector.locked` and Generate keeps it (engine.py:786-799, note "override:" 612-615); Reset gives back | R7 | ELEC AIT |
| EDIT-C6-011 | connector_edit.py:199-278 | On a hand-made harness: add/rename/delete pins, wires follow rename | R7 | ELEC AIT |
| EDIT-C6-012 | wires.py:154-190, 193-199 (context) | Per-wire gauge, type, colour, length (lock); label, note (always kept); `manual` wires drawn by hand (kept, ends editable) | R7 | ELEC AIT |
| EDIT-C6-013 | build_data.py (context) | Per-wire strip length at both ends, contact part per pin, crimp tool per contact part, accessories per harness; kept on regeneration without locking the wire | R7 | AIT |
| EDIT-C6-014 | links.py:521-583, 586-597 | Hand-made links with pairs chosen by hand; role per pin ("" = derived) | R7 | ELEC |
| EDIT-C6-015 | counterparts.py:78-111 | `signal_counterparts` replaces the TX/RX pairing table (validated) | R3 | ELEC |
| EDIT-C6-016 | edit.py:983-995 | Wire colour per signal name via generation config | R3 | AIT |
| EDIT-C6-017 | copies.py:385-421 | Number of identical devices (redundant/copies) | R4 | SYS |
| EDIT-C6-018 | devices.py:163-164, 595-641, 884-1015 | Paste/import of pin tables with reasons per row (RowIssue) | R10 | ELEC AIT |
| EDIT-C6-019 | mergefix.py:540-582 | `merge-fix` command, read-only plan then apply | R14 | SYS |
| EDIT-C6-020 | edit.py (waivers): 594-600 | Waivers (mandatory justification, tied to finding hash) exist in model (review.py:35-48); deleted automatically with their object | R7 R12 | SYS ELEC |

## Change history (R8) and overrides (R7): answers to the special questions

**What is recorded.** Change log entries (ChangeEntry: id, harness, revision, kind, by, when, comment) only for three events: `review`, `release`, `new_revision` (model/review.py:94-106; release.py:100-111). Baseline per release: snapshot of harness + devices, interfaces, box connectors, used parts, types, frozen config, links, waivers (snapshot.py:361-388), `by`, date, comment, `content_hash`. Both are write-once (locks.py:80-94). `by` is typed text (or Git user.name with roles on); `when` is a typed date, no time. Reason is REQUIRED (>=10 chars) for release, new revision, accepting placeholders or unapproved parts; EMPTY for a review submission (release.py:589).

**Not recorded (no who/when/old/new/reason):** every design edit (pins, wires, connectors, links, parts, interface types, config values, waivers, approvals, placeholder flag), wire locking/reset, manual groups, deletions, undo/redo; edits to cosmetic fields after release; a Waiver has no author or date (review.py:35-48); Part.approval has no approver/date. Undo history is in memory only: label + ops, no person/time (commands.py:169-173), max 200 steps, lost on exit; the journal (recovery.py) is the latest state only. Git commits (gitinfo.py) are the only source of a "who/when", read-only, whole-repo, not tied to the engineering reason.

**Overrides an ELEC / AIT engineer can make and what happens at regeneration** (all must be on a non-released harness):

| override | stored as | flagged | kept at Generate | record of who/when/why |
|---|---|---|---|---|
| wire gauge, type, colour, length | `Wire.locked=true` (one flag for all four) wires.py:90 | note "override: ... kept" in generation notes (engine.py:709); output column "yes" (outputs/tables.py:127) | yes, all four, even those not edited; plan unchanged on new interface | none |
| wire label, note | `Wire.label/note` | not flagged | always kept (engine.py:710-) | none |
| strip length per end | `Wire.strip_a_mm/_b_mm` | not flagged as override (unverified in outputs) | kept, wire not locked (build_data.py:19-21) | none |
| contact part per pin | `Pin.contact_part`: on generated harness set on device pin and copied | not flagged | follows device | none |
| crimp tool | `Part.tool` | no | part data | none; blocked when release uses the part (locks.py) |
| cable connector part/gender/keying/pin details | `Connector.locked` | note "override" (engine.py:612-615); finding `locked_data_lost` if device connector vanishes (engine.py:894) | kept | none |
| hand-made harness, wires, groups | `Harness.generated=false`, `Wire.manual`, `ShieldGroup.manual` | marked in model; mating checks | kept as is | none |
| pin allocation on device | `Pin.locked` / `fixed` | pin mode shown (devices.py:1219) | never moved | none |
| accept placeholder / unapproved parts at release | text in release comment | in log + baseline | frozen | yes (who, date, reason; but the reason is a free sentence, not machine readable) |

Re-validation: after any edit `History.execute` re-runs the integrity check and cancels the edit only on NEW integrity errors (commands.py:209-217); design-rule consequences (derating, EMC, segregation) are not re-run per edit, they appear at next Generate / check. A locked wire is not re-checked against derating on its own gauge by this code (unverified: depends on DRC).

## Top findings

1. EDIT-C1-046 / C4-016 [ELEC][AIT]: editing a wire length (or colour) silently locks gauge and type too (single `Wire.locked`), so derating is never recomputed for that wire; not logged, no reason.
2. EDIT-C1-017 / C2-002 [ELEC][AIT]: baseline freezes only a subset of generation config; `service_loop_m` (added x2 to every length), `default_gauge_awg`, `wire_part_by_construction` are outside it, so a released cut length list cannot be reproduced from the recorded config.
3. Change history section / EDIT-C1-013, C2-022 [SYS]: only three event kinds are logged (review, release, new revision); no who/when/old/new/why for any design edit; undo history is in memory, label-only, 200 steps.
4. EDIT-C1-022 / C1-021 [SYS]: baseline `content_hash` is written but never re-checked; the hash covers everything but release bookkeeping; no config/tool version stored with it in this module.
5. EDIT-C1-009 / C1-010 [ELEC][AIT]: release gate ignores approval of contacts and accessories and ignores strip lengths, contact assignment and test limits; gate list is fixed in code.
6. EDIT-C4-001 / C4-002 [SYS][ELEC][AIT]: a released harness, its baseline and its change log are immutable; a typo can only be fixed in a new revision; no flagged, justified override.
7. EDIT-C2-007 / C1-038 / C2-008 [ELEC]: pin direction and role are inferred from signal NAMES and interface types, with silent narrowing and silent blanks; the pin table shows a note but no derivation trace; unknown (mis-typed) names count as plain "signal".
8. EDIT-C1-047 / C6-013 [AIT]: strip length, contacts, crimp tool and accessories are free entries, no default, no limit, no check, no override flag, no record of who entered them; yet they feed the build data.

Next: [the audit](../transparency_audit.md), [appendix E](interchange-and-cli.md), [appendix G](gui-work-screens.md)
