"""How an as-built result is compared (S9, D-191): the derivation kind `asbuilt-result`.

A derivation exists only for a thing that has an as-built record with a value, so a project with no
records has none of these and its derivations are as they were. Each one calls `core.asbuilt` and
`tables.limit_value`, the code the report and the sheet use, so an explanation cannot disagree
with the report:

    a test result   the measured value, the limit of the project's test limits and the margin: a
                    continuity resistance must not exceed its limit, an insulation resistance must
                    not be lower than its limit
    a cut length    the length that was cut, the length of the design (the one `wire-length`
                    explains) and the difference; the tool applies no tolerance unless the project
                    sets one (`asbuilt_cut_tolerance_mm`), and then the check is the distance from
                    the design against the tolerance, like a measured value against its limit
    a strip length  the same, only when the project sets `asbuilt_strip_tolerance_mm` (without a
                    tolerance a strip length has no derivation, as before)

Neither says that a harness passed; the check says whether the value is within the limit of the
project, and the result stays what the person recorded.
"""

from harness_design_studio.core.asbuilt import LIMIT_KEYS, TOLERANCE, LengthCheck, length_check
from harness_design_studio.core.derive import Check, Derivation, Input, Step, _g
from harness_design_studio.core.generate.lengths import wire_length
from harness_design_studio.core.model import AsBuiltRecord, Harness, Project, Wire
from harness_design_studio.core.model.asbuilt import record_id
from harness_design_studio.core.outputs import tables

SOURCE = "asbuilt/records.json"


def _record(project: Project, kind: str, hid: str, subject: str) -> AsBuiltRecord | None:
    return project.asbuilt.get(record_id(kind, hid, subject))


def result_derivation(project: Project, h: Harness, tid: str) -> Derivation | None:
    """The measured value of a test compared with its limit; None while no value was recorded."""
    rec = _record(project, "test", h.id, tid)
    row = next((r for r in tables.tests(project, h, marks=False)[1:] if r[0] == tid), None)
    if rec is None or row is None:
        return None
    kind = row[1]
    key = "continuity_ohm" if kind == "continuity" else "isolation_mohm"
    actual = getattr(rec, key)
    if actual is None:
        return None
    limit_key, unit = LIMIT_KEYS[key]
    limit = tables.limit_value(project, limit_key)
    upper = kind == "continuity"
    quantity = "Measured continuity resistance" if upper else "Measured insulation resistance"
    equation = (
        f"margin = limit - measured; the largest resistance accepted as continuous is {limit_key}"
        if upper
        else f"margin = measured - limit; the smallest insulation resistance is {limit_key}"
    )
    inputs = [
        Input("Measured value", actual, unit, f"{SOURCE}: test {tid} of harness {h.id}"),
        Input(
            "Limit",
            limit,
            unit,
            f"config/generation.json: {limit_key}" + ("" if limit is not None else " (not set)"),
        ),  # fmt: skip
    ]
    check = None
    steps: list[Step] = []
    missing: tuple[str, ...] = ()
    if limit is None:
        missing = (f"generation.{limit_key} (the limit of the test); the value is not compared until it is set",)  # fmt: skip
    else:
        margin = limit - actual if upper else actual - limit
        within = margin >= 0
        word = "at most" if upper else "at least"
        steps.append(Step("Margin", f"{_g(limit)} - {_g(actual)}" if upper else f"{_g(actual)} - {_g(limit)}", round(margin, 9), unit))  # fmt: skip
        check = Check(
            actual, limit, unit, within, round(margin, 9),
            f"{_g(actual)} {unit} measured; the limit is {word} {_g(limit)} {unit}: "
            + ("within the limit" if within else "OUT OF THE LIMIT"),
        )  # fmt: skip
    return Derivation(
        "asbuilt-result", f"Test {h.id}.{tid}", quantity, actual, unit, equation,
        tuple(inputs), tuple(steps), check, (),
        f"As recorded: result {rec.result or 'not recorded'}. The tool does not accept a result "
        "that is out of its limit and does not say that the harness passed.", missing,
    )  # fmt: skip


def _tolerance_parts(
    c: LengthCheck, actual: float, designed: float, unit: str, what: str
) -> tuple[Input, Step, Step, Check]:
    """The tolerance as an input, the two steps and the check of a length that has a tolerance."""
    tolerance = Input("Tolerance", c.tolerance_mm, "mm", f"config/generation.json: {c.key} (A-ASBUILT-TOLERANCE)")  # fmt: skip
    distance = Step("Distance from the designed value", f"|{_g(c.difference)}| {unit} in mm", c.distance_mm, "mm")  # fmt: skip
    margin = Step("Margin", f"tolerance - distance = {_g(c.tolerance_mm)} - {_g(c.distance_mm)}", c.room_mm, "mm")  # fmt: skip
    verdict = "within the tolerance" if c.within else "OUT OF TOLERANCE"
    check = Check(
        c.distance_mm, c.tolerance_mm, "mm", c.within, c.room_mm,
        f"{_g(actual)} {unit} {what}, {_g(designed)} {unit} is designed: {_g(c.distance_mm)} mm "
        f"from the design, the tolerance is {_g(c.tolerance_mm)} mm: {verdict}",
    )  # fmt: skip
    return tolerance, distance, margin, check


