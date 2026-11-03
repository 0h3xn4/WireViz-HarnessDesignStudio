"""How the build workbook decides, and how its labels, colours and shields are made (D-191, S1).

Every function here calls the code that writes the sheet or generates the object, so an explanation
cannot disagree with the file it explains: `buildsheet.readiness` and `buildsheet.open_items` for
*Ready to build*, `tables.tests`, `tables.limit_value` for the test limits, `tables.wire_label_texts`
and `tables.connector_label_text` for the labels, `wirecolours.signal_colour` for the colour and
`generate.shields.plan` for the shield groups. The derivations are:

    readiness            Ready to build: the checks that block, how many are open
    readiness-check      one check of the Start here sheet and the wires or pins that are open
    test-limit           one test limit of the test sheet and where the number comes from
    wire-label           the two labels of a wire
    connector-label      the label of a cable connector
    wire-colour          the colour of a wire and where it came from
    shield-group         a shield group: why it exists and why it has these ends
"""

from harness_design_studio.core import settings
from harness_design_studio.core.derive import (
    Check,
    Derivation,
    Input,
    Step,
    _g,
    origin_text,
    text_step,
)
from harness_design_studio.core.edit import EditError
from harness_design_studio.core.generate import shields
from harness_design_studio.core.model import Connector, Harness, Project, ShieldGroup, Wire
from harness_design_studio.core.outputs import buildsheet, tables
from harness_design_studio.core.wirecolours import resolve, signal_colour

SHOWN = 8  # how many open items a line names before "and N more": no result depends on it

# What each check of the Start here sheet counts as open, in plain words (the predicates are in
# `buildsheet.open_items`, which also writes the sheet).
CHECK_MEANING = {
    "Wires without a length": "a wire is open when it has no length: none is stored on it and its path through the routing segments is not complete",
    "Wires without a gauge": "a wire is open when its gauge (AWG) is not decided",
    "Wires without a colour": "a wire is open when its colour is empty",
    "Wires without a part": "a wire is open when it names no wire part of the library",
    "Pins in use without a termination": "a pin with a wire on it is open when its termination is still 'unspecified' (crimp or solder not said)",
    "Wires without strip lengths": "a wire is open when the strip length at either end is empty",
    "Pins in use without a contact part": "a pin with a wire on it is open when it names no contact part",
    "Parts that are not approved": "a part used by a connector or wire of the harness is open when it is not in the parts list or its approval is not 'approved'",
}


def _names(items: tuple[str, ...]) -> str:
    if not items:
        return "none"
    shown = ", ".join(items[:SHOWN])
    return shown + (f" and {len(items) - SHOWN} more" if len(items) > SHOWN else "")


# ---- Ready to build ----------------------------------------------------------------------------


