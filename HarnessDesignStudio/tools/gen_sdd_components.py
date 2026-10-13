"""Component table and requirement-to-component trace for the SDD (ECSS-E-ST-40C 5.5.2, Annex F 6).

A component is a module of the package under src/. The table lists its layer, its purpose (first
line of the module docstring), the components it imports, and the tool requirements (REQ-...) that
reach it: a requirement reaches a module when the module is named in its "Verified by" column, or
is imported (directly) by a test file named there. "Indirect" requirements reach it through the
components that are reached directly and depend on it (their code runs the module). Writes compliance/sdd_components.csv.
Exit code 1 if a module has no docstring (ECSS-E-ST-40C 5.5.2: purpose of each component).
"""

from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
HEADER = ["component", "layer", "purpose", "depends_on", "requirements", "requirements_indirect"]


def package() -> str:
    names = sorted(p.name for p in SRC.iterdir() if (p / "__init__.py").exists())
    return names[0]


def modules(pkg: str) -> dict[str, Path]:
    """Component id (path inside the package, no suffix, slash separated) -> file."""
    out = {}
    for p in sorted((SRC / pkg).rglob("*.py")):
        rel = p.relative_to(SRC / pkg).with_suffix("")
        out["/".join(rel.parts)] = p
    return out


def _component_of(dotted: str, pkg: str, known: set[str]) -> str | None:
    """Longest known component for an imported dotted name inside the package."""
    parts = dotted.split(".")
    if parts[0] != pkg:
        return None
    rest = parts[1:]
    while rest:
        for cand in ("/".join(rest), "/".join([*rest, "__init__"])):
            if cand in known:
                return cand
        rest = rest[:-1]
    return "__init__" if "__init__" in known else None


def imports(path: Path, pkg: str, known: set[str], own: str) -> set[str]:
    found: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module] + [f"{node.module}.{a.name}" for a in node.names]
        for n in names:
            c = _component_of(n, pkg, known)
            if c and c != own:
                found.add(c)
    return found


def purpose(path: Path) -> str:
    doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
    return doc.strip().splitlines()[0].strip() if doc else ""


def requirement_files() -> dict[str, list[str]]:
    import tools.trace as trace

    return {rid: trace.FILE.findall(verified) for rid, _t, _s, verified in trace.requirements()}


def build() -> list[list[str]]:
    pkg = package()
    mods = modules(pkg)
    known = set(mods)
    deps = {c: imports(p, pkg, known, c) for c, p in mods.items()}
    reach: dict[str, set[str]] = {c: set() for c in mods}
    for rid, files in requirement_files().items():
        for f in files:
            direct = f"src/{pkg}/"
            if f.startswith(direct):
                c = f[len(direct) :].removesuffix(".py")
                if c in reach:
                    reach[c].add(rid)
            elif f.startswith("tests/") and f.endswith(".py") and (ROOT / f).is_file():
                for c in imports(ROOT / f, pkg, known, ""):
                    reach[c].add(rid)
    indirect: dict[str, set[str]] = {c: set() for c in mods}
    for c in mods:
        seen: set[str] = set()
        todo = list(deps[c])
        while todo:
            d = todo.pop()
            if d not in seen:
                seen.add(d)
                todo.extend(deps[d])
        for d in seen:
            indirect[d] |= reach[c]
    rows = []
    for c, p in mods.items():
        layer = c.split("/")[0] if "/" in c else "(package)"
        rows.append(
            [
                c,
                layer,
                purpose(p),
                " ".join(sorted(deps[c])),
                " ".join(sorted(reach[c])),
                " ".join(sorted(indirect[c] - reach[c])),
            ]
        )
    return rows


def main() -> int:
    rows = build()
    out = ROOT / "compliance" / "sdd_components.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(rows)
    bare = [r[0] for r in rows if not r[2] and not r[0].endswith("__init__")]
    for c in bare:
        print(f"{c}: no module docstring")
    direct = sum(bool(r[4]) for r in rows)
    either = sum(bool(r[4] or r[5]) for r in rows)
    print(f"{len(rows)} components, {direct} reached directly, {either} directly or indirectly")
    return 1 if bare else 0


if __name__ == "__main__":
    sys.exit(main())
