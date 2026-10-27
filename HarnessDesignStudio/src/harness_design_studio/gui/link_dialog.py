"""The Link connectors window, and the question before a harness is made from a connection.

A connection joins a connector of one device to a connector of another, pin by pin (M2 of the
workshop feedback). The window proposes the pairs from the signal names on the pins
(`core.links.propose_pairs`, never from their position), shows them as a table (the pin and signal
of the first connector beside the pin and signal of the second), and lets the person change any
pair, add or remove pairs and give a pin its role (Power, Return, Ground, Signal, Shield, Spare).
What looks wrong is written under the table while typing (`core.links.check_link` on a copy of the
project with the changes, never a message box); OK stays off only when the connection cannot be
made at all. The window collects values; `MainWindow` runs them through the controller as one undo
step. The same window edits the pairs of a connection that exists (the connectors are then fixed).

    dlg = LinkDialog(parent, theme, project, a_unit="OBC", b_unit="RW1")
    dlg.pairs(), dlg.roles(), dlg.name()
    CreateHarnessDialog(parent, theme, harness_preview(project, "L1"))
"""

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.core import devices, edit
from harness_design_studio.core.commands import Op, Put, apply_ops
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.errors import HarnessError
from harness_design_studio.core.links import (
    Proposal,
    check_link,
    effective_role,
    link_caption,
    natural_key,
    plan_add_link,
    plan_create_harness,
    plan_set_pairs,
    plan_set_roles,
    propose_pairs,
)
from harness_design_studio.core.model import Connector, Pin, Project
from harness_design_studio.core.pairing import pair_by_number, parse_pairing
from harness_design_studio.gui import strings
from harness_design_studio.gui.connector_picker import ConnectorPicker
from harness_design_studio.gui.notice import InlineNotice, Severity
from harness_design_studio.gui.tables import Column, DictTableModel, TableView
from harness_design_studio.gui.theme import ThemeManager

ROLES: tuple[str, ...] = ("", "power", "return", "ground", "signal", "shield", "spare")


def harness_preview(project: Project, link_id: str) -> str:
    """One plain sentence on what "Create harness" will add (raises `EditError` with the reason
    when it cannot be made)."""
    ops, hid = plan_create_harness(project, link_id)
    harness = next(o.obj for o in ops if isinstance(o, Put) and o.collection == "harnesses")
    link = project.links[link_id]
    return strings.LINK_HARNESS_PREVIEW.format(
        name=harness.name,  # type: ignore[attr-defined]
        connectors=len(harness.connectors),  # type: ignore[attr-defined]
        wires=len(harness.wires),  # type: ignore[attr-defined]
        caption=link_caption(link),
    )


def _buttons(dialog: QDialog, ok_text: str) -> tuple[QPushButton, QHBoxLayout]:
    row = QHBoxLayout()
    row.addStretch(1)
    cancel = QPushButton(strings.CANCEL)
    cancel.setObjectName("dlg-cancel")
    cancel.clicked.connect(dialog.reject)
    ok = QPushButton(ok_text)
    ok.setObjectName("dlg-ok")
    ok.setProperty("primary", True)
    ok.setAutoDefault(True)
    ok.setDefault(True)
    ok.clicked.connect(dialog.accept)
    row.addWidget(cancel)
    row.addWidget(ok)
    return ok, row


class CreateHarnessDialog(QDialog):
    """Says what Create harness will add and asks once. Nothing is made before OK."""

    def __init__(self, parent: QWidget | None, theme: ThemeManager, sentence: str) -> None:
        super().__init__(parent)
        self.setObjectName("link-harness-dialog")
        self.setWindowTitle(strings.LINK_HARNESS_TITLE)
        self.setAccessibleName(strings.LINK_HARNESS_TITLE)
        lay = QVBoxLayout(self)
        self.text = QLabel(sentence)
        self.text.setObjectName("link-harness-text")
        self.text.setWordWrap(True)
        lay.addWidget(self.text)
        note = QLabel(strings.LINK_HARNESS_NOTE)
        note.setProperty("muted", True)
        note.setWordWrap(True)
        lay.addWidget(note)
        self.ok, row = _buttons(self, strings.LINK_HARNESS_OK)
        self.ok.setToolTip(strings.LINK_HARNESS_OK_TIP)
        self.ok.setAccessibleName(strings.LINK_HARNESS_OK)
        lay.addLayout(row)


