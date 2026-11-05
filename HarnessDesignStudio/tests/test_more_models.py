"""D-191, S3b: four more methods that can be chosen (requirement R4): the pin fit strategy, the
choice of a connector, the segmentation method and the format of the labels. The default of each is
what the tool did before; each alternative is checked against a hand calculation on a small project,
and the explanation names the model in force."""

import json
import shutil
from pathlib import Path

import pytest

from harness_design_studio import api
from harness_design_studio.core import configcheck, settings
from harness_design_studio.core.derive import Derivation, render
from harness_design_studio.core.generate import pins as pinmod
from harness_design_studio.core.generate.pins import Request, allocate
from harness_design_studio.core.generation_status import generation_status
from harness_design_studio.core.model import ConfigFile, Project
from harness_design_studio.core.samples import mini3
from tests.test_generate_parts import _connector
from tools.trace_numbers import command

# ---- helpers -------------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def base(tmp_path_factory: pytest.TempPathFactory) -> Path:
    folder = tmp_path_factory.mktemp("more-models-base") / "flatsat"
    api.create_project(folder, "flatsat")
    return folder


@pytest.fixture
def work(base: Path, tmp_path: Path) -> Path:
    folder = tmp_path / "flatsat"
    shutil.copytree(base, folder)
    return folder


def set_value(folder: Path, assignment: str) -> None:
    command("settings", str(folder), "--set", assignment)


def derivation(folder: Path, obj: str, kind: str) -> Derivation:
    return next(d for d in api.explain(folder, obj) if d.id == kind)


def with_model(project: Project, **values: object) -> None:
    project.config["model"] = ConfigFile(name="model", placeholder=False, values=dict(values))


# ---- 1. the pin fit strategy ---------------------------------------------------------------------


def _placed(strategy: str, pins: int, gap: int = 0, n_serial: int = 2) -> dict[str, str]:
    """`IF-P.PWR` -> pin: a power interface, then `n_serial` RS-422 interfaces (TX pair, RX pair)."""
    p = mini3()
    requests = [Request("IF-P", p.interface_types["power_primary"])]
    requests += [Request(f"IF-{c}", p.interface_types["rs422"]) for c in "AB"[:n_serial]]
    out = allocate(_connector(pins), requests, {}, gap, strategy=strategy)
    assert not out.errors, out.errors
    return {f"{iid}.{sig}": pid for (iid, sig), pid in out.pins.items()}


def test_pin_fit_first_fit_is_what_the_allocator_always_did() -> None:
    # hand calculation, 12 pins, no gaps: power 1-2, then each group on the next free neighbours
    assert _placed("first_fit", 12) == {
        "IF-P.PWR": "1", "IF-P.RTN": "2",
        "IF-A.TX+": "3", "IF-A.TX-": "4", "IF-A.RX+": "5", "IF-A.RX-": "6",
        "IF-B.TX+": "7", "IF-B.TX-": "8", "IF-B.RX+": "9", "IF-B.RX-": "10",
    }  # fmt: skip
    p = mini3()
    requests = [Request("IF-P", p.interface_types["power_primary"])]
    assert (
        allocate(_connector(12), requests, {}, 0).pins
        == allocate(_connector(12), requests, {}, 0, strategy="first_fit").pins
    )
    assert pinmod.DEFAULT_STRATEGY == "first_fit"


def test_pin_fit_last_fit_fills_from_the_last_pin_down() -> None:
    # hand calculation, 12 pins: power on the last two pins (11, 12); the first group of the first
    # signal interface takes the highest free run below it (9, 10), the next group 7, 8, ...
    assert _placed("last_fit", 12) == {
        "IF-P.PWR": "11", "IF-P.RTN": "12",
        "IF-A.TX+": "9", "IF-A.TX-": "10", "IF-A.RX+": "7", "IF-A.RX-": "8",
        "IF-B.TX+": "5", "IF-B.TX-": "6", "IF-B.RX+": "3", "IF-B.RX-": "4",
    }  # fmt: skip


