# Override a value and keep a history

This page shows how to set a value of a generated wire yourself and say why, how the tool keeps what you set and flags it everywhere, how to accept an error of an electrical rule as a recorded deviation, and how to keep and read the change history of a project: who changed what, when, from what to what, and why. Use it when a review asks *who changed this, and on what grounds?*

> **Since stage S4 of the transparency work** (decision D-191). The steps in the editor are described from the program's code and its tests; the program was not watched on a screen while this page was written. Nothing here says that a design meets a requirement: an override or a deviation records that **a person decided**, it does not make the design right.

## Contents

- [Before you start](#before-you-start)
- [1. Override a value, with a reason](#1-override-a-value-with-a-reason)
- [2. See what the override does](#2-see-what-the-override-does)
- [3. Give a value back to the design](#3-give-a-value-back-to-the-design)
- [4. Where an override is shown](#4-where-an-override-is-shown)
- [5. Accept an error as a deviation](#5-accept-an-error-as-a-deviation)
- [6. Keep a history](#6-keep-a-history)
- [7. Read the history](#7-read-the-history)
- [8. What the journal is not](#8-what-the-journal-is-not)
- [Common mistakes](#common-mistakes)

## Before you start

- An **override** is a gauge, a wire type, a colour or a length that you set on a **generated** wire in place of the value the design gives. A wire you drew yourself has no generated value, so setting its gauge is not an override and needs no reason.
- The **reason** is kept with the wire in the design file. **Who** and **when** are kept in the journal and nowhere else: no design file, no hash and no written output holds a name or a time, so the same design still gives the same bytes.
- A wire that was locked in an earlier version has no reason. It stays locked and is shown as *Locked (no reason recorded)*; nothing is changed in the file until you override a value of it.
- The harness must not be released. For a released one start a new revision first ([change a released harness](change-a-released-harness.md)).

## 1. Override a value, with a reason

In the editor: choose the wire (see [edit a wire](edit-a-wire.md)), change its gauge, type, colour or length. A **Reason** box appears below the fields; **Apply** stays off until it holds a sentence. The same holds for **Edit all wires…**.

On the command line:

```
harness-design-studio override wheel-link W001-001 gauge_awg 20 --reason "Heater load added after CDR, see ECR-114"
```

`FIELD` is `gauge_awg`, `part_id`, `colour` or `length_m`. **An override without a reason is refused**, in the editor, on the command line and in the model: the reason cannot be empty or only spaces. Several overrides on one wire each keep their own reason.

Generation keeps the values you overrode when you press **Generate** again. The other values of the wire follow the design, and the gauge is sized for the length you set.

## 2. See what the override does

```
harness-design-studio explain wheel-link W001-001
```

The first part says **Overridden by the engineer**: for each overridden value, the value you set and the reason, the value the design would have given and how it would have been decided, and the consequence: the check on the value you set with the actual, the limit and the margin, for example *the wire carries 0.8 A but allows 0.54 A after derating*. The `override` command prints the same after it saves. The other derivations of the wire (length, current limit, voltage drop, mass) already use the value you set. `derivations.json` and `derivations.csv` ([every derivation as files](../models/README.md#every-derivation-as-files)) carry it too.

## 3. Give a value back to the design

```
harness-design-studio override wheel-link W001-001 --clear gauge_awg
```

The override is removed and the value is cleared; the next **Generate** gives the wire the value the design asks for. When it was the last override the wire is unlocked. **Reset to generated** in the Edit wire tab does this for every value of the selected wires.

## 4. Where an override is shown

Only a project that has an override shows any of this; a project without one is written exactly as before. The reason is written, never a name or a time: *who* and *when* are in the journal (`deviation DIR` lists them), because a written file that held them would change with the day it was made.

| Place | What shows |
| --- | --- |
| The wire table and the Edit wire tab | The word *Overridden* in the Locked column, the reason in its tooltip and in the line under the form |
| `wirelist.csv` and its sheet | A last column *Overrides*: the fields and their reasons |
| The build workbook | A column *Override* on the cut list and a section *Overrides and deviations* on *Start here* |
| `tests.csv` and the *Tests* sheet | A last column *Deviations* for a test of a wire that has an override or a deviation (`override gauge_awg: reason; deviation current-over-wire: reason`), and on the *Tests* sheet the band *Overrides and deviations* above the table |
| The as-built report | The note of a measured test line repeats it (`design: override ...`) |
| The drawing | Lines *OVERRIDE …* beneath the diagram |
| `explain` and the derivation files | The derivation *Overridden by the engineer* |
| The release record | The comment of the release says how many values were overridden and which |
| The baseline | The released harness holds its overrides, with their reasons |

## 5. Accept an error as a deviation

An error of an electrical rule (wire current, voltage drop, contact current, bundle current, working voltage of a wire or connector, temperature margin) cannot be waived like a warning. It can be **accepted as a deviation**: the finding is not removed, it stays on every list and output marked **DEVIATION**, with the reason, and it no longer blocks a release.

In the editor: on the error card in the Problems list press **Accept as deviation…** and write the reason (at least 10 characters). On the command line:

```
harness-design-studio deviation wheel-link current-over-wire.W001-001 --reason "Accepted by the PA board, NCR-17"
harness-design-studio deviation wheel-link                      # list them, with who and when
harness-design-studio deviation wheel-link current-over-wire.W001-001 --remove
```

A deviation does **not** meet the requirement; it records that a person accepted the error. It is shown in the Problems list and the Checks panel (with who and when), in `drc` and `drc_report.md` (a section *Deviations*), in `drc_findings.csv` (*Waived* reads `deviation`), in the drawing, the *Start here* and *Tests* sheets of the build workbook of the harness it is about, in the column *Deviations* of `tests.csv` for the tests of the wires it is about (the wire itself; the wires of the interface for a finding on a connector of the interface; the wires that end on a connector for the temperature margin of its part), and in the release record. If the finding changes later (the numbers in its text change), the deviation no longer applies and the error is open again.

## 6. Keep a history

A project has a change journal if and only if it has the file `journal.json`.

- `harness-design-studio new` and **New project** in the editor start one (`new --no-journal` does not).
- For an existing project: `harness-design-studio journal wheel-link --start`, or **Help > Change history… > Start a journal**.
- A project without one is opened and saved exactly as before, byte for byte.

Entries are made when the project is **saved**, by comparing the files that changed with what was on disk, so every way of changing a project is recorded: the editor, the command line and a script. Generation is one entry for each harness it changed (wires added, changed and removed, and the model hash before and after), not one for each field.

The author is, in this order: the global option `--author NAME` (before the command), the environment variable `HARNESS_AUTHOR`, the name Git has (`git config user.name`), the user name of the computer, `unknown`.

## 7. Read the history

```
harness-design-studio journal wheel-link
harness-design-studio journal wheel-link --object W001-001
harness-design-studio journal wheel-link --since 12 --json
```

Each line reads `#12 2026-11-03T10:00:05Z Ann [override] wire:W001-001 gauge_awg: 24 -> 20 (reason: ...)`. `--object` takes `W001-001`, `wire:W001-001` or a configuration key such as `derating.bundle_derating`; `explain` of an object also prints its history when the project has a journal. In the editor, **Help > Change history…** lists the same with a filter box. An import is an entry too (`kind` `import`, object `import:KIND:FILE`): it says which file was read, by its hash, and how many rows were read, dropped and converted; the full record is `imports/records.json`. A change to `extensions/enabled.json` or to a file of `extensions/` is an entry too (`kind` `config`, object `extension:FILE`): the files are design inputs, so the journal keeps the SHA-256 of each before and after, taken from the bytes on disk when the project is saved.

With `--json`, `journal`, `override` and `deviation` print one document each (the keys are in [`CLI.md`](../CLI.md)), and a script gets the same data from `harness_design_studio.api` (`get_journal`, `set_override`, `clear_override`, `get_overrides`, `list_deviations`, `accept_deviation`, `remove_deviation`, `start_journal`).

What is recorded: a change of any design input (devices, interfaces, connectors, links, harness fields, wire fields, library parts), a configuration value, an override (with its reason), a waiver or a deviation (with its justification), the approval of a part, a review, a release or a new revision (with the comment), and a generation. Not recorded: the positions of devices on the diagram.

The journal is **append-only**. An entry cannot be changed or removed; each entry carries a chain value made from the one before it, so a changed, removed or inserted entry makes `validate` report *the change journal is damaged* (exit 1), and the editor will not save over it. Cutting off the last entries is not detectable from the file; keep the project in Git (see [use Git and CI](use-git-and-ci.md)) for that.

## 8. What the journal is not

- It is **not** part of the model hash, the baseline or any written output.
- It is **not** a proof of who typed: the name is the one the computer, Git or `--author` gave. A project that must tie a name to a person needs the roles of [release a harness](release-a-harness.md) and the history of Git.
- It is **not** a merge of two people's work. `journal.json` belongs to one working copy. When two people append to it on different Git branches, Git reports a conflict in the file; keep one side's file (the chain only holds for one line of entries). The changes that arrive from the other branch are in the design files and in Git's history, and the journal does not record them again, because it compares a save with what was on disk. Decide in the team who keeps the journal of record.
- It is **not** an approval. A release still needs its own steps.

## Common mistakes

- **Typing a reason that says nothing.** The tool refuses an empty reason; it cannot refuse an empty sentence. A review will read it.
- **Expecting a cleared override to change the wire at once.** `--clear` removes the override and the value; **Generate** gives the design's value.
- **Editing `journal.json` by hand.** It is read as a record: a change makes it damaged. Fix a wrong entry by a new change, not by editing.
- **Starting the journal late.** The history starts at the first save after it exists; earlier changes are only in Git, if you used it.

Next: [edit a wire](edit-a-wire.md), [read and fix problems](read-and-fix-problems.md), [release a harness](release-a-harness.md), [see what the tool assumes](see-what-the-tool-assumes.md)
