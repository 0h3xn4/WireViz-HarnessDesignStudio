"""The expression language of declarative extensions (D-191 (5), S8).

A small language that can only read documented values and do arithmetic with them. It is parsed by
the hand-written parser below and evaluated by the tree walker below; nothing is ever handed to
Python's own evaluator, to `ast`, to `eval` or to `exec`, and no name of the language reaches a
Python object: a *field* is a name of a table the tool registers, a *function* is a name of the
whitelist in `FUNCTIONS`. Whatever is not in these tables is refused when the file is read, with the
position in the expression.

    wire.gauge_awg <= param('max_awg')              a comparison (the usual form of a condition)
    wire.category == 'power' and wire.mm2 >= 0.5     and, or, not
    round(wire.voltage_drop_v / wire.current_a, 4)   arithmetic and functions
    lookup('ampacity-custom', wire.gauge_awg)        a table of the extension file
    setting('derating.max_voltage_drop_v')           a setting of the project (config/*.json)

Grammar, from the loosest binding to the tightest::

    expression := and ("or" and)*
    and        := not ("and" not)*
    not        := "not" not | comparison
    comparison := sum (("==" | "!=" | "<" | "<=" | ">" | ">=" | "in") sum)?      (not chained)
    sum        := product (("+" | "-") product)*
    product    := unary (("*" | "/" | "%") unary)*
    unary      := "-" unary | power
    power      := atom ("**" unary)?                       (the exponent is a whole number 0 to 6)
    atom       := number | text | true | false | null | "[" list "]" | "(" expression ")"
                | scope "." field | function "(" arguments ")"

A value that is not known (a wire without a length) is `null`: arithmetic with it gives `null`, an
ordering comparison with it gives `null`, and a condition that is `null` is "not checked", never
"passed" and never "failed". `and` and `or` follow the usual three-valued logic (false and null is
false, true or null is true). Comparisons with `<=`, `>=`, `==` and the others use the tool's own
tolerance (a value within one billionth of its limit is at the limit, D-LIMIT-TOLERANCE), the same as
the built-in rules, so an extension rule and a built-in rule agree at the exact limit.
"""

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TypeGuard

from harness_design_studio.core.generate.sizing import exceeds

MAX_LENGTH = 600  # characters of one expression
MAX_NODES = 120
MAX_DEPTH = 24
MAX_EXPONENT = 6  # "**": a whole number from 0 to this one

type Value = float | int | str | bool | None | list[Value]


