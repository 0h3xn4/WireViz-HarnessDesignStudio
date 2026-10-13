"""Extract the requirements of the five compliance standards into compliance/requirements/*.csv.

Usage: python -m tools.extract_requirements STANDARDS_FOLDER

STANDARDS_FOLDER holds the five PDFs (they are not part of the repository; they are ECSS and ESA
publications). The script needs `pdftotext` (poppler). Requirement IDs, clause numbers, texts and the
applicability tables (ECSS-E-ST-40C Table R-1, ECSS-Q-ST-80C Table D-2) are read from the documents;
nothing is cited from memory. Columns that are a judgement (type, harness relevance, automation) are
proposals, listed with `basis` and reviewed in compliance/gap_analysis.md; per-requirement
corrections are in compliance/requirements/overrides.csv and are merged here.
"""

import csv
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "compliance" / "requirements"
TEXT_LIMIT = 600

STANDARDS = {
    "ECSS-E-ST-40C": "ECSS-E-ST-40C-Rev.1(30April2025).pdf",
    "ECSS-Q-ST-80C": "ECSS-Q-ST-80C-Rev.2(30April2025).pdf",
    "ECSS-Q-ST-30-11C": "ECSS-Q-ST-30-11C-Rev.2(23June2021).pdf",
    "ECSS-E-ST-20-07C": "ECSS-E-ST-20-07C-Rev.2(3January2022).pdf",
    "ESCC-3901": "escc3901iss4-4.pdf",
}
PROCESS_STANDARDS = ("ECSS-E-ST-40C", "ECSS-Q-ST-80C")
DESIGN_STANDARDS = ("ECSS-Q-ST-30-11C", "ECSS-E-ST-20-07C", "ESCC-3901")

ID_LINE = re.compile(r"^\s*(ECSS-[A-Z]-ST-[0-9-]+_\d+)\s*$")
HEADING = re.compile(
    r"^\s{0,24}((?:[A-Z]\.\d+(?:\.\d+)*)|(?:\d+(?:\.\d+)+)|(?:\d{1,2}))\s{2,}(\S.*?)\s*$"
)
# top-level headings such as "6.12 Connectors RF" use a single space and no indent
HEADING_TOP = re.compile(r"^((?:\d+\.\d+))\s([A-Z]\S.*?)\s*$")
FOOTER = re.compile(
    r"^\s*(ECSS-[A-Z]-ST-[0-9A-Za-z-]+C Rev\.\d+|\d{1,2} \w+ \d{4}|\d{1,3})\s*$|^\s*\f"
)
LETTER = re.compile(r"^\s*([a-z])\.\s+(.*)")
NONNORMATIVE = re.compile(r"^\s*(NOTE|EXAMPLE)s?\b")
EXPECTED = re.compile(r"^\s*EXPECTED OUTPUT")
TOC_DOTS = re.compile(r"\.{4,}")

HARNESS_WORDS = re.compile(
    r"\b(cable|cables|wire|wires|wiring|harness|harnesses|connector|connectors|contact|contacts|"
    r"shield|shields|shielding|shielded|twist|twisted|bundle|bundles|backshell|braid|"
    r"harnessing|bonding|bonded|grounding|segregat\w*|separation|routing|conductor|conductors|"
    r"coax\w*|pin|pins|insulation|screen)\b",
    re.I,
)


@dataclass
class Req:
    standard: str
    id: str
    clause: str = ""
    title: str = ""
    letter: str = ""
    text: str = ""
    expected_output: str = ""
    deleted: bool = False
    kind: str = ""
    extra: dict[str, str] = field(default_factory=dict)


def to_text(pdf: Path) -> list[str]:
    done = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    )
    return done.stdout.splitlines()


def squeeze(lines: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(x.strip() for x in lines)).strip()


def parse_ecss(standard: str, lines: list[str]) -> list[Req]:
    """Requirements are introduced by an ID line; the clause is the nearest heading above."""
    reqs: list[Req] = []
    clause = title = ""
    current: Req | None = None
    body: list[str] = []
    outputs: list[str] = []
    mode = ""

    def close() -> None:
        nonlocal current, body, outputs, mode
        if current is not None:
            text = squeeze(body)
            m = LETTER.match(text)
            if m:
                current.letter, text = m.group(1), m.group(2)
            current.deleted = text.startswith("<<deleted")
            current.text = text
            current.expected_output = squeeze(outputs)
            reqs.append(current)
        current, body, outputs, mode = None, [], [], ""

    for line in lines:
        if ID_LINE.match(line):
            close()
            current = Req(standard, ID_LINE.match(line).group(1), clause, title)  # type: ignore[union-attr]
            mode = "text"
            continue
        top = HEADING_TOP.match(line)
        h = top or HEADING.match(line)
        if h and not TOC_DOTS.search(line) and (top or not line.strip().endswith(("-", ","))):
            number, name = h.group(1), h.group(2)
            if name[0].isupper() or name.startswith("<<") or name == ".":
                close()
                clause, title = number, name
                continue
        if current is None:
            continue
        if FOOTER.match(line) or not line.strip():
            continue
        if EXPECTED.match(line):
            mode = "output"
            outputs.append(line)
            continue
        if NONNORMATIVE.match(line):
            mode = "skip"
            continue
        if mode == "text":
            body.append(line)
        elif mode == "output":
            outputs.append(line)
    close()
    return reqs


