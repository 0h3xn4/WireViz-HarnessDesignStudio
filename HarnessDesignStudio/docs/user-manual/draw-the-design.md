# Draw the design

This page shows how to start a project and draw its units and the interfaces between them in the app, the part of the work that only you can do.

## Contents

- [Before you start](#before-you-start)
- [1. Start a project](#1-start-a-project)
- [2. Add units](#2-add-units)
- [3. Connect two units](#3-connect-two-units)
- [4. Set the current and voltage of a link](#4-set-the-current-and-voltage-of-a-link)
- [5. Guided or Expert](#5-guided-or-expert)
- [6. Tidy the diagram and find things](#6-tidy-the-diagram-and-find-things)
- [7. Change your mind: delete, undo, save](#7-change-your-mind-delete-undo-save)
- [Common mistakes](#common-mistakes)

## Before you start

- The tool is installed ([`INSTALL.md`](../INSTALL.md)). Start **Harness Design Studio** from the application menu. From a source install, run `harness-design-studio-gui`.
- You know what a **unit** (a box with connectors on it, such as the on-board computer) and an **interface** (one connection between two units, such as a data link) are. If not, read [`CONCEPTS.md`](../CONCEPTS.md) first (ten minutes) or look the word up in the [glossary](../GLOSSARY.md).
- Here you draw units and interfaces, and the tool makes the connectors, pins and wires from them ([generate harnesses](generate-harnesses.md)). To make a harness yourself, with no interfaces, see [build a harness by hand](build-a-harness-by-hand.md).

Steps in the app are described from the program's own texts and code. They have not been run on a screen (GUI, not run).

## 1. Start a project

You can start in the app or on the command line. The result is the same: a folder of small JSON files, which is your project.

**In the app**

1. Choose **File > New project from an example…** and pick an example (the list is the same as `harness-design-studio new --list`). Or choose **File > New project…** for an empty project.
2. Choose an **empty folder**, then type a project name.
3. To open a project you made earlier: **File > Open project…** (Ctrl+O), or press **Open** beside it in the **Recent projects** of the **Home** page (Ctrl+7).

**Home** has the same starts as buttons (**New project…**, **Open project…**, **New from an example…**, **Open the sample project**), and **Try the flatsat example** opens a copy of that example in your Documents folder.

**On the command line**

```
harness-design-studio new --list
harness-design-studio new wheel-link --template first-steps --name "Wheel link"
```

```
Project 'Wheel link' created in wheel-link (3 units, 2 interfaces).
Next: harness-design-studio validate wheel-link   or open it in the app (File > Open project).
```

Then open the `wheel-link` folder with **File > Open project…**. You cannot break the example: it is your own copy.

| Example | Use it for |
| --- | --- |
| `blank` | A real design. Starter parts and 17 interface types, no units. |
| `first-steps` | Learning. Three units, a power link and an RS-422 link (a data link between two units). |
| `small-satellite` | Seeing a realistic system with redundancy. 14 units. |
| `minimal-satellite`, `flatsat` | A small spacecraft and a complete test bench. **Not in the 0.1.0 packages** (see the [changelog](../../CHANGELOG.md)). `harness-design-studio new --list` shows five examples on 1.0.0 and three on 0.1.0. |

The app also has **File > Open the sample project**. That is example data. Save a copy (**Save a copy…** in the banner) before you change anything.

## 2. Add units

1. Choose **Edit > Add unit** and pick one of the kinds: **Computer**, **Power unit**, **Actuator (wheel)**, **Sensor (star tracker)**, **Payload**, **Transceiver**, **Pyro unit**, **Computer (many interfaces)**, **Power distribution unit**, **Battery**, **Solar array**, **Sun sensor**, **Magnetorquer** or **Heater panel**. **Add > Unit…** in the **Project** tab on the left shows the same list, and so does the command palette (Ctrl+K, type "add").
2. The unit appears at once. No window opens. The ID and the name are given automatically, for example `PCDU1` and "Power unit 1", `OBC1` and "Computer 1", `RW1` and "Actuator (wheel) 1".
3. To change the ID or the name, select the unit and edit **ID** or **Name** in the **Inspector** on the right.
4. Drag the unit to move it. A unit cannot be dragged past the top or left edge of the diagram, and the diagram grows to the right and downwards to hold a unit you place far out (switching to **Expert** grows it too). The lane it sits in is its **zone** (a panel or compartment of the spacecraft). A blank project has two lanes, `panel-A` and `panel-B`. **Edit > Add zone…** adds a lane: type a zone name.

Each unit comes with connectors. You do not need to look at them in Guided mode.

## 3. Connect two units

1. Open the arrow beside the **Connect** button above the diagram and pick an interface type, for example **RS-422** or **Primary power**; the type in use has a tick. (**Edit > Connect with** has the same list; the key **C** switches the connect tool on with the last type. **Ctrl+I** or **Add > Interface…** opens a form where you pick the type and both units.)
2. Click the first unit, then the second unit. Units that cannot take that type are greyed out, with the reason next to them.
3. A link is drawn. It gets an ID (`IF-001`) and a name such as "Primary power PCDU1 to RW1". The tool picks the connectors and marks them **auto-filled** until you confirm them (see [read and fix problems](read-and-fix-problems.md)).
4. The connect tool stays on, so you can draw more links. Press **Esc**, or the **Select** button above the diagram, to stop. While the connect tool is on, dragging a unit moves nothing (it is not a move tool); if the first unit you clicked is deleted or its link is undone, the tool forgets that first click.

To make a backup chain, select a unit and press **Create redundant copy** (above the diagram, in the **Inspector** or in the **Edit** menu). The tool adds the twin unit (`PCDU1-R`) and copies its links to it. See [redundancy and zones](redundancy-and-zones.md).

## 4. Set the current and voltage of a link

1. Click the link. The **Inspector** shows its fields.
2. Fill in **Max current (A)** and, if you know it, **Voltage (V)**. Use a plain number such as `2` or `2.5`; it must be above 0 (a value of 0 or less, or an impossible number, is refused). The field shows the stored number exactly (`12.3456789`, not `12.3457`), so leaving a field without typing never changes the value.
3. **Chain (nominal / redundant)** says whether the link belongs to the main chain or to the backup.

Without a current on a power link, the wire gauge (the thickness of the wire) stays *pending*. The tool never guesses it.

## 5. Guided or Expert

Use the **Guided** and **Expert** buttons in the top bar (also in the **View** menu and under **Settings > Editing**).

- **Guided** (the default): you work with units and links. The tool chooses connectors and pins.
- **Expert**: you also see each connector and can choose the exact connector at each end of a link.

Switching never changes your data.

## 6. Tidy the diagram and find things

- **View > Arrange diagram** puts the units in order and gives each one room. **Undo** restores the old positions.
- **Click a unit or a link** and only its links stay in full colour. Press **Esc** or click the empty background to see everything again.
- The **Show** list at the right end of the Model tab bar fades everything except one signal class, one connector or one bundle (a harness).
- **Ctrl+K** (**Search**) lets you type a command or an ID and jump to it.
- Zoom with **Ctrl+=** and **Ctrl+-**, or **Ctrl+wheel** at the pointer. **F** fits the whole diagram, **Shift+F** zooms to the selection and **Ctrl+0** shows 100 %. **View > Show all link labels** (or **Settings > Editing > Show every link label**) shows voltages and currents on every link in a dense diagram.
- **Shift+click**, **Ctrl+click** or a drag on the background select several items; **Ctrl+A** selects all. **Ctrl+F** finds a unit or link and marks every match. **Edit > Align**, **Space evenly** and **Duplicate** (Ctrl+D) work on the selection.
- A badge on a unit or link counts its problems, warnings and values still to enter, and a lock with *W001 A* shows what a released harness holds.
- The **Project** tab on the left lists every unit and link as a tree, and the **Interfaces** tab beside it (Ctrl+Shift+T) lists every link as a table you can edit, and the **Units** tab (Ctrl+Shift+J) every unit. The tables work like a spreadsheet: Enter edits a cell, Esc cancels, **Ctrl+V pastes a block copied from Excel** (one Ctrl+Z undoes the whole paste), and an edit made with several rows selected applies to all of them; a right-click on the header chooses the columns. Paste fills the rows that exist; a new unit is added with **Add** and a new link with **Ctrl+I**. Shift+arrows in the tree select several units or links at once.

## 7. Change your mind: delete, undo, save

- **Delete** removes the selected unit or link. A window first lists what else it removes (the links and connectors of the unit). A unit that a manual harness plugs into cannot be deleted until that harness is changed. **Undo** (Ctrl+Z) brings it back; **Redo** is Ctrl+Y. When a step cannot be undone the Undo button is off and its tooltip says why: after you **save** a release or a new revision it reads "This release was saved; it cannot be undone. Use 'Revise' to change the harness." A redo that is no longer possible gives a plain message instead of failing silently.
- **Ctrl+S** saves. The status bar says "All changes saved" or "Unsaved changes (autosaved to the recovery journal)". For the sample, or a project that has no folder yet, nothing is autosaved, and it says "Unsaved changes (not kept anywhere until you save)". If the app closes before you save, it offers to **Restore** your last edits at the next start. If the project files changed after those edits were made (for example by a Git pull), the window says so before it restores: restoring brings back the old state of everything and saving then replaces the newer files. A failed restore says so ("The unsaved changes could not be restored. They are still in the recovery folder."). **Discard changes** when you close removes the recovery journal. A project that is open read-only stays read-only after a restore or a reload.
- If the project changed on disk (for a Git pull, say), the window offers **Reload** or **Keep my version**, and asks once per state of the files. A project that was deleted, or lost its `project.json`, while it was open is reported when you come back to the window.
- A message at the bottom (a toast) that repeats with a new **Undo** replaces the old one. Save, Save As and autosave say in plain words when the project holds text that cannot be written to a file (an unpaired special character): "Nothing was saved: the project contains text that cannot be written to a file ...". Retype that text and save again.
- **File > Save as…** (Ctrl+Shift+S) saves a copy in another empty folder.

## Common mistakes

- **A unit cannot be connected.** It is greyed out because it has no free connector of that type. The reason is written next to it. Pick another unit, or add a unit that has the connector.
- **Nothing happens when you click a unit.** The connect tool is still on and waits for the second end. Press **Esc**.
- **An interface name with a line break.** A name is one line; typing a line break in the table gives "A name is one line. Remove the line break." A project name that is too long or has control characters is explained in the same way.
- **A long ID ends in "...".** Long unit IDs and connector names are shortened on the diagram with an ellipsis; select the unit to read the full text in the **Inspector**.
- **"Read-only" banner.** The project was saved by a newer tool, it is open in another window, or its folder cannot be locked for editing (read-only media). See [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).
- **The folder is refused.** `harness-design-studio new` and **New project…** need a folder that does not exist yet or is empty. Nothing is ever overwritten.

Next: [generate the harnesses](generate-harnesses.md), [redundancy and zones](redundancy-and-zones.md)
