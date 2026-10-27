"""The words of a release blocker for a person at the screen (Release 1.9, W1).

`core.vcs.release` words its blockers for both the screen and the command line, so some of them
quote a command (`harness-design-studio import-lengths DIR FILE`) or a flag (`--accept-placeholders`).
The command line keeps those words. On the screen they are replaced by the place in the program
that does the same, and nothing else in the sentence changes. No Qt here.
"""

import re
from typing import Final

from harness_design_studio.gui import strings

_REWRITES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"\s*\(`harness-design-studio config DIR` lists them\)"), ""),
    (re.compile(r"\s*\(command line: --accept-(?:placeholders|unapproved-parts) REASON\)"), ""),
    (
        re.compile(
            r"Fill in the derating values \(the file config/derating\.json; "
            r"`harness-design-studio config DIR` lists what is missing\) or set the gauge by hand\."
        ),
        strings.RELEASE_TEXT_GAUGE,
    ),
    (
        re.compile(
            r"Enter the routing segment lengths \(`harness-design-studio import-lengths DIR FILE` "
            r"loads them from a table\)\."
        ),
        strings.RELEASE_TEXT_LENGTHS,
    ),
)


def plain_blocker(message: str) -> str:
    """`message` without command-line words (a message that has none comes back as it was)."""
    for pattern, replacement in _REWRITES:
        message = pattern.sub(replacement, message)
    return message
