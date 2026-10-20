# Questions and troubleshooting

Short answers. If yours is not here, check the **Problems** tab or the Problems panel (Ctrl+Shift+M; they say what is wrong and how to fix it) and [`HOWTO.md`](HOWTO.md).

## Questions

**Where do I start?** Install it ([`INSTALL.md`](INSTALL.md)), then follow [`LEARNING_PATH.md`](LEARNING_PATH.md): nine short steps, each with the example or template to use and how you know you are done. A one-page summary of commands and keys is in [`CHEATSHEET.md`](CHEATSHEET.md).

**Which example should I start with?** `first-steps` for the tutorial (three units). `minimal-satellite` to see a small but realistic spacecraft and as a starting point to adapt. `small-satellite` to see redundancy and a larger diagram. `flatsat` for a complete bench setup with ground equipment, already generated ([`FLATSAT_EXAMPLE.md`](FLATSAT_EXAMPLE.md)). `blank` for your own design. `harness-design-studio new --list` shows them all. `minimal-satellite`, `flatsat` and the `design-worksheet.md` template are not in the 0.1.0 packages (see [`CHANGELOG.md`](../CHANGELOG.md)): the list shows five examples on 1.0.0, three (`blank`, `first-steps`, `small-satellite`) on 0.1.0.

**I have no data yet. Can I still use the tool?** Yes. Fill in `design-worksheet.md` from the templates (`harness-design-studio templates my-templates`) to decide your units and interfaces on paper, then enter them. Every missing number shows up as *pending* or *not checked* until you supply it; nothing is invented.

**Do I need to know how the tool works inside?** No. [`CONCEPTS.md`](CONCEPTS.md) is enough, and [`GETTING_STARTED.md`](GETTING_STARTED.md) walks you through it.

**Why does it say "pending" and "not checked" everywhere?** Because the tool contains no engineering numbers. Derating factors, wire ratings, EMC rules and part approvals come from your programme; until they are entered, results say so instead of guessing. `harness-design-studio config DIR` lists what is missing. See "Placeholders" in [`CONCEPTS.md`](CONCEPTS.md).

**Can I just use the demo values?** For learning, yes (`harness-design-studio templates DIR` copies them, see [`GETTING_STARTED.md`](GETTING_STARTED.md) part 7). They are not engineering data. Never release a real design with them. A release is refused while the configuration files are marked as placeholders unless you give a written reason, which is kept in the change log.

**Can I edit a generated harness by hand?** Not in the sense of editing a drawing. You change the design (units, interfaces, connectors, values) and generate again. To keep a wire's gauge, type, colour or length, set it in the **Edit wire** tab (Drawings area; [edit a wire](user-manual/edit-a-wire.md), new in 1.4.0): it locks the wire and generation keeps it. Before 1.4.0 this needed `"locked": true` in the harness file (`physical/harnesses/<ID>.json`). A pin choice is kept by locking the pin in the **Devices** tab. A harness that is released is locked; start a new revision to change it.

**What happens when I generate again?** IDs, locked wires and locked pins are kept, released harnesses are never touched, and a report says what was added, changed and removed. Generating twice gives the same result.

**Which interface types exist? Can I add my own?** Seventeen ship with the tool. The baseline for communication is RS-422, RS-485 and CAN, with Ethernet as the alternative for high data rates; the others are power (primary, secondary), SpaceWire, MIL-STD-1553B, LVDS, I2C, analog, thermistor, heater, discrete, pyro, RF coax and ground. They are stored in the project's `logical/interface_types.json`. There is no editor for them in the app yet; a new type is another entry in that file in the same format (see [`FILE_FORMAT.md`](FILE_FORMAT.md)).

**Which connectors does the tool use?** Micro-D 9, 15, 21, 25 and 31 pin for power and data, RJ45 for Ethernet and SMA for RF (see "The standards the tool starts from" in [`CONCEPTS.md`](CONCEPTS.md)). They are example parts; import your approved list to replace them. Older D-sub, MDM, circular and TNC parts stay in the library.

**Can two or more units share one link (a bus)?** Not yet. A link between more than two units is skipped with a warning (D-116 in [`DECISIONS.md`](DECISIONS.md)).

**Does it use the internet?** Never. A test checks it.

**Where do I put the project in Git?** The project folder is the repository (or a folder in it). Everything in it is plain JSON in a fixed format, so diffs show real changes only. `.gitignore` is written for you. See [`HOWTO.md`](HOWTO.md) section 15.

**What do I commit, and what not?** Commit the whole project folder. `outputs/` can be committed (reviewers like to see it) or ignored; it is always safe to delete and regenerate.

**How do I know a printed drawing matches the design?** Every output carries the tool version and a *model hash* (12 characters). `harness-design-studio verify DIR --outputs` checks the files against the design.

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
| On Ubuntu the app does not start; a message about `xcb`, `libEGL` or `libxkbcommon` | System libraries are missing. `sudo apt install libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0`. |
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