def readiness_derivation(project: Project, h: Harness) -> Derivation:
    """The answer to *Ready to build* of the build workbook, and the checks it comes from."""
    checks = buildsheet.readiness(project, h)
    blocking_names = settings.names(project, "model", "readiness_blocking")
    open_blocking = [c for c in checks if c.status == buildsheet.TO_FIX]
    answer = "yes" if not open_blocking else "no"
    shown = buildsheet.ready_text(answer, project.placeholder_configs())
    inputs = [
        Input(
            "Checks that block",
            ", ".join(blocking_names) or "none",
            "",
            f"config/model.json: readiness_blocking ({origin_text(project, 'model', 'readiness_blocking')})",
        ),
        Input(
            "Placeholder configuration files",
            ", ".join(project.placeholder_configs()) or "none",
            "",
            "the project: configuration files still marked as not reviewed (they change the wording of a yes, not the answer)",
        ),
    ]
    steps = [
        Step(
            c.label,
            (f"{c.status}, nothing open" if c.open == 0 else f"{c.status}: {_names(c.items)}")
            + (
                ""
                if c.blocking
                else " (not in model.readiness_blocking: a note, does not change the answer)"
            ),
            c.open,
            "open",
        )
        for c in checks
    ]
    steps.append(
        Step(
            "Checks that block and are open",
            "number of checks with status TO FIX",
            len(open_blocking),
            "checks",
        )
    )
    check = Check(
        float(len(open_blocking)),
        0.0,
        "checks",
        not open_blocking,
        -float(len(open_blocking)),
        "no check that blocks is open: Ready to build is yes"
        if not open_blocking
        else f"{len(open_blocking)} check(s) that block have open items ({', '.join(c.label for c in open_blocking)}): Ready to build is no",
    )
    return Derivation(
        "readiness",
        f"Harness {h.id}",
        "Ready to build",
        None,
        "",
        "Ready to build = yes when none of the checks named in model.readiness_blocking has an open item",
        tuple(inputs),
        tuple(steps),
        check,
        ("A-READY-CHECKS", "A-READY-SCOPE"),
        "The same function writes the Start here sheet of "
        f"{h.id}{buildsheet.FILE_SUFFIX}; the eight checks and what to do about each are on that sheet. "
        "The answer is not a statement that the harness passes its design checks or may be built.",
        text=shown,
    )


def readiness_check_derivation(project: Project, h: Harness, c: buildsheet.Check) -> Derivation:
    """One check of the Start here sheet: its predicate, its count, the open wires or pins."""
    inputs = [
        Input(
            "Open items",
            _names(c.items),
            "",
            f"the design: harness {h.id} (buildsheet.open_items)",
        ),
        Input(
            "Blocks Ready to build",
            "yes" if c.blocking else "no",
            "",
            f"config/model.json: readiness_blocking ({origin_text(project, 'model', 'readiness_blocking')})",
        ),
    ]
    steps = [
        Step("What is counted", CHECK_MEANING[c.label], c.open, "open"),
        text_step(
            "Effect on Ready to build",
            "this check is in model.readiness_blocking: an open item makes the answer no"
            if c.blocking
            else "this check is not in model.readiness_blocking: it is a note, an open item does not change the answer",
            "blocks" if c.blocking else "note",
        ),
    ]
    ok = c.open == 0
    check = (
        Check(
            float(c.open),
            0.0,
            "open",
            ok,
            -float(c.open),
            f"{c.open} open"
            + ("" if ok else f"; this check blocks Ready to build. What to do: {c.todo}"),
        )
        if c.blocking
        else None  # a note has no limit: the count is the value, and nothing is compared
    )
    return Derivation(
        "readiness-check",
        f"Harness {h.id}: {c.label}",
        c.label,
        float(c.open),
        "open",
        "open items = the wires, pins or parts of the harness that fail the check",
        tuple(inputs),
        tuple(steps),
        check,
        ("A-READY-CHECKS", "A-READY-SCOPE"),
        "Counted by buildsheet.open_items, the function that writes the Start here sheet.",
    )


# ---- test limits -------------------------------------------------------------------------------

_TEST_UNIT = {
    "test_continuity_max_ohm": "ohm",
    "test_isolation_min_mohm": "Mohm",
    "test_isolation_voltage_v": "V",
}


