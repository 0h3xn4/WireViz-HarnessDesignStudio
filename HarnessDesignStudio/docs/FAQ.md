# Questions and troubleshooting

Short answers. If yours is not here, check the **Problems** tab or the Problems panel (Ctrl+Shift+M; they say what is wrong and how to fix it) and [`HOWTO.md`](HOWTO.md).

## Questions

**Where do I start?** Install it ([`INSTALL.md`](INSTALL.md)), then follow [`LEARNING_PATH.md`](LEARNING_PATH.md): nine short steps, each with the example or template to use and how you know you are done. A one-page summary of commands and keys is in [`CHEATSHEET.md`](CHEATSHEET.md).

**Which example should I start with?** `first-steps` for the tutorial (three units). `minimal-satellite` to see a small but realistic spacecraft and as a starting point to adapt. `small-satellite` to see redundancy and a larger diagram. `flatsat` for a complete bench setup with ground equipment, already generated ([`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md)). `blank` for your own design. `harness-design-studio new --list` shows them all. `minimal-satellite`, `flatsat` and the `design-worksheet.md` template are not in the 0.1.0 packages (see [`CHANGELOG.md`](../CHANGELOG.md)): the list shows five examples on 1.0.0, three (`blank`, `first-steps`, `small-satellite`) on 0.1.0.

**I have no data yet. Can I still use the tool?** Yes. Fill in `design-worksheet.md` from the templates (`harness-design-studio templates my-templates`) to decide your units and interfaces on paper, then enter them. Every missing number shows up as *pending* or *not checked* until you supply it; nothing is invented.

**Do I need to know how the tool works inside?** No. [`CONCEPTS.md`](CONCEPTS.md) is enough, and [`GETTING_STARTED.md`](GETTING_STARTED.md) walks you through it.

**Why does it say "pending" and "not checked" everywhere?** Because the tool contains no engineering numbers. Derating factors, wire ratings, EMC rules and part approvals come from your programme; until they are entered, results say so instead of guessing. `harness-design-studio config DIR` lists what is missing. See "Placeholders" in [`CONCEPTS.md`](CONCEPTS.md).

**Can I just use the demo values?** For learning, yes (`harness-design-studio templates DIR` copies them, see [`GETTING_STARTED.md`](GETTING_STARTED.md) part 7). They are not engineering data. Never release a real design with them. A release is refused while the configuration files are marked as placeholders unless you give a written reason, which is kept in the change log.

**Can I create a project completely from scratch, with no example and no interface table?** Yes. **File > New project…** with the example *blank* gives an empty project with starter parts and no unit. The empty diagram says where to start: press **Add a device** (Ctrl+Shift+N), or **Add** in the project panel, or pick a kind of unit under **Edit > Add unit**. Then connect the units ([draw the design](user-manual/draw-the-design.md)), define devices down to each pin ([define a device](user-manual/define-a-device.md)), or, since 1.5.0, make a harness with no interface at all: **New harness…** (Ctrl+Shift+H), its connectors in the **Connectors** tab and its wires in **Edit wire** ([build a harness by hand](user-manual/build-a-harness-by-hand.md)). Generate leaves a harness you made alone.

**Can I edit a generated harness by hand?** Not in the sense of editing a drawing. You change the design (units, interfaces, connectors, values) and generate again. To keep a wire's gauge, type, colour or length, set it in the **Edit wire** tab (Drawings area; [edit a wire](user-manual/edit-a-wire.md), new in 1.4.0): it locks the wire and generation keeps it. Before 1.4.0 this needed `"locked": true` in the harness file (`physical/harnesses/<ID>.json`). A pin choice is kept by locking the pin in the **Devices** tab. A harness that is released is locked; start a new revision to change it.

**What happens when I generate again?** IDs, locked wires and locked pins are kept, so are the wires you drew or edited in the **Edit wire** tab, your wire, connector and harness labels, strip lengths, accessories (while the connector or wire they sit on is kept), the cable contact of a unit's pin and the groups you made; released harnesses are never touched, and a report says what was added, changed and removed (and, as *locked_data_lost*, anything it could not keep because its interface is gone). Generating twice gives the same result.

**Can two wires go to one pin?** Yes, since 1.4.0: draw the wire in the **Edit wire** tab. The design rule *Several wires on one pin* (`pin-shared`, a warning) names each such pin so a reviewer sees it, and the independent check says *pin_shared* (a warning) instead of failing when a wire you drew is one of them ([edit a wire](user-manual/edit-a-wire.md)).

**Can I give a pin a name for what it does, and put a label on a connector or a harness?** Yes, since 1.4.0. A pin has a free-text *function* (Devices tab, column *Function*; the pinout import reads a *Function* column). A box connector has a *Label* on its card in the Devices tab; the harness and its cable connectors have one in the *Labels* section of the **Edit wire** tab. `labels.csv` prints them; the pinout lists get *Function* and *Termination* columns only when a pin has one.

**Can I reuse a device in another project?** Yes, since 1.4.0. In the **Devices** tab, **Save to library…** writes the device with its connectors, pinouts, parts and interface types to a device library file (JSON); **Add from library…** in the other project adds it, never replacing anything (a taken ID gets the next free one, `GYRO1-2`). On the command line: `export-devices` and `import-devices` ([define a device](user-manual/define-a-device.md#use-a-device-in-another-project)).

**Can I load a parts list exported from InvenTree?** Yes, as a file: the parts import reads the `.csv`, `.tsv`, `.json` or `.xlsx` export of InvenTree (the `IPN` column becomes the part ID). There is no live connection to a server; the tool never uses the network. You still say what the approval values mean ([import data](user-manual/import-data.md)).

**Which interface types exist? Can I add my own?** Seventeen ship with the tool. The baseline for communication is RS-422, RS-485 and CAN, with Ethernet as the alternative for high data rates; the others are power (primary, secondary), SpaceWire, MIL-STD-1553B, LVDS, I2C, analog, thermistor, heater, discrete, pyro, RF coax and ground. They are stored in the project's `logical/interface_types.json`. In the app, **New interface type…** (in the **Devices** tab, from the Fill dialog) adds one with its signals; or add another entry to that file in the same format (see [`FILE_FORMAT.md`](FILE_FORMAT.md)).

**Which connectors does the tool use?** Micro-D 9, 15, 21, 25 and 31 pin for power and data, RJ45 for Ethernet and SMA for RF (see "The standards the tool starts from" in [`CONCEPTS.md`](CONCEPTS.md)). They are example parts; import your approved list to replace them. Older D-sub, MDM, circular and TNC parts stay in the library.

**Can two or more units share one link (a bus)?** Not yet. A link between more than two units is skipped with a warning (D-116 in [`DECISIONS.md`](DECISIONS.md)).

**Does it use the internet?** Never. A test checks it.

**Where do I put the project in Git?** The project folder is the repository (or a folder in it). Everything in it is plain JSON in a fixed format, so diffs show real changes only. `.gitignore` is written for you. See [`HOWTO.md`](HOWTO.md) section 15.

**What do I commit, and what not?** Commit the whole project folder. `outputs/` can be committed (reviewers like to see it) or ignored; it is always safe to delete and regenerate.

**How do I know a printed sheet or drawing matches the design?** Every output carries the tool version and a *model hash* (12 characters); the build workbook has it in the footer of every printed sheet. `harness-design-studio verify DIR --outputs` checks the files against the design.

**What do I build a harness from?** From the build workbook: `outputs/harnesses/<ID>/<ID>_build.xlsx`, one Excel file for each harness (new in 1.7.0). Its first sheet says whether the harness is ready to build and what is missing; the others are the cut list, one block for every connector, the parts, the labels and a test sheet with empty columns for the result. Work on a copy of it, not on the file in `outputs/`. See [export the outputs](user-manual/export-the-outputs.md).

**Where are the PDF drawings of the harnesses?** Since 1.7.0 `harness-design-studio export DIR` does not write them unless you add `--drawings` (in the app: tick **Include the PDF drawings** in the Export window). The block diagram and the harness overview are always written. In 1.6.0 and earlier the drawings were always written.

**Does the build workbook say the strip length, the contact and the crimp tool?** Yes, when you have entered them (new in 1.7.0): the strip length of each wire end on the cut list, the contact and the crimp tool of each pin on the connector blocks, and a sheet *Accessories* for sleeving, heat shrink, labels and backshells. What is not entered reads `to fill in`. The tool sets none of them itself and checks none ([enter the build data](user-manual/enter-the-build-data.md), [what the workbook holds](user-manual/export-the-outputs.md#what-the-build-workbook-holds-and-what-it-does-not)).

**How do I enter strip lengths for many wires?** Select the wires in the *Edit wire* tab and type **Strip A (mm)** and **Strip B (mm)**, or press **Apply strip lengths to all wires of this harness**; or import a table with `harness-design-studio import-build-data DIR strip-lengths.csv --dry-run` ([enter the build data](user-manual/enter-the-build-data.md#1-strip-lengths)).

**Why is the contact of a pin of a generated harness greyed out?** Generate copies it from the pin of the unit. Set it in the *Devices* tab, column *Cable contact* (press **Contact** to show it), and generate again. On a harness you made by hand you set it on the cable connector's own pin.

**Where is the user guide?** In the app: **F1**. As a file: [`guide/USER_GUIDE.md`](guide/USER_GUIDE.md).

**How do I get the dark theme?** Open **Settings** (Ctrl+,), section **Appearance**, and choose **Theme**: *Follow the system*, *Light* or *Dark*. **View > Theme** does the same. The window changes at once.

**The animations bother me.** Tick **Reduce motion** under **Settings > Appearance** (or **View > Reduce motion**). Menus, lists and tooltips then stop fading and sliding.

**Can I paste from Excel?** Yes, into the **Units** and **Interfaces** tables of the left panel (Ctrl+Shift+J, Ctrl+Shift+T): select the first cell, press Ctrl+V. The block fills the rows that exist and is one undo step. A new unit or interface does not come from a paste: use the **Add** button, **Ctrl+I**, or **File > Import > Import interfaces…**.

**What does "Offline" in the status bar mean?** The program works offline: nothing leaves this computer, and there is no account and no update check.

**Where does the app keep my settings?** **Settings > About** names the file. It holds the theme, the interface size and your other choices, never design data. On Ubuntu it is `~/.config/HarnessDesigner/HarnessDesigner.ini`.

## Problems

| You see | Why and what to do |
| --- | --- |
| `harness: command not found` after `install.sh` | `~/.local/bin` is not on your PATH. Run `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && . ~/.bashrc`, or log out and in. |
| On Ubuntu the app does not start; a message about `xcb`, `libEGL` or `libxkbcommon` | System libraries are missing. From 1.5.0 the packaged app names the missing library and the `sudo apt install` line itself (`harness-design-studio-gui --check-system` runs only that check); on a source install run `sudo apt install libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0`. |
| The window is tiny or the text is too small or large | **Settings > Appearance > Interface size** or **View > Interface size** (the first size follows your screen; changing it takes about a second). The settings file is named in **Settings > About** (on Ubuntu `~/.config/HarnessDesigner/HarnessDesigner.ini`); delete it to reset. |
| *Read-only* banner | The project was saved by a newer tool version, is open in another window, or its folder cannot be locked for editing (for example read-only media). Install the newer tool, close the other window, or copy the project to a folder you can write to. Nothing was changed. |
| *Project already open* | Another window or session has it open. Close it there, or choose **Open read-only**. A lock left by a crashed session on the same machine is taken over automatically, also after a restart. A lock from another computer is respected: the message names the lock file to delete if you are sure nobody has the project open. |
| *This project has problems* (recovery view) | Some files could not be loaded; everything else did. **Save salvaged copy** writes a clean copy. The original is protected and never overwritten. |
| *Unsaved changes found* at start | The last session ended before saving. **Restore** brings your last edits back. |
| `harness-design-studio new` says the folder is not empty | Choose a folder that does not exist yet (or is empty). It never overwrites. |
| `harness-design-studio generate` says *not saved* | The project has errors. Run `harness-design-studio validate DIR` and fix what it prints. |
| A wire gauge says *pending* | A value is missing. `harness-design-studio config DIR` says which; a gauge also needs the interface's **Max current** and the segment lengths. |
| `harness-design-studio release` says *blocked* | Each reason is printed in words. Typically a gauge or length is missing, an error is open, or the configuration files are still placeholders (review them and set `"placeholder": false`, or give a reason with `--accept-placeholders`), or a part is not approved (approve it in the parts list, or give a reason with `--accept-unapproved-parts`). |
| *Outputs out of date* (status chip or banner) | The design changed since the last export. Export again. |
| *Blocked because it touches released items* | The harness is released, and so are the parts, interface types and configuration values it uses. An edit, `harness-design-studio import-parts` or `harness-design-studio config` that would change them is refused. Start a new revision (`harness-design-studio revise`), make the change, release again. |
| `import-netlist` says a file is not a netlist | It must be KiCad's `.net` (S-expression) or XML export, not a `.kicad_sch`. |
| `kicad-cli` cannot load a library | A KiCad installation problem. Export the netlist from the schematic editor instead (File > Export > Netlist). |
| An import says *row N* has a problem | Nothing was applied. Fix the row; the message says what is wrong. Use `--dry-run` to check first. |
| Merge conflict in a project file | Open the file, resolve the markers like in any text file, then `harness-design-studio check DIR` finds leftovers. |
| Exit code 2 from `harness-design-studio` | A usage error, or an unreadable project (including a project with damaged files: `harness-design-studio validate DIR` lists them). The message says which. Exit 1 means the project has errors or a step is blocked; 0 is success; 130 means you pressed Ctrl-C. |

## Still stuck

Run `harness-design-studio validate DIR` and `harness-design-studio drc DIR` and read the messages: each says what is wrong and how to fix it. Include their output when you ask for help, and check it first if the project is confidential: the messages name units, interfaces and parts.

Next: [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md), [`GLOSSARY.md`](GLOSSARY.md), [user manual](user-manual/README.md).
