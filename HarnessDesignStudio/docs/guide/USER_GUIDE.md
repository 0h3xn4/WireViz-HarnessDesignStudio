# Harness Design Studio: user guide

This guide is for systems engineers who have never used the tool. It works offline. Press **F1** in the app to open it.

New here? Read sections 1 to 4 (about fifteen minutes). Section 3 gives you a ready-made practice project to play with.

## 1. What the tool does

You draw units (computer, power unit, wheels ...) and the interfaces between them. The tool turns that into harnesses: which wires, on which pins, in which connectors. It checks the result, writes the drawings and lists, and keeps a record of every release.

Your design is the source of truth. Everything else (harnesses, drawings, lists) is generated from it and can be generated again at any time.

Seven words carry most of the meaning:

| Word | What it is |
| --- | --- |
| **Unit** | A box with connectors on it: the computer `OBC1`, the power unit `PCDU1`, the wheel `RW1`. |
| **Interface** | One connection between two units, of a type such as RS-422 or primary power. This is what you add. |
| **Connector, pin** | A plug or socket, and one contact of it. A pin carries one signal. |
| **Harness** | A bundle of wires with connectors that carries interfaces between units. Generated, never drawn by hand. |
| **Wire** | One conductor between two pins, with a gauge, a part and a length. |
| **Zone** | A lane of the diagram (a panel or compartment) that units sit in. |
| **Placeholder** | A value nobody has entered yet. The tool never invents engineering numbers. |

The starter library follows one baseline:

| For | Baseline |
| --- | --- |
| Communication | RS-422, RS-485 and CAN |
| High data rates (for example a payload) | Ethernet, on an RJ45 connector, as the alternative |
| Power and data connectors | Micro-D 9, 15, 21, 25 and 31 pin (power: 9 pin; for data the size follows the number of interface types the connector carries) |
| RF | SMA |

Other interface types and older connector parts stay in the library for projects that need them. All parts are examples with fictional part numbers, none approved; your approved parts list replaces them.

## 2. Install and start (Ubuntu 24.04 or newer)

1. Install the package: `sudo apt install ./harness-design-studio_<version>_amd64.deb`. Or unpack the `.tar.gz` anywhere and run `./harness-design-studio/install.sh` (no administrator rights needed; it installs for your user).
2. Check it: `harness-design-studio --version` prints the version. If the command is not found after `install.sh`, add `~/.local/bin` to your PATH (the installer prints how).
3. Start **Harness Design Studio** from the application menu, or run `harness-design-studio`.
4. The command line tool is `harness-design-studio`; `harness` works as a short alias (see section 10, Command line).

No network access is needed or used. On a minimal Ubuntu the app may need a few system libraries; the installer lists them.

## 3. Start from an example

The tool ships five practice projects (examples). List them and create one in a new folder:

```
harness-design-studio new --list
harness-design-studio new wheel-link --template first-steps
```

Then **File > Open project…** and pick the folder. You cannot break anything: it is your own copy.

Version 1.0.0 has five examples. If `harness-design-studio new --list` shows only `blank`, `first-steps` and `small-satellite`, you have the 0.1.0 packages, which have those three; `minimal-satellite`, `flatsat` and the wire colours of section 7 are new in 1.0.0.

| Example | What it is |
| --- | --- |
| `blank` | An empty project with the starter parts and interface types. Use it for a real design. |
| `first-steps` | Three units, a power link and an RS-422 link. Nothing is generated yet: start here. |
| `minimal-satellite` | Seven units, nominal only: power, computer, radio, wheel and sun sensor. Adapt it. |
| `small-satellite` | 14 units with nominal and redundant chains. Generate it to see a realistic system. |
| `flatsat` | A complete bench: 23 flight and ground units, generated, with example numbers. |

`harness-design-studio templates my-templates` copies templates for your own data: CSV files for interfaces, parts and lengths, a KiCad netlist, a CI script and a review checklist. The demo engineering values in it are for learning only.

## 4. The window and your first project

The window has these parts. Everything is also reachable with the keyboard (section 14).

