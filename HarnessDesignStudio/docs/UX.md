# UX specification (gate for M2)

> **Historical: the design record of M2, partly superseded twice.** The IBM Carbon colours, the IBM Plex fonts, the palette, the bottom tabs and the wireframes below describe the editor of 0.1.0 to 1.0.0; the UI overhaul of version 1.3.0 (D-150, published 2026-10-20) replaced the look (tokens in `gui/theme/tokens.py`, Inter and JetBrains Mono, light and dark themes) and the window (a navigation rail, one top bar, a Problems panel). **For the current design read [`DESIGN.md`](DESIGN.md), [`ui/UI_OVERHAUL_PLAN.md`](ui/UI_OVERHAUL_PLAN.md) (section 4 maps every old tab, menu and dialog to its new place) and [`ui/BEFORE_AFTER.md`](ui/BEFORE_AFTER.md); for the behaviour, the [user guide](guide/USER_GUIDE.md).** This page is the specification the editor was first built from. In October 2026 (version 1.1.0) the editor was rebuilt against the owner's "UX/UI Standard" ([section 13](#13-redesign-against-the-uxui-standard-october-2026), [`ux-audit.md`](ux-audit.md#build-status)), and in version 1.3.0 again ([section 14](#14-the-ui-overhaul-version-130-october-2026)); versions 1.4.0 to 1.7.0 added editing features and a simple workspace to that window ([sections 15 to 17](#15-the-ait-feedback-version-140-october-2026)); sections 4, 5, 7 and 8 below describe the M2 design and are kept as the record. Two earlier decisions changed what the diagram looks like: **D-140** replaced the one-letter chips on links by pictures (and added routing, focus and connector pictures), and **D-141** made the harness drawing a wiring diagram in which wires are drawn in their wire colour (the old rule "wire colours are text only, never drawing colours" no longer holds). The wireframes below show the earlier look. The pictures of the real editor in [`ux/qt/`](ux/qt/02-guided-main.png) and in [`ui/screenshots/after/`](ui/screenshots/after/) show the current window, not the wireframes; the screenshots in `ux/screens/` are of the prototype (see [`ux/screens/README.md`](ux/screens/README.md)). See [`DECISIONS.md`](DECISIONS.md) for D-140 and D-141.

## Contents

