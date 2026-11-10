# SPDX-FileCopyrightText: 2026 0h3xn4
# SPDX-License-Identifier: GPL-3.0-only
"""S8: the expression language of declarative extensions is small, safe and exact.

What is checked: the parser accepts the documented grammar and refuses everything else, with the
column of the problem (never `eval`, attribute access, a call outside the whitelist, a name that
begins with an underscore); the evaluator follows the documented arithmetic, three-valued logic and
tolerance; and nothing in the module hands text to Python's own evaluator."""

import ast
from pathlib import Path

import pytest

from harness_design_studio.core.extensions import expr
from harness_design_studio.core.extensions.expr import (
    Env,
    ExprError,
    ExprRuntimeError,
    Vocabulary,
    evaluate,
    parse,
    render,
)

VOCAB = Vocabulary(
    fields=frozenset(
        {"wire.gauge_awg", "wire.category", "wire.length_m", "wire.current_a", "harness.id"}
    ),
    settings=frozenset({"derating.max_voltage_drop_v"}),
    params=frozenset({"max_awg", "limit"}),
    lookups=frozenset({"ampacity"}),
)


class FakeEnv(Env):
    def __init__(self, **fields: object) -> None:
        self.fields = fields

    def field(self, scope: str, name: str) -> expr.Value:
        return self.fields.get(f"{scope}.{name}")  # type: ignore[return-value]

    def setting(self, name: str) -> expr.Value:
        return {"derating.max_voltage_drop_v": 0.5}.get(name)

    def param(self, name: str) -> expr.Value:
        return {"max_awg": 22, "limit": 2.0}.get(name)

    def lookup(self, table: str, key: expr.Value) -> expr.Value:
        return {20: 11.0, 22: 7.0}.get(key) if table == "ampacity" else None  # type: ignore[arg-type]


def ev(text: str, **fields: object) -> expr.Value:
    return evaluate(
        parse(text, VOCAB), FakeEnv(**{k.replace("__", "."): v for k, v in fields.items()})
    )


# ---- what the parser refuses ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "fragment"),
    [
        ("__import__('os').system('x')", "underscore"),
        ("wire.gauge_awg.__class__", "underscore"),
        ("wire.gauge_awg.real", "attribute access"),
        ("harness.id.upper()", "attribute access"),
        ("open('/etc/passwd')", "not in the whitelist"),
        ("eval('1')", "not in the whitelist"),
        ("exec('x')", "not in the whitelist"),
        ("print(1)", "not in the whitelist"),
        ("getattr(wire, 'x')", "not in the whitelist"),
        ("wire.nothing", "unknown field"),
        ("project.name", "not a scope"),
        ("wire", "not a value"),
        ("x", "not a value"),
        ("1 +", "ends too early"),
        ("(1 + 2", "')' was expected"),
        ("1 2", "not expected here"),
        ("wire.gauge_awg = 3", "use '=='"),
        ("wire.gauge_awg < 3 < 5", "cannot be chained"),
        ("2 ** wire.gauge_awg", "whole number"),
        ("2 ** 99", "whole number"),
        ("'open", "not closed"),
        ("lambda: 1", "not part of the expression language"),
        ("[x for x in y]", "not a value"),
        ("param('nope')", "unknown parameter"),
        ("lookup('nope', 1)", "unknown lookup table"),
        ("setting('derating.nope')", "unknown setting"),
        ("setting(wire.category)", "text in quotes"),
        ("round()", "takes 1 to 2"),
        ("1 if 2 else 3", "not expected"),
        ("", "empty"),
        ("   ", "empty"),
        ("a; b", "not part of the expression language"),
        ("1 // 2", "value was expected"),
        ("wire.gauge_awg @ 2", "not part of the expression language"),
        ("{1: 2}", "not part of the expression language"),
        ("`ls`", "not part of the expression language"),
        ("x" * 700, "longer than"),
    ],
)
def test_the_parser_refuses_what_is_not_in_the_language(text: str, fragment: str) -> None:
    with pytest.raises(ExprError) as err:
        parse(text, VOCAB)
    assert fragment in err.value.message, err.value.message
    assert err.value.column >= 1


def test_a_refusal_names_the_column_and_a_close_name() -> None:
    with pytest.raises(ExprError) as err:
        parse("wire.gauge_awg <= 3 and wire.gauge_awx > 1", VOCAB)
    assert err.value.column == 25 and "did you mean wire.gauge_awg" in err.value.message
    with pytest.raises(ExprError) as err:
        parse("rond(1)", VOCAB)
    assert "did you mean round" in err.value.message


def test_a_deep_or_long_expression_is_refused_not_evaluated() -> None:
    with pytest.raises(ExprError, match="nested too deeply"):
        parse("(" * 40 + "1" + ")" * 40, VOCAB)
    with pytest.raises(ExprError, match="too long"):
        parse(" + ".join(["1"] * 130), VOCAB)
    with pytest.raises(ExprError, match="more than 50"):
        parse("[" + ",".join(["1"] * 60) + "]", VOCAB)


# ---- what it works out ------------------------------------------------------------------------------------