def parse_escc3901(lines: list[str]) -> list[Req]:
    """ESCC 3901 has no requirement IDs: one record per numbered clause of the body, in clause form."""
    reqs: list[Req] = []
    start = next(
        (i for i, ln in enumerate(lines) if re.match(r"^1\s+INTRODUCTION\s*$", ln) and i > 150), 0
    )
    clause = title = ""
    body: list[str] = []

    def close() -> None:
        text = squeeze(body)
        if clause and text and "shall" in text:
            reqs.append(
                Req("ESCC-3901", f"ESCC3901-{clause}", clause, title, "", text, deleted=False)
            )

    for line in lines[start:]:
        h = re.match(r"^\s{0,6}(\d+(?:\.\d+)*)\s{2,}(\S.*?)\s*$", line)
        if h and not TOC_DOTS.search(line) and not re.search(r"\s\d+\s*$", h.group(2)[-6:]):
            close()
            clause, title, body = h.group(1), h.group(2), []
            continue
        if re.match(r"^\s*(ESCC Generic Specification|No\. 3901|PAGE|ISSUE)", line):
            continue
        body.append(line)
    close()
    return reqs


# ---- applicability tables (process standards) ----------------------------------------------------


def applicability_e40(lines: list[str]) -> dict[str, tuple[str, str, str, str]]:
    """Table R-1 lists a requirement (5.5.3.2c) or each expected output of it (5.5.3.2a eo a);
    the outputs of one requirement are combined (all Y gives Y, otherwise the values joined by /)."""
    start = next(i for i, ln in enumerate(lines) if "Table R-1: Criticality applicability" in ln)
    cell = r"(Y\w*|N\w*|-|See)"
    row = re.compile(
        rf"^(\d+(?:\.\d+)+[a-z]?)(?:\s+eo\s+[a-z]+)?\s+(.*?)\s+{cell}\s+{cell}\s+{cell}\s+(\S.*?)\s*$"
    )
    seen: dict[str, list[tuple[str, str, str, str]]] = {}
    for line in lines[start:]:
        m = row.match(line)
        if m:
            seen.setdefault(m.group(1), []).append((m.group(3), m.group(4), m.group(5), m.group(6)))
    return {
        key: tuple("/".join(sorted({v[k] for v in vals})) for k in range(4))  # type: ignore[misc]
        for key, vals in seen.items()
    }


def applicability_q80(lines: list[str]) -> dict[str, tuple[str, str, str, str]]:
    start = next(i for i, ln in enumerate(lines) if "Table D-2: Applicability matrix" in ln)
    out: dict[str, tuple[str, str, str, str]] = {}
    for line in lines[start:]:
        m = re.match(
            r"^\s*(\d+(?:\.\d+)*[a-z]?)\s+(?:.*?\s{2,})?([YN-])\s{2,}([YN-])\s{2,}([YN-])\s{2,}(\S.*?)\s*$",
            line,
        )
        if m:
            out[m.group(1)] = (m.group(2), m.group(3), m.group(4), m.group(5))
    return out


def lookup(
    table: dict[str, tuple[str, str, str, str]], clause: str, letter: str
) -> tuple[str, str, str, str] | None:
    keys = [f"{clause}{letter}", clause]
    parts = clause.split(".")
    keys += [".".join(parts[:k]) for k in range(len(parts) - 1, 0, -1)]
    for k in keys:
        if k in table and table[k] != ("-", "-", "-", "-"):
            return table[k]
    return None


# ---- proposals -----------------------------------------------------------------------------------


def propose_type(r: Req) -> str:
    t = r.text.lower()
    if r.deleted:
        return "deleted"
    if r.text.startswith(("Table", "Figure")):
        return "design-rule" if r.standard in DESIGN_STANDARDS else "documentation"
    if re.search(
        r"\b(document|record|report|plan|file|drd|specification|manual|minutes|log)\b", t
    ) and re.search(
        r"\bshall\b.*\b(be )?(document|record|report|provid|includ|prepar|deliver|issue|maintain|list)",
        t,
    ):
        return "documentation"
    if r.standard in PROCESS_STANDARDS:
        if re.search(
            r"\b(software|product)\b.*\bshall\b.*\b(provide|perform|implement|compute|calculate|accept|reject|support|detect|report)",
            t,
        ):
            return "functional" if "supplier" not in t[:40] else "process"
        return "process"
    if re.search(
        r"\b(verify|verified|verification|test|tested|analysis|demonstrat|inspection|review|approv|waiv|customer|supplier)\b",
        t,
    ) and not re.search(
        r"\b(derat|margin|limit|maximum|minimum|shall be (less|greater|lower|higher|at least|below|above))",
        t,
    ):
        return "process"
    if r.standard in DESIGN_STANDARDS:
        return "design-rule"
    return "product"


