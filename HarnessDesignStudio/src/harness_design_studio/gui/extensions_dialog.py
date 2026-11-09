# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Extensions of the open project (D-191 (5), S8): the page under **Help > Extensions** and the
question that names the code before a Python plug-in is loaded.

    ExtensionsDialog(parent, theme, ctl).exec()
    TrustDialog(parent, theme, info, source).exec()

Nothing here runs a plug-in. The page lists what `harness-design-studio extensions` lists (the
declarative files, the Python plug-ins, the registered items, the problems). The trust question shows
the name, version, file, SHA-256 and number of lines of the code and, on request, the code itself;
the person types the plug-in's name to trust it, so a click through cannot trust it by accident. The
trust is kept in the user's settings folder (`core.extensions.trust`), never in the project.
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core.extensions import manager, plugins, trust
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import EditorController
from harness_design_studio.gui.dialog_base import Dialog
from harness_design_studio.gui.theme import ThemeManager, mark_mono

MAX_SOURCE_SHOWN = 200_000  # characters of a plug-in's code shown in the question


def source_text(root: str, info: plugins.PluginInfo) -> str:
    """The code of a project plug-in, to read before trusting it (an installed package: a note)."""
    if info.source != plugins.PROJECT:
        return f"({info.where}: the code is in the installed package.)"
    try:
        text = (Path(root) / info.where).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "(the file cannot be read)"
    return text[:MAX_SOURCE_SHOWN] + ("\n(...)" if len(text) > MAX_SOURCE_SHOWN else "")


