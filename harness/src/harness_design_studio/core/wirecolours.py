"""Wire colours: the IEC 60757 names and codes, and how to read a colour typed by a person.

The table is used to draw and to offer a choice; it decides nothing about a design. A colour that
this table does not know is kept as typed and drawn grey.
"""

# (name, IEC 60757 code, screen colour)
COLOURS: tuple[tuple[str, str, str], ...] = (
    ("black", "BK", "#1a1a1a"),
    ("brown", "BN", "#8b5a2b"),
    ("red", "RD", "#e02020"),
    ("orange", "OG", "#ff8c00"),
    ("yellow", "YE", "#ffd700"),
    ("green", "GN", "#22aa22"),
    ("blue", "BU", "#1e5bd8"),
    ("violet", "VT", "#8a2be2"),
    ("grey", "GY", "#9a9a9a"),
    ("white", "WH", "#ffffff"),
    ("pink", "PK", "#ff8fb0"),
    ("turquoise", "TQ", "#20b2aa"),
)
UNSET_COLOUR = "#808080"
_BY_CODE = {code: (code, hexcolour) for _n, code, hexcolour in COLOURS}
_BY_NAME = {name: _BY_CODE[code] for name, code, _h in COLOURS} | {
    "gray": _BY_CODE["GY"],
    "purple": _BY_CODE["VT"],
}


def _one(key: str) -> tuple[str, str] | None:
    return _BY_NAME.get(key.lower()) or _BY_CODE.get(key.upper())


def resolve(name: str | None) -> tuple[str, str]:
    """(code, screen colour) of a wire colour: ("BK", "#1a1a1a"). A colour that is not set gives
    ("", grey); one this table does not know keeps its text (shortened) and is drawn grey. Two
    known colours joined by "/" or "-" ("yellow/green") give both codes ("YE/GN"), drawn grey."""
    if not name:
        return "", UNSET_COLOUR
    key = name.strip()
    found = _one(key)
    if found:
        return found
    parts = [_one(p.strip()) for p in key.replace("-", "/").split("/")]
    if len(parts) == 2 and parts[0] and parts[1]:
        return f"{parts[0][0]}/{parts[1][0]}", UNSET_COLOUR
    return key[:6], UNSET_COLOUR


def name_of(value: str | None) -> str:
    """The table's colour name for a typed colour ("RD" gives "red"), or "" when it is not one."""
    code, _hex = resolve(value)
    return next((n for n, c, _h in COLOURS if c == code), "")
