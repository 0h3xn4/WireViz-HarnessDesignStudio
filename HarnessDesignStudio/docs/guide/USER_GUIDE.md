# Harness Design Studio: user guide

This guide is for systems engineers who have never used the tool. It works offline. Press **F1** in the app to open it.

New here? Read sections 1 to 4 (about fifteen minutes). Section 3 gives you a ready-made practice project to play with.

## 1. What the tool does

You draw devices (computer, power unit, wheels ...) and the interfaces between them. The tool turns that into harnesses: which wires, on which pins, in which connectors. It checks the result, writes a build workbook and lists for every harness, and keeps a record of every release.

Your design is the source of truth. Everything else (harnesses, build workbooks, lists, drawings) is generated from it and can be generated again at any time.

Seven words carry most of the meaning:

| Word | What it is |
| --- | --- |
| **Device** | A box with connectors on it: the computer `OBC1`, the power unit `PCDU1`, the wheel `RW1`. |
| **Interface** | One connection between two devices, of a type such as RS-422 or primary power. This is what you add. |
| **Connector, pin** | A plug or socket, and one contact of it. A pin carries one signal. |
| **Harness** | A bundle of wires with connectors that carries interfaces between devices. Generated; its wires can be edited and wires of your own added. You can also make one by hand, with no interface (section 7). |
| **Wire** | One conductor between two pins, with a gauge, a part and a length. |
| **Zone** | A lane of the diagram (a panel or compartment) that devices sit in. |
| **Placeholder** | A value nobody has entered yet. The tool never invents engineering numbers. |

The starter library follows one baseline:

| For | Baseline |
| --- | --- |
| Communication | RS-422, RS-485 and CAN |
| High data rates (for example a payload) | Ethernet, on an RJ45 connector, as the alternative |
| Power and data connectors | Micro-D 9, 15, 21, 25 and 31 pin (power: 9 pin; for data the size follows the number of interface types the connector carries) |
| RF | SMA |

Other interface types and older connector parts stay in the library for projects that need them. All parts are examples with fictional part numbers, none approved; your approved parts list replaces them.

## 2. Install and start

The steps below are for Ubuntu 24.04 or newer. There are also packages for Windows 10 and 11 (from version 1.2.0); `docs/INSTALL.md` in the repository (way D) describes them. macOS is not supported (removed in 1.6.0).

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

Then **File > Open project…** and pick the folder. You cannot break anything: it is your own copy. At a first run the editor opens it on the **Next step** page (section 5); press **Model** in the rail on the left to see the diagram.

Version 1.0.0 has five examples. If `harness-design-studio new --list` shows only `blank`, `first-steps` and `small-satellite`, you have the 0.1.0 packages, which have those three; `minimal-satellite`, `flatsat` and the wire colours of section 7 came with 1.0.0.

| Example | What it is |
| --- | --- |
| `blank` | An empty project with the starter parts and interface types and no devices. Use it for a real design: the empty diagram has the button **Add a device**. |
| `first-steps` | Three devices, a power link and an RS-422 link. Nothing is generated yet: start here. |
| `minimal-satellite` | Seven devices, nominal only: power, computer, radio, wheel and sun sensor. Adapt it. |
| `small-satellite` | 14 devices with nominal and redundant chains. Generate it to see a realistic system. |
| `flatsat` | A complete bench: 23 flight and ground devices, generated, with example numbers. |

`harness-design-studio templates my-templates` copies templates for your own data: CSV files for interfaces, parts and lengths, a KiCad netlist, a CI script and a review checklist. The demo engineering values in it are for learning only.

## 4. The window and your first project

The window has these parts. Everything is also reachable with the keyboard (section 14).

| Part | What it holds |
| --- | --- |
| **Navigation rail** | Down the left edge: **Next step**, **Home**, **Model**, **Checks**, **Drawings**, **Outputs**, **Revisions** and, at the bottom, **Settings**. It opens the area you choose; the button at its foot shows icons only. **Next step**, **Home** and **Settings** are pages of their own. The Simple workspace (section 5) leaves **Home** out of the rail; Ctrl+7 and **Go > Go to Home** still open it. |
| **Top bar** | The project name, *Saved* or *Unsaved changes*, the revision, a short model hash, where you are, **Undo** and **Redo**, **Guided** and **Expert**, **Show panels** (Simple workspace only), **Search** (Ctrl+K), the three steps **Generate** (the one blue button), **Check** and **Release…**, then **Export…** and a status chip. The tooltip of a step says what is done and what comes next. |
| **Banner** | Appears under the top bar when something needs you: the plans or the exported files are out of date (buttons **Generate** and **Export…**), or a generate, export or check failed (**Try again**). A change that is refused because a harness is released stays on screen as a message over the diagram, with **Start new revision…**, until the next change goes through. |
| **Tabs** | **Diagram**, **Harness**, **Lists**, **Checks**, **Releases**, **Devices** (Ctrl+1 to Ctrl+6). Each area shows its own: Model has Diagram and Devices; Checks, Drawings (the Harness tab), Outputs (the Lists tab) and Revisions (the Releases tab) have one each. |
| **Left panel** | Closed in the Simple workspace until you press **Show panels**. The **Project** tab: a tree of devices, interfaces, harnesses, parts, interface types, configuration files and imports, with a filter and an **Add** button. The **Device list** tab (Ctrl+Shift+J) and the **Interfaces** tab (Ctrl+Shift+T): every device and every interface as a table that works like a spreadsheet (see below). |
| **Right panel** | Closed in the Simple workspace too. **Inspector** (the fields of what you selected, and where it is used), **Why** (the reasons for a choice) and **Problems** (the problem cards, with a **To do** list above them). |
| **Problems panel** | Closed until you press **Problems (n)** in the status bar (when that button is shown) or choose **View > Problems panel** (Ctrl+Shift+M): every open problem with its severity, rule, object and message; click one to go to the object. |
| **Status bar** | What runs in the background (with **Cancel**) or the last check, the project folder, **Problems (n)**, *Offline*, a link *n values pending · n rules not checked*, and the zoom level (the button, the count and the link are problem notices, see below). The model hash, the rule count and *Generated at model …* are in the tooltip of the counts. The Simple workspace shows only the save state, the running job, *Offline* and the project path. |

The status chip in the top bar says one thing: *Up to date*, *Plans out of date* (the diagram changed after Generate), *Outputs out of date* (the design changed after the last export), *Not generated*, or the running job (*Generating…*, *Exporting…*, *Checking…*). Colour is never the only sign: every state has an icon and a word, and the two states for "nothing known yet" have a pattern. **Pending** (dotted) is a value nobody has entered; **Not checked** (hatched) is a rule that could not run. Neither is a pass, and neither is empty.

**Show problem notices** (View menu, and Settings > Editing) switches off, in one step, what shows problems without being asked: **Problems (n)**, the count on the Problems tab, the status chip, the chip and badges on the diagram, the pending-values link and the *out of date* banner. It is on in Full and off in Simple, for each workspace. **Check**, the Checks tab, the Problems panel and the read-only, locked, damaged-file and sample banners always stay.