| Part | What it holds |
| --- | --- |
| **Top bar** | The project name, a short model hash, *Saved* or *Unsaved changes*, **Generate** (the one blue button), **Check**, **Export…** and a status chip. |
| **Banner** | Appears under the top bar when something needs you: the plans or the exported files are out of date (buttons **Generate** and **Export…**), or a generate, export or check failed (**Try again**). A change that is refused because a harness is released stays on screen as a message over the diagram, with **Start new revision…**, until the next change goes through. |
| **Tabs** | **Diagram**, **Harness**, **Lists**, **Checks**, **Releases** (Ctrl+1 to Ctrl+5). |
| **Left panel** | The **Project** tab: a tree of units, interfaces, harnesses, parts, interface types, configuration files and imports, with a filter and an **Add** button. The **Interfaces** tab (Ctrl+Shift+T): every interface as a table you can sort, filter and edit with the keyboard. |
| **Right panel** | **Inspector** (the fields of what you selected, and where it is used), **Why** (the reasons for a choice) and **Problems** (the problem cards, with a **To do** list above them). |
| **Status bar** | The project folder, the number of rules and the tool version, *Generated at model …*, a link *n values pending · n rules not checked*, and the zoom level. |

The status chip in the top bar says one thing: *Up to date*, *Plans out of date* (the diagram changed after Generate), *Outputs out of date* (the design changed after the last export), *Not generated*, or the running job (*Generating…*, *Exporting…*, *Checking…*). Colour is never the only sign: every state has an icon and a word, and the two states for "nothing known yet" have a pattern. **Pending** (dotted) is a value nobody has entered; **Not checked** (hatched) is a rule that could not run. Neither is a pass, and neither is empty.

Panels you hide or move are remembered; **View > Reset layout** puts them back. In a small or narrow window the tool hides panels so the diagram stays large, and says so.

### Your first project in ten steps

1. Start the app. The sample project opens with a short tour; skip it or follow it. The tour leaves out a step whose panel is hidden (a small window or a high interface size), records that it was shown however you close it, and can be started again with **Help > Replay the tour**.
2. **File > New project…** opens one window: choose an empty folder, give the project a name, and optionally pick an example (section 3; `first-steps` has three units, start there). A problem with the folder or the name is written under the field. **File > New project from an example…** is the same window with the first example ticked.
3. Add units: press **Add** in the Project tab and choose **Unit…**, or use **Edit > Add unit**. Pick *Computer*, then add a *Power unit* and an *Actuator (wheel)*.
4. Connect them. Press **C** (or the **Connect** button above the diagram; the arrow beside it lists the interface types, as does **Edit > Connect with**), pick an interface type such as *RS-422*, then click the first unit and the second. Units that cannot take this interface are greyed out, with the reason written next to them. **Ctrl+I** (or **Add > Interface…**) opens a form for the same thing.
5. Look at **Problems** (right panel). Each card says what is wrong, why it matters and how to fix it. Many have a one-click **Fix**. The **Checks** tab lists all 34 design rules with their result (section 6).
6. The top of the **Problems** tab has a **To do** list of what is left to do; a click on a line shows the unit or interface.
7. Press **Generate** in the top bar (**Generate harnesses**, Ctrl+G). A preview shows what will be added; nothing changes until you press **Apply**. **Undo** takes it all back. The **Harness** tab opens.
8. In the **Harness** tab pick a harness: its connectors and pins, its wires, a drawing (zoom with the wheel, change sheet with **Previous sheet** and **Next sheet**) and *Why* for the selected wire, connector or pin. The **Lists** tab shows the wire list, pinouts, BOM and test tables.
9. Save with **Ctrl+S**.
10. Press **Export…** in the top bar (Ctrl+E): choose what to look at and press **Export** to write drawings and lists into the project's `outputs` folder (section 8).

On a power interface set **Max current (A)** in the Inspector; without it the wire gauge stays pending.

## 5. Guided and Expert mode

- **Guided** (default): you work with units and interfaces. The tool chooses connectors and pins and marks its choices as *auto-filled* until you confirm them.
- **Expert**: you also see each connector of a unit and can choose the exact connector for every end of an interface.

Switching modes never changes your data.

### Reading a dense diagram

A system with many units has many links. The editor makes them readable in these ways:

