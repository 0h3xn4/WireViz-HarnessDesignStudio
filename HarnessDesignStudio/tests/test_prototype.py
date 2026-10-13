"""REQ-UX-02: the clickable prototype really supports the main journeys (run in headless Chromium).

Skipped when Playwright or a Chromium binary is not available (unless HARNESS_REQUIRE_BROWSER is
set, as in CI: then either one missing is an error). Fails on any console error or on
any request that is not a local file (the prototype must work fully offline).
"""

import glob
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

if os.environ.get("HARNESS_REQUIRE_BROWSER"):  # CI: a missing package is an error, not a skip
    import playwright  # noqa: F401
else:
    pytest.importorskip("playwright")
from playwright.sync_api import Page, Route, sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
_ROOTS = [
    os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or "",
    "/opt/pw-browsers",
    str(Path.home() / ".cache" / "ms-playwright"),
]
CHROME = sorted(
    path
    for root in _ROOTS
    if root
    for pattern in ("chromium-*/chrome-linux/chrome", "chromium-*/chrome-linux64/chrome")
    for path in glob.glob(f"{root}/{pattern}")
)
if not CHROME and os.environ.get("HARNESS_REQUIRE_BROWSER"):  # CI sets this: no silent skipping
    raise RuntimeError("HARNESS_REQUIRE_BROWSER is set but no Chromium was found")
pytestmark = [pytest.mark.ux, pytest.mark.skipif(not CHROME, reason="no Chromium available")]
URL = (ROOT / "prototype" / "index.html").as_uri()


@pytest.fixture(scope="module")
def browser() -> Iterator[object]:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME[-1], args=["--no-sandbox"])
        yield b
        b.close()


@pytest.fixture
def page(browser) -> Iterator[Page]:  # type: ignore[no-untyped-def]
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    problems: list[str] = []
    pg.on("pageerror", lambda e: problems.append(f"pageerror: {e}"))
    pg.on("console", lambda m: problems.append(f"console: {m.text}") if m.type == "error" else None)

    def only_local(route: Route) -> None:
        if route.request.url.startswith(("file:", "data:", "about:")):
            route.continue_()
        else:
            problems.append(f"network request: {route.request.url}")
            route.abort()

    pg.route("**/*", only_local)
    pg.goto(URL + "?notour")
    yield pg
    ctx.close()
    assert not problems, problems


def open_more(pg: Page) -> None:
    """Secondary controls (scale, theme, panel toggles) live in a menu on narrower windows."""
    if pg.is_visible("#morebtn") and pg.is_hidden("#theme"):
        pg.click("#morebtn")


def state(pg: Page, expr: str) -> Any:
    return pg.evaluate(f"window.__proto.{expr}")


def connect(pg: Page, type_id: str, a: str, b: str) -> None:
    pg.click(f'[data-type="{type_id}"]')
    pg.click(f'.unit[data-u="{a}"] rect.u-rect')
    pg.click(f'.unit[data-u="{b}"] rect.u-rect')


def test_sample_loads_with_status_and_no_tour_when_disabled(page: Page) -> None:
    assert state(page, "D.units.length") == 3 and state(page, "D.ifaces.length") == 2
    assert page.is_hidden("#tour")
    page.click('[data-tab="todo"]')
    assert "not generated" in page.inner_text("#tabbody")


def test_j1_tour_can_be_skipped_and_replayed(browser) -> None:  # type: ignore[no-untyped-def]
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(URL)  # first run: the tour starts by itself
    pg.wait_for_selector("#tour", state="visible")
    assert "Step 1 of 5" in pg.inner_text("#tour")
    pg.click("#tn")
    assert "Step 2 of 5" in pg.inner_text("#tour")
    pg.click("#ts")
    assert pg.is_hidden("#tour")
    pg.click("#helpbtn")
    pg.click("#h1")
    assert "Step 1 of 5" in pg.inner_text("#tour")
    pg.close()


