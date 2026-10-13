"""Explain data: the recorded reasons behind generated objects (no guessing, only what was logged)."""

from harness_design_studio.core.model import Harness, Project, Wire


def _without_driver(line: str, w: Wire) -> str:
    """Only a TX/RX pair (labelled "TX+/RX+") has a driving end; PWR, RTN and other single paths
    do not, so "(X drives)" is left off their wiring line."""
    if line.startswith("wiring:") and w.signal and "/" not in w.signal:
        for end in ("X", "Y"):
            line = line.removesuffix(f" ({end} drives)")
    return line


def explain_wire(project: Project, h: Harness, w: Wire) -> list[str]:
    prov = project.generation.provenance if project.generation else {}
    keys = [f"wire:{w.id}", f"gauge:{w.id}", f"harness:{h.id}"]
    cables = {c.id: c for c in h.connectors}
    pin_keys = []
    for cid, pin in ((w.from_connector, w.from_pin), (w.to_connector, w.to_pin)):
        box = cables[cid].mates_with if cid in cables else None
        if box:
            pin_keys.append((f"pin:{box}.{pin}", f"{box} pin {pin}: "))
    out: list[str] = []
    for k in keys:
        out.extend(_without_driver(line, w) for line in prov.get(k, []))
    for k, where in pin_keys:  # the line itself does not say which connector it is about
        out.extend(where + line for line in prov.get(k, []))
    return out


def explain_harness(project: Project, h: Harness) -> list[str]:
    prov = project.generation.provenance if project.generation else {}
    return list(prov.get(f"harness:{h.id}", []))


def explain_connector(project: Project, h: Harness, connector_id: str) -> list[str]:
    """Why a cable connector of the harness is as it is (its mating part), as recorded."""
    prov = project.generation.provenance if project.generation else {}
    return list(prov.get(f"connector:{connector_id}", []))


def explain_pin(project: Project, h: Harness, connector_id: str, pin: str) -> list[str]:
    """Why a pin carries its signal, as recorded for the box connector that the cable connector
    mates with."""
    prov = project.generation.provenance if project.generation else {}
    cable = next((c for c in h.connectors if c.id == connector_id), None)
    if cable is None or not cable.mates_with:
        return []
    return list(prov.get(f"pin:{cable.mates_with}.{pin}", []))
