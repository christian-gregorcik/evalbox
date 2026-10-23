"""Run a suite of checks against a language model and fail the build when it regresses."""

from .checks import Observation, known_checks
from .errors import CheckConfigError, EvalboxError, SuiteError, UnknownCheckError
from .report import to_dict, to_json, to_text
from .response import Attempt, CheckResult, Response
from .runner import CaseResult, SuiteResult, run
from .suite import Case, Suite, load, parse

__all__ = [
    "Attempt",
    "Case",
    "CaseResult",
    "CheckConfigError",
    "CheckResult",
    "EvalboxError",
    "Observation",
    "Response",
    "Suite",
    "SuiteError",
    "SuiteResult",
    "UnknownCheckError",
    "known_checks",
    "load",
    "parse",
    "run",
    "to_dict",
    "to_json",
    "to_text",
]
__version__ = "0.1.0"
