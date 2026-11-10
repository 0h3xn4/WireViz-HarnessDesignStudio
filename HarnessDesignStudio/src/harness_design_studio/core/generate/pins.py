# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Pin allocation for one box connector. Rules (each placement records why it was chosen):

1. Pins the user locked are never moved.
2. Signals of a twisted pair go on adjacent pins; power and return are grouped.
3. Power goes first on the connector; other signals follow after the configured gap.
4. A previous generated allocation is kept when it is still valid (small changes, small diffs).
"""

from dataclasses import dataclass, field

from harness_design_studio.core import settings
from harness_design_studio.core.model import Connector, InterfaceType, Project

DEFAULT_ORDER = ("power", "ground")  # the interface categories allocated first, in this order

# The model that picks the run of pins for a group of signals (`model.pin_fit_strategy`, S3b).
# `first_fit` is what the tool always did and is the default.
STRATEGIES = ("first_fit", "last_fit", "spread")
DEFAULT_STRATEGY = "first_fit"
STRATEGY_TEXT = {
    "first_fit": "the first free run of pins, from the first pin up",
    "last_fit": "the last free run of pins, from the last pin down (power at the end, the signals below it)",
    "spread": "the first free run of pins that has a free pin on each side of it, apart from the pins of its own interface (first fit when there is no room)",
}


def strategy(project: Project) -> str:
    """The pin fit strategy in force: the one function generation and the explanation call."""
    value = settings.effective(project, "model", "pin_fit_strategy").value
    return str(value) if value in STRATEGIES else DEFAULT_STRATEGY


def earlier_strategy(project: Project) -> str:
    """The fit the harnesses were last generated with: a non-default one is recorded in the
    generation record (`model:pin_fit_strategy`); no entry means the default."""
    lines = (
        project.generation.provenance.get("model:pin_fit_strategy") if project.generation else None
    )
    name = lines[0].split(":", 1)[0] if lines else DEFAULT_STRATEGY
    return name if name in STRATEGIES else DEFAULT_STRATEGY


def _rank(categories: tuple[str, ...], category: str) -> int:
    """The place of a category in the order of allocation: its index in `categories`, after which
    every other category comes (model.pin_allocation_categories)."""
    return categories.index(category) if category in categories else len(categories)


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
    categories: tuple[str, ...] = DEFAULT_ORDER,
    fit: str = DEFAULT_STRATEGY,
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
        requests, key=lambda r: (_rank(categories, r.itype.category), r.interface_id)
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
            # keep the earlier pin: small diffs; else the first free pin of that name (the last, for last_fit)
            chosen = before if before in free else free[-1 if fit == "last_fit" else 0]
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


def groups_of(
    itype: InterfaceType, categories: tuple[str, ...] = DEFAULT_ORDER
) -> list[tuple[str, list[str]]]:
    """Signal groups that must sit together: power as one block, else pairs, else singles."""
    if itype.category in categories:
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
    categories: tuple[str, ...] = DEFAULT_ORDER,
    strategy: str = DEFAULT_STRATEGY,
) -> Allocation:
    """Allocate pins of `connector` for `requests`. Locked pins (and their signals) are untouched.
    `held` maps (interface, signal) to a locked pin that already carries that signal: it is used
    as it is instead of placing the signal on another pin. `return_gap` unassigned pins are left
    between the signals of a power interface (ECSS-Q-ST-30-11C 6.11.3 a). `strategy` is the model
    that picks the run of pins (`model.pin_fit_strategy`, see STRATEGY_TEXT)."""
    result = Allocation()
    held = held or {}
    if strategy not in STRATEGIES:
        strategy = DEFAULT_STRATEGY
    if any(p.fixed and p.signal for p in connector.pins):  # even when a released harness holds some
        return _allocate_fixed(connector, requests, previous, held, categories, strategy)
    order = [p.id for p in connector.pins]
    index = {pid: k for k, pid in enumerate(order)}
    taken = {p.id for p in connector.pins if p.locked}
    owner = {p.id: p.interface_id or "" for p in connector.pins if p.locked}  # "" = no interface
    power_end = -1  # index of the last pin used by a power group
    power_start = len(order)  # index of the first pin used by a power group (last_fit)
    ranked = sorted(requests, key=lambda r: (_rank(categories, r.itype.category), r.interface_id))

    def place(req: Request, fit: str) -> tuple[bool, bool]:
        """Place every group of one interface by the fit `fit`. Returns (failed, no_room): no_room
        is only true for `spread`, when a group has no run of pins with a free pin on each side."""
        nonlocal power_end, power_start
        is_power = req.itype.category in categories
        down = fit == "last_fit"
        min_start = 0 if is_power or down else (power_end + 1 + gap_pins if power_end >= 0 else 0)
        limit = (
            power_start - gap_pins
            if down and not is_power and power_start < len(order)
            else len(order)
        )  # last_fit: the signals lie below the power group, the gap between them
        note = "" if fit == DEFAULT_STRATEGY else f"; {fit.replace('_', ' ')}"
        for why, signals in groups_of(req.itype, categories):
            for s in [s for s in signals if (req.interface_id, s) in held]:
                pid = held[(req.interface_id, s)]
                if is_power and pid in index:  # a locked power pin counts for the gap as well
                    power_end = max(power_end, index[pid])
                    power_start = min(power_start, index[pid])
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
                    and idxs[-1] < limit
                ):
                    chosen = [o for o in old if o is not None]  # kept: small changes, small diffs
                    if spaced:
                        taken.update(order[idxs[0] : idxs[-1] + 1])
                        owner.update(dict.fromkeys(order[idxs[0] : idxs[-1] + 1], req.interface_id))
            if chosen is None:
                for start in starts(min_start, limit, span, down):
                    block = order[start : start + span]
                    if any(b in taken for b in block):
                        continue
                    if fit == "spread" and not apart(start, span, req.interface_id):
                        continue
                    chosen = block[::stride]
                    if spaced:
                        taken.update(block)  # the pins between stay unassigned
                        owner.update(dict.fromkeys(block, req.interface_id))
                    break
            if chosen is None and fit == "spread":
                return False, True
            if chosen is None and spaced:
                result.warnings.append(
                    (
                        req.interface_id,
                        f"{', '.join(signals)} could not be separated by an unassigned contact on {connector.id}",
                    )
                )
                spaced = False
                for start in starts(min_start, limit, k, down):
                    block = order[start : start + k]
                    if not any(b in taken for b in block):
                        chosen = block
                        break
            if chosen is None:
                free = [
                    pid
                    for k2, pid in enumerate(order)
                    if pid not in taken and min_start <= k2 < limit
                ]
                if len(free) >= k:
                    chosen, reason = (
                        free[-k:] if down else free[:k],
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
                    return True, False
            for s, pid in zip(signals, chosen, strict=True):
                taken.add(pid)
                owner[pid] = req.interface_id
                result.pins[(req.interface_id, s)] = pid
                result.reasons.setdefault(pid, []).append(
                    f"pin-allocation: {s} of {req.interface_id} ({why}{'; ' + reason if reason else ''}{note})"
                )
            if is_power:
                power_end = max(power_end, max(index[p] for p in chosen))
                power_start = min(power_start, min(index[p] for p in chosen))
        return False, False

    def apart(start: int, span: int, interface_id: str) -> bool:
        """The pin before and the pin after a run belong to no other interface (spread)."""
        before, after = start - 1, start + span
        return all(
            owner.get(order[j], interface_id) == interface_id
            for j in (before, after)
            if 0 <= j < len(order)
        )

    for req in ranked:
        taken_before, owner_before = set(taken), dict(owner)
        ends_before = (power_end, power_start)
        n_warnings, n_errors = len(result.warnings), len(result.errors)
        for fit in ("spread", "first_fit") if strategy == "spread" else (strategy,):
            failed, no_room = place(req, fit)
            if not failed and not no_room:
                break
            _forget(result, req.interface_id)  # all or nothing per interface
            taken.clear()
            taken.update(taken_before)
            owner.clear()
            owner.update(owner_before)
            power_end, power_start = ends_before
            if no_room:  # no gap fits: first fit, as the model says
                del result.warnings[n_warnings:]
                del result.errors[n_errors:]
                continue
            break
    return result


def starts(low: int, limit: int, span: int, down: bool) -> range:
    """The first indexes a run of `span` pins can start at, in the order a fit looks at them:
    from `low` up, or from the last place that fits down. `limit` is one past the last pin the run
    may use."""
    last = limit - span
    return range(last, low - 1, -1) if down else range(low, last + 1)


def _forget(result: Allocation, interface_id: str) -> None:
    """Take every pin of one interface out of the result again (its other pins stay free)."""
    for key in [k for k in result.pins if k[0] == interface_id]:
        pid = result.pins.pop(key)
        if pid in result.reasons:
            result.reasons[pid] = [
                line for line in result.reasons[pid] if f" of {interface_id} " not in line
            ]
            if not result.reasons[pid]:
                del result.reasons[pid]
