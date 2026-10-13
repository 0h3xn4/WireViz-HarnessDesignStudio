"""Starter library and interface types. EXAMPLE data only: no numbers, nothing is qualified.

Baseline (D-130): RS-422, RS-485 and CAN for communication; Micro-D 9, 15, 21, 25 and 31 pin for
power and data; Ethernet (RJ45) as the alternative for high data rates; SMA for RF. The other
connectors and interface types stay in the library for projects that need them.
"""

from .model import InterfaceType, Part, SignalDef


def starter_parts() -> list[Part]:
    """Example parts with fictional part numbers. All unverified and pending approval."""
    spec = [
        ("EX-DSUB-9-M", "connector", "D-sub 9-pin, male (example)", 9),
        ("EX-DSUB-9-F", "connector", "D-sub 9-pin, female (example)", 9),
        ("EX-DSUB-15-M", "connector", "D-sub 15-pin, male (example)", 15),
        ("EX-DSUB-15-F", "connector", "D-sub 15-pin, female (example)", 15),
        ("EX-MICROD-9-M", "connector", "Micro-D 9-pin, male (example, baseline power and data)", 9),
        (
            "EX-MICROD-9-F",
            "connector",
            "Micro-D 9-pin, female (example, baseline power and data)",
            9,
        ),
        (
            "EX-MICROD-15-M",
            "connector",
            "Micro-D 15-pin, male (example, baseline power and data)",
            15,
        ),
        (
            "EX-MICROD-15-F",
            "connector",
            "Micro-D 15-pin, female (example, baseline power and data)",
            15,
        ),
        (
            "EX-MICROD-21-M",
            "connector",
            "Micro-D 21-pin, male (example, baseline power and data)",
            21,
        ),
        (
            "EX-MICROD-21-F",
            "connector",
            "Micro-D 21-pin, female (example, baseline power and data)",
            21,
        ),
        (
            "EX-MICROD-25-M",
            "connector",
            "Micro-D 25-pin, male (example, baseline power and data)",
            25,
        ),
        (
            "EX-MICROD-25-F",
            "connector",
            "Micro-D 25-pin, female (example, baseline power and data)",
            25,
        ),
        (
            "EX-MICROD-31-M",
            "connector",
            "Micro-D 31-pin, male (example, baseline power and data)",
            31,
        ),
        (
            "EX-MICROD-31-F",
            "connector",
            "Micro-D 31-pin, female (example, baseline power and data)",
            31,
        ),
        (
            "EX-RJ45-M",
            "connector",
            "Ethernet RJ45 8P8C, male plug (example, alternative for high data rates)",
            8,
        ),
        (
            "EX-RJ45-F",
            "connector",
            "Ethernet RJ45 8P8C, female jack (example, alternative for high data rates)",
            8,
        ),
        ("EX-MDM-21-M", "connector", "MDM 21-pin, male (example)", 21),
        ("EX-CIRC-19-F", "connector", "Circular MIL-DTL-38999-style, 19-pin, female (example)", 19),
        ("EX-SMA-F", "connector", "SMA coax, female (example, baseline RF)", 1),
        ("EX-SMA-M", "connector", "SMA coax, male (example, baseline RF)", 1),
        ("EX-TNC-M", "connector", "TNC coax, male (example)", 1),
        ("EX-TNC-F", "connector", "TNC coax, female (example)", 1),
        ("EX-MDM-21-F", "connector", "MDM 21-pin, female (example)", 21),
        ("EX-CIRC-19-M", "connector", "Circular MIL-DTL-38999-style, 19-pin, male (example)", 19),
        ("EX-WIRE-SINGLE", "wire", "Single-conductor wire (example)", None),
        ("EX-WIRE-TWISTED-SHIELDED", "wire", "Twisted shielded pair (example)", None),
        ("EX-SLEEVE", "sleeving", "Braided sleeving (example)", None),
        ("EX-LABEL", "label", "Wire marker sleeve (example)", None),
    ]
    mates = {
        pid: pid[:-1] + ("F" if pid.endswith("M") else "M")
        for pid, cat, _d, _p in spec
        if cat == "connector"
    }
    mates = {k: v for k, v in mates.items() if v in {p for p, *_ in spec}}
    return [
        Part(
            id=pid,
            category=cat,  # type: ignore[arg-type]
            description=desc,
            approval="pending",
            unverified=True,
            pin_count=pins,
            mates_with=mates.get(pid),
        )
        for pid, cat, desc, pins in spec
    ]


