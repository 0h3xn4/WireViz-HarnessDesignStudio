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
