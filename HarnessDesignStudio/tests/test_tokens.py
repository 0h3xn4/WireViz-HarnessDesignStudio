"""REQ-UX-01: design tokens meet WCAG 2.2 AA and stay distinguishable for colour-blind users."""

import itertools
import math

import pytest

from harness_design_studio.gui.theme.tokens import (
    CATEGORIES,
    CONTROL_HEIGHT,
    DARK,
    LIGHT,
    SPACING,
    SURFACES,
    TEXT_TOKENS,
    TYPE_SCALE,
    _lin,
    contrast,
)

THEMES = {"light": LIGHT, "dark": DARK}
TEXT_ROLES = (*TEXT_TOKENS, "locked", "released", "stale")  # fmt: skip
STATE_TOKENS = (
    "success",
    "error",
    "warning",
    "pending",
    "not-checked",
    "locked",
    "released",
    "stale",
)
CATS = [f"cat-{c}" for c in CATEGORIES]

# Machado et al. (2009) colour-vision-deficiency matrices, full severity, linear RGB.
CVD = {
    "protan": [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
    "deutan": [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]],
    "tritan": [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]],
}  # fmt: skip


def _lab(rgb: list[float]) -> tuple[float, float, float]:
    r, g, b = rgb
    x = 0.4124 * r + 0.3576 * g + 0.1805 * b
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = 0.0193 * r + 0.1192 * g + 0.9505 * b

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x / 0.95047), f(y), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def _views(hex_colour: str) -> list[tuple[float, float, float]]:
    lin = [_lin(int(hex_colour[i : i + 2], 16)) for i in (1, 3, 5)]
    views = [lin]
    for m in CVD.values():
        views.append(
            [max(0.0, min(1.0, sum(m[r][c] * lin[c] for c in range(3)))) for r in range(3)]
        )
    return [_lab(v) for v in views]


@pytest.mark.parametrize("theme", THEMES)
def test_text_and_status_colours_meet_aa_text(theme: str) -> None:
    t = THEMES[theme]
    for role in TEXT_ROLES:
        for surface in SURFACES:
            assert contrast(t[role], t[surface]) >= 4.5, (theme, role, surface)
    assert contrast(t["accent.text"], t["accent"]) >= 4.5
    assert contrast(t["accent.text"], t["accent.hover"]) >= 4.5


@pytest.mark.parametrize("theme", THEMES)
def test_ui_boundaries_focus_and_categories_meet_aa_graphics(theme: str) -> None:
    t = THEMES[theme]
    for role in ("border.control", "focus", *CATS):
        for surface in SURFACES:
            assert contrast(t[role], t[surface]) >= 3.0, (theme, role, surface)


@pytest.mark.parametrize("theme", THEMES)
def test_category_colours_stay_apart_for_colour_blind_users(theme: str) -> None:
    t = THEMES[theme]
    views = {c: _views(t[c]) for c in CATS}
    worst = min(
        math.dist(views[a][i], views[b][i])
        for a, b in itertools.combinations(CATS, 2)
        for i in range(4)
    )
    assert worst >= 20, f"{theme}: two categories look too alike (min dE {worst:.1f})"


def test_every_category_has_non_colour_cues() -> None:
    icons = [c["icon"] for c in CATEGORIES.values()]
    labels = [c["label"] for c in CATEGORIES.values()]
    assert len(set(icons)) == len(icons) and len(set(labels)) == len(labels)
    assert set(THEMES) == {"light", "dark"} and set(LIGHT) == set(DARK)


def test_spacing_is_on_the_4px_grid() -> None:
    assert all(s % 4 == 0 for s in SPACING)


def test_type_and_spacing_scales_are_the_standards() -> None:
    assert tuple(TYPE_SCALE.values()) == (11, 12, 13, 15, 18, 22)
    assert SPACING == (4, 8, 12, 16, 24, 32)
    assert CONTROL_HEIGHT in SPACING


