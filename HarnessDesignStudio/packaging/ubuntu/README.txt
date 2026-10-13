Harness Design Studio: Ubuntu package
============================
Per-user install (no administrator rights):   ./install.sh
System-wide install:                          sudo ./install.sh --system   (into /usr/local/lib/harness-design-studio)
Remove:                                       ./uninstall.sh   (or: sudo ./uninstall.sh --system)

The installer writes the list of what it installed to .harness-design-studio-install in the install folder.
uninstall.sh removes only what is on that list and refuses to touch a cli, LICENSES, _internal or
harness-design-studio-gui folder or file it did not install. install.sh refuses to install into the folder
the package was unpacked in, and does not replace a link in the bin folder that points to another program.
An older install (version 0.1.0, no list) must be removed first: run its uninstall.sh, or delete the folder.

Needs these system libraries (already present on a normal Ubuntu desktop):
  libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0
  libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0
  Install with: sudo apt install libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libfontconfig1 libdbus-1-3 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0

The tool never uses the network. The user guide opens with F1 inside the app.
Programs: harness-design-studio-gui (the editor), harness-design-studio (the command line tool; the short
name harness works too, it is the same program).
Check the package: ./harness-design-studio-gui --selftest
