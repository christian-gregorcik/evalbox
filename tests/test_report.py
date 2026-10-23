import json

from evalbox import report
from evalbox.response import Response
from evalbox.runner import run
from evalbox.suite import parse

SUITE = parse(
    {
        "name": "demo",
        "cases": [
            {"name": "greets", "prompt": "hi", "repeat": 2, "checks": [{"equals": "hi"}]},
            {"name": "refuses", "prompt": "hi", "checks": [{"equals": "no"}], "tags": ["safety"]},
        ],
    }
)


def passing_model(prompt):
    return Response(text="hi", cost_usd=0.001)


def test_text_report_marks_the_failing_case():
    text = report.to_text(run(SUITE, passing_model))
    assert "greets" in text
    assert "FAIL" in text
    assert text.strip().splitlines()[-1].startswith("FAIL")


def test_text_report_says_pass_when_everything_passes():
    suite = parse({"cases": [{"name": "a", "prompt": "hi", "checks": [{"equals": "hi"}]}]})
    text = report.to_text(run(suite, passing_model))
    assert text.strip().splitlines()[-1].startswith("PASS")


def test_the_note_column_is_trimmed_to_the_width():
    suite = parse({"cases": [{"name": "a", "prompt": "hi", "checks": [{"equals": "x" * 500}]}]})
    for line in report.to_text(run(suite, passing_model), width=90).splitlines():
        assert len(line) <= 120


def test_json_report_has_every_case():
    data = json.loads(report.to_json(run(SUITE, passing_model)))
    assert data["suite"] == "demo"
    assert data["passed"] is False
    assert [case["name"] for case in data["cases"]] == ["greets", "refuses"]
    assert data["cases"][0]["attempts"] == 2
    assert data["cases"][1]["tags"] == ["safety"]


def test_json_report_lists_the_failures():
    data = report.to_dict(run(SUITE, passing_model))
    failures = data["cases"][1]["failures"]
    assert len(failures) == 1
    assert "expected 'no'" in failures[0]["reason"]


def test_json_report_counts_cost():
    data = report.to_dict(run(SUITE, passing_model))
    assert data["cost_usd"] == 0.003
