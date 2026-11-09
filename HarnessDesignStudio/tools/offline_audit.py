"""The offline audit: run the built program through a whole workflow and watch what it does (REQ-OFFLINE-02).

Linux. It takes the package a user downloads (the `.tar.gz` or the `.deb` of a release, or an
unpacked program folder), or, with `--source`, the source install of this checkout, and runs this
workflow twice, each time with a new, empty home folder (a first start):

    --version; new (from the flatsat example); the canaries are written into the project; validate;
    import-parts (a CSV); generate; check; drc; export --drawings; export-data; verify --outputs;
    release (with the --accept flags); log; two deliberate errors (a folder that does not exist, a
    damaged CSV); the editor (offscreen unless --gui-platform xcb): opens the project, F1 for the
    guide with the system's URL opener replaced by a recorder (no browser is started), the rule check
    in its helper process, a folder that does not exist, idle for --idle seconds, quit.

Run (a), *isolated*: every command in a network namespace that has no network (`unshare -rn`,
`bwrap --unshare-net` or `sudo unshare -n`, whichever works here; the probe inside is reported).
Everything must still work: the exit codes are compared with the expected ones.

Run (b), *traced*: every command under `strace -f` with the computer's normal network, so that the
program could reach out if it tried. From the trace it reports every socket family used, every
connect/sendto/bind target, every program started, every file written or created and every shared
library opened, and it looks for the canaries (unique words put into device names, notes, interface
names, part numbers and the project name) in every write the processes made, in the files they
left, in the output of the commands and in the trace.

Anything that is not on the reviewed allow-list (`tools/offline_audit_allow.json`, one reason per
entry) is a finding; the exit code is 1 when there is a finding or a step did not do what it should,
2 when the audit itself cannot run (no strace, no way to isolate). The result is a JSON report and a
short Markdown summary in --out (default `offline-audit/`), with the traces and the output of every
command beside them.

What it cannot see: anything on a path the workflow does not take; the kernel and other programs
(a browser that would open the guide, the desktop's file dialogs, which run in other processes); a
trusted Python plug-in (none is in the workflow; they can be switched off, REQ-OFFLINE-05).

Usage:
  python -m tools.offline_audit --package dist/harness-design-studio-1.17.0-linux-x86_64.tar.gz
  python -m tools.offline_audit --package dist/harness-design-studio_1.17.0_amd64.deb
  python -m tools.offline_audit --source            # the checkout, not a package (see the report)
Options: --out DIR, --idle SECONDS (default 20), --isolation auto|unshare-rn|bwrap|sudo-unshare,
--gui-platform offscreen|xcb (xcb runs the editor on a virtual X display, needs xvfb-run),
--only isolated|traced, --keep (keep the work folder).
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ALLOW_LIST = ROOT / "tools" / "offline_audit_allow.json"
FORMAT = "harness-design-studio-offline-audit"
FORMAT_VERSION = 1
TEMPLATE = "flatsat"
STEP_TIMEOUT_S = 600
GUI_TIMEOUT_S = 180  # beyond the idle time

# What makes a file able to use the network, by name (a shipped file or a library a process opened).
# tools/build_installer.py removes the ones the program does not need (REQ-OFFLINE-04).
NETWORK_CAPABLE: dict[str, str] = {
    "Qt network library": r"(^|/)(lib)?Qt6Network(\.so|\.dll|$)",
    "Qt WebEngine": r"(^|/)(lib)?Qt6WebEngine|QtWebEngineProcess",
    "Qt VNC platform plug-in (a VNC server)": r"(^|/)(lib)?qvnc\.(so|dll)",
    "Qt TUIO touch plug-in (listens on UDP)": r"(^|/)(lib)?qtuiotouchplugin\.(so|dll)",
    "Qt TLS or network-information plug-in": r"(^|/)(lib)?q(openssl|schannel|cert)backend|"
    r"(^|/)(lib)?q(networklistmanager|networkmanager|glib)\.(so|dll)",
    "OpenSSL TLS library": r"(^|/)libssl(-3|\.so)",
    "OpenSSL crypto library": r"(^|/)libcrypto(-3|\.so)",
    "Python TLS module": r"(^|/)_ssl(\.cpython|\.pyd|\.\w+\.so)",
    "Python socket module": r"(^|/)_socket(\.cpython|\.pyd|\.\w+\.so)",
    "Kerberos / GSSAPI (network login)": r"(^|/)lib(gssapi_krb5|krb5|k5crypto|krb5support)\.so",
    "libcurl": r"(^|/)libcurl",
    "DNS resolver library": r"(^|/)lib(resolv|nss_dns|nss_mdns\w*|nss_resolve)\.so",
}
NETWORK_CONFIG_FILES = (
    "/etc/resolv.conf", "/etc/hosts", "/etc/host.conf", "/etc/gai.conf", "/etc/services",
    "/etc/protocols", "/run/systemd/resolve/resolv.conf", "/run/systemd/resolve/stub-resolv.conf",
)  # fmt: skip


def network_capable(name: str) -> str:
    """What makes `name` (a path or a file name) network-capable ("" when nothing does)."""
    for what, pattern in NETWORK_CAPABLE.items():
        if re.search(pattern, name):
            return what
    return ""


# ---- the program under test ------------------------------------------------------------------


@dataclass
class Program:
    kind: str  # "package" or "source"
    cli: list[str]
    gui: list[str]
    folder: Path | None  # the program folder of a package
    env: dict[str, str] = field(default_factory=dict)  # added to the environment of every command
    origin: str = ""  # what was audited, in words
    sha256: str = ""  # of the package file


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def unpack(package: Path, into: Path) -> Program:
    """The program folder of a `.tar.gz`, a `.deb` (unpacked, not installed) or a folder."""
    if package.is_dir():
        folder = package
    elif package.name.endswith(".tar.gz"):
        with tarfile.open(package) as tar:
            tar.extractall(into, filter="tar")
        folder = into / "harness-design-studio"
    elif package.suffix == ".zip":
        import zipfile

        with zipfile.ZipFile(package) as zf:
            zf.extractall(into)  # noqa: S202 - zipfile drops absolute paths and ".." itself
        folder = into
    elif package.suffix == ".deb":
        subprocess.run(["dpkg-deb", "-x", str(package), str(into)], check=True)  # noqa: S607
        folder = into / "opt" / "harness-design-studio"
    else:
        raise SystemExit(f"error: not a package this audit knows: {package}")
    exe = ".exe" if sys.platform == "win32" else ""
    gui = folder / f"harness-design-studio-gui{exe}"
    cli = folder / "cli" / f"harness-design-studio{exe}"
    if not (gui.is_file() and cli.is_file()):
        raise SystemExit(f"error: {folder} is not the program folder of the package")
    return Program(
        "package", [str(cli)], [str(gui)], folder, {}, f"package {package.name}",
        sha256_file(package) if package.is_file() else "",
    )  # fmt: skip


def source_program() -> Program:
    src = str(ROOT / "src")
    return Program(
        "source",
        [sys.executable, "-P", "-m", "harness_design_studio.cli.main"],
        [sys.executable, "-P", str(ROOT / "packaging" / "gui_entry.py")],
        None,
        {"PYTHONPATH": src},
        f"source install of {ROOT} with {sys.executable}",
    )


# ---- isolation ---------------------------------------------------------------------------------

PROBE = r"""
import errno, json, socket
names = [l.split(":")[0].strip() for l in open("/proc/net/dev").read().splitlines()[2:]]
out = {"interfaces": sorted(n for n in names if n)}
for host, port in (("192.0.2.1", 9), ("1.1.1.1", 53)):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, port)); s.send(b"x"); out[host] = "sent"
    except OSError as exc:
        out[host] = errno.errorcode.get(exc.errno, str(exc.errno))
    finally:
        s.close()
