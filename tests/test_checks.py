import pytest

from evalbox.checks import Observation, build, known_checks
from evalbox.errors import CheckConfigError, UnknownCheckError


def seen(text, latency_ms=10.0, cost_usd=None):
    return Observation(text=text, latency_ms=latency_ms, cost_usd=cost_usd)


def test_unknown_check_names_the_ones_that_exist():
    with pytest.raises(UnknownCheckError) as caught:
        build("spelled_wrong", None, "suite")
    assert "json_valid" in str(caught.value)
    assert "spelled_wrong" in str(caught.value)


def test_known_checks_are_sorted_and_unique():
    names = known_checks()
    assert names == sorted(set(names))


def test_equals_trims_by_default():
    check = build("equals", {"value": "42"}, "suite")
    assert check(seen("  42\n")).passed


def test_equals_can_keep_whitespace():
    check = build("equals", {"value": "42", "strip": False}, "suite")
    assert not check(seen(" 42")).passed


def test_equals_accepts_a_bare_value():
    assert build("equals", "yes", "suite")(seen("yes")).passed


def test_equals_reports_what_it_wanted():
    result = build("equals", {"value": "yes"}, "suite")(seen("no"))
    assert not result.passed
    assert "'yes'" in result.detail


def test_contains_ignoring_case():
    check = build("contains", {"value": "Total", "ignore_case": True}, "suite")
    assert check(seen("the total is 10")).passed


def test_not_contains_is_the_inverse():
    check = build("not_contains", "sorry", "suite")
    assert check(seen("here you go")).passed
    assert not check(seen("sorry, I cannot")).passed


def test_regex_with_flags():
    check = build("regex", {"pattern": "^total", "flags": "im"}, "suite")
    assert check(seen("line one\nTotal: 5")).passed


def test_regex_rejects_an_unknown_flag():
    with pytest.raises(CheckConfigError):
        build("regex", {"pattern": "a", "flags": "x"}, "suite")


def test_regex_rejects_a_broken_pattern():
    with pytest.raises(CheckConfigError):
        build("regex", {"pattern": "("}, "suite")


def test_json_valid():
    check = build("json_valid", None, "suite")
    assert check(seen('{"a": 1}')).passed
    assert not check(seen("{a: 1}")).passed


def test_json_field_reads_a_dotted_path():
    check = build("json_field", {"path": "order.lines.0.sku", "equals": "A1"}, "suite")
    assert check(seen('{"order": {"lines": [{"sku": "A1"}]}}')).passed


def test_json_field_reports_a_missing_path():
    check = build("json_field", {"path": "order.total"}, "suite")
    result = check(seen('{"order": {}}'))
    assert not result.passed
    assert "order.total" in result.detail


def test_json_field_handles_a_negative_index():
    check = build("json_field", {"path": "items.-1", "equals": "last"}, "suite")
    assert check(seen('{"items": ["first", "last"]}')).passed


def test_json_field_needs_something_to_assert():
    with pytest.raises(CheckConfigError):
        build("json_field", {"path": "a", "exists": False}, "suite")


def test_json_schema_passes_and_fails():
    schema = {"type": "object", "required": ["total"], "properties": {"total": {"type": "number"}}}
    check = build("json_schema", {"schema": schema}, "suite")
    assert check(seen('{"total": 10}')).passed
    bad = check(seen('{"total": "ten"}'))
    assert not bad.passed
    assert "total" in bad.detail


def test_json_schema_rejects_a_broken_schema():
    with pytest.raises(CheckConfigError):
        build("json_schema", {"schema": {"type": "not-a-type"}}, "suite")


def test_max_latency():
    check = build("max_latency_ms", 100, "suite")
    assert check(seen("hi", latency_ms=50)).passed
    assert not check(seen("hi", latency_ms=150)).passed


def test_max_cost_fails_when_the_model_reports_nothing():
    check = build("max_cost_usd", 0.01, "suite")
    assert not check(seen("hi")).passed
    assert check(seen("hi", cost_usd=0.001)).passed


def test_length_bounds():
    check = build("length", {"min": 2, "max": 4}, "suite")
    assert check(seen("abc")).passed
    assert not check(seen("a")).passed
    assert not check(seen("abcde")).passed


def test_length_rejects_a_max_below_min():
    with pytest.raises(CheckConfigError):
        build("length", {"min": 5, "max": 2}, "suite")


def test_a_check_that_wants_a_mapping_says_so():
    with pytest.raises(CheckConfigError):
        build("json_field", ["path"], "suite")
