"""The words that are the two ends of one line: a transmit word meets a receive word (1.9.0).

A signal name is split into words (`UART_TX` is UART, TX; `SPW_DOUT+` is SPW, DOUT, +; `TX_P` is TX,
P). A word of the transmit family meets the matching word of the receive family when everything
else in the two names is the same, so `TX` and `RX`, `UART_TX` and `UART_RX`, `MOSI` and `MISO`
are counterparts. The table of word pairs is the project's own: the key `signal_counterparts` of
`config/naming.json` (a list of pairs such as `["TX", "RX"]`, either word first). While the key is
not set the table below is used, which is the table the tool had before it became a setting. The
review of links (`links.py`) and the pairing proposal read the table from here. No Qt, no model.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass

# The table the tool ships with: the first word of each pair transmits, the second receives.
DEFAULT_COUNTERPARTS: tuple[tuple[str, str], ...] = (
    ("tx", "rx"),
    ("txd", "rxd"),
    ("txp", "rxp"),
    ("txn", "rxn"),
    ("dout", "din"),
    ("mosi", "miso"),
    ("sdo", "sdi"),
)

CONFIG_FILE = "naming"
CONFIG_KEY = "signal_counterparts"

_WORDS = re.compile(r"[a-z]+|\d+|[+-]")
_LETTERS = re.compile(r"[A-Za-z]+")


@dataclass(frozen=True)
class Counterparts:
    """A table of word pairs, ready to look words up. `counter` gives the word at the other end
    of the line, `side` says whether a word transmits or receives."""

    counter: Mapping[str, str]
    side: Mapping[str, str]

    @classmethod
    def of(cls, pairs: tuple[tuple[str, str], ...] | list[list[str]]) -> "Counterparts":
        counter: dict[str, str] = {}
        side: dict[str, str] = {}
        for x, y in pairs:
            x, y = x.casefold(), y.casefold()
            counter[x], counter[y] = y, x
            side[x], side[y] = "transmit", "receive"
        return cls(counter, side)

    def split(self, name: str) -> tuple[tuple[str, ...], str, tuple[str, ...]] | None:
        """(words before, transmit/receive word, words after) of a name in lower case, or None
        when the name has no word of the table."""
        words = _WORDS.findall(name)
        for k, w in enumerate(words):
            if w in self.side:
                return tuple(words[:k]), w, tuple(words[k + 1 :])
        return None

    def are_counterparts(self, x: str, y: str) -> bool:
        """True when two different names, in lower case, are the two ends of one line: the words
        of the table meet and everything else is the same (a prefix such as UART_ or SPW_ may be
        missing on one side)."""
        sx, sy = self.split(x), self.split(y)
        return bool(
            sx
            and sy
            and self.counter[sx[1]] == sy[1]
            and sx[2] == sy[2]
            and (sx[0] == sy[0] or not sx[0] or not sy[0])
        )


DEFAULT = Counterparts.of(DEFAULT_COUNTERPARTS)


def check_pairs(value: object) -> str | None:
    """Why a value is not a table of word pairs (None when it is one): a list of pairs of two
    different words, each made of letters only, and no word in two pairs (a word meets one word).
    Case does not matter. An empty list is a table with no pairs: only equal names are paired."""
    if not isinstance(value, list):
        return 'must be a list of pairs of words, for example [["TX", "RX"], ["MOSI", "MISO"]]'
    seen: set[str] = set()
    for pair in value:
        if not (
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(w, str) and _LETTERS.fullmatch(w) for w in pair)
        ):
            return (
                "must be a list of pairs of two words made of letters only (no digits, no signs), "
                'for example ["TX", "RX"]'
            )
        x, y = pair[0].casefold(), pair[1].casefold()
        if x == y:
            return f"has the pair '{pair[0]}' and '{pair[1]}', which is one word twice"
        for w in (x, y):
            if w in seen:
                return f"uses the word '{w}' in two pairs; a word meets one other word"
            seen.add(w)
    return None


def from_config(values: Mapping[str, object] | None) -> Counterparts:
    """The table of `config/naming.json`: its `signal_counterparts` when that is set and valid,
    else the table the tool ships with (an invalid one is reported by the configuration check)."""
    raw = values.get(CONFIG_KEY) if values else None
    if not isinstance(raw, list) or check_pairs(raw) is not None:
        return DEFAULT
    return Counterparts.of(raw)
