"""Pin allocation for one box connector. Rules (each placement records why it was chosen):

1. Pins the user locked are never moved.
2. Signals of a twisted pair go on adjacent pins; power and return are grouped.
3. Power goes first on the connector; other signals follow after the configured gap.
4. A previous generated allocation is kept when it is still valid (small changes, small diffs).
"""

from dataclasses import dataclass, field

from harness_design_studio.core.model import Connector, InterfaceType

CATEGORY_RANK = {"power": 0, "ground": 1}


@dataclass
class Request:
    interface_id: str
    itype: InterfaceType


@dataclass
class Allocation:
    # (interface_id, signal) -> pin id
    pins: dict[tuple[str, str], str] = field(default_factory=dict)
    reasons: dict[str, list[str]] = field(default_factory=dict)  # pin id -> lines
    errors: list[tuple[str, str]] = field(default_factory=list)  # (interface_id, message)
    warnings: list[tuple[str, str]] = field(default_factory=list)


def _allocate_fixed(
    connector: Connector,
    requests: list[Request],
    previous: dict[tuple[str, str], str],
    held: dict[tuple[str, str], str],
) -> Allocation:
    """The pinout is fixed by the unit's design: every signal goes to the free pin of that name.
    A signal the connector has no pin for is an error; nothing is placed on unnamed pins. A locked
    pin that already carries a signal of an interface keeps it (`held`): that signal is not
    placed again and the pin is not offered to anyone else."""
    result = Allocation()
    by_signal: dict[str, list[str]] = {}
    for p in connector.pins:
        if p.fixed and p.signal and not p.locked:
            by_signal.setdefault(p.signal, []).append(p.id)
    used: set[str] = set(held.values())
    for req in sorted(
        requests, key=lambda r: (CATEGORY_RANK.get(r.itype.category, 2), r.interface_id)
    ):
        missing = []
        picked: list[tuple[str, str]] = []
        for sig in (s.name for s in req.itype.signals):
            if (req.interface_id, sig) in held:
                continue  # already on its locked pin
            free = [pid for pid in by_signal.get(sig, []) if pid not in used]
            if not free:
                missing.append(sig)
                continue
            before = previous.get((req.interface_id, sig))
            chosen = before if before in free else free[0]  # keep the earlier pin: small diffs
            picked.append((sig, chosen))
            used.add(chosen)
        if missing:
            for _sig, pid in picked:  # all or nothing per interface
                used.discard(pid)
            result.errors.append(
                (
                    req.interface_id,
                    f"{connector.id} has a fixed pinout and no free pin named {', '.join(missing)}",
                )
            )
            continue
        for sig, pid in picked:
            result.pins[(req.interface_id, sig)] = pid
            result.reasons.setdefault(pid, []).append(
                f"pin-allocation: {sig} of {req.interface_id} uses pin {pid} because the pinout of {connector.id} is fixed by the unit design"
            )
        for sig in (s.name for s in req.itype.signals):
            if (locked_pin := held.get((req.interface_id, sig))) is not None:
                result.pins[(req.interface_id, sig)] = locked_pin
                result.reasons.setdefault(locked_pin, []).append(
                    f"pin-allocation: {sig} of {req.interface_id} stays on pin {locked_pin} because the pin is locked"
                )
    return result


def groups_of(itype: InterfaceType) -> list[tuple[str, list[str]]]:
    """Signal groups that must sit together: power as one block, else pairs, else singles."""
    if itype.category in ("power", "ground"):
        return [("power and return grouped", [s.name for s in itype.signals])]
    out: list[tuple[str, list[str]]] = []
    seen: dict[str, int] = {}
    for s in itype.signals:
        if s.pair is None:
            out.append(("single signal", [s.name]))
        elif s.pair in seen:
            out[seen[s.pair]][1].append(s.name)
        else:
            seen[s.pair] = len(out)
            out.append((f"pair {s.pair} on adjacent pins", [s.name]))
    return out


