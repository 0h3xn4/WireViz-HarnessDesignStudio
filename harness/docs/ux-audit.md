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
