"""The checks a case can run against one answer.

A check is built once, when the suite is loaded, and called once per attempt. Building
it early means a suite with a typo in it fails before a single token is paid for.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .errors import CheckConfigError, UnknownCheckError
from .response import CheckResult


@dataclass(frozen=True)
class Observation:
    """Everything a check is allowed to look at."""

    text: str
    latency_ms: float
    cost_usd: float | None


Check = Callable[[Observation], CheckResult]
Builder = Callable[[Any, str], Check]

_BUILDERS: dict[str, Builder] = {}


def builder(name: str) -> Callable[[Builder], Builder]:
    def register(fn: Builder) -> Builder:
        _BUILDERS[name] = fn
        return fn

    return register


def build(name: str, config: Any, where: str) -> Check:
    """Turn one entry from a case's ``checks`` list into a callable."""
    try:
        make = _BUILDERS[name]
    except KeyError:
        known = ", ".join(sorted(_BUILDERS))
        raise UnknownCheckError(
            f"unknown check {name!r}; known checks are {known}", where
        ) from None
    return make(config, where)


def known_checks() -> list[str]:
    return sorted(_BUILDERS)


def _as_mapping(config: Any, name: str, where: str) -> dict[str, Any]:
    if config is None:
        return {}
    if not isinstance(config, dict):
        raise CheckConfigError(
            f"{name} expects a mapping of options, got {type(config).__name__}", where
        )
    return config


def _require(config: dict[str, Any], key: str, name: str, where: str) -> Any:
    if key not in config:
        raise CheckConfigError(f"{name} needs {key!r}", where)
    return config[key]


def _number(value: Any, name: str, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CheckConfigError(f"{name} needs a number, got {value!r}", where)
    return float(value)


@builder("equals")
def _equals(config: Any, where: str) -> Check:
    options = config if isinstance(config, dict) else {"value": config}
    options = _as_mapping(options, "equals", where)
    expected = str(_require(options, "value", "equals", where))
    ignore_case = bool(options.get("ignore_case", False))
    strip = bool(options.get("strip", True))

    def run(observation: Observation) -> CheckResult:
        actual = observation.text.strip() if strip else observation.text
        wanted = expected.strip() if strip else expected
        if ignore_case:
            actual, wanted = actual.lower(), wanted.lower()
        if actual == wanted:
            return CheckResult("equals", True)
        return CheckResult("equals", False, f"expected {wanted!r}, got {actual[:120]!r}")

    return run


@builder("contains")
def _contains(config: Any, where: str) -> Check:
    options = _as_mapping(
        config if isinstance(config, dict) else {"value": config}, "contains", where
    )
    needle = str(_require(options, "value", "contains", where))
    ignore_case = bool(options.get("ignore_case", False))

    def run(observation: Observation) -> CheckResult:
        haystack = observation.text.lower() if ignore_case else observation.text
        wanted = needle.lower() if ignore_case else needle
        if wanted in haystack:
            return CheckResult("contains", True)
        return CheckResult("contains", False, f"{needle!r} not in answer")

    return run


@builder("not_contains")
def _not_contains(config: Any, where: str) -> Check:
    inner = _contains(config, where)

    def run(observation: Observation) -> CheckResult:
        result = inner(observation)
        if result.passed:
            return CheckResult("not_contains", False, "forbidden text was present")
        return CheckResult("not_contains", True)

    return run


_FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}


@builder("regex")
def _regex(config: Any, where: str) -> Check:
    options = config if isinstance(config, dict) else {"pattern": config}
    options = _as_mapping(options, "regex", where)
    pattern = str(_require(options, "pattern", "regex", where))
    flags = 0
    for letter in str(options.get("flags", "")):
        if letter not in _FLAGS:
            raise CheckConfigError(f"regex: unknown flag {letter!r}, use any of ims", where)
        flags |= _FLAGS[letter]
    try:
        compiled = re.compile(pattern, flags)
    except re.error as exc:
        raise CheckConfigError(f"regex: {exc}", where) from None

    def run(observation: Observation) -> CheckResult:
        if compiled.search(observation.text):
            return CheckResult("regex", True)
        return CheckResult("regex", False, f"no match for {pattern!r}")

    return run


def _parse_json(text: str) -> tuple[Any, str | None]:
    try:
        return json.loads(text), None
    except ValueError as exc:
        return None, str(exc)