class AddConnectorDialog(QDialog):
    """Add a connector to a device from the connection window: the kind (family, pins, gender)
    and, when wanted, a name. Nothing is added to the project before the connection is saved."""

    def __init__(
        self, parent: QWidget | None, theme: ThemeManager, project: Project, unit_id: str
    ) -> None:
        super().__init__(parent)
        self.project, self.unit_id = project, unit_id
        self.setObjectName("link-add-connector-dialog")
        self.setWindowTitle(strings.LINK_ADDCONN_TITLE)
        self.setAccessibleName(strings.LINK_ADDCONN_TITLE)
        lay = QVBoxLayout(self)
        intro = QLabel(strings.LINK_ADDCONN_INTRO.format(unit_id))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.picker = ConnectorPicker(project)
        lay.addWidget(self.picker)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("link-add-connector-name")
        self.name_edit.setAccessibleName(strings.LINK_ADDCONN_NAME)
        self.name_edit.setToolTip(strings.LINK_ADDCONN_NAME_TIP)
        self.name_edit.setPlaceholderText(devices.next_connector_name(project, unit_id)[1])
        form.addRow(strings.LINK_ADDCONN_NAME, self.name_edit)
        lay.addLayout(form)
        self.notice = InlineNotice(theme)
        lay.addWidget(self.notice)
        self.ok, row = _buttons(self, strings.LINK_ADDCONN_OK)
        lay.addLayout(row)
        self.picker.changed.connect(self._check)
        self.name_edit.textChanged.connect(lambda _t: self._check())
        self._check()

    def plan(self) -> tuple[list[Op], str]:
        """The operations that add the connector and its ID (raises `EditError` with the reason)."""
        return devices.ops_add_connector(
            self.project,
            self.unit_id,
            part_id=self.picker.part_id(),
            name=self.name_edit.text().strip() or None,
        )

    def _check(self) -> None:
        problem = ""
        if not self.picker.available() or not self.picker.part_id():
            problem = strings.LINK_ADDCONN_NO_PART
        else:
            try:
                self.plan()
            except (EditError, HarnessError, ValueError) as exc:
                problem = str(exc)
        if problem:
            self.notice.show_notice("error", problem)
        else:
            self.notice.clear()
        self.ok.setEnabled(not problem)


class PastePairingDialog(QDialog):
    """A pairing pasted from a table (two columns). Only the text is asked for here; the window
    turns it into a proposal and the person accepts it there."""

    def __init__(self, parent: QWidget | None, theme: ThemeManager, a_id: str, b_id: str) -> None:
        super().__init__(parent)
        self.setObjectName("link-paste-dialog")
        self.setWindowTitle(strings.LINK_PASTE_TITLE)
        self.setAccessibleName(strings.LINK_PASTE_TITLE)
        self.setMinimumWidth(theme.px(420))
        lay = QVBoxLayout(self)
        intro = QLabel(strings.LINK_PASTE_INTRO.format(a_id, b_id))
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.text = QPlainTextEdit()
        self.text.setObjectName("link-paste-text")
        self.text.setAccessibleName(strings.LINK_PASTE_NAME)
        self.text.setToolTip(strings.LINK_PASTE_TIP)
        self.text.setPlaceholderText(strings.LINK_PASTE_HINT)
        lay.addWidget(self.text, 1)
        clip = QGuiApplication.clipboard().text() if QGuiApplication.clipboard() else ""
        if "\t" in clip:  # a table copied from a spreadsheet is already here
            self.text.setPlainText(clip)
        self.ok, row = _buttons(self, strings.LINK_PASTE_OK)
        lay.addLayout(row)
        self.text.textChanged.connect(lambda: self.ok.setEnabled(bool(self.text.toPlainText().strip())))  # fmt: skip
        self.ok.setEnabled(bool(self.text.toPlainText().strip()))

    def pasted(self) -> str:
        return self.text.toPlainText()


def _device_label(project: Project, uid: str) -> str:
    u = project.units[uid]
    return f"{uid}  {u.name}" if u.name and u.name != uid else uid