- **Pictures tell the kinds apart.** A link carries the picture of its kind: a bolt for power, a ground symbol, a bus with end stops for CAN, two arrows for a differential pair (RS-422, LVDS), a bus with drops for RS-485, a node with branches for SpaceWire, two boxes for Ethernet, a sine wave for an analog signal, a square wave for a discrete signal, a spark for a pyro line, a ring for RF coax. A link with twisted-pair signals is drawn as two lines, a redundant link is dashed. The legend (button at the bottom left of the diagram; **View > Show legend**) shows the pictures the project uses.
- **Connectors are drawn as they look**: a flange with screw holes and the shell in front of it: a tapered D for a D-sub, a rounded block for a Micro-D, a round shell, an RJ45 plug, a coax ring. The size and the dots follow the pin count, which is also written as a number. **Gender is black or white**: a male connector (pins) is drawn solid, a female connector (sockets) as an outline, and a connector whose gender is not set with a dashed outline; the legend says so. The harness drawings and the mating matrix state the gender of every cable connector in words. In Expert mode a dashed line splits the unit into a left side and a darker right side (ports sit on the edge of their side), and every port reads from its edge inwards: the designator (J01), the connector picture and the pin count. In Guided mode a unit shows its connectors as small pictures. What a link carries is drawn on the link.
- **Numbers appear when they exist.** A power link shows e.g. `28 V · 5 A` beside its picture, but only what somebody entered; nothing is filled in. In a diagram of more than 30 links the numbers show for the selected, focused or hovered link; *View > Show all link labels* shows them everywhere. Hover a link to read its name, type, values and ends in words.
- **Click a unit or a link.** Only its links stay in full colour; everything else fades. Click the empty background or press Escape to see everything again. This is the quickest way to answer "what is connected to this?".
- **Show** (the list in the toolbar, *All interfaces* by default) fades everything except one signal class, one connector or one bundle. It can be combined with a selection.
- **Links run in lines.** Each link leaves on the edge that faces the unit at its other end, goes sideways into the gutter between lanes, runs up or down in its own track, and enters the other unit sideways. Links between the same two lanes run side by side, ordered so that they cross as little as possible.
- **Arrange diagram** (View menu, Ctrl+Shift+L, or the toolbar button) puts the units in order and keeps room for each one: a unit with many connectors is tall in Expert mode, and the units around it make way. One undo step restores the old positions.

Zoomed far out, a unit shows its ID and each kind of link its own dash pattern and a small picture; zoom in to see pictures and numbers.

### Marks on the diagram

- **Problems, warnings, values to enter, not checked.** A unit or link that has open findings shows a small badge with an icon and a count: problems, warnings, values still to enter (*V ? · A ?* on a power link), and *not checked*. Click a badge to select the object; its problems are in the Problems list. Hover a badge to read what it counts. Before the first check has finished every object shows *not checked*, so a clean card is never mistaken for a passed one.
- **Locks.** An object that a released harness holds shows a lock and the harness and revision (*W001 A*), and a faint tint. The tooltip says who locks it and what stays editable.
- **Auto-filled.** A card with connectors the tool chose shows a dashed *n auto* chip, in Guided mode too; hover it to read why they were chosen and that nobody has confirmed them yet.
- **State of the harnesses.** A chip in the top left of the diagram says *Harnesses out of date*, *not generated yet*, *Outputs out of date*, *not exported yet* or *up to date*.
- **Card pictures and tags.** A card shows a picture of its kind of unit and the number of connectors (*12 conn*). FLIGHT or GROUND tags are a viewer setting: right-click a unit and choose **Tag zone … as**; they are not saved in the project.

### Moving around and selecting

- **Click** selects one item. **Shift+click** or **Ctrl+click** adds or removes, a **drag on the background** draws a rectangle, **Ctrl+A** selects all. With several units selected the Inspector shows what they have in common; **Delete**, **Duplicate** (Ctrl+D), **Align** and **Space evenly** (Edit menu) act on all of them as one undo step.
- **Ctrl+wheel** zooms at the pointer, the wheel scrolls, **Shift+wheel** scrolls sideways, the **middle button** or **Space** with a drag pans. **F** fits everything, **Shift+F** zooms to the selection, **Ctrl+0** shows 100 %. The zoom level is at the right of the status bar.
- **Ctrl+F** finds a unit or link by ID, name, connector or type and marks every match; Enter goes to the next. **Double-click** a link or unit (or press Enter on it) opens it in the **Harness** tab.
- **Right-click** shows a menu with the same actions as the menus; an entry that cannot be used stays in the menu, greyed out, with the reason.
- **View > Show legend**, **Show overview map** and **Snap to grid** switch overlays and the grid; hold **Alt** while dragging to place a unit freely.

## 6. Problems, checks and waivers

- **Error**: must be fixed. Errors cannot be waived.
- **Warning**: fix it, or **Waive** it with a reason of at least 10 characters. Waived warnings stay visible in the report with their reason.
- **Note**: information, for example *not checked because a value is still a placeholder*.