def starter_interface_types() -> list[InterfaceType]:
    """Reusable interface templates. Impedance, EMC class and gauge are left for an engineer."""

    def sigs(*items: tuple[str, str, str | None]) -> list[SignalDef]:
        return [SignalDef(name=n, direction=d, pair=p) for n, d, p in items]  # type: ignore[arg-type]

    rows: list[tuple[str, str, str, str, str, list[SignalDef]]] = [
        ("power_primary", "Primary power", "power", "twisted_pair", "none",
         sigs(("PWR", "passive", None), ("RTN", "passive", None))),
        ("power_secondary", "Secondary power", "power", "twisted_pair", "none",
         sigs(("PWR", "passive", None), ("RTN", "passive", None))),
        ("rs422", "RS-422", "data", "twisted_shielded_pair", "per_pair",
         sigs(("TX+", "out", "TX"), ("TX-", "out", "TX"), ("RX+", "in", "RX"), ("RX-", "in", "RX"))),
        ("rs485", "RS-485", "data", "twisted_shielded_pair", "overall",
         sigs(("A", "bidir", "BUS"), ("B", "bidir", "BUS"))),
        ("ethernet", "Ethernet", "data", "twisted_shielded_pair", "per_pair",
         sigs(("TX+", "out", "TX"), ("TX-", "out", "TX"), ("RX+", "in", "RX"), ("RX-", "in", "RX"))),
        ("spacewire", "SpaceWire", "data", "twisted_shielded_pair", "per_pair",
         sigs(("DIN+", "in", "DIN"), ("DIN-", "in", "DIN"), ("SIN+", "in", "SIN"), ("SIN-", "in", "SIN"),
              ("DOUT+", "out", "DOUT"), ("DOUT-", "out", "DOUT"), ("SOUT+", "out", "SOUT"), ("SOUT-", "out", "SOUT"))),
        ("can", "CAN", "data", "twisted_shielded_pair", "overall",
         sigs(("CANH", "bidir", "BUS"), ("CANL", "bidir", "BUS"))),
        ("mil1553b", "MIL-STD-1553B", "data", "twisted_shielded_pair", "overall",
         sigs(("BUS+", "bidir", "BUS"), ("BUS-", "bidir", "BUS"))),
        ("lvds", "LVDS", "data", "twisted_shielded_pair", "per_pair",
         sigs(("D+", "out", "D"), ("D-", "out", "D"))),
        ("i2c", "I2C", "data", "single", "none",
         sigs(("SDA", "bidir", None), ("SCL", "out", None), ("GND", "passive", None))),
        ("analog", "Analog signal", "analog", "twisted_shielded_pair", "overall",
         sigs(("SIG+", "out", "SIG"), ("SIG-", "out", "SIG"))),
        ("thermistor", "Thermistor", "thermal", "twisted_pair", "none",
         sigs(("T+", "passive", "T"), ("T-", "passive", "T"))),
        ("heater", "Heater", "power", "twisted_pair", "none",
         sigs(("HTR+", "passive", "H"), ("HTR-", "passive", "H"))),
        ("discrete", "Discrete / bilevel", "discrete", "single", "none",
         sigs(("SIG", "out", None), ("RTN", "passive", None))),
        ("pyro", "Pyro initiator", "pyro", "twisted_shielded_pair", "overall",
         sigs(("FIRE+", "out", "FIRE"), ("FIRE-", "out", "FIRE"))),
        ("rf_coax", "RF coax", "rf", "coax", "none", sigs(("RF", "bidir", None))),
        ("ground", "Ground / chassis", "ground", "single", "none", sigs(("GND", "passive", None))),
    ]  # fmt: skip
    return [
        InterfaceType(
            id=tid, name=name, category=cat, construction=cons, shielding=shield,  # type: ignore[arg-type]
            signals=signals, unverified=True,
        )
        for tid, name, cat, cons, shield, signals in rows
    ]  # fmt: skip
