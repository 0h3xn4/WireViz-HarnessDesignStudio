# UX audit against the "UX/UI Standard — Harness Design Studio" (October 2026)

Status: **audit only, nothing in the editor has been changed for it.** The standard says to stop here and wait for approval; the sections "Approval needed" at the end list what I propose to build and in which order.

What was audited: the editor (`harness-gui`, PySide6 widgets) on the `flatsat` example, offscreen, light and dark, 1280×720, 1920×1080 and 3840×2160, plus a 100-unit / 800-link stress project. Three reviewers worked in parallel (A: app shell and visual system; B: canvas and states; C: the Harness, Lists, Checks, Releases, Imports and Export screens and the flatsat journey). They ran and drove the program; each finding says how it was verified. Screenshots are in `docs/ux/audit/`. What earlier UX work already did is in [`UX_GUIDELINES_REVIEW.md`](UX_GUIDELINES_REVIEW.md) (the earlier guideline set) and [`UX.md`](UX.md).

Not covered: a real display and real GPU (everything ran on the Qt `offscreen` platform, device pixel ratio 1), screen readers, Windows/macOS (the app is Ubuntu only). Timings come from a shared 4-core sandbox and are probably slower than a workstation.

**Severity.** *high*: breaks a non-negotiable principle of the standard or a core flow. *medium*: clear gap against the target layout. *low*: polish. **Effort.** S under a day, M a few days, L about a week or more.

## 0. What the editor is today (confirmed)

- Stack: PySide6 widgets (the standard said "confirm from the code first"). Main window `gui/main_window.py`; token-driven theme `gui/theme.py` + `gui/tokens.py`; canvas `gui/canvas.py`; panels `gui/panels.py`.
- Shell: left **Palette** dock | centre diagram with a tool row and the legend | right **Properties** dock | bottom dock with five tabs (Problems, To-do, Interface table, Harness plans, Outline). Top toolbar: Undo, Redo, Guided/Expert, Search (Ctrl+K), filters, Generate.
- Undo is the core `History` (200 steps, locks enforced on edit and redo), not `QUndoStack`. Generate and export run in cancellable worker threads; checks run in a helper process.

## A. App shell and visual system

Requirement by requirement (done / partly / missing). Evidence: file and line, or screenshot.

### A1. App shell

| Requirement | Status | Evidence |
|---|---|---|
| Top bar: project name | partly | only in the window title (`controller.py:298`, `main_window.py:791`) |
| Top bar: short model hash | partly | in the status bar (`main_window.py:842`), shows "…" for about 250 ms after each edit, not monospace |
| Dirty marker | partly | `*` in the title and a status-bar text; not in a top bar |
| **Generate** primary | partly | button exists (`main_window.py:701`) but has no `primary` property; the checked Guided/Select toggles take the accent colour, so the hierarchy is inverted |
| Check button | missing | checks run on their own 1.2 s after the last edit (`controller.py:43`); no way to run on demand |
| Export in the top bar | partly | only inside the Harness plans tab, hidden while there are no harnesses; not in a menu or Ctrl+K |
| Status chip (up to date / stale / running) | missing | plain labels in Harness plans; verified: after an edit the status is "stale" and no banner shows ([shot](ux/audit/shell-s_harness_tab_after_edit_light_1440.png)) |
| Left project tree (units, interfaces, harnesses with badge, parts, types, configuration, imports) | missing | the left dock is the Palette; the nearest thing is the Outline tab (units and interfaces only, bottom dock) |
| Problem badges on tree nodes | missing | only the tab text "Problems (28)" |
| Lock icon on released items | missing | verified after releasing W001: IF-010 shows no lock on the canvas, in Properties or in the outline ([shot](ux/audit/shell-s_locked_iface_selected_light_1440.png)) |
| Main tabs Diagram / Harness / Lists / Checks / Releases | missing | the diagram is the fixed centre; there is no Lists view and no Checks table; Problems is a card list capped at 25 |
| Right dock Inspector / Why / Problems | partly | only Properties; Why is a sub-tab of Harness plans driven by wire selection; Problems is in the bottom dock |
| Status bar: project path, rules version, last generate, "n checks not run – m values pending" link | missing | status bar shows save state, selection and counts only |
| Ctrl+K palette | partly | 160 entries but no Generate, Export, Check, Release, Revise, Reset layout; shows 14 results; modal ([shot](ux/audit/shell-palette_light.png)) |
| Shortcuts in menus | partly | the Connect tool `C` is in no menu; Fit is Ctrl+0 (standard: `F` fit, Ctrl+0 100 %) |
| Dock layout saved; View > Reset layout | missing | only window geometry is saved (verified: docks reset on reopen) |
| Undo for everything | done functionally | every edit is a labelled history step; not `QUndoStack`; menu text is a static "Undo" |
| Locked items refuse edits and say why / how to revise | done (text) | "PDU2 cannot be deleted: W001 is released. Start a new revision of it first…"; shown as a 5 s toast; nothing is disabled in advance |
| Keyboard-only | partly | Tab/Enter/Shift+Arrow/Esc work; the canvas is a Tab trap (67 stops in flatsat); no F6, no panel shortcuts |
| Worker + progress + Cancel | partly | Generate: done. Check: helper process, no progress or Cancel. Export: progress and Cancel, but `write_outputs` and `verify_project` (2.1 s at stress size) run on the UI thread |
| 100+ units stay smooth | partly | at 100 units / 800 links: install 0.76 s, select 100–160 ms, add/undo/redo about 270 ms; **moving a unit 0.8–1.4 s** (re-routing in `canvas._redraw_changed`); CLAUDE.md says edits should be under 100 ms |
| Empty states | done | "Your diagram is empty. Add your first unit from the palette…" (no import hint) |
| Toasts for success; banners for stale and failed | partly | toasts done; failed generate/export are toasts only (export check failure opens a modal); no persistent banner |
| No chained modals | partly | New project = 2 dialogs, New from example = 3, Add zone = `QInputDialog` |

