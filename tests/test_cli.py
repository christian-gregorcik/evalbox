import json
import sys

import pytest
import yaml

from evalbox import cli
from evalbox.errors import ModelImportError

SUITE = {
    "name": "demo",
    "cases": [{"name": "greets", "prompt": "hi", "checks": [{"equals": "hi"}]}],
}


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    (tmp_path / "suite.yaml").write_text(yaml.safe_dump(SUITE), encoding="utf-8")
    (tmp_path / "fake_model.py").write_text(
        "def answer(prompt):\n"
        "    return 'hi'\n\n\n"
        "def wrong(prompt):\n"
        "    return 'bye'\n\n\n"
        "not_callable = 3\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    yield tmp_path
    sys.modules.pop("fake_model", None)


def test_a_passing_run_exits_zero(workspace, capsys):
    assert cli.main(["suite.yaml", "--model", "fake_model:answer"]) == cli.EXIT_OK
    assert "PASS" in capsys.readouterr().out


def test_a_failing_run_exits_one(workspace, capsys):
    assert cli.main(["suite.yaml", "--model", "fake_model:wrong"]) == cli.EXIT_FAILED_CASES
    assert "FAIL" in capsys.readouterr().out


def test_a_missing_suite_exits_two(workspace, capsys):
    assert cli.main(["nope.yaml", "--model", "fake_model:answer"]) == cli.EXIT_BAD_USAGE
    assert "evalbox:" in capsys.readouterr().err


def test_a_missing_model_exits_two(workspace, capsys):
    assert cli.main(["suite.yaml", "--model", "fake_model:missing"]) == cli.EXIT_BAD_USAGE
    assert "missing" in capsys.readouterr().err


def test_quiet_prints_only_the_summary(workspace, capsys):
    cli.main(["suite.yaml", "--model", "fake_model:answer", "--quiet"])
    assert len(capsys.readouterr().out.strip().splitlines()) == 1


def test_json_output_is_written(workspace):
    cli.main(["suite.yaml", "--model", "fake_model:answer", "--json", "report.json"])
    data = json.loads((workspace / "report.json").read_text(encoding="utf-8"))
    assert data["passed"] is True


def test_load_model_needs_a_colon():
    with pytest.raises(ModelImportError, match="module:attribute"):
        cli.load_model("fake_model")


def test_load_model_refuses_something_that_is_not_callable(workspace):
    with pytest.raises(ModelImportError, match="not callable"):
        cli.load_model("fake_model:not_callable")


def test_workers_must_be_positive(workspace):
    with pytest.raises(SystemExit):
        cli.main(["suite.yaml", "--model", "fake_model:answer", "--workers", "0"])