class TrustDialog(Dialog):
    """Names the code and asks for its name to be typed. Accepted means: trust it."""

    def __init__(
        self, parent: QWidget | None, theme: ThemeManager, info: plugins.PluginInfo, source: str
    ) -> None:
        super().__init__(parent)
        self.info = info
        self.setObjectName("trust-dialog")
        self.setWindowTitle(strings.EXT_TRUST_TITLE)
        self.resize(theme.px(720), theme.px(420))
        lay = QVBoxLayout(self)
        body = QLabel(strings.EXT_TRUST_BODY.format(name=info.name))
        body.setWordWrap(True)
        body.setObjectName("trust-body")
        lay.addWidget(body)
        self.fields: dict[str, QLabel] = {}
        values = (
            info.name, info.version, ", ".join(info.kinds), info.where, info.sha256, str(info.lines)
        )  # fmt: skip
        for label, value in zip(strings.EXT_TRUST_FIELDS, values, strict=True):
            row = QHBoxLayout()
            name = QLabel(label)
            name.setMinimumWidth(theme.px(90))
            shown = QLabel(value)
            shown.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            shown.setWordWrap(True)
            mark_mono(shown)
            shown.setObjectName(f"trust-{label.lower().replace('-', '')}")
            row.addWidget(name)
            row.addWidget(shown, 1)
            lay.addLayout(row)
            self.fields[label] = shown
        if info.description:
            what = QLabel(info.description)
            what.setWordWrap(True)
            lay.addWidget(what)
        risk = QLabel(strings.EXT_TRUST_RISK)
        risk.setWordWrap(True)
        risk.setObjectName("trust-risk")
        lay.addWidget(risk)
        self.source_btn = QPushButton(strings.EXT_SHOW_SOURCE)
        self.source_btn.setCheckable(True)
        self.source_btn.setObjectName("trust-show-source")
        lay.addWidget(self.source_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        self.source = QPlainTextEdit()
        self.source.setReadOnly(True)
        self.source.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.source.setPlainText(source)
        self.source.setObjectName("trust-source")
        self.source.setAccessibleName(strings.EXT_TRUST_NAME)
        mark_mono(self.source)
        self.source.setVisible(False)
        lay.addWidget(self.source, 1)
        self.source_btn.toggled.connect(self._toggle_source)
        lay.addWidget(QLabel(strings.EXT_TRUST_TYPE))
        self.typed = QLineEdit()
        self.typed.setObjectName("trust-typed")
        self.typed.setAccessibleName(strings.EXT_TRUST_TYPE)
        lay.addWidget(self.typed)
        row = QHBoxLayout()
        row.addStretch(1)
        self.later = QPushButton(strings.EXT_TRUST_LATER)
        self.later.setObjectName("trust-later")
        self.later.setDefault(True)
        self.ok = QPushButton(strings.EXT_TRUST_OK)
        self.ok.setObjectName("trust-ok")
        self.ok.setEnabled(False)
        row.addWidget(self.later)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.later.clicked.connect(self.reject)
        self.ok.clicked.connect(self.accept)
        self.typed.textChanged.connect(lambda t: self.ok.setEnabled(t.strip() == info.name))

    def _toggle_source(self, shown: bool) -> None:
        self.source.setVisible(shown)
        self.source_btn.setText(strings.EXT_HIDE_SOURCE if shown else strings.EXT_SHOW_SOURCE)


def _exec(dlg: QDialog) -> int:
    return int(dlg.exec())


def _table(headers: tuple[str, ...], name: str) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setObjectName(name)
    t.setHorizontalHeaderLabels(list(headers))
    t.verticalHeader().hide()
    t.horizontalHeader().setStretchLastSection(True)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    return t


def _yes(flag: object) -> str:
    return (
        strings.EXT_NOT_APPLICABLE
        if flag is None
        else (strings.EXT_YES if flag else strings.EXT_NO)
    )


class ExtensionsDialog(Dialog):
    """Help > Extensions: what the project's extensions are, and the way to trust a plug-in."""

    def __init__(self, parent: QWidget | None, theme: ThemeManager, ctl: EditorController) -> None:
        super().__init__(parent)
        self.ctl, self.theme = ctl, theme
        self.setObjectName("extensions-dialog")
        self.setWindowTitle(strings.EXT_TITLE)
        self.setAccessibleName(strings.EXT_NAME)
        self.resize(theme.px(980), theme.px(680))
        lay = QVBoxLayout(self)
        intro = QLabel(strings.EXT_INTRO)
        intro.setWordWrap(True)
        intro.setObjectName("extensions-intro")
        lay.addWidget(intro)
        self.empty = QLabel(strings.EXT_NO_FOLDER)
        self.empty.setObjectName("extensions-empty")
        lay.addWidget(self.empty)
        self.files_label = QLabel(f"<b>{strings.EXT_FILES}</b>")
        self.files = _table(strings.EXT_FILE_COLUMNS, "extensions-files")
        self.plugins_label = QLabel(f"<b>{strings.EXT_PLUGINS}</b>")
        self.plugins = _table(strings.EXT_PLUGIN_COLUMNS, "extensions-plugins")
        self.items_label = QLabel(f"<b>{strings.EXT_ITEMS}</b>")
        self.builtin = QCheckBox(strings.EXT_SHOW_BUILTIN)
        self.builtin.setObjectName("extensions-show-builtin")
        self.items = _table(strings.EXT_ITEM_COLUMNS, "extensions-items")
        self.problems_label = QLabel(f"<b>{strings.EXT_PROBLEMS}</b>")
        self.problems = QPlainTextEdit()
        self.problems.setReadOnly(True)
        self.problems.setObjectName("extensions-problems")
        self.problems.setMaximumHeight(theme.px(90))
        mark_mono(self.problems)
        for w in (
            self.files_label, self.files, self.plugins_label, self.plugins,
            self.items_label, self.builtin, self.items, self.problems_label, self.problems,
        ):  # fmt: skip
            lay.addWidget(w, 1 if isinstance(w, QTableWidget) else 0)
        row = QHBoxLayout()
        self.trust_btn = QPushButton(strings.EXT_TRUST)
        self.trust_btn.setObjectName("extensions-trust")
        self.revoke_btn = QPushButton(strings.EXT_REVOKE)
        self.revoke_btn.setObjectName("extensions-revoke")
        self.reload_btn = QPushButton(strings.EXT_RELOAD)
        self.reload_btn.setObjectName("extensions-reload")
        close = QPushButton(strings.CLOSE)
        close.setObjectName("extensions-close")
        close.setDefault(True)
        for b in (self.trust_btn, self.revoke_btn, self.reload_btn):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(close)
        lay.addLayout(row)
        close.clicked.connect(self.accept)
        self.trust_btn.clicked.connect(self.ask_trust)
        self.revoke_btn.clicked.connect(self.revoke)
        self.reload_btn.clicked.connect(self.reload)
        self.builtin.toggled.connect(self.fill)
        self.plugins.itemSelectionChanged.connect(self._buttons)
        self.run_dialog: Callable[[QDialog], int] = _exec  # tests replace this
        self.fill()

    # ---- content -----------------------------------------------------------------------------------
    def fill(self) -> None:
        doc = manager.listing(self.ctl.project)
        has = bool(doc["has_folder"])
        self.empty.setVisible(not has)
        for w in (
            self.files_label, self.files, self.plugins_label, self.plugins, self.problems_label,
            self.problems,
        ):  # fmt: skip
            w.setVisible(has)
        self.items_label.setVisible(True)
        self.builtin.setVisible(has)
        self._rows(
            self.files,
            [
                [
                    f["file"],
                    f["name"],
                    f["version"],
                    f["sha256"][:12],
                    _yes(f["enabled"]),
                    f["status"],
                ]
                for f in doc["files"]
            ],
        )
        self._rows(
            self.plugins,
            [
                [
                    p["name"], p["version"], ", ".join(p["kinds"]), p["where"], p["sha256"][:12],
                    str(p["lines"]), _yes(p["enabled"]), _yes(p["trusted"]),
                    p["state"] + (f": {p['message']}" if p["message"] and p["state"] != "disabled" else ""),
                ]
                for p in doc["plugins"]
            ],
        )  # fmt: skip
        show_all = self.builtin.isChecked() or not has
        items = [i for i in doc["items"] if show_all or i["source"] != "built-in"]
        self._rows(
            self.items,
            [
                [
                    i["kind"], i["name"], i["source"], i["origin"], i["version"], i["sha256"][:12],
                    _yes(i["enabled"]), _yes(i["trusted"]) if i["source"] != "built-in" else strings.EXT_YES,
                ]
                for i in items
            ],
        )  # fmt: skip
        self.problems.setPlainText("\n".join(self._problem_lines(doc)))
        self._buttons()

    @staticmethod
    def _problem_lines(doc: dict[str, object]) -> list[str]:
        out = []
        for i in doc["issues"]:  # type: ignore[attr-defined]
            where = f"{i['file']}:{i['line']}" if i["line"] else i["file"]
            out.append(
                f"{i['severity']}: {where}: "
                + (f"{i['path']}: " if i["path"] else "")
                + i["message"]
            )
        return out

    @staticmethod
    def _rows(table: QTableWidget, rows: list[list[str]]) -> None:
        table.setRowCount(len(rows))
        for r, cells in enumerate(rows):
            for c, text in enumerate(cells):
                table.setItem(r, c, QTableWidgetItem(str(text)))
        table.resizeColumnsToContents()

    # ---- the buttons -------------------------------------------------------------------------------
    def selected_plugin(self) -> plugins.PluginInfo | None:
        ext = self.ctl.project.extensions
        rows = self.plugins.selectionModel().selectedRows() if ext is not None else []
        return ext.plugins[rows[0].row()] if rows and rows[0].row() < len(ext.plugins) else None

    def _buttons(self) -> None:
        info = self.selected_plugin()
        usable = info is not None and info.state != plugins.INVALID
        self.trust_btn.setEnabled(bool(usable and info is not None and not info.trusted))
        self.revoke_btn.setEnabled(bool(info is not None and info.trusted))

    def ask_trust(self) -> bool:
        """Name the code and ask. True when it was trusted."""
        info = self.selected_plugin()
        ext = self.ctl.project.extensions
        if info is None or ext is None:
            return False
        dlg = TrustDialog(self, self.theme, info, source_text(ext.root, info))
        if self.run_dialog(dlg) != QDialog.DialogCode.Accepted:
            return False
        trust.trust(info.name, info.sha256, info.version, info.where)
        self.ctl.reload_extensions()
        self.fill()
        return True

    def revoke(self) -> None:
        info = self.selected_plugin()
        if info is None:
            return
        trust.revoke(info.name)
        self.ctl.reload_extensions()
        self.fill()

    def reload(self) -> None:
        self.ctl.reload_extensions()
        self.fill()


def ask_to_trust_enabled(
    parent: QWidget | None,
    theme: ThemeManager,
    ctl: EditorController,
    run: Callable[[QDialog], int] = _exec,
) -> int:
    """When a project is opened: for each plug-in that the project enables and that is not trusted,
    name the code and ask. Returns how many were trusted. Declining changes nothing: the plug-in is
    listed as not loaded, and the Checks panel says so."""
    ext = ctl.project.extensions
    if ext is None or ctl.read_only:
        return 0
    trusted = 0
    for info in ext.plugins:
        if info.enabled and info.state == plugins.UNTRUSTED:
            dlg = TrustDialog(parent, theme, info, source_text(ext.root, info))
            if run(dlg) == QDialog.DialogCode.Accepted:
                trust.trust(info.name, info.sha256, info.version, info.where)
                trusted += 1
    if trusted:
        ctl.reload_extensions()
    return trusted