The quick checks run on every edit. The design rules (34 of them) run in the background a moment after you stop editing, or when you press **Check** (F5); the top bar says *Checking…* while they run and you can cancel. The **Problems** cards say when they are checking, and a header such as *34 rules: 20 passed, 2 failed, 12 not checked* says how it went.

The **Checks** tab (Ctrl+4) has one row for each rule:

- A strip on top counts the rules *passed*, *failed*, *not checked* and the *pending values*; each count is a button that filters the table. The status-bar link *n values pending · n rules not checked* opens the same tab.
- **Result** is a chip with an icon and a word: *Pass*, *Fail*, *Not checked* (the rule could not run) or *Pending*. *Pass (placeholder values)* means the rule passed on values nobody has reviewed. Click the **Result** header to put the worst first.
- **Fix all (n)** (top right of the tab) applies the one-click fix of every open problem that has one, as one undo step; n is how many there are, and its tooltip says which kinds of fix (for example *Choose connectors automatically (2)*). It never confirms a connector the tool chose: confirming says that a person looked at it, so those stay open for you (the *Confirm connectors* button on the problem itself does it). It is greyed out, with the reason in its tooltip, when n is 0 or the project is read-only. A fix that a released harness locks is left out and named in the message; the rest are done. Connectors the tool chooses this way are marked *auto* until you confirm them.
- Select a rule to see what it found, what it needs, and the requirement IDs it serves. Press Enter on an offending object, or double-click it, to show it on the diagram. Ctrl+F filters the rules.
- A rule that is *not checked* names the value it waits for and has **Supply value…**. It opens **Engineering values**: every value the rules need, grouped by config file, with its unit, a *placeholder* toggle and the reason when a value is refused. **Apply** (Ctrl+Enter) sets all your changes as one undo step and the checks run again. Values locked by a released harness are shown disabled with the reason. The tool never supplies a number itself. **Design > Engineering values…** opens the same window.

## 7. Generating harnesses

- **Wire colours**: *Edit > Wire colours...* sets one colour for each signal (PWR, RTN, CANH ...), from the IEC 60757 colours. The wires take them the next time you generate, the *Colour* column of the wire table in the **Harness** tab and of the wire list in **Lists** shows them, and the drawings draw them with the colour code as text. Nothing is preset: a signal with no colour is drawn grey. A wire between two different signals (`TX+/RX+`) takes the colour of the first.

- By default one harness is made for each pair of unit connectors. Nominal and redundant chains, and pyro lines, never share a harness.
- Pins are chosen by rules (power first, pairs side by side, pins you locked in the harness file never moved). **Why is it like this?** shows the reason for each choice.
- Generating again keeps IDs and the wires and pins you locked in the harness file (`"locked": true`; the app has no button for it), never touches released harnesses, and shows a report of what was added, changed and removed.
- A wire gauge stays **pending** until the derating values exist and the lengths are known (section 11, What an engineer must fill in). The tool never guesses an engineering value.

## 8. Outputs

`outputs/` contains, for every harness: drawing (SVG for the A3 sheets, PDF for A3 and A4), wire list, pinouts, BOM, mass and length, continuity and isolation tests, labels, a WireViz-style YAML file and an Excel workbook. For the whole system: block diagram, harness overview, BOM, mating and traceability matrices, DRC report, change log, revision report, and one JSON file with the whole model. Every file carries the tool version and a model hash. The status chip in the top bar and the header of the **Harness** tab show whether the outputs are up to date. Details are in `docs/OUTPUTS.md` in the repository (it is not installed with the app).

**Export…** (top bar, File menu or Design menu, Ctrl+E) opens the **Export outputs** window. It shows the output folder, a tree of harnesses and documents, and, once the export has run, the list of files written with **Open**, **Reveal in folder**, a picture of the selected drawing and **Copy selection to folder…**. The export always writes the complete set; the ticks in the tree choose what the list shows and what is copied. A problem found by the independent check, or a write error, stays in a notice in the window and nothing is written. The project must be saved to a folder first.

The **Lists** tab (Ctrl+3) shows the same tables on screen for one harness: **Wire list**, **Pinouts**, **BOM**, **Mass and length**, **Test tables**, **Labels** and the **System BOM**. Click a header to sort, type in the filter box, press Ctrl+C to copy the selected cells as text, and **Export table** writes the rows you see as CSV or Excel. **Only pending or not checked** keeps the rows whose value is still open.

