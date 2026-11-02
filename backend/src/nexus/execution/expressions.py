"""A small declarative language for conditions and templates. It is parsed here and never
reaches eval, so a workflow file cannot run code through a condition."""

import json
import re
from dataclasses import dataclass
from typing import Any

MAX_LENGTH = 500
_TOKEN = re.compile(
    r"""\s*(?:
      (?P<number>\d+(?:\.\d+)?)
    | (?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')
    | (?P<name>[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)*)
    | (?P<op>==|!=|>=|<=|>|<|\(|\))
    )""",
    re.VERBOSE,
)
_KEYWORDS = {"and", "or", "not", "in", "contains", "true", "false", "null"}
_TEMPLATE = re.compile(r"\{\{(.+?)\}\}")


class ExpressionError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str


def _tokenize(source: str) -> list[Token]:
    if len(source) > MAX_LENGTH:
        raise ExpressionError(f"Expression is longer than {MAX_LENGTH} characters")
    tokens: list[Token] = []
    position = 0
    stripped = source.rstrip()
    while position < len(stripped):
        match = _TOKEN.match(stripped, position)
        if match is None:
            raise ExpressionError(f"Unexpected text at position {position}: {source[position:]!r}")
        kind = match.lastgroup or ""
        value = match.group(kind)
        if kind == "name" and value in _KEYWORDS:
            kind = "keyword"
        tokens.append(Token(kind, value))
        position = match.end()
    if not tokens:
        raise ExpressionError("Expression is empty")
    return tokens


def _compare(operator: str, left: Any, right: Any) -> bool:
    if operator == "==":
        return left == right
    if operator == "!=":
        return left != right
    if operator == "in":
        return left in right if right is not None else False
    if operator == "contains":
        return right in left if left is not None else False
    if left is None or right is None:
        return False
    match operator:
        case ">":
            return left > right
        case "<":
            return left < right
        case ">=":
            return left >= right
        case "<=":
            return left <= right
    raise ExpressionError(f"Unknown operator {operator}")


def _resolve(path: str, scope: dict[str, Any]) -> Any:
    first, *rest = path.split(".")
    if first in scope:
        current = scope[first]
    else:
        # Bare names read from the node's input, so `score > 0.8` works.
        source = scope.get("input")
        current = source.get(first) if isinstance(source, dict) else None
    for part in rest:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


class _Parser:
    def __init__(self, tokens: list[Token], scope: dict[str, Any] | None) -> None:
        self.tokens = tokens
        self.position = 0
        # Without a scope this only checks syntax, so validation can run it on any workflow.
        self.scope = scope

    def peek(self) -> Token | None:
        return self.tokens[self.position] if self.position < len(self.tokens) else None

    def accept(self, *values: str) -> str | None:
        token = self.peek()
        if token and token.kind in ("keyword", "op") and token.value in values:
            self.position += 1
            return token.value
        return None

    def parse(self) -> Any:
        value = self.parse_or()
        if self.peek() is not None:
            raise ExpressionError(f"Unexpected {self.peek().value!r}")
        return value

    def parse_or(self) -> Any:
        value = self.parse_and()
        while self.accept("or"):
            right = self.parse_and()
            value = bool(value) or bool(right)
        return value

    def parse_and(self) -> Any:
        value = self.parse_not()
        while self.accept("and"):
            right = self.parse_not()
            value = bool(value) and bool(right)
        return value

    def parse_not(self) -> Any:
        if self.accept("not"):
            return not self.parse_not()
        return self.parse_comparison()

    def parse_comparison(self) -> Any:
        value = self.parse_primary()
        operator = self.accept("==", "!=", ">=", "<=", ">", "<", "in", "contains")
        if operator is None:
            return value
        right = self.parse_primary()
        if self.scope is None:
            return True
        try:
            return _compare(operator, value, right)
        except TypeError as error:
            raise ExpressionError(f"Cannot compare with {operator}: {error}") from error

    def parse_primary(self) -> Any:
        token = self.peek()
        if token is None:
            raise ExpressionError("Expression ends too early")
        self.position += 1
        if token.kind == "number":
            return float(token.value) if "." in token.value else int(token.value)
        if token.kind == "string":
            return re.sub(r"\\(.)", r"\1", token.value[1:-1])
        if token.kind == "name":
            return None if self.scope is None else _resolve(token.value, self.scope)
        if token.value in ("true", "false", "null"):
            return {"true": True, "false": False, "null": None}[token.value]
        if token.value == "(":
            value = self.parse_or()
            if not self.accept(")"):
                raise ExpressionError("Missing )")
            return value
        raise ExpressionError(f"Unexpected {token.value!r}")


def check_syntax(source: str) -> None:
    _Parser(_tokenize(source), None).parse()


def evaluate(source: str, scope: dict[str, Any]) -> Any:
    return _Parser(_tokenize(source), scope).parse()


def _render(value: Any, scope: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _render(item, scope) for key, item in value.items()}
    if isinstance(value, list):
        return [_render(item, scope) for item in value]
    if not isinstance(value, str):
        return value
    whole = _TEMPLATE.fullmatch(value.strip())
    if whole:
        return evaluate(whole.group(1), scope)

    def substitute(match: re.Match[str]) -> str:
        result = evaluate(match.group(1), scope)
        return result if isinstance(result, str) else json.dumps(result)

    return _TEMPLATE.sub(substitute, value)


def render_template(template: str, scope: dict[str, Any]) -> Any:
    """Fills {{expression}} slots in a JSON template, or in plain text when it is not JSON."""
    try:
        document = json.loads(template)
    except json.JSONDecodeError:
        document = template
    return _render(document, scope)
