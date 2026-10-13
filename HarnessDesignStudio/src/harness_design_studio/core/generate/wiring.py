"""Which signal of one end connects to which signal of the other end.

Both ends carry the same interface type, each from its own point of view: an `out` signal of one
end goes to the matching `in` signal of the other (TX+ to RX+, DOUT+ to DIN+); `passive` and
`bidir` signals connect to the same-named signal. Matching is by position among the type's
outs and ins, which is why the starter types list them in matching order.
"""

from dataclasses import dataclass

from harness_design_studio.core.model import InterfaceType


@dataclass(frozen=True)
class Link:
    from_end: str  # "X" or "Y": the end whose signal drives (or the first end for passive signals)
    from_signal: str
    to_signal: str

    @property
    def label(self) -> str:
        return (
            self.from_signal
            if self.from_signal == self.to_signal
            else f"{self.from_signal}/{self.to_signal}"
        )


def links_of(itype: InterfaceType) -> tuple[list[Link], list[str]]:
    """Return the links for one interface and notes about signals that needed a fallback rule."""
    outs = [s.name for s in itype.signals if s.direction == "out"]
    ins = [s.name for s in itype.signals if s.direction == "in"]
    notes: list[str] = []
    links: list[Link] = []
    paired = min(len(outs), len(ins)) if (outs and ins) else 0
    if outs and ins and len(outs) != len(ins):
        notes.append(
            f"type {itype.id} has {len(outs)} out and {len(ins)} in signals; "
            "the extra ones connect to the same-named signal"
        )
    for k in range(paired):
        links.append(Link("X", outs[k], ins[k]))
        links.append(Link("Y", outs[k], ins[k]))
    # Unpaired directional signals (one-directional types such as analog) and passive/bidir
    # signals are single paths: the same name at both ends.
    leftover = {*outs[paired:], *ins[paired:]}
    for s in itype.signals:
        if s.direction in ("passive", "bidir") or s.name in leftover:
            links.append(Link("X", s.name, s.name))
    return links, notes
