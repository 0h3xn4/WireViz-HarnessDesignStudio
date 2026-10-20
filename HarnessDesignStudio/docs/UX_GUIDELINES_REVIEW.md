# Review against the UX/UI guidelines (October 2026)

> **Historical (D-150).** This page describes the editor of versions 1.0.0 to 1.2.0 under the IBM Carbon design system and IBM Plex fonts, which the UI overhaul replaced in version 1.3.0 (published 2026-10-20): the tokens, themes and fonts are now in `gui/theme/` (Inter and JetBrains Mono, light and dark; see [`DESIGN.md`](DESIGN.md), [`ui/UI_OVERHAUL_PLAN.md`](ui/UI_OVERHAUL_PLAN.md) and [`ui/BEFORE_AFTER.md`](ui/BEFORE_AFTER.md)). References to Carbon, Plex, the toolbar and the old tabs below record what was decided then; they are not the current design. The statuses (what the tool does about each guideline) were not re-checked for 1.3.0, except that the files named as evidence still exist.

> **Newer standard.** This page reviews the first guideline set (*UX/UI Guidelines for the Harness Tool*), and its statuses below are still true for that set. Later in October 2026 the owner gave a second document, the "UX/UI Standard: Harness Design Studio", and approved an audit of the editor against it; the editor was then rebuilt (version 1.1.0), and again in version 1.3.0. That audit, with an issue-by-issue **Build status** (done, partly, not done, needs owner decision), is [`ux-audit.md`](ux-audit.md); the design rules the rebuild follows are in [`DESIGN.md`](DESIGN.md). Where the two disagree about how the window looks (for example "Problems panel", "navigation for large harnesses", the palette or the tab layout), read those two pages.

The owner's document *UX/UI Guidelines for the Harness Tool* is written for a WireViz-based tool: YAML on one side, a live diagram on the other, Monaco as the editor, Graphviz for drawing. This tool is different by design: it is **model-first** (the design is a folder of JSON files edited through a diagram editor, tables and dialogs; generated harnesses are never edited by hand) and **clean-room** (WireViz YAML is an export format only; WireViz and Graphviz are not used). So some guidelines apply as written, some apply in a different form, and some do not apply. This page says which, with the evidence. Done in this change: marked **new**.

## Offline and closed operation

