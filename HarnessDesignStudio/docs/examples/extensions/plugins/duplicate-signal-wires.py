# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""An example plug-in: a rule that no two wires of a harness carry the same signal between the
same two connectors. A declarative rule cannot do this, because it looks at one object at a time;
Python can compare the wires of a harness with each other.

This file runs with the rights of the person who trusts it. Read it before you do.
"""

from collections import defaultdict

PLUGIN = {
    "name": "duplicate-signal-wires",
    "version": "1.0.0",
    "api": 1,
    "kinds": ["rule"],
    "description": "Two wires of one harness with the same signal between the same two connectors.",
}


def register(api):
    def check(project):
        for h in sorted(project.harnesses.values(), key=lambda x: x.id):
            seen = defaultdict(list)
            for w in h.wires:
                if w.signal:
                    seen[(w.signal, w.from_connector, w.to_connector)].append(w.id)
            for (signal, a, b), ids in sorted(seen.items()):
                if len(ids) > 1:
                    wires = ", ".join(sorted(ids))
                    yield api.Hit(
                        h.id,
                        f"{h.id} has {len(ids)} wires for {signal} from {a} to {b} ({wires})",
                        key=f"{signal}.{a}.{b}",
                    )

    api.rule(
        "x-duplicate-signal-wires",
        title="Duplicate signal wires",
        severity="warning",
        why=(
            "Two wires for one signal between the same two connectors are usually a mistake, "
            "and a pair of wires in parallel is not what the interface describes."
        ),
        how="Delete one of the wires, or give the second a signal name of its own.",
        compares=(
            "the signal and the two connectors of each wire of a harness "
            "with those of the other wires of the same harness"
        ),
        check=check,
    )
