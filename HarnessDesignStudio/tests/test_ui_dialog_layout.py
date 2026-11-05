# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""REQ-GUI-23. The *Add device* window of a real display: the name field lay over the note under
it and the banner over the buttons, and the banner *A device needs a name.* showed before anything
was typed.

The cause: a top-level window may be made as small as its layout's minimum size, and that counts a
word-wrapped label as one line. At that size the layout has less height than its wrapped text
needs and squeezes the rows into each other. `gui/dialog_base.py` keeps the window's minimum
height equal to what the layout needs at its width. These tests pin the cause (the window at its
smallest size, with the banner shown and hidden, at larger fonts), the banner (shown only after a
change), and that every dialog of the program has the base. The audit itself is tested here too,
so that a sweep that finds nothing can be trusted to be able to find something.
"""

import importlib
import inspect
import pkgutil

import pytest

pytest.importorskip("PySide6")
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
)

pytestmark = pytest.mark.gui

import harness_design_studio.gui as gui_package  # noqa: E402
from harness_design_studio.core.samples import new_project  # noqa: E402
from harness_design_studio.gui.devices_dialogs import (  # noqa: E402
    NewDeviceDialog,
    QuickDeviceDialog,
)
from harness_design_studio.gui.dialog_base import Dialog, Wizard, needed_height  # noqa: E402
from harness_design_studio.gui.wrap_label import WrapLabel  # noqa: E402
from tests.layout_audit import audit  # noqa: E402
from tests.layout_cases import cases  # noqa: E402
from tests.test_ui_layout_sweep import SCENARIOS, settle, themed  # noqa: E402


def open_dialog(cls, scenario: str = "light"):
    name, scale, extra = SCENARIOS[scenario]
    dlg = cls(None, themed(name, scale, extra), new_project())
    dlg.show()
    settle()
    return dlg


def at_smallest(dlg) -> None:
    """What a window manager that opens the window small, or a person dragging an edge, does."""
    dlg.resize(1, 1)
    settle()


# ---- the Add device windows --------------------------------------------------------------------


@pytest.mark.parametrize("scenario", ["light", "font-plus-4pt", "light-150"])
@pytest.mark.parametrize("cls", [NewDeviceDialog, QuickDeviceDialog])
def test_add_device_at_its_smallest_size_has_nothing_over_anything(qtbot, cls, scenario) -> None:
    dlg = open_dialog(cls, scenario)
    qtbot.addWidget(dlg)
    assert audit(dlg) == []
    at_smallest(dlg)
    assert audit(dlg) == []
    # the smallest size is the height the wrapped note and the banner need, not one line of each
    assert dlg.height() >= needed_height(dlg) >= dlg.layout().totalMinimumSize().height()
    if cls is QuickDeviceDialog:  # (the narrow one: the layout's own minimum is 2 lines short)
        assert needed_height(dlg) > dlg.layout().totalMinimumSize().height()


@pytest.mark.parametrize("cls", [NewDeviceDialog, QuickDeviceDialog])
def test_add_device_grows_when_the_banner_appears_and_stays_whole(qtbot, cls) -> None:
    dlg = open_dialog(cls)
    qtbot.addWidget(dlg)
    before = dlg.height()
    dlg.name.setText("x")
    dlg.name.setText("")  # the person typed and took it out: the reason shows
    settle()
    assert dlg.notice.isVisibleTo(dlg) and "needs a name" in dlg.notice.text()
    assert dlg.height() > before  # the window grew by the banner
    assert audit(dlg) == []
    at_smallest(dlg)
    assert audit(dlg) == []


@pytest.mark.parametrize("cls", [NewDeviceDialog, QuickDeviceDialog])
def test_the_banner_does_not_show_before_anything_is_typed(qtbot, cls) -> None:
    dlg = open_dialog(cls)
    qtbot.addWidget(dlg)
    assert not dlg.ok.isEnabled()  # the button says it: a name is needed
    assert not dlg.notice.isVisibleTo(dlg) and dlg.notice.text() == ""
    dlg.name.setText("Star tracker")
    assert dlg.ok.isEnabled() and not dlg.notice.isVisibleTo(dlg)
    dlg.name.setText("")  # emptied again: now the banner says why the button is off
    assert not dlg.ok.isEnabled() and dlg.notice.isVisibleTo(dlg)
    dlg.name.setText("Star tracker")
    assert not dlg.notice.isVisibleTo(dlg)  # and it goes when the reason does


def test_a_window_that_gets_more_text_than_it_was_built_for_grows(qtbot) -> None:
    class Note(Dialog):
        def __init__(self) -> None:
            super().__init__()
            lay = QVBoxLayout(self)
            self.field = QLineEdit()
            self.note = QLabel("A note. " * 4)
            self.note.setWordWrap(True)
            lay.addWidget(self.field)
            lay.addWidget(self.note)

    dlg = Note()
    qtbot.addWidget(dlg)
    dlg.show()
    settle()
    assert audit(dlg) == []
    dlg.note.setText("A much longer note that needs more lines at this width. " * 6)
    settle()
    assert audit(dlg) == []
    dlg.resize(1, 1)
    settle()
    assert audit(dlg) == [] and dlg.height() >= needed_height(dlg)


def test_a_wrapped_label_in_a_split_pane_counts_all_its_lines(qtbot) -> None:
    """A splitter does not ask for height for width: the label's minimum height has to follow."""
    from PySide6.QtWidgets import QSplitter

    window = QWidget()
    split = QSplitter()
    pane = QWidget()
    lay = QVBoxLayout(pane)
    plain = QLabel("word " * 60)
    plain.setWordWrap(True)
    wrap = WrapLabel("word " * 60)
    lay.addWidget(plain)
    lay.addWidget(wrap)
    split.addWidget(pane)
    outer = QVBoxLayout(window)
    outer.addWidget(split)
    window.resize(300, 400)
    shown(qtbot, window)
    narrow = wrap.width()
    assert (
        wrap.minimumSizeHint().height()
        >= wrap.heightForWidth(narrow)
        > plain.minimumSizeHint().height()
    )


