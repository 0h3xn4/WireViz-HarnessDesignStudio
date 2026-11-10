# Legal audit of Harness Design Studio

Date of this audit: 2026-11-09. Repository state: `master` at commit `0cc13bb` (version 1.17.0 in `pyproject.toml`). Phase 1 of the owner's brief. No change to the tool was made for this audit.

**This is not legal advice.** The author of this audit is an AI (Claude, through Claude Code). Questions that need a lawyer are in `lawyer-questions.md`. Decisions that only the owner can make are in `owner-checklist.md`. Every risk is in `risk-register.md`.

Companion files in this folder:

- `audit-annex-third-party.md`: the full component inventory per package format (areas 4 and 5).
- `audit-annex-promise-words.md`: every promise-word hit in user-facing files, with file and line (area 9).

## 0. Read this first

### 0.1 How this audit was done, and how far to trust it

- Five read-only checks ran in parallel (licensing and claims; third-party components; releases and CI; WireViz, names and liability; privacy and secrets). Findings marked **[checked]** were re-checked by the main author against git or the files. All other findings come from one of the read-only checks and were not re-checked one by one.
- Packages were downloaded and opened: `.deb` 1.17.0 and 1.0.0, `.tar.gz` 1.17.0, Windows `.zip` 1.17.0, macOS `.dmg` 1.5.0. The Windows installer `.exe` could not be unpacked (Inno Setup 6.7.0). Its payload is assumed to equal the `.zip`.
- **No test was run.** The sandbox has Python 3.13. The project needs 3.14 or newer. Phase 2 needs a Python 3.14 environment before the rule "the full test suite must pass after every phase" can be met.
- The history scan used git and regular expressions. **gitleaks was not used.** A step that downloaded a scanner binary was blocked by the session's permission system, and I did not work around it. The command for you to run is in `owner-checklist.md`.
- Trademark registers could not be searched (see area 10). Nothing in this audit says a name is free.
- Full e-mail addresses and the name of one third party are deliberately not written in this folder, because this folder is public. They are given to the owner in the chat.

### 0.2 The brief and the repository disagree in these places

| Brief says | Repository shows | Effect |
|---|---|---|
| Releases 1.0.0 to 1.4.0 | **20 releases**, v1.0.0 to v1.17.0 (2026-10-12 to 2026-11-09) [checked] | Every "existing releases" step covers 20 releases. |
| Packages for Ubuntu, Windows and macOS | Ubuntu (`.deb`, `.tar.gz`) and Windows (`.zip`, setup `.exe`) since 1.6.0. macOS `.dmg` only in 1.2.0 to 1.5.0 (8 files). macOS was dropped (D-168). [checked] | The macOS packages still sit on four old releases. They cannot be rebuilt. |
| Packages are not signed | Correct. No release has a signature, provenance, SBOM, licence, notices or source offer. | See areas 4, 6, 14. |
| "Nobody else has contributed code" and "no employer, client or other person has any claim" | `CLAUDE.md` and D-186 say the tool is "used internally and never shared". Tag `v1.15.0` was created by **another named person with a company e-mail address** [checked]. Documents speak of "your company", "your IT", "customer and supplier". | **Needs your answer before Phase 2.** See area 12 and `owner-checklist.md`. |
| Upstream parts (`src/wireviz`, `docs/`, `examples/`, `tutorial/`) are unchanged | **12 of 13 files in `src/wireviz` differ from the fork base** `e4fe099f`, plus `setup.py`, `docs/README.md` and `.github/workflows/main.yml` [checked]. Cause: commit `a4431e2a` (2026-10-27, PR #119) applied formatter and Python 3.14 changes. | Breaks your decision. Several README sentences ("Unchanged") are false. See area 3. |
| Commit author e-mail check: "any other author e-mail" | Full history holds 1,151 commits, mostly upstream WireViz history by many people. [checked] | The e-mail check must only look at commits after the fork point. |
| An SBOM and a licence report exist | **Neither is in the repo or on any release.** The generator covers only Python packages. | See area 4. |
| The repository is public | Correct. GitHub reports the whole repository as GPL-3.0. | See area 1. |

### 0.3 Ten findings that matter most

1. **No licence for `HarnessDesignStudio/`, and conflicting statements** (LIC-1, LIC-8). The tool says "no licence granted". GitHub and the upstream README imply GPL-3.0 for the whole repository. 20 public releases carry no licence.
2. **Possible involvement of a third party or employer** (COM-1, REL-6). D-186 says "internal". A tag was made by someone else with a company address. You must answer.
3. **No warranty disclaimer, no intended-use statement, no project status** in the README top, the app, the outputs or `INSTALL.md` (CLM-1, LIA-1).
4. **Source offers and notices for LGPL/GPL parts are missing in every package** (TPC-1 to TPC-6). The `.deb` and `.tar.gz` bundle 87 Ubuntu libraries with no notices.
5. **Upstream WireViz files were modified** against your decision, and the README says "unchanged" (WIR-5).
6. **Personal e-mail addresses are in public git history**: a mailbox address on 98 commits, a second personal address on 3 commits and in 2 commit messages (PRV-1, PRV-2). The current tree is clean.
7. **"Clean-room" is used 17 times** and is not supported by the evidence (AUT-1, WIR-3).
8. **ECSS and ESCC requirement text is copied** into about 1,900 CSV rows (AUT-4, TMK-6).
9. **Wording that can read as a promise or an approval:** "Independent check", "No problems. Nice work.", "released", "approved" (LIA-3 to LIA-5, CLM-D).
10. **Supply chain:** no GitHub Action is pinned to a commit SHA (34 of 34), no signing, no scans in the release workflow (SEC-1, SEC-6, SEC-9).

---

## 1. Licensing

**What is stated now, and where**

| Place | Statement | Source |
|---|---|---|
| `pyproject.toml:14` | `license = "LicenseRef-Proprietary"` | file |
| `tools/build_deb.py:23-37` | `.deb` copyright file: "No licence is granted by this file". Pinned by `tests/test_installers.py:457-475`. | file |
| Root `README.md:122` | "not decided (D-02/D-143)... no licence granted" | file |
| Root `LICENSE` | GPL-3.0 text of WireViz. No scope statement. | file |
| Embedded upstream README (`README.md:332`) | "License: GPL-3.0", without limit | file |
| `packaging/windows/README-windows.txt:35-37` | "no licence is granted". Shown as the first installer page (`.iss:38`). | file |
| About dialog `gui/strings.py:2215`, shown by `gui/settings_page.py:326` | "placeholder, not yet chosen" | file |
| `CLAUDE.md:9`, `DECISIONS.md` D-02, D-03, D-143, D-186, D-200 | placeholder; "used internally and never shared" | file |
| `docs/SPEC.md:32`, `tools/licence_report.py:15-17` | dependencies must allow "closed internal use"; any GPL dependency is rejected | file |
| GitHub | repository licence detected as GPL-3.0 | GitHub API |
| Release bodies, `tools/release_notes.py` | no licence line for the tool | releases |

**Findings**

- **LIC-1** The statements conflict. Fix: apply decision L-1 everywhere; add `HarnessDesignStudio/LICENSE`; add a scope sentence to the root `LICENSE` section of the README. L high / I high. Owner decision: no.
- **LIC-2** No file has an SPDX or licence header. A search for `SPDX-License-Identifier` finds nothing. Files without header: about 649 Python files (`src` 257, `tests` 339, `tools` 46, `packaging` 2, `docs/examples` 5), 6 shell, 3 HTML (one is the generated in-app guide), 1 JS, 1 YAML plus 2 byte-compared fixtures, 1 Inno Setup file. JSON, CSV, Markdown and SVG files need a `REUSE.toml` entry. Generated files must be changed in their generator, and that changes the golden outputs. L high / I medium.
- **LIC-3** The About dialog and the installer tell users that no licence is granted. The Licences section lists fonts, icons and Qt only. The GPL text of the tool itself cannot be seen in the app (GPL-3.0 section 5(d)). `packaging/licences/GPL-3` already exists. L high / I medium.
- **LIC-4** The `.deb` `copyright` file is not a valid licence statement. Update the pinning test too.
- **LIC-5** The rationale "allow closed internal use" (D-02, SPEC) is wrong after L-1. Record a new decision. The allow-list tests (REQ-LIC-01) assume "permissive or LGPL only" and fail or mislead once the tool is GPL-3.0-only (TPC-10).
- **LIC-6** The root `LICENSE` file has no statement of what it covers. Same fix as LIC-1.
- **LIC-7** `CONTRIBUTING.md` has no inbound licence and no DCO. Decision L-4 covers it.
- **LIC-8** 20 releases (1.0.0 to 1.17.0) were published with the "no licence granted" text, or with no text. Option (a) or (b) of Phase 2 step 2.9. Lawyer question Q-2. Owner decision: yes.
- **LIC-9** The release-note generator and the release pages carry no licence or disclaimer line, except one sentence ("aid to a designer's work, not a certificate") from 1.1.0 on.

## 2. Authorship and copyright

**What exists**

- The only copyright line is in the `.deb`: "the repository owner (GitHub account 0h3xn4)". No source file has a copyright line. No `NOTICE` exists.
- The AI-authorship sentence ("Written mainly by an AI (Claude, through Claude Code); the owner set requirements and approved decisions and releases") is in five places: root `README.md:120`, `HarnessDesignStudio/README.md:5`, `docs/user-manual/README.md:100`, `compliance/README.md:20`, `CHANGELOG.md:635`. It matches Section 0 of the brief and goes no further. No claim of personal authorship and no personal name was found.
- Git evidence for `HarnessDesignStudio/` [checked]: 451 commits touch the folder. 350 have author "Claude" (`noreply@anthropic.com`). 98 have the owner's mailbox address as author and GitHub as committer (these are merge commits and squashed pull requests). 3 have a second personal address (Claude name, owner's account address). There is no other human author in the folder history.

