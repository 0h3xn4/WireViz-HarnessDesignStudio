# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""UI overhaul M2: the areas (no Qt): every main tab belongs to exactly one area."""

from harness_design_studio.gui import areas

MAIN_TABS = ("diagram", "harness", "lists", "checks", "releases", "devices")


def test_every_main_tab_is_in_exactly_one_area() -> None:
    held = [t for a in areas.AREAS for t in a.tabs]
    assert sorted(held) == sorted(MAIN_TABS)
    for tab in MAIN_TABS:
        assert tab in areas.tabs_of(areas.area_of_tab(tab))


def test_the_rail_lists_the_nine_areas_in_order_with_next_step_first_and_settings_last() -> None:
    assert areas.KEYS == (
        "next", "home", "model", "checks", "drawings", "outputs", "asbuilt", "revisions",
        "settings",
    )  # fmt: skip
    assert areas.PAGES == ("next", "home", "asbuilt", "settings")  # the areas that are pages
    assert areas.DEFAULT in areas.KEYS


def test_areas_have_titles_tips_and_icons_that_exist() -> None:
    from harness_design_studio.gui import icons

    for a in areas.AREAS:
        assert a.title and a.tip and a.icon in icons.ICONS