class LinkDialog(QDialog):
    """Link connectors: two connectors, the pairs between their pins, the role of a pin."""

    add_a_connector: QPushButton
    add_b_connector: QPushButton

    def __init__(
        self,
        parent: QWidget | None,
        theme: ThemeManager,
        project: Project,
        *,
        a_unit: str = "",
        a_connector: str = "",
        b_unit: str = "",
        b_connector: str = "",
        link_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.theme, self.project, self.link_id = theme, project, link_id
        self.setObjectName("link-dialog")
        title = strings.LINK_EDIT_TITLE if link_id else strings.LINK_TITLE
        self.setWindowTitle(title)
        self.setAccessibleName(title)
        self.setMinimumWidth(theme.px(760))
        self._pairs: list[tuple[str, str]] = []
        self._roles: dict[tuple[str, str], str] = {}
        self._proposal: Proposal | None = None
        self._offer: Proposal | None = None  # a proposal shown and not yet accepted
        self._offer_how = ""
        self._loading = False
        # connectors added in this window: they are made when the connection is saved
        self.extra_ops: list[Op] = []
        self.ask_connector: Callable[[str], tuple[list[Op], str] | None] = self._ask_connector
        self.ask_paste: Callable[[], str | None] = self._ask_paste
        lay = QVBoxLayout(self)
        intro = QLabel(strings.LINK_EDIT_INTRO if link_id else strings.LINK_INTRO)
        intro.setWordWrap(True)
        intro.setProperty("muted", True)
        lay.addWidget(intro)
        # the name
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("link-name")
        self.name_edit.setAccessibleName(strings.LINK_NAME)
        self.name_edit.setToolTip(strings.LINK_NAME_TIP)
        self.name_edit.setPlaceholderText(strings.LINK_NAME_HINT)
        form.addRow(strings.LINK_NAME, self.name_edit)
        lay.addLayout(form)
        # the two ends
        ends = QHBoxLayout()
        self.a_device, self.a_conn = self._end(strings.LINK_FIRST, "a", ends)
        arrow = QLabel("↔")
        arrow.setAccessibleName(strings.LINK_JOINED)
        ends.addWidget(arrow, 0, Qt.AlignmentFlag.AlignBottom)
        self.b_device, self.b_conn = self._end(strings.LINK_SECOND, "b", ends)
        lay.addLayout(ends)
        # the table
        self.model = DictTableModel(
            [
                Column("a_pin", strings.LINK_COL_PIN_A, mono=True, width=70),
                Column("a_signal", strings.LINK_COL_SIGNAL_A, width=110),
                Column("a_role", strings.LINK_COL_ROLE_A, width=90),
                Column("b_pin", strings.LINK_COL_PIN_B, mono=True, width=70),
                Column("b_signal", strings.LINK_COL_SIGNAL_B, width=110),
                Column("b_role", strings.LINK_COL_ROLE_B, width=90),
            ],
            (),
            theme,
        )
        self.table = TableView(self.model, theme, name=strings.LINK_TABLE_NAME)
        self.table.setObjectName("link-pairs")
        self.table.setSortingEnabled(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setMinimumHeight(theme.px(150))
        lay.addWidget(self.table, 1)
        self.empty = QLabel(strings.LINK_NO_PAIRS_YET)
        self.empty.setObjectName("link-pairs-empty")
        self.empty.setProperty("muted", True)
        lay.addWidget(self.empty)
        # one pair at a time: the pins and their roles
        edit_row = QHBoxLayout()
        self.a_pin = self._combo("link-a-pin", strings.LINK_PIN_A, strings.LINK_PIN_TIP)
        self.a_role = self._combo("link-a-role", strings.LINK_ROLE_A, strings.LINK_ROLE_TIP)
        self.b_pin = self._combo("link-b-pin", strings.LINK_PIN_B, strings.LINK_PIN_TIP)
        self.b_role = self._combo("link-b-role", strings.LINK_ROLE_B, strings.LINK_ROLE_TIP)
        for role in (self.a_role, self.b_role):
            for key in ROLES:
                role.addItem(strings.LINK_ROLE_NAMES[key], key)
        for label, box in (
            (strings.LINK_COL_PIN_A, self.a_pin),
            (strings.LINK_COL_ROLE_A, self.a_role),
            (strings.LINK_COL_PIN_B, self.b_pin),
            (strings.LINK_COL_ROLE_B, self.b_role),
        ):
            edit_row.addWidget(QLabel(label))
            edit_row.addWidget(box, 1)
        lay.addLayout(edit_row)
        buttons = QHBoxLayout()
        self.add_pair = self._button("link-add-pair", strings.LINK_ADD_PAIR, strings.LINK_ADD_TIP)
        self.change_pair = self._button(
            "link-change-pair", strings.LINK_CHANGE_PAIR, strings.LINK_CHANGE_TIP
        )
        self.remove_pair = self._button(
            "link-remove-pair", strings.LINK_REMOVE_PAIR, strings.LINK_REMOVE_TIP
        )
        self.pair_numbers = self._button(
            "link-pair-by-number", strings.LINK_BY_NUMBER, strings.LINK_BY_NUMBER_TIP
        )
        self.paste_pairs = self._button(
            "link-paste-pairs", strings.LINK_PASTE, strings.LINK_PASTE_BUTTON_TIP
        )
        for b in (self.add_pair, self.change_pair, self.remove_pair):
            buttons.addWidget(b)
        buttons.addStretch(1)
        buttons.addWidget(self.pair_numbers)
        buttons.addWidget(self.paste_pairs)
        lay.addLayout(buttons)
        lay.addWidget(self._build_offer(theme))
        help_ = QLabel(strings.LINK_ROLE_HELP)
        help_.setObjectName("link-role-help")
        help_.setWordWrap(True)
        help_.setProperty("muted", True)
        lay.addWidget(help_)
        # what is left over, what the proposal did not pair, what the review says
        self.unpaired = QLabel()
        self.unpaired.setObjectName("link-unpaired")
        self.unpaired.setWordWrap(True)
        lay.addWidget(self.unpaired)
        self.notes = QLabel()
        self.notes.setObjectName("link-notes")
        self.notes.setWordWrap(True)
        self.notes.setProperty("muted", True)
        lay.addWidget(self.notes)
        self.problem = InlineNotice(theme)  # why the connection cannot be made (OK stays off)
        self.problem.setObjectName("link-problem")
        self.review = InlineNotice(theme)  # what looks wrong (OK stays on)
        self.review.setObjectName("link-review")
        lay.addWidget(self.problem)
        lay.addWidget(self.review)
        self.ok, row = _buttons(self, strings.LINK_SAVE if link_id else strings.LINK_OK)
        self.ok.setAccessibleName(strings.LINK_SAVE if link_id else strings.LINK_OK)
        self.ok.setToolTip(strings.LINK_OK_TIP)
        lay.addLayout(row)
        self._fill_devices()
        self._preset(a_unit, a_connector, b_unit, b_connector)
        self._wire()
        self._ends_changed()

    def _build_offer(self, theme: ThemeManager) -> QFrame:
        """The proposal of Pair by pin number or Paste a pairing: the pairs, what was left out, and
        two buttons. Nothing joins the table before Accept."""
        box = QFrame()
        box.setObjectName("link-offer")
        box.setProperty("card", True)
        lay = QVBoxLayout(box)
        self.offer_title = QLabel()
        self.offer_title.setObjectName("link-offer-title")
        self.offer_title.setWordWrap(True)
        lay.addWidget(self.offer_title)
        self.offer_model = DictTableModel(
            [
                Column("a_pin", strings.LINK_COL_PIN_A, mono=True, width=70),
                Column("a_signal", strings.LINK_COL_SIGNAL_A, width=110),
                Column("b_pin", strings.LINK_COL_PIN_B, mono=True, width=70),
                Column("b_signal", strings.LINK_COL_SIGNAL_B, width=110),
            ],
            (),
            theme,
        )
        self.offer_table = TableView(self.offer_model, theme, name=strings.LINK_OFFER_TABLE)
        self.offer_table.setObjectName("link-offer-pairs")
        self.offer_table.setSortingEnabled(False)
        self.offer_table.setMaximumHeight(theme.px(130))
        lay.addWidget(self.offer_table)
        self.offer_notes = QLabel()
        self.offer_notes.setObjectName("link-offer-notes")
        self.offer_notes.setWordWrap(True)
        self.offer_notes.setProperty("muted", True)
        lay.addWidget(self.offer_notes)
        row = QHBoxLayout()
        row.addStretch(1)
        self.offer_discard = self._button(
            "link-offer-discard", strings.LINK_OFFER_DISCARD, strings.LINK_OFFER_DISCARD_TIP
        )
        self.offer_accept = self._button(
            "link-offer-accept", strings.LINK_OFFER_ACCEPT, strings.LINK_OFFER_ACCEPT_TIP
        )
        self.offer_accept.setProperty("primary", True)
        row.addWidget(self.offer_discard)
        row.addWidget(self.offer_accept)
        lay.addLayout(row)
        self.offer_discard.clicked.connect(lambda _c=False: self._set_offer(None))
        self.offer_accept.clicked.connect(lambda _c=False: self.accept_offer())
        self.offer_box = box
        box.hide()
        return box

    # ---- building ---------------------------------------------------------------------------
    def _end(self, title: str, key: str, row: QHBoxLayout) -> tuple[QComboBox, QComboBox]:
        col = QVBoxLayout()
        head = QLabel(title)
        head.setProperty("muted", True)
        device = self._combo(
            f"link-{key}-device", f"{title}: {strings.LINK_DEVICE}", strings.LINK_DEVICE_TIP
        )
        conn = self._combo(
            f"link-{key}-connector",
            f"{title}: {strings.LINK_CONNECTOR}",
            strings.LINK_CONNECTOR_TIP,
        )
        add = self._button(
            f"link-{key}-add-connector", strings.LINK_ADDCONN, strings.LINK_ADDCONN_TIP
        )
        add.clicked.connect(lambda _c=False, k=key: self._add_connector(k))
        setattr(self, f"add_{key}_connector", add)
        for w in (head, device, conn, add):
            col.addWidget(w)
        row.addLayout(col, 1)
        return device, conn

    @staticmethod
    def _combo(name: str, accessible: str, tip: str) -> QComboBox:
        box = QComboBox()
        box.setObjectName(name)
        box.setAccessibleName(accessible)
        box.setToolTip(tip)
        return box

    @staticmethod
    def _button(name: str, text: str, tip: str) -> QPushButton:
        b = QPushButton(text)
        b.setObjectName(name)
        b.setAccessibleName(text)
        b.setToolTip(tip)
        return b

    def _fill_devices(self) -> None:
        for box in (self.a_device, self.b_device):
            for uid in sorted(self.project.units, key=natural_key):
                box.addItem(_device_label(self.project, uid), uid)

    def _preset(self, a_unit: str, a_conn: str, b_unit: str, b_conn: str) -> None:
        link = self.project.links.get(self.link_id or "")
        if link is not None:
            self.name_edit.setText(link.name)
            ca = self.project.connectors.get(link.a_connector)
            cb = self.project.connectors.get(link.b_connector)
            a_unit, a_conn = (ca.unit_id or "", ca.id) if ca else (a_unit, a_conn)
            b_unit, b_conn = (cb.unit_id or "", cb.id) if cb else (b_unit, b_conn)
            self._pairs = [(p.a_pin, p.b_pin) for p in link.pairs]
        if link is None and not b_unit:  # no device given: the first two, so they differ
            ids = sorted(self.project.units, key=natural_key)
            a_unit = a_unit or (ids[0] if ids else "")
            b_unit = next((u for u in ids if u != a_unit), "")
        for box, uid in ((self.a_device, a_unit), (self.b_device, b_unit)):
            k = box.findData(uid)
            if k >= 0:
                box.setCurrentIndex(k)
        if link is None and not (a_conn and b_conn):
            a_conn, b_conn = self._best_connectors(a_unit, a_conn, b_unit, b_conn)
        self._load_connectors(self.a_device, self.a_conn, a_conn)
        self._load_connectors(self.b_device, self.b_conn, b_conn)
        if link is not None:
            for w in (self.a_device, self.a_conn, self.b_device, self.b_conn):
                w.setEnabled(False)
                w.setToolTip(strings.LINK_ENDS_FIXED)
            for button in (self.add_a_connector, self.add_b_connector):
                button.setEnabled(False)
                button.setToolTip(strings.LINK_ENDS_FIXED)

    def _best_connectors(
        self, a_unit: str, a_conn: str, b_unit: str, b_conn: str
    ) -> tuple[str, str]:
        """Which connectors to start with when the person picked devices only: the two that the
        signal names pair best (the first of each when none pairs, or when a device has one)."""
        if a_unit not in self.project.units or b_unit not in self.project.units:
            return a_conn, b_conn
        ca = [c.id for c in edit.unit_connectors(self.project, a_unit) if a_conn in ("", c.id)]
        cb = [c.id for c in edit.unit_connectors(self.project, b_unit) if b_conn in ("", c.id)]
        best, found = (a_conn or (ca[0] if ca else ""), b_conn or (cb[0] if cb else "")), 0
        for x in ca:
            for y in cb:
                try:
                    n = len(propose_pairs(self.project, x, y).pairs)
                except EditError:
                    continue
                if n > found:
                    best, found = (x, y), n
        return best

    def _load_connectors(self, device: QComboBox, conn: QComboBox, wanted: str = "") -> None:
        conn.blockSignals(True)
        conn.clear()
        uid = device.currentData()
        for c in edit.unit_connectors(self.project, uid) if uid else []:
            conn.addItem(f"{c.id}  {c.name}" if c.name and c.name != c.id else c.id, c.id)
        k = conn.findData(wanted) if wanted else 0
        conn.setCurrentIndex(max(0, k))
        conn.blockSignals(False)

    def _device_changed(self, side: str) -> None:
        device, conn = (self.a_device, self.a_conn) if side == "a" else (self.b_device, self.b_conn)
        self._load_connectors(device, conn)
        self._ends_changed()

    def _wire(self) -> None:
        self.a_device.currentIndexChanged.connect(lambda _i: self._device_changed("a"))
        self.b_device.currentIndexChanged.connect(lambda _i: self._device_changed("b"))
        self.a_conn.currentIndexChanged.connect(lambda _i: self._ends_changed())
        self.b_conn.currentIndexChanged.connect(lambda _i: self._ends_changed())
        self.name_edit.textChanged.connect(lambda _t: self._revalidate())
        self.table.selectionModel().selectionChanged.connect(lambda *_a: self._row_chosen())
        self.a_pin.currentIndexChanged.connect(lambda _i: self._pin_chosen("a"))
        self.b_pin.currentIndexChanged.connect(lambda _i: self._pin_chosen("b"))
        self.a_role.currentIndexChanged.connect(lambda _i: self._role_chosen("a"))
        self.b_role.currentIndexChanged.connect(lambda _i: self._role_chosen("b"))
        self.add_pair.clicked.connect(self._add)
        self.change_pair.clicked.connect(self._change)
        self.remove_pair.clicked.connect(self._remove)
        self.pair_numbers.clicked.connect(lambda _c=False: self.offer_by_number())
        self.paste_pairs.clicked.connect(lambda _c=False: self.offer_pasted())

    # ---- the values -------------------------------------------------------------------------
    def a_connector_id(self) -> str:
        return str(self.a_conn.currentData() or "")

    def b_connector_id(self) -> str:
        return str(self.b_conn.currentData() or "")

    def pairs(self) -> list[tuple[str, str]]:
        return list(self._pairs)

    def roles(self) -> dict[tuple[str, str], str]:
        """Pins whose role the person changed: `{(connector, pin): role}`."""
        return dict(self._roles)

    def name(self) -> str:
        return self.name_edit.text().strip()

    def proposal(self) -> Proposal | None:
        return self._proposal

    def _connector(self, side: str) -> Connector | None:
        return self.project.connectors.get(
            self.a_connector_id() if side == "a" else self.b_connector_id()
        )

    def _pin(self, conn: Connector, pin_id: str) -> Pin | None:
        """The pin as it will be, with the role the person chose here."""
        pin = next((p for p in conn.pins if p.id == pin_id), None)
        if pin is not None and (conn.id, pin_id) in self._roles:
            return pin.model_copy(update={"role": self._roles[(conn.id, pin_id)]})
        return pin

    def _role_label(self, conn: Connector, pin: Pin | None) -> str:
        if pin is None:
            return ""
        return strings.LINK_ROLE_NAMES.get(effective_role(pin, self.project, conn), "")

    # ---- reacting ---------------------------------------------------------------------------
    def _ends_changed(self) -> None:
        """A connector was picked: the proposal is worked out again (a new connection) and the
        pin lists follow."""
        a, b = self._connector("a"), self._connector("b")
        self._roles = {k: v for k, v in self._roles.items() if k[0] in (self.a_connector_id(), self.b_connector_id())}  # fmt: skip
        for side, conn, box in (("a", a, self.a_pin), ("b", b, self.b_pin)):
            box.blockSignals(True)
            box.clear()
            for p in sorted(conn.pins, key=lambda p: natural_key(p.id)) if conn else []:
                box.addItem(f"{p.id}  {p.signal}" if p.signal else p.id, p.id)
            box.blockSignals(False)
            self._pin_chosen(side)
        self._proposal = None
        self._set_offer(None)
        if self.link_id is None:
            self._pairs = []
            if a is not None and b is not None:
                try:
                    self._proposal = propose_pairs(self.project, a.id, b.id)
                    self._pairs = [(p.a_pin, p.b_pin) for p in self._proposal.pairs]
                except EditError:
                    self._proposal = None
        self._refresh()

    # ---- a connector added here, a pairing proposed by number or pasted ---------------------------
    def _ask_connector(self, unit_id: str) -> tuple[list[Op], str] | None:
        dlg = AddConnectorDialog(self, self.theme, self.project, unit_id)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        return dlg.plan()

    def _add_connector(self, side: str) -> None:
        """Add a connector to the device picked on this side. It joins the project when the
        connection is saved (`extra_ops`); until then it exists in this window only."""
        device, conn = (self.a_device, self.a_conn) if side == "a" else (self.b_device, self.b_conn)
        uid = str(device.currentData() or "")
        if not uid or self.link_id:
            return
        try:
            planned = self.ask_connector(uid)
            if planned is None:
                return
            ops, cid = planned
            self.project = edit.clone_with(self.project, ops)
        except (EditError, HarnessError, ValueError) as exc:
            self.problem.show_notice("error", str(exc))
            return
        self.extra_ops += ops
        self._load_connectors(device, conn, cid)
        self._ends_changed()

    def _ask_paste(self) -> str | None:
        dlg = PastePairingDialog(
            self, self.theme, self.a_connector_id() or "?", self.b_connector_id() or "?"
        )
        return dlg.pasted() if dlg.exec() == QDialog.DialogCode.Accepted else None

    def _skipped(self) -> tuple[set[str], set[str]]:
        """The pins already in the table (a proposal never offers them again)."""
        return {p[0] for p in self._pairs}, {p[1] for p in self._pairs}

    def _ready_to_pair(self) -> bool:
        a, b = self._connector("a"), self._connector("b")
        return a is not None and b is not None and a.unit_id != b.unit_id

    def offer_by_number(self) -> Proposal | None:
        """Pair by pin number: show pin 1 to pin 1, 2 to 2 ... as a proposal. Nothing joins the
        table until Accept."""
        if not self._ready_to_pair():
            return None
        skip_a, skip_b = self._skipped()
        try:
            found = pair_by_number(
                self.project,
                self.a_connector_id(),
                self.b_connector_id(),
                skip_a=skip_a,
                skip_b=skip_b,
            )
        except (EditError, HarnessError) as exc:
            self.problem.show_notice("error", str(exc))
            return None
        self._set_offer(found, strings.LINK_OFFER_BY_NUMBER)
        return found

    def offer_pasted(self, text: str | None = None) -> Proposal | None:
        """Paste a pairing: two columns, a pin of the first connector and a pin of the second.
        `text` is what was pasted (asked for when not given)."""
        if not self._ready_to_pair():
            return None
        if text is None:
            text = self.ask_paste()
            if text is None:
                return None
        skip_a, skip_b = self._skipped()
        try:
            found = parse_pairing(
                self.project,
                self.a_connector_id(),
                self.b_connector_id(),
                text,
                skip_a=skip_a,
                skip_b=skip_b,
            )
        except (EditError, HarnessError) as exc:
            self.problem.show_notice("error", str(exc))
            return None
        self._set_offer(found, strings.LINK_OFFER_PASTED)
        return found

    def offer(self) -> Proposal | None:
        """The proposal that waits for Accept (None: there is none)."""
        return self._offer

    def _set_offer(self, found: Proposal | None, how: str = "") -> None:
        self._offer, self._offer_how = found, how
        if found is None:
            self.offer_box.hide()
            return
        a, b = self._connector("a"), self._connector("b")
        rows = []
        for a_pin, b_pin in ((p.a_pin, p.b_pin) for p in found.pairs):
            pa = self._pin(a, a_pin) if a else None
            pb = self._pin(b, b_pin) if b else None
            rows.append(
                {
                    "a_pin": a_pin,
                    "a_signal": (pa.signal if pa and pa.signal else "") or strings.LINK_NO_SIGNAL,
                    "b_pin": b_pin,
                    "b_signal": (pb.signal if pb and pb.signal else "") or strings.LINK_NO_SIGNAL,
                }
            )
        self.offer_model.set_rows(rows)
        for k, w in enumerate((100, 120, 104, 120)):
            self.offer_table.setColumnWidth(k, self.theme.px(w))
        n = len(found.pairs)
        self.offer_title.setText(
            strings.LINK_OFFER_TITLE.format(how, strings.LINK_N_PAIRS[0 if n == 1 else 1].format(n))
        )
        self.offer_notes.setText("\n".join(found.notes))
        self.offer_notes.setVisible(bool(found.notes))
        self.offer_accept.setEnabled(n > 0)
        self.offer_box.show()

    def accept_offer(self) -> None:
        """The person accepts the proposal: its pairs join the table (nothing is saved yet)."""
        found = self._offer
        if found is None:
            return
        have = set(self._pairs)
        self._pairs += [(p.a_pin, p.b_pin) for p in found.pairs if (p.a_pin, p.b_pin) not in have]
        self._set_offer(None)
        self._refresh(select=len(self._pairs) - 1)

    def _pin_chosen(self, side: str) -> None:
        conn = self._connector(side)
        pin_box, role_box = (self.a_pin, self.a_role) if side == "a" else (self.b_pin, self.b_role)
        pin = self._pin(conn, str(pin_box.currentData() or "")) if conn else None
        role_box.blockSignals(True)
        role_box.setCurrentIndex(max(0, role_box.findData(pin.role if pin else "")))
        role_box.setEnabled(pin is not None)
        role_box.blockSignals(False)

    def _role_chosen(self, side: str) -> None:
        conn = self._connector(side)
        pin_box, role_box = (self.a_pin, self.a_role) if side == "a" else (self.b_pin, self.b_role)
        pin_id = str(pin_box.currentData() or "")
        if conn is None or not pin_id:
            return
        role = str(role_box.currentData() or "")
        stored = next((p.role for p in conn.pins if p.id == pin_id), "")
        if role == stored:
            self._roles.pop((conn.id, pin_id), None)
        else:
            self._roles[(conn.id, pin_id)] = role
        self._refresh()

    def _chosen_row(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        return self.table.proxy.mapToSource(rows[0]).row() if rows else -1

    def _row_chosen(self) -> None:
        k = self._chosen_row()
        if self._loading or not 0 <= k < len(self._pairs):
            self._buttons_enabled()
            return
        a_pin, b_pin = self._pairs[k]
        for box, pin in ((self.a_pin, a_pin), (self.b_pin, b_pin)):
            box.blockSignals(True)
            box.setCurrentIndex(max(0, box.findData(pin)))
            box.blockSignals(False)
        self._pin_chosen("a")
        self._pin_chosen("b")
        self._buttons_enabled()

    def _buttons_enabled(self) -> None:
        chosen = self._chosen_row() >= 0
        self.change_pair.setEnabled(chosen)
        self.remove_pair.setEnabled(chosen)
        self.add_pair.setEnabled(bool(self.a_pin.currentData() and self.b_pin.currentData()))
        ready = self._ready_to_pair()
        self.pair_numbers.setEnabled(ready)
        self.paste_pairs.setEnabled(ready)

    def _current_pair(self) -> tuple[str, str] | None:
        a, b = self.a_pin.currentData(), self.b_pin.currentData()
        return (str(a), str(b)) if a and b else None

    def _add(self) -> None:
        pair = self._current_pair()
        if pair is not None:
            self._pairs.append(pair)
            self._refresh(select=len(self._pairs) - 1)

    def _change(self) -> None:
        k, pair = self._chosen_row(), self._current_pair()
        if pair is not None and 0 <= k < len(self._pairs):
            self._pairs[k] = pair
            self._refresh(select=k)

    def _remove(self) -> None:
        k = self._chosen_row()
        if 0 <= k < len(self._pairs):
            del self._pairs[k]
            self._refresh()

    # ---- showing ----------------------------------------------------------------------------
    def _rows(self) -> list[dict[str, str]]:
        a, b = self._connector("a"), self._connector("b")
        rows: list[dict[str, str]] = []
        for a_pin, b_pin in self._pairs:
            pa = self._pin(a, a_pin) if a else None
            pb = self._pin(b, b_pin) if b else None
            rows.append(
                {
                    "a_pin": a_pin,
                    "a_signal": (pa.signal if pa and pa.signal else "") or strings.LINK_NO_SIGNAL,
                    "a_role": self._role_label(a, pa) if a else "",
                    "b_pin": b_pin,
                    "b_signal": (pb.signal if pb and pb.signal else "") or strings.LINK_NO_SIGNAL,
                    "b_role": self._role_label(b, pb) if b else "",
                }
            )
        return rows

    def _refresh(self, select: int = -1) -> None:
        self._loading = True
        try:
            self.model.set_rows(self._rows())
            for k, w in enumerate((100, 120, 96, 104, 120, 96)):  # (the headers read in full)
                self.table.setColumnWidth(k, self.theme.px(w))
            if 0 <= select < len(self._pairs):
                self.table.selectRow(select)
        finally:
            self._loading = False
        self.empty.setVisible(not self._pairs)
        self._buttons_enabled()
        self._show_leftovers()
        self._revalidate()

    def _show_leftovers(self) -> None:
        a, b = self._connector("a"), self._connector("b")
        left: list[str] = []
        used_a = {p[0] for p in self._pairs}
        used_b = {p[1] for p in self._pairs}
        for conn, used in ((a, used_a), (b, used_b)):
            if conn is None:
                continue
            pins = []
            for p in sorted(conn.pins, key=lambda p: natural_key(p.id)):
                pin = self._pin(conn, p.id)
                if pin is None or p.id in used or not pin.signal:
                    continue
                if effective_role(pin, self.project, conn) == "spare":
                    continue
                pins.append(f"{p.id} ({pin.signal})")
            if pins:
                left.append(strings.LINK_UNPAIRED_LINE.format(conn.id, ", ".join(pins)))
        self.unpaired.setText(
            " ".join(left) if left else (strings.LINK_ALL_PAIRED if self._pairs else "")
        )
        notes = list(self._proposal.notes) if self._proposal else []
        self.notes.setText("\n".join(notes))
        self.notes.setVisible(bool(notes))

    def _plan(self) -> tuple[Project, str] | str:
        """The project as it will be (a copy) and the link's ID, or the sentence that says why the
        connection cannot be made."""
        a, b = self._connector("a"), self._connector("b")
        if a is None or b is None:
            device = self.a_device if a is None else self.b_device
            return strings.LINK_NO_CONNECTOR.format(device.currentData() or "?")
        if a.unit_id == b.unit_id:
            return strings.LINK_SAME_DEVICE.format(a.unit_id)
        if not self._pairs:
            return strings.LINK_NO_PAIRS
        ops = plan_set_roles(self.project, self._roles)
        if self.link_id:
            ops += plan_set_pairs(self.project, self.link_id, self._pairs)
            lid = self.link_id
        else:
            more, lid = plan_add_link(self.project, a.id, b.id, self._pairs, self.name())
            ops += more
        scratch = edit.clone_with(self.project, [])
        apply_ops(scratch, ops)
        return scratch, lid

    def _revalidate(self) -> None:
        if self._loading:
            return
        try:
            planned = self._plan()
        except (EditError, HarnessError, ValueError) as exc:
            planned = str(exc)
        if isinstance(planned, str):
            self.problem.show_notice("error", planned)
            self.review.clear()
            self.ok.setEnabled(False)
            return
        self.problem.clear()
        self.ok.setEnabled(True)
        scratch, lid = planned
        link = scratch.links.get(lid)
        found = check_link(scratch, link) if link is not None else []
        if not found:
            self.review.clear()
            return
        worst: Severity = "error" if any(f.severity == "error" for f in found) else "warning"
        head = strings.LINK_REVIEW_ERRORS if worst == "error" else strings.LINK_REVIEW_WARNINGS
        self.review.show_notice(worst, head, details=[f.message for f in found])

    # ---- for tests and screen readers ---------------------------------------------------------
    def rows(self) -> Sequence[dict[str, str]]:
        return self._rows()


__all__ = [
    "AddConnectorDialog",
    "CreateHarnessDialog",
    "LinkDialog",
    "PastePairingDialog",
    "harness_preview",
]