Outputs are checked independently before they are written (every cell of the tables, the pins and signals in the drawings, the PDF texts and the sheets of the workbooks are compared with the design). If that check fails, nothing is written. Export is refused for a project that is read-only or has damaged files. The PDF drawings use the Windows-1252 character set: a character outside it (for example the ohm sign) shows as `?` in the PDF, and the export warns and names each such character; the SVG keeps it. The `outputs` folder is always safe to delete and make again.

## 9. Review, release and revisions

1. Make the design pass: no errors, plans current, every wire sized and measured.
2. **Export…** and review the outputs.
3. Open the **Releases** tab (Ctrl+5), or the **Harness** tab, and pick the harness. **Submit for review** (optional; **Open in review** in the Harness tab), then **Release…**. Type your name and a comment (at least 10 characters). Anything that blocks the release is listed in plain words, and under the form a line says what is still missing for the button to work. The window lists **What this release locks** (for example *18 wires, 198 pins, 9 interfaces, 3 parts, 1 interface type, 5 config files*) as a tree you can open; a config file that is still a placeholder is marked *Pending*. While a configuration file is still marked as a placeholder, the window also asks for a written reason (at least 10 characters); it is kept in the change log and the baseline. Once an engineer has reviewed the values and cleared the mark, no reason is asked. The same holds for the parts: while the harness uses parts that are not approved (or are example data), the window asks for a second written reason.
4. The harness is now **Released** (locked): it, the interfaces it carries and the pins it uses cannot be edited, and neither can the parts, interface types and configuration values it uses (importing parts or applying a profile that would change them is refused). A lock shows on the diagram, in the tree and in the Inspector, and a refused change says why and offers **Start new revision…**. A baseline (frozen snapshot) and a change log entry are stored. Once you have saved a release, **Undo** is off for that step; to change the harness start a new revision.
5. To change it: **New revision…** (Harness tab: **Revise…**). The window says what happens (the next revision becomes a draft, the released one stays as a baseline) and lists what becomes editable and what stays locked because another released harness uses it. The old revision stays available.

The **Releases** tab shows one timeline of every review, release and new revision, with a filter for one harness and chips for the event and the baseline. Under it, **Compare revision … with …** lists what differs between two revisions, or a revision and the working design, grouped by kind with counts; **Mark on diagram** marks the changed units and interfaces and **Clear marks** removes the marks. The **More** menu of the **Harness** tab has **Changes…**, **Change log…** and **Delete harness** (not possible once the harness is released; a generated harness comes back the next time you generate); the same three are in the Design menu and in the context menu of a harness in the Project tree.

Export the outputs again after a release so the drawings show *released*. The release check looks at the harness (gauges, lengths, open errors) and at whether the configuration files are still marked as placeholders. It cannot judge whether the values are right; that stays a decision for a person.

## 10. Command line

All commands take the project folder. Exit code 0 means success, 1 means the project has errors or a step is blocked, 2 means usage error or unreadable project (this includes a project with damaged files, which every command except `validate` and `check` refuses), 130 means interrupted with Ctrl-C. Commands that import data take `--dry-run`: they show what they would do and change nothing.

| Command | What it does |
| --- | --- |
| `harness-design-studio new FOLDER [--template NAME] [--name TEXT]` | create a project from an example (`harness-design-studio new --list` shows them) |
| `harness-design-studio templates FOLDER` | copy the import templates, CI scripts and the review checklist to a new folder |
| `harness-design-studio library DIR [--library-version V] [--library-source TEXT] [--library-date YYYY-MM-DD]` | show or record where the parts library comes from |
| `harness-design-studio schema FOLDER` | write JSON Schemas of the project files for editors that complete and check JSON |
| `harness-design-studio validate DIR` | check a project for errors |
| `harness-design-studio check DIR` | validate, plus problems left by Git merges (including released harnesses that were edited) |
| `harness-design-studio migrate DIR` | upgrade an old-format project (originals are kept) |
| `harness-design-studio generate DIR` | generate harnesses and save (not saved if errors) |
| `harness-design-studio verify DIR [--outputs]` | independent check of the harnesses, and of `outputs/` |
| `harness-design-studio drc DIR` | design rule report (Markdown); exit 1 on unwaived errors |
| `harness-design-studio export DIR` | write and verify all outputs |
| `harness-design-studio review DIR HARNESS --by NAME` | submit a draft for review |
| `harness-design-studio release DIR HARNESS --by NAME --comment TEXT [--checker NAME] [--accept-placeholders REASON] [--accept-unapproved-parts REASON]` | release (blocked while checks fail, or while values are placeholders or parts are not approved and no reason is given) and re-export |
| `harness-design-studio revise DIR HARNESS --by NAME --comment TEXT` | start a new revision |
| `harness-design-studio diff DIR HARNESS [--from REV] [--to REV]` | what changed since a baseline |
| `harness-design-studio compare OLD NEW` | compare two project folders (for example two Git checkouts); the last line names what is not compared |
| `harness-design-studio log DIR [HARNESS]` | print the change log |
| `harness-design-studio config DIR [--ampacity-csv FILE] [--apply-profile NAME]` | list missing or invalid engineering values; load a current-by-gauge table; fill unset values from a standard profile |
| `harness-design-studio import-parts DIR FILE --approved VALUE ...` | import an approved-parts list; you say what the approval values mean |
| `harness-design-studio import-lengths DIR FILE [--unit mm]` | import routing segment lengths from a table |
| `harness-design-studio import-netlist DIR FILE --unit U [--prefix J] [--connector J1=ID] [--part J1=PART] [--signal-map NAME=SIGNAL\|FILE]` | read connector pinouts of a unit from a KiCad netlist (.net or .xml); the pins become fixed |