**Findings**

- **AUT-1** "clean-room": 17 lines in 15 files. User-facing: root `README.md:129`, `HarnessDesignStudio/README.md:59`, `CONTRIBUTING.md:25`, `docs/STATUS.md:51`, `docs/examples/README.md:276`, `docs/OUTPUTS.md:126`, and the v1.0.0 release body. Internal: `CLAUDE.md:3`, D-01, D-03, D-143, `docs/developer/architecture.md:70`, `docs/ui/UI_OVERHAUL.md:9`, `docs/UX_GUIDELINES_REVIEW.md:7`, `compliance/PHASE0.md:52`, `compliance/docs/SRF.md:3`, `docs/DOCS_AUDIT.md:51`. It is in no code, test, tool, packaging file or app string.
  Why it matters: the term implies separated teams. `AUDIT.md:1492-1495` (2026-10-12) records that agents read all of `src/wireviz`, `docs/syntax.md` and the examples five days after the first code commit. The content check (area 3) found no copying, but it cannot show independence. `CONTRIBUTING.md:25` and D-01 say it was done "so that it does not inherit that licence". That contradicts L-1.
  Fix: replace with "Harness Design Studio does not copy or import WireViz code." Record a new decision. Do not rewrite D-01. Owner decision for the v1.0.0 release body and for files under `docs/`: yes.
- **AUT-2** The README says the owner "approved the releases". Release pages 1.12.0 to 1.17.0 and `compliance/SIGNOFF.md` say the owner has not signed these releases off. Fix: one text in `texts.md`.
- **AUT-3** The authorship wording differs in at least seven files. `docs/ait/PLAN_2.0.md:13,719` and `docs/transparency_final_audit.md:225` say "parallel agents". Fix: one text.
- **AUT-4** `compliance/requirements/*.csv` (1,948 lines) and `compliance_matrix.csv` quote ECSS and ESCC requirement text, cut to 600 characters per row. `core/standard_profiles.py` embeds ECSS table values. Reuse terms were not checked. See TMK-6 and `lawyer-questions.md` Q-6.
- **AUT-5** A copyright line is planned. A `NOTICE` must come with it (brief 2.2).
- **AUT-6** Two commit messages carry `Co-authored-by: Claude <personal address of the account owner>`. See PRV-2.
- **AUT-7** `docs/ui/UI_OVERHAUL.md:26,82` mentions "SpaceMissionStudio, SystemDesignStudio, HarnessDesignStudio... one product family, three repositories". `docs/TIPS.md:232` and `docs/DOCS_AUDIT.md:233` name Requirements Studio, Budget Studio, AIT Logbook and ICD Studio as "your other tools". If any of them is not yours alone, that is an ownership question. Owner decision: yes.