@builder("json_valid")
def _json_valid(config: Any, where: str) -> Check:
    _as_mapping(config, "json_valid", where)

    def run(observation: Observation) -> CheckResult:
        _, error = _parse_json(observation.text)
        if error is None:
            return CheckResult("json_valid", True)
        return CheckResult("json_valid", False, error)

    return run


@builder("json_schema")
def _json_schema(config: Any, where: str) -> Check:
    options = _as_mapping(config, "json_schema", where)
    schema = _require(options, "schema", "json_schema", where)
    try:
        import jsonschema
    except ImportError:
        raise CheckConfigError(
            "json_schema needs the jsonschema package; install evalbox[schema]", where
        ) from None
    try:
        validator_for = jsonschema.validators.validator_for(schema)
        validator_for.check_schema(schema)
        validator = validator_for(schema)
    except jsonschema.exceptions.SchemaError as exc:
        raise CheckConfigError(f"json_schema: {exc.message}", where) from None

    def run(observation: Observation) -> CheckResult:
        value, error = _parse_json(observation.text)
        if error is not None:
            return CheckResult("json_schema", False, f"not json: {error}")
        problems = sorted(validator.iter_errors(value), key=lambda e: list(e.path))
        if not problems:
            return CheckResult("json_schema", True)
        first = problems[0]
        path = "/".join(str(part) for part in first.path) or "(root)"
        return CheckResult("json_schema", False, f"{path}: {first.message}")

    return run


def _walk(value: Any, path: str) -> tuple[Any, bool]:
    """Follow a dotted path. Digits index into lists. Returns (value, found)."""
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.lstrip("-").isdigit():
            index = int(part)
            if not -len(current) <= index < len(current):
                return None, False
            current = current[index]
        else:
            return None, False
    return current, True


@builder("json_field")
def _json_field(config: Any, where: str) -> Check:
    options = _as_mapping(config, "json_field", where)
    path = str(_require(options, "path", "json_field", where))
    has_equals = "equals" in options
    expected = options.get("equals")
    must_exist = bool(options.get("exists", True))
    if not has_equals and not must_exist:
        raise CheckConfigError("json_field: give it equals, or leave exists true", where)

    def run(observation: Observation) -> CheckResult:
        value, error = _parse_json(observation.text)
        if error is not None:
            return CheckResult("json_field", False, f"not json: {error}")
        found_value, found = _walk(value, path)
        if not found:
            return CheckResult("json_field", False, f"{path} is missing")
        if has_equals and found_value != expected:
            return CheckResult(
                "json_field", False, f"{path} is {found_value!r}, expected {expected!r}"
            )
        return CheckResult("json_field", True)

    return run


@builder("max_latency_ms")
def _max_latency(config: Any, where: str) -> Check:
    limit = _number(config, "max_latency_ms", where)

    def run(observation: Observation) -> CheckResult:
        if observation.latency_ms <= limit:
            return CheckResult("max_latency_ms", True)
        return CheckResult(
            "max_latency_ms", False, f"{observation.latency_ms:.0f} ms over {limit:.0f} ms"
        )

    return run


@builder("max_cost_usd")
def _max_cost(config: Any, where: str) -> Check:
    limit = _number(config, "max_cost_usd", where)

    def run(observation: Observation) -> CheckResult:
        if observation.cost_usd is None:
            return CheckResult("max_cost_usd", False, "the model reported no cost")
        if observation.cost_usd <= limit:
            return CheckResult("max_cost_usd", True)
        return CheckResult("max_cost_usd", False, f"{observation.cost_usd:.4f} over {limit:.4f}")

    return run


@builder("length")
def _length(config: Any, where: str) -> Check:
    options = _as_mapping(config, "length", where)
    low = _number(options.get("min", 0), "length.min", where)
    high = options.get("max")
    ceiling = _number(high, "length.max", where) if high is not None else None
    if ceiling is not None and ceiling < low:
        raise CheckConfigError("length: max is below min", where)

    def run(observation: Observation) -> CheckResult:
        size = len(observation.text)
        if size < low:
            return CheckResult("length", False, f"{size} characters, needs at least {low:.0f}")
        if ceiling is not None and size > ceiling:
            return CheckResult("length", False, f"{size} characters, allowed at most {ceiling:.0f}")
        return CheckResult("length", True)

    return run