def test_pin_fit_last_fit_keeps_the_gap_between_power_and_signals() -> None:
    # two pins between the power block (pins 11, 12) and the signals: the signals end at pin 8
    placed = _placed("last_fit", 12, gap=2, n_serial=1)
    assert placed["IF-P.PWR"] == "11" and placed["IF-A.TX+"] == "7" and placed["IF-A.TX-"] == "8"
    assert placed["IF-A.RX+"] == "5" and placed["IF-A.RX-"] == "6"


def test_pin_fit_spread_leaves_one_free_pin_between_interfaces() -> None:
    # hand calculation, 12 pins: power 1-2, pin 3 free, IF-A on 4-7 (its two pairs stay together),
    # pin 8 free, IF-B on 9-12; nothing is left over, so this is the tightest spread there is
    assert _placed("spread", 12) == {
        "IF-P.PWR": "1", "IF-P.RTN": "2",
        "IF-A.TX+": "4", "IF-A.TX-": "5", "IF-A.RX+": "6", "IF-A.RX-": "7",
        "IF-B.TX+": "9", "IF-B.TX-": "10", "IF-B.RX+": "11", "IF-B.RX-": "12",
    }  # fmt: skip


def test_pin_fit_spread_falls_back_to_first_fit_when_there_is_no_room() -> None:
    # 6 pins hold the power block and one RS-422 interface only if they sit side by side
    assert _placed("spread", 6, n_serial=1) == _placed("first_fit", 6, n_serial=1)
    # 7 pins: the gap fits (power 1-2, gap 3, IF-A 4-7)
    assert _placed("spread", 7, n_serial=1)["IF-A.TX+"] == "4"
    # 10 pins: the second interface cannot be spread, so it is placed by first fit and no signal is lost
    ten = _placed("spread", 10)
    assert len(set(ten.values())) == len(ten) == 10


@pytest.mark.parametrize("strategy", pinmod.STRATEGIES)
def test_pin_fit_never_uses_a_locked_pin_or_one_pin_twice(strategy: str) -> None:
    from harness_design_studio.core.model import evolve

    p = mini3()
    c = _connector(12)
    locked = {"1", "12", "6"}
    c = evolve(
        c, pins=[evolve(x, locked=True, signal="X") if x.id in locked else x for x in c.pins]
    )
    requests = [
        Request("IF-P", p.interface_types["power_primary"]),
        Request("IF-A", p.interface_types["rs422"]),
    ]
    out = allocate(c, requests, {}, 0, strategy=strategy)
    assert not out.errors
    used = list(out.pins.values())
    assert len(used) == len(set(used)) == 6 and not locked & set(used)
    again = allocate(c, requests, {}, 0, strategy=strategy)
    assert again.pins == out.pins  # deterministic
    if (
        strategy == "last_fit"
    ):  # hand calculation: pins 11, 12 for power are not free (12 is locked)
        assert {out.pins[("IF-P", "PWR")], out.pins[("IF-P", "RTN")]} == {"10", "11"}


def test_pin_fit_power_return_gap_is_kept_by_every_strategy() -> None:
    p = mini3()
    requests = [Request("IF-P", p.interface_types["power_primary"])]
    first = allocate(_connector(9), requests, {}, 0, return_gap=1, strategy="first_fit")
    last = allocate(_connector(9), requests, {}, 0, return_gap=1, strategy="last_fit")
    assert (first.pins[("IF-P", "PWR")], first.pins[("IF-P", "RTN")]) == ("1", "3")
    assert (last.pins[("IF-P", "PWR")], last.pins[("IF-P", "RTN")]) == ("7", "9")


