# UI overhaul plan (Phase 1: audit and plan, no GUI code changed)

Status: **for the owner's review. Nothing in this plan is implemented.** Brief: `UI_OVERHAUL.md`.
Date: 2026-10-19. Base: `master` 6a04874, version 1.2.0. Tool folder: `HarnessDesignStudio/`.

What Phase 1 added to the repository: this plan, `PERF_BASELINE.md`, `screenshots/before/` (87 pictures: every
tab, menu, dialog and the narrow, wide, scaled and stress variants, in light and dark), and two scripts,
`tools/ui_screenshots.py` and `tools/ui_perf.py`. No file under `src/` was touched.

## 1. What I found out first (things that change the plan)

1. **The tool is smaller than the brief assumes.** No WebEngine, no Plotly, no Graphviz, no QtSvg. Drawings are
   made by our own SVG/PDF writers and shown on screen by our own widgets. So: no `QWebEngineView`, no plot
   template, no linked time cursors, no WSL2 software-rendering concern. I treat the brief's *Plots* section and the
   WebEngine/plotly.js items as **not applicable** (and keep them out of M1) unless you say a plot is coming.
   Question Q4.
2. **Part of the brief is already true.** Icons already are Lucide (D-146, 46 icons, drawn with `QPainter` from path
   strings because the packaged programs leave out QtSvg). Tables already are model/view (`tables.TableView`,
   `DictTableModel`, `TableProxy`). All colours already come from one token file (`gui/tokens.py`); hex literals
   exist only there (56), in `appicon.py` (4) and three `QColor(r, g, b)` in `glyphs.py`. `setStyleSheet` is called
   only in `theme.py`. Heavy work (generation plan, arrange, export, rule check) already runs in workers. The
   overhaul is therefore mostly **structure and look**, not a plumbing rewrite.
3. **No usability findings from AIT engineers exist in the repository** (no `FEEDBACK.md`, no AIT file, no GitHub
   issues; I checked all three). The brief says those take priority. Q1.
4. **Carbon is wider than the style sheet.** It is in `gui/tokens.py`, `gui/theme.py`, `gui/fonts.py`,
   `resources/fonts/` (IBM Plex, 1.2 MB), `packaging/gui_entry.py`, `tools/build_installer.py`,
   `tools/collect_licences.py`, `resources/__init__.py`, five docs and **three test files that assert the old
   look** (see section 6). Removing it completely touches those tests; the brief says all tests stay unchanged.
   This is the biggest open question (Q2).
5. **Stress-size benchmark shows 11 s per edit with the rule check on** (50 to 240 ms with it off; a focused profile
   shows 64 to 219 ms). Unexplained; details in `PERF_BASELINE.md`. Must be resolved before M5.
6. **Theme and scale changes take 0.55 to 0.95 s** (whole-application style sheet re-polish). The brief wants a live
   switch; M1 has to fix this, not just add a new palette.

## 2. Inventory

### Screens (all pictured in `screenshots/before/`, `_light` and `_dark`)

| Ref | Screen |
|---|---|
| 01, 02 | Main window, Diagram tab, Guided and Expert (01 is also at 1280×720, 1920×1080 = `40-*`, 1150×400 = `41-*`, scale 150 % = `42-*`) |
| 03 to 07 | Tabs Harness, Lists (7 sub-tabs), Checks, Releases, Devices |
| 08 | Left dock, Interfaces tab |
| 09 to 11 | Right dock tabs Inspector, Why, Problems |
| 12, 13 | Command palette (Ctrl+K), first-run tour |
| menu-* | File, Edit, View, Design, Go, Help menus open |
| 20 | Generate preview dialog |
| 21 | Delete-impact dialog |
| 22 to 27 | New interface, Wire colours, Glossary, Known issues, New project from example, Import interfaces |
| 28 | Engineering values dialog |
| 29, 30 | Export window before and after the export |
| 31, 32 | Import wizard: file page, column-mapping page |
| 33 | Release dialog |
| 34 to 36 | After a release: diagram with locks, harness, Releases compare |
| 37, 38 | New revision dialog, Changes dialog |
| 50, 51 | First start (empty project), stress project (100 units) |

Not reachable by the harness (need a real file chooser or a destructive state): the Open/Save-as file choosers,
the device-editor dialogs in `devices_dialogs.py` (add connector, add pins, assign, fill; reached from the Devices
tab, listed in section 4), the history dialog and the diff dialog beyond picture 38. M4 and M8 add them.

