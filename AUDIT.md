# Pre-release audit: findings list

Status: findings list from the audit (nothing was changed while auditing). **Critical and high findings are fixed on this branch (see 'Phase 4 status').** Medium findings are fixed on the branch `fix/audit-medium` (see 'Phase 4 status: medium findings'); most low findings are not.

Audited tree: `master` at `956ff71` (Harness Design Studio 0.1.0 plus the WireViz fork it lives in). Audit date: 2026-10-12.

## Owner decisions received (2026-10-12)

- **Q2: yes.** A release freezes the parts, interface types and configuration that the released harness uses (E-5, second half of I-2). To be implemented with the medium fixes.
- **Q31: never change WireViz.** The upstream findings H-1 to H-9 (and all other H-* findings in `src/wireviz/`) are **will not fix**; they stay listed so the README/docs can name them. Only fork-level files (`setup.py`, `MANIFEST.in`, docs) may change.
- **Q32: keep** the distribution name `wireviz` and version `0.4.1` of the root package.

## Phase 4 status: critical and high findings (branch `fix/audit-critical-high`)

Each fix has a test that failed on the old code (the agents ran the new tests against the unmodified source first). Full suite on the merged branch: **1244 passed, 1 skipped, 1 timing test failed once** (`test_gui_perf.py::test_selection_is_fast`, 155 ms against 150 ms; it fails and passes alternately on `master` too, the known open "selection at stress size" item). I also re-ran my own reproductions of F2-1, A-2, C-1, E-1, D-1 and A-3 against the merged branch: all are fixed.

| Finding | Status | Note |
|---|---|---|
| F2-1 (segfault) | fixed | unit height cached and changed only after the scene is told; 5 subprocess paint tests (they segfault on the old code); I also ran the reviewer's crash scripts on flatsat in both modes and 6 random walks: no crash |
| A-2 / E-13 / F1-7 (undo erases saved release) | fixed, **default applied** | undo of a *saved* release/revision/review is refused; unsaved still undoable |
| A-1 (linked/unreadable/oversized file overwritten) | fixed | such files make the project "recovered"; save refuses; CLI refuses too (E-2) |
| A-3 (lone surrogate) | fixed | loader treats it as invalid JSON; writers raise a plain `SaveError`; editor shows a message instead of an exception |
| A-4 / C-1 (wire from a pin to itself) | fixed | new integrity error `wire_to_itself`; verifier no longer raises (`wire_same_pin`, `wire_same_end`) |
| B-1 (up to date despite errors) | fixed | plan with errors is not empty; editor opens the preview |
| B-2 (invalid configuration used) | fixed | validated first, invalid values treated as unset and reported |
| B-4 (naming templates crash/hang) | fixed | falls back to the default with a warning |
| C-2 / F1-4 (DRC failure shown as all clear) | fixed | "Design rule check failed: ..." in the panel and as an error finding |
| C-3 (verifier blind to exchanged pins) | fixed, **default applied** | `Wire.signal` (when set) and written cable-side pin signals must match the pinout |
| C-5 (temperature errors never block) | fixed | finding is per connector/wire use |
| C-6 (silent skips) | fixed | "not checked" notes for missing bundle factor, gauge, length (and C-7, C-18) |
| D-1 (6-digit lengths refuse export) | fixed, **default applied** | full precision in data files, 6 digits only on drawings |
| D-2 (long IDs refuse export) | fixed, **default applied** | font shrinks to 1.4 mm instead of cutting; one exception: a cable-block title with two 64-character IDs is still cut (both IDs appear whole in the connector headers) |
| E-1 (stray quote) | fixed | strict CSV; plain error with the line; nothing imported |
| E-2 / C-13 (damaged project, exit 0) | fixed, **default applied** | all reading and writing commands refuse with exit 2 |
| E-3 / K-2 (XLSX active sheet) | fixed | first visible sheet, named in the output |
| F1-1, F1-2, F1-3 (read-only lost) | fixed | restore and reload keep read-only; the other window's journal is kept |
| F1-6 (export into read-only/damaged) | fixed | |
| F1-8 (bad settings crash) | fixed | |
| F2-2 / F1-12, F2-3, F2-9 | fixed | stale Confirm, filter with "-" or spaces, silent rounding of current/voltage |
| G-1 (undeclared bundled code) | fixed, **default applied** | the six packages are excluded; build fails on anything not on the allow-list; real build and frozen run checked (12 MB smaller, output byte-identical) |
| I-1 (one signal on two fixed pins) | fixed | and B-6 |
| I-2 (release locks) | **partly** | box connectors and units of the baseline are now compared by `check`; locks pinned by tests. **Not done yet:** freezing parts, interface types and configuration (owner said yes; scheduled with the medium fixes) |
| H-18 (my `setup.py` regression) | fixed | |
| H-1 to H-9 (upstream WireViz) | **will not fix** | owner decision: WireViz code is never changed |

Also fixed on the way: C-7, C-18, A-5/F1-10, F1-15/F2-11, F1-3, B-6, parts of B-5 and C-14 (helper deadline of 180 s; `close()` no longer waits on a stuck check; waiting for a long legitimate check on window release is unchanged).

Defaults applied for questions you have not answered yet (change them by telling me): see the **default applied** rows. Also: a read-only session that restores a journal stays read-only (Save As only); a plan with warnings (not only errors) now opens the preview rather than the "up to date" notice; the verifier refuses on integrity errors with the wording "damaged files" because `export` already did, which is slightly wrong for a design error and can be reworded.

## Phase 4 status: medium findings (branch `fix/audit-medium`)

Same method: every fix has a test that failed on the old code (agents ran the new tests against the unmodified source). Full suite on the merged branch: **1735 passed, 2 skipped** (one skip needs a non-root user). `ruff`, `ruff format` and bare `mypy` (which covers `src`, `tests` and `tools`, as CI does) are clean.

**Fixed:** A-5, A-6, A-7, A-8 (and low A-9 to A-12), B-3, B-5, B-6, B-7, B-8 (manual harnesses only), B-9, B-10, B-11, B-12, B-14, B-20 (and most of B-15), C-4 to C-13, C-15 to C-17 (and C-20, C-21, C-24), C-14 (helper deadline of 180 s, close and release no longer wait on a stuck check), D-3 to D-11, D-13 (core side), E-4 to E-12, F1-3, F1-9, F1-11, F1-13 to F1-21, F1-23, F1-28 (partly), F2-4, F2-6, F2-7, F2-12, F2-13, G-2 to G-6, G-8 to G-11, I-3 to I-8, I-12, K-4 to K-7. Several low findings fixed on the way (see the commits and `CHANGELOG.md`).

**Owner decision Q2 (yes) implemented (E-5, I-2):** a release now freezes the parts, interface types and configuration that the released harness uses; `check` reports a change as released-modified; edits are refused while the harness is released ("start a new revision"). Config is frozen as whole files (`derating`, `emc`, `segregation`, `titleblock`) plus eight named `generation` keys, while any harness is released. Waivers are recorded but not locked. Old baselines without these records still load and are not flagged.

**Not fixed or only partly (and why):**
- B-8: a released harness is not part of the generation input hash, because that would make releasing one harness block the next (the release gate refuses a stale generation). Only manual harnesses are included.
- B-13 (a segment cycle that the generator can build in one corner case) is now reported as a rule error (`segment-loop`); the generator itself is unchanged.
- B-16, B-17, B-19, B-21 and the remaining B-22 items: open questions for the owner or low.
- C-19, C-22, C-23: partly (the double report of one wire by two cited rules is kept; some silent skips remain).
- D-12, D-14, D-17: low, not done. D-18 done (headings).
- F1-16 (QAction leak does not reproduce; the stale-entry crash is fixed), F1-27 (strings partly moved), F1-28 (some tests added), F2-10 (newline refused in the interface table only).
- G-12 to G-17: the cheap items done (libc6 >= 2.39, install.sh links, permissions block in CI, library lists, test_docs_links covers the developer and manual folders); not done: action SHA pinning, the `.deb` shipping README/svg under /opt, the `gui_entry --selftest` details, wheel dotfiles, a metrics.json freshness test (it would conflict on every change).
- I-9 (traceability counts a requirement ID that is only mentioned) and I-11 (coverage gate on `core` only, as T-07 defines): left unchanged, owner decisions.
- K-10 (docs promise locking a wire or pin in the app; the app cannot) and the other low K items.

**New behaviour you should know about (defaults, tell me to change them):** `sheet` may be left out of the title block (the verifier skips the sheet-number check then); unknown or duplicate title block fields are an error; PDFs keep Windows-1252 and the export warns by naming each replaced character; a shield's end A is the start of its lowest-ID wire for the whole harness; the CSV apostrophe guard is kept and now reversible (`+5V` still appears as `'+5V`); an import-parts file with a repeated part ID is an error; numbers in imports must be plain (`1,234` is refused as ambiguous); pin counts are 1 to 1000; the numeric ranges of the model (AWG 0 to 40, lengths 0 to 10 000 m, currents and voltages above 0); a project whose lock cannot be taken opens read-only automatically; the rule count is 34 (new rule `segment-loop`); `libc6 (>= 2.39)` in the `.deb`; the release script fails when the version is already a git tag or `## Unreleased` is not empty.

## Phase 5: release readiness (2026-10-12, `master` after PR 43)

**Verdict: the tools are not releasable as 0.1.0, and could be released as a next version once the owner items below are decided.** The code-side blockers found by the audit (critical, high and medium) are fixed on `master`; what remains is a decision or an action only the owner can take. I am not certifying anything: "releasable" here means "I know of no code defect that should stop it", not a compliance statement.

| Checklist item | Status |
|---|---|
| All tests pass | **Yes.** `pytest` in `harness/`: 1735 passed, 2 skipped (one needs a non-root user, one is a browser test that CI runs). CI on PR 43 (Ubuntu 24.04, Python 3.12): green, including the packaging job. `ruff`, `ruff format` and bare `mypy` (src, tests, tools) are clean. One wall-clock test (`test_gui_perf.py::test_selection_is_fast`, limit 150 ms) is borderline on slow machines; it is the known open "selection at stress size" item, not a regression. |
| Help text and docs accurate | **Yes, as far as tests can tell.** `CLI.md`, `RULES.md` and the in-app guide are generated and checked for freshness; the docs tests now compare the quoted output of every tutorial command and the examples README with the real output; all relative links resolve; every `--help` runs. Not checked by a person: the glossary entries marked "(general meaning)" still need an engineer. |
| Version and changelog | **Open (owner).** `pyproject.toml`, `__init__.py` and `CHANGELOG.md` all say 0.1.0 and the tag `v0.1.0` exists; `CHANGELOG.md` has a long `## Unreleased` section. The release script (`tools/release_check`) now refuses this on purpose. Decide the next version number; then the "Unreleased" heading is renamed and the three version strings are changed together. I did not bump it. |
| Dependencies pinned | **Direct dependencies: yes** (exact pins in `pyproject.toml`, build tool pinned, PyInstaller and Playwright pinned in the dev extras). **Transitive dependencies are not locked** (typing-extensions, annotated-types, et-xmlfile, typing-inspection, pydantic-core are resolved at install time); the SBOM lists what the package actually contains. Not done (G-16). |
| No debug output or TODO hacks | **Yes.** No `TODO/FIXME/HACK`, `breakpoint()`, debug prints or secrets in `harness/src` (the only `print` outside the CLI is `--version`). |
| Clean install from scratch | **Verified.** Fresh Python 3.12 virtual environment, `pip install ./harness[gui]` from an exported copy of the tree: `harness --version`, `new --template flatsat`, `validate`, `generate`, `drc`, `verify`, `export` (112 files), `verify --outputs`, a real `release`, then `config --apply-profile` refused by the new release freeze, all `--help` pages, GUI import offscreen. The packaged app (PyInstaller, `tools.build_installer`) was built from the same commit: `--selftest` ok, packaged command line gives the same model hash (`25294117de0d`) and 112 files, no rich/pygments/chardet/lxml inside, 186 MB. |

**Not verified (so not claimed):** the `.deb` and the `install.sh` on a real clean Ubuntu 24.04 machine (`clean-machine-test.sh`), the full non-quick `release_check` (it needs the release container and a new version number), a real display (all editor tests run offscreen), Python 3.13 vs 3.12 differences in the packaged app (it ships its own interpreter), Excel/LibreOffice/Acrobat opening the outputs, and anything on non-Ubuntu systems.

**Owner items that block or shape a release:**
1. Version number and changelog heading (see above).
2. Licence of `harness/` (D-02): the root `LICENSE` is GPL-3.0, `pyproject.toml` says `LicenseRef-Proprietary`, and the `.deb` copyright file still says "to be filled in before distribution". I did not touch it.
3. Attach the packages to the release page; the repository "About" text still describes WireViz.
4. The open engineering decisions already named in `compliance/SIGNOFF.md` (D-10, D-11, D-12, D-15): generation still runs on placeholder values, and every result says so.
5. Known upstream WireViz bugs (H-1 to H-9) are **not fixed by decision** ("never change WireViz"); the most visible ones: PNG output can overwrite an extension-less input file, `&`, `<`, `>` in labels break rendering, YAML words such as `NO` and `ON` become booleans, and the TELALT colour table has a typo. Say if you want them listed in the root README.
6. Answers still open in section 4 (for example the exit-code policy, the undo-history cap, the traceability wording of "traced", whether `cli` joins the coverage gate): the current behaviour is documented in the status sections above.

**What I am still uncertain about:** the release freeze is new and broad (it freezes the whole `derating`, `emc`, `segregation` and `titleblock` files while any harness is released, so with several released harnesses a change to derating needs a new revision of each); this follows your "yes" but it will feel strict in daily use. The editor was tested only offscreen, so look and feel on a real display (drag, drop, the tour, high scale factors) deserves a manual pass before the release. Low-severity findings were mostly left open; they are listed in sections 3 and 5.

## 1. Verdict and summary

**Not releasable as it stands.** The full suite is green, but the audit found defects that lose work, falsify a result, or contradict a documented guarantee. The ones that decide this:

| # | Finding | Why it blocks |
|---|---|---|
| 1 | **F2-1** The editor crashes (segmentation fault, whole program gone) when a connected unit is deleted in Guided mode, or an "Add unit" is undone in Expert mode. Reproduced by me with the flatsat example. | Crash on normal use, unsaved work lost. |
| 2 | **A-2 / E-13 / F1-7** Release, Save, Undo, Save erases the baseline and the change-log entry from disk and unlocks the harness. Reproduced by me. | Breaks the central rule "a released harness cannot be changed or its record removed". |
| 3 | **C-1 / A-4** A wire with the same pin at both ends passes `validate`, then `verify` and `drc` stop with an internal error, and the editor reports "all 33 rules checked" (C-2). Reproduced by me. | Hard failure on bad input plus a false "all clear" in the editor. |
| 4 | **C-3, C-5, C-6** The independent verifier cannot see exchanged pins or changed signals; temperature-margin errors never block a release; current and voltage-drop checks are silently skipped when data is missing. | The checks the project sells as independent are weaker than documented, and silent where "not checked" must be said. |
| 5 | **A-1, E-2, C-13** A damaged, unreadable or linked project file is "saved over" or ignored; most report commands print clean results with exit 0. | Data loss / wrong result without a message. |
| 6 | **D-1, D-2** Normal lengths with more than six digits (CAD mm exports) and long but legal IDs make `harness export` refuse with a message that does not say why. Reproduced by me (D-1). | The main deliverable cannot be produced. |
| 7 | **E-1** One stray quote in an imported CSV swallows the following rows and the import reports success. Reproduced by me. | Silent wrong data. |
| 8 | **I-1, I-2** A fixed-pin connector can carry one signal on two pins with the verifier silent (reproduced by the reviewer); parts and interface types are editable after a release, and `check` ignores the stored units and box connectors (E-4, E-5). | A wrong pinout that looks right; the "released = locked" promise has gaps. |
| 9 | **G-1** The packaged app contains third-party code (rich, pygments, chardet, markdown-it, toml) whose licences and SBOM entries are missing. | Licence compliance of the shipped package. |

Counts, after removing duplicate reports of the same defect: 1 critical, 26 high, 88 medium, 65 low (Harness Design Studio, de-duplicated); upstream WireViz code: 0 critical, 9 high, 9 medium, 5 low. 180 Harness Design Studio findings in total; each has file and line, severity, what is wrong, why it matters and the proposed fix in section 5. Severity is as defined below.

What is good (details under "Checked and found fine" in every area): save is atomic and survived `kill -9` in all 12 trials; round trips are byte-identical for all examples and templates; the lock allowed exactly one winner in 40 races of 8 processes; hostile strings in 17 fields produced well-formed SVG/PDF/XLSX; 33 rules fire on their positive cases; output is identical for any `PYTHONHASHSEED`; the models reject NaN, duplicate keys and control characters; the 1319 relative Markdown links resolve; the packaged app builds and runs end to end; the other generators in `tools/` are idempotent.

### Test-suite status (run by me on `956ff71`, Python 3.13)

`pytest` over the whole `harness/tests` folder on `master` (956ff71), Python 3.13.16, offscreen Qt, run as root: **1038 passed, 1 skipped, 0 failed** (11 min 15 s). The one skip is `test_atomic_lock.py::test_read_only_folder`, which needs a non-root user (CI runs it). An earlier run under coverage, with the machine heavily loaded by the reviewers, had one failure, the wall-clock test `test_stress_generates_fast` (15 s against a limit of 10 s); it did not recur. The suite did not contain a test that fails for any of the findings below, which is the point of Phase 4: each fix will come with a test that fails before it.

The coverage run (95.7 % line and branch coverage of `core/`) shows that a green suite says little about correctness here: of the mutations tried, 40 of 58 in the data layer and 13 of 25 in generation were caught by the tests, and 11 survivors are listed for the DRC (C-16); the survivors are listed per area and by the test-quality reviewer (Area I). Several tests assert nothing (tautologies listed in A-18, B, C-16, D, E-18, F1-28, G-9).

## 2. How the audit was done, and its limits

- **Phase 1 (map).** The structure, entry points, inputs, outputs and dependencies of every tool were mapped and shown to you earlier in this session.
- **Phase 2.** Eleven independent reviewers read the whole code base by area (A data layer, B generation/editing, C DRC/verifier, D outputs/drawing, E change control/CLI/importers, F1 and F2 editor, G tools/packaging/CI, H upstream WireViz, I test quality, K documentation). Each had to *run* the commands, options, bad inputs and edge cases they judged, and give a reproduction for every finding; the findings below were not accepted without one. Some also changed the code in scratch copies to test whether the tests notice (mutation testing); `master` was never changed.
- **My verification.** I re-ran the reproductions for F2-1 (segfault, rc 139), A-2 (release erased from disk), C-1 (verify/drc crash), E-1 (stray quote), D-1 (export refused), A-3 (surrogate crash on save), G-2 (uninstall removes a folder it did not create) and H-2 (upstream: same connector at both ends wired to the wrong pin). All reproduced. The remaining findings rest on the reviewers' evidence; "Confidence" in each entry says *confirmed* (reproduced), *likely* (by reading plus partial run) or *uncertain*.
- **Not covered** (so nothing here says these are fine): behaviour on Windows/macOS/other Linux distributions (the app is Ubuntu 24.04+ only), a real display (all GUI work ran on the `offscreen` Qt platform, as root), Python 3.12 at runtime (the audit machine runs 3.13; CI uses 3.12), power loss, permission-denied cases that need a non-root user (partly covered with `setpriv`), Excel/LibreOffice/Acrobat, KiCad itself, `--system` install and the clean-machine script, network-dependent tools (SBOM, vulnerability check), the PyInstaller package on a machine without development libraries.
- **Severity.** *critical*: crash, data loss or a wrong result that is presented as correct, on normal use. *high*: the same on less common but realistic use, or a documented guarantee that does not hold. *medium*: wrong or misleading behaviour with a workaround, or a missing check. *low*: polish, documentation, latent. † marks a rating where I differ from the reviewer's.
- Upstream WireViz code (`src/wireviz/`) is listed separately (section 3, "Upstream"), because the owner decides whether upstream code in this fork is changed at all. Those bugs also exist in upstream 0.4.1.
- One finding is my own regression: **H-18**. The documentation restructure (PR 39) made `docs/README.md` the documentation index, but the root `setup.py` still uses it as the package description. It is in the upstream table because of the file it sits in, but it is a fork-level defect and a release item.
- Already known and still open, owned by you: the release page assets for v0.1.0, the version decision (master and the release both print 0.1.0), the licence of `harness/` (D-02), the repository "About" text, the glossary entries marked "(general meaning)" that need an engineer's check.


## 3. Findings list (all areas, de-duplicated)

Severity is the lead's rating (reviewers' ratings in the area sections; differences marked †). Rows are sorted by severity, then area. 'Dup' lists reports of the same defect by other reviewers.