Panels you hide or move are remembered for each project; **View > Reset layout** puts them back. In a small or narrow window the tool hides panels so the diagram stays large, and says so.

### Home, the three steps and the tables

**Home** (Ctrl+7; not in the rail of the Simple workspace) shows the open project with its counts, four buttons (**New project…**, **Open project…**, **New from an example…**, **Open the sample project**), your **Recent projects** with how many harnesses are draft, in review or released (**Open**, **Remove from the list**) and the **Examples**. **Try the flatsat example** opens a copy of that example in your Documents folder.

The three steps in the top bar go in order. **Generate** builds the harnesses, **Check** (F5) runs the design rules, **Release…** locks a harness as a numbered revision. A step that has to wait says what to do first, for example *generate the harnesses first* or *check the design first*. When you look at part of a released harness, a banner says so and offers **Start new revision…** and **Show the revisions**.

The **Device list** and **Interfaces** tables work like a spreadsheet:

- **Enter** or **F2** edits the selected cell, **Esc** keeps the old text, and **Ctrl+C** copies the selected cells.
- **Ctrl+V** pastes a block of cells copied from Excel. It is one undo step; cells that cannot take a value (a read-only column, or past the end of the table) are left out and counted in the message.
- An edit made with several rows selected applies to all of them.
- A right-click on the header chooses the columns. Numbers are right-aligned and the unit is in the header.
- The tables edit the rows that exist. A new interface comes from **New interface…** (Ctrl+I) or the import.

The **Problems panel** (Ctrl+Shift+M, or **Problems (n)** in the status bar) lists every open problem: severity, rule, object and message. Filter it with **All**, **Error** or **Warning**. Click a row to go to the object; **Details and fixes** (right-click, or Shift+Enter) opens the problem as a card in the Inspector.

### Settings

Press **Settings** on the rail (Ctrl+,). The page lists six sections. Every setting takes effect at once and is kept for the next start; the page follows the View menu and Ctrl+K, which change the same settings.

- **Appearance**: **Theme** (*Follow the system*, *Light* or *Dark*), **Interface size** (100, 125, 150 or 200 %; it takes about a second to apply) and **Reduce motion**, which turns off the fades and slides of menus, lists and tooltips. The interface uses the bundled fonts Inter and JetBrains Mono.
- **Editing**: **Workspace** (*Simple* or *Full*), **Mode** (*Guided* or *Expert*), **Snap devices to the grid**, **Show every link label** and **Show connectors on connections**.
- **Project**: **Open the engineering values…**, the window of section 6, and the **Library folder** (after 1.7.0: **Choose…**, **Clear** and **Open the library…**; the folder that your team shares, see "The library" below).
- **Keyboard shortcuts**: every key of the window, with a box **Filter the shortcuts…**. They are fixed and cannot be changed.
- **About**: the version, the Python, Qt and PySide6 versions, and where your settings are kept. **Help > About** opens this section.
- **Licences**: the fonts, the icons and Qt, with their licence texts.

### Your first project in ten steps

At a first run the editor is in the Simple workspace and a project opens on the **Next step** page (section 5). Press **Model** in the rail (or Ctrl+1) to get to the diagram, and **Show panels** in the top bar for the Project tab and the Inspector. The steps below work in both workspaces.

1. Start the app. The sample project opens with a short tour; skip it or follow it. The tour leaves out a step whose panel is hidden (a small window or a high interface size), records that it was shown however you close it, and can be started again with **Help > Replay the tour**.
2. **File > New project…** opens one window: choose an empty folder, give the project a name, and optionally pick an example (section 3; `first-steps` has three devices, start there). A problem with the folder or the name is written under the field. **File > New project from an example…** is the same window with the first example ticked.
3. Add devices: press **Add** in the Project tab, or use **Edit > Add device** (the Project tab is closed in the Simple workspace, so use the menu there). Pick *Computer*, then add a *Power unit* and an *Actuator (wheel)*. In a project with no device the empty diagram also has the button **Add a device**, which asks for a name first and adds a device whose connectors you define yourself (see The Devices tab).
4. Connect them. Press **C** (or the **Connect** button above the diagram), then click the first device and the second: the window **Link connectors** proposes which pins go together from the signal names on the pins (see below). The older way, by interface type, is in the arrow beside **Connect** and under **Edit > Connect with an interface type…**: pick a type such as *RS-422*, then click two devices; devices that cannot take it are greyed out, with the reason beside them. **Ctrl+I** (or **Add > Interface…**) opens a form for that way.
5. Look at **Problems** (right panel, or the Problems panel at the bottom, Ctrl+Shift+M). Each card says what is wrong, why it matters and how to fix it. Many have a one-click **Fix**. The **Checks** tab lists all 39 design rules with their result (section 6).
6. The top of the **Problems** tab has a **To do** list of what is left to do; a click on a line shows the device or interface.
7. Press **Generate** in the top bar (**Generate harnesses**, Ctrl+G). A preview shows what will be added; nothing changes until you press **Apply**. **Undo** takes it all back. The **Harness** tab opens (the Drawings area).
8. In the **Harness** tab pick a harness: its connectors and pins, its wires, a drawing (zoom with the wheel, change sheet with **Previous sheet** and **Next sheet**) and *Why* for the selected wire, connector or pin. The **Lists** tab (the Outputs area) shows the wire list, pinouts, BOM and test tables.
9. Save with **Ctrl+S**.
10. Press **Export…** in the top bar (Ctrl+E): choose what to look at and press **Export** to write the build workbooks and lists into the project's `outputs` folder (section 8). Tick **Include the PDF drawings** if you also want the harness drawings.

On a power interface set **Max current (A)** in the Inspector; without it the wire gauge stays pending.

**Connecting by the pinout** (after 1.7.0). **Edit > Link connectors…** (Ctrl+Shift+K), or **Connect** and two devices, opens **Link connectors**. The program pairs the pins by signal name, never by position (`TX+` meets `RX+`, `PWR` meets `PWR`; an output is not paired with an output); you change, add or remove pairs and give a pin a role (Power, Return, Ground, Signal, Shield, Spare), then press **Link connectors**.

The connection is a dash-dotted line on the diagram and an entry under **Connections** in the Project tab. **Design > Check my connections** reviews them and changes nothing. **Create harness** makes a harness with one wire for each pair, only when you press it and agree; the program never makes one on its own. In Expert mode, or with **View > Show connectors on connections**, a small box at each end of the line names the connector and the pins the connection pairs; the tooltip names the way through the harness once one exists, and **Show the harness** (right-click on the line) opens the Harness tab on it.

### The Devices tab

The **Devices** tab (Ctrl+6) shows one device down to each pin. Pick the device on the diagram or in the project tree, or in the box at the top of the tab. The header gives its state (*Draft*: no interface ends on it, *In use*, *Locked* by a released harness, or *Read-only*), the number of connectors, pins and signals, and two buttons: **Duplicate** (the same as Edit > Duplicate) and **Export pinout…**.

