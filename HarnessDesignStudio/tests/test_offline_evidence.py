"""The offline and security evidence kit (D-203).

REQ-OFFLINE-02: the offline audit (`tools/offline_audit.py`) reads an strace log correctly (socket
families, connect targets, programs started, files written, libraries mapped as code), judges what
it saw against a reviewed allow-list in which every entry has a reason, and passes for the source
install of this checkout in a network namespace and under strace (a slow test, where strace and
`unshare` exist); the editor's `--audit-run` opens a project, asks for the local guide only and
imports no network module of Python.
REQ-OFFLINE-03: the canaries: unique words planted in a project are found in every encoding the
audit looks for and attributed to the field they came from; a canary outside the project, its
outputs and the places the allow-list names (with the fields it allows) is a finding.
REQ-OFFLINE-04: the packages carry none of the network-capable native files that the program never
loads (the Qt network library, the VNC and TUIO plug-ins, Kerberos, OpenSSL's TLS library, Python's
TLS module): the build removes them and refuses a package that still has one, and a file that
stays never needs one that was removed. The guide that F1 opens loads nothing from elsewhere.
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tools import build_installer, offline_audit
from tools.offline_audit import (
    ALLOW_LIST,
    allowed,
    canary_hits,
    joined_lines,
    load_allow_list,
    network_capable,
    read_trace,
    which_tokens,
)

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "harness_design_studio"

TRACE = """\
100  execve("/opt/app/harness-design-studio-gui", ["/opt/app/harness-design-studio-gui", "--audit-run", "p"], 0x7ffd /* 9 vars */) = 0
100  openat(AT_FDCWD</work>, "/opt/app/_internal/libQt6Gui.so.6", O_RDONLY|O_CLOEXEC) = 3</opt/app/_internal/libQt6Gui.so.6>
100  mmap(0x7f0000000000, 4096, PROT_READ|PROT_EXEC, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3</opt/app/_internal/libQt6Gui.so.6>, 0x1000) = 0x7f0000000000
100  openat(AT_FDCWD</work>, "/opt/app/_internal/PySide6/Qt/plugins/platforms/libqvnc.so", O_RDONLY|O_CLOEXEC) = 4</opt/app/_internal/PySide6/Qt/plugins/platforms/libqvnc.so>
100  openat(AT_FDCWD</work>, "p/project.json", O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC, 0666) = 5</work/p/project.json>
100  write(5</work/p/project.json>, "{\\"name\\": \\"Bench CNRYABCDEF123456PRJ\\"}", 36) = 36
100  mkdir("p/outputs", 0777)               = 0
100  renameat2(AT_FDCWD</work>, "p/.a.tmp", AT_FDCWD</work>, "p/a.json", 0) = 0
100  socket(AF_UNIX, SOCK_STREAM|SOCK_CLOEXEC, 0) = 6<UNIX-STREAM:[1234]>
100  connect(6<UNIX-STREAM:[1234]>, {sa_family=AF_UNIX, sun_path=@"/run/display/X99"}, 21) = 0
100  write(6<UNIX-STREAM:[1234->1235]>, "title Bench CNRYABCDEF123456PRJ", 31) = 31
100  socket(AF_INET, SOCK_DGRAM|SOCK_CLOEXEC, IPPROTO_IP <unfinished ...>
101  clone3({flags=CLONE_VM, exit_signal=0, stack=0x7f, stack_size=0x7ff}, 88) = 102
100  <... socket resumed>) = 7<UDP:[5678]>
100  connect(7<UDP:[5678]>, {sa_family=AF_INET, sin_port=htons(53), sin_addr=inet_addr("192.0.2.53")}, 16) = 0
100  write(1</dev/null<char 1:3>>, "ok", 2) = 2
101  execve("/opt/app/harness-design-studio-gui", ["/opt/app/harness-design-studio-gui", "--drc-worker"], 0x7ffd /* 9 vars */) = 0
101  execve("/usr/bin/xdg-open", ["xdg-open", "file:///x"], 0x7ffd /* 9 vars */) = -1 ENOENT (No such file or directory)
"""


@pytest.fixture
def trace(tmp_path: Path) -> Path:
    path = tmp_path / "t.strace"
    path.write_text(TRACE, encoding="utf-8")
    return path


# ---- REQ-OFFLINE-02: reading a trace ------------------------------------------------------------


def test_the_trace_reader_puts_unfinished_calls_together(trace: Path) -> None:
    lines = [text for _pid, text in joined_lines(trace)]
    assert any(
        t.startswith("socket(AF_INET, SOCK_DGRAM|SOCK_CLOEXEC, IPPROTO_IP) = 7") for t in lines
    )


def test_the_trace_reader_finds_sockets_connections_children_files_and_libraries(
    trace: Path,
) -> None:
    facts = read_trace(trace, Path("/work"))
    assert facts.families == {"AF_UNIX": 1, "AF_INET": 1}
    targets = {(c["family"], c["target"]) for c in facts.connections}
    assert targets == {("AF_UNIX", '@"/run/display/X99"'), ("AF_INET", "192.0.2.53:53")}
    programs = [(c["program"], c["argv"][1:], c["ok"]) for c in facts.children]
    assert programs == [
        ("/opt/app/harness-design-studio-gui", ["--audit-run", "p"], True),
        ("/opt/app/harness-design-studio-gui", ["--drc-worker"], True),
        ("/usr/bin/xdg-open", ["file:///x"], False),  # a program tried and not found still counts
    ]
    assert set(facts.written) == {"/work/p/project.json", "/work/p/outputs", "/work/p/a.json"}
    # a library mapped as code is loaded; one only opened (Qt reads plug-in metadata) is not
    assert facts.libraries == {"/opt/app/_internal/libQt6Gui.so.6"}
    assert "/opt/app/_internal/PySide6/Qt/plugins/platforms/libqvnc.so" in facts.opened_libraries
    where = [w for w, _data in facts.writes]
    assert where == ["/work/p/project.json", "UNIX-STREAM:[1234->1235]", "/dev/null"]


def test_every_entry_of_the_allow_list_has_a_reason_and_a_known_kind() -> None:
    entries = load_allow_list(ALLOW_LIST)
    assert entries
    for e in entries:
        assert e["kind"] in offline_audit.KINDS and len(e["reason"]) >= 30, e
    # nothing on it lets the program reach another computer or open a listening socket
    patterns = " ".join(e["pattern"] for e in entries)
    for family in ("AF_INET", "AF_INET6", "AF_NETLINK", "AF_PACKET"):
        assert family not in patterns
    # the one library it may load is OpenSSL's crypto library (hashlib's SHA-256), never TLS
    assert [e["pattern"] for e in entries if e["kind"] in ("library", "package_file")] == [
        "*_socket.*", "*libcrypto*", "*_socket.pyd", "*libcrypto*",
    ]  # fmt: skip
    # Python's socket module may be loaded on Windows only (platform.node() for the lock file)
    assert all(
        e.get("platform") == "win32" for e in entries
        if e["kind"] == "python_module" or e["pattern"] == "*_socket.pyd"
    )  # fmt: skip


def test_what_the_allow_list_does_not_name_is_a_finding() -> None:
    entries = load_allow_list(ALLOW_LIST)
    places = {"gui": "/opt/app/gui", "project": "/w/p", "home": "/w/home", "tmp": "/w/tmp"}
    findings: list[dict[str, str]] = []
    ok: list[dict[str, str]] = []
    offline_audit.judge("child", "/opt/app/gui --drc-worker", entries, places, findings, ok)
    offline_audit.judge("child", "/usr/bin/xdg-open file:///x", entries, places, findings, ok)
    offline_audit.judge("socket_family", "AF_INET", entries, places, findings, ok)
    offline_audit.judge("written", "/w/p/outputs/a.pdf", entries, places, findings, ok)
    offline_audit.judge("written", "/w/home/.cache/x", entries, places, findings, ok)
    assert [f["value"] for f in findings] == [
        "/usr/bin/xdg-open file:///x", "AF_INET", "/w/home/.cache/x",
    ]  # fmt: skip
    assert len(ok) == 2 and all(r["reason"] for r in ok)


# ---- REQ-OFFLINE-03: the canaries -----------------------------------------------------------------


def test_a_canary_is_found_in_utf8_and_utf16_and_named_by_its_field() -> None:
    tokens = offline_audit.canary_tokens()
    base = tokens["base"]
    assert re.fullmatch(r"CNRY[0-9A-F]{12}", base)
    assert tokens["device name"].startswith(base) and tokens["device note"].startswith(base)
    assert canary_hits(f"x {tokens['device note']} y".encode(), base) == 1
    assert canary_hits(tokens["part number"].lower().encode("utf-16-le"), base) == 1
    assert canary_hits(b"nothing here", base) == 0
    text = f"{tokens['interface note']} and {tokens['interface name']}"
    assert which_tokens(text, tokens) == ["interface name", "interface note"]


def test_a_canary_outside_the_allowed_places_or_fields_is_a_finding() -> None:
    entries = load_allow_list(ALLOW_LIST)
    places = {"home": "/w/home", "tmp": "/w/tmp"}
    ini = "/w/home/.config/HarnessDesigner/HarnessDesigner.ini"
    # the recent-projects list may hold the project name and nothing else
    assert allowed(entries, "canary", ini, places, ["project name"])
    assert not allowed(entries, "canary", ini, places, ["project name", "device name"])
    assert not allowed(entries, "canary", "/w/home/.cache/thumbnails/x", places, ["device name"])
    assert allowed(entries, "canary", "{project-or-data}", places, ["device name"])


def test_planting_the_canaries_puts_one_in_each_kind_of_field(tmp_path: Path) -> None:
    from harness_design_studio.core import templates
    from harness_design_studio.core.io.loader import load_project

    folder = tmp_path / "p"
    templates.create_project(folder, offline_audit.TEMPLATE)
    tokens = offline_audit.canary_tokens()
    offline_audit.plant_canaries(folder, tokens)
    project = load_project(folder)
    assert not project.has_errors
    p = project.project
    text = json.dumps(
        [p.meta.name, [(u.name, u.notes) for u in p.units.values()],
         [(i.name, i.notes) for i in p.interfaces.values()],
         [part.part_number for part in p.parts.values()]],
        default=str,
    )  # fmt: skip
    assert set(which_tokens(text, tokens)) == {
        "project name", "device name", "device note", "interface name", "interface note",
        "part number",
    }  # fmt: skip


# ---- REQ-OFFLINE-04: what the packages carry ------------------------------------------------------

SHIPPED_NAMES = [
    "libQt6Network.so.6", "Qt6Network.dll", "libqvnc.so", "libqtuiotouchplugin.so",
    "qtuiotouchplugin.dll", "libgssapi_krb5.so.2", "libkrb5.so.3", "libk5crypto.so.3",
    "libkrb5support.so.0", "libssl.so.3", "libssl-3-x64.dll", "libssl-3.dll",
    "_ssl.cpython-314-x86_64-linux-gnu.so", "_ssl.pyd",
]  # fmt: skip
KEPT_NAMES = [
    "libQt6Gui.so.6", "Qt6Gui.dll", "libqxcb.so", "qwindows.dll", "libqoffscreen.so",
    "libQt6DBus.so.6", "libcrypto.so.3", "libcrypto-3-x64.dll", "_socket.pyd", "libssl_helper.txt",
]  # fmt: skip


@pytest.mark.parametrize("name", SHIPPED_NAMES)
def test_the_network_capable_files_are_named_for_removal_and_for_the_audit(name: str) -> None:
    assert build_installer.network_strip_reason(name), name
    assert network_capable(name), name  # the audit reports the same files


@pytest.mark.parametrize("name", KEPT_NAMES)
def test_the_files_the_program_needs_are_not_removed(name: str) -> None:
    assert not build_installer.network_strip_reason(name), name


def test_the_build_removes_them_and_refuses_a_package_that_still_has_one(tmp_path: Path) -> None:
    internal = tmp_path / "app" / "_internal"
    plugins = internal / "PySide6" / "Qt" / "plugins" / "platforms"
    plugins.mkdir(parents=True)
    (plugins / "libqvnc.so").write_bytes(b"x" * 10)
    (plugins / "libqxcb.so").write_bytes(b"y")
    (internal / "libQt6Network.so.6").symlink_to("PySide6/Qt/plugins/platforms/libqvnc.so")
    assert build_installer.check_package([internal]) == 1  # a package that has them is refused
    removed = build_installer.strip_network_capable([internal])
    assert sorted(Path(p).name for p, _size in removed) == ["libQt6Network.so.6", "libqvnc.so"]
    assert sum(size for _p, size in removed) == 10
    assert (plugins / "libqxcb.so").is_file()
    assert build_installer.network_capable_files([internal]) == []


def test_a_file_that_stays_never_needs_a_removed_library(tmp_path: Path) -> None:
    gui = next(
        (
            Path(p)
            for p in sys.path
            if (Path(p) / "PySide6" / "Qt" / "lib" / "libQt6Gui.so.6").is_file()
        ),
        None,
    )
    if gui is None:
        pytest.skip("needs the Linux PySide6 wheel")
    lib = gui / "PySide6" / "Qt" / "lib" / "libQt6Gui.so.6"
    needed = build_installer.elf_needed(lib)
    assert "libQt6Core.so.6" in needed and "libQt6Network.so.6" not in needed
    folder = tmp_path / "_internal"
    folder.mkdir()
    shutil.copy2(lib, folder / "libQt6Gui.so.6")
    (folder / "libQt6Core.so.6").write_bytes(b"")
    # pretend Qt Core were network-capable: the build must stop, not ship a broken package
    pattern = r"^libQt6Core\.so\.6$"
    build_installer.NETWORK_STRIP[pattern] = "a test"
    try:
        with pytest.raises(SystemExit, match="needs a library that was removed"):
            build_installer.strip_network_capable([folder])
    finally:
        del build_installer.NETWORK_STRIP[pattern]


def test_python_modules_that_could_reach_the_network_are_left_out_of_the_package() -> None:
    for module in (
        "ssl",
        "_ssl",
        "multiprocessing",
        "PySide6.QtNetwork",
        "PySide6.QtWebEngineCore",
    ):
        assert module in build_installer.EXCLUDES, module
    # and nothing of the program imports them, so leaving them out cannot break it
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not re.search(
            r"^\s*(import|from)\s+(multiprocessing|ssl|concurrent)\b", text, re.M
        ), path


def test_the_guide_loads_nothing_from_elsewhere() -> None:
    """F1 hands the guide to the system's browser; it must not make the browser fetch anything."""
    for page in (SRC / "resources" / "guide").rglob("*.htm*"):
        html = page.read_text(encoding="utf-8")
        assert not re.search(
            r"""(src|href|action)\s*=\s*["']?\s*(https?:|//|ftp:)""", html, re.I
        ), page
        assert not re.search(r"url\(\s*['\"]?\s*(https?:|//)", html, re.I), page
        assert not re.search(r"@import\s+['\"]?(https?:|//)", html, re.I), page