def sheet_limit_derivation(
    project: Project, h: Harness, key: str, row: list[str] | None = None
) -> Derivation:
    """Where one number of the *Limit* or *Test voltage* column of the test sheet comes from.
    With `row` (a row of `tables.tests`) the test is named."""
    entry = next(e for e in tables.TEST_LIMITS if e[0] == key)
    _key, sheet_unit, what = entry
    rows = tables.tests(project, h)[1:]
    kind = "continuity" if key == "test_continuity_max_ohm" else "isolation"
    mine = [r for r in rows if r[1] == kind]
    s = settings.setting("generation", key)
    if s is None:  # a key the registry does not know: never happens, kept honest
        raise EditError(f"'{key}' is not a test limit.")
    value = tables.limit_value(project, key)
    cfg = project.config.get("generation")
    placeholder = bool(cfg is not None and cfg.placeholder)
    unit = _TEST_UNIT[key]
    subject = (
        f"Harness {h.id}: {what} limit" if row is None else f"Test {h.id}.{row[0]}: {what} limit"
    )
    missing: tuple[str, ...] = ()
    if value is None:
        missing = (
            f"generation.{key} ({s.what.rstrip('.')}); the test sheet shows '{tables.TBD}' until it is set",
        )
    inputs = [
        Input(
            s.label,
            value,
            unit,
            f"config/generation.json: {key}"
            + (
                " (the file is still marked as not reviewed: placeholder)"
                if placeholder and value is not None
                else ""
            )
            + ("" if value is not None else " (not set)"),
        ),
        Input(
            "Tests that use it",
            len(mine),
            "",
            f"the test sheet of harness {h.id}: "
            + (f"{mine[0][0]} to {mine[-1][0]}" if mine else "none")
            + f", every {kind} test",
        ),
    ]
    if row is not None:
        _test_id, _kind, _from, _to, *_rest = row
        inputs.insert(
            0,
            Input(
                "Test",
                f"{row[0]} {row[1]}: {row[2]} to {_to}",
                "",
                f"harness {h.id}, test sheet",
            ),
        )
    steps = [
        text_step(
            "As written on the test sheet",
            f"{_g(value)} {sheet_unit}" if value is not None else tables.TBD,
            tables.TBD if value is None else f"{_g(value)} {sheet_unit}",
            "",
        )
    ]
    return Derivation(
        "test-limit",
        subject,
        s.label,
        value,
        unit,
        f"limit = the value of generation.{key}, the same for every {kind} test of every harness",
        tuple(inputs),
        tuple(steps),
        None,
        ("A-TEST-LIMITS", "A-TEST-LIST"),
        f"Source of the number: {s.source}. The tool records no standard or test procedure for it, "
        "and it does not follow the length, gauge or part of the wire.",
        missing,
    )


def sheet_limit_derivations(project: Project, h: Harness) -> list[Derivation]:
    return [sheet_limit_derivation(project, h, key) for key, _u, _w in tables.TEST_LIMITS]


def explain_test(project: Project, object_id: str) -> list[Derivation]:
    """A test of the test sheet, as HARNESS.T001: the limits it uses and where they come from."""
    left, _, right = object_id.partition(".")
    h = project.harnesses.get(left)
    if h is None or not right:
        return []
    row = next((r for r in tables.tests(project, h)[1:] if r[0] == right), None)
    if row is None:
        return []
    keys = (
        ["test_continuity_max_ohm"]
        if row[1] == "continuity"
        else ["test_isolation_min_mohm", "test_isolation_voltage_v"]
    )
    found = [sheet_limit_derivation(project, h, k, row) for k in keys]
    if project.asbuilt:  # what was measured in this test (S9)
        from harness_design_studio.core import derive_asbuilt

        result = derive_asbuilt.result_derivation(project, h, right)
        found += [] if result is None else [result]
    return found


# ---- labels, colours, shields -------------------------------------------------------------------


