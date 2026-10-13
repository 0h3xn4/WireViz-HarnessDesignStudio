"""The table of a generation preview: what Generate will do to each harness.

    GeneratePlanTable(theme, settings=None)
    table.set_plan(plan, project)

One row per harness the plan names: new, changed, unchanged or removed (a released harness is left
alone and says so), with the locked pins that stay where you put them. Built from
`GenerationPlan.report`; the core cannot scope a generation to one harness, so there is no
per-harness regenerate here.
"""

from typing import Any

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from harness_design_studio.core.generate.engine import GenerationPlan
from harness_design_studio.core.model import Harness, Project
from harness_design_studio.gui import strings
from harness_design_studio.gui.tables import Column, DictTableModel, TableView, natural_key
from harness_design_studio.gui.theme import ThemeManager

# change key -> (state chip key, word); "unchanged" has no chip: nothing is going to happen
CHANGES: dict[str, tuple[str | None, str]] = {
    "new": ("info", strings.GP_NEW),
    "changed": ("warning", strings.GP_CHANGED),
    "unchanged": (None, strings.GP_UNCHANGED),
    "removed": ("warning", strings.GP_REMOVED),
    "frozen": ("released", strings.GP_FROZEN),
}
_ORDER = {"new": 0, "changed": 1, "removed": 2, "frozen": 3, "unchanged": 4}


def plan_rows(plan: GenerationPlan, project: Project | None = None) -> list[dict[str, Any]]:
    """The rows of the table: harness, name, change and the locked pins kept, from the plan's
    report. A harness the plan adds is found in `plan.harnesses`, one it removes or keeps in
    `project`."""
    rep = plan.report
    known: dict[str, Harness] = dict(project.harnesses) if project else {}
    known.update(plan.harnesses)
    boxes: dict[str, set[str]] = {}
    for hid, h in known.items():
        boxes[hid] = {c.mates_with for c in h.connectors if c.mates_with}
    kept = [k.rpartition(".")[0] for k in rep.kept_locks]  # "BOX.pin" -> "BOX"
    rows: list[dict[str, Any]] = []
    for change, ids in (
        ("new", rep.added),
        ("changed", rep.changed),
        ("unchanged", rep.unchanged),
        ("removed", rep.removed),
        ("frozen", rep.frozen),
    ):
        state, word = CHANGES[change]
        for hid in ids:
            h = known.get(hid)
            n = sum(1 for box in kept if box in boxes.get(hid, ()))
            rows.append(
                {
                    "harness": hid,
                    "name": h.name if h else "",
                    "change": word,
                    "change_key": change,
                    "change_state": state,
                    "change_why": strings.GP_TIPS[change],
                    "locked": n,
                }
            )
    rows.sort(key=lambda r: (_ORDER[r["change_key"]], natural_key(r["harness"])))
    return rows


COLUMNS = [
    Column("harness", strings.GP_HARNESS, mono=True, width=96),
    Column("name", strings.GP_NAME, width=200),
    Column("change", strings.GP_CHANGE, state="change_state", tooltip="change_why", width=140),
    Column("locked", strings.GP_LOCKED, numeric=True, width=140),
]


class GeneratePlanTable(QWidget):
    """The harness / change / locked pins table of a `GenerationPlan` (read-only, sortable,
    Ctrl+C copies it as tab-separated text)."""

    def __init__(self, theme: ThemeManager, settings: QSettings | None = None) -> None:
        super().__init__()
        self.setObjectName("generate-plan-table")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.model = DictTableModel(COLUMNS, (), theme)
        self.view = TableView(
            self.model, theme, name=strings.GP_TABLE, settings=settings, key="generate-plan"
        )
        self.view.setObjectName("generate-plan")
        lay.addWidget(self.view, 1)
        self.note = QLabel()
        self.note.setObjectName("generate-plan-note")
        self.note.setWordWrap(True)
        self.note.setProperty("muted", True)
        lay.addWidget(self.note)

    def set_plan(self, plan: GenerationPlan, project: Project | None = None) -> None:
        rows = plan_rows(plan, project)
        self.model.set_rows(rows)
        attributed = sum(r["locked"] for r in rows)
        elsewhere = len(plan.report.kept_locks) - attributed
        if not rows:
            self.note.setText(strings.GP_NONE)
        elif elsewhere > 0:
            self.note.setText(strings.GP_LOCKS_ELSEWHERE.format(elsewhere))
        else:
            self.note.setText("")
