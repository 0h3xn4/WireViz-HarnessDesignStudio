# Install

The tool runs on **Ubuntu 24.04 or newer** (64-bit, x86) and, from version 1.2.0, also on **Windows 10 and 11** (64-bit) and **macOS 13 or newer** (Apple Silicon and Intel). It needs no network, no administrator account for the per-user install, and no other software to be installed first (Python and Qt are inside the package). Version 1.1.0 and older are packaged for Ubuntu only; the Windows and macOS sections below describe the packages from 1.2.0. The newest release is 1.3.0 (2026-10-20), the one with the new user interface; the file names are listed under [Get the package](#get-the-package). None of the packages is signed.

## Contents

- [Before you start (two minutes)](#before-you-start-two-minutes)
- [Get the package](#get-the-package)
- [A. The `.deb` package (recommended)](#a-the-deb-package-recommended)
- [B. The `.tar.gz` without administrator rights](#b-the-targz-without-administrator-rights)
- [Check that it works](#check-that-it-works)
- [Your first five minutes after installing](#your-first-five-minutes-after-installing)
- [If the app does not start](#if-the-app-does-not-start)
- [C. Run from source (developers)](#c-run-from-source-developers)
- [D. Windows (from 1.2.0)](#d-windows-from-120)
- [E. macOS (from 1.2.0)](#e-macos-from-120)
- [Where things are stored](#where-things-are-stored)

Pick **one** way. On Ubuntu, if you are unsure, use A. On Windows use D, on a Mac use E.

**Which version do you have?** Run `harness-design-studio --version`. These pages describe the command names that come after version 1.0.0: the command line tool is `harness-design-studio`, the editor `harness-design-studio-gui`, and `harness` is kept as a short alias of the command line tool. The packages of 0.1.0 and 1.0.0 only know the short name `harness` for the command line tool (their `harness-design-studio` is the editor), so type `harness` instead of `harness-design-studio` and `harness-design-studio --selftest` instead of `harness-design-studio-gui --selftest` there. These pages describe version 1.0.0 and later. If you still have the 0.1.0 packages, they lack the five examples (`minimal-satellite` and `flatsat` are new), the `design-worksheet.md` template, the wiring-diagram drawing with wire colours and *Edit > Wire colours...*: `harness-design-studio new --list` shows three examples (`blank`, `first-steps`, `small-satellite`) instead of five. See [`CHANGELOG.md`](../CHANGELOG.md) for what changed.

| | You are | Way |
| --- | --- | --- |
| **A** | an engineer who wants to use the tool | install the `.deb` package |
| **B** | the same, without administrator rights | unpack the `.tar.gz` and run `install.sh` |
| **C** | a developer or you want the newest source | run it from source |
| **D** | on Windows 10 or 11 (from 1.2.0) | run the setup program, or extract the portable `.zip` |
| **E** | on a Mac, macOS 13 or newer (from 1.2.0) | open the `.dmg` and drag the app to Applications |

## Before you start (two minutes)

On Windows and macOS go straight to [D](#d-windows-from-120) or [E](#e-macos-from-120); they have their own checks. On Ubuntu, check that your machine is supported. Open a terminal (Ctrl+Alt+T) and run:

```
lsb_release -rs          # must print 24.04 or higher
uname -m                 # must print x86_64
```

If the first command is not found, run `cat /etc/os-release` and read `VERSION_ID`. Ubuntu 22.04 and older are not supported. Other Linux distributions are not supported either (Windows and macOS: see D and E, from version 1.2.0).

You also need about 500 MB of free disk space for the program (`df -h ~` shows it) and a screen of at least 1280 x 720 for the app. The command line tool works without a screen.

## Get the package

You need one file, either `harness-design-studio_<version>_amd64.deb` (way A), `harness-design-studio-<version>-linux-<arch>.tar.gz` (way B), `harness-design-studio-<version>-windows-x86_64-setup.exe` or `harness-design-studio-<version>-windows-x86_64.zip` (way D) or `harness-design-studio-<version>-macos-arm64.dmg` / `harness-design-studio-<version>-macos-x86_64.dmg` (way E). Ask your tool administrator, or take it from one of these places:

- the **Releases** page of the project's repository (look for the newest version number). Version 1.3.0 (tag `v1.3.0`, published 2026-10-20) has these seven files attached; the release workflow (`.github/workflows/release.yml`) attaches them when a tag `vX.Y.Z` is pushed:

  | File | For | Way |
  | --- | --- | --- |
  | `harness-design-studio_1.3.0_amd64.deb` | Ubuntu 24.04 and newer, 64-bit | A |
  | `harness-design-studio-1.3.0-linux-x86_64.tar.gz` | Linux, without administrator rights | B |
  | `harness-design-studio-1.3.0-windows-x86_64-setup.exe` | Windows 10 and 11, 64-bit, the setup program | D |
  | `harness-design-studio-1.3.0-windows-x86_64.zip` | Windows 10 and 11, 64-bit, portable | D |
  | `harness-design-studio-1.3.0-macos-arm64.dmg` | macOS 13 or newer, Apple Silicon | E |
  | `harness-design-studio-1.3.0-macos-x86_64.dmg` | macOS 13 or newer, Intel | E |
  | `SHA256SUMS` | the SHA-256 checksum of each of the six packages | |

  Versions 1.0.0 and 1.1.0 have only the `.deb`, the `.tar.gz` and a `SHA256SUMS` file; 1.2.0 has the same six packages as 1.3.0. The release record (`compliance/SIGNOFF.md`, the *Publication* sections) says how each version was published. If the page of the version you want lists no package, use one of the other places or way C;
- the build artifacts of a CI run (Actions, then the run, then *Artifacts*): the artifact `harness-design-studio-ubuntu-24.04` of the CI run holds the `.deb`, the `.tar.gz` and the software bill of materials and licence report (no checksum file); the run of the workflow `harness-design-studio packages (Windows, macOS)` on a branch `pkg/...` keeps the Windows and macOS packages as the artifacts `harness-design-studio-windows-x86_64`, `harness-design-studio-macos-arm64` and `harness-design-studio-macos-x86_64`. Such a build is made again on another machine and is not the file of a release.

You can also build it yourself (way C, last section). That route needs no release files at all.

Copy the file to the machine. It never needs to reach the network.

**Check the file** if it came over a network or on a stick. The release lists a SHA-256 checksum for each file (the `SHA256SUMS` file on the release page, one file for all packages of a release from 1.2.0, and `compliance/evidence/release_<version>_SHA256SUMS` in the repository for every release from 0.1.0 to 1.3.0). Compare:

```
sha256sum harness-design-studio_<version>_amd64.deb
```

(On Windows: `Get-FileHash <file> -Algorithm SHA256` in PowerShell; on macOS: `shasum -a 256 <file>`.)

The printed value must be the same as the one in the list. If it differs, do not install the file. The packages are not signed (this is a recorded deviation, `compliance/DEVIATIONS.md` T-19), so the checksum is the only check you have. A package built by CI is built again on another machine, so its checksum can differ from the recorded one. For such a package compute the checksum yourself (`sha256sum`) on the machine that built it and compare it with the file you received; the recorded list applies to the packages named in it.

## A. The `.deb` package (recommended)

```
sudo apt install ./harness-design-studio_<version>_amd64.deb
```

(Use `./` in front of the name; without it `apt` looks in its online lists.) This installs the program into `/opt/harness-design-studio` and puts three commands on your path:

- `harness-design-studio-gui`: the app (also in the application menu as **Harness Design Studio**).
- `harness-design-studio`: the command line tool.
- `harness`: a short alias of the command line tool (the same program). Existing scripts that call `harness` keep working.

The names are the same as in a source or `pip` install (way C).

Check it:

```
harness-design-studio --version
```

```
harness 1.3.0
```

Remove it later with `sudo apt remove harness-design-studio`. Upgrade by installing the newer `.deb` the same way.

## B. The `.tar.gz` without administrator rights

```
tar xzf harness-design-studio-<version>-linux-<arch>.tar.gz
cd harness-design-studio
./install.sh
```

This installs for **your user only**, into `~/.local/opt/harness-design-studio`, and adds links in `~/.local/bin` and an entry in your application menu.

If `install.sh` ends with a note that `~/.local/bin` is not on your PATH, the commands `harness-design-studio-gui`, `harness-design-studio` and `harness` are not found yet. Fix it once:

```
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
. ~/.bashrc
```

(or log out and in). Until then you can start the app from the application menu or `~/.local/bin/harness-design-studio-gui`.

Other options of `install.sh`: `sudo ./install.sh --system` installs for everyone into `/usr/local/lib/harness-design-studio`; `--prefix FOLDER` chooses the folder. Remove with `./uninstall.sh` (or `sudo ./uninstall.sh --system`); it removes only what the installer put there. The installer writes a file `.harness-design-studio-install` into the install folder that lists what it installed. `uninstall.sh` removes only the folders on that list and refuses to touch a `cli`, `LICENSES`, `_internal` or `harness-design-studio-gui` item that is not on it (the 0.1.0 `uninstall.sh` deleted such folders without asking); `install.sh` never replaces one either. `install.sh` refuses to install into the folder the package was unpacked from (or a folder that holds it), copies to a temporary name before it replaces an older install (a failed copy leaves the old install and the package intact), and does not replace a `harness`, `harness-design-studio` or `harness-design-studio-gui` link in the bin folder that points to another program. `--prefix ""` is refused. `uninstall.sh` removes a link only if it points into the install it removes and keeps the application-menu entry of another install; `uninstall.sh --help` prints its usage. Files installed as `root` belong to `root`. The `.tar.gz` is built with owner root, sorted entries and fixed times, so building it again gives the same bytes.

If `install.sh` says that a folder "was not installed by this installer", the install folder holds one of these names from something else (or from an older installer, which wrote no list; an install made by the 0.1.0 `install.sh` is of this kind). Choose another `--prefix`, or move that folder away first. To replace a 0.1.0 install, remove it first (run its own `uninstall.sh`, or delete `~/.local/opt/harness-design-studio` yourself), then run the new `install.sh`. Your projects are never inside the install folder.

Run `install.sh` from the **unpacked package**. Run from the source tree it refuses and prints: `This folder (...) has no built program, so there is nothing to install.`

## Check that it works

For ways A and B (the installed program):

```
harness-design-studio --version          # prints the version
harness-design-studio-gui --selftest    # opens the editor offscreen, makes a project, generates, exports, and prints "selftest ok"
```

`--selftest` exists only in the installed editor (`harness-design-studio-gui` of the `.deb` and the `.tar.gz`). When you run from source (way C) the app command is also called `harness-design-studio-gui` (and `harness-gui`), but that one does not know the flag and simply starts the app. From source, check with `harness-design-studio --version`, then the five-minute check below, and `pytest` if you installed the `dev` extras.

Then start **Harness Design Studio** from the application menu. The first start opens a sample project and a short tour.

**What you should see:** a window with the title *Harness Design Studio*, a navigation rail down the left edge (*Home*, *Model*, *Checks*, *Drawings*, *Outputs*, *Revisions*, *Settings*), one row at the top with the project name and the steps *Generate*, *Check* and *Release*, a diagram of boxes (units) joined by lines (interfaces) in the middle (the *Model* area), the *Project* tree, *Units* and *Interfaces* on the left, the *Inspector*, *Why* and *Problems* tabs on the right, and the menus **File**, **Edit**, **View**, **Design**, **Go** and **Help**. A short tour opens on the first start. If the window is too small or the text is hard to read, see *If the app does not start* below. **F1** opens the user guide.

## Your first five minutes after installing

```
harness-design-studio new wheel-link --template first-steps
harness-design-studio generate wheel-link
harness-design-studio drc wheel-link
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
| The app window is blank or the app closes at once | With way A or B, run `harness-design-studio-gui --selftest` in a terminal. If it prints an error about `xcb`, `libEGL` or `libxkbcommon`, install the libraries above. |
| You are connected by SSH and the app does not open | The app needs a screen. Use the `harness-design-studio` command line tool over SSH, or start the app on the machine itself. |
| `install.sh` says `This folder (...) has no built program, so there is nothing to install.` | You ran it from the source tree. Run it from the unpacked `.tar.gz` folder. |

## C. Run from source (developers)

You need Python 3.12 or newer (Ubuntu 24.04 has it) and the Qt libraries above.

```
sudo apt install python3-venv git libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0
git clone <the repository> && cd <the repository>/HarnessDesignStudio
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[gui,dev]"
```

Run the app with `harness-design-studio-gui`, the command line tool with `harness-design-studio`. The old short names `harness-gui` and `harness` still work as aliases. Run the tests with `pytest` (they run offscreen). **Without network:** build a wheelhouse once on a connected machine with `python -m tools.vendor`, copy it over and install with `pip install --no-index --find-links wheelhouse -e ".[gui,dev]"`.

Build the packages yourself:

```
python -m tools.build_installer      # dist/harness-design-studio/ and the .tar.gz
python -m tools.build_deb            # dist/harness-design-studio_<version>_amd64.deb
dist/harness-design-studio/harness-design-studio-gui --selftest
```

The release procedure and the clean-machine check are in [`RELEASE.md`](RELEASE.md).

## D. Windows (from 1.2.0)

**Needs:** Windows 10 or 11, 64-bit (x86-64), about 600 MB of free disk space and a screen of at least 1280 x 720 for the app. No administrator account, no network and no other software (Python and Qt are inside the package).

There are two files; take either:

- `harness-design-studio-<version>-windows-x86_64-setup.exe`: the **setup program** (recommended). It installs for your user only.
- `harness-design-studio-<version>-windows-x86_64.zip`: the **portable** folder. Nothing is installed.

**The first start of an unsigned program.** The packages are not signed (see [`SECURITY.md`](SECURITY.md)), so Windows SmartScreen shows a blue window, *Windows protected your PC*, the first time you run the setup program or the editor. This is expected. Compare the checksum first (above), then choose **More info** and **Run anyway**. If a browser marked the download, you can also right-click the file, choose **Properties** and tick **Unblock** at the bottom. For the `.zip`, unblock it *before* you extract it; otherwise every program in it asks once. Antivirus programs may scan the new files for a minute on the first start.

**Setup program.** Double-click it and follow the pages (the first page is the read-me). It installs into `%LOCALAPPDATA%\Programs\Harness Design Studio` (you can choose another folder), adds **Harness Design Studio** to the Start menu, puts the install folder and its `cli` folder on your user `PATH`, and registers itself under *Settings > Apps > Installed apps* where you can uninstall it. It never asks for administrator rights. Open a **new** terminal afterwards (an open one does not see the changed `PATH`):

```
harness-design-studio --version
```

```
harness 1.3.0
```

You now have the command line tool `harness-design-studio` (and its short alias `harness`) and the editor `harness-design-studio-gui`. For a script or a shared machine, the setup program also runs without windows: `harness-design-studio-<version>-windows-x86_64-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /CURRENTUSER /DIR="C:\Tools\Harness Design Studio"` (add `/LOG=setup.log` to keep a log). Remove it with *Settings > Apps*, or run `unins000.exe` in the install folder (`/VERYSILENT` makes that silent too). Your projects are never inside the install folder, and uninstalling does not touch them.

**Portable zip.** Extract it into a folder of your choice (right-click, **Extract All**), keep the path short (a very long path can hit the Windows limit of 260 characters), and start `harness-design-studio-gui.exe`. The command line tool is `cli\harness-design-studio.exe` (`cli\harness.exe` is the same program). Nothing is written to the registry or the `PATH`; delete the folder to remove the tool. To type the command from anywhere, add the `cli` folder to your `PATH` yourself.

**Check that it works.** In a terminal, in the install folder (setup program: it is on the `PATH` already; zip: `cd` to the `cli` folder):

```
harness-design-studio --version
harness-design-studio new wheel-link --template first-steps
harness-design-studio generate wheel-link
harness-design-studio drc wheel-link
```

The editor is a Windows program without a console window, so it prints nothing there. Its self-test reports through the exit code and a file. In PowerShell (`Start-Process -Wait` makes the shell wait for the editor):

```
$p = Start-Process .\harness-design-studio-gui.exe -ArgumentList '--selftest','--selftest-out','result.txt' -Wait -PassThru
$p.ExitCode        # 0 means success
Get-Content result.txt    # selftest ok
```

Then start **Harness Design Studio** from the Start menu and continue with [Your first five minutes after installing](#your-first-five-minutes-after-installing).

| You see | Do this |
| --- | --- |
| *Windows protected your PC* | Expected for an unsigned program: **More info**, then **Run anyway** (see above). |
| `harness-design-studio` is not recognized | The terminal was open during the install. Open a new one, or use the full path `%LOCALAPPDATA%\Programs\Harness Design Studio\cli\harness-design-studio.exe`. |
| The editor does not appear, or a black or empty window shows | Update the graphics driver, then run the self-test above to see whether the program itself is intact. |
| Your company blocks programs in `%LOCALAPPDATA%` | Ask for an exception for the install folder, or run the portable `.zip` from a folder that is allowed. |

Settings (theme, scale, last project; no design data) are in `%APPDATA%\HarnessDesigner\HarnessDesigner.ini`.

## E. macOS (from 1.2.0)

**Needs:** macOS 13 (Ventura) or newer, about 600 MB of free disk space and no other software. There is one disk image for each kind of Mac; take the one that fits (Apple menu > *About This Mac*: *Chip: Apple M1/M2/...* is Apple Silicon, *Processor: Intel* is Intel; or run `uname -m` in the Terminal: `arm64` or `x86_64`):

- `harness-design-studio-<version>-macos-arm64.dmg`: Apple Silicon (M1 and later).
- `harness-design-studio-<version>-macos-x86_64.dmg`: Intel Macs.

**Install.** Double-click the `.dmg`, drag **Harness Design Studio** onto the **Applications** folder in the window, then eject the image.

**The first start of an unsigned app.** The app is not signed with a Developer ID and not notarized (see [`SECURITY.md`](SECURITY.md)), so macOS refuses a plain double-click with a message that it cannot verify the developer. Compare the checksum first (above), then do one of these once:

- Open the Applications folder, **right-click** (or Control-click) the app, choose **Open**, then **Open** in the window that appears. From then on it starts normally. Apple changed this in macOS 15 (Sequoia): there the right-click **Open** may no longer get past the message, and then the next way is the one to use. This was not tested here; the packages have not been run on a Mac by a person (`compliance/SIGNOFF.md`).
- Or, in System Settings > *Privacy & Security*, press **Open Anyway** next to the message about the app (it shows for an hour after the refused start).
- Or, in the Terminal, remove the quarantine mark that the download put on the app: `xattr -dr com.apple.quarantine "/Applications/Harness Design Studio.app"`.

**The command line tool** is inside the app. Use its full path, or link it into a folder on your `PATH`:

```
"/Applications/Harness Design Studio.app/Contents/MacOS/harness-design-studio" --version
mkdir -p ~/.local/bin
ln -s "/Applications/Harness Design Studio.app/Contents/MacOS/harness-design-studio" ~/.local/bin/harness-design-studio
ln -s "/Applications/Harness Design Studio.app/Contents/MacOS/harness" ~/.local/bin/harness
```

(If `~/.local/bin` is not on your `PATH`, add `export PATH="$HOME/.local/bin:$PATH"` to `~/.zshrc`.) The editor is the app itself; `Contents/MacOS/harness-design-studio-gui` is the same editor when you want to start it from the Terminal.

**Check that it works.**

```
harness-design-studio --version
harness-design-studio-gui --selftest
```

The self-test works without a window and prints `selftest ok` (use the full path `"/Applications/Harness Design Studio.app/Contents/MacOS/harness-design-studio-gui"` if you did not link the editor). Then continue with [Your first five minutes after installing](#your-first-five-minutes-after-installing) and open the project from the app (**File > Open project...**).

| You see | Do this |
| --- | --- |
| *"Harness Design Studio" cannot be opened because the developer cannot be verified* or *is damaged and can't be opened* | Expected for an unsigned app: right-click > **Open**, or the `xattr` command above. |
| *The application can't be opened* / a message about the processor | You took the wrong image. Use `-arm64` on Apple Silicon and `-x86_64` on Intel. |
| `harness-design-studio: command not found` | Use the full path, or make the links above and open a new Terminal. |

To remove the tool, drag the app to the Trash. Settings (no design data) are in `~/.config/HarnessDesigner/HarnessDesigner.ini`.

Build the Windows and macOS packages yourself with `python -m tools.build_windows` (on Windows) and `python -m tools.build_macos` (on a Mac); see [`RELEASE.md`](RELEASE.md).

## Where things are stored

| What | Where |
| --- | --- |
| Your projects | wherever you saved them (a folder per project) |
| App settings (theme, scale, last project) | Linux and macOS: `~/.config/HarnessDesigner/HarnessDesigner.ini`; Windows: `%APPDATA%\HarnessDesigner\HarnessDesigner.ini` (no design data) |
| Autosave of an open project | `<project>/.harness-recovery/` (offered for restore after a crash; ignored by Git) |

Next: [`GETTING_STARTED.md`](GETTING_STARTED.md).