## 3. Relationship to WireViz

- **WIR-1 No code is copied or imported. [evidence, low risk]** Method: 13 upstream `.py` files (2,930 lines) against 649 tool `.py` files (about 198,000 lines), tokenised. The longest identical token run is 14 tokens (the hex colour idiom `[i:i+2], 16) for i in`). Comparison that ignores identifiers and strings matches only import and dictionary shapes. 0 identical long lines against 5,912 upstream lines (code, docs, examples, tutorial). 0 shared prose runs of 8 words and 0 shared string literals of 25 or more characters. A control run (upstream against upstream) finds the known copies, so the detector works. The tool's colour table (`core/wirecolours.py`) has its own values; only `#000000` and `#ffffff` are shared. The scripts are kept outside the repo and can be added to the evidence folder on request.
  Fix: add a CI guard that fails on `import wireviz` in `HarnessDesignStudio/`.
- **WIR-2** History: with `--find-copies-harder` over all branches, no file of the tool began as a copy of an upstream file. The one copy is the GPL-3 text (`LICENSE` to `packaging/licences/GPL-3`, commit `668ad004`), which is identical to the root `LICENSE`.
- **WIR-3** "Clean-room" is inaccurate. See AUT-1.
- **WIR-4** The README contradicts itself: "built on top of WireViz" (`README.md:5`) against "separate", "written from scratch" (`:39`, `:129`, `:133`). Fix: "lives in a fork of WireViz; does not copy or import its code; not affiliated".
- **WIR-5 Upstream parts are NOT unchanged. [checked]** Against `e4fe099f` (2025-01-16, WireViz 0.4.1): 18 files changed, +714 / -342. Changed: 12 of 13 files in `src/wireviz/*.py` (`DataClasses`, `Harness`, `__init__`, `build_examples`, `svgembed`, `wireviz`, `wv_bom`, `wv_cli`, `wv_colors`, `wv_gv_html`, `wv_helper`, `wv_html`), `setup.py` (`python_requires>=3.14`), `.gitignore`, `MANIFEST.in` (new), `docs/README.md` (replaced by an index), `docs/DOCS_AUDIT.md` and `docs/upstream/README.upstream.md` (new). Unchanged: `LICENSE`, `requirements.txt`, `pyproject.toml`, `examples/`, `tutorial/`, `docs/syntax.md`.
  Wrong statements: `README.md:128` ("Unchanged."), `:6` and `:131` (embedded README unchanged), `:163` ("not reworded", but `:264` and `:268` are reworded), `docs/upstream/README.upstream.md` is called "byte-identical" but differs in 2 lines, `README.md:157` says Python 3.7 while `setup.py` says 3.14.
  Why it matters: it breaks your decision, the public statements are false, and GPL-3.0 section 5(a) asks for a notice of modification on modified files. They have none.
  Options: (a) restore the files byte for byte (then check that `main.yml` and `setup.py` still work; this was not tested); (b) keep the changes, add a modification notice, and correct every "unchanged" sentence. Owner decision: yes. Brief rule 3 forbids changing `src/wireviz` without your OK, and that includes restoring it.
- **WIR-6** `LICENSE` is the FSF GPL-3.0. `src/wireviz` files have no copyright or SPDX header. `setup.py` names the upstream author. Many people authored upstream code (the history lists more than 20 authors). The README statements on the upstream version (0.4.1) and licence are accurate. Fix: say in `NOTICE` that the repository contains WireViz, copyright its contributors, GPL-3.0, fork base `e4fe099`.
- **WIR-7** The WireViz-style YAML (`core/outputs/exports.py:28-60`) is written by hand. The tool never imports or runs WireViz (`provenance.py:36`, `tests/test_provenance.py:23`). The docs call it "best effort, not validated". The sdist WireViz 0.4.1 parsed the test fixtures. Rendering was not tested (no Graphviz here). The wording is conservative.
- **WIR-8** The root `setup.py` builds a distribution named `wireviz` 0.4.1, the same name as the upstream package on PyPI. It is not published. Document this.
- **WIR-9** Statement accuracy: correct for the GPL, the fork point and the "not used at run time" claim. Wrong or misleading: WIR-3 to WIR-5. The About dialog and the release-note template make no WireViz claims.
- **WIR-10** Root `AUDIT.md` (265 KB) is public. It lists unfixed upstream bugs and early defects of the tool. It contains a path from an upstream example (`/Users/daniel/...`). Owner decision: keep it public or not.

## 4. Third-party components

Full tables are in `audit-annex-third-party.md`. Summary:

**What the packages hold.** Packages are PyInstaller one-folder builds. Python 3.14.10 runtime. Python packages (same set in every format): pydantic, pydantic-core, annotated-types, typing-extensions, typing-inspection, openpyxl, et-xmlfile, defusedxml, PySide6-Essentials, shiboken6. Qt 6.11.2 modules: Core, DBus, Gui, Widgets, Network, OpenGL, Svg, WaylandClient, plus platform plugins. OpenSSL, libffi, zlib, bzip2, xz, zstd, ICU 73 (Linux). Fonts: Inter 4.1, JetBrains Mono 2.304 (OFL-1.1, texts ship). Icons: Lucide (ISC) and Feather (MIT) geometry. Linux packages also hold **87 Ubuntu system libraries** (GTK 3, GLib, Cairo, Pango, libgcrypt, libsystemd, Kerberos, X11, libstdc++ and others). Windows packages also hold the Microsoft VC and UCRT DLLs and `opengl32sw.dll` (Mesa/LLVM).

