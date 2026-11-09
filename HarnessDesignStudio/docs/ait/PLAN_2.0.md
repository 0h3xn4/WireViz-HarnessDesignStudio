# Plan for the next programme of Harness Design Studio (towards 2.0.0)

Written 2026-11-05 for the owner. Based on a read-only reading of `origin/master` at commit `d01a276e`
(merge of PR #186) and of the docs and code named below. Nothing was built, run or pushed.
Three themes are in scope: (1) a cable-first, free-form harness workflow, (4) team and process
features, (5) a rebuilt user experience. Themes 2 and 3 are not planned here; where they touch this
plan it is said in one line (section 3.4).

> **Status on 2026-11-09 (added later; the text below is as written on 2026-11-05).** M0 is done: it is release 1.16.0. M1 (the migration safety net) and M2 (the real-platform test lane and the click budget) are done and published in 1.17.0 (decision D-202). M4a, the first slice of M4 (loose cable ends and a derived origin in the core, no screen; decision D-201, spike [`SPIKE_M4_LOOSE_END.md`](SPIKE_M4_LOOSE_END.md)), is merged on `master` after 1.17.0 and is not released. Format 2 is not written: `SCHEMA_VERSION` is still 1. No other milestone has a commit on `master`.

How to read it. "Format" means the project folder format (`schema_version`, now 1). "Hash" means the
model hash printed on every written file. "Golden" means a stored expected output that a test compares
byte by byte. "Sparse field" means an optional field that is left out of the file while it is empty
(the pattern of `Unit.kind`, `Wire.overrides`, `Part.conductors`): a project that does not use it is
written byte for byte as before. "Agent-day" is one agent working a full day, including waiting for CI;
sizes are honest ranges, not promises.

What I read: `docs/ARCHITECTURE.md`, `docs/FILE_FORMAT.md`, `docs/DECISIONS.md` (D-186, D-190 to D-198),
`docs/STATUS.md`, `docs/OPEN_DECISIONS.md`, `docs/transparency_final_audit.md`, `CHANGELOG.md`
(Unreleased, 1.12 to 1.15), `docs/RELEASE.md`, `.github/workflows/release.yml`, `tools/build_windows.py`;
and in `src/harness_design_studio/`: `core/model/{physical,logical,library,base,journal}.py`,
`core/io/{migrate,loader,saver,layout}.py`, `core/links.py`, `core/mergefix.py`, `core/journal.py`,
`core/part_approval.py`, `core/library_import.py`, `core/vcs/{hashing,roles}.py`, `core/integrity.py`,
`core/verify.py`, `core/generate/{engine,mass}.py`, `gui/{cable,canvas_cable,roles}.py`, `cli/main.py`.
What I did not read in full: `gui/canvas.py` (3,962 lines), `gui/main_window.py` (5,208 lines), the
drawing and workbook writers, and the test suite beyond the files named. Where a statement depends on
that, it says so.

---

## 1. What the owner gets, and what 2.0 honestly means

### Your three decisions, as the design rule of this plan

You answered three questions. They fix the shape of the plan:

1. **The format may change, with an automatic upgrade (migration).** So `schema_version` 2 is allowed.
   A project in format 1 opens in the new tool and is upgraded safely. An older tool does not get to
   edit a format 2 project.
2. **A loose cable end is a saved object.** It lives in the project and in the model hash, like a
   device or a wire. It is not a drawing trick of the window, as it is in 1.15.
3. **"Whatever came first" is the source of truth.** Every harness records its **origin**: was it made
   from interfaces, from a pin-to-pin connection, or drawn first? Whatever was entered first is
   that harness's truth. The other side is derived from it or checked against it, and the tool
   reports any disagreement as a finding. It never silently overwrites either side.

### Theme 1: cable-first, free-form harness

You will be able to pick up a cable at a port, carry it, put the loose end down on empty ground, and
save the project like that. The cable is still there when you reopen it. Later you pick up the loose
end and plug it into a port of another device; the tool pairs the pins for you to confirm. You can also
start from the harness: draw it, plug it where you like, and let the tool *derive* the interfaces and
checks from what you drew, instead of making you describe devices and interfaces first. Splices,
branches, breakouts and backshells become real things you place, see in the drawing and find in the
build workbook, instead of notes in a text field. Today (1.15) the loose end disappears when you save,
and a splice exists in the file format but nothing can create or show it.

### Theme 4: team and process

Several people can work on one project in Git without the change journal fighting itself, and the tool
repairs what is left. People can sign off a harness in the tool, with a rule you choose for how strict
it is. The Windows installer and the release carry a signature and a build record, so the Windows
warning goes away (subject to a certificate decision of yours). The parts list gets an approval status
with who, when and why, and a way to exchange data with a parts system such as InvenTree without
breaking the rule that the tool never uses the network.

### Theme 5: a rebuilt user experience

Windows and dialogs are tested on the same machine types you use, not only on Qt's invisible "offscreen"
screen. A systems engineer has a short, guided path with a fixed budget of clicks to a block diagram; an
electrical or AIT engineer has the quick, strict, everything-visible path. Devices and diagrams start
from templates. The things you said repeatedly stay promises that tests guard: devices move freely,
labels and symbols stay on their line, devices can be told apart.

### What "2.0" honestly means

- **It is a break for tools, not for projects.** A 1.x project opens in 2.0 and is upgraded
  automatically. The upgrade keeps a backup of every original file, writes a record of what it did,
  and is built so that the model hash, every number and every written file are the same before and
  after (section 2.3). The new tool's outputs for a migrated project are byte-identical to what it
  writes for the same project unmigrated; against the *old tool's* files only the version stamp
  differs, as at every release.
- **A project saved by 2.0 can no longer be edited by 1.x.** 1.15 opens such a project read-only with
  the warning "saved by a newer version of the tool" (`core/io/loader.py` lines 395 to 397; test
  `tests/test_recovery.py::test_newer_schema_is_read_only`). Honest wording: it *does not refuse to
  open*, it opens read-only, quarantines what it cannot read, and the command line `export` and
  `migrate` refuse it (`cli/main.py` line 487). That is acceptable because (D-186) the tool is used
  internally and everybody can upgrade at once.
- **The number 2.0.0 is justified at one point**: the first release that *writes* format 2. That is
  milestone M4 below. Everything before it is 1.x and keeps writing format 1.

---

## 2. The file-format question

### 2.1 What exists today (this matters more than the list of wishes)

I looked at what the model already has, because it decides what is new and what is only unfinished:

| Thing | State in 1.15 (file, code) |
| --- | --- |
| Loose end | **Not saved.** `gui/cable.py` and `gui/canvas_cable.py`: "a loose end is a draft of the window only and is never saved, hashed or written". A saved cable connector *can* already have `mates_with = null` (an unmated cable end made by hand, `core/manual_harness.py`), but a wire needs a connector at both ends (`Wire.from_connector`, `to_connector` are required) and a connector needs a part (`Connector.part_id` is required). |
| Splice | `class Splice(id, name, wire_ids)` and `Harness.splices` exist in `core/model/physical.py`, are diffed and locked (`vcs/diff.py`, `vcs/lockview.py`) and listed in the export. **Nothing creates one, no editor, no generation, no drawing, no BOM line, no mass.** `Assumption A-MASS-SCOPE` says splices are not counted. So existing projects have empty `splices` lists. |
| Branch point | `BranchPoint` and `Segment` exist and **are made by Generate** (`core/generate/engine.py` lines 647 to 690: "Branch X/Y" when several connectors share a side). They feed lengths (`generate/lengths.py`, `path_trail`) and the routing sketch in the drawing. A person cannot create or move one. OPEN_DECISIONS D-10 option C already says per-zone trunks "need the branch and segment model fully used (breakouts, in-line connectors, trunk lengths)". |
| Backshell | **Exists as an accessory**: `Accessory(kind="backshell", part_id, target=connector)` (1.7.0), counted by the opt-in mass model `full_bom` and in the build workbook. A shield end `backshell_360` is a field of `ShieldGroup` but nothing checks that a backshell is there. |
| Breakout | Not an object. Connector role `inline` exists (`Role = box, cable, inline, feedthrough, test`). |
| Hand-made harness | Exists since 1.5.0: `Harness.generated = false`; Generate leaves it alone, treats it as owning its pins (`generate/engine.py` lines 253 to 262: "manual harnesses own their pins") and warns when two harnesses plug into one box connector (`box_connector_shared`, line 372 ff). Checks, outputs, review and release already work for it (`core/verify.py` treats only `h.generated` harnesses specially). |
| Pin-to-pin connection | `Link` (1.8.0): two box connectors and pin pairs, `harness_id` when a harness was made from it (`plan_create_harness` in `core/links.py`). Interfaces are *derived for display* from a link (`derived_interfaces`), never stored. Four design rules review links; `link_wire_mismatch` already compares a harness's wires with the pairs of its link. |
| Positions | Device placements are in `logical/layout.json`, which **is in the model hash**. Label, bend and route positions are in `diagram/marks.json`, which is **outside** the hash. |
| Journal | One file `journal.json`, a list with a hash chain (`seq`, `chain`). `kind` is a closed list; a kind the reader does not know makes the whole journal "damaged". Two Git branches that both add entries conflict; `merge-fix` only knows `generated/generation.json` (`core/mergefix.py`). |
| Approvals | A part has `approval` (approved, pending, not_approved) and `unverified`; **no who, when or source** on the part (the journal has an `approval` entry with who and when). A harness has `author`, `checker`, `approver`, `released_on` as typed names; the setting `release_distinct_roles` forces three different names (`vcs/roles.py`). Nothing authenticates a name. |
| Parts import | `core/library_import.py` reads an InvenTree export *file*. No server connection, by design: a test enforces that nothing opens a network connection. |
| Roles / Quick mode | `gui/roles.py`: systems, electrical, ait. Quick mode is `ui/quick`. **Both are per-user settings in `HarnessDesigner.ini`, not in the project.** No file-format question here at all. |
| Migration machinery | `core/io/migrate.py` (one step v0 to v1, a fixture `tests/fixtures/v0_project`), in-memory upgrade on open, backup folder `.migration-backup-v<N>/` on first save, command `migrate`. **Missing**: a dry run, a migration record, an automatic before/after comparison, and the hash rule (next paragraph). |

### 2.2 A hazard that decides how the migration must be built

`model_hash` is computed from all project files with only `tool_version` blanked
(`core/io/layout.py` `model_hash`, `serialize(project, tool_version="")`). `project.json` contains
`schema_version`. So **bumping `schema_version` alone would change the hash of every project**, change
the 12-character hash printed on every written file, make every output look stale, and (through
`content_hash` in `core/vcs/hashing.py`, which is built on `model_hash`) possibly make every released
harness disagree with the `content_hash` stored in its frozen baseline. Baselines are "written once,
never edited by the tool" and must keep loading and comparing for ever.

Rule for the migration: **the hash must not depend on `schema_version`**. Concretely the hash function
reads `project.json` with `schema_version` normalised to 1 (as it already blanks `tool_version`).
Every existing hash stays what it is, a migrated project has the same hash as before, and only
genuinely new content (a loose end, an origin other than "interfaces") changes it. This is the first
thing to build (M1) and to test on a project with released harnesses, baselines, a change log, a
journal, overrides, links and as-built records. I have not run it; it is a design requirement.

Second hazard: baseline files hold frozen copies of harness objects in the format-1 shape. Any change to
the shape of `Harness` or `Wire` must leave the frozen shape readable and comparable. This is a strong
reason to **keep `Harness.generated` as it is** and to add `origin` beside it, not instead of it (2.4).

### 2.3 How a migration is made safe (v1 to v2)

All of this is built in M1, before any format 2 feature, and tested with a fake "v1 to v2" step so
that nothing real is at stake:

1. **Backup first.** Every original file is copied to `.migration-backup-v1/` (built under a temporary
   name and renamed when complete; this already exists in `core/io/saver.py`).
2. **Dry run.** `harness-design-studio migrate DIR --dry-run` loads, migrates in memory, writes
   nothing, and prints: files that would change, objects by kind before and after, the hash before and
   after (must be equal), and any object it could not carry over. Exit 0 only if nothing is lost.
3. **Migration record.** `migrate` writes `.migration-backup-v1/MIGRATION.json`: from and to version,
   tool version, SHA-256 of every file before and after, model hash before and after, counts by kind.
   It is outside the project hash and outside every output.
4. **Self-check after the write.** The tool reloads the migrated folder and compares: same model hash;
   `validate` and `check` give the same findings; baselines still match; and a full in-memory export of
   the old and the migrated project is byte-identical (same tool version on both sides, so even the
   stamp is equal). Any difference: the migration is rolled back from the backup and says so.
5. **No silent upgrade.** The editor asks once ("This project is in format 1. Upgrade to format 2? A
   copy of the original stays in `.migration-backup-v1`. Version 1.x tools can no longer edit it.") with
   *Upgrade*, *Open read-only* and *Cancel*. Today the editor migrates in memory on open and backs up
   at the first save without asking (`core/io/saver.py` lines 102 to 103).
6. **Nothing is generated by a migration.** No Generate, no new IDs, no journal entry rewritten. The
   journal gets one entry "migrated from format 1" (a new kind, so the reader must accept it: 2.6).
7. **Fixtures.** The four packaged examples, `mini3`, `sat15`, `sat15_full`, `custom_device`, the
   `m1_project` and `v0_project` fixtures, plus new ones: a project with released harnesses and
   baselines, with a journal and overrides, with links and a harness made from a link, with as-built
   records, with quarantined data, and a read-only one. The existing `tests/test_migrate.py` pattern
   ("every old version has a migration and a fixture") is extended.

### 2.4 Format 2: what goes into it, concept by concept

Principle: **define format 2 once, in the 2.0.0 release candidates, and add to it only sparsely
afterwards.** Until 2.0.0 is tagged nobody has a format 2 file, so format 2 can still change for free
(the repo has used `rc` tags before). After the tag, every later change must be an optional sparse
field, or it costs a format 3 with its own migration.

Column "bump?" says whether the concept *forces* format 2. "Old tool" is what 1.15 does with a
format 2 project in every case: opens it **read-only**, warns "newer version", quarantines objects it
cannot parse, and the command line refuses to export or migrate it.

| Concept | Where it lives | Bump? | What an older tool does (apart from the general rule above) | Migration |
| --- | --- | --- | --- | --- |
| **Loose end** (a saved, first-class, hashed end of a cable) | A **connector** of the harness with a new role `loose` (the `Role` list already has `inline`, `feedthrough`, `test`), its own ID, pins that wires attach to, `mates_with` empty. The part is the library part `TBD-CONNECTOR` (category connector, `approval` pending, `unverified`) the tool adds on first use, so `Connector.part_id` stays required and no consumer meets a missing part. Its **screen position is not in the hash** (it goes to `diagram/marks.json` as `pos:<connector id>`; moving it does not make outputs stale; same rule as labels). | Not forced (a new value of an existing list). Included in the v2 bump because a clean read-only refusal is safer than a 1.x tool quarantining a harness piece by piece. | Quarantines the harness that has one (unknown role value). | None (no format 1 project has a loose end). |
| **Bare end** (a wire end with no connector yet) | Same mechanism: a loose end connector whose part is `TBD-CONNECTOR`; "bare" is a note on the end, not a new structure. | No | as above | None |
| **Origin** | Sparse field `Harness.origin`: `interfaces`, `link` or `drawn`. Left out while it is `interfaces` and `generated` is true. `generated` stays in the file; a validator keeps the two consistent. | Not forced. Included in the bump. | Quarantines harnesses that have it. | A harness with `generated: false` gets `link` if a `Link.harness_id` names it, else `drawn`. Rewrites only those harness files. `content_hash` ignores `origin` (it joins status, author, checker, approver, released_on as release bookkeeping, `core/vcs/hashing.py`) so frozen baselines still match. |
| **Free-form harness** | An ordinary `Harness` with `origin: drawn`. `Harness.interfaces` becomes the **claim list**: interfaces the person says this harness carries (it is empty for drawn harnesses today, and `core/verify.py` only requires it to equal the wires' interface IDs for generated harnesses). | No | Opens it (it is a valid format 1 harness), minus the `origin` field. | None beyond Origin |
| **Splice** | A connector of the harness with role `splice` whose pins are **bonded** (new sparse `Connector.bonded: true`: all its pins are one net). Wires run device pin to splice pin and splice pin to device pin. Replaces the unused `Splice(wire_ids)` stub (decision: keep the stub readable, deprecated, never written). | Not forced | Quarantines the harness. | `splices` is empty everywhere (nothing creates it); a non-empty one is kept as is and reported. |
| **Branch / breakout** | Existing `BranchPoint` and `Segment`; new sparse `BranchPoint.kind` (`branch`, `breakout`); a person can now create and move them. A breakout carries an optional accessory (boot or transition: new `Accessory.kind` values, a list extension). | No | Quarantines harnesses that use the new values. | None |
| **Backshell** | Existing `Accessory(kind=backshell)`; new optional link to the connector's mating backshell part (`Part.mates_with` already exists for connectors) and a **rule** that a `backshell_360` shield end has one. | No | none for the field; the rule is new code | None |
| **Journal layout** (for merging) | `journal.jsonl`: one entry per line, no pretty-printing. Reader accepts **unknown `kind` values** (shown as "other") so later kinds (sign-off, merge) need no new format. See M7. | **Yes**: a layout change; an old tool that does not know the file would "see no journal" and could save without journaling. A read-only refusal is the only safe behaviour. | Read-only (whole project). | `journal.json` to `journal.jsonl`, chain values kept unchanged for existing entries; one `migrated` entry appended. |
| **Sign-off** | New folder `signoffs/<harness>/<revision>/<person>.json`, **one file per person** so that two people never touch the same file; outside the model hash (like `baselines/`, and like the journal it holds names and times, which design files must not, D-191). | Not forced (new optional folder). | Ignores the folder; does not enforce it. Hence v2 only (read-only for old tools). | None |
| **Part approval status with source** | Sparse fields on `Part`: `source_ref` (the id in the parts system), `source_rev`, `approved_by`, `approved_on`, `approval_note`. `Part` is a `SparseEntity`. | No | Sets aside any part that has them; wires naming it then fail `unknown_part`: a loud refusal. | None |
| **Role and layout settings** | Per-user settings file (`HarnessDesigner.ini`); a **project template** for Quick/guided starts is a normal example project | No | not applicable | None |

### 2.5 Recommendation

**Go to `schema_version` 2, once, with the first release that writes a format 2 construct (M4, tagged
2.0.0).** Make it hash-neutral and prove that with the checks of 2.3. Put *all* of these in that one
version: loose-end role, `origin`, the `journal.jsonl` layout with tolerant `kind`, and the empty
folder rules for `signoffs/`. After 2.0.0, add only sparse fields.

Alternative, which I rate second: **stay on format 1 with sparse fields for everything** (loose end as
an unmated connector, `origin` as a sparse field, journal merge by teaching `merge-fix` about
`journal.json`). It is possible: only the journal layout is a real reason for a bump, and even that can
be avoided by a `merge-fix` that parses the conflict markers. Advantages: no break at all, 1.x tools
keep opening everything. Disadvantages: a 1.15 tool opening a project with loose ends or splices would
quarantine harnesses one by one and show a half-picture instead of one clear read-only warning; the
journal stays hard to merge. You decided for the migration, and I agree with it for those two reasons,
but the alternative is cheaper if the team never mixes tool versions.

What I would not do: replace `Harness.generated` by `origin` (breaks the frozen baselines' shape) or
bump the version for each feature.

---

## 3. Milestones

### 3.0 Rhythm used, and how to read the lists

A release in this repo is: a **CHANGELOG** section; a page `docs/releases/X.md`; a **prep PR**
(`release/X-prep`: version in `pyproject.toml` and `__init__.py`, regenerated example projects, fixtures
and goldens, status lines, CLAUDE.md); the **owner's tag** (`vX.Y.Z`, which starts
`.github/workflows/release.yml`); then a **publication record** PR (`docs/publication-X`: SHA256SUMS
evidence in `compliance/evidence/`, `compliance/SIGNOFF.md`, `docs/STATUS.md`). Overhead per release is
about 1.5 agent-days and is **not** counted in the sizes below. Every milestone also owes: a CHANGELOG
entry, the affected pages of `docs/user-manual`, `docs/FILE_FORMAT.md`, `docs/ARCHITECTURE.md`,
`docs/DECISIONS.md`, and regenerated files (`compliance/traceability.csv`, `compliance/sdd_components.csv`,
`docs/RULES.md`, `docs/CLI.md`, the in-app guide, the API snapshot).

Written-output changes need a decision of yours before the goldens are renewed (D-191 (4): a change
that moves a number needs your approval case by case). Each milestone says whether it has any.

### 3.1 The 1.x steps that ship value early (format stays 1)

**M0, 1.16.0: release what master already has.**
- Goal: publish the five merged feature PRs (#182 labels on the line, #183 device looks, #184 tactile
  connecting and free canvas, #186 device kind, and the dialog-overlap fix) so a build exists for your
  real-display look before more is stacked on top.
- User sees: everything in CHANGELOG "Unreleased" (1.15.0 to master).
- Code: none new. Version bump, goldens, docs.
- Written-output change: **the block diagram for every project** (`system/block_diagram.svg`, `.pdf`:
  device looks), which you already approved ("yes, without breaking anything"); stamp and hash.
  Hash of designs does not change except for projects that set `Unit.kind`.
- Tests: the existing ones; confirm `python -m tools.output_hashes --check` and the numbers snapshot
  show only the stamp and the block diagram.
- Risk: low. Open points: PR #188 (the garbage-collector crash on a worker thread in the Linux perf
  step) was not in my worktree; confirm it is merged and master is green, including the slow tests.
  The slow-marked unused-string-constant test fails on master (you told me); fix or quarantine first.
- Size: S, 1 to 2 agent-days plus release overhead. Depends on: master green. You: tag, publication.

**M1, 1.17.0: the migration safety net (dormant).**
- Goal: everything of 2.3 and the hash rule of 2.2, working and tested, while `SCHEMA_VERSION` stays 1.
- User sees: `migrate --dry-run`, a migration record, the upgrade question in the editor, clearer
  messages. Nothing changes for projects.
- Code: `core/io/migrate.py`, `core/io/layout.py` (hash rule), `core/io/saver.py`, `cli/main.py`
  (`migrate`), `gui/` open flow (a dialog), `docs/FILE_FORMAT.md` (Versions and migration).
- Written-output change: **none, by construction** (hash rule normalises to 1). If a test finds one,
  the rule is wrong; stop and fix.
- Tests: a *test-only* fake v2 (a registered step that adds nothing) run over all fixtures; assert equal
  hash, equal findings, equal exports (byte for byte), baselines intact; failure injection (kill during
  backup, read-only folder, linked files; `tests/test_fs_safety.py` has the pattern); hypothesis test
  on random projects; the editor dialog.
- Risk: **medium**, because the hash is on every output and in every baseline; one wrong byte shows in
  600+ golden files (the output baseline lists 612 files for the four examples).
- Size: M, 4 to 6 agent-days. Depends on: M0. Can run in parallel with M2 and M3.

**M2, 1.17.x or 1.18.0: a real-platform test lane and a click budget.**
- Goal: stop relying on Qt's offscreen platform alone, and put the "quick path" under a test.
- User sees: fewer layout surprises. Nothing new on screen.
- Code and CI only: a Linux job with a virtual X display (`xvfb`) and Qt's real `xcb` platform; a
  Windows job with Qt's real `windows` platform; both run the layout audit (`tests/layout_audit.py`,
  `tests/test_ui_layout_sweep.py`, REQ-GUI-23) at several font sizes and interface scales; a
  scripted "systems engineer in four actions" test (New project, Add device twice, Connect, Export
  diagram) that counts clicks and dialogs and fails if the count grows.
- Unknown, to be tried first: whether the Windows runner gives Qt a usable desktop session and whether
  font fallback there differs from the bundled Inter/JetBrains Mono. I have not tried either.
- Written-output change: none. Risk: low (tests and CI). Size: M, 3 to 4 agent-days. Parallel to M1.
- **Honest limit:** this finds a class of problems (overlap, clipping, wrong minimum size); it is not
  your monitor (section 4).

**M3, 1.18.0: signed Windows installer and a build record.** Needs your certificate decision (section 5, D4).
- Goal: Windows setup program and `.zip` signed; every package covered by a build attestation, an SBOM
  and checksums.
- User sees: no "unknown publisher" box if reputation allows (verify; see section 4); `gh attestation`
  or a verification page in the release notes.
- Code: `tools/build_windows.py` (already signs with a `.pfx` through `signtool` when
  `HARNESS_SIGN_PFX` is set), `.github/workflows/release.yml` (the signing step exists but reads a
  `.pfx` from a secret), `docs/RELEASE.md` (the "Signing (optional)" section), `tools/release_notes.py`,
  pinning actions by commit hash (D-186 listed "pinned actions" as not done).
- Written-output change: none to the tool; the release page text and `docs/RELEASE.md` change.
- Risk: **medium to high** for schedule, low for code: depends on an outside party (certificate,
  identity checks), and on how signing is provided (a cloud service replaces the `.pfx` step).
  Linux: detached signatures or an attestation for the `.deb` and `.tar.gz`.
- Size: S to M, 2 to 4 agent-days of code; the waiting is yours. Parallel to everything; touches only
  workflows, `tools/`, `docs/RELEASE.md`.

**M3b, 1.18.x: real-display pass and simpler first run (theme 5, first slice).**
- Goal: fix what your first real-display look found and what M2 finds; make Quick/guided start faster.
- Code: dialogs and the main window only where they are wrong; no canvas changes (the canvas belongs to
  M4 and M5, section 3.5).
- User sees: a short list of fixes; device and diagram **templates** (a "Start from" list: a block
  diagram of 3 devices, a power chain, a flat-sat sample) built on the existing example projects and the
  subsystem library files (D-175), no new format.
- Written-output change: none. Risk: low to medium (many small edits in `gui/main_window.py`).
- Size: M to L, 5 to 8 agent-days, cut into small PRs. Depends on: M2 (so the lane finds things first).

### 3.2 2.0.0 and the model milestones (the order you set)

**M4, 2.0.0: format 2, loose ends as saved objects, origin recorded.**
- Goal: the first release that writes format 2: a cable can end in a saved loose end, plugged and
  unplugged by hand on the diagram and in the Harness tab, and every harness has an origin.
- User sees: drag a cable from a port, drop it on empty ground: the loose end stays, is listed in the
  project tree, survives save and reload, can be named, given a connector part later, and plugged into a
  port. Plugging pairs pins by signal name, then by number, then asks (the logic of `links.propose_pairs`
  and the re-plug of 1.15). **Unplugging** turns a connector end back into a loose end (the pins stay;
  the wires stay). The inspector shows "Origin: interfaces / link / drawn".
- Code:
  - model: `Role` gets `loose`; `Harness.origin` (sparse); `core/model/physical.py`;
  - `core/integrity.py` (a loose end is valid; two ends plugged on one box connector keep their
    existing warning), `core/manual_harness.py` (new plans: create cable from a port; plug; unplug;
    the `TBD-CONNECTOR` part), `core/links.py` (a Link created by a drag can name a harness whose far
    end is loose; the link review must say "open end", not "dangling"),
  - `core/io/migrate.py` (the real v1 to v2 step), `core/io/layout.py` (marks `pos:`),
  - `gui/cable.py` and `gui/canvas_cable.py` (the loose-end *draft* becomes a call to a core plan;
    the draft state machine stays), `gui/controller.py`, project tree, inspector.
  - The 34 files that read `from_connector` / `to_connector` (counted with grep: `outputs/verify.py` 27,
    `wires.py` 15, `outputs/tables.py` 11, `outputs/drawing.py` 11, `verify.py`, `drc/rules.py`, ...)
    **should need no change** because a loose end is an ordinary connector. That is the reason for the
    design. It must be confirmed by tests, not assumed: a loose end connector has a TBD part and maybe
    no real pin count, and the rules on pin counts, mass and BOM must say "pending", not crash.
- Written-output change: **none for the packaged examples** (sparse). For a project that has a loose
  end: the connector and pinout tables list the end as `TBD-CONNECTOR (loose end)`, the build workbook
  marks it "to fill in", the drawing shows an open end. Proposed owner decisions before the goldens are
  renewed: the wording, and whether a harness with an undecided end may be released (recommendation: it
  may not; add a release blocker `loose_end_unresolved`, waivable with a reason).
- Tests: model round trip; migration of all fixtures (2.3); every written output for a project with a
  loose end passes the independent verifier (`core/verify.py`, `outputs/verify.py`); property test
  "save, reload, same hash"; GUI journey: drag, drop on ground, save, reload, plug (offscreen is fine
  for this logic); a test that the 1.15 loader opens such a project read-only (a stored copy of the
  1.15 loader's behaviour is not available; use the documented warning and a test with `schema_version`
  99 as today).
- Risk: **high**. It is the first real format change; it touches the model, the migration and the
  canvas at once. Mitigation: M1 first; release candidates `2.0.0rc1..` for your own projects; keep the
  backup folder.
- Size: L to XL, 10 to 14 agent-days. Depends on: M1 (hard), M0. Includes M7a (journal layout) if the
  journal is to be in 2.0.0; see below.
- **Format 2 is frozen when 2.0.0 is tagged.** Anything format-shaped that is still wanted must be in
  before: the journal layout (M7a) and the tolerant journal reader.

**M7a (part of the 2.0.0 train): the journal that merges.** Listed here because it forces format 2.
- Goal: two people working on two Git branches can merge without a conflict in the journal, and a
  conflict that remains is repaired by `merge-fix`.
- Design (recommended, to be prototyped before it is trusted): `journal.jsonl`, one entry per line;
  `.gitattributes` gets `journal.jsonl merge=union` (a built-in Git merge driver that keeps both sides'
  lines, no setup per clone; I have **not** verified whether the GitHub web "Merge" button honours it,
  and that must be tried on a real repository); on load, entries are ordered by `when`, then author,
  then the id of the entry; the **chain** becomes a per-entry hash of its content plus the hash of the
  entry before it *on its own branch*, so two branches' entries are both valid after a union, and
  `merge-fix` adds one `merge` entry that names both heads and renumbers `seq`. Tamper evidence stays
  for each branch's history; the claim "no gaps in `seq`" is replaced by "every entry's parent exists".
- Why not a custom merge driver: it must be configured in every clone's `.git/config` and the GitHub
  server never runs it.
- Why `merge-fix` still matters: `generation.json` (already handled), `changelog.json` (also one list;
  two releases on two branches conflict), and **ID collisions** (below).
- ID collisions, read but not tried: harness IDs come from `next_harness_number` in
  `generated/generation.json` and link IDs from the next free `L<n>`; two branches can each create
  `W005` or `L7` with different content. Git reports an add/add conflict, and `merge-fix` refuses when
  any other file is in conflict. For a real team this needs its own small answer (a `merge-doctor` that
  explains and offers a rename of one side, in `core/mergefix.py`); I list it as M7b.
- Written-output change: none (journal is outside every hash and output).
- Tests: build merges with real `git` in a temp repository (two branches, both add entries, both
  generate, both add a link); the fixtures of the merge; fuzz the merge.
- Risk: medium to high. Size: M to L, 5 to 8 agent-days for M7a; M7b 2 to 3.
- Depends on: M1. Same files as M4 (`core/io/layout.py`, `loader.py`, `saver.py`, `migrate.py`,
  `core/journal.py`): **do not run in parallel with M4 on separate branches without agreeing the
  format first**; do M4's migration step, then M7a on top of it in the same release train.

**M5, 2.1.0: whatever came first (origin) and the drawn-first harness.**
- Goal: draw a harness first and get interfaces and checks derived from it; or have interfaces first and
  see the drawn harness checked against them; never overwrite either silently.
- User sees: on the diagram a cable between two plugged ends is a connection line even when no
  interface or link exists. **Derive from drawing** offers interfaces for the drawn wires (the logic
  of `derived_interfaces`, extended from link pairs to harness wires) and a Link ("pinout") on request.
  A connection group shows a status: *Agrees*, *Only drawn*, *Only asked for*, *Differs*.
  Problems and Why panels say it in a sentence with the fix.
- The origin model, concretely:

  | Item | Stored | Meaning |
  | --- | --- | --- |
  | `Harness.origin = interfaces` | `generated: true` as today | The harness was made by Generate from interfaces. Generate may rebuild it; a person's edits are protected by the existing locks (`Wire.locked`, `manual`, `overrides`, `Connector.locked`). |
  | `Harness.origin = link` | `generated: false`, plus `Link.harness_id` | Made by **Create harness** from a pin-to-pin connection. The link owns the pairs; the harness may be edited freely. |
  | `Harness.origin = drawn` | `generated: false` | The harness was drawn first. It is the truth. |
  | **Claims** | `Harness.interfaces` and `Wire.interface_id` (both exist) | The interfaces the harness says it carries. For `interfaces` origin Generate sets them; for `drawn` and `link` a person (or *Derive from drawing*) sets them. |

  Rules, each with a test:
  1. **Generate never touches a harness whose origin is not `interfaces`.** It already skips
     `generated: false` harnesses and treats their pins as owned and their claimed interfaces as frozen
     (`generate/engine.py` lines 253 to 262); M5's first task is a **property test** that Generate
     leaves the bytes of every drawn harness file identical, on random projects, plus a read of what
     Generate does today for an interface whose two devices are *already joined by a drawn harness* but
     which no wire claims (I have **not** traced it; line 372 ff suggests it builds a second plug and
     only warns `box_connector_shared`). The new behaviour: such an interface is not built; it is
     reported as *Only asked for*, with the choice "Claim it with this harness", "Rebuild this harness
     from interfaces" or "Waive".
  2. **The second side added later never changes the first.** Adding an interface after a drawn harness
     exists produces a finding, not a change. Drawing a harness after an interface exists produces a
     finding on the interface ("an interface asks for X; the drawn harness carries Y"). Nothing is
     overwritten.
  3. **Taking over is explicit and journaled**: *Rebuild from interfaces* shows the preview Generate
     already shows (`RegenReport`: added, removed, changed, frozen), changes `origin` to `interfaces`
     only on confirmation, is one undo step, and writes a journal entry with the reason. The reverse,
     *Keep as drawn*, sets `origin` to `drawn` (`generated` false).
  4. **A released harness is not rebuilt** (existing rule); its origin is frozen with it.
  5. **How a drawn harness yields checks:** the 39 electrical rules already run on wires whatever their
     origin. New rules (names provisional): `drawn-no-interface` (information, off in Quick mode),
     `interface-not-drawn`, `drawn-signal-differs` (the wire's signal against what the pins say, which
     `link_wire_mismatch` already does for links), `loose-end-unresolved`, `backshell-missing` (M6).
     The rule count goes from 39 up; `docs/RULES.md`, the `drc` fixtures and the rule table tests change.
  6. **What you see when they disagree:** a dashed amber connection line with a badge ("Differs"), a
     Problems entry in one sentence ("Interface IF-3 asks for CAN_H and CAN_L between OBC and RW1;
     drawn harness W007 carries CAN_H only"), the Why panel's first line "Origin: drawn (journal:
     entry #213)", and a one-click fix per case. Warnings can be waived with a reason, like any other.
- Code: `core/links.py`, `core/derive*.py` (the explanation of "origin"), `core/generate/engine.py`
  (skip rule, report), `core/drc/rules.py`, `core/outputs/connections.py` (the connection list: a drawn
  connection appears with `Origin` only if any is drawn), `gui/canvas*.py`, inspector, Problems panel.
- Written-output change: for a project with a drawn harness or a derived interface only; the examples
  have none that I know of (to be checked: no example project was opened). `system/connections.*` gains
  an `Origin` column **only while** any harness is drawn (the pattern used for `Direction` in 1.9.0).
  The new rules appear in `rule_results` and the DRC report; the rule table in `docs/RULES.md`
  changes for everybody (a documented file, not an output).
- Tests: the property test above; scenario tests for every cell of the four statuses; golden outputs for
  one new example `drawn-first`; undo of every action; journal entries.
- Risk: **high.** It changes what the tool believes about connections, and `core/generate/engine.py`
  is a 1,100-line file that generated files depend on. Mitigation: skip logic first, with the
  property test, before any screen.
- Size: XL, 12 to 18 agent-days. Depends on: M4. Can be cut into M5a (rules and statuses, no UI),
  M5b (diagram), M5c (derive from drawing) over two or three releases (2.1.0, 2.1.1, 2.2.0).

**M6, 2.2.0 to 2.3.0: splices, branches, breakouts and backshells as real objects.** Three slices:

- **M6a splice (L, 6 to 9 days).** A splice is a connector with role `splice` and `bonded` pins. The
  editor places one on a wire or in the tree; the drawing shows it; the wire list and the build
  workbook gain a line "via S1"; the **independent verifier** (`core/verify.py`, `outputs/verify.py`,
  27 references to wire ends) must follow nets through a bonded connector, which it does not today;
  the test table gains continuity through the splice; the rule `pin-shared` (one wire to a pin; it is
  built-in, `A-PIN-ONE-WIRE`) must not fire for pins joined through a splice. A new library category
  `splice` is a **new value of an existing list** (`PartCategory`): old tools set a part aside; it goes
  in format 2 from 2.0.0 as a list extension, or the splice uses `category: "other"`; decide in M4.
- **M6b branches and breakouts (L, 6 to 9 days).** Create, move, rename branch points; set segment
  lengths by hand (lengths exist: `generate/lengths.py`); a breakout kind with a boot accessory; draw the
  tree in the harness drawing (the routing sketch exists; "branch points drawn in the diagram" is listed
  as *not done* in D-141); the build workbook cut list follows segments.
- **M6c backshell (M, 3 to 4 days).** The accessory becomes visible: placed from the connector, mating
  part suggested from `Part.mates_with`, the rule `backshell-missing` for `backshell_360` shield ends,
  a line in the drawing.
- Written-output change: **only for harnesses that use them**, by the sparse rule; the examples keep
  their bytes. For the build workbook, wire list, test tables, BOM, drawing and open data **new lines
  and columns appear only when a splice, breakout or placed backshell exists**. Mass: see 3.4.
- Risk: high for M6a (the verifier and the net model), medium for the others.
- Depends on: M4 (roles, hash); M5 for the nicest drawing but not hard. Total about 15 to 22
  agent-days across three PRs. All three touch the same files (`core/model/physical.py`,
  `outputs/drawing.py`, `outputs/buildsheet.py`, `core/verify.py`, `core/outputs/verify.py`) and **must
  be serialised**; they can be run in parallel with M8 to M10.

### 3.3 Team, parts and the rest of the experience (2.x)

**M8, 2.x: sign-off in the tool.**
- Goal: review and release steps are signed in the tool by named people, with a strictness you choose.
- User sees: in the Releases tab each harness revision shows who has signed which role (author, checker,
  approver), when, with what comment, against which `content_hash`; a sign-off for an older content hash
  is shown as stale.
- Design: `signoffs/<harness>/<revision>/<person>.json`, one file per person (no merge conflicts),
  outside the model hash; a journal entry of kind `signoff`; the existing `author/checker/approver`
  fields and `release_distinct_roles` setting stay and become *derived* from sign-offs when present.
  Strictness is a setting with three levels (section 5, D2).
- **Authentication, honestly:** nothing in a plain file can prove who typed a name. The options are
  (a) trust the name, as today; (b) let the Git host enforce it: protected branch, required reviewers
  on the folders `baselines/` and `signoffs/` (a `CODEOWNERS` file), signed commits; the tool shows
  "last commit of this folder: signed by X" (it already reads the Git files without starting `git`,
  `core/vcs/gitinfo.py`, but verifying a signature needs gpg or ssh tools or a crypto library, and the
  tool has none and ships three dependencies); (c) the tool signs entries with its own key: needs a new
  dependency and key handling, not recommended now. Recommendation: (b), written up as a process page
  and a CI check template, with (a) in the tool.
- Written-output change: the release evidence page and revision report gain a "signed by" block
  (only when sign-offs exist). Risk: medium. Size: M, 4 to 6 agent-days. Depends on M7a (journal kinds).

**M9, 2.x: parts library with approval status and a parts system.**
- Goal: one approved parts list for the team, with who approved what and when, and an exchange with
  InvenTree.
- Honest constraint: **the tool never uses the network and a test enforces it**
  (`docs/ARCHITECTURE.md` section 4, `tests/test_offline.py`; `docs/ait/AIT_FEEDBACK_PLAN.md` item 1 says
  "no live connection to InvenTree"). A live connection would reverse a design rule (and a security
  review, `docs/SECURITY.md`).
- Recommended design: (1) the part gets the sparse fields of 2.4 (who, when, source id, source
  revision, note); (2) approval stays a person's action with a journal entry (`core/part_approval.py`
  already does this on the Next step page); (3) the **library folder** (D-175, a shared drive or Git
  repository) is where the team's parts live; (4) a **separate, optional script** outside the tool
  (`tools/inventree_sync.py`, not in the package) calls the InvenTree REST API and writes the export
  file the importer already reads, and reads back a file of "parts used by this project with their
  approval status" the tool writes. The script is the only code that uses a network, it is not shipped
  in the installer, and the offline test still holds.
- Unknown, needs a real InvenTree server and your decision on where it runs: the exact fields and
  status values your instance uses, authentication, and how you want conflicts (the part changed in
  InvenTree after the project approved it) shown. I have not seen an InvenTree instance.
- Written-output change: BOM and `parts.csv` may show approval metadata columns, **only when set**.
- Risk: medium (external system). Size: M, 4 to 6 agent-days plus your server. Parallel to M5/M6
  (touches `core/model/library.py`, `core/library_import.py`, `gui/library_window.py`).

**M10, ongoing: the user-experience rebuild (theme 5).** Cut into small releases, never one big one:
- **Click budget and guided path.** The test of M2 stays; the Next step page gets a "Systems
  path" with at most four steps to an exported block diagram and no required dialog except naming.
  The electrical/AIT path is the full tool as today. Both already exist as roles and Quick mode; the
  work is to *measure* and trim, not to build a third mode.
- **Simpler device and diagram model.** A device is a name, a kind and connectors from a template
  (the kind table `core/device_kinds.py` and the subsystem library already provide the data). The
  rebuilt "Add device" is a template picker. Pin-level editing stays in the Devices tab.
- **Promises as tests.** Devices freely movable (already true since 1.15); labels and symbols stay on
  their line (1.15); devices distinguishable (looks); guarded by `tests/test_ui_canvas_overlaps.py` and
  the sweep.
- **Canvas work conflicts with M4 and M5**: serialise (section 3.5).
- Size: L overall, 8 to 14 agent-days in slices of 2 to 4. Real users needed for the guided path
  (section 4).

### 3.4 Interactions with themes not chosen

- **Theme 2 (reviewed calculations):** the mass model counts connectors and wires only, plus contacts
  and accessories under the opt-in `full_bom` (`generate/mass.py`). A splice has no mass in either
  mode, and a placed backshell is already counted under `full_bom`. M6a must **not** change the default
  mass; it may add a splice part to `full_bom`. A change of the default needs your approval case by case
  (D-191 (4)). The AC and skin-effect drop model is untouched.
- **Theme 3 (physical design):** branch and segment lengths in M6b are typed numbers; the "length from
  CAD" and bend radius work would write into the same fields and needs the same sparse rule. Nothing in
  this plan blocks it.

### 3.5 Order, parallel work and the places where branches collide

Order you asked for, with what can run beside it:

```
M0 ──► M1 ──► M4 (2.0.0) ──► M5 ──► M6a ──► M6b ──► M6c
        │       ▲ M7a (journal format) goes in with M4
        │
M2 ─────┤ (tests and CI only)                      M8, M9 after M4 / M7a
M3 ─────┘ (workflows, tools/, docs/RELEASE.md)     M10 in slices, canvas slices serialised
```

Can run in parallel on separate branches (each from `master`, merged to `master`, never stacked):
M2, M3, M3b (no canvas), M9 (library files), and the **specification** part of M4 beside the code of
M1. Not in parallel with each other: M1 then M4 then M7a (all in `core/io/`), M4 then M5 (canvas and
`generate/engine.py`), M6a, M6b, M6c (model, drawing, verifier), M10 canvas slices with M4 to M6.

Conflict hot spots (from the git log: the "regenerate the traceability file" and "renumber the
requirement rows" merges of PRs #184 to #186 are the symptom):

| File or group | Who touches it | What I propose |
| --- | --- | --- |
| `CHANGELOG.md` "Unreleased" | every PR | one fragment file per PR in a folder, assembled at release prep (a small `tools/` script); stops the constant conflict |
| generated files: `compliance/traceability.csv`, `compliance/sdd_components.csv`, `docs/RULES.md`, `docs/CLI.md`, in-app guide, `tests/fixtures/api_snapshot.json`, `docs/ui/OUTPUT_HASHES_BASELINE.json`, `tests/fixtures/numbers/` | most PRs | never hand-merge: on conflict take either side and run one `tools/regen_all` command; put the same command in the PR checklist; do **not** renew baselines in a feature PR except the one that owns the change |
| requirement numbers (`REQ-GUI-22` and so on) | feature PRs | reserve a range per milestone in `docs/PLAN.md` before the first commit (the renumbering in PRs #184 to #186 came from two branches taking the next number) |
| `core/model/physical.py`, `core/io/*` | M1, M4, M6, M7a | serialise as above |
| `gui/canvas.py` (3,962 lines), `gui/canvas_cable.py`, `gui/canvas_links.py`, `gui/controller.py` | M4, M5, M10 canvas | serialise; one owner per week |
| `gui/main_window.py` (5,208 lines), `gui/strings.py` (3,414 lines) | nearly everything | keep edits small; strings in blocks per feature |
| the PR whose head did not update after a push | any | after each push, compare `git rev-parse HEAD` with `gh api repos/0h3xn4/wireviz-harnessdesignstudio/pulls/N --jq .head.sha` before waiting 50 minutes for CI; I do not know the cause |

Rule of thumb for stacking: never base a branch on an unmerged branch. If M5 needs M4, wait for M4 to
be merged to master (each merge to master is one PR that CI has passed), or use release candidates
tagged from a **release branch** that takes only merges from master.

---

## 4. What I can verify, and what only you can

**I and my parallel agents can verify:**
- model and file logic: round trips, migration (all fixtures, dry run, record, rollback on failure),
  hash neutrality, golden outputs, numbers snapshot, the independent verifiers, the 39 (or more) rules,
  Generate never touching a drawn harness (property tests), journal merges with real `git` in a temp
  repository, offline test, API snapshot, schema export;
- GUI logic on the offscreen platform: gestures, state machines, undo, layout audit (overlap, clipping,
  minimum size) at several font sizes;
- documents, release preparation PRs, the workflow files (by reading and by a dry run on a branch).

**I cannot verify, and I will say so in each release text:**
- **Real display behaviour.** Offscreen is not your monitor: real font rendering and fallback, 125/150%
  scaling, window manager sizes, multiple screens, Wayland versus X, native file dialogs, the feel of
  dragging a cable. The layout audit and the M2 lane reduce the number of surprises; only you (or a
  second person) at a real screen can confirm. Proposal: each release candidate comes with a one-page
  checklist (open, drag a cable, drop it, save, reopen, plug, resize the window, change the interface
  size) and a few screenshots to send back. Your first look already found three defects offscreen never
  showed; assume there are more.
- **Whether the tactile feel is right.** The thresholds (`DRAG_PX 4`, `SNAP_PX 14`, `PLUG_PX 9`) are
  my guesses. Only hands decide.
- **A signed installer.** Needs a certificate or a signing service and an identity check done by you.
  Options, with what must be checked (I could not check current facts; do not trust prices from me):
  1. a commercial code-signing certificate: since 2023 the certificate authorities have had to keep the
     private key on a hardware token or in a cloud HSM, so a `.pfx` file in a GitHub secret (what
     `release.yml` expects) may no longer be something a CA will issue; ask the CA what they deliver.
  2. Microsoft's cloud signing service (Azure Trusted Signing; the product name and who is eligible,
     individuals or only organisations, in which countries, have changed more than once; check Microsoft's
     page today);
  3. SignPath Foundation (free signing for qualifying open-source projects): **needs an open-source
     licence. The licence here is the placeholder `LicenseRef-Proprietary` (D-02, D-143), the
     repository's root licence is the WireViz GPL-3.0, and D-186 says the tool is internal.** That is a
     legal and ownership question for you, not for me;
  4. a commercial cloud signing service (SignPath and others sell this; prices not checked);
  5. an **internal code-signing certificate** from your organisation's own PKI, trusted on company
     computers by policy: no public cost, removes the warning on those computers only. Probably the best
     fit with D-186 (internal use). Needs your IT;
  6. self-signed and imported by hand: no cost, no SmartScreen help, works for a handful of machines.
  Also unknown: SmartScreen reputation. A newly signed program from a new publisher may still warn until
  it has a download history; whether an "extended validation" certificate still skips that, I believe
  not any more, **verify**.
  Linux: signatures for the `.deb` and `.tar.gz` and GitHub's build attestation
  (`actions/attest-build-provenance`; available for public repositories, to my knowledge; the repository
  is public) are cheap; whether `gh attestation verify` works on an offline machine with a downloaded
  bundle must be tried.
- **Real multi-user merging.** At least two people, two machines and real branches, over several days,
  in a real GitHub repository, including the web merge button, a rebase and a force-push. I can build
  the temp-repository tests; they will not find the human accidents.
- **InvenTree.** Needs a real server (or a copy of yours) with your fields and your status values. My
  tests can only read a file.
- **The guided path for a systems engineer.** Whether four clicks is *enough* is a question for two or
  three people who have never seen the tool, with a stopwatch. The workshop of 2026-10-23 (a systems
  engineer, an AIT engineer, an electrical engineer) is the right audience. I can build the test that
  keeps the count; I cannot tell whether it is the right count.
- **Engineering truth.** Nothing in this plan adds a derating or ampacity value; every splice, backshell
  and loose end stays "pending" until a project supplies data (D-11).

---

## 5. Owner decisions

### 5.1 Already taken (they shape the plan; no question left)

- **D-A. Format 2 with an automatic upgrade, older tools do not edit.** Taken. The plan builds the
  safety net first (M1) and one coordinated bump (2.0.0).
- **D-B. A loose end is a saved, hashed object.** Taken. Existence and connection are in the hash; its
  *screen position* is not, so tidying the drawing never marks outputs stale. Tell me if you want the
  position in the hash too; then every drag of a loose end would make outputs stale, as moving a device
  does today.
- **D-C. Whatever came first is the truth (origin).** Taken. Stored as `Harness.origin`; Generate never
  overwrites a drawn or link-first harness; disagreement is a finding; taking over is an explicit,
  journaled, undoable action (section 3.2, M5).

### 5.2 Still yours

1. **Sign-off strictness.** Options: *Off* (names typed as today), *Recorded* (sign-offs exist,
   nothing is enforced), *Enforced* (release needs three sign-offs by three different people for the
   three roles, which `release_distinct_roles` does today for typed names). **Recommendation:** default
   *Recorded*, *Enforced* as a project setting (the quick path stays quick, the strict path stays
   strict). Authentication by the Git host (CODEOWNERS, protected branch, signed commits), not by a
   key inside the tool.
2. **Who may approve what.** Today a role is a view, never a permission (`gui/roles.py`), and the tool
   has no user accounts. **Recommendation:** keep it so; "may approve" is a *named list* in a project
   setting (`config/naming.json`, like `release_distinct_roles`), checked against the typed or
   Git-derived name, and enforced by the Git host for the folders that matter.
3. **Where parts live.** Options: a team library folder (a shared drive or a Git repository, exists in
   1.8.0); InvenTree as the master with files exchanged; the project's own library (today).
   **Recommendation:** the library folder is the team's working copy; InvenTree stays the master where
   you have it; exchange by file and a separate script, so the offline guarantee holds. Do not add a live
   network connection to the tool unless you decide to change that rule.
4. **Certificate and identity.** See section 4. **Recommendation:** an internal certificate through your
   IT if you have one (fits D-186); otherwise a cloud signing service whose eligibility you confirm.
   Reopen D-02 and T-19 (licence and signing) in writing before M3 starts, because D-186 postponed them
   "until the tool is given to anyone outside".
5. **What 2.0.0 contains.** **Recommendation:** tag 2.0.0 only when M4 (loose ends, origin, format 2,
   the journal layout) is done and your own projects have run through `2.0.0rc` builds. M5 and M6
   follow as 2.1 and 2.2.
6. **May a harness with a loose end be released?** **Recommendation:** no, with a waivable blocker
   `loose_end_unresolved` and a recorded reason (consistent with your "honest about what it does not
   know").
7. **The minimum a systems engineer must do to get a block diagram.** **Recommendation:** four actions:
   *New project*, *Add device* (a name, optionally a kind) for each device, *Connect* (drag from a port
   to a port), *Export diagram*; no required field except names; no dialog the person did not ask for;
   guarded by a test in M2. Strictness (checks, release) is reached only by leaving Quick mode.
8. **Journal merge approach.** **Recommendation:** `journal.jsonl` with a union merge and a
   `merge-fix` that renumbers, tried first on a real repository; if the web merge button ignores the
   attribute, merges happen locally (`git merge`, `merge-fix`, commit), which for a small team is
   acceptable.
9. **Mass with splices.** **Recommendation:** leave the default (connectors and wires) alone; add
   splice parts to the opt-in `full_bom` model only (theme 2 stays out of scope).
10. **Release cadence.** **Recommendation:** keep one release per milestone, small; run the slow tests
    on a schedule or on pull requests that touch `core/` (section 6).

---

## 6. Risks and what could go wrong

1. **The hash is on everything.** The migration's whole safety depends on 2.2 being right. A test that
   migrates a project with released harnesses and compares every output must exist *before* anything
   uses it. If the hash rule cannot be made neutral without changing existing hashes, stop and tell
   you; the fall-back is a one-time renewal of every baseline with your approval.
2. **Frozen baselines.** Released baselines keep format 1 shapes for ever. Any change to `Harness`,
   `Wire` or `Connector` must keep them loadable and comparable. This is why `generated` stays and
   `origin` is bookkeeping for `content_hash`.
3. **Verification burden of this repo.** Each release needs: regenerated example projects, goldens, the
   numbers snapshot (eleven scenarios), the output hash baseline (612 files), a docs set that tests read
   (4,400 tests, about 326 test files), a prep PR, a publication record. CI runs 40 to 55 minutes on
   Linux and Windows. Slow-marked tests (22 of about 10 s or more) run only on master and in the
   release check, so a PR can be green and master red. Plan one extra day per milestone for CI cycles
   and assume two push-and-wait rounds per PR.
4. **State of master.** The Linux perf-step crash (the garbage collector on a worker thread) was fixed
   in PR #188, which I did not see in my worktree; and an unused-string-constant test fails on master
   because it is slow-marked. M0 starts by getting master green with the slow tests, or every later
   branch inherits the red.
5. **Stacked branches and merge pain.** Section 3.5. Release candidates from a release branch rather
   than stacked feature branches; changelog fragments; regenerate-not-merge for generated files.
6. **A model that is wrong in a way tests do not show.** The pseudo-connector design (loose end and
   splice as connectors) is attractive because 34 files need no change, but a `TBD-CONNECTOR` has no
   real pin count and no mass, and rules and the BOM may treat it as a real part. M4's first PR is a
   spike with a loose end through every output, the verifier, the DRC and the open data, before any
   screen. If the design is wrong, the cost is found early and format 2 is not frozen yet.
7. **The verifier is independent by design.** Splices (M6a) need it to follow nets; that is a second
   implementation of connectivity and doubles the test effort.
8. **Real-display uncertainty.** Section 4. A release can pass every offscreen test and still look wrong.
9. **Team merging is only partly solvable by tools.** ID collisions, two people editing the same wire's
   override, the GitHub web merge, rebases that rewrite history: the journal's tamper evidence assumes
   linear history. A team needs a short written process in `docs/user-manual/use-git-and-ci.md`.
10. **Your tolerance for restrictiveness versus due diligence.** You want a quick path and a strict path.
    The design keeps one tool and one file format with two behaviours chosen by role, Quick mode and
    settings: *drawn* data may be loose and "pending" in Quick; the same project shows blockers (loose
    ends, disagreements, sign-offs) in the strict path. The danger is feature creep in "quick": every
    new safeguard must say in which mode it is on, and a test must hold the click budget.
11. **Signing is an outside dependency** that can stall M3 for weeks without any code being wrong.
    Keep it off the critical path.
12. **Legal.** D-186: internal use; licence placeholder; a public GPL-3.0 repository around it. Signing
    and any outside distribution reopen this. I am not able to settle it.
13. **Agent-day estimates are for the work the repo's own history shows** (1.12 to 1.15 were prepared
    in about three calendar days with parallel agents). They do **not** include your review time, tag
    and publication, or real-display checks. Expect the calendar time of M4 to M6 to be dominated by
    those, not by coding.

---

## 7. First three steps (what I would start now)

1. **M0: cut 1.16.0 from master.**
   First deliverable: the prep PR `release/1.16.0-prep`: version bump, the `## Unreleased` section
   renamed, the page `docs/releases/1.16.0.md`, regenerated examples and goldens with a table of
   *exactly which files changed* (expected: the block diagram files for every project, the stamp), a
   short owner checklist for your real-display look (open, drag a cable, drop on ground, reopen, resize,
   change interface size), and, before it, a note on whether master is green including the slow tests
   (PR #188 merged or not). You tag.
2. **M1: the migration safety net.**
   First deliverable: a PR with (a) the hash rule (`schema_version` normalised in `model_hash`) and its
   proof, a test that migrates every fixture with a fake no-op "v1 to v2" step and finds identical hash,
   identical findings and byte-identical exports; (b) `migrate --dry-run` and the migration record
   `MIGRATION.json`. No format change, no screen. This PR is also the review point for you: it is the
   part of the whole programme that can lose your data if it is wrong.
3. **M4, spike: loose ends in the core, no screen.**
   First deliverable: a branch (not merged) with `Role = loose`, `TBD-CONNECTOR`, the plans
   *create cable from a port*, *plug*, *unplug*, and one test project with a loose end run through
   `validate`, `drc`, `generate`, `export`, `verify`, `export-data`, the independent verifier and the
   migration step, plus a two-page draft of format 2 in `docs/FILE_FORMAT.md`. Its purpose is to find,
   before any pixel is drawn, where a loose connector breaks an output or a rule (risk 6). Its result
   decides the final shape of M4.

In parallel, without waiting: **M2** (the real-platform lane and the click-budget test, tests and CI
only) and your **decision D4** (the certificate), because M3 can only start when that is answered.