### Code (src/harness_design_studio/gui, 29,457 lines)

Largest: `canvas.py` 3,415, `main_window.py` 3,128, `strings.py` 1,842, `devices_view.py` 1,597,
`project_tree.py` 1,511, `controller.py` 1,368, `harness_view.py` 1,339, `export_dialog.py` 1,039,
`checks_panel.py` 934, `panels.py` 916, `dialogs.py` 883, `import_wizard.py` 829.

- **Styles:** one style sheet generated in `theme.stylesheet()` (27 size/px references there); Fusion style on every
  OS; radius 0; control height 32; type scale 12/13/16/20; IBM Plex Sans/Mono. Hard-coded colour: tokens.py 56,
  appicon.py 4, glyphs.py 3. Hard-coded pixel numbers outside theme.py: `canvas.py` 5, `indicators.py` 2, `legend.py`
  1, `panels.py` 1, `preview.py` 1, plus layout margins and spacings (`setContentsMargins`, `setSpacing`, fixed
  widths) all over; the "no pixel size in GUI code" test needs a definition (Q9).
- **Item-widget lists** (`QTableWidget`/`QTreeWidget`/`QListWidget`): `dialogs.py` 18, `command_palette.py` 5,
  `project_tree.py` 1, `tables.py` 1. All small data, except possibly the project-tree one (checked in M4).
- **GUI-thread work that exceeds 50 ms** (measured or by reading): theme and scale change (550 to 950 ms); project
  open/install (150 ms flatsat, 1.3 to 1.5 s stress); first show of Harness/Lists/Devices tabs (35 to 63 ms, built
  eagerly); import-file parse and preview; save; interface-table rebuild at stress size; Releases diff; applying a rule-check
  result (about 50 ms at stress size). To measure in M1 with an optional timing log.
- **Threads:** `background.py` (`JobRunner`), `PlanWorker`, `ArrangeWorker`, `OutputsWorker`, `DrcWorker` +
  `drc_process.py`. These stay as they are.
- **Dialogs, classes:** ConfirmDialog, WaiverDialog, NewInterfaceDialog, WireColoursDialog, ImportDialog,
  GlossaryDialog, IssuesDialog, GeneratePreviewDialog, ChangeDialog, DiffDialog, HistoryDialog, ExportDialog,
  ConfigValueDialog, NewProjectDialog, import wizard (file, columns, result), six device dialogs, CommandPalette
  (overlay), Tour (overlay).

## 3. Findings per screen

Each finding is something a user sees. IDs are used by the milestones.

### Shell (01, 02, 40, 41, 42; menu-*)

- **S1 Five rows of chrome before any content.** Menu bar, toolbar (Undo, Redo, Guided, Expert, Arrange, Search,
  filter), title row (name, hash, saved, Generate, Check, Export, chip), tab row, tool row. At 1440×900 about
  200 px (22 %) of the height is controls (01). Convoluted and cluttered.
- **S2 Same command in up to four places.** Generate is a button, a menu item, a palette entry and a stepper-like
  chip; Export is a toolbar button, two menu items and a window; Delete, Create redundant copy and Zoom exist in the
  menu, the diagram tool row and the inspector. Users cannot tell which is "the" place.
- **S3 Boxed, zero-radius, 1 px border everything.** Every control and chip has a hard outline; there is no
  elevation or grouping, so nothing reads as primary except the blue Generate button. This is the "raw, outdated"
  impression (01, 05, 07).
- **S4 Project identity is cramped and truncated.** "Flatsat (EXAMPLE n… engineering data)" is cut in the title
  row at every size; the 8-hex "model" hash (44716722) is shown next to it and again in the status bar and again in
  "Generated at model 5cc39057". Hashes are for traceability, not for the primary line (01, 41).
- **S5 State is told in five dialects.** "Saved" text, "Plans up to date" chip, "Outputs not exported yet" box inside
  the canvas, "4 values pending · 12 rules not checked" in the status bar, per-harness chips (Up to date, Not
  exported, Check passed) in the Harness tab. The user's real question — *where am I in generate → review →
  release?* — has no single answer (01, 03, 05).
- **S6 Problems are hidden in a right-hand tab** ("Problems (28)") next to Inspector and Why, so it competes with
  the inspector for the same 300 px column (09 to 11).