try:
    socket.getaddrinfo("example.com", 443); out["dns"] = "resolved"
except OSError as exc:
    out["dns"] = type(exc).__name__
print(json.dumps(out))
"""


ISOLATION_METHODS = ("unshare-rn", "bwrap", "sudo-unshare")


def isolation_prefixes() -> dict[str, list[str]]:
    uid, gid = os.getuid(), os.getgid()  # type: ignore[attr-defined,unused-ignore]
    return {
        "unshare-rn": ["unshare", "--user", "--map-root-user", "--net", "--"],
        "bwrap": ["bwrap", "--dev-bind", "/", "/", "--unshare-net", "--die-with-parent", "--"],
        "sudo-unshare": [
            "sudo", "-n", "--preserve-env", "unshare", "--net", "--",
            "setpriv", f"--reuid={uid}", f"--regid={gid}", "--clear-groups", "--",
        ],
    }  # fmt: skip


def find_isolation(wanted: str) -> tuple[str, list[str], list[dict[str, Any]], dict[str, Any]]:
    """The first way to run a command without network that works here: (name, prefix, what was
    tried, what the probe saw inside)."""
    tried: list[dict[str, Any]] = []
    for name, prefix in isolation_prefixes().items():
        if wanted not in ("auto", name):
            continue
        if shutil.which(prefix[0]) is None:
            tried.append({"method": name, "ok": False, "why": f"{prefix[0]} is not installed"})
            continue
        try:
            done = subprocess.run(  # noqa: S603
                [*prefix, sys.executable, "-I", "-c", PROBE],
                capture_output=True, text=True, timeout=60, check=False,
            )  # fmt: skip
        except (OSError, subprocess.SubprocessError) as exc:
            tried.append({"method": name, "ok": False, "why": str(exc)})
            continue
        if done.returncode != 0:
            tried.append(
                {"method": name, "ok": False, "why": (done.stderr or done.stdout).strip()[-400:]}
            )
            continue
        probe = json.loads(done.stdout.strip().splitlines()[-1])
        isolated = (
            set(probe["interfaces"]) <= {"lo"}
            and probe["192.0.2.1"] != "sent"
            and probe["1.1.1.1"] != "sent"
            and probe["dns"] != "resolved"
        )
        tried.append({"method": name, "ok": isolated, "probe": probe})
        if isolated:
            return name, prefix, tried, probe
    return "", [], tried, {}


# ---- the workflow ------------------------------------------------------------------------------


@dataclass
class Step:
    name: str
    program: str  # "cli" or "gui"
    args: list[str]
    expect: tuple[int, ...] = (0,)
    before: str = ""  # a preparation the audit does itself before the step (not traced)


def workflow(idle: float) -> list[Step]:
    p = "audit-project"
    accept = "offline audit run, not a real release"
    return [
        Step("version", "cli", ["--version"]),
        Step("new project from an example", "cli", ["new", p, "--template", TEMPLATE]),
        Step("validate", "cli", ["validate", p], (0, 1), before="canaries"),
        Step(
            "import a CSV of parts",
            "cli",
            ["import-parts", p, "parts.csv", "--approved", "Approved"],
            before="csv",
        ),  # fmt: skip
        Step("generate", "cli", ["generate", p]),
        Step("check", "cli", ["check", p], (0, 1)),
        Step("drc", "cli", ["drc", p], (0, 1)),
        Step("export with drawings", "cli", ["export", p, "--drawings"]),
        Step("export-data", "cli", ["export-data", p, "--out", "audit-data"]),
        Step("verify the outputs", "cli", ["verify", p, "--outputs"]),
        Step(
            "release with the --accept flags",
            "cli",
            [
                "release",
                p,
                "W001",
                "--by",
                "A. Engineer",
                "--checker",
                "B. Checker",
                "--comment",
                "Offline audit release",
                "--accept-placeholders",
                accept,
                "--accept-unapproved-parts",
                accept,
                "--accept-asbuilt",
                accept,
                "--accept-loose-ends",
                accept,
            ],
        ),  # fmt: skip
        Step("log", "cli", ["log", p]),
        Step(
            "deliberate error: a folder that does not exist",
            "cli",
            ["validate", "no-such-project"],
            (1, 2),
        ),  # fmt: skip
        Step(
            "deliberate error: a damaged CSV",
            "cli",
            ["import-lengths", p, "damaged.csv"],
            (1, 2),
            before="damaged",
        ),  # fmt: skip
        Step(
            "editor: open, F1, rule check, error, idle, quit",
            "gui",
            ["--audit-run", p, "gui-report.json", str(idle)],
        ),  # fmt: skip
    ]


def canary_tokens() -> dict[str, str]:
    """One random word for each kind of field; all start with the same base, which is searched."""
    base = "CNRY" + secrets.token_hex(6).upper()
    return {
        "base": base,
        "project name": f"{base}PRJ",
        "device name": f"{base}DEV",
        "device note": f"{base}NOTE",
        "interface name": f"{base}IFN",
        "interface note": f"{base}IFNOTE",
        "part number": f"{base}PN",
        "imported part": f"{base}IMP",
    }


def _edit_json(path: Path, change: Any) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def plant_canaries(project: Path, tokens: dict[str, str]) -> None:
    """Write the canaries into the project the way an engineer's data would be there."""

    def proj(doc: dict[str, Any]) -> None:
        doc["name"] = f"Bench {tokens['project name']}"

    _edit_json(project / "project.json", proj)
    for n, path in enumerate(sorted((project / "logical" / "units").glob("*.json"))):

        def units(doc: dict[str, Any], first: bool = n == 0) -> None:
            for i, unit in enumerate(doc["units"]):
                if first and i == 0:
                    unit["name"] = f"Unit {tokens['device name']}"
                unit["notes"] = f"Note {tokens['device note']}"

        _edit_json(path, units)
    for n, path in enumerate(sorted((project / "logical" / "interfaces").glob("*.json"))):

        def interfaces(doc: dict[str, Any], first: bool = n == 0) -> None:
            for i, itf in enumerate(doc["interfaces"]):
                if first and i == 0:
                    itf["name"] = f"Link {tokens['interface name']}"
                itf["notes"] = f"Note {tokens['interface note']}"

        _edit_json(path, interfaces)

    def parts(doc: dict[str, Any]) -> None:
        for part in doc["parts"]:
            part["part_number"] = f"{tokens['part number']}-{part['id']}"

    _edit_json(project / "library" / "connector.json", parts)


