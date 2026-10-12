# Release a harness

This page shows how to review and release a harness, which freezes it: it, the links it carries and the pins it uses can no longer be edited, and a record is stored.

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
| `placeholder_config`: a config file is still marked `"placeholder": true` | An engineer reviews the values and sets `"placeholder": false` in each file. Or release with a written reason (below). |
| `parts_unapproved`: the harness uses a part that is not approved, or is example data | Import your approved parts list ([import data](import-data.md#approved-parts-list)). Or release with a written reason (below). |

Try it. You see the two reasons that remain after the demo values and the lengths are in:

```
harness release wheel-link W002 --by "A. Engineer" --comment "First release of the wheel power harness"
```

```
blocked: [placeholder_config] These configuration files are still placeholders: derating, emc, generation, segmentation, segregation, titleblock. Have an engineer review the values and set "placeholder" to false in each file (`harness config DIR` lists them). Or release on placeholders with a written reason (command line: --accept-placeholders REASON); the reason is kept in the change log.
blocked: [parts_unapproved] 2 part(s) used by W002 are not approved (or are example data): EX-MICROD-9-M, EX-WIRE-SINGLE. Approve them in the parts list, or release with a written reason (command line: --accept-unapproved-parts REASON); the reason is kept in the change log.
```

Nothing was changed. The exit code is 1. (On a project without the demo values, you also see `gauge_pending`, `length_unknown` and `outputs_missing`.)

## 2. Submit for review (optional)

A harness is `draft`, then optionally `in_review`, then `released`.

- App: select the harness in **Harness plans**, press **Submit for review**, confirm your name.
- Command line:

```
harness review wheel-link W002 --by "A. Engineer"
```

```
Submit W002 for review: done.
```

## 3. Release

**On the command line**

For a real design, an engineer reviews the values and clears every `"placeholder"` mark, and the approved parts list is imported. Then the release needs nothing more than a name and a comment. For this **practice project**, accept the two gates and say why. The reasons are kept in the change log and in the baseline, so every later report shows that the release rested on them:

```
harness release wheel-link W002 --by "A. Engineer" --comment "First release of the wheel power harness" --accept-placeholders "Practice project: demo values only" --accept-unapproved-parts "Practice project: example parts only" --checker "B. Checker"
```

```
Release W002 revision A: done.
Outputs re-exported with the released status (38 files).
```

`--checker` is optional and goes in the title block. Each reason needs at least 10 characters.

**In the app**

1. In **Harness plans**, select `W002` and press **Release…**.
2. The window **Release W002** opens. Anything that blocks the release is listed in words ("Blocked until these are fixed:"). When nothing blocks it, it says "Nothing blocks this release."
3. Fill in **Your name**, optionally **Checked by (optional)**, and **Comment (what changed or why)**.
4. While a config file is still a placeholder, the window shows which ones and a field **Reason for releasing on placeholder values (kept in the change log)**. While the harness uses parts that are not approved, there is a second field **Reason for releasing with parts that are not approved (kept in the change log)**. Fill in both for a practice release.
5. Press **Release**. The button stays greyed out until nothing blocks the release and the fields are complete.
6. The app says "W002 released. Export the outputs again so the drawings show the released status."

GUI, not run: the app steps are described from the program's texts and code. They have not been looked at on screen.

## 4. After the release

- `W002` is now **released (locked)**. The Harness plans tab shows "A released (locked)". The harness, the links it carries and the pins it uses cannot be edited. The app refuses an edit and gives the reason.
- A **baseline** (a frozen copy) is stored in `baselines/W002/W002.A.json`, and an entry goes into `changelog.json`.
- Print the history:

```
harness log wheel-link W002
```

```
Entry | Harness | Revision | Event | By | Date | Comment
C0001 | W002 | A | submitted for review | A. Engineer | 2026-10-10 | 
C0002 | W002 | A | released | A. Engineer | 2026-10-10 | First release of the wheel power harness [Released on placeholder configuration (derating, emc, generation, segmentation, segregation, titleblock); accepted by A. Engineer: Practice project: demo values only] [Released with parts that are not approved (EX-MICROD-9-M, EX-WIRE-SINGLE); accepted by A. Engineer: Practice project: example parts only]
```

(The date is the day you run it.)

- The drawing now says `status released`, and its title block shows the date of the release, the author and approver (the name you gave) and the checker. The release command exports again for you; in the app, press **Export outputs** again.
- If someone edits a released harness file by hand anyway, `harness check` reports `released_modified: W002 was changed after its release (revision A); it no longer matches its baseline.` and exits with 1. To change a released harness, start a new revision: [change a released harness](change-a-released-harness.md).

## Common mistakes

- **Releasing on placeholders with a lazy reason.** The reason is read by reviewers. Say what the release is for.
- **Thinking the release means the values are right.** The check looks at the harness and at the placeholder mark. It cannot judge the numbers.
- **"The comment needs at least 10 characters."** Write a real comment.
- **"Harness W999 does not exist."** Check the ID in the **Harness plans** tab (exit code 2).
- **A comment that is too long.** Together with the reasons it must fit 2,000 characters.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md), [`CLI.md`](../CLI.md#harness-release).

Next: [change a released harness](change-a-released-harness.md), [use Git and CI](use-git-and-ci.md)
