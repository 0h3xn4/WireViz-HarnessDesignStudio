# Release a harness

This page shows how to review and release a harness, which freezes it: it, the links it carries, the pins it uses, and the parts, interface types and configuration values it relies on can no longer be changed, and a record is stored.

> **Two meanings of "release".** This page is about releasing a **harness** of your design. Releasing the **tool itself** (a new version of Harness Design Studio) is a different job for the developers: [`developer/release.md`](../developer/release.md). The release checklist in [`RELEASE.md`](../RELEASE.md) is about the tool, not about your harness.

## Contents

- [Before you start](#before-you-start)
- [1. Make the design ready](#1-make-the-design-ready)
- [2. Submit for review (optional)](#2-submit-for-review-optional)
- [3. Release](#3-release)
- [4. After the release](#4-after-the-release)
- [Common mistakes](#common-mistakes)

## Before you start

- You have a generated and exported project. This page uses the practice project of [fill in the engineering values](fill-in-engineering-values.md#practice-with-demo-values) (demo values and segment lengths loaded, generated, exported). Release the harness `W002`, the power harness.
- A release needs a **name** and a **comment of at least 10 characters**. The name goes into the change log and the title block.
- **The tool is not a person.** It checks that the harness is complete and that the design has no open errors. It cannot tell whether your values are right. That stays a decision for the engineer who releases.
- The tool and your design are made mainly by software and have not been independently reviewed. A release made with it does not mean a harness complies with any standard.

## 1. Make the design ready

A release is blocked until all of these hold. The tool lists what is missing, in words.

| Blocker | What to do |
| --- | --- |
| An open error | Fix it ([read and fix problems](read-and-fix-problems.md)). |
| `gauge_pending`: a wire has no gauge | Fill in the derating values ([fill in the engineering values](fill-in-engineering-values.md)), or set the gauge by hand. |
| `length_unknown`: a wire has no length | Import the segment lengths ([import data](import-data.md#segment-lengths)). |
| `outputs_missing` / `outputs_stale` | Export, then release ([export the outputs](export-the-outputs.md)). |
| `outputs_linked`: the `outputs` folder (or a folder in it) is a link, or cannot be written | Replace the link with a real folder, make the folder writable, and export again. The release is blocked up front because the released status could not be written into the outputs. |
| `placeholder_config`: a config file is still marked `"placeholder": true` | An engineer reviews the values and sets `"placeholder": false` in each file. Or release with a written reason (below). |
| `parts_unapproved`: the harness uses a part that is not approved, or is example data | Import your approved parts list ([import data](import-data.md#approved-parts-list)). Or release with a written reason (below). |

Try it. You see the two reasons that remain after the demo values and the lengths are in:

```
harness-design-studio release wheel-link W002 --by "A. Engineer" --comment "First release of the wheel power harness"
```

```
blocked: [placeholder_config] These configuration files are still placeholders: derating, emc, generation, segmentation, segregation, titleblock. Have an engineer review the values and set "placeholder" to false in each file (`harness-design-studio config DIR` lists them). Or release on placeholders with a written reason (command line: --accept-placeholders REASON); the reason is kept in the change log.
blocked: [parts_unapproved] 2 part(s) used by W002 are not approved (or are example data): EX-MICROD-9-M, EX-WIRE-SINGLE. Approve them in the parts list, or release with a written reason (command line: --accept-unapproved-parts REASON); the reason is kept in the change log.
```

Nothing was changed. The exit code is 1. (On a project without the demo values, you also see `gauge_pending`, `length_unknown` and `outputs_missing`.)

## 2. Submit for review (optional)

A harness is `draft`, then optionally `in_review`, then `released`.

- App: open the **Releases** tab (Ctrl+5), pick the harness and press **Submit for review** (in the **Harness** tab the button is **Open in review**), confirm your name.
- Command line:

```
harness-design-studio review wheel-link W002 --by "A. Engineer"
```

```
Submit W002 for review: done.
```

## 3. Release

**On the command line**

For a real design, an engineer reviews the values and clears every `"placeholder"` mark, and the approved parts list is imported. Then the release needs nothing more than a name and a comment. For this **practice project**, accept the two gates and say why. The reasons are kept in the change log and in the baseline, so every later report shows that the release rested on them:

```
harness-design-studio release wheel-link W002 --by "A. Engineer" --comment "First release of the wheel power harness" --accept-placeholders "Practice project: demo values only" --accept-unapproved-parts "Practice project: example parts only" --checker "B. Checker"
```

```
Release W002 revision A: done.
Outputs re-exported with the released status (38 files).
```

`--checker` is optional and goes in the title block. Each reason needs at least 10 characters. A name, checker, comment or reason with control characters or too much text (a name is one line of at most 200 characters; a comment together with the reasons at most 2,000) is a blocker that names the option, for example `blocked: [by_invalid] --by: The name must not contain control characters or line breaks.` Line breaks in a comment are allowed and are shown as spaces in the change log and the revision report. `--date ""` is an error; leave `--date` out for today. A date earlier than the last change-log entry of the same harness is refused (`blocked: [date_before_last] --date: ...`), so a release cannot be dated before its own review.

If the re-export after the release fails (for example the disk is full), the release stands. The command says `The release was recorded (see `harness-design-studio log`); only the outputs still show the old status. Fix the problem, then run `harness-design-studio export` to re-stamp them.` and ends with an error code (1 or 2).

**In the app**

1. In the **Releases** tab (or the **Harness** tab), pick `W002` and press **Release…** (**Design > Release harness…** does the same for the harness in view).
2. The window **Release W002** opens. Anything that blocks the release is listed in words ("Blocked until these are fixed:"). When nothing blocks it, it says "Nothing blocks this release." Under the list is the tree **What this release locks**, headed by a sentence such as "This release locks: n wires, n pins, n interfaces, n parts, n interface types, n config files." Open a group to see each object; a config file that is still a placeholder is marked *Pending*, and a value that is not set reads "not set (pending)".
3. Fill in **Your name**, optionally **Checked by (optional)**, and **Comment (what changed or why)**.
4. While a config file is still a placeholder, the window shows which ones and a field **Reason for releasing on placeholder values (kept in the change log)**. While the harness uses parts that are not approved, there is a second field **Reason for releasing with parts that are not approved (kept in the change log)**. Fill in both for a practice release.
5. Press **Release**. The button stays greyed out until nothing blocks the release and the fields are complete; a line under the form says what is still missing (for example "write at least 10 characters in the comment (3 more to go)").
6. The app says "W002 released. Export the outputs again so the drawings show the released status."

GUI, not run: the app steps are described from the program's texts and code. They have not been looked at on screen.

## 4. After the release

- `W002` is now **released (locked)**. The **Releases** tab lists the release with a *Released* chip, and the **Harness** tab header says *Released · rev A*. A lock and *W002 A* appear on the objects it holds, in the **Project** tree and on the diagram. The harness, the links it carries and the pins it uses cannot be edited. The app refuses an edit and gives the reason.
- **A release also freezes what the harness uses**: the parts of its connectors and wires (and of the unit connectors it plugs into), the interface types of its links, and the configuration its checks and outputs read (all of `derating`, `emc`, `segregation` and `titleblock`, and eight keys of `generation`). The editor and the commands `import-parts` and `config` (including `--apply-profile` and `--ampacity-csv`) refuse a change to these, with the reason and the way out. (`harness-design-studio library`, which only records where the parts data come from, is not affected.) Example, importing the parts list after the release:

```
error: This change was blocked because it touches released items.
  - Part EX-MICROD-9-F is used by W002, which is released. W002 is released (revision A); start a new revision to change it.
```

The exit code is 1, and `--dry-run` says the same ("Dry run: this import would be blocked. Nothing was changed."). What stays open: new parts, parts and interface types that no released harness uses, notes and names, and the `segmentation`, `naming` and other `generation` settings. The configuration applies to every harness, so while any harness is released a change to it needs a new revision of each released harness. The complete list is in [`FILE_FORMAT.md`](../FILE_FORMAT.md#what-a-release-freezes). A release of the 0.1.0 tool froze less; its baselines are still read and are not flagged.
- A release or new revision that has been **saved** can no longer be undone (the Undo button is off, and its tooltip says "This release was saved; it cannot be undone. Use 'Revise' to change the harness."). Before you save, it can still be undone.
- A **baseline** (a frozen copy) is stored in `baselines/W002/W002.A.json`, and an entry goes into `changelog.json`.
- Print the history:

```
harness-design-studio log wheel-link W002
```

```
Entry | Harness | Revision | Event | By | Date | Comment
C0001 | W002 | A | submitted for review | A. Engineer | 2026-10-10 | 
C0002 | W002 | A | released | A. Engineer | 2026-10-10 | First release of the wheel power harness [Released on placeholder configuration (derating, emc, generation, segmentation, segregation, titleblock); accepted by A. Engineer: Practice project: demo values only] [Released with parts that are not approved (EX-MICROD-9-M, EX-WIRE-SINGLE); accepted by A. Engineer: Practice project: example parts only]
```

(The date is the day you run it.)

- The drawing now says `status released`, and its title block shows the date of the release, the author and approver (the name you gave) and the checker. The release command exports again for you; in the app, press **Export…** again.
- If someone edits a released harness file by hand anyway, `harness-design-studio check` reports `released_modified: W002 was changed after its release (revision A); it no longer matches its baseline.` and exits with 1. It also compares the units and box connectors, and the parts, interface types and configuration values stored in the baseline. To change a released harness, start a new revision: [change a released harness](change-a-released-harness.md).

## Common mistakes

- **Releasing on placeholders with a lazy reason.** The reason is read by reviewers. Say what the release is for.
- **Thinking the release means the values are right.** The check looks at the harness and at the placeholder mark. It cannot judge the numbers.
- **"The comment needs at least 10 characters."** Write a real comment.
- **"Harness W999 does not exist."** Check the ID in the **Harness** tab or the **Project** tree (exit code 2).
- **A comment that is too long.** Together with the reasons it must fit 2,000 characters.
- **"This change was blocked because it touches released items" when you import parts or change a derating value.** A released harness uses them. Start a new revision ([change a released harness](change-a-released-harness.md)).

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md), [`CLI.md`](../CLI.md#harness-design-studio-release).

Next: [change a released harness](change-a-released-harness.md), [use Git and CI](use-git-and-ci.md)