def prepare(work: Path, what: str, tokens: dict[str, str]) -> None:
    if what == "canaries":
        plant_canaries(work / "audit-project", tokens)
    elif what == "csv":
        (work / "parts.csv").write_text(
            "part number,manufacturer,description,category,pin count,approval status\n"
            f"{tokens['imported part']}-9F,Maker {tokens['imported part']},Micro-D {tokens['imported part']},"
            "connector,9,Approved\n",
            encoding="utf-8",
        )
    elif what == "damaged":
        (work / "damaged.csv").write_bytes(b"\xff\xfe\x00harness;;\x00\r\r\n" * 3)


# ---- running -------------------------------------------------------------------------------------


@dataclass
class Ran:
    name: str
    command: list[str]
    exit: int
    expect: tuple[int, ...]
    seconds: float
    stdout: Path
    stderr: Path
    trace: Path | None

    @property
    def ok(self) -> bool:
        return self.exit in self.expect


def base_env(work: Path, program: Program, gui_platform: str) -> dict[str, str]:
    """A first start: a new, empty home folder; temporary files in a folder of the audit."""
    home, tmp, runtime = work / "home", work / "tmp", work / "runtime"
    for d in (home, tmp, runtime):
        d.mkdir(parents=True, exist_ok=True)
    if sys.platform != "win32":
        runtime.chmod(0o700)
    if sys.platform == "win32":  # Windows programs need much of the environment (SYSTEMROOT...)
        env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PYTHON")}
        env.update(TEMP=str(tmp), TMP=str(tmp), PYTHONUTF8="1", HARNESS_AUTHOR="A. Engineer")
    else:
        keep = ("PATH", "LANG", "LC_ALL", "USER", "LOGNAME", "SHELL", "TZ")
        env = {k: v for k, v in os.environ.items() if k in keep}
        env.update(
            HOME=str(home), TMPDIR=str(tmp), XDG_RUNTIME_DIR=str(runtime), PYTHONUTF8="1",
            HARNESS_AUTHOR="A. Engineer", PYTHONFAULTHANDLER="1",
        )  # fmt: skip
    if gui_platform == "offscreen":
        env["QT_QPA_PLATFORM"] = "offscreen"
    env.update(program.env)
    return env


