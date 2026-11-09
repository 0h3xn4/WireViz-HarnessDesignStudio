# Spike M4: the loose end as an ordinary connector (findings)

> **Status: historical, except section 8.** This is the report of the throw-away spike (branch
> `spike/m4-loose-end`, from `master` at `c531bc6c`, after M1). It is kept as the record of what was
> tried and found. The first production slice, **M4a** (core, release blocker, migration step), was
> built from it; the owner took the eight decisions of section 8 as the lead recommended (decision
> **D-201**, `docs/DECISIONS.md`): origin is derived and never stored, the wording of section 4,
> unplug resets the part, a real part resolves the end, the blocker is for release, a number
> mismatch is refused, a loose end is a DRC warning, and `SCHEMA_VERSION` moves in a separate final
> step. Where the text below says "SPIKE", "not done" or "the spike", read it as the state of the
> prototype; what M4a built and what is left for M4b (the words in the written outputs) and M4c (the
> editor) is in the changelog (`## Unreleased`) and in D-201.

Plan sections tested: 2.4 (Loose end, Bare end, Origin), 2.5, 3.2 (M4); decision D-200 (a), (e), (f).

## 1. Verdict: go, with changes to the plan

The design works. A loose end that is an ordinary `Connector` (role `loose`, part `TBD-CONNECTOR`,
no `mates_with`) was carried by every part of the tool I ran, with no crash in any command except one
that I caused myself (section 3, row 9). Nothing in the model, the hash, the file layout or the
independent verifier needs a new concept.

Five things in the plan are wrong or missing, and they change the work:

1. **`Harness.origin` as a stored field breaks the migration.** Writing `origin` into the files of
   hand-made harnesses changes the model hash and the content hash, and the M1 safety net refuses the
   upgrade (section 5). Deriving the origin, and storing only what cannot be derived, does not.
2. **"The 34 files that read `from_connector` / `to_connector` need no change" is true and useless.**
   17 of the 34 need nothing and 5 are GUI, but 9 need work, and the files that need it are the readers
   of `mates_with`, the connector `part_id` and the bill of materials, which that count does not find
   (section 6).
3. **Every written number or word for the end exists twice**, in the generator and in the independent
   verifier (`core/outputs/verify.py`). The verifier refused my first output change, as designed.
4. **The part `TBD-CONNECTOR` has four side effects** the plan does not list: it makes all generated
   plans "stale" when it is first added, it is covered by the existing "parts not approved" waiver, it
   appears in the part pickers, and the DRC tells the person to "approve" it.
5. **"A Link created by a drag can name a harness whose far end is loose" does not fit the model.** A
   `Link` joins two device connectors (`integrity._check_links` makes anything else `dangling_link`).
   A half-dragged cable is a harness, never a Link.

Size: the plan says L to XL, 10 to 14 agent-days. My estimate for the whole of M4 is 14 to 19, about
10 to 13 of them in core, outputs, release and migration, and 4 to 6 in the GUI (section 7).

## 2. What was built

Core only, 15 source files (about 520 added lines) and the regenerated `docs/CLI.md`, plus tests. Everything is marked `SPIKE M4`.

| Piece | Where |
| --- | --- |
| Role `loose`, `Origin`, `Harness.origin` (sparse), constants `LOOSE_ROLE`, `TBD_PART_ID` | `core/model/physical.py` |
| Plans: `plan_cable_from_port`, `plan_add_loose_end`, `propose_plug`, `plan_plug_loose_end`, `plan_unplug`, `plan_resolve_loose_end`; `tbd_part` added on first use | `core/manual_harness.py` |
| Pairing reused: `propose_pairs_between`, `pair_by_number_between` (the old functions now call them) | `core/links.py`, `core/pairing.py` |
| Integrity: `loose_end_mated`, `loose_end_in_generated_harness`, `origin_mismatch` | `core/integrity.py` |
| Release: `loose_end_unresolved`, `loose_end_reason_short`, the note, `--accept-loose-ends` | `core/vcs/release.py`, `cli/changes.py` |
| Marks: `pos:<connector id>` is an offset mark; orphan rule | `core/model/review.py`, `core/io/layout.py` |
| Wording in tables, labels, BOM; the ninth readiness check; both in the verifier | `core/outputs/tables.py`, `buildsheet.py`, `verify.py`, `core/derive_build.py` |
| DRC wording; generation status ignores `TBD-CONNECTOR` | `core/drc/rules.py`, `core/generation_status.py` |
| The project with loose ends, and 31 tests | `tests/loose_support.py`, `tests/test_spike_m4_loose_end.py` |

