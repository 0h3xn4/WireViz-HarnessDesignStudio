# Harness Design Studio

An offline desktop tool for the electrical harnesses of a spacecraft, made for systems engineers and for electrical / AIT engineers. You describe the **devices** (computer, power unit, reaction wheel ...) and the **interfaces** between them; the tool generates the harnesses (connectors, pins, wires, with a reason for each choice), checks them, and writes a build workbook, wire lists and test tables. The same design always gives byte-identical files, so Git diffs show real changes only. It never uses the network.

> **Honest limits.** Written mainly by an AI (Claude, through Claude Code); the owner set the requirements and approved the decisions and releases. No other person has reviewed it independently ([`compliance/DEVIATIONS.md`](compliance/DEVIATIONS.md)), no compliance with any standard is claimed, and no engineering values are supplied until your project enters them (results then say *pending* or *not checked*). It lives in a fork of [WireViz](https://github.com/wireviz/WireViz) but shares no code with it ([`../README.md`](../README.md#original-wireviz-readme)). The latest release, the status and the release history: [`docs/STATUS.md`](docs/STATUS.md).

## The 10-minute tour

You need the tool installed ([`docs/INSTALL.md`](docs/INSTALL.md); `sudo apt install ./harness-design-studio_<version>_amd64.deb` on Ubuntu). A test runs every command below, in this order, and checks the lines quoted.

1. **Make a practice project** (2 minutes): a folder of small JSON files with three devices and two interfaces (power and RS-422). The first command prints the version; `harness` is a short name for the same command.

   ```
   harness-design-studio --version
   harness-design-studio new wheel-link --template first-steps
   harness-design-studio validate wheel-link
   ```

2. **Generate the harnesses** (1 minute). You should see `2 added, 0 changed, 0 unchanged, 0 removed, 0 frozen (released); 0 locked pin(s) kept`. Run it again: it says `0 added, 0 changed, 2 unchanged`, because the same design gives the same result.

   ```
   harness-design-studio generate wheel-link
   harness-design-studio generate wheel-link
   ```

3. **Let the tool check its own work** (2 minutes). `verify` re-reads the harnesses without the generator's help; `drc` prints the design rule report (errors, warnings, and the checks that could not run because a number is missing).

   ```
   harness-design-studio verify wheel-link
   harness-design-studio drc wheel-link
   ```

4. **Write the outputs** (1 minute). You should see `34 files written to wheel-link/outputs`: the build workbook of each harness (`harnesses/W001/W001_build.xlsx`), wire lists, pinouts, the bill of materials, test tables and the report of step 3. The PDF drawings only with `--drawings`.

   ```
   harness-design-studio export wheel-link
   ```

5. **Open it in the app** (4 minutes). Start **Harness Design Studio**, choose **File > Open project…** and pick `wheel-link`. The first start asks *Who are you working as?* (**View > Role** changes it). A Systems engineer lands on the **Next step** page, which names one thing to do; an Electrical / AIT engineer lands on the diagram. Look at **Model** (the diagram), **Checks** (what passed and what is *not checked*, and why) and, as an Electrical / AIT engineer, **Drawings** (a harness, and its **Why** tab with the reason for every choice).

That is the whole idea. The full tutorial with the output of every command is [`docs/GETTING_STARTED.md`](docs/GETTING_STARTED.md) (45 minutes); [`docs/LEARNING_PATH.md`](docs/LEARNING_PATH.md) is the route in nine steps.

## Documentation

| You want to | Go to |
| --- | --- |
| do a task (draw, generate, edit a wire, import, devices, export, release, Git, CI) | [`docs/user-manual/`](docs/user-manual/README.md): one page per task |
| look something up | [`docs/CLI.md`](docs/CLI.md), the user guide ([`docs/guide/USER_GUIDE.md`](docs/guide/USER_GUIDE.md), **F1** in the app), [`docs/CHEATSHEET.md`](docs/CHEATSHEET.md), [`docs/GLOSSARY.md`](docs/GLOSSARY.md) |
| fix a problem | [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md), [`docs/FAQ.md`](docs/FAQ.md) |
| supply engineering values or review | [`docs/CONFIG.md`](docs/CONFIG.md), [`docs/PLACEHOLDERS.md`](docs/PLACEHOLDERS.md), [`docs/RULES.md`](docs/RULES.md), [`docs/OUTPUTS.md`](docs/OUTPUTS.md) |
| see the other examples and templates | [`docs/examples/README.md`](docs/examples/README.md) (`harness-design-studio new --list`; five projects); the CSV and script templates: `harness-design-studio templates my-templates` |
| see what changed | [`CHANGELOG.md`](CHANGELOG.md), [`docs/STATUS.md`](docs/STATUS.md) |

A project is a folder of small JSON files; put it in Git ([`docs/FILE_FORMAT.md`](docs/FILE_FORMAT.md)). Every document is listed in [`docs/README.md`](docs/README.md) and [`../docs/README.md`](../docs/README.md).

## For developers

Clean-room: never copy code from `../src/wireviz` (GPL-3.0). Start with [`../CONTRIBUTING.md`](../CONTRIBUTING.md), [`docs/developer/`](docs/developer/README.md) and [`CLAUDE.md`](CLAUDE.md); release procedure: [`docs/RELEASE.md`](docs/RELEASE.md).

```
python3.14 -m venv .venv && . .venv/bin/activate && pip install -e ".[gui,dev]"
pytest -n auto -m "not perf" && pytest -m perf   # tests; add --cov for the 90% core coverage gate
ruff format . && ruff check . && mypy
python -m tools.release_check --quick
```
