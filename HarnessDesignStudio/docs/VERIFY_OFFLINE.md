# Verify it yourself in 30 minutes: no network, no telemetry

This page is for a colleague who wants to check, without trusting the people who made the tool, that Harness Design Studio does not use the network and does not send or copy design data anywhere. Every check runs on the package you download from the release page, with tools of the operating system. What each check shows, and what it cannot show, is said with it. The same checks run automatically on every change and on every release (`tools/offline_audit.py`, the end of this page); the report of a release is attached to its release page as `offline-audit-<version>.md` and `.json`.

## Contents

- [What is claimed, and what is not](#what-is-claimed-and-what-is-not)
- [1. Check that you have the published file (2 minutes)](#1-check-that-you-have-the-published-file-2-minutes)
- [Linux (Ubuntu 24.04)](#linux-ubuntu-2404)
- [Windows 10 and 11](#windows-10-and-11)
- [The automatic audit](#the-automatic-audit)
- [Switch Python plug-ins off on your computers](#switch-python-plug-ins-off-on-your-computers)

## What is claimed, and what is not

**Claimed:** the program opens no network connection, listens on no port, looks up no host name and starts no program but its own design rule check helper (itself, with `--drc-worker`). Design data is written only into the project folder, its outputs and its backups, with three exceptions that stay on your computer and are named here: the editor's **recent-projects list** in its settings file keeps the folder, the **project name** and the numbers of devices, interfaces and harnesses of each project opened (**Clear list** on the Home page removes them); while a build workbook (`.xlsx`) is written, its worksheets are in **temporary files** of the system's temporary folder for that moment (made by the spreadsheet library openpyxl, deleted at once); and the window title (the project name) goes to your display server.

**Not claimed:**

- A test shows the absence of network use only on the paths it runs. The workflow below is broad (start, examples, import, generate, check, export with drawings, open data, release, the editor, errors, idle time), but not every menu.
- A **trusted Python plug-in** (S8) runs with your rights and can use the network: that is how plug-ins work. No plug-in runs unless a project enables it **and** you trusted that exact code; your IT department can switch plug-ins off entirely ([below](#switch-python-plug-ins-off-on-your-computers)). Rules and tables written as data (declarative extensions) are never run and are not affected.
- The operating system, the desktop (its file dialogs run in other processes) and the **browser** that shows the guide when you press F1 are outside the claim. The guide itself is one local HTML file that loads nothing from elsewhere (a test checks it).
- The packages are not code-signed; the checksum shows that your file is the published one, not who made it ([`SECURITY.md`](SECURITY.md)).

## 1. Check that you have the published file (2 minutes)

Download the package and `SHA256SUMS` from the release page into one folder.

Linux:

```
sha256sum -c SHA256SUMS --ignore-missing
```

Windows (PowerShell): compare the output with the line of your file in `SHA256SUMS`.

```
Get-FileHash -Algorithm SHA256 .\harness-design-studio-<version>-windows-x86_64.zip
```

## Linux (Ubuntu 24.04)

Unpack the `.tar.gz` into a new folder (nothing is installed) and make a project to try it on. The commands use `HDS` for the command line program:

```
mkdir hds-check && cd hds-check
tar xzf ../harness-design-studio-<version>-linux-x86_64.tar.gz
HDS=$PWD/harness-design-studio/cli/harness-design-studio
GUI=$PWD/harness-design-studio/harness-design-studio-gui
```

**2. It works without a network (5 minutes).** Run the commands in a network namespace that has no network at all (only a loopback device that is down):

```
unshare -rn sh -c "cat /proc/net/dev; $HDS new p --template flatsat && $HDS generate p && $HDS export p --drawings && $HDS export-data p --out p-data && $HDS release p W001 --by Me --comment 'Offline check release' --accept-placeholders 'offline check only' --accept-unapproved-parts 'offline check only'"
```

Expected: `/proc/net/dev` lists only `lo`, and every command succeeds. If `unshare` says `Operation not permitted`, your system restricts user namespaces (Ubuntu 24.04 does, through AppArmor); use `sudo unshare -n sudo -u $USER sh -c "..."` instead, or pull the network cable. The editor works the same way: `unshare -rn $GUI` (it needs a display; on a desktop the display is reached through a local socket, which works inside the namespace for the classic X display; a Wayland session may need `QT_QPA_PLATFORM=xcb`).

**3. It does not even try (10 minutes).** Run the same commands with the normal network, under `strace`, which logs every network call and every program started (`sudo apt-get install strace` if it is missing):

```
strace -f -e trace=%network,%process -o trace.log $HDS export p --drawings
strace -f -e trace=%network,%process -o gui.log $GUI p      # use the editor a while, press F1, close it
grep -E 'socket\(|connect\(|sendto\(|sendmsg\(|bind\(|listen\(' trace.log gui.log
grep execve trace.log gui.log
```

Expected: no `AF_INET`, `AF_INET6`, `AF_NETLINK` or `AF_PACKET` at all; in `gui.log` only `AF_UNIX` (the local display and desktop bus) and connects to local paths such as `/tmp/.X11-unix/X0` or the session bus. `execve` names only the program itself (the packaged program starts itself once more in the same process), the editor started again with `--drc-worker` (the design rule check helper), and, on a display without a desktop session, `dbus-launch`. Pressing F1 hands the guide to your desktop (`xdg-open`, then your browser): that is the one thing the editor asks another program to do, and it is a local file.

**4. Which network code is even there (3 minutes).** The package carries no Qt network library, no VNC or TUIO plug-in, no Kerberos and no TLS library (from the release after 1.17.0; they are removed at build time and the build fails if one comes back):

```
find harness-design-studio \( -iname '*Network*' -o -iname '*ssl*' -o -iname '*krb5*' -o -iname '*gssapi*' -o -iname '*vnc*' -o -iname '*tuio*' -o -iname '*WebEngine*' \)
```

Expected: nothing. While the editor runs, list what it has loaded: `grep -E 'Network|ssl|crypto|krb5|gssapi|curl|resolv' /proc/$(pgrep -f harness-design-studio-gui | head -1)/maps`. Expected: nothing, or only `libcrypto` when your build of Python takes SHA-256 from OpenSSL's crypto library (no TLS).

**5. Design data stays in the project (5 minutes).** Put a word nobody else uses into the project, for example `ZqxCanary42`, as a device name and a note (in the editor, or by editing `p/logical/units/*.json`), run the commands and the editor again, then search everywhere you can read:

```
grep -rIl --exclude-dir=p --exclude-dir=p-data ZqxCanary42 ~ /tmp /var/tmp 2>/dev/null
```

Expected: nothing; only if the word is also in the **project name** does `~/.config/HarnessDesigner/HarnessDesigner.ini` (the recent-projects list) hold it. For the temporary files of the workbook, run `strace -f -e trace=openat,write -s 200 -o w.log $HDS export p` and `grep ZqxCanary42 w.log | grep -v '/p/'`: they show up as `openpyxl.*` files of your temporary folder, which are deleted when the workbook is written.

**6. Optional: a packet capture.** In a namespace that does have a network (a pair of virtual cables to the host), any packet the program sent would show:

```
sudo ip netns add hds && sudo ip link add hds0 type veth peer name hds1 && sudo ip link set hds1 netns hds
sudo ip addr add 10.99.0.1/24 dev hds0 && sudo ip link set hds0 up
sudo ip netns exec hds sh -c 'ip addr add 10.99.0.2/24 dev hds1; ip link set hds1 up; ip link set lo up; ip route add default via 10.99.0.1'
sudo tcpdump -i hds0 -w hds.pcap &
sudo ip netns exec hds sudo -u $USER $HDS export p --drawings
sudo kill %1; tcpdump -r hds.pcap | wc -l       # expected: 0 packets (IPv6 router solicitations of the kernel itself aside)
sudo ip netns del hds
```

## Windows 10 and 11

Extract the `.zip` into a new folder, for example `C:\hds-check`, and open **PowerShell as administrator** there.

**2. Block it from the network and see that it works (5 minutes).**

```
Get-ChildItem C:\hds-check -Recurse -Filter *.exe | ForEach-Object {
  New-NetFirewallRule -DisplayName "HDS check $($_.Name) out" -Direction Outbound -Program $_.FullName -Action Block
  New-NetFirewallRule -DisplayName "HDS check $($_.Name) in" -Direction Inbound -Program $_.FullName -Action Block }
$HDS = "C:\hds-check\cli\harness-design-studio.exe"
& $HDS new p --template flatsat; & $HDS generate p; & $HDS export p --drawings; & $HDS export-data p --out p-data
```

Expected: every command succeeds. Start the editor (`harness-design-studio-gui.exe`), open the project, press F1, use it a while.

**3. It does not even try (10 minutes).** Switch on Windows' own audit of every connection the filtering platform allows or blocks, and of every program started, then repeat step 2:

```
auditpol /set /subcategory:"Filtering Platform Connection" /success:enable /failure:enable
auditpol /set /subcategory:"Process Creation" /success:enable
# ... run the commands and the editor again ...
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=5152,5156,5157,5158,5159} | Where-Object { $_.Message -match 'harness-design-studio' }
Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4688} | Where-Object { $_.Message -match 'Creator Process Name:.*harness-design-studio' } | Format-List TimeCreated, Message
```

Expected: no filtering-platform event of a `harness-design-studio` program (5156 would be an allowed connection, 5157 a blocked one, 5158 and 5159 a port it listened on). The programs it started are the editor itself with `--drc-worker` and `conhost.exe` (Windows' console host for the command line program). Live, **Resource Monitor** (`resmon`), tab **Network**, shows no `harness-design-studio` process at all. A packet capture (`pktmon start --capture -f hds.etl`, then `pktmon stop`) records the whole computer's traffic and needs filtering by hand; the firewall audit above is the per-program record. Afterwards: `Remove-NetFirewallRule -DisplayName "HDS check*"` and set the audit back (`/success:disable /failure:disable`).

**4. Which network code is even there.** `Get-ChildItem C:\hds-check -Recurse | Where-Object Name -match 'Network|ssl|vnc|tuio|WebEngine'` lists nothing (from the release after 1.17.0). `libcrypto-3*.dll` may be there: Python takes SHA-256 from it.

**5. Design data stays in the project.** With a word such as `ZqxCanary42` in a device name and a note:

```
Select-String -Path "$env:APPDATA\HarnessDesigner\*", "$env:TEMP\*" -Pattern ZqxCanary42 -List
```

Expected: nothing, or the settings file `HarnessDesigner.ini` when the word is in the project name (the recent-projects list).

## The automatic audit

`tools/offline_audit.py` does all of the above, and more, in one run, and writes a JSON report and a short Markdown summary. It needs the source of the same version (the `HarnessDesignStudio/` folder of the repository at the release tag) only for the audit script itself; the program it audits is the package:

```
cd HarnessDesignStudio
PYTHONPATH=src:. python3 -m tools.offline_audit --package ../harness-design-studio-<version>-linux-x86_64.tar.gz --out offline-audit
```

On Linux it runs a whole workflow twice: (a) every command in a network namespace without network (it tries `unshare -rn`, `bwrap --unshare-net` and `sudo unshare -n`, and reports which worked and what the namespace looked like inside); (b) every command under `strace -f` with the normal network. It plants canaries in the project name, device names and notes, interface names and notes, part numbers and an imported part, and looks for them in every write any process made (deleted temporary files included), in the files left behind, in the settings, in the output of the commands and in the trace. It lists every socket, connection, program started, file written and shared library loaded, and the network-capable files in the package. Everything it sees is judged against a reviewed allow-list, `tools/offline_audit_allow.json`, in which every entry carries its reason; anything else is a finding and the audit exits with 1. `--gui-platform xcb` runs the editor on a virtual X display (`xvfb-run`) instead of Qt's offscreen platform. On Windows, in an administrator shell, `python -m tools.offline_audit --package FILE.zip` blocks the programs with firewall rules, switches the audit events on, runs the same workflow and reads the events (it cannot see files that were written and deleted again; Linux's trace can).

From the release after 1.17.0 the report of the Linux package, audited on GitHub's Ubuntu 24.04 runner, is attached to the release page; the CI workflow `harness-design-studio offline audit` runs the audit on every change of the program.

## Switch Python plug-ins off on your computers

Python plug-ins are the one way a project can bring code that runs (after the user trusted it). To forbid them on a computer, whatever a project or a user says:

- **Machine-wide (what an IT department uses):** create the file `/etc/harness-design-studio/policy.json` (Linux) or `%ProgramData%\HarnessDesignStudio\policy.json` (Windows) as an administrator, with the text `{"python_plugins": "off"}`, and leave it writable by administrators only. While the file exists, plug-ins are off unless it says exactly `{"python_plugins": "allowed"}`; a file that cannot be read or is not understood also switches them off.
- **For a session, a script or CI:** the environment variable `HARNESS_DESIGN_STUDIO_NO_PLUGINS=1`.

Then no plug-in module is imported, `harness-design-studio extensions DIR` and **Help > Extensions** say *Python plug-ins are switched off on this computer* with the reason, plug-ins are listed as `blocked`, `trust` refuses to trust one, and a project that enables one gets the warning `x-extension-problem`. Rules and tables written as data still apply. Check it with `harness-design-studio extensions DIR`.