Left, the list of the device's connectors; right, the connector's part, gender, keying and what it carries, and how its pins are allocated: *Automatic* (Generate puts the signals on free pins) or *Fixed pinout* (the signals go to the pins of their own name).

Below, the pin table: pin, signal, mode (*Free*, *Fixed*, *Locked*), interface, direction and class (taken from the interface type of the signal, empty when no type has that signal), the wire and a state. The *Function* column is free text for what the pin does (since 1.4.0). **Contact** adds the contact size and the termination (*crimp* or *solder*). The connector card has a *Label* field: text that `labels.csv` prints for the connector.

With **Contact** on there is one more column, **Cable contact** (since 1.7.0): the contact part of the library that the cable side uses on this pin. Generate copies it to the cable connector. **Cable contact…** (also in the context menu) sets it for the selected pins in one undo step. Pasted headers *Cable contact*, *Contact part* and *Cable contact part* fill it; *Contact* alone is still the contact size.

Under it the notes about the connector, for example a signal that no interface type has, or *CANH* without *CANL* on a fixed pinout; a double-click selects the pin the note is about.

At the bottom, **Pinout as exported** shows the rows of `system/box_pinouts.csv` for this device; **Export pinout…** saves them as a CSV file or an Excel workbook.

**Save to library…** writes the device with its connectors, pinouts, parts and interface types to a *device library file* (JSON; an existing file is added to), and **Add from library…** adds devices from such a file to this project (since 1.4.0). Nothing in the project is replaced: a taken ID gets the next free one (`GYRO1-2`), and a part or interface type the project already has stays as it is. Adding is one undo step.

#### The library (after 1.7.0)

The **library** is a folder that your team shares, on a shared drive or in a Git repository. It holds **device files** (the *device library file* above) and **subsystem files**: a subsystem is a set of devices with the connections between them, added to a project in one step. A blank project holds no subsystem. The program only reads the folder, never uses a network, and writes into it only when you press **Save**.

- **File > Library folder…** (also **Settings > Project**) chooses the folder. It is a setting of you, on this computer.
- **File > Library…** (Ctrl+Shift+O, also **Library…** on the Home page) opens the **library window**, a window of its own beside the editor that does not block it. On the left a search field (Ctrl+F) and a filter *Devices and subsystems / Devices / Subsystems* over the list; on the right a preview, the connectors and pins of a device or the devices and connections of a subsystem. **Refresh** (F5) reads the folder again. A folder that is missing or cannot be read, and a file that is damaged, are said in words in the window.
- **Add to project** (or Enter in the list) adds the chosen device or subsystem as one undo step. Nothing of the project is replaced: a taken ID gets the next free one (`OBC-2`), a subsystem sets the subsystem of each device to its name and adds the connections between them, and it is all or nothing. **Number of these devices** beside it adds a device in that number (see below).
- **Save selection to library…** saves the devices selected in the project, as devices or as a subsystem with a name and a description. A subsystem file is never replaced: a name that is taken is refused under the field. A connection with one end on a device that is not selected is left out, and the window says how many.
- On the command line: `export-subsystem` and `import-subsystem` (section 10).

**A number of the same device** (after 1.7.0). *Number of these devices* in the **Add device** window and in the **Devices** tab (with **Add copies**) says how many of a device the design has, in place of choosing a nominal and a redundant chain. Two are `ID` and `ID-R`, exactly what **Create redundant copy** makes (so a project does not change whichever way you did it); three add `ID-3`, and so on up to 10, each with the connectors of the device and its links mirrored where the other end has a free connector. It is one undo step. The number is counted from the devices that exist: it only grows, so to have fewer you delete a copy.

#### Defining a device

- **Edit > Add device > Device…** (Ctrl+Shift+N; also **Add** in the Project tab, and the button **Add a device** on an empty diagram) opens the window **Add device**: type the **Name** (for example *Star tracker*), accept or change the **ID** it suggests (`STAR1`; once you edit it, it stops following the name) and pick the **Subsystem**. **Add device** adds an empty device in a free slot and opens the Devices tab. The kinds in **Edit > Add device** need no name.
- Under the connector list pick a part (type to search; the first entry is **New part…**, which also makes the mating half) and press **Add connector** (Ctrl+Shift+C goes to the picker; Enter adds). The pins are numbered from the part's pin count. **Delete connector** shows what it touches first.
- Click a cell and type, or press F2 or Enter. Enter keeps the value and goes down; Esc cancels. A pin name is checked while you type. **Add pin** (Insert) adds a pin after the current one; Delete clears the signal of the selected pins; **Delete** (Shift+Delete) deletes pins after a line that says what they touch; Space cycles the mode (*Free*, *Fixed*, *Locked*); Ctrl+V pastes cells copied from a spreadsheet, either a column from the current cell down or a table with a header row (*Pin*, *Signal*, *Mode*, *Contact size*, *Termination*, *Cable contact*).
- **Fill…** (Ctrl+L) puts the signals of an interface type on the selected pins in order (for example *CANH*, *CANL*). **Assign…** (Ctrl+Enter) locks the selected pins to an interface that ends on this device. Both are one undo step; **New interface type…** is in the dialog.
- On the card, a part with another pin count asks on one line whether to resize the pins and set the gender; both happen in one step. A fixed pinout is a promise that each interface signal has a pin of its name (the card says so).
- A part or interface type made here is marked *pending* or *unverified*. The tool never approves a part. A released device shows a banner with **Start new revision…**; its spare pins stay editable, its pin names and count do not.

## 5. Guided and Expert mode

**Next step.** The first item of the rail, **Next step**, shows one page, *What to do next*: one card with one button, and the six steps of the work, each with an icon and a word (*done*, *next*, *to do*). It looks at the project and names the first step that is not done. The link **Show everything** switches to the Full workspace.

**Simple or Full.** The workspace is a setting in the View menu and under **Settings > Editing**. A first run (a settings file with nothing stored yet) gets *Simple*, which opens a project on the Next step page. A settings file that already holds values keeps *Full*, which opens a project where it opened before.

Simple shows less. The project tree, the inspector and the Problems panel start closed (**Show panels** in the top bar opens the tree and the inspector together), the minimap and the legend are off, the status bar keeps the save state, the running job, *Offline* and the path, and the tools above the diagram are **Select**, **Connect**, **Add device** and **More**. **Home** is not in the rail. Nothing is removed: each item keeps its menu entry (and its shortcut, where it has one), and Ctrl+K finds it. Each workspace keeps its own layout. The problem notices are off in Simple.

The workspace is not the mode. Guided and Expert change only how much the diagram shows:

- **Guided** (default): you work with devices and interfaces. The tool chooses connectors and pins and marks its choices as *auto-filled* until you confirm them.
- **Expert**: you also see each connector of a device and can choose the exact connector for every end of an interface.

Switching modes never changes your data.

### Reading a dense diagram

A system with many devices has many links. The editor makes them readable in these ways:

- **Pictures tell the kinds apart.** A link carries the picture of its kind: a bolt for power, a ground symbol, a bus with end stops for CAN, two arrows for a differential pair (RS-422, LVDS), a bus with drops for RS-485, a node with branches for SpaceWire, two boxes for Ethernet, a sine wave for an analog signal, a square wave for a discrete signal, a spark for a pyro line, a ring for RF coax. A link with twisted-pair signals is drawn as two lines, a redundant link is dashed. The legend (button at the bottom left of the diagram; **View > Show legend**) shows the pictures the project uses.
- **Connectors are drawn as they look**: a flange with screw holes and the shell in front of it: a tapered D for a D-sub, a rounded block for a Micro-D, a round shell, an RJ45 plug, a coax ring. The size and the dots follow the pin count, which is also written as a number. **Gender is black or white**: a male connector (pins) is drawn solid, a female connector (sockets) as an outline, and a connector whose gender is not set with a dashed outline; the legend says so. The harness drawings and the mating matrix state the gender of every cable connector in words. In Expert mode a dashed line splits the device into a left side and a darker right side (ports sit on the edge of their side), and every port reads from its edge inwards: the designator (J01), the connector picture and the pin count. In Guided mode a device shows its connectors as small pictures. What a link carries is drawn on the link.
- **Numbers appear when they exist.** A power link shows e.g. `28 V · 5 A` beside its picture, but only what somebody entered; nothing is filled in. In a diagram of more than 30 links the numbers show for the selected, focused or hovered link; *View > Show all link labels* shows them everywhere. Hover a link to read its name, type, values and ends in words.
- **Click a device or a link.** Only its links stay in full colour; everything else fades. Click the empty background or press Escape to see everything again. This is the quickest way to answer "what is connected to this?".
- **Show** (the list at the right end of the Model tab bar, *All interfaces* by default; **More > Show only** in the Simple workspace) fades everything except one signal class, one connector or one bundle. It can be combined with a selection.
- **Links run in lines.** Each link leaves on the edge that faces the device at its other end, goes sideways into the gutter between lanes, runs up or down in its own track, and enters the other device sideways. Links between the same two lanes run side by side, ordered so that they cross as little as possible.
- **Arrange diagram** (View menu, Ctrl+Shift+L, or the button at the right end of the Model tab bar; **More** in the Simple workspace) puts the devices in order and keeps room for each one: a device with many connectors is tall in Expert mode, and the devices around it make way. One undo step restores the old positions.

Zoomed far out, a device shows its ID and each kind of link its own dash pattern and a small picture; zoom in to see pictures and numbers.

### Marks on the diagram

- **Problems, warnings, values to enter, not checked.** A device or link that has open findings shows a small badge with an icon and a count: problems, warnings, values still to enter (*V ? · A ?* on a power link), and *not checked*. Click a badge to select the object; its problems are in the Problems list. Hover a badge to read what it counts. Before the first check has finished every object shows *not checked*, so a clean card is never mistaken for a passed one.
- **Locks.** An object that a released harness holds shows a lock and the harness and revision (*W001 A*), and a faint tint. The tooltip says who locks it and what stays editable.
- **Auto-filled.** A card with connectors the tool chose shows a dashed *n auto* chip, in Guided mode too; hover it to read why they were chosen and that nobody has confirmed them yet.
- **State of the harnesses.** A chip in the top left of the diagram says *Harnesses out of date*, *not generated yet*, *Outputs out of date*, *not exported yet* or *up to date*.
- **Card pictures and tags.** A card shows a picture of its kind of device and the number of connectors (*12 conn*). FLIGHT or GROUND tags are a viewer setting: right-click a device and choose **Tag zone … as**; they are not saved in the project.

### Moving around and selecting

- **Click** selects one item. **Shift+click** or **Ctrl+click** adds or removes, a **drag on the background** draws a rectangle, **Ctrl+A** selects all. With several devices selected the Inspector shows what they have in common; **Delete**, **Duplicate** (Ctrl+D), **Align** and **Space evenly** (Edit menu) act on all of them as one undo step.
- **Ctrl+wheel** zooms at the pointer, the wheel scrolls, **Shift+wheel** scrolls sideways, the **middle button** or **Space** with a drag pans. **F** fits everything, **Shift+F** zooms to the selection, **Ctrl+0** shows 100 %. The zoom level is at the right of the status bar.
- **Ctrl+F** finds a device or link by ID, name, connector or type and marks every match; Enter goes to the next. **Double-click** a link or device (or press Enter on it) opens it in the **Harness** tab.
- **Right-click** shows a menu with the same actions as the menus; an entry that cannot be used stays in the menu, greyed out, with the reason.
- **View > Show legend**, **Show overview map** and **Snap to grid** switch overlays and the grid; hold **Alt** while dragging to place a device freely.

## 6. Problems, checks and waivers

- **Error**: must be fixed. Errors cannot be waived.
- **Warning**: fix it, or **Waive** it with a reason of at least 10 characters. Waived warnings stay visible in the report with their reason.
- **Note**: information, for example *not checked because a value is still a placeholder*.

The quick checks run on every edit. The design rules (39 of them, four of which review the connections between connectors: **Design > Check my connections** shows only those) run in the background a moment after you stop editing, or when you press **Check** (F5); the top bar says *Checking…* while they run, and the status bar shows the job with **Cancel**. The **Problems** cards say when they are checking, and a header such as *39 rules: 20 passed, 2 failed, 12 not checked* says how it went.

The **Checks** tab (Ctrl+4) has one row for each rule:

- A strip on top counts the rules *passed*, *failed*, *not checked* and the *pending values*; each count is a button that filters the table. The status-bar link *n values pending · n rules not checked* opens the same tab. When the design changes, the tab says *Out of date* until the rules have run again; **Check again** runs them now.
- **Result** is a chip with an icon and a word: *Pass*, *Fail*, *Not checked* (the rule could not run) or *Pending*. *Pass (placeholder values)* means the rule passed on values nobody has reviewed. Click the **Result** header to put the worst first.
- **Fix all (n)** (top right of the tab) applies the one-click fix of every open problem that has one, as one undo step; n is how many there are, and its tooltip says which kinds of fix (for example *Choose connectors automatically (2)*). It never confirms a connector the tool chose: confirming says that a person looked at it, so those stay open for you (the *Confirm connectors* button on the problem itself does it). It is greyed out, with the reason in its tooltip, when n is 0 or the project is read-only. A fix that a released harness locks is left out and named in the message; the rest are done. Connectors the tool chooses this way are marked *auto* until you confirm them.
- Select a rule to see what it found, what it needs, and the requirement IDs it serves. Press Enter on an offending object, or double-click it, to show it on the diagram. Ctrl+F filters the rules.
- A rule that is *not checked* names the value it waits for and has **Supply value…**. It opens **Engineering values**: every value the rules need, grouped by config file, with its device, a *placeholder* toggle and the reason when a value is refused. **Apply** (Ctrl+Enter) sets all your changes as one undo step and the checks run again. Values locked by a released harness are shown disabled with the reason. The tool never supplies a number itself. **Design > Engineering values…** opens the same window.

