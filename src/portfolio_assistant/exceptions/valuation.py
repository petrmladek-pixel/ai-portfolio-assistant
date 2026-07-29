"""Custom exceptions for the valuation subsystem."""


class ValuationError(Exception):
    """Raised when valuation of the portfolio fails (e.g., missing prices)."""
