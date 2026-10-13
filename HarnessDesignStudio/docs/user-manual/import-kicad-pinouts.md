# Import KiCad pinouts

This page shows how to read the connector pinout of a unit (which signal is on which pin) from a KiCad netlist, so that you do not type it again.

## Before you start

- **KiCad** is a program for drawing electronics. Here it is used only for the electronics inside each unit. It knows which signal is on which pin of the unit's connectors ([glossary: pinout](../GLOSSARY.md)).
- You need a **netlist** from KiCad, in one of two forms:
  - the S-expression `.net` file that the schematic editor writes by default (in KiCad's schematic editor, the netlist export; the menu name depends on the KiCad version and was not checked here), or
  - the XML file: `kicad-cli sch export netlist --format kicadxml -o unit.net.xml unit.kicad_sch` (the input file goes last).
- A `.kicad_sch` schematic file is **not** accepted. The tool reads KiCad's own computed connections, not the drawing.
- KiCad is not needed to follow this page. The templates contain a small netlist to practice with. The KiCad commands above were not run for this page; the netlist import was checked with the template file.
- The unit must exist in your project and have the connectors you import into.

## 1. Get the practice files

```
harness-design-studio new wheel-link --template first-steps
harness-design-studio templates my-templates
```

`my-templates/wheel-connectors.net` is a small netlist for the two connectors of the wheel `RW1` (`RW1-J01` for power, `RW1-J02` for the RS-422 link). `my-templates/signal-map.csv` renames KiCad net names to signal names.

## 2. Try it without changing anything

```
harness-design-studio import-netlist wheel-link my-templates/wheel-connectors.net --unit RW1 --prefix J --connector J1=RW1-J01 --connector J2=RW1-J02 --dry-run
```

```
J1: OK updated RW1-J01 (2 signal pin(s))
J2: OK updated RW1-J02 (4 signal pin(s))
Dry run: nothing was changed.
```

What the options mean:

- `--unit RW1` is the unit the connectors belong to.
- `--prefix J` says that KiCad parts whose reference starts with `J` are connectors. (Or name them one by one with `--ref J1 --ref J2`.)
- `--connector J1=RW1-J01` says which connector of the unit a KiCad reference becomes. A field called `HarnessConnector` on the KiCad symbol does the same; the practice netlist has it, so `--connector` is optional there.
- `--part J1=PART-ID` chooses the library part of a new connector. A KiCad field `HarnessPart` does the same.
- `--signal-map` renames KiCad net names to the signal names of the interface type. Either pairs (`--signal-map CAN_H=CANH --signal-map CAN_L=CANL`) or a file of pairs (`--signal-map my-templates/signal-map.csv`). Names that match nothing are listed. They are never guessed.

## 3. Read the rows, then apply

Read each line. It names the connector and how many pins got a signal. Net names are cleaned (`/io/TX+` becomes `TX+`). Nets without a name leave the pin without a signal.

Run the same command without `--dry-run`:

```
harness-design-studio import-netlist wheel-link my-templates/wheel-connectors.net --unit RW1 --prefix J --connector J1=RW1-J01 --connector J2=RW1-J02
```

```
J1: OK updated RW1-J01 (2 signal pin(s))
J2: OK updated RW1-J02 (4 signal pin(s))
Imported 2 connector(s). Generate harnesses again to connect interfaces to the fixed pins.
```

The import is all or nothing: a netlist with a problem changes nothing. Now generate:

```
harness-design-studio generate wheel-link
```

```
2 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
```

## What "fixed" means

Imported pins are **fixed**: generation connects an interface signal to the pin that has the same name and never moves it. A connector with fixed pins is filled by name only; there is no automatic placement. If a needed signal has no free pin, generation reports an error for that interface instead of using another pin. With a netlist that lacks the `RX-` net:

```
error: [pin_allocation] IF-002: RW1-J02 has a fixed pinout and no free pin named RX-.
1 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 2 wires checked: 4 error(s)
Not saved: fix the errors above first.
```

(The numbers depend on the project. Here the netlist had no `RX-` net.) The command exits with 1.

Fix the netlist (or the signal map), import again, generate again.

## Common mistakes

- **"The file is not a KiCad netlist (no (export ...) at the top)."** You gave it a `.kicad_sch` file. Export a netlist from the schematic editor.
- **`--unit` missing.** The command needs it: `error: the following arguments are required: --unit`.
- **A connector with more pins in KiCad than in the library part.** It is refused. Choose a bigger part with `--part`.
- **`kicad-cli` fails to load a library.** That is a KiCad install problem. Export the netlist from the schematic editor instead.
- **Trusting the import blindly.** The reader was checked against one real KiCad 10.0.6 file and small hand-made ones. Hierarchical sheets and multi-unit symbols were not tried on a real project. Check the printed rows for each unit.

More: [`KICAD.md`](../KICAD.md), [`TROUBLESHOOTING.md`](../TROUBLESHOOTING.md).

Next: [import data](import-data.md), [generate harnesses](generate-harnesses.md)