## 7. Generating harnesses

- **Wire colours**: *Edit > Wire colours...* sets one colour for each signal (PWR, RTN, CANH ...), from the IEC 60757 colours. The wires take them the next time you generate, the *Colour* column of the wire table in the **Harness** tab and of the wire list in **Lists** shows them, and the drawings draw them with the colour code as text. Nothing is preset: a signal with no colour is drawn grey. A wire between two different signals (`TX+/RX+`) takes the colour of the first.

- By default one harness is made for each pair of device connectors. Nominal and redundant chains, and pyro lines, never share a harness.
- Pins are chosen by rules (power first, pairs side by side, pins you locked in the harness file never moved). **Why is it like this?** shows the reason for each choice.
- Generating again keeps IDs, the wires you edited and the pins you locked, never touches released harnesses, and shows a report of what was added, changed and removed.
- **Edit wire** (since 1.4.0): in the **Drawings** area pick one or several wires and open the **Edit wire** tab beside **Why**. It sets the gauge, type (a wire part of the library), colour and length, the strip length at each end (**Strip A (mm)**, **Strip B (mm)**; since 1.7.0), a label that the wire labels print instead of the signal name, and a note. **Apply** (Ctrl+Enter) changes only the fields you touched; gauge, type, colour and length lock the wire so Generate keeps them, strip lengths, label and note are always kept. **Reset to generated** gives the wires back to generation. The same tab draws wires of your own (**New wire**: a connector and pin at each end; Generate keeps them, and you can move their ends or delete them), allows several wires on one pin (the design rule *Several wires on one pin* names them) and twists or shields selected wires together (**Group**: twisted pair, shielded pair, quad, coax or overall shield; **Ungroup** takes a group you made apart; **Change group…** changes its kind, wires and shield ends). **Edit all wires…** (also Edit > Edit all wires of the harness…, Ctrl+Shift+B) sets the same gauge, type, colour and length on all wires of the harness, the selected wires or the wires of one signal in one step, and locks them like an edited wire. At the bottom the **Labels** section gives the harness and a cable connector a label for `labels.csv` (a box connector has a **Label** field on its card in the **Devices** tab), and the **Devices** pin table has a **Function** column for your own words about what a pin does. A released harness cannot be edited.

- **New harness** (since 1.5.0): a harness needs no interface. In the **Drawings** area press **New harness…** (or Edit > New harness…, Ctrl+Shift+H) and type a name. The **Connectors** tab beside the drawing adds its cable connectors (a part of the library, optionally plugging into a connector of a device, optionally with pin names of your own), sets the function, termination, contact size and contact of a pin, and deletes a connector that has no wires. Under **Edit connector** you change a connector later (part, gender, keying, name) and under **Pin of a connector** the signal and role of a pin; **Add pin**, **Rename pin** and **Delete pin** change the pin set. Draw its wires in **Edit wire**. Generate leaves such a harness as it is. One that Generate made takes no new connector, but its connectors can be edited (part, gender, keying, the details of a pin): the connector then belongs to you and Generate keeps it, until **Give back to Generate** (its name, pins and contacts keep following the device).

- **Build data** (since 1.7.0): what a technician needs and the design does not give. The strip length of each wire end is in the **Edit wire** tab; **Apply strip lengths to all wires of this harness** fills a whole harness. The contact on a pin of a generated harness is set on the device's pin (**Devices** tab, **Cable contact**); on a harness made by hand it is the **Contact** of the pin form in the **Connectors** tab (**Contact for all pins of this connector** sets a whole connector). The crimp tool belongs to a contact part: click the part in the project tree and use **Crimp tool** and **Set tool** in the Inspector.
- The **Accessories** tab (right of **Connectors**) lists the sleeving, heat shrink, labels and backshells of a harness with ID, kind, part, what they go on, position in words, length of one piece, quantity and note. **Add accessory** takes the next free ID (ACC-001, ...); **Change accessory**, **Delete accessory** and **New accessory** do what they say. It is off for a released harness. Nothing is computed from any of these values and the tool sets none of its own; `harness-design-studio import-build-data` reads them from a table.
- A wire gauge stays **pending** until the derating values exist and the lengths are known (section 11, What an engineer must fill in). The tool never guesses an engineering value.

## 8. Outputs

`outputs/` contains, for every harness: the build workbook (`<ID>_build.xlsx`, see below), wire list, pinouts, BOM, mass and length, continuity and isolation tests, labels, a WireViz-style YAML file and an Excel workbook of the data tables. The PDF and SVG drawings of the harnesses (SVG for the A3 sheets, PDF for A3 and A4) are written only when you ask for them.

For the whole system: block diagram, harness overview, BOM, mating and traceability matrices, DRC report, change log, revision report, and one JSON file with the whole model. Every file carries the tool version and a model hash. The status chip in the top bar and the header of the **Harness** tab show whether the outputs are up to date. Details are in `docs/OUTPUTS.md` in the repository (it is not installed with the app).

The **build workbook** is the file to build a harness from. **Start here** says whether the harness is ready to build and what is missing; **Cut list** lists the wires in cut order, with their colours and strip lengths; **Connectors** has one block per connector, pin by pin, with the contact, the crimp tool and tick columns; **Parts**, **Accessories**, **Labels** and **Tests** follow, with empty columns for the result; **About** names the version and design. A missing value reads *to fill in*. Work on a copy: a changed file in `outputs/` fails the output check.

The build data shows in the tables only where it is used: the wire list gets *Strip A (mm)* and *Strip B (mm)*, the pinouts get *Contact*, a harness with accessories gets `accessories.csv`, and the bill of materials counts the contacts used on pins and the accessory parts (pieces as *ea*, parts with a length as metres *m*).

**Export…** (top bar, File menu or Design menu, Ctrl+E) opens the **Export outputs** window; a project that has harnesses but no folder yet first asks where to save it, with a folder chooser. The window shows the output folder, a tree of harnesses and documents, the check box **Include the PDF drawings** and, once the export has run, the list of files written with **Open**, **Reveal in folder**, a picture of the selected drawing and **Copy selection to folder…**. The export always writes the complete set; the ticks in the tree choose what the list shows and what is copied.

The harness drawings are written only while **Include the PDF drawings** is ticked; it starts ticked when the last export into the folder had them. A problem found by the independent check, or a write error, stays in a notice in the window and nothing is written. The project must be saved to a folder first.

The **Lists** tab (Ctrl+3) shows the same tables on screen for one harness: **Wire list**, **Pinouts**, **BOM**, **Mass and length**, **Test tables**, **Labels** and the **System BOM**. Click a header to sort, type in the filter box, press Ctrl+C to copy the selected cells as text, and **Export table** writes the rows you see as CSV or Excel. **Only pending or not checked** keeps the rows whose value is still open.