class ExprError(ValueError):
    """The expression cannot be read: `column` is the 1-based position of the first problem."""

    def __init__(self, message: str, column: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.column = column


class ExprRuntimeError(ValueError):
    """The expression is fine but cannot be worked out for one object (a text added to a number)."""


# ---- the tree -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Const:
    value: Value


@dataclass(frozen=True)
class ListOf:
    items: tuple[Node, ...]


@dataclass(frozen=True)
class Field:
    scope: str
    name: str

    @property
    def id(self) -> str:
        return f"{self.scope}.{self.name}"


@dataclass(frozen=True)
class Unary:
    op: str  # "-" | "not"
    operand: Node


@dataclass(frozen=True)
class Binary:
    op: str  # + - * / % ** and or
    left: Node
    right: Node


@dataclass(frozen=True)
class Compare:
    op: str  # == != < <= > >= in
    left: Node
    right: Node


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple[Node, ...]


type Node = Const | ListOf | Field | Unary | Binary | Compare | Call


# ---- what the parser may accept ------------------------------------------------------------------


@dataclass(frozen=True)
class Vocabulary:
    """The names an expression may use. `fields` are "scope.name"; the others are the names of the
    settings ("derating.max_voltage_drop_v"), the parameters and the lookup tables that exist."""

    fields: frozenset[str]
    settings: frozenset[str] = frozenset()
    params: frozenset[str] = frozenset()
    lookups: frozenset[str] = frozenset()

    @property
    def scopes(self) -> frozenset[str]:
        return frozenset(f.partition(".")[0] for f in self.fields)


# ---- functions -----------------------------------------------------------------------------------


def _num(x: object) -> TypeGuard[int | float]:
    return isinstance(x, int | float) and not isinstance(x, bool)


def _numbers(name: str, args: Sequence[object]) -> list[float] | None:
    """The arguments as numbers; None when one is not known; an error when one is not a number."""
    if any(a is None for a in args):
        return None
    numbers: list[float] = []
    for a in args:
        if not _num(a):
            raise ExprRuntimeError(f"{name}() works on numbers")
        numbers.append(float(a))
    return numbers


def _f_abs(x: Value) -> Value:
    n = _numbers("abs", [x])
    return None if n is None else abs(n[0])


def _f_min(*xs: Value) -> Value:
    n = _numbers("min", xs)
    return None if n is None else min(n)


def _f_max(*xs: Value) -> Value:
    n = _numbers("max", xs)
    return None if n is None else max(n)


def _f_round(x: Value, digits: Value = 0) -> Value:
    n = _numbers("round", [x, digits])
    if n is None:
        return None
    if n[1] != int(n[1]) or not 0 <= n[1] <= 9:
        raise ExprRuntimeError("round() takes a whole number of digits from 0 to 9")
    return round(n[0], int(n[1]))


def _f_floor(x: Value) -> Value:
    n = _numbers("floor", [x])
    return None if n is None else math.floor(n[0])


def _f_ceil(x: Value) -> Value:
    n = _numbers("ceil", [x])
    return None if n is None else math.ceil(n[0])


def _f_sqrt(x: Value) -> Value:
    n = _numbers("sqrt", [x])
    if n is None:
        return None
    if n[0] < 0:
        raise ExprRuntimeError("sqrt() of a negative number")
    return math.sqrt(n[0])


def _text(name: str, *xs: Value) -> list[str] | None:
    if any(x is None for x in xs):
        return None
    if not all(isinstance(x, str) for x in xs):
        raise ExprRuntimeError(f"{name}() works on text")
    return [str(x) for x in xs]


def _f_lower(x: Value) -> Value:
    t = _text("lower", x)
    return None if t is None else t[0].lower()


def _f_upper(x: Value) -> Value:
    t = _text("upper", x)
    return None if t is None else t[0].upper()


def _f_startswith(x: Value, y: Value) -> Value:
    t = _text("startswith", x, y)
    return None if t is None else t[0].startswith(t[1])


def _f_endswith(x: Value, y: Value) -> Value:
    t = _text("endswith", x, y)
    return None if t is None else t[0].endswith(t[1])


def _f_contains(x: Value, y: Value) -> Value:
    t = _text("contains", x, y)
    return None if t is None else t[1] in t[0]


def _f_len(x: Value) -> Value:
    if x is None:
        return None
    if isinstance(x, str | list):
        return len(x)
    raise ExprRuntimeError("len() works on text and lists")


# name -> (function, fewest arguments, most arguments, one line for the documentation)
FUNCTIONS: dict[str, tuple[Callable[..., Value], int, int, str]] = {
    "abs": (_f_abs, 1, 1, "absolute value"),
    "min": (_f_min, 1, 8, "the smallest of the numbers"),
    "max": (_f_max, 1, 8, "the largest of the numbers"),
    "round": (_f_round, 1, 2, "round(x, digits): rounded to 0 to 9 decimals"),
    "floor": (_f_floor, 1, 1, "the whole number below"),
    "ceil": (_f_ceil, 1, 1, "the whole number above"),
    "sqrt": (_f_sqrt, 1, 1, "square root"),
    "lower": (_f_lower, 1, 1, "text in lower case"),
    "upper": (_f_upper, 1, 1, "text in upper case"),
    "startswith": (_f_startswith, 2, 2, "startswith(text, start): true when the text begins so"),
    "endswith": (_f_endswith, 2, 2, "endswith(text, end): true when the text ends so"),
    "contains": (_f_contains, 2, 2, "contains(text, part): true when the part is in the text"),
    "len": (_f_len, 1, 1, "the length of a text or a list"),
}
# Special forms, worked out by the evaluator because they read the environment or choose a branch.
SPECIAL = {
    "if": "if(condition, then, otherwise): only the chosen branch is worked out",
    "setting": "setting('file.key'): the value a setting has in this project (its default when unset)",
    "param": "param('name'): a parameter of the extension file (`parameters`)",
    "lookup": "lookup('table', key): a value of a lookup table of the extension file",
}
CALLABLE_NAMES = tuple(sorted({*FUNCTIONS, *SPECIAL}))
KEYWORDS = frozenset({"and", "or", "not", "in", "true", "false", "null"})


# ---- the tokens ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Token:
    kind: str  # "num" "str" "name" "op" "end"
    text: str
    value: Value
    column: int


_TWO = ("==", "!=", "<=", ">=", "**")
_ONE = "+-*/%()[],.<>"


def tokenize(text: str) -> list[Token]:
    if len(text) > MAX_LENGTH:
        raise ExprError(f"the expression is longer than {MAX_LENGTH} characters", MAX_LENGTH)
    tokens: list[Token] = []
    i = 0
    while i < len(text):
        ch = text[i]
        col = i + 1
        if ch in " \t":
            i += 1
        elif ch.isdigit() or (ch == "." and text[i + 1 : i + 2].isdigit()):
            j = i
            while j < len(text) and (text[j].isdigit() or text[j] == "."):
                j += 1
            if j < len(text) and text[j] in "eE" and text[j + 1 : j + 2] in tuple("0123456789+-"):
                j += 2
                while j < len(text) and text[j].isdigit():
                    j += 1
            raw = text[i:j]
            try:
                number = float(raw)
            except ValueError:
                raise ExprError(f"{raw!r} is not a number", col) from None
            if not math.isfinite(number):
                raise ExprError(f"{raw!r} is not a finite number", col)
            tokens.append(Token("num", raw, int(raw) if raw.isdigit() else number, col))
            i = j
        elif ch in "'\"":
            j = i + 1
            chars: list[str] = []
            while j < len(text) and text[j] != ch:
                if text[j] == "\\" and text[j + 1 : j + 2] in (ch, "\\"):
                    j += 1
                chars.append(text[j])
                j += 1
            if j >= len(text):
                raise ExprError("a text is not closed", col)
            tokens.append(Token("str", text[i : j + 1], "".join(chars), col))
            i = j + 1
        elif ch.isalpha():
            j = i
            while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                j += 1
            word = text[i:j]
            tokens.append(Token("name", word, word, col))
            i = j
        elif ch == "_":
            raise ExprError("a name cannot begin with an underscore", col)
        elif text[i : i + 2] in _TWO:
            tokens.append(Token("op", text[i : i + 2], text[i : i + 2], col))
            i += 2
        elif ch in _ONE:
            tokens.append(Token("op", ch, ch, col))
            i += 1
        elif ch == "=":
            raise ExprError("'=' is not an operator here; use '==' to compare", col)
        else:
            raise ExprError(f"the character {ch!r} is not part of the expression language", col)
    tokens.append(Token("end", "", None, len(text) + 1))
    return tokens


# ---- the parser ----------------------------------------------------------------------------------


def _close(word: str, choices: Sequence[str]) -> str:
    """ " (did you mean ...?)" for the closest of the choices, else an empty text."""
    import difflib

    hit = difflib.get_close_matches(word, list(choices), n=1, cutoff=0.6)
    return f" (did you mean {hit[0]}?)" if hit else ""


class _Parser:
    def __init__(self, text: str, vocab: Vocabulary) -> None:
        self.tokens = tokenize(text)
        self.pos = 0
        self.vocab = vocab
        self.nodes = 0

    @property
    def tok(self) -> Token:
        return self.tokens[self.pos]

    def take(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def is_op(self, *ops: str) -> bool:
        return self.tok.kind == "op" and self.tok.text in ops

    def is_word(self, *words: str) -> bool:
        return self.tok.kind == "name" and self.tok.text in words

    def expect(self, op: str) -> None:
        if not self.is_op(op):
            raise ExprError(f"'{op}' was expected here", self.tok.column)
        self.pos += 1

    def count(self, column: int) -> None:
        self.nodes += 1
        if self.nodes > MAX_NODES:
            raise ExprError(f"the expression is too long (more than {MAX_NODES} parts)", column)

    def parse(self) -> Node:
        node = self.expression(0)
        if self.tok.kind != "end":
            raise ExprError(f"'{self.tok.text}' is not expected here", self.tok.column)
        return node

    def expression(self, depth: int) -> Node:
        if depth > MAX_DEPTH:
            raise ExprError("the expression is nested too deeply", self.tok.column)
        left = self.and_(depth)
        while self.is_word("or"):
            col = self.take().column
            self.count(col)
            left = Binary("or", left, self.and_(depth))
        return left

    def and_(self, depth: int) -> Node:
        left = self.not_(depth)
        while self.is_word("and"):
            col = self.take().column
            self.count(col)
            left = Binary("and", left, self.not_(depth))
        return left

    def not_(self, depth: int) -> Node:
        if self.is_word("not"):
            col = self.take().column
            self.count(col)
            return Unary("not", self.not_(depth + 1))
        return self.comparison(depth)

    def comparison(self, depth: int) -> Node:
        left = self.sum_(depth)
        if self.is_op("==", "!=", "<", "<=", ">", ">=") or self.is_word("in"):
            tok = self.take()
            self.count(tok.column)
            node = Compare(tok.text, left, self.sum_(depth))
            if self.is_op("==", "!=", "<", "<=", ">", ">=") or self.is_word("in"):
                raise ExprError(
                    "comparisons cannot be chained; join them with 'and'", self.tok.column
                )
            return node
        return left

    def sum_(self, depth: int) -> Node:
        left = self.product(depth)
        while self.is_op("+", "-"):
            tok = self.take()
            self.count(tok.column)
            left = Binary(tok.text, left, self.product(depth))
        return left

    def product(self, depth: int) -> Node:
        left = self.unary(depth)
        while self.is_op("*", "/", "%"):
            tok = self.take()
            self.count(tok.column)
            left = Binary(tok.text, left, self.unary(depth))
        return left

    def unary(self, depth: int) -> Node:
        if self.is_op("-"):
            col = self.take().column
            self.count(col)
            return Unary("-", self.unary(depth + 1))
        return self.power(depth)

    def power(self, depth: int) -> Node:
        base = self.atom(depth)
        if self.is_op("**"):
            tok = self.take()
            self.count(tok.column)
            exponent = self.unary(depth + 1)
            if not (
                isinstance(exponent, Const)
                and _num(exponent.value)
                and float(exponent.value) == int(exponent.value)
                and 0 <= float(exponent.value) <= MAX_EXPONENT
            ):
                raise ExprError(
                    f"the exponent must be a whole number from 0 to {MAX_EXPONENT}", tok.column
                )
            return Binary("**", base, exponent)
        return base

    def atom(self, depth: int) -> Node:
        tok = self.tok
        self.count(tok.column)
        if tok.kind == "num" or tok.kind == "str":
            self.pos += 1
            return Const(tok.value)
        if self.is_op("("):
            self.pos += 1
            node = self.expression(depth + 1)
            self.expect(")")
            return node
        if self.is_op("["):
            self.pos += 1
            items: list[Node] = []
            while not self.is_op("]"):
                items.append(self.expression(depth + 1))
                if self.is_op(","):
                    self.pos += 1
                elif not self.is_op("]"):
                    raise ExprError("',' or ']' was expected here", self.tok.column)
            self.pos += 1
            if len(items) > 50:
                raise ExprError("a list of more than 50 items", tok.column)
            return ListOf(tuple(items))
        if tok.kind == "name":
            return self.name(depth)
        raise ExprError(
            "a value was expected here" if tok.kind != "end" else "the expression ends too early",
            tok.column,
        )

    def name(self, depth: int) -> Node:
        tok = self.take()
        word = tok.text
        if word in ("true", "false", "null"):
            return Const({"true": True, "false": False, "null": None}[word])
        if word in KEYWORDS:
            raise ExprError(f"'{word}' cannot be used here", tok.column)
        if self.is_op("("):
            return self.call(tok, depth)
        if self.is_op("."):
            return self.field(tok)
        scopes = sorted(self.vocab.scopes)
        raise ExprError(
            f"'{word}' is not a value; a field is written scope.name, with the scope one of "
            f"{', '.join(scopes)}" + _close(word, [*scopes, *CALLABLE_NAMES]),
            tok.column,
        )

    def field(self, scope_tok: Token) -> Node:
        scope = scope_tok.text
        self.pos += 1  # the dot
        if self.tok.kind != "name":
            raise ExprError("a field name was expected after the dot", self.tok.column)
        name_tok = self.take()
        if self.is_op("."):
            raise ExprError(
                "attribute access is not allowed: a field is scope.name and nothing more",
                self.tok.column,
            )
        if self.is_op("("):
            raise ExprError(
                "methods cannot be called: only the functions of the list", self.tok.column
            )
        fid = f"{scope}.{name_tok.text}"
        if fid not in self.vocab.fields:
            same_scope = sorted(f for f in self.vocab.fields if f.startswith(scope + "."))
            if not same_scope:
                raise ExprError(
                    f"'{scope}' is not a scope here (use one of {', '.join(sorted(self.vocab.scopes))})"
                    + _close(scope, sorted(self.vocab.scopes)),
                    scope_tok.column,
                )
            raise ExprError(f"unknown field '{fid}'" + _close(fid, same_scope), scope_tok.column)
        return Field(scope, name_tok.text)

    def call(self, tok: Token, depth: int) -> Node:
        name = tok.text
        if name not in FUNCTIONS and name not in SPECIAL:
            raise ExprError(
                f"the function '{name}' is not in the whitelist ({', '.join(CALLABLE_NAMES)})"
                + _close(name, CALLABLE_NAMES),
                tok.column,
            )
        self.expect("(")
        args: list[Node] = []
        while not self.is_op(")"):
            args.append(self.expression(depth + 1))
            if self.is_op(","):
                self.pos += 1
            elif not self.is_op(")"):
                raise ExprError("',' or ')' was expected here", self.tok.column)
        self.pos += 1
        self.check_call(tok, name, args)
        return Call(name, tuple(args))

    def check_call(self, tok: Token, name: str, args: list[Node]) -> None:
        if name in FUNCTIONS:
            _fn, low, high, _doc = FUNCTIONS[name]
            if not low <= len(args) <= high:
                want = str(low) if low == high else f"{low} to {high}"
                raise ExprError(f"{name}() takes {want} argument(s), not {len(args)}", tok.column)
            return
        wanted = {"if": 3, "setting": 1, "param": 1, "lookup": 2}[name]
        if len(args) != wanted:
            raise ExprError(f"{name}() takes {wanted} argument(s), not {len(args)}", tok.column)
        if name == "if":
            return
        first = args[0]
        if not (isinstance(first, Const) and isinstance(first.value, str)):
            raise ExprError(f"the first argument of {name}() must be a text in quotes", tok.column)
        known = {
            "setting": self.vocab.settings,
            "param": self.vocab.params,
            "lookup": self.vocab.lookups,
        }[name]
        if first.value not in known:
            what = {"setting": "setting", "param": "parameter", "lookup": "lookup table"}[name]
            raise ExprError(
                f"unknown {what} '{first.value}'" + _close(first.value, sorted(known)), tok.column
            )


def parse(text: str, vocab: Vocabulary) -> Node:
    """The tree of an expression, or `ExprError` with the column of the first problem."""
    if not isinstance(text, str) or not text.strip():
        raise ExprError("the expression is empty", 1)
    return _Parser(text, vocab).parse()


# ---- reading the tree ------------------------------------------------------------------------------


def walk(node: Node) -> list[Node]:
    """Every node of the tree, parents before children, left to right."""
    out: list[Node] = [node]
    kids: tuple[Node, ...] = ()
    if isinstance(node, ListOf):
        kids = node.items
    elif isinstance(node, Unary):
        kids = (node.operand,)
    elif isinstance(node, Binary | Compare):
        kids = (node.left, node.right)
    elif isinstance(node, Call):
        kids = node.args
    for k in kids:
        out += walk(k)
    return out


def fields_used(node: Node) -> list[str]:
    """The fields the expression reads, each once, in the order they appear."""
    return list(dict.fromkeys(n.id for n in walk(node) if isinstance(n, Field)))


def literal_text(node: Node) -> str:
    """The text of a call's first argument, which the parser has checked is a text in quotes."""
    return str(node.value) if isinstance(node, Const) else ""


def calls_used(node: Node, name: str) -> list[str]:
    """The literal first arguments of `setting`, `param` or `lookup` calls, each once."""
    return list(
        dict.fromkeys(
            literal_text(n.args[0]) for n in walk(node) if isinstance(n, Call) and n.name == name
        )
    )


_PRECEDENCE = {"or": 1, "and": 2, "==": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4, "in": 4,
               "+": 5, "-": 5, "*": 6, "/": 6, "%": 6, "**": 8}  # fmt: skip


def _show_const(v: Value) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    return f"{v:g}" if isinstance(v, float) else str(v)


def render(node: Node, parent: int = 0) -> str:
    """The expression as text in one fixed form (spaces around operators, quotes as `'`), with
    brackets only where the order of working needs them."""
    if isinstance(node, Const):
        return _show_const(node.value)
    if isinstance(node, Field):
        return node.id
    if isinstance(node, ListOf):
        return "[" + ", ".join(render(i) for i in node.items) + "]"
    if isinstance(node, Call):
        return f"{node.name}(" + ", ".join(render(a) for a in node.args) + ")"
    if isinstance(node, Unary):
        if node.op == "not":
            text = "not " + render(node.operand, 3)
            return f"({text})" if parent > 3 else text
        return "-" + render(node.operand, 7)
    prec = _PRECEDENCE[node.op]
    text = f"{render(node.left, prec)} {node.op} {render(node.right, prec + 1)}"
    return f"({text})" if prec < parent else text


# ---- working it out ----------------------------------------------------------------------------------


class Env:
    """What an expression reads. The extension code gives the real one; tests give simple ones."""

    def field(self, scope: str, name: str) -> Value:
        raise NotImplementedError

    def setting(self, name: str) -> Value:
        raise NotImplementedError

    def param(self, name: str) -> Value:
        raise NotImplementedError

    def lookup(self, table: str, key: Value) -> Value:
        raise NotImplementedError


@dataclass
class Trace:
    """Optional record of what was read while an expression was worked out."""

    fields: dict[str, Value] = field(default_factory=dict)
    settings: dict[str, Value] = field(default_factory=dict)
    params: dict[str, Value] = field(default_factory=dict)
    lookups: list[tuple[str, Value, Value]] = field(default_factory=list)


def _checked(x: Value) -> Value:
    if isinstance(x, float) and not math.isfinite(x):
        raise ExprRuntimeError("the result is not a finite number")
    return x


def _arith(op: str, a: Value, b: Value) -> Value:
    if a is None or b is None:
        return None
    if not (_num(a) and _num(b)):
        raise ExprRuntimeError(f"'{op}' works on numbers")
    x, y = float(a), float(b)
    if op == "+":
        return _checked(x + y)
    if op == "-":
        return _checked(x - y)
    if op == "*":
        return _checked(x * y)
    if y == 0:
        raise ExprRuntimeError("division by zero")
    if op == "/":
        return _checked(x / y)
    if op == "%":
        return _checked(math.fmod(x, y))
    return _checked(x**y)  # "**": the exponent was checked when the expression was read


def _equal(a: Value, b: Value) -> bool:
    if _num(a) and _num(b):
        return not exceeds(float(a), float(b)) and not exceeds(float(b), float(a))
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_equal(x, y) for x, y in zip(a, b, strict=True))
    return type(a) is type(b) and a == b


def compare(op: str, a: Value, b: Value) -> bool | None:
    """One comparison with the tool's tolerance; None when a side is not known (ordering only)."""
    if op == "==":
        return _equal(a, b)
    if op == "!=":
        return not _equal(a, b)
    if op == "in":
        if b is None:
            return None
        if not isinstance(b, list):
            raise ExprRuntimeError("'in' needs a list on its right")
        return any(_equal(a, x) for x in b)
    if a is None or b is None:
        return None
    if isinstance(a, str) and isinstance(b, str):
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]
    if not (_num(a) and _num(b)):
        raise ExprRuntimeError(f"'{op}' compares two numbers or two texts")
    x, y = float(a), float(b)
    if op == "<=":
        return not exceeds(x, y)
    if op == ">=":
        return not exceeds(y, x)
    if op == ">":
        return exceeds(x, y)
    return exceeds(y, x)  # "<"


