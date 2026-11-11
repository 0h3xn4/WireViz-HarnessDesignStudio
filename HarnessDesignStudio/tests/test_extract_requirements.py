# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""The footer test of tools/extract_requirements.py: rewritten as two patterns and a function
(CodeQL could not read the one pattern with an anchor between two alternatives); it accepts and
refuses exactly the lines the old pattern did."""

import re

import pytest

from tools.extract_requirements import is_footer

# The old pattern was these two alternatives joined by "|" (re.match tries both at the start)
OLD_TEXT = re.compile(r"^\s*(ECSS-[A-Z]-ST-[0-9A-Za-z-]+C Rev\.\d+|\d{1,2} \w+ \d{4}|\d{1,3})\s*$")
OLD_BREAK = re.compile(r"^\s*\f")
LINES = [
    "12", "  12  ", "123", "1234", "12\n", "  7 \n", "ECSS-Q-ST-80C Rev.2", " ECSS-E-ST-40C Rev.1 ",
    "ECSS-Q-ST-30-11C Rev.2", "ECSS-Q-ST-80C Rev.2 page", "30 April 2025", " 3 January 2022 ",
    "30 April 25", "\f", "\fNext page text", "  \f12", "\f12", "a 12", "12 a", "", "   ",
    "5.2.2.1 Specification", "The supplier shall", "\t12\t", "12\r\n", "x\f",
]  # fmt: skip


@pytest.mark.parametrize("line", LINES)
def test_the_footer_test_matches_the_old_pattern(line: str) -> None:
    assert is_footer(line) == bool(OLD_TEXT.match(line) or OLD_BREAK.match(line)), repr(line)