def wire_label_derivation(project: Project, h: Harness, w: Wire) -> Derivation:
    """The two labels printed for a wire and what each part of the text is."""
    wire_texts = tables.wire_label_texts(project, w)
    a, b = wire_texts
    emc = tables.emc_class_of(project, w)
    name = tables.wire_name(w)
    name_from = (
        "the label a person gave the wire"
        if w.label
        else "the signal of the wire (the label of the link of its interface type)"
        if w.signal
        else "nothing: the wire has neither a label nor a signal, so only its ID is printed"
    )
    inputs = [
        Input(
            "Wire ID",
            w.id,
            "",
            f"the design; the pattern is config/naming.json: wire ({origin_text(project, 'naming', 'wire')})",
        ),
        Input("Label of the wire", w.label, "", f"wire {w.id}: Label (typed by a person)"),
        Input(
            "Signal",
            w.signal,
            "",
            f"wire {w.id}: Signal, from the interface {w.interface_id or '(none)'}",
        ),
        Input("Name printed", name or None, "", name_from),
        Input("End A", f"{w.from_connector}.{w.from_pin}", "", f"wire {w.id}"),
        Input("End B", f"{w.to_connector}.{w.to_pin}", "", f"wire {w.id}"),
        Input(
            "EMC class",
            emc or None,
            "",
            "the interface type of the wire (emc_class)"
            if emc
            else "the interface type has no EMC class: no tag is printed",
        ),
    ]
    steps = [
        text_step(
            "Label A (printed at end A)",
            "ID, name, 'to', the far end B, [EMC class]",
            f"{w.id}-A: {a}",
            "",
        ),
        text_step(
            "Label B (printed at end B)",
            "ID, name, 'to', the far end A, [EMC class]",
            f"{w.id}-B: {b}",
            "",
        ),
    ]
    return Derivation(
        "wire-label",
        f"Wire {w.id}",
        "Wire labels",
        None,
        "",
        "label = wire ID + name (the wire's label, else its signal) + ' to ' + far end + ' [EMC class]' when the interface type has a class",
        tuple(inputs),
        tuple(steps),
        None,
        ("A-LABEL-FORMAT",),
        "The same function writes the Labels table and the Labels sheet of the build workbook "
        "(tables.wire_label_texts); the form is built into the tool.",
        text=f'{w.id}-A "{wire_texts[0]}"; {w.id}-B "{wire_texts[1]}"',
    )


def connector_label_derivation(project: Project, h: Harness, c: Connector) -> Derivation:
    """The label printed for a cable connector."""
    box = project.connectors.get(c.mates_with or "")
    text = tables.connector_label_text(project, c)
    name = tables.connector_label(project, c)
    from_where = (
        f"the label of connector {c.id}"
        if c.label
        else f"the label of the device connector {box.id}, which it plugs into"
        if box is not None and box.label
        else "nothing: neither the connector nor its mate has a label"
    )
    inputs = [
        Input("Label of the cable connector", c.label, "", f"connector {c.id}: Label"),
        Input(
            "Label of the device connector",
            box.label if box else None,
            "",
            f"connector {c.mates_with or '-'}: Label",
        ),
        Input("Mates", c.mates_with or "-", "", f"connector {c.id}"),
    ]
    steps = [
        text_step("Name", from_where, name or "(none)", ""),
        text_step(
            "Label text",
            "name (ID mates DEVICE-CONNECTOR), or just 'ID mates DEVICE-CONNECTOR'",
            text,
            "",
        ),
    ]
    return Derivation(
        "connector-label",
        f"Connector {c.id}",
        "Connector label",
        None,
        "",
        "label = connector label, else the device connector's label, then '(ID mates DEVICE-CONNECTOR)'",
        tuple(inputs),
        tuple(steps),
        None,
        ("A-LABEL-FORMAT",),
        "The same function writes the Labels table and the Labels sheet (tables.connector_label_text).",
        text=text,
    )