def test_arithmetic_comparison_and_functions_on_hand_values() -> None:
    assert ev("1 + 2 * 3") == 7
    assert ev("(1 + 2) * 3") == 9
    assert ev("2 ** 3") == 8
    assert ev("-2 ** 2") == -4
    assert ev("10 % 4") == 2
    assert ev("7 / 2") == 3.5
    assert ev("round(2.567, 1)") == 2.6
    assert ev("abs(-3)") == 3 and ev("min(3, 1, 2)") == 1 and ev("max(3, 1, 2)") == 3
    assert ev("floor(2.9)") == 2 and ev("ceil(2.1)") == 3 and ev("sqrt(16)") == 4
    assert ev("upper('ab')") == "AB" and ev("lower('AB')") == "ab" and ev("len('abc')") == 3
    assert ev("startswith('power', 'po')") is True and ev("endswith('power', 'x')") is False
    assert ev("contains('power', 'owe')") is True
    assert ev("'a' in ['a', 'b']") is True and ev("3 in [1, 2]") is False
    assert ev("if(1 < 2, 'yes', 'no')") == "yes"
    assert ev("wire.gauge_awg <= param('max_awg')", wire__gauge_awg=20) is True
    assert ev("wire.gauge_awg <= param('max_awg')", wire__gauge_awg=24) is False
    assert ev("setting('derating.max_voltage_drop_v') * 2") == 1.0
    assert ev("lookup('ampacity', wire.gauge_awg)", wire__gauge_awg=22) == 7.0
    assert ev("lookup('ampacity', wire.gauge_awg)", wire__gauge_awg=21) is None


def test_the_comparisons_use_the_tolerance_of_the_built_in_rules() -> None:
    """A value within one billionth of its limit is at the limit (definition D-LIMIT-TOLERANCE)."""
    assert ev("a.x <= 1.0".replace("a.x", "wire.current_a"), wire__current_a=1.0 + 1e-12) is True
    assert ev("wire.current_a < 1.0", wire__current_a=1.0 - 1e-12) is False
    assert ev("wire.current_a >= 1.0", wire__current_a=1.0 - 1e-12) is True
    assert ev("wire.current_a > 1.0", wire__current_a=1.0 + 1e-12) is False
    assert ev("wire.current_a == 1.0", wire__current_a=1.0 + 1e-12) is True
    assert ev("wire.current_a <= 1.0", wire__current_a=1.001) is False


def test_an_unknown_value_stays_unknown_and_logic_has_three_values() -> None:
    assert ev("wire.length_m + 1") is None
    assert ev("wire.length_m <= 3") is None
    assert ev("not (wire.length_m <= 3)") is None
    assert ev("wire.length_m == null") is True
    assert ev("wire.length_m != null") is False
    assert ev("false and wire.length_m <= 3") is False
    assert ev("true and wire.length_m <= 3") is None
    assert ev("true or wire.length_m <= 3") is True
    assert ev("false or wire.length_m <= 3") is None
    assert ev("min(1, wire.length_m)") is None
    assert ev("if(wire.length_m <= 3, 1, 2)") is None
    assert ev("1 in wire.length_m") is None


def test_a_type_mismatch_is_a_runtime_error_for_that_object_not_a_crash() -> None:
    for text in (
        "'a' + 1",
        "'a' < 1",
        "-'a'",
        "not 1",
        "1 and 2",
        "abs('x')",
        "upper(1)",
        "1 in 2",
        "1 / 0",
        "sqrt(-1)",
        "round(1.5, 20)",
        "len(3)",
    ):
        with pytest.raises(ExprRuntimeError):
            ev(text)


def test_a_result_that_is_not_a_number_is_refused() -> None:
    with pytest.raises(ExprRuntimeError, match="finite"):
        ev(" * ".join(["999999 ** 6"] * 10))


def test_the_deciding_comparison_gives_the_actual_value_and_the_limit() -> None:
    env = FakeEnv(**{"wire.gauge_awg": 24, "wire.category": "power"})
    node = parse("wire.category == 'power' and wire.gauge_awg <= param('max_awg')", VOCAB)
    leaf = expr.deciding_compare(node, env)
    assert leaf is not None and leaf.op == "<="
    assert evaluate(leaf.left, env) == 24 and evaluate(leaf.right, env) == 22
    assert expr.deciding_compare(parse("not (1 < 2)", VOCAB), env) is None


def test_render_gives_one_form_and_reads_back_the_same() -> None:
    for text in (
        "wire.gauge_awg <= param('max_awg')",
        "wire.category == 'power' and (wire.gauge_awg > 3 or wire.length_m < 1)",
        "not (wire.gauge_awg > 3)",
        "round(wire.length_m * 2, 3) + -1",
        "'a' in ['a', 'b']",
        "lookup('ampacity', wire.gauge_awg) - setting('derating.max_voltage_drop_v')",
    ):
        once = render(parse(text, VOCAB))
        assert render(parse(once, VOCAB)) == once
    assert render(parse('wire.category == "power"', VOCAB)) == "wire.category == 'power'"
    assert expr.fields_used(parse("wire.gauge_awg + wire.gauge_awg + harness.id", VOCAB)) == [
        "wire.gauge_awg",
        "harness.id",
    ]


def test_the_module_never_hands_text_to_the_python_evaluator() -> None:
    """No eval, exec, compile, __import__, ast, getattr or import machinery in the language."""
    src = Path(expr.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = {
        "eval",
        "exec",
        "compile",
        "__import__",
        "getattr",
        "setattr",
        "globals",
        "locals",
        "vars",
        "open",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in banned, node.func.id
        if isinstance(node, ast.Import):
            assert not {a.name for a in node.names} & {"ast", "importlib", "builtins", "os", "sys"}
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in {"ast", "importlib", "builtins", "os", "sys"}
