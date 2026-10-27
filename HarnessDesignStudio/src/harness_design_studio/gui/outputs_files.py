"""The Outputs area's list of documents: every file of the outputs folder with its document type, format,
size, time written and SHA-256, and whether it still equals what the export wrote.

    panel = OutputsFiles(ctl, theme, settings)       # under the lists in the Lists tab
    panel.refresh()                                  # reads the folder and hashes the files in a helper thread

The hashes are those of the files **on disk** (not of what the program remembers), worked out in a
`QThread` so a folder of hundreds of drawings never holds up the window. Each is compared with the
`manifest.json` the export wrote beside the files: *Matches export*, *Changed since export*,
*Missing* or *Not in the export*. Open, Reveal in folder and Copy to folder act on the selected
files. Nothing here changes a file.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.io.fs import atomic_write_bytes
from harness_design_studio.core.outputs.build import MANIFEST
from harness_design_studio.gui import export_docs, icons, strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.empty_state import attach_empty_state
from harness_design_studio.gui.export_dialog import human_size, may_open, open_url, reveal_url
from harness_design_studio.gui.notice import InlineNotice
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager

Opener = Callable[[QUrl], bool]


@dataclass(frozen=True)
class FileFacts:
    """One file as found on disk (`sha256` is "" for a file that is listed but missing)."""

    rel: str
    size: int
    mtime: float
    sha256: str
    listed: str  # the sha256 the manifest lists for it, "" when it does not list the file


def read_listed(folder: Path) -> dict[str, str]:
    """path -> sha256 as listed in the manifest of `folder` ({} when there is none or it is
    unreadable)."""
    try:
        doc = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
        return {str(f["path"]): str(f["sha256"]) for f in doc["files"]}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def read_stamp(folder: Path) -> str:
    """The short model hash the files were made from ("" when the manifest cannot be read)."""
    try:
        return str(json.loads((folder / MANIFEST).read_text(encoding="utf-8"))["model_hash"])
    except (OSError, ValueError, KeyError, TypeError):
        return ""


def gather(folder: Path) -> list[FileFacts]:
    """Every file under `folder` and every file the manifest lists, hashed (this reads them all:
    call it off the GUI thread)."""
    listed = read_listed(folder)
    out: dict[str, FileFacts] = {}
    if folder.is_dir():
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(folder).as_posix()
            try:
                data = path.read_bytes()
                stat = path.stat()
            except OSError:
                continue
            out[rel] = FileFacts(
                rel, len(data), stat.st_mtime, hashlib.sha256(data).hexdigest(), listed.get(rel, "")
            )
    for rel, digest in listed.items():
        if rel not in out and export_docs.is_safe(rel):
            out[rel] = FileFacts(rel, 0, 0.0, "", digest)  # listed but gone
    return [out[k] for k in sorted(out)]


def state_of(f: FileFacts) -> tuple[str, str]:
    """(state key of `gui.states`, the words) for one file."""
    if f.rel == MANIFEST:
        return "info", strings.OUT_STATE_MANIFEST
    if f.sha256 == "":
        return "fail", strings.OUT_STATE_MISSING
    if f.listed == "":
        return "warning", strings.OUT_STATE_UNLISTED
    if f.sha256 != f.listed:
        return "fail", strings.OUT_STATE_CHANGED
    return "pass", strings.OUT_STATE_MATCHES


def format_of(rel: str) -> str:
    ext = rel.rpartition(".")[2] if "." in rel.rpartition("/")[2] else ""
    return ext.upper()


class _GatherThread(QThread):
    def __init__(self, folder: Path, generation: int) -> None:
        super().__init__()
        self.folder, self.generation = folder, generation
        self.facts: list[FileFacts] = []
        self.error: str | None = None

    def run(self) -> None:
        try:
            self.facts = gather(self.folder)
        except Exception as exc:  # never let it escape the thread
            self.error = str(exc) or type(exc).__name__


class OutputsFiles(QWidget):
    """The list of the outputs folder's files. See the module text.

    `opener(QUrl)` is what Open and Reveal call (`QDesktopServices.openUrl`, tests replace it);
    `ask_folder(title)` chooses the folder Copy writes to; `refreshed` is emitted when a reading ends."""

    refreshed = Signal()

    def __init__(
        self,
        ctl: EditorController,
        theme: ThemeManager,
        settings: QSettings | None = None,
        *,
        opener: Opener | None = None,
        ask_folder: Callable[[str], str | None] | None = None,
    ) -> None:
        super().__init__()
        self.ctl, self.theme = ctl, theme
        self.opener: Opener = opener or QDesktopServices.openUrl
        self.ask_folder: Callable[[str], str | None] = ask_folder or self._ask_folder
        self.setObjectName("outputs-files")
        self.setAccessibleName(strings.OUT_FILES_NAME)
        self.facts: list[FileFacts] = []
        self.folder: Path | None = None
        self._generation = 0
        self._thread: _GatherThread | None = None
        self._old: list[_GatherThread] = []
        self._dirty = True

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(theme.space(4))
        bar = QHBoxLayout()
        self.title = QLabel(strings.OUT_FILES_TITLE)
        self.title.setProperty("heading", True)
        self.summary = QLabel()
        self.summary.setObjectName("outputs-summary")
        self.summary.setProperty("muted", True)
        bar.addWidget(self.title)
        bar.addWidget(self.summary, 1)
        self.open_btn = self._button(
            "open", "outputs-open", strings.EXP_OPEN, strings.EXP_OPEN_TIP, "folder-open"
        )
        self.reveal_btn = self._button(
            "reveal", "outputs-reveal", strings.EXP_REVEAL, strings.EXP_REVEAL_TIP, "folder-open"
        )
        self.copy_btn = self._button(
            "copy", "outputs-copy", strings.OUT_COPY, strings.OUT_COPY_TIP, "export"
        )
        self.verify_btn = self._button(
            "verify", "outputs-verify", strings.OUT_VERIFY, strings.OUT_VERIFY_TIP, "refresh"
        )
        for b in (self.open_btn, self.reveal_btn, self.copy_btn, self.verify_btn):
            bar.addWidget(b)
        lay.addLayout(bar)
        self.notice = InlineNotice(theme)
        self.notice.setObjectName("outputs-notice")
        lay.addWidget(self.notice)
        cols = [  # what matters first: the file, whether it matches, its checksum
            Column("rel", strings.OUT_COLUMNS["file"], mono=True, tooltip="full_path", width=250),
            Column("result", strings.OUT_COLUMNS["state"], state="state", tooltip="reason", width=160),
            Column("sha", strings.OUT_COLUMNS["sha"], mono=True, tooltip="sha_full", width=120),
            Column("doc", strings.OUT_COLUMNS["doc"], width=180),
            Column("scope", strings.OUT_COLUMNS["scope"], width=80),
            Column("format", strings.OUT_COLUMNS["format"], width=64),
            Column("size_text", strings.OUT_COLUMNS["size"], numeric=True, width=80, sort_key=None),
            Column("when", strings.OUT_COLUMNS["when"], mono=True, width=140),
        ]  # fmt: skip
        self.model = DictTableModel(cols, [], theme)
        self.table = TableView(
            self.model, theme, name=strings.OUT_FILES_NAME, settings=settings, key="outputs-files"
        )
        self.table.setObjectName("outputs-table")
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        lay.addWidget(self.table, 1)
        attach_empty_state(self.table, strings.OUT_EMPTY_TITLE, strings.OUT_EMPTY_HINT)
        self.open_btn.clicked.connect(self.open_selected)
        self.reveal_btn.clicked.connect(self.reveal_selected)
        self.copy_btn.clicked.connect(lambda: self.copy_selected())
        self.verify_btn.clicked.connect(self.refresh)
        self.table.activated.connect(lambda _i: self.open_selected())
        sel = self.table.selectionModel()
        if sel is not None:
            sel.selectionChanged.connect(lambda *_: self._sync_buttons())
        self._sync_buttons()

    def _button(self, key: str, name: str, text: str, tip: str, icon: str) -> QPushButton:
        b = QPushButton()
        b.setObjectName(name)
        icons.icon_button(b, icon, self.theme, tip, text=text)
        return b

    @staticmethod
    def _ask_folder(title: str) -> str | None:
        path = QFileDialog.getExistingDirectory(None, title)
        return path or None

    # ---- reading ---------------------------------------------------------------------------
    @property
    def reading(self) -> bool:
        return self._thread is not None

    def invalidate(self) -> None:
        """Something that may have changed the files happened: read again when this is shown."""
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event: object) -> None:  # noqa: N802
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def refresh(self) -> None:
        """Read and hash the outputs folder in a helper thread; the table fills when it ends."""
        self._dirty = False
        folder = self.ctl.outputs_folder()
        self.folder = folder
        self._drop()
        if folder is None or not folder.is_dir():
            self._show([])
            return
        thread = _GatherThread(folder, self._generation)
        thread.finished.connect(self._done)
        self._thread = thread
        self.summary.setText(strings.OUT_READING)
        self._sync_buttons()
        thread.start()

    def _drop(self) -> None:
        thread, self._thread = self._thread, None
        self._generation += 1
        if thread is not None:
            self._old.append(thread)
        self._old = [t for t in self._old if t.isRunning()]

    def _done(self) -> None:
        thread = self._thread
        if thread is None or not thread.isFinished() or thread.generation != self._generation:
            return
        self._thread = None
        if thread.error is not None:
            self.notice.show_notice("error", strings.OUT_READ_FAILED.format(thread.error))
            self._show([])
        else:
            self.notice.clear()
            self._show(thread.facts)
        self.refreshed.emit()

    def wait_idle(self, timeout_ms: int = 20_000) -> bool:
        """For tests: wait until a running reading has ended."""
        thread = self._thread
        if thread is not None:
            thread.wait(timeout_ms)
            self._done()
        return not self.reading

    def closeEvent(self, event: object) -> None:  # noqa: N802
        self._drop()
        for t in self._old:
            t.wait()
        super().closeEvent(event)  # type: ignore[arg-type]

    # ---- showing ---------------------------------------------------------------------------
    def _row(self, f: FileFacts) -> dict[str, Any]:
        doc = export_docs.classify(f.rel)
        state, words = state_of(f)
        folder = self.folder or Path()
        return {
            "rel": f.rel,
            "doc": doc.label,
            "scope": strings.EXP_WHOLE_FOLDER
            if doc.scope == ""
            else strings.EXP_SYSTEM_SCOPE
            if doc.scope == export_docs.SYSTEM
            else doc.scope,
            "format": format_of(f.rel),
            "size_text": human_size(f.size) if f.sha256 else "",
            "size": f.size,
            "when": datetime.fromtimestamp(f.mtime).strftime("%Y-%m-%d %H:%M") if f.sha256 else "",
            "sha": f.sha256[:12],
            "sha_full": f.sha256,
            "state": state,
            "result": words,
            "reason": strings.OUT_REASON.get(words, ""),
            "full_path": str(folder / f.rel),
        }

    def _show(self, facts: list[FileFacts]) -> None:
        self.facts = facts
        self.model.set_rows([self._row(f) for f in facts])
        if not facts:
            self.summary.setText("")
        else:
            bad = sum(1 for f in facts if state_of(f)[0] == "fail")
            stamp = read_stamp(self.folder) if self.folder else ""
            self.summary.setText(
                strings.OUT_SUMMARY.format(len(facts), self.folder, stamp)
                + (strings.OUT_SUMMARY_BAD.format(bad) if bad else "")
            )
        self._sync_buttons()

    def rows(self) -> list[dict[str, Any]]:
        return [dict(r) if isinstance(r, dict) else {} for r in self.model.rows()]

    def selected_facts(self) -> list[FileFacts]:
        rels = {str(r.get("rel")) for r in self.table.selected_rows() if isinstance(r, dict)}
        return [f for f in self.facts if f.rel in rels]

    def _sync_buttons(self) -> None:
        have = bool(self.selected_facts())
        for b in (self.open_btn, self.reveal_btn, self.copy_btn):
            b.setEnabled(have)
        self.verify_btn.setEnabled(self.ctl.outputs_folder() is not None)

    # ---- Open, Reveal, Copy ---------------------------------------------------------------
    def open_selected(self) -> QUrl | None:
        files = self.selected_facts()
        if not files or self.folder is None:
            return None
        path = self.folder / files[0].rel
        if not may_open(path, listed=files[0].listed != ""):

            def folder() -> None:
                self.opener(reveal_url(path.parent))

            self.notice.show_notice(
                "warning",
                strings.OUT_NOT_OPENED,
                button=strings.EXP_REVEAL_FOLDER,
                tooltip=strings.EXP_REVEAL_FOLDER_TIP,
                callback=folder,
            )
            return None
        url = open_url(path)
        self.opener(url)
        return url

    def reveal_selected(self) -> QUrl | None:
        files = self.selected_facts()
        if not files or self.folder is None:
            return None
        url = reveal_url(self.folder / files[0].rel)
        self.opener(url)
        return url

    def copy_selected(self, folder: str | Path | None = None) -> int:
        """Copy the selected files (as they are on disk, the manifest left out) to an empty folder,
        keeping the folder layout. Returns the number copied."""
        if self.folder is None:
            return 0
        files = [f for f in self.selected_facts() if f.rel != MANIFEST and f.sha256]
        if not files:
            self.notice.show_notice("warning", strings.EXP_COPY_NONE)
            return 0
        chosen = str(folder) if folder is not None else self.ask_folder(strings.EXP_COPY_FOLDER)
        if not chosen:
            return 0
        dest = Path(chosen)
        if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
            self.notice.show_notice("error", strings.EXP_COPY_NOT_EMPTY)
            return 0
        try:
            for f in files:
                if not export_docs.is_safe(f.rel):
                    raise HarnessError(f"'{f.rel}' is not a path inside the outputs folder.")
                data = (self.folder / f.rel).read_bytes()
                atomic_write_bytes(dest / f.rel, data, backup=False, root=dest, durable=False)
        except (HarnessError, OSError) as exc:
            self.notice.show_notice("error", str(exc))
            return 0
        self.notice.show_notice(
            "info",
            strings.EXP_COPY_DONE.format(len(files), dest),
            button=strings.EXP_REVEAL,
            tooltip=strings.EXP_REVEAL_TIP,
            callback=lambda: self._reveal(dest),
        )
        return len(files)

    def _reveal(self, path: Path) -> None:
        self.opener(reveal_url(path))

    def select_file(self, rel: str) -> bool:
        for r in range(self.table.proxy.rowCount()):
            if (
                self.table.proxy.index(r, 0).data(Qt.ItemDataRole.EditRole) == rel
                or self.table.proxy.index(r, 0).data() == rel
            ):
                self.table.selectRow(r)
                return True
        return False
