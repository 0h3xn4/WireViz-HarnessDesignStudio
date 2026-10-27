from dataclasses import asdict
from itertools import groupby
from typing import TYPE_CHECKING, Any

from wireviz.DataClasses import AdditionalComponent, Cable, Color, Connector
from wireviz.wv_colors import translate_color
from wireviz.wv_gv_html import html_bgcolor_attr, html_line_breaks
from wireviz.wv_helper import clean_whitespace

if TYPE_CHECKING:  # the import at run time would be circular
    from wireviz.Harness import Harness

BOM_COLUMNS_ALWAYS = ("id", "description", "qty", "unit", "designators")
BOM_COLUMNS_OPTIONAL = ("pn", "manufacturer", "mpn", "supplier", "spn")
BOM_COLUMNS_IN_KEY = ("description", "unit") + BOM_COLUMNS_OPTIONAL

HEADER_PN = "P/N"
HEADER_MPN = "MPN"
HEADER_SPN = "SPN"

BOMKey = tuple[str, ...]
BOMColumn = str  # = Literal[*BOM_COLUMNS_ALWAYS, *BOM_COLUMNS_OPTIONAL]
BOMEntry = dict[BOMColumn, str | int | float | list[str] | None]


def optional_fields(part: Connector | Cable | AdditionalComponent) -> BOMEntry:
    """Return part field values for the optional BOM columns as a dict."""
    part = asdict(part)
    return {field: part.get(field) for field in BOM_COLUMNS_OPTIONAL}


def get_additional_component_table(
    harness: Harness, component: Connector | Cable
) -> list[str]:
    """Return a list of diagram node table row strings with additional components."""
    rows = []
    if component.additional_components:
        rows.append(["Additional components"])
        # Ignore components that have qty 0
        for part in [
            part
            for part in component.additional_components
            if component.get_qty_multiplier(part.qty_multiplier)
        ]:
            common_args = {
                "qty": part.qty * component.get_qty_multiplier(part.qty_multiplier),
                "unit": part.unit,
                "bgcolor": part.bgcolor,
            }
            if harness.options.mini_bom_mode:
                id = get_bom_index(
                    harness.bom(),
                    bom_entry_key({**asdict(part), "description": part.description}),
                )
                rows.append(
                    component_table_entry(
                        f"#{id} ({part.type.rstrip()})", **common_args
                    )
                )
            else:
                rows.append(
                    component_table_entry(
                        part.description, **common_args, **optional_fields(part)
                    )
                )
    return rows


def get_additional_component_bom(component: Connector | Cable) -> list[BOMEntry]:
    """Return a list of BOM entries with additional components."""
    bom_entries = []
    # Ignore components that have qty 0
    for part in [
        part
        for part in component.additional_components
        if component.get_qty_multiplier(part.qty_multiplier)
    ]:
        bom_entries.append(
            {
                "description": part.description,
                "qty": part.qty * component.get_qty_multiplier(part.qty_multiplier),
                "unit": part.unit,
                "designators": component.name if component.show_name else None,
                **optional_fields(part),
            }
        )
    return bom_entries


def bom_entry_key(entry: BOMEntry) -> BOMKey:
    """Return a tuple of string values from the dict that must be equal to join BOM entries."""
    if "key" not in entry:
        entry["key"] = tuple(
            clean_whitespace(make_str(entry.get(c))) for c in BOM_COLUMNS_IN_KEY
        )
    return entry["key"]


