# Findings: third-party components and GUI framework (brief areas 4 and 5, step 2.5)

Auditor: read-only. Date of work: 2026-11-09. Repo: `/home/user/WireViz-HarnessDesignStudio`, commit `0cc13bb1` (tag `v1.17.0` is `4c5a56c1`, the packages are from that tag).
Nothing in the repo was changed. All downloads are in `.../scratchpad/dl/` (own empty dir per package), nothing from them was run. Python was used with `-I` only to read them.

## 0. Summary

Top findings, most important first:

1. **No compliant source offer for Qt/PySide6 or for any other LGPL/GPL component.** The packages say only "available from the Qt Project (https://code.qt.io)". The release has no source archives. (TPC-1)
2. **The Linux packages (.deb, .tar.gz) bundle 87 Ubuntu system libraries** (GTK 3, GLib, Cairo, Pango, libgcrypt, libsystemd, Kerberos, X11, libstdc++ ...). Most are LGPL-2.1+ or MIT/BSD-style. **None of their licence texts, copyright notices or source offers ship.** (TPC-2)
3. **Python itself (PSF), OpenSSL (Apache-2.0), libffi, zlib, bzip2, xz, zstd, ICU, the Qt-internal third-party code and the Rust crates inside pydantic_core have no notices in any package.** (TPC-3, TPC-4, TPC-5)
4. **There is no `LICENSE`, `NOTICE` or `THIRD_PARTY_NOTICES` of the project inside any package.** The .deb `copyright` file says "LicenseRef-Proprietary ... No licence is granted". (TPC-6)
5. **The SBOM and licence report are not in the repo and not attached to any release.** The SBOM that `tools/gen_sbom.py` makes lists only the Python packages of a clean venv. The real packages hold about 100 more components. (TPC-9)
6. **Windows packages ship Microsoft runtime DLLs (VCRUNTIME140, MSVCP140, ucrtbase, 42 api-ms-win-*.dll) and Mesa/LLVM `opengl32sw.dll`** with no notice. (TPC-7)

Good news (verified):

- **Qt binding is PySide6-Essentials 6.11.2 (Qt 6.11.2).** Not PyQt. No Addons wheel.
- **No GPL-only or commercial-only Qt module is bundled in any package.** Bundled: Core, DBus, Gui, Widgets, Network, OpenGL, Svg, WaylandClient (+ platform plugins). All carry `LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` in the source headers I read (Qt 6.11.2 tag). Section 3 lists what I did and did not read.
- **Qt is linked dynamically, packages are PyInstaller one-folder, the Qt libraries are separate files and are byte-identical to the PyPI wheels (163 of 163 files compared on Linux).** A user can replace them. Not documented. (TPC-13)
- **Fonts (Inter 4.1, JetBrains Mono 2.304) are byte-identical to the upstream release files; their OFL texts are byte-identical to upstream and ship in the 1.17.0 packages and in macOS 1.5.0.** (The 1.0.0 .deb had IBM Plex instead, also with its OFL text.) No Reserved Font Name is declared in either. No modified font.
- **No licence found that conflicts with GPL-3.0-only** in what is bundled. Open points: Microsoft redistributables, Mesa/LLVM, FreeType dual licence choice. See section 7.
- **Prototype and docs: no third-party JS, CSS or fonts.** See section 8.

## 1. What I did (method)

| Step | How |
| --- | --- |
| Download | `curl` through the agent proxy, no TLS bypass. SHA-256 of the four packages match the published `SHA256SUMS` (checked); the `SHA256SUMS` file matches the digest GitHub shows for it. |
| .deb | `dpkg-deb -x` and `-e`. v1.17.0 and v1.0.0. |
| .tar.gz | `tar -xzf` (no-same-owner). |
| Windows .zip | Python `zipfile`. |
| Windows setup.exe | **Not unpackable.** `innoextract 1.9` says "Could not determine setup data version" (file header says Inno Setup 6.7.0, newer than the tool). `7z` cannot open it. I rely on `packaging/windows/harness-design-studio.iss` (`Source: "{#SourceDir}\*"`, recursive, so same payload as the .zip) and on the file sizes (43.6 MB installer vs 71.3 MB zip, LZMA2 solid). Treat the installer payload as "same as .zip, not verified". |
| macOS .dmg (v1.5.0) | `7z x` (reads the HFS+ image; one error = the `Applications` symlink was not extracted). |
| PyInstaller archive | Read with PyInstaller 6.22.3's `CArchiveReader` in a scratch venv (read only). Module names and version strings come from the raw PYZ table. I did **not** unmarshal bytecode (3.13 vs 3.14 mismatch segfaults). |
| ELF/PE facts | `readelf`, `strings`, `pefile` (read only). |
| Bundled Ubuntu libs | The build ran on Ubuntu 24.04 (compiler string `GCC: (Ubuntu 13.3.0-6ubuntu2~24.04.1)`). This audit host is also Ubuntu 24.04.5 and holds the same libs. I compared SHA-256 of every bundled `.so` with the host file and, for 8 libs not on the host, with the `.deb` downloaded from `archive.ubuntu.com/ubuntu/pool`. **All 87 matched byte for byte.** Licence information is from those packages' `/usr/share/doc/<pkg>/copyright`. That file is **not** in our package. |
| Qt/PySide6 | Wheels `PySide6_Essentials-6.11.2` and `shiboken6-6.11.2` (linux `manylinux_2_34_x86_64` and `win_amd64`) from PyPI. Compared all files of the Linux package under `PySide6/` and `shiboken6/` with the wheel: 163 identical, 0 different. Windows wheel read for licence files only. |
| Qt licences | Source headers and `REUSE.toml` / `qt_attribution.json` read from `raw.githubusercontent.com/qt/<repo>/v6.11.2/`. `doc.qt.io`, `download.qt.io`, `code.qt.io` are blocked by the proxy (not retried). The GitHub API is blocked for these repos. |
| Source install set | `pip install --dry-run --report` with `--python-version 3.14 --only-binary=:all: --ignore-requires-python` and explicit manylinux platform tags, into a dummy `--target`, for the runtime set and for runtime + dev extras. Licence fields then read from PyPI JSON `/pypi/<name>/<version>/json`. Python here is 3.13; nothing was installed or run. |
| Fonts | Downloaded `Inter-4.1.zip` and `JetBrainsMono-2.304.zip` from the upstream GitHub releases and compared SHA-256 of the TTFs and the licence texts. |
| Icons | `lucide-icons/lucide` tag `1.56.0` `LICENSE` and 52 `icons/*.svg` read from raw.githubusercontent.com. |

Raw working files (not for the repo): `.../scratchpad/audit/tpc/` (`libmap-gui.txt`, `pkg-licences.txt`, `libtable.md`, `dev-report.json`, `dev-licences.json`, `pydantic-core-crates.txt`, file lists per package).

## 2. Inventory per package format

### 2.1 Layout and licence files, all formats

| | .deb 1.17.0 | .tar.gz 1.17.0 | Windows .zip 1.17.0 (= setup.exe payload, unverified) | macOS .dmg 1.5.0 | .deb 1.0.0 |
| --- | --- | --- | --- | --- | --- |
| Top level | `opt/harness-design-studio/{harness-design-studio-gui, cli/, _internal/, LICENSES/}`, `usr/bin/*` symlinks, `usr/share/applications/*.desktop`, `usr/share/icons/hicolor/scalable/apps/harness-design-studio.svg`, `usr/share/doc/harness-design-studio/{copyright, LICENSES/}` | `harness-design-studio/{harness-design-studio-gui, cli/, _internal/, LICENSES/, README.txt, install.sh, uninstall.sh, .desktop.in, .svg}` | `harness-design-studio-gui.exe, cli/{harness-design-studio.exe, harness.exe, _internal/}, _internal/, LICENSES/, README-windows.txt` | `Harness Design Studio.app` (Contents/{MacOS, Frameworks, Resources/LICENSES}), `README.txt`, `Applications` symlink | like 1.17.0 with Python 3.12 |
| Files | 916 entries. Every file under `_internal/`, `cli/`, `LICENSES/` and the GUI program has the same SHA-256 as in the tarball (checked); the tarball adds only `README.txt`, `install.sh`, `uninstall.sh`, `.desktop.in`, `.svg` | 921 entries, 767 regular files, 278 MB | 798 entries, 152 MB | not counted | 937 entries |
| Project `LICENSE` | **no** | **no** | **no** | **no** | **no** |
| Project `NOTICE` / `THIRD_PARTY_NOTICES*` | **no** | **no** | **no** | **no** | **no** |
| Debian `copyright` | yes, **"License: LicenseRef-Proprietary ... No licence is granted by this file."** (`tools/build_deb.py:23-37`) | n/a | n/a | n/a | same text |
| `LICENSES/` folder | yes: `README.txt`, `GPL-3.txt`, `LGPL-3.txt` (both byte-identical to Debian `common-licenses`), 10 Python package licences, Inter and JetBrains Mono OFL, Lucide/Feather | same as .deb (hashes identical) | same plus `pyside6-essentials/` and `shiboken6/` with `LicenseRef-Qt-Commercial.txt` (only licence file in the Windows wheels) | same as Linux (typing-inspection 0.4.4) | + `ibm-plex/OFL-1.1-IBM-Plex.txt`; no Inter/JetBrains/Lucide |
| Licence of the tool stated in package | "not chosen yet ... no licence is granted" (`README.txt`/`README-windows.txt:36-37`, `copyright`) | same | same | same | same |
| Source offer / pointer | `LICENSES/README.txt`: "Its source is available from the Qt Project (https://code.qt.io, Qt for Python)." Nothing else. | same | same | same | same |
| Signature | none | none | none (exe have no version resource, no Authenticode) | ad-hoc `_CodeSignature` | none |

Release v1.17.0 assets (checked with the GitHub API): the five files only. **No SBOM, no licence report, no source archive, no `THIRD_PARTY_NOTICES`** (`.github/workflows/release.yml:208` builds `files=(dist/*.tar.gz dist/*.deb dist/*-setup.exe dist/*.zip dist/SHA256SUMS)`).

### 2.2 Python packages in the packages (identical set in all formats)