def test_j2_add_unit_and_empty_state(page: Page) -> None:
    page.click("#helpbtn")
    page.click("#h4")  # empty project
    assert page.is_visible("#empty") and "Add your first unit" in page.inner_text("#empty")
    page.click('[data-add="computer"]')
    assert page.is_hidden("#empty") and state(page, "D.units.length") == 1


def test_j3_guided_connect_prevents_invalid_and_marks_auto(page: Page) -> None:
    page.click('[data-add="sensor"]')  # ST1 supports power + spacewire/rs422, not CAN
    page.click('[data-type="can"]')
    page.click("#t-connect")
    # ST1 has no CAN connector: greyed out with an explanation, and clicking explains why.
    assert "u-no" in (page.get_attribute('.unit[data-u="ST1"]', "class") or "")
    page.click('.unit[data-u="ST1"] rect.u-rect')
    assert "no free CAN connector" in page.inner_text("#toast")
    assert state(page, "D.ifaces.length") == 2  # nothing created
    # valid connection: OBC-A to ST1 over RS-422
    connect(page, "rs422", "OBC-A", "ST1")
    assert state(page, "D.ifaces.length") == 3
    assert state(page, "D.ifaces[2].a.auto") is True  # chosen for the user and marked
    assert "Auto" in page.inner_text("#props")
    page.click("#i-conf")
    assert state(page, "D.ifaces[2].a.auto") is False


def test_j3_expert_mode_exact_connector_rules(page: Page) -> None:
    page.click("#m-expert")
    page.click('[data-type="power_primary"]')
    page.click("#t-connect")
    busy = page.get_attribute('.port[data-u="RW1"][data-p="J01"]', "class") or ""
    assert " no" in busy  # RW1.J01 already carries IF-001
    wrong = page.get_attribute('.port[data-u="OBC-A"][data-p="J01"]', "class") or ""
    assert " no" in wrong  # J01 of the computer is data, not power
    page.click('.port[data-u="OBC-A"][data-p="J01"] rect')
    assert "already carries IF-002" in page.inner_text("#toast")
    page.click('.port[data-u="OBC-A"][data-p="J03"] rect')
    assert "does not carry Primary power" in page.inner_text("#toast")
    page.click('.port[data-u="PCDU-A"][data-p="J02"] rect')  # valid source
    page.click('.port[data-u="OBC-A"][data-p="J02"] rect')
    assert state(page, "D.ifaces.length") == 3
    assert state(page, "D.ifaces[2].a.auto") is False


def test_undo_redo_roundtrip(page: Page) -> None:
    h0 = state(page, "hash()")
    page.click('[data-add="payload"]')
    assert state(page, "hash()") != h0
    page.keyboard.press("Control+z")
    assert state(page, "hash()") == h0
    page.keyboard.press("Control+y")
    assert state(page, "D.units.length") == 4


def test_j4_table_edits_sync_to_canvas(page: Page) -> None:
    page.click('[data-tab="table"]')
    page.fill('input[data-c="name"][data-i="IF-001"]', "Wheel supply")
    page.press('input[data-c="name"][data-i="IF-001"]', "Tab")
    assert state(page, "D.ifaces[0].name") == "Wheel supply"
    page.click('tr[data-sel="IF-002"] td:first-child')
    assert "IF-002" in page.inner_text("#selinfo")
    page.fill("#flt", "power")
    assert page.locator("tr[data-sel]").count() == 1


def test_j5_redundant_chain_and_waiver(page: Page) -> None:
    page.click('.unit[data-u="RW1"] rect.u-rect')
    page.click("#redundant")
    assert state(page, "D.units.map(u=>u.id).includes('RW1-R')") is True
    assert state(page, "D.ifaces.filter(i=>i.side==='redundant').length") == 2
    # the mirrored interfaces cross-strap to the nominal OBC/PCDU: a warning that can be waived
    page.click('[data-tab="problems"]')
    assert "nominal chain to the redundant chain" in page.inner_text("#tabbody")
    page.locator("[data-waive]").first.click()
    page.click("#yes")
    assert "at least 10 characters" in page.inner_text("#werr")  # justification is mandatory
    page.fill("#why", "Cross-strap is by design: see ICD section 4.2")
    page.click("#yes")
    assert len(state(page, "D.waived")) == 1
    assert "Cross-strap is by design" in page.inner_text("#tabbody")


