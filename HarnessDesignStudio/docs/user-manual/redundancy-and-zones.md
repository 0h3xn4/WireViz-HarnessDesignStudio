# Redundancy and zones

This page shows how to add a backup (redundant) chain to a design, what the tool does about links between the main and the backup chain, and how zones (lanes) work.

## Before you start

- You have a project with devices and links ([draw the design](draw-the-design.md)). The examples below use `first-steps`.
- **Nominal** is the main chain of devices. **Redundant** is its backup. The tool keeps them apart: a nominal and a redundant chain never share a connector or a harness, so one failure cannot take out both ([glossary](../GLOSSARY.md)).
- A **zone** is a place on the spacecraft, for example a panel or a compartment. In the diagram a zone is a vertical **lane** ([glossary](../GLOSSARY.md)).

The steps below use the app. As a Systems engineer press **Model** in the rail to reach the diagram, and **Show panels** in the top bar when a step needs the **Inspector** or the **Project** tab ([draw the design](draw-the-design.md#before-you-start)). They are described from the program's texts and code and have not been run on a screen (GUI, not run). The numbers and messages below were reproduced with the same program code and the command line.

## Say how many: the number of devices (after 1.7.0)

The simplest way to ask for redundancy is to say how many of a device the design has. In the **Devices** tab choose the device, raise **Number of these devices** (for example from 1 to 2) and press **Add copies**; in the **Add device** window the same field makes the device in that number at once. With 2 the program adds the twin `PCDU1-R` that the next section describes; with 3 it adds `PCDU1-3` as well, and so on, each with the connectors of the device and the links of the device mirrored where the other end has a free connector. It is one undo step. [Use the library](use-the-library.md#4-a-number-of-the-same-device) has the details. The rest of this page is the older way, a copy made on the redundant chain, which stays and gives the same result for the second device.

## 1. Make a redundant copy of a device

1. Select a device, for example `PCDU1`.
2. Press **Create redundant copy** above the diagram (or in the **Inspector**), or choose **Edit > Create redundant copy**. (As a Systems engineer the button is under **More** above the diagram.) (The button is greyed out for a device that already is a redundant copy or already has one.)
3. A twin appears in the next lane: `PCDU1-R`, named "Power unit 1 (redundant)", with the same connectors (`PCDU1-R-J01`, ...). The tool then copies the links of the device (their IDs end in `-R`).

A copied link needs a free connector of the right type at the other end. In `first-steps`, `RW1` has one power connector and it is used, so copying `PCDU1` first copies no link. A message says so ("1 interface(s) could not be mirrored (no free connector): IF-001"). Copy `RW1` next: `IF-001-R` then joins `PCDU1-R` and `RW1-R`.

If the device at the other end has no twin yet but has a free connector, the copied link goes to the **nominal** device at the other end. That is a link between the two chains. The tool flags it as a warning (see below).

## 2. Fix a link between the two chains

This is the usual result when you copy several devices one after the other. With `first-steps`, copy `PCDU1`, then `RW1`, then `OBC1`. The **Problems** tab (right panel; as a Systems engineer press **Show panels** first) then shows:

```
IF-002-R connects the nominal chain to the redundant chain
```

The card explains that one failure could affect both chains. It has a **Show** button, a **Waive…** button and a fix button called **Connect to a redundant copy of OBC1**.

- Press the fix button. The nominal end moves onto the twin (`OBC1-R`). Both ends are then on the redundant chain, and the warning goes.
- Or press **Waive…** and write a reason of at least 10 characters if the link between the chains is wanted. The reason stays in the report.

After the fix, the project has six devices and four links. Save with Ctrl+S. Then on the command line:

```
harness-design-studio generate red2
harness-design-studio drc red2
```

```
4 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
4 interfaces and 12 wires checked: 0 error(s)
```

(`red2` is whatever folder you made with `harness-design-studio new red2 --template first-steps`. The second line comes from `harness-design-studio generate`; `harness-design-studio drc` prints the whole design rule report.) The design rule report no longer lists a `cross-strap` warning.

You can also draw a link by hand: under **Edit > Connect with an interface type…** (or the arrow beside **Connect**), pick the type, click `OBC1-R`, then `RW1-R`. The tool sets the **Chain** of that link to *redundant* by itself, because both ends are redundant.

## 3. Zones and lanes

- A device's zone is **set by where you place it**: drag the device into a lane. The field **Zone (set by where you place the device)** in the **Inspector** is read-only.
- **Edit > Add zone…** asks for a **Zone name** and adds a lane. A name that exists already is refused.
- A blank project and `first-steps` have the lanes `panel-A` and `panel-B`.
- Zones matter when harnesses are made. The default groups links by pair of device connectors. The setting `per_zone_pair` groups links between the same two zones. See [generate harnesses](generate-harnesses.md#how-links-become-harnesses).

## Common mistakes

- **A "cross-strap" warning you did not expect.** You copied one device and not its neighbour. Copy both, then use the fix button.
- **The copy button is greyed out.** The device is already a redundant copy, or already has one (`PCDU1-R` exists), or the project is read-only. See [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).
- **A harness mixes the chains.** It cannot: the default rules forbid it (`forbid_nominal_with_redundant` in `config/segregation.json`). See [`CONFIG.md`](../CONFIG.md).

Next: [use the library](use-the-library.md), [generate harnesses](generate-harnesses.md), [read and fix problems](read-and-fix-problems.md)