**Findings** (each has more detail in the annex)

- **TPC-1** No compliant source offer for Qt, PySide6 or any other LGPL/GPL binary. The packages say only "available from the Qt Project (https://code.qt.io)". No release has source archives. L high / I high.
- **TPC-2** 87 Ubuntu libraries are bundled in `.deb` and `.tar.gz` with no licence texts, notices or source offers. About 43 come only from an optional GTK theme plugin and from `libQt6Network`, which the app does not use. Pruning is an owner decision.
- **TPC-3 to TPC-5** No notices for Python (PSF), OpenSSL (Apache-2.0), libffi, zlib, bzip2, xz, zstd, ICU, Qt-internal third-party code, and at least 26 Rust crates inside `pydantic_core`.
- **TPC-6** No project `LICENSE`, `NOTICE` or `THIRD_PARTY_NOTICES` in any package.
- **TPC-7** The Windows package ships Microsoft runtime DLLs and Mesa/LLVM `opengl32sw.dll` without notice. Whether the Microsoft redistribution terms are met is open. Owner decision and lawyer question.
- **TPC-8** The Windows `LICENSES` folder holds a Qt commercial licence text that the Linux and macOS packages lack.
- **TPC-9** The SBOM and licence report are not in the repo and not on any release. The generator (`tools/gen_sbom.py`) reads only the Python packages of a clean venv, about 100 components fewer than the Linux package holds. `docs/SECURITY.md:26` ("with every release") and `compliance/docs/CMP.md:33` say otherwise. L high / I medium.
- **TPC-10** The licence policy and tests assume "permissive or LGPL only" and do not cover native components.
- **TPC-11** Transitive dependencies are not pinned (for example `typing-inspection` 0.4.4 in 1.0.0, 0.4.5 in 1.17.0).
- **TPC-12** `libQt6Network` and `libQt6Svg` ship although code comments say Svg is left out and the app "never uses the network".
- **TPC-13** Qt is replaceable (separate files, byte-identical to the PyPI wheels) but this is not documented. On macOS the code signature blocks replacement.
- **TPC-14** Licence choices must be recorded: Qt option, FreeType, cairo, graphite2, libdbus, libcap, libzstd.
- **TPC-15** The PyInstaller bootloader has no notice and its version is not recorded.
- **TPC-16** macOS releases 1.2.0 to 1.5.0 are public with the same gaps and a bundle identifier that was made up.
- **TPC-17** The Lucide notice text is older than the upstream licence text of the version used.
- **TPC-18** The About page lists only 4 components.
- **TPC-19** The first public `.deb` (1.0.0) bundled IBM Plex instead of Inter and JetBrains Mono, also with its OFL text.

