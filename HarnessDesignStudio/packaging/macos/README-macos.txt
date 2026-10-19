Harness Design Studio: macOS package
====================================

An offline tool for designing the electrical harnesses of a spacecraft. It never uses the network,
and nothing is downloaded when you install or run it. Python and Qt are inside the app.

Install
  Drag "Harness Design Studio" onto the Applications folder in this window.
  This image is for one kind of Mac: harness-design-studio-<version>-macos-arm64.dmg for Apple
  Silicon (M1 and later), harness-design-studio-<version>-macos-x86_64.dmg for Intel Macs.
  Needs macOS 13 or newer.

First start of an app that is not signed
  The app is not signed with a Developer ID and not notarized unless the release page says so.
  macOS then refuses a plain double-click ("cannot be opened because the developer cannot be
  verified"). Do one of these once:
    - Control-click (right-click) the app in Applications, choose Open, then Open again.
    - Or in Terminal:  xattr -dr com.apple.quarantine "/Applications/Harness Design Studio.app"
  Check the file against the SHA256SUMS of the release first:
      shasum -a 256 harness-design-studio-<version>-macos-<arch>.dmg

Command line tool
  It is inside the app. In Terminal:
      "/Applications/Harness Design Studio.app/Contents/MacOS/harness-design-studio" --version
  "harness" is the same program under its short name. To type just harness-design-studio, link
  it into a folder on your PATH, for example:
      mkdir -p ~/.local/bin
      ln -s "/Applications/Harness Design Studio.app/Contents/MacOS/harness-design-studio" ~/.local/bin/harness-design-studio
      ln -s "/Applications/Harness Design Studio.app/Contents/MacOS/harness" ~/.local/bin/harness

Check the program
  "/Applications/Harness Design Studio.app/Contents/MacOS/harness-design-studio-gui" --selftest
  prints "selftest ok" (it needs no window; it works offscreen).

Remove
  Drag the app to the Trash. The settings of the editor are in ~/.config/HarnessDesigner/HarnessDesigner.ini (no design data).

Licences of the components are in the app (Contents/Resources/LICENSES, README.txt lists them).
Qt for Python (PySide6) is used under the LGPL-3. The licence of Harness Design Studio itself has
not been chosen yet (decision D-02): no licence is granted by this file.
The user guide opens with F1 inside the editor.
