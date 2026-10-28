# Harness Design Studio 1.8.0: audit, review and test report

Audited: master `d58072d` (tag `v1.8.0` plus the publication record), 2026-10-26/27.
Method: six independent read-only auditors on a clean copy of master, each reproducing or measuring what they report (see section 10 for where their reports are). This document is the synthesis. I re-ran three of the top findings myself (section 3, marked "re-checked").

---

## 1 Verdict in one page

**Overall: 3.6 / 5. A strong, honest single-engineer generator and checker with an excellent data layer. It is not yet a safe team tool, and the new 1.8.0 "pinout first" path is the least protected path in the product.**

| Area | Auditor | Rating | One line |
|---|---|---|---|
| Core data layer, file format, change control | A | 4.0 | No crash in 19,000+ hostile inputs; undo is byte-exact for 85 planner paths; 1.7.0 and 1.8.0 files interchange byte for byte. |
| Engineering correctness (generation, rules, outputs) | B | 3.5 | The four shipped examples are physically right; realistic cases produce impossible harnesses or false results that nothing flags. |
| Command line, importers, security, release machinery | C | 4.0 | About 600 CLI calls and 90 hostile files: no traceback, atomic everywhere. Release path publishes without a recorded test or vulnerability run. |
| The editor (GUI), both roles | D | 3.0 | No crash, no warning, undo coherent; the Systems engineer journey from a blank project is a dead end; keyboard traps; layout clipped. |
| Tests and code quality | E | 4.0 | 3,779 tests, 94.3 % coverage, ruff/mypy strict clean; three timing tests fail on an idle machine; two giant files. |
| Product fit, documentation, roadmap | F | 3.0 | Documentation is unusually truthful (6 stale claims of about 55); gaps are in team use, buses, variants, import of existing data and trust. |

**Count of findings** (all reproduced or marked "by reading"): about 130 in total, **no Critical**, 14 High (13 distinct after merging duplicates), about 55 Medium, about 47 Low, about 17 Info.

**The five things that matter most**
1. **The tool can produce, and then pass, a physically wrong harness.** Two cable plugs on one box connector (re-checked), a routing loop for a device chain, TX wired to TX from a plausible-looking pairing (re-checked), a harness that no longer matches its link, wires with no current that get no ampacity check and no "not checked" note.
2. **"Silence must not look like a pass" is violated in several places** (rules show *pass* with no data; the build sheet says *Ready to build: yes* on placeholder values; `link-direction` raises false non-waivable errors in the other direction).
3. **The Systems engineer role cannot get from a blank project to a released harness** by following the Next step page, and a connections-only project cannot be exported at all.
4. **Team and audit use is weaker than the documents say**: parallel Generate always conflicts on `generated/generation.json`; one name can author, check and approve; the change log has no tamper evidence; releasing runs no tests; an older tool silently edits a 1.8.0 project that uses links.
5. **Speed at the specified size** (200 devices, 20,000 wires): edits 125 to 190 ms (target 100), autosave freezes the window 2.5 s, export about 17 to 22 minutes extrapolated.

**What is genuinely good** (section 2): determinism, undo, robustness, atomic file handling, security hygiene, documentation accuracy, test depth, honesty of the outputs about placeholders.

---

## 2 What is solid (evidence)

