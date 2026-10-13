# Set wire colours

This page shows how to give each signal (power, return, CAN high, ...) a wire colour, so that the wire list shows it and the harness drawings draw it.

> **Not in the 0.1.0 packages.** *Edit > Wire colours...*, the *Colour* column set from signals and the coloured wiring-diagram drawing are new in 1.0.0. They are not in the 0.1.0 `.deb` and `.tar.gz`. See the [changelog](../../CHANGELOG.md). `harness new --list` shows five examples on 1.0.0 and three on 0.1.0.

## Before you start

- You have a generated project. The tool defines **no colours of its own**: a signal you do not colour is drawn grey. Which colour a signal gets is your programme's rule.
- The colours come from the IEC 60757 list: black (BK), brown (BN), red (RD), orange (OG), yellow (YE), green (GN), blue (BU), violet (VT), grey (GY), white (WH), pink (PK), turquoise (TQ). The two-letter code is also written next to the wire on the drawing, so a greyscale print loses nothing.

## 1. In the app

1. Choose **Edit > Wire colours...**.
2. The **Wire colours** window lists each signal name of the interface types the project uses (for example `PWR`, `RTN`, `TX+`, `CANH`). Next to each is a list: **no colour**, or one of the colours with its code.
3. Pick a colour for each signal you want, then press **Save**.
4. The app says "Wire colours saved. Generate the harnesses to apply them." Saving is one undo step.
5. Press **Generate** and **Apply**. The wires take the colours now, and the **Colour** column of the wire table in the **Harness** tab (and of the wire list in **Lists**) shows them.
6. Press **Export…** to get the drawings with the colours ([export the outputs](export-the-outputs.md)).

GUI, not run: the menu name and the texts above are taken from the program's code. The dialog has not been looked at on screen.

## 2. In the project file (also for scripts)

The setting is the key `wire_colour_by_signal` in `config/generation.json`, inside `values`:

```
"wire_colour_by_signal": {
  "PWR": "red",
  "RTN": "black"
}
```

(The rest of the file stays as it is. See [the shape of a config file](fill-in-engineering-values.md#the-shape-of-a-config-file).) Then:

```
harness generate wheel-link
harness export wheel-link
```

```
0 added, 1 changed, 1 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
38 files written to wheel-link/outputs (model 53f9d7e557d3).
```

Only the power harness changed, because the RS-422 signals have no colour yet. In `outputs/harnesses/W002/wirelist.csv` the `Colour` column now reads:

```
W002-001,PWR,IF-001,W002-P1,1,W002-P2,1,22,EX-WIRE-SINGLE,red,1,W002-S1,
W002-002,RTN,IF-001,W002-P1,2,W002-P2,2,22,EX-WIRE-SINGLE,black,1,W002-S1,
```

(The gauge 22 is there because demo values were loaded in this example.) In the drawing the two wires carry the text `W002-001  RD` and `W002-002  BK`.

## Rules to know

- A wire between two different signals is labelled like `TX+/RX+`. It takes the colour of the first signal that has one.
- A wire that has a colour of its own (set by hand and locked) keeps it. The signal colour is used only when the wire has none.
- Change the colours and generate again: the wires follow. `red` became `blue` in a test.
- A colour that is not in the list (for example `mauve`) is kept as typed. The drawing writes it as text, shortened to six letters, and draws the wire grey. The app's list offers only the 12 colours.
- A two-letter code (`BK`) in the file is understood too.

## Common mistakes

- **Colours do not appear after saving the dialog.** Saving only records the choice. Generate the harnesses, then export.
- **A top-level `wire_colour_by_signal` key.** It must be inside `values`, or the file is refused ([fill in the engineering values](fill-in-engineering-values.md#the-shape-of-a-config-file)).
- **Expecting the tool to know the right colours.** It does not. The wiring practice of your programme decides them.
- **The 0.1.0 packages have no such menu.** See the box at the top.

More: [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md), [`CONFIG.md`](../CONFIG.md).

Next: [export the outputs](export-the-outputs.md), [release a harness](release-a-harness.md)
