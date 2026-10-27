"""Two more ways to propose the pairs of a connection (Release 1.9, W1): by pin number and from a
pasted table. Like `links.propose_pairs` they only PROPOSE: they return a `Proposal` that the
window shows, and a person accepts (the owner's rule: the tool proposes, a person confirms). They
change nothing and write nothing.

    pair_by_number(project, "OBC-J01", "RW1-J02")          # pin 1 to pin 1, 2 to 2 ...
    parse_pairing(project, "OBC-J01", "RW1-J02", text)      # "1<TAB>4" per line, from a spreadsheet

Both leave out pins that another link already pairs, pins an interface wires (Generate owns them),
and the pins named in `skip_a` / `skip_b` (the pairs the person already has in the window).
"""

import re
from collections.abc import Collection

from .links import Proposal, _two_devices, natural_key, pins_in_links
from .model import Connector, PinPair, Project

_SPLIT_TAB = re.compile(r"\t")
_SPLIT_MARK = re.compile(r"\s*[;,]\s*")
_SPLIT_SPACE = re.compile(r"\s+")


def _free(
    project: Project, conn: Connector, skip: Collection[str], notes: list[str]
) -> dict[str, str]:
    """The pins that can be paired now, by lower-case ID -> ID, with a note for those that cannot."""
    taken = pins_in_links(project, conn.id)
    out: dict[str, str] = {}
    by_link: dict[str, list[str]] = {}
    wired: list[str] = []
    for p in sorted(conn.pins, key=lambda p: natural_key(p.id)):
        if p.id in taken:
            by_link.setdefault(taken[p.id], []).append(p.id)
        elif p.interface_id:
            wired.append(p.id)
        elif p.id not in skip:
            out[p.id.casefold()] = p.id
    for lid, pids in sorted(by_link.items()):
        notes.append(
            f"Pin{'s' if len(pids) > 1 else ''} {', '.join(pids)} of {conn.id} "
            f"{'are' if len(pids) > 1 else 'is'} already paired in link {lid}."
        )
    if wired:
        notes.append(
            f"Pin{'s' if len(wired) > 1 else ''} {', '.join(wired)} of {conn.id} "
            f"{'are' if len(wired) > 1 else 'is'} used by an interface that Generate wires, so not offered."
        )
    return out


def _proposal(
    pairs: list[PinPair], fa: dict[str, str], fb: dict[str, str], notes: list[str]
) -> Proposal:
    used_a = {p.a_pin for p in pairs}
    used_b = {p.b_pin for p in pairs}
    pairs.sort(key=lambda p: natural_key(p.a_pin))
    return Proposal(
        tuple(pairs),
        tuple(v for v in fa.values() if v not in used_a),
        tuple(v for v in fb.values() if v not in used_b),
        tuple(notes),
    )


def pair_by_number(
    project: Project,
    a_connector_id: str,
    b_connector_id: str,
    *,
    skip_a: Collection[str] = (),
    skip_b: Collection[str] = (),
) -> Proposal:
    """Pin 1 to pin 1, pin 2 to pin 2 ... (the same pin ID on both connectors, case ignored)."""
    a, b = _two_devices(project, a_connector_id, b_connector_id)
    notes: list[str] = []
    fa = _free(project, a, skip_a, notes)
    fb = _free(project, b, skip_b, notes)
    pairs = [PinPair(a_pin=fa[k], b_pin=fb[k]) for k in fa if k in fb]
    out = _proposal(pairs, fa, fb, notes)
    if not pairs:
        notes.append(
            f"No pin of {a.id} has the same number as a free pin of {b.id}, so nothing was paired."
        )
    else:
        for conn, left in ((a, out.unpaired_a), (b, out.unpaired_b)):
            if left:
                notes.append(
                    f"{len(left)} pin{'s' if len(left) > 1 else ''} of {conn.id} "
                    f"({', '.join(left[:6])}{', ...' if len(left) > 6 else ''}) "
                    f"{'have' if len(left) > 1 else 'has'} no pin with the same number and "
                    f"{'are' if len(left) > 1 else 'is'} left unpaired."
                )
    return Proposal(out.pairs, out.unpaired_a, out.unpaired_b, tuple(notes))


def _cells(line: str) -> list[str]:
    for split in (_SPLIT_TAB, _SPLIT_MARK, _SPLIT_SPACE):
        parts = [c.strip().strip("\"'") for c in split.split(line.strip())]
        if len(parts) >= 2:
            return parts
    return [line.strip()]


def parse_pairing(
    project: Project,
    a_connector_id: str,
    b_connector_id: str,
    text: str,
    *,
    skip_a: Collection[str] = (),
    skip_b: Collection[str] = (),
) -> Proposal:
    """A pairing pasted from a table: one line per pair, the pin of the first connector, a tab (a
    comma, a semicolon or spaces work too), the pin of the second. More columns are ignored. A
    first line that names no pin of either connector is taken for a heading. Lines that cannot be
    used are named in the notes; the others are proposed."""
    a, b = _two_devices(project, a_connector_id, b_connector_id)
    notes: list[str] = []
    fa = _free(project, a, skip_a, notes)
    fb = _free(project, b, skip_b, notes)
    have_a = {p.id.casefold() for p in a.pins}
    have_b = {p.id.casefold() for p in b.pins}
    pairs: list[PinPair] = []
    seen_a: set[str] = set()
    seen_b: set[str] = set()
    first = True
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        cells = _cells(raw)
        was_first, first = first, False
        if len(cells) < 2:
            notes.append(f"Line {number} was skipped: it needs a pin of {a.id}, a tab and a pin of {b.id}.")  # fmt: skip
            continue
        ka, kb = cells[0].casefold(), cells[1].casefold()
        if was_first and ka not in have_a and kb not in have_b:
            continue  # a heading ("Pin A", "Pin B")
        bad = [
            f"{conn.id} has no pin '{cell}'"
            for conn, cell, have in ((a, cells[0], ka in have_a), (b, cells[1], kb in have_b))
            if not have
        ]
        if bad:
            notes.append(f"Line {number} was skipped: {' and '.join(bad)}.")
            continue
        if ka not in fa or kb not in fb:
            which = a.id if ka not in fa else b.id
            pin = cells[0] if ka not in fa else cells[1]
            notes.append(
                f"Line {number} was skipped: pin {pin} of {which} cannot be paired here "
                "(it is already paired, used by an interface, or in the table already)."
            )
            continue
        if ka in seen_a or kb in seen_b:
            twice = cells[0] if ka in seen_a else cells[1]
            notes.append(f"Line {number} was skipped: pin {twice} is in an earlier line. A pin can be in one pair only.")  # fmt: skip
            continue
        seen_a.add(ka)
        seen_b.add(kb)
        pairs.append(PinPair(a_pin=fa[ka], b_pin=fb[kb]))
    if not pairs and not any("skipped" in n for n in notes):
        notes.append("The text holds no pair. Paste two columns: a pin of the first connector, a tab, a pin of the second.")  # fmt: skip
    return _proposal(pairs, fa, fb, notes)
