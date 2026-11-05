"""Tactile connecting on the diagram: the cable in hand, as a state machine with no Qt in it.

A person picks up a cable at a port of a device, carries it over the diagram and puts it down on a
port of another device (or on the device itself, or on empty ground, where it stays as a loose
end until it is plugged in or dropped). The same hand picks up the end of a connection that is
plugged in already and plugs it in somewhere else. This module holds what is decided without a
screen: where a port is, which port the cable snaps to, whether a port can take it, the orthogonal
line of the rubber band, how fast the view scrolls when the cable nears its edge, and the states
a press, a drag, a click and Esc lead through.

    cable = Cable()
    cable.press(Port("OBC", "OBC-J01", 290, 90, "right"), (290, 90))
    cable.move((400, 120), scale=1.0)              # past the drag distance: the cable is in hand
    out = cable.release((520, 180), Landing("port", port=Port("RW1", "RW1-J02", 470, 200, "left")))
    # out.kind == "connect": the window that makes the connection does the rest

Nothing here changes a project. The scene (`gui/canvas_cable.py`) asks it what to do, draws what it
answers and carries out the outcome through the same operations as the Connect tool; a loose end
is a draft of the window only and is never saved, hashed or written.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field

from harness_design_studio.core import links
from harness_design_studio.core.edit import unit_connectors
from harness_design_studio.core.model import Project

# ---- the numbers of the gesture (screen pixels unless the name says scene) ----------------------
DRAG_PX = 4.0  # how far the pointer goes before a press is a drag
SNAP_PX = 14.0  # how near a port the cable end must be to snap to it
PLUG_PX = 9.0  # how near the end of a plugged-in connection a press picks it up
EDGE_PX = 36.0  # the strip along the edge of the view in which the view scrolls
SCROLL_PX = 22.0  # the most it scrolls in one step, at the very edge
OUT = 36.0  # how far the rubber band leaves a port before it turns (scene units)
END_GAP = 4.0  # between a device edge and the vertical piece of a line (scene units)
PLUG_DOT = 5.0  # the radius of the dot that marks a plugged-in end (scene units)
PLUG_OFFSET = 8.0  # how far out of its port the plug of a connection sits (scene units)

# the states
IDLE, PRESSED, CARRY, HOLD = "idle", "pressed", "carry", "hold"
# what a press began on
NEW, REPLUG, DRAFT = "new", "replug", "draft"
# why a port refuses the cable (the window words them)
SAME_DEVICE, FULL, PLUGGED, READ_ONLY = "same_device", "full", "plugged", "read_only"


@dataclass(frozen=True)
class Port:
    """A place a cable plugs in, in scene coordinates: the point on the device edge where the line
    meets it. `connector_id` is empty for the device as a whole (Guided and Quick: the tool picks
    the connector, as it does when two devices are clicked)."""

    unit_id: str
    connector_id: str = ""
    x: float = 0.0
    y: float = 0.0
    side: str = "right"  # the edge of the device it is on

    @property
    def key(self) -> tuple[str, str]:
        return (self.unit_id, self.connector_id)

    @property
    def at(self) -> tuple[float, float]:
        return (self.x, self.y)


@dataclass(frozen=True)
class Landing:
    """What is under the cable end: a `port` (snapped), a device `card` (not on a port) or
    nothing (`none`, empty ground)."""

    kind: str = "none"
    port: Port | None = None
    unit_id: str = ""  # the device of a card


@dataclass(frozen=True)
class Draft:
    """A loose end: the cable stays plugged in at `anchor` and ends in the air at `end`. UI only.
    `replaces` names the connection whose end was picked up (it stays in the project until the
    cable is plugged in elsewhere) and `replaces_end` which end ("a" or "b") that was."""

    anchor: Port
    end: tuple[float, float]
    replaces: str = ""
    replaces_end: str = ""


@dataclass(frozen=True)
class Outcome:
    """What a release (or a click, or Esc) leads to. `kind`:
    "none" nothing to do; "click" a press that never became a drag (`start` says on what);
    "connect" a new connection from `anchor` to `target`; "replug" the end `end` of connection
    `replaces` moves to `target`; "loose" the cable end stays in the air (the draft); "refused"
    `reason` says why the target cannot take it; "cancel" the cable was put away; "dropped" the
    draft was thrown away."""

    kind: str = "none"
    anchor: Port | None = None
    target: Port | None = None
    target_unit: str = ""  # a card: the device, the tool picks the connector
    replaces: str = ""
    end: str = ""
    reason: str = ""
    start: str = ""


# ---- what a port can take -----------------------------------------------------------------------


@dataclass(frozen=True)
class Occupancy:
    """How the connectors of a project are used, worked out once for a gesture: the pins that
    connections pair (per connector) and the connectors a cable plug of a harness sits on."""

    used: dict[str, int] = field(default_factory=dict)
    plugs: frozenset[str] = frozenset()

    @classmethod
    def of(cls, project: Project, ignoring: str = "") -> Occupancy:
        """`ignoring` is a connection whose pins do not count (the one being re-plugged)."""
        from harness_design_studio.core.integrity import mating_plugs

        used: dict[str, int] = {}
        index = links.link_pin_index(project)
        for connector_id, pins in index.items():
            held = [pin for pin, ids in pins.items() if any(i != ignoring for i in ids)]
            used[connector_id] = len(held)
        return cls(used, frozenset(mating_plugs(project.harnesses.values())))

    def free_pins(self, project: Project, connector_id: str) -> tuple[int, int]:
        """(free pins, all pins) of a connector."""
        c = project.connectors.get(connector_id)
        total = len(c.pins) if c is not None else 0
        return max(0, total - self.used.get(connector_id, 0)), total

    def device_free(self, project: Project, unit_id: str) -> tuple[int, int, int]:
        """(connectors, free pins, all pins) of a device."""
        conns = [c.id for c in unit_connectors(project, unit_id)]
        free = sum(self.free_pins(project, c)[0] for c in conns)
        total = sum(self.free_pins(project, c)[1] for c in conns)
        return len(conns), free, total


def refusal(project: Project, occ: Occupancy, anchor: Port, target: Port | None) -> str:
    """Why a cable held at `anchor` cannot be put on `target`; "" when it can. The reasons are
    those the connection itself would give: the same device, a connector with every pin in use,
    a connector with a cable plug on it already."""
    if target is None:
        return ""
    if target.unit_id == anchor.unit_id:
        return SAME_DEVICE
    if target.connector_id:
        if target.connector_id in occ.plugs:
            return PLUGGED
        free, total = occ.free_pins(project, target.connector_id)
        if total and not free:
            return FULL
        return ""
    conns, free_pins, total_pins = occ.device_free(project, target.unit_id)
    if conns and total_pins and not free_pins:
        return FULL
    return ""


# ---- geometry -----------------------------------------------------------------------------------


def nearest(
    ports: Sequence[Port], at: tuple[float, float], scale: float, *, radius_px: float = SNAP_PX
) -> Port | None:
    """The port nearest to `at` within `radius_px` screen pixels (at the zoom `scale`), else None.
    A tie goes to the first port in the list, so the result is the same every time."""
    reach = radius_px / max(scale, 1e-9)
    best: Port | None = None
    best_d = reach * reach
    for p in ports:
        d = (p.x - at[0]) ** 2 + (p.y - at[1]) ** 2
        if d <= best_d and (best is None or d < best_d):
            best, best_d = p, d
    return best


def route(a: Port, to: tuple[float, float]) -> list[tuple[float, float]]:
    """The rubber band from a port to a point: out of the port's edge, then across in right
    angles, as the lines of the connections run. Facing the port it meets the point halfway;
    behind it, it goes round by `OUT`."""
    (xa, ya), (xb, yb) = a.at, to
    sign = 1.0 if a.side == "right" else -1.0
    if (xb - xa) * sign > 2 * END_GAP:
        mid = (xa + xb) / 2
        return [a.at, (mid, ya), (mid, yb), to]
    out = xa + sign * OUT
    out = max(out, xb + sign * END_GAP) if sign > 0 else min(out, xb + sign * END_GAP)
    return [a.at, (out, ya), (out, yb), to]


def plug_spot(poly: Sequence[tuple[float, float]], first: bool) -> tuple[float, float]:
    """Where the plug of a plugged-in end sits: a little way out along the line from the port, at
    the first end of `poly` (`first`) or its last. A press here picks the end up."""
    (x, y), (nx, ny) = (poly[0], poly[1]) if first else (poly[-1], poly[-2])
    dx, dy = nx - x, ny - y
    length = (dx * dx + dy * dy) ** 0.5
    if not length:
        return (x, y)
    return (x + dx / length * PLUG_OFFSET, y + dy / length * PLUG_OFFSET)


def plug_direction(path: Sequence[tuple[float, float]]) -> tuple[float, float]:
    """The unit direction of the last piece of a path (where the plug end points)."""
    (x0, y0), (x1, y1) = path[-2], path[-1]
    dx, dy = x1 - x0, y1 - y0
    length = (dx * dx + dy * dy) ** 0.5
    return (dx / length, dy / length) if length else (1.0, 0.0)


def edge_scroll(
    width: float,
    height: float,
    at: tuple[float, float],
    *,
    margin: float = EDGE_PX,
    top: float = SCROLL_PX,
) -> tuple[float, float]:
    """How far to scroll the view, in pixels, for a pointer at `at` in a viewport of this size:
    nothing inside the middle, faster the nearer the pointer is to an edge (and past it), at most
    `top`. A positive x scrolls to the right, a positive y down."""

    def axis(pos: float, size: float) -> float:
        if pos < margin:
            return -top * min(1.0, (margin - pos) / margin)
        if pos > size - margin:
            return top * min(1.0, (pos - (size - margin)) / margin)
        return 0.0

    return (axis(at[0], width), axis(at[1], height))


# ---- the state machine --------------------------------------------------------------------------


class Cable:
    """The cable in hand (`state`) and the loose end that may be left behind (`draft`).

    `press` on a start spot (a port, the end of a connection, the loose end) begins the gesture;
    `move` takes it over once the pointer went `DRAG_PX`; `release` ends a drag or a click;
    `cancel` (Esc) puts away what is in hand and throws the draft away. A click on a loose end
    picks it up and holds it (`HOLD`: it follows the pointer without the button) until the next
    click puts it down."""

    def __init__(self) -> None:
        self.state = IDLE
        self.draft: Draft | None = None
        self.start = ""  # NEW, REPLUG or DRAFT: what the gesture began on
        self.anchor: Port | None = None  # the end that stays plugged in
        self.replaces = ""
        self.replaces_end = ""
        self.pos = (0.0, 0.0)  # the cable end, scene coordinates
        self._down = (0.0, 0.0)  # where the press was (scene)
        self._moved_px = 0.0
        self.target: Port | None = None  # the port the cable end has snapped to
        self.card = ""  # the device the cable end is over (not on a port)

    # ---- asking ------------------------------------------------------------------------------
    @property
    def active(self) -> bool:
        """A cable is being carried (the button is down on a drag, or it is held)."""
        return self.state in (CARRY, HOLD)

    @property
    def busy(self) -> bool:
        return self.state != IDLE

    # ---- the gesture -------------------------------------------------------------------------
    def press(
        self,
        anchor: Port,
        at: tuple[float, float],
        *,
        start: str = NEW,
        replaces: str = "",
        end: str = "",
    ) -> None:
        """The button went down on a start spot. `anchor` is the end that stays where it is."""
        self.state, self.start, self.anchor = PRESSED, start, anchor
        if start != DRAFT:
            self.draft = None  # one loose cable at a time
        self.replaces, self.replaces_end = replaces, end
        self.pos = self._down = at
        self._moved_px = 0.0
        self.target, self.card = None, ""

    def move(self, at: tuple[float, float], *, scale: float = 1.0) -> bool:
        """The pointer moved (to scene point `at`). True once the cable is in hand."""
        if self.state == PRESSED:
            self._moved_px = max(
                self._moved_px,
                ((at[0] - self._down[0]) ** 2 + (at[1] - self._down[1]) ** 2) ** 0.5 * scale,
            )
            if self._moved_px < DRAG_PX:
                return False
            self.state = CARRY
        if self.state in (CARRY, HOLD):
            self.pos = at
            return True
        return False

    def over(self, landing: Landing) -> None:
        """Say what is under the cable end now (the scene looks it up for each move)."""
        self.target = landing.port if landing.kind == "port" else None
        self.card = landing.unit_id if landing.kind == "card" else ""

    def release(
        self,
        at: tuple[float, float],
        landing: Landing,
        *,
        refused: str = "",
        unchanged: bool = False,
    ) -> Outcome:
        """The button came up. `landing` is what is under the cable end; `refused` is the reason
        `refusal` gave for it ("" when it fits); `unchanged` says the end was put back on the
        connector it was picked up from. Returns what to do."""
        was = self.state
        start, anchor = self.start, self.anchor
        replaces, end = self.replaces, self.replaces_end
        if was == PRESSED:  # never became a drag: a click
            if start == DRAFT:
                self.state, self.pos = HOLD, at  # the loose end is picked up and follows
                return Outcome("click", anchor, start=start)
            self._reset()
            return Outcome("click", anchor, replaces=replaces, end=end, start=start)
        if was not in (CARRY, HOLD) or anchor is None:
            self._reset()
            return Outcome("none")
        return self._put_down(at, landing, refused, unchanged)

    def put_down(
        self,
        at: tuple[float, float],
        landing: Landing,
        *,
        refused: str = "",
        unchanged: bool = False,
    ) -> Outcome:
        """A click while the cable is held: it goes down where it is."""
        if self.state != HOLD or self.anchor is None:
            return Outcome("none")
        return self._put_down(at, landing, refused, unchanged)

    def _put_down(
        self, at: tuple[float, float], landing: Landing, refused: str, unchanged: bool
    ) -> Outcome:
        anchor, replaces, end = self.anchor, self.replaces, self.replaces_end
        if anchor is None:
            return Outcome("none")
        target = landing.port if landing.kind == "port" else None
        target_unit = landing.unit_id if landing.kind == "card" else ""
        if landing.kind == "none":
            self.draft = Draft(anchor, at, replaces, end)
            self._reset()
            return Outcome("loose", anchor, replaces=replaces, end=end)
        if refused:
            self._reset(keep_draft=True)
            return Outcome("refused", anchor, target, target_unit, replaces, end, refused)
        self._reset(keep_draft=False)
        if unchanged:  # put back where it came from: nothing changes
            return Outcome("cancel", anchor, target)
        kind = "replug" if replaces else "connect"
        return Outcome(kind, anchor, target, target_unit, replaces, end)

    def cancel(self) -> Outcome:
        """Esc: what is in hand is put away (a re-plugged connection was never touched) and the
        draft is thrown away."""
        had = self.state != IDLE or self.draft is not None
        dropped = self.draft is not None
        self._reset()
        self.draft = None
        if not had:
            return Outcome("none")
        return Outcome("dropped" if dropped else "cancel")

    def drop_draft(self) -> bool:
        """Throw the loose end away; True when there was one."""
        had = self.draft is not None
        self.draft = None
        return had

    def grab_draft(self, at: tuple[float, float]) -> bool:
        """Begin carrying the draft (a press on its loose end)."""
        d = self.draft
        if d is None:
            return False
        self.press(d.anchor, at, start=DRAFT, replaces=d.replaces, end=d.replaces_end)
        return True

    def _reset(self, *, keep_draft: bool = True) -> None:
        self.state, self.start = IDLE, ""
        self.target, self.card = None, ""
        self.replaces = self.replaces_end = ""
        self.anchor = None
        if not keep_draft:
            self.draft = None

    # ---- what is drawn -----------------------------------------------------------------------
    def shown(self) -> tuple[Port, tuple[float, float]] | None:
        """The cable to draw: (anchor, loose end). While carrying it ends at the pointer (or on
        the port it snapped to); at rest it is the draft."""
        if self.active and self.anchor is not None:
            end = self.target.at if self.target is not None else self.pos
            return self.anchor, end
        if self.draft is not None:
            return self.draft.anchor, self.draft.end
        return None