def test_j6_delete_shows_impact_and_is_undoable(page: Page) -> None:
    page.click('.unit[data-u="RW1"] rect.u-rect')
    page.click("#delete")
    text = page.inner_text("#dlg")
    assert "IF-001" in text and "IF-002" in text and "undo" in text.lower()
    page.click("#no")  # Cancel is the default focus: nothing happened
    assert state(page, "D.units.length") == 3
    page.click("#delete")
    page.click("#yes")
    assert state(page, "D.units.length") == 2 and state(page, "D.ifaces.length") == 0
    page.keyboard.press("Control+z")
    assert state(page, "D.units.length") == 3 and state(page, "D.ifaces.length") == 2


def test_j7_status_todo_is_clickable_and_problems_have_fix(page: Page) -> None:
    page.click('[data-add="pyro"]')
    page.click('[data-tab="todo"]')
    assert "not connected to anything" in page.inner_text("#tabbody")
    page.click("[data-todo='0']")
    assert "PYRO1" in page.inner_text("#selinfo")
    page.click('[data-tab="problems"]')
    assert "PYRO1 is not connected" in page.inner_text("#tabbody")


def test_j8_command_palette(page: Page) -> None:
    page.keyboard.press("Control+k")
    assert page.is_visible("#cmdk")
    page.fill("#cmdin", "expert")
    page.keyboard.press("Enter")
    assert state(page, "UI.mode") == "expert"
    page.keyboard.press("Control+k")
    page.fill("#cmdin", "rw1")
    page.keyboard.press("Enter")
    assert "RW1" in page.inner_text("#selinfo")


def test_j9_modes_do_not_change_data(page: Page) -> None:
    h = state(page, "hash()")
    page.click('.unit[data-u="OBC-A"] rect.u-rect')
    assert not page.locator("[data-part]").first.is_visible()  # guided: no physical details
    page.click("#m-expert")
    assert page.locator("[data-part]").first.is_visible()  # expert: connectors and parts appear
    assert page.locator("[data-part]").count() == 3
    page.click("#m-guided")
    assert state(page, "hash()") == h


def test_j10_generate_verify_stale_release(page: Page) -> None:
    page.click("#generate")
    assert "2 harness plans" in page.inner_text("#dlg")
    page.click("#yes")
    page.wait_for_selector("text=Independent check passed", timeout=5000)
    assert state(page, "D.gen.harnesses.length") == 2
    assert page.is_enabled("#rel")
    page.click('[data-add="payload"]')  # the model changes: plans become outdated
    assert "Outdated" in page.inner_text("#tabbody")
    assert page.is_disabled("#rel")  # cannot release outdated plans
    page.click("#undo")
    assert page.is_enabled("#rel")
    page.click("#rel")
    page.click("#yes")
    assert "Please add a short comment" in page.inner_text("#re")
    page.fill("#rc", "First release for review")
    page.click("#yes")
    assert state(page, "D.gen.released.W001") is True
    assert page.is_disabled('[data-lock="W001-001"]')  # released items are locked


def test_regeneration_report_keeps_locked_pins(page: Page) -> None:
    page.click("#generate")
    page.click("#yes")
    page.wait_for_selector("text=Independent check passed")
    page.check('[data-lock="W001-001"]')
    page.click("#generate")
    assert "keep 1 pin lock" in page.inner_text("#dlg")
    page.click("#no")


def test_generate_can_be_cancelled_without_partial_result(page: Page) -> None:
    page.click("#generate")
    page.click("#yes")
    page.click("#cancelgen")
    assert state(page, "D.gen") is None


