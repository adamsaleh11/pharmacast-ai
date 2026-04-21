from __future__ import annotations


class BacktestError(Exception):
    """Base error for backtesting failures."""


class BacktestSchemaError(BacktestError):
    """Raised when an input CSV does not match the expected schema."""


class BacktestLeakageError(BacktestError):
    """Raised when training and actual data overlap."""


