"""Static scans of the source tree shared by the architecture, offline and security tests.

Plain AST walking, no imports of the scanned code. Relative imports are resolved against the
package of the file (`from ..gui import fonts` in core/units.py is harness_design_studio.gui.fonts),
and `importlib.import_module("x")` / `__import__("x")` count as imports of "x"."""

import ast
from pathlib import Path

DYNAMIC = "<dynamic import>"  # a computed module name: the scan cannot know what is imported
_IMPORTERS = {"import_module", "__import__"}
_OS_PROCESS = {"system", "popen", "startfile", "fork", "forkpty"}


def package_of(path: Path, root: Path) -> list[str]:
    """Dotted package of a file; `root` is the folder that holds the top-level package."""
    return list(path.relative_to(root).with_suffix("").parts[:-1])


def imported_names(path: Path, root: Path) -> set[str]:
    """Absolute dotted names a file imports (module and module.name for `from` imports)."""
    return imported_names_of(ast.parse(path.read_text(encoding="utf-8")), package_of(path, root))


def imported_names_of(tree: ast.AST, package: list[str]) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = len(package) - (node.level - 1)
                if keep < 1:  # beyond the top-level package
                    names.add(f"<outside the package>.{node.module or ''}")
                    continue
                base = [*package[:keep], *([node.module] if node.module else [])]
            else:
                base = (node.module or "").split(".") if node.module else []
            target = ".".join(base)
            if target:
                names.add(target)
            names.update(f"{target}.{a.name}" for a in node.names if a.name != "*" and target)
        elif isinstance(node, ast.Call) and _called_name(node) in _IMPORTERS:
            arg = node.args[0] if node.args else None
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                names.add(arg.value)
            else:
                names.add(DYNAMIC)
    return names


def _called_name(node: ast.Call) -> str | None:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


def process_or_browser_uses(tree: ast.AST) -> list[str]:
    """Uses of os.exec*/os.spawn*/os.system/os.popen (also `from os import ...`), of the
    webbrowser module and of QDesktopServices; whether it is a call or a reference."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            owner, attr = node.value.id, node.attr
            if owner == "os" and (
                attr in _OS_PROCESS or attr.startswith(("exec", "spawn", "posix_spawn"))
            ):
                found.append(f"os.{attr}")
            elif owner == "webbrowser":
                found.append(f"webbrowser.{attr}")
        if isinstance(node, ast.Name) and node.id == "QDesktopServices":
            found.append("QDesktopServices")
        if isinstance(node, ast.ImportFrom) and node.module == "os":
            found.extend(
                f"os.{a.name}"
                for a in node.names
                if a.name in _OS_PROCESS or a.name.startswith(("exec", "spawn", "posix_spawn"))
            )
    return sorted(set(found))