def run_workflow(
    program: Program, work: Path, logs: Path, prefix: list[str], tokens: dict[str, str],
    idle: float, gui_platform: str, label: str,
) -> list[Ran]:  # fmt: skip
    work.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    env = base_env(work, program, gui_platform)
    ran: list[Ran] = []
    for n, step in enumerate(workflow(idle), 1):
        if step.before:
            prepare(work, step.before, tokens)
        base = program.cli if step.program == "cli" else program.gui
        cmd = [*base, *step.args]
        # the virtual display is the audit's, not the program's: it is started outside the trace
        xvfb = (
            ["xvfb-run", "-a", "-s", "-nolisten tcp"]
            if step.program == "gui" and gui_platform == "xcb"
            else []
        )
        tracing = bool(prefix) and prefix[0] == "strace"
        trace = logs / f"{label}-{n:02d}.strace" if tracing else None
        if trace is not None:
            full = [*xvfb, *prefix, "-o", str(trace), "--", *cmd]
        else:
            full = [*prefix, *xvfb, *cmd]
        out, err = logs / f"{label}-{n:02d}.stdout", logs / f"{label}-{n:02d}.stderr"
        start = time.monotonic()
        with out.open("wb") as o, err.open("wb") as e:
            try:
                code = subprocess.run(  # noqa: S603
                    full, cwd=work, env=env, stdout=o, stderr=e, stdin=subprocess.DEVNULL,
                    timeout=(GUI_TIMEOUT_S + idle) if step.program == "gui" else STEP_TIMEOUT_S,
                    check=False,
                ).returncode  # fmt: skip
            except subprocess.TimeoutExpired:
                code = -999
        ran.append(
            Ran(step.name, cmd, code, step.expect, time.monotonic() - start, out, err, trace)
        )
        print(f"  [{label}] {step.name}: exit {code}{'' if code in step.expect else '  <-- unexpected'}",
              flush=True)  # fmt: skip
    return ran


# ---- reading a trace -----------------------------------------------------------------------------

LINE = re.compile(r"^(\d+)\s+(.*)$")
CALL = re.compile(r"^(\w+)\((.*)\)\s+=\s+(-?\w+|\?)(?:<([^>]*)>)?(.*)$")
# the path strace -y shows for a descriptor: `3</a/file>`, `1</dev/null<char 1:3>>`, `5<UNIX-STREAM:[1->2]>`
FD_PATH = re.compile(r"^(-?\d+|AT_FDCWD)(?:<((?:[^<>-]|-(?!>)|->)*)(?:<[^>]*>)?>)?")
MMAP_FILE = re.compile(r"PROT_EXEC.*, \d+<([^<>]*)(?:<[^>]*>)?>, ")
WRITE_FLAGS = ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND")
WRITE_LIKE = ("write", "pwrite64", "writev", "pwritev", "pwritev2", "sendto", "sendmsg",
              "sendmmsg", "send")  # fmt: skip