def test_import_preview_reports_row_errors_and_is_one_undo(page: Page) -> None:
    page.click("#importbtn")
    text = page.inner_text("#prev")
    for expected in (
        "Unknown interface type",
        "already used",
        "does not exist",
        "No free CAN connector",
    ):
        assert expected in text
    assert "2 of 6 rows can be imported" in text
    assert state(page, "D.ifaces.length") == 2  # nothing imported until confirmed
    assert page.inner_text("#yes") == "Import 2 rows (one undo step)"
    page.click("#yes")
    assert state(page, "D.ifaces.length") == 4
    assert state(page, "D.ifaces[2].a.auto") is True  # imported connectors are marked auto-filled
    page.keyboard.press("Control+z")
    assert state(page, "D.ifaces.length") == 2  # one step undoes the whole import


def test_import_cancel_changes_nothing(page: Page) -> None:
    page.click("#importbtn")
    page.click("#no")
    assert state(page, "D.ifaces.length") == 2


def test_live_validation_of_ids(page: Page) -> None:
    page.click('.unit[data-u="OBC-A"] rect.u-rect')
    page.fill("#f-id", "RW1")
    page.press("#f-id", "Tab")
    assert "already used" in page.inner_text("#e-id")
    assert page.get_attribute("#f-id", "aria-invalid") == "true"
    assert state(page, "D.units[0].id") == "OBC-A"
    page.fill("#f-id", "1bad")
    page.press("#f-id", "Tab")
    assert "start with a letter" in page.inner_text("#e-id")


def test_dragging_a_unit_changes_zone(page: Page) -> None:
    box = page.locator('.unit[data-u="OBC-A"] rect.u-rect').bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + 20, box["y"] + 15)
    page.mouse.down()
    page.mouse.move(box["x"] + 520, box["y"] + 15, steps=5)
    page.mouse.up()
    assert state(page, "D.units[0].x") > 435
    page.click('.unit[data-u="OBC-A"] rect.u-rect')
    assert page.input_value("#f-id ~ input[disabled]") == "panel-B"  # zone follows position


def test_theme_scale_and_keyboard_focus(page: Page) -> None:
    open_more(page)
    page.click("#theme")
    assert page.evaluate("document.documentElement.dataset.theme") == "dark"
    page.select_option("#scale", "200%")
    assert page.evaluate("document.body.style.zoom") == "2"
    page.focus('.unit[data-u="OBC-A"]')
    page.keyboard.press("Enter")
    assert "OBC-A" in page.inner_text("#selinfo")


def test_new_units_never_overlap_existing_ones(page: Page) -> None:
    for tpl in ("sensor", "payload", "transceiver", "pyro", "actuator", "computer"):
        page.click(f'[data-add="{tpl}"]')
    pos = state(page, "D.units.map(u=>[u.x,u.y])")
    for i, a in enumerate(pos):
        for b in pos[i + 1 :]:
            assert abs(a[0] - b[0]) >= 176 or abs(a[1] - b[1]) >= 90, (a, b)


def test_pressed_and_primary_buttons_stay_readable_on_hover(page: Page) -> None:
    page.hover("#t-select")  # pressed button
    bg = page.evaluate("getComputedStyle(document.querySelector('#t-select')).backgroundColor")
    assert bg != page.evaluate(
        "getComputedStyle(document.querySelector('#t-connect')).backgroundColor"
    )
    page.hover("#generate")  # primary button keeps its filled look
    colour = page.evaluate("getComputedStyle(document.querySelector('#generate')).color")
    assert colour == "rgb(255, 255, 255)"


def test_connect_mode_marks_source_and_explains_greyed_units_inline(page: Page) -> None:
    page.click('[data-add="sensor"]')
    page.click('[data-type="can"]')
    page.click("#t-connect")
    # inline reasons are visible text, not hover-only tooltips
    assert "No free CAN connector" in (page.text_content('.unit[data-u="ST1"]') or "")
    page.click('.unit[data-u="OBC-A"] rect.u-rect')  # OBC-A has a free CAN connector
    cls = page.get_attribute('.unit[data-u="OBC-A"]', "class") or ""
    assert "u-from" in cls.split() and "u-no" not in cls.split()
    assert "FROM" in (page.text_content('.unit[data-u="OBC-A"]') or "")
    # nothing else can take CAN: the hint says so explicitly
    assert "No other unit has a free CAN connector" in page.inner_text("#hint")


