"""The Home area, a page of its own (Settings is in `settings_page.py`).

    home = HomePage(theme, new=..., open_=..., example=..., sample=...)
    home.show_project(name, path, summary)

It only shows and calls back; the window does the work. Home is the first screen of a project:
what is open and how to start another.
"""

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from harness_design_studio.gui import strings
from harness_design_studio.gui.recent import RecentEntry
from harness_design_studio.gui.shell import ElidedLabel
from harness_design_studio.gui.states import StateChip
from harness_design_studio.gui.theme import ThemeManager, mark_mono


def _example_infos() -> tuple:  # type: ignore[type-arg]
    """The packaged examples (`core.templates.TEMPLATES`) except the empty project."""
    from harness_design_studio.core import templates

    return tuple(t for t in templates.TEMPLATES if t.name != "blank")


def _page(theme: ThemeManager, name: str, title: str) -> tuple[QScrollArea, QVBoxLayout]:
    """A scrolling page with a title and a column that is never wider than a readable line."""
    scroll = QScrollArea()
    scroll.setObjectName(name)
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setAccessibleName(title)
    body = QWidget()
    outer = QHBoxLayout(body)
    column = QVBoxLayout()
    column.setSpacing(theme.space(16))
    outer.setContentsMargins(theme.space(24), theme.space(24), theme.space(24), theme.space(24))
    outer.addLayout(column, 1)
    outer.addStretch(1)
    heading = QLabel(title)
    heading.setProperty("title", True)
    heading.setAccessibleName(title)
    column.addWidget(heading)
    scroll.setWidget(body)
    body.setMaximumWidth(theme.px(900))
    return scroll, column


def _card(theme: ThemeManager, heading: str) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setProperty("card", True)
    lay = QVBoxLayout(card)
    lay.setContentsMargins(theme.space(16), theme.space(12), theme.space(16), theme.space(16))
    lay.setSpacing(theme.space(8))
    label = QLabel(heading)
    label.setProperty("heading", True)
    lay.addWidget(label)
    return card, lay