- **Robustness.** 14,340 structure-aware mutants of rich projects through about 25 stages, 1,650 on-disk byte/file-system mutants, 3,000 library/planner iterations, the repo's hypothesis fuzz test: **zero crashes** in the loader, integrity, serializer, links, change control, undo, DRC, verify and generation planning (A). About 600 CLI invocations: **zero tracebacks**; every hostile importer input (zip bombs, XXE, FIFOs, traversal ids, 5,000-digit numbers) ended in a plain sentence, exit 2 and an unchanged project (C).
- **Determinism.** Same design gives the same bytes: three runs with different working directory, locale, timezone and hash seed produced identical folders including xlsx, svg and pdf (B). Shuffling insertion order of every collection gives identical files (A). Two exports 2 s apart: identical (F, C).
- **Backward compatibility.** Projects saved by 1.7.0 re-save with 1.8.0 byte-identical except `project.json`; the reverse also holds (A). `output_hashes --check` against 1.2.0 still prints *identical*.
- **Undo/redo.** 85 planner paths applied, undone and compared by serialized bytes and model hash: all exact (A). In the GUI, tree, diagram, selectors and counts followed nine do/undo/redo cycles (D).
- **Engineering numbers.** Rule thresholds are exact at the boundary (2.5 A passes, 2.5000001 fails; 49 vs 50 mating cycles; gauge steps); ECSS tables 6-10, 6-41, 6-42 in the code equal the standard text in the repo; AWG areas within 0.1 % of geometry (B). The four shipped examples (6, 24, 54, 103 wires) had no physical error in an independent checker; TX/RX crossing, return wires, genders and mating parts were right (B).
- **Output integrity.** The output verifier caught all 18 hand edits, also with a repaired manifest; wire list, cut list, tests, BOM metres and mass agree across files (flatsat: 103 wires, 329.6 m, 2,374.4 g) (B). Spreadsheet formula injection is neutralised in CSV and xlsx (B, C).
- **Security.** No network, no unsafe deserialisation, symlinks and traversal contained, atomic writes with a real lock, SVG/xlsx safe with hostile names (C).
- **Release engineering.** Tag/version/changelog check, one `SHA256SUMS`, smoke tests on the finished files, the four published hashes equal the compliance evidence (C, F).
- **Documentation.** 1,905 relative links and 242 command lines and 63 menu paths all valid; Getting Started reproduces output for output (model hash, "Rules run: 39", "0 of 17 set"); only 6 of about 55 claims stale (F).
- **Honesty culture.** Placeholders propagate to notes and block release unless a written reason is kept; "pending" instead of invented values (B, F).
- **Tests.** 3,779 collected; 3,729 non-perf passed on three different groupings; coverage 94.3 % (core 95.7 %); every 1.8.0 module at 90 to 100 % except `gui/canvas_links.py` (80 %); `core` never imports `gui` (tested) (E).

---

## 3 The findings that should drive decisions

IDs refer to the auditor reports (letter + number). "Re-checked" = I reproduced it myself.

### 3.1 Wrong-but-silent engineering results (highest priority)

