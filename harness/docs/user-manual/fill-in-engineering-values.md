# Fill in the engineering values

This page shows how to supply the numbers the tool does not invent (derating factors, wire current ratings, voltage drop, test limits), so that wire gauges get decided and the checks that said "not checked" can run.

## Contents

- [Before you start](#before-you-start)
- [1. See what is missing](#1-see-what-is-missing)
- [The shape of a config file](#the-shape-of-a-config-file)
- [2. Load the current-by-gauge table](#2-load-the-current-by-gauge-table)
- [3. Edit the other values](#3-edit-the-other-values)
- [4. Generate again](#4-generate-again)
- [5. Mark a file as reviewed](#5-mark-a-file-as-reviewed)
- [Practice with demo values](#practice-with-demo-values)
- [Values from a standard (profiles)](#values-from-a-standard-profiles)
- [Common mistakes](#common-mistakes)

## Before you start

- Out of the box the tool holds **no engineering numbers**. Your programme decides them. (Optional profiles can fill in values from a standard; see [the end of this page](#values-from-a-standard-profiles). They still need an engineer's review.) Until you enter them they are **placeholders**: wire gauges stay *pending*, and checks that need a number say *not checked* instead of passing silently ([glossary](../GLOSSARY.md)).
- Who supplies the numbers: an engineer on your programme, for example from your programme's derating standard (*derating* means using a wire or contact below its maximum for safety; see the [glossary](../GLOSSARY.md)). This page does not tell you which numbers to use.
- You have a generated project, for example `harness new wheel-link --template first-steps` then `harness generate wheel-link`.

## 1. See what is missing

```
harness config wheel-link
```

```
Engineering values: 0 of 17 set.
- MISSING config/derating.json ampacity_a_by_awg: current each wire gauge may carry, in amperes, as {"20": 5.0, ...}. Needed for: wire sizing, wire current check.
- MISSING config/derating.json bundle_derating: factor (above 0, at most 1) for wires in a bundle. Needed for: wire sizing, wire current check.
...
Files still marked as placeholder (set "placeholder": false after review): derating, emc, generation, segregation.
Waiting for an owner decision: config/segmentation.json is a placeholder until the rule for how interfaces are grouped into harnesses is confirmed.
Waiting for an owner decision: config/titleblock.json is a placeholder until the title block fields are confirmed.
```

The command exits with 1 while values are missing. It lists every missing value, what depends on it, and any value that is set but invalid (for example `INVALID config/derating.json: bundle_derating must be a number above 0 and at most 1.`). Use it as your hand-over checklist. The full list of files and keys is in [`CONFIG.md`](../CONFIG.md) and [`PLACEHOLDERS.md`](../PLACEHOLDERS.md).

**In the app** (GUI, not run here): the status bar says how many values are pending, for example "4 values pending · 12 rules not checked"; pressing it opens the **Checks** tab filtered to the rules that could not run. Press **Supply value…** on one of them, or choose **Design > Engineering values…**, to open the **Engineering values** window. It lists every value by config file with its unit and what it is needed for. Type the values you have and press **Apply** (Ctrl+Enter): all of them are set as one undo step and the checks run again. A refused value is explained under its field, and a value that a released harness locks is disabled with the reason. The window changes the same files as the steps below.

## The shape of a config file

Every file in the project's `config/` folder has the same three keys: `name`, `placeholder` and `values`. The numbers go **inside `values`**:

```
{
  "name": "derating",
  "placeholder": true,
  "values": {
    "ampacity_a_by_awg": null,
    "bundle_derating": 0.8,
    "contact_current_factor": null,
    "contact_rating_key": "contact_current_a",
    "max_ambient_temperature_c": null,
    "max_voltage_drop_v": null,
    "spare_pin_fraction": null,
    "temperature_derating": 0.9
  }
}
```

`null` means "not decided". If you write a key at the top level, outside `values`, the file is refused. This is what `harness validate` prints when `"bundle_derating": 0.8` stands next to `values`:

```
ERROR   quarantined: A configuration could not be loaded and was set aside: bundle_derating: Extra inputs are not permitted [config/derating.json]
INFO    config_defaulted: Configuration 'derating' is missing or unreadable; the built-in placeholder is used. [config/derating.json]
```

If the file holds only `{"bundle_derating": 0.8}`, the first line reads `... name: Field required; placeholder: Field required; values: Field required (+1 more) [config/derating.json]` instead.

The built-in placeholder replaces your file, so your values do not count. Put them inside `values`.

## 2. Load the current-by-gauge table

The table says how many amperes each wire gauge (AWG) may carry. It comes from your programme. Make a two-column CSV file, gauge and amperes (a header is optional, decimal commas are accepted):

```
gauge,amperes
22,3
20,5
```

Load it. The command checks it before it writes anything:

```
harness config wheel-link --ampacity-csv amp.csv
```

```
Loaded 2 gauges into config/derating.json. Review it, then set "placeholder": false when the file is complete.
Engineering values: 1 of 17 set.
- MISSING config/derating.json bundle_derating: factor (above 0, at most 1) for wires in a bundle. Needed for: wire sizing, wire current check.
...
```

(The numbers 3 and 5 are only an example of the format. They are not engineering data.)

## 3. Edit the other values

Open the file named in the list, for example `config/derating.json`, in a text editor and set the values inside `values` (or use the **Engineering values** window of the app, see above). Close the project in the app first, or reload it afterwards. Then check:

```
harness config wheel-link
harness validate wheel-link
```

A thinner wire must not carry more than a thicker one; a factor must be above 0 and at most 1. The check says so if you break such a rule. The same problems appear as errors in the app (rule `config-invalid`).

For the test limits (`test_continuity_max_ohm`, `test_isolation_min_mohm`, `test_isolation_voltage_v`) and the other keys of `generation.json`, see [`CONFIG.md`](../CONFIG.md). The wire colours are set in a different way: [set wire colours](set-wire-colours.md) (not in the 0.1.0 packages).

## 4. Generate again

A gauge needs more than the table. It also needs the current of the link and the length of the wire, because the voltage drop is checked over the length.

1. Set **Max current (A)** on each power link in the app ([draw the design](draw-the-design.md#4-set-the-current-and-voltage-of-a-link)).
2. Import the segment lengths ([import data](import-data.md#segment-lengths)).
3. Generate again:

```
harness generate wheel-link
```

## 5. Mark a file as reviewed

When an engineer has reviewed all the values in a file, set `"placeholder": false` in that file (top level, next to `name`). Do it only after the review (in the app, untick *Values in this file are placeholders (not reviewed)* in the **Engineering values** window). The mark is what the release check looks at ([release a harness](release-a-harness.md)). It cannot tell whether the values are right. That stays a decision for a person.

## Practice with demo values

To see the machinery work before you have real values, the templates contain demo values. They are **not engineering data**. Never release a real design with them.

```
harness templates my-templates
cp my-templates/config-demo-values/*.json wheel-link/config/
harness import-lengths wheel-link my-templates/segment-lengths.csv --unit mm
harness generate wheel-link
harness export wheel-link
```

```
38 files written to wheel-link/outputs (model 57f544aa1797).
```

(The model hash depends on the project; yours may differ.) After two header lines, the first two wires in `outputs/harnesses/W002/wirelist.csv` read:

```
W002-001,PWR,IF-001,W002-P1,1,W002-P2,1,22,EX-WIRE-SINGLE,,1,W002-S1,
W002-002,RTN,IF-001,W002-P1,2,W002-P2,2,22,EX-WIRE-SINGLE,,1,W002-S1,
```

Gauge 22 and length 1 m. In the app, the **Why** tab of `W002` explains it:

```
wire-sizing: ampacity: AWG 22 carries 2.16 A derated (factor 0.72) for 2 A
wire-sizing: voltage drop: AWG 22 gives 0.211345 V over 2 conductor(s), limit 0.5 V
contact-check: not done for PCDU1-J01 (contact rating or derating factor is a placeholder)
```

The files stay marked `"placeholder": true`, so every result built on them still says so. The last line shows the tool still refusing to check what it has no number for.

## Values from a standard (profiles)

If your programme works to ECSS-Q-ST-30-11C or ECSS-E-ST-20-07C, you can start from the values the tool holds from the text of those standards as supplied to this project:

```
harness config wheel-link --apply-profile ecss-q-st-30-11c
```

```
set derating.contact_current_factor = 0.5  (ECSS-Q-ST-30-11_0140051: Table 6-10 current 50 %)
...
Profile ecss-q-st-30-11c: 11 value(s) set, 0 kept. These values come from the supplied standard and still need an engineer's review; the files stay "placeholder": true until you set it to false.
```

Only values that are still unset are filled; each is printed with the requirement it comes from. The other profile is `ecss-e-st-20-07c`. Applying a profile does not make a design compliant with anything, and it does not fill the current-by-gauge table.

## Common mistakes

- **Values at the top level of the file.** See [the shape of a config file](#the-shape-of-a-config-file).
- **Setting `"placeholder": false` to make a warning go away.** The mark means "an engineer reviewed this". Do not use it for anything else.
- **Gauges still pending after all values are set.** The link has no **Max current (A)**, or the wire has no length. `harness release` lists which ([release a harness](release-a-harness.md)).
- **Using the demo values for a real design.** They exist only to show the flow.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

Next: [import data](import-data.md), [release a harness](release-a-harness.md)
