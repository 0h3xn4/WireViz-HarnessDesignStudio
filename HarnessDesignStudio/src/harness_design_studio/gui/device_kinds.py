# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The kinds of device on the screen: the words of the inspector and the tooltip.

The table of the kinds, the families, the order in which a kind is read from a device and the
accent colours are in `core/device_kinds.py` (no Qt, so the written block diagram draws the same
looks from the model alone). This module re-exports them for the window and adds the one thing
that is the screen's: the sentence that says what a device looks like and why.
"""

from harness_design_studio.core.device_kinds import (
    ACCENTS,
    FAMILIES,
    FAMILY,
    FROM_LINKS,
    GENERIC,
    KIND,
    KIND_IDS,
    KINDS,
    OVERVIEW_TINT,
    SHAPES,
    Family,
    Kind,
    Looks,
    automatic_looks,
    id_letters,
    looks_for,
    looks_of,
    used_kinds,
    words_of,
)
from harness_design_studio.gui import strings

__all__ = [
    "ACCENTS",
    "FAMILIES",
    "FAMILY",
    "FROM_LINKS",
    "GENERIC",
    "KIND",
    "KINDS",
    "KIND_IDS",
    "OVERVIEW_TINT",
    "SHAPES",
    "Family",
    "Kind",
    "Looks",
    "automatic_looks",
    "id_letters",
    "looks_for",
    "looks_of",
    "sentence",
    "used_kinds",
    "words_of",
]


def sentence(looks: Looks, name: str, unit_id: str) -> str:
    """One plain sentence for the inspector and the tooltip: `Looks like: Battery (from the name
    Battery 1)`, or `Looks like: Battery (set by hand)`."""
    if looks.source == "manual":
        why = strings.LOOKS_FROM_MANUAL
    elif looks.source == "name":
        why = strings.LOOKS_FROM_NAME.format(name=name)
    elif looks.source == "id":
        why = strings.LOOKS_FROM_ID.format(id=unit_id)
    elif looks.source == "subsystem":
        why = strings.LOOKS_FROM_SUBSYSTEM.format(word=looks.clue)
    elif looks.source == "links":
        why = strings.LOOKS_FROM_LINKS
    else:
        why = strings.LOOKS_FROM_NOTHING
    return strings.LOOKS_LIKE.format(kind=looks.kind.label, why=why)
