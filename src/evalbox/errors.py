"""Errors raised while loading or running a suite."""


class EvalboxError(Exception):
    """Base class for every error this package raises on purpose."""


class SuiteError(EvalboxError):
    """The suite file is missing something, or says something that cannot be run."""

    def __init__(self, message: str, where: str | None = None) -> None:
        super().__init__(f"{where}: {message}" if where else message)
        self.where = where


class UnknownCheckError(SuiteError):
    """A case asks for a check that is not registered."""


class CheckConfigError(SuiteError):
    """A check was given arguments it cannot work with."""


class ModelImportError(EvalboxError):
    """The model given on the command line could not be imported or is not callable."""
