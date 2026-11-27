"""Closed variable vocabulary and a tiny arithmetic parser for DERIVED variables (no eval)."""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

UNITS = frozenset({"percent", "point10", "point4", "credit", "period", "day", "semester", "vnd"})
TYPES = frozenset({"number", "integer", "boolean", "enum", "string", "date"})
INPUTS = frozenset({"USER", "DERIVED", "PROFILE", "RECORD"})


class DerivationInvalid(ArithmeticError):
    """Division by zero or a non-finite derived value."""


@dataclass(frozen=True)
class Variable:
    key: str
    type: str
    label: str
    input: str = "USER"
    unit: str | None = None
    min: float | None = None
    max: float | None = None
    step: float | None = None
    values: tuple[str, ...] = ()
    pattern: str | None = None
    derive: str | None = None
    help: str = ""

    @property
    def numeric(self) -> bool:
        return self.type in {"number", "integer"}

    @property
    def grid_step(self) -> float:
        if self.step:
            return float(self.step)
        return 1.0 if self.type == "integer" else 0.1


_TOKEN = re.compile(r"\s*(?:(\d+(?:\.\d+)?)|([A-Za-z_][A-Za-z0-9_.]*)|(.))")


def _tokens(text: str):
    pos, out = 0, []
    text = text.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise ValueError("bad expression")
        num, name, sym = m.groups()
        if num is not None:
            out.append(("num", float(num)))
        elif name is not None:
            out.append(("var", name))
        elif sym in "+-*/()":
            out.append(("sym", sym))
        else:
            raise ValueError(f"unsupported character {sym!r}")
        pos = m.end()
    return out


class Expr:
    """AST: ('num', x) | ('var', key) | ('neg', e) | (op, l, r)."""

    def __init__(self, text: str):
        self.text = text
        self._toks = _tokens(text)
        self._i = 0
        self.ast = self._sum()
        if self._i != len(self._toks):
            raise ValueError("trailing tokens")

    def _peek(self):
        return self._toks[self._i] if self._i < len(self._toks) else (None, None)

    def _take(self):
        tok = self._toks[self._i]
        self._i += 1
        return tok

    def _sum(self):
        node = self._prod()
        while self._peek() in {("sym", "+"), ("sym", "-")}:
            op = self._take()[1]
            node = (op, node, self._prod())
        return node

    def _prod(self):
        node = self._atom()
        while self._peek() in {("sym", "*"), ("sym", "/")}:
            op = self._take()[1]
            node = (op, node, self._atom())
        return node

    def _atom(self):
        kind, val = self._peek()
        if kind is None:
            raise ValueError("unexpected end")
        self._take()
        if kind == "num":
            return ("num", val)
        if kind == "var":
            return ("var", val)
        if (kind, val) == ("sym", "("):
            node = self._sum()
            if self._peek() != ("sym", ")"):
                raise ValueError("missing )")
            self._take()
            return node
        if (kind, val) == ("sym", "-"):
            return ("neg", self._atom())
        raise ValueError("unexpected token")

    def variables(self) -> tuple[str, ...]:
        seen: list[str] = []

        def walk(n):
            if n[0] == "var":
                if n[1] not in seen:
                    seen.append(n[1])
            elif n[0] in {"num"}:
                return
            else:
                for c in n[1:]:
                    walk(c)
        walk(self.ast)
        return tuple(seen)

    def evaluate(self, values: dict) -> float | None:
        """None when a needed base variable is missing; raises DerivationInvalid on /0."""
        def ev(n):
            k = n[0]
            if k == "num":
                return n[1]
            if k == "var":
                return values.get(n[1])
            if k == "neg":
                v = ev(n[1])
                return None if v is None else -v
            a, b = ev(n[1]), ev(n[2])
            if a is None or b is None:
                return None
            if k == "+":
                return a + b
            if k == "-":
                return a - b
            if k == "*":
                return a * b
            if b == 0:
                raise DerivationInvalid("division by zero")
            return a / b
        return ev(self.ast)


