Harness Design Studio: Windows package
======================================

An offline tool for designing the electrical harnesses of a spacecraft. It never uses the network,
and nothing is downloaded when you install or run it. Python and Qt are inside the package.
For Windows 10 and 11, 64-bit (x86-64).

Programs
  harness-design-studio-gui.exe        the editor (Start menu: Harness Design Studio)
  cli\harness-design-studio.exe        the command line tool; cli\harness.exe is the same program
                                       under its short name

Setup program (harness-design-studio-<version>-windows-x86_64-setup.exe)
  Installs for your user only, into %LOCALAPPDATA%\Programs\Harness Design Studio (no administrator
  rights), adds a Start menu entry, and puts the install folder and its cli folder on your user
  PATH, so a new terminal finds harness-design-studio, harness and harness-design-studio-gui.
  Remove it under Settings > Apps, or run unins000.exe in the install folder.

Portable zip (harness-design-studio-<version>-windows-x86_64.zip)
  Extract it anywhere and run harness-design-studio-gui.exe. Nothing is installed, nothing is
  changed in the registry or on the PATH. Delete the folder to remove it.

Not signed
  Unless the build had a certificate, Windows SmartScreen shows "Windows protected your PC" on
  the first start of the setup program or the editor: choose "More info", then "Run anyway". Check
  the file against the SHA256SUMS of the release first:
      Get-FileHash harness-design-studio-<version>-windows-x86_64-setup.exe -Algorithm SHA256

Check the program
  cli\harness-design-studio.exe --version
  cli\harness-design-studio.exe new wheel-link --template first-steps
  harness-design-studio-gui.exe --selftest --selftest-out result.txt
      (exit code 0, and "selftest ok" in result.txt; the editor has no console window)

Licences of the components are in the LICENSES folder (README.txt there lists them). Qt for Python
(PySide6) is used under the LGPL-3. The licence of Harness Design Studio itself has not been
chosen yet (decision D-02): no licence is granted by this file.
The user guide opens with F1 inside the editor.