| ID | Severity | Area | What | Dup |
|---|---|---|---|---|
| F2-1 | critical | F2 | Segmentation fault: UnitItem.boundingRect changes before prepareGeometryChange/removeItem (stale scene index) |  |
| A-1 | high | A | Unreadable, over-64 MB or symlinked project file is not "recovered": the next save moves it to .bak and regenerates it |  |
| A-2 | high | A | Undo and redo bypass the release locks | E-13, F1-7 |
| A-3 | high | A | A lone surrogate escape ("\ud800") loads clean, then Save, Save As and autosave crash with UnicodeEncodeError |  |
| B-1 | high | B | The GUI says "Harnesses are already up to date" when generation failed with errors |  |
| B-2 | high | B | Generation uses invalid configuration without checking it |  |
| B-4 | high | B | Naming templates can crash or hang generation |  |
| C-1 | high | C | verify_project crashes on a wire whose two ends are the same pin | A-4 |
| C-2 | high | C | Any exception in the design rule check is swallowed by the editor and shown as "Design rules: all 33 rules checked." | F1-4 |
| C-3 | high | C | The verifier never compares Wire.signal or the cable-side pin table with the pinout; exchanging the pins of two wires passes verify, drc and the outpu |  |
| C-5 | high | C | Temperature-margin errors never block a release |  |
| C-6 | high | C | Current and voltage-drop checks silently skip wires when the bundle table has no entry, the gauge is unset or the length is unknown, with no "not chec |  |
| D-1 | high | D | A wire length with more than 6 significant digits makes `harness export` refuse to write |  |
| D-2 | high | D | IDs the model allows (up to 64 chars) make export fail: the drawing truncates them and the verifier calls them "missing" |  |
| E-1 | high | E | A stray double quote in a CSV silently swallows the following rows (import-parts reports success) |  |
| E-2 | high | E | Read-only/report commands ignore damaged project files and print clean-looking results with exit 0 |  |
| E-3 | high | E | XLSX import reads the workbook's active sheet, not the first sheet as documented | K-2 |
| F1-1 | high | F1 | Journal "Restore" after "Open read-only" makes the project editable and lock-less; Save writes into the folder another instance holds (contr |  |
| F1-2 | high | F1 | reload() (check_disk "Reload") drops read-only for a project opened read-only because another instance holds it (controller.py:749-755). Rep |  |
| F1-6 | high | F1 | GUI Export writes outputs into read-only (other instance / newer-version) and damaged (recovered) projects; CLI refuses both (cli/main.py:27 |  |
| F1-8 | high | F1 | Corrupt/hand-edited settings ini crashes the GUI at startup: ui/scale=abc/1.5/empty -> ValueError (main_window.py:1436), ui/geometry=garbage |  |
| F2-2 | high | F2 | Stale properties form after undo/delete of an interface: "Confirm" button of a deleted interface raises KeyError in a slot | F1-12 |
| F2-3 | high | F2 | Interface table filter finds nothing for any text containing "-" or a space (IDs like IF-PWR, two words) |  |
| F2-9 | high | F2 | Properties panel silently rounds Max current / Voltage to 6 significant digits when a field merely loses focus |  |
| G-1 | high | G | Frozen package bundles undeclared third-party code missing from LICENSES and the SBOM |  |
| I-1 | high | I | Fixed-pin allocation: double-booking untested, and a held (locked) pin is ignored on the fixed path (real defect) |  |
| I-2 | high | I | Release locks: tests leave the lock rules unpinned, and two real gaps exist |  |
| A-5 | medium | A | Journal restore silently does nothing if the project has any integrity error; the GUI ignores the result | F1-10 |
| A-6 | medium | A | No numeric domain checks: impossible values load clean and reach the outputs |  |
| A-7 | medium | A | A stale lock can survive a reboot or hostname change; the error gives no way out |  |
| A-8 | medium | A | Saving reads through symlinks: the .bak of a linked file copies outside content into the project |  |
| B-10 | medium | B | A redundant copy duplicates pin assignments onto the twin |  |
| B-11 | medium | B | delete_impact does not detect manual harnesses that plug into the unit |  |
| B-12 | medium | B | Generation wires some invalid inputs onto the same pin without a finding |  |
| B-14 | medium | B | Zone names are not validated; a project with no zones breaks editing |  |
| B-20 | medium | B | Compatibility checks scale as connectors x interfaces |  |
| B-3 | medium | B | Float arithmetic rejects currents that equal the derated limit |  |
| B-5 | medium | B | Templates that give an invalid ID at format time fall back silently |  |
| B-6 | medium | B | A locked fixed pin makes its interface fail and the harness disappear |  |
| B-7 | medium | B | Locked power pins do not enforce the power-to-signal gap |  |
| B-8 | medium | B | generation_status stays "current" after a change that alters the plan |  |
| B-9 | medium | B | Locked wires and user data are lost silently on regeneration |  |
| C-10 | medium | C | direction-conflict is a non-waivable error on wires that generator and verifier both expect |  |
| C-11 | medium | C | Duplicate finding IDs: one object with several problems, one waiver covers all |  |
| C-12 | medium | C | power-return-adjacent is weaker than its message and the requirement it cites |  |
| C-13 | medium | C | harness drc ignores load problems: exit 0 and "0 errors" on a project whose config could not be loaded |  |
| C-14 | medium | C | The DRC helper has no timeout; a stuck check blocks the lock, wait_drc() and process exit; run_check also misses ValueError | F1-5 |
| C-15 | medium | C | Float order of operations: generator and DRC disagree at the exact limit |  |
| C-16 | medium | C | Tests that pass although the code is wrong (mutation results) |  |
| C-17 | medium | C | part-unapproved ignores unverified parts while the release gate counts them |  |
| C-4 | medium | C | Shield groups, wire construction/part and gauge are not verified at all |  |
| C-7 | medium | C | Temperature margin: a missing part rating max_temp_c or a missing margin is silent |  |
| C-8 | medium | C | --apply-profile writes unreviewed standard values into a file marked "placeholder": false and leaves it reviewed |  |
| C-9 | medium | C | bundle_factor_by_count accepts K above 1 (up to 2) |  |
| D-10 | medium | D | The output verifier checks far fewer cells than the docs suggest |  |
| D-11 | medium | D | Cyclic routing-segment graphs are not rejected, and the builder and verifier pick different paths |  |
| D-13 | medium | D | The XLSX build writes temp files and fails with a raw traceback when the temp folder is full; the GUI then reports "cancelled" |  |
| D-3 | medium | D | Pin IDs longer than 7 characters are cut to "XXXXXX~", so different pins look identical |  |
| D-4 | medium | D | The CSV formula guard is lossy, so a signal starting with `'` plus a trigger character breaks verification |  |
| D-5 | medium | D | The title block field list is never validated | K-1 |
| D-6 | medium | D | PDF drawings silently replace characters outside cp1252 with "?", while the SVG keeps them |  |
| D-7 | medium | D | Shield terminations flip sides between sheets of a multi-sheet drawing when the shield's wires run in both directions |  |
| D-8 | medium | D | Same model hash, different bytes: box_pinouts.csv and system.xlsx depend on the insertion order of project.harnesses |  |
| D-9 | medium | D | Negative or absurd lengths are accepted everywhere and produce "complete" negative totals |  |
| E-10 | medium | E | Release is saved before the re-export; if the re-export fails the command exits non-zero but the release stands |  |
| E-11 | medium | E | `harness library`: any bad value is reported as a bad date, and dates are not strict YYYY-MM-DD | K-3 |
| E-12 | medium | E | import-parts: duplicate rows, number parsing, useless per-row messages, unbounded pin count |  |
| E-4 | medium | E | `harness check` / release_integrity ignores units and box connectors stored in the baseline snapshot |  |
| E-5 | medium | E | Parts, configuration and waivers are not frozen or recorded by a release; Baseline.content_hash is never verified |  |
| E-6 | medium | E | Data commands blocked by the release lock: dry-run says OK, the real run gives rc 2 and hides the reasons |  |
| E-7 | medium | E | import-netlist overwrites a user-locked pin and can leave a pin with an interface but no signal |  |
| E-8 | medium | E | `harness compare` says "No differences" when waivers, project name, zones, library info and layout differ |  |
| E-9 | medium | E | Ctrl-C prints a Python traceback |  |
| F1-11 | medium | F1 | ImportDialog: after an edit makes CSV invalid, OK stays enabled with previous plan and imports it (dialogs.py:360-367). t22.py: IF-900 impor |  |
| F1-13 | medium | F1 | ToastHost drops a repeated message even when it carries a new Undo; old Undo button then reports "no longer the latest" (main_window.py:178- |  |
| F1-14 | medium | F1 | Toolbar filter value list refreshed only on full Delta (main_window.py:810-813): empty after Generate; after undo of generation filter targe |  |
| F1-15 | medium | F1 | connect_from not reset when source unit deleted/undone: second click raises EditError out of pick() (controller.py:401-432). t30.py. | F2-11 |
| F1-16 | medium | F1 | _rebuild_connect_menu leaks QActions (window.addAction in _act, never removed); stale "CAN" palette entry runs _toggle_connect on missing ty |  |
| F1-17 | medium | F1 | check_disk: project deleted or project.json removed -> LoadError escapes slot on every window activation (main_window.py:1406-1418, controll |  |
| F1-19 | medium | F1 | PlanWorker/OutputsWorker exceptions shown as "Generation cancelled"/"Export cancelled"; PlanWorker.error never set (main_window.py:102-152). |  |
| F1-20 | medium | F1 | Progress dialog not shown for first 400 ms (setMinimumDuration) so UI is live while worker reads live project; edits possible (t26.py); appl |  |
| F1-21 | medium | F1 | Project on read-only media cannot be opened even read-only (lock acquire first, SaveError naming .harness.lock.takeover) (controller.py:665- |  |
| F1-23 | medium | F1 | Status "Unsaved changes (autosaved to the recovery journal)" shown for sample/no-folder project where nothing is autosaved (strings.py UNSAV |  |
| F1-28 | medium | F1 | Weak tests: mutation removing follower logic from _delta_of -> 93 tests pass (journeys/changes/audit_gui/filters/readability); test_cancelle |  |
| F1-3 | medium | F1 | Read-only open: "Discard them" / Save-As clear_journal() deletes the OTHER instance's autosave journal (main_window.py:1359-1362, controller |  |
| F1-9 | medium | F1 | New project / example with invalid name (>200 chars or control chars) -> pydantic ValidationError escapes new_project_flow (catches HarnessE |  |
| F2-12 | medium | F2 | With the Connect tool active, dragging a unit moves it on screen but never in the model |  |
| F2-13 | medium | F2 | Switching to Expert mode does not grow the scene: the lowest units end outside the scene rectangle and the lane backgrounds |  |
| F2-4 | medium | F2 | Legend is not repainted when the kinds of link in use change (stale key) |  |
| F2-6 | medium | F2 | A unit can be dragged outside the scene rectangle and then cannot be reached (negative / far positions are saved) |  |
| F2-7 | medium | F2 | Tour highlights hidden panels at high UI scale / small windows; closing the window within 200 ms of the first-run start prints a RuntimeError |  |
| G-10 | medium | G | The GitHub Actions template is weaker than build.sh; the README says "the same" |  |
| G-11 | medium | G | gen_scf: exits 0 with an empty SHA256SUMS; source manifest depends on the environment |  |
| G-2 | medium | G | uninstall.sh removes folders it did not install and still says "Your projects are not touched" |  |
| G-3 | medium | G | install.sh can delete its own unpacked package |  |
| G-4 | medium | G | Ownership of installed files comes from whoever unpacked or built the tarball |  |
| G-5 | medium | G | The versions step of release_check passes vacuously; the release can reuse 0.1.0 |  |
| G-6 | medium | G | build_deb is not reproducible unless SOURCE_DATE_EPOCH is set; the unit test masks this |  |
| G-7 | medium | G | XLSX output bytes depend on whether lxml is installed |  |
| G-8 | medium | G | Release gate skips tests silently and passes |  |
| G-9 | medium | G | soak's "undo then redo restores the exact model" is a vacuous assertion |  |
| I-10 | medium | I | Goldens: what proves them correct |  |
| I-11 | medium | I | Coverage gate scope and the uncovered core code that matters |  |
| I-12 | medium | I | Skips, environment dependence and flakiness |  |
| I-3 | medium | I | No test pins any exact limit of a rule or gate (boundary survivors) |  |
| I-4 | medium | I | Formula-injection escaping is only partly tested |  |
| I-5 | medium | I | Other untested behaviours (survivors) |  |
| I-6 | medium | I | Verifier mutation tests do not say which check fires |  |
| I-7 | medium | I | Static guards have blind spots |  |
| I-8 | medium | I | Vacuous, tautological or crash-only assertions (all read; line numbers in this tree) |  |
| I-9 | medium | I | The traceability gate checks that a requirement ID is mentioned, not that it is verified |  |
| K-4 | medium | K | `harness generate` piped to a program that closes early is not saved, and the error text is wrong |  |
| K-5 | medium | K | The "outputs outdated" error carries the wrong explanation (wires do not match) |  |
| K-6 | medium | K | The in-app guide (index.html) is not identical to USER_GUIDE.md: a table row is broken |  |
| K-7 | medium | K | Documentation tests do not compare quoted output, so the docs can drift (and have) |  |
| A-10 | low | A | New files ignore the umask; lock helper litter in non-project folders |  |
| A-11 | low | A | Temp files from a killed save are never cleaned up |  |
| A-12 | low | A | Editor schemas: library/manifest.json matches two schemas; ID rules missing |  |
| A-13 | low | A | Loading many set-aside objects is quadratic |  |
| A-14 | low | A | Unbounded undo history; every edit runs the whole-model integrity check twice |  |
| A-15 | low | A | "Frozen" is shallow; caches cannot see in-place list changes |  |
| A-16 | low | A | Text validation holes: dates, format characters, zones, no normalisation |  |
| A-17 | low | A | Referential gaps in check_integrity |  |
| A-18 | low | A | Weak or tautological tests |  |
| A-9 | low | A | Migration backup is trusted if the folder merely exists |  |
| B-13 | low | B | Segment graph can contain a cycle |  |
| B-15 | low | B | Edit operations are inconsistent about how they fail |  |
| B-16 | low | B | The explanations (Explain tab) contain imprecise text |  |
| B-17 | low | B | Segregation settings do not behave as documented |  |
| B-18 | low | B | Interface current and default gauge are unvalidated |  |
| B-19 | low | B | A multi-colour wire is printed with a truncated colour code |  |
| B-21 | low | B | Mass can say "Complete: yes" while leaving out parts |  |
| B-22 | low | B | Smaller items |  |
| C-18 | low | C | voltage-drop skips gauge 0 (AWG 0) |  |
| C-19 | low | C | current-over-wire and bundle-current report the same wire twice; the "derating not checked" note is wrong when the table replaces the single factor |  |
| C-20 | low | C | Profile table is shared by reference with project data |  |
| C-21 | low | C | Config validation gaps |  |
| C-22 | low | C | Silent skips and small inconsistencies in rules |  |
| C-23 | low | C | Verifier independence and ID stability |  |
| C-24 | low | C | Documentation mismatches |  |
| D-12 | low | D | Wire loops below a cable block (wires with both ends on one side) are not counted by pagination and can run into the title block |  |
| D-14 | low | D | write_outputs partial-failure details |  |
| D-15 | low | D | The harness overview draws only the first and last unit of a harness |  |
| D-16 | low | D | In a long routing-sketch chain the segment length can be cut off |  |
| D-17 | low | D | core/routing.py preconditions |  |
| D-18 | low | D | Miscellaneous |  |
| E-14 | low | E | Control characters, long text and newlines in --by/--comment/--checker/reasons: wrong exit code, log and report injection |  |
| E-15 | low | E | Date handling in review/release/revise |  |
| E-16 | low | E | KiCad XML: the DOCTYPE/entity guard is bypassed by UTF-16 without BOM (and UTF-32). Known item, now reproduced. |  |
| E-17 | low | E | Output and exit-code polish |  |
| E-18 | low | E | Test gaps found by reading |  |
| F1-18 | low | F1 | "Keep my version" is not remembered (fingerprint unchanged): box closing re-activates window and re-asks. t29.py: 2 dialogs from one check. |  |
| F1-22 | low | F1 | Open on a non-project folder leaves .harness.lock.takeover in it (t34.py). |  |
| F1-24 | low | F1 | Explicit "Discard changes" on close leaves journal; next start offers Restore (t36.py). |  |
| F1-25 | low | F1 | Opening the folder that is already open offers "already open in another window", and Read-only choice releases own lock (t1.py). |  |
| F1-26 | low | F1 | Accessible names missing: IssuesDialog list, HistoryDialog list, DiffDialog combo+list (t23.py); test_accessibility does not open them and a |  |
| F1-27 | low | F1 | Many UI strings outside strings.py (controller messages, labels, dialogs.py:326 headers, "Arrange diagram", etc.); main_window.py:873 string |  |
| F2-10 | low | F2 | Interface table / model accepts a newline in Name, Arabic-Indic digits in numeric cells; invalid chain text fails silently |  |
| F2-14 | low | F2 | Label chip registry is stale after the link values are edited (update_path is a no-op inside the batch) |  |
| F2-5 | low | F2 | OutlinePanel keeps the old highlighted row after the selection is cleared |  |
| F2-8 | low | F2 | Long IDs / connector names are clipped without an ellipsis on the canvas |  |
| G-12 | low | G | Deb `Depends: libc6 (>= 2.35)` is asserted, not computed, and a test locks it in |  |
| G-13 | low | G | Several smaller packaging and installer issues |  |
| G-14 | low | G | CI details |  |
| G-15 | low | G | Staleness and drift in generated and compliance records |  |
| G-16 | low | G | Wheel and dependency hygiene |  |
| G-17 | low | G | A test writes into the source tree |  |
| I-13 | low | I | Documentation mismatch about the mini3 golden |  |
| K-10 | low | K | "Lock a wire or pin" is presented as a feature, but neither the app nor the CLI can lock |  |
| K-11 | low | K | `import-lengths` reads columns by position; the shipped README and IMPORTS.md say or imply header matching |  |
| K-12 | low | K | Missing netlist file reports "The netlist must be a regular file." |  |
| K-13 | low | K | CHANGELOG "Unreleased" bullets that are not true |  |
| K-14 | low | K | Messages and help refer to files that are not installed, and use internal IDs |  |
| K-15 | low | K | CLI.md (generated) small inaccuracies |  |
| K-16 | low | K | Small wording errors |  |
| K-17 | low | K | `.harness.lock.takeover` is an undocumented permanent file |  |
| K-18 | low | K | Editor settings written by `harness schema` map `library/manifest.json` to two schemas |  |
| K-19 | low | K | A zero or negative `max_current_a` is accepted |  |
| K-8 | low | K | Flatsat export file count is 112, three places say 111 |  |
| K-9 | low | K | CONFIG.md: `max_ambient_temperature_c` is "recorded for reference", but it drives an error-level rule; `emc.classes` is read by nothing |  |

### Upstream WireViz code (owner decides whether it is touched at all)

| ID | Severity | What |
|---|---|---|
| H-1 | high | Generating PNG can overwrite and delete an existing file, including the input YAML |
| H-2 | high | Same connector at both ends of a cable, addressed by pin labels, is wired wrongly |
| H-3 | high | Connector `loops` use the pin ID as the Graphviz port number |
| H-4 | high | No escaping of &, <, > in text fields: render fails, and the &amp; workaround pollutes the TSV |
| H-5 | high | YAML 1.1 scalars turn labels into booleans or numbers silently; undocumented |
| H-6 | high | TELALT colour code: first five pairs have a one-colour ring (table typo) |
| H-7 | high | parse(output_formats="png") (a string) writes nothing or crashes although documented as allowed |
| H-8 | high | parse() keeps state in a mutable default, mutates its input, and rejects Path/str for image_paths |
| H-9 | high | Cable wire numbers are not validated: wire 0 takes the last wire's colour silently; wire above wirecount fails late; `s` on an unshielded cable accept |
| H-10 | medium | Arrow (mate) pins are not mapped from labels or checked |
| H-11 | medium | Wrong top-level structure silently ignored; duplicate keys silently dropped |
| H-12 | medium | `--prepend` silently loses sections when both files have the same top-level key |
| H-13 | medium | Templates are searched next to the output, but documented as next to the YAML |
| H-14 | medium | HTML and SVG output contain unescaped user text, including attribute injection |
| H-15 | medium | Bad types crash with unhelpful exceptions (no component name or key) |
| H-16 | medium | AWG/mm2 conversion table: inconsistent and number-format sensitive |
| H-17 | medium | Non-UTF-8 locale (e.g. Windows cp1252) crashes SVG/HTML output and leaves temp files |
| H-18 | medium | Packaging (fork): description is the docs index; unreliable file read; no python_requires; same name and version as upstream |
| H-19 | low | Documentation and data inconsistencies |
| H-20 | low | Cosmetic or consistency bugs in output |
| H-21 | low | Dead code and latent errors |
| H-22 | low | CLI behaviour that differs from what it prints, and error handling |
| H-23 | low | tweak.override values are used as regex replacement templates |

## 4. Questions for the owner (intended behaviour is unclear; nothing will be decided silently)

These are the points where the code and the documents say different things, or where a fix would change behaviour. The finding IDs show where each comes from. Please answer by number; "your call" is a valid answer for any of them.

**Change control and data safety**

1. **Undo of a release (A-2 / E-13 / F1-7).** Today a release is one undoable step, and "undo" also works after Save, which deletes the baseline and change-log entry from disk. D-102 says "undoable until saved". Proposed: undo of a release/revise step is refused once the project has been saved (and the undo stack is cleared on save). Alternative: refuse it always. Which?
2. **What a release freezes (E-4, E-5, A-17, I notes).** A release stores units and box connectors in the baseline but only compares the harness and its interfaces; parts, configuration, interface types and waivers can change after release without any finding. Should parts (approval, mass, pin count), configuration and waivers be frozen or at least compared? Proposed minimum: compare snapshot units and box connectors, and record the used parts' approval status.
3. **Damaged projects (A-1, C-13, E-2).** Proposed rule: every command that reports or writes refuses (exit 2, damaged files named) when the project has load errors, as `export` and `migrate` already do. Is exit 2 right for the read-only reports (`drc`, `verify`, `log`, `diff`, `compare`, `config`, `library`)?
4. **Journal and read-only sessions (F1-1, F1-2, F1-3, A-5).** Proposed: "Restore journal" never turns a read-only session into an editable one and never deletes another instance's journal. Agreed?
5. **Locks (A-7).** If a lock file survives a reboot or comes from another computer, what is the policy? Proposed: store the process start time/boot id and treat a mismatch on the same computer as stale; print the lock file path in the error; for another computer keep the lock and say how to remove it.

**Numbers and units**

6. **Valid ranges (A-6, B-18, D-9, K-19, C-21).** Proposed: AWG 0 to 40 (integer), length ≥ 0 and ≤ 10 000 m (the import limit), current > 0, voltage > 0, pin count 1 to 1 000, masses ≥ 0, `next_harness_number` ≥ 1, `schema_version` ≥ 1. Is a length of 0 ever meaningful? Are these bounds acceptable?
7. **Precision of table numbers (D-1).** Tables print 6 significant digits, the verifier compares exactly. Proposed: write full precision (shortest round-trip repr) in CSV/YAML/XLSX; keep rounding only for display text. Or keep 6 digits and compare with the same rounding. Which?
8. **"1,234" in imports (E-12).** Decimal comma (1.234) or thousands separator (1234)? Today it becomes 1.234. Proposed: reject ambiguous input with a message. And pin-count upper bound (1 000)?
9. **IDs longer than the drawing can show (D-2, D-3).** The model accepts 64-character IDs, 16-character pin IDs; the drawing truncates at about 33/62/7 characters and the verifier then refuses the export. Proposed: lower the model limits to what the drawing can show (connector 32, wire 60, pin 10) with a clear message, or never truncate (wrap/shrink). Which?

**Meaning of signals and checks**

10. **`Wire.signal` (C-3).** Is it a label derived from the pinout (verifier must check it and the cable-side pin table) or free text on hand-drawn harnesses? Proposed: derived; verifier checks it when set.
11. **Shields in the verifier (C-4).** Should a missing shield group, or a wire construction/gauge/part that differs from the plan, be a verifier error? Proposed: shield group presence yes; gauge/colour/part no (document it).
12. **Unpaired directional signals (C-10).** CLK (out) generated end to end is reported as "joins two outputs" and blocks release. Proposed: the rule skips signals that the generator wires straight through, or the signal definition gets a "pass-through" flag.
13. **Power/return spacing (C-12).** Requirement text asks for an unassigned contact between power and return; the rule counts only list distance of the same interface. Proposed: count unassigned pins in the window and consider all power/ground pins. OK?
14. **Profile and placeholder flag (C-8).** `--apply-profile` currently leaves `"placeholder": false` on files that now contain unreviewed standard values. Proposed: set placeholder back to true for any file the profile changes. OK?
15. **Unverified parts (C-17).** Report them in the DRC rule (as the release gate does), or only at release?
16. **Mass (B-21).** SPEC says mass includes shielding, sleeving, backshells and tie-downs; the code sums cable connectors and wires only and says "Complete: yes". Add a "not included" note, or add the missing items?
17. **Segmentation settings (B-17).** `forbid_nominal_with_redundant=false` still separates; `category_pairs_to_separate` over-separates. Fix the code or the document?
18. **Multi-colour wires (B-19).** `yellow/green` is stored but drawn grey with a truncated code. How should multi-colour wires be written and drawn?
19. **Regeneration losing locked wires (B-9, B-8).** Should regeneration refuse (or warn loudly) when a locked wire or entered segment lengths would be dropped, and should a change of released status or manual harnesses make generation "stale"?
20. **Looped segment graphs (D-11, B-13).** Are loops legal? Proposed: DRC error for non-tree segment graphs.

**Output and documents**

21. **Title block fields (D-5 / K-1).** Is `sheet` mandatory? Proposed: yes, always shown; unknown names and duplicates rejected by `configcheck`.
22. **CSV guard (D-4).** `+5V` and `-12V` are written as `'+5V` in every CSV. Keep (spreadsheet safety) or write them plainly and quote?
23. **PDF characters (D-6).** PDF drops characters outside Windows-1252 (Ω, Δ shown as "?"). Embed a Unicode font, or warn in the export report and document?
24. **Shield "end A" (D-7)** with wires running both ways, and **harness overview with 3+ units (D-15).** What should they mean?
25. **XLSX byte identity across machines (G-7).** Bytes depend on whether `lxml` is installed. Proposed: force `OPENPYXL_LXML=False` so the packaged app and a developer checkout agree. OK?
26. **Release gate script and version tags (G-5).** The gate passes while `v0.1.0` already exists and "Unreleased" is full. Proposed: fail when the version is already tagged or "Unreleased" is not empty at release time.
27. **CI template and DRC (G-10).** Should unwaived DRC errors fail the CI template (build.sh does, the Actions workflow does not)?
28. **Bundled third-party code (G-1).** The packaged app contains rich, pygments, markdown-it, chardet, toml and others that are not in the licence notices or SBOM. Proposed: exclude them from the package (they are build-time only); if that is not possible, ship their licences. Which?
29. **Locking from the app (K-10).** The docs promise "lock a wire or pin" but neither the app nor the CLI can do it. Add the control, or reword the docs to "edit the harness file"?
30. **Date policy for review/release (E-15)** and **segregation of duties (E-14 note):** may author, checker and approver be the same free-text name? May a release be dated before its review?

**Whole-project decisions**

31. **Upstream WireViz code.** Most of its bugs (H-1 to H-9) have small fixes. Change upstream code in this fork at all, or only document the known problems in the README? (A note: changes to `src/wireviz/` make future upstream merges harder.)
32. **Distribution name and version of the fork root package (H-18).** The root `setup.py` still builds `wireviz 0.4.1`, the same name and version as upstream on PyPI. Rename/re-version, or leave and document?
33. **Licence (D-02) and `.deb` copyright text (G-13).** The `.deb` copyright file says "to be filled in before distribution"; the root LICENSE is GPL-3.0 while `harness/` says LicenseRef-Proprietary. This has to be decided before any distribution; I will not choose it.
34. **Undo history size (A-14).** About 1.5 MB per retained step at stress size. Cap at a fixed number of steps (e.g. 200)?
35. **Exit-code policy (E-17).** The CLI documents 0/1/2; several commands use 1 and 2 differently (import row errors, config problems, missing `--unit`). Proposed: 0 ok, 1 findings/blocked, 2 usage or damaged/unreadable, and update CLI.md.


## 5. Detailed findings by area

Each entry: file and line, what is wrong, why it matters, proposed fix, confidence, and whether an owner decision is needed. IDs are the reviewers' own (letter = area). Paths are relative to `harness/` unless they start with `src/`, `.github/` or are upstream files.


### Area A: Data layer and persistence

(Saved by the lead from the reviewer's hand-back. 18 findings: 3 high, 5 medium, 10 low, 0 critical. Scratch: audit/A/.)
Files read completely: core/model/* (all 9), core/io/{canonical,fs,layout,loader,migrate,saver}.py, core/{ids,units,errors,issues,integrity,recovery,schemas,commands,starter,templates}.py; also core/vcs/locks.py, parts of vcs/release.py, vcs/consistency.py, edit.py, cli/main.py, cli/data.py, gui/controller.py, gui/main_window.py (open/save/journal). Tests: helpers, test_model, test_io, test_atomic_lock, test_integrity, test_integrity_cache, test_commands, test_migrate, test_schemas, test_units_ids, test_soak, test_recovery, test_recovery_journal, test_fuzz, test_error_locations, test_security (no test_templates file exists).
Ran: round trips (mini3, sat15, sat15_full, 5 templates), pydantic strictness barrage, 36 structural mutations through all stages, kill -9 during save (12 trials), lock race 8 procs x 40 trials, 3 concurrent generates, links/permissions (setpriv drop of dac_override), 70 MB file, read-only dirs, umask 077, CRLF+BOM, nesting depth 50-996, lone surrogates, 32000 quarantined items, journal restore, undo of release, History memory/time at stress, JSON Schemas vs saved files, hypothesis fuzz 600 examples, 58 hand mutations in a scratch copy.
Not covered: case-insensitive FS/Windows, power loss, widget-level GUI.

#### A-1 [high] Unreadable, over-64 MB or symlinked project file is not "recovered": the next save moves it to .bak and regenerates it
- Where: core/io/loader.py:83-93 (`symlink_ignored`, `file_too_large`, `file_unreadable` are issues only, not in `quarantine_files`); core/io/saver.py:210 (guard checks `project.recovered` only), :266-273 (stale file renamed to .bak); cli/main.py:100-117 and cli/data.py save without checking has_errors (only migrate/export check, main.py:283).
- Evidence (normal user via setpriv): `chmod 000 perm/physical/harnesses/W008.json`; `harness validate` ERROR file_unreadable; `harness generate perm` -> "1 added, 1 changed, 6 unchanged..." rc 0, no mention; `ls` shows W008.json.bak (mode 000) and a new W009.json. Same with a 70 MB file and with the file as a symlink. A symlinked project.json loads as "Untitled project" and the real name is overwritten; a symlinked/too-large changelog.json or baselines/*.json is treated as absent.
- Fix: put these files in `broken` so the project counts as recovered, or make save_project refuse when load had error issues; every mutating CLI command stops on loaded.has_errors like migrate/export. Test: load with one chmod 000 harness; save must raise; CLI generate non-zero.
- Confidence: confirmed. Owner decision: no (Q2 below).

#### A-2 [high] Undo and redo bypass the release locks
- Where: core/commands.py:429-452 (execute calls check_locks) vs 466-480 (undo/redo only apply_ops); GUI release is one undoable step: gui/controller.py:278-283, 596-600.
- Evidence (undorel.py, sat15_full): release+save; undo -> status draft, baselines [], changelog []; save removed baselines/W001/W001.A.json and changelog.json (kept as .bak); harness edited without a new revision.
- Why: D-105/D-126 say baselines and change log "cannot be deleted or replaced"; one keystroke erases the record even after save/export; changelog.json disappears including earlier entries.
- Fix: clear the undo stack on save, or refuse undo/redo of steps that put baselines/change-log entries, or run check_locks on inverse ops. Test: release, save, undo must raise; baseline file still exists.
- Confidence: confirmed. Owner decision: YES (is undoing a release in the same session intended?). (Also reported as E-13.)

#### A-3 [high] A lone surrogate escape ("\ud800") loads clean, then Save, Save As and autosave crash with UnicodeEncodeError
- Where: core/io/canonical.py:7-9 (ensure_ascii=False then .encode("utf-8")); loader.py:95 accepts the escape; saver.py:261-262 (quarantine.json); recovery.py:407 (journal); handlers catch only HarnessError/OSError: gui/main_window.py:1367-1399, controller.write_journal_now.
- What: Name/Text reject surrogates, but ConfigFile.values (dict[str, Any]) and every quarantined raw accept them; UnicodeEncodeError is a ValueError, not a HarnessError.
- Evidence: config/naming.json with "extra": "x\ud800y": `harness validate` 0 errors; save_project raises UnicodeEncodeError; CLI generate prints "error: 'utf-8' codec can't encode character '\ud800'...". Unit notes with \ud800 -> unit quarantined, project recovered; Save As (the only way out) and the autosave journal raise; Save As writes other files before failing on quarantine.json, so the new folder is partial.
- Fix: loads_strict treats a lone surrogate as invalid JSON (file kept verbatim in quarantine_files); catch ValueError in GUI save/autosave paths. Test: fuzz strategy with surrogates then save_project/write_journal.
- Confidence: confirmed. Owner decision: no.

#### A-4 [medium] A wire with the same connector and pin at both ends passes integrity, then crashes verify and drc
- Where: core/integrity.py:126-134 (no rule); core/verify.py:214 and 223 (`a, b = sorted(conn)` on a one-element frozenset). Same as C-1. Evidence: validate 0 errors; check 0 errors; `harness verify` / `harness drc`: "error: not enough values to unpack (expected 2, got 1)". 600-example fuzz did not find it.
- Fix: integrity error `wire_to_itself` and make verify tolerate a one-element set. Test: add to test_integrity.NEGATIVE and verify tests.

#### A-5 [medium] Journal restore silently does nothing if the project has any integrity error; the GUI ignores the result
- Where: gui/controller.py:688-697 (`if res is None or res.has_errors: return False`); gui/main_window.py:1349-1356 ignores the return; core/recovery.py:28-32 has `base_fingerprint` never passed or read.
- Evidence: project with a missing units file (pre-existing errors, not recovered); edit; journal written; open_path -> journal_available() True; restore_journal() returns False; session still shows `OBC notes ''`. Next autosave replaces the journal. Because base_fingerprint is unused, a journal made before a `git pull` is restored over pulled files with no warning.
- Fix: refuse only when res is None; message when restore fails; store/compare base_fingerprint. Test: journal round trip with a pre-existing dangling reference.

#### A-6 [medium] No numeric domain checks: impossible values load clean and reach the outputs
- Where: model/physical.py (gauge_awg, length_m), library.py (pin_count, mass_g, mass_per_m_g, ratings), logical.py (impedance_ohm, max_current_a, voltage_v, default_gauge_awg), generation.py (next_harness_number), project.py (schema_version), review.py (x, y).
- Evidence: accepted: gauge_awg 999, -5, 10**400; length_m -1; pin_count -3 and 0; negative masses; next_harness_number -5; schema_version -1, 0, 10**30. Flatsat copy: W001-001 gauge_awg 999 and W001-002 length_m -3.5: validate 0 errors; export writes `-3.5` into wirelist.csv; AWG 999 caught only by DRC voltage-drop; the negative length appears in no finding; schema_version -1 read as current and rewritten as 1.
- Fix: Field(ge/le) constraints or integrity rule per field. Owner decision: YES (is length 0 / negative ever meaningful?).

#### A-7 [medium] A stale lock can survive a reboot or hostname change; the error gives no way out
- Where: core/io/fs.py:237-245 (same host and os.kill(pid,0) succeeds = live; other host = live); cli error text; docs/TROUBLESHOOTING.md:155 mentions deleting the file only for the other-computer case. `since` stored, never used; CLI text says "open this copy read-only" which doesn't exist for CLI.
- Evidence: by reading + existing test_live_local_lock_blocks (pid 1). Fix: store /proc/<pid> start time or boot id and treat a mismatch as stale; print the lock file path in the error. Confidence: likely. Owner decision: YES (policy for other hosts).

#### A-8 [medium] Saving reads through symlinks: the .bak of a linked file copies outside content into the project
- Where: core/io/fs.py:133-139 (shutil.copyfile(target, bak_tmp) follows links); saver.py:256 (`path.is_file() and path.read_bytes()`); saver.py:243-246 (migration backup).
- Evidence: waivers.json symlink to ../secret.txt; load warns symlink_ignored; after a save that wrote waivers.json, the new real waivers.json.bak (mode 600) contained "TOP SECRET OUTSIDE". Writes are safe; reads are not.
- Fix: skip the backup or rename the link when target.is_symlink(); same in migration backup. Test: extend test_symlinked_project_files_are_ignored_not_followed with a save and a search for the secret.

#### A-9 [low] Migration backup is trusted if the folder merely exists
- core/io/saver.py:241-247 (`if not backup.exists()`); result.backup_dir set regardless. Evidence: `.migration-backup-v0` as a symlink to an existing empty folder: `harness migrate` prints "originals are kept in a .migration-backup-* folder" and the target stays empty; dangling link: "File exists". Fix: build under a temp name and rename when complete; refuse links.

#### A-10 [low] New files ignore the umask; lock helper litter in non-project folders
- core/io/fs.py:125 (`else 0o644`); fs.py:199-205 (guard file created before anything is checked). Evidence: `umask 077; harness new um` gives 644 project.json inside 700 dirs; `harness generate notproj` leaves a 0-byte .harness.lock.takeover; on an unwritable folder the error says "read-only ... '.harness.lock.takeover'" instead of "not a project"; .gitignore written once so older projects lack the takeover line. Fix: 0o666 & ~umask; lock only folders with project.json.

#### A-11 [low] Temp files from a killed save are never cleaned up
- core/io/fs.py:102-107, 147-150 (cleanup only in finally). Evidence (12 kills): 5 left `.aocs.json.4j31mntn.tmp`-style full copies of design data; later saves leave them. In all 12 trials every file was whole JSON. Fix: sweep stale `.*.tmp` at save.

#### A-12 [low] Editor schemas: library/manifest.json matches two schemas; ID rules missing
- core/schemas.py:49 (`library/*.json` also matches manifest.json); Id/PinId use AfterValidator, not exported to JSON Schema. Evidence: manifest.json fails schema 'parts'; matches>1 [('library/manifest.json', ['library-info','parts'])]; schema for units.id is {"title":"Id","type":"string"} no pattern; test_schemas picks first match with next(...). Fix: disjoint patterns; add `pattern` for IDs.

#### A-13 [low] Loading many set-aside objects is quadratic
- core/io/loader.py:126-157 (_add_lines re-reads and rescans per quarantined object). 2000 bad units 0.3 s; 8000 1.8 s; 32000 (3 MB) 29.6 s. Fix: one pass per file.

#### A-14 [low] Unbounded undo history; every edit runs the whole-model integrity check twice
- core/commands.py:419-452; core/integrity.py (pins() rebuilt each call). Stress project: 300 edits of the biggest harness 185 ms each (~90 ms per check_integrity, two per edit); RSS 264 -> 736 MB (~1.5 MB per retained step); unit edits 110 ms; History.execute("x", []) pushes an empty undo step and clears redo (GUI guards, CLI doesn't). Owner decision: YES (cap or compress?).

#### A-15 [low] "Frozen" is shallow; caches cannot see in-place list changes
- core/model/base.py:11-13; core/io/layout.py (_HARNESS_CACHE keyed by id(h)); core/integrity.py:48-250. h.wires.pop() leaves model_hash unchanged so a save would write stale cached bytes; no code mutates in place (grep) so latent. Also by reading: integrity cache token (integrity.py:215-221) does not include the owning harness's `generated` flag used by _check_connector.

#### A-16 [low] Text validation holes: dates, format characters, zones, no normalisation
- core/model/library.py:34-37, model/base.py:23-30, core/io/loader.py:198-202. LibraryInfo.date accepts 20240101 and 2024-W01-1; names accept newline, U+202E, U+200B, U+2028, private-use, whitespace-only; no NFC normalisation (NFC vs NFD é differ; duplicate-signal and Pin.signal matching use exact strings); layout.json zones with control characters or 100000 chars load clean; released_on "soon" and revision "é ü 1" load clean. Owner decision: YES.

#### A-17 [low] Referential gaps in check_integrity
- All gave integrity []: Connector.carries naming a non-existent interface type; Part.mates_with naming a non-existent part or itself; a waiver whose object_id doesn't exist (ops_rename_unit edit.py:560-588 leaves such waivers behind); change-log entry or baseline for a non-existent harness; baseline id != `<harness_id>.<revision>`; status released with no baseline is not an integrity error (only check/DRC release_integrity); case-insensitive duplicate detection omits baseline IDs (revisions "A" and "a" collide on case-insensitive FS).

#### A-18 [low] Weak or tautological tests
- tests/test_recovery_journal.py:247 `assert read_journal(root) is None or read_journal(root) is not None`; tests/test_fuzz.py:561-563 asserts a constant; tests/test_security.py:93-103 oversized-file test accepts `or result.has_errors`; :182-202 first loop asserts paths start with tmp_path; tests/test_integrity.py:212-214 asserts >= 14 codes, :216 test_part_object_unused tests nothing. Mutation (58, my subset): caught 40. Survived: drop directory fsync; drop O_NOFOLLOW on the lock temp file; drop flock guard around lock takeover; ignore a lock from another host; remove top-level symlink check in save_project; remove link check before renaming stale files; change write order (generation.json/project.json last); allow_nan=True in canonical.dumps; ensure_ascii=True; unsorted harness sub-lists in serialize; cache token ignoring duplicate wire IDs; wrong rollback order in apply_ops; "second error with same key counts as new" in History.execute; revision not incremented on execute; wrong undo of SetConfig for a new config; allowing U+FFFE in names; journal dropping its quarantine list; create_project overwriting a non-empty folder.

##### Checked and found fine
Round trip byte-identical for mini3, sat15, sat15_full and all 5 templates; model_hash holds; unchanged save writes nothing; CRLF+BOM load and normalise. Canonical JSON: sorted keys, -0.0 kept, floats repr, NaN/Infinity/1e999 rejected, duplicate keys rejected incl. escapes, ints > 4300 digits -> invalid_json issue, nesting depth 50-996 OK, 100000-deep arrays reported. Pydantic strict (bool for int, str for number, tuple for list rejected; extra keys rejected; control chars rejected; exact enums); IDs ASCII only; reserved names rejected. Atomic save under kill -9: every file whole, project loads with 0 errors, retry works. Lock: 40 trials x 8 processes exactly one winner; 3 concurrent generates one runs. Writing through links at temp/.bak names or symlinked physical/harnesses refused/replaced; dangling migration-backup link errors. Read-only folder/subfolder give clean SaveError. Recovery: truncated file, invalid UTF-8, merge markers, duplicate IDs across files, wrong structure, unknown config name, newer schema (read-only) handled; quarantined data kept verbatim on Save As; recovered project cannot overwrite its folder; 600-example fuzz passed. Migration v0->v1 lossless with backup; partial migration re-runnable. History: transaction all-or-nothing on exceptions; new integrity errors roll back and keep redo; pre-existing errors don't block unrelated edits. 36 structural mutations ran through checks/drc/verify/plan/generate/build_outputs/verify_outputs without crash except A-4. Starter data: connector parts have symmetric mates_with and equal pin counts, all unverified/pending, no invented numbers. create_project refuses a non-empty folder.

##### Questions for the owner
A-2 (undo of a release, before/after save?); A-1 (every mutating CLI command refuses when load reported any error?); A-6 (valid numeric ranges: AWG 0-40, length 0, pin_count 0?); A-7 (lock policy for other host/old boot; is "delete .harness.lock" acceptable guidance?); A-14 (cap undo history?); A-16 (NFC-normalise names, reject bidi/zero-width characters? Are parts (mass, approval) meant to sit outside the release lock and baseline snapshot? They can change after a release without any finding).

### Area B: Generation and editing

(Saved by the lead from the reviewer's hand-back. 22 findings: 0 critical, 3 high, 11 medium, 8 low. Paths relative to harness/. Scratch: audit/B/.)
Files read completely: core/generate/{engine 868, explain 22, lengths 148, mass 47, naming 78, pins 193, segmentation 150, sizing 119, wiring 50}.py, core/{edit 877, checks 224, describe 111, samples 261, wirecolours 43}.py; supporting: commands, ids, units, configcheck, model/*, vcs/locks (part), docs CONFIG/PLACEHOLDERS/user-manual generate-harnesses, gui/controller + main_window generate/edit paths. Tests: test_generate, test_generate_parts, test_audit_generate, test_edit, test_checks, test_describe, test_wire_colours, test_provenance, test_numerics (head).
Ran: ~113 targeted tests (stress timing test deselected), naming templates (attribute access, subscripts, reserved names, truncation, unicode), pin allocation fuzz 3x20,000 + directed cases, sizing boundaries/bad tables/bad factors, odd topologies (self-link, same-unit, multi-drop, 0/1 endpoints, duplicate signals, cycles), locked/released harnesses, rename/delete/redundant copy/zones/arrange/autoplace, determinism with 3 PYTHONHASHSEEDs, save/reload idempotence, perf 100-1000 harnesses, edit random walks (6 seeds x 250 steps), generation fuzz, 25 mutants.

#### B-1 [high] The GUI says "Harnesses are already up to date" when generation failed with errors
- core/generate/engine.py:108-111 (GenerationPlan.empty), :71-91 (plain_summary); gui/controller.py:602-608 (apply_generation); gui/main_window.py:939-941 (generate_flow). `empty` looks only at ops; a plan whose only result is pin_allocation errors has just a SetGeneration op, so it counts as empty; generate_flow skips the preview dialog and toasts GEN_UP_TO_DATE; plain_summary returns "Nothing needs to change." for a plan with errors.
- Evidence (t_empty.py, t_gui_gen.py): two units with a 4-pin connector, IF-1 generated, then IF-2 added to the same full connectors: `plan.empty True | errors ['IF-2: A-J01 has too few free pins for RX+, RX- (0 free, 2 needed).']`; plain "Nothing needs to change."; apply_generation emits 'Harnesses are already up to date. Nothing to change.'; generation record not updated so status stays stale.
- Fix: `empty` false (or show the dialog) when report.errors/warnings exist; plain_summary mentions errors. Test: plan with only pin errors must not produce GEN_UP_TO_DATE.

#### B-2 [high] Generation uses invalid configuration without checking it
- core/generate/sizing.py:445-512, engine.py:387-390 and :765-770. configcheck.validate runs only in DRC and `harness config`.
- Evidence (t_badcfg2.py, t_gap2.py, t_col.py) on sat15_full: bundle_derating=3.0 -> gauges [26] (configcheck says "must be above 0 and at most 1"); temperature_derating=5.0 -> [26]; ampacity table 26 AWG=9 A, 24 AWG=2 A -> [26]; ampacity {"50":9.0,"20":5.0} -> ValueError "AWG size 50 is outside the supported range 0..40"; power_signal_gap_pins=-30 -> ValueError zip() argument; wire_colour_by_signal {"PWR": ""} -> ValidationError (None becomes colour "None", 5 becomes "5"); string value service_loop_m "0.1" silently ignored.
- Fix: call configcheck.validate at the start of plan_generation; add error findings; treat invalid values as unset (pending); clamp/reject AWG keys outside 0..40 in size_wire. Test: parametrised invalid values expect a finding, pending, no exception.

#### B-3 [medium] Float arithmetic rejects currents that equal the derated limit
- core/generate/sizing.py:479 `table[awg] * factor >= current_a`; same in core/drc/rules.py:260 (see C-15). 221 of 1331 decimal-exact boundary cases falsely rejected; ampacity 1.0 A, K 0.6 x 0.75, current 0.45 A: 0.6*0.75 = 0.44999999999999996 -> "no listed gauge carries 0.45 A after derating". Fix: relative tolerance 1e-9 or Decimal/Fraction. test_numerics tests only 2.7 = 5.0 x 0.6 x 0.9 (rounds correctly).

#### B-4 [high] Naming templates can crash or hang generation
- core/generate/naming.py:218-228 (_fmt catches only KeyError/IndexError/ValueError), :249-260 (_distinct samples n = 1..3 only); engine.py:704-710, :531-536, :626-630 (unbounded while loops).
- Evidence (t_naming.py): harness="W{n.foo}" AttributeError; harness="W{n[0]}" and cable_connector="{harness}-{n[0]}" TypeError; wire="{harness.foo}-{n}", shield="{harness}-{n.x}" AttributeError; harness="COM{n}" ValidationError reserved name on Windows (namer checks ID_RE but not check_id reserved names); harness="H{n!s:.1}" infinite loop (SIGALRM fired after 20 s; distinct for n=1..3, repeats from n=10, _new_harness_id loops forever).
- Fix: catch Exception in _fmt/_distinct; validate with check_id; test distinctness up to n=200; bound loops. (Also the known "naming template memory" item.)

#### B-5 [medium] Templates that give an invalid ID at format time fall back silently
- naming.py:224-227 appends to self.warnings during generation but engine.py:231-234 reports namer.warnings before any name is generated. "W {n}", "{n}W", "Wé{n:03d}", "W-{n}." all gave W001... with findings []. Docs: invalid pattern "is reported and the default is used". Fix: emit findings after generation or validate in namer_for.

#### B-6 [medium] A locked fixed pin makes its interface fail and the harness disappear
- pins.py:231-243 (_allocate_fixed skips locked pins and ignores held); engine.py:401-407, :459-469 (fixed branch clears interface_id on locked pins). Evidence (t_fixed.py): fixed RS-422 pinout, generated, pin 4 (TX+) locked: regeneration reports "IF-1: A-J01 has a fixed pinout and no free pin named TX+."; pin 4 ends locked=True interface_id=None, wires [], harness removed; with a second set of same-named pins TX+ moves to pin 8 and locked pin 4 is cleared. Fix: treat a locked fixed pin as held for its own interface. (Different, worse instance of the known "fixed-pin double-booking untested".)

#### B-7 [medium] Locked power pins do not enforce the power-to-signal gap
- pins.py:318-324 (held signals `continue` before the power_end update at :391). Evidence (t_held.py): power pins 1 and 3 locked, gap changed 3 -> 6: TX+ stayed on pin 7 (gap 3), no finding. Fix: include held power pins in power_end.

#### B-8 [medium] generation_status stays "current" after a change that alters the plan
- engine.py:117-154 (input_hash) covers neither manual harnesses nor released status. Evidence (t_stale.py): manual harness with a wire for IF-010 added: status current; plan_generation reports "1 removed" and "IF-010 was not generated: it is already routed by a manual harness". Fix: include interface ids carried by non-generated harnesses and the released set. Owner decision: YES (does released status count as input?).

#### B-9 [medium] Locked wires and user data are lost silently on regeneration
- engine.py:301-304, :661-666, :506-596 (old data kept only per group key). Evidence: (t_lockw.py) a locked wire (gauge, length, colour) whose interface is deleted or whose signal is removed from the type disappears with no finding ("1 removed"); (t_ren.py) per_unit_pair mode: renaming a unit changes every group key -> "12 added, 12 removed" new harness IDs; locked wire and entered segment lengths lost. per_connector_pair and per_zone_pair unaffected. Fix: warn when a locked wire or entered lengths are discarded; match old harnesses by interface set when the key changes. Owner decision: YES.

#### B-10 [medium] A redundant copy duplicates pin assignments onto the twin
- edit.py:714-730 (_twin_unit_ops: evolve(c, id=new_id, unit_id=tid) keeps pin.interface_id and signal). Evidence (t_twin.py): BAT1-R-J01 pins 1,2 carry PWR/RTN for IF-010 which does not end on the twin; after regeneration they remain (IF-010 carried by a released harness so keep() locks them); IF-010-R takes pins 3,4; box pinout outputs would show IF-010 on the twin. Fix: clear interface_id (and generated signals unless locked/fixed) in the copy.

#### B-11 [medium] delete_impact does not detect manual harnesses that plug into the unit
- edit.py:454-468 compares w.from_connector to box IDs, but wires use cable connector IDs; the link is Connector.mates_with (used by vcs/locks.py). Evidence (t_del.py): mini3 W001 with interface_id=None wires gives blocked_by_harnesses=(); delete fails with a generic "cancelled because it would leave the project inconsistent". Test weakness: tests/test_edit.py:204 builds wire with from_connector="OBC-J01" (a box ID), a shape real data never has. Fix: map cable connector -> mates_with.

#### B-12 [medium] Generation wires some invalid inputs onto the same pin without a finding
- segmentation.py:99-117, engine.py:377-386 (duplicate Requests for a connector used at both ends), wiring.py. Evidence (t_topo.py): interface with both ends on the same connector -> wires W001-001 and W001-002 on pin 5, no generation finding (verify fails "Pin 5 is used by 2 wires"); (t_sig.py) type with a duplicate signal name -> two wires on one pin (check_integrity reports it but generation still runs); interfaces with 0 or 1 endpoints reported as "multi-drop interfaces (more than two units) are not generated yet" (wrong reason). Fix: skip and report interfaces whose two ends are on one connector and types with duplicate signal names.

#### B-13 [low] Segment graph can contain a cycle
- engine.py:511-578. Evidence (t_cycle.py): connectors shared by interfaces in both X and Y positions (per_zone_pair, all in one zone) give segments (B1,B2),(P1,B1),(P2,B1),(P2,B2),(P3,B2): breaks path_length's unique-path assumption. Unlikely through the GUI (one interface per connector).

#### B-14 [medium] Zone names are not validated; a project with no zones breaks editing
- edit.py:551-557 (ops_add_zone), :164-185, :195-296, :714-730; core/io/loader.py:198-202. Evidence (t_zone.py, t_zero.py): zones of 300 chars or "a\x00b" accepted and saved; moving a unit into that lane fails ValidationError (lane unusable). zones == []: ops_add_unit says "There is no room left in the diagram"; zone_of_x and ops_redundant_copy raise IndexError; ops_arrange raises KeyError: 0. Fix: validate names with Name; treat empty zone list as one implicit lane.

#### B-15 [low] Edit operations are inconsistent about how they fail
- edit.py: KeyError from ops_move_unit, ops_confirm_interface, ops_complete_chain, ops_set_endpoint_connector, ops_set_connector_part, ops_update_interface, ops_update_unit, position_of, ops_set_wire_colours (when generation.json is missing); raw pydantic ValidationError from ops_rename_unit and ops_add_unit(unit_id=...); ops_set_endpoint_connector(index=-1) silent no-op, index 5 IndexError; ops_add_interface(interface_id=<existing>) silently overwrites that interface (IF-001 changed rs422 -> can); ops_add_interface doesn't check the connector belongs to the unit; unit_compat for a non-existent unit says "has no free X connector"; connector_compat "In use" message names J01 (not unique); waive_op with a control character says "needs at least 10 characters".

#### B-16 [low] The explanations (Explain tab) contain imprecise text
- engine.py:657-660, :552-555, :383-390, :481-484; explain.py. (t_explain.py): "(X drives)" printed for passive/bidirectional signals such as PWR (X is just the connector with the lower ID; Interface.flow not used by generation); the two pin-allocation lines for a wire are identical with no connector named; after a pin is locked the "stays on pin ... because the pin is locked" line is dead (held reason never recorded in _connector_ops); when no mating part exists provenance says "part X mates with X"; "service loop is a placeholder" note also written when the value is set but wrongly typed. Owner decision: YES (flow handling).

#### B-17 [low] Segregation settings do not behave as documented
- segmentation.py:46-57, :114; docs/CONFIG.md:47-49. (t_seg.py): forbid_nominal_with_redundant False still gives 24 groups (chain always in key); category_pairs_to_separate isolates every category named in any pair from all others (over-separates). Owner decision: YES.

#### B-18 [low] Interface current and default gauge are unvalidated
- model/logical.py:63, engine.py:752-764, sizing.py. (t_size.py, t_gauge.py): current 0 or -5 A with full inputs gives final AWG 26 (no finding); default_gauge_awg 99, -3, 1e30 written into wires; 24.5 ignored with no note; a negative length gives a negative voltage drop that passes the check.

#### B-19 [low] A multi-colour wire is printed with a truncated colour code
- core/wirecolours.py:372. resolve("yellow/green") == ("yellow", "#808080"); "white/blue" -> "white/"; "green-yellow" -> "green-". Drawing text shows a plausible single colour while the wire is drawn grey. Owner decision: YES (how to write/draw multi-colour wires).

#### B-20 [medium] Compatibility checks scale as connectors x interfaces
- edit.py:309-332, called from gui/canvas.py:156-160. (t_compat_perf.py): unit_compat for all 200 units of the stress project 4.2 s (21 ms each) on a loaded machine; interface_using scans all interfaces for every connector of the unit; connect-tool highlight refreshes every unit at stress size. Fix: build the set of used connector IDs once per refresh.

#### B-21 [low / question] Mass can say "Complete: yes" while leaving out parts
- mass.py, core/outputs/tables.py:160-175; docs/SPEC.md:62 says mass comes from wires, connectors, backshells, shielding, sleeving, tie-downs; code sums cable connectors and wires only. Owner decision: YES.

#### B-22 [low] Smaller items
- ops_arrange not idempotent at stress size (200, 100, 28, 0 ops over passes; docstring says a tidy diagram stays put); pins.allocate keeps the pins of an interface that failed halfway (~2200 of 20,000 fuzz cases; engine drops them but later interfaces cannot use the pins); samples.py:149-150 no-op `ops = [o for o in ops]`; ops_add_unit 54 ms per unit at ~400 units; branch/shield/segment/cable templates not checked for cross-kind collisions (branch="{harness}-P{n}" gave branch IDs equal to connector IDs, 6 overlaps, integrity and verify pass); a pin with fixed=True but no signal gets an interface_id but no signal and verify fails.

##### Weak tests and mutation results
25 mutants: killed 13 (>=->> in the ampacity test, removing path_conductors, the pin gap, naming _distinct check, held-pin and explain-provenance logic). Survivors: voltage-drop <= -> <; bundle_k boundary (count <= n); service loop 2x -> 1x (engine.py `length += 2 * loop` asserted nowhere); mass margin and wire mass x length (test_mass_with_full_data_and_margin asserts `r.total_g == 20.0 or r.missing`, nearly a tautology); pins stride (power_return_gap_pins spacing untested); segmentation _esc (test passes with the escape removed); inverted contact-current check; removing locked wires from input_hash; wire_length preferring segments over a stored length; removing the frozen-group skip in plan_generation (same outputs); dropping .strip() in waive_op. Also weak: test_sizing_voltage_drop_can_force_a_larger_wire (`s.error or ...awg <= 20`), test_pins_non_adjacent_is_a_warning (`warnings or errors`). No test for hash-seed independence or plan purity beyond cancellation (both held in runs). No negative test for most edit operations with invalid IDs.

##### Checked and found fine
10 random-fuzz runs of allocate (non-power gap, return gap, adjacency, no double-booking, no use of locked pins when held is empty); plan purity; two-run byte identity; PYTHONHASHSEED independence (0, 1, 777); regeneration idempotent also after save/reload with 28 shields and 29 segments (S10/S2 ordering); CLI generate twice identical directory hashes; plans applied through History respect release locks; frozen released harnesses not modified; 1000-harness plan 3.9 s, 300 interfaces on one connector 1.3 s; edit random walks never produced an integrity error, undo/redo held; sizing arithmetic and voltage-drop formula agree with a hand check; pending/placeholder handling and None current give "pending"; checks.find, fix_ops, waive_op limits (10..2000) as documented; ops_rename_unit and ops_delete_unit cascade work; renaming a unit of a released harness blocked; part_gender and connector_family right for all starter parts; format-string injection like {harness.__class__} only produces an invalid ID that falls back to default (see B-5).

##### Questions for the owner
segregation.forbid_nominal_with_redundant false (B-17); released status / manual harnesses make generation stale and locked wires lost visibly (B-8, B-9); per_unit_pair group keys survive a rename (B-9); Interface.flow and "(X drives)" text for power (B-16); mass to include shields, sleeving, backshells (B-21); how to write/draw a multi-colour wire (B-19).

### Area C: Design rule check, standard profiles, configuration check, independent verifier

(Saved by the lead from the reviewer's hand-back. 24 findings: 5 high, 12 medium, 7 low, 0 critical. Scratch: audit/C/ (scripts e*.py, m*.py, fz*.py, mut*.py, g1.py, wk*.py).)

Files read completely: core/drc/{__init__,base,report,rules,standard_rules,worker}.py, core/standard_profiles.py, core/configcheck.py, core/verify.py, core/model/config.py, gui/drc_process.py, core/integrity.py; parts of generate/sizing, lengths, engine, cli/main, cli/data, vcs/release, vcs/snapshot, checks.py, gui/controller.py. Tests: test_drc, test_standard_rules, test_profiles, test_drc_process, test_data_import (config), test_numerics, test_generate (verifier), test_fuzz (head).
Ran: all 33 rules (positive, clean, null numbers, locations, duplicate IDs, waivers: 909 findings, determinism PYTHONHASHSEED 0..4), hand-built experiments, verifier mutations, ~3,000 random mutated projects through drc.run, profile application, helper process stub, CLI on damaged projects, 30 mutations of the tests.
Not covered: GUI Problems panel visuals, PyInstaller worker route, release gate (E), vcs/consistency.release_integrity.

#### C-1 [high] verify_project crashes on a wire whose two ends are the same pin
- Where: core/verify.py:213-214 (`a, b = sorted(conn)`); reached from core/drc/__init__.py:35 and the release gate.
- Evidence: small-satellite copy, first wire of W001.json given to_connector/to_pin = from_connector/from_pin. `harness validate`: 0 errors. `harness verify` and `harness drc`: "error: not enough values to unpack (expected 2, got 1)", rc=2.
- Fix: when len(conn) != 2 report a verifier error; add the check to integrity. Test: mutation "wire from a pin to itself"; property test that verify_project never raises.
- Confidence: confirmed. Owner decision: no.

#### C-2 [high] Any exception in the design rule check is swallowed by the editor and shown as "Design rules: all 33 rules checked."
- Where: gui/controller.py:43-54 (DrcWorker.run), :171-196 (_drc_done); gui/drc_process.py:71, :118-125 (run_check catches only OSError, EOFError); gui/panels.py:661; gui/strings.py:310.
- Evidence (g1.py): with the C-1 project, console prints "Error calling Python override of QThread::run()... RuntimeError"; then drc_current True, findings 25 errors 0, panel text "all 33 rules checked".
- Fix: catch Exception in DrcWorker.run, keep drc_current False, show "Design rule check failed: <reason>" (plus a synthetic error finding). Test: GUI test with drc.run raising.
- Confidence: confirmed. Owner decision: no.

#### C-3 [high] The verifier never compares Wire.signal or the cable-side pin table with the pinout; exchanging the pins of two wires passes verify, drc and the output verifier
- Where: core/verify.py:120-159 (_wire_connection reads only the mated box connector's pin); core/drc/rules.py:30-40 (_end_signal).
- Evidence (m1.py, m2.py): sat15 W001 (PWR pin 1, RTN pin 2) exchange pins: verify [], drc [], outputs verify ok. wirelist.csv: `W001-001,PWR,IF-010,W001-P1,2,W001-P2,2` (PWR wire on RTN pin). Also wire.signal changed PWR->RTN: verify [] drc []; cable pin signal changed: verify [] drc []. Swapping only one end is caught, so test_verifier_detects_swapped_pins passes.
- Fix: require Wire.signal (when set) to match the label from the two box pins; require cable-side pin signal/interface_id to equal the box-side pin. Test: mutations "exchange pins", "change wire.signal", "change cable pin signal".
- Confidence: confirmed. Owner decision: YES: is Wire.signal a derived label that must match the pinout, or free text on hand-drawn harnesses?

#### C-4 [medium] Shield groups, wire construction/part and gauge are not verified at all
- Where: core/verify.py (no check). Evidence (m4.py): removing all shield groups of W002 (twisted pair + overall shield): verify ok True, no DRC finding. Changing a wire's gauge, colour or part: verify [] drc [].
- Fix: check "type with shielding != none has a shield group covering its wires"; document that gauge is not covered. Confidence: confirmed. Owner decision: YES (are shields in the verifier's scope?).

#### C-5 [high] Temperature-margin errors never block a release
- Where: core/drc/standard_rules.py:108-113 (`Hit(f"{what}-temperature.{pid}")`), core/vcs/release.py:268-281, core/drc/__init__.py locate().
- What: the object id "connector-temperature.<PART>" is not a related object nor resolvable by locate(), so it is never in any harness's `mine`. Only error-severity rule whose findings cannot be scoped to a harness.
- Evidence (r1.py): pos_temperature_margin() gives one error; release_blockers for all 24 harnesses has no rule_error. Control: pos_wire_voltage() gives two rule_error blockers for W001.
- Fix: one hit per use (cable connector or wire id) or map part ids to harnesses in the gate; part-based locate. Test: release test "temperature-margin error blocks the harness using the part". Confidence: confirmed. Owner decision: no.

#### C-6 [high] Current and voltage-drop checks silently skip wires when the bundle table has no entry, the gauge is unset or the length is unknown, with no "not checked" note
- Where: core/drc/rules.py:238-249, :264-284, :453-529 (_unchecked); core/drc/standard_rules.py:281-291.
- Evidence (e1.py, e2.py): table {"1":1.0}, harness with 2 wires, AWG 20 wire carrying 500 A: `bundle-current []`, `current-over-wire []`, notes only the contact-rating and Table 6-42 lines. Sizing says "pending: derating.bundle_factor_by_count (no entry for 2 wires)". Gauge None: skipped. Limit and resistivity set, no lengths: voltage-drop silent. The profile table ends at 300 wires; a 301-wire harness (per_unit_pair/per_zone_pair) is skipped.
- Fix: add unchecked-config entries ("bundle factor: no entry for N wires", "wire current / voltage drop not checked for N wires without gauge / length"). Confidence: confirmed. Owner decision: no.

#### C-7 [medium] Temperature margin: a missing part rating max_temp_c or a missing margin is silent
- Where: core/drc/standard_rules.py:93-113 and unchecked() (178-261). Evidence (tm1.py): max_ambient_temperature_c=120, margins set, no part has max_temp_c: no finding and no note. Fix: add "not checked for <parts>: no max_temp_c" and "margin not set" lines. Confidence: confirmed.

#### C-8 [medium] --apply-profile writes unreviewed standard values into a file marked "placeholder": false and leaves it reviewed
- Where: core/standard_profiles.py:105-115 (`placeholder=True if base is None else base.placeholder`). Contradicts D-131, CONFIG.md, CLI help and CLI closing message.
- Evidence (copy p7): derating.json placeholder false with four owner values; `harness config p7 --apply-profile ecss-q-st-30-11c` adds ~15 values, file stays "placeholder": false; `harness validate` no longer lists derating as placeholder. Release gate uses project.placeholder_configs(), so the profile values pass as reviewed.
- Fix: set placeholder=True for any file in which the profile sets a value, and say so. Confidence: confirmed. Owner decision: YES (may a profile set a reviewed file back to placeholder?).

#### C-9 [medium] bundle_factor_by_count accepts K above 1 (up to 2)
- Where: core/standard_profiles.py:118-130 (_table_ok allows 0 < x <= 2, shared with L), used line 160. Evidence (cv1.py): {"1": 1.5, "2": 1.2} and {"1": 2.0} pass configcheck.validate; sizing would allow 150-200 % ampacity. Table 6-41 K is at most 1. Fix: separate bound for K (0 < K <= 1). Confidence: confirmed.

#### C-10 [medium] direction-conflict is a non-waivable error on wires that generator and verifier both expect
- Where: core/drc/rules.py:184-200 vs core/verify.py:48-65. Evidence (dc1.py): add CLK (direction out) to the rs422 type with TX/RX: generate wires CLK end to end, verify ok True, DRC reports "joins two outputs" (2 errors, not waivable, block release).
- Fix: skip signals the verifier treats as pass-through, or share the pairing function. Confidence: confirmed. Owner decision: YES (what do unpaired directional signals mean?).

#### C-11 [medium] Duplicate finding IDs: one object with several problems, one waiver covers all
- Where: core/drc/rules.py:66-74 (_dangling_wires: both ends dangling = two hits with w.id), :111-113 (_model_inconsistent: every issue of a connector uses c.id), core/drc/__init__.py:12 (apply_waivers by ID), base.py:48-53.
- Evidence (e4.py, w1.py): two `wire-dangling.W002-001` findings with different text; two orphan pins on OBC1-J01 give two `model-inconsistent.OBC1-J01`; waiving the first shows waiver=True on both.
- Fix: discriminator (pin, end, issue code) in the object id or de-duplicate in Rule.run; assert unique ids in a test. Confidence: confirmed.

#### C-12 [medium] power-return-adjacent is weaker than its message and the requirement it cites
- Where: core/drc/standard_rules.py:151-175. Requirement ECSS-Q-ST-30-11_0140052 asks for at least one unassigned contact between power and return; the rule only tests list distance of the same interface's return pin; ignores power/return of different interfaces; never checks the contacts between are unassigned.
- Evidence (pr2.py, OBC1-J01, gap 1): PWR pin 1, data signal of another interface on pin 2, RTN pin 3: no finding. Fix: count unassigned pins in the window; consider all power/ground pins. Confidence: confirmed. Owner decision: YES.

#### C-13 [medium] harness drc ignores load problems: exit 0 and "0 errors" on a project whose config could not be loaded
- Where: cli/main.py:_drc (ignores loaded.issues/recovered/read_only; migrate and export refuse such projects). Evidence (copy p4): truncated config/derating.json; `harness validate` 1 error; `harness drc` "Open: 0 error(s)", rc=0, no mention of the unreadable file. Fix: print load errors at the top and return non-zero. Confidence: confirmed. Owner decision: YES (refuse with exit 2 like export/migrate?).

#### C-14 [medium] The DRC helper has no timeout; a stuck check blocks the lock, wait_drc() and process exit; run_check also misses ValueError
- Where: gui/drc_process.py:44-85 (blocking receive while holding self._lock), :107 (atexit close needs the lock), :118-125; core/drc/worker.py:48-57. Evidence (wk1.py stub worker that never answers): finished within 6 s? False; close() blocked behind the stuck run: True. receive() raises ValueError("message too large") on a corrupted length; run_check catches only OSError, EOFError. Fix: deadline read (select), kill child and fall back, close() must not wait for the lock holder, catch Exception. Confidence: confirmed with a stub.

#### C-15 [medium] Float order of operations: generator and DRC disagree at the exact limit
- Where: core/drc/rules.py:249 (`table[gauge] * bundle * temp`) vs core/generate/sizing.py:81-84 (`factor = bundle * temp`; `table[awg] * factor >= current_a`). Evidence (fl1.py): ampacity 1.5 A, bundle 0.6, temperature 0.6, current 0.54 A: sizing picks AWG 20 ("carries 0.54 A derated"); DRC gives a non-waivable error "carries 0.54 A but allows 0.54 A" (0.5399999999999999 < 0.54). 183 of 310 common combinations differ in the last bit. Fix: one shared limit function and a relative tolerance. Confidence: confirmed.

#### C-16 [medium] Tests that pass although the code is wrong (mutation results)
30 mutations in a copy; survivors (no test failed): contact current boundary < to <=; wire current boundary; temperature derating (`* temp`) dropped from _wire_current_limit; voltage-drop round-trip factor n=2 to 1; voltage-drop boundary > to >=; spare-pin boundary; mate-mismatch keying comparison disabled; pin-count comparison disabled; drc.run sort key without finding ID (CLI sorts again so golden passes); verify.py `if cable.mates_with in project.connectors` to `if True`; `have > n` to `have > n + 5`. Killed (good): direction inverted, shield-wrong-end, wire voltage boundary, mating boundary, withstand, min-to-max, temperature sign, bundle boundary, power/return window, manufacturer, specification, EMC split threshold, shield-parts, profile overwrite, bundle monotonic. By reading: test_rule_fires_on_a_violation never checks object_id points at the injected object; the "clean" negative runs contain no currents or ratings; test_drc_on_the_stress_project ends with `assert isinstance(Connector, type) and isinstance(Pin, type)`; test_verifier_detects_* assert only that codes(p) is non-empty; the default fuzz run (40 examples) never found C-1. Fix: boundary tests (at the limit passes, a hair above fails), keying and pin-count tests, assert object_id. Confidence: confirmed.

#### C-17 [medium] part-unapproved ignores unverified parts while the release gate counts them
- Where: core/drc/rules.py:162-178 vs core/vcs/release.py unapproved_parts (`approval != "approved" or part.unverified`). Evidence (misc1.py): all 28 starter parts unverified; set approved: 0 part-unapproved findings, release gate still lists ['EX-MICROD-9-M', 'EX-WIRE-SINGLE']. Fix: report unverified parts in the rule. Confidence: confirmed.

#### C-18 [low] voltage-drop skips gauge 0 (AWG 0)
- core/drc/rules.py:274 (`... and length and w.gauge_awg:`) although 0 <= gauge <= 40 is accepted. Evidence (e5.py): gauge 20 gives a finding, gauge 0 gives []. Fix: `is not None`.

#### C-19 [low] current-over-wire and bundle-current report the same wire twice; the "derating not checked" note is wrong when the table replaces the single factor
- rules.py:238-259, standard_rules.py:277-296, rules.py:212-218 and :456-462; CONFIG.md. Evidence: both rules fire on W001-001; with bundle_factor_by_count set and bundle_derating null, current-over-wire fires but the info note "Current and derating limits were not checked" is still shown.

#### C-20 [low] Profile table is shared by reference with project data
- core/standard_profiles.py:33-36, 54, 101 (Setting.value is the module dict BUNDLE_K / PARTIAL_L, stored without copy). Evidence (pf1.py): `c.values['bundle_factor_by_count'] is sp.BUNDLE_K` True; in-place edit changes the profile for the process. Fix: deepcopy.

#### C-21 [low] Config validation gaps
- core/configcheck.py, standard_profiles validate. max_ambient_temperature_c not validated ("hot", -500 accepted); contact_rating_key, default_gauge_awg (200 accepted), forbid_* flags and emc.classes not validated; category_pairs_to_separate / conflicting_class_pairs accept identical names ([["A","A"]]) and duplicates/reversed pairs; NaN power_return_gap_pins crashes int(gap) (standard_rules.py:157; reachable only via API since loader refuses NaN).

#### C-22 [low] Silent skips and small inconsistencies in rules
- mate-mismatch silent when gender "unspecified" (the default) or no mates_with; connector-manufacturer compares case/whitespace-sensitively; emc-class-split reads h.interfaces only (standard_rules.py:353; with h.interfaces == [] the finding disappears: misc1.py 1 to 0); part-based findings (shield-parts.*, wire-spec.*, *-temperature.*, mating-cycles.*, emc-class.*) have no locate target ("Show" does nothing); dead code (second element of _shielded_parts always []; bundle_wire_count is len(h.wires)); applying a profile changes generation inputs so plans become stale (outputs_outdated), not said by the CLI.

#### C-23 [low] Verifier independence and ID stability
- core/verify.py:163 lazily imports generation_status from generate/engine.py (staleness depends on the generator's input_hash, which omits gauge, colour, part and pins of unlocked wires: why C-3/C-4 stay "current"); CLAUDE.md says the verifier must not import generation logic. verify-mismatch ids embed an enumeration index for issues without an object, so ids change as other issues appear/disappear.

#### C-24 [low] Documentation mismatches
- CONFIG.md says max_ambient_temperature_c is "recorded for reference" but temperature-margin uses it; PLACEHOLDERS.md "what keeps a rule silent" lacks the D-131 rules; RULES.md/unchecked-config promise a not-checked line for every silent rule, untrue for C-6, C-7.

##### Checked and found fine
All 33 rules fire on positive case, quiet on clean and with null numbers; no exception from any rule over ~3,000 mutated projects except C-1. Units and directions: contact current, wire current, voltage-drop formula (AWG 20, 3 A, 50 m = 9.85 V), connector voltage = lower of two, wire voltage, temperature (at limit passes), mating cycles, spare pins, bundle K lookup, twisted pairs skipped by shield rules. Table 6-41/6-42 profile values match requirement text; every profile setting and rule `sources` id exists. Profile: fills only None, keeps any owner value incl. 0/False/""/{}; idempotent; unknown profile refused rc 2; read-only/damaged project refused. NaN/Infinity/1e999 rejected by loader. Report deterministic (same SHA-256 for PYTHONHASHSEED 0-4); sorted by (severity, id); errors not waivable; all 909 waivable findings waivable. Verifier fails on: missing wire, duplicate wire, one-end pin swap, nonexistent pin, wrong mates_with, removed interface_id, interface moved, box pinout swap, stale plans. Helper process restarts after kill, falls back in-process on start failure, recovers after error reply; `-P` keeps cwd off sys.path. Stress project (140 harnesses, 20,000 wires) drc.run 4.3 s on a loaded machine.

##### Questions for the owner
C-3 (Wire.signal derived or free text?), C-4 (shields in verifier scope?), C-8 (profile may set reviewed file back to placeholder?), C-10 (unpaired out/in signals), C-12 (contacts between power and return strictly unassigned?), C-17 (unverified starter parts as DRC finding or only at release?), C-13 (`harness drc` refuse with exit 2 on load errors?).

### Area D: Outputs, drawings and routing geometry

(Saved by the lead from the reviewer's hand-back. 18 findings: 0 critical, 2 high, 9 medium, 7 low. Scratch: audit/D/.)
Files read completely: core/outputs/{build 323, canvas 243, drawing 741, exports 125, provenance 58, stamp 62, system 178, tables 280, verify 652}.py, core/routing.py 319; supporting: generate/lengths, mass, wirecolours, ids, model/base+physical, io/fs (atomic write), io/layout (hash), CLI _export/_verify, GUI OutputsWorker/export_flow, gui/canvas.py routing geometry. Docs/tests: OUTPUTS.md, CLAUDE.md, test_outputs (530), test_audit_outputs (261), test_drawing_layout (217), test_routing (195).
Ran: all five examples + sat15_full + mini3: generate, export, verify --outputs; independent recompute of wire list, pinouts, BOM (quantities, metres, unknown counts, used-in), mass/length (incl. margin), tests (IDs, limits), labels, box pinouts, mating matrix, traceability: 0 errors; geometry check that each wire curve ends on the model's pins/connectors: 0 errors; 17 hostile strings in project/unit/harness/connector/signal/colour/notes/EMC fields (xmllint/ElementTree, pdfinfo, pdftotext, openpyxl, PyYAML, json); harnesses with 0, 1, 2, 3, 2000 wires (2000: ~6.5 s build, 6 s verify); ~450 random harnesses through drawing, ~200 through build+verify; 33 cell mutations of finished files; write paths (read-only outputs/subfolder, outputs/subfolder as symlink, symlinked manifest/file/harness folder, manifest listing a directory or outside path, simulated disk full, ulimit -f, setpriv); determinism (PYTHONHASHSEED, dict re-order); route_links with random/coincident/zero-size/inverted/NaN/inf/duplicate/missing-gap/2000-link inputs.
Not covered: WireViz itself, Excel/LibreOffice/Acrobat, non-root permission runs, GUI export (read only).

#### D-1 [high] A wire length with more than 6 significant digits makes `harness export` refuse to write
- outputs/tables.py:17-18 (`num` = "%.6g") vs outputs/verify.py:231 (absolute tolerance 1e-9). Evidence (documented workflow): `harness import-lengths P len.csv --unit mm` with `W003,W003-L1,1234.567`, `harness generate P`, `harness export P`: "Not written: the outputs failed their independent check. [out_wire_differs] Wire W003-001 has a different length in the wire list." (also W001-018, W003-002). Lengths 1.234567, 12.34567, 123.4567 and 100000.5 in a project file fail the same way. CAD exports in mm with 3 decimals are the normal source. The release re-export would be blocked too; message does not say why. The 6-digit rounding also silently rounds BOM and mass totals.
- Fix: write full precision or compare with the same rounding / relative tolerance. Test: length_m=1.234567 must export and verify. Owner decision: YES (precision policy).

#### D-2 [high] IDs the model allows (up to 64 chars) make export fail: the drawing truncates them and the verifier calls them "missing"
- outputs/drawing.py:454 (connector header fit, 33 chars), :576 (wire label fit, 62 chars), verify.py:481-485. Evidence (t11.py, t12.py, t13.py): connector ID of 34 chars -> "Connector C…A is missing from the drawing of H1", export refused (33 is fine); wire ID of 63 chars same refusal; at 61 chars with a mixed gauge/length cable block the wire is not drawn at all; between ~45 and 60 chars "AWG n  length" is silently cut ("… RD  AWG 2~") while the verifier passes.
- Fix: never truncate IDs or label data (wrap/shrink), or restrict ID length consistently; clear verifier message. Owner decision: YES.

#### D-3 [medium] Pin IDs longer than 7 characters are cut to "XXXXXX~", so different pins look identical
- drawing.py:469 (`fit(pin, 10.5, PIN_SIZE)`); model allows 16-char pin IDs. SHIELD_GND_1 and SHIELD_GND_2 both draw as "SHIELD~" (t11.py). test_a_long_pin_id_stays_inside_its_column accepts this. Verifier doesn't check pins in drawings (D-10).

#### D-4 [medium] The CSV formula guard is lossy, so a signal starting with `'` plus a trigger character breaks verification
- outputs/stamp.py:33-44 (_safe adds `'`, _unsafe strips it). Evidence (t2.py): signals `'=1+1`, `'@x`, `'-x`, `'+x` -> "out_wire_differs ... signal" plus "out_xlsx", export refused; `'=x` reads back as `=x`. Common names `+5V`, `-12V` are written as `'+5V` in every CSV (documented, but consumers see the apostrophe; XLSX correct). Owner decision: YES (how should +5V look in CSV?).

#### D-5 [medium] The title block field list is never validated
- drawing.py:616-624, :590-608; verify.py:486-489; core/configcheck.py has no title block check; CONFIG.md says `fields` chooses which fields appear. Evidence (t16.py): fields ["project","harness_id"] or ["foo","bar"] -> "The title block of ... shows the wrong sheet number", export refused; misspelled key `harnes_id` drawn as "-"; 30 fields give rows 2.4 mm high with overlapping 3 mm text. (Same as K-1.) Owner decision: YES (is `sheet` mandatory?).

#### D-6 [medium] PDF drawings silently replace characters outside cp1252 with "?", while the SVG keeps them
- canvas.py:150-152 (encode("cp1252","replace")). Evidence (t15.py): "Rsense 10kΩ ±5% → ΔV 日本" -> "Rsense 10k? ±5% ? ?V ??" in pdftotext. Docs say PDF has the same content as SVG. Ω and Δ are normal in electronics, no warning. Fix: warn in the export report, or embed a Unicode font; at least document. Owner decision: YES.

#### D-7 [medium] Shield terminations flip sides between sheets of a multi-sheet drawing when the shield's wires run in both directions
- drawing.py:334-336 (reference wire = first wire of the shield on this page; D-141 says end A is the end of the shield's first wire). Evidence (shield2.py): overall shield end_a=backshell_360, end_b=floating over 30 wires A->B then 30 wires B->A on A4 (3 sheets): sheets 1-2 backshell left, sheet 3 right. Example projects contain no such shield. Single-point grounding drawn at opposite ends on different sheets. Fix: one reference wire per shield for the whole harness. Owner decision: YES (what does end A mean physically?).

#### D-8 [medium] Same model hash, different bytes: box_pinouts.csv and system.xlsx depend on the insertion order of project.harnesses
- tables.py:95-106 (wire IDs joined in iteration order, not sorted; mating matrix sorted only by cable connector ID). Evidence (t18.py): two harnesses wired to the same box pin, built W001,W000 vs W000,W001: pin row "W001-001;W000-001" vs "W000-001;W001-001". GUI session (insertion order) and CLI export after reload (sorted) differ for the same model; breaks the deterministic-output rule; manifest and stale checks disagree. Fix: sort wire IDs in box_pinouts and pinouts; tie-break mating rows by harness ID.

#### D-9 [medium] Negative or absurd lengths are accepted everywhere and produce "complete" negative totals
- core/model/physical.py (Wire.length_m, Segment.length_m unbounded); validate and drc silent. Evidence: one wire `length_m: -5.0` in sat15: validate 0 errors, export succeeds, bom.csv "EX-WIRE-SINGLE ... -3.8 m", mass_length.csv "W001,2,2,-3.8,0,8.8,0.88,9.68,yes"; 1e308 gives "mass and length do not match" (infinite sum). (Same family as A-6, B-18.) Fix: ge=0 and a sane maximum in the model (import already limits 0..10000 m); DRC error.

#### D-10 [medium] The output verifier checks far fewer cells than the docs suggest
- verify.py; claims in OUTPUTS.md/CLAUDE.md. Mutation (mut1.py, in-memory files): NOT noticed: pinout signal, spare flag and part columns; BOM category, approval, "wires without length", "used in"; test limits, test voltage, isolation wire IDs; label text and quantity; mass "missing data"; mating matrix gender and part columns; traceability From/To/wires; all of box_pinouts.csv incl. a removed row; system BOM "used in"; DRC finding text and severity; two pin numbers swapped in the drawing SVG and signal text in the SVG; YAML gauge, length, connection pin; PDF content other than wire IDs; provenance counts. Caught: wire-list ends and shield group, and anything changed in a folder with a manifest (hash catches it). Fix: add checks and mutation tests for these columns and a drawing pin check.

#### D-11 [medium] Cyclic routing-segment graphs are not rejected, and the builder and verifier pick different paths
- generate/lengths.py:10-28 (BFS fewest hops) vs outputs/verify.py:313-333 (DFS). Evidence (f136.py, fuzz seed 136): wire W5 C0->C- gets 100.623 m from builder and 101.123 m from verifier -> "differs from the design: length", export refused; `harness validate` reports nothing for a segment loop. Fix: flag non-tree segment graphs as DRC error; one shared path rule. Owner decision: YES (are loops legal; which path wins?). (Related to B-13.)

#### D-12 [low] Wire loops below a cable block (wires with both ends on one side) are not counted by pagination and can run into the title block
- drawing.py:550-566 (`yr = bt+height+2.5+0.9*nth`) vs _fits (213-229). Fuzz seeds 31, 97, 107 on A3 overshoot the title block top by up to 38 mm; seed 139 (13 wires) by 0.9 mm; needs many same-side wires sharing pins (loop-back plugs); existing test covers 3 wires. Fix: include loop height in _fits and _place_blocks.

#### D-13 [low/medium] The XLSX build writes temp files and fails with a raw traceback when the temp folder is full; the GUI then reports "cancelled"
- exports.py:88 (openpyxl write-only), gui/main_window.py:143-152. Evidence: `ulimit -f 60; harness export small-satellite` -> traceback ending `lxml.etree.SerialisationError: IO_EFBIG`, exit 1, nothing written, no message. By reading: OutputsWorker.run catches only OutputsCancelled, so any other build error leaves result=None and the user sees "Export was cancelled" (see F1-19). Fix: catch Exception in CLI and worker and report the real error.

#### D-14 [low] write_outputs partial-failure details
- Correct: disk-full/read-only raise SaveError with a sensible message and leave no .tmp; old manifest kept and the mixed state detected as out_stale/out_modified; symlinks handled. Weak: a hand-edited/corrupt manifest listing a directory (e.g. "harnesses") makes every later export fail "The outputs could not be written (Is a directory)" after all new files were written; empty folders of removed harnesses stay; outputs_status(deep) lacks the symlink test that damaged_files has; read_folder follows file symlinks (read only).

#### D-15 [low] The harness overview draws only the first and last unit of a harness
- system.py:152-166 (units[0], units[-1] in file order): a harness with three mating units shows one edge between first and last; the middle unit has no edge. Confidence: likely (by reading). Owner decision: YES.

#### D-16 [low] In a long routing-sketch chain the segment length can be cut off
- drawing.py:716-725 (`fit(f"{g.id} {length}", gap_x, 2.2)`); gap_x shrinks to ~10 mm at scale 0.29 for 14 nodes (~7 chars, "W001-L~"); the length (useful part) is lost; existing test checks only boxes stay on the sheet. Likely (by reading).

#### D-17 [low] core/routing.py preconditions
- (rt1.py) route_links raises KeyError when geo.gaps lacks a gap between two lanes used by a link, or for a negative lane. GUI always supplies all gaps and clamps lanes (edit.lane_index). Correct: coincident ends, zero-size and inverted geometry, duplicate IDs; NaN wrong order no crash (model forbids NaN); 2000 links 0.04 s; orthogonality and end points hold on all random cases.

#### D-18 [low] Miscellaneous
- Markdown reports (drc_report.md, revision_report.md) put names unescaped into headings; a project name with a newline breaks the heading (by reading). XLSX stores every number as text; CSV is UTF-8 without BOM so Excel misreads non-ASCII. tables.py:223 `.replace("  "," ")` also collapses double spaces inside a signal name.

#### Test quality
Golden digests are produced by the same code so they only detect change; mutation tests cover only the columns listed as caught in D-10; no test for D-1, D-2 (long ID), D-3, D-5, D-7, D-8 and none for multi-sheet shields; test_a_long_pin_id_stays_inside_its_column locks in the D-3 truncation.

##### Checked and found fine
All tables match independent recomputation on every example and sat15_full/mini3; drawing pin and connector endpoints of every wire on all sheets of small-satellite, flatsat, sat15_full (A3 and A4) match the model; shield sleeves contain their wires, nested and disjoint, on 300 random cases; 17 hostile strings in 9 name fields: SVG well-formed XML, PDF passes pdfinfo/pdftotext, XLSX opens, YAML and JSON parse, verifier clean (except D-4); 0/1/2/3-wire harnesses verify clean, 2000 wires builds in 6.5 s with 41 sheets numbered correctly; determinism under PYTHONHASHSEED variation and dict re-ordering identical except D-8; control chars, surrogates, U+FFFE/FFFF rejected by the model so XML/XLSX never get illegal characters; XLSX sheet names fixed and unique; write safety: outputs folder, system/, harness folder or file as symlink refused ("nothing was written"), symlinked manifest replaced with target untouched, manifest paths with .. / absolute / outside ignored, disk full -> SaveError no .tmp, read-only folders clear error, foreign files in outputs/ kept; damaged project refused; model hash stable across save/reload and every file kind carries it (verifier checks); unknown colours drawn grey with text code kept; routing tests meaningful. `.harness.lock.takeover` appears after any CLI export (locking area, see A-10).

##### Questions for the owner
Precision of table numbers (D-1); limit IDs to what the drawing can show or never truncate (D-2, D-3); shield "end A" with wires in both directions (D-7); CSV `'+5V`/`'-12V` guard (D-4); is `sheet` mandatory in the title block, unknown keys? (D-5); are looped segment graphs legal and which path wins; non-negative lengths (D-9, D-11); harness overview for 3+ connectors (D-15); PDF Unicode font or warn (D-6).

### Area E: Change control, command line, importers

(Saved by the lead from the reviewer's hand-back. 18 findings: 3 high, 10 medium, 5 low, 0 critical. Scratch: audit/E/.)
Files read completely: core/vcs/{release 473, locks 99, diff 206, snapshot 55, hashing 38, report 84, consistency 58}.py, cli/{main 316, changes 211, data 406, start 85}.py, core/{imports 274, library_import 245, kicad 462}.py; also commands.py, io/fs.py, generate/lengths.py, configcheck.py, model/review.py. Docs: CLI.md, IMPORTS.md, KICAD.md. Tests: test_change_control.py full; test_audit_cli, test_data_import, test_imports, test_kicad by headings.
Ran: all 21 subcommands vs missing/empty/file/non-project/trailing slash/""/relative/absolute/unicode/space/symlinked-root paths, schema-99 project, damaged JSON, read-only (chattr +i), closed stdout, full disk, `| head`, SIGINT, 3 concurrent releases, `--` handling; release state machine on flatsat incl. 29 revise cycles; ~45 CSV, ~25 XLSX cases (formula, merged, two sheets, zip bomb, billion-laughs, XXE), import-parts 28 cases, 13 ampacity-CSV cases, KiCad S-expr/XML (DOCTYPE variants, UTF-16/32, limits). Targeted tests passed (2m22s).
Not covered: unprivileged-user permission tests (ran as root), GUI release dialog, Ctrl-C outside export.

#### E-1 [high] A stray double quote in a CSV silently swallows the following rows (import-parts reports success)
- core/imports.py:48-50: `csv.reader(io.StringIO(text), delimiter=...)` non-strict; used by read_table for import-parts, import-lengths, config --ampacity-csv, --signal-map.
- Evidence: q1.csv header + `P-001,Acme,"Micro-D 9 pin male,connector,9,Approved` + 3 more part lines: `harness import-parts proj q1.csv --approved Approved --rejected Rejected --category connector` prints "row 2: OK added P-001", "1 part(s) ready, 0 row(s) with problems", "Imported 1 part(s)", rc 0; the description of P-001 holds the other three lines.
- Fix: csv.reader(..., strict=True); csv.Error already caught. Test: parse_csv('a,b\n"x,1\ny,2\n') must raise ImportError_.

#### E-2 [high] Read-only/report commands ignore damaged project files and print clean-looking results with exit 0
- cli/main.py:149-160 (_drc), 163-182 (_verify); cli/changes.py:101, 109-117, 177-211 (compare, log, diff); cli/data.py:159-225 (config, library). Only validate, check, export, migrate look at issues/recovered.
- Evidence: broken logical/units/avionics.json: `harness drc` normal report "Open: 0 error(s), 6 warning(s)" rc 0 (validate: 6 errors rc 1). Broken changelog.json: `harness log` prints only the header, rc 0 (release record appears empty). Damaged baselines/W001/W001.B.json: `harness diff d3 W001` silently compares against revision A, rc 0 (wrong baseline). `harness compare d4 d4` (damaged, same folder twice) "No differences." rc 0. verify prints spurious signal_missing without the cause; config/library report the partial model. generate on damaged project prints a summary then fails "Parts of this project could not be loaded" (rc 2); the file is not overwritten.
- Fix: one helper load_for_report(path) used by all: print load errors to stderr, return 2 if has_errors or recovered. (Same family as C-13.)

#### E-3 [high] XLSX import reads the workbook's active sheet, not the first sheet as documented
- core/imports.py:~129 (`ws = wb.active`); IMPORTS.md says "read from the first sheet". Evidence: workbook Data (first) `W001,W001-L1,111`, Notes (active) `W002,W002-L1,222`: read_table returns the W002 row; `import-lengths --dry-run` "1 length(s) ready". A hidden first sheet is skipped silently. (Same as K-2.) Fix: `wb.worksheets[0]` or first visible; name the sheet read.

#### E-4 [medium] `harness check` / release_integrity ignores units and box connectors stored in the baseline snapshot
- core/vcs/consistency.py:11-47 compares only the harness and its carried interfaces; snapshot.py:38-55 also stores units and box connectors; locks.py:46-98 protects only locked pins and part/gender/keying.
- Evidence: edit physical/connectors/aocs.json RW1-J01 in a released flatsat copy (pin 1 signal PWR->HACKED, part EX-MICROD-9-F->-9-M, pin 2 interface IF-010->IF-011): `harness check` only "not_canonical" warning, 0 errors, rc 0; `harness diff` shows 3 changes; verify flags only the signal.
- Fix: compare b.snapshot.connectors and units in release_integrity. Owner decision: YES (should units and box connectors be part of the lock? snapshot stores them).

#### E-5 [medium] Parts, configuration and waivers are not frozen or recorded by a release; Baseline.content_hash is never verified
- locks.py, snapshot.py, consistency.py; model/review.py:57 stores content_hash, never read (only release.py:401, outputs/build.py).
- Evidence: released flatsat W001 (rev B): `import-parts` (EX-WIRE-SINGLE approved, mass changed) rc 0 "Imported 2 part(s)"; check 0 errors; diff "No differences."; export rewrote 112 files with new numbers. Also `config --ampacity-csv/--apply-profile` can change derating.
- Fix: snapshot used parts (id, approval, mass, pin_count) and compare in release_integrity, or compare content_hash. Owner decision: YES (are parts/config meant to float after release?).

#### E-6 [medium] Data commands blocked by the release lock: dry-run says OK, the real run gives rc 2 and hides the reasons
- cli/data.py:177-179 `except (HarnessError, ImportError_)` catches TransactionError before cli/main.py:200 which prints `problems` and returns 1; _netlist dry run never calls check_locks.
- Evidence: released flatsat, netlist moving PWR of RW1-J01 to pin 3: `import-netlist --dry-run` "J1: OK updated RW1-J01", rc 0; without --dry-run "error: This change was blocked because it touches released items." rc 2, no item/harness named. Same handler for config, library, import-parts, import-lengths. CLI.md says 1 = blocked.
- Fix: catch TransactionError separately in data.run, print .problems, return 1; run check_locks in the preview.

#### E-7 [medium] import-netlist overwrites a user-locked pin and can leave a pin with an interface but no signal
- core/kicad.py pin loop: `evolve(base, signal=..., fixed=signal is not None, interface_id=None if signal is not None else base.interface_id)`.
- Evidence 1: pin 1 of RW1-J01 `locked: true`; netlist puts /OTHER on pin 1 -> ('1','OTHER', interface None, fixed True, locked True), no warning. Evidence 2: generated first-steps, pin 1 = PWR/IF-001; netlist names pin 1 `Net-(J1-Pad1)` -> pin 1 signal None, interface_id 'IF-001', fixed False; validate 0 errors; next generate fails "RW1-J01 has a fixed pinout and no free pin named PWR".
- Fix: skip locked pins and warn; clear interface_id when signal is cleared. Owner decision: YES (netlist override locked pin?).

#### E-8 [medium] `harness compare` says "No differences" when waivers, project name, zones, library info and layout differ
- core/vcs/diff.py:100-119 flatten_project covers units, interface types, interfaces, parts, box connectors, harnesses, config only. Evidence: two flatsat copies; second gets a waiver, moved placement, changed project name, new zone, library version 99: compare "0 added, 0 removed, 0 changed. No differences."; `diff -rq` shows waivers.json, layout.json, project.json, library/manifest.json differ. A waiver changes what blocks a release. Baselines and change log also invisible. Fix: add them to flatten_project or print "not compared: ...".

#### E-9 [medium] Ctrl-C prints a Python traceback
- cli/main.py:185-217 catches no KeyboardInterrupt. Evidence: SIGINT 0.8 s into `harness export`: stderr ends with openpyxl traceback ... KeyboardInterrupt, rc -2. Lock released (finally); old manifest stays (written last). Fix: `except KeyboardInterrupt: print("interrupted", file=sys.stderr); return 130`.

#### E-10 [medium] Release is saved before the re-export; if the re-export fails the command exits non-zero but the release stands
- cli/changes.py:143-152 and 155-174 (_restamp); vcs/release.py outputs_blockers follows a linked outputs folder when reading. Evidence: `outputs` symlink to another folder: `harness release s1 W001 ...` prints "Release W001 revision A: done." then "error: The outputs folder (or a folder in it) is a link, so nothing was written.", rc 2; `harness log` shows the release; rerun `already_released`; title blocks stay "draft". Same if verify_outputs fails (rc 1) or disk full. Fix: make linked/unwritable outputs a release blocker before committing; on restamp failure print "The release was recorded; run `harness export` to re-stamp".

#### E-11 [medium] `harness library`: any bad value is reported as a bad date, and dates are not strict YYYY-MM-DD
- core/library_import.py:215-232 (`except ValueError` always gives the date message); core/model/library.py _iso_date uses date.fromisoformat (accepts more on 3.11+). Evidence: --library-version of 201 chars, --library-name= (empty), control char in --library-source all print "The library date must be written YYYY-MM-DD"; --library-date 20260101 stored; 2026-W02-3 and 2026-W02 stored in library/manifest.json; release.py has strict DATE_RE, this path doesn't. (Same as K-3.)

#### E-12 [medium] import-parts: duplicate rows, number parsing, useless per-row messages, unbounded pin count
- core/library_import.py:84-91 (_number), 105-205 (plan_parts_import, message ~191). Evidence: same part ID twice (`P-1,...,Yes,1` then `P-1,...,No,2`): both "OK added P-1", "2 part(s) ready", one Put; last row silently wins. Mass "1,234" accepted as 1.234 g (same class as known import-lengths item); 1e3, 1_0, 1e23, -0 accepted; pin count 1e1, 9.0 accepted; pin count 99999999 accepted -> import-netlist (spare-pin fill range(1, pin_count+1)) under ulimit -v 4 GB ends in MemoryError traceback / >100 s. Description > 200 chars or control char gives row message "ERROR 1 validation error for Part" with no field. Two approval columns (status, approved): first alias silently wins. Fix: error rows for duplicate IDs; strict number regex; pin_count max (e.g. 1000); field-name messages. Owner decision: YES ("1,234"; pin_count bound).

#### E-13 [medium] The release record can be undone and then saved away (undo bypasses check_locks)
- core/commands.py:214-228; vcs/locks.py promises baselines/change-log entries "cannot be deleted"; gui/controller.py apply_change makes release one undoable step. Evidence (API): release W001 via History, save_project, undo, save_project: baselines/W001/W001.A.json becomes .bak; changelog.json shrinks 637 -> 198 bytes; harness back to in_review. tests/test_change_control.py::test_release_can_be_undone_in_the_session asserts this on purpose but only before a save. (Same as A-2.) Fix: clear undo stack on save or refuse undo of release/revise steps after a save.

#### E-14 [low] Control characters, long text and newlines in --by/--comment/--checker/reasons: wrong exit code, log and report injection
- vcs/release.py:380-401; model/base.py _no_control_chars allows \n and \t; cli/changes.py:114; vcs/report.py:60-67. Evidence: reason of 11 \x01 -> "error: comment: Value error, must not contain control characters" rc 2 (not blocked rc 1; names "comment" not the option); --by of 201 chars -> "author: String should have at most 200 characters"; by reading gui change_flow doesn't catch ValidationError from plan_release; --comment with newline + fake entry makes outputs/system/revision_report.md contain a line looking like a separate change-log entry by "Boss"; `harness log` prints it over two lines; --by 'a|b' ambiguous in the " | " table. Fix: validate by/checker/comment/reasons in _common as blockers; escape or collapse newlines.

#### E-15 [low] Date handling in review/release/revise
- cli/changes.py:86-87 (_today); vcs/release.py valid_date. --date "" silently means today; 0001-01-01 and 9999-12-31 accepted; no check vs earlier log entries (release dated before its own review). Owner decision: YES (date policy).

#### E-16 [low] KiCad XML: the DOCTYPE/entity guard is bypassed by UTF-16 without BOM (and UTF-32). Known item, now reproduced.
- core/kicad.py _parse_xml (byte search for `<!doctype`, `<!entity`) and _to_utf8 (BOM only). Evidence: a netlist with DOCTYPE and 4 ENTITY definitions encoded utf-16-le/-be without BOM is parsed; value 10,000 chars long; UTF-8 version refused; at levels 6-7 expat stops with "limit on input amplification factor" (0.15 s, 65 MB). External entity -> "undefined entity". Fix: decode to text first (detect UTF-16/32 by BOM or NUL pattern) then search case-insensitively; or use defusedxml (already a dependency).

#### E-17 [low] Output and exit-code polish
- `harness log proj | head -1` -> "error: a file or folder could not be used (Broken pipe)." rc 2 (main.py:206); closed stdout: drc returns 0 silently. Lock message "open this copy read-only" is GUI wording. `harness new --name ""` uses default; `--name "  "` creates project named two spaces; dangling-symlink target says 'derating.json' could not be saved (File exists); read-only parent names derating.json. Row errors of import-* go to stdout, `config` problems to stderr, verify errors to stdout; import-netlist missing --unit returns 1 while diff/log unknown harness return 2. CLI.md exit-code table says 1 = project has errors / step blocked; import row errors, config, verify, export (no harnesses) also return 1, undocumented.

#### E-18 [low] Test gaps found by reading
- test_kicad.py hostile-files test has only UTF-8 DOCTYPE cases; hypothesis test calls plan_netlist_import without asserting; test_regeneration_leaves_released_harnesses_alone compares only the harness; no tests for: check on tampered box connectors (E-4), parts changed after release (E-5), undo after save (E-13), compare ignoring waivers (E-8), restamp failure (E-10), dry-run vs lock (E-6), CSV with unclosed quote, two-sheet workbook, duplicate part ID, damaged changelog/baseline for log/diff/drc; test_audit_cli.py::test_an_inconsistent_import_is_a_blocked_step asserts rc==2 though name says "blocked" (rc 1 by docs).

##### Checked and found fine
Path handling for all commands (no traceback, rc 2, clear messages); no write through symlinked library/outputs/new-project/schema/templates targets. Schema-99 project: writing commands refuse rc 2; validate/check warn; read-only work. Read-only folder (chattr +i): readable message, rc 2, nothing changed. 3 parallel releases: exactly one succeeds. State machine behaves as designed (double release, release of in_review allowed, review of released/in_review, revise of draft, release after revise without export -> outputs_stale, short/whitespace/2500-char reasons, bad dates, unknown harness rc 2). Revisions A..Z, AA, AB, AC over 29 cycles; baselines_of ordering and diff correct. Lock enforcement through History: harness, interface, box pin, connector edits blocked; import-lengths on released harness gives error row; generate leaves released harness alone. argparse abbreviations, `--`, `--by=-x`, bad choices rc 2. CSV: BOM (also double), CRLF, bare CR OK; latin-1 and UTF-16 refused; ; and tab; quoted newline -> row error; limits 20,000/20,001 rows, 8 MB+, 100,000-char field, 200,000-char field refused; NUL; FIFO/dir/device refused. XLSX: bool/date/formula-without-cache -> row errors; merged cells error row; 200 MB zip bomb refused; billion-laughs and XXE refused (defusedxml); truncated/empty/text "not a valid .xlsx"; 20,000 rows 1.4 s. Length numbers: 1e3, -0, NaN, inf, full-width digits, 1.234,5 rejected; 1,234 -> 1.234 (known). KiCad: depth limit 64, atom limit 4M, 32 MB limit; duplicate refs, invalid UTF-8/16, unmatched brackets clear errors; DOCTYPE with 100 KB padding refused (UTF-8); netlist import one History.execute (single undo). Ampacity CSV bad input rejected with "Nothing was changed". ID regex: trailing newline doesn't pass fullmatch.

##### Questions for the owner
E-4/E-5 (release freeze scope: units, box connectors, parts, config? what is Baseline.content_hash for?); E-13 (undo of saved release?); E-7 (netlist vs Pin.locked; clear interface when signal lost?); E-12 ("1,234" decimal comma or thousands? pin_count bound?); E-15 (date policy); segregation of duties (author/checker/approver may be same free-text name); exit-code policy (import row errors 1 or 2? drc/log/diff exit 2 on damaged project E-2?); a revision can be released with no change at all (revise then release): intended?

### Area F1: Editor (GUI) part 1: window, controller, dialogs, file handling

F1-1 [high] Journal "Restore" after "Open read-only" makes the project editable and lock-less; Save writes into the folder another instance holds (controller.py:689-699 restore_journal -> _install(res.project, root, lock=None); main_window.py:1353). Repro t2.py: B.open_project -> ro, Restore -> read_only False, lock None, add_unit OK, ctl.save() "B saved".
F1-2 [high] reload() (check_disk "Reload") drops read-only for a project opened read-only because another instance holds it (controller.py:749-755). Repro t3.py: read_only False, lock None after reload.
F1-3 [medium] Read-only open: "Discard them" / Save-As clear_journal() deletes the OTHER instance's autosave journal (main_window.py:1359-1362, controller.py:730-731). Repro t3.py: A journal True -> False.
F1-4 [high] DRC helper errors/garbage -> exception in QThread.run, found=[] applied as complete result: panel "Design rules: all 33 rules checked." + "No problems. Nice work." (drc_process.py:124 catches only OSError/EOFError; controller.py:53-54,183-186). Modes error/garbage/badreply/wrongtype in t10.py/t11c.py; wrongtype returns [1,2,3] as findings.
F1-5 [medium] No timeout on helper: hang => DRC "checking..." forever and close()/open/new block forever in wait_drc (controller.py:201-204,757-763). t11c.py hang: main thread stuck in wait_drc in closeEvent. Stress size legit run blocks close 2.6 s, open 1.4 s (t12.py).
F1-6 [high] GUI Export writes outputs into read-only (other instance / newer-version) and damaged (recovered) projects; CLI refuses both (cli/main.py:278-292). t17/t18: "280 files written" for locked-by-A read-only and for recovered project.
F1-7 [high] Release -> Save -> Undo -> Save erases the release (baseline + change-log entry) from disk; D-102 says "undoable until saved". t24.py: on disk status in_review, baselines 0, changelog 1.
F1-8 [high] Corrupt/hand-edited settings ini crashes the GUI at startup: ui/scale=abc|1.5|empty -> ValueError (main_window.py:1436), ui/geometry=garbage -> TypeError (:1450). t6.py.
F1-9 [medium] New project / example with invalid name (>200 chars or control chars) -> pydantic ValidationError escapes new_project_flow (catches HarnessError/OSError only), main_window.py:1288-1292, 1315-1319. t15.py.
F1-10 [medium] open_project ignores restore_journal() False; Restore on a journal of a damaged project silently does nothing, journal kept, then overwritten by next autosave (main_window.py:1359-1360). t16.py.
F1-11 [medium] ImportDialog: after an edit makes CSV invalid, OK stays enabled with previous plan and imports it (dialogs.py:360-367). t22.py: IF-900 imported while text shows other content/error.
F1-12 [medium] Delta for Delete interface / undo of add interface has units=set() (controller.py:333-338), Properties panel keeps stale Auto/Confirm rows. t19.py.
F1-13 [medium] ToastHost drops a repeated message even when it carries a new Undo; old Undo button then reports "no longer the latest" (main_window.py:178-179). t9.py.
F1-14 [medium] Toolbar filter value list refreshed only on full Delta (main_window.py:810-813): empty after Generate; after undo of generation filter targets vanished bundle and fades 24/24 links. t32.py.
F1-15 [medium] connect_from not reset when source unit deleted/undone: second click raises EditError out of pick() (controller.py:401-432). t30.py.
F1-16 [medium] _rebuild_connect_menu leaks QActions (window.addAction in _act, never removed); stale "CAN" palette entry runs _toggle_connect on missing type -> KeyError in connect_hint, loop on each refresh (main_window.py:719-724). t33.py.
F1-17 [medium] check_disk: project deleted or project.json removed -> LoadError escapes slot on every window activation (main_window.py:1406-1418, controller.py:749). t4.py. Damaged project.json reload shows "Untitled project" recovery.
F1-18 [low] "Keep my version" is not remembered (fingerprint unchanged): box closing re-activates window and re-asks. t29.py: 2 dialogs from one check.
F1-19 [medium] PlanWorker/OutputsWorker exceptions shown as "Generation cancelled"/"Export cancelled"; PlanWorker.error never set (main_window.py:102-152). t13.py.
F1-20 [medium] Progress dialog not shown for first 400 ms (setMinimumDuration) so UI is live while worker reads live project; edits possible (t26.py); apply_generation has no staleness check (t25.py: stale plan applied, status "stale"). Docstring at :103 wrong.
F1-21 [medium] Project on read-only media cannot be opened even read-only (lock acquire first, SaveError naming .harness.lock.takeover) (controller.py:665-671). t21.py (mocked EROFS; I am root).
F1-22 [low] Open on a non-project folder leaves .harness.lock.takeover in it (t34.py).
F1-23 [medium] Status "Unsaved changes (autosaved to the recovery journal)" shown for sample/no-folder project where nothing is autosaved (strings.py UNSAVED; controller.py:767-769). t17.py.
F1-24 [low] Explicit "Discard changes" on close leaves journal; next start offers Restore (t36.py).
F1-25 [low] Opening the folder that is already open offers "already open in another window", and Read-only choice releases own lock (t1.py).
F1-26 [low] Accessible names missing: IssuesDialog list, HistoryDialog list, DiffDialog combo+list (t23.py); test_accessibility does not open them and accepts a tooltip as a name.
F1-27 [low] Many UI strings outside strings.py (controller messages, labels, dialogs.py:326 headers, "Arrange diagram", etc.); main_window.py:873 string-matches an English message.
F1-28 [medium] Weak tests: mutation removing follower logic from _delta_of -> 93 tests pass (journeys/changes/audit_gui/filters/readability); test_cancelled_worker replaces compute_plan; no test for DRC helper error/hang, restore after read-only open, release+save+undo, bad settings; smoke test uses real ~/.config settings; no-op statements in tests.

### Area F2: Editor (GUI) part 2: canvas, panels, legend, tour

(Saved by the lead from the reviewer's file report. 14 findings: 1 critical, 3 high, 6 medium, 4 low. Scratch: audit/F2/.)


#### F2-1 [critical] Segmentation fault: UnitItem.boundingRect changes before prepareGeometryChange/removeItem (stale scene index)
- Where: gui/canvas.py UnitItem.height() (l.73-76) used by boundingRect()/shape() (l.88-94); DiagramScene.apply/_apply_units_and_links (l.1032-1088: removeItem at l.1075 after the model already changed; prepareGeometryChange at l.1070 called after the new height is already in effect); refresh_all (l.1095-1103, mode already switched).
- What is wrong: a unit's height depends on live model state (expert: number of connectors; guided: number of links). The model/_adj is already changed when the scene reacts, so boundingRect() already returns the NEW rect when Qt is told (prepareGeometryChange) or when the item is removed. Qt's BSP index removes an item using its current rect, misses the cells holding the old rect, and keeps a dangling pointer; the next paint dereferences it -> SIGSEGV of the whole program.
- Evidence (real UI actions, offscreen, original code): flatsat example (resources/examples/projects/flatsat), guided: select OBC1 (13 links), act_delete (confirm accepted), processEvents -> "Fatal Python error: Segmentation fault", rc=139 (script ex_crash.py flatsat guided; also small-satellite guided, flatsat expert). sat15 sample guided: deleting OBC1 or PCDU1 crashes (min_crash.py). Expert mode on the default mini3 sample: act_expert, palette button 'payload' click, act_undo (the toast's Undo does the same) -> segfault, 3/3 runs (ui_crash.py A). Random delete/undo/redo on sat15: 6/6 seeds crash (big_crash.py). Backtrace: QGraphicsView::paintEvent -> QGraphicsScene item drawing, no Python frame.
- Proof of cause: a scratch copy where UnitItem.height() returns a cached value updated only next to prepareGeometryChange (h/ copy) survives all the above (A 2/2, big_crash 6/6, 8 fuzz seeds) while the unmodified code crashes.
- Why it matters: crash on normal use (delete a connected unit, undo an Add in Expert mode) = lost unsaved work (autosave journal only every 1.5 s); blocks release.
- Proposed fix (minimal): cache the height in the item (self._h), recompute it only immediately after prepareGeometryChange() (in _apply_units_and_links and refresh_all), and make boundingRect()/shape() use the cache; same pattern for any other boundingRect that reads live model state (ZoneItem.lane_height in _update_extent assigns before prepareGeometryChange; not shown to crash).
- Test that would have caught it: a GUI test that loads flatsat, deletes the most connected unit (and Expert: add unit then undo), then runs QApplication.processEvents()/view.grab() with the window shown; currently tests never paint after the edit.
- Confidence: confirmed (reproduced)
- Needs owner decision: no

(F2-1 addendum) Second source of the same bug: controller._note() (gui/controller.py:327-344) adds the endpoint units of an interface to Delta.units only `if key in self.project.interfaces` (i.e. not for a Delete). Verified: deleting IF-TM-RW1 gives Delta(units=set(), interfaces={'IF-TM-RW1'}); the two end units change guided height (link count) without prepareGeometryChange() and without update(). See F2-2 for the properties panel consequence.

#### F2-2 [high] Stale properties form after undo/delete of an interface: "Confirm" button of a deleted interface raises KeyError in a slot
- Where: gui/controller.py:327-344 (_note: units of a Delete(interfaces) are not in Delta.units), gui/panels.py:300-313 (PropertiesPanel._changed rebuilds only if the selected unit is in delta.units), controller.confirm_interface -> core/edit.py:643 (project.interfaces[interface_id] raises KeyError, not caught by attempt(), which only catches HarnessError/ValidationError).
- What is wrong: Expert mode, unit OBC selected, interface added by "connect" with auto-chosen connectors (form shows an Auto badge and a Confirm button on the connector card). Undo removes the interface; the unit's form is not rebuilt, the Auto badge and Confirm button stay. Clicking Confirm raises an uncaught KeyError ('IF-001').
- Evidence: stale_props.py (expert; add_interface_between rs422 OBC->PCDU; select OBC; undo; click the remaining confirm-OBC-J.. button) prints traceback ending `KeyError: 'IF-001'` and "clicked ok" (exception only goes to stderr).
- Why it matters: stale controls acting on a non-existent object; uncaught exception in a Qt slot (PySide prints and continues; with sys.excepthook installed it may show a crash dialog).
- Proposed fix (minimal): in _note add the endpoints of a deleted interface using the pre-change project (capture like _owners), or make PropertiesPanel._changed also rebuild when any interface/endpoint of the selected unit is in delta.interfaces; make ops_confirm_interface raise EditError for unknown IDs.
- Test that would have caught it: select unit, add interface via connect, undo, assert no confirm-* button remains.
- Confidence: confirmed (reproduced)
- Needs owner decision: no

#### F2-3 [high] Interface table filter finds nothing for any text containing "-" or a space (IDs like IF-PWR, two words)
- Where: gui/panels.py:1029-1032 (_set_filter: `re.escape(text)`) and 947-954 (_RowFilter.filterAcceptsRow: `pattern().lower().split()`).
- What is wrong: the text is regex-escaped (Python escapes "-" and " " as "\-" and "\ ") and the proxy then splits the *escaped pattern* into words and looks for those words, backslashes included, in the row text. So "IF-PWR" searches for "if\-pwr"; "power rw1" for "power\" and "rw1". The placeholder/docstring promise "every word typed is matched against ID, name, type, units, requirement".
- Evidence (filt.py, mini3, 2 interfaces): filter "rs422" -> 1 row; "IF-PWR" -> 0; "if-pwr-rw1" -> 0; "IF-PWR-RW1" -> 0; "power rw1" -> 0; "RW1 OBC" -> 0 (pattern 'RW1\\ OBC').
- Why it matters: the main way to find an interface by its ID or by two words silently shows an empty table.
- Proposed fix: store the raw text on the proxy (e.g. self.proxy.words = text.lower().split()) and use that in filterAcceptsRow + invalidateFilter(); do not use QRegularExpression.
- Test that would have caught it: type "IF-PWR" and "power rw1" in the filter and assert 1 row.
- Confidence: confirmed (reproduced)
- Needs owner decision: no

#### F2-4 [medium] Legend is not repainted when the kinds of link in use change (stale key)
- Where: gui/legend.py:30-40 (set_project) and 43-50 (_entries uses only interface types that are *used*).
- What is wrong: the redraw signature is built from all interface_types of the project (and connector families), but the entries drawn are only the types used by at least one interface. Adding the first link of a type, or deleting the last one, leaves the signature unchanged, so neither update() nor relayout happens.
- Evidence (legend2.py, mini3): count paintEvent calls of LegendBar; delete IF-TM-RW1 (the only RS-422 link) and processEvents twice -> 0 paints, so the key still shows an "RS-422" entry; undo -> 0 paints. (Entries are computed live, so any unrelated repaint fixes it, but nothing forces one.)
- Why it matters: legend inconsistent with what is drawn (explicit review focus).
- Proposed fix: put `sorted({i.type_id for i in project.interfaces.values()})` in the signature.
- Test that would have caught it: delete the last link of a type, assert the legend repainted / entries equal used types.
- Confidence: confirmed (reproduced)
- Needs owner decision: no

#### F2-5 [low] OutlinePanel keeps the old highlighted row after the selection is cleared
- Where: gui/panels.py:1376-1380 (_select_current returns early when `sel is None`).
- Evidence (outline.py): select OBC (outline row selected), ctl.select(None) -> tree.selectedItems() still ['OBC: On-board computer (nominal)'].
- Fix: clear the tree selection (with _syncing set) when sel is None.
- Confidence: confirmed. Needs owner decision: no

#### F2-6 [medium] A unit can be dragged outside the scene rectangle and then cannot be reached (negative / far positions are saved)
- Where: gui/canvas.py UnitItem.itemChange (l.383-389: only snaps to the grid, no clamp), core/edit.py:542 ops_move_unit (no clamp), DiagramScene._update_extent (l.1017-1030: sceneRect starts at (0,0) and only grows downward).
- Evidence (drag.py, real QTest mouse press/move/release on RW1 in mini3): result `RW1 pos (-2680,-1400)`, model placement x=-2680.0 y=-1400.0; sceneRect stays (0,0,960,700); `centerOn(item)` shows scene rect (0,0,957,504), which does not intersect the item. Only Fit (which uses the content rect, zooming to 0.227) or Arrange/Undo recover it; scrolling, minimap and Tab (ensureVisible) cannot reach it. A drop far right likewise lies outside the sceneRect width (derived from the zone count).
- Why it matters: a unit "disappears" after a sloppy drag; saved in the project; the positions go into the saved layout.
- Proposed fix: clamp in itemChange (x>=0.., y>=0) or include unit rects in _update_extent (sceneRect = united with content).
- Test: drag beyond the top-left, assert item stays within sceneRect.
- Confidence: confirmed. Needs owner decision: yes (clamp vs. grow the scene).

#### F2-7 [medium] Tour highlights hidden panels at high UI scale / small windows; closing the window within 200 ms of the first-run start prints a RuntimeError
- Where: gui/tour.py:81-105 (show_step does not check target.isVisible()), gui/main_window.py:726-732 (_tour_targets) + auto_layout (hides docks), main_window.py:324 (QTimer.singleShot(200, self.tour.start) is not cancelled on close).
- Evidence (tour1.py, 1440 px window): at UI scale 200% the left dock is hidden, so steps 1 and 3 ("palette", "types") draw the frame at the hidden panel's old rectangle (0,140,375,523) over the canvas and the "generate" step's button is not visible either (target visible: False for steps 0, 2, 4); the card text still points at things that are not on screen. At 150% the right dock is hidden. tour2.py: make(first_run=True); close + deleteLater within 200 ms -> "RuntimeError: libshiboken: Internal C++ object (QLabel) already deleted" traceback from tour.start. Closing mid-tour leaves tour/done unset (the tour restarts at next launch); that may be intended (QUESTION).
- Fix: skip or reposition steps whose target is not visible (or show the dock); guard start() with a QPointer/isVisible check.
- Test: scale 200% -> every tour step target isVisibleTo(window).
- Confidence: confirmed. Needs owner decision: no.

#### F2-8 [low] Long IDs / connector names are clipped without an ellipsis on the canvas
- Where: gui/canvas.py:219 (unit ID drawn in a 160 px box, no elision), 352 (connector designator in ROW_NAME_W=24 px box, right aligned, no elision) vs the name elision that exists in guided mode (l.237). Unit IDs have no length limit (rename to "OBC-"+40*"X" accepted), connector names up to 200 chars.
- Evidence (longname.py / longid.py, screenshots longname_expert.png, longid.png): connector named "Backplane-Telemetry-Primary-J01" is drawn as "/-J01" with its beginning hidden behind the connector picture; the long ID is cut at "OBC-XXXXXXXXXXXX" so two IDs that differ only at the end look the same. Guided unit name (CJK + RTL text) elides correctly.
- Fix: use QFontMetrics.elidedText for both, and a tooltip with the full text (unit tooltip already exists).
- Confidence: confirmed. Needs owner decision: no.

#### F2-9 [high] Properties panel silently rounds Max current / Voltage to 6 significant digits when a field merely loses focus
- Where: gui/panels.py:501 (`f"{cur:g}"` fills the field), 504 (editingFinished -> _commit_number), 558-567 (_commit_if compares the re-parsed rounded value with the model value); same display rounding in the interface table (panels.py:914, `f"{i.max_current_a:g}"`; editing a Max A cell commits the rounded text).
- What is wrong: `:g` keeps 6 significant digits. A model value such as 12.3456789 A is shown as "12.3457". editingFinished is emitted on focus-out even if the text was not changed; _commit_number parses "12.3457", sees it differs from 12.3456789 and writes it as a new undo step.
- Evidence (round.py, mini3): `ctl.update_interface("IF-PWR-RW1", max_current_a=12.3456789, voltage_v=28.123456789)`, select the interface, emit editingFinished on both fields (what Tab through the form does) -> "model 12.3456789 28.123456789" becomes "12.3457 28.1235", revision changed True. 1234567.0 would show as 1.23457e+06.
- Why it matters: engineering values changed without the user typing anything (values imported from CSV/netlist keep full precision); violates "never invent engineering values".
- Proposed fix: format with repr-like shortest round-trip (`format(value, '.15g')` or `repr`), and in _commit_if/_commit_number do nothing unless the text differs from the text the field was filled with (keep the initial text; compare text, not float).
- Test that would have caught it: set an interface current 12.3456789, focus-out the field, assert value and revision unchanged.
- Confidence: confirmed (reproduced). Needs owner decision: no.

#### F2-10 [low] Interface table / model accepts a newline in Name, Arabic-Indic digits in numeric cells; invalid chain text fails silently
- table.py run (mini3): Name "line1\nline2" accepted (True; the table then shows two lines and the properties field cannot hold it); Max A "٣" accepted as 3; Chain "bogus"/"" returns False with no message (only reachable through the delegate). Everything else I tried (abc, -5, 1e999, nan, 1,5, 5000-char name, NUL, 300-char requirement) is rejected with a message and the model is unchanged.
- Confidence: confirmed. Needs owner decision: yes (are newlines allowed in names?).

#### F2-11 [medium] Connect tool keeps a source unit that was undone away; the second click raises an uncaught EditError
- Where: gui/controller.py:401-432 (pick: ops_add_interface is outside any try), connect_from is only cleared by mode change / install / end_connect; _after_change does not validate it.
- Evidence (connect.py): add unit OBC1, begin_connect("rs422"), pick(OBC1) (connect_from set), undo (unit gone, connect_from still ConnectFrom('OBC1',..), tool 'connect'), pick("PCDU") -> traceback `EditError: Unit 'OBC1' does not exist.` from the mouse/keyboard handler; the user gets no message. Same if the source unit is deleted by Delete while the tool is active (not tried separately).
- Fix: in _after_change, drop connect_from when its unit is no longer in project.units (emit connectChanged); wrap ops_add_interface in pick with the HarnessError handling used elsewhere.
- Test: begin_connect, pick, undo, pick -> message, no exception.
- Confidence: confirmed. Needs owner decision: no.

#### F2-12 [medium] With the Connect tool active, dragging a unit moves it on screen but never in the model
- Where: gui/canvas.py UnitItem.mousePressEvent (l.365-368 returns before setting _press_pos and without calling super) and mouseReleaseEvent (l.377-381: only commits when _press_pos is not None). Qt's default mouseMoveEvent still moves an ItemIsMovable item for a held left button.
- Evidence (drag2.py, real QTest press/move/release with ctl.begin_connect("rs422")): item pos (140,170) while model placement stays (30,60), revision unchanged; a later mode switch/refresh keeps the displaced item (apply only repositions units that are in a Delta). The links are routed to the displaced position; saving writes the old position; the picture and the file disagree.
- Fix: in connect mode set `_press_pos` and revert the item on release (or clear the ItemIsMovable flag while ctl.tool == "connect"), or call move_unit on release also in connect mode.
- Test: drag in connect mode, assert item pos == model placement.
- Confidence: confirmed. Needs owner decision: no.

#### F2-13 [medium] Switching to Expert mode does not grow the scene: the lowest units end outside the scene rectangle and the lane backgrounds
- Where: gui/canvas.py refresh_all (l.1095-1103, called on modeChanged; never calls _update_extent) vs _update_extent (l.1017-1030, computes the bottom from item heights).
- Evidence (extent.py, sat15, 14 units): guided: lowest unit bottom 1370 / sceneRect bottom 1536; after set_mode("expert"): lowest unit bottom 1738, sceneRect bottom still 1536 (lane_height 1536, lane backgrounds 1536 high), "unit outside scene: True"; back to guided: False. A differential fuzz (fresh DiagramScene vs live scene after random edits) reports the extent mismatch right after every mode switch.
- Why it matters: the view cannot scroll to the bottom of the lowest unit and the lane background stops under it; the minimap scales by sceneRect.
- Fix: call self._update_extent() at the end of refresh_all (and after prepareGeometryChange of the units).
- Test: expert mode, all unit bottoms inside sceneRect.
- Confidence: confirmed. Needs owner decision: no.

#### F2-14 [low] Label chip registry is stale after the link values are edited (update_path is a no-op inside the batch)
- Where: gui/canvas.py LinkItem.update_path (l.476-477 `if self.dscene._batch: return False`) called from _apply_units_and_links (l.1083, inside the batch) for changed non-follower links; the later _redraw_changed only calls update_path when the route changed.
- Evidence (chip.py, mini3): IF-PWR-RW1 has no values: chip registered 30 px, painted 30 px. update_interface(voltage 28.5, current 123.456): registered chip width stays 30.0, painted chip width 131.0. chip_free()/chip_place() therefore use the old 30 px box, so labels can overlap other labels (the overlap avoidance is blind to the longer chip).
- Fix: in apply(), after the batch, call update_path (or a chip refresh) for every link in delta.interfaces that is not a follower, not only those whose route changed.
- Confidence: confirmed. Needs owner decision: no.

##### Files read (line counts)
gui/canvas.py 1382, gui/panels.py 1395, gui/glyphs.py 343, gui/legend.py 135, gui/tour.py 118, core/routing.py 319, core/describe.py 111 (all completely); also gui/controller.py 788 (Delta, selection, connect), gui/tokens.py 109, gui/theme.py 92, parts of gui/main_window.py (tour wiring, shortcuts, auto_layout), core/edit.py (heights, move, delete, rename, lanes). Tests: tests/gui_helpers.py 68 read; test_gui_journeys.py, test_gui_filters.py, test_audit_gui.py run with -k "delete or undo or filter or expert" (16 passed, i.e. they do not detect F2-1 / F2-3); test_accessibility.py, test_gui_readability.py, test_gui_perf.py (not run) only skimmed by name, NOT read completely (time).

##### Commands run (summary)
Scripts in .../audit/F2/: fuzz1/2/3.py (differential fuzz: live scene vs fresh DiagramScene after random edits), replay.py + ddmin.py (crash minimisation), ui_crash.py, ex_crash.py, min_crash.py, big_crash.py (crash repros), drag.py, drag2.py (real QTest mouse drags), tab.py, tab2.py, tour1/2.py, glyphs_all.py (-W error), paintsweep.py (-W error; 4 examples x light/dark x 100/200% x guided/expert x selections x zoom 0.05..3, stderr empty), mem.py (1000 rebuilds + 300 installs), table.py, filt.py, round.py, legend2.py, chip.py, extent.py, a11y.py, longname.py/longid.py. A scratch copy (F2/h) with a cached UnitItem height was used to prove the cause of F2-1 and to continue the fuzz without segfaults.

##### Checked and found fine
- Route cache `_routes_key`: with the crash fixed in a scratch copy, 30+ differential fuzz runs (move, connect, endpoint change, redundancy, rename, mode switch, undo/redo, zone, delete) found no link drawn differently from a freshly built scene; Delta.followers did not hide a needed repaint (apart from F2-14 chip registry). Focus-set / opacity / z-order matched a fresh scene after every step (filter set to the same value).
- Tab/Shift+Tab walk: empty diagram, one item, past both ends, item deleted while focused, undo of focused item: no exception, focus leaves the diagram correctly. Filtered (faded) items stay in the Tab order (question below).
- Pictograms: every interface type of the default project has its own glyph, unknown type/category falls back and draws something; all connector families x pins 0..10000 x genders (incl. bad strings) draw non-empty without warnings (-W error).
- Paint-time exceptions: none in the sweep above (stderr empty). Dark theme and 200% scale render.
- Rapid drags (150), drag in read-only (no move), drag onto another unit, undo of all moves: item positions equal the model (except F2-12, connect tool).
- Interface table cell validation (abc, -5, 1e999, nan, 1,5, NUL, 5000 chars) rejected with message and model unchanged (except F2-10 notes). Lazy refresh of hidden tabs (Problems, To-do, Table, Plans, Outline) showed no stale content when shown.
- Self links are refused by the compat check; many parallel links route without exception.
- Memory: 1000 scene rebuilds and 300 project installs keep item counts constant (UnitItem 14, LinkItem 24); RSS grew about 125 -> 141 MB over 1300 cycles (about 33 KB per install; not investigated, QUESTION whether acceptable).
- Accessible names: all visible buttons, edits, combos, tables, trees in main window, both properties forms and every tab have names; only the bottom QTabWidget "bottom-tabs" has none (low).
- Extreme coordinates (1e12, 1e300, nan, inf via move_unit): no exception; fit/zoom survive (zoom after a 1e9 fit jumps to 0.02; hostile files only). Zoom limits normal project: 0.25..3.0.

##### Not covered
Problems-panel stale card content (signature = id/title/severity; I could not find an edit that changes `why`/fix with the same key), huge tables (2000 interfaces), 2000-unit zoom/fit, RTL text in connector rows, tour flag write failure (QSettings does not raise), test_gui_readability/test_accessibility/test_gui_perf reading, mutation tests of the weak tests, keyboard-only walk of every menu action. Known open item "selecting a unit at stress size is slow" not re-measured.

##### Questions for the owner
1. Should units be clamped inside the scene (F2-6) or should the scene grow to fit them?
2. Should tour/done be set when the window is closed mid-tour (now not set, so the tour returns next launch)?
3. Should filtered-out (faded) units/links stay in the Tab order?
4. Keyboard-only users in Expert mode cannot choose a specific connector with the Connect tool (Enter picks the first valid port; _first_valid_port); the endpoint combos in Properties are the only way. Intended?
5. Are newlines in names allowed (F2-10)?

### Area G: Tools, packaging, CI, dependencies

(Saved by the lead from the reviewer's hand-back. 17 numbered items: 0 critical, 1 high, 9 medium, 7 low (several group smaller items). Scratch: audit/G/.)
Files read completely: harness/tools/*.py (31), harness/packaging/** (cli_entry, gui_entry, install.sh, uninstall.sh, .desktop.in, README.txt, svg, Dockerfile.build-24.04, build-in-container.sh, clean-machine-test.sh), .github/workflows/harness-ci.yml and main.yml, harness/pyproject.toml, root pyproject.toml, setup.py, requirements.txt, all .gitignore, harness/prototype/ (app.js, template.html, index.html), examples/templates/** (ci/build.sh, ci/github-actions.yml), docs RELEASE/developer/INSTALL; tests test_installers, test_licences, test_scf, test_prototype, test_prototype_build, test_vulnerability_check, test_usability_kit, test_soak, test_trace, test_sdd_components, test_compliance_matrix, test_metrics, test_docs, test_docs_links.
Ran (scratch copies only): every generator (match committed files; second run under COLUMNS=30, LANG=C, TZ=Asia/Tokyo, random PYTHONHASHSEED identical); wheel built twice (identical hashes) and compared with the source tree; REAL PyInstaller package (tools.build_installer) and .deb built; frozen --selftest and frozen CLI end to end (new, generate, export, verify, drc, templates, import-parts); objdump glibc symbols; install.sh/uninstall.sh with fake and real trees (HOME, --prefix, HARNESS_INSTALL_ROOT in scratch); mutation of History.redo against soak; release_check --quick, gen_scf, licence_report, bad-argument runs; targeted pytest files; import scan; TODO/secret/absolute-path greps; link check of 1319 relative Markdown links (0 broken); .desktop key check; Python 3.12 syntax parse.
Not covered: Python 3.12 runtime (tests ran on 3.13), shellcheck, desktop-file-validate, extract_requirements (needs PDFs), gen_sbom and check_vulnerabilities (need network), --system install and clean-machine-test.sh. Known items confirmed in one line: root setup.py reads docs/README.md; CI does not produce SHA256SUMS.
Marker greps: no TODO/FIXME/XXX/HACK outside upstream (docs/buildscript.md:7 is upstream text), no secrets/tokens/debug prints/pdb; only developer-path hit is a KiCad test fixture (tests/fixtures/kicad/unit.net(.xml) source field /home/user/projects/...; benign). Prototype: no eval, fetch, XHR, CDN or http; every dynamic innerHTML value goes through esc() or is a generated ID/fixed string.

#### G-1 [high] Frozen package bundles undeclared third-party code missing from LICENSES and the SBOM
- tools/build_installer.py:16-22 (EXCLUDES and FORBIDDEN check), tools/collect_licences.py:286, tools/gen_sbom.py. The PyInstaller PYZ of both executables contains build-environment modules: chain pydantic._internal._core_utils -> rich.console -> rich.syntax -> pygments -> chardet. The FORBIDDEN check only looks at top-level names in _internal/, so PYZ-resident modules are invisible.
- Evidence: build/.../PYZ-00.toc has pygments 340 modules, rich 91, markdown_it 62, mdurl 6, toml 4, chardet 11, plus _internal/chardet/ and a compiled mypyc .so. dist/.../LICENSES/README.txt lists only annotated-types, defusedxml, et_xmlfile, openpyxl, pydantic, pydantic_core, PySide6, shiboken6, typing_extensions, typing-inspection and IBM Plex fonts. Installed licences: rich MIT, Pygments BSD-2, chardet 0BSD, markdown-it-py MIT, mdurl MIT, toml MIT.
- Why: shipped code whose licence notices are not shipped and not in the SBOM; the release claims "runtime dependencies only"; adds size/attack surface; depends on the build host.
- Fix: add rich, pygments, markdown_it, mdurl, chardet, toml (and yaml etc.) to EXCLUDES; make the leak check read the PYZ TOC / pyi-archive_viewer against an allow-list. Owner decision: YES (acceptable if licences are added, or must they be excluded?).

#### G-2 [medium] uninstall.sh removes folders it did not install and still says "Your projects are not touched"
- packaging/ubuntu/uninstall.sh lines 223-229 (and install.sh 157-159): `rm -rf "$prefix/{harness-design-studio,_internal,cli,LICENSES}"` with no ownership marker; docs claim "it removes only what the installer put there" (INSTALL.md:101). Evidence: `proj/` never installed to, containing cli/mine.txt, LICENSES/mine.txt, _internal/x: `sh uninstall.sh --prefix proj` prints "Removed. Your projects are not touched.", rc 0, and proj no longer exists. install.sh does the same rm -rf before copying on reinstall.
- Fix: write a marker/manifest (.harness-design-studio-install) at install time; act only when present, remove only the listed items. Test: extend test_uninstall_removes_only_what_was_installed with a user-owned cli/ and LICENSES/.

#### G-3 [medium] install.sh can delete its own unpacked package
- install.sh:134 (guard tests only prefix == here), :157-158. With --prefix = parent of the unpack folder, `rm -rf $prefix/harness-design-studio` removes $here, then aborts on cp: "cp: cannot stat '.../harness-design-studio/harness-design-studio'", rc 1, `ls B/pkg` empty. A plausible call (`tar -C ~/opt ...; ~/opt/harness-design-studio/install.sh --prefix ~/opt`) destroys the source with a half-finished install; the rm -rf/cp upgrade is not atomic. Fix: refuse when $here is inside $prefix/<item>; copy to a temp name then rename.

#### G-4 [medium] Ownership of installed files comes from whoever unpacked or built the tarball
- install.sh:158 (`cp -a`), tools/build_installer.py:93 (shutil.make_archive without owner/group). make_archive stores builder uid/gid (demonstration 1001/1001; CI tarball carries the runner's uid; `sudo tar xzf` preserves it). `sudo ./install.sh --system` uses cp -a as root, preserving the unpacking user's uid. Evidence: package chowned 1234:1234, `--prefix opt9`: `drwxr-xr-x 1234 1234 ... cli`, executables `-rwxr-xr-x 1234 1234`. /usr/local/lib/harness-design-studio (target of root-owned symlinks in /usr/local/bin) ends up owned by an ordinary uid who can replace code others run. Fix: make_archive owner="root", group="root" (+ fixed mtimes); install.sh use cp -R and chown -R root:root when root.

#### G-5 [medium] The versions step of release_check passes vacuously; the release can reuse 0.1.0
- tools/release_check.py:32-43 compares pyproject.toml, __init__ and the first non-"Unreleased" CHANGELOG heading; never checks that Unreleased is empty/renamed nor that the version is not an existing tag. On master v0.1.0 exists and Unreleased is large. Evidence: versions() returned (True, '__init__ 0.1.0, pyproject 0.1.0, CHANGELOG 0.1.0'); `git tag -l` shows v0.1.0. A forgetful maintainer gets a green gate and packages named 0.1.0 with different bytes; apt will not upgrade a same-version .deb. Fix: fail when `## Unreleased` has content at release time (non --quick) or v<version> is already a git tag. Owner decision: YES.

#### G-6 [medium] build_deb is not reproducible unless SOURCE_DATE_EPOCH is set; the unit test masks this
- tools/build_deb.py:151-161, 205-207; tests/test_installers.py:97, 242 (monkeypatch.setenv SOURCE_DATE_EPOCH). epoch() sets file times but dpkg-deb is called without SOURCE_DATE_EPOCH, so ar member timestamps are build time. Evidence: two build_deb runs on the same real tree: `cmp: differ: char 32` (ar timestamp), equal sizes 62972964; fake package without env var identical False, with True. Docstring and RELEASE docs say "Reproducible"; CI and release_check do not set it; recorded SHA-256 can never be matched by a rebuild. Fix: pass env SOURCE_DATE_EPOCH to dpkg-deb. Test: run without the monkeypatch.

#### G-7 [medium] XLSX output bytes depend on whether lxml is installed
- openpyxl/xml/__init__.py uses lxml if importable; tools/build_installer.py excludes lxml; pyproject neither declares nor forbids it; tests/helpers.py:24-37 hashes XLSX by cell content. Evidence: frozen CLI export of flatsat vs source run in the audit venv (lxml 5.4.0): `diff -rq` reports all 8 harness .xlsx, system.xlsx and manifest.json differing; with OPENPYXL_LXML=False the source run is byte-identical to the frozen output. sheet1.xml differs only in `<outlinePr ... />` vs `<outlinePr .../>`. "Byte-identical output for the same design" does not hold across machines; manifest SHA-256 values change between a dev checkout and the shipped app (false changes under change control). Fix: force OPENPYXL_LXML=False (env var before openpyxl import) in outputs/import code; golden test in a subprocess with the variable on/off. Owner decision: YES (is cross-machine byte identity of XLSX required?).

#### G-8 [medium] Release gate skips tests silently and passes
- tools/release_check.py:55-64, packaging/ubuntu/container/Dockerfile.build-24.04, tests/test_prototype.py:31-33, tests/test_outputs.py:136, tests/test_atomic_lock.py:59. CI sets HARNESS_REQUIRE_BROWSER=1 and installs poppler-utils and Chromium; release_check and the release Docker image set none, and build-in-container.sh runs as root. Skip conditions: no Chromium (prototype tests), no pdfinfo (PDF output test), root (atomic-lock permission tests). RELEASE.md step 7 says full suite passes incl. GUI journeys; the report shows only tail(out, 3) with no skip count; GUI modules use pytest.importorskip("PySide6"). Fix: set HARNESS_REQUIRE_BROWSER=1, install poppler and Chromium in the image, run as non-root, fail on skips beyond an allow-list, print the skip count.

#### G-9 [medium] soak's "undo then redo restores the exact model" is a vacuous assertion
- tools/soak.py:292-298 (`assert model_hash(project) != "" and True`). Evidence: History.redo changed in a scratch copy to not apply ops: `pytest tests/test_soak.py` still 2 passed and `python -m tools.soak 1000 7` prints "all invariants held" (test_commands catches that mutation). Fix: record before = model_hash(project) before undo; assert equality after undo+redo.

#### G-10 [medium] The GitHub Actions template is weaker than build.sh; the README says "the same"
- examples/templates/ci/github-actions.yml:17-23, ci/build.sh, templates README row. build.sh runs `harness drc` (the only command failing on unwaived design-rule errors); the workflow runs check, generate, verify, export, verify --outputs but not drc; `_check` does no DRC (cli/main.py). Not reproduced end to end (could not build a project where DRC fails but generate and verify succeed). Fix: add `harness drc design > drc-report.md` and upload it, or say "similar". Confidence: likely. Owner decision: YES (should unwaived DRC errors fail CI?).

#### G-11 [medium] gen_scf: exits 0 with an empty SHA256SUMS; source manifest depends on the environment
- tools/gen_scf.py:22, 68-71, 92; tools/release_check.py:156-160. With no deliverable in dist/: exit 0, "0 deliverables", 0-byte SHA256SUMS; release_check.integrity() only tests the files exist. SOURCE_FOLDERS includes src, so src/harness_design_studio.egg-info/ (from pip install -e or a wheel build) enters the manifest and aggregate hash (source_files contained .../PKG-INFO, SOURCES.txt). `sha256sum -c SHA256SUMS` only works from dist/, not from dist/release-docs where it is written. Fix: nonzero if no .deb and no .tar.gz; exclude *.egg-info or use git ls-files; relative paths or document the working directory.

#### G-12 [low] Deb `Depends: libc6 (>= 2.35)` is asserted, not computed, and a test locks it in
- tools/build_deb.py:116, tests/test_installers.py:255. libpython3.13.so.1.0 needs GLIBC_2.38 (build host 24.04, glibc 2.39). On 22.04 apt would install and the program fail to start (supported systems are 24.04+ but metadata doesn't say). Fix: compute with dpkg-shlibdeps/objdump or declare >= 2.39; Architecture amd64 hard-coded while tarball uses platform.machine(). Likely.

#### G-13 [low] Several smaller packaging and installer issues
- install.sh:148-155,160-161 refuses to overwrite a non-link in the bin folder but silently replaces a user's own symlink (~/.local/bin/harness) and another install's links (link target changed to opt/cli/harness); `ln -sf` without -n: a bin entry that is a symlink to a directory gets the link created inside it (realdir/harness); uninstalling prefix A deletes the shared .desktop and icon pointing to install B; `uninstall.sh --help` -> "unknown option" rc 2; `--prefix ""` silently selects the default prefix; `--prefix /` prints "must not be the folder the package was unpacked in"; Exec quoting: backslash in prefix escaped once, spec needs four; .deb copyright says "Copyright: the project owner (to be filled in before distribution)" and "decided by the project owner" (D-02 open, ships as is); packaging/ubuntu/README.txt and INSTALL.md:135 list 7 libraries but the .deb Depends, Dockerfile and CI install 15 (+libxcb-icccm4, -image0, -keysyms1, -randr0, -render-util0, -shape0, -xinerama0); .deb also ships README.txt, *.svg, *.desktop.in under /opt and README.txt tells the user to run ./install.sh; clean-machine-test.sh breaks with an absolute deb path (`$(pwd)/$deb`) and a missing argument gives unbound variable under set -u; gui_entry --selftest leaks a mkdtemp dir per run, prints only "selftest FAILED" without naming the step, --drc-worker and --selftest matched anywhere in argv; QT_QPA_PLATFORM= (empty) makes frozen selftest abort (setdefault doesn't override empty).

#### G-14 [low] CI details
- No `permissions:` block in either workflow; actions pinned to tags (v4, v5) not SHAs; upload-artifact `if-no-files-found: error` passes if only one of .deb/.tar.gz exists; concurrency group cancel-in-progress also applies to pushes on master (a second merge cancels the run on the first merge commit though RELEASE.md step 15 wants "CI green on the merge commit"); docs-only job (`changes` regex) skips tests/test_examples.py which reads docs/FLATSAT_EXAMPLE.md (test_the_flatsat_walkthrough_matches_the_example); tests/test_docs_links.py checks only top-level docs/*.md (all 1319 relative links resolve today but docs/developer/ and docs/user-manual/ not covered by a test); main.yml (upstream) runs on every push and PR for all branches (double runs).

#### G-15 [low] Staleness and drift in generated and compliance records
- compliance/metrics.json stale: regenerated now cli source_lines 921 (file 782), core functions 549 (480), cli _dispatch complexity 16, engine._build_harness 69 (68; compliance/docs/SPAMR.md says 67); no test checks it; coverage numbers in SUMMARY/SVR/SPAMR cite it. tools/gen_rule_docs.py hard-codes the four logical rules (LOGICAL); test_rule_reference_is_up_to_date compares with the same render() so a change in core/checks.py text/severity isn't detected. tools/build_guide.py markdown converter: `*.csv and *.xlsx` in code becomes <code><em>.csv and </em>.xlsx</code>; ####, nested lists, > quotes not handled; a " in a link URL breaks out of href; | inside a code span splits table cells (current guide unaffected: see K-6 for a broken row). tools/trace.py counts a requirement as traced if its ID appears anywhere in a test file even in a comment. tools/build_examples.py:256-257 deletes the shipped example folder before building (a raise, e.g. flatsat SystemExit, loses it until restored from git). tools/extract_requirements.py has no test and rewrites some standards' CSVs before it finds a missing PDF for a later one. `tools.metrics --coverage` (no value) and `usability_summary a b` give tracebacks.

#### G-16 [low] Wheel and dependency hygiene
- pyproject package-data examples/**/* omits dotfiles so the wheel lacks the five example .gitignore files (PyInstaller --add-data copies include them; harmless: saver writes .gitignore itself); defusedxml declared as runtime dependency but never imported by the project (works because openpyxl detects it; frozen build needs --hidden-import defusedxml; XLSX entity-bomb test was rejected in frozen CLI and in source runs with and without lxml); `packaging` imported by tools/collect_licences.py but not declared; tools/vendor.py downloads an unpinned `wheel`; transitive deps (typing-extensions, annotated-types, et-xmlfile, typing-inspection) not locked; SBOM from a freshly built venv not from the environment PyInstaller bundled (G-1); check_reproducible builds in-tree twice (build/ and *.egg-info left in source) and checks only the wheel (not a deliverable; tar.gz/deb not checked; tarball embeds mtimes, uid/gid, gzip timestamp); licence_report.classify: `"lgpl" in text` returns allowed before the GPL rejection ("GPL-3.0 with LGPL exception" would pass; not a current case); audit venv is Python 3.13 while CI/requires-python 3.12 and its editable install points at /home/user/wt-name/harness.

#### G-17 [low] A test writes into the source tree
- tests/test_vulnerability_check.py::test_missing_sbom_is_not_a_pass calls cv.main() without patching ROOT, which runs out.parent.mkdir(...) for harness/dist/release-docs. After targeted runs an empty harness/dist/release-docs existed (git-ignored; removed). Fix: patch ROOT or create the directory after the SBOM check.

##### Checked and found fine
All generators idempotent, match committed files, independent of locale/TZ/COLUMNS/HOME/hash seed; prototype: no network/CDN/eval/unescaped user data, index.html byte-identical to the build; frozen package --selftest ok (~2.6 s from source), `harness --version` and GUI --version work; frozen CLI new/generate/export (112 files, PDFs and XLSX)/verify --outputs/drc/templates/import-parts and rejects a DOCTYPE-bomb xlsx; ci/build.sh runs correctly (rc 0 on a valid project, usage errors rc 2, spaces OK); .desktop keys well formed; build_deb metadata, ownership (root/root) and file list as tested; install.sh refuses an unbuilt tree and non-link files in the bin folder, handles relative prefixes and spaces, PATH note shown; wheel contents match sources except dotfiles; `changes` regex logic correct for new branches (empty before) and mixed changes; version strings agree (pyproject, __init__, CHANGELOG, INSTALL); all 1319 relative Markdown links resolve; release_check --quick labels itself "NOT a release check"; check_vulnerabilities treats "could not run" as exit 2; no secrets/tokens; root .gitignore: no tracked file under data/build/dist/temp.

##### Questions for the owner
G-5 (release_check refuse when version already tagged or Unreleased non-empty?); G-1 (ship pygments/rich etc. with licences, or exclude?); G-7 (cross-machine byte identity of XLSX required? then OPENPYXL_LXML=False); G-13 (.deb "Copyright: ... to be filled in" acceptable with D-02 open?); G-10 (template should match build.sh incl. drc; unwaived DRC errors fail CI?); G-8 (release image install Chromium/poppler, HARNESS_REQUIRE_BROWSER=1, acceptable skip count?).

### Area K: Documentation, help text and messages versus behaviour


Auditor: area K. Worktree `/home/user/wt-audit` (read-only). Scratch: `.../scratchpad/audit/K/`.

##### Files read

Read completely: `harness/docs/CLI.md` (430), `guide/USER_GUIDE.md` (267), `tools/build_guide.py` and the generated `resources/guide/index.html` (31 KB), `RULES.md` (56) with `core/drc/rules.py` (600), `standard_rules.py` (413), `drc/base.py`, `drc/__init__.py`, `checks.py`; `CONFIG.md` (129) with `model/config.py`, `configcheck.py`, `standard_profiles.py`; `OUTPUTS.md` (77); `FILE_FORMAT.md` (89); `IMPORTS.md` (39), `KICAD.md` (51) with `imports.py`, `library_import.py`, `generate/lengths.py`, `kicad.py` (parts); `PLACEHOLDERS.md` (52), `CONCEPTS.md` (156), `CHEATSHEET.md` (97), `GETTING_STARTED.md` (380), `GLOSSARY.md` (261), `TROUBLESHOOTING.md` (659), `SECURITY.md` (31), `FAQ.md`, `HOWTO.md`, `TIPS.md`, `LEARNING_PATH.md`, `INSTALL.md`, `RELEASE.md`, `examples/README.md` (partly), root `README.md` (first 135 lines), `harness/README.md`, `CHANGELOG.md` files, root `CONTRIBUTING.md`, `docs/README.md`, `harness/docs/README.md`, `docs/DOCS_AUDIT.md` (262), all 14 `user-manual/*.md`, `developer/{architecture,setup-and-tests,tools,docs-maintenance,release}.md`, `harness/CLAUDE.md`, `.github/workflows/harness-ci.yml` (partly), `packaging/ubuntu/install.sh`, `uninstall.sh`, `README.txt`, `cli/main.py`, `cli/start.py`, `cli/changes.py`, `cli/data.py`, `tests/test_docs.py` (181). Not read in full: `SPEC.md`, `REQUIREMENTS.md`, `ARCHITECTURE.md`, `UX*.md`, `DECISIONS.md`, `FLATSAT_EXAMPLE.md`, `developer/upstream-sync.md`, the upstream README part, `compliance/` (spot checks only).

##### What I ran

`--help` of the program and all 21 subcommands; regenerated CLI.md from the parser (identical); `new/validate/generate/drc/export/verify` on all five examples (counts, file lists, CSV headers, manifest/export/provenance keys compared with OUTPUTS.md); the whole of GETTING_STARTED (Parts 1 to 9), the KiCad "Try it", import-parts/lengths/ampacity/profile commands, release/revise/diff/log/check flow, naming and title-block examples, segmentation modes on `small-satellite` and `minimal-satellite`, `schema`, `migrate` on the v0 fixture, error scenarios from TROUBLESHOOTING (not a project, folder exists, lock, bad template, bad config shape, fixed-pin missing), 40+ error strings grepped against the source, security claims (symlinked file and outputs folder, manifest listing `../`, 70 MB file, 100,000-deep JSON, values not quoted in messages, SVG well-formedness with hostile names, CSV/XLSX formula prefix), lychee offline check, table-shape and code-span-path checks, version/count greps, a mutation of the tutorial text against `tests/test_docs.py`. I was root, so permission-denied cases could not be tested.

Not covered: GUI behaviour of menus and dialogs (only strings compared), `.deb`/`.tar.gz` installs, KiCad itself, the PDF content, external links, `SPEC.md`/`REQUIREMENTS.md`.

Link check: `lychee --offline --include-fragments '**/*.md'` gives 13 errors, all in `docs/upstream/README.upstream.md` (intentionally excluded copy). No other dead links. Versions: `pyproject.toml`, `__init__.py`, `harness --version`, docs all say 0.1.0 (consistent). Counts verified true: 33 rules (19 + 11 + 3), 21 commands, 17 interface types, 5 examples, 15 template files, 14 schemas, 14 release steps, 28 library parts, 38/137/280 export files for three of the examples.

##### Findings

#### K-1 [high] Removing the `sheet` field (or a typo) in `titleblock.json` makes `harness export` refuse, with a wrong message
- Where: `docs/user-manual/naming-and-title-block.md` ("Remove a field to hide it, or reorder them"), `docs/CONFIG.md:98`; behaviour in `core/outputs/drawing.py:619` and the output verifier.
- What is wrong: the docs promise that any field can be left out. Leaving out `sheet`, or naming a field that does not exist, or listing a field twice, or using non-text entries, makes the independent output check fail, so nothing is written.
- Evidence: for each of the 10 fields removed in turn on `first-steps`, `generate` then `export`: nine export fine; `sheet` gives `error: [out_drawing] The title block of harnesses/W001/drawing_A3_s1.svg shows the wrong sheet number.` Also `["bogus","project"]`, `[1,2]` and `["project","project"]` give `Not written: the outputs failed their independent check.` `harness validate` and `harness config` stay silent about the bad value (only `segmentation.mode` gets a warning at generate time).
- Why it matters: a documented option fails; the message blames the sheet number, not the configuration, so the user cannot find the cause. It fails safe (nothing written).
- Proposed fix (minimal): validate `titleblock.fields` in `configcheck.validate` (known names, no duplicates, text only) and either always show `sheet` or make the verifier skip the sheet check when it is not configured. Say in CONFIG.md which fields are mandatory.
- Test that would have caught it: for each field, export with that field removed and expect success; export with an unknown field name and expect a named configuration error.
- Confidence: confirmed
- Needs owner decision: yes (is `sheet` mandatory, or hideable as documented?)

#### K-2 [medium] XLSX imports read the active sheet, docs say the first sheet
- Where: `core/imports.py:145` (`ws = wb.active`); docs: `IMPORTS.md` ("XLSX files are read from the first sheet"), templates `README.md`, `import-data.md`, `TIPS.md` ("first sheet").
- What is wrong: `wb.active` is the sheet that was active when the workbook was saved, not necessarily the first.
- Evidence: workbook with sheet `first` (length 111) and sheet `second` (length 999), `wb.active = 1`. `harness import-lengths w2 two.xlsx` then the harness JSON shows `"length_m": 0.999`. The preview does not name the sheet.
- Why it matters: silently importing the wrong data (lengths, parts approval) from a multi-sheet workbook; the preview looks normal.
- Proposed fix: read `wb.worksheets[0]` as documented, or document "active sheet" and print the sheet name in the preview.
- Test: two-sheet workbook with the second active; assert the first sheet is read.
- Confidence: confirmed
- Needs owner decision: no

#### K-3 [medium] Any invalid library field is reported as "The library date must be written YYYY-MM-DD"
- Where: `core/library_import.py` `library_ops` (`except ValueError` maps everything to the date message); CLI `harness library`, `import-parts --library-*`.
- Evidence: `harness library lb --library-version ""` and `--library-name <500 x 'x'>` both print `error: The library date must be written YYYY-MM-DD (for example 2026-10-08).` (exit 2), though no date was given.
- Why it matters: misleading, not actionable.
- Proposed fix: only map date errors to that text; otherwise say which field is not acceptable (empty or too long).
- Test: `library --library-version ""` must name the version.
- Confidence: confirmed
- Needs owner decision: no

#### K-4 [medium] `harness generate` piped to a program that closes early is not saved, and the error text is wrong
- Where: `cli/main.py` `_generate` (prints, then saves) and `main` (`except OSError` prints "a file or folder could not be used (Broken pipe)").
- Evidence: `harness generate sb | head -1` on `small-satellite` prints `24 added, ...`, then `error: a file or folder could not be used (Broken pipe).`, exit 2; `harness validate sb` afterwards: `0 harnesses`. Reproduced twice. On a 2-line output (`first-steps`) the save happened (timing dependent).
- Why it matters: the output claims "24 added" but nothing was saved; the message points at files. Scripts using `| head`, `| grep -m1`, `| less` are affected.
- Proposed fix: save first and print afterwards, or ignore `BrokenPipeError` on stdout (and say "output closed"); keep the OSError text only for real file errors.
- Test: run `generate` with stdout closed after the first line and check the project is saved.
- Confidence: confirmed
- Needs owner decision: no

#### K-5 [medium] The "outputs outdated" error carries the wrong explanation (wires do not match)
- Where: `core/drc/__init__.py:46` (every verifier error becomes `verify-mismatch` with one fixed "why"), `core/verify.py:229` (`outputs_outdated`).
- Evidence: after `import-parts` in the tutorial, `harness drc` prints title `The model changed after the harness plans were generated. Generate again before releasing.` with the text `The wires do not match the interfaces they should implement, so the harness would not carry the intended signals. To fix it: regenerate the harnesses, or correct the wiring by hand.` The same happens for any edit after generating, including a rename (also shown in the GUI card; `RULES.md` "Also reported as errors" does not mention the stale case).
- Why it matters: this is the commonest error a newcomer sees; the explanation is false for it and sends the user to look at wiring.
- Proposed fix: give `outputs_outdated` its own rule text (the design changed after the plans were generated; generate again, then export again), and mention it in RULES.md.
- Test: DRC finding for a stale generation must not contain "wires do not match".
- Confidence: confirmed
- Needs owner decision: no

#### K-6 [medium] The in-app guide (index.html) is not identical to USER_GUIDE.md: a table row is broken
- Where: `tools/build_guide.py` (table cells are split with a plain `.split("|")`, so the escaped `\|` splits too); `docs/guide/USER_GUIDE.md` section 10, `import-netlist` row.
- Evidence: generated HTML has `<td>`harness import-netlist ... NAME=SIGNAL\</td><td>FILE]`</td><td>read connector pinouts...` (3 cells, raw backticks). A word-level diff of the Markdown text against the HTML text shows only this row differs (everything else is equal apart from spacing and list numbers). `tests/test_docs.py::test_guide_html_is_up_to_date` compares the HTML to the same converter, so it cannot see it.
- Why it matters: the only document installed with the tool shows a mangled command row. (Same family as the known CLI.md pipe row.)
- Proposed fix: split on unescaped `|` in the converter and unescape `\|`; add a test that no table row has a different cell count from its header.
- Confidence: confirmed
- Needs owner decision: no

#### K-7 [medium] Documentation tests do not compare quoted output, so the docs can drift (and have)
- Where: `tests/test_docs.py` (`_run_document` checks only exit codes; the one text check is the model hash).
- Evidence (mutation): I copied the tree to scratch and changed `GETTING_STARTED.md` to say `99 files written`, `77 warning(s)` and `0 of 99 set`; `pytest tests/test_docs.py tests/test_docs_links.py` still gave `48 passed`. Real drift exists: K-8.
- Proposed fix: compare the quoted output blocks (with hashes masked) with the real output in the tutorial test, and check the counts quoted in `examples/README.md`.
- Confidence: confirmed
- Needs owner decision: no

#### K-8 [low] Flatsat export file count is 112, three places say 111
- Where: `docs/examples/README.md:219` and `:231`, `docs/TROUBLESHOOTING.md:562` ("Outputs re-exported with the released status (111 files)").
- Evidence: `harness export flatsat` prints `112 files written to flatsat/outputs (model 25294117de0d)` (same hash as the docs); a release of W001 prints `(112 files)`. The three other examples match (38, 137, 280).
- Fix: change to 112 (the drawing sheet count changed after the docs were written).
- Confidence: confirmed

#### K-9 [low] CONFIG.md: `max_ambient_temperature_c` is "recorded for reference", but it drives an error-level rule; `emc.classes` is read by nothing
- Where: `CONFIG.md` derating table; `PLACEHOLDERS.md`, `GLOSSARY.md` (EMC class "(`emc.json`)").
- Evidence: `core/drc/standard_rules.py:95` uses it as the input of rule `temperature-margin` (error, not waivable), and `unchecked` names it. `grep '"classes"'` finds only `model/config.py:86`; the EMC rules use `emc_class` on interface types and `conflicting_class_pairs`. `harness config` does not list `max_ambient_temperature_c` as missing and `--apply-profile` never sets it, so a user following the profile gets "Temperature margins were not checked" with no hint in the checklist.
- Fix: describe `max_ambient_temperature_c` as the input of the temperature margin rules; say `emc.classes` is not used and where the class lives (interface type `emc_class`).
- Confidence: confirmed (by reading plus run of `unchecked` text)

#### K-10 [low] "Lock a wire or pin" is presented as a feature, but neither the app nor the CLI can lock
- Where: `FAQ.md` ("To keep a wire or pin choice, **lock** it"), `TIPS.md` ("Lock what you decided"), `CONCEPTS.md`, `GLOSSARY.md` (Locked), `USER_GUIDE.md` section 7; contrast `user-manual/generate-harnesses.md` ("The app does not have a button to lock a wire or a pin").
- Evidence: `gui/strings.py` has only the read-only `Locked` column; the only way is editing `"locked": true` in `physical/harnesses/<ID>.json` by hand.
- Fix: say "by editing the harness file" wherever the feature is offered, or add the control.
- Confidence: confirmed
- Needs owner decision: yes (feature missing or doc wording?)

#### K-11 [low] `import-lengths` reads columns by position; the shipped README and IMPORTS.md say or imply header matching
- Where: templates `README.md` ("Header names are matched by meaning ... Order of columns does not matter", about all the CSV files), `IMPORTS.md` (lengths: "with columns harness ID, segment ID, length"), `cli/data.py` help. Only `TROUBLESHOOTING.md` and `import-data.md` state "by position".
- Evidence: `core/generate/lengths.py` `columns=(0, 1, 2)`; the tool itself prints a hint when every row fails.
- Fix: one sentence in IMPORTS.md and the templates README.
- Confidence: confirmed

#### K-12 [low] Missing netlist file reports "The netlist must be a regular file."
- Where: `core/kicad.py:240`. `harness import-netlist demo nofile.net --unit RW1` gives that text, while `import-lengths`/`import-parts` for a missing file say `The file could not be read (No such file or directory).`
- Fix: distinguish missing from not-regular.
- Confidence: confirmed

#### K-13 [low] CHANGELOG "Unreleased" bullets that are not true
- `harness new --list now sizes its columns to the longest name`: `cli/start.py` prints `f"{t.name:18} ..."`, a fixed width (works only because the longest name has 17 characters).
- "Repository front page: the page of this repository (`docs/README.md`) starts with a section on Harness Design Studio ... The original WireViz documentation follows unchanged": `docs/README.md` is now the documentation index (the DOCS_AUDIT change); the front page is the root `README.md`.
- The other bullets I could test hold (flatsat figures, four lanes, `per_zone_pair`, wire colours, `-P` for the helper process, bounded length cache, export/migrate refusing damaged projects with exit 2, drawing text, D-139 repeatability).
- Confidence: confirmed

#### K-14 [low] Messages and help refer to files that are not installed, and use internal IDs
- `harness import-lengths --help` ("see docs/IMPORTS.md"), `import-netlist --help` ("See docs/KICAD.md"), rule text `unchecked-config` ("see docs/PLACEHOLDERS.md"), templates `README.md` ("docs/CONFIG.md", "docs/IMPORTS.md") all point at repository paths; USER_GUIDE admits that the `docs/` folder is "not installed with the app".
- `harness config` prints `Waiting for an owner decision: ... until D-10 (harness boundary rule) is made.` (decision IDs from a repository log).
- The release blocker `placeholder_config` says "Or release on placeholders with a written reason" but does not name `--accept-placeholders` (the same for `parts_unapproved`/`--accept-unapproved-parts`); the option is only in `--help`.
- Confidence: confirmed

#### K-15 [low] CLI.md (generated) small inaccuracies
- Example `harness diff my-design W001 --from A --to B` fails (`error: W001 has no baseline for revision B.`) in the normal flow (B has no baseline until it is released); the same example was already fixed in LEARNING_PATH.
- The release and revise examples can never succeed on the example projects as given (release is blocked by the placeholder gate; revise needs a released harness), and the page does not say so.
- "Commands that import data accept `--dry-run`" is not true for `config --ampacity-csv`.
- `--unit UNIT` row for `import-lengths` says "(default mm) (default mm)" and hides the choices `{cm,m,mm}`; `project`, `file`, `--dry-run` rows have empty text.
- Confidence: confirmed

#### K-16 [low] Small wording errors
- `CHEATSHEET.md`: `harness check` is described as "fast logical check"; it is validate plus Git merge checks.
- `USER_GUIDE.md` section 8: "drawing (SVG and PDF, A3 and A4)": SVG exists for A3 only (the finding A18 of DOCS_AUDIT was fixed elsewhere but not here).
- `harness verify` before `generate` prints six `signal_missing ... has no wire` errors with no hint to run `harness generate` (CHEATSHEET order is generate first, so only a first-time user is hit).
- Confidence: confirmed

#### K-17 [low] `.harness.lock.takeover` is an undocumented permanent file
- Every locked command (generate, export, import, release...) leaves an empty `.harness.lock.takeover` in the project folder (`core/io/fs.py:153`). `FILE_FORMAT.md` Locking and TROUBLESHOOTING ("`.harness.lock` ... removed when closed") do not mention it. It is in the `.gitignore` the tool writes, so only projects created without that line would show it in Git.
- Confidence: confirmed

#### K-18 [low] Editor settings written by `harness schema` map `library/manifest.json` to two schemas
- `editor-settings.json` has `/library/manifest.json` -> library-info and `/library/*.json` -> parts. VS Code applies both, so the manifest would likely be reported as lacking `parts`. Not tested in VS Code.
- Confidence: uncertain

#### K-19 [low, question] A zero or negative `max_current_a` is accepted
- `harness validate` shows 0 errors for `"max_current_a": -3.0`; the Why record then says `AWG 26 carries 0.72 A derated (factor 0.72) for -3 A` (thinnest wire). With lengths known this would fix AWG 26 as the final gauge for nonsense input. Probably another reviewer's area (model validation); reported because the docs say `harness config` and the rules "check what is set (ranges)".
- Confidence: likely

##### DOCS_AUDIT "fixed" claims I verified as true
A2 (9 connectors), A5 (CHEATSHEET starts from first-steps), A6, A7, A8 (PLACEHOLDERS segmentation text), A9, A10, A11, A12, A14, A16, A17 (provenance.json listed), A19, A20 (naming keys), A22, A25, A26 (template README), A27 (install.sh text), S3, S4 (shortcut tables match `main_window.py`), S5 (menu table matches), S19 (`tools.md` lists all 30 scripts), S20, V1, V3 (DEVIATIONS header and "Fourteen waivers" text), V8 (94 modules, 78 tool requirements, 347/344 explained). Still open as the previous audit said: S15 (pipe row), A28 (gauge wording), A6 (no SHA256SUMS in CI). I did not recheck A3/A4 pictures beyond the drawing stamp (`model 8a25f0c99a86` is in `w001-drawing.png`, correct), A13, A15, A23, A24, S1, S2, S7 to S13.

##### Checked and found fine
- Every `--help` text against CLI.md (identical to the parser); all 21 commands exist and are named in the guide; exit codes 0/1/2 as documented for new/validate/generate/export/verify/release/diff/log/import-*/library/config.
- RULES.md vs registry: ids, severities, waivability, requirement ids (all exist in `compliance/requirements`), texts (generated); the `unchecked-config` logic matches the "silent until numbers exist" statement. Logical rules match `checks.py`.
- CONFIG.md key names, defaults and profile values (0.5, 0.25, 0.75, 30, 50, 0.5, K and L tables, 50 cycles, gap 1) match code; `naming.json` keys and the invalid-template warning; `segmentation.mode` invalid value warning.
- OUTPUTS.md file lists for all five examples, CSV headers, manifest/export/provenance keys, stamps (CSV, YAML, SVG `<desc>`, Markdown comment, XLSX sheets), formula prefix (`'=1+1`, XLSX stored as text), 38/39 file counts.
- FILE_FORMAT.md: file tree, id rules, strict typing (NaN, 1e999, duplicate keys, control characters, extra fields all rejected), changelog and baseline shape, `migrate` and backup folder.
- IMPORTS.md/KICAD.md: header aliases, limits, error texts, "Try it" output word for word, fixed-pin error text, `--unit` missing text, decimal comma note.
- TROUBLESHOOTING.md: all quoted messages found in the source (about 40 strings), the reproducible scenarios gave the same text and exit codes.
- SECURITY.md: no `eval/exec/pickle/subprocess` outside the two named files; symlinked project file ignored with `symlink_ignored`; symlinked `outputs/` refused; manifest paths `../` and absolute not followed; 64 MB limit; deep nesting reported; messages do not quote values; SVG well-formed with hostile names.
- GETTING_STARTED, user-manual `generate-harnesses`, `import-data`, `import-kicad-pinouts`, `naming-and-title-block` (apart from K-1), `release-a-harness`, `change-a-released-harness`, `use-git-and-ci` (`ci/build.sh`), examples README numbers (except K-8): outputs reproduce.
- Versions and counts listed above; lychee clean apart from the intentionally excluded upstream copy; no Markdown table with the wrong number of cells except the known CLI.md row; every `harness/docs` page has an inbound link.
- Glossary spot check (about 35 entries that state tool behaviour: gender, mating, release gate, wire sizing, segmentation, pin gap, service loop, starter signals of heater/I2C/discrete/analog/CAN/SpaceWire/thermistor, Micro-D size rule, categories, unit ID prefixes): accurate except the EMC class entry (K-9).

##### Questions for the owner
1. K-1: is `sheet` meant to be mandatory in the title block, or hideable as the docs say?
2. K-10: should locking a wire or pin be possible in the app or CLI, or should the docs say "edit the file"?
3. A misspelled key inside `values` of a config file is silently ignored (documented in TROUBLESHOOTING/TIPS); `harness config` then shows it as MISSING. Is a "unknown key" warning wanted? (A typo in a derating key leaves checks "not checked", so no wrong result, but easy to miss.)
4. CI (`harness-ci.yml`) only triggers on `harness/**`; a change to root `README.md`, `docs/*.md` or root `CHANGELOG.md` never runs the docs tests or link checks. Intended?
5. K-19: should interface currents be validated as above 0?

##### Summary
Counts: critical 0, high 1, medium 6, low 12 (K-1 to K-19; K-18 and K-19 uncertain or a question).

Five most important: K-1 (title block field removal breaks export with a wrong message), K-5 (stale-outputs error shows a false "wires do not match" explanation), K-2 (XLSX import reads the active, not the first, sheet), K-4 (`generate | head` skips the save with a wrong error), K-7 with K-8 (doc tests do not check quoted output; drift already present, flatsat 111 vs 112).

### Area I: Test-suite quality (mutation checks)


Area: I, test suite quality. Tree: /home/user/wt-audit (branch audit/pre-release, 956ff71). Venv Python 3.13 (project targets 3.12; CI uses 3.12).

##### Files read
All 78 tests/test_*.py files read completely (12,839 lines) plus tests/conftest.py (3), tests/helpers.py (42), tests/gui_helpers.py (68), pyproject.toml pytest/coverage config, .github/workflows/harness-ci.yml, tools/trace.py, tools/gen_output_goldens.py, and the source of the behaviours I mutated (pins, sizing, fs, stamp, commands, release, locks, consistency, verify, drc rules/base/standard_rules/__init__, lengths, cli/data, saver, loader, build, canvas, mass, segmentation, imports, diff, exports). Fixtures: structure and generation commands checked (CLAUDE.md lines 36, 51, 58, tools/gen_output_goldens.py, git log of the fixtures); JSON contents sampled, not read.

##### What I ran
- Single test files from the copy and the original (no full run). The lead's coverage run was used for part 2: 1026 passed, 1 failed (test_stress_generates_fast, 15.1 s against limit 10 s under --cov, load average 9-13), 1 skipped (test_read_only_folder, as root), 11 deselected; core total 95.67 percent (7092 statements, 237 missing lines, 196 missing branches).
- Mutation runner audit/I/mut.py on a COPY (audit/I/h), spec lists specs.py (M01-M75), specs2.py (S01-S20), specs3.py (N01-N14). Each mutation = one textual change, then `pytest -x -q` on 2 to 5 related test files ("focused set", listed in mut_results.jsonl). Results: audit/I/mut_results.jsonl, logs mut_run*.log. 109 mutations: 69 killed, 40 survived. A survivor means survived the focused set. I did NOT re-run survivors against the whole suite (a full run takes 20 min under the current load, and the brief forbids full runs); where I say "no test", I grepped the test files for the behaviour in addition.
- Repro scripts: audit/I/r/fixed1.py, r/dbl.py, r/lockgap.py, r/tautologies.py.

##### Could not cover
- GUI tests and test_prototype.py (needs Chromium; skipped here): read only, not mutated. test_gui_perf.py not run (brief).
- "Lines covered only by a test that asserts nothing about them": no per-test coverage contexts exist in the lead's run. I use the mutation survivors as the evidence for this (a line that is executed but whose change is not detected).
- Survivors not re-checked against the entire suite (see above).

##### Summary table of mutation survivors (diff = exact change; file relative to src/harness_design_studio)
See the findings; full list with diffs is in audit/I/mut_results.jsonl. Survivors:
M04 pins.py `if p.fixed and p.signal and not p.locked:` -> `if p.fixed and p.signal:`
M05 pins.py `used.add(chosen)` -> `pass`
M06 pins.py all-or-nothing `for _sig, pid in picked: used.discard(pid)` block deleted
M10 sizing.py `if drop <= max_drop and math.isfinite(drop):` -> `<`
M13 drc/rules.py `limit < i.max_current_a` -> `limit <= i.max_current_a` (current-over-wire)
M16 drc/rules.py `if drop > limit:` -> `>=`
M17 drc/rules.py `if spare < fraction * len(c.pins):` -> `<=`
M20 drc/__init__.py waiver looked up by object_id instead of finding id (any waiver of an object waives all its findings)
M22 release.py `len(accept_placeholders.strip()) < MIN_COMMENT` -> `<=`
M23 release.py `len(comment.strip()) < MIN_COMMENT` -> `<=`
M31 locks.py `and new.status == "draft"` deleted (released harness replaceable by a non-draft)
M32 locks.py `new.revision != old.revision and` deleted (released harness replaceable by an edit with the same revision)
M33 locks.py `return ap == bp and (a.part_id, a.gender, a.keying) == (...)` -> `return ap == bp`
M34 locks.py COSMETIC_INTERFACE_FIELDS += {"redundancy", "voltage_v"}
M35 locks.py `if old is not None and old != op.obj:` -> `if False:` (release record can be overwritten)
M37 fs.py `_pid_alive` PermissionError branch `return True` -> `return False`
M40 fs.py directory fsync skipped
M41 fs.py `os.chmod(tmp, mode)` deleted
M50 stamp.py '-' removed from the formula-character tuple
M51 stamp.py "\t" and "\r" removed from the tuple
M54 layout.py `digest.update(rel.encode() + b"\0" + data + b"\0")` -> `digest.update(data + b"\0")`
M56 cli/data.py `"cm": 0.01` -> `0.1`
M58 lengths.py `0 <= length` -> `0 < length`
M59 lengths.py `length <= MAX_LENGTH_M` -> `<`
M63 ids.py `or value.endswith(".")` deleted for pin ids
M72 review.py waiver `min_length=10` -> `9`
M73 units.py `AWG_MIN = 0` -> `-1`
M75 (not a mutation) `from ..gui import fonts` added to core/units.py: test_architecture, test_sdd_components and test_offline all pass
S06 verify.py `pin_reused` check disabled
S08 verify.py `signal_duplicated` (elif have > n) disabled
S09 verify.py `wire_extra` loop disabled
S11 verify.py `wire_pin_missing` check disabled
N04 segmentation.py `_esc` without the '%' escape
N05 segmentation.py `forbid_pyro_with_other in (None, True)` -> `is True`
N07 canvas.py PDF string escape without the backslash
N08 imports.py parse_csv cells not stripped (probably equivalent: later stages strip again)
N09 imports.py duplicate interface ID check made case-sensitive
N10 diff.py `_norm` order-insensitive list compare removed
N11 diff.py configuration changes not part of the diff
N14 release.py change-log number `max+1` -> `len+1` (equivalent while log entries cannot be deleted)

Killed (good): pin power-first, locked pins, power gap, gauge order and direction, derating boundary (>= vs >), current-over-contact boundary, voltage-drop path_conductors, bundle K lookup, DRC severity/waivable, error waivers, release gate (already released, stale/tampered outputs, unverified parts, gauge pending, rule-error scope, date, next revision), lock-check removal, host check of the project lock, flock guard, release() not removing the lock, data fsync, temp-file cleanup, backup link-safety, escapes_root, outputs symlink checks, loader symlink/size, CSV '@' and all-off, content_hash, mm factor, ID length/reserved names/trailing dot, import all-or-nothing (lengths and parts), undo/redo/rollback, consistency "second error", all save() protections, mass formulas, SVG '&', service loop 2x, manifest hash, JSON duplicate keys, DOCTYPE refusal, generation freezing of released harnesses, CLI lock.

##### Findings

#### I-1 [high] Fixed-pin allocation: double-booking untested, and a held (locked) pin is ignored on the fixed path (real defect)
- Where: core/generate/pins.py:28-75 (`_allocate_fixed`), :114-116 (fixed path taken before `held` is read); core/generate/engine.py:410-420 (`held` excludes `pin.fixed`); tests: tests/test_audit_generate.py `test_a_new_interface_never_lands_on_unnamed_pins_of_a_fixed_connector`, test_kicad.py.
- What is wrong: (a) No test covers two interfaces competing for the same fixed pin. Mutations M05 (`used.add(chosen)` -> `pass`), M04 (locked fixed pin offered again) and M06 (all-or-nothing per interface removed) all survive the generate/audit_generate/kicad tests. The one test that looks like a double-booking test passes for the wrong reason: with M05 applied `allocate()` puts TX+ of IF-TM-RW1 and of IF-X on pin 4 (audit/I/r/dbl.py output: `('IF-TM-RW1','TX+'): '4' ... ('IF-X','TX+'): '4'`), but the test only asserts "some pin_allocation error for IF-X", and that error comes from the OTHER end (`PCDU-J03 has too few free pins`). (b) Real defect found while writing the repro: when a connector has fixed pins, `allocate()` returns `_allocate_fixed(...)` and never looks at `held`. A hand-locked, non-fixed pin that already carries interface+signal is therefore not reused, and the signal is also placed on its fixed pin.
- Evidence: audit/I/r/fixed1.py (mini3, OBC-J01 pins 1-4 fixed RX-,RX+,TX-,TX+; pin 5 locked by hand with signal TX+ / IF-TM-RW1; then `plan_generation` + apply):
  `B pins: ... ('4','TX+','IF-TM-RW1',True,False), ('5','TX+','IF-TM-RW1',False,True)`
  `B TX+ of IF-TM-RW1 on pins: ['4', '5']`  `B verify ok: True []`  `B drc: []`  `B again plan empty: True`
  The same signal of one interface sits on two box pins; the independent verifier (core/verify.py) and every DRC rule stay silent because they only count wires.
- Why it matters: a wrong pinout that looks right (one signal claimed on two contacts) in exactly the connectors that come from a schematic. Known open item "fixed-pin double-booking untested": confirmed, and (b) is a different, worse instance.
- Proposed fix (minimal): pass `held` into `_allocate_fixed` (treat held pins as used and skip placing that signal), and add a verifier/DRC check "signal of an interface on more than one pin of a box connector".
- Test that would have caught it: (1) fixed connector with two interfaces of one type and a single set of named pins: assert the second gets an error naming THIS connector and that no pin carries two (interface, signal) pairs; (2) the locked-pin scenario above, asserting exactly one pin per (interface, signal); (3) call `allocate()` directly with two requests and assert `len(set(out.pins.values())) == len(out.pins)`.
- Confidence: confirmed (reproduced; mutation survivors M04/M05/M06).
- Needs owner decision: no.

#### I-2 [high] Release locks: tests leave the lock rules unpinned, and two real gaps exist
- Where: core/vcs/locks.py:19-24 (`_is_new_revision`), :27-30 (`_pins_equal`), :36-47 (release record), :14 (COSMETIC_INTERFACE_FIELDS); core/vcs/consistency.py:11-47; core/vcs/snapshot.py:23-35.
- What is wrong (tests): survivors M31 (`and new.status == "draft"` deleted), M32 (`new.revision != old.revision and` deleted), M33 (gender/keying/part of a used box connector no longer compared), M34 ("redundancy" and "voltage_v" made cosmetic), M35 (`if old is not None and old != op.obj:` -> `if False:`; coverage.json: locks.py:45 is never executed). No test replaces a released harness by a non-draft or same-revision copy, changes the gender/part of a used box connector, changes a design field such as redundancy of a carried interface, or tries to overwrite (Put) an existing baseline or change-log entry (only Delete is tested, test_audit_data.py).
- What is wrong (product, found while checking the missing tests): after a release, `History.execute` accepts `Put("interface_types", ...)` and `Put("parts", ...)` (check_locks only knows harnesses, interfaces, connectors), and `release_integrity()` compares only the harness and the carried interfaces, although the baseline stores units and box connectors too.
- Evidence: audit/I/r/lockgap.py on sat15_full after releasing W001:
  `1 interface_types edit ALLOWED after release; release_integrity: [] verify errors: ['wire_extra', 'wire_extra', 'wire_extra']`
  `2 parts edit ALLOWED after release; release_integrity: []`
  `3 box connector part/gender + unit name changed directly; release_integrity: [] | drc released-modified: []`
- Why it matters: "released harnesses are locked": the released drawings/BOM (part data, pin counts, mass) can change silently through the editor; a merge that changes the mating box connector is not reported as released-modified.
- Proposed fix (minimal): add parts and interface_types used by a released harness to check_locks, compare snapshot.units and snapshot.connectors in release_integrity; add the tests listed here.
- Test that would have caught it: one test per mutation M31-M35, plus "edit a part/interface type of a released harness raises TransactionError" and "hand-edited box connector gives released_modified".
- Confidence: confirmed (reproduced; survivors against the focused set test_change_control + test_audit_data).
- Needs owner decision: yes - are parts / interface types / config meant to be frozen by a release or only the harness and the interfaces it carries?

#### I-3 [medium] No test pins any exact limit of a rule or gate (boundary survivors)
- Where / mutation: M10 sizing `drop <= max_drop` -> `<`; M13 DRC current-over-wire `limit < i.max_current_a` -> `<=`; M16 DRC voltage drop `drop > limit` -> `>=`; M17 spare pins `spare < fraction * len` -> `<=`; M22/M23 release reason and comment `< MIN_COMMENT` -> `<=` (a 10-character text is the documented minimum; no test uses exactly 9/10 characters); M72 waiver `min_length=10` -> `9`; M58 length `0 <=` -> `0 <` (zero length refused); M59 length 10000 m exactly refused; M73 `AWG_MIN = -1` accepted. Killed for comparison: derating `>=` vs `>` (test_numerics), contact limit `<` vs `<=`, voltage-drop in rules? no (M16 survives).
- What is wrong: tests have the positive case ("fires on a violation", test_drc.py `test_rule_fires_on_a_violation`) and the clean case, never "exactly at the limit passes / one step over fails". Only the standard rules (tests/test_standard_rules.py) have `..._exactly_at_the_limit_passes` tests. For engineering limits an off-by-equality changes pass/fail of a real design. Also `test_sizing_voltage_drop_can_force_a_larger_wire` (test_generate_parts.py:56) asserts `s.error or (s.awg is not None and s.awg <= 20)`, which accepts "no voltage-drop effect".
- Evidence: audit/I/mut_results.jsonl entries M10 M13 M16 M17 M22 M23 M58 M59 M72 M73 (status survived; exact diffs in the file and in the list above).
- Why it matters: a deration/limit comparison that flips at equality is exactly the "wrong engineering output that looks right".
- Proposed fix: boundary tests (value == limit and limit +/- one unit) for each rule; make the voltage-drop test assert the chosen gauge.
- Confidence: confirmed (mutation). Needs owner decision: no (M58: is a zero-length segment legal? QUESTION below).

#### I-4 [medium] Formula-injection escaping is only partly tested
- Where: core/outputs/stamp.py:33-39; tests/test_security.py:49-80, tests/test_outputs.py `test_csv_cells_that_look_like_formulas_are_marked`.
- What is wrong: M50 (no escaping of a leading '-') and M51 (no escaping of tab / carriage return) survive tests outputs/security/audit_outputs/fuzz. test_security feeds "+cmd|' /C calc'!A0", "-2+3" and "\t..." as names, but asserts only that no CSV LINE starts with '=' or '@' (line start = first column of each row only) and that system.xlsx has no `<f>`. `-` and `+` leading cells in other columns, and the per-harness xlsx files, are never inspected. '@' removal and the "all off" mutation are killed.
- Evidence: mut_results.jsonl M50/M51 survived; test_security.py:75-77 `assert not line.startswith(("=", "@")), rel`.
- Why it matters: CSV injection is a brief-listed risk; a regression in the character set would not fail anything.
- Proposed fix: parse every CSV cell with `parse_csv` raw and assert no cell of any output starts with =,+,-,@,tab,CR unless numeric or prefixed with `'`; apply to all harness xlsx too.
- Confidence: confirmed (mutation). Needs owner decision: no.

#### I-5 [medium] Other untested behaviours (survivors)
- M20: waiver matching by object instead of finding id (any waiver of an object would hide all its waivable findings): no test has two findings on one object with one waiver.
- M54: model hash ignores file names (`digest.update(rel + 0 + data + 0)` -> `digest.update(data + 0)`): moving content between files does not change the hash, nothing checks it.
- M56: `--unit cm` factor (0.01) never used by any test (only mm and m).
- M63: pin ID with a trailing dot accepted (`or value.endswith(".")` deleted).
- N04: segmentation key `_esc` without '%' escaping (zone `a%7Cb` collides with `a|b`); the test only uses '|'.
- N05: pyro-isolation default (`forbid_pyro_with_other in (None, True)` -> `is True`): the default is untested.
- N07: PDF text escaping without backslash (text with `\` would break the PDF string); only '(' and ')' are asserted (test_outputs.py:`test_pdf_and_svg_escape_special_characters` includes `\\` in the input but asserts only `\\(c\\)`).
- N09: interface import duplicate-ID check case-sensitive; N10: diff list compare order-dependent; N11: configuration changes missing from `diff`/revision report (flatten_project drops `config`).
- N14 (equivalent while the log cannot be deleted) and N08 (probably equivalent) are listed in the survivors table for completeness.
- Confidence: confirmed (mutation). Needs owner decision: no.

#### I-6 [medium] Verifier mutation tests do not say which check fires
- Where: tests/test_generate.py:175-212 (`codes(p)` then `assert codes(p)`): test_verifier_detects_missing_wire / swapped_pins / duplicate_wire / missing_end_connector only assert that the set of error codes is non-empty. core/verify.py:
- Evidence: S06 (`pin_reused` check disabled), S08 (`signal_duplicated`), S09 (`wire_extra` loop), S11 (`wire_pin_missing`) all survive generate/generate_parts/audit_generate/drc; killed: signal_missing, outputs_outdated.
- Why it matters: the "independent verifier" is the main correctness argument for generation; four of its checks could be deleted unnoticed. (The same holds for the pin double use on boxes, see I-1.)
- Proposed fix: assert the specific code per test (`assert "pin_reused" in codes(p)`), one mutation test per code.
- Confidence: confirmed. Needs owner decision: no.

#### I-7 [medium] Static guards have blind spots
- test_architecture.py `_imports()` records `node.module` only; `from ..gui import fonts` inside core is `module="gui"`, level 2, and passes. Mutation M75 (that line added to core/units.py): test_architecture, test_sdd_components (dependency column) and test_offline all pass. Fix: use `node.level` to resolve relative imports.
- test_offline.py:`test_no_network_imports_in_source` and test_security.py:`test_the_code_never_evaluates_data_or_starts_programs` scan import statements and a few call names only. `importlib.import_module("socket")`, `__import__`, `webbrowser`, `QDesktopServices.openUrl` (used by the Help menu), `os.exec*`/`os.spawn*` are not covered.
- test_offline.py:`test_runtime_sockets_blocked_cli_and_gui` runs `python -I`, which ignores PYTHONPATH, so it imports whichever harness_design_studio is installed: in this environment `python -I -c "import harness_design_studio"` prints `/home/user/wt-name/harness/src/...` (another worktree), not the tree under test. Fine in CI only because of `pip install -e` of the same tree.
- Confidence: confirmed. Needs owner decision: no.

#### I-8 [medium] Vacuous, tautological or crash-only assertions (all read; line numbers in this tree)
- tests/test_recovery_journal.py:53-54 `assert read_journal(root) is None or read_journal(root) is not None` and `assert journal_differs_from_disk(root) in (True, False)` always true (only "does not raise" is tested; the coordinator quoted line 247, it is 53-54 here). The same behaviour is asserted properly in test_security.py:`test_a_damaged_journal_is_ignored`.
- tests/test_security.py:187 `assert str(f).startswith(str(tmp_path))` for f in tmp_path.rglob(...) is always true; the test cannot see a write outside the project (S01, a stray file next to the project, was killed only by other tests).
- tests/test_fuzz.py:245 `assert EXAMPLES >= 1 and io.StringIO is not None` (constant; "documents the long run").
- tests/test_drc.py:613-614 `assert copy(p) is not p` / `isinstance(Connector, type)...` import keepers inside the stress test.
- tests/test_audit_data.py:148 `assert loaded.has_errors or loaded.project.quarantine or loaded.issues` - `loaded.issues` is truthy for a clean project (it holds the info issue `placeholder_config`; audit/I/r/tautologies.py: `clean project: ... issues=[('info','placeholder_config')]`).
- tests/test_gui_journeys.py:819 `win.ctl.root is None or win.ctl.root != tmp_path / "x"` (always true); :811 `{"OBC","PCDU"} <= units or len(units) >= 3`; tests/test_gui_changes.py:107 `"locked" in ... or "released" in ...`; tests/test_gui_generate.py:105 `assert QDialog is not None`; tests/test_gui_outputs.py:106-113 `frame_count` counter asserted == 1 (the test's real check is "no exception in the event loop").
- tests/test_audit_data.py:87 `test_mini3_is_untouched` (`assert mini3().units`), tests/test_integrity.py:216 `test_part_object_unused`, tests/test_edit.py:311 `test_harness_object_import_is_used` and :343 `assert sizes`: no behaviour.
- Disjunctions that accept both outcomes: test_generate_parts.py:56 and :95 (`... or r.missing`); test_numerics.py:75 (`"2.7 A derated (factor 0.54)" in x or "carries 2.7 A" in x`); test_routing.py:175 (`a < b < c or a <= b <= c` is just `<=`); test_integrity.py:213 `len({...}) >= 14` (not tied to the codes in integrity.py; all 15 codes are in fact tested); test_security.py:96-102 (`file_too_large` or `invalid_json` or has_errors); test_outputs.py `test_detects_drawing_problems` (`out_missing` or `out_drawing`); test_recovery.py `test_dangling_reference_after_load` (two codes).
- No-assertion tests (only "does not raise"): test_atomic_lock.py:129 `test_stale_lock_is_taken_over` and :135 `test_corrupt_lock_is_stale` (never check the lock file now holds the new pid), test_drc.py:626 `test_regression_lookalike_rule_copes_with_mixed_keying`, test_fuzz.py (4 crash-only hypothesis tests), test_kicad.py random-damage test, test_audit_cli.py `test_dry_runs_do_not_take_the_lock_or_write` compares file NAMES only (a dry run that rewrote a file would pass) and `assert rc in (0, 1)`.
- Over-broad raises: `pytest.raises(Exception, match=...)` at test_checks.py:108, test_edit.py:232, test_fuzz.py:163 (all with a message match; acceptable but should name the exception). `except Exception as exc: assert type(exc).__name__ == "LoadError"` in test_fuzz.py:157 is fine.
- Permanent skip: test_security.py:49 `pytest.skip(...)` in `test_hostile_text_in_names_is_harmless_in_every_output` is hit for 2 of 15 parametrisations in every environment ("line\nbreak", "tab\there").
- Confidence: confirmed (read). Needs owner decision: no.

#### I-9 [medium] The traceability gate checks that a requirement ID is mentioned, not that it is verified
- Where: tools/trace.py:42-60, tests/test_trace.py. Status `traced` = the ID string occurs anywhere in a tests/*.py file (docstring or comment is enough); `verified-by-file-only` = docs/REQUIREMENTS.md names a tests/ or tools/ file that exists. Current numbers (computed): 78 requirements, 47 traced, 30 verified-by-file-only, 1 review-only. REQ-CC-01..07, REQ-DRC-01..04, REQ-OUT-01..05, REQ-GEN-02/03 are in the 30 (no test names them). test_trace.py accepts all three statuses.
- Why it matters: compliance/traceability.csv is part of the deliverable records; it reads as test evidence. Confidence: confirmed. Needs owner decision: yes - accept as documented, or rename statuses ("mentioned", "file named")?

#### I-10 [medium] Goldens: what proves them correct
| Golden | Produced by | Independent check |
|---|---|---|
| tests/fixtures/projects/mini3 (27 files) | `save_project(mini3())` (CLAUDE.md:36); CLAUDE.md:51 calls it "hand-made, not generated" - contradiction | none for the format itself (test_io compares builder output with it and checks load/save round trip; schemas test checks key subsets only). Loader tests use it as input. |
| tests/fixtures/projects/sat15 (57 files, 772 KB) | `generate_project(sat15())` + save | verify_project is an independent implementation but is run on the in-memory result, not on the fixture; byte compare only. Gauge, adjacency and pin order are only covered by the specific generator tests. |
| tests/fixtures/outputs/{mini3,sat15,sat15_full}.json (38/280/280 SHA-256 digests) | tools/gen_output_goldens.py | verify_outputs (separate parser, re-derives values from the model) runs on the same files (test_outputs `test_verifier_is_clean_on_the_reference_projects`): good for tables; drawings (SVG/PDF) are checked only for text content, title block, pagination and (with poppler) page size. The stamp contains the tool version, so every version bump regenerates all digests (git log: "fixtures, goldens ... regenerated" in each rc and in the 0.1.0 commit) - they detect change, not error. |
| tests/fixtures/outputs/mini3/* (29 readable files) | same | reviewable by a human, no machine check beyond the verifier |
| tests/fixtures/drc/sat15.md | `harness drc` CLI | rule positive/negative tests; the report as a whole is a snapshot |
| resources/examples/projects, compliance/*.csv, docs/guide HTML, rule docs, CLI docs, prototype/index.html | tools/build_examples, build_compliance_matrix, gen_sdd_components, trace, build_guide, gen_rule_docs, gen_cli_docs, build_prototype | `*_is_current` tests prove "regenerated", not "right"; the examples are additionally exercised by CLI flows that only check exit codes. test_docs also runs README/GETTING_STARTED commands and compares the quoted model hash (good). |
| v0_project, m1_project, kicad fixtures | hand-made (independent) | used as migration/import inputs - these are the only independent goldens |
Confidence: confirmed (read + git log). Needs owner decision: no.

#### I-11 [medium] Coverage gate scope and the uncovered core code that matters
- pyproject `[tool.coverage.run] source = ["harness_design_studio.core"]` and `fail_under = 90`: the gate measures 12.7k of 21.2k source lines. gui (7,450 lines) and cli (1,019 lines: import commands, UNITS, release CLI, lock) are not measured; cli/data.py holds the cm/mm conversion that M56 shows is untested.
- Lead's run: core 95.67 percent, branches 93.3 percent. Uncovered code worth a test (file:lines, what is missing):
  - core/io/fs.py:111-112 (escapes_root error), 120-125 (_fsync_dir failure), 137-138 (_pid_alive PermissionError: only reachable as non-root), 156-157, 171, 173 (lock guard open failure, FileExistsError race, OSError on create): tests for a lock folder that is read-only, a guard file that is a symlink (O_NOFOLLOW), and the race.
  - core/vcs/locks.py:45 (Put over an existing baseline/change-log entry), :68, :89 (see I-2).
  - core/drc/rules.py:59, 63 (duplicate wire id / duplicate pin in a connector), 74 (wire to missing pin), 124, 133, 139 (mate-mismatch: pin-count and keying differences), 348/359 (chains-mixed on one connector), 364/386 (pyro rule), standard_rules.py:218, 223, 286.
  - core/verify.py:96, 104 (wire end / mate_missing), 144-149 (wrong_endpoint / pinout_mismatch) - the verifier's own error paths (see I-6).
  - core/generate/pins.py:152-163 (relaxed adjacency fallback), engine.py:223, 283, 440, 541, 547, 612, 750, 792, 839-840 (sizing error, contact check, shield kinds), naming.py:27-32, 63-64 (bad naming template), segmentation.py:97-113 (skipped interfaces), sizing.py:41-45, lengths none.
  - core/io/loader.py:91-93, 137-138, 262, 347-348 (unreadable file, duplicate baseline), saver.py:111, 114 (stale file behind a link), 150.
  - core/imports.py:57-58, 113, 119-120, 141-162 (invalid CSV, unreadable file, xlsx limits), core/kicad.py:93, 96, 134-135, 178-179, 219, 243, 246, 325, 439, core/outputs/build.py:214-215, 257, 275, verify.py:243, 341, 387-399, 475, 492, 522-537, 558, 591, 652 (output verifier error branches), recovery.py:94-95 (corrupt journal fields), edit.py:296, 414, 534, 728, 797-803, 815-817, 836-845 (rejected edits), templates.py:66, 79, 93.
  - core/drc/worker.py:84-120 (`main`) is run in a child process and so is invisible to in-process coverage (tests exist: test_drc_process.py); measure with subprocess coverage or accept.
- Lines executed but not asserted (from mutation survivors): pins.py:55 (used.add), :34 (not p.locked), locks.py:24, :28, :45, :14, fs.py:97, :99-104 (chmod, dir fsync), stamp.py:35, layout.py:110, lengths.py:116, ids.py:32, units.py:5, drc/rules.py:257, :272 (voltage drop), :296, sizing.py:97 (drop <=), verify.py (pin_reused, signal_duplicated, wire_extra, wire_pin_missing), diff.py:148 (config) and :147.
- Confidence: confirmed. Needs owner decision: no.

#### I-12 [medium] Skips, environment dependence and flakiness
- Root: test_atomic_lock.py:59 `test_read_only_folder` is skipped when euid==0 (this sandbox and any root container). It is the only test of "save into a read-only folder raises SaveError"; also `_pid_alive` PermissionError (M37) cannot be reached as root. GitHub's runner is non-root, so CI runs them.
- Missing optional pieces skip silently: GUI modules (`importorskip("PySide6")`), `pdfinfo` (poppler; test_outputs.py:136), `dpkg-deb` (test_installers.py:93, :238), common-licenses (test_installers.py:264), test_prototype.py (`importorskip("playwright")` precedes the HARNESS_REQUIRE_BROWSER guard, so a missing playwright package skips even in CI mode; only a missing Chromium is turned into an error). test_m8.py:143 has a MODULE-level `importorskip` after 8 headless tests (sketch layout, arrange), which are skipped with it; test_audit_gui.py, test_gui_generate.py, test_gui_journeys.py and test_gui_readability.py import PySide6 BEFORE `importorskip`, so they error instead of skipping.
- Real user settings: test_gui_smoke.py:`test_window_opens` and the GUI half of test_offline.py call `create_window()` -> `make_settings()` -> `~/.config/HarnessDesigner/HarnessDesigner.ini`. After the lead's run that file exists here (`[ui] geometry=@ByteArray(...)`); `first_run` (tour) depends on `tour/done` in the developer's real file, and the tests write there on close.
- Locale: test_docs_links.py and test_docs.py use `read_text()` without encoding; with `LC_ALL=C PYTHONCOERCECLOCALE=0 PYTHONUTF8=0` `test_links_resolve[README.md]` fails with UnicodeDecodeError; test_io.py `test_unicode_survives` fails with UnicodeEncodeError on the path. CI (UTF-8) is unaffected. The product code passed my 11-file subset under that locale.
- Randomness: hypothesis tests (test_fuzz.py with 40 examples, test_generate.py, test_change_control.py, test_kicad.py) are not `derandomize=True` and no seed is pinned, so a gate run can fail on an input that the previous run did not see (reproducible only through the printed blob). The `.hypothesis` database is created in harness/ (gitignored).
- Timing: wall-clock limits in test_generate.py (stress 10 s), test_drc.py (5 s), test_m8.py (2 s), test_fuzz.py (zip bomb 5 s), test_drc_process.py (50 ms best of 3), test_gui_perf.py. In the lead's run test_stress_generates_fast failed (15.1 s > 10 s) because the run was under --cov at load 9-13; CI runs `pytest --cov` too but with HARNESS_TIME_FACTOR=3. The factor also means that the documented editor limits (e.g. selection 150 ms) are only enforced at 450 ms, so the known 190-250 ms regression passes.
- `filterwarnings = error`: every library deprecation warning fails a test; the venv is Python 3.13 and passed (1 timing failure only); no test hides warnings except test_fuzz.py (HypothesisWarning ignored).
- Shared global state: test_change_control.py `_BASE`, test_drc.py `_BASE`, test_outputs.py `_CACHE` are module caches copied with `edit.clone_with` (shallow copy: `quarantine`, `quarantine_files`, `library_info`, `generation` objects are shared; harmless today because no test mutates them in place). test_audit_generate.py installs a SIGALRM handler and never restores it (alarm cancelled). `drc_process._shared` is a process-wide helper closed by several tests.
- Confidence: confirmed (commands above). Needs owner decision: no.

#### I-13 [low] Documentation mismatch about the mini3 golden
- CLAUDE.md:36 says regenerate mini3 with `save_project(mini3(), ...)`; CLAUDE.md:51 says mini3 is "hand-made, not generated". test_io.py `test_golden_mini3_matches_committed_fixture` proves it is generated. Fix the sentence. Confidence: confirmed.

##### Checked and found fine
- All 78 test files collect and the lead's run passes (1026), so no hidden collection errors; 1 skip only.
- Strong tests (mutations killed): pin power-first/locked/gap, gauge ordering and direction, derating equality, contact boundary, release gate (already released, stale, tampered or subset outputs, unverified parts, date, comment), lock removal, other-host lock, flock guard, lock release, data fsync, tmp cleanup, backup-link safety, path-escape and symlink checks (save, export, load), CSV '@'/all, content hash, mm conversion, ID length/reserved/dot, import all-or-nothing (CLI lengths and parts), undo/redo/rollback, consistency "second error", save protections (recovered, fingerprint, inconsistent, removed objects kept as .bak), mass formulas, SVG escaping, service-loop doubling, manifest hash check, strict JSON, DOCTYPE refusal, frozen released harnesses, CLI lock.
- Integrity: every error code in core/integrity.py has a positive test.
- test_security / test_audit_cli symlink and fifo tests actually assert that nothing outside the project changes.
- Tests use fixed dates (WHEN) and `ctl.today`; no uncontrolled `sleep`/clock except the timing tests above; GUI tests use tmp ini files.

##### Questions for the owner
1. Should a release freeze parts, interface types and configuration used by the harness (I-2), or only the harness and its carried interfaces?
2. Is a zero-length segment (M58) legal, and should 10,000 m exactly be accepted (M59)?
3. Is `verified-by-file-only` meant to count as verified in traceability.csv (I-9)?
4. Should CLI and GUI be part of the 90 percent coverage gate (I-11)?
5. Should hypothesis runs in the release gate be derandomized?

##### Summary
Counts: critical 0, high 2 (I-1, I-2), medium 10 (I-3 to I-12), low 1 (I-13). Mutation: 109 mutations, 69 killed, 40 survived (28 in pass 1, 4 in pass 2, 8 in pass 3; two or three survivors are equivalent or probably equivalent).
Top five: (1) I-1 fixed-pin path ignores held pins, signal on two pins, verifier silent, and double-booking untested; (2) I-2 lock rules unpinned and parts/interface types editable after release, release_integrity ignores stored units/connectors; (3) I-3 no boundary tests for rules/gates; (4) I-6 verifier checks deletable (pin_reused, signal_duplicated, wire_extra, wire_pin_missing); (5) I-8/I-9/I-10 vacuous assertions, text-mention traceability and regenerated goldens.

### Area H: Upstream WireViz code in this fork (not Harness Design Studio)

(Saved by the lead from the reviewer's hand-back. 23 findings: 0 critical, 9 high, 9 medium, 5 low. ALL are in upstream code unless marked fork; the owner decides whether upstream code in this fork is changed at all. Scratch: audit/H/ (bad.py, t1..t16.py, inj/, cli/, pk/). graphviz was installed system-wide with apt in this container (dot 2.42.2).)
Files read completely: src/wireviz/*.py (12), setup.py, requirements.txt, pyproject.toml, docs/syntax.md, advanced_image_usage.md, buildscript.md, CONTRIBUTING.md, CHANGELOG.md, .github/workflows/main.yml, examples/*.yml (16), tutorial/*.yml (8) and .md.
Ran: all 24 example/tutorial YAMLs with `-f ghpst` (all succeed; .gv and .bom.tsv match committed except ex08.gv, H-19; .svg/.html differ only by Graphviz version), build_examples.py on a copy (readme.md files identical), ~100 bad-input cases, vermin (min Python 3.7, no walrus/removeprefix/list[str]/f-string =), sdist and wheel build.

#### H-1 [high] Generating PNG can overwrite and delete an existing file, including the input YAML
- Harness.py:672-684 (`graph.render(filename=filename, cleanup=True)` for png); name from wv_cli.py:125-126, wireviz.py:99-100. Graphviz render() writes the DOT source to `<outdir>/<name>` (no extension), runs dot, then deletes it. Evidence: extension-less YAML `harness`: `wv.sh -f p harness` -> only harness.png and harness.orig remain, input gone. `a.yml` next to directory `a/`: IsADirectoryError, and the default `-f hpst` run leaves a.tmp.svg behind.
- Fix: render with filename=f"{filename}.gv" or a temp dir; refuse output names equal to the input path. Confidence: confirmed.

#### H-2 [high] Same connector at both ends of a cable, addressed by pin labels, is wired wrongly
- Harness.py:109-129 (lines 124-127 `if name == from_name: from_pin = pin` / `if name == to_name: to_pin = pin`). Evidence (t1.py): X1 {pincount 2, pinlabels [A,B]}, connections X1: A, W1: 1, X1: B -> Connection(from_pin=2, ..., to_pin=2). Numeric pins work. A wrong wire that looks correct (A to B becomes B to B).
- Fix: map the two ends independently (index 0 and 1). Test: one connector at both ends with labels, assert from_pin != to_pin.

#### H-3 [high] Connector `loops` use the pin ID as the Graphviz port number
- Harness.py:282-287 (`f"{connector.name}:p{loop[0]}{loop_side}"`); ports are named by position p{index+1} (233, 250); correct lookup for cables at 473-475. Evidence (t2.py): pins [A,B,C] loops [[A,B]] -> `port pAl unrecognized`; pins [5,6,7] loops [[5,6]] -> `port p5l unrecognized`; by reading, pins [2,3,1] loops [[2,3]] draws between positions 2 and 3. Fix: `connector.pins.index(pin)+1`.

#### H-4 [high] No escaping of &, <, > in text fields: render fails, and the &amp; workaround pollutes the TSV
- Harness.py:195-251, 311-360; wv_bom.py:273-275, 278-286; wv_gv_html.py:73, 89. Evidence (inj/probe.py): pinlabel "A&B" rc=1 "not well-formed"; "a<b" rc=1; wirelabel "x&y", type "A & B", manufacturer "Smith & Co", notes "R & D", image caption "A & B": all rc=1; "a&amp;b" rc=0; CLI prints raw CalledProcessError traceback and leaves a.tmp. With the workaround, b.bom.tsv shows `A&amp;B`. Fix: html.escape plain-text fields while keeping the documented <a> links, or document the &amp; rule; convert Graphviz errors into a readable message. Owner decision: YES (which fields accept HTML).

#### H-5 [high] YAML 1.1 scalars turn labels into booleans or numbers silently; undocumented
- wireviz.py:430 (yaml.safe_load), Harness.py:234 (`if pinlabel:`), syntax.md. Unquoted NO, ON, OFF, Yes -> booleans; 007 -> 7; 1:30 -> 90. Evidence (t12.py): pinlabels [COM, NO, NC, ON, OFF, Yes, y, n, 007, 1:30, 1e3] loads as ['COM', False, 'NC', True, False, True, 'y', 'n', 7, 90, '1e3']; graph cells: COM, NC, True, True, y, n, 7, 90, 1e3 (NO and OFF vanish). Relay labels NO/NC/COM/ON/OFF are common. Fix: document "quote labels", warn/reject non-string labels, or YAML 1.2 loader.

#### H-6 [high] TELALT colour code: first five pairs have a one-colour ring (table typo)
- wv_colors.py:30-36: row 1 is "WHBU","BU","WHOG","OG","WHGN","GN","WHBN","BN","WHSL","SL"; every other row and TEL use two-colour rings (BUWH...). Evidence (t6.py): ALT ring == TEL ring mismatches at (0,'BU','BUWH'), (1,'OG','OGWH'), (2,'GN','GNWH'), (3,'BN','BNWH'), (4,'SL','SLWH'). Fix: "WHBU","BUWH","WHOG","OGWH","WHGN","GNWH","WHBN","BNWH","WHSL","SLWH". Owner decision: no.

#### H-7 [high] parse(output_formats="png") (a string) writes nothing or crashes although documented as allowed
- wireviz.py:63-66 (docstring), Harness.py:676-707 (`for f in fmt`, `"svg" in fmt`). Evidence (api/t.py): "png" writes no file and no error; "tsv" works by accident; "html" raises FileNotFoundError out.tmp.svg; ("png",) works; return_types="gv" ignored. Fix: `if isinstance(output_formats, str): output_formats = (output_formats,)`.

#### H-8 [high] parse() keeps state in a mutable default, mutates its input, and rejects Path/str for image_paths
- wireviz.py:33 (`image_paths = []`), 102-106, 154-158, 259, 266-270. Evidence (t4.py): default after two parses = [PosixPath(a), PosixPath(b)]; `image_paths=Path` -> TypeError 'PosixPath' not iterable; `str` -> AttributeError; a dict input is mutated and a second parse fails "unhashable type: 'dict'". Fix: image_paths=None, deepcopy dict input.

#### H-9 [high] Cable wire numbers are not validated: wire 0 takes the last wire's colour silently; wire above wirecount fails late; `s` on an unshielded cable accepted
- Harness.py:131-158 (connect() doesn't check via_wire), 453-457 (`cable.colors[connection.via_port - 1]`). Evidence (bad.py, t2.py): W1: [0,2,3] loads, colour from colors[-1], edge to non-existent port w0; W1: [1,2,4] on 3-wire cable -> IndexError at graph time with no component name; W1: s on unshielded cable accepted (port ws); same wire used twice [1,1] accepted. Fix: raise "{cable}: wire {n} not found" for ints outside 1..wirecount and `s` without shield. Owner decision: YES (double use of a wire: warn or error?).

#### H-10 [medium] Arrow (mate) pins are not mapped from labels or checked
- Harness.py:88-91 (add_mate_pin), 552, 557 (.pins.index), wireviz.py:357-360; syntax.md:199 says a <pin> may be a label. Evidence (t13.py): mating X1: [TX, RX] with --> -> ValueError 'TX' is not in list; X1: [1,9] -> ValueError 9 is not in list. Fix: reuse connect()'s label mapping and "not found" check.

#### H-11 [medium] Wrong top-level structure silently ignored; duplicate keys silently dropped
- wireviz.py:134-158, 430. Evidence (bad.py, t14.py): `connections: {a: b}` or `connectors: [X1]` -> "OK -> 0 conn 0 cables" exit 0; two X1 entries under connectors -> first dropped; name in both connectors and cables -> cable dropped. Fix: raise on wrong section type; loader rejecting duplicate keys; reject a name in both sections.

#### H-12 [medium] `--prepend` silently loses sections when both files have the same top-level key
- wv_cli.py:105-136 (text concatenation), wireviz.py:430; -p not described in README/syntax.md. Evidence: pre.yml (options + connectors X1) + main.yml (connectors X2): second `connectors:` replaces the first; "Exception: X1 is an unknown template/designator/arrow." Fix: merge parsed dicts per section or document.

#### H-13 [medium] Templates are searched next to the output, but documented as next to the YAML
- wv_html.py:26-31 uses Path(filename).parent (output folder); templates/README.md:14-17 says same folder as the YAML. Evidence: `-o out_tp` fails "mytpl.html was not found" and leaves tp.tmp.svg. Fix: pass the YAML folder to generate_html_output.

#### H-14 [medium] HTML and SVG output contain unescaped user text, including attribute injection
- wv_html.py:54-64 (BOM cells), 79-92, 106-116 (metadata, fontname, bgcolor, filename), templates/simple.html:21. Evidence: inj/b.yml -> b.html has `<script>alert('title')</script>` in <title>, <h1>, `<img src=x onerror=...>` and a BOM `<script>`; inj/d.yml fontname `arial" onmouseover="alert(1)` -> `<body style="font-family:arial" onmouseover="alert(1);...">` and in the SVG. Fix: html.escape BOM cells and attribute values; keep documented hyperlink/<br> handling. Owner decision: YES (are metadata fields meant to hold HTML?).

#### H-15 [medium] Bad types crash with unhelpful exceptions (no component name or key)
- Harness.py:305-308, 487-491, 357-359; wv_colors.py:133-141, 171; DataClasses.py:282-291, 326-339; wireviz.py:114-118, 138-147. Evidence (bad.py, t7.py): show_equiv: true without gauge -> AttributeError NoneType upper; pinlabels [10,20] -> TypeError sequence item expected str; colors [1,2] -> TypeError len; color: 5; colors ['#ff0000:'] -> IndexError at graph time; wirecount -2 -> IndexError; '3' -> TypeError; empty body `X1:` -> AttributeError; empty options/metadata/tweak -> TypeError ** NoneType; int designator; empty/number connection set; image: foo.png -> AttributeError; image {caption} -> KeyError 'src'; unknown option/attribute -> TypeError unexpected keyword; bad additional_bom_items fail at BOM time. Fix: validate dataclass inputs in one place with component + key in the message.

#### H-16 [medium] AWG/mm2 conversion table: inconsistent and number-format sensitive
- wv_helper.py:7-34; used Harness.py:305-308. String lookup with 16 entries; 17, 19, 23 AWG etc. "Unknown"; lookup uses str(value) so 1.0, 0.250 mm2, 24.0 AWG -> Unknown while 1 and 0.25 work; 0.75 mm2 -> 20 AWG (20 AWG is 0.52 mm2); 20 AWG -> 0.75 mm2 (45% above); 21 AWG -> 0.5 mm2 (21 AWG = 0.41 mm2); 50 mm2 -> 1 AWG (1 AWG = 42.4); 25 mm2 -> 4 AWG (21.2). Fix: normalise numbers, label as nearest standard size or remove. Owner decision: YES. Confidence: likely (values vs AWG areas).

#### H-17 [medium] Non-UTF-8 locale (e.g. Windows cp1252) crashes SVG/HTML output and leaves temp files
- svgembed.py:62-64 (read_text/write_text without encoding; TODO in code). Evidence: `LC_ALL=C PYTHONUTF8=0 ... wireviz ü-ünï.yml` -> UnicodeDecodeError ascii codec; leaves .png and .tmp.svg. Fix: encoding="utf-8".

#### H-18 [medium] Packaging (fork): description is the docs index; unreliable file read; no python_requires; same name and version as upstream
- setup.py:10, 20 (README_PATH = docs/README.md; open(README_PATH).read()), 34-45, requirements.txt. Evidence: `python -m build --sdist --wheel .` works; wheel METADATA description starts "# Documentation index" ("This repository holds two tools: Harness Design Studio ...") with broken-on-PyPI relative links. open() has no encoding and never closes; docs/README.md contains "…" (line 117): `PYTHONUTF8=0 LC_ALL=C python3 -c "open('docs/README.md').read()"` -> UnicodeDecodeError. Classifiers list only 3.7 and 3.8, no python_requires; CI tests 3.7-3.12; build warns License classifiers deprecated. Distribution still named wireviz 0.4.1 (same as upstream on PyPI); README says `pip3 install wireviz`, which installs upstream not this fork. Fix: README_PATH -> docs/upstream/README.upstream.md (or root README), Path.read_text(encoding="utf-8"), python_requires, consider distinct name/version. Owner decision: YES. (Regression from the docs PR #39: the lead's.)

#### H-19 [low] Documentation and data inconsistencies
- Upstream README lists WT and OR ("DIN ... WT/BN/GN", "IEC ... OR ... WT") but code/syntax.md use WH and OG; docs/syntax.md:516 IEC 60757 link to the resistor colour-band article and "ROY G BIV" (code list BN RD OG YE GN BU VT GY WH BK); docs/syntax.md:480-518 swatches load from via.placeholder.com (external; not checked); tutorial/tutorial06.md says ferrules need `category: ferrule` but tutorial06.yml uses `style: simple`; Connector.category (DataClasses.py:150) never read and not in syntax.md; docs/syntax.md:411 subtype "only shown in bom" but with mini_bom_mode false it shows in the diagram (wv_bom.py:60-63); typo "connectioin" syntax.md:235; docs/upstream/README.upstream.md (intentionally untouched copy) has 14 relative links broken from its folder; the agent also reports docs/DOCS_AUDIT.md has 7 broken relative links (lead: likely code-span text in the section-6 table, lychee reports none: to verify); examples/ex08.gv contains developer path /Users/daniel/Projects/WireViz/examples/resources/... twice (regeneration changes the file).

#### H-20 [low] Cosmetic or consistency bugs in output
- Diagram shows `0.30000000000000004 g x #2 (crimp)` for qty 0.1 x pincount 3 (wv_bom.py:265) while BOM is rounded; BOM designators sorted as text C1, C10, C2 (wv_bom.py:210); cable without length gives BOM line `0 | m`; negative length/gauge/pincount accepted; pincount 2 with pins [1,2,3] accepted; multi-colour/hex pincolors shown as empty cell (Harness.py:237-247) though syntax.md:71 says list of colors; get_color_hex accepts 3-digit hex, Graphviz warns; translate_color("#fff","full") raises ValueError; Designator "Case insensitive unique name" (DataClasses.py:18) but x1 and X1 are two connectors; designators containing ":" make dot fail; parse() with mistyped path string treated as YAML; expand("1-20000000") 9 s and 780 MB; wv_helper.py:60 bare except.

#### H-21 [low] Dead code and latent errors
- Harness.py:371 wv_colors.default_color does not exist (module defines color_default); Harness.py:672-674 svg_already_exists computed never used; Image.fixedsize can be None/0/int; no test for any upstream code; CI only builds examples and does not compare them (.github/workflows/main.yml).

#### H-22 [low] CLI behaviour that differs from what it prints, and error handling
- wv_cli.py:91-103, 119-147: `-f ""` -> IndexError; "Output file: a.tsv" but written a.bom.tsv; `-o newdir/sub` missing: -f s/-g create it, -f t/-f h alone fail FileNotFoundError; `-O same a.yml b.yml` second silently overwrites first; every error is a traceback; missing dot leaves a.tmp; one failing file stops the list; build_examples.py:115, 134 os.system with --branch in a shell string (local only); `clean` also deletes examples/readme.md and tutorial/readme.md.

#### H-23 [low] tweak.override values are used as regex replacement templates
- Harness.py:594-615 (re.subn(f'{attr}=...', f"{attr}={value}", entry)); attr unescaped in a regex. Evidence (t10.py): value `a\1b` -> PatternError invalid group reference; `C:\x` bad escape; `C:\temp` inserts TAB; `a\g<0>b` expands; attribute `fo(o` PatternError; override for non-existent node ignored without warning. Fix: re.escape(attr) and a function replacement.

##### Checked and found fine
yaml.safe_load (a !!python/object/apply:os.system tag is rejected); UTF-8 BOM and CRLF YAML and unicode designators/labels/filenames in a UTF-8 locale; Python 3.7 syntax (vermin); colour tables DIN 47100 (60), IEC (10), TEL (50), T568A/B, BW fine, only TELALT wrong; translate_color modes; designator rules (redefinition, second separator, alternation, mismatched list lengths, duplicate pins, ambiguous labels, `s` label on shielded cable); BOM dedupe, quantity sums, multipliers, additional items, integer formatting, whitespace collapsed; node names with spaces/quotes/braces/;/DOT keywords/unicode (only ":" fails); large input (two 1,000-pin connectors + 1,000-wire cable ~9 s); image embedding; build_examples regenerates identical files except ex08; CLI --help, -V, no args (help, exit 2), missing file, unknown format letter, several files, -o, -O, -p behave as coded.

##### Questions for the owner
Should upstream code in this fork be changed at all (H-1, H-2, H-3, H-4, H-6, H-7, H-8 are real bugs with small fixes; if no, the README should say which upstream issues remain)? Which text fields are meant to accept HTML (H-4, H-14)? H-16: AWG table "nearest" or "not smaller than"; keep show_equiv? H-18: should the package built from this repository keep the name wireviz and version 0.4.1? H-9: a wire used twice in a connection set: warning or error?

## Release 1.0.0 (2026-10-12)

**What was released.** Harness Design Studio 1.0.0: version 0.1.0 plus the fixes of this audit (critical, high and medium findings and the cheap low ones, see the two Phase 4 status sections above), the release freeze of parts, interface types and configuration (owner decision Q2), the examples `minimal-satellite` and `flatsat`, the design worksheet template and the wiring-diagram drawing (`harness/CHANGELOG.md`, section 1.0.0). Pull request 45 (`release/1.0.0`) was merged into `master` as commit `0c6a96a`. The tag `v1.0.0` points to that commit. It is not a statement of compliance with any standard; the compliance records say nothing new (`harness/compliance/SIGNOFF.md`, "Release 1.0.0" and "Publication of 1.0.0").

**How it was published.** The working session that prepared the release could not push the tag: every tag push was refused with HTTP 403. The owner created the tag through the GitHub release page instead (Releases, Draft a new release, tag `v1.0.0` created on publish, target `master`) and published it on 2026-10-12 at 20:37 UTC. The tag started `.github/workflows/release.yml`, which ran green: it checked that the tag matches the version and the changelog, built the packages, ran the packaged self-test, wrote `SHA256SUMS` and attached the files to the release page.

| File on the release page | SHA-256 |
|---|---|
| `harness-design-studio-1.0.0-linux-x86_64.tar.gz` | `f75c2747babbb66502fa3ccf82480067e81230ef06542097eaf5db69e2436692` |
| `harness-design-studio_1.0.0_amd64.deb` | `0fec64f63ca95c4c69d4a2eb6e57895802a9a63f3f33648a9b29696cd5af2248` |

The packages are unsigned (`harness/compliance/DEVIATIONS.md` T-19). They were built from `0c6a96a`; documents changed on `master` after that commit are not inside them (this includes the in-app user guide). The last full test run recorded in this file is the Phase 5 one (1735 passed, 2 skipped on `master` after PR 43); this section does not add a new count.

**What remains open (honestly).**
- **Repository "About" text.** It still describes WireViz. Only the owner can change it in the repository settings (item 3 of the Phase 5 list).
- **Licence of `harness/` (D-02).** Kept as the placeholder `LicenseRef-Proprietary`; the root `LICENSE` is the GPL-3.0 licence of WireViz; the `.deb` copyright text says no licence is granted (D-143). The owner has not chosen a licence.
- **Engineering values and parts.** Nobody has supplied real derating, ampacity or EMC values or an approved parts list (D-11, D-12). D-10 and D-15 were recorded as the defaults the tool implements (D-142 to D-145). Results rest on placeholders and example parts.
- **Low findings not fixed**, and medium ones fixed only in part (the list is under "Not fixed or only partly" in the medium status section): B-16, B-17, B-19, B-21, the rest of B-22, C-19, C-22, C-23, D-12, D-14, D-17, A-13 to A-18, F1-16, F1-27, F1-28 (partly), F2-10 (partly), G-12 to G-17 (the cheap ones done), I-9, I-11, K-10 and the other low K items. B-8 covers manual harnesses only (a released harness is not part of the generation input hash).
- **Upstream WireViz (H-1 to H-23).** Not fixed by decision (Q31: `src/wireviz` is never changed). H-1 to H-9 are listed in the root `README.md` ("Known problems in the bundled upstream WireViz code"). H-18 (the fork's `setup.py`) is fixed.
- **Not verified, so not claimed:** the `.deb` and `install.sh` on a real clean Ubuntu 24.04 machine, the editor on a real display (all editor tests run offscreen; drag, drop, the tour and high scale factors deserve a manual pass), Excel, LibreOffice and Acrobat opening the outputs, non-Ubuntu systems, and the glossary entries marked "(general meaning)" (they need an engineer). No independent review took place (waived, T-20 to T-30). Transitive dependencies are not locked (G-16), and the GitHub actions are not pinned to commit hashes.

**Section 4, the open questions, and the default that was applied.** The owner answered Q2 (yes), Q31 (never change WireViz) and Q32 (keep the name `wireviz` and version `0.4.1`). For the others the defaults below were applied and can be changed by telling the maintainer. "Open" means no behaviour was changed.

| Q | Default applied |
|---|---|
| 1 | Undo of a release, new revision or review is refused once it has been saved; unsaved ones can still be undone. |
| 2 | Yes: a release freezes the parts, interface types and configuration the harness uses (`docs/FILE_FORMAT.md`, "What a release freezes"). |
| 3 | Every command that reports on or changes a project refuses damaged files with exit 2 (`validate` and `check` list the damage, exit 1). |
| 4 | A restored journal or a reload keeps a read-only session read-only and never deletes another window's journal. |
| 5 | Boot id and process start time in the lock; a lock from before a restart or a reused process number is taken over; a lock from another computer is respected and the error names the file. |
| 6 | AWG 0 to 40 (whole numbers), length 0 to 10000 m, current and voltage above 0, pin count 1 to 1000, masses 0 or more, harness number and schema version 1 or more. |
| 7 | Tables and YAML keep full precision; only the drawings round to six digits. |
| 8 | An ambiguous number such as `1,234` is refused; pin count 1 to 1000. |
| 9 | IDs are never cut: the drawing shrinks the font (down to 1.4 mm); the model limits stay. |
| 10 | `Wire.signal` and the cable-side pin table are derived and checked by the verifier when set. |
| 11 | A missing shield group is a verifier error; gauge, colour and part of a wire are not checked by the verifier. |
| 12 | An unpaired directional signal that generation wires straight through is no longer a `direction-conflict`. |
| 13 | `power-return-adjacent` counts unassigned contacts between any two power or ground pins. |
| 14 | `--apply-profile` sets `"placeholder": true` on every file it changes. |
| 15 | `part-unapproved` also reports example (unverified) parts. |
| 16, 17, 18 | Open (mass completeness, segregation settings, multi-colour wires). |
| 19 | A locked wire or entered length that regeneration cannot carry over is a warning (`locked_data_lost`); the status turns stale when a manual harness takes over an interface; released harnesses do not make it stale. |
| 20 | Segments must form a tree: error `segment-loop`. |
| 21 | `sheet` may be left out of the title block; unknown or repeated field names and non-text entries are a configuration error. |
| 22 | The CSV apostrophe guard is kept and can be undone exactly. |
| 23 | PDFs keep Windows-1252; the export names every character it replaced. |
| 24 | A shield's end A is the start of its lowest-ID wire for the whole harness; the overview draws every pair of units. |
| 25 | `OPENPYXL_LXML` is forced off, so XLSX files are identical with or without lxml. |
| 26 | The release check fails when the version is already a tag or `## Unreleased` has text. |
| 27 | The CI template runs `harness drc`. |
| 28 | The six undeclared packages are excluded; the build fails on anything not on the allow-list. |
| 29 | Open (K-10): the app cannot lock a wire or pin; the documents say so. |
| 30 | Open: names are checked for control characters and length, `--date ""` is an error; the same person may author, check and approve; a release may be dated before its review. |
| 33 | The licence stays the placeholder (D-143). |
| 34 | Open (A-14): the undo history is not capped. |
| 35 | Exit-code policy unchanged (0, 1, 2); `docs/CLI.md` now lists 130 for Ctrl-C. |
