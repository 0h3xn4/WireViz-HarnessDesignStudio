# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Why a signal has this pin, why a wire is in this harness, and why a connector is this connector
(D-191, S1).

The pin allocation, the segmentation and the choice of a connector are decisions of the generator.
This module does not decide again: it reads the pins, groups and settings the generator left in the
design and calls the very functions the generator calls (`pins._rank`, `pins.groups_of`,
`segmentation.segment`, `segmentation._class_of`, `edit.free_connectors`), and it quotes the reasons
generation recorded (the Why tab: `core.why`). The derivations are:

    pin-allocation       why a signal is on a pin of a device connector (the order, the gaps, locks)
    segmentation         why the interfaces of a harness share it (the mode, the chain, the zones)
    connector-choice     why a connector is the connector of an interface, or the mating part of one
"""

from harness_design_studio.core import connector_choice, edit, settings, why
from harness_design_studio.core.derive import Derivation, Input, Step, origin_text, text_step
from harness_design_studio.core.edit import carries, unit_connectors
from harness_design_studio.core.generate import pins as pinmod
from harness_design_studio.core.generate import segmentation
from harness_design_studio.core.model import (
    Connector,
    Harness,
    InterfaceInstance,
    Project,
    Wire,
)

SHOWN = 8  # how many names a line gives before "and N more": no result depends on it


def _gen(project: Project, key: str) -> object:
    c = project.config.get("generation")
    return c.values.get(key) if c is not None else None


def _names(items: list[str]) -> str:
    if not items:
        return "none"
    return ", ".join(items[:SHOWN]) + (
        f" and {len(items) - SHOWN} more" if len(items) > SHOWN else ""
    )


def _num(v: object) -> float | None:
    return float(v) if isinstance(v, int | float) and not isinstance(v, bool) else None


def box_of(project: Project, connector_id: str) -> Connector | None:
    """The device connector of an ID that is either a device connector or the cable connector that
    plugs into one (a pin ID is the same on both)."""
    if connector_id in project.connectors:
        return project.connectors[connector_id]
    for h in project.harnesses.values():
        for c in h.connectors:
            if c.id == connector_id:
                return project.connectors.get(c.mates_with or "")
    return None


# ---- pin allocation ------------------------------------------------------------------------------


def _pin_ranks(
    project: Project, box: Connector, categories: tuple[str, ...]
) -> list[tuple[int, str, str, list[str]]]:
    """(rank, interface ID, category, pin IDs) of every interface that has pins on the connector, in
    the order the allocator places them: by the rank of the category, then the interface ID."""
    found: dict[str, list[str]] = {}
    for p in box.pins:
        if p.interface_id:
            found.setdefault(p.interface_id, []).append(p.id)
    out: list[tuple[int, str, str, list[str]]] = []
    for iid, pin_ids in found.items():
        i = project.interfaces.get(iid)
        t = project.interface_types.get(i.type_id) if i else None
        category = t.category if t else ""
        out.append((pinmod._rank(categories, category), iid, category, pin_ids))
    return sorted(out, key=lambda x: (x[0], x[1]))


def pin_allocation_derivation(project: Project, connector_id: str, pin_id: str) -> Derivation:
    """Why a pin of a device connector carries the signal it carries (or nothing)."""
    box = box_of(project, connector_id)
    pin = next((p for p in box.pins if p.id == pin_id), None) if box is not None else None
    if box is None or pin is None:
        return Derivation(
            "pin-allocation",
            f"Pin {pin_id} of {connector_id}",
            "Pin allocation",
            None,
            "",
            "pin = the first free pins of the connector, in the order of the categories",
            assumptions=("A-PIN-ORDER", "A-PIN-FIRST-FIT"),
            missing=(f"the pin {pin_id} of connector {connector_id}",),
        )
    categories = settings.names(project, "model", "pin_allocation_categories")
    cat_origin = origin_text(project, "model", "pin_allocation_categories")
    gap_signal_raw = _gen(project, "power_signal_gap_pins")
    gap_signal = int(_num(gap_signal_raw) or 0)
    gap_return_raw = _gen(project, "power_return_gap_pins")
    gap_return = int(_num(gap_return_raw) or 0)
    i = project.interfaces.get(pin.interface_id or "")
    t = project.interface_types.get(i.type_id) if i else None
    category = t.category if t else ""
    rank = pinmod._rank(categories, category) if t else None
    is_power = category in categories
    order = [p.id for p in box.pins]
    index = order.index(pin.id)
    inputs: list[Input] = [
        Input("Signal", pin.signal, "", f"pin {pin.id} of {box.id}"),
        Input("Interface", pin.interface_id, "", f"pin {pin.id} of {box.id}"),
        Input(
            "Interface category",
            category or None,
            "",
            f"interface type {t.id}: category" if t else "no interface on the pin",
        ),
        Input(
            "Order of the categories",
            ", ".join(categories) or "none",
            "",
            f"config/model.json: pin_allocation_categories ({cat_origin}); every other category follows",
        ),
        Input(
            "Pin is locked",
            "yes" if pin.locked else "no",
            "",
            f"pin {pin.id}: Locked (a locked pin is never moved)",
        ),
        Input(
            "Pinout is fixed by the device design",
            "yes" if pin.fixed else "no",
            "",
            f"pin {pin.id}: Fixed (a fixed pinout gives the signal the free pin of its name)",
        ),
        Input(
            "Pins between power and signal",
            gap_signal,
            "pins",
            "config/generation.json: power_signal_gap_pins"
            + ("" if gap_signal_raw is not None else " (not set: 0 used, a placeholder)"),
        ),
        Input(
            "Contacts between power and return",
            gap_return,
            "pins",
            "config/generation.json: power_return_gap_pins"
            + ("" if gap_return_raw is not None else " (not set: 0 used)"),
        ),
    ]
    fit = pinmod.strategy(project)
    if fit != pinmod.DEFAULT_STRATEGY:  # the default keeps its text: only another model is named
        inputs.append(
            Input(
                "Pin fit strategy (the model in force)",
                fit,
                "",
                f"config/model.json: pin_fit_strategy ({origin_text(project, 'model', 'pin_fit_strategy')})",
            )
        )
    steps: list[Step] = [
        Step(
            "Position on the connector",
            f"pin {index + 1} of {len(order)} in the pin list",
            index + 1,
            "",
        )
    ]
    if i is not None and t is not None and pin.signal:
        group_why = next(
            (w for w, names in pinmod.groups_of(t, categories) if pin.signal in names),
            "single signal",
        )
        steps.append(
            text_step(
                "Group of the signal",
                f"{pin.signal} of {i.id}: {group_why}"
                + ("; the power group counts as one block" if is_power else ""),
                group_why,
                "",
            )
        )
        steps.append(
            text_step(
                "Place of the category in the order",
                f"{category}, against the list in model.pin_allocation_categories",
                f"number {rank + 1} of the listed categories"
                if rank is not None and is_power
                else "not listed: after all the listed ones",
            )
        )
    ranks = _pin_ranks(project, box, categories)
    steps.append(
        Step(
            "Order the connector was filled in",
            "; ".join(f"{iid} ({cat}) pins {', '.join(ids)}" for _r, iid, cat, ids in ranks)
            or "no interface has a pin on it",
            len(ranks),
            "interfaces",
        )
    )
    ahead = box.pins[:index]
    free_ahead = [p.id for p in ahead if p.interface_id is None and not p.signal and not p.locked]
    taken_ahead = [p.id for p in ahead if p.interface_id is not None or p.signal]
    if fit != pinmod.DEFAULT_STRATEGY:
        steps.append(
            text_step(
                "Model in force",
                f"{fit}: {pinmod.STRATEGY_TEXT[fit]}",
                "a group of signals takes " + pinmod.STRATEGY_TEXT[fit],
            )
        )
    steps.append(
        text_step(
            "Pins ahead of it in the list",
            f"{len(taken_ahead)} carry an interface and {len(free_ahead)} are unassigned"
            + (f" ({_names(free_ahead)})" if free_ahead else ""),
            f"{fit.replace('_', ' ')}: "
            + (
                "an unassigned pin ahead is a gap, a spare pin, or a place kept for a locked or earlier choice"
                if free_ahead
                else "nothing free lies ahead of it"
            ),
        )
    )
    lines = why.reasons(project, "pin", f"{box.id}.{pin.id}")
    for r in lines:
        steps.append(text_step("Recorded when it was generated", r.line, r.rule or "recorded", ""))
    if pin.locked:
        what = f"{pin.signal or 'nothing'} stays on pin {pin.id}: the pin is locked"
    elif pin.interface_id is None and not pin.signal:
        what = "unassigned"
    elif pin.signal:
        what = f"{pin.signal} of {pin.interface_id or 'no interface'} on pin {pin.id}"
    else:
        what = "unassigned"
    return Derivation(
        "pin-allocation",
        f"Pin {pin.id} of {box.id}",
        "Pin allocation",
        None,
        "",
        "the interfaces are placed in the order of their category (power first), each group on the first free pins after the gap; locked pins stay"
        if fit == pinmod.DEFAULT_STRATEGY
        else "the interfaces are placed in the order of their category (power first), each group on "
        + pinmod.STRATEGY_TEXT[fit]
        + "; locked pins stay",
        tuple(inputs),
        tuple(steps),
        None,
        ("A-PIN-ORDER", "A-PIN-FIRST-FIT"),
        "The order and the gaps are the settings generation reads (core/generate/pins.py: allocate); "
        "the lines recorded when it ran are the ones of the Why tab. A pin allocated before a setting "
        "was changed keeps its place until the harnesses are generated again.",
        text=what,
    )


def pin_derivations_of_wire(project: Project, h: Harness, w: Wire) -> list[Derivation]:
    """The pins of the device connectors at the two ends of a wire."""
    cables = {c.id: c for c in h.connectors}
    out: list[Derivation] = []
    for cid, pid in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
        cable = cables.get(cid)
        if cable is not None and cable.mates_with in project.connectors:
            out.append(pin_allocation_derivation(project, cable.mates_with, pid))
    return out


# ---- segmentation --------------------------------------------------------------------------------


def _interface_row(
    project: Project, seg_cfg: dict[str, object], sep_cfg: dict[str, object], iid: str
) -> str:
    i = project.interfaces.get(iid)
    if i is None or i.type_id not in project.interface_types or len(i.endpoints) != 2:
        return "not found, or not between two devices"
    a, b = i.endpoints
    cls = segmentation._class_of(project, i, seg_cfg, sep_cfg)
    chain = (
        i.redundancy
        if sep_cfg.get("forbid_nominal_with_redundant") is not False
        else "(chains not kept apart)"
    )
    za = project.units[a.unit_id].zone if a.unit_id in project.units else None
    zb = project.units[b.unit_id].zone if b.unit_id in project.units else None
    return (
        f"{a.unit_id} [{za or 'no zone'}] {a.connector_id} to {b.unit_id} [{zb or 'no zone'}] {b.connector_id}; "
        f"chain {chain}, class {cls}"
    )


def segmentation_derivation(project: Project, h: Harness) -> Derivation:
    """Why the interfaces of the harness share it, and why not more or fewer of them do."""
    seg = segmentation.segment(project)
    group = next((g for g in seg.groups if g.key == h.group_key), None) if h.group_key else None
    seg_cfg = segmentation._cfg(project, "segmentation")
    sep_cfg = segmentation._cfg(project, "segregation")
    mode = settings.choice(project, "segmentation", "mode")
    flags = [
        (
            "forbid_nominal_with_redundant",
            settings.effective(project, "segregation", "forbid_nominal_with_redundant"),
        ),
        (
            "forbid_pyro_with_other",
            settings.effective(project, "segregation", "forbid_pyro_with_other"),
        ),
    ]
    pairs = settings.effective(project, "segregation", "category_pairs_to_separate")
    interfaces = sorted(h.interfaces)
    inputs: list[Input] = [
        Input(
            "Segmentation mode",
            mode,
            "",
            f"config/segmentation.json: mode ({origin_text(project, 'segmentation', 'mode')}"
            + (
                ""
                if str(seg_cfg.get("mode", mode)) == mode
                else f"; '{seg_cfg.get('mode')}' is not a mode, the default is used"
            )
            + ")",
        ),
        *[
            Input(
                f"Keep apart: {key}",
                "yes" if e.value is not False else "no",
                "",
                f"config/segregation.json: {key} ({origin_text(project, 'segregation', key)})",
            )
            for key, e in flags
        ],
        Input(
            "Category pairs kept apart",
            settings.display(pairs.value),
            "",
            f"config/segregation.json: category_pairs_to_separate ({origin_text(project, 'segregation', 'category_pairs_to_separate')})",
        ),
    ]
    for iid in interfaces:
        inputs.append(
            Input(
                f"Interface {iid}",
                _interface_row(project, seg_cfg, sep_cfg, iid),
                "",
                "the design (interface, device and zone)",
            )
        )
    steps: list[Step] = [
        text_step("Group key of the harness", h.group_key or "(none)", h.group_key or "(none)", "")
    ]
    if group is not None:
        steps.append(
            text_step(
                "Harness name made from the group", f"{group.mode}: {group.label}", group.label, ""
            )
        )
        steps.append(
            Step(
                "Interfaces in the group",
                _names(list(group.interface_ids)),
                len(group.interface_ids),
                "interfaces",
            )
        )
        if group.zones is not None:
            steps.append(
                text_step(
                    "Zones of the group",
                    f"{group.zones[0] or 'no zone'} and {group.zones[1] or 'no zone'}",
                    "per zone pair",
                    "",
                )
            )
        steps.append(
            text_step(
                "Chain of the group",
                group.chain or "nominal and redundant may share",
                group.chain or "mixed",
                "",
            )
        )
    for note in seg.notes:
        if h.name in note or (group is not None and group.label in note):
            steps.append(text_step("Note of the segmentation", note, "note", ""))
    lines = [r.line for r in why.reasons(project, "harness", h.id) if r.rule == "segmentation"]
    for line in lines:
        steps.append(text_step("Recorded when it was generated", line, "recorded", ""))
    if not h.generated:
        text = "drawn by hand: no segmentation rule made this harness"
        missing: tuple[str, ...] = ()
    elif group is None:
        text = "no group of the current design matches this harness"
        missing = (
            "generate the harnesses again: the design changed since this harness was generated",
        )
    else:
        text = f"{len(group.interface_ids)} interface(s) share it: {group.label}"
        missing = ()
    return Derivation(
        "segmentation",
        f"Harness {h.id}",
        "Why these interfaces share a harness",
        None,
        "",
        "harness = the interfaces with the same key: the chain, the class, and the pair of connectors, devices or zones the mode names",
        tuple(inputs),
        tuple(steps),
        None,
        ("A-SEGMENT-MODE", "A-ZONE"),
        "The group is the one segmentation.segment makes today; the harness keeps the key it was "
        "generated for, so a changed design is named above. Zones are a field of each device.",
        missing,
        text=text,
    )


def interface_segmentation(project: Project, interface_id: str) -> list[Derivation]:
    """Which harness carries the interface and why, or why it is carried by none."""
    out = [
        segmentation_derivation(project, h)
        for h in sorted(project.harnesses.values(), key=lambda x: x.id)
        if interface_id in h.interfaces
    ]
    if out:
        return out
    seg = segmentation.segment(project)
    skipped = next((s for s in seg.skipped if s.interface_id == interface_id), None)
    text = (
        f"in no harness: {skipped.reason}"
        if skipped is not None
        else "in no harness yet: generate the harnesses"
    )
    return [
        Derivation(
            "segmentation",
            f"Interface {interface_id}",
            "Why these interfaces share a harness",
            None,
            "",
            "an interface is carried by a harness once it has two devices, two connectors and a type",
            (
                Input(
                    "Segmentation mode",
                    settings.choice(project, "segmentation", "mode"),
                    "",
                    "config/segmentation.json: mode",
                ),
            ),
            assumptions=("A-SEGMENT-MODE", "A-ZONE"),
            reference="segmentation.segment lists the interfaces it skips with the reason.",
            text=text,
        )
    ]


# ---- the choice of a connector ---------------------------------------------------------------------


def connector_choice_derivation(project: Project, connector_id: str) -> Derivation:
    """Why this connector: chosen for an interface of a device (by you or by the tool), or the
    cable end that plugs into one (the mating part of the library)."""
    box = project.connectors.get(connector_id)
    if box is not None:
        return _box_choice(project, box)
    for h in project.harnesses.values():
        for c in h.connectors:
            if c.id == connector_id:
                return _cable_choice(project, h, c)
    return Derivation(
        "connector-choice",
        f"Connector {connector_id}",
        "Choice of connector",
        None,
        "",
        "the first free connector of the device that carries the interface type",
        assumptions=("A-CONNECTOR-CHOICE",),
        missing=(f"connector {connector_id}",),
    )


def _box_choice(project: Project, box: Connector) -> Derivation:
    ends = [
        (i, e)
        for i in sorted(project.interfaces.values(), key=lambda x: x.id)
        for e in i.endpoints
        if e.connector_id == box.id
    ]
    inputs: list[Input] = [
        Input("Device", box.unit_id, "", f"connector {box.id}"),
        Input("Part", box.part_id, "", f"connector {box.id}: part"),
        Input("Carries", ", ".join(box.carries) or "any type", "", f"connector {box.id}: Carries"),
    ]
    steps: list[Step] = []
    method = connector_choice.method(project)
    if (
        method != connector_choice.DEFAULT_METHOD
    ):  # the default keeps its text: only another model is named
        inputs.append(
            Input(
                "Connector choice (the model in force)",
                method,
                "",
                f"config/model.json: connector_choice ({origin_text(project, 'model', 'connector_choice')})",
            )
        )
    for i, e in ends:
        siblings = [c.id for c in unit_connectors(project, e.unit_id) if carries(c, i.type_id)]
        inputs.append(
            Input(
                f"Interface {i.id}",
                f"type {i.type_id}, "
                + ("chosen by the tool, not confirmed" if e.auto else "chosen by a person"),
                "",
                f"interface {i.id}: the connector at {e.unit_id}",
            )
        )
        if method != connector_choice.DEFAULT_METHOD:
            steps.append(_ranking_step(project, method, i, e.unit_id, box.id, bool(e.auto)))
        steps.append(
            text_step(
                f"Connectors of {e.unit_id} that carry {i.type_id}",
                "in ID order: "
                + _names(siblings)
                + (
                    "; the tool takes the first one that is free"
                    if e.auto
                    else "; a person picked this one"
                ),
                box.id,
                "",
            )
        )
    text = box.part_id if ends else f"{box.part_id}, used by no interface"
    return Derivation(
        "connector-choice",
        f"Connector {box.id}",
        "Choice of connector",
        None,
        "",
        "connector = the one a person picks for the interface at the device, else the first free connector of the device that carries the type"
        if method == connector_choice.DEFAULT_METHOD
        else "connector = the one a person picks for the interface at the device, else "
        + connector_choice.METHOD_TEXT[method],
        tuple(inputs),
        tuple(steps),
        None,
        ("A-CONNECTOR-CHOICE",),
        "A connector the tool chose is marked until a person confirms it (the finding 'unconfirmed'). "
        "The part of a device connector is a choice of the device design or the library, not of this tool.",
        text=text,
    )


def _ranking_step(
    project: Project, method: str, i: InterfaceInstance, unit_id: str, chosen_id: str, auto: bool
) -> Step:
    """The connectors of the device that carry the type in the order of the model in force, each
    with the pins it has, the pins an interface may take, the pins the interface needs and what is
    left over (the numbers the choice is made from)."""
    itype = project.interface_types.get(i.type_id)
    candidates = [c for c in unit_connectors(project, unit_id) if carries(c, i.type_id)]
    parts = []
    for c in connector_choice.ranked(method, candidates, itype):
        f = connector_choice.fit_of(c, itype)
        user = edit.interface_using(project, c.id)
        state = (
            "this interface"
            if user is not None and user.id == i.id
            else f"in use by {user.id}"
            if user is not None
            else "free"
        )
        fits = f"{f.spare} spare" if f.fits else f"too few pins ({f.available} for {f.needed})"
        parts.append(
            f"{c.id}: {f.pins} pins, {f.available} available, {f.needed} needed, {fits}, {state}"
        )
    return text_step(
        f"Connectors of {unit_id} in the order of {method}",
        "; ".join(parts) or "none carries the type",
        f"{connector_choice.METHOD_TEXT[method]}; the tool takes the first one that is free"
        + ("" if auto else " (a person picked " + chosen_id + ", so the model did not decide)"),
    )


def _cable_choice(project: Project, h: Harness, c: Connector) -> Derivation:
    box = project.connectors.get(c.mates_with or "")
    box_part = project.parts.get(box.part_id) if box is not None else None
    declared = box_part.mates_with if box_part is not None else None
    inputs: list[Input] = [
        Input("Mates with", c.mates_with, "", f"connector {c.id}"),
        Input(
            "Part of the device connector",
            box.part_id if box else None,
            "",
            f"connector {c.mates_with}",
        ),
        Input(
            "Mating part named by the library",
            declared,
            "",
            f"parts library: {box.part_id if box else '-'}: mates_with"
            + ("" if declared else " (none named)"),
        ),
        Input(
            "Gender of the device connector",
            box.gender if box else None,
            "",
            f"connector {c.mates_with}",
        ),
        Input(
            "Keying of the device connector",
            box.keying if box else None,
            "",
            f"connector {c.mates_with}",
        ),
        Input("Locked (edited by a person)", "yes" if c.locked else "no", "", f"connector {c.id}"),
    ]
    steps = [
        text_step(
            "Part of the cable end",
            "the mating part of the library"
            if declared and c.part_id == declared
            else "the same part as the device connector (the library names no mating part)"
            if box is not None and c.part_id == box.part_id
            else "as stored on the connector (a person changed it)",
            c.part_id,
            "",
        ),
        text_step("Gender", "the opposite of the device connector's", c.gender, ""),
    ]
    for r in why.reasons(project, "connector", c.id):
        steps.append(text_step("Recorded when it was generated", r.line, r.rule or "recorded", ""))
    return Derivation(
        "connector-choice",
        f"Connector {c.id} in {h.id}",
        "Choice of connector",
        None,
        "",
        "cable end = the mating part of the device connector's part; gender opposite, keying copied",
        tuple(inputs),
        tuple(steps),
        None,
        ("A-CONNECTOR-CHOICE",),
        "Generation checks the pair with the rule mate-mismatch (gender, part, pin count and keying).",
        text=f"{c.part_id} mates with {c.mates_with}",
    )


# ---- what the harness, the wire, the interface and the connector offer ---------------------------


def harness_derivations(project: Project, h: Harness) -> list[Derivation]:
    return [
        segmentation_derivation(project, h),
        *[
            connector_choice_derivation(project, c.id)
            for c in sorted(h.connectors, key=lambda x: x.id)
        ],
    ]


def wire_derivations(project: Project, h: Harness, w: Wire) -> list[Derivation]:
    return pin_derivations_of_wire(project, h, w)


def explain_interface(project: Project, interface_id: str) -> list[Derivation]:
    """Which harness the interface is in and why; the choice of the connector at each end; the pins
    of its signals."""
    from harness_design_studio.core.derive import contact_current_derivation

    i = project.interfaces[interface_id]
    out = interface_segmentation(project, interface_id)
    for e in i.endpoints:
        if e.connector_id and e.connector_id in project.connectors:
            out.append(connector_choice_derivation(project, e.connector_id))
            out.append(contact_current_derivation(project, i.id, e.connector_id))
            box = project.connectors[e.connector_id]
            out += [
                pin_allocation_derivation(project, box.id, p.id)
                for p in box.pins
                if p.interface_id == i.id
            ]
    return out


def explain_connector_or_pin(project: Project, object_id: str) -> list[Derivation]:
    """A connector (device or cable) by its ID, or a pin as CONNECTOR.PIN."""
    from harness_design_studio.core import derive_build

    if why.find_connector(project, object_id) is not None:
        return [
            connector_choice_derivation(project, object_id),
            *derive_build.explain_label_object(project, object_id),
        ]
    split = why.split_pin(project, object_id)
    if split is not None:
        return [pin_allocation_derivation(project, split[0], split[1])]
    return derive_build.explain_shield(project, object_id)
