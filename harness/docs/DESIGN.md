# Design system of the editor

What the interface is made of: tokens, type and spacing, state badges, interface colours, shortcuts. The code is the source: `gui/tokens.py` (values), `gui/theme.py` (palette, style sheet, fonts), `gui/icons.py`, `gui/states.py`, `gui/tables.py`. A test (`tests/test_tokens.py`) checks contrast and colour-blind separation of the tokens; `tests/test_ux_foundation.py` checks the rest. One line per decision is kept at the end, newest last.

## Theme

- Three modes: **System** (default, follows the operating system's light/dark scheme while the program runs), **Light**, **Dark**. The choice is stored as `ui/theme` (`system`, `light` or `dark`). View > Theme.
- `ThemeManager.apply()` builds a `QPalette` and the style sheet from the tokens. No widget calls `setStyleSheet` and no code holds a `#RRGGBB` literal (the logo in `appicon.py` is the one brand exception); both are checked by a test. Widgets pick up rules by property: `primary`, `danger`, `muted`, `heading`, `align="left"`, `mono`, `iconOnly`.
- `theme.color(token)`, `theme.type(name)`, `theme.space(n)`, `theme.font(...)`, `theme.mono_font()`, `theme.control_height()`, `theme.icon_size()`; `current_theme()` for widgets built without a reference to the window's manager.

## Colour tokens

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
| `cat-*` | Interface categories on the canvas (below) |

Text tokens meet 4.5:1 on `bg`, `surface` and `surface-2` in both themes; borders, focus and category colours 3:1.

## Type and spacing

- Type scale in px: `sm` 12 (captions, canvas labels, table cells, status bar), `base` 13 (body), `md` 16, `lg` 20. IBM Plex Sans for the interface, IBM Plex Mono for pin, wire and part numbers, IDs, requirement IDs, hashes and paths (`mono` property, `theme.mono_font()`, `mono_item_font()` in models).
- Spacing in px: 4, 8, 12, 16, 24, 32. Every control (button, combo box, line edit, spin box) is 32 px high at 100 % scale.
- Both are multiplied by the UI scale (100, 125, 150, 200 %).

## Icons

Lucide geometry (ISC licence, D-146) painted with `QPainter` from path strings; no SVG file at run time. `icons.icon(name, theme, role)` returns a `QIcon` that repaints in the theme's colours at any size, so a theme change needs no rebuild. Stroke width is 2/24 of the size, at least 1.5 px. Every icon button has an accessible name and a tooltip that names the shortcut: `icons.icon_button(button, name, theme, label, shortcut)`.

## State badges

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

An empty cell shows nothing at all, so pending and not-checked can never be taken for empty, pass or fail. Selected rows draw the chip in `on-primary`.

## Interface colours (canvas)

Each category has its own colour, line weight and letter, so colour is not the only cue: Power (3.5 px, `P`), Data (2, `D`), Analog (1.5, `A`), RF (2.5, `R`), Pyro (4, `!`), Discrete (1.5, `d`), Ground (1, `G`); redundancy is a dashed line. Thermal links share Analog, other links share Ground. Values in `gui/tokens.py`.

## Tables

`DictTableModel` (rows as dicts or tuples, `Column` specs) + `TableProxy` (sort by number or natural text, filter by words, state or predicate) + `TableView` (header stays in view, cell selection, state chips, saved widths). Numbers are right-aligned with tabular figures, units are in the header ("Length (m)"), pin / wire / part numbers are monospace.

## Shortcuts

| Key | Action |
|---|---|
| Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z | Undo, redo |
| Ctrl+= , Ctrl+- , Ctrl+0 | Zoom in, zoom out, fit the diagram |
| Ctrl+K | Search and commands |
| Ctrl+Shift+I | Import interfaces |
| Ctrl+C in a table | Copy the selected cells as tab-separated text |
| Ctrl+Shift+C in a table | The same with the header row |

## Decisions

- Theme follows the OS by default, because an engineer's desktop already says light or dark; Light and Dark stay one click away. (SH-19)
- Fixed the type scale to 12 / 13 / 16 / 20 and the spacing to 4 / 8 / 12 / 16 / 24 / 32 as the standard says; the base text is 13 px (it was 14). (SH-22)
- One control height (32 px) set in the theme, with `min-height` and `max-height`, so a toolbar button, a push button and a combo box line up at every UI scale. (SH-23)
- Icons are drawn from Lucide path data with a small SVG path reader, not loaded as SVG, because the packaged program leaves out QtSvg. (SH-25)
- Monospace for anything an engineer reads character by character or compares (IDs, pins, hashes, paths). (SH-21)
- `pending` is teal and dotted, `not-checked` is slate and hatched, `stale` is orange; none of them is the green, red or amber of pass, fail and warning, and each has its own icon and word. (SH-28)
- Chip fill is a 4 % tint so text on it keeps AA contrast on all three surfaces; a test computes it. (SH-28)
- A new table starts in the order the rows are given; a click on a header sorts. (SC-21)
# Design decisions: tokens, state badges, interface colours, shortcuts

One line per decision. Sections are added by the work that makes the decision.

## Diagram canvas: navigation, selection, editing (branch `ux/canvas`)

- **Selection is a set.** `EditorController.selected` holds every selected item in the order picked; `selection` stays the primary (last picked) one, so the panels and tests that read one item keep working. Click selects one, Shift-click and Ctrl-click add or remove, a drag on the background draws a rubber band (units it touches, links it holds entirely), Ctrl+A selects all.
- **One undo step per action.** Deleting, moving, aligning, spacing, duplicating and editing several items each run as one `History` transaction (`core/edit.py`: `ops_delete_many`, `ops_move_units`, `ops_align`, `ops_distribute`, `ops_duplicate_unit`).
- **Align is by the heights drawn now.** The window passes the item heights (Guided and Expert differ). Aligning side to side across lanes changes the unit's zone, as moving it does.
- **Duplicate copies connectors, never links or pin assignments** (those belong to the original); the copy gets a new ID from the original's prefix and sits in the same lane.
- **The wheel never zooms by itself.** Ctrl+wheel zooms at the pointer (1.2 per notch), the wheel scrolls up and down, Shift+wheel sideways, a trackpad scrolls by pixels. Middle button or Space with a left drag pans and never moves a unit.
- **Shortcuts.** `F` fit all, `Shift+F` zoom to selection, `Ctrl+0` 100 %, `Ctrl+=` / `Ctrl+-` zoom, `Ctrl+A` select all, `Ctrl+D` duplicate, `Ctrl+F` find, `Ctrl+Shift+L` arrange, `Delete` delete. The bare-key ones and `Delete` work only while the diagram (and for Delete the interface table or the outline) has the keyboard focus, so they cannot act from another panel.
- **Fit has a floor.** Fit never zooms out below 10 %, and a project that has just been opened not below 22 %, so names stay readable; a bigger diagram scrolls and can still be zoomed out by hand. Zoomed out, a unit shows its ID in a font sized in screen pixels (about 12 px) instead of in diagram units.
- **Overlays, never panels.** The legend (folded to one line in a window under 640 px of diagram height unless the person opened it; View > Show legend hides it, saved), the overview map (smaller under 560 px, none under 360 px, draggable, thin see-through lines) and the search bar sit over the canvas and take no layout space.
- **Legend lists only what is drawn.** No nominal/redundant lines without a redundant chain, no "auto-filled" entry without an auto-filled connector, no gender key without a known gender.
- **Grid and snap.** Dots every 10 units from 100 % (every 20 from 50 %), none below 50 %. View > Snap to grid is saved; Alt while dragging places a unit freely. Positions the model holds are never moved to the grid when drawn.
- **Dragging is cheap.** While a unit (or a selection) is dragged only its own links are drawn, as straight lines, at most every 25 ms; the routes and labels are worked out once, on release.
- **Link labels are part of the link.** A click on a label (when labels are drawn) selects its own link, whatever lies under it; the hovered or selected link is lifted above the others.
- **Double-click or Enter opens the plans.** `EditorController.openRequested(kind, id)`; the window shows the Harness plans tab with that harness and wire selected, or a toast "Not generated yet" with a Generate button.
- **Right-click menus mirror the actions.** Built from the window's own `QAction`s; an entry that cannot be used stays in the menu, greyed out, with the reason after its name and as its tooltip.
- **Find (Ctrl+F)** marks every match with a dashed halo (units: ID, name, connector; links: ID, name, type, ends), Enter and Shift+Enter go to the next and previous one and centre the view on it, Escape closes.
- **Refusals say why.** A drag, Delete, nudge or arrange in a read-only project says "This project is read-only ... Use Save as".
- **Interface delete asks first**, naming both ends and the harnesses whose wires become outdated; several items give one question listing them all.
- **Canvas numbers** live in `CanvasMetrics` (`gui/canvas.py`); a later change moves them into the token groups.

## Release, export, import and new project (ux/rel)

- The release dialog lists what the release locks as a tree under the sentence "This release locks: 18 wires, 198 pins, 9 interfaces, 3 parts, 1 interface type, 5 config files", because a person signing a release should see the objects, not only the counts. A config file that is still a placeholder is shown with the pending chip, and a frozen value that is not set reads "not set (pending)" in italics, never an empty cell. (SC-14)
- The new-revision dialog says what happens (the next revision becomes a draft, the released one stays as a baseline) and lists what becomes editable, counted only for objects that no other released harness also locks; those are listed as "stays locked". (SC-15)
- A disabled OK button always has a line under the form that says what is missing ("write at least 10 characters in the comment (3 more to go)"), and the same text is the button's tooltip. (SC-15)
- Releases tab: one timeline for all harnesses with a harness filter; the event (submitted for review, released, new revision) and the baseline are state chips (in review, released, revised), the harness state beside the filter is a chip too; the actions are buttons that emit signals and say why they are disabled in their tooltip. (SC-16)
- Differences are grouped by kind with counts in a list beside the table; added and removed objects say "(did not exist)" and "(removed)" in the empty cell, values use the report's wording ("(none)"). (SC-16)
- Export always writes the full set, because `write_outputs` deletes what is not in the new set and the independent check expects every harness. The tick marks of the harness by document tree choose what the result list shows and what "Copy selection to folder" copies; the manifest stays in the list and is never copied. (SC-12, SH-27)
- The output folder is shown read-only in monospace; an unsaved project, a read-only project and a damaged project are explained in a notice inside the dialog, with a "Save project" action for the first. (SC-12)
- A failed independent check or a write error is an inline notice with the first six problems that stays until the next export succeeds or it is dismissed; nothing is written and no pop-up opens. (SC-12)
- Reveal in folder opens the folder of the file with `QDesktopServices` (Linux file managers have no portable "select this file"); Open opens the file; the drawing picture is drawn from the project data with the sheet renderer of the drawing preview, since the packaged program has no QtSvg. (SC-12)
- Inline notices (`gui/notice.py`) carry an icon and a word for error, warning and note next to the colour, with the left bar the style sheet already used for banners. (SC-12)
- The import wizard uses the planner the command line uses for each kind, shows the same per-row reasons, and keeps the command line's rule that a list with a bad row is not imported at all (parts, lengths, ampacity table, netlist); only interfaces skip bad rows, as the existing dialog does. Option names of the command line in a planner message are put in the wizard's own words. (SC-17)
- Every import is one `ctl.run` step called "Import n rows"; what stays pending afterwards (parts whose approval is pending, the derating file that stays a placeholder, interfaces whose connectors are Auto, signals no interface uses) is listed on the third page with the pending chip. (SC-17)
- New project is one dialog (folder, name, example) with the error under the field it belongs to; the name follows the folder name until it is typed. (SH-18)

### Checks view (ux/checks: SC-1, SC-2, SC-3, SH-3, SH-17, SH-28)

- A result is one of pass, fail, not checked or pending, each a state chip (icon, word and pattern); a pass that read a placeholder file says "Pass (placeholder values)" so a pass never looks reviewed when it is not. (SC-1, SH-28)
- Results are grouped once per finished check from the findings the controller already holds (`ctl.drc_rule_results()`); while a check runs or is out of date the last finished list stays, and before the first one the table is empty with a sentence, never a list of passes. (SC-1)
- The summary strip counts "not checked" as not checked plus pending rules and "pending values" as the hand-over list `configcheck.missing`; each count is a button that filters the table. (SH-3)
- Rows sort worst first (fail, pending, not checked, pass); Tab leaves a table and the arrows move inside it; Enter on a rule moves to its details, Enter on an object shows it on the diagram. (SC-2)
- A value is supplied in a window of its own (not modal), validated while typing with the same planner that applies it, shown under the field and never in a message box; Apply is one undo step with a label. (SC-3)
- A running check says "checking" with Cancel; a failed check leaves a banner until the next success instead of a toast. (SH-17)
- Shortcuts: Ctrl+F filters the rules, Ctrl+Enter applies the engineering values, Enter shows the selected object.

## Harness view, lists and generate plan (SC-5, SC-7 to SC-11, SC-13, SC-22, SC-24)

Code: `gui/harness_view.py` (`HarnessView`), `gui/lists_panel.py` (`ListsPanel`), `gui/plan_table.py` (`GeneratePlanTable`), `gui/preview.py` (`SheetView`, `DrawingPreview`), `gui/background.py` (`JobRunner`).

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
- A disabled action's tooltip is the reason ("Only a released harness can be revised."), an enabled one's is what it does.
- Lists: a cell that is `pending`, `TBD (placeholder)`, an unknown part category, a part missing from the parts list, or a length that could not be worked out is a chip, so it cannot be taken for an empty cell or a pass. (SC-11)
- Lists export the rows as shown (filtered, sorted) through `csv_bytes` and `xlsx_bytes`; the panel emits `exportTableRequested(name, fmt)` and never opens a file dialog. (SC-11)
- Generate has no per-harness mode, so the harness view's Regenerate says it covers every harness; the plan table lists every harness the plan names. (SC-13)
- A filter that is on or off is a toggle button (fill, icon and word change when pressed), not a check box: the tick box of a `QCheckBox` has no border in the dark theme and cannot be seen. (SC-9, SC-11)
- A list's columns are measured from the model (header, longest cell, widest chip) and re-measured when the harness changes, so a "pending" chip is never cut off; the harness view's columns have fixed widths so that showing a harness does not measure hundreds of chips. (SC-7, SC-11, SC-24)

## Project tree, inspector and Why (ux/tree)

- The project tree is a `QTreeView` over a model (`gui/project_tree.py`), not a `QTreeWidget`: the model follows the controller's `Delta`, so a rename touches one row and an added unit inserts one; a rebuild of the whole tree happens only for a `full` delta (a project is opened). (SH-6)
- Seven groups in a fixed order: Units, Interfaces, Harnesses, Parts, Interface types, Configuration, Imports. Units, Interfaces, Harnesses and Configuration start open. Objects are in natural ID order (`J2` before `J10`). (SH-6, SC-20)
- A row is: kind icon, the ID in monospace, the name; on the right, from the edge inwards: the state chip, the lock, then counts as icon and number (errors, warnings, not checked). The counts also sit in the tooltip and in the accessible text, so colour is never the only cue. (SH-6)
- A harness carries the chip of its state: Draft, In review, Released A, Revised B (a draft that is a later revision of a released harness). A configuration file carries a pending chip: "Placeholder" while nobody has reviewed it, or "n pending" when values are still missing; the Configuration group adds up the missing values. (SH-6)
- Counts come from the controller's open findings, attributed with `drc.locate` plus an index of wires and cable connectors per harness (rebuilt only when a harness changes); no rule runs in the tree. With more than 1000 findings the counts follow on the short list timer, so the edit stays inside its budget. (SH-6)
- A lock icon marks every object a released harness holds; the tooltip is the sentence of `lock_reason`. It is recomputed only when the set of released harnesses changes. (CV-7)
- Keyboard: arrows move, Right opens and Left closes a group, typing jumps to a name, `/` goes to the filter, Enter selects (a unit or link also on the canvas), Ctrl+Enter or double-click opens, Enter on an import entry starts that import. Moving with the arrows selects nothing, so browsing 800 links does not redraw the canvas. (SH-6)
- A single click on an import entry only marks it; the dialog opens on Enter or double-click, because a click while browsing should never open a dialog. (SH-6)
- The filter box swaps in a proxy model only while text is typed; without it the view talks to the model directly (a proxy cost about 10 ms per change at 100 units and 800 links). (SH-6)
- Empty groups say what to do ("No interfaces yet. Add one with Ctrl+I or import a table.") in an italic row that is not an object. (SH-6)
- The right dock content has three tabs: Inspector, Why, Problems. The Inspector tab puts a banner above the existing form: state chip, the sentence of `lock_reason`, and "Start new revision" when a released harness holds the object. Fields a release forbids changed are disabled with the reason as tooltip; names and notes stay editable. (CV-7, SH-8)
- "Used in" is a table of the links, harnesses, wires and units that use the selected unit, link, part or interface type (`core/usedby.py`); a row opens on Enter or double-click. (SH-8)
- A configuration file shows its engineering values with a status chip per value: Not set (pending), Unreviewed (pending, the file is still a placeholder), Locked. "Unreviewed" has its own word so a set but unreviewed value is not mistaken for a missing one. (SH-8)
- A refused edit rebuilds the form, so the rejected value is not left showing; the toast with the reason still comes from the controller. (CV-9)
- The Why panel lists "rule: sentence" lines from the generation record (first five, then "Show all n"), then what is pending for the object and the placeholder files the result rests on, each with the shared chips. `why_text` gives the same for tooltips elsewhere. (SC-8, CV-23)
- The tooltip of the "Auto" badge carries the first recorded reasons for the connector and the sentence that it is not confirmed yet (`why.why_text`). (CV-23)
- Icons added for the tree (Lucide: cpu, plug, package, shapes, sliders-horizontal, plus); the paths were typed from the Lucide set and should be diffed against lucide-static 1.56.0 when a copy is at hand.
