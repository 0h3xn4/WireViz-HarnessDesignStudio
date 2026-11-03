"""The built-in items, registered through the same call an extension uses.

`install()` fills `registry.REGISTRY` once: the design rules of `drc.RULES`, the fields of `fields.py`,
the calculation models of the `model` settings, the output tables that `export` writes and the
readers of outside files. Nothing here changes how any of them runs; the registry lists them so that
`harness-design-studio extensions DIR` shows what the tool has and what a project added, in one table.
"""

from harness_design_studio import __version__

from .fields import BUILTIN_FIELDS
from .registry import BUILTIN, FIELD, IMPORTER, MODEL, REGISTRY, RULE, TABLE, Item

_INSTALLED = False

# (name, what the file is, the function that makes it: a reference for the reader) of the tables
# `export` writes
_TABLES = (
    ("wirelist", "Wire list of a harness (harnesses/ID/wirelist.csv).", "tables.wire_list"),
    (
        "pinouts",
        "Pinouts of the connectors of a harness (harnesses/ID/pinouts.csv).",
        "tables.pinouts",
    ),
    ("bom", "Bill of materials of a harness and of the system (bom.csv).", "tables.bom"),
    (
        "mass_length",
        "Mass and length of a harness and of the system (mass_length.csv).",
        "tables.mass_length",
    ),
    ("tests", "Continuity and isolation tests of a harness (tests.csv).", "tables.tests"),
    ("labels", "Wire and connector labels of a harness (labels.csv).", "tables.labels"),
    (
        "accessories",
        "Accessories of a harness that has some (accessories.csv).",
        "tables.accessories",
    ),
    (
        "mating_matrix",
        "Which connector mates with which (system/mating_matrix.csv).",
        "tables.mating_matrix",
    ),
    (
        "traceability",
        "Interfaces, harnesses and requirements (system/traceability.csv).",
        "tables.traceability",
    ),
    (
        "box_pinouts",
        "Pinouts of the device connectors (system/box_pinouts.csv).",
        "tables.box_pinouts",
    ),
    (
        "connections",
        "The connection list of a project with links (system/connections.csv).",
        "connections.connection_rows",
    ),
    (
        "drc_findings",
        "Every finding of the logical checks and the design rules (system/drc_findings.csv).",
        "build.findings_table",
    ),
    ("changelog", "The change log (system/changelog.csv).", "vcs.report.changelog_rows"),
)

_IMPORTERS = (
    (
        "parts",
        "Parts with their approval status and ratings (import-parts).",
        "library_import.plan_parts_import",
    ),
    ("lengths", "Wire lengths (import-lengths).", "generate.lengths.plan_length_import"),
    (
        "build-data",
        "Strip lengths, contacts and accessories (import-build-data).",
        "build_data_import.plan_build_data_import",
    ),
    ("netlist", "A KiCad netlist (import-netlist).", "kicad.plan_netlist_import"),
    ("pinout", "A device pinout from a table (import-pinout).", "pinout_import.plan_pinout_import"),
    (
        "devices",
        "Devices from a device library file (import-devices).",
        "device_library.plan_device_import",
    ),
    ("interfaces", "Interfaces from a table (the import wizard).", "imports.plan_interface_import"),
)


def install() -> None:
    """Register the built-in items. Safe to call again."""
    global _INSTALLED
    if _INSTALLED:
        return
    from harness_design_studio.core import settings
    from harness_design_studio.core.drc.rules import RULES

    for r in RULES:
        REGISTRY.register(Item(RULE, r.id, __version__, BUILTIN, doc=r.topic, obj=r))
    for d in BUILTIN_FIELDS:
        REGISTRY.register(Item(FIELD, d.id, __version__, BUILTIN, doc=d.doc, obj=d))
    for s in settings.SETTINGS:
        if s.file == "model" and s.kind == "choice":
            REGISTRY.register(
                Item(
                    MODEL,
                    f"model.{s.key}",
                    __version__,
                    BUILTIN,
                    doc=f"{s.label}: {', '.join(s.choices)} (default {s.default}).",
                    obj=s,
                )
            )
    for name, doc, ref in _TABLES:
        REGISTRY.register(Item(TABLE, name, __version__, BUILTIN, doc=doc, obj=ref))
    for name, doc, ref in _IMPORTERS:
        REGISTRY.register(Item(IMPORTER, name, __version__, BUILTIN, doc=doc, obj=ref))
    _INSTALLED = True
