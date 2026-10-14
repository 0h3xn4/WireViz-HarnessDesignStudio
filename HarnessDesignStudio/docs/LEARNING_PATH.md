# Learning path

A route from "I have just installed it" to "I can use it on my own spacecraft". Each step says what you do, how long it takes, which example or template you use, and **how you know you are done**. Do the steps in order; skip a step only if you already know it.

## Contents

- [1. Look around (10 minutes)](#1-look-around-10-minutes)
- [2. Your first harness (45 minutes)](#2-your-first-harness-45-minutes)
- [3. A realistic small system (30 minutes)](#3-a-realistic-small-system-30-minutes)
- [4. Plan your own design (30 minutes)](#4-plan-your-own-design-30-minutes)
- [5. Enter your design (1 to 2 hours)](#5-enter-your-design-1-to-2-hours)
- [6. Bring in real data (as needed)](#6-bring-in-real-data-as-needed)
- [7. Check and review (30 minutes)](#7-check-and-review-30-minutes)
- [8. Release and change (30 minutes)](#8-release-and-change-30-minutes)
- [9. Automate](#9-automate)
- [If you get stuck](#if-you-get-stuck)

If you have not installed the tool yet, start with [`INSTALL.md`](INSTALL.md).

**Which version do you have?** Steps 3 and 4 use the example `minimal-satellite` and the template `design-worksheet.md`, and the `flatsat` example is mentioned too. These, the wiring-diagram drawing with wire colours and *Edit > Wire colours...* are not in the 0.1.0 packages (see [`CHANGELOG.md`](../CHANGELOG.md)). `harness-design-studio new --list` shows five examples on 1.0.0 and three (`blank`, `first-steps`, `small-satellite`) on 0.1.0. With 0.1.0, do step 3 with `small-satellite` and plan on paper in step 4.

| Step | You learn | Time | Uses |
| --- | --- | --- | --- |
| 1. Look around | what the tool is for | 10 min | [`CONCEPTS.md`](CONCEPTS.md) |
| 2. Your first harness | generate, check and export | 45 min | example `first-steps`, [`GETTING_STARTED.md`](GETTING_STARTED.md) |
| 3. A realistic small system | read a whole design | 30 min | example `minimal-satellite` |
| 4. Plan your own design | decide units and interfaces before you click | 30 min | template `design-worksheet.md` |
| 5. Enter your design | build it in the app or import it | 1 to 2 h | `blank`, template `interfaces.csv` |
| 6. Bring in real data | parts, lengths, engineering values | as needed | templates `approved-parts.csv`, `segment-lengths.csv`, [`CONFIG.md`](CONFIG.md) |
| 7. Check and review | read every problem, decide what is a real issue | 30 min | template `design-review-checklist.md` |
| 8. Release and change | freeze a harness, then change it with a new revision | 30 min | [`HOWTO.md`](HOWTO.md) |
| 9. Automate | the same steps in a script or CI | 20 min | templates `ci/build.sh`, `ci/github-actions.yml` |

## 1. Look around (10 minutes)

Read [`CONCEPTS.md`](CONCEPTS.md). You should be able to say, in your own words, what a **unit**, an **interface**, a **harness**, a **wire** and a **project** are, and why the tool generates harnesses instead of asking you to draw them.

**Done when:** you can explain why a wire has a "Why is it like this?" text.

## 2. Your first harness (45 minutes)

Follow [`GETTING_STARTED.md`](GETTING_STARTED.md) from Part 1 to Part 6. It uses the example `first-steps` (three units, two interfaces) and shows the real output of every command.

```
harness-design-studio new wheel-link --template first-steps
harness-design-studio generate wheel-link
harness-design-studio drc wheel-link
harness-design-studio export wheel-link
```

**Done when:** you have opened `wheel-link/outputs/` and found the wire list, the pinout of one connector and the block diagram, and you know which of them says "pending" and why.

## 3. A realistic small system (30 minutes)

`minimal-satellite` has seven units without redundancy: solar array, battery, power distribution unit (`PCDU1`), on-board computer, transceiver, one reaction wheel and a sun sensor. It is the smallest example that looks like a real spacecraft.

```
harness-design-studio new mini --template minimal-satellite
harness-design-studio generate mini
harness-design-studio drc mini
```

Open it in the app (**File > Open project...**). Try these four things, in this order:

1. Click a wire of the power link from the power distribution unit (`PCDU1`) to the computer. Read **Why is it like this?**
2. Open the **Problems** tab. Most entries say that a value is *pending* or *not checked*. That is the tool being honest: nobody has supplied the derating values yet.
3. Use the **Show** list in the toolbar to look at the power interfaces only, then at the data interfaces.
4. Delete a unit, then press **Ctrl+Z**, to see that nothing is lost.

**Done when:** you can find, for any wire, which interface it belongs to and which two connector pins it joins.

The 14-unit example `small-satellite` has redundant chains; use it once you are comfortable with `minimal-satellite`. When you want to see a complete system with ground equipment, harness bundles between panels, example numbers and everything generated, take the `flatsat` example and read [`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md).

## 4. Plan your own design (30 minutes)

Before you open the tool, fill in `design-worksheet.md` (get it with `harness-design-studio templates my-templates`). It asks for the units, the interfaces between them, which of them need redundancy, and which numbers you do not have yet. A filled worksheet is half of the data entry.

**Done when:** every interface on the worksheet has two units, a type and (for power) a maximum current.

## 5. Enter your design (1 to 2 hours)

Two ways, and you can mix them:

- **In the app.** Start a project from `blank` (`harness-design-studio new my-design`), add units (**Add** in the Project tab, or the Palette tab), then draw the interfaces. See [`GETTING_STARTED.md`](GETTING_STARTED.md), Part 10.
- **From a table.** Copy `interfaces.csv` from the templates, replace the rows with yours and import it with **File > Import interfaces**. Add the units first. Importing interfaces is app only: there is no command line command for it.

**Done when:** `harness-design-studio generate my-design` finishes and `harness-design-studio check my-design` reports no errors.

## 6. Bring in real data (as needed)

Do this when the data exists; the tool works without it and says so.

- **Parts list:** `approved-parts.csv`, then `harness-design-studio import-parts`. Only approved parts make a harness releasable without a written reason.
- **Segment lengths:** `segment-lengths.csv`, then `harness-design-studio import-lengths`. Wire lengths, mass and voltage drop depend on them.
- **Engineering values** (derating, ampacity, EMC classes): [`CONFIG.md`](CONFIG.md). The files in `config-demo-values/` are **for learning only**; they stay marked as placeholders. Never copy demo values into a real design.
- **Unit connector pinouts from KiCad:** [`KICAD.md`](KICAD.md).

**Done when:** `harness-design-studio config my-design` lists no missing value you are responsible for.

## 7. Check and review (30 minutes)

Read every entry of the **Problems** tab or of `harness-design-studio drc`. For each one, decide: fix it, waive it with a reason, or note that it is outside the tool. Then go through `design-review-checklist.md` with a colleague. Rule texts: [`RULES.md`](RULES.md).

**Done when:** every open problem has a decision.

## 8. Release and change (30 minutes)

A released harness is locked, and so are the parts, interface types and configuration values it uses. To change them, you start a new revision, so the old one stays reproducible. The steps, with the exact commands, are in [`HOWTO.md`](HOWTO.md) and in Part 9 of [`GETTING_STARTED.md`](GETTING_STARTED.md). Practise on a copy of your project, not on the real one.

**Done when:** you can show, with `harness-design-studio diff` and `harness-design-studio log`, what changed since revision A. After `harness-design-studio revise`, `harness-design-studio diff DIR W002` compares revision A with the working design; revision B has a baseline of its own only after you release it, and then `--from A --to B` compares the two.

## 9. Automate

Run the same steps in a script or in CI so that every change to the design is checked: `ci/build.sh` and `ci/github-actions.yml` in the templates. Exit codes are in [`CLI.md`](CLI.md).

**Done when:** a change that adds an error makes the script fail.

## If you get stuck

[`FAQ.md`](FAQ.md) lists the usual problems. [`CHEATSHEET.md`](CHEATSHEET.md) fits on one page.

Next: [`GETTING_STARTED.md`](GETTING_STARTED.md), [user manual](user-manual/README.md).
