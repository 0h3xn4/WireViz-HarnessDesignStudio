"""Dock panels: the properties form and the problems list (with its to-do lines), and the helpers other panels use."""

from collections.abc import Callable
from decimal import Decimal
from functools import partial

from PySide6.QtCore import (
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import checks, edit, why
from harness_design_studio.core.drc import by_rule
from harness_design_studio.core.library_import import describe_library
from harness_design_studio.core.model import InterfaceInstance, Part
from harness_design_studio.gui import strings
from harness_design_studio.gui.controller import LIST_DELAY_MS, Delta, EditorController
from harness_design_studio.gui.icons import icon_button
from harness_design_studio.gui.theme import ThemeManager, current_theme, mark_mono
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


# ---- properties ----------------------------------------------------------------------------------


class _Field(QWidget):
    """A labelled line edit with an inline error line (live validation)."""

    def __init__(self, label: str, value: str, *, enabled: bool = True, mono: bool = False) -> None:
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        self.label = muted(label)
        self.edit = QLineEdit(value)
        self.edit.setEnabled(enabled)
        self.edit.setAccessibleName(label)
        if mono:  # IDs and requirement IDs read in the monospace font
            mark_mono(self.edit)
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


def format_number(value: float | None) -> str:
    """The shortest text that reads back as exactly the same number, without an exponent (a field
    shows what is stored, so leaving it unchanged changes nothing)."""
    if value is None:
        return ""
    text = repr(float(value))
    if "e" in text or "E" in text:
        text = format(Decimal(text), "f")
    return text.removesuffix(".0")


def parse_optional_float(text: str) -> tuple[float | None, str]:
    text = text.strip()
    if not text:
        return None, ""
    if not text.isascii():  # float() also reads other scripts' digits (Arabic-Indic, full-width)
        return None, strings.NUMBER_HELP
    try:
        value = float(text)
    except ValueError:
        return None, strings.NUMBER_HELP
    if value != value or value in (float("inf"), float("-inf")) or value < 0:
        return None, strings.NUMBER_HELP
    return value, ""


_DIFFERENT = object()  # the selected items hold different values of a field


def _common(values: list[object]) -> object:
    """The value all items share, or _DIFFERENT."""
    first = values[0]
    return first if all(v == first for v in values) else _DIFFERENT


class PropertiesPanel(QScrollArea):
    confirmRequested = Signal(str)
    deleteRequested = Signal()  # the Delete selection button of the several-items form
    rebuilt = Signal()  # the form was built again (the inspector re-applies locks to its fields)

    def __init__(self, ctl: EditorController, theme: ThemeManager) -> None:
        super().__init__()
        self.ctl, self.theme = ctl, theme
        self.setObjectName("properties")
        self.setAccessibleName(strings.PROPERTIES)
        self.lay = scroll_body(self)
        self.body: QWidget = self.widget()  # type: ignore[assignment]
        self.fields: dict[str, QWidget] = {}
        self._touching: set[str] = set()  # the links the form shows for a selected unit
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
        if len(self.ctl.selected) > 1:
            touched = any(
                sel.id in (delta.units if sel.kind == "unit" else delta.interfaces)
                for sel in self.ctl.selected
            )
            focus = self.body.focusWidget()
            if (touched or delta.full) and not isinstance(focus, QLineEdit | QPlainTextEdit):
                self.rebuild()
            return
        if (
            (s.kind == "unit" and (s.id in delta.units or self._links_changed(s.id, delta)))
            or (s.kind == "interface" and s.id in delta.interfaces)
            or delta.full
        ):
            focus = self.body.focusWidget()
            if focus is None or not isinstance(
                focus, QLineEdit | QPlainTextEdit
            ):  # never rebuild under the cursor
                self.rebuild()

    def _links_changed(self, unit_id: str, delta: Delta) -> bool:
        """A link of this unit came, went or changed (a link that is gone can no longer be
        looked up, so the form remembers which ones it showed)."""
        if delta.interfaces & self._touching:
            return True
        interfaces = self.ctl.project.interfaces
        return any(
            iid in interfaces and any(e.unit_id == unit_id for e in interfaces[iid].endpoints)
            for iid in delta.interfaces
        )

    def rebuild(self) -> None:
        clear_layout(self.lay)
        self.fields.clear()
        s = self.ctl.selection
        p = self.ctl.project
        if len(self.ctl.selected) > 1:
            self._touching = set()
            self._multi_form()
            self.lay.addStretch(1)
            self._state()
            return
        self._touching = (
            {i.id for i in p.interfaces.values() if any(e.unit_id == s.id for e in i.endpoints)}
            if s is not None and s.kind == "unit"
            else set()
        )
        if (
            s is None
            or (s.kind == "unit" and s.id not in p.units)
            or (s.kind == "interface" and s.id not in p.interfaces)
        ):
            self.lay.addWidget(heading(strings.PROPERTIES))
            self.lay.addWidget(muted(strings.NOTHING_SELECTED))
            self.lay.addStretch(1)
            self.rebuilt.emit()
            return
        (self._unit_form if s.kind == "unit" else self._interface_form)(s.id)
        self.lay.addStretch(1)
        self._state()
        self.rebuilt.emit()

    def _kept(self, accepted: bool) -> bool:
        """After an edit: when the controller refused it (a released harness holds the object),
        show the stored values again instead of the rejected one (CV-9)."""
        if not accepted:
            self.rebuild()
        return accepted

    def _editable(self, w: QWidget) -> QWidget:
        w.setProperty("editable", True)
        return w

    # several items -----------------------------------------------------------------------------
    def _multi_form(self) -> None:
        """What the selected items have in common, editable at once (one undo step)."""
        ctl, p = self.ctl, self.ctl.project
        units = [u for u in ctl.selected_ids("unit") if u in p.units]
        links = [i for i in ctl.selected_ids("interface") if i in p.interfaces]
        self.lay.addWidget(heading(strings.MULTI_HEAD))
        if units and links:
            count = strings.MULTI_MIXED.format(len(units), len(links))
        elif units:
            count = strings.MULTI_UNITS.format(len(units))
        else:
            count = strings.MULTI_LINKS.format(len(links))
        title = QLabel(f"<b>{count}</b>")
        title.setObjectName("multi-count")
        self.lay.addWidget(title)
        ids = [*units, *links]
        shown = ", ".join(ids[:12]) + (
            f" {strings.AND_MORE.format(len(ids) - 12)}" if len(ids) > 12 else ""
        )
        listing = muted(shown)
        listing.setObjectName("multi-ids")
        self.lay.addWidget(listing)
        self.lay.addWidget(muted(strings.MULTI_HELP))
        if units:
            self.lay.addWidget(heading(strings.UNIT))
            self.lay.addWidget(muted(strings.FIELD_CHAIN))
            self._multi_choice(
                "unit-side", ["nominal", "redundant", "none"],
                _common([p.units[u].side for u in units]),
                lambda text: ctl.update_units(units, side=text),
            )  # fmt: skip
        if links:
            self.lay.addWidget(heading(strings.INTERFACE))
            self.lay.addWidget(muted(strings.FIELD_CHAIN))
            self._multi_choice(
                "if-chain", ["nominal", "redundant", "none"],
                _common([p.interfaces[i].redundancy for i in links]),
                lambda text: ctl.update_interfaces(links, redundancy=text),
            )  # fmt: skip
            for key, label in (
                ("max_current_a", strings.FIELD_MAX_A),
                ("voltage_v", strings.FIELD_VOLTAGE),
            ):
                self._multi_number(links, key, label)
            self._multi_text(links, "requirement_id", strings.FIELD_REQUIREMENT)
        delete = QPushButton(strings.MULTI_DELETE)
        delete.setObjectName("multi-delete")
        delete.setProperty("danger", True)
        delete.setToolTip(strings.DELETE_TIP)
        delete.clicked.connect(self.deleteRequested)
        self._editable(delete)
        self.lay.addWidget(delete)

    def _multi_choice(
        self, name: str, choices: list[str], common: object, apply: Callable[[str], object]
    ) -> None:
        box = QComboBox()
        box.setObjectName(name)
        box.setAccessibleName(strings.FIELD_CHAIN)
        if common is _DIFFERENT:
            box.addItem(strings.MULTI_DIFFERENT)
        box.addItems(choices)
        if common is not _DIFFERENT:
            box.setCurrentText(str(common))
        box.activated.connect(
            lambda _i: apply(box.currentText()) if box.currentText() in choices else None
        )
        self._editable(box)
        self.lay.addWidget(box)

    def _multi_text(self, links: list[str], key: str, label: str) -> None:
        p = self.ctl.project
        common = _common([getattr(p.interfaces[i], key) for i in links])
        field = _Field(label, "" if common is _DIFFERENT else str(common or ""))
        if common is _DIFFERENT:
            field.edit.setPlaceholderText(strings.MULTI_DIFFERENT)
        self._editable(field.edit)
        self.fields[f"multi-{key}"] = field.edit

        def commit() -> None:
            text = field.edit.text().strip()
            if common is _DIFFERENT and not text:
                return  # left alone: the values stay different
            if text != str(common or ""):
                self.ctl.update_interfaces(links, **{key: text or None})

        field.edit.editingFinished.connect(commit)
        self.lay.addWidget(field)

    def _multi_number(self, links: list[str], key: str, label: str) -> None:
        p = self.ctl.project
        common = _common([getattr(p.interfaces[i], key) for i in links])
        field = _Field(label, "" if common is _DIFFERENT else format_number(common))  # type: ignore[arg-type]
        if common is _DIFFERENT:
            field.edit.setPlaceholderText(strings.MULTI_DIFFERENT)
        self._editable(field.edit)
        self.fields[f"multi-{key}"] = field.edit

        def commit() -> None:
            text = field.edit.text()
            if common is _DIFFERENT and not text.strip():
                return
            value, error = parse_optional_float(text)
            field.show_error(error)
            if error:
                return
            if common is _DIFFERENT or value != common:
                self.ctl.update_interfaces(links, **{key: value})

        field.edit.editingFinished.connect(commit)
        self.lay.addWidget(field)

    # unit ---------------------------------------------------------------------------------------
    def _unit_form(self, uid: str) -> None:
        ctl, p = self.ctl, self.ctl.project
        u = p.units[uid]
        self.lay.addWidget(heading(strings.UNIT))
        f_id = _Field(strings.FIELD_ID, u.id, mono=True)
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
                self._kept(ctl.rename_unit(uid, text))

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
        side.activated.connect(lambda _i: self._kept(ctl.update_unit(uid, side=side.currentText())))
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
        self._kept(self.ctl.update_unit(uid, **{key: value}))

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
                badge.setToolTip(self._auto_tip(c.id))
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
                lambda _i, cid=c.id, cb=combo: self._kept(
                    ctl.set_connector_part(cid, cb.currentText())
                )
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
        self.lay.addWidget(_Field(strings.FIELD_ID, i.id, enabled=False, mono=True))
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
        side.activated.connect(
            lambda _i: self._kept(ctl.update_interface(iid, redundancy=side.currentText()))
        )
        self._editable(side)
        self.lay.addWidget(side)
        for key, label in (
            ("max_current_a", strings.FIELD_MAX_A),
            ("voltage_v", strings.FIELD_VOLTAGE),
        ):
            cur = getattr(i, key)
            f = _Field(label, format_number(cur))
            self._editable(f.edit)
            self.fields[key] = f.edit
            f.edit.editingFinished.connect(lambda k=key, fld=f: self._commit_number(iid, fld, k))
            self.lay.addWidget(f)
        f_req = _Field(strings.FIELD_REQUIREMENT, i.requirement_id or "", mono=True)
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
                lambda _i, cb=combo: self._kept(
                    ctl.set_endpoint_connector(i.id, k, cb.currentData())
                )
            )
            self._editable(combo)
            lay.addWidget(combo)
        if e.auto:
            badge = QLabel(strings.AUTO)
            badge.setToolTip(self._auto_tip(e.connector_id))
            lay.addWidget(badge)
        lay.addStretch(1)
        return box

    def _auto_tip(self, connector_id: str | None) -> str:
        """Why the tool chose this connector: the recorded reasons, then what is not confirmed."""
        text = why.why_text(self.ctl.project, "connector", connector_id, 2) if connector_id else ""
        return f"{strings.AUTO_TIP}\n{text}" if text else strings.AUTO_TIP

    def _commit_if(self, iid: str, field: _Field, key: str, value: object) -> None:
        if value == getattr(self.ctl.project.interfaces[iid], key):
            return
        try:
            edit.ops_update_interface(self.ctl.project, iid, **{key: value})
        except Exception as exc:
            field.show_error(_first_line(exc))
            return
        field.show_error("")
        self._kept(self.ctl.update_interface(iid, **{key: value}))

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
UNCHECKED_RULE = "unchecked-config"  # the notes of rules that could not look at everything
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
        # Notes that a rule could not run are never cut off by the card limit: hiding them is how
        # "all rules checked" used to be claimed while rules had not been looked at.
        unchecked = [f for f in open_ if f.rule == UNCHECKED_RULE]
        rest = [f for f in open_ if f.rule != UNCHECKED_RULE] if unchecked else open_
        cards, total = self._cards(rest)
        note_cards, _ = self._cards(unchecked, limit=None)
        header = self._header(checking)
        todos = self.ctl.todos()
        waived = (
            [f for f in findings if f.waiver is not None] if len(findings) != len(open_) else []
        )
        # What would be on screen. When an edit leaves it unchanged (a rename, a move), the widgets
        # stay: rebuilding the cards and laying them out cost 150 to 300 ms after every edit.
        signature = (
            tuple(identity for identity, _ in cards),
            tuple(identity for identity, _ in note_cards),
            total,
            header,
            tuple((t.text, t.kind, t.target) for t in todos),
            tuple((f.id, f.waiver.justification if f.waiver else "") for f in waived),
            self.ctl.read_only,
            checking,
            self.ctl.drc_error,
        )
        if signature == self._signature:
            return
        self._signature = signature
        clear_layout(self.lay)
        state = muted(header)
        state.setObjectName("drc-state")
        self.lay.addWidget(state)
        if todos:  # what is left to do, as short lines that jump to the object (was the To-do tab)
            todo_heading = heading(strings.TODO_HEADING.format(len(todos)))
            todo_heading.setObjectName("todo-heading")
            self.lay.addWidget(todo_heading)
            for k, t in enumerate(todos):
                b = QPushButton(f"☐ {t.text}")
                b.setObjectName(f"todo-{k}")
                b.setProperty("align", "left")  # the theme's rule left-aligns the text
                b.clicked.connect(lambda _=False, x=t: self._todo_clicked(x.kind, x.target))
                self.lay.addWidget(b)
        if not open_ and not checking:
            self.lay.addWidget(muted(strings.NO_PROBLEMS))
        for _, build in cards:
            self.lay.addWidget(build())
        if total > MAX_CARDS:
            self.lay.addWidget(muted(strings.MORE_PROBLEMS.format(total - MAX_CARDS)))
        if note_cards:
            self.lay.addWidget(heading(strings.NOT_CHECKED_HEADING))
            for _, build in note_cards:
                self.lay.addWidget(build())
        if waived:
            self.lay.addWidget(heading(strings.WAIVED))
            for f in waived:
                if f.waiver is not None:
                    self.lay.addWidget(muted(f"✓ {f.id}: “{f.waiver.justification}”"))
        self.lay.addStretch(1)

    def _todo_clicked(self, kind: str, target: str) -> None:
        """A to-do line: an object is shown on the diagram; "warnings to fix or waive" scrolls to
        the first card below."""
        if kind != "tab":
            self.showRequested.emit(target)
            return
        for card in self.findChildren(QFrame):
            if card.property("card"):
                self.ensureWidgetVisible(card)
                return

    def _header(self, checking: bool) -> str:
        """The line above the cards: what the last check did, from the result of each rule."""
        if self.ctl.drc_error is not None:
            return self.ctl.drc_error
        if checking:  # an edit is waiting for its check, or the check was cancelled
            return strings.DRC_CHECKING if self.ctl.drc_busy() else strings.DRC_STALE
        results = self.ctl.drc_rule_results()
        if not results:
            return strings.DRC_STALE
        s = by_rule.summary(results)
        unchecked = s.not_checked + s.pending
        if not s.failed and not unchecked:
            return strings.DRC_ALL_PASSED.format(total=s.total)
        return strings.DRC_DONE.format(
            total=s.total, passed=s.passed, failed=s.failed, unchecked=unchecked
        )

    def _cards(
        self, open_: list[checks.Finding], limit: int | None = MAX_CARDS
    ) -> tuple[list[tuple[object, Callable[[], QFrame]]], int]:
        """Builders for the first `limit` cards (all of them without a limit) and the total number
        of cards. One card per finding, except that three or more unwaivable findings of one rule
        about the same object (a wire missing for each signal of an interface) share a single
        card. Counted in one cheap pass and built on demand: a project can have tens of thousands
        of findings."""
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
            if limit is not None and len(cards) >= limit:
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
                + ("\n" + strings.AND_MORE.format(count - GROUP_LIST) if count > GROUP_LIST else "")
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
            mark_mono(ref)
            lay.addWidget(ref)
        row = QHBoxLayout()
        show = QPushButton(strings.SHOW)
        icon_button(show, "search", current_theme(), strings.SHOW_ON_DIAGRAM, text=strings.SHOW)
        show.clicked.connect(lambda: self.showRequested.emit(f.object_id))
        row.addWidget(show)
        if f.fix_label:
            fix = QPushButton(f.fix_label)
            fix.setObjectName("fix")  # (not primary: Generate is the one primary button)
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
