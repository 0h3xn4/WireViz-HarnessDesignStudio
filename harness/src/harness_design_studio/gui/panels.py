"""Side and bottom panels: palette, properties, problems, to-do, interface table, harness plans."""

from collections.abc import Callable
from functools import partial

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyledItemDelegate,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import checks, drc, edit
from harness_design_studio.core.generate.explain import explain_harness, explain_wire
from harness_design_studio.core.library_import import describe_library
from harness_design_studio.core.model import InterfaceInstance, Part
from harness_design_studio.core.verify import verify_project
from harness_design_studio.core.wirecolours import name_of, resolve
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import LIST_DELAY_MS, Delta, EditorController
from harness_design_studio.gui.preview import DrawingPreview
from harness_design_studio.gui.theme import ThemeManager
from harness_design_studio.gui.tokens import CATEGORIES, style_category


def category_icon(cat: str, theme: ThemeManager, size: int = 20, pressed: bool = False) -> QIcon:
    """Letter chip in the category colour: colour is never the only cue."""
    s = theme.px(size)
    pm = QPixmap(s, s)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cat = style_category(cat)
    color = QColor(theme.tokens[f"cat-{cat}"])
    p.setPen(QPen(QColor(theme.tokens["on-primary"]) if pressed else color, 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(2, 2, s - 4, s - 4, 4, 4)
    f = QFont()
    f.setBold(True)
    f.setPixelSize(max(8, int(s * 0.55)))
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, CATEGORIES[cat]["icon"])
    p.end()
    return QIcon(pm)


def type_icon(type_id: str, cat: str, theme: ThemeManager, pressed: bool = False) -> QIcon:
    """The picture of a kind of link (bolt, bus, wave ...) in its category colour."""
    from harness_design_studio.gui import glyphs

    w, h = int(glyphs.LINK_GLYPH_W * 1.4), int(glyphs.LINK_GLYPH_H * 1.4)
    pm = QPixmap(theme.px(w + 4), theme.px(h + 4))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    colour = QColor(theme.tokens["on-primary" if pressed else f"cat-{style_category(cat)}"])
    glyphs.draw_link_glyph(p, 2, 2, type_id, cat, colour, 1.4 * theme.px(1))
    p.end()
    return QIcon(pm)


def heading(text: str) -> QLabel:
    lab = QLabel(text.upper())
    lab.setProperty("heading", True)
    return lab


def part_summary(part: Part) -> str:
    """What a library part is, in one line: description, maker, pins, approval and ratings."""
    bits = [part.description or part.id]
    if part.manufacturer:
        bits.append(part.manufacturer)
    if part.pin_count:
        bits.append(f"{part.pin_count} pins")
    if part.specification:
        bits.append(part.specification)
    bits.append(strings.APPROVAL.get(part.approval, part.approval))
    if part.unverified:
        bits.append(strings.PART_UNVERIFIED)
    if part.ratings:
        bits.append(", ".join(f"{k} {v:g}" for k, v in sorted(part.ratings.items())))
    return " · ".join(bits)


def muted(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("muted", True)
    lab.setWordWrap(True)
    lab.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
    return lab


def scroll_body(area: QScrollArea) -> QVBoxLayout:
    """Give a scroll area a body whose layout never squeezes its children (it scrolls instead)."""
    area.setWidgetResizable(True)
    body = QWidget()
    lay = QVBoxLayout(body)
    lay.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
    area.setWidget(body)
    return lay


def clear_layout(layout: QLayout) -> None:
    """Remove and delete everything in a layout, including nested layouts."""
    while layout.count():
        item = layout.takeAt(0)
        if item is None:
            continue
        widget = item.widget()
        if widget is not None:
            widget.hide()  # deleteLater is deferred; hide now so nothing lingers on screen
            widget.setParent(None)
            widget.deleteLater()
        sub = item.layout()
        if sub is not None:
            clear_layout(sub)


# ---- palette -------------------------------------------------------------------------------------


class PalettePanel(QScrollArea):
    addUnit = Signal(str)
    connectType = Signal(str)
    importRequested = Signal()

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl, self.theme = ctl, theme
        self.setObjectName("palette")
        self.setAccessibleName(strings.PALETTE)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        self.setWidget(body)
        outer = QVBoxLayout(body)
        outer.setSpacing(4)
        outer.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        outer.addWidget(heading(strings.ADD_UNIT))
        self.add_buttons: dict[str, QPushButton] = {}
        for tid, tpl in edit.TEMPLATES.items():
            shown = (
                tpl.label if len(tpl.label) <= 22 else tpl.label[:21] + "…"
            )  # full text in the tip
            b = QPushButton(f"＋ {shown}")
            b.setObjectName(f"add-{tid}")
            b.setToolTip(strings.ADD_UNIT_TIP.format(tpl.label))
            b.clicked.connect(lambda _=False, t=tid: self.addUnit.emit(t))
            outer.addWidget(b)
            self.add_buttons[tid] = b
        outer.addWidget(heading(strings.CONNECT_WITH))
        self.type_box = QVBoxLayout()
        outer.addLayout(self.type_box)
        outer.addWidget(muted(strings.CONNECT_HELP))
        outer.addWidget(heading(strings.BRING_IN_DATA))
        self.import_btn = QPushButton(strings.IMPORT_BUTTON)
        self.import_btn.setObjectName("import-button")
        self.import_btn.clicked.connect(self.importRequested)
        outer.addWidget(self.import_btn)
        outer.addStretch(1)
        self.type_buttons: dict[str, QPushButton] = {}
        ctl.connectChanged.connect(self.refresh)
        ctl.stateChanged.connect(self.refresh)
        ctl.changed.connect(lambda _d: self._maybe_rebuild_types())
        theme.changed.connect(self._rebuild_types)  # icons depend on the theme
        self._rebuild_types()

    def _maybe_rebuild_types(self) -> None:
        if set(self.type_buttons) != set(self.ctl.project.interface_types):
            self._rebuild_types()

    def _rebuild_types(self) -> None:
        clear_layout(self.type_box)
        self.type_buttons.clear()
        for tid, t in sorted(self.ctl.project.interface_types.items()):
            b = QPushButton(t.name)
            b.setObjectName(f"type-{tid}")
            b.setCheckable(True)
            b.setIcon(type_icon(tid, t.category, self.theme))
            b.setToolTip(f"{t.name}: {CATEGORIES[style_category(t.category)]['label']} interface")
            b.clicked.connect(lambda _=False, x=tid: self.connectType.emit(x))
            self.type_box.addWidget(b)
            self.type_buttons[tid] = b
        self.type_box.invalidate()
        body = self.widget()
        if body is not None:
            body.updateGeometry()
        self.refresh()

    def refresh(self) -> None:
        ro = self.ctl.read_only
        for b in self.add_buttons.values():
            b.setEnabled(not ro)
        self.import_btn.setEnabled(not ro)
        for tid, b in self.type_buttons.items():
            active = self.ctl.tool == "connect" and self.ctl.connect_type == tid
            b.setEnabled(not ro)
            if b.isChecked() != active or b.property("icon-state") is None:
                b.blockSignals(True)
                b.setChecked(active)
                b.blockSignals(False)
                t = self.ctl.project.interface_types[tid]
                b.setIcon(type_icon(tid, t.category, self.theme, pressed=active))
                b.setProperty("icon-state", active)


# ---- properties ----------------------------------------------------------------------------------


class _Field(QWidget):
    """A labelled line edit with an inline error line (live validation)."""

    def __init__(self, label: str, value: str, *, enabled: bool = True) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.label = muted(label)
        self.edit = QLineEdit(value)
        self.edit.setEnabled(enabled)
        self.edit.setAccessibleName(label)
        self.error = QLabel("")
        self.error.setProperty("error", True)
        self.error.setWordWrap(True)
        self.error.hide()
        lay.addWidget(self.label)
        lay.addWidget(self.edit)
        lay.addWidget(self.error)

    def show_error(self, message: str) -> None:
        self.error.setText(message)
        self.error.setVisible(bool(message))
        self.edit.setProperty("invalid", bool(message))
        self.edit.style().unpolish(self.edit)
        self.edit.style().polish(self.edit)


def parse_optional_float(text: str) -> tuple[float | None, str]:
    text = text.strip()
    if not text:
        return None, ""
    try:
        value = float(text)
    except ValueError:
        return None, strings.NUMBER_HELP
    if value != value or value in (float("inf"), float("-inf")) or value < 0:
        return None, strings.NUMBER_HELP
    return value, ""


class PropertiesPanel(QScrollArea):
    confirmRequested = Signal(str)

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl, self.theme = ctl, theme
        self.setObjectName("properties")
        self.setAccessibleName(strings.PROPERTIES)
        self.lay = scroll_body(self)
        self.body: QWidget = self.widget()  # type: ignore[assignment]
        self.fields: dict[str, QWidget] = {}
        ctl.selectionChanged.connect(self.rebuild)
        ctl.modeChanged.connect(self.rebuild)
        ctl.stateChanged.connect(self._state)
        ctl.changed.connect(self._changed)
        self.rebuild()

    def _state(self) -> None:
        for w in self.body.findChildren(QWidget):
            if w.property("editable") is True and self.ctl.read_only:
                w.setEnabled(False)

    def _changed(self, delta: Delta) -> None:
        s = self.ctl.selection
        if s is None:
            return
        if (
            (s.kind == "unit" and s.id in delta.units)
            or (s.kind == "interface" and s.id in delta.interfaces)
            or delta.full
        ):
            focus = self.body.focusWidget()
            if focus is None or not isinstance(
                focus, QLineEdit | QPlainTextEdit
            ):  # never rebuild under the cursor
                self.rebuild()

    def rebuild(self) -> None:
        clear_layout(self.lay)
        self.fields.clear()
        s = self.ctl.selection
        p = self.ctl.project
        if (
            s is None
            or (s.kind == "unit" and s.id not in p.units)
            or (s.kind == "interface" and s.id not in p.interfaces)
        ):
            self.lay.addWidget(heading(strings.PROPERTIES))
            self.lay.addWidget(muted(strings.NOTHING_SELECTED))
            self.lay.addStretch(1)
            return
        (self._unit_form if s.kind == "unit" else self._interface_form)(s.id)
        self.lay.addStretch(1)
        self._state()

    def _editable(self, w: QWidget) -> QWidget:
        w.setProperty("editable", True)
        return w

    # unit ---------------------------------------------------------------------------------------
    def _unit_form(self, uid: str) -> None:
        ctl, p = self.ctl, self.ctl.project
        u = p.units[uid]
        self.lay.addWidget(heading(strings.UNIT))
        f_id = _Field(strings.FIELD_ID, u.id)
        self._editable(f_id.edit)
        self.fields["id"] = f_id.edit

        def check_id(text: str) -> str:
            try:
                edit.ops_rename_unit(p, uid, text.strip())
            except Exception as exc:
                return _first_line(exc)
            return ""

        f_id.edit.textEdited.connect(lambda t: f_id.show_error(check_id(t)))

        def commit_id() -> None:
            text = f_id.edit.text().strip()
            if text != uid and not check_id(text):
                ctl.rename_unit(uid, text)

        f_id.edit.editingFinished.connect(commit_id)
        self.lay.addWidget(f_id)
        f_name = _Field(strings.FIELD_NAME, u.name)
        self._editable(f_name.edit)
        self.fields["name"] = f_name.edit
        f_name.edit.editingFinished.connect(
            lambda: self._commit_unit(uid, f_name, "name", f_name.edit.text())
        )
        self.lay.addWidget(f_name)
        self.lay.addWidget(muted(strings.FIELD_CHAIN))
        side = QComboBox()
        side.setObjectName("unit-side")
        side.addItems(["nominal", "redundant", "none"])
        side.setCurrentText(u.side)
        side.setToolTip(strings.CHAIN_TIP)
        side.setAccessibleName(strings.FIELD_CHAIN)
        side.activated.connect(lambda _i: ctl.update_unit(uid, side=side.currentText()))
        self._editable(side)
        self.lay.addWidget(side)
        zone = _Field(strings.FIELD_ZONE_AUTO, u.zone or "", enabled=False)
        zone.edit.setObjectName("unit-zone")
        self.lay.addWidget(zone)
        sub = _Field(strings.FIELD_SUBSYSTEM, u.subsystem, enabled=False)
        self.lay.addWidget(sub)
        if ctl.mode == "expert":
            self.lay.addWidget(heading(strings.CONNECTORS_PHYSICAL))
            self._connector_rows(uid)
        else:
            self.lay.addWidget(muted(strings.GUIDED_HIDES_PHYSICAL))
        btn = QPushButton(strings.REDUNDANT_COPY)
        btn.setObjectName("props-redundant")
        btn.setEnabled(u.side != "redundant" and f"{uid}-R" not in p.units)
        btn.clicked.connect(lambda: ctl.redundant_copy(uid))
        self._editable(btn)
        self.lay.addWidget(btn)

    def _commit_unit(self, uid: str, field: _Field, key: str, value: str) -> None:
        cur = getattr(self.ctl.project.units[uid], key)
        if value == cur:
            return
        try:
            edit.ops_update_unit(self.ctl.project, uid, **{key: value})
        except Exception as exc:
            field.show_error(_first_line(exc))
            return
        field.show_error("")
        self.ctl.update_unit(uid, **{key: value})

    def _connector_rows(self, uid: str) -> None:
        ctl, p = self.ctl, self.ctl.project
        auto_by_conn: dict[str, str] = {}
        for i in p.interfaces.values():
            for e in i.endpoints:
                if e.auto and e.connector_id:
                    auto_by_conn[e.connector_id] = i.id
        parts = sorted(pid for pid, part in p.parts.items() if part.category == "connector")
        for c in edit.unit_connectors(p, uid):
            card = QFrame()
            card.setProperty("card", True)
            card.setProperty("severity", "info")
            lay = QVBoxLayout(card)
            row = QHBoxLayout()
            row.addWidget(QLabel(f"<b>{c.name}</b>"))
            if c.id in auto_by_conn:
                badge = QLabel(strings.AUTO)
                badge.setToolTip(strings.AUTO_TIP)
                row.addWidget(badge)
                confirm = QPushButton(strings.CONFIRM)
                confirm.setObjectName(f"confirm-{c.id}")
                iid = auto_by_conn[c.id]
                confirm.clicked.connect(lambda _=False, x=iid: ctl.confirm_interface(x))
                self._editable(confirm)
                row.addWidget(confirm)
            row.addStretch(1)
            lay.addLayout(row)
            combo = QComboBox()
            combo.setObjectName(f"part-{c.id}")
            combo.addItems(parts)
            for k, pid in enumerate(parts):  # the part list shows what each part is, on hover
                combo.setItemData(k, part_summary(p.parts[pid]), Qt.ItemDataRole.ToolTipRole)
            combo.setCurrentText(c.part_id)
            combo.setAccessibleName(f"{strings.LIBRARY_PART} {c.name}")
            combo.activated.connect(
                lambda _i, cid=c.id, cb=combo: ctl.set_connector_part(cid, cb.currentText())
            )
            self._editable(combo)
            lay.addWidget(combo)
            info = muted(part_summary(p.parts[c.part_id]) if c.part_id in p.parts else "")
            info.setObjectName(f"part-info-{c.id}")
            lay.addWidget(info)
            combo.currentTextChanged.connect(
                lambda text, lab=info: lab.setText(
                    part_summary(p.parts[text]) if text in p.parts else ""
                )
            )
            carries = (
                ", ".join(p.interface_types[t].name for t in c.carries if t in p.interface_types)
                or strings.ANY_TYPE
            )
            lay.addWidget(muted(strings.CARRIES.format(carries)))
            self.lay.addWidget(card)
        self.lay.addWidget(muted(strings.PARTS_UNVERIFIED))
        self.lay.addWidget(muted(describe_library(p)))

    # interface ----------------------------------------------------------------------------------
    def _interface_form(self, iid: str) -> None:
        ctl, p = self.ctl, self.ctl.project
        i = p.interfaces[iid]
        t = p.interface_types[i.type_id]
        self.lay.addWidget(heading(strings.INTERFACE))
        self.lay.addWidget(_Field(strings.FIELD_ID, i.id, enabled=False))
        f_name = _Field(strings.FIELD_NAME, i.name)
        self._editable(f_name.edit)
        self.fields["name"] = f_name.edit
        f_name.edit.editingFinished.connect(
            lambda: self._commit_if(iid, f_name, "name", f_name.edit.text())
        )
        self.lay.addWidget(f_name)
        type_row = QHBoxLayout()
        icon = QLabel()
        icon.setPixmap(
            category_icon(t.category, self.theme).pixmap(self.theme.px(20), self.theme.px(20))
        )
        type_row.addWidget(icon)
        type_row.addWidget(QLabel(f"{t.name} ({CATEGORIES[style_category(t.category)]['label']})"))
        type_row.addStretch(1)
        self.lay.addLayout(type_row)
        self.lay.addWidget(muted(strings.FIELD_CHAIN))
        side = QComboBox()
        side.setObjectName("if-chain")
        side.setAccessibleName(strings.FIELD_CHAIN)
        side.addItems(["nominal", "redundant", "none"])
        side.setCurrentText(i.redundancy)
        side.activated.connect(lambda _i: ctl.update_interface(iid, redundancy=side.currentText()))
        self._editable(side)
        self.lay.addWidget(side)
        for key, label in (
            ("max_current_a", strings.FIELD_MAX_A),
            ("voltage_v", strings.FIELD_VOLTAGE),
        ):
            cur = getattr(i, key)
            f = _Field(label, "" if cur is None else f"{cur:g}")
            self._editable(f.edit)
            self.fields[key] = f.edit
            f.edit.editingFinished.connect(lambda k=key, fld=f: self._commit_number(iid, fld, k))
            self.lay.addWidget(f)
        f_req = _Field(strings.FIELD_REQUIREMENT, i.requirement_id or "")
        self._editable(f_req.edit)
        self.fields["requirement_id"] = f_req.edit
        f_req.edit.editingFinished.connect(
            lambda: self._commit_if(iid, f_req, "requirement_id", f_req.edit.text().strip() or None)
        )
        self.lay.addWidget(f_req)
        self.lay.addWidget(heading(strings.ENDS))
        for k in range(len(i.endpoints)):
            self.lay.addWidget(self._end_row(i, k))
        if any(e.auto for e in i.endpoints):
            b = QPushButton(strings.CONFIRM_AUTO)
            b.setObjectName("if-confirm")
            b.clicked.connect(lambda: ctl.confirm_interface(iid))
            self._editable(b)
            self.lay.addWidget(b)
        self.lay.addWidget(muted(strings.SIGNALS.format(", ".join(s.name for s in t.signals))))

    def _end_row(self, i: InterfaceInstance, k: int) -> QWidget:
        ctl, p = self.ctl, self.ctl.project
        e = i.endpoints[k]
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel(f"{strings.FROM if k == 0 else strings.TO}: <b>{e.unit_id}</b>"))
        if ctl.mode == "expert":
            combo = QComboBox()
            combo.setObjectName(f"end-{k}")
            combo.setAccessibleName(
                strings.CONNECTOR_AT_END.format(strings.FROM if k == 0 else strings.TO, e.unit_id)
            )
            choices = [
                c
                for c in edit.unit_connectors(p, e.unit_id)
                if c.id == e.connector_id or edit.connector_compat(p, i.type_id, c.id).ok
            ]
            for c in choices:
                combo.addItem(c.name, c.id)
            if e.connector_id in [c.id for c in choices]:
                combo.setCurrentIndex([c.id for c in choices].index(e.connector_id))
            combo.activated.connect(
                lambda _i, cb=combo: ctl.set_endpoint_connector(i.id, k, cb.currentData())
            )
            self._editable(combo)
            lay.addWidget(combo)
        if e.auto:
            badge = QLabel(strings.AUTO)
            badge.setToolTip(strings.AUTO_TIP)
            lay.addWidget(badge)
        lay.addStretch(1)
        return box

    def _commit_if(self, iid: str, field: _Field, key: str, value: object) -> None:
        if value == getattr(self.ctl.project.interfaces[iid], key):
            return
        try:
            edit.ops_update_interface(self.ctl.project, iid, **{key: value})
        except Exception as exc:
            field.show_error(_first_line(exc))
            return
        field.show_error("")
        self.ctl.update_interface(iid, **{key: value})

    def _commit_number(self, iid: str, field: _Field, key: str) -> None:
        value, error = parse_optional_float(field.edit.text())
        field.show_error(error)
        if not error:
            self._commit_if(iid, field, key, value)


def _first_line(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if callable(errors):
        msgs = [str(e.get("msg", "")).removeprefix("Value error, ") for e in errors()]
        return "; ".join(m for m in msgs if m) or strings.INVALID_VALUE
    return str(exc)


# ---- problems and to-do --------------------------------------------------------------------------


MAX_CARDS = 25
GROUP_LIST = 8  # findings named on a grouped card


def _list_timer(parent: QWidget, slot: Callable[[], None]) -> QTimer:
    timer = QTimer(parent)
    timer.setSingleShot(True)
    timer.setInterval(LIST_DELAY_MS)
    timer.timeout.connect(slot)
    return timer


class ProblemsPanel(QScrollArea):
    showRequested = Signal(str)  # object id
    waiveRequested = Signal(object)  # Finding

    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("problems")
        self.setAccessibleName(strings.PROBLEMS)
        self.lay = scroll_body(self)
        self._dirty = True
        self._signature: object = None
        self._later = _list_timer(self, self._refresh_if_dirty)
        ctl.changed.connect(lambda _d: self._invalidate())
        ctl.stateChanged.connect(self._invalidate)
        ctl.drcChanged.connect(self._invalidate)
        ctl.drcStateChanged.connect(self._invalidate)
        self.refresh()

    def _invalidate(self) -> None:
        self._dirty = True
        if not self.isVisible():
            return
        if self.ctl.findings_are_many():
            self._later.start()  # after the canvas is redrawn, once per burst of changes
        else:
            self.refresh()

    def _refresh_if_dirty(self) -> None:
        if self._dirty and self.isVisible():
            self.refresh()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def counts(self) -> tuple[int, int]:
        return self.ctl.severity_counts()

    def refresh(self) -> None:
        self._dirty = False
        checking = not self.ctl.drc_current
        findings = self.ctl.findings()
        open_ = self.ctl.open_findings()
        cards, total = self._cards(open_)
        waived = (
            [f for f in findings if f.waiver is not None] if len(findings) != len(open_) else []
        )
        # What would be on screen. When an edit leaves it unchanged (a rename, a move), the widgets
        # stay: rebuilding the cards and laying them out cost 150 to 300 ms after every edit.
        signature = (
            tuple(identity for identity, _ in cards),
            total,
            tuple((f.id, f.waiver.justification if f.waiver else "") for f in waived),
            self.ctl.read_only,
            checking,
        )
        if signature == self._signature:
            return
        self._signature = signature
        clear_layout(self.lay)
        state = muted(strings.DRC_CHECKING if checking else strings.DRC_DONE.format(len(drc.RULES)))
        state.setObjectName("drc-state")
        self.lay.addWidget(state)
        if not open_ and not checking:
            self.lay.addWidget(muted(strings.NO_PROBLEMS))
        for _, build in cards:
            self.lay.addWidget(build())
        if total > MAX_CARDS:
            self.lay.addWidget(muted(strings.MORE_PROBLEMS.format(total - MAX_CARDS)))
        if waived:
            self.lay.addWidget(heading(strings.WAIVED))
            for f in waived:
                if f.waiver is not None:
                    self.lay.addWidget(muted(f"✓ {f.id}: “{f.waiver.justification}”"))
        self.lay.addStretch(1)

    def _cards(
        self, open_: list[checks.Finding]
    ) -> tuple[list[tuple[object, Callable[[], QFrame]]], int]:
        """Builders for the first MAX_CARDS cards and the total number of cards. One card per
        finding, except that three or more unwaivable findings of one rule about the same object
        (a wire missing for each signal of an interface) share a single card. Counted in one
        cheap pass and built on demand: a project can have tens of thousands of findings."""
        Key = tuple[str, str, str, str | None]
        key: Key | None

        def key_of(f: checks.Finding) -> Key:
            return (f.rule, f.severity, f.object_id.partition(".")[0], f.fix_label)

        counts: dict[Key, int] = {}
        firsts: dict[Key, list[checks.Finding]] = {}
        waivable = 0
        for f in open_:
            if f.can_waive:
                waivable += 1
                continue
            key = key_of(f)
            n = counts.get(key, 0)
            counts[key] = n + 1
            if n < GROUP_LIST:
                firsts.setdefault(key, []).append(f)
        total = waivable + sum(1 if n >= 3 else n for n in counts.values())
        done: set[Key] = set()
        cards: list[tuple[object, Callable[[], QFrame]]] = []
        for f in open_:
            if len(cards) >= MAX_CARDS:
                break
            key = None if f.can_waive else key_of(f)
            if key is not None and counts[key] >= 3:
                if key not in done:
                    done.add(key)
                    cards.append(
                        (
                            ("group", key, counts[key], firsts[key][0].id),
                            partial(self._group_card, firsts[key], counts[key]),
                        )
                    )
                continue
            cards.append((("finding", f.id, f.title, f.severity), partial(self._card, f)))
        return cards, total

    def _group_card(self, fs: list[checks.Finding], count: int) -> QFrame:
        first = fs[0]
        card = self._card(first)
        card.setObjectName(f"finding-group-{first.id}")
        title = card.findChild(QLabel)
        if title is not None:
            sev = {
                "warning": strings.SEV_WARNING,
                "error": strings.SEV_ERROR,
                "info": strings.SEV_INFO,
            }[first.severity]
            head = first.object_id.split(".")[0]
            title.setText(f"<b>{sev} {strings.GROUPED_PROBLEMS.format(head, count)}</b>")
        lay = card.layout()
        if isinstance(lay, QVBoxLayout):
            listing = muted(
                "\n".join(f"• {f.title}" for f in fs[:GROUP_LIST])
                + (f"\n… and {count - GROUP_LIST} more" if count > GROUP_LIST else "")
            )
            lay.insertWidget(1, listing)
        return card

    def _card(self, f: checks.Finding) -> QFrame:
        card = QFrame()
        card.setProperty("card", True)
        card.setProperty("severity", f.severity)
        card.setObjectName(f"finding-{f.id}")
        lay = QVBoxLayout(card)
        sev = {
            "warning": strings.SEV_WARNING,
            "error": strings.SEV_ERROR,
            "info": strings.SEV_INFO,
        }[f.severity]
        title = QLabel(f"<b>{sev} {f.title}</b>")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
        lay.addWidget(title)
        lay.addWidget(muted(f.why))
        if f.sources:  # the requirement the rule serves, as text so it can be read and searched
            ref = QLabel(strings.REQUIREMENT_LABEL.format(", ".join(f.sources)))
            ref.setObjectName("finding-requirement")
            ref.setAccessibleName(ref.text())
            ref.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            ref.setWordWrap(True)
            lay.addWidget(ref)
        row = QHBoxLayout()
        show = QPushButton(strings.SHOW)
        show.clicked.connect(lambda: self.showRequested.emit(f.object_id))
        row.addWidget(show)
        if f.fix_label:
            fix = QPushButton(f.fix_label)
            fix.setObjectName("fix")
            fix.setProperty("primary", True)
            fix.setEnabled(not self.ctl.read_only)
            fix.clicked.connect(lambda: self.ctl.apply_fix(f))
            row.addWidget(fix)
        if f.can_waive:
            waive = QPushButton(strings.WAIVE)
            waive.setObjectName("waive")
            waive.setEnabled(not self.ctl.read_only)
            waive.clicked.connect(lambda: self.waiveRequested.emit(f))
            row.addWidget(waive)
        row.addStretch(1)
        lay.addLayout(row)
        return card


class TodoPanel(QScrollArea):
    activated = Signal(str, str)  # kind, target

    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("todo")
        self.setAccessibleName(strings.TODO)
        self.lay = scroll_body(self)
        self._dirty = True
        self._later = _list_timer(self, self._refresh_if_dirty)
        ctl.changed.connect(lambda _d: self._invalidate())
        ctl.drcChanged.connect(self._invalidate)
        self.refresh()

    def _invalidate(self) -> None:
        self._dirty = True
        if not self.isVisible():
            return
        if self.ctl.findings_are_many():
            self._later.start()  # after the canvas is redrawn, once per burst of changes
        else:
            self.refresh()

    def _refresh_if_dirty(self) -> None:
        if self._dirty and self.isVisible():
            self.refresh()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def items(self) -> list[checks.Todo]:
        return self.ctl.todos()

    def refresh(self) -> None:
        self._dirty = False
        clear_layout(self.lay)
        items = self.items()
        if not items:
            self.lay.addWidget(muted(strings.ALL_DONE))
        for k, t in enumerate(items):
            b = QPushButton(f"☐ {t.text}")
            b.setObjectName(f"todo-{k}")
            b.setStyleSheet("text-align: left;")
            b.clicked.connect(lambda _=False, x=t: self.activated.emit(x.kind, x.target))
            self.lay.addWidget(b)
        self.lay.addStretch(1)


# ---- interface table -----------------------------------------------------------------------------

COLUMNS = ["ID", "Name", "Type", "From", "To", "Chain", "Max A", "Requirement"]
EDITABLE = {1, 5, 6, 7}


class InterfaceModel(QAbstractTableModel):
    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self.ids: list[str] = []
        self.reload()

    def reload(self) -> bool:
        """Follow the project. Returns True when the rows changed (a reset); the same rows only get
        new values, which keeps column widths and selection and is much cheaper with many rows."""
        ids = sorted(self.ctl.project.interfaces)
        if ids == self.ids and ids:
            self.dataChanged.emit(self.index(0, 0), self.index(len(ids) - 1, len(COLUMNS) - 1))
            return False
        self.beginResetModel()
        self.ids = ids
        self.endResetModel()
        return True

    def rowCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self.ids)

    def columnCount(self, parent: QModelIndex | QPersistentModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return COLUMNS[section]
        return None

    def flags(self, index: QModelIndex | QPersistentModelIndex) -> Qt.ItemFlag:
        f = super().flags(index)
        if index.column() in EDITABLE and not self.ctl.read_only:
            f |= Qt.ItemFlag.ItemIsEditable
        return f

    def search_text(self, row: int) -> str:
        i = self.ctl.project.interfaces.get(self.ids[row])
        if i is None:
            return ""
        t = self.ctl.project.interface_types.get(i.type_id)
        parts = [i.id, i.name, i.type_id, t.name if t else "", i.requirement_id or "", i.redundancy]
        parts += [e.unit_id for e in i.endpoints]
        return " ".join(parts).lower()

    def _end(self, i: InterfaceInstance, k: int) -> str:
        e = i.endpoints[k]
        name = e.unit_id
        if self.ctl.mode == "expert" and e.connector_id:
            c = self.ctl.project.connectors.get(e.connector_id)
            name += f".{c.name}" if c else ""
        return name + (" (auto)" if e.auto else "")

    def data(
        self, index: QModelIndex | QPersistentModelIndex, role: int = Qt.ItemDataRole.DisplayRole
    ) -> object:
        if not index.isValid() or index.row() >= len(self.ids):
            return None
        i = self.ctl.project.interfaces.get(self.ids[index.row()])
        if i is None:
            return None
        col = index.column()
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            t = self.ctl.project.interface_types.get(i.type_id)
            return [
                i.id, i.name, t.name if t else i.type_id, self._end(i, 0), self._end(i, 1), i.redundancy,
                "" if i.max_current_a is None else f"{i.max_current_a:g}", i.requirement_id or "",
            ][col]  # fmt: skip
        if role == Qt.ItemDataRole.AccessibleTextRole:
            return f"{COLUMNS[col]} of {i.id}: {self.data(index, Qt.ItemDataRole.DisplayRole)}"
        return None

    def setData(
        self,
        index: QModelIndex | QPersistentModelIndex,
        value: object,
        role: int = Qt.ItemDataRole.EditRole,
    ) -> bool:
        if role != Qt.ItemDataRole.EditRole or index.column() not in EDITABLE:
            return False
        iid = self.ids[index.row()]
        text = str(value).strip()
        col = index.column()
        if col == 1:
            return self.ctl.update_interface(iid, name=text)
        if col == 5:
            return self.ctl.update_interface(iid, redundancy=text)
        if col == 6:
            num, err = parse_optional_float(text)
            if err:
                self.ctl.message.emit(err, False)
                return False
            return self.ctl.update_interface(iid, max_current_a=num)
        return self.ctl.update_interface(iid, requirement_id=text or None)


class _RowFilter(QSortFilterProxyModel):
    """Match every word typed against the ID, name, type (name and ID), units and requirement."""

    def filterAcceptsRow(
        self, source_row: int, source_parent: QModelIndex | QPersistentModelIndex
    ) -> bool:
        model = self.sourceModel()
        words = self.filterRegularExpression().pattern().lower().split()
        if not words or not isinstance(model, InterfaceModel):
            return True
        return all(w in model.search_text(source_row) for w in words)


class _ChainDelegate(QStyledItemDelegate):
    def createEditor(
        self, parent: QWidget, option: object, index: QModelIndex | QPersistentModelIndex
    ) -> QWidget:
        cb = QComboBox(parent)
        cb.addItems(["nominal", "redundant", "none"])
        return cb

    def setEditorData(self, editor: QWidget, index: QModelIndex | QPersistentModelIndex) -> None:
        editor.setCurrentText(str(index.data(Qt.ItemDataRole.EditRole)))  # type: ignore[attr-defined]

    def setModelData(
        self, editor: QWidget, model: object, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)  # type: ignore[attr-defined]


class InterfaceTable(QWidget):
    newInterfaceRequested = Signal()

    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("interface-table")
        self.scale_factor = 1.0
        lay = QVBoxLayout(self)
        top = QHBoxLayout()
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(strings.FILTER_PLACEHOLDER)
        self.filter.setAccessibleName(strings.FILTER_PLACEHOLDER)
        self.filter.setClearButtonEnabled(True)
        self.add_btn = QPushButton(strings.NEW_INTERFACE)
        self.add_btn.setObjectName("new-interface")
        self.add_btn.clicked.connect(self.newInterfaceRequested)
        top.addWidget(self.filter, 1)
        top.addWidget(self.add_btn)
        lay.addLayout(top)
        self.model = InterfaceModel(ctl)
        self.proxy = _RowFilter()
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(-1)
        self.view = QTableView()
        self.view.setObjectName("interfaces")
        self.view.setAccessibleName(strings.INTERFACE_TABLE)
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.sortByColumn(0, Qt.SortOrder.AscendingOrder)  # IF-001 first
        self.view.setAlternatingRowColors(True)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setItemDelegateForColumn(5, _ChainDelegate(self.view))
        header = self.view.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self._apply_widths()
        self.view.verticalHeader().hide()
        lay.addWidget(self.view)
        self.filter.textChanged.connect(self._set_filter)
        self.view.selectionModel().selectionChanged.connect(self._row_selected)
        ctl.changed.connect(self._changed)
        ctl.modeChanged.connect(self._mode_changed)
        ctl.selectionChanged.connect(self._sync_if_visible)
        ctl.stateChanged.connect(lambda: self.add_btn.setEnabled(not ctl.read_only))
        self._busy = False
        self._dirty = False

    def _mode_changed(self) -> None:
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def _set_filter(self, text: str) -> None:
        import re

        self.proxy.setFilterRegularExpression(re.escape(text.strip()) if text.strip() else "")

    def _changed(self, delta: Delta) -> None:
        if delta.full or delta.interfaces or delta.units:
            self._dirty = True
            if self.isVisible():
                self.refresh()

    def _apply_widths(self) -> None:
        for col, width in enumerate((120, 260, 150, 130, 130, 100, 70)):
            self.view.setColumnWidth(col, self.ctl_scale(width))

    def ctl_scale(self, px: int) -> int:
        return round(px * self.scale_factor)

    def refresh(self) -> None:
        self._dirty = False
        if self.model.reload():  # a model reset restores default column widths
            self._apply_widths()
            self._sync_selection()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def _row_selected(self) -> None:
        if self._busy:
            return
        rows = self.view.selectionModel().selectedRows()
        if rows:
            iid = self.proxy.data(rows[0], Qt.ItemDataRole.DisplayRole)
            self._busy = True
            self.ctl.select("interface", str(iid))
            self._busy = False

    def _sync_if_visible(self) -> None:
        if self.isVisible():
            self._sync_selection()

    def _sync_selection(self) -> None:
        if self._busy:
            return
        s = self.ctl.selection
        self._busy = True
        self.view.clearSelection()
        if s is not None and s.kind == "interface" and s.id in self.model.ids:
            src = self.model.index(self.model.ids.index(s.id), 0)
            idx = self.proxy.mapFromSource(src)
            if idx.isValid():
                self.view.selectRow(idx.row())
        self._busy = False


class HarnessPanel(QWidget):
    """Generated harnesses: status, independent check, harness list, wires and why they are so."""

    exportRequested = Signal()
    changeRequested = Signal(str, str)  # action, harness ID

    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("harness-plans")
        self._dirty = True
        lay = QVBoxLayout(self)
        self.status = QLabel()
        self.status.setObjectName("plans-status")
        self.status.setWordWrap(True)
        self.verify = QLabel()
        self.verify.setObjectName("plans-verify")
        self.verify.setWordWrap(True)
        lay.addWidget(self.status)
        lay.addWidget(self.verify)
        out_row = QHBoxLayout()
        self.outputs = QLabel()
        self.outputs.setObjectName("plans-outputs")
        self.outputs.setWordWrap(True)
        self.export_btn = QPushButton(strings.EXPORT)
        self.export_btn.setObjectName("export")
        self.export_btn.setToolTip(strings.EXPORT_TIP)
        self.export_btn.clicked.connect(self.exportRequested)
        out_row.addWidget(self.outputs, 1)
        out_row.addWidget(self.export_btn)
        lay.addLayout(out_row)
        cc_row = QHBoxLayout()
        self.cc_buttons: dict[str, QPushButton] = {}
        for action, text, tip in (
            ("review", strings.REVIEW, strings.REVIEW_TIP),
            ("release", strings.RELEASE, strings.RELEASE_TIP),
            ("revise", strings.NEW_REV, strings.NEW_REV_TIP),
            ("changes", strings.CHANGES, strings.CHANGES_TIP),
            ("history", strings.HISTORY, strings.HISTORY_TIP),
            ("delete", strings.DELETE_HARNESS, strings.DELETE_HARNESS_TIP),
        ):
            b = QPushButton(text)
            b.setObjectName(f"plans-{action}")
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=action: self._request(a))
            cc_row.addWidget(b)
            self.cc_buttons[action] = b
        cc_row.addStretch(1)
        lay.addLayout(cc_row)
        self.empty = muted(strings.NO_PLANS_BODY)
        self.empty.setObjectName("plans-empty")
        lay.addWidget(self.empty)
        self.harnesses = QTableWidget(0, len(strings.PLANS_COLUMNS))
        self.harnesses.setObjectName("plans-harnesses")
        self.harnesses.setHorizontalHeaderLabels(strings.PLANS_COLUMNS)
        self.wires = QTableWidget(0, len(strings.WIRE_COLUMNS))
        self.wires.setObjectName("plans-wires")
        self.wires.setHorizontalHeaderLabels(strings.WIRE_COLUMNS)
        self.wires.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )  # every column, the Colour one too, stays in view
        self.harnesses.setAccessibleName(strings.HARNESS_LIST)
        self.wires.setAccessibleName(strings.WIRE_LIST)
        for t in (self.harnesses, self.wires):
            t.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            t.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            t.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
            t.verticalHeader().setVisible(False)
            t.horizontalHeader().setStretchLastSection(True)
        self.explain = QLabel()
        self.explain.setObjectName("plans-explain")
        self.explain.setWordWrap(True)
        self.explain.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body = QHBoxLayout()
        body.addWidget(self.harnesses, 3)
        body.addWidget(self.wires, 4)
        self.side = QTabWidget()
        self.side.setObjectName("plans-side")
        self.side.setAccessibleName(strings.TAB_DRAWING)
        why = QScrollArea()
        why.setWidgetResizable(True)
        why.setWidget(self.explain)
        why.setAccessibleName(strings.EXPLAIN)
        self.preview = DrawingPreview()
        self.side.addTab(self.preview, strings.TAB_DRAWING)
        self.side.addTab(why, strings.TAB_WHY)
        self.side.currentChanged.connect(lambda _i: self._update_preview())
        body.addWidget(self.side, 5)
        lay.addLayout(body, 1)
        self.harnesses.itemSelectionChanged.connect(self._show_wires)
        self.harnesses.itemSelectionChanged.connect(self._update_cc_buttons)
        self.harnesses.itemSelectionChanged.connect(self._update_preview)
        self.wires.itemSelectionChanged.connect(self._show_explain)
        ctl.changed.connect(lambda _d: self._invalidate())
        self.refresh()

    def _invalidate(self) -> None:
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def _request(self, action: str) -> None:
        hid = self.selected_harness()
        if hid:
            self.changeRequested.emit(action, hid)

    def _update_cc_buttons(self) -> None:
        p = self.ctl.project
        h = p.harnesses.get(self.selected_harness() or "")
        ro = self.ctl.read_only
        status = h.status if h else ""
        has_base = bool(h) and any(b.harness_id == h.id for b in p.baselines.values())  # type: ignore[union-attr]
        on = {
            "review": status == "draft",
            "release": status in ("draft", "in_review"),
            "revise": status == "released",
            "changes": has_base,
            "history": h is not None,
            "delete": status in ("draft", "in_review"),
        }
        for action, b in self.cc_buttons.items():
            b.setEnabled(on[action] and (action in ("changes", "history") or not ro))

    def select_harness(self, harness_id: str) -> None:
        if self._dirty:
            self.refresh()
        for r in range(self.harnesses.rowCount()):
            item = self.harnesses.item(r, 0)
            if item and item.text() == harness_id:
                self.harnesses.selectRow(r)
                return

    def selected_harness(self) -> str | None:
        rows = self.harnesses.selectionModel().selectedRows()
        item = self.harnesses.item(rows[0].row(), 0) if rows else None
        return item.text() if item else None

    def refresh(self) -> None:
        self._dirty = False
        p = self.ctl.project
        status = self.ctl.generation_status()
        self.status.setText(strings.GEN_STATUS[status])
        self.status.setProperty("state", status)
        report = verify_project(p) if p.harnesses else None
        if report is None:
            self.verify.setText("")
        else:
            fmt = strings.PLANS_VERIFY_OK if report.ok else strings.PLANS_VERIFY_BAD
            self.verify.setText(fmt.format(report.summary()))
        self.empty.setVisible(not p.harnesses)
        self.outputs.setText(strings.OUT_STATUS[self.ctl.outputs_state()] if p.harnesses else "")
        self.export_btn.setEnabled(bool(p.harnesses))
        self.export_btn.setVisible(bool(p.harnesses))
        keep = self.selected_harness()
        self.harnesses.setRowCount(len(p.harnesses))
        for r, hid in enumerate(sorted(p.harnesses)):
            h = p.harnesses[hid]
            cells = [hid, h.name, str(len(h.wires)), str(len(h.interfaces)),
                     f"{h.revision} {strings.RELEASED_LOCKED}" if h.status == "released" else f"{h.revision} {h.status.replace('_', ' ')}",
                     "generated" if h.generated else "by hand"]  # fmt: skip
            for c, text in enumerate(cells):
                self.harnesses.setItem(r, c, QTableWidgetItem(text))
            if hid == keep:
                self.harnesses.selectRow(r)
        self._show_wires()
        self._update_cc_buttons()
        self._update_preview()

    @staticmethod
    def _colour_text(colour: str | None) -> str:
        """ "red (RD)" for a colour the table knows, the text as typed otherwise, "" if unset."""
        if not colour:
            return ""
        name = name_of(colour)
        return f"{name} ({resolve(colour)[0]})" if name else colour

    def _show_wires(self) -> None:
        p = self.ctl.project
        h = p.harnesses.get(self.selected_harness() or "")
        wires = h.wires if h else []
        self.wires.setRowCount(len(wires))
        for r, w in enumerate(wires):
            cells = [w.id, w.signal or "", f"{w.from_connector}.{w.from_pin}",
                     f"{w.to_connector}.{w.to_pin}",
                     "pending" if w.gauge_awg is None else str(w.gauge_awg),
                     "" if w.length_m is None else f"{w.length_m:g}",
                     self._colour_text(w.colour),
                     "yes" if w.locked else ""]  # fmt: skip
            for c, text in enumerate(cells):
                self.wires.setItem(r, c, QTableWidgetItem(text))
        self._show_explain()

    def _update_preview(self) -> None:
        """The drawing is rebuilt only while its tab is showing (selection or design changed)."""
        if self.side.currentWidget() is not self.preview or not self.isVisible():
            return
        p = self.ctl.project
        h = p.harnesses.get(self.selected_harness() or "")
        self.preview.show_harness(p if h else None, h)

    def _show_explain(self) -> None:
        p = self.ctl.project
        h = p.harnesses.get(self.selected_harness() or "")
        rows = self.wires.selectionModel().selectedRows()
        item = self.wires.item(rows[0].row(), 0) if rows else None
        if h is None:
            self.explain.setText("")
            return
        wire = next((w for w in h.wires if item and w.id == item.text()), None)
        lines = explain_wire(p, h, wire) if wire else explain_harness(p, h)
        title = f"<b>{strings.EXPLAIN}</b>"
        self.explain.setText(
            title + "<br>" + ("<br>".join(lines) if lines else strings.EXPLAIN_NONE)
        )