def evaluate(node: Node, env: Env, trace: Trace | None = None) -> Value:
    """The value of the tree. `ExprRuntimeError` when the types do not fit the operation."""
    if isinstance(node, Const):
        return node.value
    if isinstance(node, ListOf):
        return [evaluate(i, env, trace) for i in node.items]
    if isinstance(node, Field):
        value = env.field(node.scope, node.name)
        if trace is not None:
            trace.fields[node.id] = value
        return value
    if isinstance(node, Unary):
        v = evaluate(node.operand, env, trace)
        if node.op == "not":
            if v is None:
                return None
            if not isinstance(v, bool):
                raise ExprRuntimeError("'not' works on true or false")
            return not v
        if v is None:
            return None
        if not _num(v):
            raise ExprRuntimeError("'-' works on numbers")
        return -v
    if isinstance(node, Compare):
        return compare(node.op, evaluate(node.left, env, trace), evaluate(node.right, env, trace))
    if isinstance(node, Binary):
        if node.op in ("and", "or"):
            return _logic(node, env, trace)
        return _arith(node.op, evaluate(node.left, env, trace), evaluate(node.right, env, trace))
    return _call(node, env, trace)


def _truth(op: str, v: Value) -> bool | None:
    if v is None or isinstance(v, bool):
        return v
    raise ExprRuntimeError(f"'{op}' works on true or false")


