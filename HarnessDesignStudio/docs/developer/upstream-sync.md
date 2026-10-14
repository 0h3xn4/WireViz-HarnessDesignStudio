# Refresh the upstream WireViz README

This page shows how to bring this repository's copy of the WireViz README up to date when the WireViz project changes its own README, step by step, with commands that were run.

## Contents

- [What is kept where](#what-is-kept-where)
- [Before you start](#before-you-start)
- [1. Get the upstream file](#1-get-the-upstream-file)
- [2. See what changed](#2-see-what-changed)
- [3. Replace the untouched copy](#3-replace-the-untouched-copy)
- [4. Make the embedded block](#4-make-the-embedded-block)
- [5. Update the note](#5-update-the-note)
- [6. Check and commit](#6-check-and-commit)
- [Clean up](#clean-up)
- [What this does not cover](#what-this-does-not-cover)

## What is kept where

This repository is a fork of [wireviz/WireViz](https://github.com/wireviz/WireViz). The upstream project has no README at its root; its README is `docs/README.md`. Here that text is kept in two places, and it is never reworded.

| Where | What it is |
| --- | --- |
| `docs/upstream/README.upstream.md` | A **byte-identical** copy of upstream `docs/README.md`. Currently from commit `e4fe099` (2025-01-16, WireViz 0.4.1). Its relative links do not resolve in this folder, on purpose, so that it can be compared with upstream with `diff`. |
| `README.md` (repository root), between `<!-- BEGIN UPSTREAM README -->` and `<!-- END UPSTREAM README -->` | The same text with two changes: every heading is one level lower (`# WireViz` becomes `## WireViz`), and the relative links are rewritten for the new place (13 links: `../examples/...`, `../tutorial/readme.md`, `../LICENSE`, `syntax.md`, `CONTRIBUTING.md`, `buildscript.md`, `CHANGELOG.md`). Text inside code fences is left alone. |
| `README.md`, the sentence just above the begin marker | A note that says which upstream commit the text is taken from ("taken from `docs/README.md` at commit ..."). |

`docs/CONTRIBUTING.md` and `docs/CHANGELOG.md` at the root are WireViz's own files. The root has its own [`CONTRIBUTING.md`](../../../CONTRIBUTING.md) and [`CHANGELOG.md`](../../../CHANGELOG.md) for this repository, which is why the links to them are rewritten to `docs/...`.

## Before you start

- You have Git, Python 3 and a network connection. No upstream remote needs to exist. The commands below fetch by URL.
- Work on a branch, from the repository root. A scratch clone is the safest place to try this first.
- The checker `lychee` is installed ([`docs-maintenance.md`](docs-maintenance.md#check-the-links)).

## 1. Get the upstream file

```
git fetch --no-tags https://github.com/wireviz/WireViz.git master:refs/upstream-tmp/master
git rev-parse refs/upstream-tmp/master
git log -1 --format='%H %ad' --date=short refs/upstream-tmp/master
git show refs/upstream-tmp/master:src/wireviz/__init__.py | grep -n __version__
```

```
From https://github.com/wireviz/WireViz
 * [new branch]      master     -> refs/upstream-tmp/master
e4fe099f8c7b86736aee7b4227cc794b6e8b36f0
e4fe099f8c7b86736aee7b4227cc794b6e8b36f0 2025-01-16
4:__version__ = "0.4.1"
```

The first two lines of output are Git's; the next lines are the full commit, its date and the WireViz version. Write them down for step 5. (`--no-tags` keeps the upstream tags out of your repository.)

If you prefer a named remote: `git remote add upstream https://github.com/wireviz/WireViz.git` and `git fetch --no-tags upstream master`, then use `upstream/master` instead of `refs/upstream-tmp/master` below.

## 2. See what changed

```
git show refs/upstream-tmp/master:docs/README.md > /tmp/new.md
diff docs/upstream/README.upstream.md /tmp/new.md
echo "diff exit code: $?"
```

When upstream's README has not changed, there is no output from `diff` and the exit code is 0:

```
diff exit code: 0
```

Then stop. Only the note in step 5 might need a newer commit; leave it, because the text is still from the commit it names.

When there are differences, read them. Look for new relative links (`](something.md)` or `](../something)`), because step 4 only rewrites the 13 known kinds.

## 3. Replace the untouched copy

```
cp /tmp/new.md docs/upstream/README.upstream.md
cmp /tmp/new.md docs/upstream/README.upstream.md && echo identical
```

```
identical
```

Do not open the file in an editor that changes line endings or trailing spaces. It must stay byte-identical to upstream's.

## 4. Make the embedded block

Save this script as `mk_upstream_part.py` in any folder (it is not part of the repository). It reads the untouched copy, rewrites the links and lowers the headings. The headings inside code fences are left as they are; level 6 headings, which cannot go lower, stay at level 6 — look for those in the diff.

```python
"""Turn docs/upstream/README.upstream.md into the block embedded in the root README.md:
fix relative links for the new location (docs/ -> repository root) and demote headings one level."""

import re, sys

src = open(sys.argv[1], encoding="utf-8").read().splitlines()
out, fence = [], False
for line in src:
    if line.startswith("```"):
        fence = not fence
    if not fence:
        line = re.sub(r"\]\(\.\./(examples|tutorial)/", r"](\1/", line)
        line = re.sub(r"\]\(\.\./LICENSE\)", "](LICENSE)", line)
        line = re.sub(
            r"\]\((syntax|CONTRIBUTING|buildscript|CHANGELOG)\.md\)", r"](docs/\1.md)", line
        )
        if re.match(r"#{1,5} ", line):
            line = "#" + line
    out.append(line)
print("\n".join(out))
```

Save this second script as `splice_upstream.py`. It puts a block between the two markers and leaves the rest of the README alone:

```python
"""Replace the text between the upstream markers of a README with a block read from a file."""

import sys

readme, block = sys.argv[1], sys.argv[2]
begin, end = "<!-- BEGIN UPSTREAM README -->", "<!-- END UPSTREAM README -->"
text = open(readme, encoding="utf-8").read()
head, rest = text.split(begin, 1)
_, tail = rest.split(end, 1)
new = head + begin + "\n\n" + open(block, encoding="utf-8").read() + "\n" + end + tail
open(readme, "w", encoding="utf-8").write(new)
```

Run them from the repository root (use the folder where you saved the scripts):

```
python3 mk_upstream_part.py docs/upstream/README.upstream.md > /tmp/upstream_part.md
python3 splice_upstream.py README.md /tmp/upstream_part.md
git diff --stat
```

**Test the scripts first** on the unchanged copy: the splice must leave `README.md` exactly as it was. `git diff --exit-code README.md` prints nothing and exits with 0. This was checked on the current README before this page was written.

## 5. Update the note

Open `README.md` and find the sentence above `<!-- BEGIN UPSTREAM README -->`:

```
The text below is the README of [wireviz/WireViz](https://github.com/wireviz/WireViz), taken from `docs/README.md` at commit [`e4fe099`](https://github.com/wireviz/WireViz/commit/e4fe099f8c7b86736aee7b4227cc794b6e8b36f0) (2025-01-16, WireViz 0.4.1).
```

Change the short commit, the full commit in the URL, the date and the version to the values from step 1. Search the repository for the old short commit to catch every mention: `grep -rn e4fe099 --include=*.md .`. The audit page [`docs/DOCS_AUDIT.md`](../../../docs/DOCS_AUDIT.md) records the first sync as history; leave it.

## 6. Check and commit

1. No old-style relative link is left in the embedded block. This prints nothing when all is well:

   ```
   sed -n '/BEGIN UPSTREAM README/,/END UPSTREAM README/p' README.md | grep -n '](\.\./'
   ```

2. Every link in the root README resolves:

   ```
   lychee --offline --include-fragments --no-progress README.md
   ```

   A link that the scripts do not know (a new file in upstream's `docs/`) shows up here. Add its pattern to `mk_upstream_part.py` (and to this page), run steps 4 and 5 again.
3. The two files, and only these, changed: `git status --short` lists `README.md` and `docs/upstream/README.upstream.md`.
4. Commit both in one commit, with the upstream commit in the message.

Steps 1 to 4 and the check in step 6 were tested in a scratch clone of this repository, once with the real upstream file (no difference, `README.md` byte-identical) and once with an edited copy (a changed heading, a new section, a new `../examples/` link and a new link to another upstream document). The heading was lowered, the new `../examples/` link was rewritten, and `lychee` reported the link to the missing example file, as it should.

## Clean up

```
git update-ref -d refs/upstream-tmp/master
```

## What this does not cover

- Merging other upstream changes (`src/wireviz`, `examples/`, `tutorial/`, the other files in `docs/`). Those files belong to WireViz and are not edited here.
- The branch layout of WireViz. The upstream README mentions its own development branch, which this fork does not have; the text is kept as it is.

Next: [docs maintenance](docs-maintenance.md), [developer index](README.md)
