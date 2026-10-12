# Change a released harness

This page shows how to change a harness after it was released, by starting a new revision, and how to see what changed and who changed it.

## Contents

- [Before you start](#before-you-start)
- [1. Start a new revision](#1-start-a-new-revision)
- [2. Make the change](#2-make-the-change)
- [3. See what changed](#3-see-what-changed)
- [4. Release revision B](#4-release-revision-b)
- [5. Read the history](#5-read-the-history)
- [Compare two copies of a project](#compare-two-copies-of-a-project)
- [Common mistakes](#common-mistakes)

## Before you start

- A harness is released and locked ([release a harness](release-a-harness.md)). This page continues with the practice project of that page: the harness `W002`, revision A, released.
- You never edit a released harness. You start a **new revision** (A, B, C, ...). The old revision stays available, so it can always be reproduced.
- Editing a locked harness, a link it carries or a pin it uses is refused, with the reason. So is editing a **part** or **interface type** the harness uses (its connectors' and wires' parts, and the parts of the box connectors it plugs into) or the **configuration** its checks read (derating, EMC, segregation, title block, and the electrical and test values in the generation file), for example by importing parts or changing a derating value. Notes and names stay editable, and so does everything no released harness uses: new parts, other parts, the naming and segmentation settings. The exact list is in [`FILE_FORMAT.md`](../FILE_FORMAT.md#what-a-release-freezes). If the files were changed by hand anyway, `harness check` reports it ([release a harness](release-a-harness.md#4-after-the-release)).

## 1. Start a new revision

**On the command line**

```
harness revise wheel-link W002 --by "A. Engineer" --comment "Add wire colours for the second revision"
```

```
New revision B of W002: done.
```

**In the app** (GUI, not run): select `W002` in **Harness plans**, press **New revision…**, type your name and a comment (at least 10 characters), and press **Start new revision**. The app says "New revision of W002 started; it can be edited again."

Revision B is a `draft` that you can edit. Revision A and its baseline are kept.

## 2. Make the change

Edit the design as usual. As an example, give the two power signals colours in `config/generation.json` (or use **Edit > Wire colours...**; see [set wire colours](set-wire-colours.md)), then generate. (Wire colours are **newer than the 0.1.0 packages**; they are on the `master` branch only. With a 0.1.0 package, make a different change; the output below then differs.)

```
harness generate wheel-link
```

```
0 added, 1 changed, 1 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
```

## 3. See what changed

**On the command line**

```
harness diff wheel-link W002
```

```
# W002: working design against revision A

Comparing before with after: 0 added, 0 removed, 3 changed.

## Changed (3)

- Harness `W002`
  - approver: A. Engineer -> (none)
  - checker: B. Checker -> (none)
  - released_on: 2026-10-10 -> (none)
  - revision: A -> B
  - status: released -> draft
- Wire `W002-001`
  - colour: (none) -> red
- Wire `W002-002`
  - colour: (none) -> black
```

Without `--from` and `--to` the command compares the working design with the latest baseline. The harness lines (approver, status, revision) are the release bookkeeping that a new revision resets. The wire lines are your change.

**In the app**: press **Changes…**. The window "Changes in W002" lists the differences, with a list **Compare the working design with** (the baselines). **Mark on diagram** marks the changed units and interfaces on the diagram; **Clear marks** removes the marks.

## 4. Release revision B

Export, then release as before:

```
harness export wheel-link
harness release wheel-link W002 --by "A. Engineer" --comment "Second revision with wire colours" --accept-placeholders "Practice project: demo values only" --accept-unapproved-parts "Practice project: example parts only"
```

```
38 files written to wheel-link/outputs (model d7c2e9a824be).
Release W002 revision B: done.
Outputs re-exported with the released status (38 files).
```

Now both revisions have a baseline, and you can compare them:

```
harness diff wheel-link W002 --from A --to B
```

```
# W002: revision A to B

Comparing before with after: 0 added, 0 removed, 3 changed.

## Changed (3)

- Harness `W002`
  - checker: B. Checker -> (none)
  - revision: A -> B
- Wire `W002-001`
  - colour: (none) -> red
- Wire `W002-002`
  - colour: (none) -> black
```

Before revision B is released, `--to B` fails: `error: W002 has no baseline for revision B.` (exit code 2). Compare with the working design instead, as in step 3.

## 5. Read the history

```
harness log wheel-link
```

```
Entry | Harness | Revision | Event | By | Date | Comment
C0001 | W002 | A | submitted for review | A. Engineer | 2026-10-10 | 
C0002 | W002 | A | released | A. Engineer | 2026-10-10 | First release of the wheel power harness [Released on placeholder configuration (...); accepted by A. Engineer: Practice project: demo values only] [...]
C0003 | W002 | B | new revision started | A. Engineer | 2026-10-10 | Add wire colours for the second revision
C0004 | W002 | B | released | A. Engineer | 2026-10-10 | Second revision with wire colours [Released on placeholder configuration (...); ...] [...]
```

(Long parts of the comment column are shortened here with `...`.) Add a harness ID (`harness log wheel-link W002`) to see one harness. In the app: **Change log…**. The entries cannot be deleted. The outputs also have them: `system/changelog.csv` and `system/revision_report.md`.

## Compare two copies of a project

To see what differs between two project folders (for example two Git checkouts, or a copy you made before the change with `cp -r wheel-link wheel-link-A`):

```
harness compare wheel-link-A wheel-link
```

```
# Project comparison

Comparing wheel-link-A with wheel-link: 0 added, 0 removed, 4 changed.

## Changed (4)

- Configuration `generation`
  - values: {'conductor_resistivity_ohm_m': 1.72e-08, 'default_gauge_awg': None, 'mass_ma... -> {'conductor_resistivity_ohm_m': 1.72e-08, 'default_gauge_awg': None, 'mass_ma...
- Harness `W002`
  - checker: B. Checker -> (none)
  - revision: A -> B
- Wire `W002-001`
  - colour: (none) -> red
- Wire `W002-002`
  - colour: (none) -> black
```

It does not change either folder. Equal folders print `No differences.` See [use Git and CI](use-git-and-ci.md).

## Common mistakes

- **Editing the JSON of a released harness.** Start a revision instead. `harness check` finds the edit.
- **"blocked because it touches released items" when you import parts or change a derating value.** A released harness uses those parts or values. Start a new revision of that harness (of each released harness, for configuration), make the change, and release again.
- **Forgetting to export after the release.** `harness release` exports for you; after a revision you still export yourself before the next release.
- **"W002 has no baseline for revision B."** Revision B is not released yet.
- **Deleting a released harness.** The app does not allow it. Start a new revision and change it.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md), [`CLI.md`](../CLI.md#harness-revise).

Next: [use Git and CI](use-git-and-ci.md), [release a harness](release-a-harness.md)
