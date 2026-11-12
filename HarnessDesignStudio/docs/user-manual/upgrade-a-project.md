# Upgrade a project to format 2

Version 2.0.0rc1 is the first version that saves projects in **format 2**. A project saved by 1.17.1 or older is in format 1. This page shows how to upgrade such a project once, what changes in the folder, and what the older versions do with it afterwards.

## Contents

- [Before you start](#before-you-start)
- [1. See whether a project needs the upgrade](#1-see-whether-a-project-needs-the-upgrade)
- [2. Upgrade in the editor](#2-upgrade-in-the-editor)
- [3. Upgrade on the command line](#3-upgrade-on-the-command-line)
- [4. What changed in the folder](#4-what-changed-in-the-folder)
- [5. What the older versions do](#5-what-the-older-versions-do)
- [6. Go back](#6-go-back)

## Before you start

- **The upgrade changes no design data.** Format 2 is format 1 with the number 2 in `project.json`, and the change journal in the file `journal.jsonl` instead of `journal.json`. The upgrade checks that the model hash, the findings, the released baselines and a full export are the same before and after. If any of them differs, it puts every file back.
- **It is one way for the older versions.** After the upgrade, a version 1.x tool opens the project read-only and cannot save it. If other people edit the project, agree first that everyone uses 2.0.0rc1 or later.
- **With Git,** commit or stash your work before you upgrade, so that the upgrade is one commit of its own.

The commands below use the practice project `wheel-link`, made with version 1.17.1 by `harness-design-studio new wheel-link --template first-steps`. Put your own folder where you see `wheel-link`.

## 1. See whether a project needs the upgrade

A command that saves (`generate`, an import, `override`, `release` and the others) refuses a format 1 project and writes nothing:

```
harness-design-studio generate wheel-link
```

```
2 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
error: This project is in format 1, older than this tool writes (format 2), so nothing was saved. Upgrade it first: `harness-design-studio migrate DIR` (`--dry-run` shows what changes), or open it in the editor and choose Upgrade.
```

The exit code is 2, and no file was changed. `validate`, `check`, `drc` and `export` read a format 1 project without upgrading it. A project that is already in format 2 needs nothing: `harness-design-studio migrate wheel-link` then says `Already up to date.`

## 2. Upgrade in the editor

Open the project (**Open project…** on Home, or **File > Open project…**). The editor asks once, in the window *Older project format*:

*This project is in format 1. Upgrade? A copy of the original stays in .migration-backup-v1. Older tools can no longer edit it.*

- **Upgrade** upgrades the project, checks it and says *Upgraded from format 1 to 2. The original files are in .migration-backup-v1.*
- **Open read-only** opens it without a change. A note says *This project is in format 1, so it is open read-only. Upgrade it to edit it.*
- **Cancel** opens nothing.

(GUI, not run: the question was checked against the program's texts and in the tests without a screen; nobody watched it on a display.)

## 3. Upgrade on the command line

Look first. `--dry-run` writes nothing:

```
harness-design-studio migrate wheel-link --dry-run
```

```
Project format 1; this tool writes format 2.
Files that would change (4):
  changed  .gitattributes
  removed  journal.json
  new      journal.jsonl
  changed  project.json
Objects by kind, before and after:
  box connectors: 9 -> 9
  configuration files: 7 -> 7
  devices: 3 -> 3
  interface types: 17 -> 17
  interfaces: 2 -> 2
  journal entries: 1 -> 2
  library manifest: 1 -> 1
  library parts: 28 -> 28
  placements: 3 -> 3
  zones: 2 -> 2
Model hash: <hash> -> <hash> (equal).
A full export before and after: identical.
The journal gets one entry: "migrated from format 1".
Nothing is lost. Nothing was written.
```

It exits with 0 only if nothing would be lost. A project without a change journal has only `project.json` in the list. Then upgrade:

```
harness-design-studio migrate wheel-link
```

```
Migrated; the original files are kept in a .migration-backup-* folder.
Format 1 to 2. Record: .migration-backup-v1/MIGRATION.json.
Checked after the write: same model hash, same findings, baselines untouched, identical export.
The journal is now journal.jsonl (one entry per line); .gitattributes says `journal.jsonl merge=union`, so Git keeps both sides' entries of a merge. Commit both files.
```

If the check after the write finds a difference, or the write fails, the command puts every file back from the backup, says so and exits with 1.

## 4. What changed in the folder

- `project.json` says `"schema_version": 2` and the version of the tool that saved it.
- `journal.json` is now `journal.jsonl`, one entry per line, with every entry as it was and one new entry *migrated from format 1*. A save only adds lines at the end, so the journal of two Git branches merges ([Use Git and CI](use-git-and-ci.md#2-after-a-merge)).
- `.gitattributes` has the line `journal.jsonl merge=union`, so Git keeps the lines that both sides of a merge added.
- `.migration-backup-v1/` holds the original files and the record `MIGRATION.json` (the formats, the tool version, the SHA-256 of every file before and after, the model hash and the counts). Git ignores this folder and the `.bak` files (they are in the project's `.gitignore`). Keep the folder until you have looked at the upgraded project; then you can delete it.

With Git, commit the result:

```
git add -A
git commit -m "Upgrade the project to format 2"
```

## 5. What the older versions do

Version 1.17.0 and 1.17.1 open a format 2 project read-only. The editor shows the banner *Read-only: this project was saved by a newer version of the tool, or is open in another window. You cannot change it here.* On the command line, with 1.17.1:

```
harness-design-studio generate wheel-link
```

```
error: this project is read-only (saved by a newer tool version).
```

The exit code is 2. `validate`, `check` and `drc` still read it; `validate` says:

```
WARNING newer_version: This project was saved by a newer version of the tool (format 2; this tool understands up to 1). It is opened read-only. [project.json]
```

The older versions were not tried apart from 1.17.0 and 1.17.1.

## 6. Go back

With Git, go back to the commit before the upgrade. Without Git, copy the files of `.migration-backup-v1/` back into the project folder, then delete `MIGRATION.json` and `journal.jsonl` from the project folder. The project is then in format 1 again, and 1.17.1 can edit it. The line `journal.jsonl merge=union` in `.gitattributes` can stay; it does nothing for a project without that file.

Next: [Use Git and CI](use-git-and-ci.md), [Override a value and keep a history](override-and-keep-a-history.md) (the change journal), [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md#this-project-is-in-format-1-older-than-this-tool-writes-format-2-so-nothing-was-saved)