def wire_colour_derivation(project: Project, h: Harness, w: Wire) -> Derivation:
    """The colour of the wire, and whether it came from the table of the project or from a person."""
    gen = project.config.get("generation")
    table = gen.values.get("wire_colour_by_signal") if gen is not None else None
    from_table = signal_colour(table, w.signal)
    code, screen = resolve(w.colour)
    if not w.colour:
        origin = (
            "no colour: the wire has none and the table has no entry for its signal"
            if from_table is None
            else "no colour is stored on the wire, although the table has one for its signal (generate again)"
        )
    elif from_table is not None and from_table[1] == w.colour:
        origin = f"from the table of the project: the entry '{from_table[0]}'"
    else:
        origin = "typed or imported on the wire (generation keeps a colour a person gave)" + (
            "; locked" if w.locked else ""
        )
    inputs = [
        Input("Colour of the wire", w.colour, "", f"wire {w.id}: Colour"),
        Input("Signal", w.signal, "", f"wire {w.id}"),
        Input(
            "Entry of the table for the signal",
            from_table[1] if from_table else None,
            "",
            "config/generation.json: wire_colour_by_signal"
            + (f", key '{from_table[0]}'" if from_table else ", no key matches the signal")
            + ("" if table is not None else " (the table is not set)"),
        ),
        Input(
            "IEC 60757 code",
            code or None,
            "",
            "the colour table of the tool (core/wirecolours.py); it decides nothing, it only names the colour",
        ),
    ]
    steps = [text_step("Where the colour came from", origin, w.colour or "(none)", "")]
    missing = (
        ()
        if w.colour
        else (
            "the colour of the wire (set wire_colour_by_signal for its signal, or the colour of the wire)",
        )
    )
    return Derivation(
        "wire-colour",
        f"Wire {w.id}",
        "Colour",
        None,
        "",
        "colour = the colour typed on the wire, else the entry of wire_colour_by_signal for its signal, else none",
        tuple(inputs),
        tuple(steps),
        None,
        ("A-COLOUR-TABLE",),
        f"The screen colour {screen} is for drawing only. A colour that is empty is the check 'Wires without a colour' of the build workbook.",
        missing,
        text=w.colour or "",
    )


def shield_group_derivation(project: Project, h: Harness, s: ShieldGroup) -> Derivation:
    """Why the shield group exists and why it has the ends it has."""
    gen = project.config.get("generation")
    gen_values = dict(gen.values) if gen is not None else {}
    a, b, _placeholder = shields.concept_ends(gen_values)
    ifaces = [
        project.interfaces[i]
        for i in sorted(
            {w.interface_id for w in h.wires if w.interface_id} & set(project.interfaces)
        )
        if project.interfaces[i].type_id in project.interface_types
    ]
    planned = next(
        (
            p
            for p in shields.plan(project, ifaces, [w for w in h.wires if not w.manual])
            if sorted(w.id for w in p.wires) == sorted(s.wire_ids) and p.kind == s.kind
        ),
        None,
    )
    if s.manual:
        why = "made by hand (a person made this group, so generation keeps it)"
    elif planned is not None:
        why = planned.why
    else:
        why = "no rule of the generator makes it today (the design changed since generation: generate again)"
    fixed = s.kind == "coax"
    ends_from = (
        "fixed by the file format: a coax shield is bonded at both ends"
        if fixed
        else "the grounding concept of the project (generation.shield_end_a, shield_end_b)"
        if planned is not None and not s.manual
        else "as stored on the group (made by hand)"
    )
    concept_known = None not in (gen_values.get("shield_end_a"), gen_values.get("shield_end_b"))
    agrees = (s.end_a, s.end_b) == (a, b)
    inputs = [
        Input("Kind", s.kind, "", f"shield group {s.id}"),
        Input("Wires", _names(tuple(s.wire_ids)), "", f"shield group {s.id}"),
        Input("Shield end A", s.end_a, "", ends_from),
        Input("Shield end B", s.end_b, "", ends_from),
        Input(
            "Grounding concept, end A",
            gen_values.get("shield_end_a"),
            "",
            "config/generation.json: shield_end_a"
            + (
                "" if gen_values.get("shield_end_a") is not None else " (not set: floating is used)"
            ),
        ),
        Input(
            "Grounding concept, end B",
            gen_values.get("shield_end_b"),
            "",
            "config/generation.json: shield_end_b"
            + (
                "" if gen_values.get("shield_end_b") is not None else " (not set: floating is used)"
            ),
        ),
        Input(
            "Bonding required by the project",
            project.config["emc"].values.get("shield_bonding") if "emc" in project.config else None,
            "",
            "config/emc.json: shield_bonding (rule shield-bonding)",
        ),
    ]
    steps = [
        text_step("Why the group exists", why, s.kind, ""),
        text_step(
            "Ends against the grounding concept",
            f"{s.end_a}/{s.end_b} against {a}/{b}"
            + ("" if concept_known else " (the concept is not set)"),
            "equal"
            if agrees
            else (
                "not applicable to a coax or a twisted pair"
                if s.kind in ("coax", "twisted_pair")
                else "different: the rule shield-wrong-end reports it"
            ),
            "",
        ),
    ]
    missing = (
        ()
        if concept_known or fixed
        else (
            "the grounding concept: generation.shield_end_a and shield_end_b (floating is used until they are set)",
        )
    )
    return Derivation(
        "shield-group",
        f"Shield group {s.id} in {h.id}",
        "Shield group",
        None,
        "",
        "group = the wires of a coax, quad, pair or overall shield of the interface type; ends = the grounding concept (coax: both ends bonded)",
        tuple(inputs),
        tuple(steps),
        None,
        ("A-SHIELD-GROUPS", "A-SHIELD-ENDS"),
        "The same function (generate.shields.plan) makes the groups when the harness is generated. "
        "A twisted pair has no shield to ground; the rules skip it.",
        missing,
        text=f"{s.kind}, end A {s.end_a}, end B {s.end_b}",
    )


