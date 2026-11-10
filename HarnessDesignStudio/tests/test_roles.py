# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""M5 (D-176), S9: the three roles, pure logic (no Qt). REQ-GUI-14, REQ-GUI-15."""

import pytest

from harness_design_studio.gui import areas, roles, strings
from harness_design_studio.gui.roles import (
    AIT,
    ELECTRICAL,
    ROLES,
    SYSTEMS,
    clean_role,
    default_role,
    role_key,
)


def test_there_are_three_roles_and_the_old_workspaces_are_gone() -> None:
    assert ROLES == (SYSTEMS, ELECTRICAL, AIT) == ("systems", "electrical", "ait")
    from harness_design_studio.gui import next_step

    for name in ("WORKSPACES", "FIRST_RUN_WORKSPACE", "default_workspace", "workspace_key"):
        assert not hasattr(next_step, name)
    for name in ("WORKSPACE_SIMPLE", "WORKSPACE_FULL", "SETTINGS_WORKSPACE"):
        assert not hasattr(strings, name)


def test_the_names_on_screen_are_the_role_names() -> None:
    assert strings.ROLE_SYSTEMS == "Systems engineer"
    assert strings.ROLE_ELECTRICAL == "Electrical engineer"
    assert strings.ROLE_AIT == "AIT engineer"
    assert strings.M_ROLE == strings.SETTINGS_ROLE == "Role"
    assert "View > Role" in strings.ROLE_DIALOG_LATER


def test_a_file_with_nothing_stored_gets_the_hook_or_asks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(roles, "FIRST_RUN_ROLE", None)
    assert default_role(False) is None  # the window asks
    monkeypatch.setattr(roles, "FIRST_RUN_ROLE", "systems")
    assert default_role(False) == SYSTEMS
    monkeypatch.setattr(roles, "FIRST_RUN_ROLE", "electrical")
    assert default_role(False) == ELECTRICAL
    monkeypatch.setattr(roles, "FIRST_RUN_ROLE", "pink")  # not a role: the same as no hook
    assert default_role(False) is None


def test_an_existing_user_is_an_electrical_engineer_silently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for hook in (None, "systems", "electrical"):
        monkeypatch.setattr(roles, "FIRST_RUN_ROLE", hook)  # (the hook is for new files only)
        assert default_role(True) == ELECTRICAL
        assert default_role(True, None) == ELECTRICAL
        assert default_role(True, "pink") == ELECTRICAL


def test_the_workspace_of_1_7_0_carries_over() -> None:
    """Simple becomes the Systems engineer, Full the Electrical / AIT engineer."""
    assert default_role(True, "simple") == SYSTEMS
    assert default_role(True, "full") == ELECTRICAL


def test_a_stored_value_is_cleaned() -> None:
    assert clean_role("systems", ELECTRICAL) == SYSTEMS
    assert clean_role("electrical", SYSTEMS) == ELECTRICAL
    assert clean_role("pink", SYSTEMS) == SYSTEMS
    assert clean_role("simple", ELECTRICAL) == ELECTRICAL  # (the old words are not roles)
    assert clean_role("ait", SYSTEMS) == AIT
    # the value from before Electrical and AIT were two roles is the Electrical role (S9)
    assert clean_role("electrical_ait", SYSTEMS) == ELECTRICAL
    assert clean_role(None, ELECTRICAL) == ELECTRICAL
    assert clean_role("", "") == ""


def test_the_layout_keys_keep_what_the_workspaces_had() -> None:
    """Nobody loses a layout: Electrical keeps the Full keys, Systems the Simple keys."""
    assert role_key("ui/state", ELECTRICAL) == "ui/state"
    assert role_key("ui/state", SYSTEMS) == "ui/simple/state"
    assert role_key("ui/problem_notices", SYSTEMS) == "ui/simple/problem_notices"
    assert role_key("layout/ab12/area", ELECTRICAL) == "layout/ab12/area"
    assert role_key("layout/ab12/rail", SYSTEMS) == "layout/ab12/simple/rail"
    assert role_key("state", SYSTEMS) == "simple/state"
    assert role_key("state", ELECTRICAL) == "state"
    # AIT has keys of its own, next to the other two, so no layout is overwritten
    assert role_key("ui/state", AIT) == "ui/ait/state"
    assert role_key("layout/ab12/area", AIT) == "layout/ab12/ait/area"
    assert role_key("state", AIT) == "ait/state"


def test_the_rail_of_each_role() -> None:
    assert areas.hidden_in(ELECTRICAL) == ("asbuilt",)  # every area but the as-built records
    assert areas.hidden_in(SYSTEMS) == ("home", "drawings", "outputs", "asbuilt")
    assert areas.hidden_in(AIT) == ("model",)
    shown = [k for k in areas.KEYS if k not in areas.hidden_in(SYSTEMS)]
    assert shown == ["next", "model", "checks", "revisions", "settings"]
    assert areas.listed_areas(AIT) == (
        "next", "home", "checks", "drawings", "outputs", "asbuilt", "revisions", "settings",
    )  # fmt: skip
    assert areas.unlisted_everywhere() == ()  # every page is on the rail of at least one role
    # the areas still exist: menus, keys, the Next step buttons and the palette reach them
    assert set(areas.hidden_in(SYSTEMS)) <= set(areas.KEYS)


def test_the_role_sentences_name_the_work_of_each_role() -> None:
    systems = strings.ROLE_DIALOG_SYSTEMS_TEXT.lower()
    electrical = strings.ROLE_DIALOG_ELECTRICAL_TEXT.lower()
    assert "devices" in systems and "connections" in systems and "library" in systems
    ait = strings.ROLE_DIALOG_AIT_TEXT.lower()
    for word in ("connectors", "pinouts", "harnesses", "wires", "engineering values", "models"):
        assert word in electrical
    for word in ("build data", "build sheets", "as-built", "workflow"):
        assert word in ait
    for text in (
        systems, electrical, ait, strings.ROLE_SYSTEMS_TIP, strings.ROLE_ELECTRICAL_TIP,
        strings.ROLE_AIT_TIP,
    ):  # fmt: skip
        assert "unit" not in text.replace("community", "")  # the screen says device
