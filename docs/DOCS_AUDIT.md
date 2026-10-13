# Documentation audit

This page records what was found when the documentation of this repository was audited, what was changed because of it, and what was left alone. It was written before the fixes; the **Status** column was filled in at the end.

- Audit date: 2026-10-10. Branch `docs-audit`, taken from `master` at the merge of PR 38.
- Next: the [documentation index](README.md) shows the result.

## Contents

1. [Summary](#1-summary)
2. [What this repository is](#2-what-this-repository-is)
3. [Findings](#3-findings)
4. [Jargon](#4-jargon)
5. [Findability: clicks from the front page](#5-findability-clicks-from-the-front-page)
6. [Changes made to the upstream README](#6-changes-made-to-the-upstream-readme)
7. [Deferred, and decisions for the owner](#7-deferred-and-decisions-for-the-owner)

## 1. Summary

| | Count |
| --- | --- |
| Findings in the table below | 74 |
| High (a reader is blocked, misled, or a status statement is false) | 12 |
| Medium | 27 |
| Low | 35 |
| Terms a newcomer meets without an explanation | 163 (94 never explained, 69 explained late, partly, or in two senses) |

How it was done:

- **Clean install.** A fresh Python virtual environment, `pip install "HarnessDesignStudio[gui]"` from the source tree, then every command of the README and `GETTING_STARTED.md` was run in an empty folder and the output compared with the quoted output. Python 3.13 was used; the docs ask for 3.12 or newer. **Result:** the install works and the quick start works. Everything in the tutorial matched except one number (8 connectors; the tool prints 9) and one outdated sentence about wire colour. Nothing failed to run.
- **Not testable in this session** (so not checked, not guessed): the `.deb` and `.tar.gz` installs, the packaged `--selftest`, the GUI itself, KiCad, the CI artifact, and the files attached to the `v0.1.0` release page.
- **Link check.** An offline pass over all 117 Markdown files (relative links, images, anchors). One broken link existed (`docs/README.md`, `../../../releases`, which only works inside the GitHub web page). The repository's own tests already keep the rest of the tool's links intact. External links get a separate online pass at the end ([section 7](#7-deferred-and-decisions-for-the-owner)).
- **Screenshots** were re-rendered offscreen with the repository's own scripts and compared pixel by pixel with the committed ones.
- **Compliance counts** were recomputed from the CSV and JSON files.

The five things that matter most:

1. **The docs describe `master`, but `0.1.0` is what people can download.** Five examples (`minimal-satellite`, `flatsat`), the wiring-diagram drawing, wire colours and `design-worksheet.md` are described as part of "version 0.1.0". The changelog says they are not in the 0.1.0 packages, and `harness --version` prints `0.1.0` on both. A reader who installs the release gets `Unknown template 'minimal-satellite'`.
2. **No page shows the shape of a `config/*.json` file.** Every key is documented, none with the `values` wrapper the files need. Following the page literally gets the file quarantined and reset to placeholders.
3. **Status statements contradict each other.** `DEVIATIONS.md` says "No waiver has been granted by anyone" above fourteen waivers; `AUDIT.md` says "six independent reviewers" where no independent review exists; the release document says the engineering values were supplied when they were not.
4. **The front page is the WireViz README.** There was no root `README.md`; GitHub showed `docs/README.md` (WireViz's README with a short preface). The tutorial, user guide, FAQ and examples were each two clicks away and the examples folders were linked from nowhere.
5. **Terms are not explained.** `RS-422`, `CAN`, `Micro-D`, `EMC`, `derating`, `BOM`, `pinout` and 150 more appear before any explanation, and there was no glossary page.

## 2. What this repository is

| Question | Answer | How it was found |
| --- | --- | --- |
| Is it a fork? | Yes. It is a fork of [wireviz/WireViz](https://github.com/wireviz/WireViz). | `git log` begins with WireViz's first commit of 2020-05-20; the upstream `src/wireviz`, `docs/`, `examples/` and `tutorial/` are all here. |
| Which upstream commit? | `e4fe099` (2025-01-16, "Use ubuntu-latest for the supported Python versions (#442)"), WireViz version 0.4.1. | `git fetch` of upstream `master`; `git merge-base` with this repository's `master` is that commit, so nothing upstream is missing and nothing upstream was changed. |
| Is there an `upstream` remote? | No. Only `origin`. The upstream commit above was fetched by URL without adding a remote. | `git remote -v`. |
| What did Claude build on top? | A second, separate tool, **Harness Design Studio**, in `HarnessDesignStudio/` (clean-room: no WireViz code copied or imported, decision D-01), a CI workflow `.github/workflows/harness-ci.yml`, and a preface in `docs/README.md`. | `git diff e4fe099..master --stat -- . ':!harness'` shows three files: the workflow, `.gitignore`, `docs/README.md`. |
| Where was the upstream README? | `docs/README.md` (upstream has no root README either). It was byte-identical to upstream from line 29 on; lines 1–28 were the preface. | `git diff`. |
| Default branch | `master` (there is no `main`). The pull request for this audit targets `master`. | `git ls-remote`. |

The tool's own documents live in `HarnessDesignStudio/docs/` (upper-case names such as `GETTING_STARTED.md`). Tests in `HarnessDesignStudio/tests/test_docs.py` and `test_docs_links.py` run the commands of `README.md` and `GETTING_STARTED.md`, check the model hash quoted there, and check every link and anchor in those files. New pages for the tool were therefore added there, in the same style, instead of under the lower-case names a first reading of the task suggests (`faq.md` next to `FAQ.md` would also collide on Windows and macOS file systems). See the mapping in the [index](README.md).

## 3. Findings

Severity: **high** = a reader is blocked or misled, or a status statement is false; **medium** = wrong or missing but a reader can work around it; **low** = polish.
Status: **fixed**, **partly** (explained in the note), **deferred** (see [section 7](#7-deferred-and-decisions-for-the-owner)), **kept** (judged correct as is).

Paths: bare names such as `INSTALL.md` are in `HarnessDesignStudio/docs/`; `README.md` alone is `HarnessDesignStudio/README.md`.

### 3.1 Version and status

| ID | File | Problem | Sev. | Planned fix | Status |
| --- | --- | --- | --- | --- | --- |
| V1 | `README.md:24,83`, `GETTING_STARTED.md:15-27`, `LEARNING_PATH.md`, `FLATSAT_EXAMPLE.md`, `FAQ.md`, `INSTALL.md`, front page | Features that are only on `master` (examples `minimal-satellite` and `flatsat`, `design-worksheet.md`, the wiring-diagram drawing with wire colours, *Edit > Wire colours*) are described as part of version 0.1.0. The released 0.1.0 packages have three examples. `harness --version` prints `0.1.0` for both. | high | Say "newer than the 0.1.0 packages" wherever such a feature is introduced, give the `git ls-tree` check, and explain how to tell which one you have. The version number itself is not changed (code). | fixed (the version bump is deferred) |
| V2 | `INSTALL.md:30`, `compliance/SIGNOFF.md:43` | The install path relies on packages attached to the GitHub release; the sign-off says attaching them is up to the owner. Could not be checked here. | medium | State in `INSTALL.md` where the packages come from and that the build-from-source route needs no release assets. Ask the owner to attach them. | partly (owner action) |
| V3 | `compliance/DEVIATIONS.md:3,39` | Header says "No waiver has been granted by anyone"; T-18 to T-31 are waivers granted by the owner. Line 39 says "Fourteen granted … without a stated reason" but lists 13 and 12 of them do state a circumstance. | high | Correct the header and the counting sentence. Nothing else in the file is changed. | fixed |
| V4 | `compliance/docs/SRelD.md:9,10,16` | 5.1 points at the *Unreleased* changelog section, which is not in 0.1.0. The list of known problems says derating, EMC and approved parts were "supplied by the owner (D-11, D-12)"; they were not. Line 16 says the UX improvements are "planned after this audit"; they are done. | high | Point 5.1 at the `0.1.0` section; say the values were not supplied; link to `SIGNOFF.md` and `DEVIATIONS.md`. | fixed |
| V5 | `AUDIT.md:3,31,40` | "six independent reviewers" (no independent review exists: `README.md:5`, T-20, `SIGNOFF.md:22`). Still treats Ubuntu 22.04 as a target and lists waived items as "still needed". | high | Add a banner marking it a historical record of 2026-10-07; correct "independent". | fixed |
| V6 | `README.md:5`, front page `:19` | The "created mainly by an AI, not independently reviewed" notice exists as two prose copies with different wording; the evidence files are named in code spans, not links. | medium | One text in `HarnessDesignStudio/README.md#status`; the root README links to it; real links to the evidence. | partly (the root README has a short statement and real links; the long notice stays in `HarnessDesignStudio/README.md`) |
| V7 | `CLAUDE.md:6` | The status paragraph repeats the release and open-decision text three times. | medium | Left as is. `CLAUDE.md` is the coding assistant's instruction file; the owner maintains it. Listed for the owner. | deferred |
| V8 | `compliance/SUMMARY.md:56`, `compliance/docs/SRS.md:3`, `SECURITY.md:23` | Counts out of date: 89 modules / 74 reached (CSV: 94 / 79), 65 requirements (78), 9 packages (10 scanned, 11 in the SBOM report). | medium | Correct to the recomputed numbers, or remove the number and cite the report that owns it. | fixed (also `SPAMR.md`, `SVR.md`, `SDD.md`) |
| V9 | `compliance/SUMMARY.md:26` vs `:38` | 347 versus 344 rows for ECSS-Q-ST-80C, unexplained (3 rows were deleted from the standard's table). | low | Add a footnote. | fixed |
| V10 | `compliance/RISK_REGISTER.md:11,12,17,18,19,23` | Six table rows have 9 cells in a 10-column table; the waiver text lands in the "owner" column and Status is empty. | medium | Add the missing cell separator. | fixed |
| V11 | `compliance/docs/SECURITY_DOCS.md:9` | Says dependency vulnerabilities are checked by a person at each release; D-134 and `RELEASE.md` 8a say the scan is automatic. | low | Align with D-134. | fixed |
| V12 | `RELEASE.md:3,19-21`, `compliance/SIGNOFF.md:10` | Two different "14"s: "step 14" is the owner sign-off, "14 steps" are the automated checks. The intro omits step 15. Waiver history is embedded in the procedure. | medium | Add the missing statement about step 15 and a sentence separating the two uses of "14". Renumbering is not done (the numbers are quoted in `DEVIATIONS.md`, the evidence reports and `tools/release_check.py`). | partly |
| V13 | `RELEASE.md`, `HOWTO.md`, `GETTING_STARTED.md` Part 9 | "Release" means two things (releasing a harness; releasing the tool). | low | One-line disambiguation at the top of `RELEASE.md` and in the index. | fixed |

### 3.2 Accuracy against the program

| ID | File | Problem | Sev. | Planned fix | Status |
| --- | --- | --- | --- | --- | --- |
| A1 | `CONFIG.md` (all tables), `HOWTO.md:109-110`, `FILE_FORMAT.md:7` | No page shows the file shape `{"name", "placeholder", "values": {…}}`. Putting a key at the top level gets `ERROR quarantined: … Extra inputs are not permitted` and the file reverts to the placeholder (reproduced). | high | A worked example of `config/derating.json` at the top of `CONFIG.md`; fix the recipe in `HOWTO.md`. | fixed |
| A2 | `GETTING_STARTED.md:48` | Quotes "8 connectors"; the real `harness validate wheel-link` prints 9. | medium | Change to 9. | fixed |
| A3 | `GETTING_STARTED.md:174` | "colour and length say `n/a`" is outdated since the wiring-diagram drawing (D-141): unset wires are grey and the colour is not an open question. The tutorial never mentions *Edit > Wire colours*. | medium | Correct the sentence; add an optional step for colours. | fixed |
| A4 | `GETTING_STARTED.md:57,172`, `docs/img/block-diagram.png` | The editor screenshot predates the new diagram; `block-diagram.png` carries the stamp `harness-tool 0.1.0rc4 model 39697e3c467b` (old name, old version, a different hash from the tutorial's `8a25f0c99a86`). | medium | Re-render both from the tutorial project. | fixed |
| A5 | `CHEATSHEET.md:8-13` | "The loop" starts at `--template blank`, but the command line cannot add units; `generate` finds 0 interfaces and `export` fails with "no harnesses to export". | medium | Start the loop from `first-steps` and say units are added in the app. | fixed |
| A6 | `INSTALL.md:31,43` | Says the CI artifact holds a `SHA256SUMS` file. The workflow never runs the script that writes it. | medium | Reword: compute and compare the checksum yourself; point to the checksums recorded in the repository. The CI change is deferred. | partly |
| A7 | `INSTALL.md:93-96,127` | `harness-design-studio --selftest` exists only in the packaged build; from source, `harness-gui --selftest` ignores the flag and starts the GUI. The section reads as valid for every route. | medium | State that it applies to routes A and B; give the source-route check. | fixed |
| A8 | `PLACEHOLDERS.md:10` | Segmentation default is described as "per connector pair, merge within a zone". The default is `per_connector_pair`; zone merging is the separate mode `per_zone_pair`. | medium | Correct. | fixed |
| A9 | `HOWTO.md:147` | The harness-release recipe is always blocked by the placeholder and unapproved-parts gates unless the two `--accept-…` options are given; the recipe does not say so. | low | Add the gate sentence. | fixed |
| A10 | `CHEATSHEET.md:34-35` | `--comment "why"` is rejected (minimum 10 characters). | low | Use a valid comment in the example. | fixed |
| A11 | `CHEATSHEET.md:18-26,60-70` | Omits `harness templates`, `compare`, `schema`, `library`, `migrate` and the `baselines/` folder. | low | Add `templates` and `baselines/`; point to `CLI.md` for the rest. | fixed |
| A12 | `HOWTO.md:47` | "Give it a short ID and a name": adding a unit opens no dialog; ID and name are automatic. | low | Correct. | fixed |
| A13 | all newcomer docs | The app's *File > New project from an example…* and *File > New project…* are not described. | low | One line in `GETTING_STARTED.md` Part 1. | fixed |
| A14 | `GETTING_STARTED.md:65` | "Red is power, blue is data": true in the light theme only (dark theme: yellow-green and cyan). | low | Reword; point to the key under the diagram. | fixed |
| A15 | `GETTING_STARTED.md:138` | The to-do text is quoted wrongly ("confirm auto-filled connectors"). | low | Quote the real text. | fixed |
| A16 | `GETTING_STARTED.md:246` | `import-parts` output is shortened. | low | Quote the full last line. | fixed |
| A17 | `GETTING_STARTED.md:157-164`, `OUTPUTS.md:9-21` | The output table does not say it lists main files only; `system/provenance.json` is missing from the tree. | low | Mark "main files"; add `provenance.json`. | fixed |
| A18 | `CONCEPTS.md:101`, `HOWTO.md:138` | "SVG and PDF, A3 and A4": only the A3 sheets are exported as SVG. | low | Correct. | fixed |
| A19 | `FILE_FORMAT.md:7` | Config list omits `generation.json` (seven files exist). | low | Add. | fixed |
| A20 | `CONFIG.md:3,48-49` | "Every file has `placeholder: true`": `naming.json` ships `false`. The seven `naming` keys are not named. | low | Correct; list the keys. | fixed |
| A21 | `PLACEHOLDERS.md:5-11`, `OUTPUTS.md:1`, `FILE_FORMAT.md:49-155` | `generation.json` has no row in the first table. Headings use milestone names ("M3", "M5") that a newcomer cannot decode. | low | Add the row; replace milestone labels by what they cover. | fixed |
| A22 | `KICAD.md:11-17` | "Try it" uses a bare path; never says to run `harness templates` first nor to rerun without `--dry-run`. | low | Show the full steps. | fixed |
| A23 | `LEARNING_PATH.md:40,50,94-95` | "power control unit" (the unit is `PCDU1`, "Power distribution unit 1"); `harness diff … --from A --to B` fails until B is released. | low | Correct both. | fixed |
| A24 | `FLATSAT_EXAMPLE.md:77` | `per_connector_pair` "gives one harness for every interface": it gives one per pair of unit connectors (here 44). | low | Correct. | fixed |
| A25 | `IMPORTS.md:7-8`, `LEARNING_PATH.md:70`, `GETTING_STARTED.md:279` | Importing interfaces is app only; this is not stated where CI users would look. | low | Add "(app only)". | fixed |
| A26 | `templates/README.md:8,9`, `design-worksheet.md` | `approved-parts.csv` has a D-sub row and three approved parts; `signal-map.csv` changes nothing for the shipped netlist; the worksheet's example rows name zones and IDs that differ from `minimal-satellite`. | low | Correct the README lines. The worksheet is a template file (shipped in the package); listed for the owner. | partly |
| A27 | `INSTALL.md:129` | Quotes the wrong `install.sh` error text. | low | Quote the real one. | fixed |
| A28 | `RULES.md:19-20` | "choose a larger gauge" is ambiguous: a thicker wire is a lower AWG number, and the tool picks the highest AWG number first. | medium | The rule text is generated from code; deferred. Noted in the glossary entry for *AWG*. | deferred |

### 3.3 Structure, duplication and records

| ID | File | Problem | Sev. | Planned fix | Status |
| --- | --- | --- | --- | --- | --- |
| S1 | `ARCHITECTURE.md:3,21-42` | Claims the layout "matches the code". It lists directories that do not exist (`core/library/`, `core/config/`, `core/commands/`, `core/explain/`, `core/imports/`, `core/verify/`) and omits about 20 real modules. | high | Replace section 2 by the real layout; point to the generated component table. | fixed |
| S2 | `ARCHITECTURE.md:48-63,82` | Project folder layout differs from `FILE_FORMAT.md` and a real project (`changelog.jsonl` vs `changelog.json`, plural library file names, `generated/` including outputs). A `stress` golden project is named that does not exist. | medium | Delete the copy, link to `FILE_FORMAT.md`. | fixed |
| S3 | `guide/USER_GUIDE.md:47,69,41,117` | "three practice projects" above a table of five; the dialog is said to offer three; two "section N" cross references are wrong. | medium | Correct; use anchors. | fixed |
| S4 | `guide/USER_GUIDE.md:201-212`, `CHEATSHEET.md:48-57` | Shortcut tables omit six shortcuts the app defines (Ctrl+N, Ctrl+O, Ctrl+Shift+S, Ctrl+Shift+I, Ctrl+Q, Ctrl+Shift+Z). | low | Complete both tables. | fixed |
| S5 | `guide/USER_GUIDE.md` | Menu items that exist and are described nowhere: Add zone, Open the sample project, Save as, Dark theme, minimap, Replay the tour, Glossary, Delete harness. | medium | A menu table. | fixed |
| S6 | `guide/USER_GUIDE.md:163,167` | The in-app guide (the only document installed with the tool) points to files that are not installed (`docs/PLACEHOLDERS.md`, `ci/build.sh`). | low | Name the in-app route (`harness config DIR`, `harness templates`) as well. | fixed |
| S7 | `UX.md`, `UX_GUIDELINES_REVIEW.md:34` | Design records not marked as superseded: letter chips (replaced by pictograms, D-140), "wire colours never used as drawing colours" (D-141), "no auto layout / no minimap" listed as open (both exist), test counts that are wrong. | medium | Add a banner; correct the three rows. | fixed |
| S8 | `docs/ux/qt/01–07, 12, 13`, `docs/ux/screens/*` | Nine editor screenshots predate D-140 (3–5.6 % of pixels differ); 14 prototype screenshots are history with the same file numbers in a second folder. | medium | Re-render the nine with `tools/gui_screenshots.py`; add a README to `ux/screens/`. | fixed (`screens/` kept and labelled as history) |
| S9 | `compliance/` | 21 process documents, `DEVIATIONS.md`, `SIGNOFF.md`, `OPEN_ACTIONS.md`, `RISK_REGISTER.md` have no inbound link; only `SUMMARY.md` is linked. | high | `HarnessDesignStudio/compliance/README.md` as an index; link from the status section and the docs index. | fixed |
| S10 | `CHANGELOG.md` | Zero inbound links. | medium | Link from the root README, the tool README and the index ("What's new"). | fixed |
| S11 | `docs/README.md` (front page), repo root | No root `README.md`; GitHub showed the upstream README. A newcomer clicking `examples` or `tutorial` at the root gets WireViz material, and the tool's example projects are linked from nowhere. | high | New root `README.md` (see [section 6](#6-changes-made-to-the-upstream-readme)); examples page. | fixed |
| S12 | `HarnessDesignStudio/docs/README.md` | Mixes user documents and internal records on one page; the five examples are not listed there. | medium | Rebuild as the tool's index, grouped, with a separate "Project records" group. | fixed |
| S13 | `INSTALL.md`, `README.md`, `USER_GUIDE.md`, `HOWTO.md`, `FAQ.md`, `CLAUDE.md` | Install steps, the PATH fix, the Qt library line and four troubleshooting tables are copied across files. | medium | `INSTALL.md` owns installation, `FAQ.md` and the new `TROUBLESHOOTING.md` own runtime problems; the others link. | partly |
| S14 | `CLI.md` vs `USER_GUIDE.md`, `CHEATSHEET.md`, `CLAUDE.md` | Four hand-copied command lists. | low | `CLI.md` is the single source; no copy was found to be wrong, so the copies stay and the cheatsheet links. | kept |
| S15 | `CLI.md:285` | Generated row with an unescaped vertical bar in the text of one option: it renders as a broken table row. The cause is in `tools/gen_cli_docs.py`. | medium | Code change; deferred. | deferred |
| S16 | `PLAN.md`, `OPEN_DECISIONS.md` | Plan and open decisions are written as of the audit; they plan Windows CI and a PDF guide that were never built. | low | Banner "historical" at the top. | fixed |
| S17 | `HOWTO.md`, `docs/…` | Cross references by number ("section 15", "Part 7") and `docs/…` code spans instead of links. | low | Replace by anchors in the pages touched. | partly |
| S18 | `docs/demos/`, `docs/usability/` | Linked as bare folders; no index sentence. | low | Short README in `demos/`. | fixed |
| S19 | `tools/` | No README; `CLAUDE.md` names about 20 of 30 scripts. | low | A table in `developer/`. | fixed |
| S20 | `DECISIONS.md:147` | A blank line inside the table split it: the rows D-138 to D-141 rendered as plain text (found by the render check). | low | Remove the blank line. | fixed |

### 3.4 Missing pages (completeness)

| ID | Missing | Sev. | Fix | Status |
| --- | --- | --- | --- | --- |
| C1 | Root `README.md` | high | Written (fork layout). | fixed |
| C2 | Glossary | high | `HarnessDesignStudio/docs/GLOSSARY.md`. | fixed |
| C3 | Troubleshooting page with real errors | high | `HarnessDesignStudio/docs/TROUBLESHOOTING.md`, from the clean-install run. | fixed |
| C4 | Task-oriented manual, one page per workflow | medium | `HarnessDesignStudio/docs/user-manual/`. | fixed |
| C5 | One page listing every example with how to run it and the expected output | medium | `HarnessDesignStudio/docs/examples/README.md`. | fixed |
| C6 | Tips and integration page | medium | `HarnessDesignStudio/docs/TIPS.md`. No integration with the owner's other tools exists in the code; the page says so and describes the file exchange that does exist. | fixed |
| C7 | `CONTRIBUTING.md` for people, developer docs, a way to refresh the upstream README | medium | Root `CONTRIBUTING.md`, `HarnessDesignStudio/docs/developer/`. | fixed |
| C8 | Root `CHANGELOG.md` | low | A short pointer file: the tool's and upstream's changelogs are separate. | fixed |
| C9 | A current picture of the Harness plans tab, the generate preview, the release dialog and the wire-colours dialog | low | Needs the GUI; the screenshot script covers other screens. | deferred |

### 3.5 Upstream (WireViz) documents

Upstream's own `docs/*.md`, `tutorial/` and `examples/` were not edited. Observations:

| ID | Observation | Sev. | Status |
| --- | --- | --- | --- |
| U1 | The upstream README says `git checkout dev` for the development version; this fork has no `dev` branch, and upstream's own branch layout is not ours to document. | low | kept (verbatim) |
| U2 | The upstream README says WireViz needs Python 3.7 or later; the tool in `HarnessDesignStudio/` needs 3.12. The two are separate installs (`pip install -e .` at the root installs WireViz; `pip install -e "HarnessDesignStudio[gui]"` installs the tool). | medium | explained in the root README and `developer/` |
| U3 | The upstream README links `../examples/…`, `syntax.md`, `CONTRIBUTING.md`, `buildscript.md`, `CHANGELOG.md`, `../tutorial/readme.md`, `../LICENSE`. All broken once it sits at the repository root. | high | fixed in the embedded copy ([section 6](#6-changes-made-to-the-upstream-readme)) |
| U4 | Upstream's `docs/CONTRIBUTING.md` and `docs/CHANGELOG.md` are WireViz's; the root had neither a tool `CONTRIBUTING.md` nor a `CHANGELOG.md`. | low | root files added, upstream's untouched |

## 4. Jargon

163 terms were collected. How they break down:

| | Terms |
| --- | --- |
| Never explained in any newcomer document | 94 |
| Explained only in the app's glossary or in the code | 6 (pinout, derating, twisted pair, splice, cross-strap, spare pin) |
| Explained only in developer documents | 2 |
| Explained, but after the reader first meets them | 31 |
| Only a hint at first use | 25 |
| Used with more than one meaning | 5 (zone, bundle, cable, sleeving, category) |

What a newcomer meets first and is never told: *reaction wheel*, *deviation / waived by the owner*, *pinout*, *BOM*, *continuity and isolation tests*, *RS-422*, *RS-485*, *CAN*, *Micro-D*, *SMA*, *RF*, *derating*, *EMC*, *CI*, *solar array*. The first command output of the tutorial lists six configuration names (`derating`, `emc`, `generation`, `segmentation`, `segregation`, `titleblock`) that are not yet explained.

Other findings:

- *waive* has two senses (accept a warning in the tool; "waived by the owner" for a process deviation) and *baseline* has two (a release snapshot; the starting standards). Both are explained in the glossary.
- The power unit has five names in the docs (power unit, power control unit, PCDU, main power distribution, PDU).
- *Cable* is used loosely against *harness* and never defined.
- ICD, AIT, NCR and VCM, which were named in the task, are used by the tool's documents only in `SPEC.md` and `compliance/`; VCM does not occur at all. ICD, AIT and NCR have glossary entries. VCM was left out because nothing in the repository uses it and its meaning here is not stated.
- Entries marked "standard meaning" in the glossary come from general engineering knowledge, not from this repository. **An engineer should check them.**

Fix: first-use explanations in the README, a glossary at `HarnessDesignStudio/docs/GLOSSARY.md` linked from every index, and the early pages (README, INSTALL, GETTING_STARTED, CONCEPTS) link the first use of each hard term.

## 5. Findability: clicks from the front page

Before: the front page was `docs/README.md` (the WireViz README with a short preface).

| Goal | Before | After |
| --- | --- | --- |
| Install | 1 click | 1 click |
| First result | 1 click (recipe) or 2 (tutorial; not linked from the front page) | 1 click (recipe in the root README), 1 click (tutorial) |
| User manual | 2 clicks, not linked from the front page, no document called a manual | 1 click ("User manual") |
| Examples | 1–2 clicks for the list, 5 or more for the folders (linked from nowhere) | 1 click (examples page, with links to every example folder) |
| Troubleshooting | 2 clicks | 1 click |
| What changed | not reachable | 1 click |
| Status, limits, waivers | not clickable (code spans) | 2 clicks (root README → status → compliance index) |

## 6. Changes made to the upstream README

The upstream README is kept in two places and is not reworded.

- `docs/upstream/README.upstream.md`: **byte-identical** to `docs/README.md` of `wireviz/WireViz` at `e4fe099`. Because it sits one folder deeper than upstream's copy, its relative links do not resolve there; it is excluded from the link check on purpose, so that it can be diffed against upstream.
- The block between `<!-- BEGIN UPSTREAM README -->` and `<!-- END UPSTREAM README -->` in the root `README.md` is that file with exactly these changes:

| Change | Reason |
| --- | --- |
| Every heading goes down one level (`# WireViz` becomes `## WireViz`, …); 13 relative links change in all (the rows below) | The root README has one `#` heading of its own and the upstream part sits under `# Original WireViz README`. |
| `](../examples/…` becomes `](examples/…` (6 links: `demo01.yml`, `demo01.png`, `demo01.bom.tsv`, `demo02.png`, `demo02.yml`, `demo02.bom.tsv`) | Path changes because the file moves from `docs/` to the root. |
| `](syntax.md)` becomes `](docs/syntax.md)` | Same. |
| `](../tutorial/readme.md)` becomes `](tutorial/readme.md)`; `](../examples/readme.md)` becomes `](examples/readme.md)` | Same. |
| `](CONTRIBUTING.md)` becomes `](docs/CONTRIBUTING.md)` | Same; the root now has its own `CONTRIBUTING.md` for this tool, so the link has to be explicit. |
| `](buildscript.md)` becomes `](docs/buildscript.md)` | Same. |
| `](CHANGELOG.md)` becomes `](docs/CHANGELOG.md)` | Same; the root now has its own `CHANGELOG.md`. |
| `](../LICENSE)` becomes `](LICENSE)` | Same. |

How to refresh it after an upstream change: [`HarnessDesignStudio/docs/developer/upstream-sync.md`](../HarnessDesignStudio/docs/developer/upstream-sync.md).

The old `docs/README.md` (the WireViz README plus the preface) became the documentation index. Its preface text was moved into the root README. No other upstream file was edited.

## 7. Deferred, and decisions for the owner

**Needs a decision or an action from you**

1. **Version.** `master` and the released 0.1.0 both print `0.1.0`. Cut 0.1.1 (or 0.2.0) so that docs and packages agree, or keep the "newer than 0.1.0" notes. Until then the notes are in the docs.
2. **Release page.** Attach the `.deb`, the `.tar.gz` and the checksums to the `v0.1.0` release if that has not been done (the sign-off says it is up to you). Could not be checked here.
3. **Licence.** The repository `LICENSE` is GPL-3.0 (WireViz's). Decision D-02 leaves the licence of `HarnessDesignStudio/` open and the package metadata says `LicenseRef-Proprietary`. The root README says exactly that and nothing more. A licence text needs your choice.
4. **Your other tools.** The README names no integration with SpaceMissionStudio, Requirements Studio, Budget Studio, AIT Logbook or ICD Studio, because the code has none. `TIPS.md` lists the file formats that could carry data between tools; anything that needs a real exporter or importer is written as a suggestion, not a feature. Tell me what exchange you intend and I will document it once it exists.
5. **Glossary check.** Entries marked "standard meaning" were not taken from the repository; an engineer should read them.
6. **Compliance records.** Only factual corrections were made (counts, a header that contradicted its own table, a statement that engineering values were supplied, malformed table rows). Wording that records your decisions or sign-offs was not rewritten.
7. **Screenshots.** The harness plans tab, the generate preview, the release dialog and the wire-colours dialog have no current picture; they need the GUI.

**Not done because the task is documentation only** (code, tests, CI, generated files)

| Item | Where |
| --- | --- |
| An unescaped vertical bar in a generated table row | `tools/gen_cli_docs.py` (S15) |
| "choose a larger gauge" wording | rule texts in code (A28) |
| `SHA256SUMS` not produced in the CI artifact | `.github/workflows/harness-ci.yml` (A6) |
| A test for table shape and for the quoted output lines of the tutorial | `tests/` |
| A test that fails when the editor screenshots are stale | `tools/release_check.py` |
| Renumbering the release checklist | `RELEASE.md`, `tools/release_check.py`, the evidence reports |
| `design-worksheet.md` row IDs | a template file shipped in the package (A26) |
| `CLAUDE.md` status paragraph, and the missing note that ruff formats Markdown code blocks | the assistant's instruction file (V7) |

**Link checks**

| Check | Result |
| --- | --- |
| Offline (`lychee --offline --include-fragments --exclude-path compliance/requirements --exclude-path docs/upstream '**/*.md'`) over every Markdown file | 1,630 links, 0 errors |
| Own checker for tables and fences, and a render with a Markdown parser | no broken tables or fences in the changed pages (one existing table in `DECISIONS.md` was repaired, S20) |
| `test_docs.py` and `test_docs_links.py` | 48 passed |
| Whole test suite (`pytest`, from `HarnessDesignStudio/`) | 1025 passed, 1 skipped |
| `ruff format --check`, `ruff check`, `mypy` | clean. Note: ruff also formats the Python code blocks inside Markdown files, so a code block in a document can fail the lint step of CI; the developer pages say so. |
| External links, online | **Not completed.** The sandbox this work was done in blocks most outside hosts (4 of 227 links answered). The pages written for this audit contain 8 external URLs: the upstream repository, its commit `e4fe099`, the lychee releases page, the repository's own CI page and badge, `kicad.org`, and the repository's clone URL. The repository, the commit and the lychee release were reached with `git` and a download; the badge, the Actions page and `kicad.org` were not. Run `lychee --no-progress '**/*.md'` from a normal machine to check them (the upstream part of the root README has about 180 more, which are WireViz's own). |

Next: the [documentation index](README.md).