### A2. Visual system

| Requirement | Status | Evidence |
|---|---|---|
| One theme module generating `QPalette` + QSS | partly | one QSS from tokens; no `QPalette` anywhere in `gui/` |
| No scattered `setStyleSheet` | done, one exception | `panels.py:871` |
| No hard-coded colours | partly | `preview.py:32,42` (`#8a8a94`, `#ffffff`) and font "Courier" |
| Light and dark, OS default | partly | both render well; the default is always light, the OS scheme is never read |
| Canvas has its own token set | partly | shares the UI tokens plus `cat-*`; `locked` and `released` tokens exist and are not painted |
| IBM Plex Sans | done | bundled and loaded |
| IBM Plex Mono for pins, parts, hashes, paths | missing | bundled, never used in `gui/` |
| Type scale 12/13/16/20, spacing 4/8/12/16/24/32 | partly | `TYPE_SCALE` is 11/12/14/16/20/24 and only `base` is read; `SPACING` is defined and unused |
| Meaningful colour; pending/not-checked distinct | partly | link classes also differ by picture and weight; **pending is plain text** (AWG column) |
| SVG icon set; tooltips on icon buttons | partly | icons are painted in code; zoom `−` `+`, Fit, Search and every "Show" button have no tooltip |
| Consistent buttons; one primary per view | partly | 32 px push vs 35 px tool buttons in one toolbar; 20+ primary "Confirm connectors" buttons visible at once; Generate not primary |
| 1280×720 | partly | diagram gets about 705×320 px; selecting Harness plans shrinks it to a sliver ([shot](ux/audit/shell-tab_plans_light_1280x720.png)); the tab is clipped at 1440×900 |
| 4K / scale | partly | manual UI scale 100–200 %, no automatic one: at 3840×2160 all text is 14 px ([shot](ux/audit/shell-flatsat_light_scale100_3840x2160.png)) |
| `QTableView`, not `QTableWidget` | partly | Interface table is a proper `QTableView` + model + proxy; Harness plans uses two `QTableWidget`s and the import preview a third; column widths are not saved |

### A3. Issues