- **S7 Status bar is a text dump.** Seven fields, project path, model hashes; no job list, no progress, no cancel
  (the check progress sits in a chip at the right). It clips at 1150 px (41).
- **S8 Narrow windows break.** At 1150×400 the Undo button grows to "Undo Release W001 revision A", the toolbar
  overflows, inspector tabs are cut ("Problems" half visible), the status bar is truncated, the diagram has about
  150 px of height (41). At 1280×720 the diagram is usable but the inspector has dead space (40).
- **S9 Menu bar carries workflow items** (Design menu: Generate, Run checks, Submit, Release, Start new revision,
  Show changes, Delete harness, Engineering values) that are the product's main flow and are buried (menu-design).
  The Edit menu has a 15-item "Add unit" submenu of example unit kinds plus a 17-item "Connect with" submenu
  (menu-edit): lists, not commands.
- **S10 Guided/Expert is a toolbar toggle** that changes what the inspector and tables show; it is a user
  preference, but it sits next to Undo as if it were an action (01, 02).
- **S11 Left dock is a project tree with 23 units in one flat list** and a second tab "Interfaces"; a "Filter" and
  an "Add" button with a drop-down. The tree duplicates the Devices tab, the Interfaces tab duplicates the interface
  table (Ctrl+Shift+T) (01, 08).

### Diagram (01, 02, 51)

- **D1 Legend and minimap cover a quarter of the canvas by default** (01); the legend alone is 20 lines. It should
  be a collapsed popover.
- **D2 In-canvas toolbar** (Select, Connect, Create redundant copy, Delete, zoom out/in, Fit) is a second toolbar
  over the canvas and uses text buttons with 1 px borders.
- **D3 The canvas itself is good** (lanes, link routing, badges) and out of scope except colours and fonts from
  tokens; the brief allows theme colours for on-screen diagram styling.
- **D4 "All interfaces" filter combo is in the global toolbar** but only filters the diagram.
- **D5 100 units (51): readable but 1 s to repaint at full zoom in software rendering**; unchanged canvas code, so
  no promise beyond "no regression".

### Harness tab (03)

- **H1 Four status chips plus five buttons plus a "More" menu in two rows** (Draft·rev A, Up to date, Not exported,
  Check passed; Regenerate, Export, Open in review, Release, Revise, More). That is the generate → review →
  release flow, spelled as buttons; it should be the stepper.
- **H2 Three stacked tables and a drawing share one tab**: connectors/pins (clipped, "36 pins shown, 126 spare
  hidden"), wires, "Why" text box. Drawing preview is small (about 36 % of the tab) with a nested toolbar (zoom,
  Fit, previous/next sheet).
- **H3 Columns are clipped on the right** (wires table "To" shows "W001-P11." cut).

### Lists (04)

- **L1 Tabs inside a tab**: Wire list, Pinouts, BOM, Mass and length, Test tables, Labels, System BOM (7 sub-tabs
  inside the tab "Lists"). These are generated documents, so they belong with Outputs, one entry each.
- **L2 Table is plain and dense but fast** (model/view); no column-visibility menu, no Excel-style copy confirmed in
  the UI, no empty-state action. Numeric columns (AWG) are not right-aligned with units in the header.

### Checks (05)

- **C1 Table shows 14 of 34 rules in 40 % of the tab and the rest is an empty area** ("Select a rule to see what it
  found") — the result list is cramped while the space below is unused.
- **C2 State vocabulary**: "Pass", "Pass (placeholder values)", "Pending", "Not checked", "pending values" — five
  ways to say "not a real pass". Colour plus icon is correct (a test already checks colour is never alone); wording
  is for the owner to confirm, since it is domain language. I will not rename without approval.
- **C3 Problems exist twice** (Checks tab and the Problems tab/panel on the right) with different layouts.

### Releases (06, 36, 37, 38)

- **R1 Timeline table columns are clipped** ("Comment" cut, "B…" column hidden at the right edge) (36).
- **R2 Diff area: a filter list "All kinds (0)" beside an empty table** and the empty message above them — the empty
  state offers nothing to do (36).
- **R3 Locked state is shown in four places** (lock icons in the tree, "Released W001 A" banner in the inspector,
  chip, read-only fields) and is good in intent; the brief's "unmistakably locked" is met in content, not in
  hierarchy: there is no banner across the work area explaining how to start a new revision (it is in the
  inspector only, 36).

### Devices (07)

- **V1 Five stacked regions in one tab**: connectors list, part panel, pin table, connector notes, "Pinout as
  exported". Each has its own header, scroll bars and buttons (Add connector, Delete connector, Add pin, Delete,
  Fill…, Assign…, Contact), so it looks busy and clips (pin table's last column "S" cut; part drop-down text
  cut).
