# Release 1.10 plan: four small, owner-chosen changes

Status: plan, written 2026-10-28 on top of 1.9.0 (published the same day); built in release 1.10.0 (D-182 to D-185), published on 2026-10-29. Where the build differs from the plan, `W2 as built` below and D-184 say how.
Source: the open choices of D-179 and the owner's "go" of 2026-10-28 for shield ends, the cable-pin
Signal column, requirement IDs in the outputs and the split of `CLAUDE.md`. Decision D-182.
The facts below were read from the code on 2026-10-28 (file and line references are to that tree).

## Aim

Make four things true that today are not, without touching the file format and without a new design rule:

1. A coax cable's shield is bonded at both ends unless a person says otherwise.
2. The `Signal` (and `Interface`) cells of a cable connector in `pinouts.csv` are filled.
3. An interface's requirement ID can be read in the wire list and the traceability matrix.
4. `CLAUDE.md` is short enough to be worth loading into every session.

Anything else from the "1.10" list of `docs/AUDIT_1.8.0.md` section 4 (`import-links`, a command line with
`--json`, a part-catalogue importer, library locks, signing, buses, variants ...) is **not** in this plan. It stays
in the backlog until the owner picks it.

## What stays fixed

- Schema version 1; no new model field. Every output that a change below does not name keeps its bytes.
- No new design rule; the rule count stays 39 (`docs/RULES.md` is regenerated only if a message changes).
- A released harness never changes (the release freeze already holds).
- No tag and no merge by the agent. Each workstream is its own branch and pull request.
- Nothing here is a statement of compliance.

## W1 The split of `CLAUDE.md` (documents only, first, no risk to outputs)

Facts: `CLAUDE.md` is 50,117 bytes. The largest sections are the GUI layout (10.7 kB), the UI design rules
(4.8 kB), Commands (4.2 kB), Connections (3.7 kB), Editing wires (2.6 kB) and Harness and connector editing
(2.8 kB). A precedent exists: the former status text was moved word for word to `docs/developer/CLAUDE_HISTORY.md`.
No test or tool parses the sections of `CLAUDE.md`. `tests/test_docs_links.py` checks the links of the file and of
everything under `docs/` (so moved text is checked too); `tools/gen_scf.py` lists the file by name and tolerates a
smaller one. Three comments name "CLAUDE.md, UI design rules" (`tests/test_theme_scan.py:4`,
`tests/test_audit_medium_b.py:156`, `gui/timing.py:14`).

Plan:
- `CLAUDE.md` keeps Status, Commands, Conventions and one line per area that says where the rest is. Target:
  about 15 kB.
- The area sections move **word for word** into `docs/developer/agent/` (`core.md`, `gui.md`, `outputs.md`,
  `change-control.md`, `ui-design-rules.md`, `examples-and-docs.md`), each with a short heading that says when to
  read it. No text is rewritten, so nothing can become untrue by the move.
- The three comments are updated. A test (small) checks that every `docs/developer/agent/*.md` file is linked from
  `CLAUDE.md`, so a file cannot be forgotten.
- Not verified: whether Claude Code loads a `CLAUDE.md` of a subfolder on demand. The plan does not depend on it;
  it uses plain "read this file when you work on X" lines.

Acceptance: `CLAUDE.md` under 20 kB; the moved sections are byte-identical to the old text (checked by a script
that concatenates them back); docs tests green.

## W2 Two output changes, together, because both break the byte-identical baseline

### W2a The cable-pin Signal and Interface cells

Facts: `pinouts()` (`core/outputs/tables.py:199`) writes `p.signal or ""` for the Signal cell (`:160`), the
pin's own field. Generation makes cable pins without a signal or an interface (`core/generate/engine.py:597`);
only box pins get them (`:530`). So every generated cable row has an empty Signal and Interface, while the box row
has them. Of the shipped and fixture projects only `mini3` W001 (hand-built) has cable-pin signals. The verifier
recomputes the rows (`core/outputs/verify.py:1431`), so it needs the same change.

Plan: derive the cells in `pinouts()` from the wire that ends on the pin (the `attached` map at `:201` already
knows the wires): Signal and Interface of the wire. A pin with wires of two different signals shows both, joined
with ` / `; a spare pin stays empty; a signal a person typed on the pin wins over the derived one. No model change.

Effect: every `pinouts.csv` of a generated harness changes (golden `mini3` W002 and the generated outputs of
`sat15` and `flatsat`); `mini3` W001 does not. `tests/test_audit_outputs_medium.py:393` also reads these cells.

### W2b A sparse `Requirement` column

Facts: `InterfaceInstance.requirement_id` exists (`core/model/logical.py:65`) and is written only to
`system/export.json`. `traceability.csv` and `wirelist.csv` do not carry it; the `Requirement` column of
`drc_findings.csv` is the *standard* requirement, a different thing. Other sparse columns follow one pattern
(`uses_emc_classes`, `uses_wire_text`, `uses_strip_lengths`, `core/outputs/tables.py:62-71`): the column appears
only when something in the project uses it.

Plan: `uses_requirements(project)` = any interface has a requirement ID; if so, `wirelist.csv` and
`traceability.csv` get a last column `Requirement`. `connections.csv` gets none: a connection has no requirement
ID of its own (making a link a carrier of one is a file-format change, left to 2.0). The verifier's hard-coded
column offsets for the wire list (`verify.py:409-429`) and the traceability header (`:1810-1811`) are extended
with a mutation test each.