class Vocabulary:
    def __init__(self, variables: dict[str, Variable]):
        self.variables = variables
        self._exprs = {k: Expr(v.derive) for k, v in variables.items() if v.derive}
        for key, expr in self._exprs.items():
            for dep in expr.variables():
                if dep not in variables:
                    raise ValueError(f"{key}: unknown base variable {dep}")
        for key in self._exprs:  # no cycles
            self._order(key, ())

    def _order(self, key, stack):
        if key in stack:
            raise ValueError(f"derivation cycle at {key}")
        expr = self._exprs.get(key)
        if expr:
            for dep in expr.variables():
                self._order(dep, (*stack, key))

    def get(self, key) -> Variable | None:
        return self.variables.get(key)

    def expr(self, key) -> Expr | None:
        return self._exprs.get(key)

    def base_variables(self, key) -> tuple[str, ...]:
        expr = self._exprs.get(key)
        if not expr:
            return (key,)
        out: list[str] = []
        for dep in expr.variables():
            for b in self.base_variables(dep):
                if b not in out:
                    out.append(b)
        return tuple(out)

    def validate_inputs(self, inputs: dict) -> tuple[dict, list[dict]]:
        """Return (normalized, errors). Unknown / wrongly-typed / out-of-range values are errors."""
        clean: dict = {}
        errors: list[dict] = []
        for key, raw in inputs.items():
            var = self.variables.get(key)
            if var is None:
                errors.append({"var": key, "code": "UNKNOWN_VARIABLE"})
                continue
            if raw is None:
                continue
            value, code = _coerce(var, raw)
            if code:
                errors.append({"var": key, "code": code})
            else:
                clean[key] = value
        return clean, errors

    def resolve(self, inputs: dict) -> tuple[dict, dict, list[dict]]:
        """Compute derived values from base inputs. Returns (values, derived_info, errors)."""
        values = dict(inputs)
        derived: dict = {}
        errors: list[dict] = []

        def get(key):
            if key in values:
                return values[key]
            expr = self._exprs.get(key)
            if expr is None:
                return None
            base = {dep: get(dep) for dep in expr.variables()}
            if any(v is None for v in base.values()):
                return None
            try:
                result = expr.evaluate(base)
            except DerivationInvalid:
                errors.append({"var": key, "code": "DERIVATION_INVALID"})
                values[key] = None
                return None
            if result is None:
                return None
            values[key] = result
            derived[key] = {"from": base}
            return result

        for key in self.variables:
            get(key)
        return {k: v for k, v in values.items() if v is not None}, derived, errors


def _coerce(var: Variable, raw):
    t = var.type
    if t in {"number", "integer"}:
        if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
            return None, "TYPE_MISMATCH"
        try:
            val = float(raw) if not isinstance(raw, str) else float(raw.replace(",", "."))
        except ValueError:
            return None, "TYPE_MISMATCH"
        if val != val or val in (float("inf"), float("-inf")):
            return None, "TYPE_MISMATCH"
        if t == "integer":
            if val != int(val):
                return None, "TYPE_MISMATCH"
            val = int(val)
        if (var.min is not None and val < var.min) or (var.max is not None and val > var.max):
            return None, "OUT_OF_RANGE"
        return val, None
    if t == "boolean":
        if isinstance(raw, bool):
            return raw, None
        return None, "TYPE_MISMATCH"
    if t == "enum":
        if isinstance(raw, str) and raw in var.values:
            return raw, None
        return None, "OUT_OF_RANGE"
    if t == "string":
        if not isinstance(raw, str):
            return None, "TYPE_MISMATCH"
        if var.pattern and not re.fullmatch(var.pattern, raw):
            return None, "OUT_OF_RANGE"
        return raw, None
    if t == "date":
        if isinstance(raw, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
            return raw, None
        return None, "TYPE_MISMATCH"
    return None, "TYPE_MISMATCH"


def load_vocabulary(path: str | Path) -> Vocabulary:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    out: dict[str, Variable] = {}
    for key, spec in data.get("variables", {}).items():
        t = spec.get("type")
        if t not in TYPES:
            raise ValueError(f"{key}: bad type {t}")
        unit = spec.get("unit")
        if unit is not None and unit not in UNITS:
            raise ValueError(f"{key}: unit {unit} not in closed set")
        inp = spec.get("input", "USER")
        if inp not in INPUTS:
            raise ValueError(f"{key}: bad input {inp}")
        if inp == "DERIVED" and not spec.get("derive"):
            raise ValueError(f"{key}: DERIVED needs derive")
        out[key] = Variable(key=key, type=t, label=spec["label"], input=inp, unit=unit,
            min=spec.get("min"), max=spec.get("max"), step=spec.get("step"),
            values=tuple(spec.get("values", ())), pattern=spec.get("pattern"),
            derive=spec.get("derive"), help=spec.get("help", ""))
    return Vocabulary(out)