The test project is the packaged `flatsat` example plus five harnesses a person drew: a cable with a
loose end (A), a cable plugged into a port (B), a hand-made harness with two loose ends, a twisted
pair, a sleeve and a segment (C), a cable plugged and unplugged again (D), and a complete cable with
one loose end (E, the one the release gate must judge). All four non-empty packaged examples also
survive a loose-end cable plus a plug (no integrity error, no verifier error).

Behaviour of the plans, as run:

* **Cable from a port**: a new harness (origin `drawn`), a cable connector that plugs into the port,
  a loose end, and one wire per port pin that has a signal (else every pin). The loose pins carry the
  port pin's signal name, so that the plug can pair by name later.
* **Plug**: signal name first (TX to RX included, the logic of `links.propose_pairs`), else pin number,
  else nothing. The connector keeps its ID and becomes `cable` with `mates_with`, the mating part of the
  library, the opposite gender, the keying and all pins of the port. Wires follow their pins (the
  precedent is `plan_rename_pin`). One undo step.
* **Unplug**: `loose`, `mates_with` cleared, part back to `TBD-CONNECTOR`, gender and keying cleared;
  pins and wires stay.

## 3. Everything run over the project

| # | What | Result | Where and what it said | What it should say |
| --- | --- | --- | --- | --- |
| 1 | `validate`, `check` | Fine | Summary counts the ends in "205 connectors" (cosmetic) | "205 connectors, 5 of them open ends" |
| 2 | `generate` | Fine, does not touch the drawn harnesses (bytes equal). One side effect | First cable adds a library part; `generation_status.input_hash` dumps all parts, so the plans turn **stale** (`core/generation_status.py:41`) | Fixed in the spike: the TBD part is left out of the dump |
| 3 | DRC (39 rules) | No crash. One nonsense finding | `part-unapproved.TBD-CONNECTOR`: "not approved yet ... To fix it: approve the part in the parts list" (`core/drc/rules.py:235`) | "5 cable end(s) have no connector chosen yet (loose end)" (done) |
| 4 | Mass, BOM, pin counts | **Wrong number** in the BOM, wrong text in the mass | BOM counts `TBD-CONNECTOR` as "1 ea, pending (example data)" per end and sums them in the system BOM (`core/outputs/tables.py:317`, `verify.py:1148`); mass counts the end among "Connectors" and says "mass of connector part TBD-CONNECTOR" (`core/generate/mass.py:73`, `verify.py:1275`). Pin counts: fine (the part has no pin count, so `too_many_pins` cannot fire; spare pins right) | BOM line "(open end) ... to fill in", count of ends. Mass: "connector part of open end W009-P2" (BOM done, mass not) |
| 5 | `export --drawings` (CSV, XLSX, PDF, SVG, YAML, build workbook) | No crash; verifier 0 errors. Wording poor | `pinouts.csv`: role `loose`, Mates with empty (`tables.py:194`); `labels.csv`: "W009-P2 mates -" (`tables.py:536`, `verify.py:1257`); drawing: no mate line, "gender not set" (`drawing.py:101`, `:483`); build workbook: "not plugged into a unit" (`buildsheet.py:594`) | See section 4 (pinouts and labels done; drawing and build workbook not) |
| 6 | Build workbook, "Ready to build" | **Silently wrong** | A harness with every wire complete and one loose end says **"Ready to build: yes"** (`buildsheet.py:368`; the eight checks do not look at connectors) | A ninth check "Ends not decided", only while an end is loose, always blocking (done, both sides) |
| 7 | Test tables | Misleading | Continuity from `W009-P1.1` to `W009-P2.1`, "continuous, 1 ohm max" to a connector that does not exist | To: "W009-P2.1 (open end)" (not done) |
| 8 | As-built sheet | Nonsense rows | "TBD-CONNECTOR, lot of this part in the harness" and a connector row (`core/asbuilt.py:558`) | One row "open end W009-P2" (not done) |
| 9 | `explain` | **Crash**, caused by my ninth check | `KeyError: 'Ends not decided'` in `core/derive_build.py:148` (the CLI reports "input is not in a form the tool can read"). Without the new check: "Choice of connector: TBD-CONNECTOR mates with None", "[connector None]" (`core/derive_layout.py:540`); `explain TBD-CONNECTOR`: "BOM quantity 4 ea" | Table entry added. Text: "Open end: no device connector and no part chosen yet" (not done) |
| 10 | `core/verify.py`, `outputs/verify.py` | Fine (0 errors on the project and on the four examples) | The verifier fails an output the generator changed alone: "Start here shows the wrong Ready to build answer" | Both are written by hand twice |
| 11 | Release gate | **Silently passes today** | Existing `--accept-unapproved-parts` lists and covers `TBD-CONNECTOR` ("Released with parts that are not approved (..., TBD-CONNECTOR)"); the harness releases | `loose_end_unresolved` (done); the part is no longer listed as unapproved |
| 12 | `diff`, `compare` | Works, words off | "Cable connector `W009-P2`"; a plug against a baseline reports 61 added objects, most of them the pins of the port (its connector comes into the snapshot) | "Loose end W009-P2"; noise is existing behaviour |
| 13 | Importers | Fine | `import-build-data` (strip, accessory on the end), `import-lengths` (segment of the harness), `export-asbuilt` / `import-asbuilt`, `export-data`: no crash. `export-pinout`, `-devices`, `-subsystem` read device connectors and links only | |
| 14 | GUI (offscreen, no canvas work) | Opens, no exception | Project opens, harness tab of a loose-end harness builds (`gui/harness_view.py:188` falls back to the pin's own signal) | |
| 15 | 1.x reading a loose end | Harness set aside | An unknown role: "A harness could not be loaded and was set aside: connectors.1.role: Input should be ..." (error, the whole harness) | Read-only refusal comes from format 2 |

Existing tests: 1,362 passed, 1 failed and 1 skipped in the core subset I chose (integrity and tracker, DRC, manual
harness, schemas, io, migration, output hashes and goldens, outputs, build workbook, derivations,
change control, release, links, pairing, docs, API, CLI, extensions, numbers) and 228 more in GUI,
docs and release-dialog tests. The one failure was `docs/CLI.md` (the new flag), regenerated on the
branch. `ruff` and `mypy` are clean.

**The "no change needed" claim, measured.** With every loose end replaced by a real part, the written
outputs of the four loose-end harnesses differ in six kinds of file only (`bom.csv`, `labels.csv`,
`mass_length.csv`, `pinouts.csv`, `wireviz.yaml`, the drawing SVG) and in six system files that sum
them (BOM, mass, DRC report and findings, `export.json`, provenance). The wire list, tests, build
workbook values, lengths, shield groups and the segment lengths are identical. That test is in the
file (`test_the_loose_end_changes_only_the_outputs_that_say_something_about_it`).

## 4. Decisions to take (the spike's answers)

**Wording** (the build workbook already says "to fill in" for a missing wire value; I reused it).

| Output | Text |
| --- | --- |
| Part column of pinouts, tables, drawing, build workbook | `TBD-CONNECTOR (loose end)` |
| "Mates with" | `open end` |
| Connector label | `W009-P2 open end` (not "mates -") |
| BOM | no `TBD-CONNECTOR` line; one line `(open end)`, description "Connector not chosen yet (loose end)", approval "to fill in", quantity = number of ends, like the existing `(no part)` line for wires |
| Build workbook | Connectors sheet: "open end, to fill in"; Start here: the ninth check "Ends not decided" |
| Mass, missing data | "connector part of open end W009-P2" |
| Tests | "To: W009-P2.1 (open end)", expected value left as it is |
| DRC | "N cable end(s) have no connector chosen yet (loose end)" under the existing rule `part-unapproved` (no new rule, so RULES.md and the rule count are unchanged) |
| `explain` | "Open end: no device connector and no part chosen yet" |
| Summaries | "N connectors, M of them open ends" |

**Screen position.** `diagram/marks.json`, id `pos:<connector id>`, with `dx`, `dy`: the offset of the
end from where the tool puts it (out of the near port, like `bend:` and `route:`), so the end follows
its device. No new model class: `DiagramMark` already holds offsets and `Controller.move_mark` already
makes one undoable step. Two lines were needed: `OFFSET_MARK_KINDS` (a position `t` is refused for it)
and `mark_is_orphan` (without it a deleted end's mark stays in the file for ever, because unknown
kinds are never orphans). Tested: moving it changes neither `model_hash` nor `content_hash`; the mark
survives save and load; a deleted connector's mark is dropped.

**What `integrity.py` must say.** Nothing about a valid loose end: a warning or info would reach the
DRC (`_model_inconsistent` turns every non-error issue into a warning) and the open end is a normal
working state. Three errors: `loose_end_mated` (role `loose` with `mates_with`),
`loose_end_in_generated_harness` (Generate would replace it), `origin_mismatch` (generated, but
origin not `interfaces`). No change to `IntegrityTracker`: the checks read the connector and the
`generated` flag of its harness, which `_Reads.connector` already tracks. The existing warning
`link_harness_not_mated` fires when the far end of a harness made from a connection is unplugged and
says "Make the harness again from the link, or delete the link": it needs its own wording, or the
unplug must be refused for such a harness (as `plan_move_link_end` does).

**The release blocker.** `loose_end_blockers` in `core/vcs/release.py`, beside `part_blockers` and
`asbuilt_blockers`, with its own waiver `--accept-loose-ends REASON` (at least 10 characters, written
into the change log comment like the others) and `loose_end_reason_short`. It must be its own
flag: the parts waiver already covers `TBD-CONNECTOR` in practice (row 11). `unapproved_parts` now
leaves the TBD part out. "Resolved" means the role is no longer `loose` (plugged, or given a part by
`plan_resolve_loose_end`). Call sites to extend: `cli/changes.py` (3), `gui/main_window.py` (2),
`gui/dialogs.py` (release dialog), and the 15 documents that name the accept flags (`docs/CLI.md` is
generated). Existing tests need no change: the new flag is optional.

**Hash and baselines.**

* The loose end is in the model hash (it is a connector in the harness file): creating, plugging or
  unplugging one makes the outputs stale, as D-200 (a) wants. Its position is not (`diagram/` is outside
  the hash).
* Frozen baselines: the hash goldens of the migration net (made on master) still hold for
  `mini3`, the flatsat example and the `released` scenario. A harness released with a loose end reloads
  with `baseline.content_hash == content_hash(project)`; its snapshot freezes the connector with role
  `loose` and the `TBD-CONNECTOR` part. Nothing in a format 1 project can change, because a loose end is
  new content and `origin` is the only new field (section 5).
* `generation_status.input_hash` dumps every part, so the first cable made the generated plans stale
  (row 2). Fixed by leaving the TBD part out; a project without it hashes as before.

## 5. The migration, and the origin

The M1 net was run with a test-only v1 to v2 step on a v1 project with a harness made from a connection
and one made by hand (`origin` written as the plan describes: `link` if a connection names it, else
`drawn`):

| Variant | Model hash | Net |
| --- | --- | --- |
| `origin` stored in the harness file (plan 2.4) | **Changes** (and every stamp, the content hash, `W001.xlsx`, the drawings) | **Refuses**: "the upgrade changes the design" |
| Same, but the hash leaves `origin` out | Equal | **Still refuses**: `system/export.json` dumps every field of a harness, so the export differs |
| `origin` derived: `interfaces` if generated, else `link` if a connection names the harness, else `drawn`; the step only writes the number | Equal | Passes, the step rewrites only `project.json` |

The plan's sentence "`content_hash` ignores `origin` so frozen baselines still match" is not enough:
the safety net is built on the model hash and on a byte-for-byte export, not on `content_hash`. The
spike recommends the third variant: `effective_origin(project, harness)` as a function, the stored field
written only for a value the first two rules cannot give (a harness that Generate made and a person then
took over, or a link whose connection was deleted). Then 2.0 writes no `origin` at all, and the step is
empty for it. The test file holds all three variants.

Consequence for the plan: **the real v1 to v2 step of M4 is empty** (a loose end exists only in
format 2, origin is derived). Its value is the number: 1.x opens a format 2 project read-only (row 15
shows what 1.x would do without it: set the whole harness aside). If M7a (journal layout) is not in 2.0.0
the version bump has no file to rewrite. This is for the owner to weigh against the alternative in 2.5
(stay on format 1 with sparse fields), which this spike makes cheaper than the plan said.

Also tested: a project with loose ends upgrades through the net with the number-only step (hash equal,
export equal, baselines intact); a mark is outside the hash; the property test (any sequence of cable,
plug, unplug, resolve, undo on a labelled project keeps `check_integrity` clean, saves, reloads to the
same hash and equal harnesses, and `verify_project` reports no error).

## 6. The 34 files, really

The census by `from_connector` / `to_connector` finds the files that follow a wire. A loose end does not
change a wire. What changes meaning is `Connector.mates_with` (25 files in core, 4 in the GUI), the
connector `part_id` (27 in core) and the BOM.

| Of the 34 | Count | Which |
| --- | --- | --- |
| Changed in the spike | 5 | `outputs/tables.py`, `outputs/verify.py`, `outputs/buildsheet.py`, `derive_build.py`, `drc/rules.py` |
| Will need a change (found, not done) | 4 | `outputs/drawing.py`, `generate/mass.py`, `asbuilt.py`, `derive_layout.py` |
| The feature itself | 3 | `integrity.py`, `manual_harness.py`, `model/physical.py` |
| Untouched and fine | 17 | `wires.py`, `verify.py`, `generate/engine.py`, `lengths.py`, `bundle.py`, `shields.py`, `exports.py`, `snapshot.py`, `open_data.py`, `edit.py`, `devices.py`, `deviations.py`, `derive.py`, `derive_rules.py`, `samples.py`, `connector_edit.py`, `generate/explain.py` |
| GUI, not exercised | 5 | `wire_editor.py`, `harness_view.py` (opens fine), `canvas.py`, `main_window.py`, `harness_edit_dialogs.py` |

So 9 of the 34 (all in outputs and derivations) plus the readers of `mates_with` and `part_id` that the count never named
(`vcs/lockview.py`, `vcs/locks.py`, `why.py`, `outputs/system.py`, GUI pickers). The claim that the
design needs no change in the readers of wires holds; the claim that the outputs need no change does
not.

## 7. The real M4: task list

Sizes in agent-days; the spike has done the first pass of items 2 to 5 and the answer to every
"how" below.

| # | Task | Files | Size | Hazard |
| --- | --- | --- | --- | --- |
| 1 | Decide origin (derive, section 5); model `Role`, schema, docs, extension field text | `model/physical.py`, `extensions/fields.py:172`, `docs/FILE_FORMAT.md`, API snapshot | 0.5 to 1 | The three variants above |
| 2 | Core plans, pairing generalised (`parse_pairing` too), delete or edit of a loose end, TBD part kept alive | `manual_harness.py`, `links.py`, `pairing.py`, `connector_edit.py` | 2 to 3 | Part lost by a library import or edit; pickers list it; `plan_edit_connector` can give a loose end a real part and leave it `loose` |
| 3 | Integrity, DRC wording, `link_harness_not_mated` wording, summaries | `integrity.py`, `drc/rules.py`, `cli/main.py` | 1 | The DRC makes every non-error issue a warning |
| 4 | Outputs: tables, labels, BOM, mass, tests, as-built, drawing, build workbook, `explain`, **each also in the verifier**; new golden project; keep example goldens unchanged | `outputs/*.py`, `generate/mass.py`, `asbuilt.py`, `derive_*.py` | 3 to 4 | Two implementations; eight places that print a part |
| 5 | Release: blocker, flag, dialog, docs, tests; ninth readiness check | `vcs/release.py`, `cli/changes.py`, `gui/main_window.py`, `gui/dialogs.py` | 1 to 1.5 | A waiver that covers more than it names |
| 6 | Migration: number-only step (or journal, M7a), fixture `loose`, goldens, hash neutrality, generation status | `io/migrate.py`, `generation_status.py`, `tests/migration_support.py` | 1 to 2 | Hash and export identity |
| 7 | Marks and GUI: draft to plan, drag, project tree, inspector "Origin", pickers hide the TBD part, wire editor | `gui/cable.py`, `canvas_cable.py`, `controller.py`, `canvas.py`, pickers (6) | 4 to 6 | Not touched by the spike; the largest unknown |
| 8 | Documents, strings, journeys, goldens review | `docs`, `gui/strings.py`, `tests` | 1 | |

Order: 1, 2, then 3 and 6 in parallel, then 4, then 5, then 7 and 8; release candidates after 5.
Totals: 10 to 13 for items 1 to 6 and 8, 4 to 6 for item 7.

Hazards in one list: (a) the verifier is a second implementation of every output, so each wording
is two edits and one golden; (b) the TBD part is a project part that a library import or a person can
remove, rename or select for a real connector (six GUI pickers list every connector part); (c) the
unplug is lossy (part, gender and keying reset), so an unplug followed by a plug on another port
chooses the part again; (d) plugging by number can put `1PPS+` on a port pin named `PWR` without a word
(the spike's `propose_plug` adds a note, but no finding reports it afterwards: the link rules only
judge links); (e) a drawn cable on a port Generate also wants shares its pins, and
`box_connector_mated_twice` is only a warning (read in `generate/engine.py:253`, not run: a drawn wire
has no `interface_id`, so Generate does not count its pins as taken); (f) plugging fails when an unpaired pin's number is
taken on the port (refused, not renumbered); (g) `Link` cannot hold a half-connection (section 1.5).

## 8. What the owner had to decide, and what was decided (D-201)

The owner said "continue as per your recommendations"; the lead's recommendation is in brackets.

1. Origin: **derived, no stored value in 2.0** (the recommendation). It is worked out from `generated`
   and `Link.harness_id` (`core/origin.py`); the v1 to v2 step is empty.
2. The wording of section 4, in particular the BOM line `(open end)` and "open end": **as in section 4**
   (built in M4b, not in M4a).
3. Unplug: **reset the part to `TBD-CONNECTOR`**. The unplug of a harness made from a connection:
   **refused** with a plain reason.
4. Giving a loose end a connector part **resolves it** (role becomes `cable`); plugging it does too.
5. A loose end blocks the **release** (blocker `loose_end_unresolved`, waivable with a recorded reason,
   `--accept-loose-ends`), **not** "submit for review".
6. A pin of the loose end that meets a port pin of another name only by number: **refused** with the
   pins named (never silently mismatched); the number-taken case is refused as in the spike.
7. A loose end is a DRC **warning**, under the existing rule `part-unapproved`.
8. The format number: **a separate final step** controlled by the lead; M4a wires the empty step and
   keeps `SCHEMA_VERSION` at 1.

## 9. Not done

GUI and canvas; `drawing.py`, the as-built sheet, the mass text, the test table and `explain` wording;
Link behaviour with a loose end; the part pickers; a real v1 to v2 step; documents (other than
`docs/CLI.md`); a performance check at 200 devices (loose ends add connectors and pins like any cable,
and the plans are O(wires) per step, but nothing was timed).