- **V2 This is a spreadsheet job done with form widgets.** Pin allocation by `Assign…`/`Fill…` buttons and a
  separate Part panel; no inline edit with arrow keys, no multi-row bulk edit, no paste from Excel. This is the
  main target of M4.

### Inspector (09, 10)

- **I1 Empty vertical space and a tiny 4-row "Used in (39)" table** with clipped columns; the inspector shows 8
  fields and a paragraph of help text, then nothing.
- **I2 "Why" and "Problems" are tabs of the inspector**, so the inspector can show only one of the three.
- **I3 Fields are edited in place** (good) but labels are ALL CAPS section headers plus plain labels; no units
  suffix, no inline validation messages.

### Dialogs (20 to 38)

- **X1 Plain white, zero-radius, no elevation or title bar styling**; buttons right-aligned with an unusual
  purple focus ring (20, 21). Consistent but dated.
- **X2 Too many modals.** Export (29, 30) is a full 1000×620 window that is really a screen (file tree, file list,
  preview, reveal/open buttons). Engineering values (28), Wire colours (23), New interface (22), Glossary (24),
  Known issues (25), Changes (38) are information or editing surfaces that the brief wants inline. Modals that stay:
  Delete impact (21), Release (33), New revision (37), waiver (needs justification), Generate preview (20; it
  applies a change and says Undo reverses it — kept as a confirmation), the wizards.
- **X3 Import wizard (31, 32)** is already a 3-step wizard with a live preview (good); the column page has 13
  drop-downs in a form grid; word-mapping fields ("Approved when it says") have no hint of the accepted words.
  (In picture 32 every row says "Skipped" because the screenshot harness leaves the three word fields empty; that
  is the harness, not a defect.)
- **X4 Export window**: tree of 3 harnesses × 11 documents with check boxes, a 113-file table, preview, three
  buttons. It shows size but **no checksum** and no timestamp; the brief's Outputs list wants type, format,
  timestamp, checksum.
- **X5 Command palette (12)** is a plain list over a half-transparent canvas with one text row; no icons, no
  grouping, no recent items, no objects (only commands).
- **X6 First-run tour (13)** is a pop-over on the live window; keep, restyle.

### Empty state (50)

- **E1 The first start works** (Generate, Check, Export visible, tree with example data, helpful inspector text) but
  has no Home: new project, open, examples and recent projects are in File and in empty-state text of the tree.

### Dark theme (all `_dark`)