Under the lists, **Exported files** (the Outputs area) shows every file of the `outputs` folder: file, document, harness, format, size, time written, SHA-256 and a state. The state is *Matches export*, *Changed since export*, *Missing* or *Not in the export*, compared with the `manifest.json` the export wrote. The checksums are worked out in the background from the files on disk. **Open**, **Reveal in folder** and **Copy to folder…** act on the selected files; **Verify** reads the folder again. Nothing in this list changes a file.

Outputs are checked independently before they are written (every cell of the tables, the pins and signals in the drawings, the PDF texts and the sheets of the workbooks are compared with the design). If that check fails, nothing is written. Export is refused for a project that is read-only or has damaged files. The PDF drawings use the Windows-1252 character set: a character outside it (for example the ohm sign) shows as `?` in the PDF, and the export warns and names each such character; the SVG keeps it. The `outputs` folder is always safe to delete and make again.

## 9. Review, release and revisions

1. Make the design pass: no errors, plans current, every wire sized and measured.
2. **Export…** and review the outputs.
3. Open the **Releases** tab (Revisions on the rail, Ctrl+5), or the **Harness** tab, and pick the harness. **Submit for review** (optional; **Open in review** in the Harness tab), then **Release…**. Type your name and a comment (at least 10 characters). Anything that blocks the release is listed in plain words, and under the form a line says what is still missing for the button to work. The window lists **What this release locks** (for example *18 wires, 198 pins, 9 interfaces, 3 parts, 1 interface type, 5 config files*) as a tree you can open; a config file that is still a placeholder is marked *Pending*. While a configuration file is still marked as a placeholder, the window also asks for a written reason (at least 10 characters); it is kept in the change log and the baseline. Once an engineer has reviewed the values and cleared the mark, no reason is asked. The same holds for the parts: while the harness uses parts that are not approved (or are example data), the window asks for a second written reason.
4. The harness is now **Released** (locked): it, the interfaces it carries and the pins it uses cannot be edited, and neither can the parts, interface types and configuration values it uses (importing parts or applying a profile that would change them is refused). A lock shows on the diagram, in the tree and in the Inspector, and a refused change says why and offers **Start new revision…**. A baseline (frozen snapshot) and a change log entry are stored. Once you have saved a release, **Undo** is off for that step; to change the harness start a new revision.
5. To change it: **New revision…** (Harness tab: **Revise…**). The window says what happens (the next revision becomes a draft, the released one stays as a baseline) and lists what becomes editable and what stays locked because another released harness uses it. The old revision stays available.

Who changed the design last: when the project folder is inside a Git repository, a line under the buttons names the last commit of that repository (who, when, its first line, short id and branch). The tool reads it from the repository's files; it does not run Git, needs no network and keeps no e-mail address. It is the last commit of the whole repository, and changes made since are not shown.

The **Releases** tab shows one timeline of every review, release and new revision, with a filter for one harness and chips for the event and the baseline. Under it, **Compare revision … with …** lists what differs between two revisions, or a revision and the working design, grouped by kind with counts; **Mark on diagram** marks the changed devices and interfaces and **Clear marks** removes the marks. In the differences, each row is tinted by the kind of change, and a line says what the released harness locks.

The **More** menu of the **Harness** tab (Drawings) has **Changes…**, **Change log…** and **Delete harness** (not possible once the harness is released; a generated harness comes back the next time you generate); the same three are in the Design menu and in the context menu of a harness in the Project tree.

Export the outputs again after a release so the build workbook (and the drawings, if you export them) show *released*. The release check looks at the harness (gauges, lengths, open errors) and at whether the configuration files are still marked as placeholders. It cannot judge whether the values are right; that stays a decision for a person.

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
| `harness-design-studio export DIR [--drawings]` | write and verify all outputs; the PDF and SVG drawings of the harnesses only with `--drawings` |
| `harness-design-studio review DIR HARNESS --by NAME` | submit a draft for review |
| `harness-design-studio release DIR HARNESS --by NAME --comment TEXT [--checker NAME] [--accept-placeholders REASON] [--accept-unapproved-parts REASON]` | release (blocked while checks fail, or while values are placeholders or parts are not approved and no reason is given) and re-export |
| `harness-design-studio revise DIR HARNESS --by NAME --comment TEXT` | start a new revision |
| `harness-design-studio diff DIR HARNESS [--from REV] [--to REV]` | what changed since a baseline |
| `harness-design-studio compare OLD NEW` | compare two project folders (for example two Git checkouts); the last line names what is not compared |
| `harness-design-studio log DIR [HARNESS]` | print the change log |
| `harness-design-studio config DIR [--ampacity-csv FILE] [--apply-profile NAME]` | list missing or invalid engineering values; load a current-by-gauge table; fill unset values from a standard profile |
| `harness-design-studio import-parts DIR FILE --approved VALUE ...` | import an approved-parts list; you say what the approval values mean |
| `harness-design-studio import-lengths DIR FILE [--unit mm]` | import routing segment lengths from a table |
| `harness-design-studio import-netlist DIR FILE --device D [--prefix J] [--connector J1=ID] [--part J1=PART] [--signal-map NAME=SIGNAL\|FILE]` | read connector pinouts of a device from a KiCad netlist (.net or .xml); the pins become fixed |
| `harness-design-studio import-build-data DIR FILE [--dry-run]` | import strip lengths, pin contacts, accessories or the crimp tool of parts from a table (CSV, TSV, JSON or XLSX); the kind is told by the column headings; one refused row stops the whole import (exit 1, nothing changed) |
| `harness-design-studio import-pinout DIR FILE --device D [--new-device NAME] [--default-part PART] [--part J1=PART] [--column FIELD=HEADING] [--replace]` | define the connectors and pins of a device from a table (CSV or XLSX), one pin per row |
| `harness-design-studio export-pinout DIR --device D [-o FILE]` | write one device's pinout (the rows of `system/box_pinouts.csv` for it) as CSV on the screen, or to a .csv or .xlsx file |
| `harness-design-studio export-devices DIR FILE --device D [--device D2 ...]` | save devices with their connectors, pinouts, parts and interface types to a device library file (added to when it exists) |
| `harness-design-studio import-devices DIR FILE [--device D] [--list] [--dry-run]` | add devices from a device library file; a taken ID gets the next free one, nothing in the project is replaced |
| `harness-design-studio export-subsystem DIR FILE --device D [--device D2 ...] --name NAME [--description TEXT] [--replace]` | save devices and the connections between them as a subsystem library file (a file that exists is replaced only with `--replace`) |
| `harness-design-studio import-subsystem DIR FILE [--show] [--dry-run]` | add a subsystem from a subsystem library file in one step: the devices (a taken ID gets the next free one) and their connections; all or nothing |

A script that builds everything: `harness-design-studio check DIR`, `harness-design-studio generate DIR`, `harness-design-studio verify DIR`, `harness-design-studio drc DIR`, `harness-design-studio export DIR`. `harness-design-studio templates FOLDER` copies the templates, and `ci/build.sh` in that folder is this script.

## 11. What an engineer must fill in