def test_pin_fit_on_a_fixed_pinout_takes_the_free_pin_of_the_name() -> None:
    from harness_design_studio.core.model import Connector, Pin

    p = mini3()
    pins = [Pin(id=str(k), signal="PWR", fixed=True) for k in (1, 2)]
    pins += [Pin(id=str(k), signal="RTN", fixed=True) for k in (3, 4)]
    box = Connector(
        id="U-J01", name="J01", role="box", part_id="EX-DSUB-9-F", unit_id="U",
        gender="female", pins=pins,
    )  # fmt: skip
    requests = [Request("IF-P", p.interface_types["power_primary"])]
    first = allocate(box, requests, {}, 0, strategy="first_fit")
    last = allocate(box, requests, {}, 0, strategy="last_fit")
    assert (first.pins[("IF-P", "PWR")], first.pins[("IF-P", "RTN")]) == ("1", "3")
    assert (last.pins[("IF-P", "PWR")], last.pins[("IF-P", "RTN")]) == ("2", "4")


def test_pin_fit_setting_is_registered_checked_and_makes_plans_stale(work: Path) -> None:
    s = settings.setting("model", "pin_fit_strategy")
    assert s is not None and s.default == "first_fit" and s.assumption == "A-PIN-FIRST-FIT"
    assert s.choices == pinmod.STRATEGIES
    project = api.load_project(work)
    assert pinmod.strategy(project) == "first_fit"
    with_model(project, pin_fit_strategy="sideways")
    assert pinmod.strategy(project) == "first_fit"  # an unknown value is not used
    messages = [i.message for i in configcheck.validate(project)]
    assert any("pin_fit_strategy must be one of first_fit, last_fit, spread" in m for m in messages)
    assert generation_status(api.load_project(work)) == "current"
    set_value(work, 'model.pin_fit_strategy="last_fit"')
    assert generation_status(api.load_project(work)) == "stale"


def test_pin_fit_change_with_settings_regenerates_and_the_explanation_follows(work: Path) -> None:
    def pins_of(folder: Path) -> list[tuple[str, str | None]]:
        box = api.load_project(folder).connectors["MTQ1-J01"]
        return [(x.id, x.signal) for x in box.pins if x.interface_id]

    assert pins_of(work) == [("1", "PWR"), ("2", "RTN")]  # the default: pins 1, 2 of 9
    before = render(derivation(work, "MTQ1-J01.1", "pin-allocation"))
    assert "Pin fit strategy" not in before and "first fit" in before
    set_value(work, 'model.pin_fit_strategy="last_fit"')
    assert api.generate(work).ok
    assert pins_of(work) == [("8", "PWR"), ("9", "RTN")]  # the last two of 9 pins
    after = render(derivation(work, "MTQ1-J01.8", "pin-allocation"))
    assert "Pin fit strategy (the model in force) = last_fit" in after
    assert "last free run of pins" in after and "last fit" in after
    set_value(work, 'model.pin_fit_strategy="first_fit"')
    assert api.generate(work).ok
    assert pins_of(work) == [("1", "PWR"), ("2", "RTN")]  # back to the default, as it was
    assert render(derivation(work, "MTQ1-J01.1", "pin-allocation")) == before


@pytest.mark.parametrize("strategy", pinmod.STRATEGIES)
def test_pin_fit_every_strategy_places_every_signal_of_the_flatsat(
    work: Path, strategy: str
) -> None:
    set_value(work, f'model.pin_fit_strategy="{strategy}"')
    assert api.generate(work).ok
    project = api.load_project(work)
    for box in project.connectors.values():
        used = [x.id for x in box.pins if x.interface_id]
        assert len(used) == len(set(used))
    wanted = sum(
        len(project.interface_types[i.type_id].signals) for i in project.interfaces.values()
    )
    placed = sum(1 for b in project.connectors.values() for x in b.pins if x.interface_id)
    assert placed == 2 * wanted  # every signal sits on a pin at each of its two ends
    assert json.loads(command("settings", str(work), "--json"))["settings"]