| Issue | IDs | Evidence | Fix (effort) |
|---|---|---|---|
| **One box connector gets several cable plugs; one box pin can be wired by two harnesses.** Generate with two interfaces on one connector builds two harnesses that both mate it. Link → delete link → link again gives the same. Link plus Generate on the same connectors wires the same pins twice. No integrity finding, no rule, `verify` clean. **Re-checked**: `W001-P1` and `W002-P1` both mate `A-J01`, generation findings none, DRC only *part-unapproved*. | A-1, B-01 | Both auditors, independently | Integrity error `box_connector_mated_twice`; DRC `pin-wired-twice` across harnesses; `plan_add_link`/`plan_create_harness` refuse when pins carry an `interface_id`; later one plug with branches (S to M) |
| **The pairing proposes TX↔TX for vendor-style names and the review is silent.** Counterparts are six exact names; everything else pairs by equal name. **Re-checked**: `UART_TX`↔`UART_TX`, `SPW_DOUT`↔`SPW_DOUT`, 6 of 6 pairs same-name, `check_links` = no findings. In F's probe 6 of 14 pairs were wrong and the harness exported with 0 errors. | F-01, F-12, A-10 | | Token-based counterparts (TX/RX, TXD/RXD, DOUT/DIN, TX_P/RX_P, MOSI/MISO, A/B); never auto-pair equal names inside the transmit/receive family; warn when an "equal" pair has a TX/RX token on both sides; a per-pin direction (M) |
| **`link-direction` raises false, non-waivable errors** on correct analog, discrete, LVDS, pyro and I2C-SCL links (the starter types list those signals as `out` at both ends; the older rule already exempts them) and the proposal skips them. | B-03 | `propose_pairs` returns no pair for the flatsat analog link; pairing by hand gives an error | Same exemption as `direction-conflict` (S) |
| **A harness made from a link is never checked against the link.** Edit a wire to end on pin 9: `validate`, `check`, `verify`, `drc`, `export`, `verify --outputs` all rc 0; the wire list says pin 9. | C-1, A-15 | Reproduced on a hand-edited harness | Verifier error `link_wire_mismatch` + DRC rule + `harness_id` consistency (M) |
| **"Pass" with no data.** With no current/voltage anywhere, four rules show *pass*; a power interface with no current gets no gauge and four *pass*. Wires of a pinout-first harness carry no current at all, so no ampacity/voltage-drop/bundle check can run and nothing says so; a hand-typed gauge satisfies the release gate. | B-04, F-03 | `nocur.py`, run on flatsat | Per-rule "not checked" notes when nothing was evaluated; a note "N wires have no interface: current checks not done"; optional current/voltage on a Link (S then M) |
| **Routing loop for a device chain in one zone** (A–B, B–C): all wire lengths unknown, non-waivable `segment-loop`. 9 hits in 288 fuzz runs. | B-02 | `loop2.py` | One branch node when a connector is on both sides (M) |
| **Build workbook says "Ready to build: yes" on placeholder configuration**; never mentions placeholders. | F-06 | flatsat `W001_build.xlsx` | A line "Values rest on placeholder configuration" and `yes (on placeholders)` (S) |
| Other Medium items of this kind: BOM/cut list/mass count every conductor of a pair part (2x/4x the cable); coax outer conductor gets "floating at one end"; generator violates its own `power-return-adjacent` rule (60 warnings in fuzz); no provisional gauge until every length is typed; shield "end A/B" depends on sort order; cable pin Signal column empty in `pinouts.csv`; `bundle-current` duplicates `current-over-wire` with a different limit; waivers not bound to the finding text. | B-05..B-13 | | S each, B-05 and B-12 M |

### 3.2 The Systems engineer role and the pinout-first flow do not yet form a complete workflow