Some values must come from your program's standards. Until they are filled in, results say so and the affected checks say *not checked*. The list: derating factors and ampacity table (`config/derating.json`), resistivity, service loop, pin gap, mass margin, shield grounding concept and test limits (`config/generation.json`), separation rules (`config/segregation.json`), EMC rules (`config/emc.json`), title block fields (`config/titleblock.json`), part masses and ratings in the library. `harness-design-studio config DIR` prints this list for your project, with what depends on each value; the same list is in `docs/PLACEHOLDERS.md` in the repository (not installed with the app).

In the app, press **Supply value…** on a rule in the **Checks** tab (section 6) to type values in; the window also lets you clear the *placeholder* mark once the values are reviewed.

On the command line, run `harness-design-studio config DIR` to see what is missing and what depends on it, load a current-by-gauge table from a CSV with `--ampacity-csv`, edit the rest in the JSON file (the keys go inside its `values` object), and set `"placeholder": false` once reviewed.

If you work to ECSS-Q-ST-30-11C or ECSS-E-ST-20-07C you can start from the values of those standards with `--apply-profile ecss-q-st-30-11c` or `ecss-e-st-20-07c`: only unset values are filled, each is printed with the requirement it comes from, and the files stay placeholders until you review them (`harness-design-studio config DIR` lists the keys; `docs/CONFIG.md` in the repository describes them and the part ratings the new rules need).

To see the machinery work before you have real values, copy the demo values from the templates (`config-demo-values/`) over a practice project. They are not engineering data, and the files stay marked as placeholders so every result built on them says so. Never release a real design with them.

## 12. Bring in your own data

Every import first shows what it would do. A bad row stops the whole import, so nothing is half applied; only in an interface table is a bad row skipped and the rest imported. Each import is one undo step called *Import n rows*.

| You have | Do |
| --- | --- |
| Interfaces as a table | **File > Import > Import interfaces…** (Ctrl+Shift+I; CSV or XLSX with the columns id, type, from, to and optionally redundancy), or **Paste table text instead…** in the wizard for CSV text |
| An approved-parts list (CSV, TSV, JSON or XLSX; an InvenTree export file works too: its `IPN` column is the part ID) | **File > Import > Import approved parts…**, or `harness-design-studio import-parts`, saying what your approval values mean |
| Segment lengths | **File > Import > Import segment lengths…**, or `harness-design-studio import-lengths`, then generate again |
| A device's pinout as a table (connector, pin, signal ...) | **File > Import > Import device pinout…**, or `harness-design-studio import-pinout`; a new connector needs a library part; a column the project cannot store is named and left out |
| A device's connector pinout in KiCad | export a netlist, then **File > Import > Import KiCad netlist…**, or `harness-design-studio import-netlist`; the pins become fixed |
| A current-by-gauge table | **File > Import > Import engineering values: ampacity table…**, or `harness-design-studio config DIR --ampacity-csv FILE` |
| Strip lengths, pin contacts, accessories or crimp tools as a table | `harness-design-studio import-build-data` (command line only; templates `strip-lengths.csv`, `pin-contacts.csv`, `accessories.csv`) |

The six imports above the last row open the same **Import data** wizard, in four steps: **1 Choose what and which file** (the six kinds are *Interfaces*, *Approved parts*, *Segment lengths*, *Engineering values: ampacity table*, *Device pinout* and *KiCad netlist*), **2 Match the columns and check the first rows** (a live preview shows the rows), **3 Conflicts and placeholders** (every row with its reason, and what stays pending afterwards) and **4 Import**. A file of more than 1,500 rows is read in the background with a progress line and **Cancel**. The same imports are in the Project tab: press Enter on an entry under **Imports**.

The build data (last row) has no window: it is read with the command line (section 10). Example files for every one of these are in the templates folder (`harness-design-studio templates FOLDER`).

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
| Ctrl+Shift+O | open the library window (after 1.7.0) |
| Ctrl+Q | quit |
| Ctrl+K | command palette (it floats over the window; Esc or a click elsewhere closes it): type a command, an ID or a name; every command of the menus is in it |
| Ctrl+G, F5, Ctrl+E | generate harnesses, run the checks, export |
| Ctrl+I | new interface |
| Ctrl+1 to Ctrl+6 | the tabs Diagram, Harness, Lists, Checks, Releases, Devices |
| Ctrl+7, Ctrl+, | Home, Settings |
| Ctrl+Shift+T, Ctrl+Shift+J | the Interface table and the Device list (left panel) |
| Ctrl+Shift+M | show or hide the Problems panel |
| Ctrl+Shift+H | new harness by hand (the Connectors tab opens) |
| Ctrl+Shift+B | edit all wires of the harness (the same gauge, type, colour and length on many wires) |
| Ctrl+Shift+N | add a device (asks for its name first; then the Devices tab opens) |
| F6, Shift+F6 | next and previous panel (diagram, project panel, inspector) |
| Ctrl+Z, Ctrl+Y or Ctrl+Shift+Z | undo, redo (the menu names the step, for example *Undo Move PDU2*) |
| Ctrl+=, Ctrl+-, Ctrl+0 | zoom in, zoom out, real size (100 %) |
| F, Shift+F | fit the whole diagram, zoom to the selection (when the diagram has the keyboard focus) |
| Ctrl+wheel | zoom at the pointer; the wheel alone scrolls (Shift+wheel sideways); middle button or Space and drag pan |
| Ctrl+A, Ctrl+D, Ctrl+F | select everything, duplicate the selected devices, find in the diagram (in the diagram) |
| Ctrl+Shift+L | arrange the diagram |
| C, Esc | start the Connect tool, back to Select (Esc also clears the selection) |
| Tab, Enter or Space | move between devices and links; Space selects, Enter also shows the item in the Harness tab |
| Shift+click, Ctrl+click, drag on the background | add to the selection, take out of it, rubber band (the Project tree takes Shift and Ctrl too: Shift+arrows select several devices or interfaces without the mouse) |
| Shift+arrows | move the selected devices |
| Delete | delete the selected items (after showing what it affects; only in the diagram, the Interface table and the Project tree) |
| Ctrl+C, Ctrl+Shift+C in a table | copy the selected cells as text, with the header row |
| Enter or F2, Esc, Ctrl+V in a table | edit the cell, keep the old text, paste a block of cells |
| `/` in the project tree | go to the filter; Enter selects, Ctrl+Enter or double-click opens |
| Ctrl+F in Checks or Lists | filter the rules or the rows |
| F1 | this guide |

Every command is in a menu. The keys above are shown next to the items, and the tooltip of a button names its key. **Settings > Keyboard shortcuts** lists every key of the window and can be filtered. Tab visits every device and link in the diagram, so use **F6** to leave it.