def test_cross_strap_fix_completes_the_redundant_chain(page: Page) -> None:
    page.click('.unit[data-u="RW1"] rect.u-rect')
    page.click("#redundant")
    page.click('[data-tab="problems"]')
    assert "Connect to a redundant copy of PCDU-A" in page.inner_text("#tabbody")
    for _ in range(2):
        page.locator("[data-fix]").first.click()
    ids = state(page, "D.units.map(u=>u.id)")
    assert {"PCDU-A-R", "OBC-A-R", "RW1-R"} <= set(ids)
    sev = state(page, "problems().filter(p=>p.sev==='warning').length")
    assert sev == 0
    assert state(
        page,
        "D.ifaces.filter(i=>i.side==='redundant').every(i=>D.units.find(u=>u.id===i.a.u).side==='redundant' && D.units.find(u=>u.id===i.b.u).side==='redundant')",
    )


def test_redundant_copy_does_not_overlap_other_units(page: Page) -> None:
    page.click('.unit[data-u="RW1"] rect.u-rect')
    page.click("#redundant")
    pos = state(page, "D.units.map(u=>[u.x,u.y])")
    for i, a in enumerate(pos):
        for b in pos[i + 1 :]:
            assert abs(a[0] - b[0]) >= 176 or abs(a[1] - b[1]) >= 90, (a, b)


def test_links_attach_on_the_side_facing_the_gap(page: Page) -> None:
    page.click("#m-expert")
    # both ends of every sample interface: ports of panel-A units are on the right edge
    assert page.locator('.unit[data-u="OBC-A"] .port rect').first.get_attribute("x") == "169"
    assert page.locator('.unit[data-u="RW1"] .port rect').first.get_attribute("x") == "-7"


def test_panels_collapse_and_small_viewport_keeps_canvas_usable(page: Page) -> None:
    page.click("#bmin")
    assert page.is_hidden("#tabbody")
    page.click("#bmin")
    assert page.is_visible("#tabbody")
    page.click("#bexp")
    tall = page.locator("#bottom").bounding_box()
    page.click("#bexp")
    normal = page.locator("#bottom").bounding_box()
    assert tall is not None and normal is not None and tall["height"] > normal["height"]
    open_more(page)
    page.select_option("#scale", "200%")  # effective viewport 720x450 CSS px
    canvas = page.locator("#canvaswrap").bounding_box()
    assert canvas is not None and canvas["height"] >= 300  # real pixels at 200%: >= 150 CSS px
    assert page.is_hidden("#props")  # auto-collapsed so the diagram keeps the space


@pytest.mark.parametrize("step", range(5))
def test_tour_card_does_not_cover_its_target(browser, step: int) -> None:  # type: ignore[no-untyped-def]
    pg = browser.new_page(viewport={"width": 1440, "height": 900})
    pg.goto(URL)
    pg.wait_for_selector("#tour", state="visible")
    for _ in range(step):
        pg.click("#tn")
    card = pg.locator("#tour").bounding_box()
    target = pg.locator(".tourhl").first.bounding_box()
    assert card is not None and target is not None
    overlap_x = min(card["x"] + card["width"], target["x"] + target["width"]) - max(
        card["x"], target["x"]
    )
    overlap_y = min(card["y"] + card["height"], target["y"] + target["height"]) - max(
        card["y"], target["y"]
    )
    inside_big_target = (
        target["width"] > 600 and target["height"] > 300
    )  # canvas: card floats over it
    assert inside_big_target or overlap_x <= 0 or overlap_y <= 0, (step, card, target)
    pg.close()


def test_dark_theme_uses_dark_native_controls(page: Page) -> None:
    open_more(page)
    page.click("#theme")
    assert page.evaluate("getComputedStyle(document.documentElement).colorScheme") == "dark"