A script that builds everything: `harness-design-studio check DIR`, `harness-design-studio generate DIR`, `harness-design-studio verify DIR`, `harness-design-studio drc DIR`, `harness-design-studio export DIR`. `harness-design-studio templates FOLDER` copies the templates, and `ci/build.sh` in that folder is this script.

## 11. What an engineer must fill in

Some values must come from your program's standards. Until they are filled in, results say so and the affected checks say *not checked*. The list: derating factors and ampacity table (`config/derating.json`), resistivity, service loop, pin gap, mass margin, shield grounding concept and test limits (`config/generation.json`), separation rules (`config/segregation.json`), EMC rules (`config/emc.json`), title block fields (`config/titleblock.json`), part masses and ratings in the library. `harness-design-studio config DIR` prints this list for your project, with what depends on each value; the same list is in `docs/PLACEHOLDERS.md` in the repository (not installed with the app).

In the app, press **Supply value…** on a rule in the **Checks** tab (section 6) to type values in; the window also lets you clear the *placeholder* mark once the values are reviewed.

On the command line, run `harness-design-studio config DIR` to see what is missing and what depends on it, load a current-by-gauge table from a CSV with `--ampacity-csv`, edit the rest in the JSON file (the keys go inside its `values` object), and set `"placeholder": false` once reviewed.

If you work to ECSS-Q-ST-30-11C or ECSS-E-ST-20-07C you can start from the values of those standards with `--apply-profile ecss-q-st-30-11c` or `ecss-e-st-20-07c`: only unset values are filled, each is printed with the requirement it comes from, and the files stay placeholders until you review them (`harness-design-studio config DIR` lists the keys; `docs/CONFIG.md` in the repository describes them and the part ratings the new rules need).

To see the machinery work before you have real values, copy the demo values from the templates (`config-demo-values/`) over a practice project. They are not engineering data, and the files stay marked as placeholders so every result built on them says so. Never release a real design with them.

## 12. Bring in your own data

Every import first shows what it would do, and a bad row stops the whole import so nothing is half applied. Each import is one undo step called *Import n rows*.

| You have | Do |
| --- | --- |
| Interfaces as a table | **File > Import > Import interfaces…** (Ctrl+Shift+I; CSV or XLSX with the columns id, type, from, to and optionally redundancy) |
| An approved-parts list | **File > Import > Import approved parts…**, or `harness-design-studio import-parts`, saying what your approval values mean |
| Segment lengths | **File > Import > Import segment lengths…**, or `harness-design-studio import-lengths`, then generate again |
| A unit's connector pinout in KiCad | export a netlist, then **File > Import > Import KiCad netlist…**, or `harness-design-studio import-netlist`; the pins become fixed |
| A current-by-gauge table | **File > Import > Import engineering values: ampacity table…**, or `harness-design-studio config DIR --ampacity-csv FILE` |

Parts, lengths, ampacity values and netlists open the **Import data** wizard in four steps: **1 Choose what and which file**, **2 Match the columns and check the first rows** (a live preview shows every row and the reason a row is refused), **3 Conflicts and placeholders** (what stays pending afterwards, such as parts whose approval is pending) and **4 Import**. Interfaces use their own earlier window, which also previews every row. The same imports are in the Project tab: press Enter on an entry under **Imports**.

