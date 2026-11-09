"""The Windows counterpart of the offline audit (REQ-OFFLINE-06), called by `tools/offline_audit.py`.

Windows has no strace and no network namespace. What this does instead, as an administrator (the CI
runner is one):

1. Windows Defender Firewall rules that block every program of the package from the network, in and
   out (the same rules as the smoke test, `tools/smoke_package.py`);
2. the Windows audit policy for *Filtering Platform Connection* and *Packet Drop* (every connection
   that Windows' filtering platform allows or blocks, with the program that asked: events 5152,
   5156, 5157, 5158, 5159) and for *Process Creation* with the command line (event 4688), switched
   on for the run and back to what it was afterwards;
3. the same workflow as on Linux (`workflow()`), the canaries included, and the editor's
   `--audit-run`, which lists the DLLs loaded into it;
4. then: every filtering-platform event of a program of the package (any is a finding), every
   program a program of the package started, the network-capable DLLs it loaded and shipped, and
   the canaries in the temporary folder, the settings folder and the output of the commands.

What it cannot see that the Linux audit sees: the files a program wrote and deleted again (no
trace of each write); a connection that Windows' filtering platform does not audit (it audits
loopback too, but not every local IPC). Usage: `python -m tools.offline_audit --package FILE.zip`
on Windows, in an administrator shell.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET  # noqa: S405 - the system's own event log, not untrusted input
from pathlib import Path
from typing import Any

from tools.offline_audit import (
    FORMAT,
    FORMAT_VERSION,
    ROOT,
    canary_hits,
    canary_tokens,
    judge,
    load_allow_list,
    markdown,
    network_capable,
    package_contents,
    run_workflow,
    scan_files,
    source_program,
    step_rows,
    unpack,
    which_tokens,
)

AUDIT_GUIDS = {
    "Filtering Platform Connection": "{0CCE9226-69AE-11D9-BED3-505054503030}",
    "Filtering Platform Packet Drop": "{0CCE9225-69AE-11D9-BED3-505054503030}",
    "Process Creation": "{0CCE922B-69AE-11D9-BED3-505054503030}",
}
CMDLINE_KEY = r"HKLM\Software\Microsoft\Windows\CurrentVersion\Policies\System\Audit"
WFP_EVENTS = (5031, 5152, 5155, 5156, 5157, 5158, 5159)


def _ps(script: str, timeout: int = 300) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],  # noqa: S607
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        check=False,
    )  # fmt: skip


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace", check=False)  # noqa: S603


def audit_policy_on() -> tuple[list[str], list[str]]:
    """Switch the auditing on; (the commands that undo it, what failed)."""
    undo: list[str] = []
    failed: list[str] = []
    for name, guid in AUDIT_GUIDS.items():
        before = _run(["auditpol", "/get", f"/subcategory:{guid}", "/r"])
        was = (
            before.stdout.strip().splitlines()[-1].split(",")[-2] if before.returncode == 0 else ""
        )
        done = _run(
            ["auditpol", "/set", f"/subcategory:{guid}", "/success:enable", "/failure:enable"]
        )
        if done.returncode != 0:
            failed.append(f"{name}: {(done.stdout + done.stderr).strip()[:200]}")
            continue
        success = "enable" if "Success" in was else "disable"
        failure = "enable" if "Failure" in was else "disable"
        undo.append(f"auditpol /set /subcategory:{guid} /success:{success} /failure:{failure}")
    done = _run(["reg", "add", CMDLINE_KEY, "/v", "ProcessCreationIncludeCmdLine_Enabled", "/t",
                 "REG_DWORD", "/d", "1", "/f"])  # fmt: skip
    if done.returncode != 0:
        failed.append("command line in process events: " + done.stderr.strip()[:200])
    return undo, failed


def events(start: float, ids: tuple[int, ...]) -> list[dict[str, str]]:
    """The Security events of these ids since `start` (seconds since the epoch), as dicts."""
    when = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(start - 2))
    script = (
        f"$s=[datetime]'{when}'; Get-WinEvent -FilterHashtable @{{LogName='Security'; "
        f"Id={','.join(map(str, ids))}; StartTime=$s}} -ErrorAction SilentlyContinue | "
        'ForEach-Object { $_.ToXml() + "`n<!--end-->" }'
    )
    done = _ps(script)
    rows: list[dict[str, str]] = []
    ns = {"e": "http://schemas.microsoft.com/win/2004/08/events/event"}
    for chunk in done.stdout.split("<!--end-->"):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            root = ET.fromstring(chunk)  # noqa: S314
        except ET.ParseError:
            continue
        row = {"EventID": root.findtext("e:System/e:EventID", "", ns)}
        for d in root.findall("e:EventData/e:Data", ns):
            row[d.get("Name", "")] = d.text or ""
        rows.append(row)
    return rows


def block_rules(folder: Path) -> tuple[list[str], int]:
    """Firewall rules that block every program below `folder`, in and out; (names, how many)."""
    names = []
    for i, exe in enumerate(sorted(folder.rglob("*.exe"))):
        for direction in ("out", "in"):
            name = f"hds-offline-audit-{os.getpid()}-{i}-{direction}"
            rule = (f'netsh advfirewall firewall add rule name="{name}" dir={direction} action=block '
                    f'program="{exe.resolve()}" enable=yes')  # fmt: skip
            if subprocess.run(rule, capture_output=True, check=False).returncode == 0:  # noqa: S603
                names.append(name)
    return names, len(names)


def main_windows(args: argparse.Namespace) -> int:
    entries = load_allow_list(args.allow_list)
    out: Path = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    logs = out / "logs"
    logs.mkdir(parents=True)
    scratch = Path(tempfile.mkdtemp(prefix="hds-offline-audit-"))
    undo: list[str] = []
    rules: list[str] = []
    try:
        program = (
            source_program() if args.source else unpack(args.package.resolve(), scratch / "package")
        )
        folder = program.folder or Path(sys.executable).parent
        tokens = canary_tokens()
        version = subprocess.run([*program.cli, "--version"], capture_output=True, text=True,
                                 check=False).stdout.strip().split()[-1:] or ["?"]  # fmt: skip
        doc: dict[str, Any] = {
            "format": FORMAT, "format_version": FORMAT_VERSION, "version": version[0],
            "target": {"kind": program.kind, "origin": program.origin, "sha256": program.sha256},
            "machine": f"{platform.platform()}, Python {platform.python_version()}",
            "gui_platform": "offscreen", "idle_seconds": args.idle, "canary_base": tokens["base"],
        }  # fmt: skip
        rules, count = block_rules(folder)
        undo, policy_failed = audit_policy_on()
        doc["isolation"] = {
            "method": f"Windows Defender Firewall: {count} block rules (in and out) for the programs of the package",
            "tried": [{"method": "auditpol", "ok": not policy_failed, "why": "; ".join(policy_failed)}],
            "probe": {},
        }  # fmt: skip
        print(f"firewall: {count} rules; auditing: {policy_failed or 'on'}")
        start = time.time()
        work = scratch / "traced"
        ran = run_workflow(program, work, logs, [], tokens, args.idle, "offscreen", "windows")
        time.sleep(5)  # the event log is written a moment later
        findings: list[dict[str, str]] = []
        ok_rows: list[dict[str, str]] = []
        places = {"package": str(folder), "gui": program.gui[0], "cli": program.cli[0],
                  "python": sys.executable, "work": str(work)}  # fmt: skip
        ours = [p.name.lower() for p in folder.rglob("*.exe")] or ["python.exe"]
        wfp = [e for e in events(start, WFP_EVENTS)
               if any(n in e.get("Application", "").lower() for n in ours)]  # fmt: skip
        for e in wfp:
            value = (f"event {e['EventID']} {e.get('Application', '')} -> {e.get('DestAddress', '')}:"
                     f"{e.get('DestPort', '')} protocol {e.get('Protocol', '')}")  # fmt: skip
            judge("connection", value, entries, places, findings, ok_rows,
                  "Windows filtering platform event of a program of the package")  # fmt: skip
        children = [e for e in events(start, (4688,))
                    if any(n in e.get("ParentProcessName", "").lower() for n in ours)]  # fmt: skip
        child_rows = []
        for e in children:
            line = e.get("CommandLine") or e.get("NewProcessName", "")
            value = " ".join(line.replace('"', "").split())
            child_rows.append({"program": e.get("NewProcessName", ""), "command": value,
                               "parent": e.get("ParentProcessName", "")})  # fmt: skip
            judge("child", value, entries, places, findings, ok_rows,
                  f"started by {Path(e.get('ParentProcessName', '?')).name}")  # fmt: skip
        gui: dict[str, Any] = {}
        report = work / "gui-report.json"
        if report.is_file():
            gui = json.loads(report.read_text(encoding="utf-8"))
            shutil.copy2(report, logs / "windows-gui-report.json")
        dlls = gui.get("libraries_mapped", [])
        for dll in dlls:
            if network_capable(Path(dll).name):
                judge(
                    "library",
                    dll,
                    entries,
                    places,
                    findings,
                    ok_rows,
                    network_capable(Path(dll).name),
                )
        for module in gui.get("python_network_modules", []):
            judge(
                "python_module",
                module,
                entries,
                places,
                findings,
                ok_rows,
                "imported by the editor",
            )
        for url in gui.get("urls_opened", []):
            judge("url", url.replace("\\", "/"), entries,
                  # a file URL of a Windows path has a third slash: file:///C:/...
                  {"package": "/" + folder.as_posix(), "src": "/" + (ROOT / "src").as_posix()},
                  findings, ok_rows, "the editor asked the system to open it")  # fmt: skip
        for row in package_contents(program.folder):
            judge("package_file", row["file"], entries, places, findings, ok_rows, row["what"])
        base = tokens["base"]
        settings = Path(gui["settings_file"]) if gui.get("settings_file") else None
        for where in [work / "tmp", work / "home", *([settings.parent] if settings else [])]:
            for hit in scan_files(where, base):
                found = which_tokens(Path(hit).read_bytes().decode("utf-8", "replace"), tokens)
                value = hit
                if settings is not None and Path(hit).parent == settings.parent:
                    value = (
                        "{home}/.config/HarnessDesigner/" + Path(hit).name
                    )  # the same rule as Linux
                judge("canary", value, entries, {"home": "{home}"}, findings, ok_rows,
                      f"a file left behind holds the canary ({', '.join(found)})", found)  # fmt: skip
        for r in ran:
            for stream in (r.stdout, r.stderr):
                if stream.is_file() and canary_hits(stream.read_bytes(), base):
                    found = which_tokens(stream.read_bytes().decode("utf-8", "replace"), tokens)
                    judge("canary", f"{stream.suffix.lstrip('.')} of {r.name}", entries, {},
                          findings, ok_rows, f"printed by the command ({', '.join(found)})", found)  # fmt: skip
        failed = [f"{r.name}" for r in ran if not r.ok] + (
            ["the editor wrote no report"] if not gui else []
        )
        if policy_failed:
            failed.append("the audit policy could not be switched on: " + "; ".join(policy_failed))
        doc.update(
            traced={
                "steps": step_rows(ran), "socket_families": {}, "connections": wfp,
                "listening": [],
                "children": [{"program": c["command"], "argv": [], "step": "-"} for c in child_rows],
                "files_written": [], "libraries_mapped": dlls,
                "network_capable_libraries_mapped": [d for d in dlls if network_capable(Path(d).name)],
                "network_capable_files_only_read": [], "network_config_read": [],
                "package_network_capable_files": package_contents(program.folder),
                "canary_places": [r for r in ok_rows if r["kind"] == "canary"],
                "findings": findings, "allowed": ok_rows,
            },
            gui=gui, findings=findings, failed_steps=failed,
            result="pass" if not findings and not failed else "fail",
        )  # fmt: skip
        (out / "offline-audit.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n",
                                                encoding="utf-8")  # fmt: skip
        (out / "offline-audit.md").write_text(
            markdown(doc).replace(str(scratch), "WORK"), encoding="utf-8"
        )
        print((out / "offline-audit.md").read_text(encoding="utf-8"))
        return 0 if doc["result"] == "pass" else 1
    finally:
        for name in rules:
            _run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"])
        for cmd in undo:
            subprocess.run(cmd, capture_output=True, check=False)  # noqa: S603
        if not args.keep:
            shutil.rmtree(scratch, ignore_errors=True)
