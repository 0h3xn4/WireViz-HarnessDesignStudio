# Design worksheet

Fill this in **before** you open the tool. It takes 30 minutes and saves hours: the tool needs exactly this information, in this order. Print it, or copy it next to your design and fill it in. Rows in *italics* are examples from the `minimal-satellite` project; replace them.

## 1. The spacecraft

| | |
| --- | --- |
| Name | |
| One sentence: what does it do? | |
| Who owns the design and who checks it? | |
| Is any part of the harness already built or ordered? (these parts are fixed) | |

## 2. The devices

A **device** is a box with connectors: computer, power unit, radio, wheel, sensor. List every device that needs a wire.

| Name (short, unique) | What it is | Kind in the tool | Redundant copy needed? | Zone / location |
| --- | --- | --- | --- | --- |
| *OBC1* | *on-board computer* | *computer_xl* | *no* | *bus* |
| *PCDU1* | *power control unit* | *pdu* | *no* | *bus* |
| | | | | |
| | | | | |

"Kind in the tool" is the template you pick when you add the device: `computer`, `computer_xl`, `pdu`, `battery`, `solar_array`, `actuator`, `sensor`, `sun_sensor`, `magnetorquer`, `transceiver`, `payload`, `heater_panel` or `pyro`. If none fits, write what it is; connectors can be added by hand in Expert mode.

## 3. The interfaces

An **interface** is one connection need between two devices. Direction matters for power (from the source to the user).

| ID | Type | From | To | Redundancy | Max current (A, power only) | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| *IF-001* | *Primary power* | *PCDU1* | *OBC1* | *nominal* | *1.0* | *always on* |
| *IF-002* | *CAN* | *OBC1* | *PCDU1* | *nominal* | | *housekeeping* |
| | | | | | | |
| | | | | | | |

The types the tool knows from the start: Primary power, Secondary power, RS-422, RS-485, Ethernet, SpaceWire, CAN, MIL-STD-1553B, LVDS, I2C, Analog signal, Thermistor, Heater, Discrete / bilevel, Pyro initiator, RF coax, Ground / chassis. Other types can be added in the library.

You can type this table straight into `interfaces.csv` (columns `id,type,from,to,redundancy`) and import it.

## 4. What you know and what you do not

Mark each line. "Not yet" is a good answer: the tool says *pending* and does not invent a value.

| Item | Have it? | Where it comes from | Who supplies it |
| --- | --- | --- | --- |
| Approved parts list (connectors, wires) | yes / not yet | | |
| Lengths of the harness segments | yes / not yet | | |
| Wire derating and current ratings | yes / not yet | | |
| EMC classes and separation rules | yes / not yet | | |
| Connector pinouts of the devices (KiCad or table) | yes / not yet | | |
| Title block and drawing numbers | yes / not yet | | |

Each "not yet" is listed by `harness-design-studio config DIR` and shown in the Problems tab until it is filled in. See `docs/PLACEHOLDERS.md` in the tool's repository (it is not installed with the app).

## 5. Check before you start

- [ ] Every device appears in at least one interface.
- [ ] Every power interface has a source, a user and a maximum current.
- [ ] Devices that must survive a failure have a redundant copy, and the interfaces to them are marked.
- [ ] Two interfaces that must never share a connector are noted (the tool checks separation once the rules are supplied).
- [ ] Someone other than the author has read the table.

## 6. Then

1. `harness-design-studio new my-design` (or **File > New project**).
2. Add the devices, then the interfaces, in the app, or import the table.
3. `harness-design-studio generate my-design`, then read the Problems tab.

The step-by-step version is in `docs/GETTING_STARTED.md`, the whole route in `docs/LEARNING_PATH.md` (both in the tool's repository, not installed with the app).
