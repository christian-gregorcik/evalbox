"""The command line: ``evalbox suite.yaml --model mypackage.models:answer``."""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

from . import report, runner, suite
from .errors import EvalboxError, ModelImportError

EXIT_OK = 0
EXIT_FAILED_CASES = 1
EXIT_BAD_USAGE = 2


def load_model(reference: str) -> runner.Model:
    """Import ``package.module:attribute`` and hand back the callable it names."""
    module_name, separator, attribute = reference.partition(":")
    if not separator or not module_name or not attribute:
        raise ModelImportError(f"write the model as module:attribute, got {reference!r}")
    if str(Path.cwd()) not in sys.path:
        sys.path.insert(0, str(Path.cwd()))
    try:
        module = importlib.import_module(module_name)
    except ImportError as exc:
        raise ModelImportError(f"cannot import {module_name!r}: {exc}") from None
    try:
        model = getattr(module, attribute)
    except AttributeError:
        raise ModelImportError(f"{module_name!r} has no attribute {attribute!r}") from None
    if not callable(model):
        raise ModelImportError(f"{reference} is not callable")
    return model


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evalbox",
        description="Run a suite of checks against a language model.",
    )
    parser.add_argument("suite", help="path to the suite file")
    parser.add_argument(
        "--model",
        required=True,
        metavar="MODULE:ATTR",
        help="the callable to test, for example myapp.models:answer",
    )
    parser.add_argument(
        "--workers", type=int, default=4, help="calls to keep in flight (default 4)"
    )
    parser.add_argument("--json", metavar="PATH", help="also write the run as JSON")
    parser.add_argument("--quiet", action="store_true", help="print nothing but the summary line")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.workers < 1:
        parser.error("--workers must be at least 1")

    try:
        cases = suite.load(args.suite)
        model = load_model(args.model)
    except (EvalboxError, OSError) as exc:
        print(f"evalbox: {exc}", file=sys.stderr)
        return EXIT_BAD_USAGE

    result = runner.run(cases, model, workers=args.workers)

    text = report.to_text(result)
    if args.quiet:
        text = text.rsplit("\n", 1)[-1]
    print(text)

    if args.json:
        Path(args.json).write_text(report.to_json(result) + "\n", encoding="utf-8")

    return EXIT_OK if result.passed else EXIT_FAILED_CASES


if __name__ == "__main__":
    raise SystemExit(main())