class OutlinePanel(QWidget):
    """The diagram as a tree: every unit with the interfaces it takes part in. Plain Qt tree, so
    screen readers read it item by item (the canvas itself is one object to them)."""

    def __init__(self, ctl: EditorController) -> None:
        super().__init__()
        self.ctl = ctl
        self.setObjectName("outline")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tree = QTreeWidget()
        self.tree.setObjectName("outline-tree")
        self.tree.setHeaderHidden(True)
        self.tree.setAccessibleName(strings.OUTLINE)
        self.tree.setAccessibleDescription(strings.OUTLINE_HELP)
        lay.addWidget(self.tree)
        self._dirty = True
        self._syncing = False
        ctl.changed.connect(lambda _d: self._invalidate())
        ctl.selectionChanged.connect(self._select_current)
        self.tree.itemSelectionChanged.connect(self._picked)
        self.refresh()

    def _invalidate(self) -> None:
        self._dirty = True
        if self.isVisible():
            self.refresh()

    def showEvent(self, event: object) -> None:
        super().showEvent(event)  # type: ignore[arg-type]
        if self._dirty:
            self.refresh()

    def refresh(self) -> None:
        self._dirty = False
        p = self.ctl.project
        self._syncing = True
        self.tree.clear()
        for uid in sorted(p.units):
            u = p.units[uid]
            node = QTreeWidgetItem(
                [
                    f"{uid}: {u.name} ({u.side})"
                    if u.side != "none" and u.side not in u.name  # "(redundant)" may be in the name
                    else f"{uid}: {u.name}"
                ]
            )
            node.setData(0, Qt.ItemDataRole.UserRole, ("unit", uid))
            for i in sorted(
                (i for i in p.interfaces.values() if any(e.unit_id == uid for e in i.endpoints)),
                key=lambda x: x.id,
            ):
                other = next((e.unit_id for e in i.endpoints if e.unit_id != uid), "?")
                t = p.interface_types.get(i.type_id)
                child = QTreeWidgetItem([f"{i.id}: {t.name if t else i.type_id} to {other}"])
                child.setData(0, Qt.ItemDataRole.UserRole, ("interface", i.id))
                node.addChild(child)
            self.tree.addTopLevelItem(node)
        self._syncing = False
        self._select_current()

    def _picked(self) -> None:
        if self._syncing:
            return
        items = self.tree.selectedItems()
        if items:
            kind, ident = items[0].data(0, Qt.ItemDataRole.UserRole)
            self.ctl.select(kind, ident)

    def _select_current(self) -> None:
        sel = self.ctl.selection
        if sel is None or not self.isVisible():
            return
        self._syncing = True
        self.tree.clearSelection()
        for k in range(self.tree.topLevelItemCount()):
            node = self.tree.topLevelItem(k)
            if node is None:
                continue
            for item in (node, *(node.child(c) for c in range(node.childCount()))):
                if item is not None and item.data(0, Qt.ItemDataRole.UserRole) == (
                    sel.kind,
                    sel.id,
                ):
                    item.setSelected(True)
                    self.tree.scrollToItem(item)
                    self._syncing = False
                    return
        self._syncing = False