def joined_lines(path: Path) -> list[tuple[int, str]]:
    """(pid, complete call) from an strace -f log, with <unfinished ...>/<... resumed> put together."""
    pending: dict[int, str] = {}
    out: list[tuple[int, str]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        pid, text = int(m.group(1)), m.group(2)
        if text.endswith("<unfinished ...>"):
            pending[pid] = text[: -len("<unfinished ...>")].rstrip()
            continue
        if text.startswith("<... "):
            rest = text.split("resumed>", 1)[1] if "resumed>" in text else ""
            text = pending.pop(pid, "") + rest
        out.append((pid, text))
    return out


def _strings(args: str) -> list[str]:
    return re.findall(r'"((?:[^"\\]|\\.)*)"', args)


def _unescape(s: str) -> str:
    try:
        return s.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except UnicodeDecodeError:
        return s


@dataclass
class TraceFacts:
    families: dict[str, int] = field(default_factory=dict)
    connections: list[dict[str, str]] = field(default_factory=list)
    listening: list[dict[str, str]] = field(default_factory=list)
    children: list[dict[str, Any]] = field(default_factory=list)
    written: dict[str, str] = field(
        default_factory=dict
    )  # path -> how (open for writing, mkdir...)
    libraries: set[str] = field(default_factory=set)  # mapped as code (mmap with PROT_EXEC)
    opened_libraries: set[str] = field(default_factory=set)  # opened, perhaps only to be read
    config_read: set[str] = field(default_factory=set)
    writes: list[tuple[str, str]] = field(default_factory=list)  # (target, data) of every write


def read_trace(path: Path, cwd: Path) -> TraceFacts:
    facts = TraceFacts()
    for pid, text in joined_lines(path):
        m = CALL.match(text)
        if not m:
            continue
        name, args, result, result_path = m.group(1), m.group(2), m.group(3), m.group(4) or ""
        result_path = result_path.split("<")[0]
        ok = result not in ("-1", "?")
        if name == "mmap":
            lib = MMAP_FILE.search(args)
            if ok and lib:
                facts.libraries.add(lib.group(1))
            continue
        if name in ("socket", "socketpair"):
            family = args.split(",", 1)[0].strip()
            facts.families[family] = facts.families.get(family, 0) + 1
        elif name in ("connect", "sendto", "sendmsg", "bind"):
            fam = re.search(r"sa_family=(AF_\w+)", args)
            if fam:
                peer = re.search(r'sun_path=(@?"[^"]*"|@[^,}]*)', args) or re.search(
                    r'inet6?_(?:addr|pton)\([^)]*"([^"]+)"', args
                )
                port = re.search(r"sin6?_port=htons\((\d+)\)", args)
                row = {
                    "call": name, "family": fam.group(1),
                    "target": (peer.group(1) if peer else "?") + (f":{port.group(1)}" if port else ""),
                    "result": result + m.group(5).strip()[:60], "pid": str(pid),
                }  # fmt: skip
                (facts.listening if name == "bind" else facts.connections).append(row)
        elif name == "listen":
            facts.listening.append({"call": "listen", "family": "", "target": args[:80],
                                    "result": result, "pid": str(pid)})  # fmt: skip
        elif name in ("execve", "execveat"):
            strings = _strings(args)
            argv = re.search(r"\[(.*?)\]", args)
            facts.children.append({
                "pid": pid, "program": _unescape(strings[0]) if strings else "?",
                "argv": [_unescape(s) for s in _strings(argv.group(1))] if argv else [],
                "ok": ok,
            })  # fmt: skip
        elif name in ("openat", "open", "creat", "openat2"):
            strings = _strings(args)
            target = (
                result_path if ok and result_path else (_unescape(strings[0]) if strings else "")
            )
            if not target:
                continue
            if not target.startswith("/"):
                dirfd = FD_PATH.match(args)
                base = dirfd.group(2) if dirfd and dirfd.group(2) else str(cwd)
                target = os.path.normpath(os.path.join(base, target))
            writing = name == "creat" or any(f in args for f in WRITE_FLAGS)
            if ok and writing:
                facts.written.setdefault(target, "opened for writing")
            if ok and re.search(r"\.so(\.\d+)*$", target):
                facts.opened_libraries.add(target)
            if ok and target in NETWORK_CONFIG_FILES:
                facts.config_read.add(target)
        elif name in ("mkdir", "mkdirat", "rename", "renameat", "renameat2", "link", "linkat",
                      "symlink", "symlinkat", "unlink", "unlinkat", "rmdir", "truncate"):  # fmt: skip
            if not ok:
                continue
            dirfds = re.findall(r"(?:^|, )(-?\d+|AT_FDCWD)<([^>]*)>", args)
            strings = [_unescape(s) for s in _strings(args)]
            base = dirfds[0][1] if dirfds else str(cwd)
            for s in (
                strings[-1:] if name.startswith(("rename", "link", "symlink")) else strings[:1]
            ):
                target = s if s.startswith("/") else os.path.normpath(os.path.join(base, s))
                facts.written.setdefault(target, name)
        if name in WRITE_LIKE:
            fd = FD_PATH.match(args)
            where = fd.group(2) if fd and fd.group(2) else (fd.group(1) if fd else "?")
            facts.writes.append((where, args))
    return facts


# ---- judging ---------------------------------------------------------------------------------------


def load_allow_list(path: Path) -> list[dict[str, Any]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = doc["allow"]
    for e in entries:
        if not e.get("reason", "").strip() or e.get("kind") not in KINDS:
            raise SystemExit(
                f"error: allow-list entry without a reason or with an unknown kind: {e}"
            )
    return entries


KINDS = ("socket_family", "connection", "child", "written", "library", "network_config_read",
         "package_file", "canary", "python_module", "url")  # fmt: skip


def allowed(
    entries: list[dict[str, Any]], kind: str, value: str, places: dict[str, str],
    fields: list[str] | None = None,
) -> str:  # fmt: skip
    """The reason of the first entry of `kind` whose pattern matches `value` ("" when none does).
    An entry with `fields` (canaries) accepts only a hit of those fields."""
    for e in entries:
        if e["kind"] != kind:
            continue
        if fields is not None and "fields" in e and not set(fields) <= set(e["fields"]):
            continue
        pattern = e["pattern"]
        for key, real in places.items():
            pattern = pattern.replace("{" + key + "}", real)
        if fnmatch.fnmatchcase(value, pattern):
            return str(e["reason"])
    return ""


def judge(kind: str, value: str, entries: list[dict[str, Any]], places: dict[str, str],
          findings: list[dict[str, str]], allowed_rows: list[dict[str, str]], detail: str = "",
          fields: list[str] | None = None) -> None:  # fmt: skip
    reason = allowed(entries, kind, value, places, fields)
    row = {"kind": kind, "value": value, **({"detail": detail} if detail else {})}
    if reason:
        allowed_rows.append({**row, "reason": reason})
    else:
        findings.append(row)


def which_tokens(text: str, tokens: dict[str, str]) -> list[str]:
    """The fields whose canary is in `text` (longest words first, so a word is not counted twice)."""
    low = text.lower()
    found = []
    for kind, word in sorted(tokens.items(), key=lambda kv: -len(kv[1])):
        if kind != "base" and word.lower() in low:
            found.append(kind)
            low = low.replace(word.lower(), "")
    return sorted(found)


def canary_hits(data: bytes, base: str) -> int:
    low = data.lower()
    return sum(
        low.count(form) for form in (base.lower().encode(), base.lower().encode("utf-16-le"))
    )


def scan_files(root: Path, base: str, skip: tuple[Path, ...] = ()) -> list[str]:
    """Files below `root` (not below a `skip` folder) that hold the canary."""
    hits: list[str] = []
    if not root.exists():
        return hits
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.is_symlink() or any(p.is_relative_to(s) for s in skip):
            continue
        try:
            if canary_hits(p.read_bytes(), base):
                hits.append(str(p))
        except OSError:
            continue
    return hits


def package_contents(folder: Path | None) -> list[dict[str, str]]:
    if folder is None:
        return []
    rows = []
    for p in sorted(folder.rglob("*")):
        what = network_capable(p.name)
        if what and (p.is_file() or p.is_symlink()):
            rows.append({"file": p.relative_to(folder).as_posix(), "what": what,
                         "bytes": str(p.stat().st_size if p.exists() else 0)})  # fmt: skip
    return rows


def evaluate(
    program: Program, traced: list[Ran], work: Path, logs: Path, tokens: dict[str, str],
    entries: list[dict[str, Any]],
) -> dict[str, Any]:  # fmt: skip
    home, tmp = work / "home", work / "tmp"
    places = {
        "project": str(work / "audit-project"), "data": str(work / "audit-data"),
        "work": str(work), "home": str(home), "tmp": str(tmp), "runtime": str(work / "runtime"),
        "logs": str(logs), "package": str(program.folder or ""), "python": sys.executable,
        "python_prefix": sys.base_prefix, "src": str(ROOT / "src"), "root": str(ROOT),
        "cli": program.cli[0] if program.kind == "package" else sys.executable,
        "gui": program.gui[0] if program.kind == "package" else sys.executable,
    }  # fmt: skip
    findings: list[dict[str, str]] = []
    ok_rows: list[dict[str, str]] = []
    families: dict[str, int] = {}
    connections: list[dict[str, str]] = []
    listening: list[dict[str, str]] = []
    children: list[dict[str, Any]] = []
    written: dict[str, str] = {}
    libraries: set[str] = set()
    opened: set[str] = set()
    config_read: set[str] = set()
    canary: list[dict[str, Any]] = []
    base = tokens["base"]
    for r in traced:
        if r.trace is None or not r.trace.is_file():
            continue
        facts = read_trace(r.trace, work)
        for k, v in facts.families.items():
            families[k] = families.get(k, 0) + v
        connections += [{**c, "step": r.name} for c in facts.connections]
        listening += [{**c, "step": r.name} for c in facts.listening]
        # the first program of a step is the one the audit started; the packaged program's starter
        # (PyInstaller's bootloader) then starts itself once more in the same process
        first = facts.children[0] if facts.children else None
        for i, c in enumerate(facts.children):
            again = (
                first is not None
                and i > 0
                and c["pid"] == first["pid"]
                and c["program"] == first["program"]
            )
            children.append(
                {**c, "step": r.name, "started_by_audit": i == 0, "same_process_again": again}
            )
        for path, how in facts.written.items():
            written.setdefault(path, how)
        libraries |= facts.libraries
        opened |= facts.opened_libraries
        config_read |= facts.config_read
        for target, data in facts.writes:
            if (
                canary_hits(_unescape(data).encode("utf-8", "replace"), base)
                or base.lower() in data.lower()
            ):
                canary.append({"where": f"a write to {target}", "step": r.name, "target": target,
                               "fields": which_tokens(data, tokens)})  # fmt: skip
    for fam, count in sorted(families.items()):
        judge("socket_family", fam, entries, places, findings, ok_rows, f"{count} socket(s)")
    for c in connections:
        judge("connection", f"{c['family']} {c['target']}", entries, places, findings, ok_rows,
              f"{c['call']} in step '{c['step']}', result {c['result']}")  # fmt: skip
    for c in listening:
        findings.append({"kind": "listening", "value": f"{c['call']} {c['family']} {c['target']}",
                         "detail": f"step '{c['step']}'"})  # fmt: skip
    for c in children:
        if c["started_by_audit"]:
            continue
        value = ("(same process again) " if c["same_process_again"] else "") + " ".join(
            [c["program"], *c["argv"][1:]]
        )
        judge("child", value, entries, places, findings, ok_rows,
              f"step '{c['step']}', {'started' if c['ok'] else 'tried and failed'}")  # fmt: skip
    for path, how in sorted(written.items()):
        judge("written", path, entries, places, findings, ok_rows, how)
    net_libs = sorted(p for p in libraries if network_capable(p))
    for p in net_libs:
        judge("library", p, entries, places, findings, ok_rows, network_capable(p))
    for p in sorted(config_read):
        judge("network_config_read", p, entries, places, findings, ok_rows)
    for row in package_contents(program.folder):
        judge("package_file", row["file"], entries, places, findings, ok_rows, row["what"])
    # the canaries: in every write of the processes, the files they left, their output, the traces
    expected_places = (work / "audit-project", work / "audit-data")
    for hit in canary:
        t = hit["target"]
        if t.startswith(str(logs) + "/"):  # the output of the command, which the audit keeps
            which = "stdout" if t.endswith(".stdout") else "stderr"
            t = f"{which} of {next((r.name for r in traced if str(r.stdout) == t or str(r.stderr) == t), '?')}"
        inside = any(t.startswith(str(p) + "/") for p in expected_places)
        judge("canary", t if not inside else "{project-or-data}", entries, places, findings, ok_rows,
              f"{hit['where']} in step '{hit['step']}' ({', '.join(hit['fields'])})", hit["fields"])  # fmt: skip
    left = scan_files(work, base, skip=(*expected_places, logs))
    for p in left:
        if p.endswith(("parts.csv",)) and Path(p).parent == work:
            continue  # the audit's own input file
        found = which_tokens(Path(p).read_bytes().decode("utf-8", "replace"), tokens)
        judge("canary", p, entries, places, findings, ok_rows,
              f"a file left behind holds the canary ({', '.join(found)})", found)  # fmt: skip
    for r in traced:
        for stream in (r.stdout, r.stderr):
            if stream.is_file() and canary_hits(stream.read_bytes(), base):
                found = which_tokens(stream.read_bytes().decode("utf-8", "replace"), tokens)
                judge("canary", f"{stream.suffix.lstrip('.')} of {r.name}", entries, places,
                      findings, ok_rows, f"printed by the command ({', '.join(found)})", found)  # fmt: skip
        if r.trace and r.trace.is_file():
            names = [line for _pid, line in joined_lines(r.trace)
                     if base.lower() in line.lower() and not line.startswith(WRITE_LIKE)]  # fmt: skip
            for line in names[:5]:
                judge("canary", "trace: " + line[:120], entries, places, findings, ok_rows,
                      f"in the trace of step '{r.name}' (not a write)")  # fmt: skip
    return {
        "socket_families": families,
        "connections": connections,
        "listening": listening,
        "children": [c for c in children if not c["started_by_audit"]],
        "files_written": [{"path": p, "how": h} for p, h in sorted(written.items())],
        "libraries_mapped": sorted(libraries),
        "network_capable_libraries_mapped": net_libs,
        # opened without being mapped as code: Qt reads the metadata of every plug-in of a folder
        "network_capable_files_only_read": sorted(
            p for p in opened - libraries if network_capable(p)
        ),
        "network_config_read": sorted(config_read),
        "package_network_capable_files": package_contents(program.folder),
        "canary_places": [r for r in ok_rows if r["kind"] == "canary"],
        "findings": findings,
        "allowed": ok_rows,
    }


# ---- the report ------------------------------------------------------------------------------------


def step_rows(ran: list[Ran]) -> list[dict[str, Any]]:
    return [{"step": r.name, "exit": r.exit, "expected": list(r.expect), "ok": r.ok,
             "seconds": round(r.seconds, 1)} for r in ran]  # fmt: skip


def _one_name(value: str) -> str:
    """A file with a random name (Qt's and openpyxl's temporary files, a pipe's number) as a pattern."""
    return re.sub(r"(openpyxl\.|/#|pipe:\[|UNIX-STREAM:\[)[^/]*$", r"\1*", value)


def markdown(doc: dict[str, Any]) -> str:
    t = doc.get("traced") or {}
    lines = [
        f"# Offline audit of Harness Design Studio {doc['version']}",
        "",
        f"**Result: {doc['result'].upper()}** ({len(doc['findings'])} finding(s) not on the allow-list,"
        f" {len(doc['failed_steps'])} step(s) that did not do what they should).",
        "",
        f"- What was audited: {doc['target']['origin']}"
        + (f" (SHA-256 `{doc['target']['sha256']}`)" if doc["target"]["sha256"] else ""),
        f"- Where: {doc['machine']}",
        f"- Isolation for run (a): {doc['isolation']['method'] or 'none found'}"
        + (f"; inside it: interfaces {doc['isolation']['probe'].get('interfaces')},"
           f" a UDP send to 192.0.2.1 gave {doc['isolation']['probe'].get('192.0.2.1')},"
           f" a name lookup gave {doc['isolation']['probe'].get('dns')}" if doc["isolation"]["probe"] else ""),
        f"- Canary base word: `{doc['canary_base']}` (in the project name, device names and notes,"
        " interface names and notes, part numbers and an imported part)",
        "",
        "| Run | Steps | All as expected |",
        "| --- | --- | --- |",
    ]  # fmt: skip
    for key, title in (
        ("isolated", "(a) no network"),
        (
            "traced",
            "(b) watched (Linux: strace with the normal network; Windows: firewall and audit events)",
        ),
    ):
        if doc.get(key):
            steps = doc[key]["steps"]
            lines.append(
                f"| {title} | {len(steps)} | {'yes' if all(s['ok'] for s in steps) else 'NO'} |"
            )
    if t:
        lines += [
            "",
            "## What the trace shows",
            "",
            f"- Socket families: {', '.join(f'{k} ({v})' for k, v in t['socket_families'].items()) or 'none'}",
            f"- connect/sendto targets: {len(t['connections'])}"
            + "".join(f"\n  - {c['family']} {c['target']} ({c['step']}, result {c['result']})" for c in t["connections"][:20]),
            f"- Listening sockets: {len(t['listening'])}",
            f"- Programs started by the program: {len(t['children'])}"
            + "".join(f"\n  - {'(the same process again) ' if c.get('same_process_again') else ''}`{' '.join([c['program'], *c['argv'][1:]])[:200]}` ({c['step']})" for c in t["children"][:20]),
            f"- Files written or created: {len(t['files_written'])} (each one judged against the allow-list)",
            f"- Network-capable libraries loaded (mapped as code): {', '.join(t['network_capable_libraries_mapped']) or 'none'}",
            f"- Network-capable files only read, not loaded: {', '.join(t['network_capable_files_only_read']) or 'none'}",
            f"- Network configuration files read: {', '.join(t['network_config_read']) or 'none'}",
            f"- Network-capable files in the package: {', '.join(r['file'] for r in t['package_network_capable_files']) or 'none'}",
            "- Canary found in (allowed places, each with its reason in the JSON report): "
            + (", ".join(sorted({_one_name(r["value"]) for r in t["canary_places"]})) or "nowhere"),
        ]  # fmt: skip
    gui = doc.get("gui") or {}
    if gui:
        lines += ["", "## The editor", "",
                  f"- Steps: {', '.join(f'{k}: {v}' for k, v in gui.get('steps', {}).items())}",
                  f"- URLs it asked the system to open: {', '.join(gui.get('urls_opened', [])) or 'none'}",
                  f"- Settings file: `{gui.get('settings_file', '?')}`",
                  f"- Python network modules imported: {', '.join(gui.get('python_network_modules', [])) or 'none'}"]  # fmt: skip
    lines += ["", "## Findings (not on the allow-list)", ""]
    lines += [f"- {f['kind']}: `{f['value']}` {f.get('detail', '')}" for f in doc["findings"]] or [
        "None."
    ]
    lines += ["", "## Not claimed", "",
              "Testing shows the absence of network use only on the paths this workflow runs. The "
              "kernel, the desktop and the browser that opens the guide are outside the claim. A "
              "trusted Python plug-in can use the network unless plug-ins are switched off "
              "(`HARNESS_DESIGN_STUDIO_NO_PLUGINS`, or the policy file; docs/SECURITY.md). "
              "See docs/VERIFY_OFFLINE.md to repeat this yourself.", ""]  # fmt: skip
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    what = parser.add_mutually_exclusive_group(required=True)
    what.add_argument(
        "--package", type=Path, help="a .tar.gz or .deb of the program, or its folder"
    )
    what.add_argument("--source", action="store_true", help="the source install of this checkout")
    parser.add_argument("--out", type=Path, default=Path("offline-audit"))
    parser.add_argument("--idle", type=float, default=20.0)
    parser.add_argument("--isolation", default="auto", choices=["auto", *ISOLATION_METHODS])
    parser.add_argument("--gui-platform", default="offscreen", choices=["offscreen", "xcb"])
    parser.add_argument("--only", choices=["isolated", "traced"])
    parser.add_argument("--allow-list", type=Path, default=ALLOW_LIST)
    parser.add_argument("--keep", action="store_true", help="keep the work folder")
    args = parser.parse_args(argv)
    if sys.platform == "win32":
        from tools.offline_audit_windows import main_windows

        return main_windows(args)
    if not sys.platform.startswith("linux"):
        print("error: the offline audit runs on Linux and Windows", file=sys.stderr)
        return 2
    if args.only != "isolated" and shutil.which("strace") is None:
        print("error: strace is not installed (sudo apt-get install strace)", file=sys.stderr)
        return 2
    if args.gui_platform == "xcb" and shutil.which("xvfb-run") is None:
        print(
            "error: --gui-platform xcb needs xvfb-run (sudo apt-get install xvfb)", file=sys.stderr
        )
        return 2
    entries = load_allow_list(args.allow_list)
    out: Path = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    logs = out / "logs"
    logs.mkdir(parents=True)
    scratch = Path(tempfile.mkdtemp(prefix="hds-offline-audit-"))
    try:
        program = (
            source_program() if args.source else unpack(args.package.resolve(), scratch / "package")
        )
        tokens = canary_tokens()
        from harness_design_studio import __version__

        version = __version__
        if program.kind == "package":
            got = subprocess.run([*program.cli, "--version"], capture_output=True, text=True,
                                 check=False).stdout.strip()  # fmt: skip
            version = got.split()[-1] if got else "?"
        doc: dict[str, Any] = {
            "format": FORMAT, "format_version": FORMAT_VERSION, "version": version,
            "target": {"kind": program.kind, "origin": program.origin, "sha256": program.sha256},
            "machine": f"{platform.platform()}, uid {os.getuid()}, Python {platform.python_version()}",  # type: ignore[attr-defined,unused-ignore]
            "gui_platform": args.gui_platform, "idle_seconds": args.idle,
            "canary_base": tokens["base"],
        }  # fmt: skip
        failed: list[str] = []
        doc["isolation"] = {"method": "", "tried": [], "probe": {}}
        if args.only != "traced":
            name, prefix, tried, probe = find_isolation(args.isolation)
            doc["isolation"] = {"method": name, "tried": tried, "probe": probe}
            if not prefix:
                print("error: no way to run a program without network works here:", file=sys.stderr)
                for t in tried:
                    print(f"  {t['method']}: {t.get('why') or t.get('probe')}", file=sys.stderr)
                return 2
            print(f"run (a): every command without network ({name})", flush=True)
            ran = run_workflow(program, scratch / "isolated", logs, prefix, tokens, args.idle,
                               args.gui_platform, "isolated")  # fmt: skip
            doc["isolated"] = {"steps": step_rows(ran)}
            failed += [f"(a) {r.name}" for r in ran if not r.ok]
        if args.only != "isolated":
            print("run (b): every command under strace, with the normal network", flush=True)
            strace = ["strace", "-f", "-qq", "-yy", "-s", "65536",
                      "-e", "trace=%network,%process,%file,write,writev,pwrite64,pwritev,pwritev2,mmap"]  # fmt: skip
            work = scratch / "traced"
            ran = run_workflow(program, work, logs, strace, tokens, args.idle, args.gui_platform,
                               "traced")  # fmt: skip
            doc["traced"] = {
                "steps": step_rows(ran),
                **evaluate(program, ran, work, logs, tokens, entries),
            }
            failed += [f"(b) {r.name}" for r in ran if not r.ok]
            gui_report = work / "gui-report.json"
            if gui_report.is_file():
                doc["gui"] = json.loads(gui_report.read_text(encoding="utf-8"))
                shutil.copy2(gui_report, logs / "traced-gui-report.json")
                traced = doc["traced"]
                for module in doc["gui"].get("python_network_modules", []):
                    judge("python_module", module, entries, {}, traced["findings"], traced["allowed"],
                          "imported by the editor (not necessarily used: see the socket families)")  # fmt: skip
                for url in doc["gui"].get("urls_opened", []):
                    judge("url", url, entries, {"package": str(program.folder or ""), "src": str(ROOT / "src")},
                          traced["findings"], traced["allowed"], "the editor asked the system to open it")  # fmt: skip
            else:
                failed.append("(b) the editor wrote no report")
        doc["findings"] = (doc.get("traced") or {}).get("findings", [])
        doc["failed_steps"] = failed
        doc["result"] = "pass" if not doc["findings"] and not failed else "fail"
        (out / "offline-audit.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n",
                                                encoding="utf-8")  # fmt: skip
        # the summary names the work folder WORK, so that it reads the same on every machine
        (out / "offline-audit.md").write_text(
            markdown(doc).replace(str(scratch), "WORK"), encoding="utf-8"
        )
        print((out / "offline-audit.md").read_text(encoding="utf-8"))
        return 0 if doc["result"] == "pass" else 1
    finally:
        if args.keep:
            print(f"work folder kept: {scratch}")
        else:
            shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