- [1. Targets (from the spec) and how they are checked](#1-targets-from-the-spec-and-how-they-are-checked)
- [2. Personas](#2-personas)
- [3. The ten journeys](#3-the-ten-journeys)
- [4. Information architecture](#4-information-architecture)
- [5. Wireframes](#5-wireframes)
- [6. Interaction rules ("prevent, then explain")](#6-interaction-rules-prevent-then-explain)
- [7. Design system](#7-design-system)
- [8. Mapping to the M2 implementation (Qt)](#8-mapping-to-the-m2-implementation-qt)
- [9. Usability test plan (you run it; findings become priority bugs)](#9-usability-test-plan-you-run-it-findings-become-priority-bugs)
- [10. UX review log (my own walkthrough, as the process requires)](#10-ux-review-log-my-own-walkthrough-as-the-process-requires)
- [11. Questions for you (please answer or mark "you decide")](#11-questions-for-you-please-answer-or-mark-you-decide)
- [12. Qt editor review log (M2 implementation)](#12-qt-editor-review-log-m2-implementation)
- [13. Redesign against the UX/UI Standard (October 2026)](#13-redesign-against-the-uxui-standard-october-2026)
- [14. The UI overhaul (version 1.3.0, October 2026)](#14-the-ui-overhaul-version-130-october-2026)
- [15. The AIT feedback (version 1.4.0, October 2026)](#15-the-ait-feedback-version-140-october-2026)
- [16. A harness from nothing, and a blank project that says where to start (versions 1.5.0 and 1.6.0)](#16-a-harness-from-nothing-and-a-blank-project-that-says-where-to-start-versions-150-and-160)
- [17. Build sheets, build data and the simple workspace (version 1.7.0)](#17-build-sheets-build-data-and-the-simple-workspace-version-170)
- [18. Connections between connectors (after 1.7.0, not released)](#18-connections-between-connectors-after-170-not-released)

Status: **approved by the owner; the Qt editor is implemented (section 12), was rebuilt in October 2026 (section 13) and again for version 1.3.0 (section 14), and gained the editing features of versions 1.4.0 to 1.6.0 (sections 15 and 16) the build data and the simple workspace of version 1.7.0 (section 17) and, after 1.7.0 and not released, the connections between connectors (section 18).** The prototype below was the review gate. The clickable prototype (`prototype/index.html`, open it in any browser, offline) implements the journeys below with mock data, and automated browser tests (`tests/test_prototype.py`) verify that the journeys really work. Screenshots of the prototype are in `docs/ux/screens/`.

This document is the contract for the editor in M2. Where the prototype and this text disagree, this text wins; tell me which is wrong.

## 1. Targets (from the spec) and how they are checked

| Target | How it will be measured |
| --- | --- |
| First-time systems engineer builds a 5-unit diagram and generates harness plans in under 15 minutes, using only in-app guidance | Timed usability test, task T1 (section 9) |
| At least 90% success on core tasks; SUS of at least 80 | Usability tests T1 to T8; SUS questionnaire |
| No core task needs the manual | Observer counts manual/glossary opens during tests (glossary and the tour are allowed, the manual is not) |
| Never lose more than the last few seconds of work | Autosave every change to a recovery journal; soak and crash-injection tests (M2 acceptance) |
| Feedback within 100 ms; progress for anything over 1 s; nothing blocks the UI | Automated timing tests on the stress project |
| WCAG 2.2 AA, colour-blind safe, keyboard only, scaling 100 to 200% | `tests/test_tokens.py` (contrast, colour-blind separation), prototype tests at 200%, manual screen-reader pass in M7 |

## 2. Personas

| | Dana, systems engineer | Sam, software engineer | Elena, harness (EE) engineer | Rui, reviewer / AIT technician |
| --- | --- | --- | --- | --- |
| Goal | Define devices and interfaces, get a harness plan she can trust without learning pin allocation | See which buses and discretes reach which device, with exact signal names | Own the physical truth: connectors, pins, wires, shields; release drawings | Check plans against the design; use them for continuity and isolation tests |
| Knows | The architecture, ICDs in spreadsheets | Protocols and signal names; not wire gauges | Everything physical; wants speed and control | Reads drawings; knows test procedures |
| Fears | Making a wiring mistake she cannot see | Stale or wrong documents | Tool hides or overrides her decisions | Printed sheet differs from the model |
| Mode | Guided | Guided, table view | Expert | Read-only views, outputs |
| Needs from the tool | Only valid actions; explanations; a to-do list | Search, filter, cross-highlight | Locks, overrides kept on regeneration, full detail | Revision, model hash and status on every sheet; stale warnings |

## 3. The ten journeys

Each journey lists the steps, what the tool must do to prevent mistakes, and the success criterion. The journeys are unchanged; where they name the palette, the bottom panel or the Properties panel, the same step is now done in the project tree or the Add menu, the Checks area or the Problems panel, and the Inspector (see sections 13 and 14 and the user guide). "P" marks what the prototype demonstrates; the test name is in `tests/test_prototype.py`.

**J1. First run and tour (Dana).** Opens the app, sees a sample project (mini3) and a 5-step tour (palette, canvas, connecting, problems/to-do, generate) that she can skip or replay from Help. Success: she can name the next action without reading anything else. *P: `test_j1_*`.*

**J2. Build the diagram (Dana).** Adds five devices from the palette (computer, power unit, wheel, star tracker, transceiver), drags them into panel A or B (zone follows position), renames them. New devices never land on top of others; IDs and names validate as typed (duplicates, format); empty state says "Add your first device from the palette on the left." Success: 5 devices in under 5 minutes. *P: `test_j2_*`, `test_new_units_never_overlap_*`, `test_live_validation_of_ids`, `test_dragging_a_unit_changes_zone`.*

**J3. Connect devices safely (Dana, Guided mode).** Picks an interface type, clicks the first device (it is marked FROM), then the second. Devices that cannot take that type are greyed out and say why in visible text under the device ("No free CAN connector"), not only in a tooltip; if no device can, the hint says so. The tool picks the connectors and marks them "Auto" until confirmed. Success: wrong connections are impossible, not just reported. *P: `test_j3_*`, `test_connect_mode_marks_source_*`.*

**J4. ICD table and import (Dana, Sam).** Switches to the table view (always in sync with the canvas), edits names, chain, current, requirement ID inline, filters by text. Imports a CSV/XLSX with column mapping and a preview that lists every row's status; nothing changes until she confirms; the import is one undo step. Success: 6 rows with 4 problems show exactly which rows fail and why. *P: `test_j4_*`, `test_import_*`.*

**J5. Redundant chain (Dana).** Selects a device, clicks "Create redundant copy": a copy appears with mirrored names (`-R`), dashed lines and a REDUNDANT label. Where it would connect to a nominal device (a cross-strap), a warning appears with a one-click fix ("Connect to a redundant copy of PCDU-A") or a waiver that needs a written justification. Success: two clicks produce a clean redundant chain. *P: `test_j5_*`, `test_cross_strap_fix_*`.*

**J6. Problems, to-do and Explain (Dana, Rui).** The bottom panel shows Problems (what is wrong, why it matters, how to fix, one-click fix when safe) and a to-do list ("1 device is not connected", "2 auto-filled assignments to review", "plans out of date"), each item clickable. Every generated item has a plain-language "Explain". Success: she can reach "no problems, plans verified" by following the list alone. *P: `test_j7_*`, explain dialogs.*

**J7. Generate, verify, regenerate (Dana, Elena).** "Generate" first shows what will be created; progress is cancellable and cancelling leaves nothing behind; an independent check runs and its result and the model hash are shown. Editing the model afterwards marks the plans Outdated and blocks release. Regeneration first reports "keeps N locked pins, changes M plans" and applies nothing until confirmed. *P: `test_j10_*`, `test_regeneration_report_*`, `test_generate_can_be_cancelled_*`.*

**J8. Expert refinement (Elena).** Switches to Expert mode (data is unchanged): connectors appear on the devices, ports face the gap between panels, parts are chosen from the library list, auto-filled values are confirmed, pins are locked. Only valid ports are selectable; busy or wrong-type ports say why. Success: she completes a manual connector assignment without leaving the canvas. *P: `test_j3_expert_*`, `test_j9_modes_*`.*

**J9. Software engineer: what reaches my device? (Sam).** Searches an ID with Ctrl+K, filters the table by device or type, selects an interface and sees its signals, both ends and requirement ID; selection highlights across canvas, table and harness list. Success: answers "which signals reach OBC-A.J01?" in under 30 seconds. *P: partly (`test_j8_command_palette`, table filter); cross-highlighting is specified in section 5 and built in M2.*

**J10. Release, change log, diff (Elena, Rui).** Releasing asks for a mandatory comment, is blocked while plans are outdated or the verifier reports errors, locks the harness (greyed controls, lock badge) and stores a baseline. Rui sees status, revision and model hash on every sheet. Success: a released plan cannot be edited by accident. *P: release dialog and locking in `test_j10_*`; diff view is specified in section 5 and built in M6.*

### Cross-cutting safety net (every journey)
- **Delete shows what else goes** (interfaces, outdated plans), Cancel is the default button, and the result is undoable (`test_j6_*`).
- **Unlimited undo/redo**; one import or one regeneration is one step.
- **Autosave** on every committed change into a recovery journal beside the project (never design data in logs or outside the project folder); after a crash the app offers "Restore the last session" with a diff of what would be recovered.
- **Newer file / corrupt file / open twice**: read-only banner, recovery view listing every problem with a "Save salvaged copy" button, "already open elsewhere" dialog (core behaviour exists since M1).

## 4. Information architecture

This is the M2 layout. The window today has a navigation rail, one top bar, the areas with their tabs, a project panel and a Problems panel instead; see [section 14](#14-the-ui-overhaul-version-130-october-2026) (and [section 13](#13-redesign-against-the-uxui-standard-october-2026) for the window of 1.1.0 and 1.2.0).

```
Window
├─ Header: project name · Mode [Guided|Expert] · Undo/Redo · Search/commands (Ctrl+K) · Generate · Help · More (scale, theme, panel toggles)
├─ Left: Palette ── Add a unit (templates) · Connect with (interface types, with category icon) · Import
├─ Centre: Block diagram (Select | Connect tools, zoom/fit, legend) ── zones as vertical lanes
├─ Right: Properties (unit | interface | harness | wire) ── Expert-only sections progressively disclosed
├─ Bottom tabs: Problems · To-do · Interface table · Harness plans (+ later: Outputs, Changes)
└─ Status bar: autosave state · selection · counts · model hash
```
Modes: Guided shows the logical layer only; Expert adds connectors, pins and parts. Switching never changes data (`test_j9_modes_do_not_change_data`).

Navigation rules: everything reachable by command palette; panels collapsible; below 1500 CSS px the secondary header controls move to "More", below 1150 px the Properties panel hides, below 800 px the palette hides, and when the window is under 640 px tall the bottom panel collapses to its tab bar (this is what makes 150% to 200% scaling usable, `test_panels_collapse_*`).

## 5. Wireframes

The wireframes show the M2 look. Pictures of the current editor are in [`ux/qt/`](ux/qt/).

### 5.1 Main window (see the prototype pictures [`ux/screens/02-guided-main.png`](ux/screens/02-guided-main.png) and [`04-expert-connectors.png`](ux/screens/04-expert-connectors.png))
```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│ Harness Design Studio  mini3  [Prototype]   [Guided|Expert] ↶ ↷  [Search Ctrl+K] [Generate] ? ⋯More │
├────────────┬──────────────────────────────────────────────────────────────┬───────────────────┤
│ ADD A UNIT │ [Select|Connect]  hint text            [Redundant copy][Del] │ PROPERTIES        │
│ + Computer │ ┌─ PANEL-A ─────────────┐ ┌─ PANEL-B ─────────────┐          │ ID    [RW1      ] │
│ + Power    │ │ ┌OBC-A────NOMINAL┐    │ │       ┌RW1────NOMINAL┐│          │ Name  [Reaction…] │
│ + Wheel    │ │ │ computer       ●────┼─┼──D IF-002──●          ││          │ Chain [nominal ▾] │
│ CONNECT    │ │ └────────────────┘    │ │       └──────────────┘│          │ Zone  panel-B (auto)
│ [P] Power  │ │ ┌PCDU-A───NOMINAL┐    │ │                       │          │ ── Expert only ── │
│ [D] RS-422 │ │ │                ●──P IF-001────●               │          │ J01 [part ▾] Auto │
│ [D] CAN …  │ └─────────────────────────┘ └─────────────────────┘          │                   │
│ IMPORT…    │ legend: P Power D Data … ── nominal  ╌╌ redundant  ▢ auto     │                   │
├────────────┴──────────────────────────────────────────────────────────────┴───────────────────┤
│ Problems (2) · To-do (4) · Interface table · Harness plans [verified]        ⤢ Taller ▾ Collapse │
│ ⚠ Warning  IF-001-R connects the nominal chain to the redundant chain                           │
│   why: a cross-strap means one failure could affect both chains…                                │
│   [Show] [Connect to a redundant copy of PCDU-A] [Waive…]                                       │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ All changes saved · Selected: RW1-R · 5 units, 4 interfaces · model ca4eee68                    │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Connecting (see [`ux/screens/03-connect-compatible-highlight.png`](ux/screens/03-connect-compatible-highlight.png))
```
 Palette: [CAN]●pressed     Hint: "Click the second unit. Valid ones are highlighted."
 ┌OBC-A────── FROM┐  (dashed primary outline)      ┌ST1──────NOMINAL┐ (greyed)
 │ source         │                                  └────────────────┘
 └────────────────┘                                  ✕ No free CAN connector   ← visible text
 If no unit qualifies, the hint turns into a warning: "No other unit has a free CAN connector. Pick another type…"
```

### 5.3 Harness plans tab with the verifier result (see [`ux/screens/09-harness-plans.png`](ux/screens/09-harness-plans.png))
```
 ✓ Independent check passed  model ca4eee68        W001: PCDU-A to RW1 (Primary power)   [Why does this harness exist?] [Release…]
 ID    Harness                 Chain     Status    Wire      Signal From          To          Gauge        Lock  [Why this pin?]
 W001  PCDU-A to RW1           ━━ nominal draft    W001-001  PWR    W001-P1 pin 1 W001-P2 pin 1 AWG — (rules pending) ☐
 W003  PCDU-A to RW1-R         ╌╌ redundant draft  W001-002  RTN    …
 Outdated state: badge "Outdated: the diagram changed", Release disabled with tooltip.
```
The real tab (M3/M5) adds the harness drawing preview, wire list, pinout, BOM and test tables as sub-tabs and the sheet preview below.

### 5.4 Harness drawing sheet (M5 target; print theme, A3 landscape)
```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│  P1 (J: PCDU-A.J01)   ──── W001-001 PWR  AWG ?  RD ───────────────  P2 (RW1.J01)         │
│  [pin face / table]   ──── W001-002 RTN  AWG ?  BK ───────────────  [pin face / table]   │
│       segment length ───────── 0.00 m (service loop +… from config) ──────────          │
├────────────────────────────────────────────────────────────────────┬────────────────────┤
│ Notes · parts list (approval status)                                │ TITLE BLOCK        │
│                                                                     │ project/harness/rev│
│                                                                     │ date/author/check  │
│                                                                     │ status · model hash│
└────────────────────────────────────────────────────────────────────┴────────────────────┘
```
Open question for you: do you have a company title block (D-15)?

### 5.5 Regeneration preview and release ([`ux/screens/08-generate-preview.png`](ux/screens/08-generate-preview.png), release dialog)
```
 Regenerate harness plans?   Regeneration will keep 1 pin lock and change 3 of 4 harness plans.
                             Nothing is applied until you confirm. Locked pins are never moved.   [Cancel] [Regenerate]
 Release W001?  Releasing freezes its IDs and locks it … Change comment (required) [____]        [Cancel] [Release]
```

### 5.6 Recovery and read-only states (M2, from M1 core)
```
 ┌ This project has problems ─────────────────────────────────────────────────────────┐
 │ 2 files could not be read. Everything else was loaded.                              │
 │ ✕ logical/units/power.json — not valid JSON (truncated). 3 interfaces depend on it. │
 │ The original folder is protected. [Save salvaged copy…] [Show details] [Close]       │
 └─────────────────────────────────────────────────────────────────────────────────────┘
 Banner: "Read-only: saved by a newer version of this tool." · "Open in another window: close it first."
```

## 6. Interaction rules ("prevent, then explain")

The rules still hold. Where rule 7 says a cell reads "rules pending", the editor now shows a **Pending** chip (icon, word and dotted pattern), and a rule that could not run shows a **Not checked** chip; see [`DESIGN.md`](DESIGN.md).

1. **Only valid actions are possible.** Compatibility is computed before the click; invalid targets are greyed with the reason as visible text, an `aria-label` and a tooltip.
2. **Auto-filled values are visibly marked** (dashed amber outline + "Auto" badge) until a person confirms them; the to-do list counts them.
3. **Messages have three parts:** what is wrong, why it matters, how to fix it (with a button when the fix is safe). No codes in the headline; the rule ID is in "Details".
4. **Destructive actions** (delete, regenerate over edits, release) show their exact impact first; Cancel is the default; all are undoable except release (which is reversible only by a new revision).
5. **Free text is validated as typed** (ID format, duplicates, numbers with devices) and the field keeps its value until valid; nothing is saved invalid.
6. **Long work** shows progress and a Cancel; cancelling leaves no partial result.
7. **Placeholders are loud.** Anywhere a value depends on unfilled rule configuration (e.g. wire gauge), the cell says "rules pending" and explains why, instead of showing a number.
8. **One-click fixes must make engineering sense.** The prototype review found a "fix" that made a redundant device nominal (defeating its purpose); fixes are only offered if a reviewer would agree with them.
9. **Cross-highlighting:** selecting a wire, signal or connector highlights it in the canvas, harness list, wire list and pinout at once (M2 for canvas, table and properties; M3 onward for plans).
10. **Terminology** is fixed: *device*, *interface*, *connector*, *pin*, *wire*, *harness*, *chain* (nominal/redundant), *plan* for the generated documents. The glossary and tooltips carry the domain terms.

## 7. Design system

**M2 values.** The colours, fonts, scale and icon notes in this section are the M2 design and are kept as the record; they are **not** the current values. Version 1.1.0 and 1.2.0 used IBM Carbon colours (White and Gray 100) and IBM Plex Sans and Mono (D-132) from `gui/tokens.py`. Since version 1.3.0 (D-150) the one token source is `gui/theme/tokens.py` (the files `gui/tokens.py`, `gui/theme.py` and `gui/fonts.py` are gone): Inter and JetBrains Mono (SIL OFL), a type scale of 11 / 12 / 13 / 15 / 18 / 22 px, spacing on a 4 px grid, a light and a dark theme tuned to WCAG 2.2 AA, and Lucide icons drawn in code. The current values and the reasons are in [`DESIGN.md`](DESIGN.md).

Single source of truth in M2: `src/harness_design_studio/gui/tokens.py` (no Qt import; since D-150 `gui/theme/tokens.py`). The prototype and the real GUI both read it, and `tests/test_tokens.py` enforces the accessibility numbers (it now reads the current tokens, so it no longer checks the M2 table below).

### 7.1 Colour tokens (WCAG 2.2 AA, verified by tests)
| Token | Light | Contrast on bg / surface-2 | Dark | Contrast on bg / surface-2 | Use |
| --- | --- | --- | --- | --- | --- |
| `bg` | `#FFFFFF` | n/a | `#12161B` | n/a | page background |
| `surface` | `#F4F6F8` | text 15.3 | `#1B2129` | text 14.0 | panels, cards |
| `surface-2` | `#E6EAEE` | text 13.7 | `#26303B` | text 11.6 | hover, selected row, table borders |
| `border` | `#6B7686` | 4.6 / 3.8 | `#8793A3` | 5.8 / 4.3 | control and panel outlines (graphics, 3:1) |
| `text` | `#1B1F24` | 16.6 / 13.7 | `#ECEFF3` | 15.7 / 11.6 | body text |
| `text-muted` | `#4A5565` | 7.6 / 6.3 | `#B4BDC9` | 9.6 / 7.1 | secondary text |
| `primary` | `#0B5CAD` | 6.7 / 5.5 | `#6DB3F2` | 8.1 / 6.0 | actions, selection, links |
| `on-primary` | `#FFFFFF` | 6.7 on primary | `#0A1A2B` | 7.8 on primary | text on primary |
| `focus` | `#6A2FD8` | 7.0 / 5.8 | `#B79BFF` | 7.9 / 5.8 | keyboard focus ring (3 px) |
| `error` | `#B3261E` | 6.5 / 5.4 | `#FF8A80` | 8.0 / 5.9 | errors, destructive actions |
| `warning` | `#8A5200` | 6.4 / 5.3 | `#F2B04A` | 9.6 / 7.1 | warnings, outdated |
| `success` | `#1B6E3C` | 6.3 / 5.2 | `#6FD39A` | 9.9 / 7.3 | verified, OK |
| `info` | `#0B5CAD` | 6.7 / 5.5 | `#6DB3F2` | 8.1 / 6.0 | information |
| `auto-fill` | `#7A5C00` | 6.3 / 5.2 | `#E6C34D` | 10.6 / 7.8 | auto-filled, not yet reviewed (also dashed) |
| `locked` | `#4A5565` | 7.6 / 6.3 | `#B4BDC9` | 9.6 / 7.1 | locked items (also lock icon) |
| `released` | `#1B6E3C` | 6.3 / 5.2 | `#6FD39A` | 9.9 / 7.3 | released items (also lock icon) |

All text and status colours meet at least 4.5:1 on every surface; borders, focus ring and category colours meet at least 3:1 (`tests/test_tokens.py`).

### 7.2 Signal categories: colour is never the only cue
| Category | Icon | Line weight | Light | Dark | Contrast light / dark (on bg) |
| --- | --- | --- | --- | --- | --- |
| Power | `P` | 3.5 px | `#B83014` | `#DDFF33` | 6.1 / 15.9 |
| Data | `D` | 2 px | `#000080` | `#33FFFF` | 16.0 / 14.6 |
| Analog | `A` | 1.5 px | `#235C53` | `#9EF075` | 7.7 / 13.1 |
| RF | `R` | 2.5 px | `#9933CC` | `#E566FF` | 5.7 / 6.6 |
| Pyro | `!` | 4 px | `#5C0000` | `#F07575` | 14.4 / 6.5 |
| Discrete | `d` | 1.5 px | `#5500FF` | `#B89C14` | 7.4 / 6.7 |
| Ground | `G` | 1 px | `#3A0953` | `#46A6B9` | 15.6 / 6.4 |

Each category also has a one-letter icon in a chip on every link (superseded by D-140: every kind of link now has its own picture), a text label, and a line weight. Redundancy is a dashed line and a REDUNDANT label, never colour alone. Colours were searched, not hand-picked, to stay apart under simulated colour blindness (Machado 2009 matrices). Closest pair of category colours, in CIE76 dE (above about 20 is clearly distinguishable):

| Vision | Light: closest pair (dE) | Dark: closest pair (dE) |
| --- | --- | --- |
| normal vision | data/ground (34) | power/analog (36) |
| protanopia | data/ground (26) | analog/discrete (27) |
| deuteranopia | analog/pyro (34) | analog/discrete (26) |
| tritanopia | data/ground (25) | power/analog (24) |

An earlier hand-picked palette had a protanopia pair at dE 2.2 (indistinguishable); the test now fails below 20.

### 7.3 Typography, spacing, icons, components
- **Fonts (bundled, no CDN):** Inter (UI) and JetBrains Mono (IDs, pins, hashes), both SIL OFL. The prototype falls back to system fonts; the release bundles the files and PDF output embeds them.
- **Scale (px):** xs 11, sm 12, base 14, md 16, lg 20, xl 24. **Spacing:** 4 / 8 / 12 / 16 / 24 / 32 / 48 (4/8 px grid).
- **Icons:** Lucide (ISC) bundled as SVG; the prototype uses text chips only. Category icons are letters in chips so they survive black-and-white printing (superseded by D-140: pictures replaced the letters; the dark outline and dash patterns keep prints readable).
- **Components:** button (default, primary, danger, ghost, pressed), segmented control, text field with live validation message, select, table with sticky header and inline editing, badge (auto, locked, released, stale, ok, warn, error), problem card, to-do row, dialog (title, impact list, Cancel default, primary action), toast with Undo, progress bar with Cancel, tour card, command palette, glossary.
- **States** (always more than colour): selected (thick primary outline), hover, focus (3 px focus colour ring), error (red + text), warning (amber + icon + text), auto-filled (dashed amber + "Auto"), locked and released (lock icon + greyed controls), disabled (reduced opacity + reason in tooltip/label), outdated (amber badge + disabled release).
- **Themes:** light, dark (follows the OS by default); outputs always use the print theme. Native controls follow the theme (`color-scheme`).
- **Scaling:** UI scale 100 to 200% with automatic panel collapsing (section 4). In Qt this is application scaling plus the same collapsing rules.

## 8. Mapping to the M2 implementation (Qt)

This is the M2 mapping. Since then the overview map and the legend are overlays on the canvas, tables use `tables.TableView`, and the views are the modules listed in section 13 and, for the current layout of `gui/`, in [`ARCHITECTURE.md`](ARCHITECTURE.md#cli-and-gui) section 2.

| UX element | Qt building block |
| --- | --- |
| Canvas | `QGraphicsView` + `QGraphicsScene`, items culled when off-screen; ports and links as items; minimap as a second view |
| Table view | `QTableView` over a model that reads the same `Project`; edits become commands |
| Properties, dialogs | Widgets generated from the pydantic model fields where possible, so validation is the model's validation |
| Undo/redo, autosave | `History` from M1 plus a recovery journal |
| Problems/to-do | One model fed by DRC (M4) and the status rules; clicking selects objects through a single selection service (enables cross-highlighting) |
| Command palette | A registry of `Action` objects; menus, shortcuts and the palette all read it |
| Strings | `gui/strings.py` (already in place) |
| Tests | pytest-qt journeys mirroring `tests/test_prototype.py`; offscreen screenshots for the review step |

M2 scope: canvas editor, interface types, table view, CSV/XLSX import, properties, problems/to-do (logical rules only), command palette, autosave and recovery, tour and glossary, themes and scaling. Generation, full DRC, outputs, diff are M3 to M6 and appear in the UI only as the empty states and badges shown in the prototype.

## 9. Usability test plan (you run it; findings become priority bugs)

3 to 5 users per persona. Think-aloud, no help except what is in the app, a timer, and an observer log of every wrong click.

| Task | Persona | Success criterion |
| --- | --- | --- |
| T1 Build a 5-unit diagram with 4 interfaces and generate plans | Dana | Under 15 minutes, no manual |
| T2 Connect a device that has no free connector of the type | Dana | Understands why it is greyed, finds the fix |
| T3 Create a redundant chain and clear its warnings | Dana | Clean, or a justified waiver |
| T4 Import the team's ICD CSV with 2 bad rows | Dana, Sam | Finds and understands both errors; one undo reverts |
| T5 Find every signal that reaches one connector | Sam | Under 30 seconds |
| T6 Replace an auto-chosen connector and lock a pin, then regenerate | Elena | Lock kept, report understood |
| T7 Release a harness, then change the model | Elena, Rui | Understands "outdated", cannot release stale |
| T8 Recover from a corrupt file | Elena | Salvages the rest, original untouched |

Metrics: task success (target at least 90%), time on task, wrong clicks, SUS (target at least 80), count of "I don't know what this means" remarks.

## 10. UX review log (my own walkthrough, as the process requires)

I rendered every screen and walked every journey. Found, fixed, and covered by a regression test unless marked open.

| # | Issue | Severity | Status |
| --- | --- | --- | --- |
| 1 | A newly added device was placed exactly on top of an existing one | High | Fixed (`test_new_units_never_overlap_*`) |
| 2 | Hover overrode the pressed/primary button styles, making "Connect" and "Waive" unreadable | High | Fixed (`test_pressed_and_primary_*`) |
| 3 | In connect mode the chosen source device was greyed ("cannot connect to itself"); reasons for greyed devices were hover-only; no message when nothing was valid | High | Fixed: FROM marker, inline reasons, warning hint |
| 4 | The cross-strap "fix" made the redundant device nominal, defeating its purpose | High | Fixed: "Connect to a redundant copy of X" (`test_cross_strap_fix_*`) |
| 5 | At 150 to 200% the header wrapped over most of the screen and the canvas collapsed to nothing | High | Fixed: compact header, auto-collapsing panels (`test_panels_collapse_*`) |
| 6 | Redundant copy overlapped its neighbours; links between devices in the same lane drew as degenerate loops; both links entered a device at one point | Medium | Fixed: free-slot placement, ports on the side facing the gap, offset anchors |
| 7 | Toasts covered the Problems buttons; the tour card covered the element it explained | Medium | Fixed: toasts over the canvas, tour card placed beside its target (`test_tour_card_*`) |
| 8 | Dark theme showed bright white native checkboxes | Low | Fixed (`color-scheme`) |
| 9 | Link labels can still overlap in dense diagrams; no automatic layout | Medium | Closed later: labels slide along their link (Q11, M7); **Arrange diagram** exists (M8); D-140 added routing |
| 10 | Wire list shows only two rows in the default bottom panel height | Low | Mitigated ("Taller" button); real tab gets a split view |
| 11 | When Properties is auto-hidden (narrow window) selecting an item shows nothing | Low | Closed later: a message says so (Q14, M7) |
| 12 | No minimap, no keyboard-only way to draw a link other than Tab and Enter on devices | Medium | Closed later: the overview map exists (View > Show overview map); in the editor the Connect tool starts with **C** and Enter picks a device |
| 13 | Prototype data is mock: pins, gauges and the "independent check" are simulated | Info | By design; the real verifier is M3 |

## 11. Questions for you (please answer or mark "you decide")

1. **Mode default:** should the app start in Guided for everyone (my proposal) or remember the last mode per user?
2. **Zones as lanes:** is "zone = which vertical lane the device sits in" acceptable, or do you want free-form zones that can be named and drawn as boxes (more flexible, more UI)?
3. **One harness per interface** is only the prototype's mock rule (DECISIONS D-10). Which real rule should the "Why does this harness exist?" text describe?
4. **Cross-strap fix:** is "create a redundant copy of the nominal end" the right default, or should the first suggestion always be "waive with justification"?
5. **Device templates** in the palette (computer, power unit, wheel, ...): which devices does your organisation use most? Do you want to import your own list (CSV) in M2?
6. **Title block / drawing standard** (D-15) and whether sheet size defaults to A3.
7. **Language of the glossary:** the 10 terms in the prototype are my wording. Please correct any definition your reviewers would dispute.
8. **Prototype sign-off:** which of the open issues (9, 11, 12; all closed since) block you from approving M2 implementation?

## 12. Qt editor review log (M2 implementation)

Screenshots of the real editor (offscreen render) are in `docs/ux/qt/`; the journey tests are in `tests/test_gui_journeys.py`. I walked every journey and rendered every screen as the process requires. Found, fixed and covered by a test unless marked open.

| # | Issue | Severity | Status |
| --- | --- | --- | --- |
| Q1 | Problems cards collapsed into blank bars when several findings were listed (word-wrapped labels were squeezed instead of the panel scrolling) | High | Fixed (scrolling bodies that size to content) |
| Q2 | Devices saved without positions (any M1 project) stacked in one slot | High | Fixed: deterministic auto-placement at load (`test_autoplace.py`) |
| Q3 | Selection was lost after renaming a device | High | Fixed (`test_j2_id_validation_*`) |
| Q4 | Saving a copy to a folder that does not exist yet failed (the project lock needs the folder) | High | Fixed (`test_sample_save_as_*`) |
| Q5 | Edits and selection took 350 to 650 ms at stress size | High | Fixed to about 20 ms (select) and 100 to 125 ms (edit); see M2 demo note |
| Q6 | At 150% scale palette labels were truncated and the bottom panel was capped so the table was unusable | High | Fixed: docks scale with the UI, no height cap |
| Q7 | After a theme change the palette collapsed into overlapping slivers | Medium | Fixed (layout invalidated on rebuild) |
| Q8 | Table filter for "rs422" found nothing because the column shows "RS-422" | Medium | Fixed: the filter matches ID, name, type name and ID, devices, requirement |
| Q9 | Table column widths reset on every refresh; names truncated | Medium | Fixed |
| Q10 | Link chips truncated long IDs; the Properties panel showed its message twice (deleted widgets lingered); import preview put the long status in the middle and cut off "To"; "Create redundant copy" enabled for a redundant device; new devices off-screen after selection | Medium | Fixed |
| Q11 | Interface chips can still overlap in dense diagrams | Medium | Mostly fixed in M7: labels slide along their link to free space (placement grid); a test limits overlaps on `sat15`; automatic device layout is still lane placement |
| Q12 | The connect hint wraps and makes the toolbar jump | Low | Fixed in M7: the hint reserves two lines (`test_connect_hint_has_a_fixed_height...`) |
| Q13 | At 150% and above the legend wraps and the canvas is small | Low | Improved in M8: the bottom panel is capped at 45% of the window height and toasts use the room available. The canvas at 150% on a 1440x900 window is about 250 px high; the legend still wraps; the diagram does not scale with the UI scale (zoom and Fit do that) |
| Q14 | Properties and palette auto-hide on narrow windows without a hint | Low | Fixed in M7: a message says so once, and again when Properties is needed |
| Q15 | The canvas is not exposed to screen readers (Qt graphics items) | Medium | Partly fixed in M7: the canvas announces device and interface counts and the selection and names the Interface table as the accessible alternative; items are still not individually exposed. A test audit (`tests/test_accessibility.py`) found and fixed unnamed fields in the release dialog and the harness tables. A manual screen-reader pass (Orca) is still needed |
| Q16 | An edit at stress size costs about 120 ms (target 100 ms); undo about 250 ms | Medium | Improved in M7: integrity results are cached per object (a generated 20,000-wire project: 110 ms to 22 ms per check). Measured now: rename about 100 ms, move about 100 ms, undo about 200 ms. Measured again on 2026-10-09 (`python -m tools.bench_gui`, three whole add / undo / redo cycles, software rendering, 200 devices, 2,000 interfaces): select under 20 ms, rename and move 25 to 60 ms, add device 60 to 90 ms, **undo 46 to 59 ms**, redo 11 to 26 ms. All inside the 100 ms target. The earlier "undo about 200 ms" was the first undo after start-up, which pays for one-off work (about 100 to 200 ms once); the benchmark took a single sample and so reported that one. It now times whole cycles. **Closed** |

## 13. Redesign against the UX/UI Standard (October 2026)

The owner approved an audit of the editor against the "UX/UI Standard: Harness Design Studio" ([`ux-audit.md`](ux-audit.md): 83 numbered issues) and the editor was rebuilt. What changed in the window (this is the window of 1.1.0 and 1.2.0; version 1.3.0 changed it again, see [section 14](#14-the-ui-overhaul-version-130-october-2026)):

```
Window
├─ Top bar: project name · short model hash · saved / unsaved · Generate (the one primary button) · Check · Export… · status chip
├─ Banners (persistent): plans or files out of date, failed generate / export / check (a refused change stays as a message over the diagram, with "Start new revision…")
├─ Tabs: Diagram · Harness · Lists · Checks · Releases (Ctrl+1 to Ctrl+5)
├─ Left dock: Project tree (units, interfaces, harnesses, parts, interface types, configuration, imports) · Interfaces (the editable interface table)
├─ Right dock: Inspector · Why · Problems (the Inspector tab also lists "Used in")
└─ Status bar: folder · rules and version · "Generated at model xxxxxxxx" · values pending link · zoom
```

New dialogs: Export (harness by document tree, result list, Reveal in folder), the Import wizard (parts, segment lengths, ampacity, KiCad netlist; since UI overhaul M7 interfaces use the wizard too, with the older dialog behind *Paste table text instead…*), New project (one dialog), the engineering values form (**Supply value…**), and release and new-revision dialogs that list what is locked and what becomes editable. The diagram gained multi-selection, navigation keys, state badges, locks, a legend overlay, find and context menus.

The journeys of section 3 still apply; the screenshots in [`ux/qt/`](ux/qt/) and [`ux/build/`](ux/build/) show the result, and [`DESIGN.md`](DESIGN.md) has one line per design decision. What was not built, and why, is under "Build status" in the audit (for example the Fix all button, the non-modal palette, compact Guided footprints, writing a subset of the outputs).

## 14. The UI overhaul (version 1.3.0, October 2026)

The owner's brief ([`ui/UI_OVERHAUL.md`](ui/UI_OVERHAUL.md)) and the plan that was approved ([`ui/UI_OVERHAUL_PLAN.md`](ui/UI_OVERHAUL_PLAN.md)) led to decisions D-150 to D-159 and to version 1.3.0 (published 2026-10-20). Its milestones M1 to M9 are the overhaul's own and are not the milestones of [`PLAN.md`](PLAN.md). What changed in the window:

```
Window
├─ Menus: File · Edit · View · Design · Go · Help
├─ Top bar (one row): project name · saved / unsaved · revision · short model hash · Undo · Redo · Guided | Expert · Search (Ctrl+K) · Generate › Check › Release… · Export… · status chip
├─ Navigation rail (left edge): Home · Model · Checks · Drawings · Outputs · Revisions · Settings
├─ Banners (persistent): plans or files out of date, a failed step, "this is part of a released harness" with Start new revision
├─ The open area: Model = tabs Diagram and Devices; Checks; Drawings = the Harness tab; Outputs = the Lists tab with the list of exported files and their SHA-256; Revisions = the Releases tab; Home and Settings are pages
├─ Left panel: Project (the tree) · Units · Interfaces (the last two are spreadsheet-like tables)
├─ Right panel: Inspector · Why · Problems
├─ Bottom: the Problems panel (Ctrl+Shift+M), closed until asked for
└─ Status bar: last check · saved and selection · counts · job indicator with Cancel · Problems · Offline marker · values pending and rules not checked · zoom
```

The three steps Generate, Check and Release show their state and what is next. There is one import wizard for every kind of import, and a settings page with Appearance (theme, interface size, reduce motion), Editing, Project, Keyboard shortcuts, About and Licences. The window no longer freezes on a large file or after an edit in a large project. The look is in [`DESIGN.md`](DESIGN.md) and the pictures are in [`ui/BEFORE_AFTER.md`](ui/BEFORE_AFTER.md) and [`ui/screenshots/after/`](ui/screenshots/after/).

What did not change: the design model, the file format, the 34 design rules, the command line and every generated file (checked with `tools/output_hashes.py`). The journeys of section 3 still apply. What was not done, and why, is in [`ui/BEFORE_AFTER.md`](ui/BEFORE_AFTER.md) ("What is left, and why"); no person has used the new interface in a usability session, and the screen-reader pass of [`usability/screen_reader_pass.md`](usability/screen_reader_pass.md) has not been held (waived, `compliance/DEVIATIONS.md`).

## 15. The AIT feedback (version 1.4.0, October 2026)

The feedback of the AIT engineers (ten requirements; plan and status in [`ait/AIT_FEEDBACK_PLAN.md`](ait/AIT_FEEDBACK_PLAN.md), decisions D-160 to D-165) changed the editor in five places. The window of section 14 is otherwise unchanged.

| Where | What is new |
| --- | --- |
| Drawings area, Harness tab | The *Edit wire* tab beside *Why*: change the gauge, type, colour, length, label and note of the selected wires; *New wire* draws a wire between two pins; *Group* twists or shields selected wires; *Labels* names the harness and its cable connectors. Several wires may share a pin (the rule *Several wires on one pin*, a warning; the tool has 35 design rules since this release). |
| Model area, Devices tab | A *Function* column in the pin table, a *Label* field on the connector card, the buttons *Save to library…* and *Add from library…* (a device library file), and a *Termination* column when pins have one. |
| Revisions area | A line with the last commit of the project's Git repository (who, when, what, branch), shown only when there is one. |
| Import wizard | The parts import also reads `.tsv` and `.json` files and an export of InvenTree. |
| Outputs | The wire list, pinout lists and labels gain columns and rows only when the new fields are used, so existing projects keep the same files. |

The interaction rules of section 6 apply as before: a change is one undo step, a released harness refuses with the reason, a mistake is said inline, and the tool never fills in an engineering value by itself. Known weakness (still there in 1.7.0): the *Edit wire* tab is the third column of the row above the drawing, beside the pin table and the wire table, so its form (about 320 px wide at 100 % scale) is often wider than the tab and scrolls sideways. Measured offscreen on the flatsat example: with the project panel and the inspector open the tab is 231 to 233 px wide in a window of 1280 to 1600 px and 275 px at 1760 px, so the form scrolls; with both panels closed the tab is 296 px at 1280 px (still short by a few pixels) and 341 px or more from 1440 px, so the form fits. The tabs *Connectors* and *Accessories* (1.7.0) need about 260 px and 316 px. A wider tab is a candidate for a later release.

## 16. A harness from nothing, and a blank project that says where to start (versions 1.5.0 and 1.6.0)

The window of section 14 is unchanged apart from the points below (decisions D-166 and D-167; the macOS removal of D-168 changes no screen).

| Where | What is new |
| --- | --- |
| Drawings area, Harness tab | **New harness…** (also in the Edit menu, Ctrl+Shift+H) makes an empty draft harness; the button also shows in the empty state of the tab, which no longer waits for interfaces. A third tab, *Connectors*, beside *Why* and *Edit wire* adds cable connectors to such a harness (a library part, or the other half of a device's connector), sets the function, termination and contact size of a pin and deletes a connector that has no wires. For a harness that Generate made, a released harness or a read-only project it is off, and a note says why. The wires are drawn in *Edit wire* as before. |
| Model area, empty diagram | The blank project says what to do: the button **Add a device** (the same as Edit > Add device > Device…, Ctrl+Shift+N) is shown until there is a device and is hidden in a read-only project; since the workshop feedback (M1, D-172) it opens a small dialog that asks for the name first and suggests the ID. The texts of the empty diagram, the empty link and device lists and the narrow-window notice name only controls that exist (the palette of the M2 design was removed in 1.3.0). |
| Starting the editor on Linux | If the machine lacks a library the package cannot carry (`libgl1`, `libegl1`, `libxcb1`) or has no desktop session, the editor says what is missing and the `sudo apt install` line, in the terminal and, when one is installed, in a small window (zenity, kdialog or xmessage), instead of a Python traceback. `harness-design-studio-gui --check-system` runs only that check. |

The interaction rules of section 6 apply as before: a change is one undo step, a released harness refuses with the reason, and the tool never fills in an engineering value by itself. Nothing in the file format or in any generated file changed in these two releases.

## 17. Build sheets, build data and the simple workspace (version 1.7.0)

The feedback of the test users of 1.6.0 (plan and status in [`ait/TEST_USER_FEEDBACK_PLAN.md`](ait/TEST_USER_FEEDBACK_PLAN.md), decisions D-169, D-170 and D-171) changed the window in these places. Stage S3 of the plan (plain words) was discarded by the owner and stage S4 (a blank project that asks for one thing at a time) is not built; nothing here claims that the tool is easier to use, because the testers have not repeated the tasks.

| Where | What is new |
| --- | --- |
| Navigation rail | **Next step** is the first area, a page of its own like Home: the heading *What to do next*, one card with the next step in plain words and its one button (an empty project also offers *or make a harness by hand*, *New harness…*), the six steps below it (*Add your devices*, *Connect them*, *Generate the harnesses*, *Check the design*, *Get the build sheets*, *Review and release*) each with an icon and a word (*done*, *next*, *to do*, *not possible*), and the link *Show everything*. The rules are a pure function of the facts of the project (`gui/next_step.py`, `gui/next_page.py` only shows and calls back). |
| View > Simple / Full, Settings | The workspace setting `ui/workspace`. A settings file with no stored value starts in **Simple** and opens a project on *Next step*; a settings file that holds values keeps **Full**, which is the window of sections 14 to 16 plus the Next step area. |
| The Simple workspace (stage S2) | The rail does not list Home (Next step does its job; Ctrl+7 and the Go menu still reach it). The project tree, the inspector, the Problems panel, the minimap, the legend and the counts of the status bar are closed or off until asked for; the diagram tool row shows *Select*, *Connect*, *Add device* and **More**. One switch, *Show panels* (View menu and a button), opens and closes the tree and the inspector together. Full and Simple remember their own layout, so one never overwrites the other. Open point: a click on a device or link does not open the inspector in Simple (a toast with *Show panels* says so once per window); going to an object with *Show* (from a list of problems) does open it. |
| Drawings area, Harness tab | A fourth tab, *Accessories*, beside *Why*, *Edit wire* and *Connectors*: a table of the sleeving, heat shrink, labels and backshells of the harness and a form to add, change and delete one (one undo step each). *Edit wire* gets the strip lengths (the selected wires, or all wires of the harness). Off for a released harness and a read-only project, with the reason shown. |
| Model area, Devices tab | A *Cable contact* column in the pin table (hidden until the **Contact** toggle is on) and the bulk action **Cable contact…**. Generate copies the contact to the cable pin. |
| Inspector | The page of a part of the category contact has **Crimp tool** and **Set tool**. |
| Export window | The check box **Include the PDF drawings** (see [`OUTPUTS.md`](OUTPUTS.md)); the build workbook is always written. |
| Command line | `export --drawings` and `import-build-data` ([`CLI.md`](CLI.md)); the same plans as the window use. |

The interaction rules of section 6 apply as before: a change is one undo step, a released harness refuses with the reason, a mistake is said inline, and the tool never fills in an engineering value by itself (an empty strip length, contact or tool stays empty and reads *to fill in* in the build workbook). The look and the code are in [`DESIGN.md`](DESIGN.md).

## 18. Connections between connectors (after 1.7.0, not released)

Milestone M2 of the workshop feedback (decision D-173, plan and status in [`ait/WORKSHOP_FEEDBACK_PLAN.md`](ait/WORKSHOP_FEEDBACK_PLAN.md), "M2 as built"): the pinout is the truth, the tool proposes and checks. The user's page is [`user-manual/connect-two-connectors.md`](user-manual/connect-two-connectors.md).

| Where | What is new |
| --- | --- |
| Window *Link connectors* (Edit > Link connectors…, Ctrl+Shift+K; the Connect tool and C after two devices; right-click on the Connections group or on a device) | A dialog of 760 pixels or more: an optional **Name**; a device and a connector on each side; the table *Pairs of pins* (pin, signal and role of the first connector beside pin, signal and role of the second), proposed by signal name and editable (**Add pair**, **Change pair**, **Remove pair**, the role of a pin: Automatic, Power, Return, Ground, Signal, Shield, Spare); under the table the notes of the proposal, the pins not paired and the review in plain words (an inline notice, never a message box). **Link connectors** is off only when the connection cannot be made (the same device twice, no pair, a pin in two pairs); a warning does not forbid it. One undo step. The same window with the connectors fixed edits the pairs (**Save the pairs**). |
| Model area, diagram | A connection is a dash-dotted line (an interface is solid) between the two devices, or between the two connectors in Expert mode, with the two connector names and, under them, what the pairs carry (derived, never stored). Click selects it. |
| Project tree | The group **Connections** (L1 - OBC-J01 - RW1-J02 ...) with the actions *Edit the pairs…*, *Rename…*, *Create harness*, *Delete connection*; double-click edits the pairs; the tooltip names the pairs, the harness and the checks. |
| Edit menu | **Link connectors…**, **Connect** (C), **Connect with an interface type…** (the older, interface-first way, also the arrow beside the Connect button) and **Selected connection**. |
| Design menu, Problems panel | **Check my connections** opens the Problems panel on the new filter **Connections** and says how many things there are to look at; it changes nothing. Four design rules (39 in all). |
| Create harness | A window that says *This adds the harness … with N cable connectors and M wires, one wire for each pair of …* and makes it only on **Create harness**; one undo step; the Harness tab then opens on it. The tool never creates a harness on its own. |
| Next step page | A connection counts as *Connect* done; with connections and no harness and no interface the card is *Make the harness of your connection* with the button **Create harness**. |

The interaction rules of section 6 apply as before: a change is one undo step, a released harness locks its connection with the reason, a mistake is said inline, and nothing is invented (a wire made from a connection has no length, gauge or colour until the person enters them).

Next: [`DESIGN.md`](DESIGN.md), [`ux-audit.md`](ux-audit.md), [`usability/README.md`](usability/README.md)
