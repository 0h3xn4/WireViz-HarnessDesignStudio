TrueType copies of the bundled IBM Plex fonts (D-149)

src/harness_design_studio/resources/fonts/ holds IBM Plex Sans and IBM Plex Mono as WOFF2 files.
Qt on Linux and macOS reads them; Qt on Windows does not read WOFF2. The Windows package
therefore adds the six files in this folder to the same place (tools/build_windows.py does it with
PyInstaller's --add-data), and gui/fonts.py loads them when the WOFF2 files gave no IBM Plex
family. The Linux and macOS packages and the Python wheel do not carry them.

How they were made: each .woff2 of resources/fonts was decompressed to the TrueType file of the
same name with fontTools (fontTools.ttLib.TTFont(path); font.flavor = None; font.save(...));
nothing else in the font was changed. Licence: SIL Open Font License 1.1, the text is shipped in
the package (LICENSES/ibm-plex/OFL-1.1-IBM-Plex.txt). Remake them from the WOFF2 files when those
change.