Example files for every one of these are in the templates folder (`harness-design-studio templates FOLDER`).

## 13. When something goes wrong

| You see | Meaning and what to do |
| --- | --- |
| *Read-only* banner | The project was saved by a newer version of the tool, is open in another window, or its folder cannot be locked for editing (for example read-only media). Install the newer tool, close the other window, or copy the project to a folder you can write to. Nothing was changed. |
| *Project already open* | Another window or session has the project open. Close it there, or choose **Open read-only**. A lock left by a crashed session or from before a restart is taken over; a lock from another computer is respected (the message names the lock file). |
| *This project has problems* (recovery view) | Some files could not be loaded. Everything else loaded. **Save salvaged copy** writes a clean copy; the original is protected. |
| *Unsaved changes found* at start | The last session ended before saving. **Restore** brings back your last edits; if the files changed since (a Git pull), the window says so first. A project that was open read-only stays read-only. |
| *Project changed on disk* | Someone (or Git) changed the files. Reload to see them, or keep your version (asked once per state of the files). A project that was deleted while open is reported when you return to the window. |
| *Outputs out of date* (status chip or banner) | The design changed since the last export. Export again. |
| *Blocked because it touches released items* | The harness is released, and so are the parts, interface types and configuration values it uses. Start a new revision. |
| A wire gauge says *pending* | A value is missing: `harness-design-studio config DIR` says which. A gauge also needs the interface's Max current and the segment lengths. |
| `harness-design-studio` is not found | `~/.local/bin` is not on your PATH. Add it, or log out and in. |

## 14. Keyboard and menus

| Keys | Action |
| --- | --- |
| Ctrl+N, Ctrl+O | new project, open project |
| Ctrl+S, Ctrl+Shift+S | save, save as |
| Ctrl+Shift+I | import interfaces from a table |
| Ctrl+Q | quit |
| Ctrl+K | command palette (it floats over the window; Esc or a click elsewhere closes it): type a command, an ID or a name; every command of the menus is in it |
| Ctrl+G, F5, Ctrl+E | generate harnesses, run the checks, export |
| Ctrl+I | new interface |
| Ctrl+1 to Ctrl+5 | the tabs Diagram, Harness, Lists, Checks, Releases |
| Ctrl+Shift+T | the Interface table (left panel) |
| F6, Shift+F6 | next and previous panel (diagram, project panel, inspector) |
| Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z | undo, redo (the menu names the step, for example *Undo Move PDU2*) |
| Ctrl+=, Ctrl+-, Ctrl+0 | zoom in, zoom out, real size (100 %) |
| F, Shift+F | fit the whole diagram, zoom to the selection (when the diagram has the keyboard focus) |
| Ctrl+wheel | zoom at the pointer; the wheel alone scrolls (Shift+wheel sideways); middle button or Space and drag pan |
| Ctrl+A, Ctrl+D, Ctrl+F | select everything, duplicate the selected units, find in the diagram (in the diagram) |
| Ctrl+Shift+L | arrange the diagram |
| C, Esc | start the Connect tool, back to Select (Esc also clears the selection) |
| Tab, Enter or Space | move between units and links; Space selects, Enter also shows the item in the Harness tab |
| Shift+click, Ctrl+click, drag on the background | add to the selection, take out of it, rubber band (the Project tree takes Shift and Ctrl too: Shift+arrows select several units or interfaces without the mouse) |
| Shift+arrows | move the selected units |
| Delete | delete the selected items (after showing what it affects; only in the diagram, the Interface table and the Project tree) |
| Ctrl+C, Ctrl+Shift+C in a table | copy the selected cells as text, with the header row |
| `/` in the project tree | go to the filter; Enter selects, Ctrl+Enter or double-click opens |
| Ctrl+F in Checks or Lists | filter the rules or the rows |
| F1 | this guide |

Every command is in a menu. The keys above are shown next to the items, and the tooltip of a button names its key. Tab visits every unit and link in the diagram, so use **F6** to leave it.