class HomePage(QScrollArea):
    def __init__(
        self,
        theme: ThemeManager,
        *,
        new: Callable[[], None],
        open_: Callable[[], None],
        example: Callable[[], None],
        sample: Callable[[], None],
        library: Callable[[], None] = lambda: None,
        open_recent: Callable[[str], None] | None = None,
        forget_recent: Callable[[str], None] | None = None,
        open_example: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self.theme = theme
        self._open_recent = open_recent or (lambda _p: None)
        self._forget_recent = forget_recent or (lambda _p: None)
        page, column = _page(theme, "home-page", strings.HOME_TITLE)
        self.setObjectName("home-page")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWidget(page.takeWidget())
        self.setAccessibleName(strings.HOME_TITLE)
        card, lay = _card(theme, strings.HOME_PROJECT)
        self.name = ElidedLabel()
        self.name.setProperty("title", True)
        self.name.setObjectName("home-name")
        self.name.setAccessibleName(strings.HOME_PROJECT)
        self.path = ElidedLabel()
        self.path.setObjectName("home-path")
        mark_mono(self.path)
        self.path.setProperty("muted", True)
        self.summary = QLabel()
        self.summary.setObjectName("home-summary")
        self.summary.setProperty("muted", True)
        for w in (self.name, self.path, self.summary):
            lay.addWidget(w)
        column.addWidget(card)
        start, start_lay = _card(theme, strings.HOME_ACTIONS)
        row = QHBoxLayout()
        self.buttons: dict[str, QPushButton] = {}
        for key, text, callback in (
            ("new", strings.HOME_NEW, new),
            ("open", strings.HOME_OPEN, open_),
            ("example", strings.HOME_EXAMPLE, example),
            ("sample", strings.HOME_SAMPLE, sample),
            ("library", strings.HOME_LIBRARY, library),
        ):
            b = QPushButton(text)
            b.setObjectName(f"home-{key}")
            b.setAccessibleName(text.rstrip("…"))
            if key == "library":
                b.setToolTip(strings.HOME_LIBRARY_TIP)
            b.clicked.connect(lambda _c=False, cb=callback: cb())
            row.addWidget(b)
            self.buttons[key] = b
        row.addStretch(1)
        start_lay.addLayout(row)
        column.addWidget(start)
        # recent projects: a card each, filled by `set_recent`
        self.recent_card, self.recent_lay = _card(theme, strings.HOME_RECENT)
        self.recent_empty = QLabel(strings.HOME_RECENT_NONE)
        self.recent_empty.setProperty("muted", True)
        self.recent_empty.setWordWrap(True)
        self.recent_lay.addWidget(self.recent_empty)
        self.recent_rows: list[QWidget] = []
        column.addWidget(self.recent_card)
        # the packaged examples, with a one-click way into the flatsat
        ex, ex_lay = _card(theme, strings.HOME_EXAMPLES)
        self.example_buttons: dict[str, QPushButton] = {}
        for info in _example_infos():
            line = QHBoxLayout()
            col = QVBoxLayout()
            title = QLabel(info.title)
            title.setProperty("title", False)
            blurb = QLabel(info.summary)
            blurb.setWordWrap(True)
            blurb.setProperty("muted", True)
            col.addWidget(title)
            col.addWidget(blurb)
            line.addLayout(col, 1)
            b = QPushButton(
                strings.HOME_EXAMPLE_FLATSAT
                if info.name == "flatsat"
                else strings.HOME_EXAMPLE_OPEN
            )
            b.setObjectName(f"home-example-{info.name}")
            b.setAccessibleName(f"{strings.HOME_EXAMPLE_OPEN}: {info.title}")
            if info.name == "flatsat":
                b.setProperty("primary", True)
                b.setToolTip(strings.HOME_EXAMPLE_FLATSAT_TIP)
            if open_example is not None:
                b.clicked.connect(lambda _c=False, n=info.name: open_example(n))
            line.addWidget(b, 0, Qt.AlignmentFlag.AlignTop)
            ex_lay.addLayout(line)
            self.example_buttons[info.name] = b
        column.addWidget(ex)
        column.addStretch(1)

    def set_recent(self, entries: Sequence[RecentEntry], *, exists: Callable[[str], bool]) -> None:
        """One card per recent project (the folder must still exist to be opened)."""
        for w in self.recent_rows:
            self.recent_lay.removeWidget(w)
            w.deleteLater()
        self.recent_rows = []
        self.recent_empty.setVisible(not entries)
        for e in entries:
            card = QWidget()
            card.setObjectName("home-recent")
            lay = QHBoxLayout(card)
            lay.setContentsMargins(0, self.theme.space(4), 0, self.theme.space(4))
            col = QVBoxLayout()
            title = QLabel(e.name or e.path)
            title.setProperty("title", True)
            path = ElidedLabel(e.path)
            mark_mono(path)
            path.setProperty("muted", True)
            counts = QLabel(strings.HOME_COUNTS.format(e.units, e.interfaces, e.harnesses))
            counts.setProperty("muted", True)
            col.addWidget(title)
            col.addWidget(path)
            chips = QHBoxLayout()
            chips.addWidget(counts)
            for state, n, text in (
                ("draft", e.draft, strings.HOME_DRAFT),
                ("in-review", e.in_review, strings.HOME_IN_REVIEW),
                ("released", e.released, strings.HOME_RELEASED),
            ):
                if n:
                    chip = StateChip(self.theme)
                    chip.set_state(state, str(n))
                    chip.setToolTip(text.format(n))
                    chips.addWidget(chip)
            chips.addStretch(1)
            col.addLayout(chips)
            lay.addLayout(col, 1)
            present = exists(e.path)
            open_btn = QPushButton(strings.HOME_OPEN_BTN)
            open_btn.setObjectName("home-recent-open")
            open_btn.setAccessibleName(f"{strings.HOME_OPEN_BTN} {e.name or e.path}")
            open_btn.setEnabled(present)
            if not present:
                open_btn.setToolTip(strings.HOME_MISSING.format(e.path))
            open_btn.clicked.connect(lambda _c=False, p=e.path: self._open_recent(p))
            drop = QPushButton(strings.HOME_REMOVE)
            drop.setObjectName("home-recent-remove")
            drop.setProperty("ghost", True)
            drop.setAccessibleName(f"{strings.HOME_REMOVE}: {e.name or e.path}")
            drop.clicked.connect(lambda _c=False, p=e.path: self._forget_recent(p))
            lay.addWidget(open_btn, 0, Qt.AlignmentFlag.AlignTop)
            lay.addWidget(drop, 0, Qt.AlignmentFlag.AlignTop)
            self.recent_lay.addWidget(card)
            self.recent_rows.append(card)

    def show_project(self, name: str, path: str, summary: str) -> None:
        self.name.set_full_text(name)
        self.path.set_full_text(path or strings.HOME_NO_PROJECT)
        self.summary.setText(summary)
