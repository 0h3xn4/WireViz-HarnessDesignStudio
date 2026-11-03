# mypy: disable-error-code="no-untyped-def,no-untyped-call"
"""D2 (D-193): the editor shows the cross-section in mm² beside every AWG gauge, and writes none.

The wire and pin tables of the harness view, the lists panel (the written table keeps the plain
gauge), the gauge field of the Edit wire tab, the findings of the Checks panel and the Why lines.
Offscreen."""

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtCore import Qt  # noqa: E402

from harness_design_studio.core.checks import Finding  # noqa: E402
from harness_design_studio.core.units import area_text, gauge_short  # noqa: E402
from harness_design_studio.gui import strings  # noqa: E402
from harness_design_studio.gui.checks_panel import object_row  # noqa: E402
from harness_design_studio.gui.states import STATE_ROLE  # noqa: E402
from tests.test_ux_harness import make_view, theme  # noqa: E402, F401, F811
from tests.test_ux_lists import make_panel  # noqa: E402


def test_the_wire_and_pin_tables_show_the_area_and_sort_by_the_gauge(qtbot, theme) -> None:  # noqa: F811
    _ctl, view = make_view(qtbot, theme)
    for table, model in ((view.wire_table, view.wire_model), (view.pin_table, view.pin_model)):
        col = model.column_index("gauge")
        seen = 0
        for r, row in enumerate(model.rows()):
            gauge = row["gauge"]
            cell = model.index(r, col)
            if isinstance(gauge, int):
                assert cell.data() == gauge_short(gauge) and "mm²" in cell.data()
                assert model.sort_value(r, col) == float(gauge)  # sorts as the number
                seen += 1
            elif gauge == strings.HV_PENDING:
                assert cell.data() == strings.HV_PENDING and cell.data(STATE_ROLE) == "pending"
        assert seen, table
    assert view.wire_model.headerData(4, Qt.Orientation.Horizontal) == "Gauge (AWG)"


def test_the_copied_cells_carry_the_area_too(qtbot, theme) -> None:  # noqa: F811
    _ctl, view = make_view(qtbot, theme)
    view.wire_table.selectAll()
    text = view.wire_table.copy_selection(headers=True)
    assert "(0.205 mm²)" in text or "(0.326 mm²)" in text or "mm²)" in text


def test_the_lists_show_the_area_and_the_written_table_does_not(qtbot, theme) -> None:  # noqa: F811
    ctl, panel = make_panel(qtbot, theme)
    view = panel.view("wirelist")
    m = view.model()
    col = next(c for c in range(m.columnCount()) if m.headerData(c, Qt.Orientation.Horizontal) == "AWG")  # fmt: skip
    cells = [m.index(r, col).data(Qt.ItemDataRole.DisplayRole) for r in range(m.rowCount())]
    numbers = [c for c in cells if c and c[0].isdigit()]
    assert numbers and all(c.endswith(" mm²)") for c in numbers)
    assert any(c == strings.HV_PENDING or c.startswith("pending") for c in cells) or len(numbers) == len(cells)  # fmt: skip
    # the file the panel exports is the table: the plain gauge
    data = panel.table_bytes("csv", "wirelist").decode()
    assert "mm²" not in data
    assert panel.table_bytes("csv", "wirelist") == panel.table_bytes("csv", "wirelist")
    del ctl


def test_the_gauge_field_of_the_edit_wire_tab_shows_the_area(qtbot, theme) -> None:  # noqa: F811
    _ctl, view = make_view(qtbot, theme)
    ed = view.wire_editor
    wires = [r["id"] for r in view.wire_model.rows() if isinstance(r["gauge"], int)]
    row = next(i for i, r in enumerate(view._wire_data) if r["id"] == wires[0])
    from tests.test_ui_wire_editor import select_rows

    select_rows(view, row)
    n = int(ed.gauge.text())
    assert ed.gauge_area.text() == strings.WIRE_GAUGE_AREA.format(area_text(n))
    assert ed.gauge_area.text().endswith(" mm²")
    ed.gauge.setText("24")
    assert ed.gauge_area.text() == "0.205 mm²"
    for text in ("", "abc", "41", "-1", " "):
        ed.gauge.setText(text)
        assert ed.gauge_area.text() == "", text
    ed.gauge.setText("0")
    assert ed.gauge_area.text() == "53.5 mm²"
    # the value that is applied is the typed number, not the text with the area
    ed.gauge.setText("22")
    assert ed.gauge.text() == "22"


def test_a_finding_that_names_a_gauge_shows_its_area_on_screen() -> None:
    f = Finding(
        "current-over-wire.W001-001",
        "current-over-wire",
        "error",
        "W001-001",
        "Wire W001-001 (AWG 24) carries 2 A but allows 1.08 A after derating",
        "why",
    )
    row = object_row(f)
    assert "(AWG 24 (0.205 mm²))" in row["message"]
    assert f.title == "Wire W001-001 (AWG 24) carries 2 A but allows 1.08 A after derating"  # the finding itself is not changed  # fmt: skip