| Menu | Item | What it does |
| --- | --- | --- |
| File | New project… (Ctrl+N) | one window: an empty folder, a name, and optionally an example |
| File | New project from an example… | the same window with the first example ticked |
| File | Open project… (Ctrl+O) | opens a project folder |
| File | Open the sample project | opens the built-in sample (example data); **Save as…** keeps your changes |
| File | Save (Ctrl+S), Save as… (Ctrl+Shift+S) | saves the project; save as writes a copy to a new folder |
| File | Import | Interfaces…, Approved parts…, Segment lengths…, Engineering values: ampacity table…, KiCad netlist… (section 12) |
| File | Export… (Ctrl+E) | the Export outputs window (section 8) |
| File | Quit (Ctrl+Q) | closes the app |
| Edit | Undo, Redo | steps back and forward through your changes |
| Edit | Select all, Duplicate, Delete, Find in diagram | work on the selection; Duplicate copies a unit with its connectors but not its links; Delete shows what else goes with it |
| Edit | Create redundant copy | builds a redundant (backup) copy of the selected unit and its chain |
| Edit | New interface… (Ctrl+I), Connect (C) | a form for a new interface; the Connect tool |
| Edit | Align, Space evenly | line up or space out the selected units |
| Edit | Add zone… | adds a lane to the diagram; asks for its name |
| Edit | Wire colours... | chooses the wire colour of each signal (section 7) |
| Edit | Add unit | one item for each kind of unit (computer, power unit, wheel ...) |
| Edit | Connect with | one item for each interface type (the arrow beside the Connect button lists the same); then click two units |
| View | Guided, Expert | the two modes of section 5 |
| View | Theme | Follow the system (the default), Light or Dark |
| View | Show overview map, Show legend, Snap to grid | overlays and the grid |
| View | Show all link labels | shows the values (such as `28 V · 5 A`) on every link, not only on the selected one |
| View | Interface size | makes text and controls larger: 100, 125, 150 or 200 %; the first size follows your screen |
| View | Zoom in, Zoom out, Fit all, Zoom to 100 %, Zoom to selection | zooms the diagram (Ctrl+=, Ctrl+-, F, Ctrl+0, Shift+F) |
| View | Arrange diagram | tidies the units inside their lanes; Undo restores them |
| View | Project, Inspector | shows or hides each panel |
| View | Reset layout | puts the panels back where they were at the start |
| Design | Generate harnesses (Ctrl+G) | builds the harness plans after a preview |
| Design | Run checks (F5), Cancel the running check | runs the design rules now |
| Design | Export… (Ctrl+E) | the Export outputs window |
| Design | Submit harness for review…, Release harness…, Start new revision… | change control for the harness in view (section 9) |
| Design | Show changes of harness…, Show change log of harness…, Delete harness… | the harness in view: what changed since a baseline, who changed what, delete a draft |
| Design | Engineering values… | the window where you type the values the rules wait for (section 6) |
| Go | Go to Diagram, Harness, Lists, Checks, Releases (Ctrl+1 to Ctrl+5) | shows that tab |
| Go | Go to Interface table (Ctrl+Shift+T) | opens the Interfaces tab of the left panel with the keyboard in the table |
| Go | Next panel, Previous panel (F6, Shift+F6) | moves the keyboard focus between the panels |
| Help | User guide (F1) | opens this guide |
| Help | Search and commands (Ctrl+K) | the command palette |
| Help | Replay the tour | shows the short first-run tour again |
| Help | Glossary | the list of words the tool uses |
| Help | Show project problems | lists what could not be loaded, for a project with problems |
| Help | About | the version and a short note about the tool |

The **Show** list in the toolbar fades everything except one signal class (power, data, analog, RF ...), one connector or one bundle (harness), so a large diagram can be read one piece at a time; choose *All interfaces* to see everything again. It changes nothing in the project. The **Interface table** and **Outline** tabs of the bottom panel list every interface and unit as text; they are the screen-reader friendly views of the diagram.

## 15. Glossary

- **Harness**: a bundle of wires with connectors that carries signals between units.
- **Interface**: a logical connection between two units, for example RS-422 from the computer to a wheel.
- **Nominal / redundant**: the main chain and its backup. They never share a connector or harness.
- **Auto-filled**: a connector the tool chose; unconfirmed until a person looks at it.
- **Pending**: a value nobody has entered yet, for example a wire gauge that waits for a derating value. Shown with a dotted chip, never as a number.
- **Not checked**: a design rule that could not run because a value it needs is missing. It is not a pass.
- **Out of date**: the harness plans or the exported files no longer match the design; generate or export again.
- **Baseline**: a frozen snapshot made when a harness is released.
- **Waiver**: a recorded decision to accept a warning, with a reason.
- **Placeholder**: a value nobody has entered yet; the tool never invents one.
- **Model hash**: a fingerprint of the design; every output carries it.
- **Fixed pin**: a pin whose signal the unit itself defines (imported from KiCad); generation never moves it.