def cut_length_derivation(project: Project, h: Harness, w: Wire) -> Derivation | None:
    """The length that was cut against the length of the design; None while none was recorded."""
    rec = _record(project, "wire", h.id, w.id)
    if rec is None or rec.cut_length_m is None:
        return None
    designed = wire_length(h, w)
    inputs = [
        Input("Cut length", rec.cut_length_m, "m", f"{SOURCE}: wire {w.id} of harness {h.id}"),
        Input(
            "Designed length",
            designed,
            "m",
            "the design (explain the wire: kind wire-length)"
            + ("" if designed is not None else " (no length)"),
        ),  # fmt: skip
    ]
    steps: list[Step] = []
    check: Check | None = None
    assumptions: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    value: float | None = None
    if designed is None:
        missing = (f"the length of wire {w.id} in the design",)
    else:
        value = round(rec.cut_length_m - designed, 9)
        steps.append(Step("Difference", f"{_g(rec.cut_length_m)} - {_g(designed)}", value, "m"))
        c = length_check(project, "cut length", "m", rec.cut_length_m, designed)
        if c is not None:  # the project set a tolerance: the length is judged like a test value
            tolerance, distance, margin, check = _tolerance_parts(c, rec.cut_length_m, designed, "m", "was cut")  # fmt: skip
            inputs.append(tolerance)
            steps += [distance, margin]
            assumptions = ("A-ASBUILT-TOLERANCE",)
    if check is not None:
        note = (
            "The tolerance is the project's own value (config/generation.json); the tool supplies "
            "none. Neither this check nor the report says that the harness passed."
        )
    else:
        note = (
            "As designed."
            if value is not None and abs(value) < TOLERANCE
            else "The tool applies no tolerance to a length: any difference is listed."  # fmt: skip
        )
    return Derivation(
        "asbuilt-result", f"Wire {w.id}", "Cut length minus designed length", value, "m",
        "difference = cut length - designed length", tuple(inputs), tuple(steps), check,
        assumptions, note, missing,
    )  # fmt: skip


def strip_length_derivation(project: Project, h: Harness, w: Wire, end: str) -> Derivation | None:
    """A strip length against the designed strip length, only when the project set a tolerance for
    strip lengths (`asbuilt_strip_tolerance_mm`): None otherwise, or while one is not recorded or
    the design has none, so a project without the setting has the derivations it always had."""
    rec = _record(project, "wire", h.id, w.id)
    actual = (rec.strip_a_mm if end == "A" else rec.strip_b_mm) if rec is not None else None
    designed = w.strip_a_mm if end == "A" else w.strip_b_mm
    if actual is None or designed is None:
        return None
    c = length_check(project, f"strip {end}", "mm", actual, designed)
    if c is None:
        return None
    tolerance, distance, margin, check = _tolerance_parts(c, actual, designed, "mm", "was stripped")  # fmt: skip
    inputs = (
        Input(f"Strip length {end}", actual, "mm", f"{SOURCE}: wire {w.id} of harness {h.id}"),
        Input(f"Designed strip length {end}", designed, "mm", f"wire {w.id}: strip_{end.lower()}_mm"),  # fmt: skip
        tolerance,
    )  # fmt: skip
    difference = Step("Difference", f"{_g(actual)} - {_g(designed)}", c.difference, "mm")
    return Derivation(
        "asbuilt-result", f"Wire {w.id} strip {end}", f"Strip length {end} minus designed strip length",
        c.difference, "mm", "difference = strip length - designed strip length", inputs,
        (difference, distance, margin), check, ("A-ASBUILT-TOLERANCE",),
        "The tolerance is the project's own value (config/generation.json); the tool supplies none. "
        "Neither this check nor the report says that the harness passed.",
    )  # fmt: skip


def harness_derivations(project: Project, h: Harness) -> list[Derivation]:
    """The test results of a harness that has records, in test order."""
    if not project.asbuilt:
        return []
    found = (result_derivation(project, h, r[0]) for r in tables.tests(project, h, marks=False)[1:])
    return [d for d in found if d is not None]


def wire_derivations(project: Project, h: Harness, w: Wire) -> list[Derivation]:
    if not project.asbuilt:
        return []
    found = [
        cut_length_derivation(project, h, w),
        strip_length_derivation(project, h, w, "A"),
        strip_length_derivation(project, h, w, "B"),
    ]
    return [d for d in found if d is not None]