def _logic(node: Binary, env: Env, trace: Trace | None) -> Value:
    decisive = node.op == "or"  # a true decides "or", a false decides "and"
    left = _truth(node.op, evaluate(node.left, env, trace))
    if left is decisive:
        return decisive
    right = _truth(node.op, evaluate(node.right, env, trace))
    if right is decisive:
        return decisive
    return None if left is None or right is None else (not decisive)


def _call(node: Call, env: Env, trace: Trace | None) -> Value:
    name = node.name
    if name == "if":
        cond = _truth("if", evaluate(node.args[0], env, trace))
        if cond is None:
            return None
        return evaluate(node.args[1 if cond else 2], env, trace)
    if name in ("setting", "param"):
        key = literal_text(node.args[0])
        value = env.setting(key) if name == "setting" else env.param(key)
        if trace is not None:
            (trace.settings if name == "setting" else trace.params)[key] = value
        return value
    if name == "lookup":
        table = literal_text(node.args[0])
        key_value = evaluate(node.args[1], env, trace)
        found = env.lookup(table, key_value)
        if trace is not None:
            trace.lookups.append((table, key_value, found))
        return found
    fn = FUNCTIONS[name][0]
    return _checked(fn(*[evaluate(a, env, trace) for a in node.args]))


def deciding_compare(node: Node, env: Env) -> Compare | None:
    """The comparison that makes a condition false (the first one that is false in an `and`, the
    first of all in an `or`): the actual value and the limit of a finding come from it."""
    if isinstance(node, Compare):
        return node
    if isinstance(node, Binary) and node.op in ("and", "or"):
        for side in (node.left, node.right):
            try:
                v = evaluate(side, env)
            except ExprRuntimeError:
                continue
            if v is False or node.op == "or":
                found = deciding_compare(side, env)
                if found is not None:
                    return found
    return None