# ---- every dialog has the base ----------------------------------------------------------------------


def gui_classes() -> list[type]:
    found = []
    for mod in pkgutil.walk_packages(gui_package.__path__, "harness_design_studio.gui."):
        if ".theme" in mod.name:
            continue
        module = importlib.import_module(mod.name)
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if obj.__module__ == mod.name:
                found.append(obj)
    return found


def test_every_dialog_and_wizard_of_the_program_derives_from_the_base() -> None:
    bare = [
        f"{c.__module__}.{c.__name__}"
        for c in gui_classes()
        if (issubclass(c, QDialog) and not issubclass(c, QWizard) and not issubclass(c, Dialog))
        or (issubclass(c, QWizard) and not issubclass(c, Wizard))
    ]
    assert not bare, f"derive these from gui.dialog_base.Dialog (or Wizard): {bare}"


def test_the_sweep_has_a_case_for_every_dialog_of_the_program() -> None:
    covered = {name for case in cases() for name in case.classes}
    dialogs = {
        c.__name__
        for c in gui_classes()
        if issubclass(c, Dialog | Wizard)
        and c not in (Dialog, Wizard)
        and not c.__name__.startswith("_")
    }
    # (the base of the planner dialogs and the pages of the wizard are covered by their dialogs)
    missing = sorted(dialogs - covered - {"FilePage"})
    assert not missing, f"add these to tests/layout_cases.py: {missing}"


# ---- the audit finds what it is meant to find ---------------------------------------------------------


def shown(qtbot, widget: QWidget) -> QWidget:
    qtbot.addWidget(widget)
    widget.show()
    settle()
    return widget


def test_the_audit_sees_two_widgets_lying_over_each_other(qtbot) -> None:
    host = QWidget()
    a, b = QPushButton("first", host), QPushButton("second", host)
    host.resize(300, 200)
    a.setGeometry(10, 10, 120, 40)
    b.setGeometry(60, 20, 120, 40)
    shown(qtbot, host)
    assert [f.rule for f in audit(host)] == ["overlap"]
    b.setProperty("overlay", True)  # a widget that is meant to lie over another is not a finding
    assert audit(host) == []


def test_the_audit_sees_a_child_that_reaches_out_of_its_parent(qtbot) -> None:
    host = QWidget()
    child = QPushButton("cut off", host)
    host.resize(100, 60)
    child.setGeometry(60, 10, 100, 30)
    shown(qtbot, host)
    assert [f.rule for f in audit(host)] == ["outside"]


def test_the_audit_sees_a_wrapped_label_that_is_too_short_and_a_cut_text(qtbot) -> None:
    host = QWidget()
    wrapped = QLabel("word " * 40, host)
    wrapped.setWordWrap(True)
    wrapped.setGeometry(0, 0, 120, 20)
    cut = QLabel("a label that does not fit its width", host)
    cut.setGeometry(0, 100, 40, 20)
    host.resize(200, 200)
    shown(qtbot, host)
    rules = sorted(f.rule for f in audit(host))
    assert "wrap-clipped" in rules and "text-cut" in rules


def test_the_audit_sees_a_window_that_is_shorter_than_its_text_needs(qtbot) -> None:
    dlg = QDialog()
    lay = QVBoxLayout(dlg)
    label = QLabel("word " * 60)
    label.setWordWrap(True)
    lay.addWidget(label)
    lay.addWidget(QLineEdit())
    shown(qtbot, dlg)
    dlg.resize(1, 1)  # a plain dialog may be made as small as its layout's minimum
    settle()
    rules = {f.rule for f in audit(dlg)}
    assert "window-short" in rules, rules
    app = QApplication.instance()
    assert app is not None