def generate_bom(harness: Harness) -> list[BOMEntry]:
    """Return a list of BOM entries generated from the harness."""
    bom_entries = []
    # connectors
    for connector in harness.connectors.values():
        if not connector.ignore_in_bom:
            description = (
                "Connector"
                + (f", {connector.type}" if connector.type else "")
                + (f", {connector.subtype}" if connector.subtype else "")
                + (f", {connector.pincount} pins" if connector.show_pincount else "")
                + (
                    f", {translate_color(connector.color, harness.options.color_mode)}"
                    if connector.color
                    else ""
                )
            )
            bom_entries.append(
                {
                    "description": description,
                    "designators": connector.name if connector.show_name else None,
                    **optional_fields(connector),
                }
            )

        # add connectors aditional components to bom
        bom_entries.extend(get_additional_component_bom(connector))

    # cables
    # TODO: If category can have other non-empty values than 'bundle', maybe it should be part of description?
    for cable in harness.cables.values():
        if not cable.ignore_in_bom:
            if cable.category != "bundle":
                # process cable as a single entity
                description = (
                    "Cable"
                    + (f", {cable.type}" if cable.type else "")
                    + (f", {cable.wirecount}")
                    + (
                        f" x {cable.gauge} {cable.gauge_unit}"
                        if cable.gauge
                        else " wires"
                    )
                    + (" shielded" if cable.shield else "")
                    + (
                        f", {translate_color(cable.color, harness.options.color_mode)}"
                        if cable.color
                        else ""
                    )
                )
                bom_entries.append(
                    {
                        "description": description,
                        "qty": cable.length,
                        "unit": cable.length_unit,
                        "designators": cable.name if cable.show_name else None,
                        **optional_fields(cable),
                    }
                )
            else:
                # add each wire from the bundle to the bom
                for index, color in enumerate(cable.colors):
                    description = (
                        "Wire"
                        + (f", {cable.type}" if cable.type else "")
                        + (f", {cable.gauge} {cable.gauge_unit}" if cable.gauge else "")
                        + (
                            f", {translate_color(color, harness.options.color_mode)}"
                            if color
                            else ""
                        )
                    )
                    bom_entries.append(
                        {
                            "description": description,
                            "qty": cable.length,
                            "unit": cable.length_unit,
                            "designators": cable.name if cable.show_name else None,
                            **{
                                k: index_if_list(v, index)
                                for k, v in optional_fields(cable).items()
                            },
                        }
                    )

        # add cable/bundles aditional components to bom
        bom_entries.extend(get_additional_component_bom(cable))

    # add harness aditional components to bom directly, as they both are List[BOMEntry]
    bom_entries.extend(harness.additional_bom_items)

    # remove line breaks if present and cleanup any resulting whitespace issues
    bom_entries = [
        {k: clean_whitespace(v) for k, v in entry.items()} for entry in bom_entries
    ]

    # deduplicate bom
    bom = []
    for _, group in groupby(sorted(bom_entries, key=bom_entry_key), key=bom_entry_key):
        group_entries = list(group)
        designators = sum(
            (make_list(entry.get("designators")) for entry in group_entries), []
        )
        total_qty = sum(entry.get("qty", 1) for entry in group_entries)
        bom.append(
            {
                **group_entries[0],
                "qty": int(total_qty)
                if float(total_qty).is_integer()
                else round(total_qty, 3),
                "designators": sorted(set(designators)),
            }
        )

    # add an incrementing id to each bom entry
    return [{**entry, "id": index} for index, entry in enumerate(bom, 1)]


def get_bom_index(bom: list[BOMEntry], target: BOMKey) -> int:
    """Return id of BOM entry or raise exception if not found."""
    for entry in bom:
        if bom_entry_key(entry) == target:
            return entry["id"]
    raise Exception("Internal error: No BOM entry found matching: " + "|".join(target))


def bom_list(bom: list[BOMEntry]) -> list[list[str]]:
    """Return list of BOM rows as lists of column strings with headings in top row."""
    keys = list(BOM_COLUMNS_ALWAYS)  # Always include this fixed set of BOM columns.
    for fieldname in BOM_COLUMNS_OPTIONAL:
        # Include only those optional BOM columns that are in use.
        if any(entry.get(fieldname) for entry in bom):
            keys.append(fieldname)
    # Custom mapping from internal name to BOM column headers.
    # Headers not specified here are generated by capitilising the internal name.
    bom_headings = {
        "pn": HEADER_PN,
        "mpn": HEADER_MPN,
        "spn": HEADER_SPN,
    }
    return [
        [bom_headings.get(k, k.capitalize()) for k in keys]
    ] + [  # Create header row with key names
        [make_str(entry.get(k)) for k in keys] for entry in bom
    ]  # Create string list for each entry row


def component_table_entry(
    type: str,
    qty: int | float,
    unit: str | None = None,
    bgcolor: Color | None = None,
    pn: str | None = None,
    manufacturer: str | None = None,
    mpn: str | None = None,
    supplier: str | None = None,
    spn: str | None = None,
) -> str:
    """Return a diagram node table row string with an additional component."""
    part_number_list = [
        pn_info_string(HEADER_PN, None, pn),
        pn_info_string(HEADER_MPN, manufacturer, mpn),
        pn_info_string(HEADER_SPN, supplier, spn),
    ]
    output = (
        f"{qty}"
        + (f" {unit}" if unit else "")
        + f" x {type}"
        + ("<br/>" if any(part_number_list) else "")
        + (", ".join([pn for pn in part_number_list if pn]))
    )
    # format the above output as left aligned text in a single visible cell
    # indent is set to two to match the indent in the generated html table
    return f"""<table border="0" cellspacing="0" cellpadding="3" cellborder="1"{html_bgcolor_attr(bgcolor)}><tr>
   <td align="left" balign="left">{html_line_breaks(output)}</td>
  </tr></table>"""


def pn_info_string(
    header: str, name: str | None, number: str | None
) -> str | None:
    """Return the company name and/or the part number in one single string or None otherwise."""
    number = str(number).strip() if number is not None else ""
    if name or number:
        return f'{name if name else header}{": " + number if number else ""}'
    else:
        return None


def index_if_list(value: Any, index: int) -> Any:
    """Return the value indexed if it is a list, or simply the value otherwise."""
    return value[index] if isinstance(value, list) else value


def make_list(value: Any) -> list:
    """Return value if a list, empty list if None, or single element list otherwise."""
    return value if isinstance(value, list) else [] if value is None else [value]


def make_str(value: Any) -> str:
    """Return comma separated elements if a list, empty string if None, or value as a string otherwise."""
    return ", ".join(str(element) for element in make_list(value))