| Issue | IDs | Fix (effort) |
|---|---|---|
| Next step page is a dead end from a blank project: a new device has no connector; the Link window says so; template pins have no signals so the proposal is empty (75 interactions for a 25-pin connector). Only a team-supplied library subsystem worked. | D1, D15 | First connector in Add device; "Add a connector" inside Link connectors; explicit "Pair by pin number" and "Paste a pairing" buttons (user-confirmed, so the owner's rule holds) (M) |
| After the first harness the page stays on "Fix what is marked" forever (unapproved starter parts) and offers no fix. | D2 | Preselect the first failed rule, say what to do, add Waive/Approve, do not let a warning hold the page (M) |
| A connections-only project cannot be exported ("run generate first"); connections are absent from the block diagram and `traceability.csv`; derived interfaces exist only on screen. | F-02, F-08 | `connections.csv/.xlsx` (ICD-style), links in the block diagram and traceability, allow export without harnesses (M) |
| The role still shows the full Devices/Harness screens and all 163 menu entries (Electrical: 162). Systems tour has 2 steps and does not mention Add device/Connect/Next step. | D5, D26 | Keep the person on the Next step page/diagram after each step; hide engineering menu entries (still in the palette) (M) |
| Stale interface-first wording: tour step 3, Harness/Lists/tree empty states ("Press Generate"), Generate as the primary button even with no device, "Not generated" chips for hand-made harnesses, release blockers that quote command-line commands. | D6, D7 | One wording pass keyed on "project has links/hand-made harnesses" (S to M) |
| Problem counts disagree (toast 14, tree 14, Problems panel 24 under a filter, inspector 16). Chip "Check passed" beside a failed rule. | D12, D13 | Show "14 of 24"; rename chip (S) |
| Pin role is invisible and uneditable in the Devices tab. | D11, F7 | Role column (S) |

### 3.3 Change control, audit trail, team use

| Issue | IDs | Fix |
|---|---|---|
| One name can author, check and approve; any name and any date accepted (verified with `--by Z --checker Z --date 2020-01-01`). | F-07 | Distinct-role switch, default name from Git, back-date guard (S to M) |
| Change log and baselines are not tamper-evident; deleting `changelog.json` passes `check`. | A-13 | Cross-check baselines vs log, hash chain (M) |
| Box-pin signals under a released link/hand harness are not frozen; `import-pinout --replace` changed them with exit 0. | A-2 | Freeze pins used by released wires (S to M) |
| Two people each pressing Generate always conflict in `generated/generation.json`; the docs say edits merge cleanly. `links.json` is one file with sequential IDs (two branches both create `L3`). | F-05, A-23 | `.gitattributes`, `merge-fix`, shard links, random id part (S to M) |
| A 1.7.0 tool opens and edits a 1.8.0 project that uses links without stopping (`schema_version` stays 1). | A-3 | Marker older tools cannot ignore (S) |
| Release workflow publishes with no pytest, no vulnerability scan, no required green CI of the tag; re-running replaces published files (`--clobber`) so recorded checksums stop matching. | C-2, C-3 | `needs:` a green run; scan + SBOM in the workflow; refuse to overwrite (S to M) |

### 3.4 Library (shared folder) governance

"Save to library" silently replaces a same-ID device and can lower a part's approval (A-7, D4). A device with a cable contact cannot be added from the library although the preview says it can (A-4). A renamed device cannot be saved and re-added (A-5). One malformed file makes `scan_folder` raise and hides every good entry (A-6). No File column, 299 identical rows for 299 copies (D18). **All S to M.** The folder has no locking: two writers can overwrite each other.

### 3.5 Keyboard, layout, accessibility

- **Tab never leaves** the pair table of an existing connection (Link window), the library list, and 7 main-window tables: `TableView` keeps Qt's default `tabKeyNavigation=True` (D3). One line fixes most of it. The existing Tab-walk test does not select a row, so it cannot see this.
- Clipped/overlapping controls at the default 1440x900 Electrical layout (Harness side tabs read "Why E... Co... Ac...", pin toolbar "[+ Add pi] [Delet]"); at 1024x600 the Devices card overlaps; the library window's minimum (1094 px) and the Link window (696 px high) do not fit small screens (D10). Banners and toasts cover the diagram (D14). Connection-end boxes overlap neighbouring devices (D16).
- Contrast is good: every text token reaches 4.5:1 except light `status.critical` on `diff.removed` (4.26) (D20).
- `gui/canvas_links.py` click/double-click/keyboard path has no test (E-F5).

### 3.6 Command line, Windows, import/export

- **No CLI for the 1.8.0 features** (links, connector/group/bulk edits, number of devices, library list/save) and **no `--json` on any of the 28 commands** (C-8, F-17). A CI script cannot reproduce the headline workflow.
- Windows: redirected output fails on non-cp1252 characters (`drc proj > report.md` with a project named "Ω": `'charmap' codec can't encode`), and CI cannot see it because it forces UTF-8 (C-4). One line fixes it.
- Re-importing unchanged data exits 1 and prints "OK updated" (C-5). CSV outputs have no BOM and a comment first line, so Excel mis-reads UTF-8 and shows the stamp as row 1 (C-6). `export-pinout -o x.tsv` writes commas (C-11). `import-lengths` accepts duplicates, last row wins silently, and zero (C-9). Excel's own cp1252/UTF-16 "CSV" is refused (C-13).
- GUI: "Open" in the Outputs list hands any file in `outputs/` to the operating system, including a `.bat` or `.lnk` in a received project (C-7, by reading).
- Unescaped names in two rich-text labels (delete confirmation) (C-15).

### 3.7 Performance (measured)

| What | 15 dev | 60 dev | 150 dev | 200 dev (spec) | 300 dev | 1,000 dev |
|---|---|---|---|---|---|---|
| Generate | 0.1 s | 0.2 s | 1.3 s | 8.8 s | 1.7 s* | 42 s |
| Load project | 44 ms | 0.19 s (GUI open) | 0.59 s | **7.5 s, 670 MB** | 0.96 s* | 24 s, 1.9 GB |
| One edit (`History.execute`) | 1 ms | – | 22–25 ms (50 dev) | **125–190 ms** | – | 605–670 ms |
| One edit in the GUI | – | 105 ms | 252 ms | – | 456 ms | – |
| Autosave journal (GUI thread) | 27 ms | – | 0.49 s (50 dev) | **2.5 s** | – | ~10 s est. |
| Export (build_outputs) | ~6 s | 13 s | 55 s | – | 74 s | 17–22 min extrapolated at 20,000 wires |
| `plan_create_harness` | – | – | 200 pairs 1.3 s | – | – | 1,000 pairs **31.7 s** (quadratic) |

\*different project shapes (B and D used synthetic pinout-first projects of different density); compare ratios, not columns. Causes found: two full integrity checks per edit (A-8); the journal re-serialises everything (A-9); the legend rebuilds `all_connectors()` per harness connector (D9: `connector_family` 126 of 328 ms); export creates fresh openpyxl style objects per cell, 28,693 times for the flatsat (B-08); undo steps copy the whole harness, +1.4 MB per step (A-12).
Memory is stable (no leak seen over 200 edits and undos; RSS 203 to 231 MB at 150 to 300 devices).

### 3.8 Maintainability

- Two constants in `gui/strings.py` are defined twice and the second wins: `WAIVED` (the Problems panel shows the heading "Waived. The justification will appear in the DRC report." where the one word was meant) and `STEP_GENERATE` (Undo shows "Generate"). **Re-checked.** Neither ruff nor mypy catches it. (I had seen this earlier in the session and left it; it is now item 1 of the 1.8.1 list.) E-F2.
- `gui/main_window.py` is 4,588 lines in one class with 246 methods; `canvas.py` 3,555; `strings.py` 2,980 lines and 2,268 names in one namespace with 67 unused and 172 duplicated labels (E-F3, F7).
- `CLAUDE.md` has grown to 48 KB of changelog-like paragraphs (longest line 4,461 characters); it is loaded into every Claude Code session (E-F4). README has a 1,000-word Status section and the first screen is release history (F-13).
- Three of 46 timing tests fail on an idle machine at the default factor (CI sets 3): `test_stress_generates_fast` 11.0 s of 10 s, 224 ms vs 200 ms, 306 ms vs 300 ms (E-F1). The doc tells developers to run `pytest -m perf` alone, so they get red from machine speed alone.
- 42 of 116 requirements pass traceability on file existence only (E-F8). 47 functions above McCabe 15, four above 30 (`_build_harness`, `_system`, `check_locks`, `plan_device_import`); no complexity guard in the lint config (E-F6). Whole suite about 55 minutes.

### 3.9 Trust and adoption (F-11, C-16, C-17)

Packages are unsigned (SmartScreen); the licence is a placeholder (`LicenseRef-Proprietary`, D-02) inside a repository whose root carries GPL-3.0; `.deb` maintainer is `noreply@example.invalid`; no CPython/Qt third-party notices; no GitHub Action pinned by SHA; `windows-latest` unpinned in three workflows; transitive dependencies not locked; no dependabot/CodeQL. The README banner is honest; it is also a stop sign for a space programme.

---

## 4 Recommended plan

### 1.8.1, "trust fixes" (no new features; about 2 to 3 weeks)

Small, high-value, mostly S effort. Each has a clear test.

| # | Fix | Source |
|---|---|---|
| 1 | Remove the duplicate constants; add a test that no top-level name in `strings.py` is assigned twice and that none is unused | E-F2, E-F7 |
| 2 | `link-direction` and the proposal: same exemption as `direction-conflict` | B-03 |
| 3 | Integrity error and DRC rule for a box connector mated twice and a box pin wired by two harnesses; `plan_add_link`/`plan_create_harness` refuse or warn | A-1, B-01 |
| 4 | Token-based TX/RX counterparts and a warning on TX↔TX / RX↔RX "equal" pairs | F-01, A-10 |
| 5 | "Not checked" notes whenever a rule had nothing to evaluate; note for wires without an interface; placeholder line on the build sheet | B-04, F-03, F-06 |
| 6 | Verify a link harness against its link (`link_wire_mismatch`) | C-1 |
| 7 | `tabKeyNavigation=False` in `TableView`, Tab-walk tests that select a row | D3 |
| 8 | Confirm before replacing a library device; never lower an approval silently; `scan_folder` really never raises; contact parts travel with the device; connector-id derivation on rename | D4, A-4..A-7 |
| 9 | UTF-8 on stdout/stderr; Windows CI step with a non-ASCII project name; "Already up to date" exit 0; Outputs "Open" allow-list | C-4, C-5, C-7 |
| 10 | Older tools stop on a project that uses links (schema marker) | A-3 |
| 11 | `isolated` rule counts links; legend caching (edit under 100 ms at 150 devices); timing tests default factor 2 | F-09, D9, E-F1 |
| 12 | Doc corrections: the 6 stale claims and the merge-cleanly claim; CONNECT-TWO-CONNECTORS says current checks do not run on interface-less wires | F section 5b |

### 1.9, "make the Systems engineer role work and give every role an output" (about 6 to 8 weeks)

First connector in Add device; Pair by pin number / Paste a pairing; actionable Fix page (Waive/Approve); `connections.csv/.xlsx` and links in the block diagram and traceability; keep the person on the Next step page; hide engineering menu entries; wording pass; per-pin `direction`; configurable counterpart table; change-control identity switch; requirement IDs in outputs; `.gitattributes`/`merge-fix`; README cut to 60 lines plus a 10-minute tour; incremental integrity and background autosave; export style-object reuse and per-harness incremental export; single bundle rule; coax/twisted-pair shield ends; `plan_create_harness` in one pass.

### 1.10, "fit a real workflow" (about 3 months)

`import-links` (Excel wire list/ICD into links, with dry run); CLI for links/edits/library with `--json` and `generate --check`; real part-catalogue importer; library versioning and lock; signing, SBOM, licence decision, pinned actions, hashed lock; release workflow gated on green CI and vulnerability scan; tamper-evident change log and review workflow; test-result import and hipot sheet; power/mass roll-up; requirement exchange (CSV first); measure the roles with 3 to 5 users; S4 guided first project; cross-strap matrix. Design (no code) of buses and variants.

### 2.0, model changes

Bus topologies (trunk and stubs), variants (FM/EM/EQM), formboard drawing, ReqIF, file format v2 with Link as a first-class carrier of current/class/requirement.

---

## 5 New features, prioritised

| Priority | Feature | Problem it solves | Effort |
|---|---|---|---|
| **Must** | Connector occupancy view and rule ("who plugs into J01, which pins, by which harness") | The invisible double-wiring of 3.1 | M |
| **Must** | Import of an existing cross-device wire list / ICD into links | Teams have Excel; first ten minutes decide adoption | M |
| **Must** | Connection list / ICD workbook for the Systems engineer | The role has no deliverable | M |
| **Must** | Bus topologies (CAN, 1553, SpaceWire, RS-485 multi-drop) | The flatsat models one CAN bus as eight point-to-point links | L |
| **Must** | CLI for links and the 1.8.0 edits, `--json`/JUnit output | CI cannot reproduce the headline workflow | M |
| **Must** | Real part-catalogue import | The library holds 24 example connectors and 2 wires, all pending | M |
| Should | Link↔harness sync with diff preview and drift warning | Drift today is silent | M |
| Should | Cable object with N conductors (one cut, one BOM line) | BOM/mass 2x/4x for pairs | M |
| Should | Variants FM/EM/EQM | Same design, different devices | L |
| Should | As-built and deviation records; hipot sheet and result import | AIT records what was built | M to L |
| Should | Review and sign-off workflow with named roles | QA wants evidence | M |
| Should | Tamper-evident change log | Audit trail rests on Git alone | M |
| Should | Power budget and system mass roll-up | Systems engineer | M |
| Should | Mirror links on redundant copies | "2 of these devices" does nothing for link-based designs | M |
| Should | Team presets (role, library folder, profile, required release roles) | Programme-wide setup | S to M |
| Should | Library governance: versions, diff on replace, File column, index | Shared folder is unprotected | M |
| Should | Contact-vs-wire gauge rule; voltage drop as % of rail; pyro loop resistance | Gaps in sizing rules | S to M |
| Could | Formboard/nailboard drawing; cross-strap/FDIR matrix; subsystem view of the diagram; WireViz YAML import; pin role column and bulk role; pinout comparison view | | M to L |
| Quality tooling | `python -m tools.quality` (one command for all gates), GUI coverage gate, module→test→requirement map, mutation testing on `generate`, `verify`, `links`, property tests for `propose_pairs` | | S to M |

**Do not build** (F): 3D routing/MCAD integration; a network library server or real-time multi-user editing (contradicts the offline guarantee and the owner's decision; fix merge pain and library locking instead); a schematic editor (KiCad is the pinout source); auto-creating connections or harnesses (the owner's own rule, and F-01 shows why); vendor machine data (KBL/VEC) and catalogue scrapers.

---

## 6 The 23 workshop points: what 1.8.0 actually delivers

Consolidated from D (what the GUI does) and F (what code and documents do). D = delivered, P = partly, N = not.

| # | Point | Status | Remaining gap |
|---|---|---|---|
| 1 | New devices get their own name | D | Docs say `GYRO3`, the dialog gives `GYRO1` |
| 2 | "units" → "devices" | P | Inspector heading "UNIT", 14 lines of `drc` output, a CSV column; files by design |
| 3 | "Problems" notification | D (Systems) / P (Electrical) | Counts disagree |
| 4 | Export fails | P | Two causes explained; a third found (links-only project); real cause still unknown |
| 5 | What is RTN | D | `Class` blank for RTN |
| 6 | Edit the connector | D | GUI only; tab labels truncated at 1440 px; no per-pin lock |
| 7 | More harness editing (twisting) | P | Group kinds yes; lay length, sleeving placement, branch geometry not modelled |
| 8 | Length and gauge | D | GUI only |
| 9 | Connector visible on the harness in the diagram | P | Boxes overlap neighbours and clip |
| 10 | Power on the pins | P | Role in the Link window only; no voltage/current per pin |
| 11 | Connect chosen connectors, no signal type | D | |
| 12 | Labelled pins propose the pinout | P | Fails on vendor-style names and unnamed pins |
| 13 | Any connector to any, pin to counterpart | P | Gender/keying/pin count of the two connectors not compared |
| 14 | The user connects, the tool checks | D | The review is weak (3.1) |
| 15 | The user's pinout is not disregarded | D (links) / P (interfaces) | |
| 16 | Interfaces derived, not entered | P | Display only; not stored, not in any output |
| 17 | Subsystems in a library, blank project clean | D | |
| 18 | Separate library window | D | Does not fit 1024 px; Tab trap |
| 19 | Library for everyone ("kladow") | P | Shared folder works; no lock, silent overwrite; "kladow" unknown |
| 20 | Number of devices instead of chains | D | Naming mix `ID`, `ID-R`, `ID-3`; links not copied; no CLI |
| 21 | "Feed Sam's tool into Claude" | N | Not understood, nothing built |
| 22 | Too overcrowded; create harnesses simply | P / N | Systems role lean but dead-ended; Electrical layout crowded and clipped; not measured |
| 23 | Two user modes | D | No team preset; "Show everything" switches the role; Esc on the question stores Electrical |

Count: D 10, D/P 2, P 9, P/N 1 (point 22), N 1 (point 21, not checkable). **The central idea of the workshop, "pinout first, the tool checks", is built, but the checking is the weakest part (3.1).**

---

## 7 Documentation truthfulness (F)

About 55 verifiable claims checked, **6 wrong or stale**, none dangerous: CHEATSHEET says interface types live in `library/` (they are in `logical/`); CONCEPTS/FAQ "no engineering numbers from any standard" (profiles ship ECSS tables behind `config --apply-profile`); "two people merge cleanly" (false when both run Generate); README step 3 "opens on the Next step page" (Systems role only); a Getting Started excerpt with three lines instead of four; the `import-pinout` hint "Generate again" in a project without interfaces. Jargon without a glossary entry: FDIR, EEE, lay length, formboard, ferrule, hipot. Volume is the problem: 98 documents in `docs/`, about 254,000 words (323,000 with all Markdown), README 2,550 words; there is no 10-minute tour, which matters because the workshop's complaint was "overwhelming".

---

## 8 Open questions to the owner

1. **"kladow"** (point 19) and **"Sam's tool"** (point 21): what are they, where are the files? They block closing two points and may change the library design and the import format.
2. **The export failure** of the workshop (point 4): which window, project, message?
3. Which **deliverable does each role hand over** (connection list/ICD vs build sheets)? Decides the Systems rail and F-02.
4. **Standards and QA process**: ECSS-E-ST-20-05 and Q-ST-70 are not in the compliance set. Decides rule priorities and the sign-off design.
5. Do **FM/EM/EQM variants** and as-built records matter? Decides the file-format plan.
6. **Licence and signing** (D-02) and budget: blocks any distribution outside the owner's circle.
7. **Who tests?** Nobody has watched the GUI on a real display, and nothing measures ease of use; every claim about points 22 and 23 depends on it.
8. Two earlier role defaults: should the Systems rail hide Home, Drawings and Outputs, and should a stored 1.7.0 Simple choice become Systems engineer?

*Answered by the owner on 2026-10-28 (D-181): questions 1 and 2 are discarded, question 3 follows the recommendation (Systems engineer: connection list; Electrical / AIT engineer: build workbook, drawings and lists), question 7 is later. Questions 4, 5, 6 and 8 are still open.*

---

## 9 What this audit could not check

- **No real display, GPU, HiDPI or screen reader.** The GUI was driven offscreen with screenshots; Tab behaviour was measured with synthetic key events.
- **No Windows, no installers built, no clean-machine install**, no vulnerability scan (needs network), GitHub-side settings (branch protection, secrets).
- **Sandbox ran as root on Python 3.13**; CI uses Ubuntu 24.04, Python 3.12 and a time factor of 3. Four permission-error tests skip as root, and three timing tests fail here that may pass in CI.
- All timings were taken on a 4-CPU machine shared by up to six jobs (up to about 2x inflated); ratios are reliable.
- Commercial-tool comparisons are general knowledge, labelled unverified. The ECSS standards were not independently read beyond the repo's own requirement files.
- Imports (parts, build data, lengths) were fuzzed by C but not by A/B beyond the shipped templates; redundant-copy and number-of-devices only through the shipped examples.
- I re-checked three findings myself (box connector shared, TX↔TX pairing with no finding, duplicate constants); the rest rest on the auditors' reproductions. Their scripts are kept under `audit-1.8.0/<letter>/` so each can be re-run.

---

## 10 Where the detail is

The six auditor reports (about 210 KB of findings with evidence, repro steps and recommendations, IDs A-1 to F-19 as cited above) are not part of the repository, to keep the documents small; the IDs in this report refer to them. The fixes made for 1.8.1 are listed in `CHANGELOG.md` (section *Unreleased* until 1.8.1 is published) and decided in D-177.

What was and was not fixed in 1.8.1: the items of section 4 "1.8.1" were done except A-3 (schema marker, a file-format decision), C-2 and C-3 (release workflow), and B-13/B-11/B-20 (they would change the written pinout tables); everything from 1.9 onward is open.
