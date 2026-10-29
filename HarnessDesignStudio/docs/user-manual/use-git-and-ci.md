# Use Git and CI

This page shows how to keep a project in Git, how to check it after a merge, and how to run the whole build in a script or on a build server (CI, continuous integration: a server that runs your checks on every push).

## Contents

- [Before you start](#before-you-start)
- [1. Put a project in Git](#1-put-a-project-in-git)
- [2. After a merge](#2-after-a-merge)
- [3. Compare two checkouts](#3-compare-two-checkouts)
- [4. Run it in a script](#4-run-it-in-a-script)
- [5. Run it on a build server](#5-run-it-on-a-build-server)
- [Other helpers](#other-helpers)
- [Common mistakes](#common-mistakes)

## Before you start

- Git is installed (`sudo apt install git`).
- A project is a **folder of small JSON files**, written in a fixed format (sorted keys, the same bytes for the same design). So two people who edit different parts of the design (different devices, different parts, different config files) get a clean merge of those files, and a Git diff shows only real changes. The one file that does not merge cleanly is `generated/generation.json`, the record of the last Generate: it holds a hash of the whole design, so when both people ran Generate it conflicts every time. The command `harness-design-studio merge-fix` resolves exactly that conflict ([how](#when-generatedgenerationjson-conflicts)). The format is in [`FILE_FORMAT.md`](../FILE_FORMAT.md).

## 1. Put a project in Git

The project folder can be a repository, or a folder inside one. Example, with a practice project:

```
mkdir gitdemo && cd gitdemo
git init -b main .
harness-design-studio new design --template first-steps
git add -A
git commit -m "Start from first-steps"
```

The tool wrote a `.gitignore` inside the project (`design/.gitignore`). It ignores backup files (`*.bak`), lock files, temporary files and the recovery folders. It does not ignore `outputs/`. Decide for yourself whether the exports belong in the repository; the folder can always be made again. To leave them out, add `outputs/` to your own `.gitignore`.

`harness-design-studio new` also wrote a `.gitattributes` (`design/.gitattributes`, since version 1.9). It has one effect: Git treats `generated/generation.json` as a binary file, so a merge in which two people both pressed Generate stops on that file without writing conflict markers into it ([why and what to do](#when-generatedgenerationjson-conflicts)). Every other file stays text and merges line by line. A project made before 1.9 does not have the file: copy `ci/gitattributes` from the templates (`harness-design-studio templates my-templates`) to `design/.gitattributes`.

Work as usual, then commit. Generate once and commit the result:

```
harness-design-studio generate design
git add -A
git commit -m "Generate harnesses"
```

A second generation changes nothing:

```
harness-design-studio generate design
git status --short
```

```
0 added, 0 changed, 2 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
```

(No line from `git status`: nothing changed.) A real change shows as a real change. After setting `service_loop_m` from `null` to `0.1` in `design/config/generation.json`:

```
git diff
```

```
-    "service_loop_m": null,
+    "service_loop_m": 0.1,
```

Running `harness-design-studio generate design` then also changes `design/generated/generation.json`, because the model changed. Commit both before you go on.

**Who made the last change.** When the project folder is inside a Git repository, the **Revisions** area of the app shows a line with the last commit of that repository: who, when, its first line, the short id and the branch (since 1.4.0). The app reads the repository's own files; it does not run `git` and needs no network. It names the last commit of the whole repository, not of the project alone, and it does not see changes you have not committed yet. The change log of a harness (`harness-design-studio log`) stays the record of who reviewed, released or revised it.

## 2. After a merge

If Git stops on a conflict inside a project file, it leaves markers (`<<<<<<<`, `=======`, `>>>>>>>`) in the file. Resolve it like any text conflict. Then let the tool check the folder:

```
harness-design-studio check design
```

Before the conflict is resolved, this prints:

```
ERROR   merge_conflict: The file contains unresolved Git merge conflict markers. Resolve the conflict first. [generated/generation.json]
```

and exits with 1. Other errors may follow, because the broken file could not be read (for example unknown devices). After the fix:

```
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
3 devices, 2 interfaces, 13 connectors, 2 harnesses: 0 error(s), 0 warning(s).
```

`harness-design-studio check` does everything `harness-design-studio validate` does, and also finds merge markers and released harnesses that were edited after their release (`released_modified`).

### When `generated/generation.json` conflicts

When two people each pressed Generate on their own branch, the merge stops on `generated/generation.json` (the line `"input_hash"`), although the files they edited merged without a conflict. Nobody should edit that file by hand. One command lets the tool write the record again for the merged design:

```
harness-design-studio merge-fix design
git add -A
git commit
```

`merge-fix` first looks at which files of the project are in conflict, the files with conflict markers and the files Git still lists as unmerged (it reads the repository's own files; it does not start `git`). If the record is the only one, it keeps this branch's version of it, runs `generate` and then `check`, and prints what they print. If any other file is in conflict (for example both people changed the same line of a device), it refuses, names the files and changes nothing; resolve those yourself, then run it again. It writes nothing itself except that record; `generate` then writes what it always writes, and a harness that a person made by hand is never touched. If `generate` or `check` is blocked, the record is put back as it was found. When the merged design needs no new harness, `generate` prints `0 added, 0 changed, ... unchanged`; if it does, `generate` builds it and you commit those files too. `git add -A` is still yours to run: `merge-fix` does not change the Git index.

With the `.gitattributes` of a new project, the record is a valid JSON file during the conflict (our side, no markers), so `check` and the app can read the project and `verify` says that the record is out of date. Without it, the file holds the markers and `check` reports `merge_conflict` until `merge-fix` has run. `merge-fix` works the same way in both cases.

The same by hand (this is what `merge-fix` does):

```
git checkout --ours design/generated/generation.json
harness-design-studio generate design
harness-design-studio check design
git add -A
git commit
```

(`--theirs` works as well. Which side you keep hardly matters, because `generate` writes the record again from the merged design: it takes over only the *Why* texts of released harnesses and the number of the next harness from the side you keep.) `check` must end with `0 error(s)`.

Another way is to keep `generated/` out of Git (a line `generated/` in the `.gitignore` of the repository) and to run `generate` after every checkout. Then the record can never conflict, but it also holds the reasons that the Why tab shows and the number of the next harness, so each checkout starts those from what `generate` finds.

By design, a few other files can conflict when two people change them on two branches, and `merge-fix` leaves them to you: `changelog.json` and `baselines/` when two people release (keep both entries), `layout.json` (all positions of the diagram are in one file), `logical/links.json` (one file for all connections, numbered `L1`, `L2` ...: two people who each add a connection on their own branch both create the next number, so after the merge one of the two must be renumbered by hand), and the number of a new harness (two new interfaces get the same harness number on two branches; run `generate` after the merge and read what it says). Files in `outputs/`, if you keep them in Git, are made from the design: after a merge run `export` again, or leave the folder out of Git.

In the app, a project that changes on disk (for example after a `git pull`) shows "Project changed on disk" with **Reload** and **Keep my version**.

## 3. Compare two checkouts

```
harness-design-studio compare OLD NEW
```

lists what was added, removed and changed between two project folders, for example two checkouts of different commits. It changes nothing. Equal folders print `No differences.` The last line names what is not compared (the generation record, the contents of baselines and the files of the outputs folders). An example with output is in [change a released harness](change-a-released-harness.md#compare-two-copies-of-a-project).

## 4. Run it in a script

Every `harness-design-studio` command returns an exit code: **0** success, **1** the project has errors or a step is blocked, **2** a usage error or a project that cannot be read (a project with damaged files is refused with 2 by every command except `validate` and `check`, which list the damage and end with 1), **130** you pressed Ctrl-C. So `&&` stops at the first problem:

```
harness-design-studio validate design && harness-design-studio generate design && harness-design-studio drc design && harness-design-studio export design
```

The templates contain a ready script. Copy the templates and run it:

```
harness-design-studio templates my-templates
sh my-templates/ci/build.sh design
```

```
INFO    placeholder_config: Placeholder rule configuration still in use: derating, emc, generation, segmentation, segregation, titleblock. An engineer must review these before results are trusted.
3 devices, 2 interfaces, 13 connectors, 2 harnesses: 0 error(s), 0 warning(s).
0 added, 0 changed, 2 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
2 interfaces and 6 wires checked: 0 error(s)
34 files written to design/outputs (model 10dad18f5611).
2 interfaces and 6 wires checked: 0 error(s)
build ok: design/outputs
```

(This is the output for the project above, which was generated before. On a project that was never generated, the connectors line reads `9 connectors, 0 harnesses` and the next line reads `2 added`. The model hash differs from project to project.)

The script runs `check`, `generate`, `verify`, `drc` (it stops if there are unwaived errors), `export` and `verify --outputs`. It ends with `build ok`.

Importing interfaces is not part of a script: it works in the app only ([import data](import-data.md)).

## 5. Run it on a build server

`my-templates/ci/github-actions.yml` is a GitHub Actions workflow that does the same on every push, including the `harness-design-studio drc` step (it fails the build when an error is not waived and keeps `drc-report.md` as a download). Copy it to `.github/workflows/` in your design repository. It expects the `.deb` package of the tool in the repository (under `tools/`), installs it, runs the checks and keeps `design/outputs` as a download. Change the folder name `design` and the package path to match your repository. The build server needs no network access to the tool itself, because the tool never uses the network.

This file was not run on a build server for this page. The `ci/build.sh` script was run (above).

## Other helpers

- `harness-design-studio migrate design` upgrades a project saved by an older tool version (the originals are kept). On a current project it says `Already up to date.`
- `harness-design-studio schema design/schemas` writes JSON Schemas of the project files, for editors that complete and check JSON. The command tells you how to use them in VS Code.
- `design-review-checklist.md` in the templates is a list for the person who releases a harness.

## Common mistakes

- **Merging by taking one side of a whole file.** Check with `harness-design-studio check` afterwards.
- **Editing a released harness in an editor.** The check reports it. Start a new revision instead ([change a released harness](change-a-released-harness.md)).
- **Committing the lock file.** `.harness.lock` is ignored by the `.gitignore` the tool writes. If you copied the project without it, add the lines yourself.
- **CI fails with exit code 1 and the drc report.** There are unwaived errors. The report says which.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md), [`CLI.md`](../CLI.md).

Next: [release a harness](release-a-harness.md), [user manual index](README.md)