# ---- what the harness and the wire offer ----------------------------------------------------------


def harness_derivations(project: Project, h: Harness) -> list[Derivation]:
    """Readiness (the answer, then each check), the three test limits, the shield groups and the
    labels of the cable connectors."""
    out = [readiness_derivation(project, h)]
    out += [readiness_check_derivation(project, h, c) for c in buildsheet.readiness(project, h)]
    out += sheet_limit_derivations(project, h)
    out += [shield_group_derivation(project, h, s) for s in sorted(h.shields, key=lambda x: x.id)]
    out += [
        connector_label_derivation(project, h, c) for c in sorted(h.connectors, key=lambda x: x.id)
    ]
    if project.asbuilt:  # the as-built results (S9): only a project that has records has them
        from harness_design_studio.core import derive_asbuilt

        out += derive_asbuilt.harness_derivations(project, h)
    return out


def wire_derivations(project: Project, h: Harness, w: Wire) -> list[Derivation]:
    """The label, the colour and the shield group of a wire."""
    out = [wire_label_derivation(project, h, w), wire_colour_derivation(project, h, w)]
    group = next((s for s in h.shields if w.id in s.wire_ids), None)
    if group is not None:
        out.append(shield_group_derivation(project, h, group))
    if project.asbuilt:  # the length that was cut (S9)
        from harness_design_studio.core import derive_asbuilt

        out += derive_asbuilt.wire_derivations(project, h, w)
    return out


def explain_shield(project: Project, object_id: str) -> list[Derivation]:
    """A shield group by its ID (W001-S1), or by HARNESS.SHIELD."""
    for h in project.harnesses.values():
        for s in h.shields:
            if object_id in (s.id, f"{h.id}.{s.id}"):
                return [shield_group_derivation(project, h, s)]
    return []


def explain_label_object(project: Project, object_id: str) -> list[Derivation]:
    """A cable connector by its ID: its label (the choice of connector is in `derive_layout`)."""
    for h in project.harnesses.values():
        for c in h.connectors:
            if c.id == object_id:
                return [connector_label_derivation(project, h, c)]
    return []


__all__ = [
    "explain_label_object",
    "explain_shield",
    "explain_test",
    "harness_derivations",
    "readiness_check_derivation",
    "readiness_derivation",
    "shield_group_derivation",
    "sheet_limit_derivation",
    "sheet_limit_derivations",
    "wire_colour_derivation",
    "wire_derivations",
    "wire_label_derivation",
]
