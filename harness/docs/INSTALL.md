# Install

The tool runs on **Ubuntu 24.04 or newer** (64-bit, x86). It needs no network, no administrator account for the per-user install, and no other software to be installed first (Python and Qt are inside the package).

## Contents

- [Before you start (two minutes)](#before-you-start-two-minutes)
- [Get the package](#get-the-package)
- [A. The `.deb` package (recommended)](#a-the-deb-package-recommended)
- [B. The `.tar.gz` without administrator rights](#b-the-targz-without-administrator-rights)
- [Check that it works](#check-that-it-works)
- [Your first five minutes after installing](#your-first-five-minutes-after-installing)
- [If the app does not start](#if-the-app-does-not-start)
- [C. Run from source (developers)](#c-run-from-source-developers)
- [Where things are stored](#where-things-are-stored)

Pick **one** of the three ways. If you are unsure, use A.

**Which version do you have?** The five examples (`minimal-satellite` and `flatsat` among them), the `design-worksheet.md` template, the wiring-diagram drawing with wire colours and *Edit > Wire colours...* are on `master` and are **not** in the released 0.1.0 packages (see [`CHANGELOG.md`](../CHANGELOG.md#unreleased-after-010)). `harness --version` prints `0.1.0` for both. To tell them apart run `harness new --list`: a newer build lists five examples, the 0.1.0 packages list three (`blank`, `first-steps`, `small-satellite`). Way C has them when you clone `master`. The other pages of this manual describe the newer build.

| | You are | Way |
| --- | --- | --- |
| **A** | an engineer who wants to use the tool | install the `.deb` package |
| **B** | the same, without administrator rights | unpack the `.tar.gz` and run `install.sh` |
| **C** | a developer or you want the newest source | run it from source |

## Before you start (two minutes)

Check that your machine is supported. Open a terminal (Ctrl+Alt+T) and run:

```
lsb_release -rs          # must print 24.04 or higher
uname -m                 # must print x86_64
```

If the first command is not found, run `cat /etc/os-release` and read `VERSION_ID`. Ubuntu 22.04 and older are not supported. Other Linux distributions, macOS and Windows are not supported either.

You also need about 500 MB of free disk space for the program (`df -h ~` shows it) and a screen of at least 1280 x 720 for the app. The command line tool works without a screen.

## Get the package

You need one file, either `harness-design-studio_<version>_amd64.deb` (way A) or `harness-design-studio-<version>-linux-<arch>.tar.gz` (way B). Ask your tool administrator, or take it from one of these places:

- the **Releases** page of the project's repository, when the packages are attached to the release (look for the newest version number). The release record says that attaching the files to the release page is up to the repository owner (`compliance/SIGNOFF.md`, section Publication); if the page lists no `.deb` or `.tar.gz`, use one of the other two places or way C;
- the build artifacts of a CI run (Actions, then the run, then *Artifacts*): the artifact is called `harness-design-studio-ubuntu-24.04` and holds the `.deb`, the `.tar.gz` and the software bill of materials and licence report (no checksum file).

You can also build it yourself (way C, last section). That route needs no release files at all.

Copy the file to the machine. It never needs to reach the network.

**Check the file** if it came over a network or on a stick. The release lists a SHA-256 checksum for each file (`compliance/evidence/release_<version>_SHA256SUMS` in the repository). Compare:

```
sha256sum harness-design-studio_<version>_amd64.deb
```

The printed value must be the same as the one in the list. If it differs, do not install the file. The packages are not signed (this is a recorded deviation, `compliance/DEVIATIONS.md` T-19), so the checksum is the only check you have. A package built by CI is built again on another machine, so its checksum can differ from the recorded one. For such a package compute the checksum yourself (`sha256sum`) on the machine that built it and compare it with the file you received; the recorded list applies to the packages named in it.

## A. The `.deb` package (recommended)

```
sudo apt install ./harness-design-studio_<version>_amd64.deb
```

(Use `./` in front of the name; without it `apt` looks in its online lists.) This installs the program into `/opt/harness-design-studio` and puts two commands on your path:

- `harness-design-studio`: the app (also in the application menu as **Harness Design Studio**).
- `harness`: the command line tool.

Check it:

```
harness --version
```

```
harness 0.1.0
```

Remove it later with `sudo apt remove harness-design-studio`. Upgrade by installing the newer `.deb` the same way.

## B. The `.tar.gz` without administrator rights

```
tar xzf harness-design-studio-<version>-linux-<arch>.tar.gz
cd harness-design-studio
./install.sh
```

This installs for **your user only**, into `~/.local/opt/harness-design-studio`, and adds links in `~/.local/bin` and an entry in your application menu.

If `install.sh` ends with a note that `~/.local/bin` is not on your PATH, the commands `harness-design-studio` and `harness` are not found yet. Fix it once:

```
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
. ~/.bashrc
```

(or log out and in). Until then you can start the app from the application menu or `~/.local/bin/harness-design-studio`.

Other options of `install.sh`: `sudo ./install.sh --system` installs for everyone into `/usr/local/lib/harness-design-studio`; `--prefix FOLDER` chooses the folder. Remove with `./uninstall.sh` (or `sudo ./uninstall.sh --system`); it removes only what the installer put there. The installer writes a file `.harness-design-studio-install` into the install folder that lists what it installed; it never replaces or removes a `cli`, `LICENSES`, `_internal` or `harness-design-studio` folder that is not in that list, and it refuses to install into the folder the package was unpacked from. Files installed as `root` belong to `root`.

If `install.sh` says that a folder "was not installed by this installer", the install folder holds one of these names from something else (or from an older installer, which wrote no list). Choose another `--prefix`, or move that folder away first.

Run `install.sh` from the **unpacked package**. Run from the source tree it refuses and prints: `This folder (...) has no built program, so there is nothing to install.`

## Check that it works

For ways A and B (the installed program):

```
harness --version          # prints the version
harness-design-studio --selftest    # opens the editor offscreen, makes a project, generates, exports, and prints "selftest ok"
```

`--selftest` exists only in the installed program (`harness-design-studio`). When you run from source (way C) the app command is `harness-gui`, which does not know the flag and simply starts the app. From source, check with `harness --version`, then the five-minute check below, and `pytest` if you installed the `dev` extras.

Then start **Harness Design Studio** from the application menu. The first start opens a sample project and a short tour.

**What you should see:** a window with the title *Harness Design Studio*, a diagram of boxes (units) joined by lines (interfaces) in the middle, tabs such as *Problems* at the bottom or side, and the menus **File**, **Edit**, **View**, **Help**. If the window is too small or the text is hard to read, see *If the app does not start* below. **F1** opens the user guide.

## Your first five minutes after installing

```
harness new wheel-link --template first-steps
harness generate wheel-link
harness drc wheel-link
```

Then open `wheel-link` in the app (**File > Open project...**). If this works, the installation is complete. Continue with [`LEARNING_PATH.md`](LEARNING_PATH.md) (the whole route) or [`GETTING_STARTED.md`](GETTING_STARTED.md) (the first step in detail).

## If the app does not start

The app needs a few system libraries that every normal Ubuntu desktop has. On a minimal install (a container, a server image) add them:

```
sudo apt install libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0
```

The `.deb` asks `apt` for these itself. More help: [`FAQ.md`](FAQ.md).

| You see | Do this |
| --- | --- |
| `E: Unable to locate package ./harness-design-studio_...` or `apt` cannot find the file | Run the command in the folder that holds the file, and keep the `./` in front of the name. |
| `dpkg: dependency problems` | Run `sudo apt install -f`. It installs the missing system libraries from your normal Ubuntu sources (this is the only step that may need network). |
| `harness: command not found` after the `.tar.gz` install | `~/.local/bin` is not on your PATH; see way B above. |
| The app window is blank or the app closes at once | With way A or B, run `harness-design-studio --selftest` in a terminal. If it prints an error about `xcb`, `libEGL` or `libxkbcommon`, install the libraries above. |
| You are connected by SSH and the app does not open | The app needs a screen. Use the `harness` command line tool over SSH, or start the app on the machine itself. |
| `install.sh` says `This folder (...) has no built program, so there is nothing to install.` | You ran it from the source tree. Run it from the unpacked `.tar.gz` folder. |

## C. Run from source (developers)

You need Python 3.12 or newer (Ubuntu 24.04 has it) and the Qt libraries above.

```
sudo apt install python3-venv git libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0
git clone <the repository> && cd <the repository>/harness
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[gui,dev]"
```

Run the app with `harness-gui`, the command line tool with `harness`. Run the tests with `pytest` (they run offscreen). **Without network:** build a wheelhouse once on a connected machine with `python -m tools.vendor`, copy it over and install with `pip install --no-index --find-links wheelhouse -e ".[gui,dev]"`.

Build the packages yourself:

```
python -m tools.build_installer      # dist/harness-design-studio/ and the .tar.gz
python -m tools.build_deb            # dist/harness-design-studio_<version>_amd64.deb
dist/harness-design-studio/harness-design-studio --selftest
```

The release procedure and the clean-machine check are in [`RELEASE.md`](RELEASE.md).

## Where things are stored

| What | Where |
| --- | --- |
| Your projects | wherever you saved them (a folder per project) |
| App settings (theme, scale, last project) | `~/.config/HarnessDesigner/HarnessDesigner.ini` (no design data) |
| Autosave of an open project | `<project>/.harness-recovery/` (offered for restore after a crash; ignored by Git) |

Next: [`GETTING_STARTED.md`](GETTING_STARTED.md).