Where the version comes from: `LICENSES/README.txt` (written by `tools/collect_licences.py` from the build venv metadata) and, independently, strings in the PYZ table of the program (`pydantic.version` 2.13.5 and 2.46.5, `openpyxl._constants` 3.1.5, `defusedxml` 0.7.1, `annotated_types` 0.8.0, `et_xmlfile` 2.0.0, `PySide6` 6.11.2). Only `pydantic-2.13.5.dist-info` ships as dist-info in the package. The licence expression is from the PyPI wheel METADATA (read from the wheels I downloaded). `typing_extensions` and `typing_inspection` versions: only from `LICENSES/README.txt` (no version string found in the PYZ).

| Component | Version | Licence (wheel METADATA) | Licence file shipped | Notes |
| --- | --- | --- | --- | --- |
| pydantic | 2.13.5 | MIT | yes | |
| pydantic_core | 2.46.5 | MIT | yes (pydantic-core's own text only) | Rust extension. At least 26 crates are linked in (partial list from embedded paths: ahash 0.8.12, aho-corasick 1.1.3, base64 0.22.1, getrandom 0.3.3, hashbrown 0.16.1, hex 0.4.3, icu_normalizer 1.5.0, idna 1.1.0, jiter 0.14.0, lexical-parse-float 1.0.5, lru 0.16.3, memchr 2.7.4, num-bigint 0.4.6, num-integer 0.1.46, once_cell 1.21.3, percent-encoding 2.3.2, pyo3 0.28.3, pyo3-ffi 0.28.3, regex 1.12.3, regex-automata 0.4.13, regex-syntax 0.8.5, serde_json 1.0.149, smallvec 1.15.1, speedate 0.17.0, url 2.5.8, uuid 1.23.0). Their licences: **unverified** (not in the wheel). |
| annotated-types | 0.8.0 | MIT | yes | |
| typing_extensions | 4.16.0 | PSF-2.0 | yes | |
| typing-inspection | 0.4.5 (0.4.4 in 1.0.0 and macOS 1.5.0) | MIT | yes | floating transitive version |
| openpyxl | 3.1.5 | MIT | yes (`LICENCE.rst`) | |
| et_xmlfile | 2.0.0 | MIT | yes (3 files) | `LICENCE.python` is also shipped |
| defusedxml | 0.7.1 | PSFL | yes | not imported by name; `--hidden-import defusedxml` (`tools/build_installer.py`) |
| PySide6_Essentials | 6.11.2 | `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only` | LGPL-3 and GPL-3 text from Debian / `packaging/licences/` (the Linux wheel carries **no** licence file at all; the Windows wheel carries only `LicenseRef-Qt-Commercial.txt`) | see section 3 |
| shiboken6 | 6.11.2 | same | same | |
| harness_design_studio | 1.17.0 | `LicenseRef-Proprietary` (`pyproject.toml:14`) | none | |

CLI program (`cli/_internal/`) holds the same pure-Python set minus PySide6/shiboken6 (excluded in `tools/build_installer.py:build_programs`).

Not in the packages (the allow-list check in `tools/build_installer.py:41-` and `FORBIDDEN` do their job for Python code): rich, pygments, tomli, setuptools, pip, lxml, attrs, mypy, pytest, hypothesis. Confirmed by the PYZ module list (only stdlib + the 10 packages above + app).

### 2.3 Python runtime

| Format | Runtime | Source of info | Licence file in package |
| --- | --- | --- | --- |
| Linux (.deb, .tar.gz) | CPython **3.14.10**, shared `libpython3.14.so.1.0` (32.5 MB), 51 extension modules in `python3.14/lib-dynload/`, `base_library.zip`; compiler `GCC 13.3.0-6ubuntu2~24.04.1` | `strings` on libpython; origin of the build (probably `actions/setup-python`) **unverified** | **none** (PSF-2.0 text not shipped; `LICENSES/typing-extensions/LICENSE` and `et-xmlfile/LICENCE.python` hold PSF-style texts but are those packages' own) |
| Windows | CPython **3.14.10** (`python314.dll`, `python3.dll`, `.pyd` files; version resources "Python Software Foundation") | pefile | none |
| macOS 1.5.0 | CPython **3.12.10** (`Python.framework`) | strings | none |
| .deb 1.0.0 | CPython **3.12.15** (`libpython3.12.so.1.0`; the string as found, I did not check whether that version number exists upstream) | strings | none |

OpenSSL: Linux 3.0.13 (Ubuntu `libssl3t64 3.0.13-0ubuntu3.16`, Apache-2.0 per Debian copyright), Windows **3.5.9** (`libcrypto-3.dll`, `libssl-3.dll`, "The OpenSSL Project"), macOS 3.0.16 (`libssl.3.dylib`, `libcrypto.3.dylib`). Licence text shipped: **none**.

### 2.4 Qt / PySide6 (all formats)

Binding: **PySide6-Essentials 6.11.2 + shiboken6 6.11.2** (Qt for Python, the official binding). Not PyQt. `pyproject.toml:19` extra `gui`. The code imports only `PySide6.QtCore`, `QtGui`, `QtWidgets` (plus `QtTest` in tests/tools and `QtSvg` in `tools/handling_screenshots.py:267`, none shipped). Qt version: `Qt 6.11.2 ... release build; by GCC 11.5.0 (Red Hat 11.5.0-5)` (string in `libQt6Core.so.6`), Windows `Qt6Core.dll` 6.11.2.0.

| Part | Linux (deb/tar), under `_internal/PySide6/Qt/` | Windows | macOS 1.5.0 |
| --- | --- | --- | --- |
| Qt modules | libQt6**Core, DBus, Gui, Network, OpenGL, Svg, WaylandClient, Widgets** + platform support libs libQt6**EglFSDeviceIntegration, EglFsKmsSupport, WlShellIntegration, XcbQpa**; **ICU 73** (libicudata 32 MB, libicui18n, libicuuc) | Qt6**Core, Gui, Network, Svg, Widgets** | QtCore, QtDBus, QtGui, QtNetwork, QtSvg, QtWidgets (frameworks) |
| Python bindings | QtCore, QtDBus, QtGui, QtWidgets (`.abi3.so`), `libpyside6`, `libshiboken6` | QtCore, QtGui, QtWidgets `.pyd`, `pyside6.abi3.dll`, `shiboken6.abi3.dll` | same 4 |
| Plugins (count) | 45: platforms (xcb, wayland, eglfs, linuxfb, minimal, minimalegl, offscreen, vkkhrdisplay, vnc), platformthemes (**qgtk3**, qxdgdesktopportal), platforminputcontexts (compose, ibus), imageformats (gif, icns, ico, jpeg, svg, tga, tiff, wbmp, webp), iconengines (svg), generic (evdev x4, tuiotouch), egldeviceintegrations (3), wayland-* (12), xcbglintegrations (2) | generic/tuiotouch, iconengines/svgicon, imageformats (9), platforms (direct2d, minimal, offscreen, windows), styles/modernwindows | cocoa, minimal, offscreen, macstyle, imageformats incl. macheif, macjp2, tuiotouch, svgicon |
| Translations | 96 `.qm` (qt_*, qtbase_*, qt_help_*) | 96 `.qm` | not counted |
| QML / Quick | **none** (no QtQml/QtQuick libs) | none | none |
| Other | `opengl32sw.dll` (software OpenGL) is Windows only | `opengl32sw.dll`, MSVCP140*.dll | |

Not bundled but contained in the PyPI `PySide6_Essentials` wheel that a **source install** downloads: 80 Qt libs incl. Concurrent, Designer, Help, Lottie, LabsStyleKit, QuickTimeline, WaylandCompositor, Sql, PrintSupport, Test, UiTools, Xml, Qml/Quick family.

### 2.5 Bundled system libraries (Linux only; 87 files in `_internal/`, 10 of the same files again in `cli/_internal/`)

Present in `.deb` and `.tar.gz`. `libGL`, `libEGL`, `libc`, `libm` are **not** bundled (the .deb `Depends:` list covers libegl1, libgl1 etc.). Licence column: from the Debian `copyright` file of that exact package (not from our package). Where the Debian file is not machine-readable I wrote what its text says.

| Bundled file (in `_internal/`) | Ubuntu 24.04 package and version (byte-identical match) | Licence (from that package's Debian copyright file; not shipped) |
| --- | --- | --- |
| libX11-xcb.so.1 | libx11-xcb1 2:1.8.7-1ubuntu0.1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libX11.so.6 | libx11-6 2:1.8.7-1ubuntu0.1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXau.so.6 | libxau6 1:1.0.9-1build6 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXcomposite.so.1 | libxcomposite1 1:0.4.5-1build3 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXcursor.so.1 | libxcursor1 1:1.2.1-1build1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXdamage.so.1 | libxdamage1 1:1.1.6-1build1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXdmcp.so.6 | libxdmcp6 1:1.1.3-0ubuntu6 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXext.so.6 | libxext6 2:1.3.4-1build2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXfixes.so.3 | libxfixes3 1:6.0.0-2build1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXi.so.6 | libxi6 2:1.8.1-1build1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXinerama.so.1 | libxinerama1 2:1.1.4-3build1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXrandr.so.2 | libxrandr2 2:1.5.2-2build1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libXrender.so.1 | libxrender1 1:0.9.10-1.1build1 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libatk-1.0.so.0 | libatk1.0-0t64 2.52.0-1build1 | LGPL-2+ (Debian copyright) |
| libatk-bridge-2.0.so.0 | libatk-bridge2.0-0t64 2.52.0-1build1 | LGPL-2+ (Debian copyright; also AFL-2.1/GPL-2+ parts) |
| libatspi.so.0 | libatspi2.0-0t64 2.52.0-1build1 | LGPL-2+ (Debian copyright; also AFL-2.1 or GPL-2+ parts) |
| libblkid.so.1 | libblkid1 2.39.3-9ubuntu6.6 | LGPL-2.1+ (util-linux; Debian copyright per-directory; package default GPL-2+) |
| libbrotlicommon.so.1 | libbrotli1 1.1.0-2ubuntu0.1 | MIT (Debian copyright) |
| libbrotlidec.so.1 | libbrotli1 1.1.0-2ubuntu0.1 | MIT (Debian copyright) |
| libbsd.so.0 | libbsd0 0.12.1-1build1.1 | BSD-3-clause and other BSD/ISC variants (Debian copyright) |
| libbz2.so.1.0 | libbz2-1.0 1.0.8-5.1ubuntu0.1 | bzip2 BSD-variant (Debian copyright) |
| libcairo-gobject.so.2 | libcairo-gobject2 1.18.0-3build1 | LGPL-2.1 or MPL-1.1 (Debian copyright text) |
| libcairo.so.2 | libcairo2 1.18.0-3build1 | LGPL-2.1 or MPL-1.1 (Debian copyright text) |
| libcap.so.2 | libcap2 1:2.66-5ubuntu2.4 | BSD-3-clause or GPL-2 (Debian copyright) |
| libcom_err.so.2 | libcom-err2 1.47.0-2.4~exp1ubuntu4.1 | mixed (Debian copyright lists GPL-2, LGPL-2, BSD-3, Apache-2, ISC, MIT-US-export); per-file unverified |
| libcrypto.so.3 | libssl3t64 3.0.13-0ubuntu3.16 | Apache-2.0 (OpenSSL 3.0.13; Debian copyright) |
| libdatrie.so.1 | libdatrie1 0.2.13-3build1 | LGPL-2.1+ (Debian copyright) |
| libdbus-1.so.3 | libdbus-1-3 1.14.10-4ubuntu4.1 | GPL-2+ or AFL-2.1, and Expat (Debian copyright) |
| libepoxy.so.0 | libepoxy0 1.5.10-1build1 | MIT/Expat (Debian copyright) |
| libexpat.so.1 | libexpat1 2.6.1-2ubuntu0.6 | MIT (Debian copyright) |
| libffi.so.8 | libffi8 3.4.6-1build1 | MIT/Expat (Debian copyright) |
| libfontconfig.so.1 | libfontconfig1 2.15.0-1.1ubuntu2 | MIT-style permissive, Keith Packard notice (Debian copyright text, non-DEP5) |
| libfreetype.so.6 | libfreetype6 2.13.2+dfsg-1ubuntu0.2 | FTL (alt. GPL-2+) (Debian copyright) |
| libfribidi.so.0 | libfribidi0 1.0.13-3build1 | LGPL-2.1+ (Debian copyright) |
| libgcc_s.so.1 | libgcc-s1 14.2.0-4ubuntu2~24.04.1 | GPL-3 with GCC Runtime Library Exception (Debian copyright text, non-DEP5) |
| libgcrypt.so.20 | libgcrypt20 1.10.3-2ubuntu0.2 | LGPL-2.1+ for most files (Debian copyright text) |
| libgdk-3.so.0 | libgtk-3-0t64 3.24.41-4ubuntu1.3 | LGPL-2+ and LGPL-2.1+ and Expat (Debian copyright) |
| libgdk_pixbuf-2.0.so.0 | libgdk-pixbuf-2.0-0 2.42.10+dfsg-3ubuntu3.3 | LGPL-2+ and LGPL-2.1+ and CC0-1.0 (Debian copyright) |
| libgio-2.0.so.0 | libglib2.0-0t64 2.80.0-6ubuntu3.10 | LGPL-2.1+ (Debian copyright) |
| libglib-2.0.so.0 | libglib2.0-0t64 2.80.0-6ubuntu3.10 | LGPL-2.1+ (Debian copyright) |
| libgmodule-2.0.so.0 | libglib2.0-0t64 2.80.0-6ubuntu3.10 | LGPL-2.1+ (Debian copyright) |
| libgobject-2.0.so.0 | libglib2.0-0t64 2.80.0-6ubuntu3.10 | LGPL-2.1+ (Debian copyright) |
| libgpg-error.so.0 | libgpg-error0 1.47-3build2.1 | LGPL-2.1+ (Debian copyright) |
| libgraphite2.so.3 | libgraphite2-3 1.3.14-2ubuntu0.24.04.1 | LGPL-2.1+ or MPL-1.1 or GPL-2+ (Debian copyright) |
| libgssapi_krb5.so.2 | libgssapi-krb5-2 1.20.1-6ubuntu2.10 | MIT Kerberos permissive notices (Debian copyright text, non-DEP5) |
| libgthread-2.0.so.0 | libglib2.0-0t64 2.80.0-6ubuntu3.10 | LGPL-2.1+ (Debian copyright) |
| libgtk-3.so.0 | libgtk-3-0t64 3.24.41-4ubuntu1.3 | LGPL-2+ and LGPL-2.1+ and Expat (Debian copyright) |
| libharfbuzz.so.0 | libharfbuzz0b 8.3.0-2build2 | MIT (Debian copyright) |
| libjpeg.so.8 | libjpeg-turbo8 2.1.5-2ubuntu2 | IJG/BSD-3-clause/Zlib mix (Debian copyright lists Zlib, BSD-3-clause, Expat, NTP) |
| libk5crypto.so.3 | libk5crypto3 1.20.1-6ubuntu2.10 | MIT Kerberos permissive notices (Debian copyright text, non-DEP5) |
| libkeyutils.so.1 | libkeyutils1 1.6.3-3build1 | LGPL-2+ for the library, GPL-2+ for tools (Debian copyright lists both) |
| libkrb5.so.3 | libkrb5-3 1.20.1-6ubuntu2.10 | MIT Kerberos permissive notices (Debian copyright text, non-DEP5) |
| libkrb5support.so.0 | libkrb5support0 1.20.1-6ubuntu2.10 | MIT Kerberos permissive notices (Debian copyright text, non-DEP5) |
| liblz4.so.1 | liblz4-1 1.9.4-1build1.1 | BSD-2-clause (library; GPL-2+ for tools) (Debian copyright) |
| liblzma.so.5 | liblzma5 5.6.1+really5.4.5-1ubuntu0.4 | public domain (xz 5.4.5) (Debian copyright) |
| libmd.so.0 | libmd0 1.1.0-2build1.1 | BSD-3-clause/ISC/public-domain variants (Debian copyright) |
| libmount.so.1 | libmount1 2.39.3-9ubuntu6.6 | LGPL-2.1+ (Debian copyright, libmount/*) |
| libpango-1.0.so.0 | libpango-1.0-0 1.52.1+ds-1build1 | LGPL-2+ and LGPL-2.1+ (Debian copyright) |
| libpangocairo-1.0.so.0 | libpangocairo-1.0-0 1.52.1+ds-1build1 | LGPL-2+ and LGPL-2.1+ (Debian copyright) |
| libpangoft2-1.0.so.0 | libpangoft2-1.0-0 1.52.1+ds-1build1 | LGPL-2+ and LGPL-2.1+ (Debian copyright) |
| libpcre2-8.so.0 | libpcre2-8-0 10.42-4ubuntu2.1 | BSD-3-clause-Cambridge with binary-library exception (Debian copyright) |
| libpixman-1.so.0 | libpixman-1-0 0.42.2-1build1 | MIT (Debian copyright text) |
| libpng16.so.16 | libpng16-16t64 1.6.43-5ubuntu0.7 | libpng licence (Debian copyright) |
| libselinux.so.1 | libselinux1 3.5-2ubuntu2.1 | public domain (Debian copyright) |
| libssl.so.3 | libssl3t64 3.0.13-0ubuntu3.16 | Apache-2.0 (OpenSSL 3.0.13; Debian copyright) |
| libstdc++.so.6 | libstdc++6 14.2.0-4ubuntu2~24.04.1 | GPL-3 with GCC Runtime Library Exception (Debian copyright text, non-DEP5) |
| libsystemd.so.0 | libsystemd0 255.4-1ubuntu8.18 | LGPL-2.1+ (Debian copyright) |
| libthai.so.0 | libthai0 0.1.29-2build1 | LGPL-2.1+ (Debian copyright) |
| libuuid.so.1 | libuuid1 2.39.3-9ubuntu6.6 | BSD-3-clause (Debian copyright, libuuid/*) |
| libxcb-cursor.so.0 | libxcb-cursor0 0.1.4-1build1 | MIT/X (Debian copyright) |
| libxcb-glx.so.0 | libxcb-glx0 1.15-1ubuntu2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libxcb-icccm.so.4 | libxcb-icccm4 0.4.1-1.1build3 | MIT/X Consortium (Debian copyright) |
| libxcb-image.so.0 | libxcb-image0 0.4.0-2build1 | MIT/X11 (Debian copyright) |
| libxcb-keysyms.so.1 | libxcb-keysyms1 0.4.0-1build4 | MIT/X11 (Debian copyright) |
| libxcb-randr.so.0 | libxcb-randr0 1.15-1ubuntu2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libxcb-render-util.so.0 | libxcb-render-util0 0.3.9-1build4 | MIT/X Consortium (Debian copyright) |
| libxcb-render.so.0 | libxcb-render0 1.15-1ubuntu2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libxcb-shape.so.0 | libxcb-shape0 1.15-1ubuntu2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libxcb-shm.so.0 | libxcb-shm0 1.15-1ubuntu2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libxcb-sync.so.1 | libxcb-sync1 1.15-1ubuntu2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libxcb-util.so.1 | libxcb-util1 0.4.0-1build3 | MIT (Debian copyright) |
| libxcb-xfixes.so.0 | libxcb-xfixes0 1.15-1ubuntu2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libxcb-xkb.so.1 | libxcb-xkb1 1.15-1ubuntu2 | MIT/X11-style permissive (Debian copyright text, non-DEP5) |
| libxkbcommon-x11.so.0 | libxkbcommon-x11-0 1.6.0-1build1 | MIT-style (Debian copyright text, non-DEP5) |
| libxkbcommon.so.0 | libxkbcommon0 1.6.0-1build1 | MIT-style (Debian copyright text, non-DEP5) |
| libz.so.1 | zlib1g 1:1.3.dfsg-3.1ubuntu2.3 | Zlib (Debian copyright) |
| libzstd.so.1 | libzstd1 1.5.5+dfsg2-2build1.1 | BSD-3-clause or GPL-2 (Debian copyright) |

`libpython3.14.so.1.0` is listed in 2.3. Summary of what the 87 are: 3 GCC runtime pieces (libgcc_s, libstdc++), OpenSSL (2), Python-support libs (libffi, libz, libbz2, liblzma, libzstd, libuuid), the GTK 3 stack pulled in only by the optional Qt plugin `platformthemes/libqgtk3.so` (libgtk-3, libgdk-3, libgdk_pixbuf, libcairo, libcairo-gobject, libpango*, libatk*, libatspi, libharfbuzz, libfribidi, libthai, libdatrie, libgraphite2, libpixman, libepoxy, libgio/libglib/libgobject/libgmodule/libgthread, libmount, libblkid, libselinux, libpcre2-8, libcap), Kerberos (libgssapi_krb5, libkrb5, libk5crypto, libkrb5support, libcom_err, libkeyutils; pulled in by `libQt6Network.so.6`), libsystemd and libgcrypt/libgpg-error/liblz4/libmd/libbsd (via libdbus), libbrotli (via QtNetwork), and ~35 X11/xcb/xkbcommon libs (Qt xcb platform plugin).

### 2.6 Windows-only components

| File(s) | Version (pefile) | Licence / terms | Notice shipped |
| --- | --- | --- | --- |
| `VCRUNTIME140.dll`, `VCRUNTIME140_1.dll` (in 4 folders: `_internal`, `cli/_internal`, `PySide6`, `shiboken6`), `PySide6/MSVCP140*.dll`, `shiboken6/MSVCP140.dll` | 14.51.36247.0 (vcruntime); 14.44.35211.0 (msvcp140) | Microsoft Visual Studio redistributable ("Distributable Code") terms. **Unverified** (no file in package) | no |
| `ucrtbase.dll`, 42 `api-ms-win-*.dll` (each in `_internal` and `cli/_internal`) | 10.0.26100.1742 | Microsoft Windows Universal CRT redistributable terms. **Unverified** | no |
| `libcrypto-3.dll`, `libssl-3.dll` | OpenSSL 3.5.9 | Apache-2.0 (OpenSSL 3.x). **Unverified** (no file in package) | no |
| `libffi-8.dll` | no version resource | libffi: expected MIT. **Unverified** | no |
| `PySide6/opengl32sw.dll` | no version resource; strings show LLVM | Mesa llvmpipe software renderer, Qt ships it as "opengl32sw". Licence expected MIT + LLVM (Apache-2.0 with LLVM exception). **Unverified** | no |
| `python314.dll`, `.pyd` | 3.14.10 | PSF-2.0, **unverified** from package | no |
| `harness-design-studio-gui.exe`, `cli\*.exe` | PyInstaller bootloader (strings `PYINSTALLER_*`); no version resource | PyInstaller bootloader: GPL-2.0-or-later with the bootloader exception (per PyInstaller 6.22.3 wheel METADATA, not per package) | no |
| `setup.exe` | Inno Setup 6.7.0 (string in file) | Inno Setup licence. **Unverified**, installer not unpacked | no |

### 2.7 PyInstaller (all formats)

Bootloader embedded in `harness-design-studio-gui`, `cli/harness-design-studio` (ELF, BuildID `e150a976...`, both programs share the same bootloader), `.exe` files. The exact bootloader version is not printed in the binary. The build pin is `pyinstaller==6.22.3` (`pyproject.toml` dev extra); that the shipped binary came from 6.22.3 is **inferred, not verified**. PyInstaller 6.22.3 wheel METADATA: licence "GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones)"; `pyinstaller-hooks-contrib 2026.9`: Apache-2.0 and GPL-2.0 classifiers. No PyInstaller licence or notice ships. Type: one-folder (`_internal/`), not one-file. Not one-file means libraries are real files on disk.

### 2.8 Fonts, icons, images, other assets

| Asset | Where | Licence | Licence file shipped | Check |
| --- | --- | --- | --- | --- |
| Inter 4.1 (Regular, Medium, SemiBold TTF; name table version `4.001;git-9221beed3`) | `resources/fonts/`, in all packages | OFL-1.1, "Copyright 2016 The Inter Project Authors" | yes, `OFL-1.1-Inter.txt` next to fonts and in `LICENSES/inter/` | TTF SHA-256 equals upstream `Inter-4.1.zip` `extras/ttf/*`; licence text equals upstream `LICENSE.txt`. No RFN named. Font trademark string "Inter UI and Inter is a trademark of rsms" is in the name table (OFL does not grant trademark rights; the font is used under its own name, unmodified: fine). |
| JetBrains Mono 2.304 (Regular, Medium TTF) | same | OFL-1.1, "Copyright 2020 The JetBrains Mono Project Authors" | yes | TTF SHA-256 equals upstream `JetBrainsMono-2.304.zip` `fonts/ttf/*`; OFL text equals upstream `OFL.txt`. No RFN. |
| IBM Plex Sans / Mono (woff2) | **only in the 1.0.0 packages** (and the guide of old releases) | OFL-1.1, "with Reserved Font Name Plex" | yes in 1.0.0 | Files not compared with upstream (not downloaded). Replaced by Inter/JetBrains in the UI overhaul (D-150). Text of the IBM Plex OFL is now only in git history. |
| Lucide icon geometry (58 icons in `gui/icons.py`, "lucide-static 1.56.0") | code, drawn at run time (no icon files) | ISC (Lucide) + MIT for the Feather-derived icons | yes, `LICENSES/lucide/LICENSE.txt` (text from `gui/licences.py:LUCIDE_LICENCES`) | Spot check against `lucide-icons/lucide@1.56.0`: of 52 icons whose Lucide name is given in a comment, 27 have path data identical to upstream, 25 not identical by my crude path-only comparison (upstream uses `<circle>/<line>/<rect>` elements for some; not resolved). **The shipped text is not upstream's current LICENSE** ("Copyright (c) 2026 Lucide Icons and Contributors"); it is the older wording "Lucide Contributors 2022". See TPC-17. |
| App logo | `packaging/ubuntu/harness-design-studio.svg`, `docs/img/logo.svg`, painted in code by `gui/appicon.py`; `.ico` made by `tools/make_icons.py` from that code | project's own drawing (rects and two Béziers, no third-party outline) | n/a | No embedded images or fonts in the SVGs. No third-party icon set. |
| `docs/img/banner.svg` | docs only | text converted to paths from **IBM Plex** (comment in the file) | OFL text not next to it | OFL allows documents/images made with the font. Not packaged. |
| Example projects, templates, guide HTML | `resources/examples`, `resources/guide/index.html` | project's own; content question (real part numbers) belongs to another auditor | n/a | `index.html` has no external URL, no script src, no font-face. |
| Screenshots | `docs/**/*.png` (383 files) | show the UI with Inter, JetBrains Mono, Lucide | n/a | not packaged |

## 3. GUI framework in detail (brief area 5)

| Question | Answer | Evidence |
| --- | --- | --- |
| Which binding? | PySide6 (Qt for Python) **6.11.2**, wheel **PySide6-Essentials**, plus shiboken6 6.11.2. Not PyQt. | `pyproject.toml:19`, PYZ string, wheel METADATA, `LICENSES/README.txt` |
| Essentials or Addons? | Essentials only. Addons (Charts, DataVisualization, Quick3D, WebEngine, Multimedia, ...) are not installed and not bundled. | `pyproject.toml`, file lists of all packages |
| Licence of the binding | PyPI METADATA: `LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. | wheel METADATA (both wheels) |
| Qt modules bundled | Core, DBus, Gui, Widgets, Network, OpenGL, Svg, WaylandClient (+ QPA support libs). Windows: Core, Gui, Network, Svg, Widgets. | file lists |
| Is any bundled module GPL-only or commercial-only? | **No.** I read the `SPDX-License-Identifier` of at least one source file from each of these Qt 6.11.2 modules/plugins: qtbase Core (`qobject.cpp`), Gui (`qguiapplication.cpp`), Widgets (`qwidget.cpp`), Network (`qnetworkaccessmanager.cpp`), DBus (`qdbusconnection.cpp`), OpenGL (`qopenglbuffer.cpp`), plugins xcb, eglfs (`api/qeglfsintegration.cpp`), linuxfb, offscreen, vnc, minimal, gtk3 theme, xdgdesktopportal theme, ibus and compose input contexts, imageformats gif, jpeg, ico, generic tuiotouch; qtsvg `qsvgrenderer.cpp`, svg imageformat, svg iconengine. All read: `LicenseRef-Qt-Commercial OR LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`. Qt Wayland: `qtwayland/REUSE.toml` annotates `src/client/qwayland.json` and `src/plugins/**.json` with the same four-way expression and the **compositor** sources and `hardwareintegration/compositor` with `LicenseRef-Qt-Commercial OR GPL-3.0-only`. The compositor library is **not** bundled (only `libQt6WaylandClient`). I did not read a `.cpp` header of the Wayland client or the wayland decoration/shell plugins (404 on the guessed paths). | `scratchpad/audit/tpc/qtsrc/headers.txt` |
| GPL-only modules that exist in the PyPI wheel but are not shipped | `QtWaylandCompositor` (`qwaylandcompositor.cpp`: `LicenseRef-Qt-Commercial OR GPL-3.0-only`) and `QtQuickTimeline` (`qquicktimeline.cpp`: same). Both are in `PySide6_Essentials` 6.11.2 although the wheel METADATA says LGPL OR GPL. They matter only for people who `pip install` and for the SBOM. Not in the app packages. Other wheel modules (Lottie, LabsStyleKit, QuickVectorImage etc.) I did not check. | headers; wheel file list |
| How is Qt linked? | Dynamically. `QtWidgets.abi3.so` has `NEEDED libQt6Widgets.so.6, libQt6Gui.so.6, libQt6Core.so.6, libpyside6, libshiboken6`; `RPATH $ORIGIN/:$ORIGIN/Qt/lib:$ORIGIN/../shiboken6/`. The GUI program is a PyInstaller bootloader and links only libdl, libz, libpthread, libc. Qt libs are ELF shared objects (`libQt6Core.so.6` etc.), real files in `_internal/PySide6/Qt/lib/` with symlinks at `_internal/` top. | `readelf -d` |
| One-file or one-folder? | One-folder (PyInstaller `--noconfirm`, no `--onefile`). | `tools/build_installer.py:pyinstaller_build`; layout |
| Modified Qt? | No. 163 of 163 files under `PySide6/` and `shiboken6/` of the Linux package are byte-identical to the PyPI wheels. `pydantic_core` `.so` is identical to its wheel too. (Windows not compared byte-wise, only the licence files.) | hash comparison |
| Can a user replace the Qt libraries? | Yes on Linux and Windows: they are separate files, loaded from the install folder. Replacement works with another build of the same Qt/PySide6 version (ABI). Not documented beyond one sentence in `LICENSES/README.txt` ("you may replace it with another build of the same version"). The Python code of the program itself is in a compressed archive inside the executable (not replaceable without a rebuild; GPL needs the source, not replaceability). On macOS the frameworks are replaceable but the app carries an ad-hoc `_CodeSignature`, which a replacement breaks. | layout; `LICENSES/README.txt` |
| Is the LGPL-3 text shipped? | Yes (`LICENSES/LGPL-3.txt`, `GPL-3.txt`, byte-identical to Debian `common-licenses`; the repo copies in `packaging/licences/` are byte-identical too). The in-app About/Settings page shows `strings.LICENCE_QT`. | cmp; `gui/strings.py:2224` |
| Is a corresponding-source offer shipped? | **No, not in a form GPL-3.0 section 6 / LGPL-3.0 accept.** Only a URL to the Qt Project. See TPC-1. | `LICENSES/README.txt`, `gui/strings.py:2224-2229` |
| Qt third-party code (inside Qt libs) | Qt 6.11.2 `qt_attribution.json` lists code that Qt's own libraries contain: PCRE2 10.47 (BSD-3 with exception) and its JIT (BSD-2), double-conversion 3.4.0 (BSD-3), rfc6234 SHA (BSD-3), tinycbor 7.0 (MIT), md4c 0.5.3 (MIT), harfbuzz-ng 14.3.0 (MIT), FreeType 2.14.3 (FTL or GPL-2.0-only), libjpeg-turbo 3.2.0 (IJG and BSD-3), libpng 1.6.58, zlib 1.3.2, easing equations (BSD-3), sRGB ICC profile (LicenseRef-ICC). Which ones are actually compiled into the wheel's libs is **unverified** (symbols for PCRE2, FreeType, HarfBuzz wrapper are present in libQt6Core / libQt6Gui; the wheel was built by The Qt Company). | `scratchpad/audit/tpc/qtsrc/a_*.json` |
| ICU | `libicudata/i18n/uc.so.73` (ICU 73) shipped in the Linux package. Licence: ICU/Unicode licence, **unverified** from package. | file list |

Qt licensing choice: the project plans GPL-3.0-only. Qt allows `LGPL-3.0-only` or `GPL-3.0-only` to be chosen (the `GPL-2.0-only` option is not usable with a GPL-3.0-only program). The packages say LGPL-3. Either choice needs the licence text, notices and source. The LGPL-3 route adds the replaceability and "prominent notice" duties (LGPL-3.0 section 4), which the one-folder layout already satisfies in practice.

## 4. Source install: what `pip install` pulls in

Command class: `pip install harness-design-studio[gui]` (runtime) and `[gui,dev]` (developers). `requires-python = ">=3.14"`; this host has 3.13, so I resolved with `--python-version 3.14 --ignore-requires-python --only-binary=:all:` and manylinux tags (see section 1). The result is today's resolution; nothing in the repo pins the transitive packages (no lock file, no hashes), so a later user may get other versions.

**Runtime (`[gui]`), 10 distributions, same set as in the packages:** pydantic 2.13.5 (MIT), pydantic_core 2.46.5 (MIT), annotated-types 0.8.0 (MIT), typing_extensions 4.16.0 (PSF-2.0), typing-inspection 0.4.5 (MIT), openpyxl 3.1.5 (MIT), et_xmlfile 2.0.0 (MIT), defusedxml 0.7.1 (PSFL), PySide6_Essentials 6.11.2 and shiboken6 6.11.2 (`LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only`). Build backend `setuptools==84.0.0` (MIT) is pinned in `[build-system]`. In a source install the user downloads Qt from PyPI; the project distributes no Qt binary then. The source install has no `LICENSES/` folder; `strings.LICENCE_QT` tells the user the text is "with the PySide6 package", but the Linux PySide6 wheel contains no licence file and the Windows wheel only `LicenseRef-Qt-Commercial.txt` (see TPC-8).

**Dev extras (`[gui,dev]`), 84 distributions in total, 74 beyond the runtime set** (licence from PyPI JSON; none is shipped in a package): altgraph 0.17.5 (MIT), arrow 1.4.0 (Apache), ast_serialize 0.13.1 (MIT), attrs 26.1.0 (MIT), boolean.py 5.0 (BSD-2), CacheControl 0.14.4 (Apache-2.0), **certifi 2026.10.23 (MPL-2.0)**, chardet 7.7.0 (0BSD), charset-normalizer 3.5.2 (MIT), coverage 7.17.2 (Apache-2.0), cyclonedx-bom 7.5.0 (Apache-2.0), cyclonedx-python-lib 11.12.0 (Apache-2.0), execnet 2.1.2 (MIT), filelock 4.2.9 (MIT), **fqdn 1.6.0 (MPL-2.0)**, greenlet 3.5.6 (MIT AND PSF-2.0), **hypothesis 6.168.5 (MPL-2.0)**, idna 3.20 (BSD-3), iniconfig 2.3.1 (MIT), isoduration 20.11.0 (ISC), jsonpointer 3.10 (BSD), jsonschema 4.26.0 (MIT), jsonschema-specifications 2025.9.1 (MIT), lark 1.3.1 (MIT), librt 0.16.0 (MIT), license-expression 30.4.4 (Apache-2.0), lxml 6.1.3 (BSD-3), markdown-it-py 4.2.0 (MIT), mdurl 0.1.2 (MIT), msgpack 1.2.4 (Apache-2.0), mypy 2.4.0 (MIT), mypy_extensions 1.2.0 (MIT), packageurl-python 0.17.6 (MIT), packaging 26.3 (Apache-2.0 OR BSD-2-Clause), **pathspec 1.1.1 (MPL-2.0)**, pip 26.3 (MIT), pip-licenses 5.5.5 (MIT), pip-requirements-parser 32.0.1 (MIT), pip_api 0.0.35 (Apache), pip_audit 2.10.1 (Apache), platformdirs 4.14.5 (MIT), playwright 1.63.0 (Apache-2.0; its wheel carries a Node.js driver, browsers are downloaded separately), pluggy 1.7.0 (MIT), prettytable 3.18.0 (BSD-3), py-serializable 2.2.0 (Apache-2.0), pyee 13.0.1 (MIT), Pygments 2.21.0 (BSD-2), **pyinstaller 6.22.3 (GPL-2.0-or-later with special exception)**, **pyinstaller-hooks-contrib 2026.9 (Apache-2.0 and GPL-2.0 classifiers)**, pyparsing 3.3.3 (MIT), pytest 9.1.1 (MIT), pytest-cov 7.1.0 (MIT), pytest-qt 4.5.0 (MIT), pytest-timeout 2.4.0 (MIT), pytest-xdist 3.8.0 (MIT), python-dateutil 4.0.0 (BSD-3), referencing 0.37.0 (MIT), requests 2.34.2 (Apache-2.0), rfc3339-validator 0.1.4 (MIT), rfc3986-validator 0.1.1 (MIT), rfc3987-syntax 1.1.0 (MIT per `license_expression`, Apache classifier), rich 15.0.0 (MIT), rpds-py 2026.9.1 (MIT), ruff 0.16.10 (MIT), setuptools 84.2.1 (MIT), six 1.17.0 (MIT), sortedcontainers 2.4.0 (Apache), tomli 2.5.0 (MIT), tomli_w 1.2.0 (MIT), tzdata 2026.6 (Apache-2.0), uri-template 1.3.0 (MIT), urllib3 2.8.0 (MIT), wcwidth 0.9.4 (MIT), webcolors 25.10.0 (BSD-3).

No GPL-only package in the dev set except PyInstaller (with exception). MPL-2.0 packages (certifi, fqdn, hypothesis, pathspec) are rejected by the project's own allow-list (`tools/licence_report.py:12-13` comment "MPL is not listed") but are dev-only and not distributed. They do not conflict with GPL-3.0-only (MPL-2.0 section 3.3 lets it be combined with GPL). The `DEV_ONLY` set in `tools/licence_report.py:19` lists 13 names; the real dev set has 84. This does not matter while the report is made from the runtime venv.

## 5. Existing SBOM and licence report versus the real packages

Where they are: **nowhere in the repo and nowhere on the release page.** `tools/gen_sbom.py` writes `dist/release-docs/sbom.cdx.json` and `licence-report.md`; CI (`.github/workflows/harness-ci.yml:112,115-121`) uploads them as a build artifact of a CI run (retention not checked), and `tools/release_check.py` runs it locally. `compliance/evidence/release_0.1.0_report.md:11` says "SBOM and licence report: 11 packages, 0 rejected"; the 1.8.0 quick check says "SKIPPED". `release.yml` does not build or upload either. `docs/SECURITY.md:26` states "CycloneDX SBOM and licence report with every release and release candidate", `compliance/docs/CMP.md:33` says "for each delivery ... SBOM and licence report", and `docs/developer/release.md:21` lists the SBOM as a step of the release check. That is **not true for the published releases 1.0.0 to 1.17.0** (assets checked for 1.17.0; the SECURITY.md text itself says the records for 1.0.0 to 1.16.0 are only checksum lists).

What the generator produces, from the code (I did not run it; it needs network and Python 3.14): `venv` + `pip install .[gui]`; `cyclonedx_py environment` (Python distributions only) and `piplicenses --with-system`. So: the 10 runtime distributions, the project itself, and `pip` (the venv's own pip; "11 packages" in the 0.1.0 report matches).

Drift against what the packages really hold:

| In the package, not in the SBOM / report | Format |
| --- | --- |
| CPython 3.14.10 runtime (libpython, 51 extension modules, stdlib zip) | all |
| OpenSSL 3.0.13 (Linux) / 3.5.9 (Windows) | all |
| libffi, zlib, libbz2, liblzma, libzstd, libuuid | Linux; libffi Windows |
| Qt 6.11.2 as modules: only "PySide6_Essentials" appears; no Qt version, no module list, no plugin list | all |
| ICU 73 | Linux |
| 87 Ubuntu system libraries (section 2.5) | Linux |
| Qt-internal third-party code (section 3) | all |
| Rust crates inside pydantic_core (>= 26) | all |
| PyInstaller bootloader and runtime hooks | all |
| Inter 4.1 and JetBrains Mono 2.304 (5 TTF files) | all; they ARE in `LICENSES/README.txt` but not in the SBOM |
| Lucide/Feather icon geometry | all; same |
| Microsoft VC and UCRT DLLs, Mesa/LLVM `opengl32sw.dll` | Windows |
| Python 3.12 framework, OpenSSL dylibs | macOS 1.5.0 |

In the SBOM but not in the packages: `pip`. Version drift between releases: `typing-inspection` 0.4.4 (1.0.0, macOS 1.5.0) vs 0.4.5 (1.17.0), because transitive packages are not pinned. Only one SBOM per CI run (Linux); none for Windows.

The package allow-list in `tools/build_installer.py:41-46` (`ALLOWED_PACKAGES`, run through `check_package`) is a good control for Python code. Nothing checks the native libraries (the 87 `.so`, the Qt plugins, the DLLs) against any list.

## 6. Obligations per component and whether the packages meet them

"Notice" = copyright notice and licence text to be reproduced. "Source" = source code or a valid offer.

| Component (licence) | Obligation when distributing the binary | Linux deb/tar | Windows zip/setup | Met? |
| --- | --- | --- | --- | --- |
| Qt 6.11.2 libs (choose LGPL-3.0-only or GPL-3.0-only) | licence text, copyright/notice, say it is used and under which licence, corresponding source (or valid written offer) for the Qt version shipped, allow replacement (LGPL-3 s.4) | LGPL-3 and GPL-3 text yes; one-line statement yes; **no valid source offer**; replacement possible, not documented | same | **partly** (TPC-1, TPC-13) |
| PySide6 / shiboken6 (same) | same | same | same | **partly** |
| Qt third-party code (BSD, MIT, FTL, ICU, ...) | reproduce notices | no | no | **no** (TPC-4) |
| GTK 3, GLib, Cairo, Pango, ATK, AT-SPI, GDK-Pixbuf, FriBidi, libthai, libdatrie, libgcrypt, libgpg-error, libsystemd, libmount, libblkid, libkeyutils, graphite2 (LGPL-2.1 / 2.1+) | licence text, notice, source or offer, allow relinking | **no licence text of LGPL-2.1, no notices, no offer** (LGPL-3 text is shipped, which is a different licence) | n/a | **no** (TPC-2) |
| libstdc++, libgcc_s (GPL-3 + GCC Runtime Library Exception) | notice, source offer (GPL-3 s.6) | GPL-3 text shipped; no notice; no offer | n/a (MSVC runtimes instead) | **partly** (TPC-2) |
| OpenSSL 3.x (Apache-2.0) | licence text, NOTICE if any, state changes (none) | no | no | **no** (TPC-3) |
| CPython (PSF-2.0 + bundled third-party notices) | PSF licence and copyright notice | no | no | **no** (TPC-3) |
| libffi, zlib (zlib licence), bzip2, xz (public domain), zstd (BSD-3), libuuid (BSD-3), expat, libpng, libjpeg-turbo, freetype (FTL), harfbuzz, fontconfig, pixman, X11/xcb libs (MIT/X11-style), libbrotli, libpcre2, lz4, libmd/libbsd (BSD), Kerberos (MIT-style) | notice and licence text in binary distributions (most of these) | no | partly n/a | **no** (TPC-2) |
| ICU 73 | Unicode/ICU licence text | no | n/a | **no** (TPC-4) |
| pydantic, pydantic_core, annotated-types, typing-inspection, openpyxl, et_xmlfile (MIT), typing_extensions (PSF-2.0), defusedxml (PSFL) | notice and licence text | yes (`LICENSES/*/`) | yes | **yes** for the package itself; **no** for the Rust crates in pydantic_core (TPC-5) |
| Inter, JetBrains Mono (OFL-1.1) | keep copyright and licence with the font; do not sell the font alone; modified versions must not use an RFN | yes, next to the fonts and in `LICENSES/` | yes | **yes** |
| Lucide (ISC), Feather (MIT) | notice and licence text | yes (text slightly outdated, TPC-17) | yes | **yes, with a wording drift** |
| PyInstaller bootloader (GPL-2.0-or-later + exception) | with the exception, none beyond GPL-3's normal duties for the combined program | no notice | no notice | **unclear/low** (TPC-15) |
| Microsoft VC runtime, UCRT | Microsoft redistribution terms (not in package) | n/a | no notice | **unknown** (TPC-7) |
| Mesa/LLVM `opengl32sw.dll` | MIT + Apache-2.0 w/ LLVM exception notices (expected) | n/a | no | **no** (TPC-7) |
| Inno Setup runtime in setup.exe | Inno Setup licence | n/a | unverified | unknown |
| Project code, GPL-3.0-only (planned) | licence text, notices, source | none of the three in any package | same | **no** (TPC-6) |

## 7. GPL-3.0-only compatibility of every licence found

| Licence | Found in | Compatible with distribution under GPL-3.0-only? |
| --- | --- | --- |
| MIT / Expat / X11 / MIT-US-export / Kerberos MIT-style | Python packages, X11 libs, expat, libffi, harfbuzz, ... | yes |
| BSD-2 / BSD-3 / BSD-3 with exception / ISC / Zlib / libpng / public domain / 0BSD / bzip2 | zlib, libpng, lz4, zstd (BSD option), libuuid, libbsd, libmd, pcre2, Lucide | yes |
| Apache-2.0 | OpenSSL 3.x | yes with GPL-3 (not with GPL-2-only); the project is GPL-3.0-only, so yes |
| PSF-2.0 / PSFL / Python-2.0 | CPython, typing_extensions, defusedxml, et_xmlfile | yes |
| OFL-1.1 | Inter, JetBrains Mono, IBM Plex (1.0.0) | yes for fonts as separate data files (OFL fonts may not be relicensed, nor sold alone; neither happens) |
| LGPL-3.0-only | Qt 6.11.2, PySide6, shiboken6 (chosen option) | yes |
| GPL-3.0-only (Qt option) | same | yes |
| GPL-2.0-only (third Qt option) | same | **not usable**; do not choose it (the project does not) |
| LGPL-2.1 / LGPL-2.1+ / LGPL-2+ | GTK, GLib, Cairo (LGPL-2.1 option), Pango, ATK, libgcrypt, libsystemd, libmount, libblkid, libthai, ... | yes: dynamic use of an LGPL library from a GPL-3 program is allowed; "or later" parts can be taken under LGPL-3 / GPL-3 |
| MPL-1.1 (option of Cairo, graphite2) | | not GPL-compatible alone; **choose the LGPL option**; no issue if recorded |
| GPL-3 with GCC Runtime Library Exception | libstdc++, libgcc_s | yes |
| FTL or GPL-2.0-only | FreeType (system lib) | FTL option used. I believe the FreeType Licence is compatible with GPL-3 but not GPL-2 (FSF licence list). **Could not fetch the FSF page**, so: unverified, owner/lawyer to confirm or remove (TPC-14). |
| AFL-2.1 or GPL-2+ | libdbus | take GPL-2+; yes |
| IJG, libpng-2.0, Unicode/ICU, FTL parts | libjpeg-turbo, Qt internals, ICU | permissive; yes (Unicode/ICU: unverified from package) |
| Microsoft Visual Studio / UCRT redistributable terms | Windows DLLs | **unknown**; GPL-3 s.1 "System Libraries" may cover them (UCRT is part of Windows 10+; the VC runtimes are not). Needs a lawyer or removal (`vcruntime` is required by Python). TPC-7 |
| Mesa (MIT) + LLVM (Apache-2.0 with LLVM exception) | opengl32sw.dll (expected, unverified) | yes if the expectation holds |
| Qt commercial (`LicenseRef-Qt-Commercial`) | not used; only a text file in the Windows wheels | n/a; but see TPC-8 |

No incompatibility found. Unknowns: Microsoft redistributables, Mesa/LLVM, the exact third-party notices inside Qt and pydantic_core, FTL/GPL-3 statement.

## 8. Prototype and docs/ux assets

- `HarnessDesignStudio/prototype/` (3 files: `app.js` 51.5 KB, `index.html` 67.6 KB, `template.html` 14.1 KB): hand-written, no `<script src>`, no `<link>`, no `@font-face`, no `url(` to remote hosts, no framework strings (grep for jquery, lodash, d3, react, vue, bootstrap, tailwind: 0). Fonts are named only (`'Inter', 'Segoe UI', system-ui, sans-serif` and `'JetBrains Mono', Consolas, monospace`), nothing embedded. No licence header; project's own work.
- `HarnessDesignStudio/docs/` has no `.js`, `.css`, `.woff*`, `.ttf`, `.otf`; the only non-image, non-text assets are `docs/img/logo.svg` and `docs/img/banner.svg` (banner text is IBM Plex outlines, OFL; see section 2.8). Python examples under `docs/examples/` are the project's own scripts.
- No `http(s)://cdn|fonts|unpkg|cdnjs|ajax` URL in `docs`, `prototype`, `src`, `packaging`, `tools`.
- Not checked: the root-level upstream WireViz `docs/` and `examples/` (out of scope, unchanged upstream).

## 9. Issues

Likelihood and impact are my guesses (low / medium / high). "Owner" = needs an owner decision.

### TPC-1 No compliant corresponding-source offer for Qt, PySide6 and the other LGPL/GPL binaries
- **What:** the only "offer" is a pointer: "Its source is available from the Qt Project (https://code.qt.io, Qt for Python)." The release page and assets have no source archives and no written offer.
- **Where:** `tools/collect_licences.py:112-116` (writes `LICENSES/README.txt`); `src/harness_design_studio/gui/strings.py:2224-2229` (`LICENCE_QT`, shown in the app); `packaging/windows/README-windows.txt:35-36`; release assets (`release.yml:208`).
- **Why it matters:** LGPL-3.0 incorporates GPL-3.0 section 6 for the binary of the library: the distributor must provide the source of the exact version or a written offer valid for three years, or equivalent access at the same place as the binary download. A link to the upstream project does not state the version, is not an offer by the distributor, and is not under the owner's control. Same for the Ubuntu LGPL libraries (TPC-2) and for libstdc++/libgcc_s.
- **Fix:** per release attach (a) Qt for Python 6.11.2 source (`pyside-setup` tarball or the PyPI sdist of PySide6 6.11.2 and shiboken6 6.11.2, plus the Qt 6.11.2 `qtbase`, `qtsvg`, `qtwayland` source tarballs), (b) the Ubuntu source packages for the bundled libraries at the versions in section 2.5 (or `apt-get source` instructions plus a mirror copy), (c) a written offer in `THIRD_PARTY_NOTICES.txt`, valid at least 3 years after the last release that holds the binary, stating exact versions and SHA-256 of the sources; (d) simplest alternative: stop bundling the Ubuntu libraries (TPC-12).
- **Likelihood/impact:** medium / medium (a complaint is unlikely, but this is the main licence duty and easy to meet).
- **Owner decision:** yes (what to host, for how long; where the written offer is valid).

### TPC-2 87 bundled Ubuntu system libraries, no notices, no licence texts, no source offer (Linux deb and tar.gz)
- **What:** `_internal/` holds 87 shared libraries copied from the Ubuntu 24.04 build host (list and licences in section 2.5). Licences include LGPL-2.1/2.1+ (GLib, GTK 3, Cairo, Pango, ATK, libgcrypt, libsystemd, libthai, ...), GPL-3 with GCC exception, MIT/X11, BSD, Zlib. `LICENSES/` has none of these. The .deb `copyright` file says only "see /usr/share/doc/harness-design-studio/LICENSES/".
- **Where:** `/opt/harness-design-studio/_internal/*.so*` in the .deb and the tarball; `tools/build_deb.py:33-37`; `tools/collect_licences.py` (collects only Python distributions, fonts, Lucide, LGPL-3/GPL-3).
- **Why it matters:** LGPL-2.1 s.4/6 and the permissive licences require the licence text and notice with every binary copy; LGPL requires source or offer (TPC-1) and the right to replace the library (the one-folder layout allows it).
- **Fix (choose):** (a) generate `THIRD_PARTY_NOTICES.txt` per package from the Debian `copyright` files of the exact package versions plus the LGPL-2.1 text; or (b) **remove most of them from the package**: GTK 3, GLib, Cairo, Pango, ATK, GDK-Pixbuf, HarfBuzz, graphite2, pixman, epoxy, fribidi, thai (about 35 libs) come only from the optional Qt plugin `platformthemes/libqgtk3.so`; Kerberos, brotli, libkeyutils, com_err (about 8) come only from `libQt6Network.so.6`, which the program does not use (`PySide6.QtNetwork` is excluded in `tools/build_installer.py:26`, yet the `.so` ships); libsystemd/libgcrypt/libgpg-error/lz4/md/bsd/cap come via libdbus. Exclude those plugins/binaries in the PyInstaller call, re-run the self-test, and declare what remains as `Depends:` in the .deb where possible. This shrinks the licence surface and the 278 MB package.
- **Likelihood/impact:** medium / medium.
- **Owner decision:** yes (whether to prune; changes package contents and may change the look on GNOME with the GTK theme plugin).

### TPC-3 No notice for Python, OpenSSL, libffi, zlib, bzip2, xz, zstd in any package
- **What:** CPython 3.14.10 (PSF-2.0) and its bundled components (OpenSSL 3.0.13 / 3.5.9 Apache-2.0, libffi, zlib, bzip2, xz, zstd, libuuid, expat) are in every package; no licence text. `tools/collect_licences.py` collects only distributions that `importlib.metadata` knows.
- **Where:** `_internal/libpython3.14.so.1.0`, `libssl.so.3`, `libcrypto.so.3`, `libffi.so.8`, `libz.so.1`, ... (Windows: `python314.dll`, `libcrypto-3.dll`, ...; macOS: `Python.framework`, `libssl.3.dylib`).
- **Why:** PSF-2.0 section 2 requires retaining the PSF licence and copyright notice in derivative distributions; Apache-2.0 section 4 requires a copy of the licence; the BSD/MIT/zlib licences require notices.
- **Fix:** add the CPython `LICENSE` (from the python.org source for the exact 3.14.10), the OpenSSL `LICENSE.txt`, and the small-library notices to `THIRD_PARTY_NOTICES.txt`; extend `collect_licences.py` with a static table of non-Python components checked against the package contents (see TPC-9).
- **Likelihood/impact:** medium / low-medium.
- **Owner decision:** no.

### TPC-4 Qt-internal third-party code and ICU 73: notices missing
- **What:** Qt's libraries contain third-party code (section 3) and the Linux package ships ICU 73 (`libicudata.so.73` 32 MB, `libicui18n`, `libicuuc`). No notices ship. The PyPI wheels carry no licence files (Linux) or only `LicenseRef-Qt-Commercial.txt` (Windows).
- **Where:** `_internal/PySide6/Qt/lib/`, `Qt6Core.dll` etc.
- **Why:** BSD/MIT/FTL/Unicode licences require notices in binary distributions; FreeType's FTL asks for credit in documentation.
- **Fix:** include Qt's "Third-Party Licenses used in Qt" list for 6.11.2 (from the `qt_attribution.json` files of qtbase 6.11.2) and the ICU licence in `THIRD_PARTY_NOTICES.txt`. I could not fetch doc.qt.io; the `qt_attribution.json` files on GitHub are the source I used.
- **Likelihood/impact:** low-medium / low.
- **Owner decision:** no.

### TPC-5 Rust crates inside `pydantic_core` have no notices
- **What:** the wheel's only licence file is pydantic-core's own MIT text; at least 26 crates are linked into the `.so` (list in 2.2). Their licences are not in the wheel and I could not read them: **unverified**.
- **Where:** `_internal/pydantic_core/_pydantic_core.cpython-314-x86_64-linux-gnu.so` (identical to the PyPI wheel), `LICENSES/pydantic-core/LICENSE`.
- **Why:** MIT/Apache-2.0/Unicode-3.0 crates need their notices in binary distributions; most projects miss this, but it is on the checklist.
- **Fix:** take the `Cargo.lock`-based licence list of pydantic-core 2.46.5 from its source (sdist on PyPI) with `cargo-about` or a manual list, add to `THIRD_PARTY_NOTICES.txt`.
- **Likelihood/impact:** low / low.
- **Owner decision:** no.

### TPC-6 No project `LICENSE` / `NOTICE` / `THIRD_PARTY_NOTICES.txt` in any package; Debian `copyright` says "no licence is granted"
- **What:** none of the five package formats contains a `LICENSE`, `NOTICE` or `THIRD_PARTY_NOTICES*` of the project. The .deb `copyright` file says `License: LicenseRef-Proprietary ... No licence is granted by this file.` The Windows and macOS readmes say the same. `pyproject.toml:14` is `LicenseRef-Proprietary`.
- **Where:** `tools/build_deb.py:23-37`, `packaging/windows/README-windows.txt:35-37`, `packaging/ubuntu/README.txt`, `pyproject.toml:14`. (Licensing text conflicts belong to the licensing auditor; I list it because the third-party notice file must sit next to the project licence.)
- **Fix:** step 2.1/2.5: `LICENSE`, `NOTICE`, `THIRD_PARTY_NOTICES.txt` in every package root (and `usr/share/doc/harness-design-studio/` in the .deb), rewrite the `copyright` file as a real DEP-5 file listing the bundled components.
- **Likelihood/impact:** high (certain) / medium.
- **Owner decision:** covered by L-1.

### TPC-7 Windows: Microsoft runtime DLLs and `opengl32sw.dll` shipped without notice or verified terms
- **What:** `VCRUNTIME140.dll` 14.51.36247.0, `VCRUNTIME140_1.dll`, `MSVCP140*.dll` 14.44.35211.0, `ucrtbase.dll` 10.0.26100.1742 and 42 `api-ms-win-*.dll` (twice, GUI and CLI folders), plus `PySide6/opengl32sw.dll` (software OpenGL, LLVM visible in strings).
- **Where:** `_internal/` and `cli/_internal/` of the zip/installer.
- **Why:** these are not under an open-source licence; Microsoft's redistribution terms apply. Whether the GPL "System Library" exception covers them is a legal question. Mesa/LLVM notices missing.
- **Fix:** (a) keep and add a notice and a lawyer question; or (b) do not bundle the UCRT (`api-ms-win-*`, `ucrtbase.dll` are in Windows 10+ already; PyInstaller bundles them only when the build Python has them), require the VC++ Redistributable instead; (c) document `opengl32sw.dll` (Qt ships it unmodified; Qt's licence docs list it) and add Mesa/LLVM notices.
- **Likelihood/impact:** low / medium.
- **Owner decision:** yes, and a lawyer question.

### TPC-8 `LicenseRef-Qt-Commercial.txt` shipped in the Windows `LICENSES/`, nothing like it on Linux/macOS; source-install text refers to a PySide6 licence file that is not there
- **What:** `tools/collect_licences.py` copies any file named like a licence from the wheel's dist-info. The Windows wheels contain only the Qt *commercial* licence reference, so the Windows package has `LICENSES/pyside6-essentials/LicenseRef-Qt-Commercial.txt` and `shiboken6/...` ("Licensees holding valid commercial Qt licenses may use this software..."). The Linux wheel has no licence file. `strings.LICENCE_QT` says the texts are "with the PySide6 package (an installation from the source)": the PySide6 wheels have no LGPL text.
- **Where:** `zip/LICENSES/{pyside6-essentials,shiboken6}/`; `tools/collect_licences.py:24,73-77`; `gui/strings.py:2224`.
- **Why:** the packages differ per platform; the commercial text can be read as if a commercial licence were offered or in use. The source-install statement is wrong.
- **Fix:** in `collect_licences.py` write the same fixed Qt text for all platforms (skip `LicenseRef-Qt-*`); change the `LICENCE_QT` string to point to the LICENSES folder of the project's source (`packaging/licences/`).
- **Likelihood/impact:** medium / low.
- **Owner decision:** no.

### TPC-9 SBOM and licence report: not in repo, not on releases, cover only the Python venv; documents claim otherwise
- **What:** see section 5. Claims in `docs/SECURITY.md:26` and `compliance/docs/CMP.md:33` do not match the published releases. The generated SBOM lacks about 100 components of the Linux package and 150+ files in the Windows package.
- **Where:** `tools/gen_sbom.py`, `tools/licence_report.py`, `.github/workflows/harness-ci.yml:112`, `release.yml:208`.
- **Fix:** build the inventory from the **built package** (walk the unpacked `.deb`/zip; map each `.so`/`.dll` through `dpkg -S` / table), write `third-party-inventory-<version>.md` and a CycloneDX/SPDX SBOM per format, attach both to each release, and add a CI check that fails when the package has a file with no entry or the inventory has an entry with no file. Keep `ALLOWED_PACKAGES` as is.
- **Likelihood/impact:** high (certain) / medium.
- **Owner decision:** no (brief step 2.5 already asks for it).

### TPC-10 Licence policy and tests encode "permissive or LGPL only"; will fail once the project is GPL-3.0-only and does not cover non-Python components
- **What:** `REQ-LIC-01` (`docs/REQUIREMENTS.md:9`, `docs/SPEC.md:32`, D-02, D-43) says dependencies must be permissive or LGPL "allowing closed internal use". `tools/licence_report.py` rejects GPL and unlisted licences (including MPL) and `OWN` is `LicenseRef-Proprietary`; `tests/test_licences.py` tests this. The allow-list sees only Python metadata.
- **Fix:** update REQ-LIC-01, D-02/D-43 and the allow-list for GPL-3.0-only; add the licences in section 7 as an explicit allow-list (SPDX ids) for native components; make the check read the package inventory, not just the venv.
- **Likelihood/impact:** certain / low.
- **Owner decision:** follows L-1.

### TPC-11 Transitive dependencies and build host are not pinned
- **What:** only top-level runtime packages and dev extras are pinned (`pyproject.toml:15,21-29`). `typing_extensions`, `typing-inspection`, `annotated-types`, `pydantic_core` (pinned by pydantic), `et_xmlfile`, `shiboken6` (pinned by PySide6) float. No lock file, no hashes. The Ubuntu libraries come from whatever the runner had on build day (all 87 equal today's Ubuntu 24.04 updates). Evidence: `typing-inspection` 0.4.4 in 1.0.0 and macOS 1.5.0, 0.4.5 in 1.17.0. The dev resolution today is 84 packages, unpinned beyond the 15 listed.
- **Fix:** commit a hashed lock file (`pip-compile --generate-hashes` or `uv.lock`) used by CI and release, record Ubuntu package versions in the inventory (TPC-9).
- **Likelihood/impact:** medium / low.
- **Owner decision:** no.

### TPC-12 Packages carry modules that are not used and contradict the documentation
- **What:** `libQt6Network.so.6` (plus `libgssapi_krb5` and friends) and `libQt6Svg.so.6` with the svg plugins ship although `PySide6.QtNetwork` and `PySide6.QtSvg` are excluded from the Python side and the code docstrings say "The packaged program leaves out QtSvg" (`gui/icons.py:3`, `gui/appicon.py:4`). Also shipped: Wayland, EGLFS/KMS, LinuxFB, VNC, Vulkan-display, IBus, evdev, TUIO plugins and 96 translations. A Qt library that can open sockets is present in a program documented as "never uses the network" (`README`, release notes).
- **Where:** `tools/build_installer.py:26-31` (`EXCLUDES` removes only Python modules); file list.
- **Why:** licence surface (TPC-2/4), size (278 MB), attack surface, and accuracy of claims (relevant to the "claims" auditor).
- **Fix:** prune binaries via a spec file (`excludes` for binaries, `a.binaries` filter) and keep the selftest and the no-network test; or correct the docstrings and the claim to "the program does not call Qt Network".
- **Likelihood/impact:** medium / low.
- **Owner decision:** yes (pruning changes package contents).

### TPC-13 Replaceability of Qt is possible but not explained; macOS signature blocks it
- **What:** Qt is dynamic, one-folder, unmodified (section 3). The only text: "It is a separate library in this package: you may replace it with another build of the same version." No steps (which folder, which files, same major.minor ABI). On macOS (releases 1.2.0 to 1.5.0) `_CodeSignature` is ad-hoc, a replaced framework breaks it.
- **Fix:** add 5 lines to `THIRD_PARTY_NOTICES.txt`: path of the Qt libs per platform, that PySide6 bindings must be the same 6.11.x, how to run with `LD_LIBRARY_PATH` or by replacing the file. State that the app code is source-available under GPL.
- **Likelihood/impact:** low / low.
- **Owner decision:** no.

### TPC-14 Licence choices must be recorded: Qt option, FreeType, cairo, graphite2, libdbus, libcap, libzstd
- **What:** several bundled libraries are dual-licensed. To stay GPL-3.0-only compatible the recorded choice must be: Qt `LGPL-3.0-only` (or `GPL-3.0-only`), never `GPL-2.0-only`; FreeType `FTL` (the other option is GPL-2.0-only, not compatible); Cairo `LGPL-2.1`; graphite2 `LGPL-2.1+`; libdbus `GPL-2+`; libcap and libzstd `BSD-3-clause`. The FTL-with-GPL-3 compatibility is **unverified** (FSF page not reachable).
- **Fix:** record the choices in `THIRD_PARTY_NOTICES.txt` and the inventory; lawyer to confirm FTL.
- **Likelihood/impact:** low / low.
- **Owner decision:** no (lawyer question for FTL).

### TPC-15 PyInstaller bootloader: no notice, version not recorded
- **What:** every program is a PyInstaller bootloader (GPL-2.0-or-later with exception). No PyInstaller licence or version is shipped or recorded; `pyinstaller==6.22.3` is a dev pin only.
- **Fix:** record the PyInstaller version in the inventory and add its COPYING text to `THIRD_PARTY_NOTICES.txt` (harmless under GPL-3).
- **Likelihood/impact:** low / low.
- **Owner decision:** no.

### TPC-16 macOS releases 1.2.0 to 1.5.0 remain public with the same gaps and a made-up bundle identifier
- **What:** the 1.5.0 `.dmg` has Python 3.12.10, OpenSSL 3.0.16, six Qt frameworks and the same `LICENSES/` as Linux (no Python/OpenSSL notices, no source offer, no project licence). `Info.plist`: `CFBundleIdentifier org.harnessdesignstudio.app`, `NSHumanReadableCopyright` "Harness Design Studio". macOS was removed after 1.5.0 (D-168) but the files are still downloadable.
- **Fix:** part of the "existing releases" decision (brief 2.9.8). Checking whether the reverse-DNS prefix `org.harnessdesignstudio` is a domain someone else owns belongs to the trademark/name auditor.
- **Likelihood/impact:** medium / low.
- **Owner decision:** yes (what to do with old releases).

### TPC-17 Lucide notice text is not the upstream licence of the version used
- **What:** the notice in `gui/licences.py:17-` (`LUCIDE_LICENCES`, shipped as `LICENSES/lucide/LICENSE.txt`) reads "Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022 as part of Feather (MIT). All other copyright (c) for Lucide are held by Lucide Contributors 2022." The `LICENSE` of Lucide tag 1.56.0 reads "ISC License / Copyright (c) 2026 Lucide Icons and Contributors" plus a list of Feather-derived icons and the MIT text. Also the string "geometry taken from lucide-static 1.56.0" could be proven for 27 of 52 icons only.
- **Fix:** ship the upstream `LICENSE` of the exact tag verbatim; list which of the 58 icons derive from Feather.
- **Likelihood/impact:** low / low.
- **Owner decision:** no.

### TPC-18 About page lists only 4 components
- **What:** `gui/licences.py:COMPONENTS` shows Inter, JetBrains Mono, Lucide/Feather and Qt only; pydantic, openpyxl, defusedxml and so on are in the package `LICENSES/` but not in the About page; the first-listed licence for Qt there is LGPL only.
- **Fix:** list all components from the generated inventory in the About/Licences view (brief step 2.1 also needs the full GPL text there).
- **Likelihood/impact:** low / low.
- **Owner decision:** no.

### TPC-19 v1.0.0 .deb: first public package
- **What:** content is as 1.17.0 except: Python 3.12.15, IBM Plex Sans/Mono woff2 fonts (OFL-1.1, `OFL-1.1-IBM-Plex.txt` shipped, RFN "Plex"), no Lucide, 12 Qt libs + ICU 73 + 45 plugins as now. No project licence, no notices for Python/OpenSSL/system libs, no source offer. `copyright` says "No licence is granted".
- **Fix:** same decision as TPC-16 (old releases).
- **Owner decision:** yes (same as TPC-16).

## 10. Proposed order of work for step 2.5

1. Decide TPC-1 and TPC-2 route (host sources vs prune and depend).
2. Write one build step that makes `THIRD_PARTY_NOTICES.txt`, the inventory and the SBOM from the *unpacked package*, and a CI check that compares them with the package (TPC-3,4,5,9).
3. Fix `collect_licences.py` for TPC-8, TPC-17.
4. Update the licence policy and allow-list (TPC-10).
5. Lock file (TPC-11).

## 11. Could not verify

- **Windows `setup.exe` payload.** `innoextract 1.9` and `7z` cannot read Inno Setup 6.7.0. I assumed it equals the zip (from the `.iss` file). No file inside it was seen.
- **Exact bootloader version** of PyInstaller in the shipped binaries (inferred 6.22.3 from the pin).
- **Where the CPython 3.14.10 build came from** (python.org, setup-python or other) and its upstream licence file; the Python and OpenSSL licence texts are not in any package, so their licence is stated from general knowledge, not from a file.
- **Licences of the Rust crates** inside pydantic_core, of the **Qt-internal third-party code** actually compiled into the wheels, of **ICU 73**, of **`opengl32sw.dll`** (Mesa/LLVM), of the **Microsoft DLLs**, and of the **Inno Setup runtime**.
- **Qt module licences not read from a source header:** Qt Wayland client (`.cpp` paths returned 404; only `REUSE.toml` json annotations read), the wayland decoration/shell/graphics plugins, `libqevdev*`, `libqicns`, `libqwebp`, `libqtiff`, `libqtga`, `libqwbmp`, `libqvkkhrdisplay`, `libqlinuxfb` was read, `libqeglfs-*` integrations (only `eglfs` main read). I assume the whole of qtbase `src/plugins` is the same four-way expression because every file I read is.
- **Qt documentation** (`doc.qt.io` module licence table): blocked by the proxy.
- **The FSF statement on FreeType Licence and GPL-3.**
- **Whether the CI artifact with the SBOM still exists** and what it contains (needs GitHub auth; the GitHub API is blocked for this session). I judged from the code.
- **Windows binaries byte-wise against the Windows wheels** (only licence files compared). macOS contents were not compared with wheels.
- **Lucide: 25 of 52 icons** not matched by my path-only comparison.
- **Dev-set licences** are from PyPI JSON of today's resolution, not read from wheel files, and not relevant to distribution.
- **The IBM Plex woff2 files** in 1.0.0 were not compared with upstream.
- **Whether any of the 87 bundled libs has a different licence per file than the headline in the Debian `copyright` file** (I used the package-level paragraph; for util-linux, libkeyutils, libcom_err the per-file view was not resolved).
