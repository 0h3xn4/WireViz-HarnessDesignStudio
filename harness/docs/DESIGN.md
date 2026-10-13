# Design system of the editor

What the editor is made of and why: tokens, type and spacing, themes, icons, state chips, tables, the diagram, the window, the views, shortcuts, and a list of decisions. The code is the source: `gui/tokens.py` (values), `gui/theme.py` (palette, style sheet, fonts), `gui/icons.py`, `gui/states.py`, `gui/tables.py`. `tests/test_tokens.py` checks contrast and colour-blind separation of the tokens and `tests/test_ux_foundation.py` the rest of the foundation; each view has its own test file (named in the sections below).

The standard behind it is "UX/UI Standard: Harness Design Studio"; the audit against it and what was built for each issue is in [`ux-audit.md`](ux-audit.md) (issue IDs such as SH-6, CV-7, SC-12 appear in brackets below). Rules for code in `gui/`: tables are `tables.TableView`, states are `states.StateChip` or `StateDelegate`, icons come from `icons.py`, no widget calls `setStyleSheet` and no code holds a `#RRGGBB` literal, every string is in `gui/strings.py`.

Contents: [Tokens](#tokens) · [Type and spacing](#type-and-spacing) · [Themes](#themes) · [Icons](#icons) · [State badges and chips](#state-badges-and-chips) · [Tables](#tables) · [The diagram](#the-diagram) · [The window](#the-window) · [Views](#views) · [Shortcuts](#shortcuts) · [Decisions](#decisions)

## Tokens

| Token | Use |
|---|---|
| `bg`, `surface`, `surface-2`, `border`, `text`, `text-muted` | Surfaces, lines and text |
| `primary`, `on-primary` | The one accent: the primary action and the selection |
| `focus` | Keyboard focus ring |
| `error`, `warning`, `success`, `info` | Severity and pass / fail |
| `pending`, `not-checked`, `stale` | A value or result that is not known yet, a rule that could not run, outputs older than the model |
| `locked`, `released` | Locked items, released harnesses |
| `auto-fill` | Auto-filled, not reviewed |
| `paper`, `pasteboard` | The drawing preview: the sheet (white in both themes, it is a picture of paper) and the table it lies on |
| `cat-*` | Interface categories on the canvas ([colours](#interface-colours)) |

Text tokens meet 4.5:1 on `bg`, `surface` and `surface-2` in both themes; borders, focus and category colours 3:1. The clickable prototype (`prototype/`, built by `tools.build_prototype`) reads the same values.

## Type and spacing

- Type scale in px: `sm` 12 (captions, canvas labels, table cells, status bar), `base` 13 (body), `md` 16, `lg` 20. IBM Plex Sans for the interface; IBM Plex Mono for pin, wire and part numbers, IDs, requirement IDs, hashes and paths (`mono` property, `theme.mono_font()`, `mono_item_font()` in models).
- Spacing in px: 4, 8, 12, 16, 24, 32. Every control (button, combo box, line edit, spin box) is 32 px high at 100 % scale, set in the theme with `min-height` and `max-height`.
- Both are multiplied by the UI scale (100, 125, 150, 200 %; View > Interface size).
- API: `theme.color(token)`, `theme.type(name)`, `theme.space(n)`, `theme.font(...)`, `theme.mono_font()`, `theme.control_height()`, `theme.icon_size()`; `current_theme()` for widgets built without a reference to the window's manager.

## Themes

- Three modes: **System** (default, follows the operating system's light/dark scheme while the program runs), **Light**, **Dark**. The choice is stored as `ui/theme` (`system`, `light` or `dark`); View > Theme. A damaged value falls back to System.
- `ThemeManager.apply()` builds a `QPalette` and the style sheet from the tokens. The only `setStyleSheet` call is the theme's; widgets pick up rules by property: `primary`, `danger`, `muted`, `heading`, `align="left"`, `mono`, `iconOnly`, `toggle`. A test checks that no widget styles itself and that no hex literal or literal pixel size is left in `gui/` (the logo in `appicon.py` is the one brand exception).
- The first UI scale follows the screen height (1300 px: 125 %, 1600: 150 %, 2000: 200 %) unless the system already scales (ratio 1.5 or more); the person's choice is saved and wins. (SH-26)

## Icons

Lucide geometry (ISC licence, D-146) painted with `QPainter` from path strings; no SVG file at run time, because the packaged program leaves out QtSvg. `icons.icon(name, theme, role)` returns a `QIcon` that repaints in the theme's colours at any size, so a theme change needs no rebuild. Stroke width is 2/24 of the size, at least 1.5 px. Every icon button has an accessible name and a tooltip that names the shortcut: `icons.icon_button(button, name, theme, label, shortcut)`; a tooltip reads "text (shortcut)". The paths for the project tree (cpu, plug, package, shapes, sliders-horizontal, plus) were typed from the Lucide set and should be diffed against lucide-static 1.56.0 when a copy is at hand. (SH-25)

## State badges and chips

One look for a state everywhere (table cell, card, header): icon, word and, for the two "nothing known yet" states, a pattern. Colour is never the only cue; a test renders the chips in grey and checks that they still differ.

| State | Icon | Word | Colour token | Border and fill |
|---|---|---|---|---|
| pass | circle-check | Pass | `success` | solid |
| fail | circle-x | Fail | `error` | solid |
| warning | triangle-alert | Warning | `warning` | solid |
| info | info | Info | `info` | solid |
| pending | clock | Pending | `pending` | dotted border, dotted fill, italic |
| not-checked | circle-dashed | Not checked | `not-checked` | dashed border, hatched fill, italic |
| locked | lock | Locked | `locked` | solid |
| released | package-check | Released | `released` | solid |
| stale | refresh-cw | Out of date | `stale` | solid |
| draft | file-pen | Draft | `text-muted` | solid |
| in-review | eye | In review | `info` | solid |
| revised | rotate-ccw | Revised | `primary` | solid |

- An empty cell shows nothing at all, so pending and not-checked can never be taken for empty, pass or fail. Selected rows draw the chip in `on-primary`. (SH-28)
- `pending` is teal and dotted, `not-checked` is slate and hatched, `stale` is orange; none of them is the green, red or amber of pass, fail and warning, and each has its own icon and word. (SH-28)
- Chip fill is a 4 % tint so text on it keeps AA contrast on all three surfaces; a test computes it. (SH-28)
- A result is one of pass, fail, not checked or pending; a pass that read a placeholder file says "Pass (placeholder values)" so a pass never looks reviewed when it is not. (SC-1, SH-28)
- Release states use the same words everywhere (tree, tables, Harness header, Releases): Draft, In review, Released · rev B, and Revised · rev B for a draft that is a later revision of a released harness. (SC-5, SH-6)
- A cell that is `pending`, `TBD (placeholder)`, an unknown part category, a part missing from the parts list, or a length that could not be worked out is a chip, so it cannot be taken for an empty cell or a pass. (SC-11)
- A filter that is on or off is a toggle button (fill, icon and word change when pressed), not a check box: the tick box of a `QCheckBox` has no border in the dark theme and cannot be seen. (SC-9, SC-11)
- A checked toggle in a tool row (Guided, Expert, Select, Connect) is neutral: bold text on the raised surface with a 3 px bar under it (`toggle` property), so selected is told by weight and shape as well as colour. Generate is the only accent-coloured button of the window, and the Fix buttons of problem cards are not primary. (SH-1, SH-24)
- Inline notices (`gui/notice.py`) carry an icon and a word for error, warning and note next to the colour, with the left bar the style sheet already used for banners. (SC-12)
- A disabled OK button always has a line under the form that says what is missing ("write at least 10 characters in the comment (3 more to go)"), and the same text is the button's tooltip; a disabled action's tooltip is the reason ("Only a released harness can be revised."), an enabled one's is what it does. (SC-15)

## Tables

`DictTableModel` (rows as dicts or tuples, `Column` specs) + `TableProxy` (sort by number or natural text, filter by words, state or predicate) + `TableView` (header stays in view, cell selection, state chips, saved widths). Numbers are right-aligned with tabular figures, units are in the header ("Length (m)"), pin / wire / part numbers are monospace. Ctrl+C copies the selected cells as tab-separated text, Ctrl+Shift+C adds the header row.

- A new table starts in the order the rows are given; a click on a header sorts. Column widths and the sort order are saved. (SC-21, SH-10)
- A list's columns are measured from the model (header, longest cell, widest chip) and re-measured when the harness changes, so a "pending" chip is never cut off; the Harness view's columns have fixed widths so that showing a harness does not measure hundreds of chips. (SC-7, SC-11, SC-24)
- Tables are `QTableView` over a model, never `QTableWidget`; a test checks the table code. The old Harness plans panel, the older import dialog and the wire colours window still hold `QTableWidget`s (SC-21).

## The diagram

Code: `gui/canvas.py` (scene, items, view, `CanvasMetrics`), `gui/legend.py`, `gui/canvas_state.py`, `gui/canvas_badges.py`, `gui/glyphs.py`. Tests: `test_gui_canvas_ux.py`, `test_gui_canvas_state.py`, `test_canvas_state.py`, `test_describe_cstate.py`.

### Interface colours

Each category has its own colour, line weight and letter, so colour is not the only cue: Power (3.5 px, `P`), Data (2, `D`), Analog (1.5, `A`), RF (2.5, `R`), Pyro (4, `!`), Discrete (1.5, `d`), Ground (1, `G`); redundancy is a dashed line. Thermal links share Analog, other links share Ground. Values in `gui/tokens.py`. Far away a link still says what it is: below 50 % each category has its own dash pattern (analog, RF, pyro, discrete, ground; power and data stay solid) and a small plate with the kind's picture is drawn at a fixed screen size (up to 400 links); the selected or hovered link is drawn in full with a label never under 18 px. (CV-21)

### Selection, navigation and editing (canvas)

- **Selection is a set.** `EditorController.selected` holds every selected item in the order picked; `selection` stays the primary (last picked) one, so the panels and tests that read one item keep working. Click selects one, Shift-click and Ctrl-click add or remove, a drag on the background draws a rubber band (units it touches, links it holds entirely), Ctrl+A selects all. (CV-1)
- **One undo step per action.** Deleting, moving, aligning, spacing, duplicating and editing several items each run as one `History` transaction (`core/edit.py`: `ops_delete_many`, `ops_move_units`, `ops_align`, `ops_distribute`, `ops_duplicate_unit`). (CV-1, CV-2)
- **Align is by the heights drawn now.** The window passes the item heights (Guided and Expert differ). Aligning side to side across lanes changes the unit's zone, as moving it does. (CV-2)
- **Duplicate copies connectors, never links or pin assignments** (those belong to the original); the copy gets a new ID from the original's prefix and sits in the same lane. (CV-2)
- **The wheel never zooms by itself.** Ctrl+wheel zooms at the pointer (1.2 per notch), the wheel scrolls up and down, Shift+wheel sideways, a trackpad scrolls by pixels. Middle button or Space with a left drag pans and never moves a unit. (CV-3)
- **Bare-key shortcuts act only in the diagram.** `F`, `Shift+F`, `Ctrl+A`, `Ctrl+D`, `Ctrl+F` and `Delete` work only while the diagram (and for Delete the interface table or the outline) has the keyboard focus, so they cannot act from another panel. (CV-4, CV-18)
- **Fit has a floor.** Fit never zooms out below 10 %, and a project that has just been opened not below 22 %, so names stay readable; a bigger diagram scrolls and can still be zoomed out by hand. Zoomed out, a unit shows its ID in a font sized in screen pixels (about 12 px) instead of in diagram units. The zoom level is shown in the status bar; a click on it returns to 100 %. (CV-4, CV-5)
- **Overlays, never panels.** The legend (folded to one line in a window under 640 px of diagram height unless the person opened it; View > Show legend hides it, saved), the overview map (smaller under 560 px, none under 360 px, draggable, thin see-through lines) and the search bar sit over the canvas and take no layout space. (CV-15, CV-16)
- **The legend lists only what is drawn.** No nominal/redundant lines without a redundant chain, no "auto-filled" entry without an auto-filled connector, no gender key without a known gender, no lock entry without a lock. (CV-15)
- **Grid and snap.** Dots every 10 units from 100 % (every 20 from 50 %), none below 50 %. View > Snap to grid is saved; Alt while dragging places a unit freely. Positions the model holds are never moved to the grid when drawn. (CV-17)
- **Dragging is cheap.** While a unit (or a selection) is dragged only its own links are drawn, as straight lines, at most every 25 ms; the routes and labels are worked out once, on release. (CV-24, SH-15)
- **Link labels are part of the link.** A click on a label (when labels are drawn) selects its own link, whatever lies under it; the hovered or selected link is lifted above the others. (CV-14)
- **Double-click or Enter opens the plans.** `EditorController.openRequested(kind, id)`; the window shows the Harness tab with that harness and wire selected, or a toast "Not generated yet" with a Generate button. (CV-11)
- **Right-click menus mirror the actions.** Built from the window's own `QAction`s; an entry that cannot be used stays in the menu, greyed out, with the reason after its name and as its tooltip. (CV-12)
- **Find (Ctrl+F)** marks every match with a dashed halo (units: ID, name, connector; links: ID, name, type, ends), Enter and Shift+Enter go to the next and previous one and centre the view on it, Escape closes. (CV-13)
- **Refusals say why.** A drag, Delete, nudge or arrange in a read-only project says "This project is read-only ... Use Save as". (CV-20)
- **Interface delete asks first**, naming both ends and the harnesses whose wires become outdated; several items give one question listing them all. (CV-18)
- **Arrange has a shortcut and a button;** more than 60 units are arranged in a worker. (CV-27)
- **Canvas numbers** live in `CanvasMetrics` (`gui/canvas.py`); a later change moves them into the token groups. (CV-29)

### State marks (canvas)

- **One index, built off the paint path.** `gui/canvas_state.py` turns the open findings, the pending values and the release locks into `ObjectState` per unit, link and box connector (`ctl.state_index()`, cached per findings key). The scene takes a new index 120 ms after an edit (at once for a new project and when check results arrive) and repaints only the objects whose entry changed; a paint is a dictionary lookup. (CV-6)
- **Badge = icon + count, never colour alone.** Compact form of a state chip (`gui/canvas_badges.py`): the state's icon, token and border pattern (solid; dotted for pending; dashed for not checked); the word is in the tooltip and the legend. Order: problems (error), warnings, pending, not checked. (CV-6)
- **What a count means.** Errors and warnings are open findings on the unit (also through its connectors and the parts it uses) or on the link (also through its wires); information findings and waived ones are not counted. Pending is the V and A still to enter on power links (a unit adds up its links'). Not checked is 1 on every object while the project has no check result (it never ran or it failed), so a clean card is not mistaken for a passed one; an out-of-date result keeps its marks. (CV-6, CV-8)
- **Click a badge, see the problems.** A badge is a button: a click selects the object and emits `ctl.problemsRequested(object_id)`; the context menu has the same as "Show problems" (greyed with the reason when there is none). `StateIndex.finding_ids(kind, id)` lists the findings counted for the object. `MainWindow` does not connect `problemsRequested` yet, so today a click only selects the object. (CV-6)
- **Locks.** A unit, link or connector that a release locks shows a lock icon and "W001 A" (harness and revision, "+n" for more) in the `locked` colour; the card also gets a 9 % tint of the `released` colour, the legend lists it, and the tooltip says who locks it and what stays editable. On link labels the text shows when the label is drawn in full, otherwise the icon alone; on connectors (Expert) a lock sits in the port square. (CV-7)
- **Auto-filled is marked in Guided too.** A dashed olive "3 auto" chip on the card (the legend's own key) and a dashed ring round the label of a link with an unconfirmed connector. (CV-8)
- **A missing value is "?", not blank.** Only power links need V and A (`describe.VALUES_NEEDED`, a table): "V ? · A ?" in the pending colour and italics; data, analog and other links stay blank because there nothing applies. Where labels are not drawn (dense diagram) the pending badge says it. (CV-8)
- **Link tooltip** is rich text from `describe.link_summary`: harness, wire count, state, what is still to enter, auto connectors, lock, and what the checks say. (CV-10)
- **Card picture and tags.** `describe.unit_glyph` picks one of 11 pictures from the words in the unit's name, its subsystem, its link categories and its connector families (no model field); FLIGHT / GROUND is a viewer setting by zone name (`QSettings` key `canvas/zone_tags`, default none, set from the unit's menu "Tag zone ... as"); NOMINAL shows only where the project has a redundant chain. The header says "12 conn"; connector pictures that do not fit end in "+3", never silently. (CV-19)
- **Corner chip.** Harnesses and outputs "out of date", "not generated yet", "not exported yet", "changed since export" or "up to date" as state chips on a card in the top left, read 400 ms after the last change. (CV-22)
- **Why on the canvas.** The auto chip, a click on it, an auto connector's tooltip (Expert) and the menu entry "Why?" give the sentence "was chosen for you, the first free ... connector" plus what generation recorded (`core.generate.explain`); the canvas emits `ctl.whyRequested(kind, id)`, which `MainWindow` does not connect yet (the tooltip of the auto badge already carries the reasons, and the Why tab of the Inspector and the Harness view show them). (CV-23)

## The window

Code: `gui/main_window.py`, `gui/shell.py` (slots, banners, status chip rules, `auto_scale`), `gui/topbar.py`, `gui/notice.py`. Tests: `test_ux_shell.py`.

- **Layout.** Top bar, a banner area, then the main tabs Diagram · Harness · Lists · Checks · Releases (Ctrl+1 to Ctrl+5); left dock (the Project tree tab, the Palette tab), right dock (the Inspector view with its Inspector, Why and Problems tabs), bottom dock (Problems, To-do, Interface table, Harness plans, Outline: the five old tabs, kept until they are retired), status bar. Views plug into named slots (`MainWindow.install_view(name, widget)`: harness, lists, tree, inspector, why, problems); a slot that is not filled keeps an empty-state page and its tab stays hidden. The Harness, Lists, tree and inspector slots are filled; the Why and Problems tabs live inside the Inspector view, so those two slots stay unfilled. (SH-7, SC-5)
- **One primary button.** Generate is the only accent-coloured button of the window (see [State badges](#state-badges-and-chips)). (SH-1, SH-24)
- **Top bar.** Project name, short model hash in monospace, a dirty marker, Generate, Check, Export… and the status chip. It folds the dirty text, the hash and the words of Check and Export away when narrow. (SH-1)
- **Status chip.** Words, icon and colour from the state chips: Up to date (pass), Plans up to date (nothing exported yet), Plans out of date and Outputs out of date (stale), Generating, Exporting and Checking (info), Not generated (draft). Order of precedence: a running job, then out of date (plans before files), then a running check, then up to date. (SH-2)
- **Banners and refusals stay.** Out-of-date plans or files, and a failed generate, export or check, are banners with the buttons that fix them (Generate, Export…, Try again); the stale banner can be hidden until the design changes again, the chip never hides. A refusal because of a release stays as a toast without a timer, with "Start new revision…", until the next change goes through. (SH-2, SH-5, SH-17, SC-23)
- **Hash and states are read once per model state**, after a pause of 250 ms that grows to at most 2 s for a design that takes long to hash (4 times what the last reading cost). The plans check of the old Harness plans panel is cached the same way; the Harness and Lists views compute theirs in a worker. (SH-16, SC-24)
- **Status bar.** Folder in monospace cut in the middle, "34 rules · v1.0.0", "Generated at model xxxxxxxx" (the generation record's input hash, no clock, so exports stay reproducible), the pending-values link ("4 values pending · 12 rules not checked", it opens Checks filtered), the zoom level. (SH-9, SH-3)
- **Layout is saved.** `saveState` with a version number next to the geometry; View > Reset layout restores the first layout and forgets the saved one. Table column widths are saved by the tables. (SH-10)
- **Short and narrow windows.** Below 800 px (at 100 %) of height the bottom panel is hidden, below 1150 px of width the right dock and below 800 px the left dock; a toast says so, and the panel comes back when the window grows again unless the person hid it. The bottom panel never takes more than 40 % of the window. At 1280 x 720 the diagram has about 70 % of the window height on the flatsat example (a test requires at least 55 %). (SH-26)
- **Panels may be squeezed.** Pages of the main tabs and of the bottom panel have the Ignored size policy, so what a panel holds never makes the window wider than the screen (it did, to 1600 px, once the check results were in). The smallest window the layout allows is about 1150 x 300 px at 100 % scale (measured offscreen). (SH-26)
- **Ctrl+K** lists every enabled action with its shortcut, the unit and interface templates, go to harness, unit or interface; a name that starts with the typed text comes first, then a word that starts with it, then the rest; there is no cap. It is still a modal dialog. (SH-11)
- **Undo and Redo name the step** ("Undo Move PDU2") from `History.next_undo_label` and `next_redo_label`. (SH-14)
- **One dialog for a new project**, after the question about unsaved changes: folder, name and example, with the error under the field it belongs to; the name follows the folder name until it is typed. (SH-18)
- **Focus.** F6 and Shift+F6 move between the diagram, the project panel, the inspector and the bottom panel; the diagram still takes a Tab stop for each unit and link. (SH-13)

## Views

### Project tree, Inspector and Why

Code: `gui/project_tree.py`, `gui/inspector.py`, `gui/why_panel.py`; core `core/usedby.py`, `core/why.py`, `core/vcs/lockview.py`. Tests: `test_ux_tree.py`, `test_ux_tree_window.py`, `test_ux_inspector.py`, `test_ux_why.py`, `test_ux_refused_edit.py`.

- The project tree is a `QTreeView` over a model, not a `QTreeWidget`: the model follows the controller's `Delta`, so a rename touches one row and an added unit inserts one; a rebuild of the whole tree happens only for a `full` delta (a project is opened). (SH-6)
- Seven groups in a fixed order: Units, Interfaces, Harnesses, Parts, Interface types, Configuration, Imports. Units, Interfaces, Harnesses and Configuration start open. Objects are in natural ID order (`J2` before `J10`). (SH-6, SC-20)
- A row is: kind icon, the ID in monospace, the name; on the right, from the edge inwards: the state chip, the lock, then counts as icon and number (errors, warnings, not checked). The counts also sit in the tooltip and in the accessible text, so colour is never the only cue. (SH-6)
- A harness carries the chip of its state: Draft, In review, Released A, Revised B. A configuration file carries a pending chip: "Placeholder" while nobody has reviewed it, or "n pending" when values are still missing; the Configuration group adds up the missing values. (SH-6)
- Counts come from the controller's open findings, attributed with `drc.locate` plus an index of wires and cable connectors per harness (rebuilt only when a harness changes); no rule runs in the tree. With more than 1000 findings the counts follow on the short list timer, so the edit stays inside its budget. (SH-6)
- A lock icon marks every object a released harness holds; the tooltip is the sentence of `lock_reason`. It is recomputed only when the set of released harnesses changes. (CV-7)
- Keyboard: arrows move, Right opens and Left closes a group, typing jumps to a name, `/` goes to the filter, Enter selects (a unit or link also on the canvas), Ctrl+Enter or double-click opens, Enter on an import entry starts that import. Moving with the arrows selects nothing, so browsing 800 links does not redraw the canvas. (SH-6)
- A single click on an import entry only marks it; the dialog opens on Enter or double-click, because a click while browsing should never open a dialog. (SH-6)
- The filter box swaps in a proxy model only while text is typed; without it the view talks to the model directly (a proxy cost about 10 ms per change at 100 units and 800 links). (SH-6)
- Empty groups say what to do ("No interfaces yet. Add one with Ctrl+I or import a table.") in an italic row that is not an object. (SH-6, SC-22)
- The tree opens imports (interfaces with the existing dialog, the other kinds with the import wizard); its Add menu adds a unit (template menu) or an interface; a double-click on a link opens the Harness tab with the wire selected; "Why" on a harness, wire, connector or pin opens the Why tab. (SH-6, SH-7, SH-8)
- The right dock has three tabs: Inspector, Why, Problems. The Inspector tab puts a banner above the existing form: state chip, the sentence of `lock_reason`, and "Start new revision" when a released harness holds the object. Fields a release forbids changed are disabled with the reason as tooltip; names and notes stay editable. (CV-7, SH-8, SC-6)
- "Used in" is a table of the links, harnesses, wires and units that use the selected unit, link, part or interface type (`core/usedby.py`); a row opens on Enter or double-click. (SH-8)
- A configuration file shows its engineering values with a status chip per value: Not set (pending), Unreviewed (pending, the file is still a placeholder), Locked. "Unreviewed" has its own word so a set but unreviewed value is not mistaken for a missing one. (SH-8)
- A refused edit rebuilds the form, so the rejected value is not left showing; the toast with the reason still comes from the controller. (CV-9)
- The Why panel lists "rule: sentence" lines from the generation record (first five, then "Show all n"), then what is pending for the object and the placeholder files the result rests on, each with the shared chips. `why_text` gives the same for tooltips elsewhere; the tooltip of the "Auto" badge carries the first recorded reasons for the connector and the sentence that it is not confirmed yet. (SC-8, CV-23)

### Harness view, Lists and the generate plan

Code: `gui/harness_view.py` (`HarnessView`), `gui/lists_panel.py` (`ListsPanel`), `gui/plan_table.py` (`GeneratePlanTable`), `gui/preview.py` (`SheetView`, `DrawingPreview`), `gui/background.py` (`JobRunner`). Tests: `test_ux_harness.py`, `test_ux_harness_core.py`, `test_ux_lists.py`.

- A released harness shows `Released · rev B`, a draft with an earlier release `Revised · rev B`; the same chip words as the tree and the tables. (SC-5)
- The pin table's State column: `Pending` chip (words "Gauge pending", "Length pending") for a value not known yet, `Not checked` chip with the word "Auto-filled" for what Generate chose and nobody has reviewed, nothing for a spare pin or a value set by hand. (SC-7, SC-9)
- The Locked column is the lock chip with the sentence of `lockview.lock_reason` as its tooltip (it names the harness and revision); a lock set by hand says that Generate keeps it. (SC-7)
- Spare pins are hidden by default and counted under the table ("52 pins shown, 432 spare hidden"), so nothing disappears silently. (SC-9)
- The wire colour has a swatch and its name and code ("red (RD)"). The swatch comes from `core.wirecolours`, so it is a data colour, not a token.
- Hover is a dashed outline in the drawing and a surface tint on table rows; selection is a solid outline and the table selection, so they differ without colour. (SC-10)
- The drawing sheet is painted from `core.outputs.canvas.Sheet` in scene units (mm); `Sheet.marks` maps (kind, id) to item indexes and never reaches SVG or PDF. Zoom is 1x (fit) to 24x, the wheel zooms to the cursor, drag pans. (SC-10)
- Why is shown for a wire, a connector, a pin (box pin reasons plus the wire's) or the harness, from `core.generate.explain`; "Show in Why panel" emits `whyRequested(kind, id)`. (SC-8)
- The independent check, the outputs state and the design state are computed on a copy of the project in a worker and cached by the editor's state token; until they arrive the three chips say "Checking…" (pending). The tooltip of the check chip gives both times. (SC-24)
- Empty states say what to do and show one enabled Generate button only when there are interfaces; there is no row of disabled buttons without a harness. (SC-22)
- Lists export the rows as shown (filtered, sorted) through `csv_bytes` and `xlsx_bytes`; the panel emits `exportTableRequested(name, fmt)` and never opens a file dialog (the window asks for a file name through `ask_save_path`). (SC-11)
- Generate has no per-harness mode, so the Harness view's Regenerate says it covers every harness; the plan table lists every harness the plan names. The plan table is not in the Generate preview dialog yet. (SC-13)

### Checks

Code: `gui/checks_panel.py`, `gui/config_dialog.py`; core `core/drc/by_rule.py`, `core/configcheck.py`. Tests: `test_ux_checks.py`, `test_drc_by_rule.py`, `test_configcheck_values.py`.

- Results are grouped once per finished check from the findings the controller already holds (`ctl.drc_rule_results()`); while a check runs or is out of date the last finished list stays, and before the first one the table is empty with a sentence, never a list of passes. (SC-1)
- The summary strip counts "not checked" as not checked plus pending rules and "pending values" as the hand-over list `configcheck.missing`; each count is a button that filters the table. (SH-3)
- The rules are listed in the order of the rule registry; sorting by the Result column puts the worst first (fail, pending, not checked, pass). Tab leaves a table and the arrows move inside it; Enter on a rule moves to its details, Enter on an object shows it on the diagram. (SC-2)
- A value is supplied in a window of its own (not modal), validated while typing with the same planner that applies it, shown under the field and never in a message box; Apply is one undo step with a label. (SC-3)
- A running check says "checking" with Cancel; a failed check leaves a banner until the next success instead of a toast. (SH-17)

### Releases, Export, Import

Code: `gui/releases_panel.py`, `gui/export_dialog.py`, `gui/export_docs.py`, `gui/import_wizard.py`, `gui/import_kinds.py`, `gui/new_project_dialog.py`, `gui/lock_tree.py`, `ChangeDialog` in `gui/dialogs.py`; core `core/vcs/lockview.py`, `core/vcs/timeline.py`. Tests: `test_ux_rel_*.py`, `test_vcs_lockview.py`, `test_vcs_timeline.py`.

- The release dialog lists what the release locks as a tree under the sentence "This release locks: 18 wires, 198 pins, 9 interfaces, 3 parts, 1 interface type, 5 config files", because a person signing a release should see the objects, not only the counts. A config file that is still a placeholder is shown with the pending chip, and a frozen value that is not set reads "not set (pending)" in italics, never an empty cell. (SC-14)
- The new-revision dialog says what happens (the next revision becomes a draft, the released one stays as a baseline) and lists what becomes editable, counted only for objects that no other released harness also locks; those are listed as "stays locked". (SC-15)
- Releases tab: one timeline for all harnesses with a harness filter; the event (submitted for review, released, new revision) and the baseline are state chips (in review, released, revised), the harness state beside the filter is a chip too; the actions are buttons that emit signals and say why they are disabled in their tooltip. (SC-16)
- Differences are grouped by kind with counts in a list beside the table; added and removed objects say "(did not exist)" and "(removed)" in the empty cell, values use the report's wording ("(none)"). (SC-16)
- Export always writes the full set, because `write_outputs` deletes what is not in the new set and the independent check expects every harness. The tick marks of the harness by document tree choose what the result list shows and what "Copy selection to folder" copies; the manifest stays in the list and is never copied. (SC-12, SH-27)
- The output folder is shown read-only in monospace; an unsaved project, a read-only project and a damaged project are explained in a notice inside the dialog, with a "Save project" action for the first. (SC-12)
- A failed independent check or a write error is an inline notice with the first six problems that stays until the next export succeeds or it is dismissed; nothing is written and no pop-up opens. (SC-12)
- Reveal in folder opens the folder of the file with `QDesktopServices` (Linux file managers have no portable "select this file"); Open opens the file; the drawing picture is drawn from the project data with the sheet renderer of the drawing preview, since the packaged program has no QtSvg. (SC-12)
- The import wizard uses the planner the command line uses for each kind, shows the same per-row reasons, and keeps the command line's rule that a list with a bad row is not imported at all (parts, lengths, ampacity table, netlist); only interfaces skip bad rows, as the existing dialog does. Option names of the command line in a planner message are put in the wizard's own words. (SC-17)
- Every import is one `ctl.run` step called "Import n rows"; what stays pending afterwards (parts whose approval is pending, the derating file that stays a placeholder, interfaces whose connectors are Auto, signals no interface uses) is listed on the third page with the pending chip. (SC-17)

## Shortcuts

Every shortcut is in a menu and in the tooltip as "text (shortcut)". Keys marked "diagram" work only while the diagram has the keyboard focus.

| Key | Action |
|---|---|
| Ctrl+N, Ctrl+O, Ctrl+S, Ctrl+Shift+S, Ctrl+Q | New project, open, save, save as, quit |
| Ctrl+Shift+I | Import interfaces |
| Ctrl+I | New interface |
| Ctrl+G | Generate harnesses |
| F5 | Run the checks |
| Ctrl+E | Export… |
| Ctrl+K | Search and commands |
| F1 | User guide |
| Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z | Undo, redo |
| Ctrl+1 to Ctrl+5 | The main tabs: Diagram, Harness, Lists, Checks, Releases |
| F6, Shift+F6 | Next and previous panel |
| Ctrl+= , Ctrl+- , Ctrl+0 | Zoom in, zoom out, 100 % |
| F, Shift+F (diagram) | Fit all, zoom to the selection |
| Ctrl+A, Ctrl+D, Ctrl+F (diagram) | Select all, duplicate, find |
| Ctrl+Shift+L | Arrange the diagram |
| C, Esc | Connect tool, back to Select |
| Delete (diagram, interface table, outline) | Delete the selection, after showing what it affects |
| Ctrl+wheel, wheel, Shift+wheel, middle button or Space and drag | Zoom at the pointer, scroll, scroll sideways, pan |
| Ctrl+C, Ctrl+Shift+C in a table | Copy the selected cells as tab-separated text, with the header row |
| Ctrl+F in Checks or Lists | Filter the rules or the rows |
| Ctrl+Enter in the engineering values window | Apply the values |
| Enter, Ctrl+Enter in the export result list | Open the file, show it in its folder |
| `/`, Enter, Ctrl+Enter in the project tree | Go to the filter, select, open |

## Decisions

Decisions about the foundation, one line each (decisions of a view are in its section above):

- Theme follows the OS by default, because an engineer's desktop already says light or dark; Light and Dark stay one click away. (SH-19)
- Fixed the type scale to 12 / 13 / 16 / 20 and the spacing to 4 / 8 / 12 / 16 / 24 / 32 as the standard says; the base text is 13 px (it was 14). (SH-22)
- One control height (32 px) set in the theme, so a toolbar button, a push button and a combo box line up at every UI scale. (SH-23)
- Icons are drawn from Lucide path data with a small SVG path reader, not loaded as SVG, because the packaged program leaves out QtSvg. (SH-25)
- Monospace for anything an engineer reads character by character or compares (IDs, pins, hashes, paths). (SH-21)
- `pending`, `not-checked` and `stale` are their own tokens with their own icon and word, never the colours of pass, fail or warning. (SH-28)
- A new table starts in the order the rows are given; a click on a header sorts. (SC-21)
- Selection is a set and every multi-item action is one undo step. (CV-1)
- Overlays (legend, overview map, search) never take layout space. (CV-15, CV-16)
- Export writes the full output set; the choice in the dialog only filters what is listed and copied, until the core can write a subset. (SC-12)
- A badge, chip or cell for an unknown value is never empty and never green: pending and not checked have a pattern. (SH-28, CV-8)
- The command palette (Ctrl+K) is still a modal dialog, and the Palette is still a tab beside the project tree; both are kept for now. (SH-6, SH-11)
- Flight and ground are a viewer setting by zone name, because the model has no such field and the redesign may not change the model. (CV-19)
