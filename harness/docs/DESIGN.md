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

## Canvas state marks (ux/cstate: CV-6, CV-7, CV-8, CV-10, CV-19, CV-21, CV-22, CV-23)

- **One index, built off the paint path.** `gui/canvas_state.py` turns the open findings, the pending values and the release locks into `ObjectState` per unit, link and box connector (`ctl.state_index()`, cached per findings key). The scene takes a new index 120 ms after an edit (at once for a new project and when check results arrive) and repaints only the objects whose entry changed; a paint is a dictionary lookup. (CV-6)
- **Badge = icon + count, never colour alone.** Compact form of a state chip (`gui/canvas_badges.py`): the state's icon, token and border pattern (solid; dotted for pending; dashed for not checked); the word is in the tooltip and the legend. Order: problems (error), warnings, pending, not checked. (CV-6)
- **What a count means.** Errors and warnings are open findings on the unit (also through its connectors and the parts it uses) or on the link (also through its wires); information findings and waived ones are not counted. Pending is the V and A still to enter on power links (a unit adds up its links'). Not checked is 1 on every object while the project has no check result (it never ran or it failed), so a clean card is not mistaken for a passed one; an out-of-date result keeps its marks. (CV-6, CV-8)
- **Click a badge, see the problems.** A badge is a button: a click selects the object and emits `ctl.problemsRequested(object_id)`; the context menu has the same as "Show problems" (greyed with the reason when there is none). The window decides how Problems is filtered (`StateIndex.finding_ids(kind, id)` lists the findings counted for the object). (CV-6)
- **Locks.** A unit, link or connector that a release locks shows a lock icon and "W001 A" (harness and revision, "+n" for more) in the `locked` colour; the card also gets a 9 % tint of the `released` colour, the legend lists it, and the tooltip says who locks it and what stays editable. On link labels the text shows when the label is drawn in full, otherwise the icon alone; on connectors (Expert) a lock sits in the port square. (CV-7)
- **Auto-filled is marked in Guided too.** A dashed olive "3 auto" chip on the card (the legend's own key) and a dashed ring round the label of a link with an unconfirmed connector. (CV-8)
- **A missing value is "?", not blank.** Only power links need V and A (`describe.VALUES_NEEDED`, a table): "V ? · A ?" in the pending colour and italics; data, analog and other links stay blank because there nothing applies. Where labels are not drawn (dense diagram) the pending badge says it. (CV-8)
- **Link tooltip** is rich text from `describe.link_summary`: harness, wire count, state, what is still to enter, auto connectors, lock, and what the checks say. (CV-10)
- **Card picture and tags.** `describe.unit_glyph` picks one of 11 pictures from the words in the unit's name, its subsystem, its link categories and its connector families (no model field); FLIGHT / GROUND is a viewer setting by zone name (`QSettings` key `canvas/zone_tags`, default none, set from the unit's menu "Tag zone ... as"); NOMINAL shows only where the project has a redundant chain. The header says "12 conn"; connector pictures that do not fit end in "+3", never silently. (CV-19)
- **Far away a link still says what it is.** Below 50 % each category has its own dash pattern (analog, RF, pyro, discrete, ground; power and data stay solid) and a small plate with the kind's picture is drawn at a fixed screen size (up to 400 links); the selected or hovered link is drawn in full with a label never under 18 px. (CV-21)
- **Corner chip.** Harnesses and outputs "out of date", "not generated yet", "not exported yet", "changed since export" or "up to date" as state chips on a card in the top left, read 400 ms after the last change. (CV-22)
- **Why on the canvas.** The auto chip, a click on it, an auto connector's tooltip (Expert) and the menu entry "Why?" give the sentence "was chosen for you, the first free ... connector" plus what generation recorded (`core.generate.explain`); the window gets `ctl.whyRequested(kind, id)`. (CV-23)