# ---- the editor's part of the audit, and the whole audit --------------------------------------------


def test_the_editor_audit_run_opens_the_project_and_asks_for_the_local_guide_only(
    tmp_path: Path,
) -> None:
    pytest.importorskip("PySide6")
    from harness_design_studio.core import templates

    templates.create_project(tmp_path / "p", "first-steps")
    env = {
        **os.environ, "HOME": str(tmp_path / "home"), "XDG_CONFIG_HOME": str(tmp_path / "home" / ".config"),
        "QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": str(ROOT / "src"),
        "APPDATA": str(tmp_path / "appdata"),
    }  # fmt: skip
    report = tmp_path / "report.json"
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-P", str(ROOT / "packaging" / "gui_entry.py"), "--audit-run", "p", str(report), "0.5"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=180, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr[-2000:]
    doc = json.loads(report.read_text(encoding="utf-8"))
    assert all(doc["steps"].values()), doc["steps"]
    assert [u for u in doc["urls_opened"] if not u.startswith("file://")] == []
    assert any(u.endswith("resources/guide/index.html") for u in doc["urls_opened"])
    assert doc["python_network_modules"] == []


@pytest.mark.slow
@pytest.mark.skipif(
    not sys.platform.startswith("linux") or shutil.which("strace") is None,
    reason="the audit needs Linux and strace",
)
def test_the_offline_audit_of_the_source_install_passes(tmp_path: Path) -> None:
    out = tmp_path / "audit"
    only = [] if shutil.which("unshare") else ["--only", "traced"]
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "tools.offline_audit", "--source", "--out", str(out), "--idle", "2", *only],
        cwd=ROOT, capture_output=True, text=True, timeout=900, check=False,
        env={**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "src"), str(ROOT)])},
    )  # fmt: skip
    if done.returncode == 2 and "no way to run a program without network" in done.stderr:
        pytest.skip("no network namespace can be made here: " + done.stderr[-300:])
    doc = json.loads((out / "offline-audit.json").read_text(encoding="utf-8"))
    assert done.returncode == 0, json.dumps(doc["findings"][:10]) + done.stdout[-2000:]
    traced = doc["traced"]
    assert not traced["connections"] and not traced["listening"]
    assert set(traced["socket_families"]) <= {"AF_UNIX"}
    assert (out / "offline-audit.md").read_text(encoding="utf-8").count("Result: PASS") == 1


