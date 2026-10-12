"""The one place that imports openpyxl. Everything in the program gets openpyxl names from here,
because the XML writer has to be chosen before openpyxl is imported: with lxml installed openpyxl
writes the same workbook with different bytes (namespace declarations, `<x/>` against `<x />`), so
the output hashes would differ between a developer checkout and the packaged program. Forcing the
plain-Python writer makes them agree. If openpyxl was imported earlier with lxml in use (by code
that did not come through here), it is imported again, so the bytes still agree."""

import os
import sys

os.environ["OPENPYXL_LXML"] = "False"

if "openpyxl.xml" in sys.modules and sys.modules["openpyxl.xml"].LXML:
    for _name in [n for n in sys.modules if n == "openpyxl" or n.startswith("openpyxl.")]:
        del sys.modules[_name]

import openpyxl.xml  # noqa: E402  (after the variable is set, on purpose)
from openpyxl import Workbook, load_workbook  # noqa: E402
from openpyxl.cell import WriteOnlyCell  # noqa: E402
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE  # noqa: E402

PLAIN_WRITER: bool = openpyxl.xml.LXML is False

__all__ = ["ILLEGAL_CHARACTERS_RE", "PLAIN_WRITER", "Workbook", "WriteOnlyCell", "load_workbook"]
