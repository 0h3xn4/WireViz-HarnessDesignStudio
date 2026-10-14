"""Render screenshots of the prototype's key screens into docs/ux/screens (needs Playwright)."""

import glob
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "ux" / "screens"
URL = (ROOT / "prototype" / "index.html").as_uri()


def shot(page: Page, name: str) -> None:
    page.wait_for_timeout(150)
    page.screenshot(path=str(OUT / f"{name}.png"))
    print(name)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    chrome = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))[-1]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"])
        page = b.new_page(viewport={"width": 1440, "height": 900})
        page.goto(URL)
        page.wait_for_selector("#tour", state="visible")
        shot(page, "01-first-run-tour")
        page.click("#ts")
        shot(page, "02-guided-main")
        page.click('[data-add="sensor"]')
        page.click('[data-type="can"]')
        page.click("#t-connect")
        page.click('.unit[data-u="OBC-A"] rect.u-rect')
        shot(page, "03-connect-compatible-highlight")
        page.keyboard.press("Escape")
        page.click("#m-expert")
        page.click('[data-type="power_primary"]')
        page.click("#t-connect")
        shot(page, "04-expert-connectors")
        page.keyboard.press("Escape")
        page.click("#t-select")
        page.click('.unit[data-u="RW1"] rect.u-rect')
        page.click("#redundant")
        page.click('[data-tab="problems"]')
        shot(page, "05-redundant-copy-and-problems")
        page.locator("[data-waive]").first.click()
        page.click("#yes")
        shot(page, "06-waiver-requires-justification")
        page.click("#no")
        page.click('[data-tab="table"]')
        shot(page, "07-interface-table")
        page.click("#generate")
        shot(page, "08-generate-preview")
        page.click("#yes")
        page.wait_for_selector("text=Independent check passed")
        shot(page, "09-harness-plans")
        page.click('.unit[data-u="RW1"] rect.u-rect')
        page.click("#delete")
        shot(page, "10-delete-impact")
        page.click("#no")
        page.click("#importbtn")
        shot(page, "11-import-preview")
        page.click("#no")
        page.keyboard.press("Control+k")
        page.fill("#cmdin", "conn")
        shot(page, "12-command-palette")
        page.keyboard.press("Escape")
        page.click("#morebtn")
        page.click("#theme")
        shot(page, "13-dark-theme")
        page.click("#theme")
        page.select_option("#scale", "150%")
        shot(page, "14-scale-150")
        b.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
