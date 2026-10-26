# Enter the build data

This page shows how to enter what a technician needs to build a harness and the model does not get from the design: the strip length at each end of a wire, the contact on each pin and the crimp tool for it, and the sleeving, heat shrink, labels and backshells; it shows how to do it in the app and from a file, and what the build workbook then shows.

> **Since 1.7.0.** The build data is part of 1.7.0 (decision D-170). A project made by 1.6.0 or earlier opens as it is and keeps byte-identical files and outputs until you enter one of these values. The steps in the app are described from the program's texts and its tests; the program was not watched on a screen while this page was written. The commands were run, and the output is what they printed.

## Contents

- [What it is for](#what-it-is-for)
- [Before you start](#before-you-start)
- [1. Strip lengths](#1-strip-lengths)
- [2. Contacts and crimp tools](#2-contacts-and-crimp-tools)
- [3. Accessories](#3-accessories)
- [4. What the outputs then show](#4-what-the-outputs-then-show)
- [What Generate does with it](#what-generate-does-with-it)
- [Common mistakes](#common-mistakes)

## What it is for

A harness design says which wire goes from which pin to which pin. A person who cuts, strips, crimps and sleeves the harness needs more: how much insulation to take off each end, which contact goes on a pin and with which tool, and what goes over the wires. The tool holds these as **build data**. Every item is optional and is **your** value:

| Item | What it is | Where it lives |
| --- | --- | --- |
| **Strip length** | Millimetres of insulation removed at the From end (**Strip A**) and the To end (**Strip B**) of a wire. | The wire. |
| **Contact** | A part of the library with the category *contact*: the contact the cable side uses on a pin. | The pin. |
| **Crimp tool** | The crimp tool, or its setting, for a contact part, in your words. | The contact part. |
| **Accessory** | Sleeving, heat shrink, a label, a backshell or something else, with where it goes in words, the length of one piece and how many. | The harness. |

The tool **computes nothing from them and checks nothing**: it does not know whether a contact fits a pin or whether 6 mm is a sensible strip length, and it sets no default. An empty value stays empty and the build workbook marks it `to fill in`. See [the glossary](../GLOSSARY.md) for *strip length*, *contact part*, *crimp tool* and *accessory*.

## Before you start

- You have a generated project with a harness that is not released. A released harness is locked, accessories included: start a new revision first ([change a released harness](change-a-released-harness.md)). The practice project is the one used everywhere in this manual:

```
harness-design-studio new wheel-link --template first-steps
harness-design-studio generate wheel-link
```

- Starting files for the three kinds of table are in the templates (`strip-lengths.csv`, `pin-contacts.csv` and `accessories.csv`; run `harness-design-studio templates my-templates`, see [import data](import-data.md#before-you-start)). Their rows are **examples with example numbers**: replace them with your own values.
- A contact or an accessory names a **part of the library**. The library must hold the part first: a contact part comes in with the parts import ([import data](import-data.md#approved-parts-list); the starter library has none).

## 1. Strip lengths

**In the app** (GUI, not run): choose **Drawings** on the rail (a Systems engineer's rail does not list it: use **Go > Go to Harness**), select a wire (or several) and open the **Edit wire** tab. It has two fields, **Strip A (mm)** for the From end and **Strip B (mm)** for the To end.

- For several wires a field that differs between them is empty and says *various*; an empty field clears the value. A decimal comma is accepted.
- **Apply** sets them together with any other field you touched, as one undo step.
- **Apply strip lengths to all wires of this harness** gives every wire of the harness the two values in the fields (a field you emptied clears it) and says `Strip lengths changed on N of M wires of W001.`
- Strip lengths do **not** lock the wire: the form says `Strip lengths do not lock the wire against Generate: they are always kept, like the note.`

**From a file.** `harness-design-studio import-build-data DIR FILE` reads a table (`.csv`, `.tsv`, `.json` or `.xlsx`) and finds out what it holds from the column headings. For strip lengths the headings are `Wire`, `Strip A (mm)` and `Strip B (mm)`; `Harness` is optional while the wire ID is unique in the project. Any case works, and other columns are ignored (so you can keep a `Comment` column). The file `strip-lengths.csv`:

```
Wire,Strip A (mm),Strip B (mm)
W001-001,6,6
W001-002,6,5
W001-003,6,6
W001-004,6,5
```

First look at what it would do:

```
harness-design-studio import-build-data wheel-link strip-lengths.csv --dry-run
```

```
Import strip lengths: 4 row(s) read.
row 2: OK strip A 6 mm, strip B 6 mm
row 3: OK strip A 6 mm, strip B 5 mm
row 4: OK strip A 6 mm, strip B 6 mm
row 5: OK strip A 6 mm, strip B 5 mm
4 added, 0 changed, 0 unchanged, 0 refused.
Dry run: nothing was changed.
```

Run it again without `--dry-run` to apply. The last line is then `Build data imported. Generate keeps it; the build sheets show it.` The summary line counts the rows: *added* is a value that was empty, *changed* a value that was different, *unchanged* a value that was already there. The same file imported twice changes nothing; the second time every row reads `(as it was)` and the summary says `0 added, 0 changed, 4 unchanged, 0 refused.`

An empty cell **leaves the value alone** (it never clears one). To clear a strip length use the app.

**One bad row stops the whole import.** The command ends with exit code 1 and nothing is changed:

```
Import strip lengths: 2 row(s) read.
row 2: ERROR The strip length at the To end must be a number of millimetres, for example 6.
row 3: ERROR Wire 'W009-001' does not exist.
0 added, 0 changed, 0 unchanged, 2 refused.
Nothing was changed.
```

A strip length is a number from 0 to 100,000 mm. The upper limit only guards against a typing slip; it is not a design limit.

## 2. Contacts and crimp tools

A contact is a library part of the category *contact*, and the crimp tool belongs to that part, so the tool is written once for every pin that uses the contact.

**Put the contact parts in the library.** Parts of the category *contact* come in with the parts import. The columns `Tool` and `Crimp tool` are read as the crimp tool:

```
part number,description,category,crimp tool,approval status
EX-CONTACT-22,Socket contact for 22 AWG (example),contact,EXAMPLE crimp tool and setting 4,Approved
EX-CONTACT-24,Pin contact for 24 AWG (example),contact,EXAMPLE crimp tool and setting 3,Approved
```

```
harness-design-studio import-parts wheel-link contact-parts.csv --approved Approved
```

```
row 2: OK added EX-CONTACT-22
row 3: OK added EX-CONTACT-24
2 part(s) ready, 0 row(s) with problems.
Imported 2 part(s). Project parts library (version 0), source: contact-parts.csv (sha256 582037e5ed65), date: not recorded.
```

(The two parts are examples with example data. Use your own parts and say in `--approved` which words in your file mean approved; see [import data](import-data.md#approved-parts-list).)

**Which pin gets the contact depends on who made the harness.**

- **A harness made by Generate** takes the contact from the pin of the **device**, as it takes the termination and the function. In the app (GUI, not run), open **Model** > **Devices** (Ctrl+6), press **Contact** to show the columns, and fill the new column **Cable contact** (between **Termination** and **Function**): an editable choice of the contact parts of the library. The tooltip says `The contact the cable side uses on this pin. Generate copies it to the cable connector.` To give the same contact to several pins, select them and press **Cable contact…** (also in the context menu); that is one undo step. Pasted headers work as well: `Cable contact`, `Contact part` and `Cable contact part` mean this column, while `Contact` alone still means the contact size.
- **A harness you made by hand** ([build a harness by hand](build-a-harness-by-hand.md)) has no device pin to copy from. In the **Connectors** tab the pin form has **Contact**, and **Contact for all pins of this connector** gives the chosen contact to every pin of the selected connector.

In the **Connectors** tab of a generated harness the controls are off. They say why: `The contact of a pin of a generated harness is set on the pin of the device, in the Devices tab (column Cable contact). Generate copies it to the cable connector.`

**From a file, for a generated harness**, name the contact on the device's pins. The pinout import of a device reads the column `Cable contact` (see [define a device](define-a-device.md#take-the-pinout-from-a-spreadsheet)):

```
Connector,Pin,Cable contact
OBC1-J01,1,EX-CONTACT-22
OBC1-J01,2,EX-CONTACT-22
OBC1-J01,3,EX-CONTACT-22
OBC1-J01,4,EX-CONTACT-22
```

A second file, `unit-contacts-rw1.csv`, does the same for the pins 1 to 4 of `RW1-J02` (the other end of `W001`) with `EX-CONTACT-24`. Then generate again:

```
harness-design-studio import-pinout wheel-link unit-contacts.csv --device OBC1
harness-design-studio import-pinout wheel-link unit-contacts-rw1.csv --device RW1
harness-design-studio generate wheel-link
```

```
OBC1-J01: OK updated (4 pin(s))
Imported 1 connector(s), 4 pin(s). Generate harnesses again to connect interfaces to the pins.
RW1-J02: OK updated (4 pin(s))
Imported 1 connector(s), 4 pin(s). Generate harnesses again to connect interfaces to the pins.
0 added, 1 changed, 1 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept
2 interfaces and 6 wires checked: 0 error(s)
```

Generate changed `W001` (its cable pins now have the contacts) and left `W002` as it was.

**From a file, for a harness made by hand**, `import-build-data` reads the contact of each cable pin. The headings are `Harness`, `Connector`, `Pin` and `Contact`; `Tool` is optional and sets the crimp tool of that contact part. The file `pin-contacts.csv`:

```
Harness,Connector,Pin,Contact,Tool
W001,W001-P1,1,EX-CONTACT-22,
W001,W001-P1,2,EX-CONTACT-22,
W001,W001-P2,1,EX-CONTACT-24,
W001,W001-P2,2,EX-CONTACT-24,
```

```
harness-design-studio import-build-data heater pin-contacts.csv --dry-run
```

```
Import pin contacts: 4 row(s) read.
row 2: OK contact EX-CONTACT-22
row 3: OK contact EX-CONTACT-22
row 4: OK contact EX-CONTACT-24
row 5: OK contact EX-CONTACT-24
4 added, 0 changed, 0 unchanged, 0 refused.
Dry run: nothing was changed.
```

(`heater` is a project with one harness made by hand, `W001`, with two D-sub connectors and two wires; a harness made by hand has no command line way to make it, so it was made with the program's own functions for this run.) A contact that is not a part of the category *contact* is refused with its row: `row 2: ERROR 'EX-WIRE-SINGLE' is not a contact part of the library (category contact).` The same file imported on the generated harness `W001` of `wheel-link` is refused, and the message says where to set it:

```
Import pin contacts: 2 row(s) read.
row 2: ERROR W001 is made by Generate, which copies the contact from the pin of the device. Set it on the device's pin in the Devices tab (column Cable contact), then Generate again.
row 3: ERROR W001 is made by Generate, which copies the contact from the pin of the device. Set it on the device's pin in the Devices tab (column Cable contact), then Generate again.
0 added, 0 changed, 0 unchanged, 2 refused.
Nothing was changed.
```

**The crimp tool.** In the app (GUI, not run), click a part of the category contact in the project tree (as a Systems engineer press **Show panels** first). The **Inspector** shows the part page with **Crimp tool**; type the tool or its setting (`Tool X, setting 4` is the kind of text meant) and press **Set tool**. Parts cannot be edited anywhere else. From a file, a table with the headings `Part` and `Tool` sets it (`part-tools.csv`):

```
Part,Tool
EX-CONTACT-22,EXAMPLE crimp tool and setting 5
```

```
harness-design-studio import-build-data wheel-link part-tools.csv
```

```
Import part tools: 1 row(s) read.
row 2: OK tool EXAMPLE crimp tool and setting 5
0 added, 1 changed, 0 unchanged, 0 refused.
Build data imported. Generate keeps it; the build sheets show it.
```

(`changed`, because the parts file above had already given `EX-CONTACT-22` another tool.) The parts import itself reads a `Tool` or `Crimp tool` column as well, as the file above does.

## 3. Accessories

An accessory is something that goes on a harness besides its wires and connectors. It has:

| Field | What it is |
| --- | --- |
| **ID** | The name inside the harness, for example `ACC-001`. It cannot be changed once the accessory exists. |
| **Kind** | sleeving, heat shrink, label, backshell or other. |
| **Part** | A part of the library, or none. |
| **On** | A connector or a wire of this harness, or the harness itself. |
| **Position** | Where it goes, in your words, for example `50 mm from the P1 end`. Nothing is computed from it. |
| **Length (mm)** | The length of one piece, optional. |
| **Quantity** | How many pieces, a whole number from 1 to 9999. |
| **Note** | Your remark. |

**In the app** (GUI, not run): in the **Drawings** area, choose the harness and open the **Accessories** tab, the fourth tab on the right of the harness view after **Connectors**. A table lists the accessories (ID, Kind, Part, On, Position, Length (mm), Quantity, Note), and a form with the same fields is below it. An empty harness shows `No accessories yet` and says what accessories are for.

![The Drawings area with the Accessories tab open: a table of two accessories of harness W001, a sleeving on a wire and a heat shrink on a connector, and below it the form with ID, Kind, Part, On, Position, Length, Quantity and Note, and the buttons Add accessory and Change accessory](../img/accessories-tab.png)

- **Add accessory** adds the form as a new accessory. Its **ID** is filled in with the next free one (`ACC-001`, `ACC-002`, ...).
- Select a row to see it in the form, change the form and press **Change accessory**.
- **Delete accessory** removes the selected row. **New accessory** clears the form and the selection.
- Each is one undo step. For a released harness the tab is off and says so.

**From a file.** The headings are `Harness`, `Kind`, `Part`, `Target`, `Position`, `Length (mm)`, `Quantity` and `Note`, and optionally `ID`. `Target` is a connector or a wire of the harness; **empty means the harness itself**. A row without an `ID` is numbered `ACC-001`, `ACC-002`, ... . With an `ID` the file is safe to import again: the row finds its accessory instead of adding one. The file `accessories.csv`:

```
ID,Harness,Kind,Part,Target,Position,Length (mm),Quantity,Note
ACC-001,W001,sleeving,EX-SLEEVE,W001-001,whole wire,,1,
ACC-002,W001,heat_shrink,,W001-P1,50 mm from the P1 end,30,2,part not chosen yet
```

```
harness-design-studio import-build-data wheel-link accessories.csv --dry-run
```

```
Import accessories: 2 row(s) read.
row 2: OK sleeving on W001-001
row 3: OK heat shrink on W001-P1
2 added, 0 changed, 0 unchanged, 0 refused.
Dry run: nothing was changed.
```

The kind is one of `sleeving`, `heat_shrink`, `label`, `backshell` and `other`. A target that is not a connector or a wire of the harness is refused:

```
Import accessories: 1 row(s) read.
row 2: ERROR 'W001-P9' is not a connector or a wire of W001.
0 added, 0 changed, 0 unchanged, 1 refused.
Nothing was changed.
```

## 4. What the outputs then show

Export as usual ([export the outputs](export-the-outputs.md)). The build data does not change a project that does not use it, so the practice project without it still writes 34 files. With the accessories above, `export` writes one more file, `accessories.csv` of the harness:

```
harness-design-studio export wheel-link
```

```
35 files written to wheel-link/outputs (model 75ac89ce46da).
```

(The model hash depends on the project and the tool version; yours differs.)

**The tables show the data only where it is used.**

- `wirelist.csv` gets the columns `Strip A (mm)` and `Strip B (mm)` after the others when **any** wire of the project has a strip length. The wires of the other harnesses then have empty cells.
- `pinouts.csv` and `box_pinouts.csv` get the column `Contact` after `Function` and `Termination` when any pin of the project has a contact.
- A harness with accessories gets `accessories.csv`: `Accessory, Kind, Part, Target, Position, Length (mm), Quantity, Note`, sorted by ID. An empty `Target` means the harness.
- `bom.csv` counts the contact parts and the accessory parts. See the rule in [`OUTPUTS.md`](../OUTPUTS.md#tables).

`harnesses/W001/accessories.csv` (after its `#` stamp line):

```
Accessory,Kind,Part,Target,Position,Length (mm),Quantity,Note
ACC-001,sleeving,EX-SLEEVE,W001-001,whole wire,,1,
ACC-002,heat_shrink,,W001-P1,50 mm from the P1 end,30,2,part not chosen yet
```

The bill of materials has one line per part **and unit**. `ea` counts the connector parts, each contact part once for every pin that has a wire attached, and the accessory parts that have no length (their quantities added). `m` counts the wire parts and the accessory parts that have a length (length in mm times quantity, added, divided by 1000). A part used both ways gets two lines, `ea` first. An accessory with no part adds no line, so `ACC-002` above is in `accessories.csv` and not in the BOM. With one more sleeving of 100 mm, quantity 3, on a wire, the BOM of `W001` holds:

```
EX-SLEEVE,sleeving,,,Braided sleeving (example),pending (example data),1,ea,,W001
EX-SLEEVE,sleeving,,,Braided sleeving (example),pending (example data),0.3,m,,W001
```

**The build workbook always shows the build data**, and a missing value reads `to fill in` ([section 3 of export the outputs](export-the-outputs.md#3-the-build-workbook-sheet-by-sheet)):

- **Cut list**: the columns **Strip A (mm)** and **Strip B (mm)** after **Length (m)**.
- **Connectors**: the columns **Contact** and **Tool** after **Contact size**: the contact part of the pin and the crimp tool of that part. A pin in use without a contact reads `to fill in`.
- **Accessories**: a sheet between **Parts** and **Labels**, with **Done (x)** and the columns of `accessories.csv`. A harness-level target shows as `(harness)`; with none entered the sheet says `No accessories entered.`
- **Start here**: two more `NOTE` lines, **Wires without strip lengths** and **Pins in use without a contact part**, each with the number open and what to do. A `NOTE` does not stop `Ready to build`.

For `W001` of the practice project, whose four wires have strip lengths and whose pins in use have contacts, both lines say `0` and `OK`. The harness `W002` has neither, and its **Start here** says:

| Check | Open | Status | What to do |
| --- | --- | --- | --- |
| Wires without strip lengths | 2 | `NOTE` | Enter the strip length at both ends in the Edit wire tab (or with import-build-data). |
| Pins in use without a contact part | 4 | `NOTE` | Name the contact part of each pin (Devices tab, or Connectors tab of a harness made by hand). |

The independent check reads the new columns, the sheet and the file cell by cell. A file that was changed after the export is reported as before (`out_modified`); a wrong `accessories.csv`, or one for a harness without accessories, is `out_accessories`.

## What Generate does with it

- **Strip lengths** are always kept, like a label or a note. They do not lock the wire.
- **The contact** is copied from the device's pin to the cable connector's pin. On a harness made by hand, Generate leaves the harness alone.
- **Accessories** are kept while the connector or wire they sit on is kept. If Generate cannot keep one, it says so in the finding `locked_data_lost` before you apply, for example `the accessory ACC-001 (sleeving on W001-001)`.
- **A release** locks the harness with its accessories, and freezes the contact and accessory parts like any part it uses ([release a harness](release-a-harness.md)).

## Common mistakes

- **Importing the contacts of a generated harness.** It is refused. Set the contact on the device's pin (Devices tab, or `import-pinout` with a `Cable contact` column) and generate again.
- **A part that is not a contact.** A contact must be a part of the category *contact*. Import the part first.
- **Expecting a clear from an empty cell.** An empty cell leaves a value as it is. Clear it in the app.
- **An accessory on something that is not there.** A project whose accessory names a connector or wire that its harness does not have (for example after a hand edit of a file or a Git merge) is an error, `dangling_accessory`, and `harness-design-studio validate` ends with exit code 1: `Accessory 'ACC-001' in harness 'W001' belongs to 'W001-P9', which is not a connector or a wire of this harness.` Change the target in the **Accessories** tab or the file, or delete the accessory ([troubleshooting](../TROUBLESHOOTING.md)).
- **Expecting a check.** The tool does not check that a strip length is sensible or that a contact fits a connector. That is for the engineer.
- **Working in a stale export.** After an import, generate and export again; `harness-design-studio verify DIR --outputs` says if the files are out of date.

More: [`OUTPUTS.md`](../OUTPUTS.md), [`FILE_FORMAT.md`](../FILE_FORMAT.md).

Next: [export the outputs](export-the-outputs.md), [import data](import-data.md)