| ID | Issue | Sev | Proposed fix | Eff | Screenshot | Hits |
|---|---|---|---|---|---|---|
| SH-1 | No project/state top bar: name only in the OS title; no Check or Export; Generate not primary; accent on the Guided/Select toggles | high | new `gui/topbar.py` (`TopBar`): name, short hash in mono, dirty dot, Generate (`primary`), Check, Export, status chip; shared `QAction`s with shortcuts; neutral selected style for toggles (`theme.py`) | M | [shot](ux/audit/shell-flatsat_light_1920x1080.png) | P3 |
| SH-2 | Stale generation or outputs shown only as text in one tab; no banner, no chip, no "running" | high | `StatusChip` driven by generation/outputs state and worker flags; persistent `Banner` with Generate/Export buttons when stale | M | [shot](ux/audit/shell-s_harness_tab_after_edit_light_1440.png) | P3; "stale without banner" |
| SH-3 | "all 34 rules checked" is shown while `unchecked-config` cards say rules were not checked; no not-checked/pending summary or link | high | derive not-run rules from `unchecked-config`; header "34 rules: n findings, n not checked (values pending)"; status-bar link that filters Problems; `not-checked` and `pending` tokens and icons | M | [shot](ux/audit/shell-placeholders_problems_light_1920x1080.png) | P2; "pending looks like a pass" |
| SH-4 | No lock or release badge on units, interfaces, harnesses; tokens unused; lock discoverable only by a failed edit | high | `ctl.locked_ids()` (reuse `core/vcs/locks.py`); lock glyph and tooltip on `UnitItem`/`LinkItem`, Properties header, tree and outline; disable non-cosmetic fields with the reason | M | [shot](ux/audit/shell-s_locked_iface_selected_light_1440.png) | P3, P5 |
| SH-5 | Refusal is a 5 s toast over the canvas | medium | persistent for refusals and errors, bottom-right, with a "Start new revision…" button | S | same | P5 |
| SH-6 | No project tree; Parts, Types, Configuration, Imports not browsable; Outline has no badges and rebuilds fully on every change | high | new `gui/tree.py` (`QTreeView` + model): Units, Interfaces, Harnesses (state badge), Parts, Interface types, Configuration (placeholder flag), Imports; per-node problem counts; incremental update from `Delta`; Palette becomes a "+ Add" menu | L | [shot](ux/audit/shell-tab_outline_light_1920x1080.png) | target layout; P1, P3 |
| SH-7 | No main tabs; Harness plans is cramped in the bottom dock (diagram shrinks to a sliver at 1280×720) | high | central `QTabWidget` (Diagram, Harness, Lists, Checks, Releases); move `HarnessPanel` out of the bottom dock; replace its `QTableWidget`s | L | [shot](ux/audit/shell-tab_plans_light_1280x720.png) | target layout; "QTableWidget" |
| SH-8 | Right dock is only Properties; Why and Problems elsewhere; no source/placeholder status, no "used in" | medium | right dock tabs Inspector / Why / Problems; "Used in" section; per-field placeholder badges | M | [shot](ux/audit/shell-flatsat_light_1920x1080.png) | P4 |
| SH-9 | Status bar lacks path, rules version, last generate, checks-not-run link | medium | extend `_build_status`: elided mono path, rules version, "generated at model xxxxxxxx" from the generation record (no wall-clock: outputs must stay deterministic), SH-3 link | S | same | P3 |
| SH-10 | Dock layout not saved; no Reset layout | medium | `saveState`/`restoreState` in settings; View > Reset layout; save column widths | S | [shot](ux/audit/shell-menu_view_light.png) | target layout |
| SH-11 | Ctrl+K lacks Generate, Export, Check, Release, Revise, Reset layout, tab switching; 14-result cap; modal | medium | make real `QAction`s so the palette lists them; "Go to harness"; no cap; rank by prefix | S | [shot](ux/audit/shell-palette_light.png) | P6 |
| SH-12 | Shortcut and tooltip gaps (Connect `C` in no menu, Fit is Ctrl+0, no shortcut for Generate/Export/Check, bare tooltips) | medium | add actions to menus; `F` fit, Ctrl+0 100 %; tooltips as "text (shortcut)" | S | [shot](ux/audit/shell-menu_view_light.png) | P6 |
| SH-13 | Canvas is a Tab trap (67 stops); no F6 panel cycling | medium | F6/Shift+F6 across canvas, tree, inspector, bottom dock; Ctrl+1..5 tabs; roving focus inside the canvas | M | behaviour | P6 |
| SH-14 | Undo menu text static; no history view; not `QUndoStack` | low | "Undo Move PDU2" from the history labels; later a `QUndoView`-style history dock | S/M | — | P5 |
| SH-15 | Moving a unit takes 0.8–1.4 s at 100 units / 800 links (documented target: 100 ms) | high | re-route only links touching moved units; spatial index instead of the O(units × links) scan; straight preview while dragging; re-run `tools.bench_gui` and `test_gui_perf` | M | [shot](ux/audit/shell-stress100_light_1440x900.png) | P7 |
| SH-16 | `verify_project` and output writing run on the UI thread (2.1 s at stress size) | medium | verify in a worker or cached by model hash; write outputs inside the worker | M | — | P7; "frozen UI" |
| SH-17 | Failed runs are toasts (modal for export); Check has no progress or Cancel | medium | persistent failure banner until the next success; "checking…" chip state with Cancel | S | — | toasts vs banners |
| SH-18 | Chained modals for New project (2), New from example (3), Add zone | low | one `NewProjectDialog` with inline validation; inline zone edit | M | — | "chains of modal dialogs" |
| SH-19 | No `QPalette`; default always light; OS scheme ignored | medium | build `QPalette` from tokens; System/Light/Dark defaulting to the OS scheme | S | [shot](ux/audit/shell-flatsat_dark_1920x1080.png) | visual system |
| SH-20 | Hard-coded colours and one `setStyleSheet` | low | `paper`/`pasteboard` tokens for the drawing preview; property rule in `theme.py` | S | — | "no hard-coded colours" |
| SH-21 | IBM Plex Mono bundled and never used | medium | `ThemeManager.mono_font()` for hash, path, requirement IDs, pin/wire columns, ID fields, preview | S | [shot](ux/audit/shell-flatsat_light_1920x1080.png) | visual system |
| SH-22 | Type and spacing scales not enforced; dock titles do not scale | low | fix the scale to the standard, `theme.type()`/`theme.space()`, replace literals, grep test | M | — | visual system |
| SH-23 | 32 px vs 35 px buttons in one toolbar | low | equalise in `theme.py` | S | [shot](ux/audit/shell-flatsat_light_1920x1080.png) | "inconsistent button sizes" |
| SH-24 | 20+ primary "Confirm connectors" buttons at once; Generate not primary | medium | drop `primary` on card buttons; one "Fix all (n)" | S | [shot](ux/audit/shell-tab_problems_light_1920x1080.png) | "several primary buttons" |
| SH-25 | No SVG icon set; zoom uses "+" and "−" text | medium | bundle Lucide or Tabler SVGs (licence in `DECISIONS.md`), recolour from tokens, icons plus text, tooltips | M | [shot](ux/audit/shell-flatsat_light_1920x1080.png) | visual system |
| SH-26 | Diagram gets 44 % of the height at 1280×720; no automatic scale at 4K | medium | legend as a toggleable overlay; tool row into the toolbar; initial scale from the screen DPI | M | [shot](ux/audit/shell-flatsat_light_1280x720.png) | acceptance 1280×720 and 4K |
| SH-27 | Export lacks harness × document choice, result list, "Reveal in folder"; hidden until harnesses exist | medium | `ExportDialog` or tab with checkable harness × document types, progress, result table with Reveal | L | [shot](ux/audit/shell-tab_plans_light_1280x720.png) | Export section |
| SH-28 | Pending values are plain text; nothing distinguishes pending or not-checked from empty or pass | high | `pending` and `not-checked` tokens, icons and a delegate; dotted/hatched pattern plus label so colour is not the only cue | M | [shot](ux/audit/shell-placeholders_problems_light_1920x1080.png) | P2 |

Counts: high 8 (SH-1, 2, 3, 4, 6, 7, 15, 28), medium 15, low 5.

Verified good and to keep: cancellable workers with a private clone and a stale-plan guard; one labelled undo history with locks enforced on edit and redo; a single token-driven QSS with contrast-tested tokens and bundled IBM Plex Sans; accessible names; Outline and Interface table as keyboard alternatives; a toast when panels are hidden by a narrow window; `InterfaceTable` as a real `QTableView`.
