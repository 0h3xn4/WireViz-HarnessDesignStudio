"""Every kind of derivation, with the page of `docs/models/` that describes it (D-191, S1).

A derivation has a `kind` (its `id`). This table is the list of kinds the tool can produce and the
page that explains the model behind each. A test walks the kinds a project produces and the rules of
the registry, and fails on one that is not listed here or whose page does not name it, so a new
derivation cannot be added without its page (S10 of the plan: none is left out).
"""

# kind -> (the page of docs/models/, what it explains)
KINDS: dict[str, tuple[str, str]] = {
    "wire-length": ("wire-length.md", "the length of a wire"),
    "wire-current-limit": ("wire-sizing.md", "the current a wire's gauge may carry after derating"),
    "wire-voltage-drop": ("wire-sizing.md", "the voltage drop over a wire"),
    "wire-override": (
        "overrides.md",
        "a value of a wire set by the engineer, and its consequences",
    ),
    "wire-mass": ("mass.md", "the mass of a wire"),
    "harness-mass": ("mass.md", "the mass of a harness"),
    "part-bom": ("bom.md", "the quantity of a part in the bill of materials"),
    "contact-current": ("contact-current.md", "the current the contacts of a connector may carry"),
    "readiness": ("readiness.md", "the answer Ready to build of the build workbook"),
    "readiness-check": ("readiness.md", "one check behind Ready to build and what is open"),
    "test-limit": ("test-limits.md", "a limit or the voltage of the test sheet"),
    "pin-allocation": ("pin-allocation.md", "why a signal is on a pin"),
    "connector-choice": ("pin-allocation.md", "why a connector is the connector of an interface"),
    "segmentation": ("segmentation.md", "why the interfaces of a harness share it"),
    "wire-label": ("labels-and-colours.md", "the labels of a wire"),
    "connector-label": ("labels-and-colours.md", "the label of a cable connector"),
    "wire-colour": ("labels-and-colours.md", "the colour of a wire"),
    "shield-group": ("shields.md", "a shield group, its wires and its ends"),
    "asbuilt-result": (
        "asbuilt.md",
        "an as-built result compared with its limit or with the designed value",
    ),
    "rule-limit": ("rule-limits.md", "the limit a design rule compares a number with"),
    "rule-check": ("rule-limits.md", "what a yes/no design rule compares"),
}


def page_of(kind: str) -> str:
    """The page of `docs/models/` for a kind of derivation."""
    return KINDS[kind][0]
