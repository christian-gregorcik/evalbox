"""What a model hands back, and what one attempt at a case produced."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Response:
    """One answer from a model.

    Only ``text`` is required. Fill in ``cost_usd`` and the token counts when the
    provider reports them; the checks that look at cost simply never pass when the
    number is missing, which is better than quietly treating it as free.
    """

    text: str
    cost_usd: float | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None


@dataclass(frozen=True)
class CheckResult:
    """The verdict from a single check."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class Attempt:
    """One call to the model, with everything the report needs afterwards."""

    index: int
    response: Response | None
    latency_ms: float
    error: str | None = None
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.error is None and all(check.passed for check in self.checks)

    @property
    def first_failure(self) -> str:
        if self.error is not None:
            return f"model raised: {self.error}"
        for check in self.checks:
            if not check.passed:
                return f"{check.name}: {check.detail}" if check.detail else check.name
        return ""