def harness_relevant(r: Req) -> bool:
    """Proposal: does the requirement concern wires, cables, connectors, contacts or harnesses?"""
    if r.standard == "ECSS-Q-ST-30-11C":
        if r.clause.startswith(("5.", "6.11", "6.12", "6.32")):
            return True
        if r.clause[:1].isdigit() and r.clause.split(".")[0] == "6":
            return False  # the other component families (capacitors, diodes, ...)
        return bool(HARNESS_WORDS.search(r.text))
    return bool(HARNESS_WORDS.search(r.text) or HARNESS_WORDS.search(r.title))


def propose_automation(r: Req, relevant: bool) -> str:
    if not relevant or r.deleted:
        return "n/a"
    t = r.text.lower()
    if re.search(
        r"\b(analysis|test|tested|verified|verification|inspection|review|approved|customer|justif|demonstrat)\b",
        t,
    ):
        return "human"
    if re.search(
        r"\d|table|\bshall (not )?(be )?(less|greater|lower|higher|below|above|at least|separated|segregated|twisted|shielded|bonded)",
        t,
    ):
        return "partial"
    return "human"


def load_overrides() -> dict[str, dict[str, str]]:
    path = OUT / "overrides.csv"
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row["ID"]: row for row in csv.DictReader(f)}


def write(
    standard: str, reqs: list[Req], tables: dict[str, tuple[str, str, str, str]] | None
) -> None:
    overrides = load_overrides()
    OUT.mkdir(parents=True, exist_ok=True)
    header = ["ID", "clause", "letter", "clause_title", "text", "type", "deleted"]
    if standard == "ECSS-E-ST-40C":
        header += ["expected_output"]
    if standard in PROCESS_STANDARDS:
        header += ["cat_A", "cat_B", "cat_C", "cat_D"]
    else:
        header += ["harness_relevant", "automation"]
    header += ["basis", "note"]
    with (OUT / f"{standard}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in reqs:
            ov = overrides.get(r.id, {})
            text = r.text if len(r.text) <= TEXT_LIMIT else r.text[: TEXT_LIMIT - 1] + "…"
            row = [
                r.id,
                r.clause,
                r.letter,
                r.title,
                text,
                ov.get("type") or propose_type(r),
                "Y" if r.deleted else "",
            ]
            if standard == "ECSS-E-ST-40C":
                row.append(r.expected_output[:TEXT_LIMIT])
            if standard in PROCESS_STANDARDS:
                found = lookup(tables or {}, r.clause, r.letter)
                if found is None:
                    if not r.clause[:1].isdigit():
                        found = ("DRD",) * 4  # content of a document: applies when it is required
                    elif r.clause.startswith("6.2.9"):
                        found = (
                            "transversal",
                        ) * 4  # security: applied independently of criticality
                    else:
                        found = ("not listed",) * 4  # no row in the applicability table: review
                row += list(found)
            else:
                rel = harness_relevant(r)
                row += [
                    ov.get("harness_relevant") or ("Y" if rel else "N"),
                    ov.get("automation")
                    or propose_automation(
                        r, ov.get("harness_relevant", "Y" if rel else "N") == "Y"
                    ),
                ]
            row += ["reviewed" if ov else "proposed", ov.get("note", "")]
            w.writerow(row)


def main(folder: str) -> int:
    base = Path(folder)
    absent = [base / name for name in STANDARDS.values() if not (base / name).is_file()]
    for (
        pdf
    ) in absent:  # before any list is rewritten, so a missing PDF leaves all of them as they were
        print(f"missing: {pdf}", file=sys.stderr)
    if absent:
        return 2
    for standard, name in STANDARDS.items():
        pdf = base / name
        lines = to_text(pdf)
        tables = None
        if standard == "ECSS-E-ST-40C":
            tables = applicability_e40(lines)
        elif standard == "ECSS-Q-ST-80C":
            tables = applicability_q80(lines)
        reqs = parse_escc3901(lines) if standard == "ESCC-3901" else parse_ecss(standard, lines)
        write(standard, reqs, tables)
        live = [r for r in reqs if not r.deleted]
        print(
            f"{standard}: {len(reqs)} requirements ({len(reqs) - len(live)} deleted)"
            + (f", {len(tables)} applicability rows" if tables else "")
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