- **T1 Carbon grey-100 (#161616) with blue**: contrast is adequate (tests pass) but there is no layering: canvas,
  panels and tables are all one black, and the 1 px borders carry the whole structure (07 dark).
- **T2 Switching takes 0.55 to 0.95 s** and is available only from View > Theme (three radio items). Follow-system
  is already the default.

### Cross-cutting

- **Z1 Fonts:** IBM Plex Sans looks right at 13 px but is wide; at the sizes used the Mono IDs are good — this is the
  one thing users will keep asking for: IDs in a mono face. Inter + JetBrains Mono keeps that.
- **Z2 Keyboard:** shortcuts and F6 panel cycling exist; focus ring is the purple Carbon 2 px (works).
- **Z3 Scale:** 100/125/150/200 % (brief: 90/100/110/125 %); Q8.
- **Z4 Tooltips** exist on icon buttons (D-146 enforces name + shortcut).

## 4. Information architecture (every current tab, menu and dialog mapped)

Shell: **left nav rail** (Home, Model, Checks, Drawings, Outputs, Revisions, Settings; icon + label, collapsible),
**top bar** (project name, save state, revision, breadcrumbs, Undo/Redo, Guided/Expert segmented control,
workflow stepper Generate → Review → Release, Ctrl+K field), **workspace** (tabs per area), **right inspector**,
**bottom** status bar and a collapsible **Problems panel**. The menu bar stays (Q5) but shrinks.

| Today | New place | Notes |
|---|---|---|
| (none) | **Home** | Projects with revision/state badges, recent projects, new, open, flatsat example, sample project, first-run tour entry, Known issues |
| Tab Diagram | **Model › Diagram** | Canvas unchanged; legend becomes a popover; the in-canvas tool row becomes a slim canvas toolbar with icons; "All interfaces" filter moves into it |
| Left tab Project (tree) | **Model** side tree | Same tree, restyled; stays the master list for the inspector |
| Left tab Interfaces; Go > Interface table (Ctrl+Shift+T) | **Model › Interfaces** | Spreadsheet table (M4) |
| Tab Devices | **Model › Connectors and pins** (M4), with **Units**, **Wires** and **Cables** as sibling tabs fed from the generated plan | One master-detail table pair instead of five stacked regions |
| Edit > Add unit (15), Connect with (17), Align, Space evenly, Add zone, Wire colours | Diagram toolbar, palette, context menu; Wire colours becomes a column of the Wires/Signals table | Palette keeps every command |
| Tab Harness | **Drawings** (preview + connectors/pins/wires of the selected harness) | The stepper replaces the chip/button rows |
| Tab Lists (7 sub-tabs) | **Outputs › Documents** (one entry per list: Wire list, Pinouts, BOM, Mass and length, Test tables, Labels, System BOM), shown in the central table | No tabs inside tabs |
| Export window (Ctrl+E) | **Outputs** area (list with type, format, timestamp, checksum; Open, Reveal, Copy to folder); the modal goes away | Export itself still goes through the existing `OutputsWorker` |
| Tab Checks | **Checks** (rules table) and **Problems panel** (bottom) | Rule-result vocabulary unchanged without approval |
| Engineering values dialog; Design > Engineering values | **Checks › Engineering values** tab | |
| Right tab Problems | **Problems panel** (bottom, collapsible) | Click to jump to the object |
| Right tab Why | Inspector section "Why" (collapsible) | |
| Right tab Inspector | **Inspector** | Collapsible sections, unit suffixes, inline validation |
| Tab Releases | **Revisions** (timeline, diff with diff tokens, locked items) | Diff view replaces ChangeDialog/DiffDialog/HistoryDialog |
| Design > Submit for review, Release, Start new revision, Show changes/log, Delete harness | Stepper actions and Revisions toolbar; modals only for Release and New revision | |
| View > Theme, Interface size, Guided/Expert, Reset layout, panels, Snap to grid, Show overview map/legend/link labels | **Settings** (Appearance, Editor) plus View menu items for the diagram toggles | |
| Project configuration (tree node "Configuration": derating, emc, generation, naming, segmentation, segregation, titleblock) | **Settings › Project** (and Engineering values in Checks) | Q6 |
| File > New/Open/Open sample/New from example | Home, plus File menu | |
| File > Import (6 kinds) | **Model** toolbar "Import" menu → one wizard (M7) | Same parsers |
| Dialog New interface | Inline popover or inspector form on the Interfaces table (M4) | |
| Dialog Glossary | Help area reachable from the palette; searchable list | |
| Dialog Known issues | Home › Known issues | |
| Dialog Generate preview | Stays a modal confirmation (applies a change) | |
| Dialog Delete impact, Waiver, Release, New revision | Stay modal (destructive or needs justification) | |
| Command palette | Same overlay, restyled; adds objects (units, interfaces, harnesses) and settings | |
| Tour | First-run overlay on Home | |
| Status bar fields | Status bar: jobs with progress and cancel, last run, offline indicator ("Offline: nothing leaves this machine"); model hash moves to a tooltip and to Revisions | |

Nothing is dropped: every menu action stays as a `QAction` with its shortcut and is reachable from Ctrl+K.

## 5. Milestones

Each ends with: the screenshot harness re-run into `docs/ui/screenshots/m<n>/`, `tools.ui_perf` numbers pasted
into the summary, all existing tests green (CI on Linux, Windows, macOS), golden files and outputs untouched, a
`docs/DECISIONS.md` entry for each choice, and `ruff`/`mypy` clean. Work on a branch per milestone, one PR each.

**M1 Foundation.**
- `gui/theme/` package: `tokens.py` (single source: the brief's table, tuned only where WCAG AA demands, changes
  recorded), `qss.py` (style sheet generated from tokens), `manager.py` (`ThemeManager` API kept), `fonts.py`,
  `icons.py`. Inter (400/500/600) and JetBrains Mono (400/500) as bundled TTF with OFL texts; tabular figures via
  `QFont.setFeature` (Qt 6.11). Radius 6/8, control height 28/32, row 26, 4 px grid, focus ring 2 px accent,
  shadows only on floating widgets. Reduce-motion setting (the motion helper added here).
- **Live theme switching without a style-sheet rebuild of the whole tree:** palette plus a small set of
  dynamic-property rules, so a switch takes under 150 ms (today 0.55 to 0.95 s). Same for UI scale.
- Carbon removed (tokens, style sheet, IBM Plex files, packaging references, docs); D-entry in `DECISIONS.md`.
- Icon set extended to what the new shell needs (nav rail 20 px, 16 px elsewhere); stays Lucide.
- Tests: no hex colour, font-family name or font size (px/pt) outside `gui/theme/` (AST-based, with an allow-list
  for the diagram canvas's pen widths, Q9); contrast test for every text/background pair in both themes;
  fonts test (new files, licence texts); smoke test of both themes without Qt warnings.
- Optional timing log (`HARNESS_UI_TIMING=1`) and `tools.ui_perf`; re-measure the 11 s stress finding on CI.
- *Acceptance:* theme switch ≤ 150 ms and scale change ≤ 250 ms on the flatsat in `tools.ui_perf`; no
  `Carbon`/`IBM Plex` string left outside CHANGELOG history and DECISIONS; start-up not slower than baseline +10 %;
  packaged program (PyInstaller, Windows, macOS) shows the new fonts (`tests/test_packages_*`, smoke test).

**M2 Shell.**
- Nav rail, top bar (project, save state, revision, breadcrumbs, Undo/Redo, mode switch, Ctrl+K field), central
  workspace with per-area tabs, right inspector with sections, bottom status bar with a **job list (progress,
  cancel)** and offline indicator, collapsible Problems panel (list only; filled in M5), layout saved per project
  (`QSettings` key under the project path hash, no change to project files).
- Existing tabs move into their new areas unchanged in content; `MainWindow` keeps its attribute names and
  `go_to(name)` as a compatibility layer (Q2).
- Narrow-window behaviour: rail collapses to icons below 1100 px, inspector becomes a drawer below 1000 px; 1150×400
  stays usable.
- *Acceptance:* every current menu action reachable by menu and by Ctrl+K; F6 cycles regions; 1150×400 has no
  clipped controls (picture 41 redone); first-interactive time ≤ baseline +10 %; no existing test edited except the
  list agreed in Q2.

**M3 Home and workflow stepper.**
- Home with recent projects (stored in `QSettings`), project cards with revision/state badges (read from the
  project; no format change), examples, new, open; empty states with a primary action everywhere a list can be
  empty. Stepper Generate → Review → Release replacing the chips and button rows (S5, H1); released items show a
  lock banner across the workspace with "Start new revision" (R3).
- *Acceptance:* stepper state equals the existing logic (`plans up to date`, check results, release state) in a
  test over all combinations; the banner appears on every released harness; screenshots 01, 03, 34, 35, 50 redone.

**M4 Model editors.**
- Interfaces, Units, Connectors/pins, Wires as spreadsheet-like tables: virtualised, inline edit (Enter to edit,
  Esc to cancel, arrows), multi-row bulk edit, **Ctrl+C/Ctrl+V as TSV to and from Excel**, filter and search,
  column-visibility menu, right-aligned numerics with units in headers, JetBrains Mono for IDs, pin numbers,
  part numbers; master-detail with the inspector. Editing goes through the existing controller commands (so core
  `History` undo stays; `QUndoStack` is **not** adopted because core `History` is the undo of record, Q7).
  Devices tab replaced by Connectors/pins + Part panel. New interface becomes inline.
- *Acceptance:* 200 units/2,000 interfaces table opens ≤ 200 ms and scrolls without dropped frames in the
  benchmark (`tools.bench_gui` plus a new table benchmark); paste of 500 rows applies as one undo step; keyboard-only
  edit of a pin table works (test); every existing `devices`, `ux_*` and `gui_*` test still passes.

**M5 Checks and Problems panel.**
- Problems panel: severity, rule ID, object, message; filter by severity; click jumps to the object (diagram,
  table row or inspector). Checks tab: results list uses the full area; engineering values as a tab; "results are
  stale" indicator; automatic debounced re-run (~250 ms) **only if** the stress-size finding is resolved,
  otherwise on demand.
- *Acceptance:* edit-to-stale indicator ≤ 100 ms at stress size; rule check never blocks the GUI thread > 50 ms
  (main-thread time while applying a result is measured and capped); jump-to-source test for each object kind.

**M6 Drawing preview.**
- Drawings area: the existing harness preview widget with theme-coloured chrome, zoom, pan, fit, sheet paging,
  click-to-select linked to the inspector where the drawing data allows it (the SVG writer's own element ids; no
  change to written files — checked byte-for-byte). Rendering of the preview stays in the existing worker.
- *Acceptance:* the written SVG/PDF of every example is byte-identical to 1.2.0 (existing golden tests plus a
  hash comparison script); fit/zoom/pan under 50 ms per frame on flatsat.

**M7 Imports wizard.**
- One wizard for the six import kinds: choose file → map columns with live preview → validation results → diff
  summary to accept or reject. Word-mapping fields show the accepted words. Parsing and preview move to a
  worker with cancel.
- *Acceptance:* each kind imports the packaged sample through the new wizard with the same project result as
  before (existing import tests unchanged and green); a 20,000-row file keeps the GUI responsive.

**M8 Outputs and Revisions.**
- Outputs area: one list of documents with type, format, timestamp, checksum (computed in a worker from the
  written files), Open, Reveal, Copy to folder; the Lists tables as entries. Revisions area: history timeline,
  diff view with the added/removed/changed tokens, locked and recorded items per revision.
- *Acceptance:* checksums equal `SHA256SUMS`-style hashes of the files on disk; Export results identical to
  1.2.0 byte-for-byte; diff view agrees with `core.vcs` change records in a test.

**M9 Settings.**
- Appearance (theme: system/light/dark, UI scale 90 to 125 % plus existing steps if kept, reduce motion), editor
  (mode, snap, labels), project configuration, shortcuts list, about, licences (fonts, icons).
- *Acceptance:* every setting persists across restarts and applies live; both themes pass the contrast test.

**Final milestone: performance, accessibility, documentation, release.**
- Performance pass against `PERF_BASELINE.md`; accessibility pass (keyboard-only walk of every area; visible
  focus; tooltips on every icon-only button; contrast); `docs/ui/screenshots/after/`; `docs/ui/BEFORE_AFTER.md`;
  user-guide screenshots rebuilt; `CLAUDE.md` design rules (written in M1, finished here); CHANGELOG; version
  **1.3.0** (Q3); platform packages built and smoke-tested on Windows and macOS; the clean-machine install check
  that is waiver T-30 stays open.
- *Acceptance:* all "Definition of done" lines in the brief; outputs of all examples byte-identical to 1.2.0.

Rough size: M1 and M2 are the heaviest (each about a full session or more), M4 the riskiest, M3 and M5 to M9
moderate.

## 6. Tests: what must stay and what has to change

2,163 tests, 59 GUI test files (about 19.5k lines). Most drive `MainWindow` through its attributes: `win.ctl` (591
uses), `win.view` (236), toasts, `interface_table`, `devices_view`, `harness_view`, `dock_left`, `dock_right`,
`left_tabs`, `main_tabs`, `go_to(...)`. Counts of what is structure-bound: `main_tabs` 22 uses in 8 files, `left_tabs` 11
in 5, `dock_left` 22 in 6, `dock_right` 18 in 7, `toolbar` 7 in 7, `menuBar` 6 in 4, `go_to` 20 in 11.

My plan to honour "all existing tests pass unchanged" as far as it can be honoured:

1. Keep every `MainWindow` attribute and method the tests use as a **compatibility layer** that points to the new
   widgets (`go_to("lists")` selects Outputs › Wire list; `main_tabs` stays as a thin object with the same
   index/text API). No test edit needed for these.
2. Three test files assert the **old look**: `test_fonts.py` (IBM Plex files and family names), `test_tokens.py`
   (imports `gui.tokens`, token names such as `surface-2`, the type scale 12/13/16/20 and the 32 px control height; its
   contrast and colour-blind checks stay as they are and run on the new tokens), and the font/height parts of `test_ux_foundation.py` and
   `test_ux_tree.py` (family == "IBM Plex Mono", 32 px control height). The brief requires Carbon and IBM Plex to
   be removed completely, so these assertions cannot pass unchanged. I propose to **replace those assertions with
   the same checks against the new tokens and fonts** (same intent, new constants), and list every edited
   assertion in the milestone's PR for your review. Q2.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Test edits beyond the three files above (layout-dependent tests) | Compatibility layer; each edited assertion listed in the PR; stop and ask if more than a handful |
| Inter/JetBrains Mono on Windows (Qt cannot load WOFF2) and macOS | Bundle TTF; verified in the platform workflow and the packaged smoke test |
| Packaged programs leave out QtSvg | Keep path-based Lucide icons (no QtSvg); no new Qt module in the package |
| Live theme switch cannot reach 150 ms with QSS alone | Fall back to palette + fewer QSS rules; measure early in M1 before building on it |
| Stress-size edit stall with the rule check on (11 s in the benchmark) | Re-measure first (M1); if it is in the core check, stop and ask |
| Spreadsheet editing (M4) disagrees with controller commands/undo granularity | Route every cell edit through existing controller commands; paste = one `History` group |
| Window-geometry or layout state from users of 1.2.0 | New settings keys; old keys ignored, never migrated destructively |
| 13 MB of before-screenshots in git | Acceptable once; `after/` and per-milestone sets are not committed except the final set (Q10) |
| Scope creep into the canvas, drawings or generated files | Hard rule restated at the start of each milestone; M6 has a byte-identity check |
| CI time (Linux ~32 min; macOS runner queue) | One PR per milestone, no combined PRs |

## 8. Questions for you

1. **AIT feedback.** None exists in the repository (no FEEDBACK.md, no issues). Can you send it (even as raw
   notes)? It would change M3 to M5 priorities. Until then I treat the findings above as the priority list.
2. **Tests that assert Carbon/IBM Plex.** May I replace the assertions in `test_fonts.py`, `test_tokens.py` and the
   font/height parts of `test_ux_foundation.py`/`test_ux_tree.py` with the same checks on the new tokens and
   fonts, and keep a `MainWindow` compatibility layer for everything else? (The alternative, leaving Carbon in,
   contradicts the brief.)
3. **Version.** 1.3.0 (next minor after 1.2.0). Correct? (The brief's example says 1.0.0 to 1.1.0.)
4. **Plots, WebEngine, plotly.js, Graphviz.** None exist in this tool. Confirm that the Plotly template, linked
   time cursors and WebEngine rules are out of scope.
5. **Menu bar.** Keep a compact menu bar (File, Edit, View, Go, Help; Design items moved to the stepper)? It keeps
   shortcuts and discoverability on Windows/Linux and costs about 24 px; the alternative is no menu bar, only the
   palette and the rail.
6. **Project configuration files** (derating, emc, generation, naming, segmentation, segregation, titleblock):
   under Settings › Project, or under Model? And engineering values under Checks (my proposal)?
7. **Undo.** Keep core `History` as the one undo (my proposal) rather than `QUndoStack`? Replacing it means core
   changes, which are out of bounds.
8. **UI scale.** Brief says 90/100/110/125 %; the tool offers 100/125/150/200 % (150 and 200 are there for
   accessibility). Keep all of 90 to 200?
9. **"No pixel size in GUI code".** I propose: no font size and no QSS/px literal outside `gui/theme/`, and
   spacing/margins only as multiples of the 4 px grid from named constants; canvas pen widths in an allow-list.
   OK?
10. **Screenshots in git.** Commit only `before/` (now) and `after/` (final)? Per-milestone sets stay out of git.
11. **Icons.** Keep Lucide as `QPainter` paths (no QtSvg in the packages) instead of loading SVG files at run time —
    this meets "Lucide, bundled, tinted from tokens" without a new Qt module. OK? I would add a dev script that
    converts Lucide's SVG to the path table so the SVGs remain the source of truth.
12. **Names.** Nav areas as in the brief (Home, Model, Checks, Drawings, Outputs, Revisions, Settings). Are
    "Drawings" (harness drawing + its tables) and "Outputs" (generated documents) the right split for your
    users, or should drawings sit under Outputs?
13. **New dependencies:** none planned (fonts are data files). Confirm no objection to adding two font families
    (about 1.5 MB, OFL) to the package and to the licence report.

## 9. What happens next

Nothing is implemented until you approve this plan. After approval: *"Implement milestone M1 from
docs/ui/UI_OVERHAUL_PLAN.md. Stop when its acceptance criteria pass."* I will start by re-measuring the stress
stall and the theme-switch cost, because the answers decide how M1 is built.
