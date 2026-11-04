# mypy: disable-error-code="no-untyped-def,no-untyped-call,attr-defined,union-attr,arg-type"
"""File > Export diagram…: the system block diagram as SVG, PDF and PNG, in a place the person
chooses, without a project folder, a harness, a check or resolved placeholders. It is always
there (it does not depend on Quick mode) and writes nothing into the project."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")
pytestmark = pytest.mark.gui

from PySide6.QtGui import QImage  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from harness_design_studio.core.commands import apply_ops  # noqa: E402
from harness_design_studio.core.links import plan_add_link  # noqa: E402
from harness_design_studio.core.model import Project  # noqa: E402
from harness_design_studio.core.samples import mini3, new_project  # noqa: E402
from harness_design_studio.gui import diagram_export, strings  # noqa: E402
from tests.gui_helpers import make_window  # noqa: E402
from tests.helpers import pinout_project  # noqa: E402


def link_only() -> Project:
    p = pinout_project()
    p.harnesses.clear()
    p.interfaces.clear()
    ops, _lid = plan_add_link(p, "OBC-J01", "RW1-J02")
    apply_ops(p, ops)
    return p


def interface_only() -> Project:
    p = mini3()
    p.harnesses.clear()
    return p


def answers(win, path: Path | None) -> list[tuple[str, str, str]]:
    asked: list[tuple[str, str, str]] = []

    def ask(title: str, suggested: str, filters: str) -> str | None:
        asked.append((title, suggested, filters))
        return str(path) if path else None

    win.ask_save_path = ask
    return asked


def png_size(path: Path) -> tuple[int, int]:
    image = QImage(str(path))
    assert not image.isNull()
    return image.width(), image.height()


@pytest.mark.parametrize("make", [interface_only, link_only, mini3])
def test_the_three_files_are_written_without_a_folder_a_harness_or_a_check(qtbot, tmp_path, make):
    win = make_window(tmp_path)
    win.ctl._install(make(), None, None)  # (no project folder)
    assert win.ctl.outputs_folder() is None
    target = tmp_path / "out" / "my_diagram.svg"
    target.parent.mkdir()
    asked = answers(win, target)
    win.act_export_diagram.trigger()
    assert asked == [
        (strings.QD_TITLE, diagram_export.suggested_name(win.ctl.project), strings.QD_FILTER)
    ]
    svg, pdf, png = (target.with_suffix(s) for s in (".svg", ".pdf", ".png"))
    assert svg.read_bytes().startswith(b"<?xml") and b"OBC" in svg.read_bytes()
    assert pdf.read_bytes().startswith(b"%PDF-1.4")
    w, h = png_size(png)
    assert w > 1000 and h > 600
    assert sorted(p.name for p in target.parent.iterdir()) == [
        "my_diagram.pdf", "my_diagram.png", "my_diagram.svg",
    ]  # fmt: skip
    assert any("my_diagram.svg" in m for m in win.toasts.messages)
    assert win.ctl.outputs_folder() is None


def test_a_link_between_two_devices_is_drawn_with_its_id(qtbot, tmp_path):
    win = make_window(tmp_path)
    win.ctl._install(link_only(), None, None)
    target = tmp_path / "d.png"
    answers(win, target)
    win.export_diagram_flow()
    assert b"L1" in target.with_suffix(".svg").read_bytes()


def test_an_ending_the_person_typed_is_not_doubled(qtbot, tmp_path):
    win = make_window(tmp_path)
    win.ctl._install(mini3(), None, None)
    answers(win, tmp_path / "flat.pdf")
    win.export_diagram_flow()
    assert sorted(p.name for p in tmp_path.glob("flat*")) == ["flat.pdf", "flat.png", "flat.svg"]
    assert diagram_export.stem_of("a/v1.2") == Path("a/v1.2")  # (only the three endings go)
    assert diagram_export.stem_of("a/b.PNG") == Path("a/b")


def test_an_empty_project_says_there_is_nothing_to_draw_and_asks_nothing(qtbot, tmp_path):
    win = make_window(tmp_path)
    win.ctl._install(new_project("Empty"), None, None)
    asked = answers(win, tmp_path / "x.svg")
    win.act_export_diagram.trigger()
    QApplication.processEvents()
    assert asked == [] and list(tmp_path.glob("x.*")) == []
    assert strings.QD_NOTHING in win.toasts.messages
    assert "nothing to draw yet" in strings.QD_NOTHING.lower()


def test_cancelling_the_chooser_writes_nothing(qtbot, tmp_path):
    win = make_window(tmp_path)
    win.ctl._install(mini3(), None, None)
    answers(win, None)
    win.export_diagram_flow()
    assert list(tmp_path.glob("*.svg")) == []


def test_a_folder_that_cannot_be_written_is_explained_not_raised(qtbot, tmp_path):
    win = make_window(tmp_path)
    win.ctl._install(mini3(), None, None)
    blocker = tmp_path / "file"
    blocker.write_text("x")
    answers(win, blocker / "d.svg")  # a file where a folder should be
    win.export_diagram_flow()
    assert any("could not" in m.lower() or "folder" in m.lower() for m in win.toasts.messages[-1:])


def test_the_action_is_in_the_file_menu_and_the_palette_in_every_role(qtbot, tmp_path):
    win = make_window(tmp_path)
    file_menu = win.menuBar().actions()[0].menu()
    assert win.act_export_diagram in file_menu.actions()
    for role in ("systems", "electrical", "ait"):
        win.set_role(role)
        assert win.act_export_diagram in win.menuBar().actions()[0].menu().actions()
        assert strings.A_EXPORT_DIAGRAM.replace("&", "") in [e.label for e in win.palette_entries()]


def test_the_png_is_drawn_from_the_same_sheet_as_the_svg_and_the_pdf():
    p = mini3()
    sheet = diagram_export.diagram_sheet(p)
    files = diagram_export.diagram_files(sheet, "stamp")
    image = QImage.fromData(files[".png"])
    assert not image.isNull() and image.width() / image.height() == pytest.approx(
        sheet.width / sheet.height, rel=0.01
    )
    assert image.pixelColor(2, 2).name() == "#ffffff"  # paper
    assert any(image.pixelColor(x, y).name() != "#ffffff" for x in range(0, 800, 7) for y in range(0, 500, 7))  # fmt: skip
    assert diagram_export.diagram_files(sheet, "stamp")[".svg"] == files[".svg"]  # (deterministic)
    assert diagram_export.diagram_sheet(new_project("E")) is None


def test_the_exported_picture_is_cut_to_its_content(qtbot, tmp_path):
    import re

    win = make_window(tmp_path)
    win.ctl._install(mini3(), None, None)
    target = tmp_path / "small.svg"
    answers(win, target)
    win.export_diagram_flow()
    svg = target.read_text()
    w, h = (float(v) for v in re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups())
    assert w < 420 and h < 297  # smaller than the standard sheet
    for x, y in re.findall(r'<text x="([-\d.]+)" y="([-\d.]+)"', svg):
        assert 0 <= float(x) <= w and 0 <= float(y) <= h
    for tag in re.findall(r"<(?:line|rect)[^>]*>", svg):
        for x in re.findall(r'(?:x|x1|x2)="([-\d.]+)"', tag):
            assert float(x) <= w + 1e-6
        for y in re.findall(r'(?:y|y1|y2)="([-\d.]+)"', tag):
            assert float(y) <= h + 1e-6
    image = QImage(str(target.with_suffix(".png")))
    assert image.width() / image.height() == pytest.approx(w / h, rel=0.01) and image.width() >= 1000  # fmt: skip


def test_a_big_project_is_not_clipped_and_stays_about_the_size_it_was():
    from harness_design_studio.core.model import Unit
    from harness_design_studio.core.outputs import system
    from harness_design_studio.core.outputs.canvas import item_bounds
    from harness_design_studio.core.outputs.stamp import stamp_of
    from harness_design_studio.core.samples import sat15

    p = sat15()
    for k in range(60):  # more lanes and rows than the standard sheet holds
        uid = f"X{k}"
        p.units[uid] = Unit(id=uid, name=f"Extra {k}", subsystem="x", zone=f"lane{k % 7}")
    full = system.block_diagram(p, stamp_of(p))
    assert full.width > 420  # (a sheet that grew to hold it)
    fitted = diagram_export.diagram_sheet(p)
    assert fitted.width <= full.width and fitted.height <= full.height
    assert fitted.width > full.width - 40  # (about the same width)
    for it in fitted.items[1:]:  # (the border, first, is redrawn to match)
        x0, y0, x1, y1 = item_bounds(it)
        assert x0 >= 0 and y0 >= 0 and x1 <= fitted.width and y1 <= fitted.height
