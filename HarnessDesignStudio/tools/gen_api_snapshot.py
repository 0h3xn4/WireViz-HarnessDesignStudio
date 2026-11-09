# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""Write tests/fixtures/api_snapshot.json: the names in `harness_design_studio.api.__all__`, the
signature of every function, the fields of every result type and the base classes of every
exception. A test (`tests/test_api_stability.py`) fails when the interface differs from the file, so
a change to it is a decision: run this on purpose, read the diff, and follow
docs/developer/api-stability.md. Usage: python -m tools.gen_api_snapshot"""

import annotationlib
import dataclasses
import inspect
import json
from pathlib import Path
from typing import Any

from harness_design_studio import api

TARGET = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "api_snapshot.json"


def _signature(fn: Any) -> str:
    return str(inspect.signature(fn, annotation_format=annotationlib.Format.STRING))


def snapshot() -> dict[str, Any]:
    functions: dict[str, str] = {}
    types: dict[str, Any] = {}
    errors: dict[str, list[str]] = {}
    constants: dict[str, str] = {}
    for name in api.__all__:
        obj = getattr(api, name)
        if inspect.isclass(obj) and issubclass(obj, BaseException):
            errors[name] = [b.__name__ for b in obj.__mro__[1:] if b is not object]
        elif inspect.isclass(obj) and dataclasses.is_dataclass(obj):
            hints = annotationlib.get_annotations(obj, format=annotationlib.Format.STRING)
            types[name] = {
                "fields": {f.name: hints[f.name] for f in dataclasses.fields(obj)},
                "methods": {
                    m: _signature(getattr(obj, m))
                    for m in sorted(vars(obj))
                    if not m.startswith("_") and inspect.isfunction(getattr(obj, m))
                },
            }
        elif inspect.isclass(obj):
            types[name] = {"fields": {}, "methods": {}, "external": True}
        elif callable(obj):
            functions[name] = _signature(obj)
        else:
            constants[name] = repr(obj)
    return {
        "api_version": api.API_VERSION,
        "all": sorted(api.__all__),
        "constants": dict(sorted(constants.items())),
        "functions": dict(sorted(functions.items())),
        "types": dict(sorted(types.items())),
        "errors": dict(sorted(errors.items())),
    }


def render() -> str:
    return json.dumps(snapshot(), indent=1, sort_keys=True) + "\n"


def main() -> None:
    TARGET.write_text(render(), encoding="utf-8")
    print(f"wrote {TARGET}")


if __name__ == "__main__":
    main()