Effect: the shipped examples `first-steps`, `minimal-satellite`, `small-satellite` and `flatsat` have requirement
IDs, so their wire lists and traceability matrices change. A project without any requirement ID is unchanged.

### The baseline problem both create

`python -m tools.output_hashes --check docs/ui/OUTPUT_HASHES_1.2.0.json` compares the files of the examples with
release 1.2.0. The tool already has exceptions for things that were added later (the version string, the build
workbook, the rule count). W2a and W2b are real differences in kept file kinds. Options:

- (a) Add two more exceptions to the 1.2.0 comparison. Keeps one baseline, but the exception list grows.
- (b) **Recommended.** Make a new stored baseline `OUTPUT_HASHES_1.10.0.json` from the finished 1.10 tool, keep the
  1.2.0 file as history with a note, and point the test at the new file. From 1.10 on, the check says "unchanged since
  1.10.0". The decision records why the 1.2.0 guarantee ends here and which differences caused it.

Acceptance for W2: both changes in one pull request with the verifier, mutation tests, `docs/OUTPUTS.md`, the
changelog (a clear "output change" entry that lists the two files), the goldens regenerated with the repo's tools,
and the baseline decision recorded. A project without connections, without requirement IDs and without generated
cable pins is byte-identical to 1.9.0 apart from the version stamp.

## W3 Shield ends by kind (coax)

Facts: shield ends do **not** depend on the kind. `ShieldKind` and `ShieldEnd` are plain literals
(`core/model/physical.py:15-16`). Generation reads `generation.shield_end_a/b` once and gives **every** group
those ends; an unset value becomes `floating` with a "placeholder" note (`core/generate/engine.py:1028-1050`,
`config.py:71-72`). Manual groups use the same keys (`core/wires.py:440`). The four shield rules skip twisted
pairs and treat a coax like any shield: `shield-unterminated` (`core/drc/rules.py:408`), `shield-wrong-end`
(`:424`), `shield-bonding` and `shield-parts` (`core/drc/standard_rules.py:366-411`). In the shipped examples only
`flatsat` has shield groups: six harnesses with twisted pairs, one of them (W005) with the only coax; all groups
are `backshell_360` / `floating`. The fixtures `sat15` and `custom_device` have twisted pairs, all
`floating` / `floating`.

Meaning: a coax outer conductor carries the signal return and is bonded at both ends; with the project-wide
"360 degrees at one end, floating at the other" it is wrong for a coax, and the rules flag it (or, with the
settings unset, silently accept `floating`).

Plan (smallest change that is right):
- **Coax only.** When generation (and the manual regroup) builds a group of kind `coax`, both ends are
  `backshell_360`, whatever the project-wide grounding concept says. The person can still set the ends of a group
  by hand (the group edit already allows it), and a note in the plan says which rule produced the value.
- **Twisted pairs: no change.** They carry no shield, the rules already skip them, and a changed end would only
  rewrite saved harness files for nothing. The drawing may stop printing ends for them (decision at the start of
  W3, with the drawing diff in front of the owner).
- The rules are not changed. Their messages are read once to check that none still says "one end" for a coax.

Effect: the saved `flatsat` W005 (its shield group), its drawing text and possibly its design-rule findings. No
other shipped example, no fixture and no golden contains a coax group (checked by search), so the change is small
and local. Released harnesses are frozen and do not change.

Acceptance: a test with a coax and a twisted pair under every combination of the two settings; the flatsat diff
shown and explained in the pull request; the shield rules' documents (`docs/RULES.md`, CONFIG) say what a coax gets.

## Order, size and risk

| Order | Workstream | Size | Risk |
| --- | --- | --- | --- |
| 1 | W1 split of `CLAUDE.md` | small | none for the product; documents only |
| 2 | W3 coax ends | small | changes one example's saved harness and drawing |
| 3 | W2 Signal column and Requirement column | medium | changes kept output files; needs the baseline decision |

W2 goes last because it is the only one that moves the baseline; W1 and W3 can be reviewed independently.
Version: **1.10.0** (minor: outputs change). Preparation and publication follow `docs/RELEASE.md` as for 1.9.0;
the tag stays the owner's step. Published on 2026-10-29 as the tag `v1.10.0` on commit `6f87980` (release workflow run 40920309052; `compliance/SIGNOFF.md`).

## Questions for the owner (defaults in bold; the plan is built on the defaults)

1. Coax: both ends `backshell_360` by default, **yes**? This is an engineering statement, not a software one:
   say no if your RF practice differs (for example 360 degrees at one end and a capacitive or floating other end).
2. The cable-pin Signal and Interface cells: **fill them for every generated harness** (outputs change), or
   keep the old empty cells behind a setting?
3. The `Requirement` column: in the **wire list and the traceability matrix only**, or also in the build sheet and
   the labels?
4. The baseline: **new stored baseline from 1.10 (option b)** or more exceptions to the 1.2.0 file (option a)?
5. Twisted pairs: **leave the saved ends alone**; print "no shield" in the drawing instead of the ends, **yes**?

## W2 as built

Built as planned with three small differences, recorded in D-184: values are joined with `;` (not ` / `); the
`Requirement` column sits after `EMC class` in the wire list and after `Routed` in the traceability matrix (not
last); the shipped examples have no requirement IDs, so only their pinout tables and per-harness workbooks changed
(90 of 612 files), and the baseline `OUTPUT_HASHES_BASELINE.json` was renewed from the finished tool.