| Guideline | Status | Evidence |
| --- | --- | --- |
| No background network use; works with networking off; an automated test checks it | done | `tests/test_offline.py`, self-test under `unshare -n` (`docs/RELEASE.md`) |
| Downloads only with consent, with checksums, a diff and rollback | not applicable today: the tool has no download feature. If one is ever added it must follow this rule; `harness import-parts` already works from files the user provides | `docs/SECURITY.md` |
| Component library by download or file import, with version, date and source visible | partly: file import with a per-row preview exists (`harness import-parts`, the editor's import); the library name and version appear in the provenance file (**new**). **New (D-133):** the library record has `source` and `date`; `harness library` shows and sets them, `harness import-parts` records the file name and checksum, and the provenance file and the editor show them | `docs/IMPORTS.md`, `tests/test_provenance.py`, `tests/test_library_source.py` |
| Everything else bundled locally: editor component, Graphviz, fonts, icons, JSON Schema | fonts **new** (IBM Plex Sans and Mono, SIL OFL, D-132); JSON Schema generated from the model, **new** (`harness schema`); Monaco and Graphviz are not used | `tests/test_fonts.py`, `tests/test_schemas.py` |
| Help and examples built in | done | F1 guide, `harness new`, `harness templates`, **File > New project from an example** (**new**) |
| No AI features; autocomplete only from schema and local library; deterministic, traceable checks | done: the tool contains no language model and every rule is deterministic; each finding now names the requirement it serves (**new**) | `docs/RULES.md`, `tests/test_drc.py` |

## Foundation

| Guideline | Status | Evidence |
| --- | --- | --- |
| IBM Carbon as the design system | **new**: Carbon White and Gray 100 colour tokens (status tones darkened for AA text contrast on every surface), square corners, Carbon-style tabs and fields, IBM Plex type. The editor is Qt, so it is styled like Carbon and does not use Carbon's component library. D-132 | `tests/test_tokens.py`, `docs/ux/qt/` screenshots |
| Undo and a command palette | done | Ctrl+Z, Ctrl+Y, Ctrl+K |
| Provenance on every output (tool version, WireViz version, input, settings, library version) | **new**: `system/provenance.json` with tool version, model hash, project, library name and version, every settings file with its placeholder flag and a hash of its values, and the design counts; every file also carries the stamp. "WireViz version" does not apply: WireViz is not used. The model hash identifies the input exactly | `tests/test_provenance.py`, `docs/OUTPUTS.md` |
| Error messages that point to the exact line and say how to fix it | **new** for project files: the message gives file, line and column (or the line of the set-aside object) and never quotes content. YAML does not apply: project files are JSON | `tests/test_error_locations.py` |
| Templates as empty states | **new**: File > New project from an example, and the empty-state text offers it | `tests/test_gui_journeys.py` |

## Editor experience and harness features

| Guideline | Status | Evidence |
| --- | --- | --- |
| Split view: YAML editor and live diagram | not applicable by design: there is no YAML to edit. The equivalents are the live diagram, the interface table (the Interfaces tab) and the project tree, which all update together. A text-first mode would be a different product; not recommended | `docs/UX.md` |
| Two-way linking between diagram and text | in the form this tool has: a finding, a table row and a project tree row select the object in the diagram (Show) and the reverse. There are no YAML lines to link | `tests/test_gui_drc.py` |
| Schema-driven editing (autocomplete, inline validation, hover documentation) | **new** for people who edit project files by hand: `harness schema FOLDER` writes JSON Schemas made from the model and an editor settings fragment. No Monaco | `docs/FILE_FORMAT.md` |
| Problems panel with severity and requirement ID, linking to the offending object, highlighted in the diagram | **new**: the card shows the requirement ID(s) as text; `drc_findings.csv` has a `Requirement` column; Show selects the object | `tests/test_gui_drc.py`, `docs/OUTPUTS.md` |
| Colour does not carry meaning alone | done: signal classes also differ by a picture on the link (D-140; this replaced the one-letter chips), line weight and the key under the diagram; redundancy is dashed; changes are dotted halos; wire colours are drawn on a dark outline and also written as IEC 60757 codes, so a greyscale print loses nothing (D-141, REQ-OUT-03 reworded; an earlier version of this review said wire colours were never drawing colours); separation under colour blindness is tested | `tests/test_tokens.py`, `core/outputs/drawing.py`; D-140 and D-141 in [`DECISIONS.md`](DECISIONS.md) |
| Navigation for large harnesses: zoom, pan, search, filter by connector, signal class or bundle | zoom, pan, search (Ctrl+K), a text filter in the interface table and the minimap exist. **New:** a filter that shows one signal class, one connector or one bundle (harness) and fades the rest (it was in a toolbar; since 1.3.0 it is the *Show* filter in the corner of the Model tab bar, D-151) | `tests/test_gui_filters.py` |
| Component library picker with ESCC part data | the picker exists; **new:** it shows description, maker, pins, specification, approval and ratings. No ESCC part data is bundled (the tool ships example parts only, marked as such); the owner's approved parts list and any ESCC data come in through the import | `tests/test_gui_journeys.py` |
| Revision diffs highlighting added, removed and changed items | done | `tests/test_gui_changes.py` |
| Print-ready A3/A4 output with a title block | done (title block fields still wait for D-15) | `docs/OUTPUTS.md` |

## What I need from the owner

Whether filtering the diagram by connector or by bundle is wanted (it is not a large change).
Nothing is open from this review.