@pytest.mark.parametrize("theme", THEMES)
def test_pending_and_not_checked_have_their_own_colours(theme: str) -> None:
    """New state tokens exist in both themes and no two state colours are the same."""
    t = THEMES[theme]
    for token in ("pending", "not-checked", "stale", "locked", "released", "paper", "pasteboard"):
        assert token in t, (theme, token)
    values = [t[k].upper() for k in STATE_TOKENS if k not in ("released",)]
    # released may share the pass tone (it is a pass-like state, told apart by icon and word)
    assert len(values) == len(set(values)), (theme, values)


@pytest.mark.parametrize("theme", THEMES)
def test_drawing_paper_and_pasteboard_stay_apart(theme: str) -> None:
    t = THEMES[theme]
    assert t["paper"].upper() == "#FFFFFF"  # the picture of a sheet stays white in both themes
    assert contrast(t["paper"], t["pasteboard"]) >= 3.0


# ---- REQ-GUI-20: the accent colours of the device cards (gui/device_kinds.py) -------------------

DEVICE = sorted(k for k in LIGHT if k.startswith("device."))


def test_every_device_family_has_an_accent_in_both_themes() -> None:
    from harness_design_studio.gui.device_kinds import FAMILIES

    wanted = sorted(f.token for f in FAMILIES if f.token)
    assert wanted == DEVICE and len(wanted) == 9
    assert sorted(k for k in DARK if k.startswith("device.")) == wanted


@pytest.mark.parametrize("theme", THEMES)
def test_device_accents_carry_the_ink_and_stand_out_from_every_surface(theme: str) -> None:
    """A badge is the accent with the pictogram in `accent.text` on it (4.5:1) and the badge and the
    band against the card, the header and the canvas (3:1, the rule for graphics)."""
    t = THEMES[theme]
    for token in DEVICE:
        assert contrast(t["accent.text"], t[token]) >= 4.5, (theme, token)
        for surface in SURFACES:
            assert contrast(t[token], t[surface]) >= 3.0, (theme, token, surface)


@pytest.mark.parametrize("theme", THEMES)
def test_device_accents_stay_apart_and_the_pictogram_and_shape_carry_the_rest(theme: str) -> None:
    """Nine colours cannot all stay apart for every kind of colour blindness (green and rose, blue
    and purple come close), so the bar is 20 for normal sight and 6 in the worst simulated view;
    two families that come close there have different badge shapes, and every kind has its own
    pictogram and its words (test_ui_device_looks.py)."""
    t = THEMES[theme]
    views = {c: _views(t[c]) for c in DEVICE}
    near = []
    for a, b in itertools.combinations(DEVICE, 2):
        dist = [math.dist(views[a][i], views[b][i]) for i in range(4)]
        assert dist[0] >= 20, f"{theme}: {a} and {b} look too alike (dE {dist[0]:.1f})"
        assert min(dist) >= 6, (
            f"{theme}: {a} and {b} (dE {min(dist):.1f} for some colour blindness)"
        )
        if min(dist) < 12:
            near.append((a, b))
    from harness_design_studio.gui.device_kinds import FAMILIES

    shape = {f.token: f.shape for f in FAMILIES}
    assert all(shape[a] != shape[b] for a, b in near), near


@pytest.mark.parametrize("theme", THEMES)
def test_the_id_stays_readable_on_a_box_seen_from_far_away(theme: str) -> None:
    """The far-away box is tinted with the accent (`device_kinds.OVERVIEW_TINT`); its ID is
    `text.primary` and must keep 4.5:1 on the tinted ground of every family."""
    from harness_design_studio.gui.device_kinds import OVERVIEW_TINT

    t = THEMES[theme]
    for token in DEVICE:
        ground = _blend(t["bg.surface"], t[token], OVERVIEW_TINT)
        assert contrast(t["text.primary"], ground) >= 4.5, (theme, token)


def _blend(base: str, over: str, share: float) -> str:
    a = [int(base[i : i + 2], 16) for i in (1, 3, 5)]
    b = [int(over[i : i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(
        f"{round(x * (1 - share) + y * share):02X}" for x, y in zip(a, b, strict=True)
    )
