"""Turning a finished run into something to read, and into JSON for the build log."""

from __future__ import annotations

import json
from typing import Any

from .runner import SuiteResult

_COLUMNS = ("case", "pass", "p50", "p95", "cost", "note")


def _row(values: tuple[str, ...], widths: tuple[int, ...]) -> str:
    return "  ".join(
        value.ljust(width) for value, width in zip(values, widths, strict=True)
    ).rstrip()


def to_text(result: SuiteResult, width: int = 120, name_width: int = 44) -> str:
    """A table of one line per case, then a summary line."""
    rows: list[tuple[str, ...]] = []
    for case in result.cases:
        mark = "ok" if case.passed else "FAIL"
        share = f"{case.passed_attempts}/{len(case.attempts)}"
        note = "" if case.passed else case.first_failure
        rows.append(
            (
                case.case.name[:name_width],
                f"{mark} {share}",
                f"{case.latency_ms(0.5):.0f} ms",
                f"{case.latency_ms(0.95):.0f} ms",
                f"${case.cost_usd:.4f}" if case.cost_usd else "-",
                note,
            )
        )

    widths = tuple(
        max(len(_COLUMNS[column]), *(len(row[column]) for row in rows))
        for column in range(len(_COLUMNS))
    )
    note_room = max(24, width - sum(widths[:-1]) - 2 * len(widths))
    widths = (*widths[:-1], min(widths[-1], note_room))

    lines = [_row(_COLUMNS, widths), _row(tuple("-" * w for w in widths), widths)]
    for row in rows:
        trimmed = (*row[:-1], row[-1][: widths[-1]])
        lines.append(_row(trimmed, widths))

    verdict = "PASS" if result.passed else "FAIL"
    lines.append("")
    lines.append(
        f"{verdict}  {len(result.cases) - len(result.failed)}/{len(result.cases)} cases, "
        f"{result.attempts} calls, ${result.cost_usd:.4f}, {result.wall_ms / 1000:.1f} s"
    )
    return "\n".join(lines)


def to_dict(result: SuiteResult) -> dict[str, Any]:
    """The same run as plain data, for a build to store or diff."""
    return {
        "suite": result.suite.name,
        "passed": result.passed,
        "attempts": result.attempts,
        "cost_usd": round(result.cost_usd, 6),
        "wall_ms": round(result.wall_ms, 1),
        "cases": [
            {
                "name": case.case.name,
                "tags": case.case.tags,
                "passed": case.passed,
                "pass_rate": round(case.pass_rate, 4),
                "threshold": case.case.threshold,
                "attempts": len(case.attempts),
                "latency_p50_ms": round(case.latency_ms(0.5), 1),
                "latency_p95_ms": round(case.latency_ms(0.95), 1),
                "cost_usd": round(case.cost_usd, 6),
                "failures": [
                    {"attempt": attempt.index, "reason": attempt.first_failure}
                    for attempt in case.attempts
                    if not attempt.passed
                ],
            }
            for case in result.cases
        ],
    }


def to_json(result: SuiteResult, indent: int = 2) -> str:
    return json.dumps(to_dict(result), indent=indent, ensure_ascii=False)