def test_an_entry_for_one_operating_system_applies_there_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entries = load_allow_list(ALLOW_LIST)
    monkeypatch.setattr(sys, "platform", "linux")
    assert not allowed(entries, "python_module", "socket", {})
    monkeypatch.setattr(sys, "platform", "win32")
    assert allowed(entries, "python_module", "socket", {})
    assert not allowed(entries, "python_module", "ssl", {})


def test_the_windows_audit_watches_connections_and_programs_started() -> None:
    """REQ-OFFLINE-06: the Windows counterpart (run in CI on windows-latest) asks Windows for the
    events of every connection its filtering platform allowed or blocked and of every program
    started; it can be imported on any platform, so that this file is checked everywhere."""
    from tools import offline_audit_windows as win

    assert {5152, 5156, 5157, 5158, 5159} <= set(win.WFP_EVENTS)
    assert set(win.AUDIT_GUIDS) == {
        "Filtering Platform Connection", "Filtering Platform Packet Drop", "Process Creation",
    }  # fmt: skip
    entries = load_allow_list(ALLOW_LIST)
    assert allowed(entries, "child", r"\??\C:\Windows\system32\conhost.exe 0xffffffff -ForceV1", {})
    assert not allowed(entries, "child", r"C:\Windows\System32\curl.exe https://x", {})
