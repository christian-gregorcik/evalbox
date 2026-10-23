"""Reading a suite file and turning it into something runnable.

Everything is validated here, before the first call to a model. A suite that is going
to fail on a misspelled check should fail in the first second, not after it has spent
ten minutes and real money.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .checks import Check, build
from .errors import SuiteError

DEFAULT_REPEAT = 1
DEFAULT_THRESHOLD = 1.0


@dataclass(frozen=True)
class Case:
    name: str
    prompt: str
    repeat: int
    threshold: float
    checks: list[Check] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Suite:
    name: str
    cases: list[Case]

    @property
    def total_attempts(self) -> int:
        return sum(case.repeat for case in self.cases)


def load(path: str | Path) -> Suite:
    """Read a suite from a YAML file."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SuiteError(str(exc), str(path)) from None
    return parse(raw, source=str(path))


def parse(raw: Any, source: str = "suite") -> Suite:
    """Turn an already-parsed mapping into a suite."""
    if not isinstance(raw, dict):
        raise SuiteError("the file must hold a mapping at the top level", source)

    name = str(raw.get("name") or Path(source).stem)
    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise SuiteError("defaults must be a mapping", source)

    raw_cases = raw.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise SuiteError("the suite needs a non-empty list of cases", source)

    seen: set[str] = set()
    cases: list[Case] = []
    for position, entry in enumerate(raw_cases, start=1):
        case = _parse_case(entry, defaults, f"{source}: case {position}")
        if case.name in seen:
            raise SuiteError(f"two cases are called {case.name!r}", source)
        seen.add(case.name)
        cases.append(case)
    return Suite(name=name, cases=cases)


def _parse_case(entry: Any, defaults: dict[str, Any], where: str) -> Case:
    if not isinstance(entry, dict):
        raise SuiteError("a case must be a mapping", where)

    prompt = entry.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise SuiteError("a case needs a prompt", where)

    name = str(entry.get("name") or prompt.strip().splitlines()[0][:60])
    where = f"{where} ({name})"

    repeat = _positive_int(
        entry.get("repeat", defaults.get("repeat", DEFAULT_REPEAT)), "repeat", where
    )
    threshold = _fraction(
        entry.get("threshold", defaults.get("threshold", DEFAULT_THRESHOLD)), "threshold", where
    )

    raw_checks = entry.get("checks")
    if not isinstance(raw_checks, list) or not raw_checks:
        raise SuiteError("a case needs at least one check", where)

    checks = [
        _parse_check(item, f"{where} check {n}") for n, item in enumerate(raw_checks, start=1)
    ]

    tags = entry.get("tags") or []
    if not isinstance(tags, list):
        raise SuiteError("tags must be a list", where)

    return Case(
        name=name,
        prompt=prompt,
        repeat=repeat,
        threshold=threshold,
        checks=checks,
        tags=[str(tag) for tag in tags],
    )


def _parse_check(item: Any, where: str) -> Check:
    if isinstance(item, str):
        return build(item, None, where)
    if isinstance(item, dict):
        if len(item) != 1:
            raise SuiteError("each check is one entry; write them as separate list items", where)
        ((check_name, config),) = item.items()
        return build(str(check_name), config, where)
    raise SuiteError(f"a check is a name or a one-key mapping, got {type(item).__name__}", where)


def _positive_int(value: Any, field_name: str, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SuiteError(f"{field_name} must be a whole number of 1 or more, got {value!r}", where)
    return value


def _fraction(value: Any, field_name: str, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SuiteError(f"{field_name} must be a number between 0 and 1, got {value!r}", where)
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise SuiteError(f"{field_name} must be between 0 and 1, got {number}", where)
    return number
