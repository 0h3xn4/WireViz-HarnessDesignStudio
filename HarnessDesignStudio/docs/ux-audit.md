# UX audit against the "UX/UI Standard — Harness Design Studio" (October 2026)

Status: **the owner approved this audit and the redesign was built.** The findings below are the audit as it was written, about the editor as it was **before** the build; they are kept unchanged so the issue IDs stay traceable. What was done for each ID, in which branch and module, which test covers it and why anything was left out is in [Build status](#build-status) at the end. The decisions behind the new look are in [`DESIGN.md`](DESIGN.md); the user-visible changes are in the `Unreleased` section of the [changelog](../CHANGELOG.md).

What was audited: the editor (`harness-gui`, PySide6 widgets) on the `flatsat` example, offscreen, light and dark, 1280×720, 1920×1080 and 3840×2160, plus a 100-unit / 800-link stress project. Three reviewers worked in parallel (A: app shell and visual system; B: canvas and states; C: the Harness, Lists, Checks, Releases, Imports and Export screens and the flatsat journey). They ran and drove the program; each finding says how it was verified. Screenshots are in `docs/ux/audit/`. What earlier UX work already did is in [`UX_GUIDELINES_REVIEW.md`](UX_GUIDELINES_REVIEW.md) (the earlier guideline set) and [`UX.md`](UX.md).

Not covered: a real display and real GPU (everything ran on the Qt `offscreen` platform, device pixel ratio 1), screen readers, Windows/macOS (the app is Ubuntu only). Timings come from a shared 4-core sandbox and are probably slower than a workstation.

**Severity.** *high*: breaks a non-negotiable principle of the standard or a core flow. *medium*: clear gap against the target layout. *low*: polish. **Effort.** S under a day, M a few days, L about a week or more.

## 0. What the editor was when audited (confirmed)

This section and sections A to C describe the editor **before** the build; the present tense below is the audit's.

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

## B. Diagram canvas and states

Method: real `QTest` mouse, key, wheel and context-menu events on the real window; flatsat (23 units, 44 links), flatsat with W001 exported and released, an empty project, a read-only project, and synthetic 23/100/150/200-unit projects. Offscreen software rendering, so absolute timings are pessimistic; 4K and screen readers were not tested.

### B1. Requirement matrix

| Requirement | Verdict | Evidence |
|---|---|---|
| Pan: Space+drag, middle drag, wheel | missing (defect) | the wheel always zooms by a fixed ×1.1 (`canvas.py:1491`), also with Ctrl or Shift; middle drag and Space+drag on a unit move the unit or do nothing |
| Zoom to cursor | done | scene point under the cursor unchanged within 0.5 units |
| Fit (`F`) | partly | button, Ctrl+0 and View > Fit work; key `F` does nothing |
| Zoom to selection; 100 % (Ctrl+0) | missing | Ctrl+0 is Fit; View > Scale is UI scaling; no zoom level is shown |
| Minimap | partly | click re-centres, no drag; at 1280×720 it covers 41 % of the canvas height; solid black at 100 units |
| Grid; snap toggle | missing / partly | no grid; a hard-wired 10-unit snap with no toggle or indicator |
| Auto-layout with undo; manual positions saved | done | undo restores exact positions; positions in `logical/layout.json`; no shortcut; synchronous (0.8–1.3 s at 100 units) |
| Cards: name | done | |
| Cards: type icon; flight/ground tag | missing | `Unit` has no kind or flight/ground field; the only tag is NOMINAL/REDUNDANT on every card |
| Cards: connector count | partly | groups that do not fit are dropped silently, no total |
| Cards: problem badge; release/lock badge | missing | flatsat has 28 problems and none appear on the canvas; after releasing W001 the canvas is unchanged |
| Links coloured by type; legend | done / missing toggle | 7 category colours, weights, dashes, twin lines, picture chips (hidden at default Fit); the legend is a permanent 82 px strip |
| Selection: click | done | |
| Shift-click, rubber band, Ctrl+A, multi-select inspector | missing | the controller holds one `Selection(kind, id)` |
| Delete with confirm naming objects | partly | units: yes; interfaces: no confirm (a window-wide `Delete` action deleted IF-002 silently from the Interface table) |
| Ctrl+D; align/distribute | missing | |
| Link hover tooltip | partly | type, V, A and ends; no harness, wire count or state |
| Double-click opens Harness view; right-click context menu | missing | |
| Ctrl+F search | partly | only Ctrl+K "Go to"; does not centre; no highlight of matches |
| Pending / not-checked / problem badges (P2) | missing | a missing V/A is blank, the same as "not applicable"; "auto-filled, not reviewed" is drawn only in Expert mode |
| State visible (P3): dirty / outputs stale / release / locks | partly | dirty yes; stale, release and locks no |
| Why one click away (P4) | missing from the canvas | 4 steps away in Harness plans |
| Undoable (P5) | done | move, arrange, delete, zone change, redundant copy |
| Nothing silent; locked items say why and how (P5) | partly | good text, but a 5 s toast with no action; after a refused edit the Properties combo kept showing the rejected value; read-only drag, Delete and nudge are silent |
| 100+ units smooth (P7) | partly | pan, zoom and select 25–80 ms at 100 units / 300 links; dragging a unit costs 146–795 ms per move; the 200-unit / 2000-link spec size is slow everywhere |

### B2. Issues

| ID | Issue | Sev | Proposed fix | Eff | Screenshot | Hits |
|---|---|---|---|---|---|---|
| CV-1 | Single selection only: no shift-click, rubber band, Ctrl+A or multi-select inspector | high | `Selection` becomes a set; `ItemIsSelectable` synced with `scene.selectionChanged`; `RubberBandDrag`; Ctrl+A action; multi-form with common fields; multi-delete in one `History` transaction | L | — | P1 |
| CV-2 | No align/distribute, no Ctrl+D | medium | `core/edit.py`: `ops_align`, `ops_distribute`, `ops_duplicate_unit`; Edit menu and context menu; after CV-1 | M | — | selection |
| CV-3 | Pan model wrong: wheel always zooms; Space-drag and middle-drag do nothing | high | Ctrl+wheel zooms by `exp(delta/240)`, plain and Shift wheel scroll; middle button and a Space flag switch to hand drag | S/M | — | pan |
| CV-4 | Navigation shortcuts wrong or missing: no `F`, no zoom to selection, Ctrl+0 = Fit, no 100 %, no zoom indicator; zoom buttons lack tooltips | high | `F` fit, Ctrl+0 100 %, Shift+F zoom to selection; rename View > Scale to "Interface size"; zoom % label | S | [shot](ux/audit/canvas-nav_1280x720.png) | P6 |
| CV-5 | Canvas too small and Fit illegible: 692×313 px at 1280×720; unit names 5.7 / 3.6 / 2.1 px at Fit | high | overview text in screen pixels; minimum legible fit scale; auto-collapse legend and docks on small windows; compact footprints for Guided | M/L | [shot](ux/audit/canvas-nav_1280x720.png) | P1, 1280×720 |
| CV-6 | No problem/pending/not-checked badge on any object | high | `gui/canvas_state.py` index id → errors, warnings, not-checked, pending; header badge strip (icon plus count, never colour alone); badge on the link chip; click opens Problems filtered | M/L | [shot](ux/audit/canvas-cv-flatsat-overview-light.png) | P2 |
| CV-7 | Release state and locks invisible on canvas and inspector | high | lock owner from a pure `vcs/locks.lock_owners`; lock glyph plus "W001 A" on cards and links; Properties banner "Locked by W001 (released, rev A)" with a revise button; locked fields disabled with a tooltip | M | [shot](ux/audit/canvas-cv-released-overview.png) | P3, P5 |
| CV-8 | Auto-filled (not reviewed) drawn only in Expert; missing V/A looks like "not applicable" | high | olive dashed outline and "n auto" count in Guided too; "V ?" / "A ?" in a pending style | S/M | [shot](ux/audit/canvas-cv-cards-guided-100.png) | P2 |
| CV-9 | A refused edit leaves the form showing the rejected value; the refusal is a 5 s toast with no action | high | rebuild the form when `ctl.update_*` returns False; refusal toast with a "Start new revision" action; refusals persist | S/M | [shot](ux/audit/canvas-cv-locked-edit-refused.png) | P5 |
| CV-10 | Link tooltip lacks harness, wire count, state | medium | pure `describe.link_summary(project, iid)`; rich text | S | [shot](ux/audit/canvas-cv-link-hover.png) | P4 |
| CV-11 | Double-click on a link or unit does nothing | high | `ctl.openRequested(kind, id)`; the window opens the Harness view on the wire; if none, a toast "Not generated yet" with Generate | S | — | P1 |
| CV-12 | No context menu | high | `DiagramView.contextMenuEvent` built from the existing actions; disabled entries carry the reason | S/M | — | P6 |
| CV-13 | No Ctrl+F; "Go to" does not centre or scroll to links; no highlight of matches | medium | Ctrl+F overlay search over id, name, connector, type; highlight all matches; Enter cycles with `centerOn` | M | — | search |
| CV-14 | 8 of 44 link labels cannot be clicked: clicking IF-010's chip selects IF-014 | medium | test `_chip_rects` before `itemAt`; add the chip rect to `LinkItem.shape()`; raise the hovered or selected link | S | [shot](ux/audit/canvas-cv-link-label-hit-conflict.png) | P1 |
| CV-15 | Legend is a permanent strip (82 px), not toggleable, lists non-applicable entries | medium | collapsible overlay; View > Show legend; list only what is present | S/M | [shot](ux/audit/canvas-cv-empty-project.png) | legend |
| CV-16 | Minimap: click only, 41 % of the canvas height at 1280×720, black at 100 units | medium | drag the view rectangle; hide on small windows; thinner pen and alpha when zoomed far out | S | [shot](ux/audit/canvas-cv-perf-zoned-100u-300l.png) | minimap |
| CV-17 | Snap forced, invisible, not switchable; no grid | medium | grid in `drawBackground` at scale ≥ 0.5; View > Snap to grid (saved); Alt bypasses | S | — | grid/snap |
| CV-18 | Interface delete has no confirm; the `Delete` action is window-wide | medium | confirm naming both ends and affected harness and wires; shortcut context limited to the diagram and tables | S | [shot](ux/audit/canvas-cv-delete-confirm-unit.png) | P5 |
| CV-19 | Cards lack a type icon and a flight/ground tag; NOMINAL printed on every card; connector groups dropped silently | medium | type icon derived from connector families and interface categories (`describe.unit_glyph`, no model change); tag chips from a UI-side zone mapping; "12 conn" total and "+3" instead of a silent cut | M | [shot](ux/audit/canvas-cv-cards-guided-100.png) | cards |
| CV-20 | Read-only: drag, Delete and nudge are silent | low | say why ("…Save a copy to edit."); forbidden cursor | S | — | P5 |
| CV-21 | At default Fit the type chips are hidden; CAN, RS-422 and Ethernet share navy | low | per-category dash or marker patterns in far mode; minimum-size chip on selected or hovered link | M | [shot](ux/audit/canvas-cv-flatsat-overview-light.png) | visual |
| CV-22 | Stale outputs not shown anywhere visible | high | banner and top-bar status chip (see SH-2) and a canvas corner chip | S | — | P3 |
| CV-23 | Why is not reachable from the canvas | high | a "Why" section in Properties for the selected link or connector (first lines plus "Show all"); tooltip on the auto badge says why the connector was chosen | M | — | P4 |
| CV-24 | Dragging a unit at 100 units costs 146–795 ms per move (all links are re-routed) | medium | during a drag update only the moved unit's links as straight preview lines, throttle 16–33 ms, route on release; cache unchanged route groups | M | — | P7 |
| CV-25 | Spec-size project (200 units / 2000 links) slow everywhere: 705 `LinkItem.paint` calls cost 0.31 s of a 0.39 s repaint | medium | gap line only above LOD 0.8; cache pens, fonts and metrics; skip links outside the exposed rect; `ItemCoordinateCache` at low LOD; batched lines when far out | M | — | P7 |
| CV-26 | Toasts overlay the top of the canvas (a third of it at 1280×720) | low | show them in a strip under the toolbar | S | — | P5 |
| CV-27 | Arrange has no shortcut or button and is synchronous | low | Ctrl+Shift+L and a toolbar button; run through the worker above 60 units | S/M | — | P6, P7 |
| CV-28 | Empty-state label is an opaque box with no keyboard path and no "units but no links" hint | low | transparent; mention Ctrl+K and Import; second hint "press C to connect two units" | S | [shot](ux/audit/canvas-cv-empty-project.png) | empty states |
| CV-29 | The canvas has no token set of its own; magic numbers in `canvas.py` | low | `CANVAS` token group and one `CanvasMetrics` dataclass | S | — | visual |

Counts: high 12 (CV-1, 3, 4, 5, 6, 7, 8, 9, 11, 12, 22, 23), medium 11, low 6.

Open question for the owner: what "flight" and "ground" mean for a unit. The model has no such field and the standard forbids changing the model, so CV-19 proposes a UI-side mapping from the zone name.

Performance (offscreen; ms): at 23 units / 44 links every action is under 135 ms; at 100 units / 300 links (zoned) pan, zoom and select take 25–80 ms but dragging a unit takes 146–795 ms; at 200 units / 2000 links pan 250–350 ms, zoom step about 600 ms, drag up to 5 s.

## C. Harness, Lists, Checks, Releases, Imports, Export (non-canvas screens)

Method: the shipped `flatsat` example opened as a real project folder, driven through the controller and the window (real mouse clicks on the canvas where possible), rendered offscreen at 1440×900, 1280×720, 1920×1080 and dark. Screenshots: `docs/ux/audit/screens-*.png`.

### C1. Headline findings

1. **There is no Harness, Lists, Checks or Releases tab.** "Harness plans" is one of five bottom-dock tabs. At the default dock height it is clipped; after Generate the dock grows to 420 px and leaves the canvas about 250 px high at 1440×900 and about 70 px at 1280×720 ([shot](ux/audit/screens-j06e-harness-1280x720.png)).
2. **"Not checked" is hidden and misreported.** The panel says "Design rules: all 34 rules checked." while flatsat has 3 not-checked notes; they sit below "…and 51 more" because the Problems list shows at most 25 cards ([shot](ux/audit/screens-j07a-problems-tab-after-checks.png)). The words "not checked" never appear on screen.
3. **A pending value cannot be supplied in the editor.** Engineering values (derating, EMC, separation, generation, ampacity) are edited only in `config/*.json` or `harness config`. The editor never names the missing key, although `core/configcheck.missing()` knows it.
4. **Stale plans and outputs have no banner, chip or To-do item**; only a plain label inside the Harness plans tab ([shot](ux/audit/screens-j04c-interface-added.png)).
5. **Release and lock state is discovered by failing an edit.** The Status column is out of view at 1440 px; Properties of an interface carried by a released harness looks editable ([shot](ux/audit/screens-j09g-properties-of-released-interface.png)); the wire table's Locked column is empty for released wires.
6. **Export is one blind click**: no choice of harnesses or documents, no folder, no result list, no Reveal, no thumbnail; the result is a 5 s toast ([shot](ux/audit/screens-j08a-after-export.png)).

### C2. Requirement by requirement

| Area | Requirement | Status | Evidence |
|---|---|---|---|
| Harness tab | Header: name, release state, interfaces, last generated hash | missing | three plain labels (`panels.py:1137`); name and status only as list columns |
| | Connector/pin table (connector, pin, signal, wire, gauge, colour, shield, locked, state) | missing | only a wire table (`Wire, Signal, From, To, AWG, Length, Colour, Locked`); no connector or pin rows, no shield or state column |
| | Drawing preview: zoomable, hover linked to the table | partly | `DrawingPreview` paints the real sheet with Previous/Next; no zoom, no hover link, hard-coded colours and font |
| | Why for the selection | partly | a "Why" tab for wires only, one raw `QLabel`; 4 clicks away |
| | Three synchronised views in a splitter | partly | no `QSplitter` in `gui/`; Drawing and Why are alternatives; the drawing does not follow the wire selection |
| | Locked pins with lock icon and tooltip naming the release | missing | "Locked" shows `yes` for user locks only; cell tooltips empty |
| | Actions: regenerate this harness / export this harness / open in review | missing / missing / partly | only global Generate and Export; "Submit for review" per harness in a row of 6 equal buttons |
| Lists | Wire list, pinouts, BOM, test tables as views | missing | they exist only as exported files (113 for flatsat) |
| | `QTableView`, sort/filter, units in headers, Ctrl+C TSV, export from the view | partly / missing | only the Interface table is a `QTableView`; Ctrl+C copies one cell, not TSV |
| | Pending / not-checked cell styling; stale banner | missing | `pending` in the AWG column is ordinary text |
| Checks | Rules table (ID, name, severity, result, count); summary strip | missing | Problems is a scroll of cards; no row for passing rules |
| | Not-checked rules show the missing value + *Supply value…* | missing | `unchecked-config` cards have no value and no action; "Show" gives "This item has no place on the diagram" |
| | Expand a rule; double-click selects on canvas | partly | cards list up to 8 titles; a "Show" button per card; no double-click |
| Releases | Timeline; diff against released | partly | modal list "Change log…" and modal diff with raw `None` values; no tab |
| | Release dialog lists what will be locked | missing | it lists blockers and asks reasons; it does not list the wires, pins, parts, types or configuration that become locked |
| | Revise explains what becomes editable | missing | opens with "Nothing blocks this release." |
| | Consistent released badge | missing | text in one hidden column; none on canvas, Properties or tree |
| | Lock refusal says why and how to revise | done (text) | toast naming interface, harness, revision and the way forward; shown only after the attempt |
| Imports | One wizard pattern for CSV/XLSX/KiCad | partly | one dialog for interface CSV/XLSX; parts, lengths, engineering values and KiCad are CLI-only |
| | Mapping with live preview; apply undoable | done | live re-plan on mapping change; "Import n rows (one undo step)" |
| Export | Choose harnesses × documents; folder; open after export | missing | none |
| | Progress and Cancel; independent check before write | done | `OutputsWorker`, `verify_outputs` before `write_outputs` |
| | Result list, Reveal in folder, thumbnail | missing | toast "113 files written…" |
| Shared | `QTableView` + model + delegates + proxy | partly | 1 `QTableView` against 4 `QTableWidget` and several `QListWidget`s; column widths not saved; numbers left-aligned; no `QFormLayout`; no engineering-value UI |
| | Inline validation, no `QMessageBox` for validation | done | `_Field.show_error`; `QMessageBox` only for About and discard-changes |
| | Empty states; toasts; persistent banners for stale or failed | partly | table and Harness tab empty states say nothing; failed runs and lock refusals are 5 s toasts |
| | Long work in a worker | partly | Generate and Export yes; Check has no progress or Cancel; `verify_project` and the preview run on the UI thread (308 ms on flatsat) |

Anti-patterns present: pending/not-checked that looks like a pass or like empty (**yes**); lock state only discoverable when an edit fails (**yes**); outputs stale without a banner (**yes**); tables built with `QTableWidget` (**yes**); chains of modal dialogs (partly: release, revise, review, changes, history, import, new interface, waive and the generate preview are all modal; none nested); no primary action (Generate is not styled primary). Not present: frozen UI during generate/export; icon-only buttons.

### C3. Issues

| ID | Issue | Sev | Proposed fix | Eff | Screenshot | Hits |
|---|---|---|---|---|---|---|
| SC-1 | "Not checked" hidden and misreported ("all 34 rules checked"); the 25-card cap hides the not-checked notes | high | reword to "34 rules ran: n passed, n failed, n not checked" from a per-rule result (`core/drc.run_by_rule()` grouping existing hits, no rule-logic change); never cap not-checked items | M | [shot](ux/audit/screens-j07a-problems-tab-after-checks.png) | P2 |
| SC-2 | No Checks tab: no rules table, no summary strip, no double-click or keyboard activation | high | new `gui/checks_panel.py`: `RulesModel` + proxy + `StateDelegate`, offending objects as children, summary strip, double-click → `show_object`; keep `ProblemsPanel` as the dockable Problems view | L | same | P2, P6 |
| SC-3 | A pending value cannot be supplied; the missing key is never shown | high | `gui/config_dialog.py` or a form in Checks: `QFormLayout` from `configcheck.NEEDS`, unit suffixes, placeholder/source toggle, inline validation, applied through the existing config ops via `ctl.run`; **Supply value…** on not-checked rows; "n values pending" status-bar link | L | [shot](ux/audit/screens-j09a-release-dialog-empty.png) | P2, P5 |
| SC-4 | Stale state has no banner, chip or To-do item | high | status chip (generated / stale / running / outputs stale) fed by `ctl.generation_status()` and `ctl.outputs_state()`; persistent `Banner` with Generate and Export; "plans out of date" To-do item | M | [shot](ux/audit/screens-j04c-interface-added.png) | P3 |
| SC-5 | Harness view in a bottom-dock tab: clipped at default height; Generate squeezes the canvas to 250 px (70 px at 1280×720); no header | high | central `QTabWidget` (Diagram · Harness · Lists · Checks · Releases); `QSplitter` for table / drawing / Why; `HarnessHeader`; drop `_give_room_to` | L | [shot](ux/audit/screens-j03-harness-tab-bottom.png) | P1, P3 |
| SC-6 | Release state hidden in an out-of-view column; no badge in Properties, canvas or tree; locked Properties looks editable | high | `ReleaseBadge` (token `released`, lock icon plus text) in a delegate; Properties disables fields with "Locked: carried by W001 rev A. New revision…" from `vcs.locks`; badge on `UnitItem` | M | [shot](ux/audit/screens-j09g-properties-of-released-interface.png) | P3, P5 |
| SC-7 | Wire table: no lock icon or tooltip; `pending` looks like data | medium | `WireModel` + `StateDelegate` (text plus icon, italic for pending), tooltip naming the release, right-aligned numbers | M | [shot](ux/audit/screens-j14a-harness-tab-dark.png) | P2 |
| SC-8 | Why is 4 clicks away, wires only, one raw label | medium | a **Why** dock bound to the selection (unit, interface, harness, wire); tooltip from `explain_wire`; formatted list; reuse `core.generate.explain` | M | [shot](ux/audit/screens-j06b-why-for-wire.png) | P4 |
| SC-9 | No connector/pin table | medium | `ConnectorPinModel` (connectors, pins, wires, shield, state) | M | [shot](ux/audit/screens-j06a-harness-selected.png) | harness spec |
| SC-10 | Drawing preview: no zoom/pan, no hover link, hard-coded colours | medium | rebuild on `QGraphicsView` with wheel zoom, fit, pan; wire ids on the in-memory sheet for hover/selection sync (no change to written bytes); tokens | L | [shot](ux/audit/screens-j06c-drawing-tab.png) | P1 |
| SC-11 | No Lists tab | high | `gui/lists_panel.py`: sub-tabs fed by the `core.outputs.tables` builders (read-only), one generic `TableModel` + proxy, units in headers, Ctrl+C TSV, export CSV/XLSX, stale banner | L | [shot](ux/audit/screens-j06a-harness-selected.png) | P1, P2 |
| SC-12 | Export is blind (no selection, folder, result list, Reveal, thumbnail) | high | `ExportDialog` (harness × document tree, folder, open after export) and `ExportResultPanel` (paths, Reveal in folder, thumbnail); default stays the full export so the byte-identical output set is unchanged; **first check that `write_outputs` can write a subset without breaking `manifest.json`** | L | [shot](ux/audit/screens-j08a-after-export.png) | export spec |
| SC-13 | Generate preview is a thin modal (counts only); no per-harness regenerate | medium | table harness / change / locked pins kept from `plan.report`; per-harness regenerate only if `plan_generation` can be scoped (core check needed) | M | [shot](ux/audit/screens-j05b-generate-preview-dialog.png) | harness actions |
| SC-14 | The release dialog does not list what gets locked | medium | a tree "This release locks: n wires, n pins, interfaces, parts, interface types, config files" from `vcs.snapshot` and `locks.check_locks`; show placeholder values | S–M | [shot](ux/audit/screens-j09a-release-dialog-empty.png) | P5 |
| SC-15 | Revise dialog says "Nothing blocks this release."; OK disabled with no hint | medium | separate `REVISE_EXPLAIN` text; inline hint for the 10-character minimum | S | [shot](ux/audit/screens-j10a-revise-dialog.png) | P5 |
| SC-16 | Releases: no timeline tab; history and diff are modal lists with raw text | medium | `gui/releases_panel.py`: `QTableView` timeline from `changelog_rows`, diff grouped by `KIND_NAMES`, values formatted with `diff._show`; keep "Mark on diagram" | M | [shot](ux/audit/screens-j10c-changes-diff-dialog.png) | P3 |
| SC-17 | Imports: only interfaces have a GUI; one cramped dialog; long reasons elided | medium | `ImportWizard(QWizard)`: file → mapping + preview → conflicts and placeholders → apply, reusing the CLI planners (`core/imports.py`, `core/kicad.py`) | L | [shot](ux/audit/screens-j11a-import-dialog.png) | import spec |
| SC-18 | Top bar lacks name, hash, dirty marker, Check, Export, chip; Generate not primary | medium | see SH-1 | M | [shot](ux/audit/screens-j01-open.png) | layout spec |
| SC-19 | No shortcuts for Generate, Export, New interface, Check, tab switching; Ctrl+K has none of them; layout not saved | medium | actions with shortcuts (Ctrl+G, Ctrl+E, Ctrl+I, …); palette entries; `saveState`/`restoreState` and Reset layout | S–M | same | P6 |
| SC-20 | Left side is a palette, not a project tree | medium | see SH-6 | L | same | layout spec |
| SC-21 | Table code not shared: 4 `QTableWidget`; widths not saved; Ctrl+C copies one cell; left-aligned numbers | medium | `gui/tables.py`: `DictTableModel`, `StateDelegate`, `copy_tsv`, width persistence; migrate harness, wire, import, diff, history views | M | — | tables rule |
| SC-22 | Empty states say nothing about what to do | low | overlay text "No interfaces yet. Add one with Ctrl+I or import a table"; hide the disabled action row when there is no harness | S | [shot](ux/audit/screens-j12b-empty-project-table.png) | empty-state rule |
| SC-23 | Failed generate/export, "changed during job" and lock refusals are 5 s toasts | medium | store the last job error; show it in the stale banner until the next success | S–M | [shot](ux/audit/screens-j09e-locked-edit-refused.png) | toasts vs banners |
| SC-24 | `HarnessPanel.refresh` takes 308 ms on the UI thread on every change | low | compute verify and outputs state in a worker like `DrcWorker`; debounce the sheet | S–M | — | P7 |
| SC-25 | **Needs an owner decision.** A name-only change to an interface carried by a released harness is allowed (cosmetic by design), yet the panel then says "Out of date" and the independent check reports "outdated … 1 error" | low | decide whether cosmetic fields count as outdated; if not, exclude them from the check without touching generated bytes | S | [shot](ux/audit/screens-j09g-properties-of-released-interface.png) | P3 |
| SC-26 | Hard-coded colours and one inline stylesheet | low | tokens (see SH-20) | S | — | visual system |

Counts: high 8 (SC-1, 2, 3, 4, 5, 6, 11, 12), medium 14, low 4.

### C4. Journey walk (flatsat, real project folder, 1440×900)

| # | Step | Clicks | Dialogs | Friction | Screenshot |
|---|---|---|---|---|---|
| 1 | Open | 0 here (File > Open is 2 + folder chooser) | none | no project name, hash or state chip; "Design rules: checking…" until the background check ends; the Harness view is only a bottom tab | [shot](ux/audit/screens-j01-open.png) |
| 2 | Select a unit | 1 | none | Properties has no connector count, "used by", placeholder/source status, lock state or Why | — |
| 3 | Add an interface | 3 | none on canvas | picking a unit with no free connector gives a clear toast; the new interface makes plans stale with no visible sign outside one tab | [shot](ux/audit/screens-j04c-interface-added.png) |
| 4 | Generate | 2 | 1 modal preview | the preview does not say which plan changes or which locks are kept; afterwards the dock jumps to 420 px and the drawing area is an empty grey box | [shot](ux/audit/screens-j05b-generate-preview-dialog.png) |
| 5 | Read a Why | 4 | none | wires only, raw text, no hover, not reachable from canvas or Properties | [shot](ux/audit/screens-j06b-why-for-wire.png) |
| 6 | Run checks | 1 (they also run on their own) | none | no Check button, no progress; "all 34 rules checked" while 3 are not; not-checked items hidden behind "…and 51 more" | [shot](ux/audit/screens-j07a-problems-tab-after-checks.png) |
| 7 | Supply a pending value | **not possible in the editor** | — | the 4 missing values and 6 placeholder files can be changed only by editing `config/*.json` or `harness config` | — |
| 8 | Export | 2 | none (progress dialog over 400 ms) | no choice, no folder, no result list; toast only | [shot](ux/audit/screens-j08a-after-export.png) |
| 9 | Release | 4 + typing | 1 modal | export first is a release blocker; the dialog does not list what is locked; two free-text reasons required; afterwards the released state is visible only in the out-of-view Status column | [shot](ux/audit/screens-j09a-release-dialog-empty.png) |
| 10 | Revise | 3 + typing | 1 modal | the dialog opens with release wording; the diff shows raw `None` values | [shot](ux/audit/screens-j10a-revise-dialog.png) |

About 20 clicks and 4 modal dialogs from open to revise, excluding typing. Hidden state: stale plans and outputs, not-checked rules, release state, lock state in Properties, pending values.

Not verified in this part: 100 units, 4K, screen readers; whether `write_outputs` can write a subset without changing `manifest.json` (SC-12); whether `plan_generation` can be scoped to one harness (SC-13); toast timing in real time.

## Build status

Checked against the code and the tests of branch `ux/docs` (the merge of all UX branches, `ux/all`, plus this documentation). Each claim was confirmed by reading the module and the test named in the row. **done** means the proposed fix exists in the window and a test covers it; **partly** says what is missing; **not done** and **needs owner decision** say why.

Branches (all merged into `ux/all`): **found** = `ux/found` (tokens, theme, icons, state chips, shared tables); **core** = `ux/core` (headless helpers); **canvas** = `ux/canvas` (navigation, selection, editing); **cstate** = `ux/cstate` (state marks on the diagram); **tree** = `ux/tree` (project tree, inspector, Why); **checks** = `ux/checks`; **harness** = `ux/harness` (Harness view, Lists, generate plan table); **rel** = `ux/rel` (Releases, Export, Import, New project); **shell** = `ux/shell` (top bar, banners, tabs, layout, palette, shortcuts). Module names are under `gui/` unless they start with `core/`. Tests are under `tests/`.

Totals: SH 28 = 22 done, 6 partly; CV 29 = 22 done, 6 partly, 1 not done; SC 26 = 20 done, 5 partly, 1 needs an owner decision.

### Shell and visual system (SH)

| ID | Status | Built in | Covered by | Note |
|---|---|---|---|---|
| SH-1 | done | shell: `topbar.py` | `test_ux_shell.py` | Name, short hash (mono), dirty marker, Generate (the only primary button), Check, Export…, status chip. The Guided, Expert, Select and Connect toggles are neutral (`toggle` property). |
| SH-2 | done | shell: `shell.py`, `topbar.py` | `test_ux_shell.py` | Status chip (up to date, plans or outputs out of date, generating, exporting, checking) and persistent banners with Generate and Export…; the stale banner can be hidden until the next change. |
| SH-3 | done | checks: `checks_panel.py`, `core/drc/by_rule.py`; shell: status bar | `test_ux_checks.py`, `test_drc_by_rule.py` | "34 rules: n passed · n failed · n not checked"; the status-bar link "n values pending · n rules not checked" opens Checks filtered. |
| SH-4 | done | core: `core/vcs/lockview.py`; cstate: `canvas_badges.py`; tree: `project_tree.py`, `inspector.py` | `test_vcs_lockview.py`, `test_gui_canvas_state.py`, `test_ux_tree.py`, `test_ux_inspector.py` | Lock icon and "W001 A" on cards, links, connectors, tree rows and in the Inspector, with fields disabled and the reason as tooltip. The audit's `ctl.locked_ids()` was not needed; the views read `lockview.locked_objects`. |
| SH-5 | done | shell: `main_window.py`, `shell.py` | `test_ux_shell.py` | A refusal stays on screen with "Start new revision…" until the next change goes through. |
| SH-6 | done | tree: `project_tree.py`; shell: `main_window.py` | `test_ux_tree.py`, `test_ux_retire.py` | `QTreeView` over a model, seven groups, state chips, problem counts, locks, incremental updates, filter, Add menu. The Palette tab is gone: Add units are in the tree's Add menu and Edit > Add unit, the interface types are the arrow beside Connect, the import is File > Import and the tree's Imports group (table below). |
| SH-7 | done | shell: `main_window.py` (tabs); harness: `harness_view.py`; `interface_table.py` | `test_ux_shell.py`, `test_ux_harness.py`, `test_ux_retire.py` | The main tabs Diagram, Harness, Lists, Checks, Releases and the Harness view exist, and the bottom dock with its five old tabs (Problems, To-do, Interface table, Harness plans, Outline) is gone with the old `HarnessPanel` and its two `QTableWidget`s, `_give_room_to` and the bottom-dock sizing. Where each function went is in "Where the bottom tabs and the Palette went" below. |
| SH-8 | done | tree: `inspector.py`, `why_panel.py`, `core/usedby.py` | `test_ux_inspector.py`, `test_usedby.py`, `test_ux_why.py` | Right dock tabs Inspector, Why, Problems; "Used in"; engineering values of a configuration file with a status chip each. |
| SH-9 | done | shell: `main_window.py` | `test_ux_shell.py` | Project folder (mono, cut in the middle), "34 rules · v1.0.0", "Generated at model xxxxxxxx" (from the generation record, no clock), pending-values link, zoom. |
| SH-10 | done | shell: `main_window.py`; found: `tables.py` | `test_ux_shell.py`, `test_ux_foundation.py` | `saveState` with a version, View > Reset layout, table column widths saved. |
| SH-11 | done | shell: `main_window.py` (`open_commands`), `command_palette.py` | `test_ux_shell.py`, `test_ux_palette.py` | Ctrl+K lists every enabled action (Generate, Export, Check, Release, Revise, Reset layout, tabs, imports, go to harness) with its shortcut, ranks by prefix, has no result cap. It is a non-modal overlay centred over the window (a child widget, not a dialog): search box and list, Up, Down, Page Up, Page Down and Enter, Esc closes, a click elsewhere or any other move of the keyboard focus closes it, Ctrl+K again closes it, and the keyboard goes back to where it was. |
| SH-12 | done | shell: `main_window.py`; canvas | `test_ux_shell.py`, `test_gui_canvas_ux.py` | Every shortcut is in a menu; Connect `C` is in Edit; `F` fits, Ctrl+0 is 100 %; Ctrl+G, Ctrl+E, F5, Ctrl+I; tooltips read "text (shortcut)". |
| SH-13 | partly | shell: `main_window.py` | `test_ux_shell.py` | F6 and Shift+F6 cycle the panels, Ctrl+1 to Ctrl+5 switch tabs. The diagram still takes one Tab stop per unit and link (`DiagramView.focusNextPrevChild`); there is no roving focus, F6 is the way out. |
| SH-14 | partly | shell: `main_window.py` | `test_ux_shell.py` | "Undo Move PDU2" and "Redo …" from the history labels. No history list or dock; it is still the core `History`, not `QUndoStack`. |
| SH-15 | done | canvas: `canvas.py` | `test_gui_canvas_ux.py`, `test_gui_perf.py` | Only the moved units' links are drawn, as straight lines, while dragging; routes are worked out on release. |
| SH-16 | partly | harness: `harness_view.py`, `background.py`; shell: `main_window.py` | `test_ux_harness.py`, `test_ux_shell.py` | The independent check, the outputs state and the plan state of the Harness and Lists views run in a worker and are cached; the hash and states of the top bar are read once per model state after a pause. Export builds and verifies in a worker, but `write_outputs` is still called on the UI thread when the worker has finished (`export_dialog.py`), and the status chip's outputs state is read on the UI thread. |
| SH-17 | done | checks: `checks_panel.py`; shell: `shell.py` | `test_ux_checks.py`, `test_ux_shell.py` | A failed generate, export or check is a banner until the next success; a running check says "Checking…" and can be cancelled. |
| SH-18 | partly | rel: `new_project_dialog.py` | `test_ux_rel_newproject.py`, `test_ux_shell.py` | New project and New project from an example are one dialog with the problem next to the field. Add zone is still a `QInputDialog`. |
| SH-19 | done | found: `theme.py` | `test_ux_foundation.py` | `QPalette` from the tokens; System (default), Light, Dark; follows the OS scheme. |
| SH-20 | done | found: `tokens.py`, `theme.py`, `preview.py` | `test_ux_foundation.py` | `paper` and `pasteboard` tokens; a test finds no hex literal and no `setStyleSheet` outside the theme (the logo in `appicon.py` is the one exception). |
| SH-21 | done | found: `theme.py` (`mono_font`) | `test_ux_foundation.py` | IBM Plex Mono for hashes, paths, IDs, pin and wire numbers, the drawing preview. |
| SH-22 | done | found: `tokens.py`, `theme.py` | `test_ux_foundation.py` | Type 12 / 13 / 16 / 20, spacing 4 / 8 / 12 / 16 / 24 / 32, `theme.type()` and `theme.space()`; a test finds no literal pixel sizes. |
| SH-23 | done | found: `theme.py` | `test_ux_foundation.py` | One 32 px control height. |
| SH-24 | done | shell: `panels.py`; checks: `checks_panel.py`, `core/checks.py` (`fix_all_plan`), `controller.py` (`fix_all`) | `test_ux_shell.py`, `test_fix_all.py`, `test_ux_fixall.py` | The Fix buttons on problem cards are not primary, so Generate is the one primary button. **Fix all (n)** in the Checks tab applies the one-click fix of every open finding that has one, as one undo step: the fixes are made one after the other on a copy of the project (a later fix sees the connectors an earlier one took), the ones that regenerate the harnesses run once at the end, and a fix a release lock refuses is left out and named in the message. n counts the open findings with a fix, and the tooltip and the message afterwards say which kinds of fix they are (for example "Choose connectors automatically (2)"). **"Fix all" never confirms:** a finding whose fix records that a person looked at something (`PERSON_ONLY_RULES`, today the "Confirm connectors" of auto-filled choices) is not counted and not fixed in bulk; the Fix button on its own card still does it (owner decision, 18 October 2026); the button is disabled with its reason when n is 0 or the project is read-only. It shows no plan first because the single Fix button of a card does not either; the message has Undo. A connector the tool chose for a link that had none is, as with the single fix, marked auto and still waits for a person to confirm it. |
| SH-25 | partly | found: `icons.py` | `test_ux_foundation.py` | A Lucide icon set (ISC licence, D-146) with tooltips naming the shortcut, recoloured from the tokens. The icons are painter paths read from path strings, not SVG files, because the package has no QtSvg. |
| SH-26 | done | shell: `main_window.py`, `shell.py`; canvas: `legend.py` | `test_ux_shell.py`, `test_gui_canvas_ux.py` | The legend and overview map are overlays; the bottom panel hides in a window under 800 px high so the diagram keeps at least 55 % of the height at 1280 x 720; the first UI scale follows the screen height. The tool row stayed above the diagram. |
| SH-27 | partly | rel: `export_dialog.py`, `export_docs.py` | `test_ux_rel_export.py`, `test_outputs_subset.py` | Folder, harness by document tree, progress with Cancel, result list, Reveal in folder, Open, drawing picture. The ticks choose what the result list shows and what "Copy selection to folder" copies; the export always writes the full set, because the core cannot write a subset (see SC-12). |
| SH-28 | done | found: `states.py`; checks | `test_ux_foundation.py`, `test_ux_checks.py` | State chips with icon, word and, for pending (dotted) and not checked (hatched), a pattern; used in every table, the tree, the canvas and the dialogs. |

### Diagram canvas (CV)

| ID | Status | Built in | Covered by | Note |
|---|---|---|---|---|
| CV-1 | done | canvas: `canvas.py`, `controller.py`, `core/edit.py` | `test_gui_canvas_ux.py`, `test_edit_canvas.py` | The selection is a set (`ctl.selected`; `ctl.selection` is the primary one); Shift- and Ctrl-click, rubber band, Ctrl+A, common fields in Properties, one undo step per action. |
| CV-2 | done | canvas: `core/edit.py` | `test_gui_canvas_ux.py`, `test_edit_canvas.py` | `ops_align`, `ops_distribute`, `ops_duplicate_unit`; Edit and right-click menus; Ctrl+D. |
| CV-3 | done | canvas: `canvas.py` | `test_gui_canvas_ux.py` | Ctrl+wheel zooms, the wheel scrolls, middle button or Space and drag pan. |
| CV-4 | done | canvas: `canvas.py`, `main_window.py` | `test_gui_canvas_ux.py` | `F`, Shift+F, Ctrl+0 = 100 %, zoom level shown, View > "Interface size", tooltips. |
| CV-5 | partly | canvas: `canvas.py`, `legend.py` | `test_gui_canvas_ux.py` | Overview text in screen pixels, a fit floor (10 %, 22 % on opening), legend and map fold in a small window. Compact footprints for Guided were not built: the room a unit takes (`edit.unit_footprints`, the taller of the Guided and Expert heights) decides where units are placed and saved in `logical/layout.json` and in the example projects, so changing it moves saved layouts. Needs an owner decision. |
| CV-6 | partly | cstate: `canvas_state.py`, `canvas_badges.py` | `test_canvas_state.py`, `test_gui_canvas_state.py` | One index of problems, warnings, pending and not checked per object; badge = icon + count, with the word in the tooltip. A click on a badge selects the object and emits `ctl.problemsRequested(id)`; `MainWindow` opens the right dock's Problems tab with the object selected (`tests/test_ux_final.py`); the list is not filtered to that object. |
| CV-7 | done | cstate: `canvas_badges.py`; tree: `inspector.py`; core: `lockview.py` | `test_gui_canvas_state.py`, `test_ux_inspector.py`, `test_vcs_lockview.py` | Lock and "W001 A" on cards, links and connectors, a faint released tint, Inspector banner with "Start new revision". |
| CV-8 | done | cstate: `canvas.py`, `core/describe.py` | `test_gui_canvas_state.py`, `test_describe_cstate.py` | "n auto" chip in Guided too; "V ? · A ?" in the pending style on power links. |
| CV-9 | done | tree: `inspector.py`, `panels.py` | `test_ux_refused_edit.py` | A refused edit rebuilds the form; the refusal stays with a "Start new revision…" button (SH-5). |
| CV-10 | done | cstate: `core/describe.py` (`link_summary`) | `test_describe_cstate.py`, `test_gui_canvas_state.py` | Rich tooltip: harness, wire count, state, what is still to enter, lock, checks. |
| CV-11 | done | canvas | `test_gui_canvas_ux.py` | Double-click or Enter emits `ctl.openRequested`; the window opens the Harness tab with the wire selected, or a toast "Not generated yet" with Generate. |
| CV-12 | done | canvas | `test_gui_canvas_ux.py` | Right-click menus built from the window's actions; a greyed entry carries the reason. |
| CV-13 | done | canvas: `canvas.py` | `test_gui_canvas_ux.py` | Ctrl+F bar over ID, name, connector, type; matches get a dashed halo; Enter and Shift+Enter centre on the next and previous. |
| CV-14 | done | canvas | `test_gui_canvas_ux.py` | A link label is part of the link's shape. |
| CV-15 | done | canvas: `legend.py` | `test_gui_canvas_ux.py` | Collapsible overlay, View > Show legend, lists only what is drawn. |
| CV-16 | done | canvas | `test_gui_canvas_ux.py` | The map can be dragged, is smaller or hidden in a small window, uses thin see-through lines. |
| CV-17 | done | canvas | `test_gui_canvas_ux.py` | Grid from 50 %, View > Snap to grid (saved), Alt bypasses. |
| CV-18 | done | canvas, shell | `test_gui_canvas_ux.py` | Deleting an interface asks first and names both ends and the harness wires; Delete works only from the diagram and the tables. |
| CV-19 | partly | cstate: `core/describe.py` (`unit_glyph`), `canvas.py` | `test_describe_cstate.py`, `test_gui_canvas_state.py` | Type picture, "12 conn", "+3" instead of a silent cut, NOMINAL only where there is a redundant chain. The flight / ground tag is a viewer setting (`QSettings` key `canvas/zone_tags`, default none) set per zone name from the unit's menu, not a property of the unit; the open question below stands. |
| CV-20 | done | canvas | `test_gui_canvas_ux.py` | Read-only drag, Delete, nudge and arrange say why. |
| CV-21 | done | cstate: `canvas.py` | `test_gui_canvas_state.py` | Below 50 % each category has its own dash pattern and a small plate with its picture. |
| CV-22 | done | cstate: `canvas_badges.py` | `test_gui_canvas_state.py` | Corner chip on the diagram plus the top-bar chip and banners (SH-2). |
| CV-23 | done | cstate, tree: `why_panel.py`, `core/why.py`, `inspector.py` | `test_gui_canvas_state.py`, `test_why.py`, `test_ux_why.py`, `test_ux_refused_edit.py` | The Why tab of the Inspector, the Why pane of the Harness view and the tooltip of the auto badge give the recorded reasons. "Why?" in the right-click menu and the click on the auto chip emit `ctl.whyRequested`, which `MainWindow` shows in the Why tab of the right dock (`tests/test_ux_final.py`). |
| CV-24 | done | canvas | `test_gui_canvas_ux.py`, `test_gui_perf.py` | See SH-15. |
| CV-25 | partly | canvas: `canvas.py` | `test_gui_canvas_ux.py` | The gap line only from scale 0.8, links outside the exposed rectangle skipped, pens and fonts cached. No `ItemCoordinateCache` and no batched lines when far out; the 200-unit, 2000-link size was not re-measured for this page. |
| CV-26 | not done | — | — | Toasts still appear over the top of the diagram (`ToastHost.reposition` in `main_window.py`), not in a strip under the toolbar. |
| CV-27 | done | canvas, shell | `test_gui_canvas_ux.py` | Ctrl+Shift+L and a toolbar button; a diagram of more than 60 units is arranged in a worker. |
| CV-28 | done | canvas | `test_gui_canvas_ux.py` | The empty-state text mentions Ctrl+K and Import, and a diagram without links says "press C to connect". |
| CV-29 | partly | canvas: `canvas.py` | `test_gui_canvas_ux.py` | `CanvasMetrics` holds the numbers; they were not moved into a `CANVAS` token group. |

### Harness, Lists, Checks, Releases, Imports, Export (SC)

| ID | Status | Built in | Covered by | Note |
|---|---|---|---|---|
| SC-1 | done | core: `core/drc/by_rule.py`; checks: `checks_panel.py`, `panels.py` | `test_drc_by_rule.py`, `test_ux_checks.py` | Per-rule results (pass, fail, not checked, pending); the Problems header no longer says "all 34 rules checked"; not-checked notes are never cut by the 25-card limit. |
| SC-2 | done | checks: `checks_panel.py` | `test_ux_checks.py` | Rules table with a summary strip, offending objects, Enter or double-click shows one on the diagram; `ProblemsPanel` stays as the dockable Problems view. |
| SC-3 | done | core: `core/configcheck.py` (`engineering_values`, `plan_set_value`); checks: `config_dialog.py` | `test_configcheck_values.py`, `test_ux_checks.py` | **Supply value…** opens every engineering value by config file, with units, inline reasons, and one undo step for Apply; Design > Engineering values…; pending link in the status bar. |
| SC-4 | done | shell: `topbar.py`, `shell.py` | `test_ux_shell.py` | Chip and banners (see SH-2). The audit's "plans out of date" To-do item was not added. |
| SC-5 | done | harness: `harness_view.py` | `test_ux_harness.py`, `test_ux_harness_core.py` | Harness is a main tab with a header (name, release state, interfaces, hash, chips) and splitters between pin table, wire table, drawing and Why. |
| SC-6 | done | core: `lockview.py`; tree: `inspector.py`; cstate | `test_vcs_lockview.py`, `test_ux_inspector.py` | Release chip and lock everywhere; locked fields disabled with the reason. |
| SC-7 | done | harness: `harness_view.py`, found: `states.py` | `test_ux_harness.py`, `test_ux_foundation.py` | State chips in the pin and wire tables, lock chip with a tooltip naming the release, right-aligned numbers. |
| SC-8 | done | tree: `why_panel.py`; harness: `harness_view.py` | `test_ux_why.py`, `test_ux_harness.py`, `test_why.py` | Why for a unit, link, harness, wire, connector or pin, in the right dock and in the Harness view. |
| SC-9 | done | harness: `harness_view.py` | `test_ux_harness.py`, `test_ux_harness_core.py` | Connector and pin table with shield, locked and state columns; spare pins hidden and counted. |
| SC-10 | done | harness: `preview.py` (`SheetView`), `core/outputs/canvas.py` | `test_ux_harness.py`, `test_ux_harness_core.py` | Zoom 1x to 24x, pan, hover and selection linked with the tables; the written SVG and PDF are unchanged. |
| SC-11 | done | harness: `lists_panel.py` | `test_ux_lists.py` | Wire list, pinouts, BOM, mass and length, test tables, labels, system BOM; units in headers; Ctrl+C as TSV; CSV and Excel export of the visible rows. |
| SC-12 | partly | rel: `export_dialog.py`, `export_docs.py` | `test_ux_rel_export.py`, `test_outputs_subset.py` | The result list, Reveal in folder, picture and notices exist. Writing only the chosen harnesses is not possible in the core: `write_outputs` deletes what is not in the new set and the independent check expects every harness; `test_outputs_subset.py` records this. Changing it would touch the verifier and the manifest. |
| SC-13 | partly | harness: `plan_table.py` | `test_ux_lists.py` | `GeneratePlanTable` (each harness: create, change, remove, keep, locked pins kept) is built and tested but the Generate preview dialog (`GeneratePreviewDialog` in `dialogs.py`) does not use it yet. A per-harness Regenerate is not possible: `plan_generation` has no way to scope to one harness, so the button says it covers every harness. |
| SC-14 | done | rel: `lock_tree.py`, `dialogs.py`; core: `lockview.release_locks` | `test_ux_rel_dialogs.py`, `test_vcs_lockview.py` | "This release locks: …" as a tree, placeholders shown as pending. |
| SC-15 | done | rel: `dialogs.py` | `test_ux_rel_dialogs.py` | The new-revision dialog says what happens and what becomes editable; a disabled OK says what is missing. |
| SC-16 | done | rel: `releases_panel.py`; core: `core/vcs/timeline.py` | `test_ux_rel_panel.py`, `test_vcs_timeline.py` | Timeline of reviews, releases and revisions, differences grouped by kind, Mark on diagram. |
| SC-17 | partly | rel: `import_wizard.py`, `import_kinds.py` | `test_ux_rel_import.py` | The four-page wizard (file, columns with live preview, conflicts and placeholders, apply) serves approved parts, segment lengths, the ampacity table and a KiCad netlist; every import is one undo step. Interfaces from Ctrl+Shift+I still open the older `ImportDialog` (the wizard can also import them but is not wired to that command). |
| SC-18 | done | shell: `topbar.py` | `test_ux_shell.py` | See SH-1. |
| SC-19 | done | shell: `main_window.py` | `test_ux_shell.py` | Actions with shortcuts, palette entries, saved layout and Reset layout. |
| SC-20 | done | tree: `project_tree.py` | `test_ux_tree.py` | See SH-6. |
| SC-21 | partly | found: `tables.py`; used by harness, checks, releases, export, import wizard and the tree | `test_ux_foundation.py` | Shared `TableView`, `DictTableModel`, `TableProxy`, state delegate, TSV copy, saved widths. Still `QTableWidget`: the older import dialog and the wire colours window (`dialogs.py`); the old Harness plans panel, which had two, is gone. |
| SC-22 | done | harness: `harness_view.py`, `lists_panel.py`; tree | `test_ux_lists.py`, `test_ux_harness.py`, `test_ux_tree.py` | Empty states say what to do; one enabled Generate button only when there are interfaces. |
| SC-23 | partly | shell: `shell.py`, `main_window.py` | `test_ux_shell.py` | Failed generate and export and lock refusals are persistent. The note "changed during the job" is still a toast. |
| SC-24 | done | harness: `background.py` (`JobRunner`), `harness_view.py`, `lists_panel.py` | `test_ux_harness.py` | The check, the outputs state and the plan state are computed on a copy in a worker and cached by the state token. |
| SC-25 | needs owner decision | — | — | A name-only change to an interface of a released harness is cosmetic by design, yet the plans then say "out of date" and the independent check reports an error. Nothing was changed: whether a cosmetic field counts as outdated is a rule decision. |
| SC-26 | done | found: `theme.py`, `tokens.py` | `test_ux_foundation.py` | See SH-20. |

### Where the bottom tabs and the Palette went

The five bottom tabs (Problems, To-do, Interface table, Harness plans, Outline), the bottom dock and the Palette tab were removed. Every function moved; nothing was dropped. Tests that read the old panels now read the new place (listed in the pull request notes).

| Old place | What it did | Where it is now |
| --- | --- | --- |
| Bottom, **Problems** | Cards with Show, Fix and Waive; grouped cards; the 25-card limit with "…and n more"; the *Not checked* notes; the list of waived findings; the rule-check state line; the count in the tab title | The **Problems** tab of the right panel (the same `ProblemsPanel`, hosted by the Inspector); the count is in that tab's title ("Problems (n)"); Show, Fix and Waive, the notes, the waived list and the state line are unchanged. F6 pane "Bottom panel" is now "Inspector". The accessible name "Problems" stays. |
| Bottom, **To-do** | One line per thing left to do (units not connected, interfaces without a connector, auto-filled connectors to review, n warnings to fix or waive); a click shows the object; the count in the tab title | A **To do (n)** section at the top of the Problems tab (`todo-heading`, `todo-0` …): the same lines from `ctl.todos()`, a click shows the object (the warnings line scrolls to the first card). Stale plans and outputs stay visible as the top-bar chip, the banners (SH-2), the Harness tab chips and the Lists banner; pending values as the status-bar link and the Checks tab (the old To-do never listed those, SC-4). |
| Bottom, **Interface table** | The keyboard and screen-reader alternative to the diagram: every interface as a sortable, filterable table; editing name, redundancy, maximum current and requirement ID in the cell; **New interface**; the selection follows the diagram both ways; Delete | The **Interfaces** tab of the left panel, the same `InterfaceTable` (now `gui/interface_table.py`), so the editing, filter, **New interface** button, selection sync and Delete work as before. Reach it with **Go > Go to Interface table** (Ctrl+Shift+T, also in Ctrl+K) or the tab; opening it widens the left panel to about 620 px and the Project tab narrows it again. Its accessible name "Interface table" is kept. This was chosen over a sub-tab of Lists because it works before anything is generated, keeps the diagram beside it and needs no new main tab. |
| Bottom, **Harness plans** | Plan status and the independent check; the outputs line and **Export**; the list of harnesses; the wire table with the Colour column; the drawing; the Why text; Submit for review, Release, New revision, **Changes…**, **Change log…**, **Delete harness**; `select_harness` and `select_wire` for the diagram's double-click | The **Harness** tab: the chips for the design, the outputs and the independent check (their tooltips carry the old sentences); the Export button (opens the Export window); the harness selector, the project tree's Harnesses group and the Releases timeline; the wire table (with Colour), the drawing and the Why pane; Review, Release and New revision buttons; a **More** menu with Changes…, Change log… and Delete harness (also in Design > Show changes of harness…, Show change log of harness…, Delete harness…, in Ctrl+K, and in the context menu of a harness row of the tree); `HarnessView.select_harness` and `select` take over the diagram's double-click. Changes and the log are also in the Releases tab (differences and timeline). The window's `export_flow` (the older inline export used by the plans panel's button) stays for its tests. |
| Bottom, **Outline** | Every unit with its interfaces as a plain tree, for the keyboard and screen readers; a selection of several units | The **Project** tree (Units and Interfaces groups, accessible name "Project" with a description). It now takes **Shift** and **Ctrl** for a multiple selection (it selects the same items on the diagram, and the other way round) and **Delete**, as the Outline did. The interfaces of a unit are in the Inspector's "Used in" table. |
| Left, **Palette**, *Add a unit* | One button per kind of unit | **Add > Unit…** in the project tree (it opens the list of kinds), **Edit > Add unit**, and Ctrl+K ("Add unit …"). |
| Left, **Palette**, *Connect with* | One toggle button per interface type; the one in use is pressed; the help sentence | The arrow beside the **Connect** button above the diagram lists the interface types (the one in use has a tick); **Edit > Connect with**; **C** with the last type; Ctrl+K ("Connect …"). The help sentence is in the tooltip. |
| Left, **Palette**, *Bring in data* | The import button (Ctrl+Shift+I) | **File > Import** (Ctrl+Shift+I), the **Imports** group of the project tree, Ctrl+K. |
| Tour | Steps "palette", "types" and "bottom" | Steps "add" (the project panel's Add), "types" (the Connect button and its arrow) and "problems" (the right panel's Problems tab); a step whose panel is hidden is still skipped. |
| Window | `dock_bottom`, the bottom-dock sizes, the 800 px height rule that hid it, the F6 pane "Bottom panel", the saved dock layout | Removed. The saved layout has a new version (2), so a layout saved with the bottom dock is ignored. A short window no longer hides a panel; the width rules for the side panels stay. |

### Left for the owner or a follow-up

- **Decisions.** SC-25 (do cosmetic edits make released outputs "outdated"); CV-5 compact Guided footprints (changes saved layouts); what flight and ground mean for a unit (CV-19).
- **Core limits.** Writing a subset of the outputs (SC-12) and generating one harness (SC-13) need changes in `write_outputs`, the output verifier and `plan_generation`.
- **Follow-ups in the window.** Connect `ctl.problemsRequested` and `ctl.whyRequested` in `MainWindow` (CV-6, CV-23); roving focus in the diagram (SH-13); a history list (SH-14); toasts in a strip (CV-26); inline zone edit (SH-18); wire the Generate preview to `GeneratePlanTable` (SC-13); wire interface import to the wizard (SC-17); write outputs inside the worker (SH-16).