| Menu | Item | What it does |
| --- | --- | --- |
| File | New project… (Ctrl+N) | one window: an empty folder, a name, and optionally an example |
| File | New project from an example… | the same window with the first example ticked |
| File | Open project… (Ctrl+O) | opens a project folder |
| File | Open the sample project | opens the built-in sample (example data); **Save as…** keeps your changes |
| File | Save (Ctrl+S), Save as… (Ctrl+Shift+S) | saves the project; save as writes a copy to a new folder |
| File | Import | Import interfaces… (Ctrl+Shift+I), Import approved parts…, Import segment lengths…, Import engineering values: ampacity table…, Import device pinout…, Import KiCad netlist…: the import wizard (section 12) |
| File | Export… (Ctrl+E) | the Export outputs window (section 8) |
| File | Library… (Ctrl+Shift+O), Library folder… | the library window and the choice of the library folder (section 4, "The library") |
| File | Quit (Ctrl+Q) | closes the app |
| Edit | Undo, Redo | steps back and forward through your changes |
| Edit | Select all, Duplicate, Delete, Find in diagram | work on the selection; Duplicate copies a device with its connectors but not its links; Delete shows what else goes with it |
| Edit | Create redundant copy | builds a redundant (backup) copy of the selected device and its chain |
| Edit | New interface… (Ctrl+I), Link connectors… (Ctrl+Shift+K), Connect (C) | a form for a new interface; the window that joins two connectors pin by pin; the Connect tool, which opens that window after two devices |
| Edit | Align, Space evenly | line up or space out the selected devices |
| Edit | Add zone… | adds a lane to the diagram; asks for its name |
| Edit | Wire colours... | chooses the wire colour of each signal (section 7) |
| Edit | Add device | one item for each kind of device (computer, power unit, wheel ...), and Device… (Ctrl+Shift+N); **New harness…** (Ctrl+Shift+H) is an item of the Edit menu |
| Edit | Connect with an interface type… | one item for each interface type (the arrow beside the Connect button lists the same); then click two devices |
| Edit | Selected connection | Edit the pairs…, Rename…, Create harness, Show the harness, Delete connection: for the connection picked in the Project tab or on the diagram |
| View | Show side panels (Simple workspace only) | opens or closes the Project tab and the Inspector together (the **Show panels** button of the top bar) |
| View | Simple, Full | the workspace (section 5): a project opens on **Next step** and less is on screen, or it opens where it opened before and everything is there |
| View | Show problem notices | shows or hides the Problems count, status chip, badges and *out of date* banner; on in Full, off in Simple |
| View | Guided, Expert | the two modes of section 5 |
| View | Theme | Follow the system (the default), Light or Dark (also under **Settings > Appearance**) |
| View | Show overview map, Show legend, Snap to grid | overlays and the grid |
| View | Reduce motion | turns off the fades and slides of menus, lists and tooltips |
| View | Show connectors on connections | draws the connector and its paired pins at both ends of every connection (always in Expert mode) |
| View | Show all link labels | shows the values (such as `28 V · 5 A`) on every link, not only on the selected one |
| View | Interface size | makes text and controls larger: 100, 125, 150 or 200 %; the first size follows your screen |
| View | Zoom in, Zoom out, Fit all, Zoom to 100 %, Zoom to selection | zooms the diagram (Ctrl+=, Ctrl+-, F, Ctrl+0, Shift+F) |
| View | Arrange diagram | tidies the devices inside their lanes; Undo restores them |
| View | Project, Inspector, Problems panel (Ctrl+Shift+M) | shows or hides each panel |
| View | Reset layout | puts the panels back where they were at the start |
| Design | Generate harnesses (Ctrl+G) | builds the harness plans after a preview |
| Design | Run checks (F5), Cancel the running check | runs the design rules now |
| Design | Check my connections | reviews every connection (four design rules) and changes nothing; the Problems panel shows only the connections |
| Design | Export… (Ctrl+E) | the Export outputs window |
| Design | Submit harness for review…, Release harness…, Start new revision… | change control for the harness in view (section 9) |
| Design | Show changes of harness…, Show change log of harness…, Delete harness… | the harness in view: what changed since a baseline, who changed what, delete a draft |
| Design | Engineering values… | the window where you type the values the rules wait for (section 6) |
| Go | Go to Diagram, Harness, Lists, Checks, Releases, Devices (Ctrl+1 to Ctrl+6) | shows that tab |
| Go | Go to Home (Ctrl+7), Go to Settings (Ctrl+,) | opens that page |
| Go | Go to Interface table (Ctrl+Shift+T), Go to Device list (Ctrl+Shift+J) | opens the Interfaces or Device list tab of the left panel with the keyboard in the table |
| Go | Next panel, Previous panel (F6, Shift+F6) | moves the keyboard focus between the panels |
| Help | User guide (F1) | opens this guide |
| Help | Search and commands (Ctrl+K) | the command palette |
| Help | Replay the tour | shows the short first-run tour again |
| Help | Glossary | the list of words the tool uses |
| Help | Show project problems | lists what could not be loaded, for a project with problems |
| Help | About | opens **Settings > About**: the version, the Python, Qt and PySide6 versions and where your settings are kept |

The **Show** list at the right end of the Model tab bar (**More > Show only** in the Simple workspace) fades everything except one signal class (power, data, analog, RF ...), one connector or one bundle (harness), so a large diagram can be read one piece at a time; choose *All interfaces* to see everything again. It changes nothing in the project. The **Interfaces** and **Device list** tabs of the left panel list every interface and device as text, and every control has an accessible name, so they are meant for a screen reader; nobody has tested the tool with a screen reader yet.

## 15. Glossary

- **Harness**: a bundle of wires with connectors that carries signals between devices.
- **Interface**: a logical connection between two devices, for example RS-422 from the computer to a wheel.
- **Connection**: two connectors joined pin by pin, with the pairs proposed from the signal names on the pins and confirmed by you (after 1.7.0). It needs no interface type.
- **Pin role**: what a pin is for: Power, Return, Ground, Signal, Shield or Spare. *Return* (`RTN`) is the line the current comes back on.
- **Nominal / redundant**: the main chain and its backup. They never share a connector or harness.
- **Auto-filled**: a connector the tool chose; unconfirmed until a person looks at it.
- **Pending**: a value nobody has entered yet, for example a wire gauge that waits for a derating value. Shown with a dotted chip, never as a number.
- **Not checked**: a design rule that could not run because a value it needs is missing. It is not a pass.
- **Out of date**: the harness plans or the exported files no longer match the design; generate or export again.
- **Baseline**: a frozen snapshot made when a harness is released.
- **Waiver**: a recorded decision to accept a warning, with a reason.
- **Placeholder**: a value nobody has entered yet; the tool never invents one.
- **Model hash**: a fingerprint of the design; every output carries it.
- **Build workbook**: the Excel file `<ID>_build.xlsx` of a harness, to build it from: what is ready, the cut list, one block per connector, parts, accessories, labels and tests.
- **Cut list**: the sheet that lists the wires in the order they are cut, with their strip lengths and a column to tick.
- **Accessory**: sleeving, heat shrink, a label or a backshell on a harness, with where it goes in words, a length and a quantity (since 1.7.0).
- **Contact part** and **crimp tool**: the library part (category contact) a pin uses, and the tool or setting for crimping it, in your words. The tool does not check either.
- **Fixed pin**: a pin whose signal the device itself defines (imported from KiCad); generation never moves it.
