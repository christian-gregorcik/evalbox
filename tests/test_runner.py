import itertools

import pytest

from evalbox.response import Response
from evalbox.runner import run
from evalbox.suite import parse


def suite_of(checks, repeat=1, threshold=1.0):
    return parse(
        {
            "cases": [
                {
                    "name": "case",
                    "prompt": "hi",
                    "repeat": repeat,
                    "threshold": threshold,
                    "checks": checks,
                }
            ]
        }
    )


def test_a_passing_case():
    result = run(suite_of([{"equals": "hi"}]), lambda prompt: "hi")
    assert result.passed
    assert result.cases[0].pass_rate == 1.0
    assert result.attempts == 1


def test_a_failing_case_keeps_the_reason():
    result = run(suite_of([{"equals": "hi"}]), lambda prompt: "bye")
    assert not result.passed
    assert result.failed[0].case.name == "case"
    assert "expected 'hi'" in result.cases[0].first_failure


def test_the_prompt_reaches_the_model():
    seen = []

    def model(prompt):
        seen.append(prompt)
        return "hi"

    run(suite_of([{"equals": "hi"}]), model)
    assert seen == ["hi"]


def test_a_model_that_raises_fails_the_attempt_without_killing_the_run():
    def model(prompt):
        raise RuntimeError("provider is down")

    result = run(suite_of([{"equals": "hi"}]), model)
    assert not result.passed
    assert "provider is down" in result.cases[0].first_failure
    assert result.cases[0].attempts[0].response is None


def test_a_model_that_returns_the_wrong_type_is_reported():
    result = run(suite_of([{"equals": "hi"}]), lambda prompt: 7)
    assert "expected str or Response" in result.cases[0].first_failure


def test_a_threshold_lets_a_flaky_case_pass():
    answers = itertools.cycle(["hi", "hi", "hi", "bye"])
    result = run(
        suite_of([{"equals": "hi"}], repeat=4, threshold=0.75), lambda p: next(answers), workers=1
    )
    assert result.passed
    assert result.cases[0].pass_rate == 0.75


def test_a_threshold_still_fails_when_it_is_missed():
    answers = itertools.cycle(["hi", "bye"])
    result = run(
        suite_of([{"equals": "hi"}], repeat=4, threshold=0.75), lambda p: next(answers), workers=1
    )
    assert not result.passed


def test_every_repeat_is_run():
    calls = itertools.count()
    run(suite_of([{"equals": "hi"}], repeat=5), lambda p: ("hi", next(calls))[0])
    assert next(calls) == 5


def test_cost_is_summed_across_attempts():
    model = lambda prompt: Response(text="hi", cost_usd=0.002)  # noqa: E731
    result = run(suite_of([{"equals": "hi"}], repeat=3), model)
    assert result.cost_usd == pytest.approx(0.006)


def test_attempts_keep_their_order_even_with_workers():
    answers = {0: "hi"}
    result = run(suite_of([{"equals": "hi"}], repeat=4), lambda p: answers.get(0, "hi"), workers=4)
    assert [attempt.index for attempt in result.cases[0].attempts] == [0, 1, 2, 3]


def test_latency_is_measured():
    result = run(suite_of([{"equals": "hi"}]), lambda p: "hi")
    assert result.cases[0].latency_ms(0.5) >= 0
    assert result.wall_ms > 0


def test_a_listener_sees_each_case_as_it_finishes():
    suite = parse(
        {
            "cases": [
                {"name": "a", "prompt": "x", "checks": [{"equals": "hi"}]},
                {"name": "b", "prompt": "y", "checks": [{"equals": "hi"}]},
            ]
        }
    )
    seen = []
    run(suite, lambda p: "hi", on_case=lambda case: seen.append(case.case.name))
    assert seen == ["a", "b"]


def test_workers_must_be_at_least_one():
    with pytest.raises(ValueError):
        run(suite_of([{"equals": "hi"}]), lambda p: "hi", workers=0)


def test_all_checks_must_pass_for_an_attempt_to_pass():
    checks = [{"contains": "hi"}, {"not_contains": "sorry"}]
    assert run(suite_of(checks), lambda p: "hi there").passed
    assert not run(suite_of(checks), lambda p: "hi, sorry").passed