**GUI framework (area 5).** PySide6-Essentials 6.11.2 (Qt 6.11.2). It is not PyQt. No Addons wheel. **No bundled Qt module is GPL-only or commercial-only.** The headers read say `Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. The GPL-only modules `QtWaylandCompositor` and `QtQuickTimeline` are in the PyPI wheel but not in the packages. Qt is linked dynamically. All 163 Qt and Shiboken files in the Linux package are byte-identical to the PyPI wheels. Qt licences were read from the Qt 6.11.2 source headers because `doc.qt.io` was not reachable. Qt is not modified.

**GPL-3.0-only compatibility.** No bundled licence found conflicts with GPL-3.0-only. Open points: Microsoft redistribution terms, Mesa/LLVM, FreeType and the dual-licence choices (TPC-14).

**Fonts and icons.** Inter and JetBrains Mono are byte-identical to the upstream release files and their OFL texts ship. No Reserved Font Name is declared in either. The prototype and docs contain no third-party JS, CSS or fonts.

## 5. Release history

All 20 releases: assets were uploaded by `github-actions[bot]`. None is immutable. All 20 tags are reachable from `master`. 18 tags are lightweight. Tags `v1.14.0` and `v1.15.0` are annotated.

| Release | Date | Assets |
|---|---|---|
| v1.0.0, v1.1.0 | 2026-10-12, 10-18 | `.deb`, `.tar.gz`, `SHA256SUMS` |
| v1.2.0 to v1.5.0 | 2026-10-19 to 10-21 | the above, plus Windows `.zip` and setup `.exe`, plus macOS `.dmg` (arm64 and x86_64) |
| v1.6.0 to v1.17.0 | 2026-10-21 to 2026-11-09 | `.deb`, `.tar.gz`, Windows `.zip`, setup `.exe`, `SHA256SUMS` |

Tag commits and the 20 `SHA256SUMS` files are in the working notes; every digest in every `SHA256SUMS` equals the digest GitHub reports for that asset (0 mismatches).

What the release texts say, over all 20: no licence, warranty, liability, intended-use, source-offer or non-affiliation text. One sentence from 1.1.0 on: "aid to a designer's work, not a certificate; check them before you rely on them" (`tools/release_notes.py:233`). Every body says the packages are not signed and that the release is not a statement of compliance with any standard. "clean-room" is in v1.0.0 only. "safe" is in v1.17.0 (8 times) and v1.0.0. The bodies claim "never uses the network" and "always byte-identical" (`release_notes.py:37,207`).

**Findings**

- **REL-1** No licence on any release. See LIC-8. Owner decision: yes.
- **REL-2** No disclaimer, intended-use or status text on any release.
- **REL-3** No LGPL source archive or written offer (TPC-1).
- **REL-4** `docs/SECURITY.md:26` says an SBOM ships with every release. None does.
- **REL-5** Unsigned, no provenance. The checksum sits on the same page as the files it protects.
- **REL-6** Personal data in tags [checked]. Annotated tag `v1.15.0` was created by a named person with a company e-mail address. Tag `v1.14.0` has the owner's mailbox address. The named person appears nowhere else in the repository. This conflicts with "nobody else contributed". Owner decision: yes.
- **REL-7** Tags and releases are mutable. `release.yml` uses `gh release upload --clobber` (line 213). `v1.16.0` was deleted and recreated (`docs/RELEASE.md:25`). No tag ruleset.
- **REL-9** Promise words ("safe") and absolute claims in release text. See area 9.
- **REL-11** `docs/INSTALL.md:3` and root `README.md:50` still name 1.16.0 as the newest release.
- **REL-12** No per-release compliance record exists for 1.17.0. Records for 1.0.0 to 1.16.0 are checksum lists only.
- **REL-13** The macOS releases 1.2.0 to 1.5.0 cannot be rebuilt (`docs/RELEASE.md:29`).

## 6. Personal data and secrets

Method: full history (1,151 commits, 20 tags), all refs. Regular expressions for tokens and keys over every added line of `HarnessDesignStudio/` and `.github/`. E-mail extraction from commit metadata, messages and files. Home-directory path search in the current tree. Image metadata check of all 383 images (Pillow). Two screenshots viewed. **gitleaks was not used** (see 0.1).

- **PRV-1 [checked]** The owner's mailbox address is the author address of 98 commits that touch `HarnessDesignStudio/` (committer: GitHub). It is the tagger address of tag `v1.14.0`. It is in public history. Whether it is private is your call. Rewriting history is not done without your decision (brief 2.7). Use the GitHub noreply address for future commits (steps in `owner-checklist.md`).
- **PRV-2 [checked]** A second personal address (the address of the account owner of this Claude Code account) is author and committer of 3 commits (`5668c62c`, `839e98f0`, `e8f3b01b`) and is in a `Co-authored-by` trailer of 2 commit messages. Owner decision: yes.
- **PRV-3 [checked]** Upstream commit metadata holds the addresses of more than 30 upstream contributors. That is upstream's history. It is informational. Rewriting is out of scope and would break the fork.
- **PRV-4 [checked]** No token, key or password was found in the added lines of the tool and workflow files. One regular-expression hit in old `release.yml` revisions was `password="$(uuidgen)"`, a throw-away keychain password for a macOS step. It is not a secret.
- **PRV-5 [checked]** Current tree: no real e-mail addresses (only `example.invalid` and `example.org`), no home-directory paths other than invented examples (`/home/ann/`, `/home/someone/`). The screenshots viewed show `/tmp/harness-screenshots/...` paths, no user names. All 383 images have no metadata. Only 2 of the 383 screenshots were viewed; the rest must be looked at before the website uses them.
- **PRV-6** `.github/workflows/release.yml` names two secrets (`WINDOWS_CERT_PFX_BASE64`, `WINDOWS_CERT_PASSWORD`). Whether they exist in the repository settings is not visible to this audit.

## 7. Data that may not be public

- **DAT-1 [checked]** `compliance/requirements/` holds about 1,900 rows of requirement text from ECSS-E-ST-40C, ECSS-Q-ST-80C, ECSS-Q-ST-30-11C, ECSS-E-ST-20-07C and ESCC-3901. `tools/extract_requirements.py` reads the PDFs and cuts each text to 600 characters. The PDFs are not in the repo. The CSVs are not in the packages. ESA holds the copyright of ECSS documents. Reuse terms were not read at source (the ECSS page was not reachable). Owner decision: yes. Lawyer question Q-6.
- **DAT-2** `core/standard_profiles.py:37-60` ships optional ECSS table values. An AI transcribed them. No record of a person checking them against the standard was found. See LIA-6.
- **DAT-3** Markers searched: ITAR, EAR99, export control, CUI, confidential, "company internal", proprietary, and names of agencies, primes and missions. The only hits are the word "proprietary" in licence texts and decisions, and the names ECSS and ESA in the standards documents. No customer, programme, mission or company name was found in the tool, examples or tests. The example projects (`flatsat`, `small-satellite`, `minimal-satellite`, fixtures `sat15`, `mini3`) use invented values and the flatsat project is labelled "EXAMPLE numbers, not engineering data". Whether any example is taken from a real project is a question to you.
- **DAT-4** Real manufacturer part numbers appear in parts libraries. They are facts. Datasheet copying was not checked.
- **DAT-5** `docs/ait/`, `docs/usability/` and `SIGNOFF.md` mention a workshop with a systems engineer, an AIT engineer and an electrical engineer, and a usability kit. No participant is named. Whether they agreed to the use of their feedback is open (COM-1).

## 8. Claims and wording

Method and counts are in `audit-annex-promise-words.md`. The word list is the brief's rule 7 plus "validated", "certified" and "compliant" and their forms.

**Promise words.** About 380 hits in user-facing files, over 3,000 in internal files. The user-facing hits are mostly: "approved" as a data type (the approved-parts list), "validate" as a CLI command, "compliance" as the folder name or in a negation ("no claim of compliance"), and licence texts. No promise word makes a claim about the tool or its results in the HDS README, app strings, CLI help, `INSTALL.md`, FAQ or GETTING_STARTED. The check in Phase 2 needs an allow-list for: data-type uses, the `compliance/` folder, licence texts, quoted standards, and tests that assert a negation.

**Claims table**

| Claim | Status | Evidence or issue |
|---|---|---|
| The app never uses the network | verified, with scope | `tests/test_offline.py` (static import scan; runtime socket patch for CLI and an offscreen window). "No data ever leaves this computer" is stronger than the test. |
| Output files are byte-identical for the same design | verified, with scope | goldens; valid for one tool version |
| 39 design rules | verified | fixture "Rules run: 39" |
| Packages are not signed | verified | |
| "Not a statement of compliance" | verified | `release_notes.py:29-32` |
| AI authorship | verified | |
| WireViz YAML "not validated against WireViz" | verified | honest |
| **CLM-D** "Outputs are checked independently" | **wrong** | In-app guide `index.html:125`, `strings.py:1452`. It is a second routine of the same program, written by the same AI. The repo records that no independent review took place (`docs/AUDIT.md:5`, `DEVIATIONS` T-20). |
| **CLM-F** "The tool never supplies a number itself" and "ships no derating or EMC values" | **wrong** | `strings.py:1178`, release text. `config --apply-profile` (`cli/data.py:96`, `core/standard_profiles.py`) writes ECSS table values. FAQ and CONCEPTS are accurate on this. |
| **CLM-V** "latest is 1.16.0" | **wrong** | v1.17.0 was published 2026-11-09 |
| Ubuntu "24.04 or newer", Windows 10 | unverifiable | CI runs only `ubuntu-24.04` and `windows-latest`. `CLAUDE.md:10`: no screen was watched on a real display by a person. |
| Disk size 500 MB / 600 MB | unverifiable and inconsistent | `README.md:114`, `INSTALL.md:40` and `:209` |
| "No other person has reviewed it" | unverifiable | D-172 and `SIGNOFF.md:129` record workshop and AIT feedback |

**Other findings**

- **CLM-1** No warranty disclaimer and no "check before relying" text in the app, outputs, `INSTALL.md` or the README top block. The only one is the release-page sentence. Generated files carry only a version and hash stamp (`core/outputs/stamp.py:25`). L high / I high.
- **CLM-2** "Safe" and "independent" wording: `FAQ.md:77`, `docs/releases/1.17.0.md:1,19`, `strings.py:32` and `:1452`.
- **CLM-3** Positive results without a placeholder caveat in the same line: `strings.py:414` ("all N rules passed"), `:127` ("No problems. Nice work."), `:470` ("Nothing blocks this release."), `:2033`, workbook "Ready to build".
- **CLM-4** `INSTALL.md:216` and the Windows README tell users to click "Run anyway" on an unsigned program. This is accurate and depends on the signing work.
- **CLM-6** The README repeats a 1,500-character status paragraph that is out of date. Point to `docs/STATUS.md`.
- **CLM-7** The README label "Honest" is self-praise.
- **CLM-8** No intended-use sentence exists. The root README caption says "23 flight and ground devices" for an example whose values are invented.
- **CLM-9** ECSS requirement IDs on the design rules (`docs/RULES.md`, Checks tooltips) can read as "implements the standard". Put the non-compliance sentence next to them.
- No statement anywhere says the tool or a design complies with a standard.

## 9. Names and trademarks

**Names in use:** WireViz (repo name, GUI label "WireViz description", `wireviz.yaml`), KiCad (`README.md:138`), InvenTree (`cli/data.py:110`), Qt, PySide6, Excel, LibreOffice, ECSS, ESCC, EPPL, MIL-STD-1553B, IEC 60757, DIN 47100, Ubuntu, Windows. These are nominative uses. IBM Carbon and Plex appear only in docs and a `banner.svg` comment (superseded by D-150). Third-party logos: only the two README badges (TMK-5).

- **TMK-1** Aggregator sites list a USPTO word mark HARNESS in classes 9 and 42 (Reg. 5409033, and a second registration). They disagree on the owner. This was **not verified at the register**. The name "Harness Design Studio" begins with that word in the same classes. "Harness" is also a generic word in wire-harness engineering, and the field differs. L low-medium / I medium. Owner decision: yes.
- **TMK-2** No product named exactly "Harness Design Studio" was found. Similar names exist: EPLAN Harness proD Studio, EMCoS Harness Studio, Siemens Capital Harness, TE HarnWare, Zuken E3, and two GitHub projects named `harness-studio`. PyPI: `harness-design-studio`, `harnessdesignstudio` and `harness-gui` returned 404; PyPI `harness` exists (unrelated). A free package name is not a trademark clearance.
- **TMK-3** The aliases `harness` and `harness-gui` (`pyproject.toml:25-29`; the `.deb` installs `/usr/bin/harness`, `tools/build_deb.py:85`). The command line tool of the DevOps company Harness is also called `harness`. D-147 forbids removing aliases without a recorded decision. Owner decision: yes.
- **TMK-4** QSettings organisation "HarnessDesigner" (`gui/app.py:17`) is generic. Low risk.
- **TMK-5** README badges use `logo=ubuntu` and `logo=windows` from shields.io (`README.md:10-11`). These are third-party logos and an external request from the README. The embedded upstream README has more. Fix: plain text. Never reuse them on the website.
- **TMK-6** ECSS text. See DAT-1.
- **TMK-7** The installer publisher is "Harness Design Studio" (`.iss:23`) and the `.deb` maintainer is "Harness Design Studio maintainers <noreply@example.invalid>" (`tools/build_deb.py:46`). Both read like an organisation. Owner decision: which handle to show.

The exact searches for you to run are in `owner-checklist.md`.

## 10. Liability exposure

**Where results can be relied on for real hardware:** wire gauge, derating, voltage drop, K factor, pinouts, wire lists, mass, BOM, build workbook, test limits, the drawing title block, the release gate, the Checks panel, the "Independent check", and the optional ECSS profiles.

**Mitigations that exist:** placeholders and "not checked" states (`strings.py:227,1095-1147`); README and STATUS say "check its results before relying on them"; `CONCEPTS.md:132` ("your responsibility"); the release-note caveat.

- **LIA-1** No warranty or liability disclaimer for the tool exists anywhere. The only "as is" texts belong to bundled fonts and icons. Because no licence is granted, GPL sections 15 and 16 do not apply to it yet. L low / I high. Fix: L-1 and brief 2.3.
- **LIA-2** No first-run notice. The About dialog shows only the placeholder licence line.
- **LIA-3** "Independent check" wording (`strings.py:247,421,432,620,875,903,1450-1454`, `guide/index.html:125`, `OUTPUTS.md:106`). Fix: "self-check". Owner decision: yes.
- **LIA-4** Comfort wording (`strings.py:127,414,470`). Fix: "No problems found by the checks that could run; N not checked".
- **LIA-5** Release vocabulary. The drawing title block has status, author, checker and approver (`core/outputs/drawing.py:648,738`). The workbook header says "status released" (`buildsheet.py:412`). In the tool, "release" is a data lock plus a typed name and a comment of 10 or more characters (`CONCEPTS.md:127`). There is no authentication and no value check. It can read as a real approval. Fix: the notice next to the status. Owner decision: yes (output content).
- **LIA-6** The optional ECSS profile values were transcribed by an AI. No person-check was found.
- **LIA-7** A harness released on placeholder values carries no marker in the drawing or workbook. The dialog warns (`strings.py:765,774`). Owner decision: yes.
- **LIA-8** Whether free software is outside the EU Product Liability Directive (EU) 2024/2853 and the Cyber Resilience Act (EU) 2024/2847 is a lawyer question (Q-7). L-2 rests on it.

## 11. Commercial signals

Confirmed absent: `FUNDING.yml`, sponsor or donate links, prices, paid support, consulting offers, "contact us", company, customer, agency and programme names, ITAR and EAR markings. `pyproject.toml` has no authors or URLs. The GitHub API shows no sponsorship. Issues are disabled.

- **COM-1 OWNER QUESTION.** D-186 (`docs/DECISIONS.md:195`, 2026-10-29): "The tool is used internally and is never shared. So licence and signing need no decision now... If the tool is ever given to anyone outside, D-02 and T-19 reopen first." No document defines "internally". The repository is public, 20 releases have been downloadable since 2026-10-12 (1.0.0 to 1.9.0 were published before D-186 was written), and `CONTRIBUTING.md` invites outside contributions. D-186 is repeated in `CLAUDE.md:9`, D-02, D-200(d), `PLAN_2.0.md:596,601,719`, `docs/transparency_audit.md:259`, `docs/developer/extensions.md:205`, `SPEC.md:32`.
  Text that implies an employer or organisation (all AI-written, addressed to "you"): `PLAN_2.0.md:599-601,655` ("your organisation's own PKI... company computers... Needs your IT"), D-200(d) ("an internal certificate through the owner's IT"), `SPEC.md:31,33` ("locked-down workstations", "export-controlled information"), "company title block" (D-15, `OPEN_DECISIONS.md:23`, `UX.md:160`, `PLACEHOLDERS.md:12`), `INSTALL.md:256` ("Your company blocks programs"), and the roles in `ORGANISATION.md` ("Owner: customer and supplier"). No document names an employer, customer, agency or programme.
  Why it matters: L-2 and your statement "no employer claim" depend on this being true. If any employer, client or university has a claim on any part, your GPL grant could be invalid for that part. D-186 is also the stated reason that licence, signing, notices and the maintainer address were skipped. It no longer holds. L high / I high. The questions are in `owner-checklist.md`.
- **COM-2** `ORGANISATION.md`, `STANDARDS.md:3` and `CLAUDE.md:9` describe the owner as "customer and supplier" who "waives" actions. In a public repo this reads like a supplier with obligations. State that the roles are template roles of a personal project.
- **COM-3** Installer publisher and `.deb` maintainer. See TMK-7.
- **COM-4** `docs/ait/PLAN_2.0.md:587-606` names commercial signing services and says "prices not checked". Low risk. Remove or reword.
- **COM-5** Add a lint for funding files and price words.

## 12. App privacy

- **NET-1 [checked]** Network-capable imports in `src`: none (`socket`, `urllib`, `http`, `ssl`, `requests`, `QtNetwork`, `QtWebEngine` not imported). `QDesktopServices.openUrl` is used in `export_dialog.py`, `main_window.py` and `outputs_files.py` to open local files and folders. `gui/drc_process.py` starts a subprocess of the tool's own program with fixed arguments. `tests/test_offline.py` scans imports (including dynamic and relative imports) and patches sockets at run time for the CLI and an offscreen window. Not covered: the packaging entry points (`packaging/gui_entry.py`, `cli_entry.py`) and a packaged build; and `openUrl` could open a web address if a URL were ever passed. Add both to the test.
- **NET-2** The only web addresses in `src` are in licence texts (`gui/licences.py`, `gui/icons.py`) and one Qt source note (`gui/strings.py:2228`). They are text, not requests.
- **NET-3** No update check, no telemetry, no crash upload, no `sys.excepthook` upload were found. Not re-checked in the packaging entry points.
- **PRV-7 [checked]** **User name in files.** The run record (`core/run_record.py:41-77`), the journal (`core/journal.py:107-122`) and release and review records (`gui/main_window.py:3457`, `core/vcs/roles.py:49`) record an "operator" or "author": the typed name, else `HARNESS_AUTHOR`, else Git `user.name`, else the OS user (`USER`, `USERNAME`, `LOGNAME`). This is written into project files and so can leave the computer if the user shares a project. Brief 2.4 step 3: I report it and do not change it without your OK.
- **PRV-8 [checked]** **Host name in a file.** The project lock file holds pid, **host name** (`platform.node()`) and start time (`core/io/fs.py:270-290`). It sits in the project folder and may be shared or committed.
- **PRV-9** Per-user settings are stored with `QSettings` (organisation and application name "HarnessDesigner", INI format, `gui/app.py:16-18`): mode, theme, scale, last project, and a recent-projects list. The recent list holds paths on the user's computer. It stays local. Mention it in the privacy statement.
- **PRV-10** Time stamps: the run record writes `time_utc` (`core/run_record.py:77`), the journal writes UTC times (`core/journal.py:81`). The CLAUDE.md rule says "no timestamps in generated data". The run record is opt-in (`--run-record`). Check that outputs other than the run record carry no time stamp.
- The in-app text `strings.py:466` tells the user that the name was taken from Git.

## 13. Security and supply chain

Facts from the files and the public GitHub API:

- Workflows: `harness-ci.yml`, `harness-packages.yml`, `harness-platforms.yml`, `harness-real-platform.yml`, `release.yml` and the inherited upstream `main.yml`. There is no Dependabot file, CODEOWNERS, `SECURITY.md` at root or in `.github`, issue template, PR template, CodeQL or dependency review.
- `permissions: contents: read` is set at top level in all workflows except `main.yml`. `release.yml` raises to `contents: write` only in the `release` and `notes` jobs (lines 162 and 226). No `pull_request_target` or `workflow_run`. No script injection was found (`inputs.tag` goes through `env`).
- Secrets: only `release.yml` uses them (`WINDOWS_CERT_PFX_BASE64`, `WINDOWS_CERT_PASSWORD`, lines 108-109).

**Findings**

- **SEC-1** None of the 34 `uses:` lines is pinned to a commit SHA (`actions/checkout@v4`, `setup-python@v5`, `upload-artifact@v4`, `download-artifact@v4`, and the third-party `ts-graphviz/setup-graphviz@v2` in `main.yml:23`). The current SHAs could not be looked up from this sandbox (proxy limit). L low / I high.
- **SEC-2** `main.yml` (inherited upstream workflow "Create Examples") has no `permissions`, runs on every push, PR and tag, installs the root package, builds the upstream examples and uploads an artifact. It does not publish. It uses a third-party action. Disable it, or restrict it. Owner decision: yes (changing a workflow file that was inherited).
- **SEC-3** Four workflows are registered in Actions although their files are gone (platform probe, probe mac perf, win lock probe, "release dry run (temporary)"). The dry-run name suggests the signing secrets. Owner decision: yes (settings).
- **SEC-4** The signing secrets are job-wide environment variables in the Windows job, so `pip install` and the build see them. Scope them to the signing step.
- **SEC-6** No signing, no cosign, no attestation, no `id-token` permission. Text saying "not signed" sits in `release_notes.py:30,90,226`, `INSTALL.md:3,80,216,253`, `SECURITY.md:29-37,63`, `RELEASE.md:45,52`.
- **SEC-7** Only direct dependencies are pinned. No lock file, no hashes. 84 distributions resolve (today). Root upstream `requirements.txt` is unpinned.
- **SEC-8 [pip-audit 2.10.1]** Runtime plus GUI set (4 packages): no known vulnerabilities. All direct pins plus `setuptools` (18): **one finding**: `setuptools==84.0.0` (build time only, `pyproject.toml:2`), GHSA-xmj3-9gf7-h52w, fixed in 84.1.0. Full resolved set (84): same one finding. Upstream root requirements: none. `tools/check_vulnerabilities.py:26` excludes `setuptools`, so the release gate would miss it. The OSV database could not be reached for a second source.
- **SEC-9** Neither `pip-audit` nor `check_vulnerabilities` runs in any workflow. `release.yml` runs no tests, no scan and no SBOM, and does not check that the tagged commit is on `master` or that CI is green (SEC-14).
- **SEC-10** No CodeQL, dependency review, Dependabot configuration or root `SECURITY.md`. `docs/SECURITY.md` has no reporting channel.
- **SEC-11** The ruleset "Protect main" requires a pull request (0 approvals), blocks force pushes and deletion, but its list of required checks is empty. No tag ruleset.
- **SEC-12** 5,577 public artifacts are kept (about 90 days), including `.deb` and `.tar.gz` files of untagged commits. `INSTALL.md:57` recommends them.
- **SEC-13** Floating `windows-latest`, apt and Playwright downloads, unpinned `pip --upgrade pip` and `pytest-timeout`.
- **SEC-14** A pushed `v*` tag publishes without a check of the commit.
- Repository settings from the API: issues disabled, Pages off, secret scanning and push protection enabled, Dependabot security updates disabled. Two-factor authentication, default token permissions and fork-PR policy are **not visible**: owner must check.

## 14. Website (planned)

Nothing exists yet. Requirements, to be verified for your country (not legal advice):

1. **Hosting.** GitHub serves the site and logs visitor IP addresses for security, as its privacy statement says. Name GitHub and link the statement. Pages limits and terms (not for commercial use, soft size and bandwidth limits) were not read at source. No custom headers, so the Content-Security-Policy works only as a meta tag and `frame-ancestors` cannot be set. The address `0h3xn4.github.io/WireViz-HarnessDesignStudio/` shows your handle and the name WireViz.
2. **Privacy notice.** No cookies, no browser storage, zero third-party requests: no consent banner is needed under the ePrivacy rule (Art. 5(3)). Zero third-party requests also avoids the Google-Fonts case type (LG München I, 20 Jan 2022, 3 O 17493/20; check the citation). No forms, no analytics.
3. **Imprint.** Depends on your country, which I do not know. Germany (section 5 DDG): applies to services normally offered for remuneration; purely private sites are commonly held exempt; a public software page is borderline. Austria, France and the UK have their own rules. If an imprint is needed it needs a real name and address. That conflicts with brief rule 3 and needs your OK (Q-5).
4. **Accessibility.** The European Accessibility Act (Directive 2019/882, applies since 2025-06-28) covers listed consumer services. A free personal software page is probably out of scope, and microenterprises are exempt. Verify the national law. WCAG 2.2 AA is a quality goal.
5. **Copyright and licences.** Ship the OFL text if the fonts are served and check the Reserved-Font-Name rule if fonts are converted to WOFF2. Include the Lucide (ISC) and Feather (MIT) notices. No ECSS text. No third-party logos. No Ubuntu or Windows badges.
6. **Deployment security.** CSP meta tag, `rel="noopener noreferrer"`, SHA-pinned actions, least permissions (`pages: write` and `id-token: write` only in the deploy job), no deploy before your OK.
7. **Wording.** No promise words. The disclaimer, intended use, AI authorship, project status, non-affiliation and trademark texts from `texts.md`.

## 15. Could not verify

- That any test passes. No test, build or CI was run. Python 3.14 is not available in the sandbox.
- The official trademark registers (USPTO, EUIPO, WIPO, TMview, national offices). Name lookups and `harness.io` and `ecss.nl` were not reachable.
- Contents of the Windows installer `.exe` (assumed equal to the `.zip`).
- The current commit SHAs of the GitHub Actions used.
- Repository and account settings (two-factor, default token permissions, fork-PR policy, existing secrets, private vulnerability reporting, code scanning).
- Whether any release body was edited after publication.
- Who the workshop and AIT participants were. Whether the sibling products named in the docs are yours. Whether any employer, client or university has a claim.
- GitHub Pages terms and the current GitHub privacy wording at source.
- Reuse terms of the ECSS and ESCC documents.
- 381 of 383 screenshots were not viewed.
- Whether the modified `src/wireviz` still produces identical example output.
- Run-time behaviour of the tool (needs Python 3.14).
