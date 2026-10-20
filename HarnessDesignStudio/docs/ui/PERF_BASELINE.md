# Performance baseline before the UI overhaul

Measured on 2026-10-19, on `master` at 6a04874 (release 1.2.0 plus two test fixes), Linux container with 4 vCPU,
Python 3.12.3, PySide6 6.11.2, **offscreen platform with software rendering**. Absolute numbers on a
laptop with a GPU and a real window system differ; the point is to compare the same script before and after.
Re-run both scripts at the end of every milestone and paste the table into the session summary.

How to repeat:

- `python -m tools.bench_gui` (stress project: 200 units, 2,000 interfaces, about 20,000 wires; the script
  already exists). `NODRC=1 python -m tools.bench_gui` switches the background rule check off.
- `python -m tools.ui_perf` (start-up, tab switching,
  theme switch, UI scale, select) on the flatsat example (23 units, 44 interfaces, 3 harnesses).

## Flatsat example (the typical project)

| What | Measured |
|---|---|
| Import of the GUI package and its resources | 525 ms |
| `MainWindow()` constructed | 255 ms |
| First `show()` plus first event-loop pass | 77 ms |
| Open the flatsat project (load, install, first paint) | 147 ms |
| **Start to first interactive window (sum)** | **about 1.0 s** |
| Switch tab, first time / median of 5 (Harness, Lists, Checks, Releases, Devices) | 60 / 22, 52 / 19, 36 / 19, 13 / 8, 55 / 18 ms |
| Select a unit (median, max) | 45 ms, 74 ms |
| **Switch theme light to dark (and back)** | **950 ms, 710 ms** |
| **Change the UI scale (any step)** | **760 to 800 ms** |

Theme and scale are applied by setting one application-wide style sheet again, which makes Qt re-polish every
widget. That is the slowest thing a user can do in the tool on a small project, and the brief asks for a *live*
switch. M1 has an acceptance criterion for it.

## Stress project (200 units, 2,000 interfaces)

`python -m tools.bench_gui`, rule check on:

| What | Measured |
|---|---|
| Install project and autoplace | 1,327 ms |
| Fit all | 44 ms |
| Select unit (first / next) | 161 / 0 ms |
| Select other unit | 353 / 16 / 0 ms |
| Rename unit, move unit, add unit, undo, redo | **10.7 to 12.7 s each** (see the note) |
| Full repaint | 1,044 / 759 / 35 ms |
| Change while the Problems tab is visible | 1,016 ms |
| Change while the interface table is visible | **11,481 ms** |

Same script with `NODRC=1` (background rule check off):

| What | Measured |
|---|---|
| Install project and autoplace | 1,455 ms |
| Select unit | 183 / 0 / 0 ms |
| Rename unit | 96 / 68 / 54 ms |
| Move unit | 397 / 48 / 120 ms |
| Add unit, undo, redo | 236 to 338 ms, 139 to 243 ms, 212 to 231 ms |
| Full repaint | 50 / 38 / 50 ms |
| Change with Problems tab / interface table visible | 64 / 81 ms |

**Note on the 11 s figures (resolved in M5, see "After M5" below and D-154; the text below is what was known at the time).** With the rule check on, every edit in the
benchmark takes about 11 s in this container; with it off the same edit takes 50 to 240 ms. A short profiling
script (select two units, then rename one, rule check on, same stress project) did **not** reproduce it: the
rename took 64 to 219 ms, of which about 50 ms is the GUI thread receiving the check's result from the helper
process (`core/drc/worker.py: receive`, mostly `pickle.loads` and pipe reads). `docs/UX.md` (Q16) recorded 25 to
60 ms for the same benchmark on 2026-10-09. So I cannot say whether the benchmark shows a regression since that
date, an artefact of this container (4 vCPUs shared with the helper process) or something in the benchmark's
own sequence of calls. M1 re-measures on the CI runners and on a normal machine first. If it reproduces, it is a
UI-side scheduling problem (how the GUI waits for and applies the check result) and stays inside the rules of
the overhaul; if the cause is inside the rule check itself, I stop and ask, as the brief requires. Either way
the plan does not rely on "edits are fast with the check running" until that is settled.

## Interactions that already run off the GUI thread

Generation plan (`PlanWorker`), diagram arrangement (`ArrangeWorker`), export (`OutputsWorker`), rule check
(`DrcWorker` plus helper process `drc_process.py`), background jobs (`JobRunner`). Everything else runs on the GUI
thread, notably: project open and install (147 ms flatsat, 1.3 to 1.5 s stress), save, the import parsers (file
read and preview), the interface table rebuild, the diff computation of the Releases tab and theme or scale
change (above). The Inventory in `UI_OVERHAUL_PLAN.md` lists each.

## After M1 (theme package, 2026-10-19; same container, same script)

| What | Before | After M1 |
|---|---|---|
| Start to first interactive window (import + window + show + open flatsat) | 1.0 to 1.15 s | 0.94 to 1.09 s |
| Switch theme light to dark (and back) | 560 to 950 ms | **77 to 138 ms** (first switch after start-up is the slowest) |
| Change the UI scale (any step) | 760 to 800 ms | 670 to 940 ms (not improved: a new style sheet and font are installed; see D-150) |
| Select a unit (median) | 45 ms | 34 to 48 ms |
| Tab switch, first time (Harness, Lists, Checks, Releases, Devices) | 60, 52, 36, 13, 55 ms | 61 to 68, 66 to 78, about 40, about 12, about 55 ms |

How the theme switch got fast: the style sheet holds no colour (it names palette roles), so a switch sets the other palette and repolishes only the 80 or so visible widgets; the 870 hidden ones are unpolished and Qt polishes them when they are first shown. Measured before the change: setting any different application style sheet costs 230 ms for a one-rule sheet and 300 to 500 ms for the real one, because Qt matches every widget again.

## After M5 (the 11-second edit explained and fixed, 2026-10-19; same container, same script)

Cause: two GUI-side lookups that scanned every wire of every harness once per finding (82,549 findings after a check of the stress project): the diagram's state index (`drc.locate`, 49 s under the profiler, about 11 s real) and the project tree's problem counts (`_wire_index`, 5 s). Both now use a dictionary or a set built once. `core` is unchanged.

| What (stress project, rule check on) | Before | After |
|---|---|---|
| Rename unit, move unit, add unit, undo, redo | 10.7 to 12.7 s each | 90 to 520 ms (rename 90 to 350, undo 250) |
| Change while the interface table is visible | 11,481 ms | 109 ms |
| Change while the Problems tab is visible | 1,016 ms | 567 ms |
| Taking in a check result on the GUI thread (82,549 findings) | not measured (the same scans) | 132 ms |
| Edit after a result has arrived, warm, minimum of 3 | about 11,000 ms | 70 to 90 ms |

## After M9

Change the UI scale: 1,100 to 1,200 ms (unchanged; 1.06 s of it is Qt's `QApplication.setStyleSheet` over about 1,250 widgets; D-158). The window shows a wait cursor while it happens.
