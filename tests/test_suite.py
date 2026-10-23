import pytest
import yaml

from evalbox.errors import SuiteError, UnknownCheckError
from evalbox.suite import load, parse

MINIMAL = {
    "name": "demo",
    "cases": [{"name": "greets", "prompt": "say hi", "checks": ["json_valid"]}],
}


def test_a_minimal_suite_loads():
    suite = parse(MINIMAL)
    assert suite.name == "demo"
    assert len(suite.cases) == 1
    assert suite.cases[0].repeat == 1
    assert suite.cases[0].threshold == 1.0


def test_defaults_apply_to_every_case():
    suite = parse({"defaults": {"repeat": 4, "threshold": 0.75}, "cases": MINIMAL["cases"]})
    assert suite.cases[0].repeat == 4
    assert suite.cases[0].threshold == 0.75
    assert suite.total_attempts == 4


def test_a_case_overrides_the_default():
    raw = {"defaults": {"repeat": 4}, "cases": [{**MINIMAL["cases"][0], "repeat": 2}]}
    assert parse(raw).cases[0].repeat == 2


def test_the_name_falls_back_to_the_first_line_of_the_prompt():
    raw = {"cases": [{"prompt": "summarise this\nin one line", "checks": ["json_valid"]}]}
    assert parse(raw).cases[0].name == "summarise this"


def test_the_top_level_must_be_a_mapping():
    with pytest.raises(SuiteError):
        parse(["case"])


def test_an_empty_suite_is_refused():
    with pytest.raises(SuiteError, match="non-empty"):
        parse({"cases": []})


def test_a_case_needs_a_prompt():
    with pytest.raises(SuiteError, match="prompt"):
        parse({"cases": [{"checks": ["json_valid"]}]})


def test_a_case_needs_a_check():
    with pytest.raises(SuiteError, match="at least one check"):
        parse({"cases": [{"prompt": "hi", "checks": []}]})


def test_duplicate_case_names_are_refused():
    case = MINIMAL["cases"][0]
    with pytest.raises(SuiteError, match="two cases"):
        parse({"cases": [case, dict(case)]})


def test_repeat_must_be_a_positive_whole_number():
    with pytest.raises(SuiteError, match="repeat"):
        parse({"cases": [{**MINIMAL["cases"][0], "repeat": 0}]})


def test_threshold_must_be_a_fraction():
    with pytest.raises(SuiteError, match="threshold"):
        parse({"cases": [{**MINIMAL["cases"][0], "threshold": 1.5}]})


def test_a_check_with_two_keys_is_refused():
    raw = {"cases": [{"prompt": "hi", "checks": [{"contains": "a", "regex": "b"}]}]}
    with pytest.raises(SuiteError, match="separate list items"):
        parse(raw)


def test_a_misspelled_check_fails_at_load_time():
    with pytest.raises(UnknownCheckError):
        parse({"cases": [{"prompt": "hi", "checks": ["json_vaild"]}]})


def test_the_error_says_which_case_is_wrong():
    raw = {
        "cases": [
            MINIMAL["cases"][0],
            {"name": "second", "prompt": "hi", "checks": ["nope"]},
        ]
    }
    with pytest.raises(UnknownCheckError, match="second"):
        parse(raw)


def test_load_reads_a_file(tmp_path):
    path = tmp_path / "suite.yaml"
    path.write_text(yaml.safe_dump(MINIMAL), encoding="utf-8")
    assert load(path).name == "demo"


def test_load_reports_broken_yaml(tmp_path):
    path = tmp_path / "suite.yaml"
    path.write_text("cases: [\n", encoding="utf-8")
    with pytest.raises(SuiteError):
        load(path)