def allocate(
    connector: Connector,
    requests: list[Request],
    previous: dict[tuple[str, str], str],
    gap_pins: int,
    held: dict[tuple[str, str], str] | None = None,
    return_gap: int = 0,
) -> Allocation:
    """Allocate pins of `connector` for `requests`. Locked pins (and their signals) are untouched.
    `held` maps (interface, signal) to a locked pin that already carries that signal: it is used
    as it is instead of placing the signal on another pin. `return_gap` unassigned pins are left
    between the signals of a power interface (ECSS-Q-ST-30-11C 6.11.3 a)."""
    result = Allocation()
    held = held or {}
    if any(p.fixed and p.signal for p in connector.pins):  # even when a released harness holds some
        return _allocate_fixed(connector, requests, previous, held)
    order = [p.id for p in connector.pins]
    index = {pid: k for k, pid in enumerate(order)}
    taken = {p.id for p in connector.pins if p.locked}
    power_end = -1  # index of the last pin used by a power group
    ranked = sorted(
        requests, key=lambda r: (CATEGORY_RANK.get(r.itype.category, 2), r.interface_id)
    )
    for req in ranked:
        is_power = req.itype.category in ("power", "ground")
        min_start = 0 if is_power else (power_end + 1 + gap_pins if power_end >= 0 else 0)
        for why, signals in groups_of(req.itype):
            for s in [s for s in signals if (req.interface_id, s) in held]:
                pid = held[(req.interface_id, s)]
                result.pins[(req.interface_id, s)] = pid
                result.reasons.setdefault(pid, []).append(
                    f"pin-allocation: {s} of {req.interface_id} stays on pin {pid} because the pin is locked"
                )
            signals = [s for s in signals if (req.interface_id, s) not in held]
            if not signals:
                continue
            k = len(signals)
            chosen: list[str] | None = None
            reason = ""  # only set when a rule had to be relaxed
            spaced = is_power and return_gap > 0 and k > 1
            stride = 1 + return_gap if spaced else 1
            span = (k - 1) * stride + 1
            old = [previous.get((req.interface_id, s)) for s in signals]
            if all(o is not None and o in index and o not in taken for o in old):
                idxs = [index[o] for o in old if o is not None]
                if (
                    idxs == list(range(idxs[0], idxs[0] + k * stride, stride))
                    and idxs[0] >= min_start
                ):
                    chosen = [o for o in old if o is not None]  # kept: small changes, small diffs
                    if spaced:
                        taken.update(order[idxs[0] : idxs[-1] + 1])
            if chosen is None:
                for start in range(min_start, len(order) - span + 1):
                    block = order[start : start + span]
                    if not any(b in taken for b in block):
                        chosen = block[::stride]
                        if spaced:
                            taken.update(block)  # the pins between stay unassigned
                        break
            if chosen is None and spaced:
                result.warnings.append(
                    (
                        req.interface_id,
                        f"{', '.join(signals)} could not be separated by an unassigned contact on {connector.id}",
                    )
                )
                spaced = False
                for start in range(min_start, len(order) - k + 1):
                    block = order[start : start + k]
                    if not any(b in taken for b in block):
                        chosen = block
                        break
            if chosen is None:
                free = [pid for k2, pid in enumerate(order) if pid not in taken and k2 >= min_start]
                if len(free) >= k:
                    chosen, reason = (
                        free[:k],
                        "no adjacent block was free, so the pins are not adjacent",
                    )
                    result.warnings.append(
                        (
                            req.interface_id,
                            f"{', '.join(signals)} could not be placed on adjacent pins of {connector.id}",
                        )
                    )
                else:
                    result.errors.append(
                        (
                            req.interface_id,
                            f"{connector.id} has too few free pins for {', '.join(signals)} ({len(free)} free, {k} needed)",
                        )
                    )
                    continue
            for s, pid in zip(signals, chosen, strict=True):
                taken.add(pid)
                result.pins[(req.interface_id, s)] = pid
                result.reasons.setdefault(pid, []).append(
                    f"pin-allocation: {s} of {req.interface_id} ({why}{'; ' + reason if reason else ''})"
                )
            if is_power:
                power_end = max(power_end, max(index[p] for p in chosen))
    return result
