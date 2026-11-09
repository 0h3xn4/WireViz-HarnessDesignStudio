# Third-party inventory 1.17.0 (linux)

Made from the built package (`python -m tools.third_party inventory`), not from the metadata of a build environment. Not legal advice; a licence marked `unknown` or `LicenseRef-` needs a person's decision.

| Component | Version | Licence | Kind | Source of the information | Files |
| --- | --- | --- | --- | --- | --- |
| PyInstaller bootloader and runtime hooks | 6.22.3 | GPL-2.0-or-later WITH Bootloader-exception | bootloader | the packages are built with PyInstaller (tools/build_installer.py) | 3 |
| Inter (font) | 4.1 | OFL-1.1 | font | file names; versions from decision D-150 | 9 |
| JetBrains Mono (font) | 2.304 | OFL-1.1 | font | file names; versions from decision D-150 | 7 |
| Lucide and Feather icon outlines (gui/icons.py) | lucide-static 1.56.0 | ISC AND MIT | icon | gui/icons.py | 0 |
| annotated-types | 0.8.0 | MIT | python | LICENSES/README.txt of the package (written at build time) | 1 |
| defusedxml | 0.7.1 | PSFL | python | LICENSES/README.txt of the package (written at build time) | 1 |
| et_xmlfile | 2.0.0 | MIT | python | LICENSES/README.txt of the package (written at build time) | 3 |
| openpyxl | 3.1.5 | MIT | python | LICENSES/README.txt of the package (written at build time) | 1 |
| pydantic | 2.13.5 | MIT | python | dist-info METADATA | 2 |
| pydantic_core | 2.46.5 | MIT | python | LICENSES/README.txt of the package (written at build time) | 1 |
| PySide6_Essentials | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | python | LICENSES/README.txt of the package (written at build time) | 0 |
| shiboken6 | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only | python | LICENSES/README.txt of the package (written at build time) | 0 |
| typing-inspection | 0.4.5 | MIT | python | LICENSES/README.txt of the package (written at build time) | 1 |
| typing_extensions | 4.16.0 | PSF-2.0 | python | LICENSES/README.txt of the package (written at build time) | 1 |
| Qt (Core, DBus, EglFSDeviceIntegration, EglFsKmsSupport, Gui, Network, OpenGL, Svg, WaylandClient, Widgets, WlShellIntegration, XcbQpa) | 6.11.2 | LGPL-3.0-only (chosen; Qt for Python and Qt are also offered under GPL-2.0-only, GPL-3.0-only and a commercial licence) | qt | library file names; version of PySide6 | 69 |
| CPython runtime | 3.14.10 | PSF-2.0 | runtime | library file name; version string inside it | 2 |
| ICU (libicudata, libicui18n, libicuuc) | 73 | ICU AND Unicode-DFS-2016 | system | libicu*.so.N beside Qt in the PySide6 wheel; the licence from the ICU project | 3 |
| libatk-bridge2.0-0t64 | 2.52.0-1build1 | LGPL-2.0-or-later | system | dpkg -S libatk-bridge-2.0.so.0; /usr/share/doc/libatk-bridge2.0-0t64/copyright | 1 |
| libatk1.0-0t64 | 2.52.0-1build1 | LGPL-2.0-or-later | system | dpkg -S libatk-1.0.so.0; /usr/share/doc/libatk1.0-0t64/copyright | 1 |
| libatspi2.0-0t64 | 2.52.0-1build1 | LGPL-2.0-or-later | system | dpkg -S libatspi.so.0; /usr/share/doc/libatspi2.0-0t64/copyright | 1 |
| libblkid1 | 2.39.3-9ubuntu6.6 | LGPL-2.1-or-later | system | dpkg -S libblkid.so.1; /usr/share/doc/libblkid1/copyright | 1 |
| libbrotli1 | 1.1.0-2ubuntu0.1 | MIT | system | dpkg -S libbrotlicommon.so.1; /usr/share/doc/libbrotli1/copyright | 2 |
| libbsd0 | 0.12.1-1build1.1 | BSD-3-Clause AND ISC | system | dpkg -S libbsd.so.0; /usr/share/doc/libbsd0/copyright | 1 |
| libbz2-1.0 | 1.0.8-5.1ubuntu0.1 | bzip2-1.0.6 | system | dpkg -S libbz2.so.1.0; /usr/share/doc/libbz2-1.0/copyright | 2 |
| libcairo-gobject2 | 1.18.0-3build1 | LGPL-2.1-only OR MPL-1.1 | system | dpkg -S libcairo-gobject.so.2; /usr/share/doc/libcairo-gobject2/copyright | 1 |
| libcairo2 | 1.18.0-3build1 | LGPL-2.1-only OR MPL-1.1 | system | dpkg -S libcairo.so.2; /usr/share/doc/libcairo2/copyright | 1 |
| libcap2 | 1:2.66-5ubuntu2.4 | BSD-3-Clause OR GPL-2.0-only | system | dpkg -S libcap.so.2; /usr/share/doc/libcap2/copyright | 1 |
| libcom-err2 | 1.47.0-2.4~exp1ubuntu4.1 | MIT | system | dpkg -S libcom_err.so.2; /usr/share/doc/libcom-err2/copyright | 1 |
| libdatrie1 | 0.2.13-3build1 | LGPL-2.1-or-later | system | dpkg -S libdatrie.so.1; /usr/share/doc/libdatrie1/copyright | 1 |
| libdbus-1-3 | 1.14.10-4ubuntu4.1 | AFL-2.1 OR GPL-2.0-or-later | system | dpkg -S libdbus-1.so.3; /usr/share/doc/libdbus-1-3/copyright | 1 |
| libepoxy0 | 1.5.10-1build1 | MIT | system | dpkg -S libepoxy.so.0; /usr/share/doc/libepoxy0/copyright | 1 |
| libexpat1 | 2.6.1-2ubuntu0.6 | MIT | system | dpkg -S libexpat.so.1; /usr/share/doc/libexpat1/copyright | 1 |
| libffi8 | 3.4.6-1build1 | MIT | system | dpkg -S libffi.so.8; /usr/share/doc/libffi8/copyright | 2 |
| libfontconfig1 | 2.15.0-1.1ubuntu2 | HPND-sell-variant | system | dpkg -S libfontconfig.so.1; /usr/share/doc/libfontconfig1/copyright | 1 |
| libfreetype6 | 2.13.2+dfsg-1ubuntu0.2 | FTL OR GPL-2.0-or-later | system | dpkg -S libfreetype.so.6; /usr/share/doc/libfreetype6/copyright | 1 |
| libfribidi0 | 1.0.13-3build1 | LGPL-2.1-or-later | system | dpkg -S libfribidi.so.0; /usr/share/doc/libfribidi0/copyright | 1 |
| libgcc-s1 | 14.2.0-4ubuntu2~24.04.1 | GPL-3.0-or-later WITH GCC-exception-3.1 | system | dpkg -S libgcc_s.so.1; /usr/share/doc/libgcc-s1/copyright | 2 |
| libgcrypt20 | 1.10.3-2ubuntu0.2 | LGPL-2.1-or-later | system | dpkg -S libgcrypt.so.20; /usr/share/doc/libgcrypt20/copyright | 1 |
| libgdk-pixbuf-2.0-0 | 2.42.10+dfsg-3ubuntu3.3 | LGPL-2.0-or-later AND LGPL-2.1-or-later AND CC0-1.0 | system | dpkg -S libgdk_pixbuf-2.0.so.0; /usr/share/doc/libgdk-pixbuf-2.0-0/copyright | 1 |
| libglib2.0-0t64 | 2.80.0-6ubuntu3.10 | LGPL-2.1-or-later | system | dpkg -S libgio-2.0.so.0; /usr/share/doc/libglib2.0-0t64/copyright | 5 |
| libgpg-error0 | 1.47-3build2.1 | LGPL-2.1-or-later | system | dpkg -S libgpg-error.so.0; /usr/share/doc/libgpg-error0/copyright | 1 |
| libgraphite2-3 | 1.3.14-2ubuntu0.24.04.1 | LGPL-2.1-or-later OR MPL-1.1 OR GPL-2.0-or-later | system | dpkg -S libgraphite2.so.3; /usr/share/doc/libgraphite2-3/copyright | 1 |
| libgssapi-krb5-2 | 1.20.1-6ubuntu2.10 | MIT | system | dpkg -S libgssapi_krb5.so.2; /usr/share/doc/libgssapi-krb5-2/copyright | 1 |
| libgtk-3-0t64 | 3.24.41-4ubuntu1.3 | LGPL-2.0-or-later AND LGPL-2.1-or-later AND MIT | system | dpkg -S libgdk-3.so.0; /usr/share/doc/libgtk-3-0t64/copyright | 2 |
| libharfbuzz0b | 8.3.0-2build2 | MIT | system | dpkg -S libharfbuzz.so.0; /usr/share/doc/libharfbuzz0b/copyright | 1 |
| libjpeg-turbo8 | 2.1.5-2ubuntu2 | IJG AND BSD-3-Clause AND Zlib | system | dpkg -S libjpeg.so.8; /usr/share/doc/libjpeg-turbo8/copyright | 1 |
| libk5crypto3 | 1.20.1-6ubuntu2.10 | MIT | system | dpkg -S libk5crypto.so.3; /usr/share/doc/libk5crypto3/copyright | 1 |
| libkeyutils1 | 1.6.3-3build1 | LGPL-2.0-or-later | system | dpkg -S libkeyutils.so.1; /usr/share/doc/libkeyutils1/copyright | 1 |
| libkrb5-3 | 1.20.1-6ubuntu2.10 | MIT | system | dpkg -S libkrb5.so.3; /usr/share/doc/libkrb5-3/copyright | 1 |
| libkrb5support0 | 1.20.1-6ubuntu2.10 | MIT | system | dpkg -S libkrb5support.so.0; /usr/share/doc/libkrb5support0/copyright | 1 |
| liblz4-1 | 1.9.4-1build1.1 | BSD-2-Clause | system | dpkg -S liblz4.so.1; /usr/share/doc/liblz4-1/copyright | 1 |
| liblzma5 | 5.6.1+really5.4.5-1ubuntu0.4 | public domain | system | dpkg -S liblzma.so.5; /usr/share/doc/liblzma5/copyright | 2 |
| libmd0 | 1.1.0-2build1.1 | BSD-3-Clause AND ISC AND public domain | system | dpkg -S libmd.so.0; /usr/share/doc/libmd0/copyright | 1 |
| libmount1 | 2.39.3-9ubuntu6.6 | LGPL-2.1-or-later | system | dpkg -S libmount.so.1; /usr/share/doc/libmount1/copyright | 1 |
| libpango-1.0-0 | 1.52.1+ds-1build1 | LGPL-2.0-or-later AND LGPL-2.1-or-later | system | dpkg -S libpango-1.0.so.0; /usr/share/doc/libpango-1.0-0/copyright | 1 |
| libpangocairo-1.0-0 | 1.52.1+ds-1build1 | LGPL-2.0-or-later AND LGPL-2.1-or-later | system | dpkg -S libpangocairo-1.0.so.0; /usr/share/doc/libpangocairo-1.0-0/copyright | 1 |
| libpangoft2-1.0-0 | 1.52.1+ds-1build1 | LGPL-2.0-or-later AND LGPL-2.1-or-later | system | dpkg -S libpangoft2-1.0.so.0; /usr/share/doc/libpangoft2-1.0-0/copyright | 1 |
| libpcre2-8-0 | 10.42-4ubuntu2.1 | BSD-3-Clause | system | dpkg -S libpcre2-8.so.0; /usr/share/doc/libpcre2-8-0/copyright | 1 |
| libpixman-1-0 | 0.42.2-1build1 | MIT | system | dpkg -S libpixman-1.so.0; /usr/share/doc/libpixman-1-0/copyright | 1 |
| libpng16-16t64 | 1.6.43-5ubuntu0.7 | libpng-2.0 | system | dpkg -S libpng16.so.16; /usr/share/doc/libpng16-16t64/copyright | 1 |
| libselinux1 | 3.5-2ubuntu2.1 | public domain | system | dpkg -S libselinux.so.1; /usr/share/doc/libselinux1/copyright | 1 |
| libssl3t64 | 3.0.13-0ubuntu3.16 | Apache-2.0 | system | dpkg -S libcrypto.so.3; /usr/share/doc/libssl3t64/copyright | 4 |
| libstdc++6 | 14.2.0-4ubuntu2~24.04.1 | GPL-3.0-or-later WITH GCC-exception-3.1 | system | dpkg -S libstdc++.so.6; /usr/share/doc/libstdc++6/copyright | 1 |
| libsystemd0 | 255.4-1ubuntu8.18 | LGPL-2.1-or-later | system | dpkg -S libsystemd.so.0; /usr/share/doc/libsystemd0/copyright | 1 |
| libthai0 | 0.1.29-2build1 | LGPL-2.1-or-later | system | dpkg -S libthai.so.0; /usr/share/doc/libthai0/copyright | 1 |
| libuuid1 | 2.39.3-9ubuntu6.6 | BSD-3-Clause | system | dpkg -S libuuid.so.1; /usr/share/doc/libuuid1/copyright | 2 |
| libx11-6 | 2:1.8.7-1ubuntu0.1 | MIT | system | dpkg -S libX11.so.6; /usr/share/doc/libx11-6/copyright | 1 |
| libx11-xcb1 | 2:1.8.7-1ubuntu0.1 | MIT | system | dpkg -S libX11-xcb.so.1; /usr/share/doc/libx11-xcb1/copyright | 1 |
| libxau6 | 1:1.0.9-1build6 | MIT | system | dpkg -S libXau.so.6; /usr/share/doc/libxau6/copyright | 1 |
| libxcb-cursor0 | 0.1.4-1build1 | MIT | system | dpkg -S libxcb-cursor.so.0; /usr/share/doc/libxcb-cursor0/copyright | 1 |
| libxcb-glx0 | 1.15-1ubuntu2 | MIT | system | dpkg -S libxcb-glx.so.0; /usr/share/doc/libxcb-glx0/copyright | 1 |
| libxcb-icccm4 | 0.4.1-1.1build3 | MIT | system | dpkg -S libxcb-icccm.so.4; /usr/share/doc/libxcb-icccm4/copyright | 1 |
| libxcb-image0 | 0.4.0-2build1 | MIT | system | dpkg -S libxcb-image.so.0; /usr/share/doc/libxcb-image0/copyright | 1 |
| libxcb-keysyms1 | 0.4.0-1build4 | MIT | system | dpkg -S libxcb-keysyms.so.1; /usr/share/doc/libxcb-keysyms1/copyright | 1 |
| libxcb-randr0 | 1.15-1ubuntu2 | MIT | system | dpkg -S libxcb-randr.so.0; /usr/share/doc/libxcb-randr0/copyright | 1 |
| libxcb-render-util0 | 0.3.9-1build4 | MIT | system | dpkg -S libxcb-render-util.so.0; /usr/share/doc/libxcb-render-util0/copyright | 1 |
| libxcb-render0 | 1.15-1ubuntu2 | MIT | system | dpkg -S libxcb-render.so.0; /usr/share/doc/libxcb-render0/copyright | 1 |
| libxcb-shape0 | 1.15-1ubuntu2 | MIT | system | dpkg -S libxcb-shape.so.0; /usr/share/doc/libxcb-shape0/copyright | 1 |
| libxcb-shm0 | 1.15-1ubuntu2 | MIT | system | dpkg -S libxcb-shm.so.0; /usr/share/doc/libxcb-shm0/copyright | 1 |
| libxcb-sync1 | 1.15-1ubuntu2 | MIT | system | dpkg -S libxcb-sync.so.1; /usr/share/doc/libxcb-sync1/copyright | 1 |
| libxcb-util1 | 0.4.0-1build3 | MIT | system | dpkg -S libxcb-util.so.1; /usr/share/doc/libxcb-util1/copyright | 1 |
| libxcb-xfixes0 | 1.15-1ubuntu2 | MIT | system | dpkg -S libxcb-xfixes.so.0; /usr/share/doc/libxcb-xfixes0/copyright | 1 |
| libxcb-xkb1 | 1.15-1ubuntu2 | MIT | system | dpkg -S libxcb-xkb.so.1; /usr/share/doc/libxcb-xkb1/copyright | 1 |
| libxcomposite1 | 1:0.4.5-1build3 | MIT | system | dpkg -S libXcomposite.so.1; /usr/share/doc/libxcomposite1/copyright | 1 |
| libxcursor1 | 1:1.2.1-1build1 | MIT | system | dpkg -S libXcursor.so.1; /usr/share/doc/libxcursor1/copyright | 1 |
| libxdamage1 | 1:1.1.6-1build1 | MIT | system | dpkg -S libXdamage.so.1; /usr/share/doc/libxdamage1/copyright | 1 |
| libxdmcp6 | 1:1.1.3-0ubuntu6 | MIT | system | dpkg -S libXdmcp.so.6; /usr/share/doc/libxdmcp6/copyright | 1 |
| libxext6 | 2:1.3.4-1build2 | MIT | system | dpkg -S libXext.so.6; /usr/share/doc/libxext6/copyright | 1 |
| libxfixes3 | 1:6.0.0-2build1 | MIT | system | dpkg -S libXfixes.so.3; /usr/share/doc/libxfixes3/copyright | 1 |
| libxi6 | 2:1.8.1-1build1 | MIT | system | dpkg -S libXi.so.6; /usr/share/doc/libxi6/copyright | 1 |
| libxinerama1 | 2:1.1.4-3build1 | MIT | system | dpkg -S libXinerama.so.1; /usr/share/doc/libxinerama1/copyright | 1 |
| libxkbcommon-x11-0 | 1.6.0-1build1 | MIT | system | dpkg -S libxkbcommon-x11.so.0; /usr/share/doc/libxkbcommon-x11-0/copyright | 1 |
| libxkbcommon0 | 1.6.0-1build1 | MIT | system | dpkg -S libxkbcommon.so.0; /usr/share/doc/libxkbcommon0/copyright | 1 |
| libxrandr2 | 2:1.5.2-2build1 | MIT | system | dpkg -S libXrandr.so.2; /usr/share/doc/libxrandr2/copyright | 1 |
| libxrender1 | 1:0.9.10-1.1build1 | MIT | system | dpkg -S libXrender.so.1; /usr/share/doc/libxrender1/copyright | 1 |
| libzstd1 | 1.5.5+dfsg2-2build1.1 | BSD-3-Clause OR GPL-2.0-only | system | dpkg -S libzstd.so.1; /usr/share/doc/libzstd1/copyright | 2 |
| zlib1g | 1:1.3.dfsg-3.1ubuntu2.3 | Zlib | system | dpkg -S libz.so.1; /usr/share/doc/zlib1g/copyright | 2 |
