"""Running a suite against a model.

The model is a plain callable that takes a prompt and returns a ``Response`` or a
string. evalbox never talks to a provider itself: that keeps the runner testable, and
it means the same suite works against an API, a local model or a recorded fixture.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from .checks import Observation
from .response import Attempt, Response
from .suite import Case, Suite

Model = Callable[[str], Any]
Listener = Callable[["CaseResult"], None]


@dataclass
class CaseResult:
    case: Case
    attempts: list[Attempt] = field(default_factory=list)

    @property
    def passed_attempts(self) -> int:
        return sum(1 for attempt in self.attempts if attempt.passed)

    @property
    def pass_rate(self) -> float:
        if not self.attempts:
            return 0.0
        return self.passed_attempts / len(self.attempts)

    @property
    def passed(self) -> bool:
        return self.pass_rate >= self.case.threshold

    @property
    def cost_usd(self) -> float:
        return sum(
            attempt.response.cost_usd
            for attempt in self.attempts
            if attempt.response is not None and attempt.response.cost_usd is not None
        )

    def latency_ms(self, quantile: float) -> float:
        return _quantile([attempt.latency_ms for attempt in self.attempts], quantile)

    @property
    def first_failure(self) -> str:
        for attempt in self.attempts:
            if not attempt.passed:
                return attempt.first_failure
        return ""


@dataclass
class SuiteResult:
    suite: Suite
    cases: list[CaseResult]
    wall_ms: float

    @property
    def passed(self) -> bool:
        return all(case.passed for case in self.cases)

    @property
    def failed(self) -> list[CaseResult]:
        return [case for case in self.cases if not case.passed]

    @property
    def cost_usd(self) -> float:
        return sum(case.cost_usd for case in self.cases)

    @property
    def attempts(self) -> int:
        return sum(len(case.attempts) for case in self.cases)


def _quantile(values: Iterable[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    position = quantile * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _coerce(value: Any) -> Response:
    if isinstance(value, Response):
        return value
    if isinstance(value, str):
        return Response(text=value)
    raise TypeError(f"the model returned {type(value).__name__}, expected str or Response")


def _attempt(case: Case, model: Model, index: int) -> Attempt:
    started = time.perf_counter()
    try:
        response = _coerce(model(case.prompt))
    except Exception as exc:  # the suite should report a broken model, not die with it
        elapsed = (time.perf_counter() - started) * 1000
        return Attempt(
            index=index, response=None, latency_ms=elapsed, error=f"{type(exc).__name__}: {exc}"
        )
    elapsed = (time.perf_counter() - started) * 1000
    observation = Observation(text=response.text, latency_ms=elapsed, cost_usd=response.cost_usd)
    return Attempt(
        index=index,
        response=response,
        latency_ms=elapsed,
        checks=[check(observation) for check in case.checks],
    )


def run(
    suite: Suite, model: Model, workers: int = 4, on_case: Listener | None = None
) -> SuiteResult:
    """Run every case, repeating each one as the suite asks, and collect the results."""
    if workers < 1:
        raise ValueError("workers must be at least 1")

    started = time.perf_counter()
    results: list[CaseResult] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for case in suite.cases:
            attempts = list(
                pool.map(lambda index, c=case: _attempt(c, model, index), range(case.repeat))
            )
            attempts.sort(key=lambda attempt: attempt.index)
            result = CaseResult(case=case, attempts=attempts)
            results.append(result)
            if on_case is not None:
                on_case(result)
    wall = (time.perf_counter() - started) * 1000
    return SuiteResult(suite=suite, cases=results, wall_ms=wall)
