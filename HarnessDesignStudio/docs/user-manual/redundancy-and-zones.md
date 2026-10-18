# Redundancy and zones

This page shows how to add a backup (redundant) chain to a design, what the tool does about links between the main and the backup chain, and how zones (lanes) work.

## Before you start

- You have a project with units and links ([draw the design](draw-the-design.md)). The examples below use `first-steps`.
- **Nominal** is the main chain of units. **Redundant** is its backup. The tool keeps them apart: a nominal and a redundant chain never share a connector or a harness, so one failure cannot take out both ([glossary](../GLOSSARY.md)).
- A **zone** is a place on the spacecraft, for example a panel or a compartment. In the diagram a zone is a vertical **lane** ([glossary](../GLOSSARY.md)).

The steps below use the app. They are described from the program's texts and code and have not been run on a screen (GUI, not run). The numbers and messages below were reproduced with the same program code and the command line.

## 1. Make a redundant copy of a unit

1. Select a unit, for example `PCDU1`.
2. Press **Create redundant copy** above the diagram (or in the **Inspector**), or choose **Edit > Create redundant copy**. (The button is greyed out for a unit that already is a redundant copy or already has one.)
3. A twin appears in the next lane: `PCDU1-R`, named "Power unit 1 (redundant)", with the same connectors (`PCDU1-R-J01`, ...). The tool then copies the links of the unit (their IDs end in `-R`).

A copied link needs a free connector of the right type at the other end. In `first-steps`, `RW1` has one power connector and it is used, so copying `PCDU1` first copies no link. A message says so ("1 interface(s) could not be mirrored (no free connector): IF-001"). Copy `RW1` next: `IF-001-R` then joins `PCDU1-R` and `RW1-R`.

If the unit at the other end has no twin yet but has a free connector, the copied link goes to the **nominal** unit at the other end. That is a link between the two chains. The tool flags it as a warning (see below).

## 2. Fix a link between the two chains

This is the usual result when you copy several units one after the other. With `first-steps`, copy `PCDU1`, then `RW1`, then `OBC1`. The **Problems** tab (right panel) then shows:

```
IF-002-R connects the nominal chain to the redundant chain
```

The card explains that one failure could affect both chains. It has a **Show** button, a **Waive…** button and a fix button called **Connect to a redundant copy of OBC1**.

- Press the fix button. The nominal end moves onto the twin (`OBC1-R`). Both ends are then on the redundant chain, and the warning goes.
- Or press **Waive…** and write a reason of at least 10 characters if the link between the chains is wanted. The reason stays in the report.

After the fix, the project has six units and four links. Save with Ctrl+S. Then on the command line:

```
harness-design-studio generate red2
harness-design-studio drc red2
```

```
4 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
4 interfaces and 12 wires checked: 0 error(s)
```

(`red2` is whatever folder you made with `harness-design-studio new red2 --template first-steps`. The second line comes from `harness-design-studio generate`; `harness-design-studio drc` prints the whole design rule report.) The design rule report no longer lists a `cross-strap` warning.

You can also draw a link by hand: under **Connect with**, pick the type, click `OBC1-R`, then `RW1-R`. The tool sets the **Chain** of that link to *redundant* by itself, because both ends are redundant.

## 3. Zones and lanes

- A unit's zone is **set by where you place it**: drag the unit into a lane. The field **Zone (set by where you place the unit)** in the **Inspector** is read-only.
- **Edit > Add zone…** asks for a **Zone name** and adds a lane. A name that exists already is refused.
- A blank project and `first-steps` have the lanes `panel-A` and `panel-B`.
- Zones matter when harnesses are made. The default groups links by pair of unit connectors. The setting `per_zone_pair` groups links between the same two zones. See [generate harnesses](generate-harnesses.md#how-links-become-harnesses).

## Common mistakes

- **A "cross-strap" warning you did not expect.** You copied one unit and not its neighbour. Copy both, then use the fix button.
- **The copy button is greyed out.** The unit is already a redundant copy, or already has one (`PCDU1-R` exists), or the project is read-only. See [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).
- **A harness mixes the chains.** It cannot: the default rules forbid it (`forbid_nominal_with_redundant` in `config/segregation.json`). See [`CONFIG.md`](../CONFIG.md).

Next: [generate harnesses](generate-harnesses.md), [read and fix problems](read-and-fix-problems.md)
