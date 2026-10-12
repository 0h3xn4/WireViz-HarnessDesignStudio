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

- The tool is installed ([`INSTALL.md`](../INSTALL.md)). Start **Harness Design Studio** from the application menu. From a source install, run `harness-gui`.
- You know what a **unit** (a box with connectors on it, such as the on-board computer) and an **interface** (one connection between two units, such as a data link) are. If not, read [`CONCEPTS.md`](../CONCEPTS.md) first (ten minutes) or look the word up in the [glossary](../GLOSSARY.md).
- You do **not** draw wires, pins or connectors. The tool makes them from your units and interfaces ([generate harnesses](generate-harnesses.md)).

Steps in the app are described from the program's own texts and code. They have not been run on a screen (GUI, not run).

## 1. Start a project

You can start in the app or on the command line. The result is the same: a folder of small JSON files, which is your project.

**In the app**

1. Choose **File > New project from an example…** and pick an example (the list is the same as `harness new --list`). Or choose **File > New project…** for an empty project.
2. Choose an **empty folder**, then type a project name.
3. To open a project you made earlier: **File > Open project…** (Ctrl+O).

**On the command line**

```
harness new --list
harness new wheel-link --template first-steps --name "Wheel link"
```

```
Project 'Wheel link' created in wheel-link (3 units, 2 interfaces).
Next: harness validate wheel-link   or open it in the app (File > Open project).
```

Then open the `wheel-link` folder with **File > Open project…**. You cannot break the example: it is your own copy.

| Example | Use it for |
| --- | --- |
| `blank` | A real design. Starter parts and 17 interface types, no units. |
| `first-steps` | Learning. Three units, a power link and an RS-422 link (a data link between two units). |
| `small-satellite` | Seeing a realistic system with redundancy. 14 units. |
| `minimal-satellite`, `flatsat` | A small spacecraft and a complete test bench. **Not in the 0.1.0 packages** (see the [changelog](../../CHANGELOG.md)). `harness new --list` shows five examples on 1.0.0 and three on 0.1.0. |

The app also has **File > Open the sample project**. That is example data. Save a copy (**Save a copy…** in the banner) before you change anything.

## 2. Add units

1. In the palette on the left, under **Add a unit**, press one of the buttons: **＋ Computer**, **＋ Power unit**, **＋ Actuator (wheel)**, **＋ Sensor (star tracker)**, **＋ Payload**, **＋ Transceiver**, **＋ Pyro unit**, **＋ Computer (many interfaces)**, **＋ Power distribution unit**, **＋ Battery**, **＋ Solar array**, **＋ Sun sensor**, **＋ Magnetorquer** or **＋ Heater panel**. Long names are shortened on the button; the tooltip has the full name. **Edit > Add unit** has the same list.
2. The unit appears at once. No window opens. The ID and the name are given automatically, for example `PCDU1` and "Power unit 1", `OBC1` and "Computer 1", `RW1` and "Actuator (wheel) 1".
3. To change the ID or the name, select the unit and edit **ID** or **Name** in **Properties** on the right.
4. Drag the unit to move it. The lane it sits in is its **zone** (a panel or compartment of the spacecraft). A blank project has two lanes, `panel-A` and `panel-B`. **Edit > Add zone…** adds a lane: type a zone name.

Each unit comes with connectors. You do not need to look at them in Guided mode.

## 3. Connect two units

1. Under **Connect with** in the palette, press an interface type, for example **RS-422** or **Primary power**. (**Edit > Connect with** has the same list; the key **C** switches the connect tool on.)
2. Click the first unit, then the second unit. Units that cannot take that type are greyed out, with the reason next to them.
3. A link is drawn. It gets an ID (`IF-001`) and a name such as "Primary power PCDU1 to RW1". The tool picks the connectors and marks them **auto-filled** until you confirm them (see [read and fix problems](read-and-fix-problems.md)).
4. The connect tool stays on, so you can draw more links. Press **Esc**, or the **Select** button above the diagram, to stop.

To make a backup chain, select a unit and press **Create redundant copy** (in **Properties** or in the **Edit** menu). The tool adds the twin unit (`PCDU1-R`) and copies its links to it. See [redundancy and zones](redundancy-and-zones.md).

## 4. Set the current and voltage of a link

1. Click the link. **Properties** shows its fields.
2. Fill in **Max current (A)** and, if you know it, **Voltage (V)**. Use a plain number such as `2` or `2.5`.
3. **Chain (nominal / redundant)** says whether the link belongs to the main chain or to the backup.

Without a current on a power link, the wire gauge (the thickness of the wire) stays *pending*. The tool never guesses it.

## 5. Guided or Expert

Use the toolbar buttons **Guided** and **Expert** (also in the **View** menu).

- **Guided** (the default): you work with units and links. The tool chooses connectors and pins.
- **Expert**: you also see each connector and can choose the exact connector at each end of a link.

Switching never changes your data.

## 6. Tidy the diagram and find things

- **View > Arrange diagram** puts the units in order and gives each one room. **Undo** restores the old positions.
- **Click a unit or a link** and only its links stay in full colour. Press **Esc** or click the empty background to see everything again.
- The **Show** list in the toolbar fades everything except one signal class, one connector or one bundle (a harness).
- **Ctrl+K** (**Search / commands**) lets you type a command or an ID and jump to it.
- Zoom with **Ctrl+=**, **Ctrl+-** and **Ctrl+0** (fit). **View > Show all link labels** shows voltages and currents on every link in a dense diagram.
- The bottom tabs **Interface table** and **Outline** list every link and unit as text. They also work with a screen reader.

## 7. Change your mind: delete, undo, save

- **Delete** removes the selected unit or link. A window first lists what else it removes (the links and connectors of the unit). **Undo** (Ctrl+Z) brings it back; **Redo** is Ctrl+Y.
- **Ctrl+S** saves. The status bar says "All changes saved" or "Unsaved changes (autosaved to the recovery journal)". For the sample, or a project that has no folder yet, nothing is autosaved, and it says "Unsaved changes (not kept anywhere until you save)". If the app closes before you save, it offers to **Restore** your last edits at the next start.
- **File > Save as…** (Ctrl+Shift+S) saves a copy in another empty folder.

## Common mistakes

- **A unit cannot be connected.** It is greyed out because it has no free connector of that type. The reason is written next to it. Pick another unit, or add a unit that has the connector.
- **Nothing happens when you click a unit.** The connect tool is still on and waits for the second end. Press **Esc**.
- **"Read-only" banner.** The project was saved by a newer tool, or it is open in another window. See [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).
- **The folder is refused.** `harness new` and **New project…** need a folder that does not exist yet or is empty. Nothing is ever overwritten.

Next: [generate the harnesses](generate-harnesses.md), [redundancy and zones](redundancy-and-zones.md)
