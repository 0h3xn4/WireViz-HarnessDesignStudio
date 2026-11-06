# Make a block diagram in five minutes

This page is for the person who wants a clear block diagram of a set-up (a test bench, a flatsat, a meeting sketch) and has no use for the checks, the harness plans and the paperwork that the rest of the tool offers. It uses **Quick mode**, a short layout you can switch on in any role, and ends with a picture you can paste into a slide or a document.

## Contents

- [Before you start](#before-you-start)
- [The five steps](#the-five-steps)
- [What Quick mode hides](#what-quick-mode-hides)
- [How to leave Quick mode](#how-to-leave-quick-mode)
- [Go on from the picture](#go-on-from-the-picture)
- [Common mistakes](#common-mistakes)

## Before you start

- The tool is installed ([`INSTALL.md`](../INSTALL.md)) and started. You do not need to know what a harness, a rule check or a revision is.
- The five steps were run one after the other in the real window, started without a screen (offscreen), and the names below are the ones it showed. Nobody has watched them on a real display yet (GUI, not run on a screen).

## The five steps

1. **Turn on Quick mode.** Press the **Role** button in the top bar and choose **Quick mode** (below the three roles). The rail on the left shrinks to **Home**, **Model** and **Settings**, and the top bar keeps your project name, Undo and Redo, the **Role** button, a **Quick** marker, the search and one button, **Export diagram**. It works whatever role you have; you keep your role.
2. **New project.** Choose **File > New project…** (Ctrl+N), choose an empty folder and type a name. The diagram opens.
3. **Add device.** In a new project press **Add a device** in the middle of the empty diagram. Later, press **Add device** (the button above the diagram in the Systems engineer role), or in any role choose **Edit > Add device > Device…** (Ctrl+Shift+N). The window asks for **a name** and, if you want, **a kind** (**Kind (optional)**: a kind gives the device the connectors that kind usually has; *No particular kind* gives one starter connector). Press **Add**. Nothing else is asked: the tool makes the ID (`Power supply` becomes `POWER1`), puts the device in a free place and gives it a connector so you can connect it at once. Add the second device the same way.
4. **Connect.** Press on the port of a device (the small square on its edge) and drag the cable to the other device, or press **Connect** (or the key C), click the first device and then the second. The two are joined at once, with no window. If you let the cable go on empty ground it stays as a loose end that you can pick up again; **Esc** drops it ([Connect two connectors](connect-two-connectors.md#pick-up-a-cable-and-plug-it-in)). A message says, for example, *Connected FLIGHT1 and POWER1. 9 pin pairs, matched by pin number.*; **Undo** takes it back, **Edit pairs** opens the window *Link connectors* if you want to choose the pins by hand. A device that had no connector got a starter connector in the same step. A connection with no paired pin is fine: the two devices are joined on the diagram all the same.
5. **Export diagram.** Press **Export diagram** in the top bar (or **File > Export diagram…**, or Ctrl+K and *Export diagram*). Choose a file name. The tool writes `<name>.svg`, `<name>.pdf` and `<name>.png` next to each other: the SVG and the PDF are vector pictures, the PNG is for a slide. This needs no project folder, no Generate and no check; it writes nothing into the project. A project with no device says *Nothing to draw yet*.

That is all. To change the picture, move the devices on the diagram, rename a device in the **Devices** tab of the **Model** area, or add and connect more devices, and export again.

## What Quick mode hides

Quick mode changes what the window shows and what it asks. It never changes a project file, the model hash or a file the tool writes; nothing is locked and nothing is deleted.

| Hidden while Quick mode is on | Where it still is |
| --- | --- |
| the rail areas **Next step**, **Checks**, **Drawings**, **Outputs**, **Revisions** and **As-built** | the **Go** and **View** menus, Ctrl+K, and the area you have open stays on the rail until you leave it |
| the top bar buttons **Generate**, **Check**, **Release** and **Export…**, the model hash, the revision and the status chip | **Design** and **File** menus, Ctrl+K, and the keys Ctrl+G, F5 and Ctrl+E |
| the problem notices: the **Problems** count, the badges on the diagram, the *out of date* banner (whatever you chose in **Show problem notices**, which comes back when you leave) | **Run checks** (F5) and the **Checks** area still work |
| the *Checking the design rules* progress in the status bar (the check still runs in the background; one you ask for with Check still shows its progress) and the *N pending* chips of the **Configuration** rows in the project tree | the **Checks** area, which says what is pending, and the tooltip of a **Configuration** row |
| the tour and the question about your role at the first start | **Help > Replay the tour** |
| the long window *Link connectors* when you connect, and the ID, subsystem and connector questions when you add a device | **Edit pairs** in the message after Connect; **Edit > Link connectors…** (Ctrl+Shift+K) opens the window when the project has more than two devices; the **Devices** tab |

The banner of the sample project stays, in a shorter form.

## How to leave Quick mode

Press the **Quick** marker in the top bar, or choose **Quick mode** again in the **Role** button's menu, in **View > Quick mode**, or untick it on the **Settings** page. The layout of your role is back at once, exactly as it was. Quick mode is remembered between sessions, like your role, and is not part of any project.

## Go on from the picture

Everything the other pages describe is still there. To make wire lists, a build workbook and the checks from the same devices, turn Quick mode off and read [Draw the design](draw-the-design.md), [Connect two connectors](connect-two-connectors.md) and [Export the outputs](export-the-outputs.md). The roles are explained in [Choose your role](choose-your-role.md).

## Common mistakes

- **The rail has no Checks.** Quick mode hides it on purpose; open **Go > Go to Checks** or turn Quick mode off.
- **Connect asks which devices.** The project has more than two devices and you pressed Ctrl+Shift+K or the menu entry without choosing two; use the **Connect** tool and click the two devices.
- **Dragging from a port does nothing.** The diagram is zoomed out too far (below about 45 %, devices are drawn as plain boxes with no ports: zoom in, or press **F**), or the Connect tool is on (press **Esc**, or **Select**), or the project is read-only.
- **The picture is smaller than a page.** Export diagram cuts the sheet to the devices, the lane titles, the links and the legend, plus a margin, so a small set-up gives a small picture that fills it. The normal export (`system/block_diagram.svg` and `.pdf` in the outputs folder) keeps its fixed sheet and is not changed.
